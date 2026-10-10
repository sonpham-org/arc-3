// The no-notes queue must not trust the older checklist-only API or failed comment loads.
// Run: node scripts/test_games_review.mjs
import assert from "node:assert/strict";
import fs from "node:fs/promises";

const source = await fs.readFile(new URL("../docs/static/js/games-review.js", import.meta.url), "utf8");
const { createReview } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);

class Element {
  constructor() { this.handlers = {}; this.classList = { add() {} }; }
  addEventListener(name, fn) { this.handlers[name] = fn; }
  append() {}
  appendChild() {}
  replaceChildren() {}
  querySelectorAll() { return []; }
}

function queue(trees, comments) {
  const elements = new Map();
  globalThis.document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, new Element());
      return elements.get(id);
    },
    createElement() { return new Element(); },
  };
  const opened = [], checked = [];
  let refreshes = 0;
  const review = createReview({
    api: {
      async reviewStatus() { refreshes++; return { trees, total: trees.length, reviewed: 0 }; },
      async treeNotes(id) {
        checked.push(id);
        if (comments[id] instanceof Error) throw comments[id];
        return { feedback: comments[id] || [] };
      },
    },
    shortDate: () => "today",
    currentTreeId: () => "here",
    onOpen: (...args) => opened.push(args),
  });
  return { review, opened, checked, elements, refreshes: () => refreshes,
    next: () => elements.get("nextUnreviewedBtn").handlers.click() };
}

const tree = (treeId, reviewed = false) => ({ treeId, reviewed, family: "arena", title: treeId,
  head: { gameId: treeId, versionId: `${treeId}@123456789abc` } });

let q = queue([tree("here"), tree("saved", true), tree("old-notes"), tree("fresh")], {
  "old-notes": [{ versionId: "old-notes@000000000000", liked: "Existing older-version review" }],
});
await q.next();
assert.deepEqual(q.checked, ["old-notes", "fresh"]);
assert.deepEqual(q.opened, [["fresh", "fresh@123456789abc"]]);
assert.equal(q.elements.get("nextUnreviewedBtn").disabled, false);
await q.review.noteSaved();
assert.equal(q.refreshes(), 2); // Posting a comment refreshes the board and progress count.

q = queue([tree("here"), tree("notes")], { notes: [{ comment: "Already reviewed" }] });
await q.next();
assert.deepEqual(q.opened, []);
assert.equal(q.elements.get("reviewProgress").textContent, "Every game is reviewed");

q = queue([tree("here"), tree("fresh")], { fresh: [{ comment: "Spam", hidden: true }, { fun: 4 }] });
await q.next();
assert.equal(q.opened[0][0], "fresh"); // Hidden comments and ratings alone are not notes.

q = queue([tree("here"), tree("unavailable"), tree("fresh")], { unavailable: new Error("offline") });
await q.next();
assert.deepEqual(q.opened, []);
assert.deepEqual(q.checked, ["unavailable"]);
assert.match(q.elements.get("reviewProgress").textContent, /Could not check comments/);
assert.equal(q.elements.get("nextUnreviewedBtn").disabled, false);

console.log("games review queue: ok");

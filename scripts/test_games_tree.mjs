// Layout of the Games page's evolution trees (docs/static/js/games-tree.js).
// Run: node scripts/test_games_tree.mjs
import assert from "node:assert/strict";
import fs from "node:fs/promises";

// Same trick as test_viewer_route.mjs: the site's .js files are browser ES modules, so load
// them from data: URLs, pointing games-tree.js's import of games-api.js at its data: URL too.
const dataUrl = (text) => `data:text/javascript;base64,${Buffer.from(text).toString("base64")}`;
const read = (name) => fs.readFile(new URL(`../docs/static/js/${name}`, import.meta.url), "utf8");
const apiUrl = dataUrl(await read("games-api.js"));
const treeSource = (await read("games-tree.js")).replace(/from "\.\/games-api\.js[^"]*"/, `from "${apiUrl}"`);
const { layoutTree } = await import(dataUrl(treeSource));

const v = (versionId, parentVersionId, kind, extra = {}) => ({ versionId, parentVersionId, kind, ...extra });
const place = (versions) => {
  const { pos, cols, lanes } = layoutTree(versions);
  return { cols, lanes, at: Object.fromEntries([...pos].map(([id, p]) => [id, [p.col, p.lane]])) };
};

// A straight line of revisions runs left to right in one lane.
assert.deepEqual(place([v("a", null, "seed"), v("b", "a", "revision"), v("c", "b", "revision", { isLineHead: true })]), {
  cols: 3,
  lanes: 1,
  at: { a: [0, 0], b: [1, 0], c: [2, 0] },
});

// A branch drops to a lane of its own in the next column.
assert.deepEqual(
  place([v("a", null, "seed"), v("b", "a", "revision", { isLineHead: true }), v("x", "a", "branch", { isLineHead: true })]).at,
  { a: [0, 0], b: [1, 0], x: [1, 1] },
);

// When a game forks, the lane follows the revision that leads to the current version, not
// merely the older one.
assert.deepEqual(
  place([
    v("a", null, "seed"),
    v("old", "a", "revision"),
    v("new", "a", "revision"),
    v("cur", "new", "revision", { isLineHead: true }),
  ]).at,
  { a: [0, 0], new: [1, 0], cur: [2, 0], old: [1, 1] },
);

// Deeper branches hang nearest the main line, so an early branch's edge never crosses a later one.
assert.deepEqual(
  place([
    v("a", null, "seed"),
    v("b", "a", "revision"),
    v("c", "b", "revision"),
    v("d", "c", "revision", { isLineHead: true }),
    v("early", "a", "branch", { isLineHead: true }),
    v("late", "c", "branch", { isLineHead: true }),
  ]).at,
  { a: [0, 0], b: [1, 0], c: [2, 0], d: [3, 0], late: [3, 1], early: [1, 2] },
);

// A version whose parent is not in the list (a hidden game) becomes a root instead of vanishing.
assert.deepEqual(place([v("a", null, "seed"), v("orphan", "gone", "revision")]).at, { a: [0, 0], orphan: [0, 1] });

// Deep chains do not recurse: a thousand versions lay out in one lane.
const chain = [v("n0", null, "seed")];
for (let i = 1; i < 1000; i++) chain.push(v(`n${i}`, `n${i - 1}`, "revision"));
const long = layoutTree(chain);
assert.equal(long.cols, 1000);
assert.equal(long.lanes, 1);

console.log("games-tree layout: ok");

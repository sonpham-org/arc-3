// Author: Claude Opus 5.5 (Bubba)
// Date: 08-October-2026
// PURPOSE: The Games page's trainability review (Son, #arc3-game-ideas-brain-dump, 8-Oct-2026).
//   Three pieces that share one answer from the team-only review-status route
//   (railway/games_store.py review_status):
//   - the Trainable board on the browse view: thumbnails of every game ticked trainable, led by
//     the official games as the starting set (an official game leaves only once someone unticks it);
//   - the sidebar review of the version on screen: the "Trainable" verdict tick and, under it,
//     Son's four-item checklist, each saved per version with who and when;
//   - "Next unreviewed game": the next tree, in board order (official first, then by id), whose
//     current version has no checklist or verdict saved by anyone, plus a reviewed-of-total count.
//   games-play.js owns the player and calls attach() for each version it opens. Signed out, none
//   of this is shown; the API refuses these routes to anyone without a team session.
// SRP/DRY check: Pass -- moved the training tick here from games-play.js rather than writing a
//   second one; reuses games-api.js for every request and games-tree.js's shortDate.

const OFFICIAL = "official";

const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
};

export function createReview({ api, shortDate, onOpen, currentTreeId }) {
  let status = null;
  const $ = (id) => document.getElementById(id);
  const checkboxes = () => [...$("reviewChecks").querySelectorAll("input[data-check]")];

  $("tbNextBtn").addEventListener("click", () => next($("tbNextBtn")));
  $("nextUnreviewedBtn").addEventListener("click", () => next($("nextUnreviewedBtn")));

  async function refresh() {
    try {
      status = await api.reviewStatus();
    } catch (err) {
      status = null;
      $("tbSummary").textContent = `Could not load the review state (${err.message}).`;
      return null;
    }
    paintBoard();
    paintProgress();
    return status;
  }

  function showBoard() {
    $("trainableBoard").hidden = false;
    return refresh();
  }

  // In the box: every official game nobody has unticked (the starting set), then every other
  // game whose latest verdict is "trainable". A ticked game shows the version that was ticked.
  function boardTrees() {
    const trees = status ? status.trees : [];
    const official = trees.filter((t) => t.family === OFFICIAL && !(t.verdict && t.verdict.trainOk === false));
    const ticked = trees.filter((t) => t.family !== OFFICIAL && t.verdict && t.verdict.trainOk);
    return [...official, ...ticked];
  }

  function paintBoard() {
    const grid = $("tbGrid");
    grid.replaceChildren();
    const trees = boardTrees();
    const ticked = trees.filter((t) => t.verdict && t.verdict.trainOk).length;
    const officials = trees.filter((t) => t.family === OFFICIAL).length;
    $("tbSummary").textContent = `${ticked} ticked trainable · the ${officials} official games lead as the starting set · a dot marks a current version nobody has reviewed`;
    for (const tree of trees) {
      const good = !!(tree.verdict && tree.verdict.trainOk);
      const shown = good ? tree.verdict : { ...tree.head, title: tree.title };
      const item = el("button", "tb-item" + (good ? " ticked" : ""));
      item.type = "button";
      item.title = good
        ? `${shown.title} · ticked by ${tree.verdict.trainOkBy || "the team"}${tree.verdict.trainOkAt ? `, ${shortDate(tree.verdict.trainOkAt)}` : ""}`
        : `${shown.title} · starting set, not ticked yet`;
      const img = el("img");
      img.alt = "";
      img.loading = "lazy";
      if (shown.thumbUrl) img.src = shown.thumbUrl;
      else img.classList.add("missing");
      const caption = el("span", "tb-name", shown.title);
      item.append(img, caption);
      if (good) item.appendChild(el("span", "tb-tick", "✓"));
      if (!tree.reviewed) {
        item.classList.add("unreviewed");
        item.title += " · current version unreviewed";
      }
      item.addEventListener("click", () => onOpen(tree.treeId, shown.versionId));
      grid.appendChild(item);
    }
  }

  function paintProgress() {
    const text = status ? `${status.reviewed} of ${status.total} reviewed` : "";
    $("tbProgress").textContent = text;
    $("reviewProgress").textContent = text;
  }

  // The tree after the one on screen, in board order, whose current version nobody has reviewed.
  // Fetched fresh each time so a teammate's reviews from the last few minutes count.
  async function next(button) {
    button.disabled = true;
    try {
      const fresh = await refresh();
      if (!fresh) return;
      const trees = fresh.trees;
      const here = trees.findIndex((t) => t.treeId === currentTreeId());
      for (let step = 1; step <= trees.length; step++) {
        const tree = trees[(here + step + trees.length) % trees.length];
        if (!tree.reviewed && tree.treeId !== currentTreeId()) return onOpen(tree.treeId, tree.head.versionId);
      }
      $("tbProgress").textContent = $("reviewProgress").textContent = "Every game is reviewed";
    } finally {
      button.disabled = false;
    }
  }

  // A save on the version on screen: keep the count honest without another round trip.
  function noteSaved(context, change) {
    if (!status) return;
    const tree = status.trees.find((t) => t.treeId === context.tree.treeId);
    if (!tree) return;
    if (tree.head.versionId === context.version.versionId && !tree.reviewed) {
      tree.reviewed = true;
      status.reviewed += 1;
    }
    if (change.verdict) tree.verdict = { ...change.verdict, title: tree.title, thumbUrl: context.version.thumbUrl };
    paintProgress();
  }

  // The sidebar review of one version: the verdict tick and the checklist under it.
  function attach(context) {
    const versionId = context.version.versionId;
    const notes = context.notes.notes || (context.notes.notes = {});
    const note = () => notes[versionId] || (notes[versionId] = {});
    paintTick(context, note, versionId);
    paintChecks(context, note, versionId);
    if (!status) refresh();
  }

  function paintTick(context, note, versionId) {
    const tick = $("trainOk");
    const who = $("trainWho");
    const paint = () => {
      tick.checked = note().trainOk === true;
      who.textContent = note().trainOk && note().trainOkBy ? `${note().trainOkBy}, ${shortDate(note().trainOkAt)}` : "";
    };
    paint();
    tick.onchange = async () => {
      const good = tick.checked;
      tick.disabled = true;
      tick.blur(); // hand the arrow keys straight back to the game
      try {
        const result = await api.setTrainOk(versionId, good);
        Object.assign(note(), { trainOk: result.trainOk, trainOkBy: result.trainOkBy, trainOkAt: result.trainOkAt });
        paint();
        noteSaved(context, { verdict: { versionId, gameId: result.gameId, trainOk: result.trainOk, trainOkBy: result.trainOkBy, trainOkAt: result.trainOkAt } });
      } catch (err) {
        paint(); // the tick means what the server holds, not what was clicked
        who.textContent = `could not save (${err.message})`;
      } finally {
        tick.disabled = false;
      }
    };
  }

  function paintChecks(context, note, versionId) {
    const who = $("reviewWho");
    const paint = () => {
      const saved = note().reviewChecks || {};
      for (const box of checkboxes()) box.checked = saved[box.dataset.check] === true;
      who.textContent = note().reviewBy ? `${note().reviewBy}, ${shortDate(note().reviewAt)}` : "";
    };
    paint();
    for (const box of checkboxes()) {
      box.onchange = async () => {
        const checks = Object.fromEntries(checkboxes().map((b) => [b.dataset.check, b.checked]));
        const fieldset = $("reviewChecks");
        fieldset.disabled = true;
        box.blur();
        try {
          const result = await api.setReviewChecks(versionId, checks);
          Object.assign(note(), { reviewChecks: result.reviewChecks, reviewBy: result.reviewBy, reviewAt: result.reviewAt });
          paint();
          noteSaved(context, {});
        } catch (err) {
          paint();
          who.textContent = `could not save (${err.message})`;
        } finally {
          fieldset.disabled = false;
        }
      };
    }
  }

  return { showBoard, refresh, attach };
}

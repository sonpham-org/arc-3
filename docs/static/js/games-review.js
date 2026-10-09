// Author: Claude Opus 5.5 (Bubba)
// Date: 09-October-2026
// PURPOSE: The Games page's trainability review (Son, #arc3-game-ideas-brain-dump, 8-Oct-2026;
//   widened to the whole catalog for Son in #arc-3, 9-Oct-2026). Three pieces that share one
//   answer from the team-only review-status route (railway/games_store.py review_status):
//   - the review board on the browse view: a thumbnail of every game tree in the catalog, every
//     family, official first (the server's order), each marked with its review state -- a dot for
//     a current version nobody has reviewed, a green tick for "trainable", a red cross for
//     "untrainable". Family chips, verdict chips and a search box narrow the list; a click opens the
//     game in the player, where the review sits in the left sidebar;
//   - the sidebar review of the version on screen: a two-way Trainable / Untrainable verdict
//     (9-Oct, Son: "have a toggle for Trainable vs. Untrainable"; it replaced a single tick), unset
//     until someone decides and clearable by clicking the chosen side again, then Son's four-item
//     checklist, each saved per version with who and when. The game's comments sit under the
//     checklist in the same box (markup in index.html; games-play.js paints them);
//   - "Next unreviewed game": the next tree, in board order (official first, then by id), whose
//     current version has no checklist or verdict saved by anyone, plus a reviewed-of-total count.
//     It walks every tree, whatever the board's filters show. After any save the review state is
//     reloaded, so the board, its filters, the count and this walk all match the verdict.
//   games-play.js owns the player and calls attach() for each version it opens. Signed out, none
//   of this is shown; the API refuses these routes to anyone without a team session.
// SRP/DRY check: Pass -- the board, filters and review stay in this one module; reuses
//   games-api.js for every request, games-tree.js's shortDate, and games.css's .chip styling for
//   the filters. The verdict saves through the existing train route (trainOk true / false, or null
//   to clear).

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

  // What the board shows: one family ("" = all), one verdict state ("" = all), and a search.
  const filter = { family: "", state: "", q: "" };
  const STATES = [
    ["", "Any state"],
    ["unreviewed", "Unreviewed"],
    ["trainable", "Trainable"],
    ["rejected", "Untrainable"],
    ["noverdict", "No verdict"],
  ];
  const verdictOf = (tree) => (!tree.verdict ? "noverdict" : tree.verdict.trainOk ? "trainable" : "rejected");

  $("tbNextBtn").addEventListener("click", () => next($("tbNextBtn")));
  $("nextUnreviewedBtn").addEventListener("click", () => next($("nextUnreviewedBtn")));
  let debounce = null;
  $("tbSearch").addEventListener("input", (e) => {
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      filter.q = e.target.value.trim().toLowerCase();
      paintBoard();
    }, 200);
  });

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

  const matchesState = (tree) =>
    !filter.state || (filter.state === "unreviewed" ? !tree.reviewed : verdictOf(tree) === filter.state);
  const matchesSearch = (tree) => {
    if (!filter.q) return true;
    const hay = [tree.title, tree.treeId, tree.family, tree.head.gameId, tree.verdict && tree.verdict.title];
    return hay.some((text) => text && String(text).toLowerCase().includes(filter.q));
  };

  // Every tree, in the server's order (official first, then by id), narrowed by the filters.
  function boardTrees() {
    const trees = status ? status.trees : [];
    return trees.filter((t) => (!filter.family || t.family === filter.family) && matchesState(t) && matchesSearch(t));
  }

  function chip(label, count, activeNow, onPick) {
    const node = el("button", "chip" + (activeNow ? " active" : ""));
    node.type = "button";
    node.append(label);
    if (count !== null) node.appendChild(el("span", "n", count));
    node.addEventListener("click", onPick);
    return node;
  }

  // Family chips count every tree in the family; state chips count within the chosen family, so
  // "Unreviewed 12" next to "arena" means twelve arena games are waiting.
  function paintFilters() {
    const trees = status ? status.trees : [];
    const families = {};
    for (const tree of trees) families[tree.family] = (families[tree.family] || 0) + 1;
    const order = Object.keys(families).sort((a, b) =>
      (b === OFFICIAL) - (a === OFFICIAL) || families[b] - families[a] || a.localeCompare(b));
    if (filter.family && !families[filter.family]) filter.family = "";
    $("tbFamilies").replaceChildren(
      chip("All games", trees.length, !filter.family, () => { filter.family = ""; paintBoard(); }),
      ...order.map((family) => chip(family, families[family], filter.family === family, () => { filter.family = family; paintBoard(); })),
    );
    const inFamily = trees.filter((t) => !filter.family || t.family === filter.family);
    const count = (state) => inFamily.filter((t) => (state === "unreviewed" ? !t.reviewed : verdictOf(t) === state)).length;
    $("tbStates").replaceChildren(
      ...STATES.map(([state, label]) => chip(label, state ? count(state) : null, filter.state === state, () => { filter.state = state; paintBoard(); })),
    );
  }

  function paintBoard() {
    paintFilters();
    const grid = $("tbGrid");
    grid.replaceChildren();
    const all = status ? status.trees : [];
    const trees = boardTrees();
    const ticked = all.filter((t) => verdictOf(t) === "trainable").length;
    const rejected = all.filter((t) => verdictOf(t) === "rejected").length;
    $("tbSummary").textContent = `Showing ${trees.length} of ${all.length} games, official first · ${ticked} trainable · ${rejected} untrainable · a dot marks a current version nobody has reviewed`;
    if (!trees.length) grid.appendChild(el("p", "tb-empty", "No games match."));
    for (const tree of trees) {
      const verdict = verdictOf(tree);
      // A game with a verdict shows the version the verdict was given on; otherwise its current version.
      const shown = tree.verdict ? tree.verdict : { ...tree.head, title: tree.title };
      const item = el("button", "tb-item" + (verdict === "trainable" ? " ticked" : verdict === "rejected" ? " rejected" : ""));
      item.type = "button";
      const by = tree.verdict ? `${tree.verdict.trainOkBy || "the team"}${tree.verdict.trainOkAt ? `, ${shortDate(tree.verdict.trainOkAt)}` : ""}` : "";
      item.title = `${shown.title} · ${tree.family} · ` + (verdict === "trainable"
        ? `marked trainable by ${by}`
        : verdict === "rejected" ? `marked untrainable by ${by}` : "no verdict yet");
      const img = el("img");
      img.alt = "";
      img.loading = "lazy";
      if (shown.thumbUrl) img.src = shown.thumbUrl;
      else img.classList.add("missing");
      const caption = el("span", "tb-name", shown.title);
      item.append(img, caption);
      if (verdict === "trainable") item.appendChild(el("span", "tb-tick", "✓"));
      if (verdict === "rejected") item.appendChild(el("span", "tb-tick no", "✕"));
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

  // A save on the version on screen: reload the review state so the board, its filters, the count
  // and "Next unreviewed game" all agree with it (a cleared verdict can hand the tree back to an
  // older version's verdict, or make the current version unreviewed again).
  function noteSaved() {
    refresh();
  }

  // The sidebar review of one version: the verdict toggle and the checklist under it.
  function attach(context) {
    const versionId = context.version.versionId;
    const notes = context.notes.notes || (context.notes.notes = {});
    const note = () => notes[versionId] || (notes[versionId] = {});
    paintTick(context, note, versionId);
    paintChecks(context, note, versionId);
    if (!status) refresh();
  }

  // The verdict: two buttons, Trainable and Untrainable, both off until someone decides. Clicking
  // the side already chosen clears it back to no verdict (the route takes good: null for that).
  function paintTick(context, note, versionId) {
    const seg = $("trainVerdict");
    const buttons = [...seg.querySelectorAll("button[data-verdict]")];
    const who = $("trainWho");
    const paint = () => {
      const verdict = note().trainOk; // true, false, or unset (null / undefined)
      for (const button of buttons) {
        const side = button.dataset.verdict === "true";
        button.setAttribute("aria-pressed", String(verdict === side));
        button.title = verdict === side ? "Click again to clear the verdict" : "";
      }
      who.textContent = typeof verdict === "boolean"
        ? `${verdict ? "Trainable" : "Untrainable"}${note().trainOkBy ? ` · ${note().trainOkBy}` : ""}${note().trainOkAt ? `, ${shortDate(note().trainOkAt)}` : ""}`
        : "No verdict yet";
    };
    paint();
    for (const button of buttons) {
      button.onclick = async () => {
        const side = button.dataset.verdict === "true";
        const good = note().trainOk === side ? null : side;
        buttons.forEach((b) => (b.disabled = true));
        button.blur(); // hand the arrow keys straight back to the game
        try {
          const result = await api.setTrainOk(versionId, good);
          Object.assign(note(), { trainOk: result.trainOk, trainOkBy: result.trainOkBy, trainOkAt: result.trainOkAt });
          paint();
          noteSaved();
        } catch (err) {
          paint(); // the buttons show what the server holds, not what was clicked
          who.textContent = `could not save (${err.message})`;
        } finally {
          buttons.forEach((b) => (b.disabled = false));
        }
      };
    }
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
          noteSaved();
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

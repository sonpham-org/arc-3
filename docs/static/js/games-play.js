// Games tab -- the evolution-tree catalog, the in-browser player, and "Feedback games".
//
// Browse: one row per game tree (games-tree.js), newest evolution first, from the Railway API;
// the static manifest is the fallback when the API or its database is not there.
// Play: any version of any game, loaded by its content-addressed source, so an old version plays
// exactly as it was. Feedback: the same player, moved into the review view (games-feedback.js).
//
// The player itself is the condensed, DB/session/social-free adaptation of the sibling arc-agi-3
// repo's human.js/human-game.js/human-input.js/human-render.js it always was.

// The ?v= is load-bearing: index.html serves this module uncached-busted otherwise, and
// a stale copy in someone's browser silently keeps old behaviour (a fixed game-over
// overlay looked broken for a whole session because of exactly this). Bump on release.
import { ensureGameEngine, gameEngineReady, onEngineProgress, gameLoad, gameStep, gameReset, gameUndo, gameJumpLevel, gameSetTileMode, gameSetFilter } from "./games-engine.js?v=20260830-nocache-catalog";
import * as api from "./games-api.js?v=20260919-ideas";
import { renderTreeRow, openVersionDrawer, closeVersionDrawer, authorBadge, shortDate } from "./games-tree.js?v=20260919-ideas";
import { createFeedback } from "./games-feedback.js?v=20260919-trees";
import { createIdeasBoard } from "./games-ideas.js?v=20260919-ideas";

// Canonical ARC-3 board palette (values 0-15) -- identical to constants.py's
// COLOR_MAP in the reference impl and to scripts/build_games_manifest.py's
// thumbnail generator, so in-browser play matches the static thumbnails.
const COLORS = [
  "#FFFFFF", "#CCCCCC", "#999999", "#666666", "#333333", "#000000", "#E53AA3", "#FF7BCC",
  "#F93C31", "#1E93FF", "#88D8F1", "#FFDC00", "#FF851B", "#921231", "#4FCC30", "#A356D6",
];
const ACTION_NAMES = { 0: "RESET", 1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "ACTION5", 6: "CLICK", 7: "ACTION7" };
// Space is ACTION5, as in ARC's own player and on arc.markbarney.net; left unmapped it scrolled
// the page away from the board (and pressed whichever button had focus).
const KEY_MAP = { w: 1, ArrowUp: 1, s: 2, ArrowDown: 2, a: 3, ArrowLeft: 3, d: 4, ArrowRight: 4, r: 0, z: 5, " ": 5, x: 7, c: 7 };

const PAGE_SIZE = 20;
const LIST_KEY = "arc3-games-list";

let me = null;              // the signed-in team member ({email}), or null for the public
let apiOk = true;           // false once the API has failed: browse the static manifest instead
const list = { family: "", q: "", evolved: false, sort: "recent", offset: 0 };
let listToken = 0;

let current = null;         // the play view's context: { version, tree, detail }
let active = null;          // the version loaded in the player, in either view
let loadToken = 0;
let state = {};             // {grid, state, levels_completed, win_levels, available_actions, tile_scale}
let stepCount = 0;
let tileMode = "solid";     // "solid" | "tiles" | "random" -- see games/arc_tiles.py
let tileSeed = 1;
const telemetry = { actions: 0, resets: 0, undos: 0, seconds: 0 };

// Mirrors frame_filters.py's FILTERS dict (docs/static/games/src/_shared/) -- labels
// and param ranges are duplicated here the same way COLORS/PALETTE already are in
// three other places in this codebase, so this isn't a new kind of drift risk.
const FILTERS = [
  { id: "none", label: "No filter" },
  { id: "palette_shuffle", label: "Palette shuffle", seeded: true },
  { id: "pixel_noise", label: "Pixel noise", seeded: true, param: "rate", min: 0, max: 0.5, step: 0.01, default: 0.05 },
  { id: "color_merge", label: "Color merge", seeded: true, param: "n_groups", min: 2, max: 8, step: 1, default: 4 },
  { id: "palette_cap", label: "Palette cap", seeded: true, param: "max_colors", min: 2, max: 12, step: 1, default: 6 },
  { id: "block_pool", label: "Block pool", seeded: false, param: "factor", min: 2, max: 8, step: 1, default: 2 },
  { id: "fog_mask", label: "Fog", seeded: true, param: "coverage", min: 0, max: 0.9, step: 0.05, default: 0.3 },
];
let filterId = "none";
let filterParams = {};
let filterSeed = 1;
let processing = false;
let liveMode = false;
let liveInterval = null;
let liveFps = 10;
let liveHeldAction = 6;
let liveIdleAction = 6;
let liveMouseX = null;
let liveMouseY = null;

const $ = (id) => document.getElementById(id);
const canvas = () => $("gameCanvas");
const stageVisible = () => !$("playView").hidden || !$("feedbackView").hidden;

// The player, as the Feedback view sees it.
const player = {
  load: (version, options) => loadVersion(version, options || {}),
  telemetry: () => ({
    ...telemetry,
    levelsCompleted: state.levels_completed || 0,
    levelsTotal: state.win_levels ?? null,
    state: state.state || "NOT_FINISHED",
    tileMode,
    filter: filterId,
  }),
  mountStage: (slot) => slot.appendChild($("stage")),
  unmountStage: () => $("playView").appendChild($("stage")),
  stop: () => stopLiveIfRunning(),
};
let feedback = null;

// ── Boot ─────────────────────────────────────────────────────────────────

async function init() {
  onEngineProgress(({ stage, percent }) => updateLoadingUI(stage, percent));
  restoreListState();

  $("backToBrowse").addEventListener("click", showBrowse);
  $("resetBtn").addEventListener("click", () => runAction(() => gameReset(), "(reset)"));
  $("undoBtn").addEventListener("click", doUndo);
  $("liveToggleBtn").addEventListener("click", toggleLive);
  $("liveFpsInput").addEventListener("input", (e) => { liveFps = +e.target.value; restartLiveTick(); });
  $("reviewThisBtn").addEventListener("click", () => current && enterFeedback({ version: current.version }));
  $("feedbackBtn").addEventListener("click", () => enterFeedback());
  $("versionDrawer").querySelector(".drawer-close").addEventListener("click", closeVersionDrawer);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeVersionDrawer(); });
  setupBrowseControls();
  setupTileBar();
  setupFilterBar();
  setupCanvasInput();
  setupKeyboard();
  setInterval(() => { if (active && stageVisible() && !document.hidden) telemetry.seconds += 1; }, 1000);

  // Back from reviewing: redraw the trees so the new feedback counts show.
  feedback = createFeedback({ player, api, getMe: () => me, onExit: () => { listRendered = false; showBrowse(); } });
  me = await api.whoAmI();
  paintWhoAmI();
  if (me) createIdeasBoard({ api, onOpenGame: playGameId }).show();
  window.addEventListener("hashchange", route);
  await route();
}

async function route() {
  const hash = new URLSearchParams(location.hash.replace(/^#/, ""));
  if (location.hash === "#feedback") return enterFeedback();
  if (hash.get("t") && hash.get("v")) return playById(hash.get("t"), hash.get("v"));
  if (hash.get("g")) return playGameId(hash.get("g"));
  showBrowse();
}

function paintWhoAmI() {
  const who = $("whoami");
  who.replaceChildren();
  if (me) {
    who.textContent = `Team · ${me.email}`;
  } else {
    who.append("Public · ");
    const link = document.createElement("a");
    link.href = api.signInUrl();
    link.textContent = "team sign-in";
    who.appendChild(link);
  }
}

// ── Views ────────────────────────────────────────────────────────────────

function showView(name) {
  $("browseView").hidden = name !== "browse";
  $("playView").hidden = name !== "play";
  $("feedbackView").hidden = name !== "feedback";
  if (name !== "feedback" && $("stage").parentElement !== $("playView")) player.unmountStage();
}

let listRendered = false;

function showBrowse() {
  stopLiveIfRunning();
  closeVersionDrawer();
  if (location.hash) history.replaceState(null, "", location.pathname + location.search);
  showView("browse");
  if (!listRendered) renderList();
}

function enterFeedback(options = {}) {
  closeVersionDrawer();
  stopLiveIfRunning();
  showView("feedback");
  if (location.hash !== "#feedback") history.replaceState(null, "", "#feedback");
  feedback.enter(options);
}

// ── Catalog (trees) ──────────────────────────────────────────────────────

function restoreListState() {
  try {
    const saved = JSON.parse(localStorage.getItem(LIST_KEY) || "{}");
    // Older saves name a single family ("arena", "custom"); only whole categories exist now.
    if (["", ...api.CATEGORY_ORDER].includes(saved.family)) list.family = saved.family;
    if (typeof saved.sort === "string") list.sort = saved.sort;
    if (typeof saved.evolved === "boolean") list.evolved = saved.evolved;
  } catch (e) {
    /* defaults */
  }
}

function saveListState() {
  try {
    localStorage.setItem(LIST_KEY, JSON.stringify({ family: list.family, sort: list.sort, evolved: list.evolved }));
  } catch (e) {
    /* not remembered */
  }
}

function setupBrowseControls() {
  let debounce = null;
  $("gameSearch").addEventListener("input", (e) => {
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      list.q = e.target.value.trim();
      list.offset = 0;
      renderList();
    }, 250);
  });
  $("sortSelect").value = list.sort;
  $("sortSelect").addEventListener("change", (e) => {
    list.sort = e.target.value;
    list.offset = 0;
    saveListState();
    renderList();
  });
  $("evolvedOnly").checked = list.evolved;
  $("evolvedOnly").addEventListener("change", (e) => {
    list.evolved = e.target.checked;
    list.offset = 0;
    saveListState();
    renderList();
  });
}

// One chip per category, not per family: arena, in-house and any glow-up or research family
// all count toward "Additional games".
function paintFamilies(families) {
  const bar = $("familyChips");
  bar.replaceChildren();
  const counts = {};
  let total = 0;
  for (const [family, n] of Object.entries(families || {})) {
    const category = api.categoryOf(family);
    counts[category] = (counts[category] || 0) + n;
    total += n;
  }
  const chips = [["", "All", total]];
  for (const category of api.CATEGORY_ORDER) {
    if (counts[category]) chips.push([category, api.CATEGORY_LABELS[category], counts[category]]);
  }
  for (const [value, label, count] of chips) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip" + (list.family === value ? " active" : "");
    chip.append(label);
    const n = document.createElement("span");
    n.className = "n";
    n.textContent = count;
    chip.appendChild(n);
    chip.addEventListener("click", () => {
      list.family = value;
      list.offset = 0;
      saveListState();
      renderList();
    });
    bar.appendChild(chip);
  }
}

const observer = "IntersectionObserver" in window
  ? new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        observer.unobserve(entry.target);
        const callback = entry.target._whenVisible;
        entry.target._whenVisible = null;
        if (callback) callback();
      }
    }, { rootMargin: "600px 0px" })
  : null;

function whenVisible(element, callback) {
  if (!observer) return callback();
  element._whenVisible = callback;
  observer.observe(element);
}

async function renderList() {
  listRendered = true;
  const token = ++listToken;
  const container = $("treeList");
  const loading = document.createElement("p");
  loading.className = "tree-loading";
  loading.textContent = "Loading games…";
  container.replaceChildren(loading);
  const query = { family: list.family, q: list.q, evolved: list.evolved ? "1" : "", sort: list.sort, offset: list.offset, limit: PAGE_SIZE };
  let data = null;
  if (apiOk) {
    try {
      data = await api.listTrees(query);
      // An empty catalog with no filter means the database has not been filled yet.
      if (!data.total && !list.family && !list.q && !list.evolved) data = null;
    } catch (err) {
      data = null;
    }
    if (!data) apiOk = false;
  }
  if (!data) data = await api.staticTrees({ ...list, limit: PAGE_SIZE });
  if (token !== listToken) return;

  paintFamilies(data.families);
  $("staticNotice").hidden = !data.static;
  container.replaceChildren();
  if (!data.trees.length) {
    const empty = document.createElement("p");
    empty.className = "tree-loading";
    empty.textContent = list.evolved && data.static
      ? "Evolution history needs the site's API, which is not answering right now."
      : "No games match.";
    container.appendChild(empty);
  }
  const ctx = {
    team: !!me,
    loadDetail: api.treeDetail,
    loadNotes: api.treeNotes,
    whenVisible,
    onPlay: (tree, version) => playVersion(version, tree, null),
    onReview: (tree, version) => enterFeedback({ version }),
    onNode: openDrawerFor,
  };
  for (const tree of data.trees) container.appendChild(renderTreeRow(tree, ctx));
  paintPager(data.total);
}

function paintPager(total) {
  const el = $("treePager");
  el.replaceChildren();
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  el.hidden = total === 0;
  const page = Math.floor(list.offset / PAGE_SIZE);
  const button = (text, disabled, offset) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = text;
    b.disabled = disabled;
    b.addEventListener("click", () => {
      list.offset = offset;
      renderList();
      $("browseView").scrollTo({ top: 0 });
    });
    return b;
  };
  const label = document.createElement("span");
  label.textContent = `${Math.min(total, list.offset + 1)}–${Math.min(total, list.offset + PAGE_SIZE)} of ${total} trees · page ${page + 1}/${pages}`;
  el.append(button("‹ Prev", page === 0, Math.max(0, list.offset - PAGE_SIZE)), button("Next ›", page >= pages - 1, list.offset + PAGE_SIZE), label);
}

async function openDrawerFor(tree, version, detail, notes) {
  let fullDetail = detail && detail.treeId ? detail : null;
  let fullNotes = notes || null;
  if (!version.static) {
    if (!fullDetail) fullDetail = await api.treeDetail(tree.treeId).catch(() => null);
    if (me && !fullNotes) fullNotes = await api.treeNotes(tree.treeId).catch(() => null);
    const fresh = fullDetail && fullDetail.versions.find((v) => v.versionId === version.versionId);
    if (fresh) version = fresh;
  }
  openVersionDrawer({
    tree,
    version,
    detail: fullDetail,
    notes: fullNotes,
    team: !!me,
    signInUrl: api.signInUrl(),
    onPlay: (t, v, d) => playVersion(v, t, d),
    onReview: (t, v) => enterFeedback({ version: v }),
    onHide: async (review, button) => {
      button.disabled = true;
      try {
        const result = await api.setFeedbackHidden(review.feedbackId, !review.hidden);
        review.hidden = result.hidden;
        button.textContent = review.hidden ? "Unhide" : "Hide as spam";
        button.closest(".review").classList.toggle("hidden-review", review.hidden);
      } catch (err) {
        button.textContent = `Failed (${err.message})`;
      } finally {
        button.disabled = false;
      }
    },
  });
}

// ── Playing a version ────────────────────────────────────────────────────

function treeSummary(detail, fallback) {
  const head = detail.versions.find((v) => v.isTreeHead) || detail.versions[detail.versions.length - 1];
  const game = detail.games.find((g) => g.gameId === head.gameId) || {};
  return { treeId: detail.treeId, family: detail.family, title: game.title, head, ...(fallback || {}) };
}

async function playById(treeId, versionId) {
  if (apiOk) {
    try {
      const detail = await api.treeDetail(treeId);
      const version = detail.versions.find((v) => v.versionId === versionId)
        || detail.versions.find((v) => v.isTreeHead);
      if (version) return playVersion(version, treeSummary(detail), detail);
    } catch (err) {
      /* fall through to the id */
    }
  }
  return playGameId(versionId.split("@")[0]);
}

// Old links (#g=<id>) and the static fallback: the latest version of that game id.
async function playGameId(gameId) {
  if (apiOk) {
    try {
      let detail = await api.treeDetail(gameId).catch(() => null);
      if (!detail || !detail.versions.some((v) => v.gameId === gameId)) {
        const found = await api.listTrees({ q: gameId, limit: 10 });
        for (const tree of found.trees) {
          const candidate = await api.treeDetail(tree.treeId);
          if (candidate.versions.some((v) => v.gameId === gameId)) { detail = candidate; break; }
        }
      }
      if (detail) {
        const mine = detail.versions.filter((v) => v.gameId === gameId);
        const version = mine.find((v) => v.isLineHead) || mine[mine.length - 1];
        if (version) return playVersion(version, treeSummary(detail), detail);
      }
    } catch (err) {
      /* static fallback below */
    }
  }
  const all = await api.staticCatalog();
  const version = all.find((v) => v.gameId === gameId);
  if (!version) return showBrowse();
  return playVersion(version, { treeId: version.treeId, family: version.family, title: version.title, head: version }, null);
}

async function playVersion(version, tree, detail) {
  closeVersionDrawer();
  showView("play");
  const hash = version.versionId
    ? `#t=${encodeURIComponent(tree.treeId)}&v=${encodeURIComponent(version.versionId)}`
    : `#g=${encodeURIComponent(version.gameId)}`;
  if (location.hash !== hash) history.replaceState(null, "", hash);
  const context = { version, tree, detail };
  current = context;
  renderVersionSidebar();
  await loadVersion(version, { blind: false });
  if (!detail && !version.static) {
    try {
      context.detail = await api.treeDetail(tree.treeId);
      if (current === context) renderVersionSidebar();
    } catch (err) {
      /* the sidebar just lists what it has */
    }
  }
}

function renderVersionSidebar() {
  const box = $("sidebarVersions");
  box.replaceChildren();
  if (!current) return;
  const versions = current.detail ? current.detail.versions.slice().reverse() : [current.version];
  $("sidebarHeading").textContent = versions.length > 1 ? `Versions (${versions.length})` : "Version";
  for (const v of versions) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "ver-item" + (v.versionId === current.version.versionId && v.gameId === current.version.gameId ? " active" : "");
    const img = document.createElement("img");
    img.alt = "";
    img.loading = "lazy";
    if (v.thumbUrl) img.src = v.thumbUrl;
    const text = document.createElement("span");
    text.className = "ver-text";
    const line = document.createElement("span");
    line.className = "ver-line";
    line.append(authorBadge(v.author), ` v${v.number || 1}`);
    if (v.isTreeHead) {
      const star = document.createElement("span");
      star.className = "ver-current";
      star.textContent = "current";
      line.appendChild(star);
    }
    const sub = document.createElement("span");
    sub.className = "ver-sub";
    sub.textContent = [v.gameId !== current.tree.treeId ? v.gameId : null, shortDate(v.createdAt)].filter(Boolean).join(" · ");
    text.append(line, sub);
    item.append(img, text);
    item.addEventListener("click", () => playVersion(v, current.tree, current.detail));
    box.appendChild(item);
  }
}

async function loadVersion(version, { blind }) {
  const token = ++loadToken;
  stopLiveIfRunning();
  const hideName = blind || api.BLIND_FAMILIES.has(version.family);
  $("gameTitle").textContent = hideName ? version.gameId : version.title || version.gameId;
  $("gameIdLabel").textContent = blind || !version.versionId ? version.gameId : `${version.gameId} · v${version.number || 1}`;
  $("versionNote").textContent = !blind && version.versionId && !version.isTreeHead && !version.isLineHead
    ? "an older version — the tree's current one is further right"
    : "";
  $("gameStatus").textContent = "—";
  $("gameStatus").className = "status";
  $("endOverlay").hidden = true;
  canvas().style.display = "none";
  $("engineLoading").hidden = gameEngineReady();

  active = null;
  let loaded;
  try {
    await ensureGameEngine();
    const source = await api.fetchSource(version.sourceUrl);
    if (token !== loadToken) return null;
    const next = await gameLoad(source.text, version.className);
    if (token !== loadToken) return null;
    state = next;
    active = version;
    loaded = { sha256: source.sha256 };
  } catch (err) {
    if (token !== loadToken) return null;
    $("engineLoading").hidden = true;
    $("gameStatus").textContent = "FAILED TO LOAD";
    $("gameStatus").className = "status status-game_over";
    $("actionHint").textContent = `This version could not be loaded: ${err.message}`;
    return null;
  }
  $("engineLoading").hidden = true;
  canvas().style.display = "block";

  stepCount = 0;
  telemetry.actions = 0;
  telemetry.resets = 0;
  telemetry.undos = 0;
  telemetry.seconds = 0;
  liveIdleAction = (state.available_actions || []).includes(7) ? 7 : 6;
  liveHeldAction = liveIdleAction;
  const isLive = (version.tags || []).includes("live");
  $("liveToggleBtn").hidden = !isLive;
  $("liveFpsWrap").hidden = !isLive;
  liveFps = Math.min(30, Math.max(2, version.defaultFps || 10));
  $("liveFpsInput").value = liveFps;

  render(state.grid);
  updateTopBar();
  updateTileBar();
  updateFilterBar();
  buildLevelStrip();
  return loaded;
}

// ── Tile modes ───────────────────────────────────────────────────────────
// The worker holds one global skin, so the chosen mode carries across games;
// the bar just has to resync after each load.

function setupTileBar() {
  for (const btn of document.querySelectorAll("#tileBar [data-tile-mode]")) {
    btn.addEventListener("click", () => applyTileMode(btn.dataset.tileMode));
  }
  $("reseedBtn").addEventListener("click", () => {
    tileSeed = 1 + Math.floor(Math.random() * 1e6);
    applyTileMode("random");
  });
}

async function applyTileMode(mode) {
  if (processing) return;
  tileMode = mode;
  updateTileBar();
  if (!active) return;
  await runAction(() => gameSetTileMode(tileMode, tileSeed), "(skin)");
}

function updateTileBar() {
  const scale = state.tile_scale || 1;
  $("tileBar").hidden = !active;
  for (const btn of document.querySelectorAll("#tileBar [data-tile-mode]")) {
    btn.classList.toggle("active", btn.dataset.tileMode === tileMode);
  }
  $("reseedBtn").hidden = tileMode !== "random";
  $("tileSeedLabel").hidden = tileMode !== "random";
  $("tileSeedLabel").textContent = `seed ${tileSeed}`;
  // A 64x64 board is already at raster resolution: there is no room inside a
  // cell to draw a motif, so only the colour reshuffle can apply.
  $("tileNote").textContent = scale >= 2
    ? `${scale}×${scale} px per cell`
    : "64×64 board — no room for tile art; Randomized recolours only";
}

// ── Frame filters ────────────────────────────────────────────────────────
// A second, independent view-layer transform (recolor/noise/merge/occlude) on
// top of whatever the tile renderer produced -- see frame_filters.py. Same
// "worker holds the global state, bar resyncs after load" pattern as tiles.

function setupFilterBar() {
  const select = $("filterSelect");
  select.innerHTML = "";
  for (const f of FILTERS) {
    const opt = document.createElement("option");
    opt.value = f.id;
    opt.textContent = f.label;
    select.appendChild(opt);
  }
  select.addEventListener("change", () => selectFilter(select.value));
  $("filterStrength").addEventListener("input", (e) => {
    const entry = FILTERS.find((f) => f.id === filterId);
    if (!entry || !entry.param) return;
    const raw = +e.target.value;
    filterParams = { [entry.param]: entry.step < 1 ? raw : Math.round(raw) };
    applyFilter();
  });
  $("filterRerollBtn").addEventListener("click", () => {
    filterSeed = 1 + Math.floor(Math.random() * 1e6);
    applyFilter();
  });
}

function selectFilter(id) {
  filterId = id;
  const entry = FILTERS.find((f) => f.id === id);
  filterParams = entry && entry.param ? { [entry.param]: entry.default } : {};
  updateFilterBar();
  applyFilter();
}

async function applyFilter() {
  if (!active) return;
  await runAction(() => gameSetFilter(filterId, filterParams, filterSeed), "(filter)");
}

function updateFilterBar() {
  $("filterBar").hidden = !active;
  $("filterSelect").value = filterId;
  const entry = FILTERS.find((f) => f.id === filterId);
  const hasParam = !!(entry && entry.param);
  $("filterParamWrap").hidden = !hasParam;
  if (hasParam) {
    const input = $("filterStrength");
    input.min = entry.min;
    input.max = entry.max;
    input.step = entry.step;
    input.value = filterParams[entry.param] ?? entry.default;
    $("filterParamLabel").textContent = entry.param;
  }
  $("filterRerollBtn").hidden = !(entry && entry.seeded);
}

// ── Actions / stepping ───────────────────────────────────────────────────

async function runAction(fn, label) {
  if (processing) return;
  processing = true;
  canvas().style.cursor = "wait";
  try {
    const next = await fn();
    if (next.error) { alert(next.error); return; }
    if (label === "(reset)" || label === "(jump)") stepCount = 0;
    else if (label !== "(undo)" && label !== "(skin)" && label !== "(filter)") stepCount++;
    if (label === "(reset)" || label === "(step-reset)") telemetry.resets++;
    else if (label === undefined) telemetry.actions++;
    await applyState(next);
  } finally {
    processing = false;
    canvas().style.cursor = (state.available_actions || []).includes(6) ? "crosshair" : "default";
  }
}

// Feedback-revised games supply intact native movement frames.
const nativeTranslationGames = new Set(["g009", "g010", "g011", "g012", "g013", "g014", "g015", "g016", "g017", "g018", "g019", "g020", "g021", "g022", "g024", "g026", "g027", "g028", "g034", "g035", "g036", "g043", "g044", "g045", "g046", "g047", "g050", "g136", "g155", "g162", "g171", "g178"]);

async function applyState(next) {
  if (next.frames && next.frames.length > 1) {
    const delay = nativeTranslationGames.has(active?.gameId) ? 40 : Math.max(16, Math.round(1000 / 30));
    for (let i = 0; i < next.frames.length - 1; i++) {
      render(next.frames[i]);
      await new Promise((r) => setTimeout(r, delay));
    }
  }
  delete next.frames;
  state = next;
  render(state.grid);
  updateTopBar();
  updateTileBar();  // camera (and so tile scale) can change on a level change
  checkEnd();
}

function doAction(actionId, data) {
  if (!active || state.state === "WIN" || state.state === "GAME_OVER") return;
  // The r key sends the game's own RESET action (ACTION 0), as it always has; it counts as a
  // reset, not a move, in the review telemetry.
  return runAction(() => gameStep(actionId, data || {}), actionId === 0 ? "(step-reset)" : undefined);
}

async function doUndo() {
  if (processing) return;
  processing = true;
  try {
    const next = await gameUndo(1);
    stepCount = Math.max(0, stepCount - 1);
    telemetry.undos++;
    await applyState(next);
  } finally { processing = false; }
}

// ── Rendering ────────────────────────────────────────────────────────────

function render(grid) {
  if (!grid || !grid.length) return;
  const c = canvas();
  const ctx = c.getContext("2d");
  const h = grid.length, w = grid[0].length;
  const scale = Math.floor(512 / Math.max(h, w));
  c.width = w * scale;
  c.height = h * scale;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      ctx.fillStyle = COLORS[grid[y][x]] || "#000";
      ctx.fillRect(x * scale, y * scale, scale, scale);
    }
  }
}

function updateTopBar() {
  const st = state.state || "NOT_FINISHED";
  const statusEl = $("gameStatus");
  statusEl.textContent = st === "NOT_FINISHED" ? "IN PROGRESS" : st.replace(/_/g, " ");
  statusEl.className = "status status-" + st.toLowerCase();
  $("levelInfo").textContent = `Level ${state.levels_completed || 0}/${state.win_levels ?? "?"}`;
  $("stepCounter").textContent = `Step ${stepCount}`;
  $("undoBtn").disabled = stepCount === 0;
  canvas().style.cursor = (state.available_actions || []).includes(6) ? "crosshair" : "default";
  $("actionHint").textContent = (state.available_actions || []).includes(6)
    ? "Click the board to act. Arrow keys / WASD also work if the game uses them."
    : "Arrow keys or WASD to act, Space (or Z) and X for the extra actions.";
  document.querySelectorAll("#levelStrip .lvl").forEach((el, i) => {
    el.classList.toggle("done", i < (state.levels_completed || 0));
    el.classList.toggle("active", i === (state.levels_completed || 0));
  });
}

function buildLevelStrip() {
  const strip = $("levelStrip");
  const total = state.win_levels || 0;
  strip.innerHTML = "";
  strip.hidden = total <= 1;
  for (let i = 0; i < total; i++) {
    const el = document.createElement("button");
    el.className = "lvl" + (i === (state.levels_completed || 0) ? " active" : "");
    el.textContent = i + 1;
    el.title = `Jump to level ${i + 1}`;
    el.addEventListener("click", () => runAction(() => gameJumpLevel(i), "(jump)"));
    strip.appendChild(el);
  }
}

function checkEnd() {
  const st = state.state;
  const overlay = $("endOverlay");
  // Hide the banner again whenever we are back in a playable state -- otherwise a reset
  // after GAME_OVER restores the game underneath but leaves the overlay covering it,
  // which reads as "reset is broken" in every game on the site.
  if (st !== "WIN" && st !== "GAME_OVER") {
    overlay.hidden = true;
    return;
  }
  stopLiveIfRunning();
  overlay.textContent = st === "WIN" ? "🎉 YOU WIN!" : "GAME OVER";
  overlay.className = "end-overlay " + (st === "WIN" ? "win" : "gameover");
  overlay.hidden = false;
}

function updateLoadingUI(stage, percent) {
  const overlay = $("engineLoading");
  if (overlay.hidden) return;
  overlay.querySelector(".loading-stage").textContent = stage || "Initializing...";
  overlay.querySelector(".bar-fill").style.width = Math.min(100, Math.max(0, percent || 0)) + "%";
}

// ── Input: keyboard + canvas click ──────────────────────────────────────

function typingInField() {
  const tag = document.activeElement?.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
}

function setupKeyboard() {
  document.addEventListener("keydown", (e) => {
    if (!stageVisible() || typingInField() || e.ctrlKey || e.metaKey || e.altKey) return;
    const action = KEY_MAP[e.key];
    if (action === undefined) return;
    e.preventDefault();
    // A focused button (Reset, a rating) would otherwise also fire when Space is released.
    if (document.activeElement?.tagName === "BUTTON") document.activeElement.blur();
    if (liveMode) liveHeldAction = action;
    else doAction(action);
  });
  document.addEventListener("keyup", (e) => {
    if (e.key === " " && stageVisible() && !typingInField()) e.preventDefault();
    if (!liveMode) return;
    const action = KEY_MAP[e.key];
    if (action !== undefined && liveHeldAction === action) liveHeldAction = liveIdleAction;
  });
}

function pointerToGrid(e) {
  const c = canvas();
  const rect = c.getBoundingClientRect();
  if (!rect.width || !rect.height) return null;
  const x = Math.floor(((e.clientX - rect.left) * 64) / rect.width);
  const y = Math.floor(((e.clientY - rect.top) * 64) / rect.height);
  return { x: Math.max(0, Math.min(63, x)), y: Math.max(0, Math.min(63, y)) };
}

function setupCanvasInput() {
  const c = canvas();
  c.addEventListener("click", (e) => {
    if (liveMode || processing) return;
    if (!(state.available_actions || []).includes(6)) return;
    const p = pointerToGrid(e);
    if (p) doAction(6, p);
  });
  c.addEventListener("mousemove", (e) => {
    const p = pointerToGrid(e);
    if (p) { liveMouseX = p.x; liveMouseY = p.y; }
  });
  const release = () => { if (liveMode && liveHeldAction === 6) liveHeldAction = liveIdleAction; };
  c.addEventListener("mousedown", (e) => {
    if (!liveMode || !(state.available_actions || []).includes(6)) return;
    const p = pointerToGrid(e);
    if (p) { liveMouseX = p.x; liveMouseY = p.y; }
    liveHeldAction = 6;
  });
  c.addEventListener("mouseup", release);
  c.addEventListener("mouseleave", release);
}

// ── Live mode (continuous tick, for physics-style games) ────────────────

function toggleLive() {
  liveMode ? stopLive() : startLive();
}

function startLive() {
  liveMode = true;
  $("liveToggleBtn").textContent = "Stop live";
  $("liveToggleBtn").classList.add("active");
  restartLiveTick();
}

function stopLive() {
  liveMode = false;
  liveHeldAction = liveIdleAction;
  $("liveToggleBtn").textContent = "Live mode";
  $("liveToggleBtn").classList.remove("active");
  if (liveInterval) { clearInterval(liveInterval); liveInterval = null; }
}

function stopLiveIfRunning() { if (liveMode) stopLive(); }

function restartLiveTick() {
  if (liveInterval) clearInterval(liveInterval);
  if (!liveMode) return;
  liveInterval = setInterval(() => {
    if (processing || state.state === "WIN" || state.state === "GAME_OVER") return;
    const data = liveMouseX != null ? { x: liveMouseX, y: liveMouseY } : {};
    runAction(() => gameStep(liveHeldAction, data));
  }, Math.max(16, Math.round(1000 / liveFps)));
}

document.addEventListener("DOMContentLoaded", init);

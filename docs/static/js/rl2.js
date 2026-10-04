// RL2 page (docs/rl2.html): the turn coach. Four views over published documents and the universal game tree:
//   GET /api/v1/rl2/doc/dashboard     builds (a tree) and modes (name, the line it adds, its dials)
//   GET /api/v1/rl2/doc/run-<run id>  one run's decisions, game by game (Decisions)
//   GET /api/v1/rl2/doc/explore-<game>  the trace grader's goal labels per run of the best combo (rows[].grades.cps,
//                                     grader/explore_publish.py): the Tree view's "goal held" overlay
//   GET /api/v1/rl2/doc/rl-campaigns  the RL training campaigns ({campaigns: [{name, updated}]})
//   GET /api/v1/rl2/doc/rl-campaign-<name>  one campaign: VMs, rounds, policy, totals, sibling groups
//                                     (gcp/controllers/gtree-rollout/rl_loop.py publish-status, arc3-sglang-parking repo)
//   GET /api/v1/gtree/games           the universal game tree: games, their five trees and each tree's start (root)
//   GET /api/v1/gtree/tree?game=&tree=[&arms=]  one game's whole tree for one node definition: nodes, edges (the
//                                     turns between two nodes, aggregated), every run's path (the Tree view's drawing)
//   GET /api/v1/gtree/node/<id>       one node of one tree: its steps grouped by action, children, parents, restarts here
//   GET /api/v1/gtree/value/<id>      per action: clear rate, mean moves to clear, Q; V; the best known path from the node
//   GET /api/v1/gtree/rollout/<id>    one rollout's steps (a turn's trace sha; the best known path's steps)
//   GET /api/v1/gtree/trace/<sha>     one step's turn: thinking, code, moves
// Server: railway/rl_review.py. With ?fixture=1 the page reads docs/static/data/rl2-fixture.json instead (fake data, for
// checking the page locally). Chrome from theme.css and rl-shell.css; every colour is solid (no gradients).

import { draw, pathView } from "./review-ui.js?v=20261003-run";

const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
const FIXTURE = params.get("fixture") === "1";
const VIEWS = ["builds", "decisions", "tree", "training"];
// views folded into the Tree view (Son 3-Oct): old links still land there
const OLD_VIEWS = { lanes: "tree", explore: "tree", sampling: "tree" };
const rawView = params.get("view");
const startNode = params.get("node") || (params.get("trail") || "").split(",").filter(Boolean).pop() || null;

const state = {
  dash: null, fixture: null, view: VIEWS.includes(rawView) ? rawView : OLD_VIEWS[rawView] || "builds",
  run: params.get("run"), game: params.get("game"), modeFilter: new Set(), open: new Set(), docs: {},
  // tree view: game, tree (t1..t5), x axis (game moves | turns), zoom, sources shown (null = all), goal overlay, the
  // node whose panel is open, the edge whose turns are listed, the run highlighted (pinned / hovered)
  treeGames: null, treeCache: {},
  tGame: params.get("tgame") || (rawView === "lanes" ? params.get("game") : null) || params.get("egame"),
  tTree: startNode ? +((startNode.split(":")[1] || "t1").slice(1)) || 1 : +(params.get("ttree") || 1),
  tX: params.get("tx") === "turn" ? "turn" : "moves", tZoom: 1,
  tArms: params.get("arms") ? new Set(params.get("arms").split(",").filter(Boolean)) : null,
  tGoal: params.get("goal") === "1", tNode: startNode, tEdge: null, tPin: null, tHover: null,
  // the open node panel: open action groups, open traces, open restarted rollouts, the best-path box
  tOpen: new Set(), tTrace: new Set(), tRoll: new Set(), bestOpen: false,
  // training view: the campaign shown, and whether every sibling group is listed
  camp: params.get("campaign"), campAll: false,
};
if (startNode && !state.tGame) state.tGame = startNode.split(":")[0];

// One solid colour per mode; stock is grey. Unknown modes take the spare colours in order.
const MODE_COLORS = {
  stock: "#8792a2", probe: "#2563eb", rethink: "#7c3aed", execute: "#059669", brief: "#0891b2", recover: "#d97706",
  transfer: "#db2777", search: "#65a30d", backtrack: "#9a3412", assumption_check: "#0f766e", role_audit: "#a21caf",
  untried_element: "#ca8a04", why_won: "#1e3a8a", requirement_audit: "#be123c", action_coverage: "#4d7c0f",
  look_around: "#0369a1", budget_measure: "#854d0e", commit_test: "#14b8a6",
};
const SPARE = ["#0f766e", "#a21caf", "#b45309", "#1e40af", "#be123c", "#4d7c0f"];
function modeColor(name) {
  if (!MODE_COLORS[name]) MODE_COLORS[name] = SPARE[Object.keys(MODE_COLORS).length % SPARE.length];
  return MODE_COLORS[name];
}

function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "style") e.style.cssText = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) if (k !== null && k !== undefined && k !== false) e.append(k instanceof Node ? k : document.createTextNode(String(k)));
  return e;
}
const isNum = x => typeof x === "number" && Number.isFinite(x);
const fx = (x, d = 1) => isNum(x) ? x.toFixed(d) : "–";
const pct = x => isNum(x) ? Math.round(x * 100) + "%" : "–";
const val = x => x === null || x === undefined ? "–" : isNum(x) ? (Number.isInteger(x) ? String(x) : x.toFixed(3).replace(/0+$/, "").replace(/\.$/, "")) : String(x);
const yesNo = x => x === null || x === undefined ? "–" : x ? "yes" : "·";
// The prompt a mode adds to the turn message, and its dials: shown on hover over any mode tag or legend chip
function modePrompt(name) {
  const m = ((state.dash && state.dash.modes) || []).find(x => x.name === name);
  if (!m) return "";
  const dials = [isNum(m.cap) ? `move cap ${m.cap}` : null, isNum(m.yield_tokens) ? `thinking budget ${m.yield_tokens} tokens` : null,
    isNum(m.temperature) ? `temperature ${m.temperature}` : null].filter(Boolean).join(" · ");
  return (m.line ? m.line.trim() : "No focus line: the turn message is left as it is.") + (dials ? "\n" + dials : "");
}
const modeTag = (name, extra) => el("span", { class: "rl2-mode" + (extra ? " " + extra : ""), style: `background:${modeColor(name)}`,
  title: modePrompt(name) || null }, name);
// inside a canvas tooltip (which the pointer cannot reach): the prompt as text under the tag
const modePromptLine = name => { const t = modePrompt(name); return t ? el("div", { class: "rl2-small rl2-eprompt" }, t) : null; };

function notice(text) { $("notice").hidden = !text; $("notice").textContent = text || ""; }
function syncUrl() {
  const q = new URLSearchParams();
  if (FIXTURE) q.set("fixture", "1");
  if (state.view !== "builds") q.set("view", state.view);
  if (state.view === "decisions" && state.run) { q.set("run", state.run); if (state.game) q.set("game", state.game); }
  if (state.view === "tree" && state.tGame) {
    q.set("tgame", state.tGame);
    if (state.tTree !== 1) q.set("ttree", String(state.tTree));
    if (state.tX === "turn") q.set("tx", "turn");
    if (state.tArms) q.set("arms", [...state.tArms].sort().join(","));
    if (state.tGoal) q.set("goal", "1");
    if (state.tNode) q.set("node", state.tNode);
  }
  if (state.view === "training" && state.camp) q.set("campaign", state.camp);
  const s = q.toString();
  history.replaceState(null, "", location.pathname + (s ? "?" + s : ""));
}

/* ------------------------------------------------------------------ data */
class NotPublished extends Error {}
let fixtureLoad = null;
const loadFixture = () => fixtureLoad || (fixtureLoad = fetch("./static/data/rl2-fixture.json", { cache: "no-store" })
  .then(r => r.json()).then(f => (state.fixture = f)));
async function getDoc(name) {
  if (state.docs[name]) return state.docs[name];
  let doc;
  if (FIXTURE) {
    await loadFixture();
    doc = name === "dashboard" ? state.fixture.dashboard : (state.fixture.docs || {})[name];
    if (!doc) throw new NotPublished(name);
  } else {
    const r = await fetch("/api/v1/rl2/doc/" + encodeURIComponent(name), { cache: "no-store", credentials: "same-origin", redirect: "manual" });
    if (r.type === "opaqueredirect" || r.status === 0 || r.status === 401) throw Object.assign(new Error("sign in"), { status: 401 });
    if (r.status === 403) throw Object.assign(new Error("not on team"), { status: 403 });
    if (r.status === 404) throw new NotPublished(name);
    if (!r.ok) throw Object.assign(new Error("HTTP " + r.status), { status: r.status });
    doc = await r.json();
  }
  state.docs[name] = doc;
  return doc;
}
const allRuns = () => (state.dash.builds || []).flatMap(b => (b.runs || []).map(r => ({ ...r, build: b.id })));
const modeNames = () => ((state.dash && state.dash.modes) || []).map(m => m.name);

/* ------------------------------------------------------------------ view 1: builds tree */
function renderBuilds() {
  const builds = state.dash.builds || [];
  const byId = new Map(builds.map(b => [b.id, b]));
  const kids = new Map();
  const roots = [];
  for (const b of builds) {
    if (b.parent && byId.has(b.parent)) { if (!kids.has(b.parent)) kids.set(b.parent, []); kids.get(b.parent).push(b); }
    else roots.push(b);
  }
  if (!builds.length) { $("buildTree").replaceChildren(el("div", { class: "empty" }, "No builds published yet.")); return; }
  const branch = list => el("ul", { class: "rl2-tree" }, list.map(b => el("li", {}, buildCard(b, byId.get(b.parent)),
    kids.has(b.id) ? branch(kids.get(b.id)) : null)));
  $("buildTree").replaceChildren(el("div", { class: "rl2-scroll" }, branch(roots)));
}
function buildCard(b, parent) {
  const m = b.mean || {};
  let delta = null;
  if (parent && isNum(m.all25) && isNum((parent.mean || {}).all25)) {
    const d = m.all25 - parent.mean.all25;
    delta = el("span", { class: "rl2-delta " + (d > 0 ? "up" : d < 0 ? "down" : ""), title: `mean all-25 minus ${parent.id}'s` },
      (d > 0 ? "+" : d < 0 ? "−" : "±") + Math.abs(d).toFixed(1) + " vs parent");
  }
  const pol = b.policy ? `${b.policy.spec || "policy"} · ${b.policy.version || "?"}` : null;
  const runs = (b.runs || []).map(r => {
    const live = r.status !== "finished";
    const can = (r.decisions || 0) > 0;
    const text = (isNum(r.all25) ? r.all25.toFixed(1) : "–") + (live ? ` · ${r.minute ?? "?"}m` : "");
    const tip = `${r.run}\n${r.status}${live ? ` at minute ${r.minute ?? "?"}` : ""}\nall-25 ${fx(r.all25)} · hard-7 ${fx(r.hard7)}\n` +
      `${r.levels ?? "–"} levels · ${r.actions ?? "–"} actions · ${r.wins ?? "–"} wins · ${r.decisions ?? 0} decisions` +
      (can ? "\nclick to inspect its decisions" : "");
    return el(can ? "button" : "span", { type: can ? "button" : null, class: "rl2-run" + (live ? " live" : "") + (can ? " can" : ""), title: tip,
      onclick: can ? () => openRun(r.run) : null }, text);
  });
  return el("div", { class: "rl2-card" + (b.kind === "coach" ? " coach" : "") },
    el("div", { class: "rl2-card-top" },
      el("span", { class: "rl2-kind" }, b.kind || "build"),
      pol ? el("span", { class: "rl2-pol mono" }, pol) : null,
      b.created ? el("span", { class: "muted rl2-date" }, b.created) : null),
    el("div", { class: "rl2-label" }, b.label || b.id),
    el("div", { class: "rl2-id mono muted" }, b.id),
    el("div", { class: "rl2-nums" },
      el("div", {}, el("b", { class: "mono" }, fx(m.all25)), el("small", {}, "all-25")),
      el("div", {}, el("b", { class: "mono" }, fx(m.hard7)), el("small", {}, "hard-7")),
      el("div", {}, el("b", { class: "mono" }, m.n ?? 0), el("small", {}, "runs"))),
    delta,
    runs.length ? el("div", { class: "rl2-runs" }, runs) : el("div", { class: "muted rl2-small" }, "no runs yet"),
    b.notes ? el("div", { class: "rl2-notes" }, b.notes) : null);
}
function openRun(run) {
  state.run = run;
  state.game = null;
  state.modeFilter.clear();
  state.open.clear();
  show("decisions");
}

/* ------------------------------------------------------------------ view 2: decisions */
async function renderDecisions() {
  const runs = allRuns().filter(r => (r.decisions || 0) > 0);
  if (!runs.length) {
    $("decPickers").replaceChildren();
    $("decBody").replaceChildren(el("div", { class: "empty" }, "No run with coach decisions yet."));
    return;
  }
  if (!state.run || !runs.some(r => r.run === state.run)) state.run = runs[0].run;
  const runSel = el("select", { "aria-label": "run", onchange: e => { state.run = e.target.value; state.game = null; state.modeFilter.clear(); state.open.clear(); renderDecisions(); } },
    runs.map(r => el("option", { value: r.run, selected: r.run === state.run }, `${r.run} · ${r.build}${r.status !== "finished" ? " (playing)" : ""}`)));
  $("decPickers").replaceChildren(el("label", {}, "run ", runSel));
  $("decBody").replaceChildren(el("div", { class: "empty" }, "loading…"));
  syncUrl();
  let doc;
  try {
    doc = await getDoc("run-" + state.run);
  } catch (e) {
    if (e instanceof NotPublished) { $("decBody").replaceChildren(el("div", { class: "empty" }, "This run's decisions are not published yet.")); return; }
    throw e;
  }
  const games = Object.keys(doc.games || {}).sort();
  if (!games.length) { $("decBody").replaceChildren(el("div", { class: "empty" }, "This run has no decisions.")); return; }
  if (!state.game || !games.includes(state.game)) state.game = games[0];
  const gameSel = el("select", { "aria-label": "game", onchange: e => { state.game = e.target.value; state.modeFilter.clear(); state.open.clear(); renderDecisions(); } },
    games.map(g => el("option", { value: g, selected: g === state.game }, `${g} (${doc.games[g].length})`)));
  const score = doc.score || {};
  $("decPickers").replaceChildren(el("label", {}, "run ", runSel), el("label", {}, "game ", gameSel),
    el("span", { class: "muted rl2-small" }, `build ${doc.build || "?"} · all-25 ${fx(score.all25)} · hard-7 ${fx(score.hard7)}`));
  syncUrl();
  drawGame(doc.games[state.game]);
}
function drawGame(decs) {
  const present = [...new Set(decs.map(d => d.mode))];
  const order = [...modeNames().filter(m => present.includes(m)), ...present.filter(m => !modeNames().includes(m))];
  const shown = d => !state.modeFilter.size || state.modeFilter.has(d.mode);
  const counts = Object.fromEntries(order.map(m => [m, decs.filter(d => d.mode === m).length]));
  const filter = el("div", { class: "rl2-filter" }, el("span", { class: "muted rl2-small" }, "show"),
    el("button", { type: "button", class: "rl2-fbtn" + (state.modeFilter.size ? "" : " on"), onclick: () => { state.modeFilter.clear(); drawGame(decs); } }, "all"),
    order.map(m => el("button", { type: "button", class: "rl2-fbtn" + (state.modeFilter.has(m) ? " on" : ""),
      onclick: () => { state.modeFilter.has(m) ? state.modeFilter.delete(m) : state.modeFilter.add(m); drawGame(decs); } },
      el("i", { style: `background:${modeColor(m)}` }), `${m} ${counts[m]}`)));
  const levels = decs.filter(d => d.o && d.o.lvl_turn).length;
  const gos = decs.filter(d => d.o && d.o.go_turn).length;
  const strip = el("div", { class: "rl2-strip", role: "img", "aria-label": `${decs.length} decisions, ${levels} level-ups` },
    decs.map(d => el("span", {
      class: "rl2-blk" + (d.o && d.o.lvl_turn ? " lvl" : "") + (d.o && d.o.go_turn ? " go" : "") + (shown(d) ? "" : " dim"),
      style: `background:${modeColor(d.mode)}`, title: `#${d.d} ${d.mode} · level ${d.f?.level ?? "?"}` +
        (d.o ? ` · ${d.o.acts ?? "?"} actions${d.o.lvl_turn ? " · level up" : ""}${d.o.go_turn ? " · game over" : ""}` : ""),
      onclick: () => { state.open.add(d.d); drawGame(decs); document.getElementById(`dec-${d.d}`)?.scrollIntoView({ block: "center" }); },
    })));
  const head = ["#", "level", "actions", "in level", "game overs", "clean streak", "mode", "prob", "cap", "acts", "level up", "game over", "level ≤30"];
  const rows = [];
  for (const d of decs) {
    if (!shown(d)) continue;
    const f = d.f || {}, o = d.o;
    const open = state.open.has(d.d);
    rows.push(el("tr", { id: `dec-${d.d}`, class: "rl2-row" + (open ? " open" : "") + (o && o.lvl_turn ? " lvlup" : ""),
      onclick: () => { open ? state.open.delete(d.d) : state.open.add(d.d); drawGame(decs); } },
      el("td", { class: "mono" }, d.d), el("td", { class: "mono" }, val(f.level)), el("td", { class: "mono" }, val(f.actions_total)),
      el("td", { class: "mono" }, val(f.actions_in_level)), el("td", { class: "mono" }, val(f.gameovers_in_level)),
      el("td", { class: "mono" }, val(f.clean_streak)), el("td", {}, modeTag(d.mode)), el("td", { class: "mono" }, val(d.prob)),
      el("td", { class: "mono" }, val(d.cap)),
      el("td", { class: "mono" }, o ? val(o.acts) : "–"),
      el("td", { class: o && o.lvl_turn ? "rl2-yes" : "muted" }, o ? yesNo(o.lvl_turn) : "–"),
      el("td", { class: o && o.go_turn ? "rl2-bad" : "muted" }, o ? yesNo(o.go_turn) : "–"),
      el("td", { class: o && o.lvl30 ? "rl2-yes" : "muted" }, o ? yesNo(o.lvl30) : "–")));
    if (open) rows.push(el("tr", { class: "rl2-detail" }, el("td", { colspan: head.length }, detail(d))));
  }
  const table = rows.length ? el("div", { class: "rl2-scroll" }, el("table", { class: "rl2-table" },
    el("thead", {}, el("tr", {}, head.map(h => el("th", {}, h)))), el("tbody", {}, rows)))
    : el("div", { class: "empty" }, "No decision with the chosen modes.");
  $("decBody").replaceChildren(
    el("div", { class: "card rl2-stripcard" },
      el("div", { class: "rl2-striphead" }, el("b", {}, state.game), el("span", { class: "muted rl2-small" },
        `${decs.length} decisions · ${levels} level-up${levels === 1 ? "" : "s"} · ${gos} game over${gos === 1 ? "" : "s"}`)),
      strip,
      el("div", { class: "legend rl2-small" }, el("span", {}, el("i", { class: "lg-lvl" }), "tick: level up this turn"),
        el("span", {}, el("i", { class: "lg-go" }), "dark base: game over this turn"))),
    filter, table);
}
function detail(d) {
  const mode = (state.dash.modes || []).find(m => m.name === d.mode);
  const kv = obj => el("dl", { class: "rl2-kv" }, Object.entries(obj || {}).flatMap(([k, v]) => [el("dt", {}, k), el("dd", { class: "mono" }, val(v))]));
  return el("div", { class: "rl2-detailbox" },
    el("div", {}, el("h4", {}, "what the coach saw"), kv(d.f)),
    el("div", {}, el("h4", {}, "what followed"), d.o ? kv(d.o) : el("div", { class: "muted" }, "no outcome (last decision of the game)")),
    el("div", {}, el("h4", {}, "mode"), modeTag(d.mode),
      mode ? el("p", { class: "rl2-line" }, mode.line || "(stock: nothing added)") : null,
      mode ? el("div", { class: "muted rl2-small" }, `thinking ${val(mode.yield_tokens)} tokens · cap ${val(mode.cap)} · temperature ${val(mode.temperature)}`) : null,
      isNum(d.t) ? el("div", { class: "muted rl2-small" }, new Date(d.t * 1000).toLocaleString()) : null));
}

// The modes and what each adds to the turn (under the Tree view's legend)
function modesCard() {
  const modes = (state.dash && state.dash.modes) || [];
  if (!modes.length) return null;
  return el("details", { class: "card rl2-modes" }, el("summary", {}, "The modes: what each one adds to the turn"),
    el("div", { class: "rl2-scroll" }, el("table", { class: "rl2-table" },
      el("thead", {}, el("tr", {}, ["mode", "line added to the turn", "thinking", "cap", "temp"].map(h => el("th", {}, h)))),
      el("tbody", {}, modes.map(m => el("tr", {}, el("td", {}, modeTag(m.name)), el("td", { class: "rl2-linecell" }, m.line || "(nothing: stock turn)"),
        el("td", { class: "mono" }, val(m.yield_tokens)), el("td", { class: "mono" }, val(m.cap)), el("td", { class: "mono" }, val(m.temperature))))))));
}

/* ------------------------------------------------------------------ the universal game tree: reads and node labels */
async function getTree(sub) {
  if (state.treeCache[sub]) return state.treeCache[sub];
  let doc;
  if (FIXTURE) {
    await loadFixture();
    doc = (state.fixture.gtree || {})[sub];
    if (!doc) throw new NotPublished(sub);
  } else {
    const [path, query] = sub.split("?");
    const r = await fetch("/api/v1/gtree/" + path.split("/").map(encodeURIComponent).join("/") + (query ? "?" + query : ""),
      { cache: "no-store", credentials: "same-origin", redirect: "manual" });
    if (r.type === "opaqueredirect" || r.status === 0 || r.status === 401) throw Object.assign(new Error("sign in"), { status: 401 });
    if (r.status === 403) throw Object.assign(new Error("not on team"), { status: 403 });
    if (r.status === 404) throw new NotPublished(sub);
    if (!r.ok) throw Object.assign(new Error("HTTP " + r.status), { status: r.status });
    doc = await r.json();
  }
  state.treeCache[sub] = doc;
  return doc;
}
const treeOf = id => +((String(id).split(":")[1] || "t1").slice(1));
// level / moves of nodes seen so far (from node views and their children), for short labels
const nodeMeta = new Map();
function nodeLabel(id) {
  const s = String(id);
  if (s.endsWith(":root")) return "start";
  const m = nodeMeta.get(s);
  const hex = s.split(":")[2] || "?";
  // t3 and t4 merge plays whatever their move count, so only t1 and t2 labels carry one; t5 a bucket of 6 moves
  const t = treeOf(s);
  const mv = t <= 2 ? ` · ${isNum(m && m.moves) ? m.moves + " mv" : "?"}`
    : t === 5 ? ` · ${isNum(m && m.moves) ? `${m.moves}–${m.moves + 5} mv` : "?"}` : "";
  if (m && isNum(m.level)) return `L${m.level}${mv} · ${hex.slice(0, 6)}`;
  return hex.slice(0, 8);
}
const pctOrDash = x => isNum(x) ? Math.round(x * 100) + "%" : "–";

/* ------------------------------------------------------------------ view 3: the tree (the universal game tree) */
// Every turn of every run is stored once and read as five trees, each starting at the game start, so every run of a game
// hangs from the same root (Son 3-Oct: "they should all be one tree starting from the same root"). gtree/tree returns
// one game's whole tree for one node definition: nodes, edges (all the turns from one node to the next) and each run's
// path. Drawn on a canvas, left to right in game moves (or turns) since the game start:
//   layout  each node hangs from its in-edge from the earliest node with the most plays (a spanning tree); a node's
//           busiest child continues its lane and the others branch below, so a stretch of single-child nodes is one
//           lane whose turns keep their own colours (the Lanes look, inside the tree). t2..t5 merge plays, so the
//           graph can be a DAG or have cycles: an edge into a node drawn on another lane is a curve, an edge back to
//           an earlier node is faint and dashed, a turn that stays on its node a small loop.
//   edges   thickness = plays, colour = the coach mode of those turns (stock light grey; several modes: stacked bands);
//           a tick + number where a level clears, a red mark at a game over, a 'restart' badge where an RL rollout
//           restored from a saved state branches off. Even levels sit on a shaded band.
//   goal    the trace grader's labels (rl2 doc explore-<game>) joined to the steps by run + harness turn (checked on
//           3-Oct: 1513 of 1514 checkpoints of the 40 graded run x game pairs land on a step of that turn, all on its
//           level); a step holds the last goal stated on its level before or during its turn.
// Hover an edge for its turns, a run for its whole path; click a node for its panel, an edge to list its turns and
// read each one's trace.
const TREES = [1, 2, 3, 4, 5];
const TREE_LABELS = { 1: "exact path", 2: "same screen after the same number of moves", 3: "same screen in the level",
  4: "same screen anywhere", 5: "restart grid: same screen, moves in bands of 6" };
const TREE_HELP = {
  1: "A node is the exact path from the game start: two runs share a node only while they played the same way.",
  2: "A node is a screen at a number of moves into its level: runs that reach the same screen after the same number of moves merge.",
  3: "A node is a screen within a level: runs merge whenever they see the same screen on the same level.",
  4: "A node is a screen, whatever the level or the moves: loops show up as edges back.",
  5: "A node is a screen on a level, with the moves in bands of 6: the grid restarts are picked from." };
const GOAL_COLORS = ["#0ca30c", "#fab219", "#d03b3b", null];   // right, partly right, wrong, none stated (status palette)
const GOAL_NAMES = ["right goal", "partly right", "wrong goal", "no goal stated"];
const F_CLEARED = 1, F_GO = 2;
const ZOOMS = [1, 2, 4, 8];
const AXIS_H = 24, PAD_L = 14, PAD_R = 28, MAX_AREA = 64e6, TIP_TURNS = 6, PANEL_TURNS = 300;
const treeUi = { token: 0, doc: null, explore: null, ix: new Map(), m: null, paint: null, rlCamps: 0 };

function resetNodeUi() { state.tOpen.clear(); state.tTrace.clear(); state.tRoll.clear(); state.bestOpen = false; }
function resetTreeSel() { state.tNode = null; state.tEdge = null; state.tPin = null; state.tHover = null; resetNodeUi(); }

// a run's short name: the run letter for the best combo's runs (with the pass when not the first), the job and try for
// an RL rollout ('gtr-rl2:bp35_p0.rl2-r001-bp35-root.k0' -> 'r001 root k0', 'rl2 r001 root k0' when several RL
// campaigns are shown)
function runShort(r, game) {
  if (r.arm === "rl") {
    const tail = String(r.id).split(":").slice(1).join(":").replace(/^[a-z0-9]{4}_p\d+\./, "");
    const camp = String(r.run).replace(/^gtr-/, "");
    const short = tail.replace("-" + game, "").replace(camp + "-", "").replace(/\.k(\d+)$/, " k$1").replace(/-/g, " ") || r.id;
    return treeUi.rlCamps > 1 ? `${camp} ${short}` : short;
  }
  const letter = String(r.run).match(/-([a-z])-\d+$/);
  const pass = String(r.id).match(/_p(\d+)$/);
  return (letter ? letter[1] : String(r.run).slice(0, 28)) + (pass && pass[1] !== "0" ? ` p${pass[1]}` : "");
}
const armOf = (doc, id) => (doc.arms || []).find(a => a.id === id) || { id, label: id };
// a run's name outside the run list (tooltips, the turns of an edge): its source, then its short name
const ARM_SHORT = { nocoach: "no coach", random70: "70% stock", random50: "50% stock", random30: "30% stock",
  grader30: "grader 30%", rl: "RL" };
const runName = (r, game) => (ARM_SHORT[r.arm] ? ARM_SHORT[r.arm] + " · " : "") + runShort(r, game);

// run index -> per step the goal held (0..3, null where the step has no harness turn); only runs from the game start,
// one rollout per run and game, with graded checkpoints [turn, moves, level, stated, held, belief, rule errors]
function goalSteps(doc, explore) {
  const out = new Map();
  if (!explore || !Array.isArray(explore.rows)) return out;
  const cpsOf = new Map(explore.rows.filter(r => r.grades && (r.grades.cps || []).length).map(r => [r.run, r.grades.cps]));
  const starts = {};
  for (const r of doc.runs) if (r.origin_kind === "start") starts[r.run] = (starts[r.run] || 0) + 1;
  doc.runs.forEach((r, i) => {
    const cps = cpsOf.get(r.run);
    if (!cps || r.origin_kind !== "start" || starts[r.run] !== 1) return;
    let p = 0, last = null;
    out.set(i, r.steps.map(s => {
      if (!isNum(s[5])) return null;
      while (p < cps.length && cps[p][0] <= s[5]) last = cps[p++];
      return last && last[2] === s[4] ? last[4] : 3;
    }));
  });
  return out;
}

// The drawing's model for the sources shown: node x (the fewest moves / turns any shown play took to get there), the
// visible edges with their turns, the spanning tree and the lanes.
function treeModel(doc, goals) {
  const byMoves = state.tX === "moves";
  const N = doc.nodes.length;
  const nx = new Array(N).fill(Infinity), disc = new Array(N).fill(-1), lvl = doc.nodes.map(n => n.level);
  let dn = 0;
  const see = n => { if (disc[n] < 0) disc[n] = dn++; };
  if (isNum(doc.root)) { see(doc.root); nx[doc.root] = 0; }
  const es = new Map(), runs = [];
  let turns = 0, maxPlays = 1;
  doc.runs.forEach((r, i) => {
    if (state.tArms && !state.tArms.has(r.arm)) return;
    runs.push(i);
    const g = goals.get(i);
    let x = byMoves ? r.x0 || 0 : r.t0 || 0;
    r.steps.forEach((s, k) => {
      const E = doc.edges[s[1]], dx = byMoves ? s[3] : 1;
      see(E.from);
      nx[E.from] = Math.min(nx[E.from], x);
      if (!isNum(lvl[E.from])) lvl[E.from] = s[4];
      if (E.to !== null) { see(E.to); nx[E.to] = Math.min(nx[E.to], x + dx); }
      let st = es.get(s[1]);
      if (!st) es.set(s[1], st = { plays: 0, modes: new Map(), runs: new Set(), go: 0, cleared: 0, dx: 0, level: s[4],
        steps: [], goal: [0, 0, 0, 0] });
      st.plays++;
      st.modes.set(s[2], (st.modes.get(s[2]) || 0) + 1);
      st.runs.add(i);
      if (s[6] & F_CLEARED) st.cleared++;
      if (s[6] & F_GO) st.go++;
      st.dx = Math.max(st.dx, dx);
      st.steps.push([i, k]);
      if (g && isNum(g[k])) st.goal[g[k]]++;
      maxPlays = Math.max(maxPlays, st.plays);
      turns++;
      x += dx;
    });
  });
  for (const [e, st] of es) {
    const to = doc.edges[e].to;
    if (to !== null && !isNum(lvl[to])) lvl[to] = st.level + (st.cleared ? 1 : 0);
  }
  const vis = [];
  for (let n = 0; n < N; n++) if (disc[n] >= 0) vis.push(n);
  vis.sort((a, b) => nx[a] - nx[b] || disc[a] - disc[b]);
  const ord = new Array(N).fill(-1);
  vis.forEach((n, k) => { ord[n] = k; });
  const push = (map, k, v) => { const l = map.get(k); if (l) l.push(v); else map.set(k, [v]); };
  const ins = new Map(), outs = new Map();
  for (const e of es.keys()) {
    const E = doc.edges[e];
    push(outs, E.from, e);
    if (E.to !== null) push(ins, E.to, e);
  }
  const parent = new Array(N).fill(-1);
  for (const v of vis) {
    if (v === doc.root) continue;
    let best = -1;
    for (const e of ins.get(v) || []) {
      const u = doc.edges[e].from;
      if (u === v || ord[u] >= ord[v]) continue;
      const a = es.get(e).plays, b = best >= 0 ? es.get(best).plays : -1;
      if (a > b || (a === b && ord[u] < ord[doc.edges[best].from])) best = e;
    }
    parent[v] = best;
  }
  const endX = e => nx[doc.edges[e].from] + es.get(e).dx;
  const kids = new Map();
  for (const v of vis) if (parent[v] >= 0) push(kids, doc.edges[parent[v]].from, { key: v, e: parent[v] });
  for (const e of es.keys()) if (doc.edges[e].to === null) push(kids, doc.edges[e].from, { key: "e" + e, e });
  const kx = c => typeof c.key === "number" ? nx[c.key] : endX(c.e);
  for (const list of kids.values()) list.sort((a, b) => es.get(b.e).plays - es.get(a.e).plays || kx(a) - kx(b));
  // lanes: leaves in depth-first order; a node sits on its busiest child's lane
  const lane = new Map();
  let lanes = 0;
  for (const top of vis.filter(v => parent[v] < 0)) {
    const stack = [{ key: top, i: 0 }];
    while (stack.length) {
      const f = stack[stack.length - 1];
      const ch = typeof f.key === "number" ? kids.get(f.key) || [] : [];
      if (f.i < ch.length) { stack.push({ key: ch[f.i++].key, i: 0 }); continue; }
      stack.pop();
      lane.set(f.key, ch.length ? lane.get(ch[0].key) : lanes++);
    }
  }
  let maxX = 1;
  for (const v of vis) maxX = Math.max(maxX, nx[v]);
  const kind = new Map();
  for (const e of es.keys()) {
    const E = doc.edges[e];
    if (E.to === null) maxX = Math.max(maxX, endX(e));
    kind.set(e, E.to === null ? "end" : parent[E.to] === e ? "tree" : E.to === E.from ? "self"
      : ord[E.to] > ord[E.from] ? "merge" : "back");
  }
  return { nx, lvl, vis, es, ins, outs, lane, lanes: Math.max(1, lanes), maxX, kind, endX, runs, turns, maxPlays };
}

async function renderTree() {
  const token = ++treeUi.token;
  const body = $("treeBody");
  if (!state.treeGames) {
    body.replaceChildren(el("div", { class: "empty" }, "loading…"));
    try {
      state.treeGames = (await getTree("games")).games || [];
    } catch (e) {
      if (e instanceof NotPublished) state.treeGames = [];
      else {
        $("treePickers").replaceChildren();
        body.replaceChildren(el("div", { class: "empty" }, e.status === 401 ? "Sign in with your team account to see the tree."
          : e.status === 403 ? "This Google account is not on the team list." : "Could not load the tree."));
        if (!e.status) console.error(e);
        return;
      }
    }
    if (token !== treeUi.token) return;
  }
  const games = state.treeGames.filter(g => g.steps > 0);
  if (!games.length) {
    $("treePickers").replaceChildren();
    body.replaceChildren(el("div", { class: "empty" }, "No tree published yet. It appears here once a run publishes its steps."));
    return;
  }
  let g = games.find(x => x.game === state.tGame);
  if (!g) { g = games[0]; state.tGame = g.game; resetTreeSel(); }
  if (!TREES.includes(state.tTree)) state.tTree = 1;
  if (state.tNode && !state.tNode.startsWith(`${g.game}:t${state.tTree}:`)) state.tNode = null;
  const seg = (label, opts, cur, set) => el("div", { class: "rl2-seg", role: "group", "aria-label": label }, opts.map(([k, t]) =>
    el("button", { type: "button", class: cur === k ? "on" : "", "aria-pressed": cur === k ? "true" : "false", onclick: () => set(k) }, t)));
  const redraw = () => { syncUrl(); if (treeUi.doc) drawTreeView(); };
  const status = el("span", { class: "muted rl2-small rl2-tstatus" });
  $("treePickers").replaceChildren(
    el("div", { class: "rl2-tctl" },
      el("label", {}, "game ", el("select", { "aria-label": "game",
        onchange: e => { state.tGame = e.target.value; resetTreeSel(); renderTree(); } },
        games.map(x => el("option", { value: x.game, selected: x.game === g.game },
          `${x.game} · ${x.rollouts} run${x.rollouts === 1 ? "" : "s"}${x.mid_rollouts ? ` (${x.mid_rollouts} restarted)` : ""}`)))),
      el("label", { title: TREE_HELP[state.tTree] }, "node = ", el("select", { "aria-label": "what counts as one node",
        onchange: e => { state.tTree = +e.target.value; resetTreeSel(); renderTree(); } },
        TREES.map(k => el("option", { value: k, selected: k === state.tTree, title: TREE_HELP[k] }, `t${k} · ${TREE_LABELS[k]}`)))),
      seg("x axis", [["moves", "game moves"], ["turn", "turns"]], state.tX, v => { state.tX = v; redraw(); }),
      seg("zoom", ZOOMS.map(z => [z, z === 1 ? "fit" : z + "×"]), state.tZoom, v => { state.tZoom = v; redraw(); }),
      status),
    el("div", { class: "rl2-tsources", id: "treeSources" }));
  syncUrl();
  const base = `tree?game=${g.game}&tree=${state.tTree}`;
  if (!state.treeCache[base]) body.replaceChildren(el("div", { class: "empty" }, "loading the tree…"));
  let doc, explore;
  try {
    [doc, explore] = await Promise.all([getTree(base), getDoc("explore-" + g.game).catch(() => null)]);
    // the server keeps whole runs up to a cap: when it had to leave some out, ask again for the sources shown only
    if (doc.truncated && state.tArms) doc = await getTree(`${base}&arms=${[...state.tArms].sort().join(",")}`);
  } catch (e) {
    if (token !== treeUi.token) return;
    if (e instanceof NotPublished) { body.replaceChildren(el("div", { class: "empty" }, `No tree for ${g.game} yet.`)); return; }
    body.replaceChildren(el("div", { class: "empty" }, "Could not load the tree."));
    console.error(e);
    return;
  }
  if (token !== treeUi.token) return;
  treeUi.doc = doc;
  treeUi.explore = explore;
  treeUi.ix = new Map(doc.nodes.map((n, i) => [n.id, i]));
  treeUi.rlCamps = new Set(doc.runs.filter(r => r.arm === "rl").map(r => r.run)).size;
  for (const n of doc.nodes) nodeMeta.set(n.id, { level: n.level, moves: n.moves });
  drawTreeView();
}

// (Re)draw the Tree view from the loaded document: sources, the chart, the runs, the edge and node panels.
function drawTreeView() {
  const doc = treeUi.doc;
  const known = new Set(doc.arms.map(a => a.id));
  if (state.tArms) {
    state.tArms = new Set([...state.tArms].filter(a => known.has(a)));
    if (!state.tArms.size || state.tArms.size === known.size) state.tArms = null;
  }
  const goals = goalSteps(doc, treeUi.explore);
  const graded = [...goals.keys()].filter(i => !state.tArms || state.tArms.has(doc.runs[i].arm)).length;
  const m = treeModel(doc, goals);
  treeUi.m = m;
  const status = document.querySelector("#treePickers .rl2-tstatus");
  if (status) status.textContent = `${m.runs.length} run${m.runs.length === 1 ? "" : "s"} · ${m.turns} turns · ${m.vis.length} nodes`;
  const on = a => !state.tArms || state.tArms.has(a);
  const setArms = next => {
    state.tArms = !next || next.size === known.size ? null : next;
    state.tEdge = null; state.tPin = null; state.tHover = null;
    syncUrl();
    // a tree the server cut short, or one fetched for some sources only, is fetched again
    if (doc.truncated || doc.arms.some(x => !x.shown)) renderTree(); else drawTreeView();
  };
  const toggleArm = a => {
    const next = new Set(state.tArms || known);
    if (next.has(a)) { if (next.size === 1) return; next.delete(a); } else next.add(a);
    setArms(next);
  };
  $("treeSources").replaceChildren(...[
    el("span", { class: "muted rl2-small" }, "sources"),
    doc.arms.map(a => el("button", { type: "button", class: "rl2-fbtn" + (on(a.id) ? " on" : ""), "aria-pressed": on(a.id) ? "true" : "false",
      title: `${a.label}: ${a.rollouts} run${a.rollouts === 1 ? "" : "s"} of ${doc.game}` + (a.id === "rl" ? " (RL rollouts, from the game start or restored mid-tree)" : ""),
      onclick: () => toggleArm(a.id) }, a.label, el("small", { class: "muted" }, a.rollouts))),
    state.tArms ? el("button", { type: "button", class: "rl2-fbtn", onclick: () => setArms(null) }, "all") : null,
    el("button", { type: "button", class: "rl2-fbtn rl2-goalbtn" + (state.tGoal && graded ? " on" : ""), disabled: graded ? null : true,
      "aria-pressed": state.tGoal && graded ? "true" : "false",
      title: graded ? `Underline each turn with the goal the model held then, as the trace grader judged it (${graded} run${graded === 1 ? "" : "s"} graded in ${doc.game})`
        : `The trace grader has not judged the runs shown in ${doc.game}.`,
      onclick: () => { state.tGoal = !state.tGoal; syncUrl(); drawTreeView(); } },
      el("i", { class: "rl2-egoal", style: `background:${GOAL_COLORS[0]}` }), "goal held")].flat().filter(Boolean));
  const chart = treeChart(doc, m, goals);
  $("treeBody").replaceChildren(...[chart.card, runList(doc, m, goals), el("div", { id: "treeEdge" }), el("div", { id: "treeNode" }),
    modesCard()].filter(Boolean));
  chart.paint();
  edgePanel();
  if (state.tNode) nodePanel(state.tNode);
}

function treeChart(doc, m, goals) {
  const modes = doc.modes;
  const canvas = el("canvas", { class: "rl2-tcanvas", role: "img", "aria-label": `${doc.game}: ${m.runs.length} runs on one tree ` +
    `from the game start (t${doc.tree}, ${TREE_LABELS[doc.tree]}), each turn coloured by its coach mode` });
  const scroll = el("div", { class: "rl2-tscroll" }, canvas);
  const tip = el("div", { class: "rl2-ttip", hidden: true });
  const chart = el("div", { class: "rl2-tchart" }, scroll, tip);
  const laneH = m.lanes <= 24 ? 24 : m.lanes <= 60 ? 18 : m.lanes <= 200 ? 12 : m.lanes <= 800 ? 8 : 5;
  const minT = Math.max(2, Math.round(laneH * 0.3)), maxT = Math.max(minT, Math.round(laneH * 0.72));
  const thick = n => m.maxPlays > 1 ? minT + (maxT - minT) * Math.log(n) / Math.log(m.maxPlays) : minT;
  const H = AXIS_H + m.lanes * laneH + 12;
  const goalOn = state.tGoal && m.runs.some(i => goals.has(i));
  let hit = { dots: [], bars: [], curves: [] };
  const paint = () => {
    if (!canvas.isConnected) return;
    const css = getComputedStyle(canvas);
    const v = (name, fb) => css.getPropertyValue(name).trim() || fb;
    const ink = v("--text", "#111"), muted = v("--muted", "#888"), line = v("--wash-line", "#e5e7eb"), wash = v("--wash", "#f3f4f6"),
      stock = v("--rl2-stock", "#d3d8e0"), red = v("--rl2-red", "#dc2626"), blue = v("--sh-blue", "#2563eb"),
      bg = v("--rl2-canvas", "#fff"), edgeLine = v("--border-strong", "#a9b5c9"), font = v("--rl-mono", "monospace");
    const W = Math.round(Math.max(320, scroll.clientWidth) * state.tZoom);
    const dpr = Math.max(0.5, Math.min(window.devicePixelRatio || 1, Math.sqrt(MAX_AREA / (W * H))));
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    canvas.style.width = W + "px";
    canvas.style.height = H + "px";
    const g = canvas.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, W, H);
    const sx = (W - PAD_L - PAD_R) / m.maxX;
    const px = x => PAD_L + x * sx;
    const py = key => AXIS_H + (m.lane.get(key) + 0.5) * laneH;
    const fill = mi => modes[mi] === "stock" ? stock : modeColor(modes[mi]);
    // axis: ticks every 1/2/5 x 10^k (about 80 px apart), faint guides through the lanes
    const raw = m.maxX / Math.max(2, Math.floor((W - PAD_L - PAD_R) / 80));
    const mag = 10 ** Math.floor(Math.log10(raw));
    const tick = Math.max(1, [1, 2, 5, 10].map(k => k * mag).reduce((a, k) => Math.abs(k - raw) < Math.abs(a - raw) ? k : a));
    g.font = "10px " + font;
    g.textBaseline = "alphabetic";
    for (let x = 0; x <= m.maxX; x += tick) {
      const p = Math.round(px(x)) + 0.5;
      g.fillStyle = line;
      g.fillRect(p - 0.5, AXIS_H - 5, 1, H - AXIS_H);
      g.fillStyle = muted;
      g.textAlign = x === 0 ? "left" : "center";
      g.fillText(String(x), p, AXIS_H - 9);
    }
    // lane pieces (tree edges and run ends) and curves (merges, edges back, loops)
    const pieces = new Map(), curves = new Map();
    for (const [e, kind] of m.kind) {
      const E = doc.edges[e], st = m.es.get(e);
      if (kind === "tree" || kind === "end") {
        const x0 = px(m.nx[E.from]);
        const x1 = Math.max(x0 + 2, px(kind === "tree" ? m.nx[E.to] : m.endX(e)));
        pieces.set(e, { e, x0, x1, y: py(kind === "tree" ? E.to : "e" + e), yf: py(E.from), th: thick(st.plays), st });
      } else {
        curves.set(e, { e, kind, xa: px(m.nx[E.from]), ya: py(E.from), xb: px(m.nx[E.to]), yb: py(E.to), st });
      }
    }
    const curvePath = c => {
      g.beginPath();
      if (c.kind === "self") { g.arc(c.xa, c.ya - 6, 4, 0, Math.PI * 2); return; }
      g.moveTo(c.xa, c.ya);
      if (c.kind === "merge") {
        const mx = (c.xa + c.xb) / 2;
        g.bezierCurveTo(mx, c.ya, mx, c.yb, c.xb, c.yb);
      } else {
        g.quadraticCurveTo((c.xa + c.xb) / 2, Math.min(c.ya, c.yb) - Math.min(70, 14 + Math.abs(c.xa - c.xb) * 0.08), c.xb, c.yb);
      }
    };
    const curvePoints = c => {
      const pts = [];
      if (c.kind === "self") return [[c.xa, c.ya - 6]];
      for (let k = 0; k <= 16; k++) {
        const t = k / 16, u = 1 - t;
        if (c.kind === "merge") {
          const mx = (c.xa + c.xb) / 2;
          pts.push([u * u * u * c.xa + 3 * u * u * t * mx + 3 * u * t * t * mx + t * t * t * c.xb,
            u * u * u * c.ya + 3 * u * u * t * c.ya + 3 * u * t * t * c.yb + t * t * t * c.yb]);
        } else {
          const cx = (c.xa + c.xb) / 2, cy = Math.min(c.ya, c.yb) - Math.min(70, 14 + Math.abs(c.xa - c.xb) * 0.08);
          pts.push([u * u * c.xa + 2 * u * t * cx + t * t * c.xb, u * u * c.ya + 2 * u * t * cy + t * t * c.yb]);
        }
      }
      return pts;
    };
    const major = st => [...st.modes].sort((a, b) => b[1] - a[1])[0][0];
    const strokeCurve = (c, color, width, faint) => {
      g.setLineDash(c.kind === "merge" ? [] : [3, 3]);
      g.strokeStyle = color;
      g.globalAlpha = faint;
      g.lineWidth = width;
      curvePath(c);
      g.stroke();
      g.setLineDash([]);
      g.globalAlpha = 1;
    };
    const bar = (p, counts, th) => {
      const list = [...counts].sort((a, b) => b[1] - a[1]);
      const y0 = p.y - th / 2;
      if (list.length === 1 || th < 5) { g.fillStyle = fill(list[0][0]); g.fillRect(p.x0, y0, p.x1 - p.x0, th); return; }
      const tot = list.reduce((s, [, n]) => s + n, 0);
      let y = y0;
      list.forEach(([mi, n], k) => {
        const h = k === list.length - 1 ? y0 + th - y : Math.max(1, th * n / tot);
        g.fillStyle = fill(mi);
        g.fillRect(p.x0, y, p.x1 - p.x0, h);
        y += h;
      });
    };
    const underline = (p, counts, th) => {
      const tot = counts.reduce((s, n) => s + n, 0);
      if (!tot) return;
      let x = p.x0;
      const y = p.y + th / 2 + 1.5, h = laneH >= 12 ? 3 : 2;
      counts.forEach((n, k) => {
        if (!n) return;
        const w = (p.x1 - p.x0) * n / tot;
        g.fillStyle = GOAL_COLORS[k] || edgeLine;
        g.fillRect(x, y, w, h);
        x += w;
      });
    };
    const marks = (p, cleared, go, level, th) => {
      if (cleared) {
        g.fillStyle = ink;
        g.fillRect(Math.round(p.x1) - 1, p.y - laneH / 2 + 2, 2, laneH - 4);
        if (laneH >= 12) { g.textAlign = "left"; g.fillText(String(level + 1), Math.round(p.x1) + 3, p.y - th / 2 - 1); }
      }
      if (go) {
        const b = p.y + th / 2 + 1;
        g.fillStyle = red;
        g.beginPath();
        g.moveTo(p.x1, b); g.lineTo(p.x1 + 3.5, b + 5); g.lineTo(p.x1 - 3.5, b + 5);
        g.closePath();
        g.fill();
      }
    };
    // even levels on a shaded band; branch connectors; curves; bars; goal underlines; level and game-over marks
    for (const p of pieces.values()) if (p.st.level % 2 === 0) { g.fillStyle = wash; g.fillRect(p.x0, p.y - laneH / 2 + 1, p.x1 - p.x0, laneH - 2); }
    g.fillStyle = edgeLine;
    for (const p of pieces.values()) if (p.y !== p.yf) g.fillRect(Math.round(p.x0) - 0.75, Math.min(p.y, p.yf), 1.5, Math.abs(p.y - p.yf));
    for (const c of curves.values()) {
      if (c.kind === "merge") strokeCurve(c, fill(major(c.st)), Math.max(1, Math.min(3, thick(c.st.plays) / 2)), 0.6);
      else strokeCurve(c, muted, 1, 0.45);
    }
    for (const p of pieces.values()) bar(p, p.st.modes, p.th);
    if (goalOn) for (const p of pieces.values()) underline(p, p.st.goal, p.th);
    for (const p of pieces.values()) marks(p, p.st.cleared > 0, p.st.go > 0, p.st.level, p.th);
    for (const c of curves.values()) if (c.kind === "merge") marks({ x1: c.xb, y: c.yb }, c.st.cleared > 0, c.st.go > 0, c.st.level, 2);
    // nodes: a dot where plays branch, merge or end, the game start in blue, a badge where RL rollouts restarted
    const dots = [];
    for (const n of m.vis) {
      const nOut = (m.outs.get(n) || []).length, nIn = (m.ins.get(n) || []).length;
      if (n === doc.root || nOut !== 1 || nIn !== 1 || doc.nodes[n].started) dots.push({ n, x: px(m.nx[n]), y: py(n) });
    }
    const r0 = laneH >= 12 ? 3 : 2;
    for (const d of dots) {
      g.beginPath();
      g.arc(d.x, d.y, d.n === doc.root ? r0 + 2.5 : r0, 0, Math.PI * 2);
      g.fillStyle = d.n === doc.root ? blue : ink;
      g.fill();
      g.lineWidth = 1;
      g.strokeStyle = bg;
      g.stroke();
    }
    const restarts = new Map();
    for (const i of m.runs) {
      const r = doc.runs[i];
      if (isNum(r.origin)) restarts.set(r.origin, (restarts.get(r.origin) || 0) + 1);
    }
    g.font = "600 9px " + font;
    for (const [n, k] of restarts) {
      const x = px(m.nx[n]), y = py(n), atRoot = n === doc.root;
      if (!atRoot) {
        g.fillStyle = blue;
        g.beginPath();
        g.moveTo(x, y - 5); g.lineTo(x + 5, y); g.lineTo(x, y + 5); g.lineTo(x - 5, y);
        g.closePath();
        g.fill();
      }
      if (laneH >= 16 || atRoot) {
        const text = "restart" + (k > 1 ? ` ×${k}` : "");
        const w = g.measureText(text).width + 8;
        // at the game start the badge sits under the start dot (nothing lies left of it)
        const bx = atRoot ? 1 : Math.max(1, x - w - 7), by = atRoot ? Math.min(H - 14, y + 8) : y - 7;
        g.fillStyle = bg;
        g.fillRect(bx, by, w, 13);
        g.strokeStyle = blue;
        g.lineWidth = 1;
        g.strokeRect(bx + 0.5, by + 0.5, w - 1, 12);
        g.fillStyle = blue;
        g.textAlign = "left";
        g.fillText(text, bx + 4, by + 9.5);
      }
    }
    g.font = "10px " + font;
    // a run hovered or picked in the run list: everything else fades, its own turns in their own modes
    const hl = isNum(state.tHover) ? state.tHover : isNum(state.tPin) ? state.tPin : null;
    if (hl !== null && m.runs.includes(hl)) {
      g.globalAlpha = 0.75;
      g.fillStyle = bg;
      g.fillRect(0, AXIS_H - 4, W, H);
      g.globalAlpha = 1;
      const r = doc.runs[hl], gs = goals.get(hl);
      r.steps.forEach((s, k) => {
        const p = pieces.get(s[1]);
        if (p) {
          const th = Math.max(p.th, minT + 1);
          if (p.y !== p.yf) { g.fillStyle = ink; g.fillRect(Math.round(p.x0) - 0.75, Math.min(p.y, p.yf), 1.5, Math.abs(p.y - p.yf)); }
          g.fillStyle = ink;
          g.fillRect(p.x0 - 0.5, p.y - th / 2 - 1, p.x1 - p.x0 + 1, th + 2);
          bar(p, [[s[2], 1]], th);
          if (goalOn && gs && isNum(gs[k])) underline(p, [0, 1, 2, 3].map(j => j === gs[k] ? 1 : 0), th);
          marks(p, s[6] & F_CLEARED, s[6] & F_GO, s[4], th);
        } else {
          const c = curves.get(s[1]);
          if (c) strokeCurve(c, c.kind === "merge" ? fill(s[2]) : ink, 2, 1);
        }
      });
      if (isNum(r.origin)) {
        const x = px(m.nx[r.origin]), y = py(r.origin);
        g.fillStyle = blue;
        g.beginPath();
        g.moveTo(x, y - 6); g.lineTo(x + 6, y); g.lineTo(x, y + 6); g.lineTo(x - 6, y);
        g.closePath();
        g.fill();
      }
    }
    // the node whose panel is open
    const sel = state.tNode && treeUi.ix.has(state.tNode) ? treeUi.ix.get(state.tNode) : null;
    if (sel !== null && m.lane.has(sel)) {
      g.beginPath();
      g.arc(px(m.nx[sel]), py(sel), 7, 0, Math.PI * 2);
      g.strokeStyle = blue;
      g.lineWidth = 2.5;
      g.stroke();
    }
    hit = { dots, bars: [...pieces.values()], curves: [...curves.values()].map(c => ({ e: c.e, pts: curvePoints(c) })) };
  };
  const find = ev => {
    const rc = canvas.getBoundingClientRect();
    const x = ev.clientX - rc.left, y = ev.clientY - rc.top;
    for (const d of hit.dots) if ((d.x - x) ** 2 + (d.y - y) ** 2 <= 36) return { node: d.n };
    let best = null;
    for (const p of hit.bars) {
      const half = Math.max(p.th / 2, 4);
      if (x >= p.x0 - 1 && x <= p.x1 + 1 && y >= p.y - half && y <= p.y + half) best = p;
    }
    if (best) return { edge: best.e };
    for (const c of hit.curves) if (c.pts.some(([a, b]) => (a - x) ** 2 + (b - y) ** 2 <= 25)) return { edge: c.e };
    return null;
  };
  const place = ev => {
    tip.hidden = false;
    const cr = chart.getBoundingClientRect();
    tip.style.left = Math.max(0, Math.min(ev.clientX - cr.left + 14, cr.width - tip.offsetWidth - 4)) + "px";
    tip.style.top = (ev.clientY - cr.top + 16) + "px";
  };
  canvas.addEventListener("pointermove", ev => {
    const h = find(ev);
    if (!h) { tip.hidden = true; canvas.style.cursor = ""; return; }
    canvas.style.cursor = "pointer";
    tip.replaceChildren(...(h.node !== undefined ? nodeTip(doc, m, h.node) : edgeTip(doc, m, goals, h.edge)));
    place(ev);
  });
  canvas.addEventListener("pointerleave", () => { tip.hidden = true; });
  canvas.addEventListener("click", ev => {
    const h = find(ev);
    if (!h) return;
    if (h.node !== undefined) { selectNode(doc.nodes[h.node].id, { scroll: true }); return; }
    state.tEdge = h.edge;
    edgePanel();
    $("treeEdge")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  });
  treeUi.paint = paint;
  // repaint whenever the chart's width changes (window, side panels, a tab drawn while hidden)
  let lastW = 0;
  const ro = new ResizeObserver(() => {
    if (!canvas.isConnected) { ro.disconnect(); return; }
    const w = scroll.clientWidth;
    if (w && w !== lastW) { lastW = w; paint(); }
  });
  ro.observe(scroll);
  const present = [...new Set([...m.es.values()].flatMap(st => [...st.modes.keys()]))].map(i => modes[i]);
  const ordered = [...modeNames().filter(x => present.includes(x)), ...present.filter(x => !modeNames().includes(x)).sort()];
  const kinds = new Set(m.kind.values());
  const card = el("div", { class: "card rl2-tcard" },
    el("div", { class: "rl2-thead" }, el("b", { class: "mono" }, doc.game),
      el("span", { class: "muted rl2-small", title: TREE_HELP[doc.tree] }, `t${doc.tree} · node = ${TREE_LABELS[doc.tree]} · ` +
        `left to right: ${state.tX === "moves" ? "game moves" : "turns"} since the game start`),
      doc.truncated ? el("span", { class: "rl2-bad rl2-small" }, `only the first ${doc.steps} turns are drawn (whole runs, plays from the start first)`) : null),
    chart,
    el("div", { class: "legend rl2-small" },
      ordered.map(x => el("span", { class: "rl2-lgmode", title: modePrompt(x) || null },
        el("i", { style: `background:${x === "stock" ? "var(--rl2-stock)" : modeColor(x)}` }), x)),
      el("span", {}, el("i", { class: "lg-lvl" }), "tick + number: level cleared (the new level)"),
      el("span", {}, el("i", { class: "lg-golane" }), "red mark: game over"),
      el("span", {}, el("i", { class: "lg-restart" }), "restart: an RL rollout restored from a saved state"),
      el("span", {}, el("i", { class: "lg-band" }), "shaded: even levels"),
      kinds.has("merge") ? el("span", {}, el("i", { class: "lg-merge" }), "curve: plays merging into a node drawn on another lane") : null,
      kinds.has("back") || kinds.has("self") ? el("span", {}, el("i", { class: "lg-back" }), "dashed: back to an earlier node (or the same one)") : null,
      el("span", {}, "thicker: more plays")),
    goalOn ? el("div", { class: "legend rl2-small" }, el("span", {}, "underline, the goal held:"),
      GOAL_NAMES.map((n, k) => el("span", {}, el("i", { class: "rl2-egoal" + (GOAL_COLORS[k] ? "" : " none"),
        style: GOAL_COLORS[k] ? `background:${GOAL_COLORS[k]}` : "" }), n))) : null);
  return { card, paint };
}

const xWord = () => state.tX === "moves" ? "moves" : "turns";
function nodeTip(doc, m, n) {
  const node = doc.nodes[n];
  const sum = list => (list || []).reduce((s, e) => s + m.es.get(e).plays, 0);
  const restarted = m.runs.filter(i => doc.runs[i].origin === n).length;
  return [el("div", { class: "mono rl2-small" }, n === doc.root ? "the game start" : nodeLabel(node.id)),
    el("div", { class: "rl2-small" }, (isNum(m.lvl[n]) ? `level ${m.lvl[n]} · ` : "") + (isNum(node.moves) ? `${node.moves} moves into the level · ` : "") +
      `reached after ${m.nx[n]} ${xWord()}`),
    el("div", { class: "rl2-small" }, `${sum(m.ins.get(n))} turns arrive · ${sum(m.outs.get(n))} leave` +
      (restarted ? ` · ${restarted} restart${restarted === 1 ? "" : "s"} here` : "")),
    el("div", { class: "muted rl2-small" }, "click to open the node")];
}
function turnBits(s, status) {
  const bits = [`L${s[4]}`, `${s[3]} mv`];
  if (isNum(s[7])) bits.push(`${Math.round(s[7] / 100) / 10}k tok`);
  return [el("span", { class: "mono" }, bits.join(" · ")),
    s[6] & F_CLEARED ? el("span", { class: "rl2-yes" }, `cleared L${s[4]}`) : null,
    s[6] & F_GO ? el("span", { class: "rl2-bad" }, "game over") : null,
    isNum(status) ? el("span", { class: "rl2-gstat" }, el("i", { class: "rl2-egoal" + (GOAL_COLORS[status] ? "" : " none"),
      style: GOAL_COLORS[status] ? `background:${GOAL_COLORS[status]}` : "" }), GOAL_NAMES[status]) : null];
}
function edgeTip(doc, m, goals, e) {
  const st = m.es.get(e), E = doc.edges[e], kind = m.kind.get(e);
  const where = kind === "end" ? `${nodeLabel(doc.nodes[E.from].id)} → the run ended`
    : kind === "self" ? `stayed on ${nodeLabel(doc.nodes[E.from].id)}`
      : `${E.from === doc.root ? "start" : nodeLabel(doc.nodes[E.from].id)} → ${nodeLabel(doc.nodes[E.to].id)}` + (kind === "back" ? " (back)" : "");
  const list = [...st.modes].sort((a, b) => b[1] - a[1]);
  const rows = st.steps.slice(0, TIP_TURNS).map(([i, k]) => {
    const r = doc.runs[i], s = r.steps[k], g = goals.get(i);
    return el("div", { class: "rl2-ttturn rl2-small" }, el("span", { class: "mono" }, runName(r, doc.game)),
      el("span", { class: "rl2-dot", style: `background:${doc.modes[s[2]] === "stock" ? "var(--rl2-stock)" : modeColor(doc.modes[s[2]])}` }),
      ...turnBits(s, state.tGoal && g ? g[k] : null));
  });
  return [el("div", { class: "rl2-small" }, el("b", {}, `${st.plays} turn${st.plays === 1 ? "" : "s"}`), ` · ${where}`),
    el("div", { class: "rl2-ttmodes" }, list.map(([mi, n]) => el("span", {}, modeTag(doc.modes[mi]), list.length > 1 ? ` ${n}` : ""))),
    list.length === 1 ? modePromptLine(doc.modes[list[0][0]]) : null,
    ...rows,
    st.steps.length > TIP_TURNS ? el("div", { class: "muted rl2-small" }, `and ${st.steps.length - TIP_TURNS} more`) : null,
    el("div", { class: "muted rl2-small" }, "click to list every turn and read its trace")].filter(Boolean);
}

function runList(doc, m, goals) {
  const groups = doc.arms.map(a => ({ a, runs: m.runs.filter(i => doc.runs[i].arm === a.id) })).filter(x => x.runs.length);
  const chips = new Map();
  const mark = () => { for (const [i, c] of chips) c.classList.toggle("on", state.tPin === i); };
  const chip = i => {
    const r = doc.runs[i];
    const restarted = isNum(r.origin);
    const tip = `${r.id}\nrun ${r.run} · build ${r.build}${r.policy ? " · policy " + r.policy : ""}\n` +
      `${r.status} · ${val(r.levels)} levels · score ${fx(r.score)} · ${val(r.actions)} moves · ${r.steps.length} turns in this tree` +
      (r.origin_kind !== "start" ? `\nrestarted (${r.origin_kind}) from ${r.origin === doc.root ? "the game start" : nodeLabel(doc.nodes[r.path[0]].id)}` : "") +
      (goals.has(i) ? "\ngoal judged by the trace grader" : "") + "\nhover: show its path · click: keep it shown";
    const b = el("button", { type: "button", class: "rl2-trun" + (state.tPin === i ? " on" : ""), title: tip,
      onmouseenter: () => { state.tHover = i; treeUi.paint && treeUi.paint(); },
      onmouseleave: () => { state.tHover = null; treeUi.paint && treeUi.paint(); },
      onfocus: () => { state.tHover = i; treeUi.paint && treeUi.paint(); },
      onblur: () => { state.tHover = null; treeUi.paint && treeUi.paint(); },
      onclick: () => { state.tPin = state.tPin === i ? null : i; mark(); treeUi.paint && treeUi.paint(); } },
      restarted ? el("span", { class: "rl2-tre", "aria-label": "restarted mid-tree" }, "↻") : null,
      el("span", { class: "mono" }, runShort(r, doc.game)),
      el("small", { class: "muted mono" }, `${val(r.levels)} lv` + (isNum(r.score) ? ` · ${fx(r.score, 0)}` : "")),
      goals.has(i) ? el("i", { class: "rl2-egraded", title: "goal judged" }) : null);
    chips.set(i, b);
    return b;
  };
  return el("div", { class: "card rl2-truns" },
    el("div", { class: "rl2-truns-head" }, el("h3", { class: "rl2-subh" }, "Runs"),
      el("span", { class: "muted rl2-small" }, "hover a run to follow its whole path through the tree; click to keep it shown")),
    groups.map(x => el("div", { class: "rl2-tgroup" },
      el("div", { class: "rl2-tarm" }, x.a.label, el("small", { class: "muted" }, ` ${x.runs.length}`)),
      el("div", { class: "rl2-tchips" }, x.runs.map(chip)))));
}

// The turns of the edge clicked: one row per turn, its trace on demand.
function edgePanel() {
  const box = $("treeEdge"), doc = treeUi.doc, m = treeUi.m;
  if (!box || !doc || !m) return;
  const e = state.tEdge;
  const st = isNum(e) ? m.es.get(e) : null;
  if (!st) { box.replaceChildren(); return; }
  const E = doc.edges[e], goals = goalSteps(doc, treeUi.explore);
  const label = n => n === doc.root ? "the game start" : nodeLabel(doc.nodes[n].id);
  const rows = st.steps.slice(0, PANEL_TURNS).map(([i, k]) => turnRow(doc, i, k, goals, E));
  box.replaceChildren(el("div", { class: "card rl2-edge" },
    el("div", { class: "rl2-edge-head" },
      el("h3", { class: "rl2-subh" }, `${st.plays} turn${st.plays === 1 ? "" : "s"} · ${label(E.from)} → ${E.to === null ? "the run ended" : label(E.to)}`),
      el("div", { class: "rl2-bact" },
        el("button", { type: "button", class: "rl2-btn", onclick: () => selectNode(doc.nodes[E.from].id, { scroll: true }) }, "open where it starts"),
        E.to !== null ? el("button", { type: "button", class: "rl2-btn", onclick: () => selectNode(doc.nodes[E.to].id, { scroll: true }) }, "open where it leads") : null,
        el("button", { type: "button", class: "rl2-btn", onclick: () => { state.tEdge = null; edgePanel(); } }, "close"))),
    el("div", { class: "rl2-eturns" }, rows),
    st.steps.length > PANEL_TURNS ? el("div", { class: "muted rl2-small" }, `and ${st.steps.length - PANEL_TURNS} more`) : null));
}
function turnRow(doc, i, k, goals, E) {
  const r = doc.runs[i], s = r.steps[k], key = `${r.id}#${s[0]}`;
  const open = state.tTrace.has(key);
  const g = goals.get(i);
  const row = el("div", { class: "rl2-branch" + (open ? " open" : "") },
    el("div", { class: "rl2-bmain" },
      el("div", { class: "rl2-bwho" }, el("span", { class: "rl2-chip mono", title: `${r.id}\n${armOf(doc, r.arm).label}` },
        runName(r, doc.game)), " ", modeTag(doc.modes[s[2]])),
      el("div", { class: "rl2-bmeta rl2-small" }, el("span", { class: "mono muted" }, `turn ${val(s[5])} · step ${s[0]}`),
        ...turnBits(s, g ? g[k] : null),
        isNum(r.origin) && k === 0 ? el("span", { class: "rl2-origin", title: `restored (${r.origin_kind}) at ` +
          (r.origin === doc.root ? "the game start" : nodeLabel(doc.nodes[r.origin].id)) }, `restart · ${r.origin_kind}`) : null)),
    el("div", { class: "rl2-bact" },
      el("button", { type: "button", class: "rl2-btn" + (open ? " on" : ""), "aria-expanded": open ? "true" : "false",
        onclick: () => { open ? state.tTrace.delete(key) : state.tTrace.add(key); row.replaceWith(turnRow(doc, i, k, goals, E)); } },
        open ? "hide trace" : "trace"),
      el("button", { type: "button", class: "rl2-btn", title: "highlight this run's whole path",
        onclick: () => { state.tPin = i; drawTreeView(); } }, "its path")));
  if (open) {
    const box = el("div", { class: "rl2-trace" }, el("div", { class: "muted rl2-small" }, "loading trace…"));
    row.append(box);
    (async () => {
      let sha = E.plays === 1 ? E.trace : null;
      if (!sha) {
        const ro = await getTree("rollout/" + r.id);
        sha = ((ro.steps || []).find(x => x.seq === s[0]) || {}).trace_sha || null;
      }
      if (!sha) throw new NotPublished("trace");
      const content = await getTree("trace/" + sha);
      const pv = pathView(content, key, null);
      box.replaceChildren(pv.player.node, pv.list);
    })().catch(err => {
      if (!(err instanceof NotPublished)) console.error(err);
      box.replaceChildren(el("div", { class: "muted rl2-small" }, "This turn's trace is not on the server."));
    });
  }
  return row;
}

function selectNode(id, { scroll = false } = {}) {
  state.tNode = id;
  resetNodeUi();
  syncUrl();
  if (treeUi.paint) treeUi.paint();
  nodePanel(id).then(() => { if (scroll) $("treeNode")?.scrollIntoView({ block: "start", behavior: "smooth" }); });
}
const goNode = id => selectNode(id, { scroll: true });

// The node clicked (the Decision tree view's panel): its screen, steps out grouped by mode with clear rate, moves to clear
// and value, the best known path from it, the rollouts restarted there.
async function nodePanel(id) {
  if (!$("treeNode")) return;
  if (!id) { $("treeNode").replaceChildren(); return; }
  $("treeNode").replaceChildren(el("div", { class: "card rl2-npanel muted rl2-small" }, "loading the node…"));
  const close = el("button", { type: "button", class: "rl2-btn", onclick: () => { state.tNode = null; syncUrl(); nodePanel(null); treeUi.paint && treeUi.paint(); } }, "close");
  let view, value;
  try {
    [view, value] = await Promise.all([getTree("node/" + id), getTree("value/" + id).catch(e => {
      if (!(e instanceof NotPublished)) console.error(e);
      return null;
    })]);
  } catch (e) {
    if (state.tNode !== id || !$("treeNode")) return;
    if (!(e instanceof NotPublished)) console.error(e);
    $("treeNode").replaceChildren(el("div", { class: "card rl2-npanel" }, el("div", { class: "rl2-edge-head" },
      el("span", { class: "muted rl2-small" }, e instanceof NotPublished ? `Node ${nodeLabel(id)} is not ${FIXTURE ? "in the fixture" : "published yet"}.`
        : "Could not load this node."), close)));
    return;
  }
  if (state.tNode !== id || !$("treeNode")) return;
  const n = view.node;
  nodeMeta.set(n.id, { level: n.level, moves: n.moves });
  for (const s of view.steps || []) if (s.child && s.child_info) nodeMeta.set(s.child, { level: s.child_info.level, moves: s.child_info.moves });
  const canvas = n.board ? el("canvas", { class: "rl2-board", width: 160, height: 160, "aria-label": "screen at this node" }) : null;
  const root = String(n.id).endsWith(":root");
  const where = root ? `game ${n.game} · the game start` : `game ${n.game} · level ${val(n.level)} · ${val(n.moves)} moves`;
  const head = el("div", { class: "card rl2-node" },
    canvas || el("div", { class: "rl2-board none" }, "no screen stored"),
    el("div", { class: "rl2-node-info" },
      el("div", { class: "rl2-edge-head" }, el("div", { class: "rl2-node-id mono" }, n.id), close),
      el("div", { class: "rl2-node-nums" },
        el("div", {}, el("b", { class: "mono" }, n.steps), el("small", {}, n.steps === 1 ? "step out" : "steps out")),
        el("div", {}, el("b", { class: "mono" }, n.arrivals || 0), el("small", {}, "arrived")),
        el("div", {}, el("b", { class: "mono" }, Object.keys(view.by_action || {}).length), el("small", {}, "modes")),
        (view.started_here || []).length ? el("div", {}, el("b", { class: "mono" }, view.started_here.length), el("small", {}, "restarts here")) : null),
      el("div", { class: "muted rl2-small" }, `${where} · t${view.tree} ${TREE_LABELS[view.tree] || view.tree_name || ""}`),
      view.parents && view.parents.length ? el("div", { class: "rl2-parents rl2-small" }, el("span", { class: "muted" }, "came from"),
        view.parents.slice(0, 12).map(p => el("button", { type: "button", class: "rl2-chip mono", title: `${p.id} (${p.n})`, onclick: () => goNode(p.id) },
          nodeLabel(p.id), p.n > 1 ? ` ×${p.n}` : ""))) : null,
      bestLine(value),
      view.truncated ? el("div", { class: "rl2-small rl2-bad" }, "Only the first steps are shown.") : null));
  $("treeNode").replaceChildren(...[head, startedHere(view), actionGroups(view, value)].filter(Boolean));
  if (canvas) requestAnimationFrame(() => draw(canvas, n.board));
}

// Pieces of the node panel: the restart badge, rollouts restarted at the node, the best known path, steps by mode
function originBadge(kind, origin) {
  if (!kind || kind === "start") return null;
  const tip = `this rollout was restarted mid-tree (${kind}) from ${origin || "?"}`;
  if (origin && treeOf(origin) === state.tTree) {
    return el("button", { type: "button", class: "rl2-origin", title: tip + "; click to open that node", onclick: () => goNode(origin) }, `restart · ${kind}`);
  }
  return el("span", { class: "rl2-origin", title: tip }, `restart · ${kind}`);
}
function startedHere(view) {
  const list = view.started_here || [];
  if (!list.length) return null;
  const wrap = el("div", { class: "card rl2-started" });
  const redraw = () => wrap.replaceWith(startedHere(view));
  wrap.append(el("h3", { class: "rl2-subh" }, `Rollouts started here (${list.length})`),
    el("p", { class: "muted rl2-small" }, "Restarted from this node instead of the game start; their steps below carry a restart badge."));
  for (const r of list) {
    const open = state.tRoll.has(r.id);
    const res = r.result || {};
    const bits = [isNum(res.levels) ? `${res.levels} level${res.levels === 1 ? "" : "s"}` : null,
      isNum(res.actions) ? `${res.actions} actions` : null, isNum(res.score) ? `score ${fx(res.score)}` : null].filter(Boolean);
    const row = el("div", { class: "rl2-sroll" },
      el("div", { class: "rl2-bmain" },
        el("div", { class: "rl2-bwho mono" }, r.id),
        el("div", { class: "rl2-bmeta rl2-small" }, el("span", { class: "rl2-origin" }, r.origin_kind),
          el("span", { class: "rl2-chip mono" }, r.build), r.policy ? el("span", { class: "muted mono" }, r.policy) : null,
          el("span", { class: "muted" }, r.status), ...bits.map(b => el("span", { class: "mono" }, b)))),
      el("div", { class: "rl2-bact" }, el("button", { type: "button", class: "rl2-btn" + (open ? " on" : ""), "aria-expanded": open ? "true" : "false",
        onclick: () => { open ? state.tRoll.delete(r.id) : state.tRoll.add(r.id); redraw(); } }, open ? "hide steps" : "steps")));
    wrap.append(row);
    if (open) {
      const box = el("div", { class: "rl2-rsteps rl2-small" }, el("span", { class: "muted" }, "loading…"));
      row.append(box);
      getTree("rollout/" + r.id).then(doc => {
        const k = state.tTree;
        box.replaceChildren(...[...(doc.steps || []).flatMap((s, i) => [i ? el("span", { class: "muted", "aria-hidden": "true" }, "›") : null,
          el("button", { type: "button", class: "rl2-stepchip", title: `step ${s.seq}: ${s.action} at ${s["n" + k]}`, onclick: () => goNode(s["n" + k]) },
            modeTag(s.action), el("span", { class: "mono muted" }, `L${s.level}`))]),
          doc.truncated ? el("span", { class: "rl2-bad" }, "(first steps only)") : null].filter(Boolean));
      }).catch(e => {
        if (!(e instanceof NotPublished)) console.error(e);
        box.replaceChildren(el("span", { class: "muted" }, "This rollout is not on the server."));
      });
    }
  }
  return wrap;
}
// "Best known path from here": the fewest moves to clear this level any step leaving the node achieved, and the rollout
// that did it; the button lists that rollout's steps from there to the end of the level.
function bestLine(value) {
  const best = value && value.best;
  if (!value) return null;
  if (!best) return el("div", { class: "rl2-best muted rl2-small" }, "No rollout has cleared this level from here yet.");
  const wrap = el("div", { class: "rl2-best rl2-small" });
  const redraw = () => wrap.replaceWith(bestLine(value));
  wrap.append(el("span", {}, "best known path from here: ", el("b", { class: "mono" }, `${best.moves_to_clear} moves`)),
    el("span", { class: "muted mono", title: best.rollout_id }, `${best.rollout_id} #${best.seq}`),
    el("button", { type: "button", class: "rl2-btn" + (state.bestOpen ? " on" : ""), "aria-expanded": state.bestOpen ? "true" : "false",
      onclick: () => { state.bestOpen = !state.bestOpen; redraw(); } }, state.bestOpen ? "hide steps" : "open it"));
  if (state.bestOpen) {
    const box = el("div", { class: "rl2-rsteps" }, el("span", { class: "muted" }, "loading…"));
    wrap.append(box);
    getTree("rollout/" + best.rollout_id).then(doc => {
      const k = state.tTree;
      const from = (doc.steps || []).filter(s => s.seq >= best.seq);
      const lvl = from.length ? from[0].level : null;
      const mine = from.filter(s => s.level === lvl);
      box.replaceChildren(...mine.flatMap((s, i) => [i ? el("span", { class: "muted", "aria-hidden": "true" }, "›") : null,
        el("button", { type: "button", class: "rl2-stepchip", title: `step ${s.seq}: ${s.action}, ${s.moves_step} moves, at ${s["n" + k]}`,
          onclick: () => goNode(s["n" + k]) }, modeTag(s.action), el("span", { class: "mono muted" }, `${s.moves_step} mv`))]).filter(Boolean),
        doc.truncated ? el("span", { class: "rl2-bad" }, "(first steps only)") : "");
    }).catch(e => {
      if (!(e instanceof NotPublished)) console.error(e);
      box.replaceChildren(el("span", { class: "muted" }, "This rollout is not on the server."));
    });
  }
  return wrap;
}
const movesTxt = x => isNum(x) ? `${Number.isInteger(x) ? x : x.toFixed(1)} mv` : "–";
function actionGroups(view, value) {
  const actions = Object.entries(view.by_action || {}).sort((a, b) => b[1].n - a[1].n || a[0].localeCompare(b[0]));
  if (!actions.length) return el("div", { class: "empty" }, "No step leaves this node: the plays ended here.");
  const wrap = el("div", { class: "rl2-groups" });
  const redraw = () => wrap.replaceWith(actionGroups(view, value));
  const vals = (value && value.actions) || {};
  wrap.append(el("div", { class: "rl2-ghead muted rl2-small" }, el("span", {}, "action"), el("span", {}, "n"),
    el("span", {}, "cleared the level"), el("span", { class: "rl2-gmore" }, "moves to clear · also")));
  for (const [action, s] of actions) {
    const open = state.tOpen.has(action);
    const v = vals[action] || {};
    const rate = isNum(v.clear_rate) ? v.clear_rate : s.cleared;
    const mtc = isNum(v.mean_moves_to_clear) ? v.mean_moves_to_clear : s.moves_to_clear;
    const kids = (s.children || []).length;
    const row = el("button", { type: "button", class: "rl2-grow" + (open ? " open" : ""), "aria-expanded": open ? "true" : "false",
      onclick: () => { open ? state.tOpen.delete(action) : state.tOpen.add(action); redraw(); } },
      el("span", { class: "rl2-gmode" }, el("span", { class: "rl2-caret", "aria-hidden": "true" }, open ? "▾" : "▸"), modeTag(action)),
      el("span", { class: "mono" }, s.n),
      el("span", { class: "rl2-gbar", title: "share of these steps whose rollout went on to clear this level" },
        el("span", { class: "rl2-bar" }, el("i", { style: `width:${isNum(rate) ? (100 * rate).toFixed(1) : 0}%` })),
        el("b", { class: "mono" }, pctOrDash(rate))),
      el("span", { class: "rl2-gmore mono muted", title: "mean moves to clear (steps that cleared) · Q (mean of −moves, −" +
          `${value ? value.penalty : 200} if never cleared) · level within 30 actions · mean actions · game over · children` },
        el("b", { class: "rl2-mtc" }, movesTxt(mtc)),
        (isNum(v.q) ? ` · Q ${fx(v.q)}` : "") + ` · ≤30 ${pctOrDash(s.lvl30)} · ${fx(s.acts)} acts · over ${pctOrDash(s.go)}` +
        ` · ${kids} child${kids === 1 ? "" : "ren"}`));
    wrap.append(row);
    if (open) {
      const kids = s.children || [];
      wrap.append(el("div", { class: "rl2-blist" },
        el("div", { class: "rl2-kids rl2-small" }, el("span", { class: "muted" }, "leads to"),
          kids.map(c => el("button", { type: "button", class: "rl2-chip mono", title: c.id, onclick: () => goNode(c.id) }, nodeLabel(c.id), c.n > 1 ? ` ×${c.n}` : "")),
          s.ended ? el("span", { class: "muted" }, `${s.ended} ended here`) : null),
        view.steps.filter(b => b.action === action).map(b => stepItem(b, redraw))));
    }
  }
  return wrap;
}
function outcomeBits(o) {
  if (!o || !Object.keys(o).length) return [el("span", { class: "muted" }, "no outcome")];
  const bits = [];
  if (o.acts !== undefined && o.acts !== null) bits.push(el("span", {}, `${val(o.acts)} actions`));
  if (o.cleared_level) bits.push(el("span", { class: "rl2-yes" }, "cleared the level"));
  else if (o.lvl30) bits.push(el("span", { class: "rl2-yes" }, "level within 30"));
  if (o.go_turn) bits.push(el("span", { class: "rl2-bad" }, "game over"));
  return bits;
}
function stepItem(b, redraw) {
  const tOpen = state.tTrace.has(b.id);
  const ci = b.child_info;
  const d = b.detail || {};
  let next;
  if (!b.child) next = el("span", { class: "muted rl2-small" }, "rollout ended");
  else if (ci && ci.published === false) next = el("span", { class: "muted rl2-small", title: b.child }, "next node not published");
  else next = el("button", { type: "button", class: "rl2-btn primary", title: b.child, onclick: () => goNode(b.child) }, "next node →",
    ci && ci.arrivals > 1 ? el("span", { class: "rl2-merge", title: `${ci.arrivals} steps reached this node (${ci.steps} steps leave it)` }, `${ci.arrivals} arrived`) : null);
  const traceBtn = b.trace_sha ? el("button", { type: "button", class: "rl2-btn" + (tOpen ? " on" : ""), "aria-expanded": tOpen ? "true" : "false",
    onclick: () => { tOpen ? state.tTrace.delete(b.id) : state.tTrace.add(b.id); redraw(); } }, tOpen ? "hide trace" : "trace")
    : el("span", { class: "muted rl2-small" }, "no trace");
  const item = el("div", { class: "rl2-branch" + (tOpen ? " open" : "") },
    el("div", { class: "rl2-bmain" },
      el("div", { class: "rl2-bwho mono" }, el("b", {}, `#${b.seq}`), ` ${b.rollout_id}`),
      el("div", { class: "rl2-bmeta rl2-small" },
        originBadge(b.origin_kind, b.origin_state),
        el("span", { class: "rl2-chip mono" }, b.build), b.policy ? el("span", { class: "muted mono" }, b.policy) : null,
        el("span", { class: "mono" }, `cap ${val(d.cap)}`), el("span", { class: "mono" }, `p ${val(d.prob)}`),
        ...outcomeBits(b.outcome))),
    el("div", { class: "rl2-bact" }, traceBtn, next));
  if (tOpen) {
    const box = el("div", { class: "rl2-trace" }, el("div", { class: "muted rl2-small" }, "loading trace…"));
    item.append(box);
    getTree("trace/" + b.trace_sha).then(content => {
      const pv = pathView(content, b.id, null);
      box.replaceChildren(pv.player.node, pv.list);
    }).catch(e => {
      if (!(e instanceof NotPublished)) console.error(e);
      box.replaceChildren(el("div", { class: "muted rl2-small" }, "This trace is not on the server."));
    });
  }
  return item;
}

/* ------------------------------------------------------------------ view 5: training (the RL campaign) */
// One campaign document per RL campaign, written by the learner after every round: the rollout VMs, the rounds, the
// policy's mode mix at a few typical situations, totals by the first (assigned) mode, and the sibling groups (one row
// per node of the tree, one chip per try). A node links to the Tree view at that node.
const STATUS_TONE = { RUNNING: "run", PROVISIONING: "wait", STAGING: "wait", STOPPING: "wait", SUSPENDING: "wait" };
const when = t => {
  if (t === null || t === undefined || t === "") return "–";
  const d = new Date(isNum(t) ? t * 1000 : t);
  return isNaN(d) ? String(t) : d.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
};
const nodeHex = id => (String(id).split(":")[2] || "?").slice(0, 8);
async function renderTraining() {
  const body = $("trnBody");
  body.replaceChildren(el("div", { class: "empty" }, "loading…"));
  let index;
  try {
    index = await getDoc("rl-campaigns");
  } catch (e) {
    $("trnPickers").replaceChildren();
    if (e instanceof NotPublished) { body.replaceChildren(el("div", { class: "empty" }, "No training campaign published yet.")); return; }
    body.replaceChildren(el("div", { class: "empty" }, e.status === 401 ? "Sign in with your team account to see the training."
      : e.status === 403 ? "This Google account is not on the team list." : "Could not load the training campaigns."));
    if (!e.status) console.error(e);
    return;
  }
  const camps = (index.campaigns || []).filter(c => c && c.name);
  if (!camps.length) {
    $("trnPickers").replaceChildren();
    body.replaceChildren(el("div", { class: "empty" }, "No training campaign published yet."));
    return;
  }
  if (!state.camp || !camps.some(c => c.name === state.camp)) state.camp = camps[0].name;
  const sel = el("select", { "aria-label": "campaign", onchange: e => { state.camp = e.target.value; state.campAll = false; renderTraining(); } },
    camps.map(c => el("option", { value: c.name, selected: c.name === state.camp }, `${c.name} · updated ${when(c.updated)}`)));
  $("trnPickers").replaceChildren(el("label", {}, "campaign ", sel));
  syncUrl();
  let doc;
  try {
    doc = await getDoc("rl-campaign-" + state.camp);
  } catch (e) {
    if (e instanceof NotPublished) { body.replaceChildren(el("div", { class: "empty" }, "This campaign's status is not published yet.")); return; }
    throw e;
  }
  $("trnPickers").append(el("span", { class: "muted rl2-small" }, `${doc.harness || ""}${doc.harness ? " · " : ""}data ${when(doc.generated_at)}`));
  body.replaceChildren(
    el("h3", { class: "rl2-h3" }, "Machines"), vmStrip(doc.vms || []),
    el("h3", { class: "rl2-h3" }, "Rounds"), roundsTable(doc.rounds || []),
    el("h3", { class: "rl2-h3" }, `What the policy picks now · ${(doc.policy || {}).version || "no policy"}`), policyBars(doc.policy || {}),
    el("h3", { class: "rl2-h3" }, "How each first mode did"), totalsCard(doc.totals || {}, doc.advantage_by_action || {}),
    el("h3", { class: "rl2-h3" }, "Sibling groups"), siblingGroups(doc));
}
function vmStrip(vms) {
  if (!vms.length) return el("div", { class: "empty" }, "No VM has started for this campaign yet.");
  return el("div", { class: "rl2-vms" }, vms.map(v => {
    const r = v.restores || {};
    const tone = STATUS_TONE[v.status] || "off";
    return el("div", { class: "card rl2-vm" },
      el("div", { class: "rl2-vm-top" }, el("b", { class: "mono" }, v.name),
        el("span", { class: "rl2-status " + tone }, String(v.status || "unknown").toLowerCase())),
      el("div", { class: "rl2-vm-phase rl2-small", title: v.phase_time || "" },
        el("span", { class: "muted" }, "phase "), el("span", { class: "mono" }, v.last_phase || "–"),
        v.phase_time ? el("span", { class: "muted" }, ` · ${when(v.phase_time)}`) : null),
      el("div", { class: "rl2-vm-nums" },
        el("div", {}, el("b", { class: "mono" }, val(v.tries_done)), el("small", {}, "tries done")),
        el("div", {}, el("b", { class: "mono" }, val(v.tries_running)), el("small", {}, "running")),
        el("div", {}, el("b", { class: "mono" }, val(v.cleared)), el("small", {}, "cleared"))),
      el("div", { class: "rl2-vm-meta rl2-small" },
        el("span", { title: "nodes restored by replaying the logged play" }, `replay ${r.replay_exact ?? 0}`),
        el("span", { title: "nodes restored from a state snapshot" }, `snapshot ${r.snapshot ?? 0}`),
        r.unknown ? el("span", {}, `other ${r.unknown}`) : null,
        el("span", { class: "muted", title: "mean seconds to restore a node" }, `restore ${isNum(v.mean_restore_s) ? fx(v.mean_restore_s) + " s" : "–"}`),
        isNum(v.cached_tokens_first_request) ? el("span", { class: "muted", title: "mean cached tokens of each try's first request" +
          (isNum(v.prompt_tokens_first_request) ? ` (of ${Math.round(v.prompt_tokens_first_request)} prompt tokens)` : "") },
          `cached ${Math.round(v.cached_tokens_first_request / 1000)}k`) : null,
        v.errors ? el("span", { class: "rl2-bad" }, `${v.errors} error${v.errors === 1 ? "" : "s"}`) : null),
      el("div", { class: "muted rl2-small mono rl2-vm-run" }, v.run_id || ""));
  }));
}
function roundsTable(rounds) {
  if (!rounds.length) return el("div", { class: "empty" }, "No round yet.");
  const head = ["round", "policy", "trained", "train steps", "nodes with siblings", "ESS", "jobs", "tries", "at"];
  return el("div", { class: "rl2-scroll" }, el("table", { class: "rl2-table" },
    el("thead", {}, el("tr", {}, head.map(h => el("th", {}, h)))),
    el("tbody", {}, [...rounds].reverse().map(r => el("tr", {},
      el("td", { class: "mono" }, r.round), el("td", { class: "mono" }, r.version || "–"),
      el("td", { class: r.trained ? "rl2-yes" : "muted" }, r.trained ? "yes" : "·"),
      el("td", { class: "mono" }, val(r.train_steps)), el("td", { class: "mono" }, val(r.nodes_with_siblings)),
      el("td", { class: "mono" }, isNum(r.ess) ? fx(r.ess) : "–"),
      el("td", { class: "mono" }, val(r.jobs)), el("td", { class: "mono" }, val(r.tries)),
      el("td", { class: "muted" }, when(r.t)))))));
}
function policyBars(pol) {
  const pts = pol.mode_dist_at || [];
  if (!pts.length || pts.every(p => !Object.keys(p.dist || {}).length)) return el("div", { class: "empty" }, "No policy yet.");
  const modes = [...new Set(pts.flatMap(p => Object.keys(p.dist || {})))];
  return el("div", { class: "card rl2-mix" },
    el("div", { class: "muted rl2-small" }, `${pol.kind || "policy"} · seq ${val(pol.seq)}` +
      (pol.stats && isNum(pol.stats.ess) ? ` · ESS ${fx(pol.stats.ess)}` : "") + (pol.trained_at ? ` · trained ${when(pol.trained_at)}` : "")),
    pts.map(p => {
      const d = Object.entries(p.dist || {}).sort((a, b) => b[1] - a[1]);
      return el("div", { class: "rl2-mixrow" },
        el("span", { class: "rl2-mixname" }, p.label),
        el("div", { class: "rl2-mixbar", role: "img", "aria-label": d.map(([m, x]) => `${m} ${pct(x)}`).join(", ") },
          d.map(([m, x]) => el("span", { style: `width:${(100 * x).toFixed(2)}%;background:${modeColor(m)}`, title: `${m}: ${pct(x)}` }))),
        el("span", { class: "mono muted rl2-small" }, d.length ? `${d[0][0]} ${pct(d[0][1])}` : "–"));
    }),
    el("div", { class: "legend rl2-small" }, modes.map(m => el("span", {}, el("i", { style: `background:${modeColor(m)}` }), m))));
}
function totalsCard(t, adv) {
  const by = Object.entries(t.by_first_action || {});
  if (!t.tries) return el("div", { class: "empty" }, "No try has finished yet.");
  return el("div", {},
    el("div", { class: "card rl2-tot" },
      el("div", {}, el("b", { class: "mono" }, t.tries), el("small", {}, "tries")),
      el("div", {}, el("b", { class: "mono" }, t.cleared), el("small", {}, "cleared")),
      el("div", {}, el("b", { class: "mono" }, pct(t.clear_rate)), el("small", {}, "clear rate")),
      el("div", {}, el("b", { class: "mono" }, isNum(t.mean_moves_to_clear) ? fx(t.mean_moves_to_clear) : "–"), el("small", {}, "moves to clear")),
      el("div", {}, el("b", { class: "mono" }, val(t.nodes_with_siblings)), el("small", {}, "nodes with siblings")),
      t.censored ? el("div", { title: "tries cut short (deadline, divergence, abort): left out of every number here" },
        el("b", { class: "mono muted" }, t.censored), el("small", {}, "cut short")) : null),
    el("div", { class: "rl2-scroll" }, el("table", { class: "rl2-table rl2-acts" },
      el("thead", {}, el("tr", {}, ["first mode", "tries", "cleared", "mean moves", "advantage"].map(h => el("th", {}, h)))),
      el("tbody", {}, by.map(([m, a]) => {
        const g = adv[m] || {};
        const ad = g.mean_adv;
        return el("tr", {}, el("td", {}, modeTag(m)), el("td", { class: "mono" }, a.n),
          el("td", {}, el("span", { class: "rl2-gbar" }, el("span", { class: "rl2-bar" }, el("i", { style: `width:${isNum(a.clear_rate) ? (100 * a.clear_rate).toFixed(1) : 0}%` })),
            el("b", { class: "mono" }, pct(a.clear_rate)))),
          el("td", { class: "mono" }, isNum(a.mean_moves) ? fx(a.mean_moves) : "–"),
          el("td", { class: "mono " + (isNum(ad) ? (ad > 0 ? "rl2-yes" : ad < 0 ? "rl2-bad" : "") : "muted"),
            title: isNum(ad) ? `mean reward minus the siblings' mean at the same node, over ${g.n} tries` : "no sibling to compare with" },
            isNum(ad) ? (ad > 0 ? "+" : ad < 0 ? "−" : "±") + Math.abs(ad).toFixed(2) : "–"));
      })))),
    el("p", { class: "muted rl2-small" }, "Advantage: the try's reward (a cleared level scores level × (fastest known moves ÷ its moves)²) minus " +
      "the mean of its siblings at the same node. Above zero: faster than the other modes there."));
}
function openTreeAt(node, game) {
  resetTreeSel();
  state.tGame = game;
  state.tTree = treeOf(node);
  state.tNode = node;
  state.treeShown = false;
  show("tree");
  $("view-tree").scrollIntoView({ block: "start" });
}
function siblingGroups(doc) {
  const nodes = doc.nodes || [];
  if (!nodes.length) return el("div", { class: "empty" }, "No node has finished tries yet.");
  const shown = state.campAll ? nodes : nodes.slice(0, 40);
  const used = [...new Set(nodes.flatMap(n => (n.tries || []).map(t => t.action)))];
  const wrap = el("div", { class: "rl2-sibs" });
  wrap.append(el("p", { class: "muted rl2-small" }, `${doc.nodes_total ?? nodes.length} nodes, newest round first. One chip per try, ` +
    "coloured by its first mode: filled ✓ with the moves it took to clear the level, outlined ✗ when it did not, dashed when it was cut short. " +
    "The ring marks the fastest try. Click a node to open it in the Tree."));
  for (const n of shown) {
    const tries = n.tries || [];
    const best = n.best_moves;
    let ringed = false;
    const href = `?${FIXTURE ? "fixture=1&" : ""}view=tree&tgame=${encodeURIComponent(n.game)}&node=${encodeURIComponent(n.node)}`;
    wrap.append(el("div", { class: "rl2-sib" },
      el("div", { class: "rl2-sib-head" },
        el("a", { class: "rl2-sib-node mono", href, title: `${n.node}\nopen in the Tree`,
          onclick: e => { if (e.metaKey || e.ctrlKey || e.shiftKey) return; e.preventDefault(); openTreeAt(n.node, n.game); } },
          `${n.game} · L${val(n.level)} · ${nodeHex(n.node)}`),
        n.class ? el("span", { class: "rl2-kind" }, n.class.replace("_", " ")) : null,
        el("span", { class: "muted rl2-small mono" }, `round ${val(n.round)}`),
        el("span", { class: "rl2-small rl2-sib-sum" },
          el("span", { class: "muted" }, "best "), el("b", { class: "mono" }, isNum(best) ? `${best} mv` : "–"),
          el("span", { class: "muted" }, " · stock "), el("b", { class: "mono" }, isNum(n.stock_moves) ? `${n.stock_moves} mv` : "–"))),
      el("div", { class: "rl2-sib-chips" }, tries.map(t => {
        const isBest = !ringed && t.cleared && isNum(best) && t.moves_to_clear === best && !t.censored;
        if (isBest) ringed = true;
        const c = modeColor(t.action);
        const cls = "rl2-try" + (t.censored ? " cut" : t.cleared ? " ok" : " no") + (isBest ? " best" : "");
        const tip = `${t.action}${isBest ? " (fastest)" : ""}\n` + (t.censored ? `cut short: ${t.stop || "?"}` : t.cleared
          ? `cleared in ${val(t.moves_to_clear)} moves` : `not cleared (${t.stop || "stopped"})`) +
          `\n${val(t.turns)} turns · ${isNum(t.tokens) ? Math.round(t.tokens / 1000) + "k" : "–"} tokens · policy ${t.policy_version || "–"} · round ${val(t.round)}`;
        return el("span", { class: cls, title: tip, style: t.cleared && !t.censored ? `background:${c};border-color:${c}` : `border-color:${c};color:${c}` },
          t.censored ? "cut" : t.cleared ? `✓ ${val(t.moves_to_clear)}` : "✗");
      }))));
  }
  if (nodes.length > 40) wrap.append(el("button", { type: "button", class: "rl2-btn", onclick: () => { state.campAll = !state.campAll; wrap.replaceWith(siblingGroups(doc)); } },
    state.campAll ? "show the newest 40" : `show all ${nodes.length}`));
  wrap.append(el("div", { class: "legend rl2-small" }, used.map(m => el("span", {}, el("i", { style: `background:${modeColor(m)}` }), m))));
  return wrap;
}

/* ------------------------------------------------------------------ shell */
function show(view) {
  state.view = view;
  for (const b of $("tabs").querySelectorAll("button")) {
    const on = b.dataset.view === view;
    b.classList.toggle("on", on);
    b.setAttribute("aria-selected", on ? "true" : "false");
  }
  for (const v of VIEWS) $("view-" + v).hidden = v !== view;
  syncUrl();
  // the tree and training views have their own data; they do not wait for the dashboard
  if (!state.dash && view !== "tree" && view !== "training") return;
  if (view === "tree" && state.treeShown) return;
  if (view === "tree") state.treeShown = true;
  if (view === "training" && state.trainingShown) return;
  if (view === "training") state.trainingShown = true;
  const fn = { builds: renderBuilds, decisions: renderDecisions, tree: renderTree, training: renderTraining }[view];
  Promise.resolve().then(fn).catch(err => {
    console.error(view, err);
    if (err && err.status === 401) notice("Sign in with your team account to see the RL2 page.");
  });
}
async function load() {
  for (const b of $("tabs").querySelectorAll("button")) b.addEventListener("click", () => show(b.dataset.view));
  show(state.view);
  try {
    state.dash = await getDoc("dashboard");
  } catch (e) {
    if (e instanceof NotPublished) notice("The RL2 data is not published yet. It appears here once the coach loop publishes its first dashboard.");
    else if (e.status === 401) notice("Sign in with your team account to see the RL2 page.");
    else if (e.status === 403) notice("This Google account is not on the team list.");
    else { console.error(e); notice("Could not load the RL2 data."); }
    $("updated").textContent = "no data";
    return;
  }
  notice(FIXTURE ? "Fixture data (fake, for checking the page): not results." : "");
  const at = state.dash.generated_at;
  $("updated").textContent = at ? "updated " + new Date(at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "updated –";
  $("footR").textContent = at ? `Data ${new Date(at).toLocaleString()}` : "";
  show(state.view);
  // the tree drew before the modes arrived: redraw its legend with their order and prompt lines
  if (state.view === "tree" && treeUi.doc) drawTreeView();
}
// repaint the tree when the theme changes (its colours come from the page's CSS; its width is watched in treeChart)
new MutationObserver(() => { if (state.view === "tree" && treeUi.paint) requestAnimationFrame(treeUi.paint); })
  .observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
load();

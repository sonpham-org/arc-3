// RL2 page (docs/rl2.html): the turn coach. Six views over published documents and the decision tree:
//   GET /api/v1/rl2/doc/dashboard     builds (a tree), modes, situations, sampling tables
//   GET /api/v1/rl2/doc/run-<run id>  one run's decisions, game by game (loaded when a run is opened, and by Lanes for
//                                     every run of the builds picked there)
//   GET /api/v1/rl2/doc/explore-index, explore-<game>  Exploration: every run of the best combo per game, coach mode
//                                     per turn and the trace grader's goal labels (grader/explore_publish.py)
//   GET /api/v1/rl2/doc/rl-campaigns  the RL training campaigns ({campaigns: [{name, updated}]})
//   GET /api/v1/rl2/doc/rl-campaign-<name>  one campaign: VMs, rounds, policy, totals, sibling groups
//                                     (gcp/controllers/gtree-rollout/rl_loop.py publish-status, arc3-sglang-parking repo)
//   GET /api/v1/gtree/games           the universal game tree: games, their five trees and each tree's start (root)
//   GET /api/v1/gtree/node/<id>       one node of one tree: its steps grouped by action, children, parents, restarts here
//   GET /api/v1/gtree/value/<id>      per action: clear rate, mean moves to clear, Q; V; the best known path from the node
//   GET /api/v1/gtree/shortest?...    one level's shortest known path in moves, merged across runs (screen graph)
//   GET /api/v1/gtree/frontier?...    restart candidates (mode coverage / uncertain / backward)
//   GET /api/v1/gtree/rollout/<id>    one rollout's steps (for rollouts restarted mid-tree)
//   GET /api/v1/gtree/trace/<sha>     one step's turn: thinking, code, moves
// Server: railway/rl_review.py. With ?fixture=1 the page reads docs/static/data/rl2-fixture.json instead (fake data, for
// checking the page locally). Chrome from theme.css and rl-shell.css; every colour is solid (no gradients).

import { draw, pathView } from "./review-ui.js?v=20261003-coach";

const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
const FIXTURE = params.get("fixture") === "1";
const VIEWS = ["builds", "decisions", "lanes", "explore", "sampling", "tree", "training"];
const MIN_N = 20;

const state = {
  dash: null, fixture: null, view: VIEWS.includes(params.get("view")) ? params.get("view") : "builds",
  run: params.get("run"), game: params.get("game"), modeFilter: new Set(), open: new Set(), docs: {},
  smpBuild: params.get("build"), metric: "share",
  // tree view: the game and tree (t1..t5) picked, the trail of nodes walked (last = shown), open action groups, traces
  // and restarted rollouts, the best-path box, the restart-candidates panel and its mode
  treeGames: null, tGame: params.get("tgame"), tTree: +(params.get("ttree") || 1),
  trail: (params.get("trail") || "").split(",").filter(Boolean), tOpen: new Set(), tTrace: new Set(), tRoll: new Set(),
  treeCache: {}, frontOpen: true, frontAll: false, frontMode: "coverage", bestOpen: false,
  // training view: the campaign shown, and whether every sibling group is listed
  camp: params.get("campaign"), campAll: false,
  // lanes view: the builds picked (null = the default set), the game, x axis (moves | index), lanes or the all-games
  // grid, the zoom; focusDec: a decision the Decisions view scrolls to once drawn (opened from a lane)
  lnBuilds: params.get("builds") ? new Set(params.get("builds").split(",").filter(Boolean)) : null,
  lnGame: params.get("view") === "lanes" ? params.get("game") : null, lnX: params.get("x") === "index" ? "index" : "moves",
  lnAll: params.get("all") === "1", lnZoom: 1, focusDec: null,
  // exploration view: the game tab, x axis (moves | index), zoom
  eGame: params.get("egame"), eX: params.get("ex") === "index" ? "index" : "moves", eZoom: 1,
};

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
  if (state.view === "lanes") {
    if (state.lnGame && !state.lnAll) q.set("game", state.lnGame);
    if (state.lnBuilds && !sameSet(state.lnBuilds, defaultLaneBuilds())) q.set("builds", [...state.lnBuilds].join(","));
    if (state.lnX === "index") q.set("x", "index");
    if (state.lnAll) q.set("all", "1");
  }
  if (state.view === "explore") { if (state.eGame) q.set("egame", state.eGame); if (state.eX === "index") q.set("ex", "index"); }
  if (state.view === "sampling" && state.smpBuild) q.set("build", state.smpBuild);
  if (state.view === "tree" && state.tGame) {
    q.set("tgame", state.tGame);
    if (state.tTree !== 1) q.set("ttree", String(state.tTree));
    if (state.trail.length) q.set("trail", state.trail.join(","));
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
const modeNames = () => (state.dash.modes || []).map(m => m.name);

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
  if (state.focusDec !== null) {
    const id = state.focusDec;
    state.focusDec = null;
    requestAnimationFrame(() => document.getElementById(`dec-${id}`)?.scrollIntoView({ block: "center" }));
  }
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

/* ------------------------------------------------------------------ view 3: sampling */
function renderSampling() {
  const smp = state.dash.sampling || {};
  const byBuild = smp.by_build || {};
  const builds = (state.dash.builds || []).filter(b => byBuild[b.id] || (b.policy && b.policy.table));
  if (!builds.length) {
    $("smpPickers").replaceChildren();
    $("smpBody").replaceChildren(el("div", { class: "empty" }, "No sampling data yet."));
    return;
  }
  if (!state.smpBuild || !builds.some(b => b.id === state.smpBuild)) state.smpBuild = builds[0].id;
  const b = builds.find(x => x.id === state.smpBuild);
  const sel = el("select", { "aria-label": "build", onchange: e => { state.smpBuild = e.target.value; renderSampling(); } },
    builds.map(x => el("option", { value: x.id, selected: x.id === state.smpBuild }, `${x.id} · ${x.label || ""}`)));
  const seg = el("div", { class: "rl2-seg", role: "group", "aria-label": "cell value" },
    [["share", "share of decisions"], ["lvl30", "level within 30 vs stock"]].map(([k, t]) =>
      el("button", { type: "button", class: state.metric === k ? "on" : "", onclick: () => { state.metric = k; renderSampling(); } }, t)));
  $("smpPickers").replaceChildren(el("label", {}, "build ", sel), seg);
  syncUrl();

  const sits = state.dash.situations || [];
  const grid = byBuild[b.id];
  const extra = grid ? [...new Set(Object.values(grid).flatMap(c => Object.keys(c)))].filter(m => !modeNames().includes(m)) : [];
  const modes = [...modeNames(), ...extra];
  const parts = [];
  if (grid) {
    parts.push(el("h3", { class: "rl2-h3" }, state.metric === "share" ? "What it picked" : "How it went, against stock"),
      gridTable(sits, modes, (sit, m) => {
        const c = (grid[sit.key] || {})[m];
        if (!c) return null;
        return state.metric === "share" ? shareCell(c.share, c.n) : deltaCell(c, (smp.stock_baseline || {})[sit.key]);
      }, state.metric === "lvl30" ? sit => {
        const base = (smp.stock_baseline || {})[sit.key];
        return base ? `${pct(base.lvl30)} (n ${base.n})` : "–";
      } : sit => {
        const n = Object.values(grid[sit.key] || {}).reduce((s, c) => s + (c.n || 0), 0);
        return String(n);
      }, state.metric === "lvl30" ? "stock" : "turns"),
      state.metric === "lvl30" ? diverging() : null);
  } else {
    parts.push(el("div", { class: "empty" }, "No decisions sampled for this build yet."));
  }
  if (b.policy && b.policy.table) {
    const t = b.policy.table;
    parts.push(el("h3", { class: "rl2-h3" }, `What it will pick: policy ${b.policy.version || ""}`),
      el("p", { class: "sub" }, "The policy's probabilities per situation: what the coach samples from on the next run."),
      gridTable(sits, modes, (sit, m) => {
        const p = (t[sit.key] || {})[m];
        return isNum(p) ? shareCell(p, null) : null;
      }));
  }
  parts.push(el("h3", { class: "rl2-h3" }, "Mode mix per build"), mixBars(byBuild), modesCard());
  $("smpBody").replaceChildren(...parts.filter(Boolean));
}
function gridTable(sits, modes, cell, rowExtra, extraHead, rowHead = "situation") {
  return el("div", { class: "rl2-scroll" }, el("table", { class: "rl2-grid" },
    el("thead", {}, el("tr", {}, el("th", { class: "sit" }, rowHead), rowExtra ? el("th", {}, extraHead) : null,
      modes.map(m => el("th", {}, modeTag(m))))),
    el("tbody", {}, sits.map(s => el("tr", {},
      el("th", { class: "sit", scope: "row" }, s.label || s.key, el("small", { class: "mono" }, s.key)),
      rowExtra ? el("td", { class: "mono muted rl2-extra" }, rowExtra(s)) : null,
      modes.map(m => cell(s, m) || el("td", { class: "rl2-cell none" }, "·")))))));
}
function shareCell(share, n) {
  const k = Math.max(0, Math.min(1, share / 0.6));
  const mix = Math.round(6 + k * 80);
  return el("td", { class: "rl2-cell" + (mix > 52 ? " ink" : ""), style: `background:color-mix(in srgb, var(--rl2-blue) ${mix}%, var(--sh-card))`,
    title: `${pct(share)}${n !== null && n !== undefined ? ` of decisions, n ${n}` : ""}` },
    pct(share), n !== null && n !== undefined ? el("small", {}, `n ${n}`) : null);
}
function deltaCell(c, base, minN = MIN_N, baseMin = 0) {
  if (!base || !isNum(c.lvl30) || !isNum(base.lvl30)) return el("td", { class: "rl2-cell none" }, "–");
  const d = c.lvl30 - base.lvl30;
  const pts = Math.round(d * 100);
  const txt = (pts > 0 ? "+" : pts < 0 ? "−" : "±") + Math.abs(pts);
  const tip = `level within 30 actions: ${pct(c.lvl30)} vs stock ${pct(base.lvl30)} · n ${c.n}` +
    (isNum(c.acts) ? ` · ${fx(c.acts)} actions per turn` : "") + (isNum(c.go) ? ` · game over ${pct(c.go)}` : "");
  if ((c.n || 0) < minN || (base.n ?? baseMin) < baseMin) return el("td", { class: "rl2-cell thin", title: tip + " (too few to tell)" }, txt, el("small", {}, `n ${c.n}`));
  const k = Math.min(1, Math.abs(d) / 0.2);
  const mix = Math.round(8 + k * 78);
  const hue = d >= 0 ? "var(--rl2-blue)" : "var(--rl2-red)";
  return el("td", { class: "rl2-cell" + (mix > 52 ? " ink" : ""), style: `background:color-mix(in srgb, ${hue} ${mix}%, var(--sh-card))`, title: tip },
    txt, el("small", {}, `n ${c.n}`));
}
function diverging(minN = MIN_N) {
  const sw = (hue, mix) => el("i", { style: `background:color-mix(in srgb, ${hue} ${mix}%, var(--sh-card))` });
  return el("div", { class: "legend rl2-small" },
    el("span", {}, sw("var(--rl2-red)", 86), sw("var(--rl2-red)", 40), "worse than stock"),
    el("span", {}, sw("var(--rl2-blue)", 40), sw("var(--rl2-blue)", 86), "better than stock"),
    el("span", {}, el("i", { class: "lg-thin" }), `fewer than ${minN} turns`),
    el("span", {}, "numbers are percentage points"));
}
function mixBars(byBuild) {
  const ids = Object.keys(byBuild);
  if (!ids.length) return el("div", { class: "empty" }, "No decisions sampled yet.");
  const modes = modeNames();
  return el("div", { class: "card rl2-mix" }, ids.map(id => {
    const tot = {};
    for (const cell of Object.values(byBuild[id])) for (const [m, c] of Object.entries(cell)) tot[m] = (tot[m] || 0) + (c.n || 0);
    const n = Object.values(tot).reduce((s, x) => s + x, 0);
    const order = [...modes.filter(m => tot[m]), ...Object.keys(tot).filter(m => !modes.includes(m))];
    return el("div", { class: "rl2-mixrow" + (id === state.smpBuild ? " on" : "") },
      el("button", { type: "button", class: "rl2-mixname mono", onclick: () => { state.smpBuild = id; renderSampling(); } }, id),
      el("div", { class: "rl2-mixbar", title: order.map(m => `${m} ${pct(tot[m] / n)}`).join("\n") },
        order.map(m => el("span", { style: `width:${(100 * tot[m] / n).toFixed(2)}%;background:${modeColor(m)}`, title: `${m}: ${pct(tot[m] / n)} (${tot[m]})` }))),
      el("span", { class: "mono muted rl2-small" }, `${n} turns`));
  }), el("div", { class: "legend rl2-small" }, modes.map(m => el("span", {}, el("i", { style: `background:${modeColor(m)}` }), m))));
}
function modesCard() {
  const modes = state.dash.modes || [];
  if (!modes.length) return null;
  return el("details", { class: "card rl2-modes" }, el("summary", {}, "The modes: what each one adds to the turn"),
    el("div", { class: "rl2-scroll" }, el("table", { class: "rl2-table" },
      el("thead", {}, el("tr", {}, ["mode", "line added to the turn", "thinking", "cap", "temp"].map(h => el("th", {}, h)))),
      el("tbody", {}, modes.map(m => el("tr", {}, el("td", {}, modeTag(m.name)), el("td", { class: "rl2-linecell" }, m.line || "(nothing: stock turn)"),
        el("td", { class: "mono" }, val(m.yield_tokens)), el("td", { class: "mono" }, val(m.cap)), el("td", { class: "mono" }, val(m.temperature))))))));
}

/* ------------------------------------------------------------------ view 4: decision tree (the universal game tree) */
// Every step of every rollout is stored once and read as five trees: t1 the path of actions (context-aware), t2 screen +
// moves, t3 level + screen, t4 screen only, t5 level + screen + moves bucketed by 6 (the restart grid). A node's steps are
// grouped by action (the mode chosen); a step leads to a child node, and plays that reach the same child merge there. Each
// tree starts at the game's root (the game start). Rollouts can also start in the middle of the tree (restarted from a
// stored t1 node): their steps carry an origin badge. The objective is game MOVES to clear a level: per action the clear
// rate and mean moves to clear, the best known path from a node, and per level the shortest path known across all runs.
const TREES = [1, 2, 3, 4, 5];
const TREE_NAMES = { 1: "path (context-aware)", 2: "screen + moves", 3: "level + screen", 4: "screen only",
  5: "screen + move bucket (restart grid)" };
const FRONT_MODES = [["coverage", "nodes short of samples"], ["uncertain", "short of samples, unsure clear rate first"],
  ["backward", "on the best known paths, nearest the goal first"]];
const FRONTIER_N = 4;
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

async function renderTree() {
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
  }
  const games = state.treeGames;
  if (!games.length) {
    $("treePickers").replaceChildren();
    body.replaceChildren(el("div", { class: "empty" }, "No tree published yet. It appears here once a run publishes its steps."));
    return;
  }
  let g = games.find(x => x.game === state.tGame);
  if (!g) { g = games[0]; state.tGame = g.game; state.trail = []; }
  if (!TREES.includes(state.tTree)) state.tTree = 1;
  const t = (g.trees || {})[String(state.tTree)] || {};
  const prefix = `${g.game}:t${state.tTree}:`;
  if (!state.trail.length || !state.trail.every(id => id.startsWith(prefix))) state.trail = t.start ? [t.start] : [];
  const gameSel = el("select", { "aria-label": "game", onchange: e => { state.tGame = e.target.value; state.trail = []; resetNodeUi(); renderTree(); } },
    games.map(x => el("option", { value: x.game, selected: x.game === g.game },
      `${x.game} · ${x.rollouts} rollout${x.rollouts === 1 ? "" : "s"}${x.mid_rollouts ? ` (${x.mid_rollouts} mid-tree)` : ""}`)));
  const treeSel = el("select", { "aria-label": "tree", onchange: e => { state.tTree = +e.target.value; state.trail = []; resetNodeUi(); renderTree(); } },
    TREES.map(k => el("option", { value: k, selected: k === state.tTree },
      `t${k} · ${TREE_NAMES[k]} · ${((g.trees || {})[String(k)] || {}).nodes ?? 0} nodes`)));
  $("treePickers").replaceChildren(el("label", {}, "game ", gameSel), el("label", {}, "tree ", treeSel),
    el("span", { class: "muted rl2-small" }, `${g.steps ?? 0} steps`));
  syncUrl();
  if (!state.trail.length) { body.replaceChildren(el("div", { class: "empty" }, "This tree has no nodes for this game yet.")); return; }
  await drawNode(state.trail[state.trail.length - 1]);
}
function resetNodeUi() { state.tOpen.clear(); state.tTrace.clear(); state.tRoll.clear(); state.bestOpen = false; }
function goNode(id, { push = true, fromStart = false } = {}) {
  if (fromStart) {
    const start = state.trail[0];
    state.trail = start && start !== id ? [start, id] : [id];
  } else if (push) {
    const at = state.trail.indexOf(id);
    state.trail = at >= 0 ? state.trail.slice(0, at + 1) : [...state.trail, id];
  }
  resetNodeUi();
  syncUrl();
  drawNode(id).then(() => $("view-tree").scrollIntoView({ block: "start" }));
}

async function drawNode(id) {
  const body = $("treeBody");
  let view, value;
  try {
    [view, value] = await Promise.all([getTree("node/" + id), getTree("value/" + id).catch(e => {
      if (!(e instanceof NotPublished)) console.error(e);
      return null;
    })]);
  } catch (e) {
    if (!(e instanceof NotPublished)) throw e;
    body.replaceChildren(trailBar(), el("div", { class: "empty" }, `Node ${id} is not published yet.`), frontierPanel());
    return;
  }
  const n = view.node;
  nodeMeta.set(n.id, { level: n.level, moves: n.moves });
  for (const s of view.steps || []) if (s.child && s.child_info) nodeMeta.set(s.child, { level: s.child_info.level, moves: s.child_info.moves });
  const canvas = n.board ? el("canvas", { class: "rl2-board", width: 160, height: 160, "aria-label": "screen at this node" }) : null;
  const root = String(n.id).endsWith(":root");
  const where = root ? `game ${n.game} · the game start` : `game ${n.game} · level ${val(n.level)} · ${val(n.moves)} moves`;
  const head = el("div", { class: "card rl2-node" },
    canvas || el("div", { class: "rl2-board none" }, "no screen stored"),
    el("div", { class: "rl2-node-info" },
      el("div", { class: "rl2-node-id mono" }, n.id),
      el("div", { class: "rl2-node-nums" },
        el("div", {}, el("b", { class: "mono" }, n.steps), el("small", {}, n.steps === 1 ? "step out" : "steps out")),
        el("div", {}, el("b", { class: "mono" }, n.arrivals || 0), el("small", {}, "arrived")),
        el("div", {}, el("b", { class: "mono" }, Object.keys(view.by_action || {}).length), el("small", {}, "actions")),
        (view.started_here || []).length ? el("div", {}, el("b", { class: "mono" }, view.started_here.length), el("small", {}, "restarts here")) : null),
      el("div", { class: "muted rl2-small" }, `${where} · t${view.tree} ${view.tree_name || TREE_NAMES[view.tree] || ""}`),
      view.parents && view.parents.length ? el("div", { class: "rl2-parents rl2-small" }, el("span", { class: "muted" }, "came from"),
        view.parents.slice(0, 12).map(p => el("button", { type: "button", class: "rl2-chip mono", title: `${p.id} (${p.n})`, onclick: () => goNode(p.id) },
          nodeLabel(p.id), p.n > 1 ? ` ×${p.n}` : ""))) : null,
      bestLine(value),
      view.truncated ? el("div", { class: "rl2-small rl2-bad" }, "Only the first steps are shown.") : null));
  const level = isNum(n.level) ? n.level : Math.min(...(view.steps || []).map(s => s.level).filter(isNum), Infinity);
  body.replaceChildren(...[trailBar(), head, startedHere(view), actionGroups(view, value),
    isFinite(level) ? shortestPanel(level, n.id) : null, frontierPanel()].filter(Boolean));
  if (canvas) requestAnimationFrame(() => draw(canvas, n.board));
}
function trailBar() {
  const first = state.trail[0] || "";
  if (state.trail.length < 2 && first.endsWith(":root")) {
    return el("div", { class: "rl2-trail muted rl2-small" }, "Game start. Open an action, then follow a step with “next node →”.");
  }
  return el("nav", { class: "rl2-trail rl2-small", "aria-label": "nodes visited" }, state.trail.flatMap((id, i) => {
    const last = i === state.trail.length - 1;
    return [i ? el("span", { class: "muted", "aria-hidden": "true" }, "›") : null,
      last ? el("span", { class: "rl2-chip on mono", "aria-current": "page" }, nodeLabel(id))
        : el("button", { type: "button", class: "rl2-chip mono", onclick: () => goNode(id) }, nodeLabel(id))];
  }));
}
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
          el("button", { type: "button", class: "rl2-stepchip", title: `step ${s.seq}: ${s.action} at ${s["n" + k]}`, onclick: () => goNode(s["n" + k], { fromStart: true }) },
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
// Shortest known path to clear one level, merged across every run on the screen graph (t3, t4 or t5; t1 and t2 use t3):
// its length in moves, its steps (from any rollouts), and this node's own distance when it is on that graph.
function shortestPanel(level, nodeId) {
  const game = state.tGame, tree = state.tTree >= 3 ? state.tTree : 3;
  const box = el("div", { class: "card rl2-short" }, el("h3", { class: "rl2-subh" }, `Shortest known path · level ${level} · t${tree}`),
    el("div", { class: "muted rl2-small" }, "loading…"));
  getTree(`shortest?game=${game}&level=${level}&tree=${tree}`).then(doc => {
    const kids = [el("h3", { class: "rl2-subh" }, `Shortest known path · level ${level} · t${tree}`)];
    const best = doc.best;
    if (!best) {
      kids.push(el("p", { class: "muted rl2-small" }, "No run has cleared this level yet."));
    } else {
      const rollouts = new Set(best.steps.map(s => s.rollout_id)).size;
      kids.push(el("p", { class: "rl2-small" }, el("b", { class: "mono" }, `${best.moves} moves`),
        ` in ${best.steps.length} step${best.steps.length === 1 ? "" : "s"}` +
        (rollouts > 1 ? `, joined from ${rollouts} runs (no single run went this way)` : ", one run") +
        ` · ${doc.goal_steps} clearing step${doc.goal_steps === 1 ? "" : "s"} known`));
      kids.push(el("div", { class: "rl2-rsteps" }, best.steps.flatMap((s, i) => [i ? el("span", { class: "muted", "aria-hidden": "true" }, "›") : null,
        el("button", { type: "button", class: "rl2-stepchip", title: `${s.id}: ${s.action}, ${s.moves_step} moves` +
            (tree === state.tTree ? "; click to open its node" : ""), disabled: tree === state.tTree ? null : true,
          onclick: tree === state.tTree ? () => goNode(s.from) : null },
          modeTag(s.action), el("span", { class: "mono muted" }, `${s.moves_step} mv`))]).filter(Boolean)));
    }
    const here = tree === state.tTree ? (doc.nodes || []).find(x => x.id === nodeId) : null;
    if (here) kids.push(el("p", { class: "rl2-small" }, isNum(here.distance)
      ? [`From this node: `, el("b", { class: "mono" }, `${here.distance} moves`), ` (next: `, modeTag(here.action), `)`]
      : el("span", { class: "muted" }, "From this node no known path clears the level.")));
    if (state.tTree < 3) kids.push(el("p", { class: "muted rl2-small" }, "Paths merge on screens, so this panel reads tree t3 (level + screen)."));
    if (doc.truncated) kids.push(el("p", { class: "rl2-bad rl2-small" }, `Only the first ${doc.steps_read} steps of this level were read.`));
    box.replaceChildren(...kids);
  }).catch(e => {
    if (!(e instanceof NotPublished)) console.error(e);
    box.replaceChildren(el("h3", { class: "rl2-subh" }, `Shortest known path · level ${level}`),
      el("p", { class: "muted rl2-small" }, "No steps of this level are stored yet."));
  });
  return box;
}

// Restart candidates (server ranking), three ways: nodes short of N samples (coverage); the same plus how unsure the
// clear rate is and a count bonus (uncertain); the nodes on each level's best known path, nearest the goal first
// (backward: start just before the goal, then move the start back).
function frontierPanel() {
  const game = state.tGame, tree = state.tTree, mode = state.frontMode;
  const key = `${game}|${tree}|${mode}`;
  const intro = {
    coverage: `Nodes where some action has fewer than ${FRONTIER_N} samples, ranked by few steps out + depth + `
      + "the spread between actions' cleared rates + 0.5 when several rollouts meet.",
    uncertain: `Nodes where some action has fewer than ${FRONTIER_N} samples, ranked as above plus p(1−p) of the clear rate `
      + "and 1/√(steps out + 1).",
    backward: "Nodes on each level's shortest known path, nearest the goal first: restart just before the goal, then further back.",
  }[mode];
  const box = el("details", { class: "card rl2-front", open: state.frontOpen ? "" : null,
    ontoggle: e => { state.frontOpen = e.target.open; } },
    el("summary", {}, `Restart candidates · ${game} · t${tree}`),
    el("div", { class: "rl2-seg rl2-fmode", role: "group", "aria-label": "ranking" }, FRONT_MODES.map(([m, label]) =>
      el("button", { type: "button", class: m === mode ? "on" : "", "aria-pressed": m === mode ? "true" : "false", title: label,
        onclick: () => { state.frontMode = m; state.frontAll = false; box.replaceWith(frontierPanel()); } }, m))),
    el("p", { class: "muted rl2-small" }, intro + " Click one to open it."));
  const list = el("div", { class: "rl2-frows" }, el("div", { class: "muted rl2-small" }, "loading…"));
  box.append(list);
  getTree(`frontier?game=${game}&tree=${tree}&N=${FRONTIER_N}&limit=50` + (mode === "coverage" ? "" : `&mode=${mode}`)).then(doc => {
    if (`${state.tGame}|${state.tTree}|${state.frontMode}` !== key) return;
    const rows = doc.nodes || [];
    for (const r of rows) nodeMeta.set(r.id, { level: r.level, moves: (nodeMeta.get(r.id) || {}).moves });
    if (!rows.length) {
      list.replaceChildren(el("div", { class: "muted rl2-small" }, mode === "backward" ? "No run has cleared a level in this game yet."
        : "Every node has enough samples."));
      return;
    }
    const shown = state.frontAll ? rows : rows.slice(0, 10);
    const parts = mode === "uncertain" ? ["few", "depth", "spread", "merge", "uncertain", "explore"] : ["few", "depth", "spread", "merge"];
    const tip = r => `${r.id}\n${r.out} steps out · ${r.arrivals} arrived from ${r.arrival_rollouts} rollout(s)` +
      (r.started_here ? ` · ${r.started_here} restart(s) here` : "") +
      (mode === "backward" ? `\nnext: ${r.action} (${r.step}); restart from t1 node ${r.t1}` : "") +
      (Object.keys(r.open || {}).length ? `\nshort of ${doc.N}: ` + Object.entries(r.open).map(([a, k]) => `${a} ${k}`).join(", ") : "");
    list.replaceChildren(
      mode === "backward"
        ? el("div", { class: "rl2-frow head muted" }, el("span", {}, "node"), el("span", {}, "to goal"),
          el("span", { class: "rl2-fparts" }, "next step"), el("span", {}, "level"))
        : el("div", { class: "rl2-frow head muted" }, el("span", {}, "node"), el("span", {}, "score"),
          el("span", { class: "rl2-fparts" }, parts.join(" · ")), el("span", {}, "open")),
      ...shown.map(r => el("button", { type: "button", class: "rl2-frow", title: tip(r), onclick: () => goNode(r.id, { fromStart: true }) },
        el("span", { class: "mono rl2-fid" }, nodeLabel(r.id)),
        mode === "backward" ? el("b", { class: "mono" }, movesTxt(r.distance)) : el("b", { class: "mono" }, fx(r.score, 2)),
        mode === "backward" ? el("span", { class: "rl2-fparts" }, modeTag(r.action))
          : el("span", { class: "mono muted rl2-fparts" }, parts.map(p => fx((r.parts || {})[p], 2)).join(" · ")),
        el("span", { class: "mono" }, mode === "backward" ? `L${r.level}` : r.missing))),
      rows.length > 10 ? el("button", { type: "button", class: "rl2-btn rl2-fmore", onclick: () => { state.frontAll = !state.frontAll; box.replaceWith(frontierPanel()); } },
        state.frontAll ? "show the top 10" : `show all ${rows.length}`) : "");
  }).catch(e => {
    if (!(e instanceof NotPublished)) console.error(e);
    list.replaceChildren(el("div", { class: "muted rl2-small" }, "No restart candidates for this tree yet."));
  });
  return box;
}

/* ------------------------------------------------------------------ view 5: training (the RL campaign) */
// One campaign document per RL campaign, written by the learner after every round: the rollout VMs, the rounds, the
// policy's mode mix at a few typical situations, totals by the first (assigned) mode, and the sibling groups (one row
// per node of the tree, one chip per try). A node links to the Decision tree view at that node.
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
  state.tGame = game;
  state.tTree = 1;
  state.trail = [node];
  resetNodeUi();
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
    "The ring marks the fastest try. Click a node to open it in the Decision tree."));
  for (const n of shown) {
    const tries = n.tries || [];
    const best = n.best_moves;
    let ringed = false;
    const href = `?${FIXTURE ? "fixture=1&" : ""}view=tree&tgame=${encodeURIComponent(n.game)}&trail=${encodeURIComponent(n.node)}`;
    wrap.append(el("div", { class: "rl2-sib" },
      el("div", { class: "rl2-sib-head" },
        el("a", { class: "rl2-sib-node mono", href, title: `${n.node}\nopen in the Decision tree`,
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

/* ------------------------------------------------------------------ view 3: lanes (every run's play of one game) */
// One lane per run for the chosen game: each decision is a segment from its game move (f.actions_total) to the next
// decision's, coloured by the mode picked (stock light grey so the other modes stand out). A tick + the new level number
// marks a level-up (o.lvl_turn, at the end of that turn), a red mark a game over (o.go_turn), a thin gap a level boundary.
// Under the lanes: per mode, how often its turns were followed by a level-up / game over / a level within 30 moves,
// against stock in the same game. "All games" swaps the lanes for a games × modes grid of that last number.
const LANE_MIN_N = 15;
const BEST_COMBO = "sbt06hic11/";
const LANE_H = 34, LANE_TOP = 13, LANE_BAR = 15, AXIS_H = 22, PAD_L = 4, PAD_R = 16;
const ZOOMS = [1, 2, 4, 8];
const lanesUi = { token: 0, missing: new Set(), failed: new Set(), paint: null };
const sameSet = (a, b) => a.size === b.size && [...a].every(x => b.has(x));
// builds with at least one run that has decisions; the best combo's coach builds first
function laneBuilds() {
  const list = (state.dash.builds || []).filter(b => (b.runs || []).some(r => (r.decisions || 0) > 0));
  const best = b => b.id.startsWith(BEST_COMBO) ? 0 : 1;
  return list.map((b, i) => [b, i]).sort((x, y) => best(x[0]) - best(y[0]) || x[1] - y[1]).map(x => x[0]);
}
const defaultLaneBuilds = () => state.dash ? new Set(laneBuilds().map(b => b.id)) : new Set();
function shortNames(ids) {
  const last = id => String(id).split("/").pop().replace(/^coach-/, "") || String(id);
  const counts = {};
  for (const id of ids) counts[last(id)] = (counts[last(id)] || 0) + 1;
  return Object.fromEntries(ids.map(id => [id, counts[last(id)] > 1 ? id : last(id)]));
}
const runLetter = run => { const m = String(run).match(/-([a-z])(?:-\d+)?$/); return m ? m[1] : String(run).slice(-6); };
// a level-up is drawn at the end of its turn; the level it reached is the next decision's level when that is higher
const newLevel = (decs, i) => {
  const now = (decs[i].f || {}).level, next = decs[i + 1] && (decs[i + 1].f || {}).level;
  return isNum(next) && isNum(now) && next > now ? next : isNum(now) ? now + 1 : "?";
};
function segEnd(decs, i) {
  const d = decs[i], at = (d.f || {}).actions_total || 0;
  const next = decs[i + 1] && (decs[i + 1].f || {}).actions_total;
  return isNum(next) && next >= at ? next : at + ((d.o && d.o.acts) || 0);
}
async function loadRuns(runs, progress) {
  const need = runs.filter(r => !state.docs["run-" + r.run] && !lanesUi.missing.has(r.run));
  let done = 0, i = 0;
  progress(done, need.length);
  const worker = async () => {
    while (i < need.length) {
      const r = need[i++];
      try { await getDoc("run-" + r.run); } catch (e) {
        if (e instanceof NotPublished) lanesUi.missing.add(r.run);
        else if (e.status === 401 || e.status === 403) throw e;
        else { console.error(r.run, e); lanesUi.failed.add(r.run); }
      }
      progress(++done, need.length);
    }
  };
  await Promise.all(Array.from({ length: Math.min(6, need.length) }, worker));
}
function modeStats(decs) {
  const s = {};
  for (const d of decs) {
    if (!d.o) continue;
    const c = s[d.mode] || (s[d.mode] = { n: 0, lvl: 0, go: 0, l30: 0 });
    c.n++;
    if (d.o.lvl_turn) c.lvl++;
    if (d.o.go_turn) c.go++;
    if (d.o.lvl30) c.l30++;
  }
  for (const c of Object.values(s)) { c.lvl_rate = c.lvl / c.n; c.go_rate = c.go / c.n; c.lvl30 = c.l30 / c.n; }
  return s;
}
const orderModes = present => [...modeNames().filter(m => present.includes(m)), ...present.filter(m => !modeNames().includes(m)).sort()];

async function renderLanes() {
  const token = ++lanesUi.token;
  const builds = laneBuilds();
  if (!builds.length) {
    $("lnPickers").replaceChildren();
    $("lnBody").replaceChildren(el("div", { class: "empty" }, "No run with coach decisions yet."));
    return;
  }
  const known = new Set(builds.map(b => b.id));
  if (!state.lnBuilds) state.lnBuilds = defaultLaneBuilds();
  state.lnBuilds = new Set([...state.lnBuilds].filter(id => known.has(id)));
  const names = shortNames(builds.map(b => b.id));
  const runsOf = b => (b.runs || []).filter(r => (r.decisions || 0) > 0);
  const chips = el("div", { class: "rl2-lbuilds", role: "group", "aria-label": "builds" },
    el("span", { class: "muted rl2-small" }, "builds"),
    builds.map(b => {
      const on = state.lnBuilds.has(b.id);
      return el("button", { type: "button", class: "rl2-fbtn" + (on ? " on" : ""), "aria-pressed": on ? "true" : "false",
        title: `${b.id}${b.label ? " · " + b.label : ""}\n${runsOf(b).length} run(s) with decisions`,
        onclick: () => { on ? state.lnBuilds.delete(b.id) : state.lnBuilds.add(b.id); renderLanes(); } },
        names[b.id], el("small", { class: "muted" }, runsOf(b).length));
    }),
    el("button", { type: "button", class: "rl2-fbtn", onclick: () => { state.lnBuilds = defaultLaneBuilds(); renderLanes(); } }, "all"));
  const seg = (label, opts, cur, set) => el("div", { class: "rl2-seg", role: "group", "aria-label": label }, opts.map(([k, t]) =>
    el("button", { type: "button", class: cur === k ? "on" : "", "aria-pressed": cur === k ? "true" : "false", onclick: () => { set(k); renderLanes(); } }, t)));
  const status = el("span", { class: "muted rl2-small" });
  const gameSlot = el("span", { class: "rl2-lgame" });
  const controls = el("div", { class: "rl2-lctl" }, gameSlot,
    seg("show", [[false, "lanes"], [true, "all games"]], state.lnAll, v => { state.lnAll = v; }),
    state.lnAll ? null : seg("x axis", [["moves", "game moves"], ["index", "decision #"]], state.lnX, v => { state.lnX = v; }),
    state.lnAll ? null : seg("zoom", ZOOMS.map(z => [z, z === 1 ? "fit" : z + "×"]), state.lnZoom, v => { state.lnZoom = v; }),
    status);
  $("lnPickers").replaceChildren(chips, controls);
  syncUrl();

  const picked = builds.filter(b => state.lnBuilds.has(b.id));
  const runs = picked.flatMap(b => runsOf(b).map(r => ({ ...r, build: b.id })));
  if (!runs.length) { $("lnBody").replaceChildren(el("div", { class: "empty" }, "Pick at least one build.")); return; }
  const body = $("lnBody");
  if (runs.some(r => !state.docs["run-" + r.run] && !lanesUi.missing.has(r.run))) body.replaceChildren(el("div", { class: "empty" }, "loading…"));
  await loadRuns(runs, (k, n) => { if (token === lanesUi.token && n) status.textContent = `loading runs ${k} of ${n}…`; });
  if (token !== lanesUi.token) return;
  const loaded = runs.filter(r => state.docs["run-" + r.run]).map(r => ({ ...r, doc: state.docs["run-" + r.run] }));
  const gone = runs.length - loaded.length;
  status.textContent = `${loaded.length} run${loaded.length === 1 ? "" : "s"}` + (gone ? ` · ${gone} not published` : "");
  if (!loaded.length) { body.replaceChildren(el("div", { class: "empty" }, "None of these runs' decisions are published yet.")); return; }
  const games = [...new Set(loaded.flatMap(r => Object.keys(r.doc.games || {})))].sort();
  if (!games.length) { body.replaceChildren(el("div", { class: "empty" }, "These runs have no decisions.")); return; }
  // default: the game the most picked runs played (ties: the first by id)
  const nRuns = g => loaded.filter(r => ((r.doc.games || {})[g] || []).length).length;
  if (!state.lnGame || !games.includes(state.lnGame)) state.lnGame = games.reduce((a, g) => nRuns(g) > nRuns(a) ? g : a, games[0]);
  if (!state.lnAll) {
    gameSlot.replaceChildren(el("label", {}, "game ", el("select", { "aria-label": "game", onchange: e => { state.lnGame = e.target.value; renderLanes(); } },
      games.map(g => el("option", { value: g, selected: g === state.lnGame },
        `${g} (${loaded.filter(r => (r.doc.games || {})[g]).length} runs)`)))));
  }
  syncUrl();
  if (state.lnAll) { body.replaceChildren(allGamesGrid(loaded, games)); return; }

  const game = state.lnGame;
  const lanes = loaded.filter(r => ((r.doc.games || {})[game] || []).length).map(r => {
    const dash = allRuns().find(x => x.run === r.run) || {};
    const pg = ((r.doc.score || {}).per_game || {})[game] ?? (dash.per_game || {})[game];
    const decs = r.doc.games[game];
    return { run: r.run, build: r.build, decs, name: `${names[r.build]} ${runLetter(r.run)}`,
      score: isNum(pg) ? fx(pg) : `all-25 ${fx((r.doc.score || {}).all25 ?? r.all25)}`, perGame: isNum(pg),
      end: segEnd(decs, decs.length - 1) };
  });
  if (!lanes.length) { body.replaceChildren(el("div", { class: "empty" }, `No picked run has decisions in ${game}.`)); return; }
  const all = lanes.flatMap(l => l.decs);
  body.replaceChildren(laneChart(lanes, game), el("h3", { class: "rl2-h3" }, `Mode effect for ${game}`), effectTable(all, lanes.length));
  lanesUi.paint();
}

function laneChart(lanes, game) {
  const present = orderModes([...new Set(lanes.flatMap(l => l.decs.map(d => d.mode)))]);
  const labels = el("div", { class: "rl2-llabels" },
    el("div", { class: "rl2-laxis muted", style: `height:${AXIS_H}px` }, state.lnX === "moves" ? "moves →" : "decision →"),
    lanes.map(l => el("div", { class: "rl2-llabel", style: `height:${LANE_H}px`,
      title: `${l.run}\nbuild ${l.build}\n${l.decs.length} decisions · ${l.perGame ? "score in " + game : "no per-game score; run"} ${l.score}` },
      el("span", { class: "rl2-lname" }, l.name), el("span", { class: "mono muted" }, l.score))));
  const canvas = el("canvas", { class: "rl2-lcanvas", role: "img",
    "aria-label": `${lanes.length} runs of ${game}, one lane each, coloured by the coach mode of each decision` });
  const scroll = el("div", { class: "rl2-lscroll" }, canvas);
  const tip = el("div", { class: "rl2-ltip", hidden: true });
  const chart = el("div", { class: "rl2-lchart" }, labels, scroll, tip);
  let hits = [];
  const paint = () => {
    if (!canvas.isConnected) return;
    const css = getComputedStyle(canvas);
    const v = (name, fb) => css.getPropertyValue(name).trim() || fb;
    const ink = v("--text", "#111"), muted = v("--muted", "#888"), line = v("--wash-line", "#ddd"), card = v("--sh-card", "#fff"),
      track = v("--wash", "#f3f4f6"), stock = v("--rl2-stock", "#d4d9e1"), red = v("--rl2-red", "#dc2626");
    const avail = Math.max(160, scroll.clientWidth);
    const W = Math.round(avail * state.lnZoom);
    const H = AXIS_H + lanes.length * LANE_H;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    canvas.style.width = W + "px";
    canvas.style.height = H + "px";
    const g = canvas.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, W, H);
    const byMoves = state.lnX === "moves";
    const maxX = Math.max(1, ...lanes.map(l => byMoves ? l.end : l.decs.length));
    const sx = x => PAD_L + x * (W - PAD_L - PAD_R) / maxX;
    // axis: ticks every 1/2/5 × 10^k (nearest to ~70 px), faint guides through every lane
    const raw = maxX / Math.max(2, Math.floor((W - PAD_L - PAD_R) / 70));
    const mag = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 5, 10].map(k => k * mag).reduce((a, k) => Math.abs(k - raw) < Math.abs(a - raw) ? k : a);
    g.font = "10px " + v("--rl-mono", "monospace");
    g.textBaseline = "alphabetic";
    for (let x = 0; x <= maxX; x += step) {
      const px = Math.round(sx(x)) + 0.5;
      g.fillStyle = line;
      g.fillRect(px - 0.5, AXIS_H - 4, 1, H - AXIS_H + 4);
      g.fillStyle = muted;
      g.textAlign = x === 0 ? "left" : "center";
      g.fillText(String(x), px, AXIS_H - 8);
    }
    hits = [];
    lanes.forEach((l, li) => {
      const y0 = AXIS_H + li * LANE_H, by = y0 + LANE_TOP;
      g.fillStyle = track;
      g.fillRect(sx(0), by, Math.max(2, sx(byMoves ? l.end : l.decs.length) - sx(0)), LANE_BAR);
      const segs = [];
      l.decs.forEach((d, i) => {
        const a = byMoves ? (d.f || {}).actions_total || 0 : i, b = byMoves ? segEnd(l.decs, i) : i + 1;
        const x0 = sx(a), w = Math.max(2, sx(b) - x0);
        g.fillStyle = d.mode === "stock" ? stock : modeColor(d.mode);
        g.fillRect(x0, by, w, LANE_BAR);
        segs.push([x0, x0 + w, i]);
      });
      // level boundaries: a thin gap where the level changes; level-ups: a tick above the lane + the new level
      g.textAlign = "left";
      l.decs.forEach((d, i) => {
        const [x0, x1] = segs[i];
        if (i && (d.f || {}).level !== (l.decs[i - 1].f || {}).level) { g.fillStyle = card; g.fillRect(x0 - 1, by, 2, LANE_BAR); }
        if (d.o && d.o.lvl_turn) {
          g.fillStyle = ink;
          g.fillRect(Math.round(x1) - 1, y0 + 2, 2, LANE_TOP - 2 + LANE_BAR);
          g.fillText(String(newLevel(l.decs, i)), Math.round(x1) + 2, y0 + 10);
        }
        if (d.o && d.o.go_turn) {
          g.fillStyle = red;
          g.beginPath();
          g.moveTo(x1 - 1, by + LANE_BAR + 1); g.lineTo(x1 + 3, by + LANE_BAR + 6); g.lineTo(x1 - 5, by + LANE_BAR + 6);
          g.closePath(); g.fill();
        }
      });
      hits.push(segs);
    });
  };
  const find = e => {
    const r = canvas.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    const li = Math.floor((y - AXIS_H) / LANE_H);
    if (li < 0 || li >= lanes.length || y - AXIS_H - li * LANE_H < LANE_TOP - 4) return null;
    const segs = hits[li] || [];
    let best = null;
    for (const s of segs) if (x >= s[0] - 1 && x <= s[1] + 1) best = s; // later segments win on overlap
    return best ? { lane: lanes[li], d: lanes[li].decs[best[2]], i: best[2] } : null;
  };
  canvas.addEventListener("pointermove", e => {
    const h = find(e);
    if (!h) { tip.hidden = true; canvas.style.cursor = ""; return; }
    canvas.style.cursor = "pointer";
    const { lane, d, i } = h, f = d.f || {}, o = d.o;
    const out = !o ? "last decision of the game" : [o.lvl_turn ? `level up this turn (to ${newLevel(lane.decs, i)})` : null,
      o.go_turn ? "game over this turn" : null, !o.lvl_turn && o.lvl30 ? "level within 30 moves" : null].filter(Boolean).join(" · ") || "no level within 30 moves";
    tip.replaceChildren(...[el("div", { class: "mono rl2-small" }, `${lane.name} · #${d.d}`), modeTag(d.mode), modePromptLine(d.mode),
      el("div", { class: "rl2-small" }, `level ${val(f.level)} · moves ${val(f.actions_total)}→${segEnd(lane.decs, i)}` +
        (o && isNum(o.acts) ? ` (${o.acts})` : "") + ` · cap ${val(d.cap)}`),
      el("div", { class: "rl2-small " + (o && o.go_turn ? "rl2-bad" : o && (o.lvl_turn || o.lvl30) ? "rl2-yes" : "muted") }, out),
      el("div", { class: "muted rl2-small" }, "click to open in Decisions")].filter(Boolean));
    tip.hidden = false;
    const cr = chart.getBoundingClientRect();
    const left = Math.min(e.clientX - cr.left + 12, cr.width - tip.offsetWidth - 4);
    tip.style.left = Math.max(0, left) + "px";
    tip.style.top = (e.clientY - cr.top + 14) + "px";
  });
  canvas.addEventListener("pointerleave", () => { tip.hidden = true; });
  canvas.addEventListener("click", e => {
    const h = find(e);
    if (h) openDecision(h.lane.run, game, h.d.d);
  });
  lanesUi.paint = paint; // renderLanes paints once the chart is in the page (it needs the container's width)
  return el("div", { class: "card rl2-lanes" }, chart,
    el("div", { class: "legend rl2-small" }, present.map(m => el("span", { class: "rl2-lgmode", title: modePrompt(m) || null },
      el("i", { style: `background:${m === "stock" ? "var(--rl2-stock)" : modeColor(m)}` }), m)),
      el("span", {}, el("i", { class: "lg-lvl" }), "tick + number: level up (the new level)"),
      el("span", {}, el("i", { class: "lg-golane" }), "red mark: game over"),
      el("span", {}, el("i", { class: "lg-gap" }), "gap: level boundary")));
}
function openDecision(run, game, d) {
  state.run = run;
  state.game = game;
  state.modeFilter.clear();
  state.open = new Set([d]);
  state.focusDec = d;
  show("decisions");
  $("view-decisions").scrollIntoView({ block: "start" });
}
function effectTable(decs, nLanes) {
  const s = modeStats(decs);
  const modes = orderModes(Object.keys(s));
  if (!modes.length) return el("div", { class: "empty" }, "No decision with an outcome yet.");
  const base = s.stock ? { lvl30: s.stock.lvl30, n: s.stock.n } : null;
  const bar = x => el("span", { class: "rl2-gbar" }, el("span", { class: "rl2-bar" }, el("i", { style: `width:${(100 * x).toFixed(1)}%` })),
    el("b", { class: "mono" }, pct(x)));
  return el("div", {},
    el("p", { class: "sub" }, `Every decision with an outcome in the ${nLanes} lane${nLanes === 1 ? "" : "s"} above (a game's last decision has none). ` +
      `"vs stock" is level within 30 moves minus stock's in this game, in percentage points: blue better, red worse, grey under ${LANE_MIN_N} turns.`),
    el("div", { class: "rl2-scroll" }, el("table", { class: "rl2-table rl2-effect" },
      el("thead", {}, el("tr", {}, ["mode", "n", "level up this turn", "game over this turn", "level within 30", "vs stock"].map(h => el("th", {}, h)))),
      el("tbody", {}, modes.map(m => {
        const c = s[m];
        return el("tr", {}, el("td", {}, modeTag(m)), el("td", { class: "mono" }, c.n), el("td", {}, bar(c.lvl_rate)),
          el("td", { class: c.go ? "mono rl2-bad" : "mono muted" }, pct(c.go_rate)), el("td", {}, bar(c.lvl30)),
          m === "stock" ? el("td", { class: "rl2-cell none" }, "base")
            : base ? deltaCell({ n: c.n, lvl30: c.lvl30, go: c.go_rate }, base, LANE_MIN_N, LANE_MIN_N) : el("td", { class: "rl2-cell none" }, "no stock"));
      })))));
}
function allGamesGrid(loaded, games) {
  const stats = Object.fromEntries(games.map(g => [g, modeStats(loaded.flatMap(r => (r.doc.games || {})[g] || []))]));
  const modes = orderModes([...new Set(Object.values(stats).flatMap(s => Object.keys(s)))]).filter(m => m !== "stock");
  const rows = games.map(g => ({ game: g, key: `${Object.values(stats[g]).reduce((t, c) => t + c.n, 0)} turns`,
    label: el("button", { type: "button", class: "rl2-glink mono", title: `show the lanes of ${g}`,
      onclick: () => { state.lnGame = g; state.lnAll = false; renderLanes(); } }, g) }));
  return el("div", {},
    el("p", { class: "sub" }, `Each cell: level within 30 moves after that mode's turns minus the same after stock turns, in the same game, ` +
      `over the ${loaded.length} loaded runs. Click a game for its lanes.`),
    gridTable(rows, modes, (row, m) => {
      const c = stats[row.game][m], st = stats[row.game].stock;
      if (!c) return null;
      if (!st) return el("td", { class: "rl2-cell none", title: "no stock turn in this game" }, "–");
      return deltaCell({ n: c.n, lvl30: c.lvl30, go: c.go_rate }, { lvl30: st.lvl30, n: st.n }, LANE_MIN_N, LANE_MIN_N);
    }, row => { const st = stats[row.game].stock; return st ? `${pct(st.lvl30)} (n ${st.n})` : "–"; }, "stock ≤30", "game"),
    diverging(LANE_MIN_N));
}
let lanesResize = 0;
window.addEventListener("resize", () => {
  clearTimeout(lanesResize);
  lanesResize = setTimeout(() => {
    if (state.view === "lanes" && lanesUi.paint) lanesUi.paint();
    if (state.view === "explore" && exUi.paint) exUi.paint();
  }, 120);
});
new MutationObserver(() => {
  if (state.view === "lanes" && lanesUi.paint) requestAnimationFrame(lanesUi.paint);
  if (state.view === "explore" && exUi.paint) requestAnimationFrame(exUi.paint);
})
  .observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

/* ------------------------------------------------------------------ view 4: exploration */
// One tab per game; one row per run of the best combo (no coach, then each coach arm). Each row is the play left to right:
// a thick line coloured by the coach mode of every turn (no-coach runs: stock throughout) and, on games the trace grader
// judged, a thin line under it with the goal the model held (status colours: right / partly right / wrong / none stated).
// Data: explore-index and explore-<game>, written by grader/explore_publish.py (D:/codex-work/daniel-base-20261001).
// A turn row is [decision #, moves at its start, level, mode index]; a checkpoint [decision #, moves, level, stated label,
// held label, belief, rule errors] (held = the last stated goal on the same level, as the grader's scoring counts it).
const GOAL_COLORS = ["#0ca30c", "#fab219", "#d03b3b", null];   // correct, partial, wrong, unstated (status palette)
const GOAL_NAMES = ["right goal", "partly right", "wrong goal", "no goal stated"];
const EX_ARM_H = 24, EX_ROW_H = 40, EX_TOP = 12, EX_MODE = 13, EX_GAP = 3, EX_GOAL = 7;
const exUi = { token: 0, paint: null };
const exTurnEnd = (row, i) => i + 1 < row.turns.length ? row.turns[i + 1][1] : Math.max(row.end, row.turns[i][1] + 1);

async function renderExplore() {
  const token = ++exUi.token;
  let idx;
  try { idx = await getDoc("explore-index"); } catch (e) {
    if (e instanceof NotPublished) {
      $("exPickers").replaceChildren();
      $("exBody").replaceChildren(el("div", { class: "empty" }, "The exploration data is not published yet."));
      return;
    }
    throw e;
  }
  if (token !== exUi.token) return;
  const games = [...idx.games].sort((a, b) => (b.graded - a.graded) || a.game.localeCompare(b.game));
  if (!state.eGame || !games.some(g => g.game === state.eGame)) state.eGame = games[0] && games[0].game;
  const tab = g => el("button", { type: "button", role: "tab", class: "rl2-fbtn" + (g.game === state.eGame ? " on" : ""),
    "aria-selected": g.game === state.eGame ? "true" : "false", title: g.graded ? "goal judged by the trace grader" : "modes only",
    onclick: () => { state.eGame = g.game; renderExplore(); } },
    g.game, g.graded ? el("i", { class: "rl2-egraded", "aria-hidden": "true" }) : null);
  const seg = (label, opts, cur, set) => el("div", { class: "rl2-seg", role: "group", "aria-label": label }, opts.map(([k, t]) =>
    el("button", { type: "button", class: cur === k ? "on" : "", "aria-pressed": cur === k ? "true" : "false",
      onclick: () => { set(k); renderExplore(); } }, t)));
  $("exPickers").replaceChildren(
    el("div", { class: "rl2-etabs", role: "tablist", "aria-label": "game" },
      el("span", { class: "muted rl2-small" }, "goal judged"), games.filter(g => g.graded).map(tab),
      el("span", { class: "muted rl2-small rl2-esep" }, "modes only"), games.filter(g => !g.graded).map(tab)),
    el("div", { class: "rl2-lctl" },
      seg("x axis", [["moves", "game moves"], ["index", "turn #"]], state.eX, v => { state.eX = v; }),
      seg("zoom", ZOOMS.map(z => [z, z === 1 ? "fit" : z + "×"]), state.eZoom, v => { state.eZoom = v; })));
  syncUrl();
  const body = $("exBody");
  let doc;
  if (!state.docs["explore-" + state.eGame]) body.replaceChildren(el("div", { class: "empty" }, "loading…"));
  try { doc = await getDoc("explore-" + state.eGame); } catch (e) {
    if (e instanceof NotPublished) { body.replaceChildren(el("div", { class: "empty" }, `No exploration data for ${state.eGame}.`)); return; }
    throw e;
  }
  if (token !== exUi.token) return;
  const arms = idx.arms.filter(a => doc.rows.some(r => r.arm === a.id));
  const groups = arms.map(a => ({ arm: a, rows: doc.rows.filter(r => r.arm === a.id && r.turns.length) })).filter(g => g.rows.length);
  if (!groups.length) { body.replaceChildren(el("div", { class: "empty" }, `No run has turns in ${state.eGame}.`)); return; }
  body.replaceChildren(...[exploreChart(doc, groups), el("h3", { class: "rl2-h3" }, `By arm in ${doc.game}`), exploreTable(doc, arms),
    doc.graded ? exploreSummaries(doc, groups) : null].filter(Boolean));
  exUi.paint();
}

function exploreChart(doc, groups) {
  const modes = doc.modes;
  const graded = doc.graded;
  const ordered = orderModes([...new Set(groups.flatMap(g => g.rows.flatMap(r => r.turns.map(t => modes[t[3]]))))]);
  const fmtScore = r => isNum(r.score) ? `${fx(r.score, 0)} pts · ${val(r.levels)} lv` : "no score";
  const labels = el("div", { class: "rl2-llabels" },
    el("div", { class: "rl2-laxis muted", style: `height:${AXIS_H}px` }, state.eX === "moves" ? "moves →" : "turn →"),
    groups.flatMap(g => [
      el("div", { class: "rl2-earm", style: `height:${EX_ARM_H}px` }, g.arm.short),
      ...g.rows.map(r => el("div", { class: "rl2-llabel", style: `height:${EX_ROW_H}px`,
        title: `${r.run}\n${r.lost ? "VM lost mid-run: left out of the averages\n" : ""}${fmtScore(r)} in ${doc.game}` },
        el("span", { class: "rl2-lname" }, `run ${r.letter}`, r.lost ? el("small", { class: "muted" }, " · VM lost") : null),
        el("span", { class: "mono muted" }, fmtScore(r))))]));
  const canvas = el("canvas", { class: "rl2-lcanvas", role: "img",
    "aria-label": `${groups.reduce((t, g) => t + g.rows.length, 0)} runs of ${doc.game}: coach mode per turn` + (graded ? " and the goal held" : "") });
  const scroll = el("div", { class: "rl2-lscroll" }, canvas);
  const tip = el("div", { class: "rl2-ltip", hidden: true });
  const chart = el("div", { class: "rl2-lchart" }, labels, scroll, tip);
  const layout = [];   // [y of the row top, row]
  let y = AXIS_H;
  for (const g of groups) { y += EX_ARM_H; for (const r of g.rows) { layout.push([y, r]); y += EX_ROW_H; } }
  const H = y;
  let hits = [];
  const paint = () => {
    if (!canvas.isConnected) return;
    const css = getComputedStyle(canvas);
    const v = (name, fb) => css.getPropertyValue(name).trim() || fb;
    const ink = v("--text", "#111"), muted = v("--muted", "#888"), line = v("--wash-line", "#ddd"), card = v("--sh-card", "#fff"),
      track = v("--wash", "#f3f4f6"), stock = v("--rl2-stock", "#d4d9e1");
    const W = Math.round(Math.max(160, scroll.clientWidth) * state.eZoom);
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    canvas.style.width = W + "px"; canvas.style.height = H + "px";
    const g = canvas.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, W, H);
    const byMoves = state.eX === "moves";
    const rowEnd = r => byMoves ? r.end : r.turns.length;
    const maxX = Math.max(1, ...layout.map(([, r]) => rowEnd(r)));
    const sx = x => PAD_L + x * (W - PAD_L - PAD_R) / maxX;
    const raw = maxX / Math.max(2, Math.floor((W - PAD_L - PAD_R) / 70));
    const mag = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 5, 10].map(k => k * mag).reduce((a, k) => Math.abs(k - raw) < Math.abs(a - raw) ? k : a);
    g.font = "10px " + v("--rl-mono", "monospace");
    for (let x = 0; x <= maxX; x += step) {
      const px = Math.round(sx(x)) + 0.5;
      g.fillStyle = line; g.fillRect(px - 0.5, AXIS_H - 4, 1, H - AXIS_H + 4);
      g.fillStyle = muted; g.textAlign = x === 0 ? "left" : "center"; g.fillText(String(x), px, AXIS_H - 8);
    }
    // arm bands: a faint rule through each arm's header
    let yy = AXIS_H;
    for (const grp of groups) { g.fillStyle = line; g.fillRect(0, yy + EX_ARM_H / 2, W, 1); yy += EX_ARM_H + grp.rows.length * EX_ROW_H; }
    hits = layout.map(([y0, r]) => {
      const mY = y0 + EX_TOP, gY = mY + EX_MODE + EX_GAP;
      const turnSegs = r.turns.map((t, i) => {
        const x0 = sx(byMoves ? t[1] : i), x1 = sx(byMoves ? exTurnEnd(r, i) : i + 1);
        return [x0, Math.max(x0 + 2, x1), i];
      });
      g.globalAlpha = r.lost ? 0.55 : 1;
      g.fillStyle = track;
      g.fillRect(sx(0), mY, Math.max(2, sx(rowEnd(r)) - sx(0)), EX_MODE);
      if (graded && r.grades) g.fillRect(sx(0), gY, Math.max(2, sx(rowEnd(r)) - sx(0)), EX_GOAL);
      for (const [x0, x1, i] of turnSegs) {
        const m = modes[r.turns[i][3]];
        g.fillStyle = m === "stock" ? stock : modeColor(m);
        g.fillRect(x0, mY, x1 - x0, EX_MODE);
      }
      // level changes: a thin gap in the line, a tick above it with the new level
      g.textAlign = "left";
      for (let i = 1; i < r.turns.length; i++) {
        if (r.turns[i][2] > r.turns[i - 1][2]) {
          const x = Math.round(turnSegs[i][0]);
          g.fillStyle = card; g.fillRect(x - 1, mY, 2, EX_MODE);
          g.fillStyle = ink; g.fillRect(x - 1, y0 + 2, 2, EX_TOP - 2 + EX_MODE);
          g.fillText(String(r.turns[i][2]), x + 2, y0 + 10);
        }
      }
      // the goal held, checkpoint to checkpoint (turn axis: the checkpoint's turn position)
      const goalSegs = [];
      if (graded && r.grades) {
        const at = new Map(r.turns.map((t, i) => [t[0], i]));
        const turnPos = d => at.has(d) ? at.get(d) : Math.max(0, r.turns.findIndex(t => t[0] >= d));
        const cps = r.grades.cps;
        const cx = c => sx(byMoves ? c[1] : turnPos(c[0]));
        cps.forEach((c, k) => {
          const x0 = cx(c), x1 = k + 1 < cps.length ? cx(cps[k + 1]) : sx(rowEnd(r));
          const col = GOAL_COLORS[c[4]];
          if (col) { g.fillStyle = col; g.fillRect(x0, gY, Math.max(1, x1 - x0), EX_GOAL); }
          goalSegs.push([x0, Math.max(x0 + 2, x1), k]);
        });
      }
      g.globalAlpha = 1;
      return { y0, mY, gY, r, turnSegs, goalSegs };
    });
  };
  const find = e => {
    const rc = canvas.getBoundingClientRect();
    const x = e.clientX - rc.left, y = e.clientY - rc.top;
    const h = hits.find(h => y >= h.y0 && y < h.y0 + EX_ROW_H);
    if (!h) return null;
    const pick = segs => { let best = null; for (const s of segs) if (x >= s[0] - 1 && x <= s[1] + 1) best = s; return best; };
    if (graded && h.r.grades && y >= h.gY - 1) { const s = pick(h.goalSegs); return s ? { h, kind: "goal", k: s[2] } : null; }
    if (y >= h.mY - 4) { const s = pick(h.turnSegs); return s ? { h, kind: "turn", i: s[2] } : null; }
    return null;
  };
  canvas.addEventListener("pointermove", e => {
    const f = find(e);
    if (!f) { tip.hidden = true; canvas.style.cursor = ""; return; }
    const r = f.h.r;
    const coached = r.arm.includes("/");
    canvas.style.cursor = f.kind === "turn" && coached ? "pointer" : "";
    if (f.kind === "turn") {
      const t = r.turns[f.i], m = doc.modes[t[3]];
      tip.replaceChildren(...[el("div", { class: "mono rl2-small" }, `run ${r.letter} · turn #${t[0]}`), modeTag(m), modePromptLine(m),
        el("div", { class: "rl2-small" }, `level ${t[2]} · moves ${t[1]}→${exTurnEnd(r, f.i)}`),
        el("div", { class: "muted rl2-small" }, coached ? "click to open in Decisions" : "no coach: stock")].filter(Boolean));
    } else {
      const cps = r.grades.cps, c = cps[f.k];
      const held = c[4];
      // a turn that states no goal keeps the last one stated on its level: quote that turn
      let src = c;
      if (c[3] === 3) for (let j = f.k - 1; j >= 0 && cps[j][2] === c[2]; j--) if (cps[j][3] !== 3) { src = cps[j]; break; }
      tip.replaceChildren(...[el("div", { class: "mono rl2-small" }, `run ${r.letter} · turn #${c[0]} · level ${c[2]} · moves ${c[1]}`),
        el("div", { class: "rl2-small" },
          el("i", { class: "rl2-egoal" + (GOAL_COLORS[held] ? "" : " none"), style: GOAL_COLORS[held] ? `background:${GOAL_COLORS[held]}` : "" }),
          el("b", {}, GOAL_NAMES[held]), src !== c ? el("span", { class: "muted" }, ` (as stated at turn #${src[0]})`) : null),
        src[5] ? el("div", { class: "rl2-small" }, `“${src[5]}”`) : null,
        (src[6] || []).length ? el("div", { class: "rl2-small rl2-bad" }, "Wrong rule: " + src[6].join("; ")) : null].filter(Boolean));
    }
    tip.hidden = false;
    const cr = chart.getBoundingClientRect();
    tip.style.left = Math.max(0, Math.min(e.clientX - cr.left + 12, cr.width - tip.offsetWidth - 4)) + "px";
    tip.style.top = (e.clientY - cr.top + 14) + "px";
  });
  canvas.addEventListener("pointerleave", () => { tip.hidden = true; });
  canvas.addEventListener("click", e => {
    const f = find(e);
    if (f && f.kind === "turn" && f.h.r.arm.includes("/")) openDecision(f.h.r.run, doc.game, f.h.r.turns[f.i][0]);
  });
  exUi.paint = paint;
  return el("div", { class: "card rl2-lanes" }, chart,
    el("div", { class: "legend rl2-small" },
      ordered.map(m => el("span", { class: "rl2-lgmode", title: modePrompt(m) || null },
        el("i", { style: `background:${m === "stock" ? "var(--rl2-stock)" : modeColor(m)}` }), m)),
      el("span", {}, el("i", { class: "lg-lvl" }), "tick + number: level reached")),
    graded ? el("div", { class: "legend rl2-small" }, el("span", {}, "thin line, the goal held:"),
      GOAL_NAMES.map((n, k) => el("span", {}, el("i", { class: "rl2-egoal" + (GOAL_COLORS[k] ? "" : " none"),
        style: GOAL_COLORS[k] ? `background:${GOAL_COLORS[k]}` : "" }), n))) : null);
}

function exploreTable(doc, arms) {
  const base = doc.by_arm[arms[0] && arms[0].id] || {};
  const head = ["arm", "runs", "score in this game", "levels", ...(doc.graded ? ["time on a wrong goal", "time not on the right goal"] : [])];
  const diff = (x, b) => isNum(x) && isNum(b) && x !== b
    ? el("small", { class: x > b ? "rl2-delta up" : "rl2-delta down" }, ` ${x > b ? "+" : ""}${fx(x - b)}`) : null;
  return el("div", {},
    el("p", { class: "sub" }, `Averages over each arm's runs in ${doc.game}; a run whose VM was lost is left out. Under a coach arm, ` +
      `the change against no coach. ` + (doc.graded ? "Time shares are of active play, counted as the grader counts them: a turn that " +
      "states no goal keeps the last goal stated on that level." : "")),
    el("div", { class: "rl2-scroll" }, el("table", { class: "rl2-table" },
      el("thead", {}, el("tr", {}, head.map(h => el("th", {}, h)))),
      el("tbody", {}, arms.map((a, k) => {
        const s = doc.by_arm[a.id];
        if (!s) return null;
        return el("tr", {}, el("td", {}, a.short), el("td", { class: "mono" }, s.n),
          el("td", { class: "mono" }, fx(s.score), k ? diff(s.score, base.score) : null),
          el("td", { class: "mono" }, fx(s.levels), k ? diff(s.levels, base.levels) : null),
          doc.graded ? el("td", { class: "mono" }, s.graded ? pct(s.wrong) : "–") : null,
          doc.graded ? el("td", { class: "mono" }, s.graded ? pct(s.off) : "–") : null);
      })))));
}

function exploreSummaries(doc, groups) {
  return el("div", {}, el("h3", { class: "rl2-h3" }, "What the judge saw, run by run"),
    groups.map(g => g.rows.some(r => r.grades) ? el("div", { class: "rl2-esum" },
      el("div", { class: "rl2-earm" }, g.arm.short),
      g.rows.filter(r => r.grades).map(r => el("details", {},
        el("summary", {}, el("b", {}, `run ${r.letter}`), el("span", { class: "mono muted" },
          ` ${isNum(r.score) ? fx(r.score, 0) + " pts · " : ""}${val(r.levels)} lv · wrong goal ${pct(r.grades.wrong)}` +
          ` · not the right goal ${pct(r.grades.off)}`)),
        el("p", {}, r.grades.summary || "–")))) : null));
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
  const fn = { builds: renderBuilds, decisions: renderDecisions, lanes: renderLanes, explore: renderExplore, sampling: renderSampling,
    tree: renderTree,
    training: renderTraining }[view];
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
}
load();

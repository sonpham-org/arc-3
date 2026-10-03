// RL2 page (docs/rl2.html): the turn coach. Four views over published documents and the decision tree:
//   GET /api/v1/rl2/doc/dashboard     builds (a tree), modes, situations, sampling tables
//   GET /api/v1/rl2/doc/run-<run id>  one run's decisions, game by game (loaded when a run is opened)
//   GET /api/v1/rl2/tree/games        the decision tree: games, levels and their start nodes
//   GET /api/v1/rl2/tree/node/<id>    one node (a game state where the coach decided): its branches, a summary per mode
//   GET /api/v1/rl2/tree/trace/<sha>  one branch's turn: thinking, code, moves
// Server: railway/rl_review.py. With ?fixture=1 the page reads docs/static/data/rl2-fixture.json instead (fake data, for
// checking the page locally). Chrome from theme.css and rl-shell.css; every colour is solid (no gradients).

import { draw, pathView } from "./review-ui.js?v=20261003-coach";

const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
const FIXTURE = params.get("fixture") === "1";
const VIEWS = ["builds", "decisions", "sampling", "tree"];
const MIN_N = 20;

const state = {
  dash: null, fixture: null, view: VIEWS.includes(params.get("view")) ? params.get("view") : "builds",
  run: params.get("run"), game: params.get("game"), modeFilter: new Set(), open: new Set(), docs: {},
  smpBuild: params.get("build"), metric: "share",
  // tree view: the game and level picked, the trail of nodes walked (last = shown), open mode groups and traces
  treeGames: null, tGame: params.get("tgame"), tLevel: params.get("tlevel") ? +params.get("tlevel") : null,
  trail: (params.get("trail") || "").split(",").filter(Boolean), tOpen: new Set(), tTrace: new Set(), treeCache: {},
};

// One solid colour per mode; stock is grey. Unknown modes take the spare colours in order.
const MODE_COLORS = {
  stock: "#8792a2", probe: "#2563eb", rethink: "#7c3aed", execute: "#059669", brief: "#0891b2", recover: "#d97706",
  transfer: "#db2777", search: "#65a30d", backtrack: "#9a3412",
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
const modeTag = (name, extra) => el("span", { class: "rl2-mode" + (extra ? " " + extra : ""), style: `background:${modeColor(name)}` }, name);

function notice(text) { $("notice").hidden = !text; $("notice").textContent = text || ""; }
function syncUrl() {
  const q = new URLSearchParams();
  if (FIXTURE) q.set("fixture", "1");
  if (state.view !== "builds") q.set("view", state.view);
  if (state.view === "decisions" && state.run) { q.set("run", state.run); if (state.game) q.set("game", state.game); }
  if (state.view === "sampling" && state.smpBuild) q.set("build", state.smpBuild);
  if (state.view === "tree" && state.tGame) {
    q.set("tgame", state.tGame);
    if (state.tLevel !== null) q.set("tlevel", String(state.tLevel));
    if (state.trail.length) q.set("trail", state.trail.join(","));
  }
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
function gridTable(sits, modes, cell, rowExtra, extraHead) {
  return el("div", { class: "rl2-scroll" }, el("table", { class: "rl2-grid" },
    el("thead", {}, el("tr", {}, el("th", { class: "sit" }, "situation"), rowExtra ? el("th", {}, extraHead) : null,
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
function deltaCell(c, base) {
  if (!base || !isNum(c.lvl30) || !isNum(base.lvl30)) return el("td", { class: "rl2-cell none" }, "–");
  const d = c.lvl30 - base.lvl30;
  const pts = Math.round(d * 100);
  const txt = (pts > 0 ? "+" : pts < 0 ? "−" : "±") + Math.abs(pts);
  const tip = `level within 30 actions: ${pct(c.lvl30)} vs stock ${pct(base.lvl30)} · n ${c.n}` +
    (isNum(c.acts) ? ` · ${fx(c.acts)} actions per turn` : "") + (isNum(c.go) ? ` · game over ${pct(c.go)}` : "");
  if ((c.n || 0) < MIN_N) return el("td", { class: "rl2-cell thin", title: tip + " (too few to tell)" }, txt, el("small", {}, `n ${c.n}`));
  const k = Math.min(1, Math.abs(d) / 0.2);
  const mix = Math.round(8 + k * 78);
  const hue = d >= 0 ? "var(--rl2-blue)" : "var(--rl2-red)";
  return el("td", { class: "rl2-cell" + (mix > 52 ? " ink" : ""), style: `background:color-mix(in srgb, ${hue} ${mix}%, var(--sh-card))`, title: tip },
    txt, el("small", {}, `n ${c.n}`));
}
function diverging() {
  const sw = (hue, mix) => el("i", { style: `background:color-mix(in srgb, ${hue} ${mix}%, var(--sh-card))` });
  return el("div", { class: "legend rl2-small" },
    el("span", {}, sw("var(--rl2-red)", 86), sw("var(--rl2-red)", 40), "worse than stock"),
    el("span", {}, sw("var(--rl2-blue)", 40), sw("var(--rl2-blue)", 86), "better than stock"),
    el("span", {}, el("i", { class: "lg-thin" }), `fewer than ${MIN_N} turns`),
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

/* ------------------------------------------------------------------ view 4: decision tree */
// A node is a game state where the coach decided; plays that reach the same state share it (merges, no forks).
// A branch is one decision there: its mode, what followed, the turn's trace and the node of that play's next decision.
async function getTree(sub) {
  if (state.treeCache[sub]) return state.treeCache[sub];
  let doc;
  if (FIXTURE) {
    await loadFixture();
    const t = state.fixture.tree || {};
    if (sub === "games") doc = t.games || { games: [] };
    else if (sub.startsWith("node/")) doc = (t.nodes || {})[sub.slice(5)];
    else if (sub.startsWith("trace/")) doc = (t.traces || {})[sub.slice(6)];
    if (!doc) throw new NotPublished(sub);
  } else {
    const r = await fetch("/api/v1/rl2/tree/" + sub.split("/").map(encodeURIComponent).join("/"),
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
const nodeLabel = id => { const [g, l, h] = String(id).split(":"); return `${g} · ${l} · ${h ? h.slice(0, 6) : "?"}`; };
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
    body.replaceChildren(el("div", { class: "empty" }, "No tree published yet. It appears here once a coached run publishes its decisions."));
    return;
  }
  let g = games.find(x => x.game === state.tGame);
  if (!g) { g = games[0]; state.tGame = g.game; state.tLevel = null; state.trail = []; }
  let lv = g.levels.find(x => x.level === state.tLevel);
  if (!lv) { lv = g.levels[0]; state.tLevel = lv.level; state.trail = []; }
  if (!state.trail.length || !state.trail[0].startsWith(g.game + ":")) state.trail = [lv.start_nodes[0]];
  const gameSel = el("select", { "aria-label": "game", onchange: e => { state.tGame = e.target.value; state.tLevel = null; state.trail = []; resetNodeUi(); renderTree(); } },
    games.map(x => el("option", { value: x.game, selected: x.game === g.game }, `${x.game} (${x.levels.reduce((s, l) => s + l.branches, 0)})`)));
  const levelSel = el("select", { "aria-label": "level", onchange: e => { state.tLevel = +e.target.value; state.trail = []; resetNodeUi(); renderTree(); } },
    g.levels.map(l => el("option", { value: l.level, selected: l.level === lv.level }, `level ${l.level} · ${l.branches} branch${l.branches === 1 ? "" : "es"} at ${l.nodes} node${l.nodes === 1 ? "" : "s"}`)));
  const pick = [el("label", {}, "game ", gameSel), el("label", {}, "level ", levelSel)];
  if (lv.start_nodes.length > 1) {
    pick.push(el("label", {}, "start ", el("select", { "aria-label": "start node", onchange: e => { state.trail = [e.target.value]; resetNodeUi(); renderTree(); } },
      lv.start_nodes.map(id => el("option", { value: id, selected: id === state.trail[0] }, nodeLabel(id))))));
  }
  $("treePickers").replaceChildren(...pick);
  syncUrl();
  await drawNode(state.trail[state.trail.length - 1]);
}
function resetNodeUi() { state.tOpen.clear(); state.tTrace.clear(); }
function goNode(id, { push = true } = {}) {
  if (push) {
    const at = state.trail.indexOf(id);
    state.trail = at >= 0 ? state.trail.slice(0, at + 1) : [...state.trail, id];
  }
  resetNodeUi();
  syncUrl();
  drawNode(id).then(() => $("view-tree").scrollIntoView({ block: "start" }));
}

async function drawNode(id) {
  const body = $("treeBody");
  let view;
  try {
    view = await getTree("node/" + id);
  } catch (e) {
    if (!(e instanceof NotPublished)) throw e;
    body.replaceChildren(trailBar(), el("div", { class: "empty" }, `Node ${id} is not published yet.`));
    return;
  }
  const n = view.node;
  const canvas = n.board ? el("canvas", { class: "rl2-board", width: 160, height: 160, "aria-label": "board at this node" }) : null;
  const head = el("div", { class: "card rl2-node" },
    canvas || el("div", { class: "rl2-board none" }, "no board stored"),
    el("div", { class: "rl2-node-info" },
      el("div", { class: "rl2-node-id mono" }, n.id),
      el("div", { class: "rl2-node-nums" },
        el("div", {}, el("b", { class: "mono" }, n.branches), el("small", {}, n.branches === 1 ? "branch" : "branches")),
        el("div", {}, el("b", { class: "mono" }, n.arrivals || 0), el("small", {}, "plays arrived")),
        el("div", {}, el("b", { class: "mono" }, Object.keys(view.by_mode || {}).length), el("small", {}, "modes"))),
      el("div", { class: "muted rl2-small" }, `game ${n.game} · level ${n.level}` + (n.first_run ? ` · first seen in ${n.first_run}` : "")),
      view.parents && view.parents.length ? el("div", { class: "rl2-parents rl2-small" }, el("span", { class: "muted" }, "came from"),
        view.parents.slice(0, 12).map(p => el("button", { type: "button", class: "rl2-chip mono", onclick: () => goNode(p) }, nodeLabel(p)))) : null,
      view.truncated ? el("div", { class: "rl2-small rl2-bad" }, "Only the first branches are shown.") : null));
  body.replaceChildren(trailBar(), head, modeGroups(view));
  if (canvas) requestAnimationFrame(() => draw(canvas, n.board));
}
function trailBar() {
  if (state.trail.length < 2) return el("div", { class: "rl2-trail muted rl2-small" }, "Level start. Open a mode, then follow a branch with “next node →”.");
  return el("nav", { class: "rl2-trail rl2-small", "aria-label": "nodes visited" }, state.trail.flatMap((id, i) => {
    const last = i === state.trail.length - 1;
    return [i ? el("span", { class: "muted", "aria-hidden": "true" }, "›") : null,
      last ? el("span", { class: "rl2-chip on mono", "aria-current": "page" }, nodeLabel(id))
        : el("button", { type: "button", class: "rl2-chip mono", onclick: () => goNode(id) }, i === 0 ? "start" : nodeLabel(id))];
  }));
}
function modeGroups(view) {
  const modes = Object.entries(view.by_mode || {}).sort((a, b) => b[1].n - a[1].n || a[0].localeCompare(b[0]));
  if (!modes.length) return el("div", { class: "empty" }, "No branch leaves this node: the plays ended here.");
  const wrap = el("div", { class: "rl2-groups" });
  const redraw = () => wrap.replaceWith(modeGroups(view));
  wrap.append(el("div", { class: "rl2-ghead muted rl2-small" }, el("span", {}, "mode"), el("span", {}, "n"),
    el("span", {}, "level within 30 actions"), el("span", { class: "rl2-gmore" }, "also")));
  for (const [mode, s] of modes) {
    const open = state.tOpen.has(mode);
    const row = el("button", { type: "button", class: "rl2-grow" + (open ? " open" : ""), "aria-expanded": open ? "true" : "false",
      onclick: () => { open ? state.tOpen.delete(mode) : state.tOpen.add(mode); redraw(); } },
      el("span", { class: "rl2-gmode" }, el("span", { class: "rl2-caret", "aria-hidden": "true" }, open ? "▾" : "▸"), modeTag(mode)),
      el("span", { class: "mono" }, s.n),
      el("span", { class: "rl2-gbar" }, el("span", { class: "rl2-bar" }, el("i", { style: `width:${isNum(s.lvl30) ? (100 * s.lvl30).toFixed(1) : 0}%` })),
        el("b", { class: "mono" }, pctOrDash(s.lvl30))),
      el("span", { class: "rl2-gmore mono muted", title: "cleared this level · mean actions · game over" },
        `cleared ${pctOrDash(s.cleared)} · ${fx(s.acts)} acts · over ${pctOrDash(s.go)}`));
    wrap.append(row);
    if (open) wrap.append(el("div", { class: "rl2-blist" }, view.branches.filter(b => b.mode === mode).map(b => branchItem(b, redraw))));
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
function branchItem(b, redraw) {
  const tOpen = state.tTrace.has(b.id);
  const ci = b.child_info;
  let next;
  if (!b.child) next = el("span", { class: "muted rl2-small" }, "play ended");
  else if (ci && ci.published === false) next = el("span", { class: "muted rl2-small", title: b.child }, "next node not published");
  else next = el("button", { type: "button", class: "rl2-btn primary", title: b.child, onclick: () => goNode(b.child) }, "next node →",
    ci && ci.arrivals > 1 ? el("span", { class: "rl2-merge", title: `${ci.arrivals} plays reached this node (${ci.branches} branches leave it)` }, `${ci.arrivals} plays`) : null);
  const traceBtn = b.trace_sha ? el("button", { type: "button", class: "rl2-btn" + (tOpen ? " on" : ""), "aria-expanded": tOpen ? "true" : "false",
    onclick: () => { tOpen ? state.tTrace.delete(b.id) : state.tTrace.add(b.id); redraw(); } }, tOpen ? "hide trace" : "trace")
    : el("span", { class: "muted rl2-small" }, "no trace");
  const item = el("div", { class: "rl2-branch" + (tOpen ? " open" : "") },
    el("div", { class: "rl2-bmain" },
      el("div", { class: "rl2-bwho mono" }, el("b", {}, `#${b.decision}`), ` ${b.run}`, el("span", { class: "muted" }, ` · ${b.play}`)),
      el("div", { class: "rl2-bmeta rl2-small" },
        el("span", { class: "rl2-chip mono" }, b.build), b.policy ? el("span", { class: "muted mono" }, b.policy) : null,
        el("span", { class: "mono" }, `cap ${val(b.cap)}`), el("span", { class: "mono" }, `p ${val(b.prob)}`),
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
  // the tree has its own data; it does not wait for the dashboard
  if (!state.dash && view !== "tree") return;
  if (view === "tree" && state.treeShown) return;
  if (view === "tree") state.treeShown = true;
  const fn = { builds: renderBuilds, decisions: renderDecisions, sampling: renderSampling, tree: renderTree }[view];
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

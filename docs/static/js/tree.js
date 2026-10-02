// Tree explorer (docs/tree.html): every play of a game as a tree of points (level starts; forks later) and the
// paths between them, with how raters judged each path. Server: GET /api/v1/review/tree?game= (railway/rl_review.py).

import { draw, el, outcomeText, pathView } from "./review-ui.js?v=20261002-tree";

const NS = "http://www.w3.org/2000/svg";
const RAMP = ["#000000", "#170100", "#300200", "#470200", "#5F0300", "#780400", "#8B1700", "#9D2D00", "#B14400", "#C45A00",
  "#D87200", "#EB8800", "#FA9D04", "#FBAF21", "#FCC03A", "#FDD256", "#FEE371", "#FFF08C", "#FFF4AC", "#FFF9CE", "#FFFDED"];
// later rounds brighter on dark, darker on light: each model reads on its background (Cellens ramp)
const STOPS = { dark: [0.45, 0.66, 0.8, 0.9, 0.97], light: [0.56, 0.32, 0.2, 0.12, 0.06] };
const $ = id => document.getElementById(id);
const state = { games: [], game: null, tree: null, sel: null, models: [], contents: {} };

function sv(tag, attrs, ...kids) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v !== null && v !== undefined) e.setAttribute(k, v);
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined) e.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  return e;
}
function ramp(t) {
  t = Math.max(0, Math.min(1, t));
  const x = t * (RAMP.length - 1), i = Math.min(RAMP.length - 2, Math.floor(x)), f = x - i;
  const a = [1, 3, 5].map(k => parseInt(RAMP[i].slice(k, k + 2), 16)), b = [1, 3, 5].map(k => parseInt(RAMP[i + 1].slice(k, k + 2), 16));
  return `rgb(${a.map((v, j) => Math.round(v + (b[j] - v) * f)).join(",")})`;
}
const light = () => document.documentElement.getAttribute("data-theme") === "light";
const modelRank = m => (m === "base" ? 0 : /^r\d+$/.test(m) ? 1 + parseInt(m.slice(1), 10) : 50);
function color(model) {
  const s = STOPS[light() ? "light" : "dark"], i = Math.max(0, state.models.indexOf(model));
  return ramp(s[Math.min(i, s.length - 1)]);
}
const label = m => (m === "base" ? "Before training" : /^r\d+$/.test(m) ? `After round ${m.slice(1)}` : m);

async function api(path) {
  const r = await fetch("/api/v1/review" + path, { credentials: "same-origin", cache: "no-store", redirect: "manual" });
  if (r.type === "opaqueredirect" || r.status === 0 || r.status === 401) throw { status: 401 };
  if (!r.ok) throw Object.assign({ status: r.status }, await r.json().catch(() => ({})));
  return r.json();
}
function banner(text) { $("banner").hidden = !text; $("banner").textContent = text || ""; }
const record = p => `${p.wins}–${p.losses}` + (p.ties ? ` · ${p.ties} tie${p.ties > 1 ? "s" : ""}` : "") + (p.neither ? ` · ${p.neither} both bad` : "");

/* ------------------------------------------------------------------ games */
async function loadGames() {
  const stats = await api("/stats");
  state.games = stats.games.filter(g => g.paths > 0).sort((a, b) => a.game.localeCompare(b.game));
  const want = new URLSearchParams(location.search).get("game");
  const first = state.games.find(g => g.game === want) || [...state.games].sort((a, b) => b.splits - a.splits)[0];
  $("games").replaceChildren(el("span", { class: "lab" }, "game"),
    ...state.games.map(g => el("button", { type: "button", "data-game": g.game, onclick: () => pickGame(g.game),
      title: `${g.paths} paths, ${g.splits} pairs, ${g.ratings} ratings` }, g.game, el("small", {}, `${g.paths}`))));
  if (first) await pickGame(first.game);
}
async function pickGame(game) {
  state.game = game;
  [...$("games").querySelectorAll("button")].forEach(b => b.classList.toggle("on", b.dataset.game === game));
  history.replaceState(null, "", `?game=${game}`);
  $("tree").replaceChildren(el("div", { class: "rv-empty" }, "loading…"));
  state.tree = await api(`/tree?game=${encodeURIComponent(game)}`);
  state.models = [...new Set(state.tree.paths.map(p => p.model))].sort((a, b) => modelRank(a) - modelRank(b) || a.localeCompare(b));
  $("legend").replaceChildren(...state.models.map(m => el("span", {}, el("i", { style: `background:${color(m)}` }), label(m))),
    el("span", {}, "× did not clear"));
  state.sel = null;
  renderTree();
  renderSide();
}

/* ------------------------------------------------------------------ the tree */
function renderTree() {
  const t = state.tree;
  const levels = Math.max(...t.nodes.map(n => n.level));
  const byLevel = {};
  t.nodes.forEach(n => (byLevel[n.level] = byLevel[n.level] || []).push(n));
  const out = {};
  t.paths.forEach(p => (out[p.node] = out[p.node] || []).push(p));
  const laneGap = 13, colW = 200, left = 70;
  const maxOut = Math.max(1, ...Object.values(out).map(ps => ps.length));
  const H = Math.max(280, maxOut * laneGap * 1.35 + 150), W = left + levels * colW + 40;
  const pos = {};
  for (const [lv, ns] of Object.entries(byLevel)) ns.forEach((n, k) => {
    pos[n.id] = { x: left + (+lv - 1) * colW, y: H / 2 + (k - (ns.length - 1) / 2) * 70 };
  });
  const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img", "aria-label": `tree of ${t.game}` });
  for (let lv = 1; lv <= levels; lv++) {
    const x = left + (lv - 1) * colW;
    svg.append(sv("line", { x1: x, x2: x, y1: 28, y2: H - 16, class: "col" }));
    svg.append(sv("text", { x, y: 18, class: "lvl", "text-anchor": "middle" }, `level ${lv}`));
  }
  const pathsLayer = sv("g"), nodesLayer = sv("g");
  for (const n of t.nodes) {
    const ps = (out[n.id] || []).slice().sort((a, b) => (b.cleared - a.cleared) || (a.actions - b.actions));
    const { x: x1, y: y1 } = pos[n.id];
    const r = 8 + 2.6 * Math.sqrt(n.paths);
    ps.forEach((p, k) => {
      const off = (k - (ps.length - 1) / 2) * laneGap;
      let d, end = null;
      if (p.cleared && p.next && pos[p.next]) {
        const { x: x2, y: y2 } = pos[p.next], dx = x2 - x1, rr = 8;
        d = `M${x1 + r},${y1} C${x1 + dx * 0.38},${y1 + off * 1.35} ${x2 - dx * 0.38},${y2 + off * 1.35} ${x2 - rr},${y2}`;
      } else {
        const ex = x1 + colW * (p.cleared ? 0.9 : 0.58), ey = y1 + off * 1.35;
        d = `M${x1 + r},${y1} C${x1 + colW * 0.25},${y1 + off * 1.2} ${x1 + colW * 0.42},${ey} ${ex},${ey}`;
        if (!p.cleared) end = { x: ex, y: ey };
      }
      const c = color(p.model);
      const tip = `${label(p.model)} · ${p.play} (${p.run})\n${outcomeText(p)}\nraters: ${record(p)}`;
      const g = sv("g", { "data-path": p.id });
      g.append(sv("path", { d, class: "path" + (state.sel && state.sel.id === p.id ? " sel" : ""), stroke: c }, sv("title", {}, tip)));
      if (end) g.append(sv("path", { d: `M${end.x - 4},${end.y - 4} L${end.x + 4},${end.y + 4} M${end.x + 4},${end.y - 4} L${end.x - 4},${end.y + 4}`,
        class: "dead", stroke: c }));
      g.append(sv("path", { d, class: "hit" }, sv("title", {}, tip)));
      g.addEventListener("click", () => select({ type: "path", id: p.id }));
      pathsLayer.append(g);
    });
    const g = sv("g", { class: "node" + (state.sel && state.sel.id === n.id ? " sel" : ""), transform: `translate(${x1},${y1})` },
      sv("circle", { r }), sv("title", {}, `start of level ${n.level}: ${n.paths} plays, ${n.splits} pairs, ${n.ratings} ratings`));
    g.addEventListener("click", () => select({ type: "node", id: n.id }));
    nodesLayer.append(g);
    nodesLayer.append(sv("text", { x: x1, y: y1 - r - 8, class: "meta", "text-anchor": "middle" },
      `${n.paths} plays · ${n.ratings} rated`));
  }
  svg.append(pathsLayer, nodesLayer);
  $("tree").replaceChildren(svg);
}

/* ------------------------------------------------------------------ details */
function select(sel) {
  state.sel = sel;
  renderTree();
  renderSide();
}
async function renderSide() {
  const side = $("side"), sel = state.sel, t = state.tree;
  if (!sel) { side.replaceChildren(el("div", { class: "muted" }, "Click a point or a line.")); return; }
  if (sel.type === "node") {
    const n = t.nodes.find(x => x.id === sel.id);
    const ps = t.paths.filter(p => p.node === n.id).sort((a, b) => (b.cleared - a.cleared) || (a.actions - b.actions));
    const canvas = el("canvas", { class: "start", width: 180, height: 180 });
    side.replaceChildren(
      el("h3", {}, `${t.game} · start of level ${n.level}`),
      el("div", { class: "muted" }, n.level === 1 ? "The game's first board: every play starts here."
        : "Every play that cleared the level before arrives on exactly this board."),
      el("div", { style: "margin-top:10px" }, canvas),
      el("div", { class: "muted", style: "margin-top:6px" }, `${n.paths} plays went on from here · ${n.splits} pairs to rate · ${n.ratings} ratings so far`),
      n.splitIds.length ? el("div", { class: "tx-actions" }, el("a", { href: `./review.html?split=${encodeURIComponent(n.splitIds[0])}` }, "Rate a pair from this point")) : null,
      el("table", { class: "tx-rows" },
        el("tr", {}, ...["", "play", "outcome", "raters W–L"].map(h => el("th", {}, h))),
        ...ps.map(p => el("tr", { onclick: () => select({ type: "path", id: p.id }) },
          el("td", {}, el("span", { class: "tx-sw", style: `background:${color(p.model)}` })),
          el("td", {}, `${p.play} · ${p.model}`), el("td", {}, p.cleared ? `cleared, ${p.actions} moves` : `stuck after ${p.actions} moves`),
          el("td", {}, record(p))))));
    if (n.start) requestAnimationFrame(() => draw(canvas, n.start));
    return;
  }
  const p = t.paths.find(x => x.id === sel.id);
  const n = t.nodes.find(x => x.id === p.node);
  const box = el("div", { class: "rv-opt" }, el("div", { class: "muted", style: "padding:10px" }, "loading the turns…"));
  side.replaceChildren(
    el("h3", {}, el("span", { class: "tx-sw", style: `background:${color(p.model)}` }), `${t.game} · level ${p.level} · ${p.play}`),
    el("div", {}, `${label(p.model)} · run ${p.run}`),
    el("div", { class: p.cleared ? "rv-outcome ok" : "rv-outcome" }, outcomeText(p)),
    el("div", { class: "muted", style: "margin-top:4px" },
      `raters: won ${p.wins}, lost ${p.losses}` + (p.ties ? `, ${p.ties} ties` : "") + (p.neither ? `, ${p.neither} both bad` : "") +
      ` · turn marks ${p.marks.up} good, ${p.marks.down} bad, ${p.marks.notes} notes`),
    el("div", { class: "tx-actions" },
      el("a", { href: "#", onclick: e => { e.preventDefault(); select({ type: "node", id: n.id }); } }, `the point it started from (level ${n.level})`),
      n.splitIds.length ? el("a", { href: `./review.html?split=${encodeURIComponent(n.splitIds[0])}` }, "Rate pairs here") : null),
    box);
  try {
    if (!state.contents[p.id]) state.contents[p.id] = await api(`/path?id=${encodeURIComponent(p.id)}`);
    if (state.sel !== sel) return;
    const { player, list } = pathView(state.contents[p.id], p.id, null);
    box.replaceChildren(player.node, list);
  } catch (e) {
    box.replaceChildren(el("div", { class: "muted", style: "padding:10px" }, "could not load this path's turns"));
  }
}

/* ------------------------------------------------------------------ start */
new MutationObserver(() => { if (state.tree) { renderTree(); $("legend").querySelectorAll("i").forEach((i, k) => { if (state.models[k]) i.style.background = color(state.models[k]); }); } })
  .observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
loadGames().catch(e => {
  if (e && e.status === 401) banner("Sign in with your team account to see the tree.");
  else if (e && e.status === 403) banner("This Google account is not on the team list.");
  else banner(`Could not load: ${(e && (e.message || e.error)) || e}`);
});

// Tree explorer (docs/tree.html): every play of a game as a tree of points (level starts; forks later) and the
// paths between them, with how raters judged each path. Server: GET /api/v1/review/tree?game= (railway/rl_review.py).

import { draw, el, outcomeText, pathView } from "./review-ui.js?v=20261003-run";
import { modelColor } from "./model-colors.js?v=20261002-blue";

const NS = "http://www.w3.org/2000/svg";
const $ = id => document.getElementById(id);
const state = { games: [], game: null, tree: null, sel: null, models: [], contents: {} };

function sv(tag, attrs, ...kids) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v !== null && v !== undefined) e.setAttribute(k, v);
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined) e.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  return e;
}
const modelRank = m => (m === "base" ? 0 : /^r\d+$/.test(m) ? 1 + parseInt(m.slice(1), 10) : 50);
const color = model => modelColor(Math.max(0, state.models.indexOf(model)));
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
  // A real tree (Son 2-Oct): independent plays share only the game start, so the game start is the root and every
  // play is its own branch out of it. Along a branch, length is moves (better = shorter): a marker where each level
  // was cleared, a cross where the play got stuck. Forks of one play will hang off its branch at the fork's move.
  const t = state.tree;
  const plays = {};
  for (const p of t.paths) (plays[`${p.run} ${p.play}`] = plays[`${p.run} ${p.play}`] || { run: p.run, play: p.play, model: p.model, segs: [] }).segs.push(p);
  const list = Object.values(plays).map(pl => {
    pl.segs.sort((a, b) => a.level - b.level);
    pl.total = pl.segs.reduce((s, p) => s + p.actions, 0);
    pl.cleared = pl.segs.filter(p => p.cleared).length;
    return pl;
  }).sort((a, b) => (b.cleared - a.cleared) || (a.total - b.total));
  const maxMoves = Math.max(10, ...list.map(pl => pl.total));
  const lane = 24, top = 46, left = 46, labelW = 150, right = 30;
  const W = Math.max(760, left + 40 + Math.min(1300, 1.8 * maxMoves) + labelW + right);
  const H = top + list.length * lane + 40;
  const x0 = left, xs = left + 40, xe = W - labelW - right;
  const x = moves => xs + (xe - xs) * moves / maxMoves;
  const rootY = top + (list.length - 1) * lane / 2;
  const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img", "aria-label": `tree of ${t.game}` });
  const step = [10, 20, 25, 50, 100, 200, 250, 500].find(s => maxMoves / s <= 8) || 1000;
  for (let m = 0; m <= maxMoves; m += step) {
    svg.append(sv("line", { x1: x(m), x2: x(m), y1: top - 16, y2: H - 22, class: "col" }));
    svg.append(sv("text", { x: x(m), y: top - 22, class: "meta", "text-anchor": "middle" }, m));
  }
  svg.append(sv("text", { x: xe, y: H - 6, class: "meta", "text-anchor": "end" }, "moves from the game start →"));
  const paths = sv("g"), marks = sv("g");
  list.forEach((pl, k) => {
    const y = top + k * lane, c = color(pl.model);
    // out of the root
    paths.append(sv("path", { d: `M${x0 + 9},${rootY} C${x0 + 26},${rootY} ${xs - 18},${y} ${xs},${y}`, class: "path", stroke: c }));
    let at = 0;
    pl.segs.forEach(p => {
      const a = x(at), b = x(at + p.actions);
      at += p.actions;
      const tip = `${label(p.model)} · ${p.play} (${p.run})\nlevel ${p.level}: ${outcomeText(p)}\nraters: ${record(p)}`;
      const g = sv("g", { "data-path": p.id });
      g.append(sv("path", { d: `M${a},${y} L${b},${y}`, class: "path" + (state.sel && state.sel.id === p.id ? " sel" : ""),
        stroke: c, "stroke-width": p.level % 2 ? 3 : 5 }, sv("title", {}, tip)));
      g.append(sv("path", { d: `M${a},${y} L${b},${y}`, class: "hit" }, sv("title", {}, tip)));
      g.addEventListener("click", () => select({ type: "path", id: p.id }));
      paths.append(g);
      if (p.cleared) {
        const m = sv("g", { class: "node", transform: `translate(${b},${y})` },
          sv("circle", { r: 7.5, style: `fill:${c};stroke:var(--panel);stroke-width:1.5` }),
          sv("text", { class: "lvlnum", "text-anchor": "middle", dy: "0.35em" }, p.level), sv("title", {}, `cleared level ${p.level} at move ${at}`));
        if (p.next) m.addEventListener("click", () => select({ type: "node", id: p.next }));
        marks.append(m);
      } else {
        marks.append(sv("path", { d: `M${b - 5},${y - 5} L${b + 5},${y + 5} M${b + 5},${y - 5} L${b - 5},${y + 5}`, class: "dead", stroke: c },
          sv("title", {}, `stuck in level ${p.level} after ${p.actions} moves`)));
      }
    });
    marks.append(sv("text", { x: x(at) + 12, y: y + 4, class: "meta" }, `${pl.play} · ${pl.cleared} level${pl.cleared === 1 ? "" : "s"} · ${pl.total} moves`));
  });
  const root = sv("g", { class: "node" + (state.sel && state.sel.type === "node" && t.nodes.find(n => n.id === state.sel.id && n.level === 1) ? " sel" : ""),
    transform: `translate(${x0},${rootY})` }, sv("circle", { r: 9 }), sv("title", {}, "the game start: the one point every play shares"));
  const first = t.nodes.find(n => n.level === 1);
  if (first) root.addEventListener("click", () => select({ type: "node", id: first.id }));
  svg.append(paths, marks, root,
    sv("text", { x: x0, y: rootY - 16, class: "lvl", "text-anchor": "middle" }, "start"));
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
      el("div", { class: "muted" }, n.level === 1 ? "The game start: the one point every play shares (same board, no history)."
        : "Every play that cleared the level before arrives on this board, each with its own history, so these are not branches of one another."),
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

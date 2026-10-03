// Score climb (docs/climb.html): every Daniel-notebook run's all-25 score over its 132 minutes, or over its actions.
//   GET /api/v1/rl2/doc/score-climb   {generated_at, suite, runs[{..., points: [[minute, score, actions|null]]}],
//                                      baselines{key: {label, n, n_actions, points, points_actions}}, default_baseline}
//   published every 5 min by climb_site.py (team read); interrupted runs are already left out there.
// Finished runs draw in grey, the chosen baseline average in black (white in dark mode), live runs in colour.

const SUITE_DEFAULT = 132;
// Live tests: the reference categorical palette without its blue slot, fixed order (validated: light worst adjacent
// CVD 9.1 / normal 19.6, three slots under 3:1 on white so table + legend carry identity; dark all checks pass).
const CATEGORICAL = {
  light: ["#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
  dark: ["#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
};
// Context-grid runs: one blue ramp; light = fewer games at once, dark = more (reversed in dark mode).
const GRID_STEPS = [7, 8, 9, 10, 12, 14, 16, 18, 20, 22];
const GRID_RAMP = { light: [[138, 184, 238], [11, 50, 112]], dark: [[30, 80, 160], [170, 205, 250]] };

const state = { data: null, baseline: null, view: "all", axis: "minutes", sort: "gap", colors: {} };
const $ = (id) => document.getElementById(id);
const theme = () => document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
const fmt = (v, d = 1) => (v === null || v === undefined || Number.isNaN(v)) ? "–" : Number(v).toFixed(d);
const signed = (v) => (v === null || v === undefined || Number.isNaN(v)) ? "–" : (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(1);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const gridS = (arm) => { const m = /ctxgrid_s(\d+)/.exec(arm || ""); return m ? +m[1] : null; };
const letter = (id) => { const m = /-([a-z])-\d{4}$/.exec(id || ""); return m ? "run " + m[1] : (id || "").replace(/^g4run-/, ""); };
const byActions = () => state.axis === "actions";
const AX = () => (byActions() ? 2 : 0);   // index of the x value in a point [minute, score, actions]
// A run's points on the current axis: on actions, only the points that carry an action count.
const series = (r) => (byActions() ? r.points.filter((p) => p[2] !== null && p[2] !== undefined) : r.points);
const lastOf = (r) => { const s = series(r); return s.length ? s[s.length - 1] : null; };
const baseSeries = (bl) => (byActions() ? (bl.points_actions || []).map((p) => [p[0], p[1], p[0]]) : bl.points || []);
const xLabel = () => (byActions() ? "actions taken (all 25 games)" : "minutes of play");
const xName = () => (byActions() ? "actions" : "minute");

// score at x on the current axis; flat past the end on minutes, null past the end on actions
function at(points, x, axis) {
  const pts = points.filter((p) => p[axis] !== null && p[axis] !== undefined);
  if (!pts.length) return null;
  if (x <= pts[0][axis]) return pts[0][1];
  for (let i = 1; i < pts.length; i++) {
    const a = pts[i - 1], b = pts[i];
    if (x <= b[axis]) return b[axis] > a[axis] ? a[1] + (b[1] - a[1]) * (x - a[axis]) / (b[axis] - a[axis]) : b[1];
  }
  return axis === 0 ? pts[pts.length - 1][1] : null;
}

function assignColors(live) {
  // colour follows the version (arm), in stable arm-name order, never by rank
  const t = theme(), colors = {};
  const [lo, hi] = GRID_RAMP[t];
  for (const s of new Set(live.map((r) => gridS(r.arm)).filter((s) => s !== null))) {
    const i = GRID_STEPS.indexOf(s), f = (i < 0 ? 0 : i) / (GRID_STEPS.length - 1);
    colors["grid:" + s] = `rgb(${lo.map((a, k) => Math.round(a + (hi[k] - a) * f)).join(",")})`;
  }
  [...new Set(live.filter((r) => gridS(r.arm) === null).map((r) => r.arm))].sort()
    .forEach((a, i) => { colors[a] = i < CATEGORICAL[t].length ? CATEGORICAL[t][i] : "fold"; });
  return colors;
}
const colorOf = (r) => (gridS(r.arm) !== null ? state.colors["grid:" + gridS(r.arm)] : state.colors[r.arm]);
const stroke = (c) => (c === "fold" ? "var(--c-fold)" : c);

function render() {
  const d = state.data;
  if (!d) return;
  const suite = d.suite || SUITE_DEFAULT, ax = AX();
  const drawable = (r) => series(r).length >= 2;
  const finishedAll = d.runs.filter((r) => r.state === "finished");
  const liveAll = d.runs.filter((r) => r.state === "live");
  const finished = finishedAll.filter(drawable);
  const live = liveAll.filter(drawable)
    .filter((r) => state.view === "all" || (state.view === "grid") === (gridS(r.arm) !== null));
  state.colors = assignColors(liveAll);
  const bl = d.baselines[state.baseline] || { label: "–", n: 0, points: [], points_actions: [] };
  const base = baseSeries(bl);
  const baseAt = (x) => (base.length ? at(base, x, ax) : null);

  const best = finishedAll.reduce((b, r) => (!b || r.points[r.points.length - 1][1] > b.points[b.points.length - 1][1] ? r : b), null);
  const gaps = live.map((r) => { const p = lastOf(r), b = baseAt(p[ax]); return { r, p, gap: b !== null ? p[1] - b : null }; })
    .filter((x) => x.gap !== null).sort((a, b) => b.gap - a.gap);
  const bEnd = base.length ? base[base.length - 1] : null;
  $("tiles").innerHTML = [
    byActions()
      ? stat("Baseline per 1,000 actions", bEnd && bEnd[0] ? fmt(1000 * bEnd[1] / bEnd[0], 2) : "–",
             bEnd ? `${fmt(bEnd[1])} at ${Math.round(bEnd[0]).toLocaleString()} actions · ${bl.n_actions ?? bl.n} runs` : bl.label)
      : stat("Baseline at minute " + suite, base.length ? fmt(baseAt(suite)) : "–", `${bl.label} · ${bl.n} runs`),
    stat("Best finished run", best ? fmt(best.points[best.points.length - 1][1]) : "–", best ? best.name : ""),
    stat("Playing now", String(liveAll.length), `${finishedAll.length} finished runs in grey`),
    stat(`Best live vs baseline (same ${xName()})`, gaps.length ? signed(gaps[0].gap) : "–",
         gaps.length ? `${gaps[0].r.name} · ${xName()} ${Math.round(gaps[0].p[ax]).toLocaleString()}` : ""),
  ].join("");
  $("liveTitle").textContent = `Playing now, against the baseline at the same ${xName()}`;
  $("chartTitle").textContent = byActions() ? "Score over actions (action efficiency)" : "Score over time";
  drawChart(finished, live, base, suite);
  drawLegend(live, bl, finishedAll.length - finished.length);
  drawLive(live, baseAt);
  drawFinished(finishedAll);
}

function stat(k, v, s) {
  return `<div class="stat"><div class="k">${esc(k)}</div><div class="v num">${esc(v)}</div><div class="s">${esc(s)}</div></div>`;
}

function niceStep(max) {
  const raw = max / 6, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  return [1, 2, 2.5, 5, 10].map((k) => k * mag).find((s) => s >= raw) || raw;
}

let geom = null;
function drawChart(finished, live, base, suite) {
  const host = $("chart"), tip = $("tip"), ax = AX();
  const W = Math.max(320, host.clientWidth), H = Math.round(Math.min(560, Math.max(300, W * 0.46)));
  const pad = { l: 40, r: 16, t: 10, b: 34 };
  const runsShown = [...finished, ...live];
  const vals = runsShown.flatMap((r) => series(r).map((p) => p[1])).concat(base.map((p) => p[1]));
  const ymax = Math.max(10, Math.ceil((Math.max(0, ...vals) + 2) / 10) * 10);
  const xmax = byActions() ? Math.max(100, ...runsShown.flatMap((r) => series(r).map((p) => p[2]))) : suite;
  const x = (v) => pad.l + (W - pad.l - pad.r) * v / xmax;
  const y = (s) => H - pad.b - (H - pad.t - pad.b) * s / ymax;
  geom = { x, y, pad, W, H, ymax, xmax, ax, finished, live, base };
  const path = (pts) => pts.map((p, i) => `${i ? "L" : "M"}${x(p[ax]).toFixed(1)},${y(p[1]).toFixed(1)}`).join("");
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Score over ${xName()}s for every run">`;
  for (let v = 0; v <= ymax; v += 10) {
    s += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--c-grid)"/>`;
    s += `<text x="${pad.l - 8}" y="${y(v) + 4}" text-anchor="end" font-size="11" fill="var(--c-muted)">${v}</text>`;
  }
  const step = byActions() ? niceStep(xmax) : 15;
  for (let v = 0; v <= xmax + 1e-9; v += step) {
    const label = byActions() ? (v >= 1000 ? (v / 1000).toLocaleString() + "k" : String(v)) : String(v);
    s += `<text x="${x(v)}" y="${H - pad.b + 18}" text-anchor="middle" font-size="11" fill="var(--c-muted)">${label}</text>`;
  }
  s += `<text x="${(pad.l + W - pad.r) / 2}" y="${H - 3}" text-anchor="middle" font-size="11" fill="var(--c-text2)">${xLabel()}</text>`;
  s += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${y(0)}" y2="${y(0)}" stroke="var(--c-axis)"/>`;
  for (const r of finished) {
    s += `<path d="${path(series(r))}" fill="none" stroke="var(--c-history)" stroke-width="1" stroke-opacity=".6" stroke-linejoin="round"/>`;
  }
  if (base.length) {
    s += `<path d="${path(base)}" fill="none" stroke="var(--c-ring)" stroke-width="6" stroke-linejoin="round"/>`;
    s += `<path d="${path(base)}" fill="none" stroke="var(--c-baseline)" stroke-width="3" stroke-linejoin="round"/>`;
  }
  for (const r of live) {
    const c = colorOf(r), dash = c === "fold" ? ' stroke-dasharray="6 4"' : "", pts = series(r);
    s += `<path d="${path(pts)}" fill="none" stroke="var(--c-ring)" stroke-width="5.5" stroke-linejoin="round"/>`;
    s += `<path d="${path(pts)}" fill="none" stroke="${stroke(c)}" stroke-width="3"${dash} stroke-linejoin="round" stroke-linecap="round"/>`;
    const p = pts[pts.length - 1];
    s += `<circle cx="${x(p[ax])}" cy="${y(p[1])}" r="4.5" fill="${stroke(c)}" stroke="var(--c-ring)" stroke-width="2"/>`;
  }
  s += `<line id="cross" x1="0" x2="0" y1="${pad.t}" y2="${H - pad.b}" stroke="var(--c-muted)" stroke-dasharray="3 3" visibility="hidden"/>`;
  s += `<path id="hilite" d="" fill="none" stroke="var(--c-hilite)" stroke-width="2" stroke-dasharray="5 3" visibility="hidden"/>`;
  s += `<rect id="hit" x="${pad.l}" y="${pad.t}" width="${W - pad.l - pad.r}" height="${H - pad.t - pad.b}" fill="transparent"/></svg>`;
  host.innerHTML = s;
  host.appendChild(tip);
  const svg = host.querySelector("svg");
  $("hit").addEventListener("mousemove", (ev) => hover(ev, svg));
  $("hit").addEventListener("mouseleave", () => {
    tip.style.display = "none";
    $("cross").setAttribute("visibility", "hidden");
    $("hilite").setAttribute("visibility", "hidden");
  });
}

function hover(ev, svg) {
  const g = geom, pt = svg.createSVGPoint();
  pt.x = ev.clientX; pt.y = ev.clientY;
  const p = pt.matrixTransform(svg.getScreenCTM().inverse());
  let xv = Math.max(0, Math.min(g.xmax, (p.x - g.pad.l) / (g.W - g.pad.l - g.pad.r) * g.xmax));
  xv = byActions() ? Math.round(xv / 10) * 10 : Math.round(xv);
  $("cross").setAttribute("x1", g.x(xv)); $("cross").setAttribute("x2", g.x(xv));
  $("cross").setAttribute("visibility", "visible");
  const b = g.base.length ? at(g.base, xv, g.ax) : null;
  const rows = g.live.map((r) => ({ r, v: at(series(r), xv, g.ax) }))
    .filter((x) => x.v !== null && lastOf(x.r)[g.ax] >= xv).sort((a, z) => z.v - a.v);
  let near = null, nd = Infinity;
  for (const r of g.finished) {
    const v = at(series(r), xv, g.ax);
    if (v === null) continue;
    const dpx = Math.abs(g.y(v) - p.y);
    if (dpx < nd) { nd = dpx; near = { r, v }; }
  }
  const hil = $("hilite");
  if (near && nd < 10) {
    hil.setAttribute("d", series(near.r).map((q, i) => `${i ? "L" : "M"}${g.x(q[g.ax])},${g.y(q[1])}`).join(""));
    hil.setAttribute("visibility", "visible");
  } else { hil.setAttribute("visibility", "hidden"); near = null; }
  const head = byActions() ? `${xv.toLocaleString()} actions` : `Minute ${xv}`;
  let h = `<div class="h">${head}</div><table>`;
  if (b !== null) h += `<tr><td><span class="sw2" style="border-color:var(--c-baseline)"></span></td><td class="n">Baseline average</td><td>${fmt(b)}</td><td></td></tr>`;
  for (const { r, v } of rows.slice(0, 14)) {
    h += `<tr><td><span class="sw2" style="border-color:${stroke(colorOf(r))}"></span></td>`
      + `<td class="n">${esc(r.name)} <span class="m">${esc(letter(r.run_id))}</span></td><td>${fmt(v)}</td>`
      + `<td class="${b !== null && v - b >= 0 ? "pos" : "neg"}">${b !== null ? signed(v - b) : ""}</td></tr>`;
  }
  if (rows.length > 14) h += `<tr><td></td><td class="n m">+${rows.length - 14} more (see the table)</td><td></td><td></td></tr>`;
  if (near) {
    h += `<tr><td><span class="sw2" style="border-color:var(--c-hilite);border-top-style:dashed"></span></td>`
      + `<td class="n">${esc(near.r.name)} <span class="m">${esc(letter(near.r.run_id))} · finished ${fmt(near.r.points[near.r.points.length - 1][1])}</span></td>`
      + `<td>${fmt(near.v)}</td><td></td></tr>`;
  }
  const tip = $("tip");
  tip.innerHTML = h + "</table>";
  tip.style.display = "block";
  const box = $("chart").getBoundingClientRect();
  let left = ev.clientX - box.left + 14, top = ev.clientY - box.top + 14;
  if (left + tip.offsetWidth > box.width) left = ev.clientX - box.left - tip.offsetWidth - 14;
  if (top + tip.offsetHeight > box.height) top = Math.max(0, box.height - tip.offsetHeight);
  tip.style.left = Math.max(0, left) + "px"; tip.style.top = top + "px";
}

function drawLegend(live, bl, hidden) {
  const seen = new Map();
  for (const r of live) {
    const key = gridS(r.arm) !== null ? "grid:" + gridS(r.arm) : r.arm;
    if (!seen.has(key)) seen.set(key, { name: r.name, color: colorOf(r), n: 0, s: gridS(r.arm) });
    seen.get(key).n++;
  }
  const items = [...seen.values()].sort((a, b) => (a.s ?? 99) - (b.s ?? 99) || a.name.localeCompare(b.name));
  const folded = items.filter((i) => i.color === "fold");
  const nb = byActions() ? (bl.n_actions ?? bl.n) : bl.n;
  let h = `<span><span class="sw" style="border-color:var(--c-baseline)"></span>Baseline: ${esc(bl.label)} (${nb})</span>`;
  h += `<span><span class="sw" style="border-color:var(--c-history);border-top-width:2px"></span>Finished runs${hidden ? ` (${hidden} without action counts not drawn)` : ""}</span>`;
  for (const i of items.filter((i) => i.color !== "fold")) h += `<span><span class="sw" style="border-color:${i.color}"></span>${esc(i.name)} ×${i.n}</span>`;
  if (folded.length) h += `<span><span class="sw" style="border-color:var(--c-fold);border-top-style:dashed"></span>Other live (${folded.length} versions; see the table)</span>`;
  $("legend").innerHTML = h;
}

function drawLive(live, baseAt) {
  const ax = AX();
  const rows = live.map((r) => {
    const p = lastOf(r), b = baseAt(p[ax]), acts = r.points[r.points.length - 1][2];
    return { r, minute: r.points[r.points.length - 1][0], actions: acts, score: p[1], base: b,
             gap: b !== null ? p[1] - b : null, per1k: acts ? 1000 * r.points[r.points.length - 1][1] / acts : null };
  });
  const k = state.sort;
  rows.sort((a, b) => (k === "name" ? a.r.name.localeCompare(b.r.name) || a.r.run_id.localeCompare(b.r.run_id)
                                    : (b[k] ?? -1e9) - (a[k] ?? -1e9)));
  let h = `<thead><tr><th data-k="name">Version</th><th>Run</th><th class="num" data-k="minute">Minute</th>`
    + `<th class="num" data-k="actions">Actions</th><th class="num" data-k="score">Score</th>`
    + `<th class="num" data-k="per1k">Per 1k actions</th><th class="num" data-k="base">Baseline then</th>`
    + `<th class="num" data-k="gap">Gap</th><th class="num">Levels</th><th class="num">Hard-7</th></tr></thead><tbody>`;
  for (const x of rows) {
    h += `<tr><td><span class="sw2" style="border-color:${stroke(colorOf(x.r))}"></span>${esc(x.r.name)}</td>`
      + `<td>${esc(letter(x.r.run_id))}</td><td class="num">${x.minute}</td>`
      + `<td class="num">${x.actions !== null && x.actions !== undefined ? x.actions.toLocaleString() : "–"}</td>`
      + `<td class="num">${fmt(x.score)}</td><td class="num">${fmt(x.per1k, 2)}</td>`
      + `<td class="num">${fmt(x.base)}</td><td class="num ${x.gap >= 0 ? "pos" : "neg"}">${signed(x.gap)}</td>`
      + `<td class="num">${x.r.levels ?? "–"}</td><td class="num">${fmt(x.r.hard7)}</td></tr>`;
  }
  if (!rows.length) h += `<tr><td colspan="10" class="muted">No runs playing in this view.</td></tr>`;
  $("live").innerHTML = h + "</tbody>";
  $("live").querySelectorAll("th[data-k]").forEach((th) => { th.onclick = () => { state.sort = th.dataset.k; render(); }; });
}

function drawFinished(finished) {
  const rows = finished.map((r) => {
    const p = r.points[r.points.length - 1];
    return { r, final: p[1], actions: p[2], per1k: p[2] ? 1000 * p[1] / p[2] : null };
  }).sort((a, b) => b.final - a.final);
  $("finSummary").textContent = `Finished runs (${rows.length}), best first`;
  let h = `<thead><tr><th>Version</th><th>Run</th><th class="num">Final score</th><th class="num">Actions</th>`
    + `<th class="num">Per 1k actions</th><th class="num">Levels</th><th class="num">Hard-7</th></tr></thead><tbody>`;
  for (const x of rows) {
    h += `<tr><td>${esc(x.r.name)}</td><td>${esc(x.r.run_id.replace(/^g4run-/, ""))}</td><td class="num">${fmt(x.final)}</td>`
      + `<td class="num">${x.actions ? x.actions.toLocaleString() : "–"}</td><td class="num">${fmt(x.per1k, 2)}</td>`
      + `<td class="num">${x.r.levels ?? "–"}</td><td class="num">${fmt(x.r.hard7)}</td></tr>`;
  }
  $("finished").innerHTML = h + "</tbody>";
}

async function load() {
  try {
    const r = await fetch("/api/v1/rl2/doc/score-climb", { cache: "no-store", credentials: "same-origin", redirect: "manual" });
    if (r.type === "opaqueredirect" || r.status === 401 || r.status === 403) throw new Error("sign in to the site to see this page");
    if (r.status === 404) throw new Error("nothing published yet");
    if (!r.ok) throw new Error("HTTP " + r.status);
    const d = await r.json();
    state.data = d;
    const sel = $("baseline");
    if (!state.baseline || !d.baselines[state.baseline]) state.baseline = d.default_baseline;
    const keys = Object.keys(d.baselines);
    if (sel.options.length !== keys.length) {
      sel.innerHTML = "";
      for (const k of keys) sel.add(new Option(`${d.baselines[k].label} (${d.baselines[k].n})`, k));
    }
    sel.value = state.baseline;
    $("updated").textContent = "published " + new Date(d.generated_at * 1000).toLocaleTimeString();
    render();
  } catch (e) {
    $("updated").textContent = "not loaded: " + e.message;
  }
}

for (const id of ["view", "axis"]) {
  $(id).addEventListener("click", (ev) => {
    const b = ev.target.closest("button");
    if (!b) return;
    $(id).querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
    state[id] = b.dataset.v;
    render();
  });
}
$("baseline").addEventListener("change", (ev) => { state.baseline = ev.target.value; render(); });
window.addEventListener("resize", () => render());
new MutationObserver(() => render()).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
load();
setInterval(load, 60000);

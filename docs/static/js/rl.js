// RL page (docs/rl.html): Daniel's no-border notebook learning from its own wins, round by round. Ported from the
// arc3-rl-live web.app page; chrome from theme.css and rl-shell.css, model colours from model-colors.js (blue).

import { modelColor } from "./model-colors.js?v=20261002-blue";

const NS = "http://www.w3.org/2000/svg";
const GPU_GIB = 95;
let DATA = null;

function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") e.className = v; else if (k === "style") e.style.cssText = v;
    else if (k === "html") e.innerHTML = v; else e.setAttribute(k, v);
  }
  for (const k of kids.flat()) if (k !== null && k !== undefined && k !== false) e.append(k instanceof Node ? k : document.createTextNode(String(k)));
  return e;
}
function sv(tag, attrs, ...kids) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v !== null && v !== undefined) e.setAttribute(k, v);
  for (const k of kids.flat()) if (k !== null && k !== undefined) e.append(k instanceof Node ? k : document.createTextNode(String(k)));
  return e;
}
const fmtK = n => n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e4 ? Math.round(n / 1e3) + "k" : n >= 1e3 ? (n / 1e3).toFixed(1) + "k" : String(Math.round(n));
const fmtInt = n => Math.round(n).toLocaleString("en-US");
const clock = iso => iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "–";
function dur(min) {
  min = Math.max(0, Math.round(min));
  if (min < 60) return min + " min";
  const h = Math.floor(min / 60), m = min % 60;
  return h + " h" + (m ? " " + m + " min" : "");
}
const durc = min => { min = Math.max(0, Math.round(min)); return min < 60 ? min + "m" : Math.floor(min / 60) + "h" + (min % 60 ? " " + (min % 60) + "m" : ""); };
function ago(iso) {
  if (!iso) return "time unknown";
  const s = (Date.now() - new Date(iso)) / 1000;
  return s < 90 ? "just now" : dur(s / 60) + " ago";
}
function until(iso) {
  const m = (new Date(iso) - Date.now()) / 60000;
  return m <= 1 ? "any minute" : "in " + dur(m);
}
const C = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const mean = a => a.length ? a.reduce((s, x) => s + x, 0) / a.length : NaN;

/* ------------------------------------------------------------------ stage states */
function states(d) {
  const t = d.train, map = s => s === "running" ? "active" : s;
  const runsOf = keys => d.panels.flatMap(p => keys.flatMap(k => (p.models[k] || { runs: [] }).runs));
  const tested = runsOf(d.models.slice(1).map(m => m.key)), base = runsOf([d.models[0].key]);
  const testedDone = tested.length > 0 && tested.every(r => r.state === "done");
  const st = {
    play: "done", pick: "done", train: map(t.job_state), merge: map(t.merge.state),
    copy: tested.length ? "done" : (t.merge.state === "done" ? "active" : "waiting"),
    test: testedDone ? "done" : tested.length ? "active" : "waiting",
    score: testedDone ? "done" : "waiting",
  };
  const basePlaying = base.filter(r => r.state !== "done").length;
  const note = {
    play: "1 Oct", pick: "done",
    train: t.job_state === "running" ? `${t.done}/${t.total}` : t.job_state,
    merge: t.merge.state === "done" ? "done" : t.merge.state === "running" ? "running" : "next",
    copy: st.copy === "done" ? "done" : "after merge",
    test: tested.length ? (testedDone ? "done" : "new weights playing") : (basePlaying ? "before-runs playing" : "before-runs done"),
    score: testedDone ? "done" : "last",
  };
  return { st, note };
}

/* ------------------------------------------------------------------ hero */
function renderHero(d) {
  const t = d.train, recs = t.records;
  document.getElementById("lede").textContent = d.round_note;
  const eye = t.job_state === "running" ? "training now" : t.job_state === "done" ? (t.merge.state === "done" ? "testing the new weights" : "merging") : t.job_state;
  document.getElementById("roundEyebrow").textContent = `${d.round} · ${eye}`;
  const learned = recs.reduce((s, r) => s + r.trained, 0);
  const seen = recs.reduce((s, r) => s + r.tokens, 0);
  const w = Math.min(8, Math.max(1, Math.floor(recs.length / 3)));
  const first = mean(recs.slice(0, w).map(r => r.loss)), last = mean(recs.slice(-w).map(r => r.loss));
  const pct = t.total ? 100 * (t.done + t.skipped) / t.total : 0;
  const stats = document.getElementById("stats");
  stats.replaceChildren(
    el("div", { class: "stat" }, el("div", { class: "k" }, "Records trained"),
      el("div", { class: "v num" }, t.done, el("small", {}, "/ " + t.total)),
      el("div", { class: "bar" }, el("b", { style: `width:${pct.toFixed(1)}%` })),
      el("div", { class: "s" }, t.skipped ? `${t.skipped} skipped (too big for memory)` : `one record every ${Math.round(t.mean_sec / 60 * 10) / 10} min`)),
    el("div", { class: "stat" }, el("div", { class: "k" }, "Winning turns learned"),
      el("div", { class: "v num" }, fmtK(learned), el("small", {}, "tokens")),
      el("div", { class: "s" }, `out of ${fmtK(seen)} tokens of game history read`)),
    el("div", { class: "stat" }, el("div", { class: "k" }, "Loss on unseen records"),
      el("div", { class: "v num" }, isNaN(last) ? "–" : last.toFixed(3)),
      el("div", { class: "s" }, recs.length >= 6 ? `${last <= first ? "▼" : "▲"} from ${first.toFixed(3)} over the first ${w} records` : "needs a few more records to show a trend")),
    el("div", { class: "stat" }, el("div", { class: "k" }, t.job_state === "running" ? "Training ends" : "Training"),
      el("div", { class: "v num" }, t.job_state === "running" && t.eta ? clock(t.eta) : t.job_state),
      el("div", { class: "s" }, t.job_state === "running" && t.eta ? `${until(t.eta)}, then merge and test` : t.adapter ? `adapter ${t.adapter.sha}, ${t.adapter.steps} steps` : "")),
  );
}

/* ------------------------------------------------------------------ loop */
function renderLoop(d) {
  const { st, note } = states(d), stages = d.stages, n = stages.length;
  const W = 560, H = 470, cx = 280, cy = 235, R = 150;
  // 50 px of margin each side: the side labels ("before-runs playing") reach past the ring
  const svg = sv("svg", { viewBox: `-50 0 ${W + 100} ${H}`, class: "loop", role: "img", "aria-label": "The loop: " + stages.map(s => s.label).join(", ") });
  svg.append(sv("defs", {}, sv("filter", { id: "glow", x: "-30%", y: "-30%", width: "160%", height: "160%" },
    sv("feGaussianBlur", { stdDeviation: "3.5", result: "b" }), sv("feMerge", {}, sv("feMergeNode", { in: "b" }), sv("feMergeNode", { in: "SourceGraphic" })))));
  svg.append(sv("circle", { cx, cy, r: R + 0.5, fill: "none", stroke: C("--rl-ring"), "stroke-width": 26 }));
  const ang = i => -Math.PI / 2 + i * 2 * Math.PI / n;
  for (let i = 0; i < n; i++) {
    const a0 = ang(i) + 0.2, a1 = ang(i + 1) - 0.2;
    const p = a => `${(cx + R * Math.cos(a)).toFixed(1)},${(cy + R * Math.sin(a)).toFixed(1)}`;
    const next = st[stages[(i + 1) % n].key], cur = st[stages[i].key];
    const cls = cur === "done" && (next === "done" || next === "active") ? "arc done" : (cur === "active" || next === "active") && cur !== "waiting" ? "arc active" : "arc";
    svg.append(sv("path", { d: `M${p(a0)} A${R},${R} 0 0 1 ${p(a1)}`, class: cls }));
  }
  stages.forEach((s, i) => {
    const a = ang(i), x = cx + R * Math.cos(a), y = cy + R * Math.sin(a), state = st[s.key];
    const g = sv("g", { class: "node " + state, transform: `translate(${x.toFixed(1)},${y.toFixed(1)})` });
    if (state === "active") g.append(sv("circle", { r: 24, class: "pulse" }));
    g.append(sv("circle", { r: 21, class: "dot" }));
    g.append(sv("text", { class: "numt", "text-anchor": "middle", dy: "0.36em" }, state === "done" ? "✓" : String(i + 1)));
    svg.append(g);
    const c = Math.cos(a), lr = R + 36;
    const anchor = Math.abs(c) < 0.25 ? "middle" : c > 0 ? "start" : "end";
    const lx = cx + lr * c, ly = cy + lr * Math.sin(a) + (Math.abs(c) < 0.25 ? (Math.sin(a) < 0 ? -10 : 8) : -6);
    svg.append(sv("text", { x: lx.toFixed(1), y: ly.toFixed(1), class: "nlabel " + state, "text-anchor": anchor }, s.label));
    svg.append(sv("text", { x: lx.toFixed(1), y: (ly + 17).toFixed(1), class: "nstate " + state, "text-anchor": anchor }, note[s.key]));
  });
  const lap = stages.filter(s => s.key !== "play").reduce((a, s) => a + (s.minutes || 0), 0);
  svg.append(sv("text", { x: cx, y: cy - 18, class: "center1", "text-anchor": "middle" }, d.round));
  svg.append(sv("text", { x: cx, y: cy + 14, class: "center3", "text-anchor": "middle" }, "≈ " + dur(lap)));
  svg.append(sv("text", { x: cx, y: cy + 36, class: "center2", "text-anchor": "middle" }, "per lap"));
  document.getElementById("loopSvg").replaceChildren(svg);

  const total = stages.reduce((a, s) => a + (s.minutes || 0), 0);
  let at = 0;
  const rows = stages.map(s => {
    const m = s.minutes || 0, left = 100 * at / total, width = Math.max(0.8, 100 * m / total);
    at += m;
    const state = st[s.key];
    return [el("div", { class: "grow" },
      el("div", { class: "gl" }, s.label),
      el("div", { class: "gt" }, el("b", { class: (s.measured ? "" : "est ") + (state === "active" ? "now" : ""), style: `left:${left}%;width:${width}%` })),
      el("div", { class: "gd" }, (s.measured ? "" : "~") + durc(m))),
    el("div", { class: "grow" }, el("div", { class: "gx" }, s.detail))];
  });
  document.getElementById("gantt").replaceChildren(...rows.flat(),
    el("div", { class: "gsum" }, el("span", {}, "First round, from the plays to a verdict"), el("span", { class: "num" }, "≈ " + dur(total))),
    el("div", { class: "muted", style: "font-size:13px" }, `Every later lap skips the first Play: ≈ ${dur(lap)}. Training is most of it, so smaller game batches per round shorten the lap the most.`));
}

/* ------------------------------------------------------------------ training */
function renderTraining(d) {
  const t = d.train, recs = t.records, N = Math.max(t.total, recs.length, 1);
  const box = document.getElementById("lossBox");
  if (!recs.length) { box.replaceChildren(el("div", { class: "empty" }, "Waiting for the first record to finish…")); renderNow(d); return; }
  const W = 760, H = 380, L = 58, R = 12, T = 16, TRK = 76, B = 34 + TRK;
  const pw = W - L - R, ph = H - T - B, step = pw / N;
  const losses = recs.map(r => r.loss);
  const hi = Math.max(0.45, Math.max(...losses) * 1.12), lo = 0;
  const x = i => L + (i + 0.5) * step, y = v => T + ph * (1 - (v - lo) / (hi - lo));
  const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart", role: "img", "aria-label": "Loss per record" });
  svg.append(sv("defs", {}, sv("filter", { id: "glow2", x: "-10%", y: "-50%", width: "120%", height: "200%" },
    sv("feGaussianBlur", { stdDeviation: "3", result: "b" }), sv("feMerge", {}, sv("feMergeNode", { in: "b" }), sv("feMergeNode", { in: "SourceGraphic" })))));
  for (let k = 0; k <= 4; k++) {
    const v = lo + (hi - lo) * k / 4;
    svg.append(sv("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), class: "gridl" }));
    svg.append(sv("text", { x: L - 8, y: y(v) + 4, class: "axis", "text-anchor": "end" }, v.toFixed(2)));
  }
  svg.append(sv("rect", { x: L + recs.length * step, y: T, width: Math.max(0, pw - recs.length * step), height: ph + 24 + TRK, class: "future" }));
  if (recs.length < N) svg.append(sv("text", { x: Math.min(W - R - 170, L + recs.length * step + 12), y: T + 20, class: "axis" }, `${N - recs.length} records to go →`));
  // tokens track
  const ty0 = H - 6, tmax = 125000;
  svg.append(sv("text", { x: L - 8, y: ty0 - TRK + 10, class: "axis", "text-anchor": "end" }, "tokens"));
  svg.append(sv("text", { x: L - 8, y: ty0, class: "axis", "text-anchor": "end" }, "0"));
  recs.forEach((r, i) => {
    const hgt = (TRK - 14) * Math.min(1, r.tokens / tmax), bw = Math.max(1.5, step * 0.66);
    svg.append(sv("rect", { x: x(i) - bw / 2, y: ty0 - hgt, width: bw, height: hgt, rx: 1.5, class: "tok" + (i === recs.length - 1 ? " last" : "") }));
    const hw = (TRK - 14) * Math.min(1, r.trained / tmax);
    svg.append(sv("rect", { x: x(i) - bw / 2, y: ty0 - hw, width: bw, height: hw, rx: 1.5, fill: C("--rl-win") }));
  });
  // x axis ticks
  for (let k = 0; k <= N; k += N > 60 ? 10 : 5) svg.append(sv("text", { x: L + k * step, y: T + ph + 22, class: "axis", "text-anchor": "middle" }, k));
  // rolling mean
  const win = 8, avg = recs.map((_, i) => mean(losses.slice(Math.max(0, i - win + 1), i + 1)));
  if (recs.length > 1) svg.append(sv("path", { d: avg.map((v, i) => (i ? "L" : "M") + x(i).toFixed(1) + "," + y(v).toFixed(1)).join(""), class: "avg" }));
  recs.forEach((r, i) => svg.append(sv("circle", { cx: x(i), cy: y(r.loss), r: i === recs.length - 1 ? 6 : 4.4, class: "pt" + (i === recs.length - 1 ? " last" : "") })));
  const hl = sv("line", { y1: T, y2: H - 6, class: "hl", visibility: "hidden" });
  svg.append(hl);
  const tip = el("div", { class: "tip" });
  svg.addEventListener("mousemove", ev => {
    const pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    const i = Math.floor((p.x - L) / step);
    if (i < 0 || i >= recs.length) { tip.style.opacity = 0; hl.setAttribute("visibility", "hidden"); return; }
    const r = recs[i];
    hl.setAttribute("x1", x(i)); hl.setAttribute("x2", x(i)); hl.setAttribute("visibility", "visible");
    tip.replaceChildren(el("div", {}, el("b", { class: "mono" }, r.game), `  record ${i + 1}`),
      el("div", {}, `loss `, el("b", { class: "mono" }, r.loss.toFixed(3)), `   rolling `, el("b", { class: "mono" }, avg[i].toFixed(3))),
      el("div", {}, `${fmtInt(r.tokens)} tokens, ${fmtInt(r.trained)} winning`),
      el("div", {}, `${(r.sec / 60).toFixed(1)} min, done ${clock(r.end)}`));
    const bb = box.getBoundingClientRect(), sp = svg.getBoundingClientRect();
    tip.style.left = (sp.left - bb.left + (x(i) / W) * sp.width) + "px";
    tip.style.top = (sp.top - bb.top + (y(r.loss) / H) * sp.height) + "px";
    tip.style.opacity = 1;
  });
  svg.addEventListener("mouseleave", () => { tip.style.opacity = 0; hl.setAttribute("visibility", "hidden"); });
  box.replaceChildren(svg, tip,
    el("div", { class: "legend" },
      el("span", {}, el("i", { style: `background:${C("--rl-point")};border-radius:50%;width:10px;height:10px` }), "loss of one record"),
      el("span", {}, el("i", { style: `background:${C("--rl-avg")};height:3px` }), "rolling mean of 8"),
      el("span", {}, el("i", { style: `background:${C("--rl-tok")}` }), "tokens read"),
      el("span", {}, el("i", { style: `background:${C("--rl-win")}` }), "of them, winning turns trained")));
  renderNow(d);
}

function renderNow(d) {
  const t = d.train, r = t.records[t.records.length - 1], card = document.getElementById("nowCard");
  if (!r) { card.replaceChildren(el("h3", {}, "Just trained"), el("div", { class: "empty" }, "nothing yet")); return; }
  const share = 100 * r.trained / r.tokens;
  card.replaceChildren(
    el("h3", {}, "Just trained"),
    el("div", { class: "g" }, r.game),
    el("div", { class: "muted", style: "font-size:13px" }, `record ${t.records.length} of ${t.total}` + (r.end ? `, finished ${clock(r.end)} (${ago(r.end)})` : "")),
    el("dl", { class: "kv" },
      el("dt", {}, "game history read"), el("dd", {}, fmtInt(r.tokens) + " tokens"),
      el("dt", {}, "winning turns trained"), el("dd", {}, `${fmtInt(r.trained)} (${share.toFixed(0)}%)`),
      el("dt", {}, "loss"), el("dd", {}, r.loss.toFixed(3)),
      el("dt", {}, "time"), el("dd", {}, (r.sec / 60).toFixed(1) + " min"),
      el("dt", {}, "optimizer steps so far"), el("dd", {}, String(r.step))),
    el("div", { class: "mem" },
      el("div", { class: "muted", style: "font-size:12.5px;margin-bottom:2px" }, "Peak GPU memory on the 4 cards (95 GiB each)"),
      ...(r.mem || []).map((m, i) => el("div", { class: "mr" }, el("span", {}, "card " + (i + 1)),
        el("div", { class: "mt" }, el("b", { style: `width:${Math.min(100, 100 * m / GPU_GIB).toFixed(1)}%` })),
        el("span", { class: "num", style: "text-align:right" }, m.toFixed(1) + " GiB")))),
    ...(t.skips.length ? [el("div", { class: "note" }, `Skipped: ${t.skips.map(s => `${s.game} (${s.why})`).join(", ")}`)] : []),
  );
}

/* ------------------------------------------------------------------ games */
function renderGames(d) {
  const grid = document.getElementById("gameGrid"), recs = d.train.records;
  const last = recs.length ? recs[recs.length - 1].game : null;
  grid.replaceChildren(...d.split.train.map(g => {
    const info = d.g0[g] || {}, max = d.levels[g] || 0;
    const c = new Set((info.c || {}).cleared || []), dd = new Set((info.d || {}).cleared || []);
    const total = ((info.c || {}).records || 0) + ((info.d || {}).records || 0);
    const done = recs.filter(r => r.game === g).length;
    const replies = ((info.c || {}).replies || 0) + ((info.d || {}).replies || 0);
    const best = Math.max(0, ...c, ...dd);
    const pips = [];
    for (let lv = 1; lv <= max; lv++) {
      const k = (c.has(lv) ? 1 : 0) + (dd.has(lv) ? 1 : 0);
      pips.push(el("i", { class: k === 2 ? "c2" : k === 1 ? "c1" : "", title: `level ${lv}: cleared in ${k} of 2 runs` }));
    }
    return el("div", { class: "gc" + (g === last && d.train.job_state === "running" ? " hot" : "") },
      el("div", { class: "gh" }, el("span", { class: "gn" }, g), el("span", { class: "gr" }, `best level ${best} of ${max}`)),
      el("div", { class: "pips" }, ...pips),
      el("div", { class: "gs" }, el("span", {}, `${replies} winning turns`), el("span", { class: "num" }, `${done}/${total} records`)),
      el("div", { class: "gb" }, el("b", { style: `width:${total ? (100 * done / total).toFixed(0) : 0}%` })));
  }));
  document.getElementById("others").replaceChildren(
    el("span", { class: "lab" }, "Held out, never trained:"), ...d.split.held.map(g => el("span", { class: "og held" }, g)),
    el("span", { class: "lab", style: "margin-left:14px" }, "Easy six, only checked:"), ...d.split.easy.map(g => el("span", { class: "og" }, g)));
}

/* ------------------------------------------------------------------ models */

/* ------------------------------------------------------------------ before vs after, round by round */
function verdict(base, last) {
  if (!last) return el("span", { class: "chip" }, "before only, so far");
  if (base.playing || last.playing || base.se === null || last.se === null) return el("span", { class: "chip active" }, "test running");
  const dv = last.total - base.total, se = Math.hypot(base.se, last.se), clear = Math.abs(dv) > 2 * se;
  return el("span", { class: "chip " + (clear ? (dv > 0 ? "done" : "failed") : "") },
    `${dv >= 0 ? "+" : ""}${dv.toFixed(1)} ± ${se.toFixed(1)} levels per run · ${clear ? (dv > 0 ? "clear gain" : "clear loss") : "within noise"}`);
}
function niceMax(v) {
  const steps = [4, 8, 12, 16, 20, 24, 32, 40, 48, 60, 80];   // quarters stay whole numbers
  return steps.find(s => s >= v) || Math.ceil(v / 20) * 20;
}

/* ------------------------------------------------------------------ score per play, round by round (Son 3-Oct) */
// One small chart per panel: the mean Kaggle-style score per play (0-100) of each model, in round order, with its
// standard error. The panel's score is the mean over its games of each game's mean score, so every game counts the
// same; its error is sqrt(sum over games of variance / plays) / games, like the panel totals of levels.
function panelScore(data) {
  if (!data || !data.plays.length) return null;
  const by = {};
  data.plays.forEach(q => { if (q.score !== null && q.score !== undefined) (by[q.game] = by[q.game] || []).push(q.score); });
  const games = Object.values(by);
  if (!games.length) return null;
  const varn = games.map(v => { const m = mean(v); return v.length > 1 ? v.reduce((s, x) => s + (x - m) ** 2, 0) / (v.length - 1) / v.length : 0; });
  return { score: mean(games.map(mean)), se: Math.sqrt(varn.reduce((s, x) => s + x, 0)) / games.length,
           n: data.plays.length, playing: data.playing > 0 };
}
function trendChart(d, p, box) {
  const cols = d.models.map((m, i) => ({ m, i, s: panelScore(p.models[m.key]) }));
  const pts = cols.filter(c => c.s);
  const W = 360, H = 190, L = 34, R = 18, T = 22, B = 30, pw = W - L - R, ph = H - T - B;
  const ymax = niceMax(Math.max(8, ...pts.map(c => c.s.score + c.s.se)) * 1.12);
  const pad = 28;                    // keeps the end columns' labels off the y axis and the card edge
  const x = i => L + pad + (cols.length > 1 ? (pw - 2 * pad) * i / (cols.length - 1) : (pw - 2 * pad) / 2),
        y = v => T + ph * (1 - v / ymax);
  const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, class: "trend", role: "img",
    "aria-label": `${p.label}: score per play by round, ` + pts.map(c => `${c.m.short} ${c.s.score.toFixed(1)}`).join(", ") });
  for (let k = 0; k <= 4; k++) {
    const v = ymax * k / 4;
    svg.append(sv("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), class: "gridl" }));
    svg.append(sv("text", { x: L - 7, y: y(v) + 4, class: "axis", "text-anchor": "end" }, Math.round(v)));
  }
  cols.forEach(c => svg.append(sv("text", { x: x(c.i), y: H - 8, class: "colh" + (c.s ? "" : " ghost"), "text-anchor": "middle" }, c.m.short)));
  pts.forEach(c => {
    if (!(c.s.se > 0) || c.s.playing) return;      // a run still playing has no meaningful error yet
    const lo = y(Math.max(0, c.s.score - c.s.se)), hi = y(c.s.score + c.s.se);
    svg.append(sv("line", { x1: x(c.i), x2: x(c.i), y1: lo, y2: hi, class: "wh" }));
    for (const yy of [lo, hi]) svg.append(sv("line", { x1: x(c.i) - 4, x2: x(c.i) + 4, y1: yy, y2: yy, class: "wh" }));
  });
  // the line joins finished models only: a run still playing has partial scores (its games are not over), so it is
  // drawn as a hollow point marked "playing", off the line
  const done = pts.filter(c => !c.s.playing);
  if (done.length > 1) svg.append(sv("path", { d: done.map((c, k) => (k ? "L" : "M") + x(c.i).toFixed(1) + "," + y(c.s.score).toFixed(1)).join(""), class: "tl" }));
  // direct labels on the first and the latest finished point only
  const labelled = [...new Set([done[0], done[done.length - 1]])].filter(Boolean);
  labelled.forEach(c => svg.append(sv("text", { x: x(c.i), y: y(c.s.score + c.s.se) - 7, class: "tv", "text-anchor": "middle" }, c.s.score.toFixed(1))));
  pts.filter(c => c.s.playing).forEach(c => svg.append(sv("text", { x: x(c.i), y: y(c.s.score) + 18, class: "tp", "text-anchor": "middle" }, "playing")));
  const tip = el("div", { class: "tip" });
  pts.forEach(c => {
    svg.append(sv("circle", { cx: x(c.i), cy: y(c.s.score), r: 5, class: "tm" + (c.s.playing ? " open" : "") }));
    const hit = sv("circle", { cx: x(c.i), cy: y(c.s.score), r: 16, class: "hit" });
    hit.addEventListener("mouseenter", () => {
      tip.replaceChildren(el("div", {}, el("b", {}, c.m.label)),
        el("div", {}, "score per play ", el("b", { class: "mono" }, c.s.score.toFixed(1)), ` ± ${c.s.se.toFixed(1)}`),
        el("div", {}, `${c.s.n} plays${c.s.playing ? ", still playing" : ""}`));
      const sp = svg.getBoundingClientRect(), bb = box.getBoundingClientRect();
      tip.style.left = (sp.left - bb.left + (x(c.i) / W) * sp.width) + "px";
      tip.style.top = (sp.top - bb.top + (y(c.s.score) / H) * sp.height) + "px";
      tip.style.opacity = 1;
    });
    hit.addEventListener("mouseleave", () => { tip.style.opacity = 0; });
    svg.append(hit);
  });
  return [svg, tip];
}
function renderTrends(d) {
  document.getElementById("betterTrends").replaceChildren(...d.panels.map(p => {
    const base = panelScore(p.models[d.models[0].key]);
    const later = d.models.slice(1).map(m => ({ m, s: panelScore(p.models[m.key]) })).filter(x => x.s);
    const fin = later.filter(x => !x.s.playing), last = fin[fin.length - 1], running = later.find(x => x.s.playing);
    let chip = el("span", { class: running ? "chip active" : "chip" }, running ? `${running.m.short} playing` : "before only, so far");
    if (base && !base.playing && last) {
      const dv = last.s.score - base.score, se = Math.hypot(base.se, last.s.se), clear = Math.abs(dv) > 2 * se;
      chip = el("span", { class: "chip " + (clear ? (dv > 0 ? "done" : "failed") : "") },
        `${last.m.short}: ${dv >= 0 ? "+" : ""}${dv.toFixed(1)} ± ${se.toFixed(1)}` + (clear ? "" : " · noise"));
    }
    const card = el("div", { class: "card trendcard" });
    card.append(el("div", { class: "th" }, el("h3", {}, p.label), chip),
      el("div", { class: "tsub" }, "score per play (0-100), round by round"), ...trendChart(d, p, card));
    return card;
  }));
}
function roundsChart(d, p) {
  const cols = d.models.map((m, i) => ({ m, i, data: p.models[m.key] }));
  if (d.next_model) cols.push({ m: d.next_model, i: cols.length, data: null, ghost: true });
  const W = 440, H = 270, L = 46, R = 22, T = 18, B = 46, ph = H - T - B;
  const vals = cols.flatMap(c => c.data ? [...c.data.reps.map(r => r.levels), c.data.total + (c.data.se || 0)] : []);
  const ymax = niceMax(Math.max(6, ...vals) * 1.12);
  const cw = (W - L - R) / cols.length, x = i => L + (i + 0.5) * cw, y = v => T + ph * (1 - v / ymax);
  const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, class: "rounds", role: "img", "aria-label": `${p.label}: levels per run, before and after each round` });
  for (let k = 0; k <= 4; k++) {
    const v = ymax * k / 4;
    svg.append(sv("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), class: "gridl" }));
    svg.append(sv("text", { x: L - 8, y: y(v) + 4, class: "axis", "text-anchor": "end" }, Math.round(v)));
  }
  svg.append(sv("text", { x: 13, y: T + ph / 2, class: "axis", transform: `rotate(-90 13 ${T + ph / 2})`, "text-anchor": "middle" }, "levels per run"));
  const pts = cols.filter(c => c.data && c.data.plays.length).map(c => [x(c.i), y(c.data.total)]);
  if (pts.length > 1) svg.append(sv("path", { d: pts.map((q, k) => (k ? "L" : "M") + q[0].toFixed(1) + "," + q[1].toFixed(1)).join(""), class: "trend" }));
  cols.forEach(c => {
    const cx = x(c.i), color = modelColor(c.i), data = c.data;
    svg.append(sv("text", { x: cx, y: H - 24, class: "colh" + (c.ghost ? " ghost" : ""), "text-anchor": "middle" }, c.m.short));
    if (c.ghost || !data || !data.plays.length) {
      svg.append(sv("rect", { x: cx - 27, y: T, width: 54, height: ph, rx: 10, class: "ghostcol" }));
      svg.append(sv("text", { x: cx, y: H - 8, class: "coln", "text-anchor": "middle" },
        c.ghost ? "next round" : c.i === 0 ? "starting" : "after merge"));
      return;
    }
    const reps = data.reps, n = reps.length;
    svg.append(sv("text", { x: cx, y: H - 8, class: "coln", "text-anchor": "middle" }, `${reps.filter(r => r.complete).length}/${n} runs done`));
    if (data.se !== null && !data.playing)
      svg.append(sv("rect", { x: cx - 25, y: y(data.total + data.se), width: 50, height: Math.max(1, y(data.total - data.se) - y(data.total + data.se)), rx: 4, fill: color, opacity: 0.16 }));
    reps.forEach((r, k) => {
      const dx = n > 1 ? (k / (n - 1) - 0.5) * 36 : 0;
      svg.append(sv("circle", { cx: (cx + dx).toFixed(1), cy: y(r.levels).toFixed(1), r: 5, fill: r.complete ? color : "none", stroke: color, "stroke-width": 2, class: r.complete ? "" : "open" },
        sv("title", {}, `run ${k + 1}: ${r.levels} levels over ${r.games} games${r.complete ? "" : " so far (still playing)"}`)));
    });
    svg.append(sv("line", { x1: cx - 27, x2: cx + 27, y1: y(data.total), y2: y(data.total), stroke: color, "stroke-width": 3, "stroke-linecap": "round" }));
    svg.append(sv("text", { x: cx + 31, y: y(data.total) + 4, class: "meanlab", fill: color }, data.total.toFixed(1)));
  });
  return svg;
}
function gameRanges(d, p) {
  const ms = d.models.map((m, i) => ({ m, i, data: p.models[m.key] })).filter(c => c.data && c.data.plays.length);
  const pmax = Math.max(...p.games.map(g => p.levels[g]));
  const rows = p.games.map(g => {
    const max = p.levels[g], W = 300, lane = 13, top = 4, H = top + Math.max(1, ms.length) * lane + 16;
    const x = v => 8 + (W - 16) * v / pmax;
    const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, class: "range" });
    svg.append(sv("rect", { x: x(0) - 5, y: top - 2, width: x(max) - x(0) + 10, height: Math.max(1, ms.length) * lane + 2, rx: 5, class: "rtrack" }));
    for (let lv = 0; lv <= max; lv++) svg.append(sv("text", { x: x(lv), y: H - 3, class: "lvl", "text-anchor": "middle" }, lv));
    ms.forEach((c, k) => {
      const lv = c.data.plays.filter(q => q.game === g).map(q => q.levels);
      if (!lv.length) return;
      const yy = top + k * lane + lane / 2, color = modelColor(c.i), lo = Math.min(...lv), hi = Math.max(...lv), mu = mean(lv);
      svg.append(sv("line", { x1: x(lo), x2: x(hi), y1: yy, y2: yy, stroke: color, "stroke-width": 6, "stroke-linecap": "round", opacity: 0.32 }));
      lv.forEach(v => svg.append(sv("circle", { cx: x(v), cy: yy, r: 2.7, fill: color })));
      svg.append(sv("line", { x1: x(mu), x2: x(mu), y1: yy - 6, y2: yy + 6, stroke: color, "stroke-width": 2.5 }));
    });
    const means = ms.map(c => { const lv = c.data.plays.filter(q => q.game === g).map(q => q.levels); return lv.length ? mean(lv).toFixed(1) : "–"; });
    return el("div", { class: "rrow" }, el("span", { class: "pg" }, g), svg, el("span", { class: "rm num" }, means.join(" → ")));
  });
  return el("div", { class: "ranges" },
    el("div", { class: "rhead" }, el("span", {}, "each game: every play as a dot, its spread as a bar, the tick is the mean"), el("span", {}, "mean")), ...rows);
}
function renderBetter(d) {
  document.getElementById("betterLegend").replaceChildren(el("div", { class: "mlegend" },
    ...d.models.map((m, i) => el("span", {}, el("i", { style: `background:${modelColor(i)}` }), el("b", {}, m.short), " ", m.note))));
  document.getElementById("betterRows").replaceChildren(...d.panels.map(p => {
    const base = p.models[d.models[0].key], trained = d.models.slice(1).map(m => p.models[m.key]).filter(x => x && x.plays.length);
    const last = trained.length ? trained[trained.length - 1] : null;
    const scores = d.models.map((m, i) => ({ m, i, s: (p.models[m.key] || {}).score })).filter(x => x.s !== null && x.s !== undefined);
    return el("div", { class: "card brow" },
      el("div", { class: "bh" },
        el("div", {}, el("h3", {}, p.label), el("div", { class: "pn" }, `${p.note} ${p.games.length} games × ${p.passes} repeats per model.`)),
        verdict(base, last)),
      el("div", { class: "bgrid" }, el("div", { class: "rchart" }, roundsChart(d, p)), gameRanges(d, p)),
      el("div", { class: "bfoot" }, "Mean Kaggle-style score per play (0–100, counts efficiency too): ",
        ...scores.map((x, k) => el("span", { class: "num", style: `color:${modelColor(x.i)}` }, (k ? "  →  " : "") + `${x.m.short} ${x.s.toFixed(1)}`))));
  }));
  const byg = {};
  d.panels.forEach(p => ((p.models[d.models[0].key] || { plays: [] }).plays).filter(q => !q.playing).forEach(q => (byg[q.game] = byg[q.game] || []).push(q.levels)));
  let w = null;
  Object.entries(byg).forEach(([g, lv]) => {
    if (lv.length < 3) return;
    const r = Math.max(...lv) - Math.min(...lv);
    if (!w || r > w[1]) w = [g, r, Math.min(...lv), Math.max(...lv), lv.length];
  });
  document.getElementById("betterNote").textContent = w && w[1] >= 2
    ? `Why so many runs: with the same model and the same no-border notebook, ${w[0]} ranged from ${w[2]} to ${w[3]} levels across ${w[4]} finished plays. One run of one game says little; totals over several runs do.`
    : "Why so many runs: one game can swing by several levels from one play to the next with the same model, so every model plays each game 5 or 6 times and the panel totals are compared.";
}

/* ------------------------------------------------------------------ every play, live */
function armLine(m, i, data, passes, games) {
  let text;
  if (!data || !data.runs.length) text = i === 0 ? "not started" : "starts once its weights are merged";
  else {
    const r = data.runs[0], started = data.plays.length, want = passes * games;
    text = r.state === "done" ? `done, ${started} of ${want} plays` :
      r.state === "playing" ? `playing since ${clock(r.ready)}: ${started}/${want} started, ${data.playing} still going` :
        `setting up (since ${clock(r.started)})`;
  }
  return el("div", { class: "arm" }, el("i", { style: `background:${modelColor(i)}` }), el("b", {}, m.short), el("span", {}, text));
}
function strip(d, p, g) {
  // one scale per panel, so a level cell is the same size on every row; levels past this game's last are blank
  const pmax = Math.max(...p.games.map(x => p.levels[x])), max = p.levels[g];
  const lanes = d.models.map((m, i) => ({ m, i, data: p.models[m.key] }));
  const cw = 26, gap = 3, W = (pmax + 1) * (cw + gap), lane = 24, H = lanes.length * lane + 18;
  const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, class: "strip" });
  for (let lv = 0; lv <= max; lv++) {
    const x0 = lv * (cw + gap);
    lanes.forEach((_, k) => svg.append(sv("rect", { x: x0, y: k * lane, width: cw, height: lane - 3, rx: 4, class: "cell" })));
    svg.append(sv("text", { x: x0 + cw / 2, y: H - 3, class: "lvl", "text-anchor": "middle" }, lv));
  }
  lanes.forEach(({ m, i, data }, k) => {
    if (!data) return;
    const y0 = k * lane, color = modelColor(i), by = {};
    data.plays.filter(x => x.game === g).forEach(x => (by[x.levels] = by[x.levels] || []).push(x));
    Object.entries(by).forEach(([lv, xs]) => xs.slice(0, 6).forEach((x, j) => {
      const cx = Number(lv) * (cw + gap) + 6 + (j % 3) * 7, cy = y0 + 6 + Math.floor(j / 3) * 9;
      svg.append(sv("circle", { cx, cy, r: 3, fill: x.playing ? "none" : color, stroke: color, "stroke-width": 1.4, class: x.playing ? "open" : "" },
        sv("title", {}, `${m.short}: level ${x.levels}, score ${x.score}${x.playing ? ", still playing" : ""}`)));
    }));
    const pm = data.per_game[g];
    if (pm && pm.mean !== null && pm.n) {
      const mx = pm.mean * (cw + gap) + cw / 2;
      svg.append(sv("line", { x1: mx, x2: mx, y1: y0 - 1, y2: y0 + lane - 2, stroke: color, "stroke-width": 2 }));
    }
  });
  return svg;
}
function renderPanels(d) {
  document.getElementById("panels").replaceChildren(...d.panels.map(p => el("div", { class: "pc" },
    el("h3", {}, p.label),
    el("div", { class: "pn" }, `${p.games.length} games × ${p.passes} repeats, one lane per model.`),
    ...d.models.map((m, i) => armLine(m, i, p.models[m.key], p.passes, p.games.length)),
    ...p.games.map(g => el("div", { class: "prow" }, el("span", { class: "pg" }, g), strip(d, p, g))),
    el("div", { class: "ptot" }, ...d.models.flatMap((m, i) => {
      const a = p.models[m.key];
      if (!a || !a.plays.length) return [];
      return [el("span", { class: "muted" }, `Panel total, ${m.short}` + (a.playing ? " (so far)" : "")),
        el("span", { class: "v", style: `color:${modelColor(i)}` }, `${a.total.toFixed(1)}${a.se !== null && !a.playing ? " ± " + a.se.toFixed(1) : ""}`)];
    })))));
}

/* ------------------------------------------------------------------ in-play test (plan C, 5-Oct) */
function pctOf(x) { return x === null || x === undefined ? "–" : Math.round(100 * x) + "%"; }
function renderInplay(d) {
  const box = document.getElementById("inplayRows");
  if (!box) return;
  const rows = d.inplay || [];
  if (!rows.length) { box.replaceChildren(el("div", { class: "note" }, "No model has played its test slice yet.")); return; }
  const idx = Object.fromEntries(d.models.map((m, i) => [m.key, i]));
  const label = k => (d.models.find(m => m.key === k) || { label: k }).label;
  const cell = g => g && g.tries ? el("td", { class: "num" }, `${g.cleared}/${g.tries} = ${pctOf(g.rate)}`,
    el("span", { class: "muted" }, `  base ${pctOf(g.base_rate)}`)) : el("td", { class: "muted" }, "–");
  const th = t => el("th", { style: "text-align:left;padding:6px 10px;font-weight:500" }, t);
  const table = el("table", { style: "width:100%;border-collapse:collapse" },
    el("thead", {}, el("tr", {}, th("Model"), th("Test tries finished"), th("Trained games, cleared at the hard level"),
      th("Never-trained games"))),
    el("tbody", {}, ...rows.map(r => {
      const i = idx[r.model] === undefined ? 0 : idx[r.model];
      const td = x => { x.style.padding = "6px 10px"; x.style.borderTop = "1px solid var(--line, rgba(0,0,0,.08))"; return x; };
      return el("tr", {},
        td(el("td", {}, el("b", { style: `color:${modelColor(i)}` }, label(r.model)))),
        td(el("td", { class: "num" }, String(r.tries))),
        td(cell((r.groups || {}).trained)), td(cell((r.groups || {}).never)));
    })));
  const per = rows.map(r => el("details", { style: "margin-top:6px" },
    el("summary", {}, `${label(r.model)}: per game`),
    el("div", { class: "pn" }, Object.entries(r.per_game || {}).sort().map(([g, x]) =>
      `${g} L${x.level} ${x.cleared}/${x.tries}` + (x.base && x.base[1] ? ` (base ${Math.round(100 * x.base[0] / x.base[1])}%)` : "") +
      (x.trained ? "" : " · never trained")).join("   ·   "))));
  box.replaceChildren(el("div", { class: "card" }, table), ...per);
}

/* ------------------------------------------------------------------ main */
// Son, 4-Oct-2026: training happens inside the hard games, so the hard panel and the train panel are one set; show
// them as a single panel and keep the held-out panel apart, as before. Games are joined, each model's runs and plays
// are joined, its level total is the sum of the panel totals and its error the root of the summed squares (the panels
// share no games). Claude Opus 5.5 for Bubba.
const MERGED_KEYS = ["train", "hard"];
function mergePanels(d) {
  if (!Array.isArray(d.panels)) return d;
  const ps = d.panels.filter(p => MERGED_KEYS.includes(p.key));
  if (ps.length < 2) return d;
  const keys = [...new Set(ps.flatMap(p => Object.keys(p.models || {})))];
  const models = {};
  for (const k of keys) {
    const parts = ps.map(p => p.models[k]).filter(Boolean);
    const done = parts.filter(a => a.plays && a.plays.length);
    const ses = done.map(a => a.se);
    const nGames = a => Object.keys(a.per_game || {}).length;
    // a panel's score is the mean over its games of each game's mean score, so the joined score weighs each panel
    // by its number of games
    const scored = done.filter(a => a.score !== null && a.score !== undefined && nGames(a));
    const gsum = scored.reduce((s, a) => s + nGames(a), 0);
    // a rep is one repeat of the whole panel (levels summed over its games); the panels repeat separately, so the
    // joined rep i is rep i of every panel added together, kept only while every panel has a rep i
    const nr = done.length ? Math.min(...done.map(a => (a.reps || []).length)) : 0;
    const reps = Array.from({ length: nr }, (_, i) => {
      const rs = done.map(a => a.reps[i]), g = rs.reduce((s, r) => s + (r.games || 0), 0);
      return { ...rs[0], levels: rs.reduce((s, r) => s + (r.levels || 0), 0), games: g,
        score: g ? rs.reduce((s, r) => s + (r.score || 0) * (r.games || 0), 0) / g : null,
        complete: rs.every(r => r.complete), playing: rs.some(r => r.playing) };
    });
    models[k] = {
      ...parts[0],
      per_game: Object.assign({}, ...parts.map(a => a.per_game || {})),
      reps,
      score: gsum ? scored.reduce((s, a) => s + a.score * nGames(a), 0) / gsum : null,
      runs: parts.flatMap(a => a.runs || []),
      plays: parts.flatMap(a => a.plays || []),
      playing: parts.reduce((s, a) => s + (a.playing || 0), 0),
      total: done.reduce((s, a) => s + (a.total || 0), 0),
      se: ses.length && ses.every(x => x !== null && x !== undefined) ? Math.sqrt(ses.reduce((s, x) => s + x * x, 0)) : null,
    };
  }
  const games = [...new Set(ps.flatMap(p => p.games || []))];
  const merged = { ...ps[0], key: "train_hard", label: "Train and hard games", note: "Training happens inside these games.",
    games, levels: Object.assign({}, ...ps.map(p => p.levels || {})), passes: Math.max(...ps.map(p => p.passes || 0)), models };
  // the merged panel takes the place of the first of the two; every other panel (held-out) stays where it was
  const out = [];
  d.panels.forEach(p => { if (!MERGED_KEYS.includes(p.key)) out.push(p); else if (!out.includes(merged)) out.push(merged); });
  return { ...d, panels: out };
}
function render(d) {
  d = mergePanels(d);
  DATA = d;
  document.getElementById("updated").textContent = "updated " + ago(d.updated);
  document.getElementById("footR").textContent = `Data ${new Date(d.updated).toLocaleString()} · refreshes every 5 min`;
  for (const [name, fn] of [["hero", renderHero], ["trends", renderTrends], ["better", renderBetter], ["inplay", renderInplay], ["loop", renderLoop], ["training", renderTraining], ["games", renderGames], ["panels", renderPanels]]) {
    try { fn(d); } catch (e) { console.error(name, e); }
  }
}
function notice(text) {
  const n = document.getElementById("notice");
  n.hidden = !text;
  n.textContent = text || "";
}
async function load() {
  try {
    // published every few minutes by the RL loop (gcp/controllers/rl/site/build_site.py on the RL branch); the
    // arc3-rl-live web.app copy of this page reads the same document as a static data.json beside it
    const webApp = /\.web\.app$/.test(location.hostname);
    const r = webApp ? await fetch("data.json?t=" + Date.now(), { cache: "no-store" })
      : await fetch("/api/v1/rl/dashboard", { cache: "no-store", credentials: "same-origin", redirect: "manual" });
    if (r.type === "opaqueredirect" || r.status === 0 || r.status === 401) { notice("Sign in with your team account to see the RL page."); return; }
    if (r.status === 403) { notice("This Google account is not on the team list."); return; }
    if (r.status === 404) { notice("Nothing has been published here yet."); return; }
    if (r.ok) { notice(""); render(await r.json()); }
  } catch (e) { console.error(e); }
}
// redraw in the other palette when the theme toggle flips
new MutationObserver(() => { if (DATA) render(DATA); })
  .observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
load();
setInterval(load, 60000);
setInterval(() => { if (DATA) document.getElementById("updated").textContent = "updated " + ago(DATA.updated); }, 20000);

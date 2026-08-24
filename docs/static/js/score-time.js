import { fetchRunsIndex, fetchRunScoreCurve } from "./api.js?v=postgres-catalog-v1";

const SVG_NS = "http://www.w3.org/2000/svg";
const state = { run: "", trace: null };
const el = {
  title: document.querySelector("#score-run"),
  runSelect: document.querySelector("#run-select"),
  stats: document.querySelector("#score-stats"),
  note: document.querySelector("#score-note"),
  chart: document.querySelector("#score-chart"),
  tooltip: document.querySelector("#score-tooltip"),
  count: document.querySelector("#completion-count"),
  body: document.querySelector("#completion-body"),
};

const hashRun = () => new URLSearchParams(location.hash.replace(/^#/, "")).get("run") || "";
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]);
const fmtScore = (value) => Number(value || 0).toFixed(3);
const fmtDuration = (seconds) => {
  const value = Number(seconds || 0);
  if (value >= 3600) return `${Math.floor(value / 3600)}h ${Math.round((value % 3600) / 60)}m`;
  return `${Math.floor(value / 60)}m ${Math.round(value % 60)}s`;
};
const fmtClock = (value) => new Intl.DateTimeFormat("en-GB", {timeZone:"UTC",hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:false}).format(new Date(value));
const svgNode = (tag, attrs = {}, text = "") => {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  if (text) node.textContent = text;
  return node;
};

function syncTabs() {
  const hash = location.hash;
  document.querySelector("#rt-viewer").href = `./viewer.html${hash}`;
  document.querySelector("#rt-trace").href = `./trace.html${hash}`;
  document.querySelector("#rt-score").href = `./score-time.html${hash}`;
}

async function populateRuns() {
  const index = await fetchRunsIndex();
  const rows = (index?.runs || []).filter((row) => row.has_execution_trace);
  const requested = hashRun();
  if (requested && !rows.some((row) => row.run === requested)) rows.unshift({run: requested});
  el.runSelect.innerHTML = rows.map((row) => `<option value="${esc(row.run)}">${esc(row.run)}</option>`).join("");
  el.runSelect.value = requested || rows[0]?.run || "";
}

function renderStats(curve) {
  const points = curve.points || [];
  const first = points.find((point) => Number(point.meanScore) > 0);
  const cards = [
    [fmtScore(curve.finalMeanScore), "final mean score"],
    [fmtDuration(state.trace.durationSeconds), "wall time"],
    [first ? fmtDuration(first.elapsedSeconds) : "—", "first score"],
    [Number(curve.completionEvents || 0).toLocaleString(), "scoring events"],
  ];
  el.stats.innerHTML = cards.map(([value, label]) => `<div class="stat"><b>${esc(value)}</b><span>${esc(label)}</span></div>`).join("");
}

function scoreAt(points, seconds) {
  let selected = points[0];
  for (const point of points) {
    if (Number(point.elapsedSeconds) > seconds) break;
    selected = point;
  }
  return selected;
}

function renderChart(curve) {
  const points = (curve.points || []).map((point) => ({...point, x:Number(point.elapsedSeconds || 0), y:Number(point.meanScore || 0)}));
  el.chart.innerHTML = "";
  if (points.length < 2) {
    el.chart.innerHTML = '<div class="score-empty">No timestamped score curve is available for this run.</div>';
    return;
  }
  const width = Math.max(340, el.chart.clientWidth || 900);
  const height = width < 620 ? 340 : 430;
  const margin = {top:22,right:24,bottom:54,left:64};
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;
  const xMax = Math.max(1, ...points.map((point) => point.x));
  const rawYMax = Math.max(1, ...points.map((point) => point.y));
  const yMax = Math.ceil(rawYMax * 1.15 * 2) / 2;
  const x = (value) => margin.left + Number(value) / xMax * innerW;
  const y = (value) => margin.top + innerH - Number(value) / yMax * innerH;
  const svg = svgNode("svg", {viewBox:`0 0 ${width} ${height}`,role:"img","aria-label":`Mean ARC3 score over runtime for ${state.run}`});
  svg.append(svgNode("title", {}, `Score over time — ${state.run}`));
  svg.append(svgNode("rect", {class:"score-frame",x:margin.left,y:margin.top,width:innerW,height:innerH,fill:"none"}));

  const yTicks = 5;
  for (let i = 0; i <= yTicks; i += 1) {
    const value = yMax * i / yTicks;
    const yy = y(value);
    svg.append(svgNode("line", {class:"score-grid",x1:margin.left,x2:margin.left+innerW,y1:yy,y2:yy}));
    svg.append(svgNode("text", {class:"score-axis-text",x:margin.left-9,y:yy+3,"text-anchor":"end"}, value.toFixed(1)));
  }
  const xTicks = width < 620 ? 4 : 7;
  for (let i = 0; i <= xTicks; i += 1) {
    const seconds = xMax * i / xTicks;
    const xx = x(seconds);
    svg.append(svgNode("line", {class:"score-grid",x1:xx,x2:xx,y1:margin.top,y2:margin.top+innerH}));
    svg.append(svgNode("text", {class:"score-axis-text",x:xx,y:margin.top+innerH+18,"text-anchor":i===0?"start":i===xTicks?"end":"middle"}, (seconds/60).toFixed(0)));
  }
  svg.append(svgNode("text", {class:"score-axis-title",x:margin.left+innerW/2,y:height-12,"text-anchor":"middle"}, "Elapsed runtime (minutes)"));
  svg.append(svgNode("text", {class:"score-axis-title",transform:`translate(16 ${margin.top+innerH/2}) rotate(-90)`,"text-anchor":"middle"}, "Mean score across games"));

  let path = `M ${x(points[0].x)} ${y(points[0].y)}`;
  for (let i = 1; i < points.length; i += 1) path += ` H ${x(points[i].x)} V ${y(points[i].y)}`;
  svg.append(svgNode("path", {class:"score-line",d:path}));
  for (const point of points.filter((point) => point.kind === "level_completion")) {
    const dot = svgNode("circle", {class:"score-dot",cx:x(point.x),cy:y(point.y),r:3.5});
    dot.addEventListener("pointerenter", () => showTooltip(point, x(point.x), y(point.y)));
    dot.addEventListener("pointerleave", hideTooltip);
    svg.append(dot);
  }

  const guide = svgNode("line", {class:"score-guide",x1:0,x2:0,y1:margin.top,y2:margin.top+innerH,visibility:"hidden"});
  const hoverDot = svgNode("circle", {class:"score-hover-dot",cx:0,cy:0,r:4,visibility:"hidden"});
  svg.append(guide, hoverDot);
  const overlay = svgNode("rect", {x:margin.left,y:margin.top,width:innerW,height:innerH,fill:"transparent"});
  overlay.addEventListener("pointermove", (event) => {
    const bounds = svg.getBoundingClientRect();
    const px = (event.clientX - bounds.left) * width / bounds.width;
    const seconds = Math.max(0, Math.min(xMax, (px - margin.left) / innerW * xMax));
    const point = scoreAt(points, seconds);
    const xx = x(seconds), yy = y(point.y);
    guide.setAttribute("x1", xx); guide.setAttribute("x2", xx); guide.setAttribute("visibility", "visible");
    hoverDot.setAttribute("cx", xx); hoverDot.setAttribute("cy", yy); hoverDot.setAttribute("visibility", "visible");
    showTooltip({...point, elapsedSeconds:seconds}, xx, yy);
  });
  overlay.addEventListener("pointerleave", () => { guide.setAttribute("visibility", "hidden"); hoverDot.setAttribute("visibility", "hidden"); hideTooltip(); });
  svg.append(overlay);
  el.chart.append(svg);
}

function showTooltip(point, x, y) {
  el.tooltip.innerHTML = `<b>${fmtScore(point.meanScore)} mean score</b><span>${fmtDuration(point.elapsedSeconds)} runtime${point.gameId ? ` · ${esc(point.gameId)} level ${point.level}` : ""}</span>`;
  el.tooltip.hidden = false;
  const panelWidth = el.chart.clientWidth;
  el.tooltip.style.left = `${Math.min(panelWidth - 300, Math.max(8, x + 12))}px`;
  el.tooltip.style.top = `${Math.max(52, y)}px`;
}
function hideTooltip() { el.tooltip.hidden = true; }

function renderCompletions(curve) {
  const rows = (curve.points || []).filter((point) => point.kind === "level_completion");
  el.count.textContent = `${rows.length} timestamped level completions${curve.untimedCompletions ? ` · ${curve.untimedCompletions} untimed` : ""}`;
  el.body.innerHTML = rows.map((point) => `<tr>
    <td>${esc(fmtDuration(point.elapsedSeconds))}</td><td>${esc(fmtClock(point.at))}</td><td>${esc(point.gameId)}</td>
    <td>${esc(point.level)}</td><td>${esc(point.action)}</td><td>${esc(fmtScore(point.meanScore))}</td><td>${esc(point.timestampBasis)}</td>
  </tr>`).join("");
}

async function load() {
  state.run = hashRun() || el.runSelect.value;
  if (!state.run) return;
  el.runSelect.value = state.run;
  syncTabs();
  el.title.textContent = `Score over time — ${state.run}`;
  try {
    state.trace = await fetchRunScoreCurve(state.run);
    const curve = state.trace.scoreCurve || {points:[]};
    el.note.textContent = curve.timestampNote || "";
    renderStats(curve);
    renderChart(curve);
    renderCompletions(curve);
  } catch (error) {
    el.chart.innerHTML = `<div class="score-empty">Unable to load score curve: ${esc(error.message)}</div>`;
  }
}

el.runSelect.addEventListener("change", () => { location.hash = `run=${encodeURIComponent(el.runSelect.value)}`; });
addEventListener("hashchange", load);
addEventListener("resize", () => state.trace?.scoreCurve && renderChart(state.trace.scoreCurve));
await populateRuns();
if (!hashRun() && el.runSelect.value) history.replaceState(null, "", `#run=${encodeURIComponent(el.runSelect.value)}`);
await load();

import { fetchRunsIndex, fetchRunTimeline } from "./api.js?v=score-compare-v2";

const SVG_NS = "http://www.w3.org/2000/svg";
const COLORS = ["#3b82f6", "#f59e0b", "#22c55e", "#a78bfa", "#ef4444", "#06b6d4", "#ec4899", "#eab308"];
const state = { rows: [], selected: new Set(), traces: new Map(), colors: new Map(), axis: "time" };
const el = {
  runList: document.querySelector("#run-list"),
  selectAll: document.querySelector("#select-all"),
  selectionCount: document.querySelector("#selection-count"),
  curveNote: document.querySelector("#curve-note"),
  axisDescription: document.querySelector("#axis-description"),
  axisButtons: [...document.querySelectorAll("[data-axis]")],
  chart: document.querySelector("#compare-chart"),
  tooltip: document.querySelector("#compare-tooltip"),
  summary: document.querySelector("#summary-body"),
  summaryFirstLabel: document.querySelector("#summary-first-label"),
};

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]);
const fmtScore = (value) => Number(value || 0).toFixed(3);
const fmtDuration = (seconds) => {
  const value = Number(seconds || 0);
  if (value >= 3600) return `${Math.floor(value / 3600)}h ${Math.round((value % 3600) / 60)}m`;
  return `${Math.floor(value / 60)}m ${Math.round(value % 60)}s`;
};
const svgNode = (tag, attrs = {}, text = "") => {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  if (text) node.textContent = text;
  return node;
};
const shortRun = (run) => {
  const match = String(run).match(/^(\d{8})_(\d{6})_(.+)$/);
  if (!match) return String(run);
  const label = match[3].replace(/^q38-taaf-cap8-/, "").replaceAll("-", " ").replace(/\bp(\d+)\b/g, "P$1");
  return `${label} · ${match[1].slice(4, 6)}/${match[1].slice(6, 8)}`;
};
const curveFor = (run) => state.traces.get(run)?.scoreCurve;
const selectedRows = () => state.rows.filter((row) => state.selected.has(row.run) && curveFor(row.run)?.points?.length > 1);
const hashParams = () => new URLSearchParams(location.hash.replace(/^#/, ""));
const axisSpec = () => state.axis === "actions"
  ? {key:"cumulativeActions", title:"Cumulative gameplay actions", tick:(value) => Math.round(value).toLocaleString(), hover:(value) => `${Math.round(value).toLocaleString()} actions`}
  : {key:"elapsedSeconds", title:"Elapsed runtime (minutes)", tick:(value) => (value / 60).toFixed(0), hover:(value) => `${fmtDuration(value)} elapsed`};

function requestedRuns() {
  const value = hashParams().get("runs") || "";
  return value.split(",").map(decodeURIComponent).filter(Boolean);
}

function requestedAxis() {
  return hashParams().get("axis") === "actions" ? "actions" : "time";
}

function updateHash() {
  const runs = state.rows.filter((row) => state.selected.has(row.run)).map((row) => encodeURIComponent(row.run));
  const params = new URLSearchParams();
  params.set("axis", state.axis);
  if (runs.length) params.set("runs", runs.join(","));
  history.replaceState(null, "", `#${params.toString().replaceAll("%2C", ",")}`);
}

function renderControls() {
  el.runList.innerHTML = state.rows.map((row) => {
    const color = state.colors.get(row.run);
    return `<label class="run-choice" style="--series-color:${color}" title="${esc(row.run)}">
      <input type="checkbox" value="${esc(row.run)}" ${state.selected.has(row.run) ? "checked" : ""}>
      <i class="series-swatch" aria-hidden="true"></i>
      <span><strong>${esc(shortRun(row.run))}</strong><small>${esc(row.run)} · final ${Number(row.avg_score || 0).toFixed(2)}</small></span>
    </label>`;
  }).join("");
  el.selectAll.textContent = state.selected.size === state.rows.length ? "Clear" : "Select all";
}

async function loadTrace(run) {
  if (state.traces.has(run)) return;
  state.traces.set(run, null);
  try {
    state.traces.set(run, await fetchRunTimeline(run, "score-compare-v1"));
  } catch (error) {
    state.traces.set(run, {error:error.message, scoreCurve:{points:[]}});
  }
}

function scoreAt(points, xValue) {
  let selected = points[0];
  for (const point of points) {
    if (Number(point.x) > xValue) break;
    selected = point;
  }
  return Number(selected?.meanScore || 0);
}

function firstScore(curve) {
  return (curve?.points || []).find((point) => Number(point.meanScore) > 0);
}

function renderSummary(rows) {
  const spec = axisSpec();
  el.summary.innerHTML = rows.map((row) => {
    const trace = state.traces.get(row.run);
    const curve = trace.scoreCurve;
    const first = firstScore(curve);
    return `<tr>
      <td><a class="summary-run" style="--series-color:${state.colors.get(row.run)}" href="./score-time.html#run=${encodeURIComponent(row.run)}"><i></i><span>${esc(row.run)}</span></a></td>
      <td>${esc(fmtScore(curve.finalMeanScore))}</td>
      <td>${esc(fmtDuration(trace.durationSeconds))}</td>
      <td>${Number(curve.finalActions ?? row.actions ?? 0).toLocaleString()}</td>
      <td>${first ? esc(spec.hover(Number(first[spec.key] || 0))) : "—"}</td>
      <td>${Number(curve.completionEvents || 0).toLocaleString()}</td>
    </tr>`;
  }).join("");
}

function renderChart(rows) {
  el.chart.innerHTML = "";
  el.tooltip.hidden = true;
  if (!rows.length) {
    el.chart.innerHTML = '<div class="compare-empty">Select at least one run with a timestamped score curve.</div>';
    return;
  }
  const spec = axisSpec();
  const series = rows.map((row) => ({
    ...row,
    color: state.colors.get(row.run),
    trace: state.traces.get(row.run),
    points: curveFor(row.run).points.map((point) => ({...point, x:Number(point[spec.key] || 0), y:Number(point.meanScore || 0)})),
  }));
  const width = Math.max(340, el.chart.clientWidth || 950);
  const height = width < 620 ? 360 : 510;
  const margin = {top:25, right:width < 620 ? 28 : 92, bottom:55, left:64};
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;
  const xMax = Math.max(1, ...series.flatMap((item) => item.points.map((point) => point.x)));
  const rawYMax = Math.max(1, ...series.flatMap((item) => item.points.map((point) => point.y)));
  const yMax = Math.ceil(rawYMax * 1.12 * 2) / 2;
  const x = (value) => margin.left + Number(value) / xMax * innerW;
  const y = (value) => margin.top + innerH - Number(value) / yMax * innerH;
  const svg = svgNode("svg", {viewBox:`0 0 ${width} ${height}`, role:"img", "aria-label":`Comparison of mean ARC3 score by ${state.axis === "actions" ? "gameplay actions" : "elapsed runtime"}`});
  svg.append(svgNode("title", {}, `Selected ARC3 runs — score by ${state.axis === "actions" ? "gameplay actions" : "elapsed runtime"}`));
  svg.append(svgNode("rect", {class:"chart-frame", x:margin.left, y:margin.top, width:innerW, height:innerH, fill:"none"}));

  const yTicks = 5;
  for (let i = 0; i <= yTicks; i += 1) {
    const value = yMax * i / yTicks;
    const yy = y(value);
    svg.append(svgNode("line", {class:"chart-grid", x1:margin.left, x2:margin.left+innerW, y1:yy, y2:yy}));
    svg.append(svgNode("text", {class:"chart-axis-text", x:margin.left-9, y:yy+3, "text-anchor":"end"}, value.toFixed(1)));
  }
  const xTicks = width < 620 ? 4 : 7;
  for (let i = 0; i <= xTicks; i += 1) {
    const xValue = xMax * i / xTicks;
    const xx = x(xValue);
    svg.append(svgNode("line", {class:"chart-grid", x1:xx, x2:xx, y1:margin.top, y2:margin.top+innerH}));
    svg.append(svgNode("text", {class:"chart-axis-text", x:xx, y:margin.top+innerH+18, "text-anchor":i===0?"start":i===xTicks?"end":"middle"}, spec.tick(xValue)));
  }
  svg.append(svgNode("text", {class:"chart-axis-title", x:margin.left+innerW/2, y:height-12, "text-anchor":"middle"}, spec.title));
  svg.append(svgNode("text", {class:"chart-axis-title", transform:`translate(16 ${margin.top+innerH/2}) rotate(-90)`, "text-anchor":"middle"}, "Mean score across games"));

  for (const item of series) {
    let path = `M ${x(item.points[0].x)} ${y(item.points[0].y)}`;
    for (let i = 1; i < item.points.length; i += 1) path += ` H ${x(item.points[i].x)} V ${y(item.points[i].y)}`;
    svg.append(svgNode("path", {class:"compare-line", d:path, stroke:item.color}));
    const final = item.points[item.points.length - 1];
    svg.append(svgNode("circle", {class:"compare-endpoint", cx:x(final.x), cy:y(final.y), r:4, fill:item.color}));
    if (width >= 620) svg.append(svgNode("text", {class:"compare-end-label", x:x(final.x)+8, y:y(final.y)+3, fill:item.color}, fmtScore(final.y)));
  }

  const guide = svgNode("line", {class:"cursor-guide", x1:0, x2:0, y1:margin.top, y2:margin.top+innerH, visibility:"hidden"});
  svg.append(guide);
  const dots = series.map((item) => {
    const dot = svgNode("circle", {class:"cursor-dot", cx:0, cy:0, r:4, fill:item.color, visibility:"hidden"});
    svg.append(dot);
    return dot;
  });
  const overlay = svgNode("rect", {x:margin.left, y:margin.top, width:innerW, height:innerH, fill:"transparent"});
  overlay.addEventListener("pointermove", (event) => {
    const bounds = svg.getBoundingClientRect();
    const px = (event.clientX - bounds.left) * width / bounds.width;
    const xValue = Math.max(0, Math.min(xMax, (px - margin.left) / innerW * xMax));
    const xx = x(xValue);
    guide.setAttribute("x1", xx); guide.setAttribute("x2", xx); guide.setAttribute("visibility", "visible");
    const values = series.map((item, index) => {
      const score = scoreAt(item.points, xValue);
      dots[index].setAttribute("cx", xx); dots[index].setAttribute("cy", y(score)); dots[index].setAttribute("visibility", "visible");
      return {item, score};
    });
    el.tooltip.innerHTML = `<span class="tooltip-time">${esc(spec.hover(xValue))}</span>${values.map(({item, score}) => `<div class="tooltip-row" style="--series-color:${item.color}"><i></i><span>${esc(shortRun(item.run))}</span><b>${esc(fmtScore(score))}</b></div>`).join("")}`;
    el.tooltip.hidden = false;
    const displayX = xx / width * el.chart.clientWidth;
    el.tooltip.style.left = `${Math.max(10, Math.min(el.chart.clientWidth - 345, displayX + 14))}px`;
    el.tooltip.style.top = "74px";
  });
  overlay.addEventListener("pointerleave", () => {
    guide.setAttribute("visibility", "hidden");
    dots.forEach((dot) => dot.setAttribute("visibility", "hidden"));
    el.tooltip.hidden = true;
  });
  svg.append(overlay);
  el.chart.append(svg);
}

function render() {
  const rows = selectedRows();
  el.selectionCount.textContent = `${rows.length} of ${state.rows.length} runs selected`;
  el.axisButtons.forEach((button) => {
    const active = button.dataset.axis === state.axis;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  el.axisDescription.textContent = state.axis === "actions" ? "Cumulative environment actions" : "Elapsed runtime · minutes";
  el.summaryFirstLabel.textContent = state.axis === "actions" ? "First score at action" : "First score at time";
  if (state.axis === "actions") {
    const timed = rows.reduce((sum, row) => sum + Number(curveFor(row.run)?.timedActions || 0), 0);
    const total = rows.reduce((sum, row) => sum + Number(curveFor(row.run)?.finalActions || 0), 0);
    el.curveNote.textContent = total ? `${timed.toLocaleString()} of ${total.toLocaleString()} actions aligned to generating calls.` : "Actions are aligned to their generating model calls.";
  } else {
    const notes = new Set(rows.map((row) => curveFor(row.run)?.timestampNote).filter(Boolean));
    el.curveNote.textContent = notes.size === 1 ? [...notes][0] : "Shared runtime axis; reconstructed and exact timestamps may coexist.";
  }
  renderChart(rows);
  renderSummary(rows);
  renderControls();
}

async function changeSelection(run, checked) {
  if (checked) {
    state.selected.add(run);
    await loadTrace(run);
  } else {
    state.selected.delete(run);
  }
  updateHash();
  render();
}

el.runList.addEventListener("change", (event) => {
  if (event.target.matches('input[type="checkbox"]')) changeSelection(event.target.value, event.target.checked);
});
el.selectAll.addEventListener("click", async () => {
  if (state.selected.size === state.rows.length) {
    state.selected.clear();
  } else {
    state.rows.forEach((row) => state.selected.add(row.run));
    await Promise.all(state.rows.map((row) => loadTrace(row.run)));
  }
  updateHash();
  render();
});
el.axisButtons.forEach((button) => button.addEventListener("click", () => {
  state.axis = button.dataset.axis === "actions" ? "actions" : "time";
  updateHash();
  render();
}));
addEventListener("resize", () => renderChart(selectedRows()));

async function init() {
  state.axis = requestedAxis();
  const index = await fetchRunsIndex();
  state.rows = (index?.runs || []).filter((row) => row.has_execution_trace).sort((a, b) => b.run.localeCompare(a.run));
  state.rows.forEach((row, indexValue) => state.colors.set(row.run, COLORS[indexValue % COLORS.length]));
  const requested = requestedRuns().filter((run) => state.rows.some((row) => row.run === run));
  const defaults = requested.length ? requested : state.rows.map((row) => row.run);
  defaults.forEach((run) => state.selected.add(run));
  renderControls();
  await Promise.all(defaults.map(loadTrace));
  if (!requested.length) updateHash();
  render();
}

init().catch((error) => {
  el.chart.innerHTML = `<div class="compare-empty">Unable to load score comparisons: ${esc(error.message)}</div>`;
});

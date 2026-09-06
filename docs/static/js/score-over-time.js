import { fetchRunsIndex, fetchRunScoreCurve } from "./api.js?v=postgres-catalog-v1";

const SVG_NS = "http://www.w3.org/2000/svg";
const COLORS = ["#3b82f6", "#f59e0b", "#22c55e", "#a78bfa", "#ef4444", "#06b6d4", "#ec4899", "#eab308"];
const state = { rows: [], selected: new Set(), traces: new Map(), colors: new Map(), axis: "time", paceMetric: "rate", lockedRun: null };
const el = {
  runList: document.querySelector("#run-list"),
  selectAll: document.querySelector("#select-all"),
  selectionCount: document.querySelector("#selection-count"),
  curveNote: document.querySelector("#curve-note"),
  axisDescription: document.querySelector("#axis-description"),
  axisButtons: [...document.querySelectorAll("[data-axis]")],
  chart: document.querySelector("#compare-chart"),
  tooltip: document.querySelector("#compare-tooltip"),
  paceChart: document.querySelector("#pace-chart"),
  paceTooltip: document.querySelector("#pace-tooltip"),
  paceDescription: document.querySelector("#pace-description"),
  paceNote: document.querySelector("#pace-note"),
  paceButtons: [...document.querySelectorAll("[data-pace-metric]")],
  summary: document.querySelector("#summary-body"),
  summaryFirstLabel: document.querySelector("#summary-first-label"),
};

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]);
const fmtScore = (value) => Number(value || 0).toFixed(3);
const fmtTokens = (value) => {
  const amount = Number(value || 0);
  if (amount >= 1_000_000) return `${(amount / 1_000_000).toFixed(amount >= 10_000_000 ? 0 : 1)}M`;
  if (amount >= 1_000) return `${(amount / 1_000).toFixed(amount >= 100_000 ? 0 : 1)}k`;
  return Math.round(amount).toLocaleString();
};
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
const axisSpec = () => {
  if (state.axis === "actions") return {key:"cumulativeActions", title:"Cumulative gameplay actions", aria:"gameplay actions", tick:(value) => Math.round(value).toLocaleString(), hover:(value) => `${Math.round(value).toLocaleString()} actions`};
  if (state.axis === "tokens") return {key:"cumulativeGeneratedTokens", title:"Cumulative generated tokens", aria:"generated tokens", tick:fmtTokens, hover:(value) => `${Math.round(value).toLocaleString()} generated tokens`};
  return {key:"elapsedSeconds", title:"Elapsed runtime (minutes)", aria:"elapsed runtime", tick:(value) => (value / 60).toFixed(0), hover:(value) => `${fmtDuration(value)} elapsed`};
};

function requestedRuns() {
  const value = hashParams().get("runs") || "";
  return value.split(",").map(decodeURIComponent).filter(Boolean);
}

function requestedAxis() {
  const axis = hashParams().get("axis");
  return ["time", "actions", "tokens"].includes(axis) ? axis : "time";
}

function requestedPaceMetric() {
  return hashParams().get("pace") === "cumulative" ? "cumulative" : "rate";
}

function updateHash() {
  const runs = state.rows.filter((row) => state.selected.has(row.run)).map((row) => encodeURIComponent(row.run));
  const params = new URLSearchParams();
  params.set("axis", state.axis);
  params.set("pace", state.paceMetric);
  if (runs.length) params.set("runs", runs.join(","));
  history.replaceState(null, "", `#${params.toString().replaceAll("%2C", ",")}`);
}

function actionPointsFor(curve) {
  if (curve?.actionPoints?.length > 1) {
    return curve.actionPoints.map((point) => ({
      ...point,
      elapsedSeconds: Number(point.elapsedSeconds || 0),
      cumulativeActions: Number(point.cumulativeActions || 0),
      actionsPerMinute: Number(point.actionsPerMinute || 0),
      exact: true,
    }));
  }
  const points = (curve?.points || []).map((point) => ({
    elapsedSeconds: Number(point.elapsedSeconds || 0),
    cumulativeActions: Number(point.cumulativeActions || 0),
  })).sort((a, b) => a.elapsedSeconds - b.elapsedSeconds);
  return points.map((point, index) => {
    const prior = points[Math.max(0, index - 1)];
    const elapsedMinutes = (point.elapsedSeconds - prior.elapsedSeconds) / 60;
    return {
      ...point,
      actionsPerMinute: elapsedMinutes > 0 ? (point.cumulativeActions - prior.cumulativeActions) / elapsedMinutes : 0,
      exact: false,
    };
  });
}

function actionPaceSummary(curve) {
  if (!curve?.actionPoints?.length) return null;
  const points = actionPointsFor(curve);
  const first = points.find((point) => point.elapsedSeconds >= 600) || points.at(-1);
  const last = points.at(-1);
  return {first:Number(first.actionsPerMinute || 0), last:Number(last.actionsPerMinute || 0)};
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
    state.traces.set(run, await fetchRunScoreCurve(run));
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

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function distributionMarkup(scores, selectedScore, color) {
  if (!scores.length) return "";
  const observedMin = Math.min(...scores);
  const observedMax = Math.max(...scores);
  const padding = observedMin === observedMax ? Math.max(.25, Math.abs(observedMin) * .08) : 0;
  const domainMin = Math.max(0, observedMin - padding);
  const domainMax = Math.max(domainMin + .001, observedMax + padding);
  const binsCount = Math.min(18, Math.max(6, Math.ceil(Math.sqrt(scores.length) * 2)));
  const bins = Array.from({length:binsCount}, () => 0);
  for (const score of scores) {
    const ratio = (score - domainMin) / (domainMax - domainMin);
    bins[Math.max(0, Math.min(bins.length - 1, Math.floor(ratio * bins.length)))] += 1;
  }
  const smooth = bins.map((count, index) => (
    (bins[index - 1] || 0) + count * 2 + (bins[index + 1] || 0)
  ) / 4);
  const peak = Math.max(1, ...smooth);
  const width = 286, plotTop = 5, plotBottom = 36, left = 5, right = 281;
  const x = (value) => left + (value - domainMin) / (domainMax - domainMin) * (right - left);
  const points = smooth.map((count, index) => {
    const xx = left + (index + .5) / binsCount * (right - left);
    const yy = plotBottom - count / peak * (plotBottom - plotTop);
    return [xx, yy];
  });
  const line = points.map(([xx, yy], index) => `${index ? "L" : "M"} ${xx.toFixed(1)} ${yy.toFixed(1)}`).join(" ");
  const area = `${line} L ${points.at(-1)[0].toFixed(1)} ${plotBottom} L ${points[0][0].toFixed(1)} ${plotBottom} Z`;
  const markerX = x(Math.max(domainMin, Math.min(domainMax, selectedScore))).toFixed(1);
  const rugs = scores.map((score) => `<line class="tooltip-dist-rug" x1="${x(score).toFixed(1)}" x2="${x(score).toFixed(1)}" y1="37" y2="41"></line>`).join("");
  return `<svg class="tooltip-distribution" viewBox="0 0 ${width} 55" role="img" aria-label="Distribution of current scores from ${fmtScore(observedMin)} to ${fmtScore(observedMax)}">
    <path class="tooltip-dist-area" d="${area}"></path>
    <path class="tooltip-dist-line" d="${line}"></path>
    ${rugs}
    <line class="tooltip-dist-marker" style="--series-color:${color}" x1="${markerX}" x2="${markerX}" y1="3" y2="42"></line>
    <circle class="tooltip-dist-marker-dot" style="--series-color:${color}" cx="${markerX}" cy="4" r="2.7"></circle>
    <text x="5" y="53">${fmtScore(observedMin)}</text>
    <text x="281" y="53" text-anchor="end">${fmtScore(observedMax)}</text>
  </svg>`;
}

function firstScore(curve) {
  const points = state.axis === "tokens" ? (curve?.tokenPoints || curve?.points || []) : (curve?.points || []);
  return points.find((point) => Number(point.meanScore) > 0);
}

function renderSummary(rows) {
  const spec = axisSpec();
  el.summary.innerHTML = rows.map((row) => {
    const trace = state.traces.get(row.run);
    const curve = trace.scoreCurve;
    const first = firstScore(curve);
    const pace = actionPaceSummary(curve);
    return `<tr>
      <td><a class="summary-run" style="--series-color:${state.colors.get(row.run)}" href="./score-time.html#run=${encodeURIComponent(row.run)}"><i></i><span>${esc(row.run)}</span></a></td>
      <td>${esc(fmtScore(curve.finalMeanScore))}</td>
      <td>${esc(fmtDuration(trace.durationSeconds))}</td>
      <td>${Number(curve.finalActions ?? row.actions ?? 0).toLocaleString()}</td>
      <td>${pace ? `${pace.first.toFixed(1)} → ${pace.last.toFixed(1)}/min` : "—"}</td>
      <td>${Number(curve.finalGeneratedTokens ?? row.tokens ?? 0).toLocaleString()}</td>
      <td>${first ? esc(spec.hover(Number(first[spec.key] || 0))) : "—"}</td>
      <td>${Number(curve.completionEvents || 0).toLocaleString()}</td>
    </tr>`;
  }).join("");
}

function renderPaceChart(rows) {
  el.paceChart.innerHTML = "";
  el.paceTooltip.hidden = true;
  const metric = state.paceMetric === "cumulative" ? "cumulativeActions" : "actionsPerMinute";
  const series = rows.map((row) => ({
    ...row,
    color: state.colors.get(row.run),
    points: actionPointsFor(curveFor(row.run)),
  })).filter((item) => item.points.length > 1);
  if (!series.length) {
    el.paceChart.innerHTML = '<div class="compare-empty">No timestamped action data is available for the selected runs.</div>';
    return;
  }

  const width = Math.max(340, el.paceChart.clientWidth || 1100);
  const height = width < 620 ? 300 : 350;
  const margin = {top:22, right:width < 620 ? 24 : 92, bottom:50, left:64};
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;
  const xMax = Math.max(1, ...series.flatMap((item) => item.points.map((point) => point.elapsedSeconds)));
  const rawYMax = Math.max(1, ...series.flatMap((item) => item.points.map((point) => Number(point[metric] || 0))));
  const yMax = state.paceMetric === "cumulative" ? Math.ceil(rawYMax / 250) * 250 : Math.ceil(rawYMax * 1.12 / 5) * 5;
  const x = (value) => margin.left + Number(value) / xMax * innerW;
  const y = (value) => margin.top + innerH - Number(value) / yMax * innerH;
  const svg = svgNode("svg", {viewBox:`0 0 ${width} ${height}`, role:"img", "aria-label":state.paceMetric === "cumulative" ? "Cumulative gameplay actions over elapsed runtime" : "Trailing ten-minute gameplay actions per minute over elapsed runtime"});
  svg.append(svgNode("title", {}, state.paceMetric === "cumulative" ? "Cumulative actions over time" : "Action throughput over time"));
  svg.append(svgNode("rect", {class:"chart-frame", x:margin.left, y:margin.top, width:innerW, height:innerH, fill:"none"}));

  for (let i = 0; i <= 5; i += 1) {
    const value = yMax * i / 5;
    const yy = y(value);
    svg.append(svgNode("line", {class:"chart-grid", x1:margin.left, x2:margin.left+innerW, y1:yy, y2:yy}));
    const label = state.paceMetric === "cumulative" ? Math.round(value).toLocaleString() : value.toFixed(1);
    svg.append(svgNode("text", {class:"chart-axis-text", x:margin.left-9, y:yy+3, "text-anchor":"end"}, label));
  }
  const xTicks = width < 620 ? 4 : 7;
  for (let i = 0; i <= xTicks; i += 1) {
    const value = xMax * i / xTicks;
    const xx = x(value);
    svg.append(svgNode("line", {class:"chart-grid", x1:xx, x2:xx, y1:margin.top, y2:margin.top+innerH}));
    svg.append(svgNode("text", {class:"chart-axis-text", x:xx, y:margin.top+innerH+18, "text-anchor":i===0?"start":i===xTicks?"end":"middle"}, (value / 60).toFixed(0)));
  }
  svg.append(svgNode("text", {class:"chart-axis-title", x:margin.left+innerW/2, y:height-11, "text-anchor":"middle"}, "Elapsed runtime (minutes)"));
  svg.append(svgNode("text", {class:"chart-axis-title", transform:`translate(16 ${margin.top+innerH/2}) rotate(-90)`, "text-anchor":"middle"}, state.paceMetric === "cumulative" ? "Cumulative actions" : "Actions per minute"));

  for (const item of series) {
    const path = item.points.map((point, index) => `${index ? "L" : "M"} ${x(point.elapsedSeconds).toFixed(1)} ${y(point[metric]).toFixed(1)}`).join(" ");
    svg.append(svgNode("path", {class:"compare-line", d:path, stroke:item.color}));
    const final = item.points.at(-1);
    svg.append(svgNode("circle", {class:"compare-endpoint", cx:x(final.elapsedSeconds), cy:y(final[metric]), r:4, fill:item.color}));
    if (width >= 620) {
      const label = state.paceMetric === "cumulative" ? Math.round(final[metric]).toLocaleString() : `${Number(final[metric]).toFixed(1)}/m`;
      svg.append(svgNode("text", {class:"compare-end-label", x:x(final.elapsedSeconds)+8, y:y(final[metric])+3, fill:item.color}, label));
    }
  }

  const guide = svgNode("line", {class:"cursor-guide", x1:0, x2:0, y1:margin.top, y2:margin.top+innerH, visibility:"hidden"});
  svg.append(guide);
  const overlay = svgNode("rect", {class:"chart-overlay", x:margin.left, y:margin.top, width:innerW, height:innerH, fill:"transparent", tabindex:0, role:"application", "aria-label":"Interactive action pace chart"});
  const inspect = (event) => {
    const bounds = svg.getBoundingClientRect();
    const px = (event.clientX - bounds.left) * width / bounds.width;
    const seconds = Math.max(0, Math.min(xMax, (px - margin.left) / innerW * xMax));
    const xx = x(seconds);
    guide.setAttribute("x1", xx); guide.setAttribute("x2", xx); guide.setAttribute("visibility", "visible");
    const values = series.map((item) => {
      const point = item.points.reduce((best, candidate) => Math.abs(candidate.elapsedSeconds - seconds) < Math.abs(best.elapsedSeconds - seconds) ? candidate : best, item.points[0]);
      return {item, point, value:Number(point[metric] || 0)};
    });
    el.paceTooltip.innerHTML = `<span class="tooltip-time"><span>${fmtDuration(seconds)} elapsed</span><em>one-minute samples</em></span>${values.map(({item, value}) => `<div class="tooltip-row" style="--series-color:${item.color}"><i></i><span>${esc(shortRun(item.run))}</span><b>${state.paceMetric === "cumulative" ? Math.round(value).toLocaleString() : `${value.toFixed(1)}/min`}</b></div>`).join("")}`;
    el.paceTooltip.hidden = false;
    const displayX = xx / width * el.paceChart.clientWidth;
    const tooltipWidth = Math.min(330, el.paceChart.clientWidth - 24);
    el.paceTooltip.style.left = `${Math.max(10, displayX + 14 + tooltipWidth <= el.paceChart.clientWidth - 10 ? displayX + 14 : displayX - tooltipWidth - 14)}px`;
    el.paceTooltip.style.top = "58px";
  };
  overlay.addEventListener("pointermove", inspect);
  overlay.addEventListener("pointerleave", () => { guide.setAttribute("visibility", "hidden"); el.paceTooltip.hidden = true; });
  svg.append(overlay);
  el.paceChart.append(svg);
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
    points: (state.axis === "tokens" ? (curveFor(row.run).tokenPoints || curveFor(row.run).points) : curveFor(row.run).points)
      .map((point) => ({...point, x:Number(point[spec.key] || 0), y:Number(point.meanScore || 0)})),
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
  const svg = svgNode("svg", {viewBox:`0 0 ${width} ${height}`, role:"img", "aria-label":`Comparison of mean ARC3 score by ${spec.aria}`});
  svg.append(svgNode("title", {}, `Selected ARC3 runs — score by ${spec.aria}`));
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

  const paths = [];
  const endpoints = [];
  const endLabels = [];
  for (const item of series) {
    let path = `M ${x(item.points[0].x)} ${y(item.points[0].y)}`;
    for (let i = 1; i < item.points.length; i += 1) path += ` H ${x(item.points[i].x)} V ${y(item.points[i].y)}`;
    const pathNode = svgNode("path", {class:"compare-line", d:path, stroke:item.color});
    svg.append(pathNode);
    paths.push(pathNode);
    const final = item.points[item.points.length - 1];
    const endpoint = svgNode("circle", {class:"compare-endpoint", cx:x(final.x), cy:y(final.y), r:4, fill:item.color});
    svg.append(endpoint);
    endpoints.push(endpoint);
    if (width >= 620) {
      const label = svgNode("text", {class:"compare-end-label", x:x(final.x)+8, y:y(final.y)+3, fill:item.color}, fmtScore(final.y));
      svg.append(label);
      endLabels.push(label);
    } else {
      endLabels.push(null);
    }
  }

  const guide = svgNode("line", {class:"cursor-guide", x1:0, x2:0, y1:margin.top, y2:margin.top+innerH, visibility:"hidden"});
  svg.append(guide);
  const dots = series.map((item) => {
    const dot = svgNode("circle", {class:"cursor-dot", cx:0, cy:0, r:4, fill:item.color, visibility:"hidden"});
    svg.append(dot);
    return dot;
  });
  const overlay = svgNode("rect", {
    class:"chart-overlay",
    x:margin.left,
    y:margin.top,
    width:innerW,
    height:innerH,
    fill:"transparent",
    tabindex:0,
    role:"application",
    "aria-label":"Interactive score chart. Hover to inspect a run, click to lock it, and press Escape to unlock."
  });
  const pointerState = (event) => {
    const bounds = svg.getBoundingClientRect();
    const px = (event.clientX - bounds.left) * width / bounds.width;
    const py = (event.clientY - bounds.top) * height / bounds.height;
    const xValue = Math.max(0, Math.min(xMax, (px - margin.left) / innerW * xMax));
    const xx = x(xValue);
    const values = series.map((item, index) => {
      const score = scoreAt(item.points, xValue);
      return {item, index, score, distance:Math.abs(y(score) - py)};
    });
    const nearest = values.reduce((best, value) => !best || value.distance < best.distance ? value : best, null);
    return {xValue, xx, values, nearest};
  };
  const focusSeries = (index, locked = false) => {
    paths.forEach((path, pathIndex) => {
      path.classList.toggle("is-hovered", pathIndex === index);
      path.classList.toggle("is-locked", locked && pathIndex === index);
      path.classList.toggle("is-muted", pathIndex !== index);
    });
    svg.insertBefore(paths[index], guide);
    endpoints.forEach((endpoint, endpointIndex) => endpoint.classList.toggle("is-muted", endpointIndex !== index));
    endLabels.forEach((label, labelIndex) => label?.classList.toggle("is-muted", labelIndex !== index));
  };
  const clearInspection = () => {
    guide.setAttribute("visibility", "hidden");
    dots.forEach((dot) => dot.setAttribute("visibility", "hidden"));
    paths.forEach((path) => path.classList.remove("is-hovered", "is-locked", "is-muted"));
    endpoints.forEach((endpoint) => endpoint.classList.remove("is-muted"));
    endLabels.forEach((label) => label?.classList.remove("is-muted"));
    el.tooltip.hidden = true;
  };
  const inspect = ({xValue, xx, values, nearest}) => {
    const lockedIndex = state.lockedRun ? series.findIndex((item) => item.run === state.lockedRun) : -1;
    const closest = lockedIndex >= 0 ? values[lockedIndex] : nearest;
    const locked = lockedIndex >= 0;
    guide.setAttribute("x1", xx); guide.setAttribute("x2", xx); guide.setAttribute("visibility", "visible");
    const allScores = values.map((value) => value.score);
    const rangeMin = Math.min(...allScores);
    const rangeMax = Math.max(...allScores);
    const runScores = closest.item.points.map((point) => point.y);
    const runMin = Math.min(...runScores);
    const runMax = Math.max(...runScores);
    focusSeries(closest.index, locked);
    dots.forEach((dot, index) => {
      dot.setAttribute("cx", xx);
      dot.setAttribute("cy", y(values[index].score));
      dot.setAttribute("visibility", index === closest.index ? "visible" : "hidden");
    });
    el.tooltip.innerHTML = `<span class="tooltip-time"><span>${esc(spec.hover(xValue))}</span><em class="${locked ? "is-locked" : ""}">${locked ? "Locked · click to release" : "Click to lock"}</em></span>
      <div class="tooltip-focus" style="--series-color:${closest.item.color}">
        <i></i><span><strong>${esc(shortRun(closest.item.run))}</strong><small>${esc(closest.item.run)}</small></span><b>${esc(fmtScore(closest.score))}</b>
      </div>
      <div class="tooltip-range"><span>This run</span><b>${fmtScore(runMin)}–${fmtScore(runMax)}</b></div>
      <div class="tooltip-range"><span>All runs now · median ${fmtScore(median(allScores))}</span><b>${fmtScore(rangeMin)}–${fmtScore(rangeMax)}</b></div>
      ${distributionMarkup(allScores, closest.score, closest.item.color)}`;
    el.tooltip.hidden = false;
    const displayX = xx / width * el.chart.clientWidth;
    const tooltipWidth = Math.min(330, el.chart.clientWidth - 24);
    const rightX = displayX + 14;
    const leftX = displayX - tooltipWidth - 14;
    el.tooltip.style.left = `${Math.max(10, rightX + tooltipWidth <= el.chart.clientWidth - 10 ? rightX : leftX)}px`;
    el.tooltip.style.top = "64px";
  };
  overlay.addEventListener("pointermove", (event) => {
    inspect(pointerState(event));
  });
  overlay.addEventListener("click", (event) => {
    const pointer = pointerState(event);
    state.lockedRun = state.lockedRun === pointer.nearest.item.run ? null : pointer.nearest.item.run;
    inspect(pointer);
    overlay.focus({preventScroll:true});
  });
  overlay.addEventListener("pointerleave", () => {
    if (!state.lockedRun) clearInspection();
  });
  overlay.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !state.lockedRun) return;
    state.lockedRun = null;
    clearInspection();
    event.preventDefault();
  });
  svg.append(overlay);
  const initialLockedIndex = state.lockedRun ? series.findIndex((item) => item.run === state.lockedRun) : -1;
  if (initialLockedIndex >= 0) focusSeries(initialLockedIndex, true);
  else if (state.lockedRun) state.lockedRun = null;
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
  el.paceButtons.forEach((button) => {
    const active = button.dataset.paceMetric === state.paceMetric;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  el.axisDescription.textContent = state.axis === "actions" ? "Cumulative environment actions" : state.axis === "tokens" ? "Cumulative generated tokens" : "Elapsed runtime · minutes";
  el.summaryFirstLabel.textContent = state.axis === "actions" ? "First score at action" : state.axis === "tokens" ? "First score at token" : "First score at time";
  if (state.axis === "actions") {
    const timed = rows.reduce((sum, row) => sum + Number(curveFor(row.run)?.timedActions || 0), 0);
    const total = rows.reduce((sum, row) => sum + Number(curveFor(row.run)?.finalActions || 0), 0);
    el.curveNote.textContent = total ? `${timed.toLocaleString()} of ${total.toLocaleString()} actions aligned to generating calls.` : "Actions are aligned to their generating model calls.";
  } else if (state.axis === "tokens") {
    const notes = new Set(rows.map((row) => curveFor(row.run)?.tokenNote).filter(Boolean));
    el.curveNote.textContent = notes.size === 1 ? [...notes][0] : "Generated-token progress from exact benchmark call accounting.";
  } else {
    const notes = new Set(rows.map((row) => curveFor(row.run)?.timestampNote).filter(Boolean));
    el.curveNote.textContent = notes.size === 1 ? [...notes][0] : "Shared runtime axis; reconstructed and exact timestamps may coexist.";
  }
  const exactPaceCurves = rows.filter((row) => curveFor(row.run)?.actionPoints?.length > 1).length;
  el.paceDescription.textContent = state.paceMetric === "cumulative" ? "Cumulative environment actions" : "Trailing 10-minute actions per minute";
  el.paceNote.textContent = rows.length && exactPaceCurves === rows.length
    ? "One-minute samples from every timestamped environment action."
    : `${exactPaceCurves} of ${rows.length} selected runs have minute-level action samples; older curves use sparse reconstruction.`;
  renderChart(rows);
  renderPaceChart(rows);
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
  state.axis = ["time", "actions", "tokens"].includes(button.dataset.axis) ? button.dataset.axis : "time";
  updateHash();
  render();
}));
el.paceButtons.forEach((button) => button.addEventListener("click", () => {
  state.paceMetric = button.dataset.paceMetric === "cumulative" ? "cumulative" : "rate";
  updateHash();
  render();
}));
addEventListener("resize", () => { renderChart(selectedRows()); renderPaceChart(selectedRows()); });

async function init() {
  state.axis = requestedAxis();
  state.paceMetric = requestedPaceMetric();
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

import { fetchGameStep, fetchRunsIndex, fetchRunTimeline } from "./api.js";

const SVG_NS = "http://www.w3.org/2000/svg";
const KIND_LABEL = {
  main_call: "Main model",
  sidecar_observer: "Observer",
  sidecar_reviewer: "Reviewer",
  theme_injection: "Ledger injection",
};
const KIND_COLOR = {
  main_call: "var(--trace-main)",
  sidecar_observer: "var(--trace-observer)",
  sidecar_reviewer: "var(--trace-reviewer)",
  theme_injection: "var(--trace-injection)",
};

const state = {
  run: null,
  trace: null,
  selected: null,
  kinds: new Set(Object.keys(KIND_LABEL)),
  search: "",
};

const el = {
  run: document.querySelector("#trace-run"),
  runSelect: document.querySelector("#run-select"),
  stats: document.querySelector("#trace-stats"),
  toolbar: document.querySelector("#trace-toolbar"),
  range: document.querySelector("#timeline-range"),
  stage: document.querySelector("#timeline-stage"),
  search: document.querySelector("#event-search"),
  list: document.querySelector("#event-list"),
  detail: document.querySelector("#event-detail"),
};

function hashRun() {
  return new URLSearchParams(location.hash.replace(/^#/, "")).get("run") || "";
}

function syncTabs() {
  const hash = location.hash;
  document.querySelector("#rt-viewer").href = `./viewer.html${hash}`;
  document.querySelector("#rt-trace").href = `./trace.html${hash}`;
  document.querySelector("#rt-harness").href = `./harness.html${hash}`;
}

function svgNode(tag, attributes = {}, text = "") {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  if (text) node.textContent = text;
  return node;
}

function fmtDuration(seconds) {
  const value = Number(seconds || 0);
  if (value >= 3600) return `${Math.floor(value / 3600)}h ${Math.round((value % 3600) / 60)}m`;
  if (value >= 60) return `${Math.floor(value / 60)}m ${Math.round(value % 60)}s`;
  return `${value.toFixed(value < 10 ? 1 : 0)}s`;
}

function fmtClock(value, seconds = false) {
  const date = new Date(value);
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "UTC", hour: "2-digit", minute: "2-digit",
    second: seconds ? "2-digit" : undefined, hour12: false,
  }).format(date);
}

function fmtDateTime(value) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "UTC", month: "short", day: "2-digit", hour: "2-digit",
    minute: "2-digit", second: "2-digit", hour12: false,
  }).format(new Date(value)) + " UTC";
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function visibleEvents() {
  return (state.trace?.events || []).filter((event) => state.kinds.has(event.kind));
}

async function populateRunSelect() {
  const index = await fetchRunsIndex();
  const rows = (index?.runs || []).filter((row) => row.has_execution_trace);
  const fallback = hashRun();
  if (fallback && !rows.some((row) => row.run === fallback)) rows.unshift({ run: fallback });
  el.runSelect.innerHTML = rows.map((row) => `<option value="${escapeHtml(row.run)}">${escapeHtml(row.run)}</option>`).join("");
  el.runSelect.value = fallback || rows[0]?.run || "";
}

function renderStats() {
  const counts = state.trace.counts || {};
  const cards = [
    [fmtDuration(state.trace.durationSeconds), "wall time"],
    [Number(counts.mainCalls || 0).toLocaleString(), "main calls"],
    [Number(counts.sidecarCalls || 0).toLocaleString(), "sidecar calls"],
    [Number(counts.themeInjections || 0).toLocaleString(), "prompt injections"],
    [Number(counts.processSamples || 0).toLocaleString(), "resource samples"],
  ];
  el.stats.innerHTML = cards.map(([value, label]) => `<div class="stat"><b>${escapeHtml(value)}</b><span>${escapeHtml(label)}</span></div>`).join("");
}

function renderTimeline() {
  const allLanes = state.trace.lanes || [];
  const events = visibleEvents();
  const laneIds = new Set(events.map((event) => event.lane));
  const lanes = allLanes.filter((lane) => laneIds.has(lane.id));
  const start = new Date(state.trace.startedAt).getTime();
  const end = new Date(state.trace.endedAt).getTime();
  const labelWidth = 230;
  const chartWidth = 1050;
  const rowHeight = 54;
  const top = 34;
  const bottom = 24;
  const height = top + lanes.length * rowHeight + bottom;
  const totalWidth = labelWidth + chartWidth;
  const x = (value) => labelWidth + Math.max(0, Math.min(1, (new Date(value).getTime() - start) / Math.max(1, end - start))) * chartWidth;
  const svg = svgNode("svg", { viewBox: `0 0 ${totalWidth} ${height}`, role: "img", "aria-label": "Aligned execution timeline" });

  const tickCount = 7;
  for (let index = 0; index < tickCount; index += 1) {
    const fraction = index / (tickCount - 1);
    const at = start + fraction * (end - start);
    const pos = labelWidth + fraction * chartWidth;
    svg.appendChild(svgNode("line", { x1: pos, x2: pos, y1: top - 8, y2: height - bottom, class: "axis-line" }));
    svg.appendChild(svgNode("text", { x: pos, y: 16, class: "axis-text", "text-anchor": index === 0 ? "start" : index === tickCount - 1 ? "end" : "middle" }, fmtClock(at)));
  }

  lanes.forEach((lane, laneIndex) => {
    const y = top + laneIndex * rowHeight;
    svg.appendChild(svgNode("rect", { x: 0, y, width: totalWidth, height: rowHeight, class: `lane-bg${laneIndex % 2 ? " alt" : ""}` }));
    svg.appendChild(svgNode("line", { x1: 0, x2: totalWidth, y1: y + rowHeight, y2: y + rowHeight, class: "lane-line" }));
    svg.appendChild(svgNode("text", { x: 12, y: y + 21, class: "lane-label" }, lane.label));
    svg.appendChild(svgNode("text", { x: 12, y: y + 38, class: "lane-meta" }, lane.cores || lane.resource || ""));
    const laneEvents = events.filter((event) => event.lane === lane.id);
    for (const event of laneEvents) {
      const startX = x(event.start);
      const endX = x(event.end || event.start);
      const width = event.instant ? 3 : Math.max(5, endX - startX);
      const rect = svgNode("rect", {
        x: startX - (event.instant ? 1.5 : 0), y: y + 12, width, height: 30, rx: event.instant ? 1 : 4,
        class: `trace-event kind-${event.kind} status-${event.status || "completed"}${state.selected?.id === event.id ? " selected" : ""}`,
        tabindex: 0, role: "button", "aria-label": `${KIND_LABEL[event.kind] || event.kind}: ${event.label}`,
      });
      rect.appendChild(svgNode("title", {}, `${fmtDateTime(event.start)}\n${event.label}\n${event.cores || event.resource || ""}`));
      const choose = () => selectEvent(event);
      rect.addEventListener("click", choose);
      rect.addEventListener("keydown", (keyEvent) => {
        if (keyEvent.key === "Enter" || keyEvent.key === " ") { keyEvent.preventDefault(); choose(); }
      });
      svg.appendChild(rect);
    }
  });
  el.stage.replaceChildren(svg);
  el.range.textContent = `${fmtDateTime(state.trace.startedAt)} → ${fmtDateTime(state.trace.endedAt)} · ${events.length.toLocaleString()} visible spans`;
}

function searchableText(event) {
  return [event.kind, event.label, event.resource, event.cores, event.gameId, event.action, event.ledgerRevision, ...(event.games || [])].join(" ").toLowerCase();
}

function renderEventList() {
  const query = state.search.trim().toLowerCase();
  const matches = visibleEvents().filter((event) => !query || searchableText(event).includes(query));
  const rows = matches.slice(0, 400).map((event) => `
    <button class="event-row${state.selected?.id === event.id ? " selected" : ""}" data-event-id="${escapeHtml(event.id)}">
      <time>${escapeHtml(fmtClock(event.start, true))}</time>
      <span class="dot" style="background:${KIND_COLOR[event.kind] || "var(--text-dim)"}"></span>
      <span class="row-label"><b>${escapeHtml(event.label)}</b><small>${escapeHtml(KIND_LABEL[event.kind] || event.kind)} · ${escapeHtml(event.cores || event.resource || "")}</small></span>
    </button>`).join("");
  el.list.innerHTML = rows + (matches.length > 400 ? `<div class="event-cap">Showing 400 of ${matches.length.toLocaleString()} matches. Narrow the filter to select later spans.</div>` : "");
  el.list.querySelectorAll("[data-event-id]").forEach((button) => {
    button.addEventListener("click", () => selectEvent(state.trace.events.find((event) => event.id === button.dataset.eventId)));
  });
}

function metaGrid(entries) {
  return `<div class="detail-meta">${entries.filter(([, value]) => value !== undefined && value !== null && value !== "").map(([label, value]) => `<div><b>${escapeHtml(label)}</b><span title="${escapeHtml(value)}">${escapeHtml(value)}</span></div>`).join("")}</div>`;
}

function formatSections(sections) {
  return (sections || []).map((section, index) => {
    const context = section.inContext === false ? " · not in captured context" : "";
    return `#${index + 1} [${section.label || "SECTION"}]${context}\n${section.content || ""}`;
  }).join("\n\n".repeat(2));
}

function nearestSample(event) {
  const samples = state.trace.processSamples || [];
  if (!samples.length) return null;
  const target = new Date(event.start).getTime();
  return samples.reduce((best, sample) => Math.abs(new Date(sample.at).getTime() - target) < Math.abs(new Date(best.at).getTime() - target) ? sample : best, samples[0]);
}

function processTable(event) {
  const sample = nearestSample(event);
  if (!sample) return "";
  const rows = (sample.processes || []).map((process) => `<tr><td>${escapeHtml(process.label)}</td><td>${escapeHtml(process.cores)}</td><td>${process.currentLogicalCpu}</td><td>${process.cpuPercent.toFixed(1)}%</td><td>${process.rssMiB.toLocaleString()} MiB</td></tr>`).join("");
  return `<table class="process-table"><thead><tr><th>Nearest sample · ${escapeHtml(fmtClock(sample.at, true))} UTC</th><th>Affinity</th><th>On CPU</th><th>CPU</th><th>RSS*</th></tr></thead><tbody>${rows}</tbody></table><div class="provenance-note">* RSS includes shared memory-mapped model pages and therefore must not be summed across servers as physical RAM.</div>`;
}

async function renderDetail(event) {
  if (!event) {
    el.detail.innerHTML = '<div class="detail-empty">Select any call or marker in the timeline.</div>';
    return;
  }
  const duration = Math.max(0, (new Date(event.end).getTime() - new Date(event.start).getTime()) / 1000);
  let input = "";
  let output = "";
  let provenance = "Exact timestamped record";
  let exact = true;
  let link = "";

  if (event.detail?.type === "inline_call") {
    input = event.detail.input || "";
    output = event.detail.output || "";
  } else if (event.detail?.type === "metadata") {
    input = JSON.stringify(event.detail.record || {}, null, 2);
    output = "This marker records a ledger block injected into a gameplay prompt; it is not a model call.";
  } else if (event.detail?.type === "game_step") {
    const payload = await fetchGameStep(state.run, event.detail.gameIndex, event.detail.stepIndex);
    const step = payload.step || {};
    const context = step.context || step.localContext || {};
    const local = step.localContext || {};
    exact = Boolean(step.traceInputExact || context.hasExactModelContext);
    provenance = exact
      ? "Exact saved request context"
      : "Cumulative transcript reconstruction. Historical direct-run TAAF did not save each request JSON, so model-side trimming or omission cannot be proven.";
    let capturedRequestSections;
    if (exact) {
      capturedRequestSections = (context.sections || []).filter((section) => section.source === "request");
    } else if (step.contextReconstruction?.kind === "prior_step_transcripts") {
      const throughStep = Number(step.contextReconstruction.throughStep ?? event.detail.stepIndex);
      const priorPayloads = await Promise.all(
        Array.from({ length: throughStep + 1 }, (_, index) => fetchGameStep(state.run, event.detail.gameIndex, index)),
      );
      capturedRequestSections = [];
      let systemPromptIncluded = false;
      priorPayloads.forEach((priorPayload) => {
        const priorSections = priorPayload.step?.localContext?.sections || [];
        priorSections.forEach((section) => {
          const isSystemPrompt = /^SYSTEM PROMPT$/i.test(section.label || "");
          if (isSystemPrompt && systemPromptIncluded) return;
          if (isSystemPrompt) systemPromptIncluded = true;
          capturedRequestSections.push(section);
        });
      });
    } else {
      capturedRequestSections = context.sections || [];
    }
    input = formatSections(capturedRequestSections);
    const generated = (local.sections || []).filter((section) => /^(THINKING|ASSISTANT|TOOL CALL|ERROR)/i.test(section.label || ""));
    output = formatSections(generated.length ? generated : local.sections || []);
    link = `<a class="detail-link" href="./viewer.html#run=${encodeURIComponent(state.run)}&game=${event.gameIndex}">Open this game in the frame viewer →</a>`;
  }

  const badge = event.kind === "main_call" ? `<span class="badge ${exact ? "exact" : "reconstructed"}">${exact ? "exact input" : "reconstructed context"}</span>` : '<span class="badge exact">exact call log</span>';
  const usage = event.usage || {};
  el.detail.innerHTML = `<div class="detail-wrap">
    <div class="detail-title"><h2>${escapeHtml(event.label)}</h2>${badge}</div>
    ${metaGrid([
      ["Start", fmtDateTime(event.start)], ["Duration", event.instant ? "point event" : fmtDuration(event.durationSeconds ?? duration)],
      ["Span type", KIND_LABEL[event.kind] || event.kind], ["Status", event.status], ["Resource", event.resource], ["CPU / affinity", event.cores],
      ["Prompt tokens", usage.promptTokens], ["Completion tokens", usage.completionTokens], ["Game", event.gameId], ["Ledger revision", event.ledgerRevision],
    ])}
    <div class="provenance-note${exact ? " exact" : ""}">${escapeHtml(provenance)}</div>
    <div class="io-grid">
      <section class="io-panel"><h3>${event.kind === "main_call" ? "Context at selected call" : "Exact input"}</h3><pre>${escapeHtml(input || "(no input body recorded)")}</pre></section>
      <section class="io-panel"><h3>${event.kind === "main_call" ? "Current call output / tool activity" : "Exact output"}</h3><pre>${escapeHtml(output || "(no output body recorded)")}</pre></section>
    </div>
    ${link}
    ${processTable(event)}
  </div>`;
}

async function selectEvent(event) {
  if (!event) return;
  state.selected = event;
  renderTimeline();
  renderEventList();
  await renderDetail(event);
}

async function loadRun(run) {
  state.run = run;
  state.selected = null;
  state.trace = await fetchRunTimeline(run);
  document.title = `${run} — execution trace`;
  el.run.textContent = run;
  el.runSelect.value = run;
  renderStats();
  renderTimeline();
  renderEventList();
  renderDetail(null);
}

el.toolbar.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-kind]");
  if (!button) return;
  const kind = button.dataset.kind;
  if (state.kinds.has(kind)) state.kinds.delete(kind); else state.kinds.add(kind);
  button.classList.toggle("on", state.kinds.has(kind));
  renderTimeline();
  renderEventList();
});
el.search.addEventListener("input", () => { state.search = el.search.value; renderEventList(); });
el.runSelect.addEventListener("change", () => { location.hash = `#run=${encodeURIComponent(el.runSelect.value)}`; });
window.addEventListener("hashchange", async () => { syncTabs(); await loadRun(hashRun()); });

syncTabs();
await populateRunSelect();
if (!hashRun() && el.runSelect.value) location.replace(`#run=${encodeURIComponent(el.runSelect.value)}`);
else await loadRun(hashRun() || el.runSelect.value);

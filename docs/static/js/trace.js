import { fetchGameStep, fetchRunsIndex, fetchRunTimeline } from "./api.js";

const KIND_LABEL = {
  main_call: "Gameplay call",
  sidecar_observer: "Observer",
  sidecar_reviewer: "Reviewer",
  curator_synthesis: "World-model curator",
  theme_injection: "Ledger injection",
  world_model_injection: "World-model injection",
};
const PHASE_LABEL = { input: "Input", reasoning: "Reasoning", tool_call: "Tool call", compact: "Compact" };

const state = {
  run: null, trace: null, pinned: null, preview: null,
  kinds: new Set(Object.keys(KIND_LABEL)), search: "", detailRequest: 0, stepCache: new Map(),
};
const el = {
  run: document.querySelector("#trace-run"), runSelect: document.querySelector("#run-select"),
  stats: document.querySelector("#trace-stats"), toolbar: document.querySelector("#trace-toolbar"),
  range: document.querySelector("#timeline-range"), heading: document.querySelector("#timeline-heading"), stage: document.querySelector("#timeline-stage"),
  search: document.querySelector("#event-search"), detail: document.querySelector("#event-detail"),
};

function hashRun() { return new URLSearchParams(location.hash.replace(/^#/, "")).get("run") || ""; }
function syncTabs() {
  const hash = location.hash;
  document.querySelector("#rt-viewer").href = `./viewer.html${hash}`;
  document.querySelector("#rt-trace").href = `./trace.html${hash}`;
  document.querySelector("#rt-score").href = `./score-time.html${hash}`;
  document.querySelector("#rt-harness").href = `./harness.html${hash}`;
}
function fmtDuration(seconds) {
  const value = Number(seconds || 0);
  if (value >= 3600) return `${Math.floor(value / 3600)}h ${Math.round((value % 3600) / 60)}m`;
  if (value >= 60) return `${Math.floor(value / 60)}m ${Math.round(value % 60)}s`;
  return `${value.toFixed(value < 10 ? 1 : 0)}s`;
}
function fmtClock(value, seconds = false) {
  return new Intl.DateTimeFormat("en-GB", { timeZone: "UTC", hour: "2-digit", minute: "2-digit", second: seconds ? "2-digit" : undefined, hour12: false }).format(new Date(value));
}
function fmtDateTime(value) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "UTC", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(new Date(value)) + " UTC";
}
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}
function searchableText(event) {
  return [event.kind, event.label, event.resource, event.cores, event.gameId, event.action, event.ledgerRevision, ...(event.games || [])].join(" ").toLowerCase();
}
function eventVisible(event) {
  if (!state.kinds.has(event.kind)) return false;
  const query = state.search.trim().toLowerCase();
  return !query || searchableText(event).includes(query);
}

async function populateRunSelect() {
  const index = await fetchRunsIndex();
  const rows = (index?.runs || []).filter((row) => row.has_execution_trace);
  const fallback = hashRun();
  if (fallback && !rows.some((row) => row.run === fallback)) rows.unshift({ run: fallback });
  el.runSelect.innerHTML = rows.map((row) => `<option value="${escapeHtml(row.run)}">${escapeHtml(row.run)}</option>`).join("");
  el.runSelect.value = fallback || rows[0]?.run || "";
}

function normalizeLegacyTrace(trace) {
  if (Number(trace.schemaVersion || 1) >= 2 || !(trace.lanes || []).some((lane) => lane.id === "main-model")) return trace;
  const gameplayEvents = (trace.events || []).filter((event) => event.kind === "main_call");
  const games = [...new Map(gameplayEvents.map((event) => [String(event.gameId || event.gameIndex), event])).values()];
  const concurrency = Number(trace.topology?.gameplayConcurrency || games.length || 1);
  const gameLane = new Map(games.map((event, index) => [String(event.gameId || event.gameIndex), `gameplay-${index}`]));
  const gameplayLanes = Array.from({ length: concurrency }, (_, index) => {
    const event = games[index]; const gameId = event?.gameId || "";
    return { id: `gameplay-${index}`, label: `Thread ${String(index + 1).padStart(2, "0")} · ${gameId || "idle"}`, resource: "Gameplay inference queue", cores: "shared GPU inference queue", group: "gameplay", games: gameId ? [gameId] : [] };
  });
  trace.events.forEach((event) => {
    const lane = gameLane.get(String(event.gameId || event.gameIndex));
    if (lane && (event.kind === "main_call" || /injection$/.test(event.kind))) event.lane = lane;
  });
  trace.lanes = [
    ...(trace.lanes || []).filter((lane) => lane.id !== "main-model" && /curator/i.test(lane.id)),
    ...(trace.lanes || []).filter((lane) => lane.id !== "main-model" && !/curator|injection/i.test(lane.id)),
    ...gameplayLanes,
  ];
  return trace;
}

function renderStats() {
  const counts = state.trace.counts || {};
  const gameplay = (state.trace.lanes || []).filter((lane) => lane.group === "gameplay").length;
  const cards = [
    [fmtDuration(state.trace.durationSeconds), "wall time"], [gameplay.toLocaleString(), "gameplay threads"],
    [Number(counts.mainCalls || 0).toLocaleString(), "gameplay calls"], [Number(counts.curatorCalls || 0).toLocaleString(), "curator calls"],
    [Number((counts.themeInjections || 0) + (counts.worldModelInjections || 0)).toLocaleString(), "prompt injections"],
    [Number(counts.processSamples || 0).toLocaleString(), "resource samples"],
  ];
  el.stats.innerHTML = cards.map(([value, label]) => `<div class="stat"><b>${escapeHtml(value)}</b><span>${escapeHtml(label)}</span></div>`).join("");
}

function phaseSummary(event) {
  if (Array.isArray(event.phaseSummary) && event.phaseSummary.length) return event.phaseSummary;
  if (event.instant || /injection$/.test(event.kind)) return [];
  return [{ phase: "reasoning", charCount: 1, sectionCount: 1, labels: [KIND_LABEL[event.kind] || event.kind] }];
}
function phaseTitle(event, phase) {
  const labels = (phase.labels || []).join(", ");
  return `${PHASE_LABEL[phase.phase] || phase.phase} · ${Number(phase.charCount || 0).toLocaleString()} captured characters${labels ? ` · ${labels}` : ""}\n${event.label}`;
}
function activeSelection(event, phase = null) {
  const selected = state.pinned || state.preview;
  return selected?.event?.id === event.id && (selected.phase || null) === (phase || null);
}

function renderTimeline() {
  const lanes = state.trace.lanes || [];
  const events = (state.trace.events || []).filter(eventVisible);
  const start = new Date(state.trace.startedAt).getTime();
  const end = new Date(state.trace.endedAt).getTime();
  const duration = Math.max(1, end - start);
  const chartWidth = Math.max(1180, Math.min(2600, Math.round(duration / 60000) * 14));
  const position = (value) => Math.max(0, Math.min(100, ((new Date(value).getTime() - start) / duration) * 100));
  el.heading.textContent = `${lanes.length}-lane execution timeline`;
  const grid = document.createElement("div");
  grid.className = "lane-grid";
  grid.style.setProperty("--chart-width", `${chartWidth}px`);

  const header = document.createElement("div");
  header.className = "time-row";
  header.innerHTML = '<div class="lane-heading">Threads</div><div class="time-track"></div>';
  const tickTrack = header.querySelector(".time-track");
  for (let index = 0; index < 7; index += 1) {
    const fraction = index / 6;
    const tick = document.createElement("span");
    tick.className = "time-tick"; tick.style.left = `${fraction * 100}%`; tick.textContent = fmtClock(start + fraction * duration);
    tickTrack.appendChild(tick);
  }
  grid.appendChild(header);

  const laneEvents = new Map(lanes.map((lane) => [lane.id, []]));
  events.forEach((event) => { if (!laneEvents.has(event.lane)) laneEvents.set(event.lane, []); laneEvents.get(event.lane).push(event); });
  lanes.forEach((lane, laneIndex) => {
    const row = document.createElement("div");
    row.className = `lane-row${lane.group === "curator" ? " curator-row" : ""}`;
    const games = lane.games || [];
    row.innerHTML = `<div class="lane-sidebar"><b>${escapeHtml(lane.label)}</b><span>${escapeHtml(games.length > 1 ? games.join(" → ") : lane.cores || lane.resource || "")}</span></div><div class="lane-track"></div>`;
    const track = row.querySelector(".lane-track"); track.dataset.laneIndex = String(laneIndex);
    for (const event of laneEvents.get(lane.id) || []) {
      const eventStart = position(event.start); const eventEnd = position(event.end || event.start);
      const bar = document.createElement("div"); const isPoint = Boolean(event.instant);
      bar.className = `event-bar kind-${event.kind} status-${event.status || "completed"}${isPoint ? " point-event" : ""}`;
      bar.style.left = `${eventStart}%`; if (!isPoint) bar.style.width = `${Math.max(.16, eventEnd - eventStart)}%`;
      bar.tabIndex = 0; bar.setAttribute("role", "button"); bar.setAttribute("aria-label", `${KIND_LABEL[event.kind] || event.kind}: ${event.label}`);
      bar.title = `${fmtDateTime(event.start)}\n${event.label}`;
      const phases = phaseSummary(event);
      if (phases.length) {
        phases.forEach((phase) => {
          const segment = document.createElement("span");
          segment.className = `event-phase phase-${phase.phase}${activeSelection(event, phase.phase) ? " selected" : ""}`;
          segment.style.flexGrow = String(Math.max(1, Number(phase.charCount || 1))); segment.title = phaseTitle(event, phase);
          segment.addEventListener("mouseenter", () => previewEvent(event, phase.phase));
          segment.addEventListener("click", (clickEvent) => { clickEvent.stopPropagation(); pinEvent(event, phase.phase); });
          segment.addEventListener("focus", () => previewEvent(event, phase.phase));
          bar.appendChild(segment);
        });
      } else if (activeSelection(event)) bar.classList.add("selected");
      bar.addEventListener("mouseenter", () => { if (!phases.length) previewEvent(event, null); });
      bar.addEventListener("mouseleave", clearPreview); bar.addEventListener("click", () => pinEvent(event, null));
      bar.addEventListener("keydown", (keyEvent) => { if (keyEvent.key === "Enter" || keyEvent.key === " ") { keyEvent.preventDefault(); pinEvent(event, null); } });
      track.appendChild(bar);
    }
    grid.appendChild(row);
  });
  el.stage.replaceChildren(grid);
  el.range.textContent = `${fmtDateTime(state.trace.startedAt)} → ${fmtDateTime(state.trace.endedAt)} · ${events.length.toLocaleString()} visible spans`;
}

function metaGrid(entries) {
  return `<div class="detail-meta">${entries.filter(([, value]) => value !== undefined && value !== null && value !== "").map(([label, value]) => `<div><b>${escapeHtml(label)}</b><span title="${escapeHtml(value)}">${escapeHtml(value)}</span></div>`).join("")}</div>`;
}
function formatSections(sections) {
  return (sections || []).map((section, index) => `#${index + 1} [${section.label || "SECTION"}]${section.inContext === false ? " · not in captured context" : ""}\n${section.content || ""}`).join("\n\n");
}
function sectionPhase(section) {
  const label = String(section?.label || "").toUpperCase(); const kind = String(section?.kind || "").toLowerCase();
  if (label.includes("COMPACT") || ["compact", "compaction"].includes(kind)) return "compact";
  if (label.includes("TOOL CALL") || kind === "tool_call") return "tool_call";
  if (/^(THINKING|ASSISTANT)/.test(label) || kind === "reasoning") return "reasoning";
  return "input";
}
function nearestSample(event) {
  const samples = state.trace.processSamples || []; if (!samples.length) return null;
  const target = new Date(event.start).getTime();
  return samples.reduce((best, sample) => Math.abs(new Date(sample.at).getTime() - target) < Math.abs(new Date(best.at).getTime() - target) ? sample : best, samples[0]);
}
function processTable(event) {
  const sample = nearestSample(event); if (!sample) return "";
  const rows = (sample.processes || []).map((process) => `<tr><td>${escapeHtml(process.label)}</td><td>${escapeHtml(process.cores)}</td><td>${process.currentLogicalCpu}</td><td>${process.cpuPercent.toFixed(1)}%</td><td>${process.rssMiB.toLocaleString()} MiB</td></tr>`).join("");
  return `<table class="process-table"><thead><tr><th>Nearest sample · ${escapeHtml(fmtClock(sample.at, true))} UTC</th><th>Affinity</th><th>On CPU</th><th>CPU</th><th>RSS*</th></tr></thead><tbody>${rows}</tbody></table><div class="provenance-note">* RSS includes shared memory-mapped pages and must not be summed as physical RAM.</div>`;
}
async function cachedStep(gameIndex, stepIndex) {
  const key = `${state.run}:${gameIndex}:${stepIndex}`;
  if (!state.stepCache.has(key)) state.stepCache.set(key, fetchGameStep(state.run, gameIndex, stepIndex));
  return state.stepCache.get(key);
}
async function capturedInput(event, step, exact) {
  const context = step.context || step.localContext || {};
  if (exact) return (context.sections || []).filter((section) => section.source === "request");
  if (step.contextReconstruction?.kind !== "prior_step_transcripts") return context.sections || [];
  const throughStep = Number(step.contextReconstruction.throughStep ?? event.detail.stepIndex);
  const payloads = await Promise.all(Array.from({ length: throughStep + 1 }, (_, index) => cachedStep(event.detail.gameIndex, index)));
  const sections = []; let systemPromptIncluded = false;
  payloads.forEach((payload) => (payload.step?.localContext?.sections || []).forEach((section) => {
    const isSystem = /^SYSTEM PROMPT$/i.test(section.label || ""); if (isSystem && systemPromptIncluded) return;
    if (isSystem) systemPromptIncluded = true; sections.push(section);
  }));
  return sections;
}

async function renderDetail(event, selectedPhase = null) {
  const request = ++state.detailRequest;
  if (!event) {
    el.detail.innerHTML = '<div class="detail-empty"><b>Token inspector</b><span>Hover a colored phase to preview it. Click a phase to pin it.</span></div>'; return;
  }
  el.detail.innerHTML = '<div class="detail-loading">Loading captured tokens…</div>';
  const duration = Math.max(0, (new Date(event.end).getTime() - new Date(event.start).getTime()) / 1000);
  let input = ""; let output = ""; let focus = ""; let provenance = "Exact timestamped record"; let exact = true; let link = "";
  if (event.detail?.type === "inline_call") {
    input = event.detail.input || ""; output = event.detail.output || ""; focus = selectedPhase === "input" ? input : output;
  } else if (event.detail?.type === "curator_call") {
    input = event.detail.input || ""; output = event.detail.output || ""; focus = selectedPhase === "input" ? input : output; exact = false;
    provenance = `${event.detail.inputProvenance || "Curator input metadata."} ${event.detail.outputProvenance || "Curator output metadata."}`;
  } else if (event.detail?.type === "metadata") {
    input = JSON.stringify(event.detail.record || {}, null, 2); output = "This point records a ledger block injected into the gameplay request; it is not a separate model call."; focus = input;
  } else if (event.detail?.type === "game_step") {
    const payload = await cachedStep(event.detail.gameIndex, event.detail.stepIndex); const step = payload.step || {};
    const context = step.context || step.localContext || {}; const local = step.localContext || {};
    exact = Boolean(step.traceInputExact || context.hasExactModelContext);
    provenance = exact ? "Exact saved request context. Phase widths are character-weighted composition, not synthetic token timestamps." : "Cumulative transcript reconstruction. Historical model-side trimming or omission cannot be proven.";
    const inputSections = await capturedInput(event, step, exact); const localSections = local.sections || [];
    const lastUser = Math.max(-1, ...localSections.map((section, index) => /^USER PROMPT$/i.test(section.label || "") ? index : -1));
    const generated = localSections.slice(lastUser + 1).filter((section) => /^(THINKING|ASSISTANT|TOOL CALL|ERROR|COMPACT)/i.test(section.label || "") || ["reasoning", "tool_call", "compact", "compaction"].includes(section.kind));
    input = formatSections(inputSections); output = formatSections(generated.length ? generated : localSections);
    focus = selectedPhase === "input" ? input : selectedPhase ? formatSections(generated.filter((section) => sectionPhase(section) === selectedPhase)) : "";
    link = `<a class="detail-link" href="./viewer.html#run=${encodeURIComponent(state.run)}&game=${event.gameIndex}">Open this game in the frame viewer →</a>`;
  }
  if (request !== state.detailRequest) return;
  const usage = event.usage || {};
  const badge = event.kind === "main_call" ? `<span class="badge ${exact ? "exact" : "reconstructed"}">${exact ? "exact input" : "reconstructed context"}</span>` : event.kind === "curator_synthesis" ? '<span class="badge reconstructed">exact call metadata + observed ledger</span>' : '<span class="badge exact">exact event log</span>';
  const phaseBadge = selectedPhase ? `<span class="phase-badge phase-${selectedPhase}">${escapeHtml(PHASE_LABEL[selectedPhase] || selectedPhase)}</span>` : "";
  const focusBody = focus || `(no ${PHASE_LABEL[selectedPhase] || selectedPhase || "selected"} text recorded for this span)`;
  const body = selectedPhase ? `<section class="focus-panel phase-border-${selectedPhase}"><h3>${escapeHtml(PHASE_LABEL[selectedPhase] || selectedPhase)} tokens in process</h3><pre>${escapeHtml(focusBody)}</pre></section>` : `<div class="io-grid"><section class="io-panel"><h3>Input / context</h3><pre>${escapeHtml(input || "(no input body recorded)")}</pre></section><section class="io-panel"><h3>Output / activity</h3><pre>${escapeHtml(output || "(no output body recorded)")}</pre></section></div>`;
  el.detail.innerHTML = `<div class="detail-wrap"><div class="detail-title"><h2>${escapeHtml(event.label)}</h2>${phaseBadge}${badge}</div>
    ${metaGrid([["Start", fmtDateTime(event.start)], ["Duration", event.instant ? "point event" : fmtDuration(event.durationSeconds ?? duration)], ["Span type", KIND_LABEL[event.kind] || event.kind], ["Status", event.status], ["Game", event.gameId], ["Prompt tokens", usage.promptTokens], ["Completion tokens", usage.completionTokens], ["Ledger revision", event.ledgerRevision ?? event.ledgerRevisionAfter], ["Evidence games", event.evidenceCount], ["Ledger entries", event.ledgerEntryCount]])}
    <div class="provenance-note${exact ? " exact" : ""}">${escapeHtml(provenance)}</div>${body}${link}${processTable(event)}</div>`;
}

function previewEvent(event, phase) { if (state.pinned) return; state.preview = { event, phase }; renderDetail(event, phase); }
function clearPreview() { if (state.pinned) return; state.preview = null; renderDetail(null); }
function pinEvent(event, phase) { state.pinned = { event, phase }; state.preview = null; renderTimeline(); renderDetail(event, phase); }

async function loadRun(run) {
  state.run = run; state.pinned = null; state.preview = null; state.stepCache.clear();
  state.trace = normalizeLegacyTrace(await fetchRunTimeline(run));
  document.title = `${run} — execution trace`; el.run.textContent = run; el.runSelect.value = run;
  renderStats(); renderTimeline(); renderDetail(null);
}

el.toolbar.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-kind]"); if (!button) return;
  const kind = button.dataset.kind; if (state.kinds.has(kind)) state.kinds.delete(kind); else state.kinds.add(kind);
  button.classList.toggle("on", state.kinds.has(kind)); renderTimeline();
});
el.search.addEventListener("input", () => { state.search = el.search.value; renderTimeline(); });
el.runSelect.addEventListener("change", () => { location.hash = `#run=${encodeURIComponent(el.runSelect.value)}`; });
window.addEventListener("keydown", (event) => { if (event.key === "Escape" && state.pinned) { state.pinned = null; renderTimeline(); renderDetail(null); } });
window.addEventListener("hashchange", async () => { syncTabs(); await loadRun(hashRun()); });

syncTabs();
await populateRunSelect();
if (!hashRun() && el.runSelect.value) location.replace(`#run=${encodeURIComponent(el.runSelect.value)}`);
else await loadRun(hashRun() || el.runSelect.value);

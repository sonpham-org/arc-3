import { fetchGameStep, fetchRunOverview, fetchRunsIndex, fetchRunTimeline } from "./api.js";
import { paintThumb, setPalette } from "./board.js?v=20260815-frames";

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
  run: null, trace: null, overview: null, pinned: null, preview: null, activeScrub: null,
  kinds: new Set(Object.keys(KIND_LABEL)), search: "", detailRequest: 0, stepCache: new Map(), gameById: new Map(),
  segmentMap: new Map(), timelineBody: null, timelineGrid: null, marker: null, previewTimer: null,
  zoom: 1, baseChartHeight: 1200,
};
const el = {
  run: document.querySelector("#trace-run"), runSelect: document.querySelector("#run-select"),
  stats: document.querySelector("#trace-stats"), toolbar: document.querySelector("#trace-toolbar"),
  range: document.querySelector("#timeline-range"), heading: document.querySelector("#timeline-heading"), zoom: document.querySelector("#timeline-zoom"),
  scroll: document.querySelector(".timeline-scroll"), stage: document.querySelector("#timeline-stage"),
  search: document.querySelector("#event-search"), detail: document.querySelector("#event-detail"),
};

function hashRun() { return new URLSearchParams(location.hash.replace(/^#/, "")).get("run") || ""; }
function syncTabs() {
  const hash = location.hash;
  document.querySelector("#rt-viewer").href = `./viewer.html${hash}`;
  document.querySelector("#rt-trace").href = `./trace.html${hash}`;
  document.querySelector("#rt-score").href = `./score-time.html${hash}`;
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
function activeSelection(event, phase = null, segmentIndex = null) {
  const selected = state.pinned || state.preview;
  return selected?.event?.id === event.id && (selected.phase || null) === (phase || null)
    && (selected.segmentIndex ?? null) === (segmentIndex ?? null);
}

function renderTimeline() {
  const lanes = state.trace.lanes || [];
  const events = (state.trace.events || []).filter(eventVisible);
  const start = new Date(state.trace.startedAt).getTime();
  const end = new Date(state.trace.endedAt).getTime();
  const duration = Math.max(1, end - start);
  state.baseChartHeight = Math.max(1200, Math.min(3600, Math.round(duration / 60000) * 14));
  const chartHeight = Math.round(state.baseChartHeight * state.zoom);
  const position = (value) => Math.max(0, Math.min(100, ((new Date(value).getTime() - start) / duration) * 100));
  el.heading.textContent = `${lanes.length}-lane vertical execution timeline`;
  state.segmentMap.clear();
  const grid = document.createElement("div");
  grid.className = "vertical-grid";
  grid.style.setProperty("--lane-count", String(lanes.length));
  grid.style.setProperty("--chart-height", `${chartHeight}px`);
  state.timelineGrid = grid;
  el.zoom.textContent = `${Math.round(state.zoom * 100)}% · Ctrl+scroll to zoom`;

  const header = document.createElement("div");
  header.className = "thread-head-row";
  const corner = document.createElement("div");
  corner.className = "time-corner";
  corner.innerHTML = "<b>UTC</b><span>time ↓</span>";
  header.appendChild(corner);
  lanes.forEach((lane, laneIndex) => {
    const head = document.createElement("div");
    head.className = `thread-head${lane.group === "curator" ? " curator-head" : ""}`;
    const game = (lane.games || []).map((gameId) => state.gameById.get(String(gameId))).find(Boolean);
    const threadMatch = String(lane.label || "").match(/Thread\s+(\d+)/i);
    const threadCode = threadMatch ? `T${String(threadMatch[1]).padStart(2, "0")}` : `T${String(laneIndex).padStart(2, "0")}`;
    if (lane.group === "gameplay" && game) {
      head.innerHTML = `<b>${escapeHtml(threadCode)}</b><canvas aria-hidden="true"></canvas><span title="${escapeHtml(game.display_name || game.game_id)}">${escapeHtml(game.game_id || game.display_name)}</span>`;
      setTimeout(() => paintThumb(head.querySelector("canvas"), game.board_ascii, 1), 0);
    } else if (lane.group === "gameplay") {
      head.innerHTML = `<b>${escapeHtml(threadCode)}</b><div class="idle-thumb">—</div><span>idle</span>`;
    } else {
      head.innerHTML = `<b>CUR</b><div class="curator-thumb">WM</div><span>Curator</span>`;
    }
    header.appendChild(head);
  });
  grid.appendChild(header);

  const laneEvents = new Map(lanes.map((lane) => [lane.id, []]));
  events.forEach((event) => { if (!laneEvents.has(event.lane)) laneEvents.set(event.lane, []); laneEvents.get(event.lane).push(event); });
  const body = document.createElement("div");
  body.className = "vertical-timeline-body";
  state.timelineBody = body;

  const axis = document.createElement("div");
  axis.className = "vertical-time-axis";
  body.appendChild(axis);
  for (let index = 0; index <= 8; index += 1) {
    const fraction = index / 8;
    const gridLine = document.createElement("div");
    gridLine.className = "vertical-time-grid";
    gridLine.style.top = `${fraction * 100}%`;
    body.appendChild(gridLine);
    const tick = document.createElement("span");
    tick.className = "vertical-time-tick";
    tick.style.top = `${fraction * 100}%`;
    tick.textContent = fmtClock(start + fraction * duration, true);
    axis.appendChild(tick);
  }

  lanes.forEach((lane, laneIndex) => {
    const track = document.createElement("div");
    track.className = `thread-column${lane.group === "curator" ? " curator-column" : ""}`;
    track.dataset.laneIndex = String(laneIndex);
    for (const event of laneEvents.get(lane.id) || []) {
      const eventStart = position(event.start); const eventEnd = position(event.end || event.start);
      const bar = document.createElement("div"); const isPoint = Boolean(event.instant);
      bar.className = `event-bar kind-${event.kind} status-${event.status || "completed"}${isPoint ? " point-event" : ""}`;
      bar.style.top = `${eventStart}%`; if (!isPoint) bar.style.height = `${Math.max(.16, eventEnd - eventStart)}%`;
      bar.tabIndex = 0; bar.setAttribute("role", "button"); bar.setAttribute("aria-label", `${KIND_LABEL[event.kind] || event.kind}: ${event.label}`);
      bar.title = `${fmtDateTime(event.start)}\n${event.label}`;
      const phases = phaseSummary(event);
      if (phases.length) {
        phases.forEach((phase, segmentIndex) => {
          const segment = document.createElement("span");
          segment.className = `event-phase phase-${phase.phase}${activeSelection(event, phase.phase, segmentIndex) ? " selected" : ""}`;
          segment.style.flexGrow = String(Math.max(1, Number(phase.charCount || 1))); segment.title = phaseTitle(event, phase);
          state.segmentMap.set(`${event.id}:${segmentIndex}`, segment);
          segment.addEventListener("pointerenter", () => previewEvent(event, phase.phase, segmentIndex, .5));
          segment.addEventListener("pointermove", (pointerEvent) => scrubFromElement(event, phase.phase, segmentIndex, segment, pointerEvent));
          segment.addEventListener("click", (clickEvent) => { clickEvent.stopPropagation(); pinEvent(event, phase.phase, segmentIndex); });
          segment.addEventListener("focus", () => previewEvent(event, phase.phase, segmentIndex, .5));
          bar.appendChild(segment);
        });
      } else {
        state.segmentMap.set(`${event.id}:event`, bar);
        if (activeSelection(event)) bar.classList.add("selected");
      }
      bar.addEventListener("pointerenter", () => { if (!phases.length) previewEvent(event, null, null, .5); });
      bar.addEventListener("pointermove", (pointerEvent) => { if (!phases.length) scrubFromElement(event, null, null, bar, pointerEvent); });
      bar.addEventListener("pointerleave", scheduleClearPreview); bar.addEventListener("click", () => pinEvent(event, null, null));
      bar.addEventListener("keydown", (keyEvent) => { if (keyEvent.key === "Enter" || keyEvent.key === " ") { keyEvent.preventDefault(); pinEvent(event, null, null); } });
      track.appendChild(bar);
    }
    body.appendChild(track);
  });
  const marker = document.createElement("div");
  marker.className = "timeline-marker";
  marker.hidden = true;
  marker.innerHTML = "<span></span>";
  body.appendChild(marker);
  state.marker = marker;
  grid.appendChild(body);
  el.stage.replaceChildren(grid);
  el.range.textContent = `${fmtDateTime(state.trace.startedAt)} → ${fmtDateTime(state.trace.endedAt)} · ${events.length.toLocaleString()} visible spans`;
  const selected = state.pinned || state.preview;
  if (selected) updateScrub(selected.event, selected.phase, selected.segmentIndex, selected.ratio ?? .5, false);
}

function scrubFromElement(event, phase, segmentIndex, segment, pointerEvent) {
  const bounds = segment.getBoundingClientRect();
  const ratio = Math.max(0, Math.min(1, (pointerEvent.clientY - bounds.top) / Math.max(1, bounds.height)));
  updateScrub(event, phase, segmentIndex, ratio, false);
}

function updateScrub(event, phase, segmentIndex, ratio, fromText) {
  const selected = state.pinned?.event?.id === event.id && state.pinned?.segmentIndex === segmentIndex ? state.pinned : state.preview;
  if (selected) selected.ratio = ratio;
  state.activeScrub = { event, phase, segmentIndex, ratio };
  const key = `${event.id}:${segmentIndex ?? "event"}`;
  const segment = state.segmentMap.get(key);
  if (segment && state.timelineBody && state.marker) {
    const segmentBounds = segment.getBoundingClientRect();
    const bodyBounds = state.timelineBody.getBoundingClientRect();
    const top = segmentBounds.top - bodyBounds.top + ratio * segmentBounds.height;
    const bodyRatio = Math.max(0, Math.min(1, top / Math.max(1, state.timelineBody.clientHeight)));
    const at = new Date(state.trace.startedAt).getTime() + bodyRatio * (new Date(state.trace.endedAt).getTime() - new Date(state.trace.startedAt).getTime());
    state.marker.style.top = `${top}px`;
    state.marker.querySelector("span").textContent = fmtClock(at, true);
    state.marker.hidden = false;
  }
  updateReasoningCursor(ratio, !fromText);
}

function zoomTimeline(nextZoom, clientY) {
  const zoom = Math.max(1, Math.min(8, nextZoom));
  if (!state.timelineBody || !state.timelineGrid || Math.abs(zoom - state.zoom) < .001) return;
  const oldHeight = state.timelineBody.clientHeight;
  const bodyBounds = state.timelineBody.getBoundingClientRect();
  const anchor = Math.max(0, Math.min(1, (clientY - bodyBounds.top) / Math.max(1, oldHeight)));
  state.zoom = zoom;
  const newHeight = Math.round(state.baseChartHeight * state.zoom);
  state.timelineGrid.style.setProperty("--chart-height", `${newHeight}px`);
  el.scroll.scrollTop += (newHeight - oldHeight) * anchor;
  el.zoom.textContent = `${Math.round(state.zoom * 100)}% · Ctrl+scroll to zoom`;
  const selected = state.pinned || state.preview;
  if (selected) updateScrub(selected.event, selected.phase, selected.segmentIndex, selected.ratio ?? .5, false);
}

function handleTimelineZoom(event) {
  if (!event.ctrlKey) return;
  event.preventDefault();
  const delta = event.deltaMode === 1 ? event.deltaY * 24 : event.deltaY;
  zoomTimeline(state.zoom * Math.exp(-delta * .0025), event.clientY);
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
function groupAdjacentSections(sections) {
  return (sections || []).reduce((groups, section) => {
    const phase = sectionPhase(section); const prior = groups[groups.length - 1];
    if (prior?.phase === phase) prior.sections.push(section);
    else groups.push({ phase, sections: [section] });
    return groups;
  }, []);
}
function scrubTextHtml(text) {
  let offset = 0;
  return String(text || "").split("\n").map((line) => {
    const start = offset; const end = start + line.length; offset = end + 1;
    return `<span class="scrub-line" data-start="${start}" data-end="${end}">${escapeHtml(line) || " "}</span>`;
  }).join("\n");
}
function installReasoningScrubber(event, phase, segmentIndex, text) {
  const pre = el.detail.querySelector(".scrubbable-text"); if (!pre) return;
  pre.addEventListener("pointermove", (pointerEvent) => {
    const line = pointerEvent.target.closest(".scrub-line"); if (!line) return;
    const start = Number(line.dataset.start || 0); const end = Number(line.dataset.end || start);
    const bounds = line.getBoundingClientRect();
    const withinLine = Math.max(0, Math.min(1, (pointerEvent.clientX - bounds.left) / Math.max(1, bounds.width)));
    const charPosition = start + withinLine * Math.max(1, end - start);
    updateScrub(event, phase, segmentIndex, charPosition / Math.max(1, text.length), true);
  });
}
function updateReasoningCursor(ratio, shouldScroll) {
  const pre = el.detail.querySelector(".scrubbable-text"); if (!pre) return;
  const total = Number(pre.dataset.totalChars || 0); const target = ratio * Math.max(1, total);
  const lines = [...pre.querySelectorAll(".scrub-line")];
  const current = lines.find((line) => target <= Number(line.dataset.end || 0)) || lines[lines.length - 1];
  const prior = pre.querySelector(".scrub-line.at-marker");
  if (prior !== current) { prior?.classList.remove("at-marker"); current?.classList.add("at-marker"); }
  const status = el.detail.querySelector(".scrub-status");
  if (status) status.textContent = `${Math.round(ratio * 100)}% through captured ${PHASE_LABEL[state.activeScrub?.phase] || "phase"} text · character-weighted position`;
  if (shouldScroll && current && pre.dataset.activeLine !== current.dataset.start) {
    pre.dataset.activeLine = current.dataset.start;
    const nextTop = current.offsetTop - pre.clientHeight * .42;
    pre.scrollTop = Math.max(0, nextTop);
  }
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

async function renderDetail(event, selectedPhase = null, selectedSegmentIndex = null) {
  const request = ++state.detailRequest;
  if (!event) {
    el.detail.innerHTML = '<div class="detail-empty"><b>Reasoning inspector</b><span>Hover a colored phase to preview it. Move across either pane to scrub the same moment; click to pin.</span></div>'; return;
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
    const phaseGroups = [{ phase: "input", sections: inputSections }, ...groupAdjacentSections(generated)];
    const selectedGroup = phaseGroups[selectedSegmentIndex] || phaseGroups.find((group) => group.phase === selectedPhase);
    focus = selectedPhase ? formatSections(selectedGroup?.phase === selectedPhase ? selectedGroup.sections : generated.filter((section) => sectionPhase(section) === selectedPhase)) : "";
    link = `<a class="detail-link" href="./viewer.html#run=${encodeURIComponent(state.run)}&game=${event.gameIndex}">Open this game in the frame viewer →</a>`;
  }
  if (request !== state.detailRequest) return;
  const usage = event.usage || {};
  const badge = event.kind === "main_call" ? `<span class="badge ${exact ? "exact" : "reconstructed"}">${exact ? "exact input" : "reconstructed context"}</span>` : event.kind === "curator_synthesis" ? '<span class="badge reconstructed">exact call metadata + observed ledger</span>' : '<span class="badge exact">exact event log</span>';
  const phaseBadge = selectedPhase ? `<span class="phase-badge phase-${selectedPhase}">${escapeHtml(PHASE_LABEL[selectedPhase] || selectedPhase)}</span>` : "";
  const focusBody = focus || `(no ${PHASE_LABEL[selectedPhase] || selectedPhase || "selected"} text recorded for this span)`;
  const body = selectedPhase ? `<section class="focus-panel phase-border-${selectedPhase}"><h3>${escapeHtml(PHASE_LABEL[selectedPhase] || selectedPhase)} captured text</h3><div class="scrub-status">Move through this text to scrub the timeline marker</div><pre class="scrubbable-text" data-total-chars="${focusBody.length}">${scrubTextHtml(focusBody)}</pre></section>` : `<div class="io-grid"><section class="io-panel"><h3>Input / context</h3><pre>${escapeHtml(input || "(no input body recorded)")}</pre></section><section class="io-panel"><h3>Output / activity</h3><pre>${escapeHtml(output || "(no output body recorded)")}</pre></section></div>`;
  el.detail.innerHTML = `<div class="detail-wrap"><div class="detail-title"><h2>${escapeHtml(event.label)}</h2>${phaseBadge}${badge}</div>
    ${metaGrid([["Start", fmtDateTime(event.start)], ["Duration", event.instant ? "point event" : fmtDuration(event.durationSeconds ?? duration)], ["Span type", KIND_LABEL[event.kind] || event.kind], ["Status", event.status], ["Game", event.gameId], ["Prompt tokens", usage.promptTokens], ["Completion tokens", usage.completionTokens], ["Ledger revision", event.ledgerRevision ?? event.ledgerRevisionAfter], ["Evidence games", event.evidenceCount], ["Ledger entries", event.ledgerEntryCount]])}
    <div class="provenance-note${exact ? " exact" : ""}">${escapeHtml(provenance)}</div>${body}${link}${processTable(event)}</div>`;
  if (selectedPhase) {
    installReasoningScrubber(event, selectedPhase, selectedSegmentIndex, focusBody);
    const selected = state.pinned || state.preview;
    updateReasoningCursor(selected?.ratio ?? .5, true);
  }
}

function cancelClearPreview() { if (state.previewTimer) clearTimeout(state.previewTimer); state.previewTimer = null; }
function previewEvent(event, phase, segmentIndex, ratio = .5) {
  cancelClearPreview(); if (state.pinned) return;
  const changed = state.preview?.event?.id !== event.id || state.preview?.segmentIndex !== segmentIndex;
  state.preview = { event, phase, segmentIndex, ratio };
  updateScrub(event, phase, segmentIndex, ratio, false);
  if (changed) renderDetail(event, phase, segmentIndex);
}
function clearPreview() {
  cancelClearPreview(); if (state.pinned) return;
  state.preview = null; state.activeScrub = null;
  if (state.marker) state.marker.hidden = true;
  renderDetail(null);
}
function scheduleClearPreview() {
  if (state.pinned) return; cancelClearPreview();
  state.previewTimer = setTimeout(clearPreview, 900);
}
function pinEvent(event, phase, segmentIndex) {
  const ratio = state.activeScrub?.event?.id === event.id && state.activeScrub?.segmentIndex === segmentIndex ? state.activeScrub.ratio : .5;
  state.pinned = { event, phase, segmentIndex, ratio }; state.preview = null;
  renderTimeline(); renderDetail(event, phase, segmentIndex);
}

async function loadRun(run) {
  state.run = run; state.pinned = null; state.preview = null; state.activeScrub = null; state.zoom = 1; state.stepCache.clear();
  const [trace, overview] = await Promise.all([fetchRunTimeline(run), fetchRunOverview(run).catch(() => ({ games: [] }))]);
  state.trace = normalizeLegacyTrace(trace); state.overview = overview || { games: [] };
  state.gameById = new Map((state.overview.games || []).map((game) => [String(game.game_id), game]));
  setPalette(state.overview.arc_palette, state.overview.color_chars);
  document.title = `${run} — execution trace`; el.run.textContent = run; el.runSelect.value = run;
  renderStats(); renderTimeline(); renderDetail(null);
}

el.search.addEventListener("input", () => { state.search = el.search.value; renderTimeline(); });
el.scroll.addEventListener("wheel", handleTimelineZoom, { passive: false });
el.runSelect.addEventListener("change", () => { location.hash = `#run=${encodeURIComponent(el.runSelect.value)}`; });
el.detail.addEventListener("pointerenter", cancelClearPreview);
el.detail.addEventListener("pointerleave", scheduleClearPreview);
window.addEventListener("keydown", (event) => { if (event.key === "Escape" && state.pinned) { state.pinned = null; state.activeScrub = null; renderTimeline(); renderDetail(null); } });
window.addEventListener("hashchange", async () => { syncTabs(); await loadRun(hashRun()); });

syncTabs();
await populateRunSelect();
if (!hashRun() && el.runSelect.value) location.replace(`#run=${encodeURIComponent(el.runSelect.value)}`);
else await loadRun(hashRun() || el.runSelect.value);

// The decision panel: every LLM call of a turn -- reasoning, the python it ran, what came back.
//
// The raw transcript is a ~38KB wall of text. The backend already splits it into an ordered
// interleave of [THINKING] / [TOOL CALL: python] / [TOOL RESULT: python] / [ASSISTANT] sections,
// so the job here is ordering and triage: lead with what the model did, collapse what it was
// told, and diff the one part of the prompt that actually changes.

import { annotateCoordRefs, MODE } from "./coords.js";
import { paintThumb } from "./board.js?v=20260815-frames";

const NOISE = /^(MODEL CONTEXT|MODEL RESPONSE META|PROMPT LOG SNAPSHOT|ACTION_RESPONSE)$/i;
const IS_CODE = /^TOOL CALL/i;
const IS_SYSTEM = /^SYSTEM PROMPT$/i;
const IS_USER = /^USER PROMPT$/i;

// A per-type colour cue, keyed off the section label so it is finer than the
// backend `kind` (which lumps THINKING+ASSISTANT and TOOL CALL+TOOL RESULT).
// The `t-*` class picks the accent colour in app.css.
function typeClass(label) {
  const l = String(label || "").toUpperCase();
  if (l.startsWith("USER PROMPT")) return "t-user";        // green
  if (l.startsWith("SYSTEM PROMPT")) return "t-system";    // neutral
  if (l.startsWith("THINKING")) return "t-thinking";       // blue
  if (l.startsWith("ASSISTANT")) return "t-assistant";     // purple
  if (l.startsWith("TOOL CALL")) return "t-toolcall";      // orange
  if (l.startsWith("TOOL RESULT")) return "t-toolresult";  // amber
  if (l.startsWith("ERROR")) return "t-error";             // red
  return "";
}

export function renderDecision(root, step, { currentClick, previousStep, mode = "review" } = {}) {
  root.innerHTML = "";
  if (!step) {
    root.innerHTML = '<div class="empty">No analyzer turn for this frame.</div>';
    return;
  }

  root.appendChild(renderHead(step, currentClick));
  if (mode === "literal") {
    root.appendChild(renderLiteral(step));
    return;
  }
  root.appendChild(renderAbsorbedFrames(step));

  const sections = (step.localContext?.sections || []).filter((s) => !NOISE.test(s.label || ""));
  if (!sections.length) {
    root.insertAdjacentHTML("beforeend", '<div class="empty">No transcript for this turn.</div>');
    return;
  }

  // The transcript IS the conversation, so render it in order: prompt, think, call, result,
  // nag, think, call... Reordering it into buckets destroys the thing a reviewer is reading for.
  const previous = previousStep?.localContext?.sections || [];
  // Each user prompt is diffed against the one before it in the conversation -- which is exactly
  // the delta the model saw. The first of a turn diffs against the previous turn's last, so the
  // chain is unbroken across turn boundaries.
  let priorPrompt = lastContent(previous, "USER PROMPT");

  let call = 0;
  for (const section of sections) {
    if (IS_SYSTEM.test(section.label)) {
      const unchanged = normalize(lastContent(previous, "SYSTEM PROMPT")) === normalize(section.content);
      root.appendChild(renderSection(section, { open: false, note: unchanged ? "unchanged" : "" }));
      continue;
    }
    if (IS_USER.test(section.label)) {
      root.appendChild(renderPrompt(section, priorPrompt));
      priorPrompt = String(section.content || "");
      continue;
    }
    if (IS_CODE.test(section.label)) call += 1;
    root.appendChild(renderSection(section, { open: true, call: IS_CODE.test(section.label) ? call : 0 }));
  }

  root.appendChild(renderRaw(step));
}

function renderLiteral(step) {
  const wrap = document.createElement("section");
  wrap.className = "literal-trace";
  const modelContext = step.context || step.localContext || {};
  const exact = step.traceInputExact === true || modelContext.hasExactModelContext === true;
  const timestamp = String(step.traceTimestamp || "timestamp unavailable in this export");
  const basis = String(step.traceTimestampBasis || "no timestamp metadata");
  const source = exact ? "Exact saved request context" : "Stored transcript reconstruction";

  const notice = document.createElement("div");
  notice.className = `literal-notice ${exact ? "is-exact" : "is-reconstructed"}`;
  notice.innerHTML = `<b>${escapeHtml(source)}</b><span>${escapeHtml(timestamp)} · ${escapeHtml(basis)}</span>`;
  if (!exact) {
    notice.insertAdjacentHTML("beforeend", "<small>Section text is shown verbatim. Older TAAF runs did not save the exact request JSON, so input-context membership is inferred from the transcript.</small>");
  }
  wrap.appendChild(notice);

  const sections = modelContext.sections || [];
  if (!sections.length) {
    wrap.insertAdjacentHTML("beforeend", '<div class="empty">No stored model input/output for this turn.</div>');
    return wrap;
  }

  for (const section of sections) {
    const direction = literalDirection(section.label);
    const record = document.createElement("article");
    record.className = `literal-record is-${direction}`;
    const head = document.createElement("div");
    head.className = "literal-record-head";
    const contextTag = section.inContext === false
      ? (exact ? " · not present in captured request" : " · context carry not verified")
      : "";
    head.innerHTML = `<b>${escapeHtml(direction.toUpperCase())}</b><span>${escapeHtml(section.label || "SECTION")}${escapeHtml(contextTag)}</span><time>${escapeHtml(timestamp)}</time>`;
    const pre = document.createElement("pre");
    pre.textContent = String(section.content || "");
    record.append(head, pre);
    wrap.appendChild(record);
  }
  return wrap;
}

function literalDirection(label) {
  const value = String(label || "").toUpperCase();
  if (value === "SYSTEM PROMPT" || value === "USER PROMPT" || value.startsWith("TOOL RESULT")) return "input";
  if (value === "THINKING" || value === "ASSISTANT" || value === "OUTPUT" || value.startsWith("TOOL CALL")) return "output";
  return "trace";
}

function renderAbsorbedFrames(step) {
  const explicit = Array.isArray(step.absorbedFrames) ? step.absorbedFrames : [];
  const fallback = step.boardEvent ? [{
    label: "Current settled frame (attached to Qwen)",
    board: step.boardEvent.board,
    board_ascii: step.boardEvent.board_ascii,
  }] : [];
  const frames = explicit.length ? explicit : fallback;
  const section = document.createElement("section");
  section.className = "absorbed-frames";

  const heading = document.createElement("div");
  heading.className = "absorbed-frames-title";
  heading.textContent = "Frames Qwen received for this reasoning step";
  section.appendChild(heading);

  if (!frames.length) {
    section.insertAdjacentHTML("beforeend", '<div class="empty">Frame input was not recorded for this turn.</div>');
    return section;
  }

  const gallery = document.createElement("div");
  gallery.className = "absorbed-frames-gallery";
  for (const frame of frames) {
    const figure = document.createElement("figure");
    const canvas = document.createElement("canvas");
    const label = document.createElement("figcaption");
    label.textContent = frame.label || "Frame seen by model";
    figure.append(canvas, label);
    gallery.appendChild(figure);
    paintThumb(canvas, frame.board || frame.board_ascii, 3);
  }
  section.appendChild(gallery);
  return section;
}

function renderHead(step, currentClick) {
  const head = document.createElement("div");
  head.className = "decision-head";

  const title = document.createElement("div");
  title.className = "turn-title";
  title.textContent = step.title || "Turn";
  head.appendChild(title);

  const actions = String(step.actionDisplay || "").split("->").map((a) => a.trim()).filter(Boolean);
  if (actions.length) {
    const chips = document.createElement("div");
    chips.className = "chips";
    for (const action of actions) {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = action;
      if (currentClick && action.includes(`row=${currentClick.row}`) && action.includes(`col=${currentClick.col}`)) {
        chip.classList.add("current");
      }
      chips.appendChild(chip);
    }
    head.appendChild(chips);
    annotateCoordRefs(chips, MODE.PROSE);
  }

  const bits = [];
  if (step.reward) bits.push(`reward ${step.reward > 0 ? "+" : ""}${step.reward}`);
  bits.push(`score ${step.score ?? 0}`);
  bits.push(`level ${step.level ?? "?"}`);
  if (step.toolCallCount) bits.push(`${step.toolCallCount} tool calls`);
  if (step.attemptCount > 1) bits.push(`${step.attemptCount} attempts`);
  if (step.llm) {
    bits.push(`in ${fmtK(step.llm.promptTokens)} / out ${fmtK(step.llm.completionTokens)}`);
    if (step.llm.errors) bits.push(`${step.llm.errors} errors`);
  }
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = bits.join(" · ");
  head.appendChild(meta);

  return head;
}

function renderSection(section, { open, call = 0, note = "" }) {
  const label = section.label || "SECTION";
  const content = section.content || "";
  const details = document.createElement("details");
  details.className = `section kind-${section.kind || "text"} ${typeClass(label)}`.trim();
  details.open = open;
  details.appendChild(summaryFor(label, content.length, { call, note }));

  const pre = document.createElement("pre");
  pre.textContent = content;
  details.appendChild(pre);

  const annotate = () => annotateCoordRefs(pre, IS_CODE.test(label) ? MODE.CODE : MODE.PROSE);
  if (open) annotate();
  else details.addEventListener("toggle", () => details.open && annotate(), { once: true });
  return details;
}

/**
 * The user prompt is ~3KB of board state resent every turn. What a reviewer needs is the
 * delta, so highlight the changed lines and let the unchanged bulk collapse away.
 */
function renderPrompt(section, previousContent) {
  const lines = String(section.content || "").split("\n");
  const before = new Set(String(previousContent || "").split("\n"));
  const changed = previousContent ? lines.filter((line) => !before.has(line)).length : lines.length;

  const details = document.createElement("details");
  details.className = `section kind-meta ${typeClass(section.label)}`.trim();
  details.appendChild(
    summaryFor(section.label, section.content.length, {
      note: previousContent ? (changed ? `${changed} changed lines` : "unchanged") : "",
    }),
  );

  const render = () => {
    const pre = document.createElement("pre");
    pre.className = "prompt";
    for (const line of lines) {
      const row = document.createElement("div");
      row.className = previousContent && !before.has(line) ? "line changed" : "line";
      row.textContent = line || " ";
      pre.appendChild(row);
    }
    details.appendChild(pre);
    annotateCoordRefs(pre, MODE.PROSE);
  };
  // 3KB of DOM nobody reads until they open it.
  details.addEventListener("toggle", () => details.open && !details.querySelector("pre") && render(), { once: true });
  return details;
}

function renderRaw(step) {
  const sections = step.localContext?.sections || [];
  const raw = sections.map((s) => `[${s.label}]\n${s.content}`).join("\n\n");
  const details = document.createElement("details");
  details.className = "section kind-meta";
  details.appendChild(summaryFor("RAW TRANSCRIPT", raw.length, {}));
  details.addEventListener("toggle", () => {
    if (!details.open || details.querySelector("pre")) return;
    const pre = document.createElement("pre");
    pre.textContent = raw;
    details.appendChild(pre);
  }, { once: true });
  return details;
}

function summaryFor(label, size, { call = 0, note = "" }) {
  const summary = document.createElement("summary");
  const name = call ? `${label} #${call}` : label;
  summary.innerHTML =
    `<span>${escapeHtml(name)}</span><span class="spacer"></span>` +
    (note ? `<span class="note">${escapeHtml(note)}</span>` : "") +
    `<span class="size">${fmtBytes(size)}</span>`;
  return summary;
}

function lastContent(sections, label) {
  for (let i = sections.length - 1; i >= 0; i -= 1) {
    if (sections[i]?.label === label) return String(sections[i].content || "");
  }
  return "";
}

const normalize = (value) => String(value || "").replaceAll("\r\n", "\n").trimEnd();

function fmtK(value) {
  const n = Number(value || 0);
  return n >= 1000 ? `${(n / 1000).toFixed(1)}K` : String(n);
}

function fmtBytes(n) {
  return n >= 1024 ? `${(n / 1024).toFixed(1)} KB` : `${n} B`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

export { fmtK };

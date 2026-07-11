// The decision panel: what the model did this turn, and why.
//
// The raw transcript is a ~38KB wall of text. The backend already splits it into an ordered
// interleave of [TOOL CALL: python] / [TOOL RESULT: python] / [ASSISTANT] / [THINKING] sections,
// so the job here is ordering and triage: lead with the code the model ran, collapse the
// boilerplate it was told, and keep the raw blob one click away.

import { annotateCoordRefs, MODE } from "./coords.js";

const CODE_LABELS = /^TOOL CALL/i;
const RESULT_LABELS = /^TOOL RESULT/i;
const NOISE_LABELS = /^(MODEL CONTEXT|MODEL RESPONSE META|PROMPT LOG SNAPSHOT|ACTION_RESPONSE)$/i;

export function renderDecision(root, step, { currentClick } = {}) {
  root.innerHTML = "";
  if (!step) {
    root.innerHTML = '<div class="empty">Select a step.</div>';
    return;
  }

  root.appendChild(renderHead(step, currentClick));

  const sections = step.localContext?.sections || [];
  if (!sections.length) {
    root.insertAdjacentHTML("beforeend", '<div class="empty">No transcript for this step.</div>');
    return;
  }

  const shown = sections.filter((section) => !NOISE_LABELS.test(section.label || ""));
  const system = shown.filter((s) => /^SYSTEM PROMPT$/i.test(s.label));
  const user = shown.filter((s) => /^USER PROMPT$/i.test(s.label));
  const body = shown.filter((s) => !/^(SYSTEM|USER) PROMPT$/i.test(s.label));

  // What the model did, in the order it did it.
  for (const section of body) root.appendChild(renderSection(section, { open: true }));
  // What it was told. Boilerplate, so collapsed and rendered only when opened.
  for (const section of user) root.appendChild(renderSection(section, { open: false }));
  for (const section of system) root.appendChild(renderSection(section, { open: false }));
}

function renderHead(step, currentClick) {
  const head = document.createElement("div");
  head.className = "decision-head";

  const attempts = step.attemptCount > 1 ? ` · ${step.attemptCount} attempts` : "";
  const title = document.createElement("div");
  title.className = "turn-title";
  title.textContent = `${step.title || "Step"}${attempts}`;
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
  if (step.llm) {
    bits.push(`${step.llm.llmCalls} calls`);
    bits.push(`in ${fmtK(step.llm.promptTokens)} / out ${fmtK(step.llm.completionTokens)}`);
    if (step.llm.errors) bits.push(`${step.llm.errors} errors`);
  }
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = bits.join(" · ");
  head.appendChild(meta);

  return head;
}

function renderSection(section, { open }) {
  const label = section.label || "SECTION";
  const content = section.content || "";
  const isCode = CODE_LABELS.test(label);

  const details = document.createElement("details");
  details.className = `section kind-${section.kind || "text"}`;
  details.open = open;

  const summary = document.createElement("summary");
  summary.innerHTML = `<span>${escapeHtml(label)}</span><span class="spacer"></span><span class="size">${fmtBytes(content.length)}</span>`;
  details.appendChild(summary);

  const pre = document.createElement("pre");
  pre.textContent = content;
  details.appendChild(pre);

  const annotate = () => annotateCoordRefs(pre, isCode ? MODE.CODE : MODE.PROSE);
  if (open) annotate();
  else details.addEventListener("toggle", () => details.open && annotate(), { once: true });

  return details;
}

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

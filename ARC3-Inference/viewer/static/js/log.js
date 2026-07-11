// The event log: one row per frame, showing the action taken and whether it did anything.

import { annotateCoordRefs, MODE } from "./coords.js";

export class EventLog {
  constructor(tbody, { onSelect }) {
    this.tbody = tbody;
    this.onSelect = onSelect;
    this.rows = [];
    this.autoScroll = true;

    tbody.addEventListener("click", (event) => {
      // A coord-ref inside the row pins a cell; it must not also move the scrubber.
      if (event.target.closest(".coord-ref")) return;
      const tr = event.target.closest("tr");
      if (tr && tr.dataset.frame !== undefined) this.onSelect(Number(tr.dataset.frame));
    });
  }

  render(frames, steps) {
    // Append-only: a live run adds frames, it never rewrites the ones already drawn.
    if (frames.length < this.rows.length) {
      this.tbody.innerHTML = "";
      this.rows = [];
    }
    const stepByTurn = new Map((steps || []).map((step) => [step.analysisStep, step]));

    for (let i = this.rows.length; i < frames.length; i += 1) {
      const tr = this.buildRow(frames[i], stepByTurn.get(frames[i].analysis_step));
      this.tbody.appendChild(tr);
      this.rows.push(tr);
    }
  }

  buildRow(frame, step) {
    const tr = document.createElement("tr");
    tr.dataset.frame = String(frame.frameIndex);

    const isTurnStart = frame.type === "action" && frame.action_num !== undefined;
    const changed = frame.board_changed;
    const type = frame.type === "initial" ? "INI" : "ACT";

    // A no-op action is a strong signal that the agent is stuck, and nothing surfaces it today.
    const delta = frame.type === "action" ? (changed ? "●" : "·") : "";
    const deltaClass = frame.type === "action" && !changed ? "col-d nochange" : "col-d";

    tr.innerHTML = `
      <td class="col-n">${frame.action_num ?? 0}</td>
      <td class="col-ty">${type}</td>
      <td class="${deltaClass}">${delta}</td>
      <td class="col-what"></td>`;

    const what = tr.querySelector(".col-what");
    what.textContent = describe(frame, step);
    if (frame.analysis_step !== undefined && isTurnStart) tr.classList.add("is-turn");
    annotateCoordRefs(what, MODE.PROSE);
    return tr;
  }

  select(frameIndex) {
    for (const tr of this.rows) tr.classList.remove("selected");
    const tr = this.rows[frameIndex];
    if (!tr) return;
    tr.classList.add("selected");
    if (this.autoScroll) tr.scrollIntoView({ block: "nearest" });
  }
}

function describe(frame, step) {
  const action = frame.action_display || frame.title || "";
  const turn = frame.analysis_step !== undefined ? `T${frame.analysis_step} ` : "";
  const decision = firstCodeLine(step);
  return decision ? `${turn}${action}  ⟨${decision}⟩` : `${turn}${action}`;
}

/** The first substantive line of the python the model ran, so decisions are skimmable. */
function firstCodeLine(step) {
  const section = (step?.localContext?.sections || []).find((s) => /^TOOL CALL/i.test(s.label || ""));
  if (!section) return "";
  const line = String(section.content || "")
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l && !l.startsWith("#"));
  return line ? (line.length > 48 ? `${line.slice(0, 47)}…` : line) : "";
}

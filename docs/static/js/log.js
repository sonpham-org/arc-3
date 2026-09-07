// The event log: one row per action, showing what the model decided and whether it worked.

import { annotateCoordRefs, MODE } from "./coords.js";

export class EventLog {
  constructor(tbody, { onSelect }) {
    this.tbody = tbody;
    this.onSelect = onSelect;
    this.rows = [];
    this.autoScroll = true;
    this.turnGroups = new Map();
    this.pendingTurnSelection = null;

    tbody.addEventListener("click", (event) => {
      // A coord-ref inside the row pins a cell; it must not also move the scrubber.
      if (event.target.closest(".coord-ref")) return;
      const turnButton = event.target.closest(".turn-group");
      if (turnButton) {
        this.pendingTurnSelection = {
          frameIndex: Number(turnButton.dataset.frame),
          turn: turnButton.dataset.turn,
        };
        this.onSelect(Number(turnButton.dataset.frame));
        return;
      }
      const tr = event.target.closest("tr");
      if (tr && tr.dataset.frame !== undefined) this.onSelect(Number(tr.dataset.frame));
    });
  }

  render(frames, steps) {
    // Append-only: a live run adds frames, it never rewrites the ones already drawn.
    if (frames.length < this.rows.length) {
      this.tbody.innerHTML = "";
      this.rows = [];
      this.turnGroups.clear();
      this.pendingTurnSelection = null;
    }
    const stepByTurn = new Map((steps || []).map((step) => [step.analysisStep, step]));

    for (let i = this.rows.length; i < frames.length; i += 1) {
      const frame = frames[i];
      const step = stepByTurn.get(frame.analysis_step);
      // Only the first action of a turn gets the decision; the rest of the batch replays it.
      const hasTurn = frame.analysis_step !== undefined && frame.analysis_step !== null;
      const isTurnHead = hasTurn && frames[i - 1]?.analysis_step !== frame.analysis_step;
      const tr = this.buildRow(frame, step, isTurnHead);
      this.tbody.appendChild(tr);
      this.rows.push(tr);

      if (hasTurn) {
        const turnKey = String(frame.analysis_step);
        let group = this.turnGroups.get(turnKey);
        if (!group || isTurnHead) {
          const cell = tr.querySelector(".col-t");
          group = { cell, button: cell.querySelector(".turn-group"), rows: [], firstFrame: frame.frameIndex };
          this.turnGroups.set(turnKey, group);
        } else {
          group.cell.rowSpan += 1;
        }
        const previousLast = group.rows[group.rows.length - 1];
        if (previousLast) previousLast.classList.remove("turn-end");
        group.rows.push(tr);
        group.rows[0].classList.add("turn-start");
        tr.classList.add("turn-end");
        group.button.setAttribute(
          "aria-label",
          `Select turn T${frame.analysis_step} and its ${group.rows.length} action${group.rows.length === 1 ? "" : "s"}`,
        );
        group.button.title = `${group.rows.length} action${group.rows.length === 1 ? "" : "s"} in this turn`;
      }
    }
  }

  buildRow(frame, step, isTurnHead) {
    const tr = document.createElement("tr");
    tr.dataset.frame = String(frame.frameIndex);

    const type = frame.type === "initial" ? "INI" : "ACT";
    // A no-op action is a strong signal the agent is stuck, and nothing surfaced it before.
    const changed = frame.board_changed;
    const delta = frame.type === "action" ? (changed ? "●" : "·") : "";
    const deltaClass = frame.type === "action" && !changed ? "col-d nochange" : "col-d";
    const hasTurn = frame.analysis_step !== undefined && frame.analysis_step !== null;
    const turn = hasTurn ? `T${frame.analysis_step}` : "";
    const turnCell = isTurnHead
      ? `<td class="col-t"><button type="button" class="turn-group" data-turn="${frame.analysis_step}" data-frame="${frame.frameIndex}">${turn}</button></td>`
      : (!hasTurn ? '<td class="col-t"></td>' : "");

    tr.innerHTML = `
      <td class="col-n">${frame.action_num ?? 0}</td>
      ${turnCell}
      <td class="col-ty">${type}</td>
      <td class="${deltaClass}">${delta}</td>
      <td class="col-what"></td>`;

    const what = tr.querySelector(".col-what");
    const action = document.createElement("span");
    action.className = "act";
    action.textContent = frame.action_display || frame.title || "";
    what.appendChild(action);

    if (isTurnHead && step) {
      tr.classList.add("is-turn");
      if (step.decisionPreview) {
        const code = document.createElement("code");
        code.className = "decision";
        code.textContent = step.decisionPreview;
        what.appendChild(code);
      }
      const bits = [];
      if (step.toolCallCount) bits.push(`${step.toolCallCount} calls`);
      if (step.attemptCount > 1) bits.push(`${step.attemptCount} attempts`);
      if (step.errorCount) bits.push(`${step.errorCount} err`);
      if (bits.length) {
        const meta = document.createElement("span");
        meta.className = step.errorCount ? "llm-meta has-error" : "llm-meta";
        meta.textContent = bits.join(" · ");
        what.appendChild(meta);
      }
    }

    annotateCoordRefs(what, MODE.PROSE);
    return tr;
  }

  select(frameIndex) {
    for (const tr of this.rows) tr.classList.remove("selected", "selected-turn");
    const tr = this.rows[frameIndex];
    if (!tr) return;
    const pending = this.pendingTurnSelection;
    this.pendingTurnSelection = null;
    if (pending && pending.frameIndex === frameIndex) {
      const group = this.turnGroups.get(pending.turn);
      if (group) group.rows.forEach((row) => row.classList.add("selected-turn"));
      else tr.classList.add("selected");
    } else tr.classList.add("selected");
    if (this.autoScroll) tr.scrollIntoView({ block: "nearest" });
  }
}

# Author: Claude Opus 5.5 (Bubba)
# Date: 25-September-2026
# PURPOSE: Scoring-only labeller for the debate-four picks of OpenMind's rule-discovery agent (#arc-3, 25-Sep-2026 11:24 ET;
#   ~/bubba-workspace/docs/2026-09-25-warehouse-expert-debate-4.md). Plugged into his game_sweep with
#   --hook debate4_labels:make. Every measure of stage1_labels.Stage1Labels (and so of debate_labels.WarehouseLabels) is
#   kept exactly, so the random arm in results/game_sweep/dp_random/ stays comparable. New: the diagnostic join the debate
#   asked for (Round 6): each EFE check the agent logged (agent.check_log, keyed by the agent's own step counter) is marked
#   with whether the self stood at a GRAB POSITION (engine label: facing a free box, not holding) when the check was
#   evaluated, so the report can say how many checks happened at grab positions, what was compared there, and what won.
#   The join is made in before(): game_sweep calls it after agent.act() and before agent.observe(), so a check made during
#   this act() carries the agent's current n_steps. Game internals are read for LABELS only; the agent is read, never
#   written.
# SRP/DRY check: Pass -- all base measures are Stage1Labels' (subclassed, not copied); new: the check / grab join.
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "warehouse"))

from stage1_labels import Stage1Labels  # noqa: E402


def make(game: str):
    return Debate4Labels() if game == "wa30" else None


class Debate4Labels(Stage1Labels):
    def __init__(self):
        super().__init__()
        self.ptr = 0                              # next unread entry of agent.check_log
        self.checks: list = []                    # [agent step, labeller step, at grab position, won, action]
        self.grab_no_check = 0                    # grab positions where no check was evaluated

    def before(self, env, agent, action) -> None:
        super().before(env, agent, action)
        if agent is None:
            return
        log = getattr(agent, "check_log", None) or []
        if self.ptr > len(log):                   # a new play would reset the log; one labeller per play, so never
            self.ptr = 0
        seen = False
        while self.ptr < len(log):
            rec = log[self.ptr]
            if rec[0] != agent.n_steps:           # a check from an earlier step the loop somehow missed: keep order
                self.checks.append([rec[0], None, None, rec[2], rec[3]])
            else:
                self.checks.append([rec[0], self.n, bool(self.e0["facing_box"]), rec[2], rec[3]])
                seen = True
            self.ptr += 1
        if self.e0["facing_box"] and not seen:
            self.grab_no_check += 1

    def result(self) -> dict:
        out = super().result()
        at = [c for c in self.checks if c[2]]
        out["checks_total"] = len(self.checks)
        out["checks_unjoined"] = sum(c[2] is None for c in self.checks)
        out["checks_at_grab"] = len(at)
        won: dict = {}
        for c in self.checks:
            key = ("grab" if c[2] else "other") + ":" + str(c[3])
            won[key] = won.get(key, 0) + 1
        out["check_won"] = won
        out["check_at_grab_actions"] = {}
        for c in at:
            if c[4] is not None:
                out["check_at_grab_actions"][c[4]] = out["check_at_grab_actions"].get(c[4], 0) + 1
        out["grab_no_check"] = self.grab_no_check
        out["check_grab_steps"] = [c[1] for c in at][:60]
        return out

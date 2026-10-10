# Author: Claude Opus 5.5 (Bubba)
# Date: 25-September-2026
# PURPOSE: Debate five, pick 3 (docs 2026-09-25-openmind-agent-expert-debate-5.md, Round 3 / Round 7; OpenMind #arc-3
#   25-Sep-2026 17:14 ET): carry knowledge across the levels and restarts of ONE play.
#     - RuleLibrary: a small library of the rule sets that held (the posterior's top rule sets that beat the counts-only
#       hypothesis) when a level was cleared, a RESET was taken or a life was lost. Newest first, deduplicated, at most
#       max_sets sets; the library's rules are the union of those sets' rules (so it stays small).
#     - MDL reuse discount: beliefs.BeliefState.price asks discount(rs): a rule already in the library costs `reuse` x its
#       description length (a rule that explained the last level is cheap to encode on the next); anything new pays full
#       price. Applied inside price(), so the per-step re-pricing (refresh_dl) keeps it.
#     - seed(beliefs): after a level change or a restart the library's sets re-enter the posterior through
#       BeliefState.add_rulesets (exact prequential replay over the stored steps, so their weight is earned, not given);
#       a set pruned while the new level punished it comes back whenever the next event happens.
#     - temper_moves(selfm, n): on a level change the contingency self's learned moves are kept as a starting belief of at
#       most n presses per button (proportions kept), so the new level's evidence can overturn them within a few presses;
#       a RESET or a lost life (same level) keeps the full counts.
#   Scope: within one play only (a game over ends the play in game_sweep; nothing crosses plays or games, which kept seed
#   pairing and matched the earlier finding that a prior pooled from other plays hurt).
#   Wired in agent.py under AgentConfig.carry_library (off by default).
# SRP/DRY check: Pass -- rule sets, keys and description lengths are rules.RuleSet's; scoring by exact replay is
#   BeliefState.add_rulesets; the self's move counts are selfmodel.ContingentSelf.stats. New: the library, the discount
#   and the tempering.
"""Rule library with an MDL reuse discount; self / move carry-over across levels and restarts (one play)."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Optional

from .rules import DLContext, RuleSet


@dataclass
class LibraryConfig:
    reuse: float = 0.5          # a library rule's price = reuse x its description length (1 = no discount)
    max_sets: int = 6           # rule sets kept (newest first)
    top: int = 2                # posterior top rule sets considered at each snapshot
    min_weight: float = 0.1     # ... with at least this posterior weight (the MAP always qualifies)
    carry_n: int = 4            # presses per button the self's learned moves are worth on a new level


class RuleLibrary:
    def __init__(self, cfg: Optional[LibraryConfig] = None):
        self.cfg = cfg or LibraryConfig()
        self.sets: list = []                 # RuleSet, newest first
        self.rules: dict = {}                # rule key -> Rule (union of the sets' rules)
        self.events: list = []               # [step, why, rule sets stored, library size after]
        self.seeded = 0                      # rule sets re-entered into the posterior (new to it at that moment)

    # -- building
    def snapshot(self, beliefs, why: str, step: int) -> int:
        """Store the rule sets that hold now: the posterior's top sets (weight >= min_weight, the MAP always) that are not
        empty and score above the counts-only hypothesis."""
        empty_key = RuleSet.empty().key()
        base = next((h.log_score for h in beliefs.hyps if h.ruleset.key() == empty_key), None)
        stored = 0
        for i, (h, w) in enumerate(beliefs.top(self.cfg.top)):
            if len(h.ruleset) == 0 or (i > 0 and w < self.cfg.min_weight):
                continue
            if base is not None and h.log_score <= base:
                continue
            self._add(h.ruleset)
            stored += 1
        self.events.append([step, why, stored, len(self.sets)])
        return stored

    def _add(self, rs: RuleSet) -> None:
        k = rs.key()
        self.sets = [rs] + [s for s in self.sets if s.key() != k]
        self.sets = self.sets[: self.cfg.max_sets]
        self.rules = {r.key(): r for s in self.sets for r in s.rules()}

    # -- using
    def discount(self, rs: RuleSet, dlc: DLContext) -> float:
        """Nats taken off rs's description length: (1 - reuse) x the length of each of its rules already in the library."""
        if not self.rules:
            return 0.0
        return (1.0 - self.cfg.reuse) * sum(r.description_length(dlc) for r in rs.rules() if r.key() in self.rules)

    def seed(self, beliefs) -> int:
        """Re-enter the library's sets into the posterior (exact replay scoring); returns how many were new to it."""
        if not self.sets:
            return 0
        n = beliefs.add_rulesets(list(self.sets), origin="library")
        self.seeded += n
        return n

    def temper_moves(self, selfm) -> None:
        """New level: each button's learned displacement counts are scaled down to at most carry_n presses (proportions
        kept, every seen displacement keeps at least one count), a starting belief the new level can overturn."""
        if selfm is None:
            return
        n = self.cfg.carry_n
        for b, c in list(selfm.stats.items()):
            tot = sum(c.values())
            if tot <= n:
                continue
            selfm.stats[b] = Counter({d: max(1, round(k * n / tot)) for d, k in c.items()})

    def report(self) -> dict:
        return {"sets": len(self.sets), "rules": len(self.rules), "seeded": self.seeded, "events": self.events[:40],
                "described": [s.describe()[:6] for s in self.sets[:3]]}

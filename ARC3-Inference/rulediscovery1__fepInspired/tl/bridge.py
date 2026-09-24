# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Glue between the tensor-logic pieces and the agent (OpenMind, #arc-3, 24-Sep-2026 tensor-logic overhaul):
#     - make_tl(cfg): a TLState (relational perception, tl/relations.py) wired to a TLLearner (tl/learner.py); the
#       agent hands the state to rules.ContextBuilder (AgentConfig.use_tl).
#     - TLSource.propose(): re-fit the learner (warm start) and export its thresholded program as TLRules; called
#       by hypotheses.HypothesisProposer next to (or, with the templates off, instead of) the template fitter.
#     - TLSource.surprise(): a surprise spike runs the learner's structure test on the recent steps and records a
#       backward-chaining explanation.
#     - mover(): the controlled sprite's arrows and learned walls for explore.ObjectContactExplorer.
# SRP/DRY check: Pass -- only construction and delegation; every mechanism lives in tl/relations, tl/learner,
#   tl/rule.
"""Tensor-logic glue for the agent: state factory, rule source for the proposer, mover for the explorer."""
from __future__ import annotations

from typing import Optional

from .learner import TLConfig, TLLearner
from .relations import TLState


def make_tl(cfg: Optional[TLConfig] = None) -> TLState:
    return TLState(TLLearner(cfg))


class TLSource:
    def __init__(self, state: TLState):
        self.state = state
        self.learner = state.learner
        self.exported: list = []
        self.proposals = 0

    def propose(self) -> list:
        st = self.state
        if not self.learner.steps:
            return []
        self.learner.fit(vocab_size=len(st.vocab.effects))
        self.exported = self.learner.export(tuple(st.vocab.types), tuple(st.vocab.effects), frozenset(st.movable))
        self.proposals += 1
        return list(self.exported)

    def surprise(self, serial: int) -> None:
        self.learner.on_surprise(serial, len(self.state.vocab.effects))

    def mover(self, ctl: tuple) -> Optional[tuple]:
        st = self.state
        if not self.learner.fits:
            return None
        return self.learner.mover_model(ctl, int(ctl[0]), tuple(st.vocab.types), tuple(st.vocab.effects))

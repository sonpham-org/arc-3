# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Artificial curiosity for the rule discovery agent, asked by OpenMind in #arc-3
#   (23-Sep-2026 22:52 ET): "curiosity is missing ... picks actions which maximize entropy. Do source
#   entropy from EBUL ... take entropy from last EBUL layer as measurement to maximize."
#     - EBULMeter: a trained EBUL encoder (distill/ebul_perception.Encoder, two evolved tanh layers,
#       ternary code of the LAST layer) over 9x9 patches centred on every object of a board
#       (ebul_perception.patch_feat / object_centres). Whole-board EBUL codes were tried first and give
#       ONE code for every Locksmith board (the global 8x8-block feature cannot see a 5-pixel move), so
#       the percept is the set of last-layer patch codes. HUD cells (the agent's online mask) are painted
#       with the board's modal colour first, so a step bar cannot pose as novelty.
#       Entropy is measured exactly as EBUL measures it: ebul.gzip_bits of the ternary code matrix. The
#       play's history is the stack of every board's codes (sorted, one row per code); the curiosity
#       reward of a step is the entropy the new board adds: gzip_bits(history + new) - gzip_bits(history).
#       The encoder is trained on patches from OTHER games' traces only (never Locksmith, never the
#       held-out seven), then frozen and cached to results/ebul_patch_encoder.pkl.
#     - CuriosityDrive: expected entropy gain per (percept, action), learned from experience (running
#       mean; an untried pair is valued optimistically at the best mean seen plus a bonus, so the agent
#       tries it; with backoff, an untried pair falls back to that action's recent gain, an exponential
#       moving average, so "the direction that kept paying" carries over to new percepts). rechoose() re-weights the policy's decision: log p(a) + gain(a) / temperature, or
#       gain alone when pure=True. The agent calls it only when it is not following a plan.
# SRP/DRY check: Pass -- encoder, features, object centres and the entropy estimate are EBUL's own
#   (distill/ebul.py, distill/ebul_perception.py), imported through _distill; new here are the history
#   entropy gain, the per-(percept, action) value table and the re-weighting of the policy.
"""EBUL-entropy curiosity: act to maximise the entropy the next observation adds."""
from __future__ import annotations

import math
import pickle
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from . import _distill as D
from .perception import Action

ENCODER_CACHE = Path(__file__).parent / "results" / "ebul_patch_encoder.pkl"
EXCLUDE = ("ls20", "vc33", "ar25", "sb26", "re86", "su15", "tr87", "tu93", "as66")


def train_encoder(n_paths: int = 80, seed: int = 0):
    """EBUL patch encoder trained on other games' boards (not Locksmith, not the held-out seven)."""
    ep = D.ebul_perception()
    paths = [p for p in ep.trace_paths(301) if not any(g in Path(p).name for g in EXCLUDE)]
    rng = np.random.default_rng(seed)
    _, Xp = ep.training_sets(list(rng.permutation(paths)[:n_paths]), rng)
    return ep.Encoder(Xp, trained=True, seed=seed)


def load_encoder(retrain: bool = False):
    if ENCODER_CACHE.exists() and not retrain:
        D.ebul_perception()                       # makes ebul_perception importable for unpickling
        with open(ENCODER_CACHE, "rb") as fh:
            return pickle.load(fh)
    enc = train_encoder()
    ENCODER_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(ENCODER_CACHE, "wb") as fh:
        pickle.dump(enc, fh)
    return enc


class EBULMeter:
    """Last-layer EBUL patch codes of a board, and the gzip entropy of the play's code history."""

    def __init__(self, encoder):
        self.enc = encoder
        self.ep = D.ebul_perception()
        self.ebul = sys.modules["ebul"]
        self.rows: list[np.ndarray] = []          # history: one ternary row per (board, code)
        self.bits = 0.0

    def reset(self) -> None:
        self.rows, self.bits = [], 0.0

    def codes(self, grid, mask: Optional[np.ndarray] = None) -> np.ndarray:
        b = np.asarray(grid, dtype=int)
        if mask is not None and mask.any():
            b = b.copy()
            b[mask] = np.bincount(b[~mask].ravel()).argmax()
        board = b.tolist()
        centres = self.ep.object_centres(board)
        if not centres:
            return np.zeros((0, self.enc.layers[-1][2]), dtype=np.int8)
        T = self.enc.code_matrix(np.stack([self.ep.patch_feat(board, y, x) for y, x in centres]))
        return np.unique(T, axis=0)             # the set of codes, in a canonical order

    def gain(self, codes: np.ndarray) -> float:
        """Entropy (gzip bits of the last-layer code matrix) this board adds to the history; commits it."""
        if len(codes) == 0:
            return 0.0
        self.rows.append(codes)
        new = float(self.ebul.gzip_bits(np.concatenate(self.rows)))
        g, self.bits = new - self.bits, new
        return g


@dataclass
class CuriosityConfig:
    temperature: float = 4.0       # bits of expected gain worth one nat of policy log-probability
    optimism: float = 8.0          # bonus (bits) for an untried (percept, action) pair
    pure: bool = False             # ignore the EFE policy, act on curiosity alone
    backoff: bool = True           # untried pair -> this action's recent gain (EMA) instead of a flat prior
    ema: float = 0.3               # weight of the newest gain in the per-action recent mean


class CuriosityDrive:
    def __init__(self, encoder, cfg: Optional[CuriosityConfig] = None, seed: int = 0):
        self.meter = EBULMeter(encoder)
        self.cfg = cfg or CuriosityConfig()
        self.rng = np.random.default_rng(seed)
        self.sum: Counter = Counter()
        self.n: Counter = Counter()
        self.best_mean = 0.0
        self.percept = None
        self.rewards: list[float] = []
        self.recent: dict = {}         # action key -> exponential moving average of its entropy gain

    def start(self, grid, mask=None) -> None:
        self.meter.reset()
        self.sum.clear()
        self.n.clear()
        self.best_mean, self.rewards = 0.0, []
        self.recent = {}
        codes = self.meter.codes(grid, mask)
        self.meter.gain(codes)
        self.percept = codes.tobytes()

    @staticmethod
    def _akey(a: Action) -> tuple:
        return a.key()

    def value(self, a: Action) -> float:
        k = (self.percept, self._akey(a))
        if self.n[k] == 0:
            ak = self._akey(a)
            if self.cfg.backoff and ak in self.recent:
                return self.recent[ak] + self.cfg.optimism / 2
            return self.best_mean + self.cfg.optimism
        return self.sum[k] / self.n[k]

    def observe(self, action: Action, grid, mask=None) -> float:
        codes = self.meter.codes(grid, mask)
        r = self.meter.gain(codes)
        k = (self.percept, self._akey(action))
        self.sum[k] += r
        self.n[k] += 1
        self.best_mean = max(self.best_mean, self.sum[k] / self.n[k])
        ak = self._akey(action)
        self.recent[ak] = r if ak not in self.recent else (1 - self.cfg.ema) * self.recent[ak] + self.cfg.ema * r
        self.percept = codes.tobytes()
        self.rewards.append(r)
        return r

    def rechoose(self, decision):
        """Re-weight the policy's scored actions by expected entropy gain; sample the result."""
        scores = decision.scores
        if not scores:
            return decision
        logits = []
        for s in scores:
            base = 0.0 if self.cfg.pure else s.log_p
            logits.append(base + self.value(s.action) / self.cfg.temperature)
        m = max(logits)
        p = np.exp(np.array(logits) - m)
        p /= p.sum()
        i = int(self.rng.choice(len(scores), p=p))
        decision.action = scores[i].action
        decision.mode = "curious" if self.cfg.pure else decision.mode + "+curious"
        return decision

# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: HDC integration A/B (OpenMind, #arc-3, 24-Sep-2026 10:17 ET: "integrate the phasor vector / fractional
#   power / hyperdimensional pieces into the agent wherever they fit, compare with and without"). The online state
#   of the three soft-computing pieces, kept by rules.ContextBuilder when AgentConfig.use_hdc is on, and handed to
#   the rules as FROZEN per-step values inside RuleContext (so beliefs.PredictionCache and the exact replay that
#   scores late hypotheses and runs model reduction stay exact: a rule never reads live state).
#     - GhostTape (hdc/stage3_synth.GhostFinder via hdc/stage4_real.MultiRunFinder): per level, one phasor tape per
#       earlier run of the player (a run ends when the player jumps back to its level-start position without a
#       RESET); every other tracked object is scored against "repeats run k at lag L on clock c". Once an object is
#       explained, the context carries (its component id, the tape's next move, the clock); rules.TapeRule turns
#       that into a predicted move event. Moves are cleaned up against the player's own displacements this level.
#     - WallMap (soft/a3_walls.SoftWalls' encoding): fractional-power place code x colour code, one memory vector
#       M = BLOCKED - FREE learned from the controlled sprite's arrow presses (the "ahead" strip of the move, and
#       whether the sprite moved). WallView is an immutable snapshot for one step: score(cells) = sim(M, query)
#       (> 0 leans blocked), verdict() abstains below the margin TAU, score_map() gives the per-cell score for the
#       explorer's search (the query is linear, so a strip's score is the mean of its cells' scores).
#     - Fate (soft/a1_common_fate.CommonFate, revocable: decay FATE_DECAY): instance-level common-fate grouping;
#       the context carries {component id: partner component ids} for the rules' sprite (rules.FATE group) and the
#       explorer. It also supplies the tracker the tape uses, so the board is tracked once.
#   The engine is never read: everything comes from the agent's own Scene, its controlled-type estimate and the
#   agency tracker's button displacements.
# SRP/DRY check: Pass -- vectors from hdc/vsa.py, tapes/finder from hdc/stage2-4, the wall encoding constants from
#   soft/a3_walls.py, common fate from soft/a1_common_fate.py. New here: the per-step snapshots, the live rewind /
#   run bookkeeping on the agent's Scene, and the per-cell score map.
"""Online HDC / soft-computing state for the rule agent (tape rule, soft wall map, common fate)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from ._distill import ag, oe
from .hdc.stage4_real import MAX_JUMP, MultiRunFinder
from .hdc.vsa import VSA
from .soft.a1_common_fate import CommonFate
from .soft.a3_walls import SCALE, W_COLOUR

PIECES = ("tape", "walls", "fate")


@dataclass
class HdcConfig:
    pieces: tuple = PIECES
    dim: int = 2048              # stage 2: exact read-back to length ~200 at 1024-4096
    tau: float = 0.05            # wall-map abstention margin (a3 guards: flat between 0.02 and 0.2)
    fate_decay: float = 0.8      # revocable fusion (a1: 0.5 never fuses; 0.7-0.9 behave alike)


# ---------------------------------------------------------------- soft wall map

class WallMap:
    def __init__(self, vsa: VSA):
        self.v = vsa
        self.thy = np.angle(vsa.Y) * SCALE
        self.thx = np.angle(vsa.X) * SCALE
        self.M = np.zeros(vsa.D, complex)
        self.codes: dict = {}
        self.n = 0

    def code(self, c: int) -> np.ndarray:
        """Colour code, seeded by the colour itself (the same in every snapshot, whatever order colours appear)."""
        if c not in self.codes:
            self.codes[c] = np.exp(1j * np.random.default_rng(10_000 + int(c)).uniform(-np.pi, np.pi, self.v.D))
        return self.codes[c]

    def query(self, ys, xs, cols) -> np.ndarray:
        P = np.exp(1j * (np.outer(ys, self.thy) + np.outer(xs, self.thx)))
        C = np.stack([self.code(c) for c in cols])
        return (P * (1 + C) + W_COLOUR * C).mean(axis=0)

    def store(self, ys, xs, cols, blocked: bool) -> None:
        q = self.query(ys, xs, cols)
        self.M = self.M + q if blocked else self.M - q      # a new array: older snapshots keep theirs
        self.n += 1

    def view(self, tau: float) -> Optional["WallView"]:
        return WallView(self, self.M, tau) if self.n else None


class WallView:
    """The wall map as it stood before one step (immutable)."""

    def __init__(self, wm: WallMap, M: np.ndarray, tau: float):
        self.wm, self.M, self.tau = wm, M, tau
        self._map = None
        self._memo: dict = {}             # (part ids, dy, dx) -> verdict: rules ask the same strip many times

    def verdict_for(self, key, cells_fn) -> Optional[bool]:
        if key not in self._memo:
            self._memo[key] = self.verdict(*cells_fn())
        return self._memo[key]

    def score(self, ys, xs, cols) -> Optional[float]:
        if len(ys) == 0:
            return None
        q = self.wm.query(ys, xs, cols)
        return float(np.real(np.sum(self.M * np.conj(q))) / self.wm.v.D)

    def verdict(self, ys, xs, cols) -> Optional[bool]:
        """True = blocked, False = free, None = abstain (no cells or |score| < tau)."""
        s = self.score(ys, xs, cols)
        if s is None or abs(s) < self.tau:
            return None
        return s > 0

    def score_map(self, arr: np.ndarray) -> np.ndarray:
        """Per-cell score for every board cell with its own colour (memoised; arr is the board it is asked on)."""
        if self._map is not None and self._map[0] is arr:
            return self._map[1]
        h, w = arr.shape
        D = self.wm.v.D
        Ey = np.exp(-1j * np.outer(np.arange(h), self.wm.thy))          # h x D
        Ex = np.exp(-1j * np.outer(self.wm.thx, np.arange(w)))          # D x w
        out = np.zeros((h, w))
        for c in np.unique(arr):
            C = self.wm.code(int(c))
            with np.errstate(all="ignore"):       # Accelerate's complex matmul raises spurious FP flags
                g = np.real(Ey @ ((self.M * np.conj(1 + C))[:, None] * Ex)) / D
            g += W_COLOUR * float(np.real(np.sum(self.M * np.conj(C)))) / D
            m = arr == c
            out[m] = g[m]
        self._map = (arr, out)
        return out


def ahead_cells(scene, comps, dy: int, dx: int):
    """The cells the sprite (comps) would move into, minus its own cells, with their colours: the strip the wall
    map is asked about. The displacement is capped like agency_contexts.look_ahead. Off-board cells dropped."""
    s = max(abs(dy), abs(dx))
    if s > ag.MAX_LOOK:
        dy, dx = round(dy * ag.MAX_LOOK / s), round(dx * ag.MAX_LOOK / s)
    pa = scene.comps
    h, w = pa.arr.shape
    own = [c.id for c in comps]
    ys_l, xs_l = [], []
    for c in comps:
        ys, xs = scene.cells(c)
        ys_l.append(ys + dy)
        xs_l.append(xs + dx)
    ys, xs = np.concatenate(ys_l), np.concatenate(xs_l)
    ok = (ys >= 0) & (ys < h) & (xs >= 0) & (xs < w)
    ys, xs = ys[ok], xs[ok]
    keep = ~np.isin(pa.lab[ys, xs], own)
    ys, xs = ys[keep], xs[keep]
    cols = pa.arr[ys, xs]
    keep = cols != oe.MASKED
    return ys[keep], xs[keep], [int(c) for c in cols[keep]]


# ---------------------------------------------------------------- ghost tape

class GhostTape:
    """Stage-4 run bookkeeping on the agent's own tracker (the Fate tracker)."""

    def __init__(self, vsa: VSA):
        self.v = vsa
        self.new_level()

    def new_level(self) -> None:
        self.finder = MultiRunFinder(self.v, [])
        self.start = None
        self.moves = {(0, 0)}
        self.pred = None

    @staticmethod
    def player_pos(tracker, ptype):
        pos = tracker.positions_of(ptype) if ptype is not None else []
        return pos[0] if len(pos) == 1 else None

    def observe(self, tracker, mv: dict, before, ptype, exclude: set) -> None:
        """mv: track -> move this step (tracker already updated); before: the player's position before it."""
        after = self.player_pos(tracker, ptype)
        if self.start is None:
            self.start = before or after
        if before is None or after is None:
            self.pred = None
            return
        pmove = (after[0] - before[0], after[1] - before[1])
        if after == self.start and before != self.start and abs(pmove[0]) + abs(pmove[1]) > MAX_JUMP:
            self.finder.rewind()                  # the run ended: its moves become a tape a ghost may repeat
            self.pred = None
            return
        others = {t: d for t, d in mv.items() if tracker.tracks[t][0] != ptype and t not in exclude}
        self.finder.add_objects(list(others))
        pm = pmove if abs(pmove[0]) + abs(pmove[1]) <= MAX_JUMP else (0, 0)
        if pm != (0, 0):
            self.moves.add(pm)
        self.finder.observe(pm, others)
        self.pred = self._predict(tracker)

    def _predict(self, tracker) -> Optional[tuple]:
        """(component id, dy, dx, clock) for the next step, from the first object explained as a copy of an
        earlier run, or None. The move is the tape read-out cleaned up against the player's moves this level."""
        for o, (key, _) in self.finder.decided.items():
            if not key[1].startswith("prev"):
                continue
            comp = tracker.comp_of.get(o)
            h = next((h for h in self.finder.hyps if h.key() == key), None)
            if comp is None or h is None:
                continue
            p = self.finder.predict(h, True)
            if p is None:
                continue
            book = sorted(self.moves)
            dy, dx = book[self.v.cleanup(p, np.stack([self.v.move(*m) for m in book]))]
            return (comp.id, int(dy), int(dx), key[2])
        return None


# ---------------------------------------------------------------- the state ContextBuilder keeps

class HdcState:
    def __init__(self, cfg: Optional[HdcConfig] = None):
        self.cfg = cfg or HdcConfig()
        on = set(self.cfg.pieces)
        self.vsa = VSA(self.cfg.dim, seed=0)
        self.fate = CommonFate(self.cfg.fate_decay)
        self.tape = GhostTape(self.vsa) if "tape" in on else None
        self.walls = WallMap(self.vsa) if "walls" in on else None
        self.use_fate = "fate" in on
        self.scene = None
        self.annot: dict = {}

    def begin(self, scene) -> None:
        self.fate.update_objects(scene.objects(), None)
        self.scene = scene
        self.annot = self._annotate(scene)

    def annotate(self, scene) -> dict:
        """RuleContext fields for a context built on `scene`: only the board the agent is actually on gets
        them (imagined boards in the planner get none, so no rule reads a stale ghost or partner id there)."""
        return self.annot if scene is self.scene else {}

    def partners(self, scene) -> dict:
        """{component id: partner component ids} of the fused groups on this (current) board."""
        find = self.fate.groups()
        by: dict = {}
        for t, c in self.fate.tr.comp_of.items():
            by.setdefault(find(t), []).append(c.id)
        out = {}
        for ids in by.values():
            if len(ids) > 1:
                for i in ids:
                    out[i] = tuple(j for j in ids if j != i)
        return out

    def _annotate(self, scene) -> dict:
        fate = self.partners(scene)
        self._fate_now = fate
        out = {}
        if self.use_fate:
            out["fate"] = fate
        if self.walls is not None:
            out["walls"] = self.walls.view(self.cfg.tau)
        if self.tape is not None:
            out["tape"] = self.tape.pred
        return out

    def observe(self, tr, ptype, direction) -> None:
        """One finished step (call before the play history advances). direction(button) -> (dy, dx) or None."""
        pre = self.scene if self.scene is not None else tr.pre
        if self.walls is not None and not tr.reset and not tr.terminal and tr.action.is_button and ptype is not None:
            d = direction(tr.action.name)
            inst = [c for c in pre.objects() if c.type_key == ptype]
            if d is not None and len(inst) == 1:
                comp = inst[0]
                ids = set(getattr(self, "_fate_now", {}).get(comp.id, ()))
                parts = [comp] + [c for c in pre.objects() if c.id in ids]
                ys, xs, cols = ahead_cells(pre, parts, d[0], d[1])
                if len(ys):
                    moved = any(k == ptype and (dy, dx) != (0, 0) for k, dy, dx in tr.moves)
                    self.walls.store(ys, xs, cols, blocked=not moved)
        post = tr.post
        if post is None:
            return
        tracker = self.fate.tr
        before = GhostTape.player_pos(tracker, ptype)
        self.fate.update_objects(post.objects(), None)
        if self.tape is not None:
            if tr.reset or tr.level_completed:
                self.tape.new_level()
                self.tape.start = GhostTape.player_pos(tracker, ptype)
            else:
                find = self.fate.groups()
                pt = [t for t, (k, _) in tracker.tracks.items() if k == ptype]
                exclude = {t for t in tracker.tracks if pt and find(t) == find(pt[0])}
                self.tape.observe(tracker, self.fate.last_moves, before, ptype, exclude)
        self.scene = post
        self.annot = self._annotate(post)

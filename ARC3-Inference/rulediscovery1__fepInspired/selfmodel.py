# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Debate pick 1 (docs 2026-09-24-warehouse-expert-debate.md, OpenMind #arc-3 22:49 ET): a CONTINGENCY-based
#   self. "Self" = what the agent's own actions predictably change, not a fixed colour + shape, so the self survives a
#   sprite that redraws itself when it turns (Warehouse: the facing strip jumps to another side of the body, both parts
#   change shape, and the type-keyed agency tracker loses the player on every turn).
#     - Seed: distill/agency_contexts.AgencyTracker (N * I(button; displacement) over object types, the existing
#       contingency test) names one controlled type; its instance on the board starts the self.
#     - Self colours, pooled over time: on every step where the self moved (D != 0), each colour that travelled with it
#       is counted: present inside the self's box before and inside the box shifted by D after (so a part redrawn in a
#       new shape on a turn counts), or touching it before and after while its old cells did not stay put (a part not
#       yet known to be self; a wall, wire or floor patch the self walks along stays put). A colour belongs to the self
#       when it travelled with it on at least half of the self's moves (and twice): the soft membership (weight =
#       share) thresholded at one half, the colour-level "soft mask of action-explained change".
#     - Tracking by location, not by shape: after a step the self's displacement D is the shift (among no-move, the
#       learned button displacements, the matched moves and the self-colour union-box shift) that re-finds the most
#       self-coloured cells at the self's old cells shifted by D. The self's parts on the new board are the self-colour
#       components under those shifted cells (a part that merges with something it grabbed comes along; a part that
#       changes to a non-self colour drops out), plus self-colour parts touching them (a part redrawn beside the old
#       cells). If less than half the cells are re-found the self is re-acquired: from the tracker's seed type if it is
#       on the board, else from the self-colour part nearest the last known self box, else (after a RESET moved it) the
#       board's cluster of touching self-colour parts with the self's colour set and the size nearest the self's.
#     - Per button: counts of D (the modal non-zero D is the button's learned move), and the colours ahead of the self
#       when a press moved it (passable) or not (blocked): a mover model for the explorer.
#     - Facing: the learned move of the last pressed button that has one, with confidence = that button's share of
#       presses giving its modal move; pick 2 uses it as the soft "ahead of me" relation.
#   Frames are per board (the live board and the previous one), so rules.ContextBuilder can freeze the self's part ids
#   into each step's RuleContext (exact replay stays exact). Nothing here reads game internals.
# SRP/DRY check: Pass -- the contingency seed is agency_contexts' tracker, look-ahead is rules.group_look_ahead, the
#   board and components are perception.Scene's. New: location tracking of a multi-part self, colour pooling, the
#   per-button mover/blocker tallies and facing.
"""Contingency-based self: the parts the agent's actions move, tracked by location through reshaping."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class SelfConfig:
    min_share: float = 0.5      # a colour is self when it co-moved with the self on at least this share of self moves
    min_count: int = 2          # ... and at least this many times
    min_keep: float = 0.5       # tracking: the chosen shift must re-find at least this share of the self's cells
    max_growth: float = 4.0     # acquisition: the grown cluster may not exceed this many times the seed's cells
    look: int = 8               # union-box search radius around the old self box (pixels), grown with learned steps


@dataclass
class SelfFrame:
    """The self on one board: component ids, their cells, the union box and the anchor (largest part)."""
    scene: object
    ids: frozenset
    ys: np.ndarray
    xs: np.ndarray
    box: tuple                   # (y0, x0, y1, x1)
    anchor: object               # oe.Comp


def _box_of(comps) -> tuple:
    return (min(c.y0 for c in comps), min(c.x0 for c in comps), max(c.y1 for c in comps), max(c.x1 for c in comps))


class ContingentSelf:
    def __init__(self, cfg: Optional[SelfConfig] = None):
        self.cfg = cfg or SelfConfig()
        self.comoved: Counter = Counter()       # colour -> self moves on which that colour moved by the same shift
        self.moved_steps = 0
        self.seed_colours: set = set()
        self.stats: dict = defaultdict(Counter)   # button -> Counter(D)
        self.passed: Counter = Counter()          # colour ahead when a press moved the self
        self.blocked: Counter = Counter()         # colour ahead when a press with a learned move did not move it
        self.cur: Optional[SelfFrame] = None
        self.prev: Optional[SelfFrame] = None
        self.facing_button: Optional[str] = None
        self.last_delta: Optional[tuple] = None   # D of the last observed step (None: self unknown there)
        self.base_cells: Optional[int] = None
        self.last_box: Optional[tuple] = None     # where the self was last seen (for re-acquisition by location)
        self.base_colours: frozenset = frozenset()  # the colours of the self when it was seen whole
        self.n_lost = 0
        self.n_acquired = 0
        self.n_tracked = 0

    # -- learned quantities
    def colours(self) -> set:
        n = self.moved_steps
        out = {c for c, k in self.comoved.items()
               if k >= self.cfg.min_count and k >= self.cfg.min_share * n}
        return out | self.seed_colours

    def direction(self, button: str) -> Optional[tuple]:
        c = Counter({d: n for d, n in self.stats.get(button, Counter()).items() if d != (0, 0)})
        if not c:
            return None
        return c.most_common(1)[0][0]

    def dirs(self) -> dict:
        return {b: d for b in sorted(self.stats) for d in [self.direction(b)] if d is not None}

    def facing(self) -> Optional[tuple]:
        """(dy, dx, confidence) of the last pressed button that has a learned move, or None."""
        b = self.facing_button
        if b is None:
            return None
        d = self.direction(b)
        if d is None:
            return None
        nz = sum(n for dd, n in self.stats[b].items() if dd != (0, 0))
        return (d[0], d[1], round(self.stats[b][d] / max(nz, 1), 3))

    def mover(self) -> Optional[tuple]:
        """({button: (dy, dx)}, blocker colours, passable colours) or None before any learned move."""
        moves = self.dirs()
        if not moves:
            return None
        passable = {c for c, n in self.passed.items() if n > 0}
        blockers = {c for c, n in self.blocked.items() if n > 0} - passable
        return moves, blockers, passable

    # -- frames
    def frame(self, scene) -> Optional[SelfFrame]:
        """The self on `scene` (the live board or the one before it); None for any other (imagined) board."""
        for f in (self.cur, self.prev):
            if f is None:
                continue
            if f.scene is scene:
                return f
            if f.scene.raw is scene.raw:              # the same board re-described under a new HUD mask
                return self._frame_at(scene, f.ys, f.xs)
        return None

    def _frame_at(self, scene, ys, xs) -> Optional[SelfFrame]:
        """Self parts on `scene` = self-colour, non-background components under the cells (ys, xs)."""
        h, w = scene.shape
        ok = (ys >= 0) & (ys < h) & (xs >= 0) & (xs < w)
        ys, xs = ys[ok], xs[ok]
        if ys.size == 0:
            return None
        cols = self.colours()
        pa = scene.comps
        ids = {int(v) for v in np.unique(pa.lab[ys, xs]) if v}
        parts = [pa.comps[i - 1] for i in sorted(ids)]
        parts = [c for c in parts if not c.bg and c.colour != pa.mode and c.colour in cols]
        if not parts:
            return None
        return self._make(scene, parts)

    @staticmethod
    def _make(scene, parts) -> SelfFrame:
        cy, cx = [], []
        for c in parts:
            yy, xx = scene.cells(c)
            cy.append(yy)
            cx.append(xx)
        anchor = max(parts, key=lambda c: (c.size, -c.id))
        return SelfFrame(scene, frozenset(c.id for c in parts), np.concatenate(cy), np.concatenate(cx),
                         _box_of(parts), anchor)

    def acquire(self, scene, tracker) -> Optional[SelfFrame]:
        """Re-find the self: the tracker's seed type on the board (nearest the last known box), else a self-colour part
        near the last known box, else the board's cluster of touching self-colour parts that has the self's colour
        set and the size nearest the self's; then grow over touching self-colour parts."""
        k = tracker.controlled() if tracker is not None else None
        if k is None or scene is None:
            return None
        self.seed_colours.add(int(k[0]))
        cols = self.colours()
        ref = self.last_box
        inst = scene.by_type().get(k, [])
        if not inst and ref is not None:             # the seed shape is not on the board (redrawn): go by location
            r = max([self.cfg.look] + [2 * max(abs(d[0]), abs(d[1])) for d in self.dirs().values()])
            inst = [c for c in scene.objects() if c.colour in cols and c.y0 <= ref[2] + r and c.y1 >= ref[0] - r
                    and c.x0 <= ref[3] + r and c.x1 >= ref[1] - r]
        if inst:
            if len(inst) > 1:
                if ref is None:
                    return None
                inst = [min(inst, key=lambda c: abs(c.y0 - ref[0]) + abs(c.x0 - ref[1]))]
            parts = self._grow(scene, [inst[0]], cols)
        else:
            parts = self._by_shape(scene, cols)
            if parts is None:
                return None
        self.n_acquired += 1
        f = self._make(scene, parts)
        if self.base_cells is None:
            self.base_cells = int(f.ys.size)
        if len({c.colour for c in parts}) >= len(self.base_colours):
            self.base_colours = frozenset(c.colour for c in parts)
        self.last_box = f.box
        return f

    def _grow(self, scene, parts: list, cols: set) -> list:
        """Add self-colour parts that touch the cluster (box gap <= 1), up to max_growth x the self's size."""
        parts = list(parts)
        have = {c.id for c in parts}
        cap = self.cfg.max_growth * max(sum(c.size for c in parts), self.base_cells or 0)
        objs = [c for c in scene.objects() if c.colour in cols and c.id not in have]
        grew = True
        while grew:
            grew = False
            b = _box_of(parts)
            for c in objs:
                if c.id in have:
                    continue
                if c.y0 <= b[2] + 1 and b[0] <= c.y1 + 1 and c.x0 <= b[3] + 1 and b[1] <= c.x1 + 1:
                    if sum(p.size for p in parts) + c.size <= cap:
                        parts.append(c)
                        have.add(c.id)
                        grew = True
        return parts

    def _by_shape(self, scene, cols: set) -> Optional[list]:
        """The cluster of touching self-colour parts with the self's full colour set, size nearest the self's."""
        if self.base_cells is None or len(self.base_colours) < 2:
            return None
        objs = [c for c in scene.objects() if c.colour in cols]
        seen, best, best_d = set(), None, None
        for c in objs:
            if c.id in seen:
                continue
            cl = self._grow(scene, [c], cols)
            seen |= {x.id for x in cl}
            if not self.base_colours <= {x.colour for x in cl}:
                continue
            dist = abs(sum(x.size for x in cl) - self.base_cells)
            if best_d is None or dist < best_d:
                best, best_d = cl, dist
        return best

    # -- one finished step
    def observe(self, tr, tracker) -> None:
        post = tr.post
        f_pre = self.frame(tr.pre) if tr.pre is not None else None
        self.last_delta = None
        if tr.reset or tr.level_completed or post is None:
            self.prev, self.cur = self.cur, (self.acquire(post, tracker) if post is not None else None)
            return
        if f_pre is None:
            self.prev, self.cur = self.cur, self.acquire(post, tracker)
            return
        cols = self.colours()
        d, score = self._shift(tr, f_pre, cols)
        if score < self.cfg.min_keep * f_pre.ys.size:
            self.n_lost += 1
            self.prev, self.cur = self.cur, self.acquire(post, tracker)
            return
        f_post = self._frame_at(post, f_pre.ys + d[0], f_pre.xs + d[1])
        if f_post is None:
            self.n_lost += 1
            self.prev, self.cur = self.cur, self.acquire(post, tracker)
            return
        parts = [post.comps.comps[i - 1] for i in sorted(f_post.ids)]
        grown = self._grow(post, parts, cols)          # a part redrawn beside the old cells (a strip that jumped sides)
        if len(grown) > len(parts):
            f_post = self._make(post, grown)
        if len({c.colour for c in grown}) > len(self.base_colours):
            self.base_colours = frozenset(c.colour for c in grown)
        self.n_tracked += 1
        self.last_delta = d
        a = tr.action
        if a.is_button:
            learned = self.direction(a.name)          # before this press is counted
            self.stats[a.name][d] += 1
            if learned is not None:
                from .rules import group_look_ahead
                pre_parts = [tr.pre.comps.comps[i - 1] for i in sorted(f_pre.ids)]
                la = group_look_ahead(tr.pre, pre_parts, learned)
                if len(la) > 1:
                    if d == learned:
                        self.passed[la[1]] += 1
                    elif d == (0, 0):
                        self.blocked[la[1]] += 1
            if self.direction(a.name) is not None:
                self.facing_button = a.name
        if d != (0, 0):
            self.moved_steps += 1
            for c in self._comoved_colours(tr.pre, post, f_pre.box, d):
                self.comoved[c] += 1
        self.prev, self.cur = self.cur, f_post
        self.last_box = f_post.box

    @staticmethod
    def _comoved_colours(pre, post, box, d) -> set:
        """Colours that travelled with the self on a move by d: inside the self's box before AND inside the shifted box
        after (a part redrawn in a new shape on a turn still counts), or touching the self's box before AND touching
        the shifted box after while their old cells did not stay put (a part not yet known to be self; a wall, a wire
        or a floor patch the self walks along stays put, so it does not count)."""
        a, b = pre.comps.arr, post.comps.arr
        h, w = a.shape
        mode = pre.comps.mode

        def sub(arr, y0, x0, y1, x1):
            return arr[max(y0, 0):max(min(y1 + 1, h), 0), max(x0, 0):max(min(x1 + 1, w), 0)]

        def touching(scene, bx):
            return [c for c in scene.objects() if c.y0 <= bx[2] + 1 and bx[0] <= c.y1 + 1
                    and c.x0 <= bx[3] + 1 and bx[1] <= c.x1 + 1]
        nb = (box[0] + d[0], box[1] + d[1], box[2] + d[0], box[3] + d[1])
        inside_pre = set(np.unique(sub(a, *box)).tolist())
        inside_post = set(np.unique(sub(b, *nb)).tolist())
        out = {int(c) for c in inside_pre & inside_post if c >= 0 and c != mode}
        after = {int(c.colour) for c in touching(post, nb)}
        for c in {int(x.colour) for x in touching(pre, box)} & after - out:
            parts = [x for x in touching(pre, box) if x.colour == c]
            ys = np.concatenate([pre.cells(x)[0] for x in parts])
            xs = np.concatenate([pre.cells(x)[1] for x in parts])
            if float((b[ys, xs] == c).mean()) < 0.5:
                out.add(c)
        return out

    def _shift(self, tr, f, cols) -> tuple:
        """The displacement that re-finds the most self-coloured object cells (not background regions of the same
        colour) at the self's old cells shifted by it."""
        post = tr.post
        cands = [(0, 0)]
        cands += sorted(set(self.dirs().values()))
        cands += sorted({(dy, dx) for k, dy, dx in tr.moves if int(k[0]) in cols})
        ub = self._union_shift(post, f, cols)
        if ub is not None:
            cands.append(ub)
        h, w = post.shape
        arr = post.comps.arr
        pa = post.comps
        bg = np.array([True] + [c.bg for c in pa.comps])        # label 0 (HUD) counts as background here
        in_cols = np.isin(arr, list(cols)) & ~bg[pa.lab] & (arr != pa.mode)   # object cells only, not a floor region
        best, best_s = (0, 0), -1
        seen = set()
        for d in cands:
            if d in seen:
                continue
            seen.add(d)
            ys, xs = f.ys + d[0], f.xs + d[1]
            ok = (ys >= 0) & (ys < h) & (xs >= 0) & (xs < w)
            s = int(in_cols[ys[ok], xs[ok]].sum())
            if s > best_s:
                best, best_s = d, s
        return best, best_s

    def _union_shift(self, post, f, cols) -> Optional[tuple]:
        """Shift of the union box of the self-colour parts near the old box, when the box keeps its size."""
        steps = [max(abs(d[0]), abs(d[1])) for d in self.dirs().values()]
        r = max([self.cfg.look] + [2 * s for s in steps])
        b = f.box
        near = [c for c in post.objects() if c.colour in cols and c.y0 <= b[2] + r and c.y1 >= b[0] - r
                and c.x0 <= b[3] + r and c.x1 >= b[1] - r]
        if not near:
            return None
        nb = _box_of(near)
        if (nb[2] - nb[0], nb[3] - nb[1]) != (b[2] - b[0], b[3] - b[1]):
            return None
        return (nb[0] - b[0], nb[1] - b[1])

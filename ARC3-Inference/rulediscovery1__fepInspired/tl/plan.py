# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Planning as forward chaining (item 5 of the tensor-logic proposal approved by OpenMind, #arc-3,
#   24-Sep-2026): reachability over the learned transition model, feeding the object-contact explorer
#   (explore.ObjectContactExplorer) in place of its hand-written breadth-first search when ExploreConfig.search
#   is "tl". Three tensor equations over the grid of sprite offsets p = (oy, ox):
#     Blocked[p]    = step( sum_{d} Sprite[d] Wall[p + d] )           (a join with an index shift = correlation of
#                                                                     the sprite mask with the learned wall map)
#     Hit_t[p]      = the sprite's box at offset p is on target t's box (Locksmith-style "on": one box inside the
#                     other; the same test as explore._on)
#     Reach[p + d_a] <- Reach[p], not Hit[p], not Blocked[p + d_a]     for every learned arrow a
#   run to fixpoint by forward chaining (engine-style step iterations), recording the pass at which each offset
#   is first derived (= the shortest path length). Paths are read back by backward chaining through the
#   distance layers. Target choice is the explorer's: least recently touched first, then shortest trip.
#   Inputs are exactly what explore.search receives (the current board, the sprite's parts, the learned
#   arrows and wall colours, the untouched objects), so the two searches are interchangeable; tests/test_tl.py
#   checks they agree on path lengths.
# SRP/DRY check: Pass -- the "on" test and wall conventions are explore.py's (imported); only the fixpoint
#   formulation is new.
"""Reachability as forward chaining over sprite offsets (tensor-logic planning for the explorer)."""
from __future__ import annotations

from typing import Callable, Optional

import numpy as np

from .._distill import oe
from .engine import nonlin


def blocked_map(blk: np.ndarray, ys: np.ndarray, xs: np.ndarray, oy_rng: tuple, ox_rng: tuple) -> np.ndarray:
    """Blocked[p] = step(sum_d Sprite[d] Wall[p + d]) over the offset grid (oy_rng, ox_rng inclusive)."""
    ny, nx = oy_rng[1] - oy_rng[0] + 1, ox_rng[1] - ox_rng[0] + 1
    acc = np.zeros((ny, nx))
    for y, x in zip(ys.tolist(), xs.tolist()):
        y0, x0 = y + oy_rng[0], x + ox_rng[0]
        acc += blk[y0:y0 + ny, x0:x0 + nx]
    return nonlin(acc, 0.0).astype(bool)


def forward_chain_reach(free: np.ndarray, hit: np.ndarray, start: tuple, deltas: list, max_iter: int = 400):
    """Fixpoint of Reach[p + d] <- Reach[p], not Hit[p], Free[p + d]. Returns the first-derived pass per offset
    (-1 = unreachable). free / hit are boolean arrays on the offset grid; start is an index into it."""
    dist = np.full(free.shape, -1, dtype=np.int32)
    dist[start] = 0
    frontier = np.zeros(free.shape, dtype=bool)
    frontier[start] = True
    H, W = free.shape
    for k in range(1, max_iter + 1):
        expand = frontier & ~hit
        new = np.zeros_like(frontier)
        for dy, dx in deltas:
            sy0, sy1 = max(0, -dy), min(H, H - dy)
            sx0, sx1 = max(0, -dx), min(W, W - dx)
            if sy0 >= sy1 or sx0 >= sx1:
                continue
            new[sy0 + dy:sy1 + dy, sx0 + dx:sx1 + dx] |= expand[sy0:sy1, sx0:sx1]
        new &= free & (dist < 0)
        if not new.any():
            break
        dist[new] = k
        frontier = new
    return dist


def search(scene, sprite: list, moves: dict, blockers, untouched: list, on: Callable, last_touch: Callable) -> Optional[tuple]:
    """Same contract as explore.ObjectContactExplorer.search: (path [(action, (dy, dx))], target comp) or None."""
    pa = scene.comps
    h, w = pa.arr.shape
    own = {c.id for c in sprite}
    ys = np.concatenate([np.nonzero(pa.lab[c.y0:c.y1 + 1, c.x0:c.x1 + 1] == c.id)[0] + c.y0 for c in sprite])
    xs = np.concatenate([np.nonzero(pa.lab[c.y0:c.y1 + 1, c.x0:c.x1 + 1] == c.id)[1] + c.x0 for c in sprite])
    box0 = (min(c.y0 for c in sprite), min(c.x0 for c in sprite), max(c.y1 for c in sprite), max(c.x1 for c in sprite))
    blk = np.isin(pa.arr, list(blockers)) if blockers else np.zeros(pa.arr.shape, dtype=bool)
    tboxes = [(c, (c.y0, c.x0, c.y1, c.x1)) for c in untouched]
    for c, (y0, x0, y1, x1) in tboxes:
        blk[y0:y1 + 1, x0:x1 + 1] = False
    blk |= pa.arr == oe.MASKED
    blk &= ~np.isin(pa.lab, list(own))                   # the sprite's own current cells never block it
    oy_rng = (-int(ys.min()), h - 1 - int(ys.max()))
    ox_rng = (-int(xs.min()), w - 1 - int(xs.max()))
    free = ~blocked_map(blk.astype(float), ys, xs, oy_rng, ox_rng)
    oy = np.arange(oy_rng[0], oy_rng[1] + 1)[:, None]
    ox = np.arange(ox_rng[0], ox_rng[1] + 1)[None, :]
    hit_of = []
    hit = np.zeros(free.shape, dtype=bool)
    for c, tb in tboxes:
        b = (box0[0] + oy, box0[1] + ox, box0[2] + oy, box0[3] + ox)
        inside_b_t = (b[0] >= tb[0]) & (b[1] >= tb[1]) & (b[2] <= tb[2]) & (b[3] <= tb[3])
        inside_t_b = (tb[0] >= b[0]) & (tb[1] >= b[1]) & (tb[2] <= b[2]) & (tb[3] <= b[3])
        m = inside_b_t | inside_t_b
        hit_of.append(m)
        hit |= m
    start = (-oy_rng[0], -ox_rng[0])
    hit[start] = False                                   # already on it: not a trip
    acts = list(moves.items())
    dist = forward_chain_reach(free, hit, start, [d for _, d in acts])
    found = []
    for (c, _), m in zip(tboxes, hit_of):
        cand = m & (dist > 0)
        if not cand.any():
            continue
        dmin = int(dist[cand].min())
        p = tuple(int(v) for v in np.argwhere(cand & (dist == dmin))[0])
        path = []
        while dist[p] > 0:                               # backward chaining through the distance layers
            for a, (dy, dx) in acts:
                q = (p[0] - dy, p[1] - dx)
                if 0 <= q[0] < dist.shape[0] and 0 <= q[1] < dist.shape[1] and dist[q] == dist[p] - 1 and not hit[q]:
                    path.append((a, (dy, dx)))
                    p = q
                    break
            else:
                path = None
                break
        if path is not None:
            found.append((list(reversed(path)), c))
    if not found:
        return None
    return min(found, key=lambda ph: (last_touch(ph[1]), len(ph[0])))

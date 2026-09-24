#!/usr/bin/env python3
# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Round four of the FEP-style offline trace analysis (OpenMind in #arc-3, expert-debate plan
#   item 2): a HAND-BUILT, object-level description of what one action did to the board, used as the
#   outcome coder for every arm of the round-four comparison.
#   Per step, both boards get the HUD lines masked (efe_trace_analysis.hud_mask), then every
#   4-connected same-colour component is found (scipy.ndimage.label per colour). Components larger
#   than BACKGROUND_AREA are background and ignored. Only components that contain or touch a changed
#   cell are matched, in this order:
#     1. identical colour, shape and position in both boards      -> unchanged, dropped
#     2. same colour and shape, other position (greedy nearest)   -> moved (dx, dy)
#     3. same shape and position, other colour                    -> recoloured (from, to)
#     4. same colour, overlapping bounding boxes                   -> grew / shrank / reshaped
#     5. leftovers                                                 -> vanished (pre) / appeared (post)
#   Changes that touch only background components give "bgchange"; no change outside the HUD gives
#   "nothing"; the harness's level_completed / game_over flags win over everything.
#   Canonical label = sorted multiset of event kinds, dx/dy clipped to -3..3, multiplicity clipped to
#   1 / 2 / 3+ (e.g. "mv+1+0", "rc3>5x3+|van"). Colour is kept only for recolours. The fixed Dirichlet
#   support is built by the caller from labels seen in TRAINING traces, plus <novel>.
#   Also exposes the per-board component table (type key, bbox, uniqueness) and the moved-object
#   list per step, which agency_contexts.py uses to find the controllable object.
#   Reads trace files only; launches nothing; no harness change.
# SRP/DRY check: Pass -- trace reading, HUD masking and BACKGROUND_AREA come from
#   efe_trace_analysis.py / novelty_vs_solves.py; nothing in distill/ matches objects between two
#   boards or names object events (efe.outcome_class buckets changed-cell counts; the round-two
#   conv coder encodes a crop).
"""Hand-built object-event outcomes for ARC-3 trace steps.

Usage (stats on the 53-trace set):
    python distill/object_events.py --n 53
"""
from __future__ import annotations

import argparse
import sys
import time
import zlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import efe_trace_analysis as efe  # noqa: E402
from novelty_vs_solves import BACKGROUND_AREA, game_type, load_nicknames  # noqa: E402

FOUR = ndimage.generate_binary_structure(2, 1)
CLIP = 3                 # dx, dy clipped to -CLIP..CLIP in labels
NOVEL = "<novel>"
MASKED = -1              # HUD cells are set to this colour in both boards


@dataclass
class Comp:
    id: int
    colour: int
    size: int
    y0: int
    x0: int
    y1: int
    x1: int
    shape: int           # CRC32 of the normalised cell mask (position- and colour-free); deterministic
    #                      across processes, unlike hash() of bytes, so keys match between traces
    bg: bool

    @property
    def type_key(self):
        """Colour + shape: what a moved object keeps."""
        return (self.colour, self.shape)


@dataclass
class BoardComps:
    arr: np.ndarray                  # board with HUD cells = MASKED
    lab: np.ndarray                  # component id per cell (0 only for MASKED)
    comps: list                      # Comp per id (index id - 1)
    mode: int                        # most common colour (outside the HUD)
    _by_type: dict = field(default=None, repr=False)

    def by_type(self) -> dict:
        if self._by_type is None:
            d = {}
            for c in self.comps:
                if not c.bg:
                    d.setdefault(c.type_key, []).append(c)
            self._by_type = d
        return self._by_type


def board_comps(board, mask_arr: np.ndarray | None) -> BoardComps:
    a = np.asarray(board, dtype=np.int16)
    if mask_arr is not None:
        a = np.where(mask_arr, MASKED, a)
    lab = np.zeros(a.shape, dtype=np.int32)
    colours = []
    n = 0
    for c in np.unique(a):
        if c == MASKED:
            continue
        lc, k = ndimage.label(a == c, structure=FOUR)
        sel = lc > 0
        lab[sel] = lc[sel] + n
        colours += [int(c)] * k
        n += k
    sizes = np.bincount(lab.ravel(), minlength=n + 1)
    comps = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        crop = lab[sl] == i
        comps.append(Comp(i, colours[i - 1], int(sizes[i]), sl[0].start, sl[1].start, sl[0].stop - 1,
                          sl[1].stop - 1, zlib.crc32(np.asarray(crop.shape, np.int32).tobytes() + crop.tobytes()),
                          int(sizes[i]) > BACKGROUND_AREA))
    vals = a[a != MASKED]
    mode = int(np.bincount(vals.ravel()).argmax()) if vals.size else 0
    return BoardComps(a, lab, comps, mode)


def _clip(v: int) -> int:
    return max(-CLIP, min(CLIP, v))


def _overlap(a: Comp, b: Comp) -> bool:
    return not (a.y1 < b.y0 or b.y1 < a.y0 or a.x1 < b.x0 or b.x1 < a.x0)


def match_events(pa: BoardComps, pb: BoardComps):
    """Events between two HUD-masked boards. Returns (events, moves); moves = [(type_key, dy, dx)]
    for every matched moved object (unclipped), for the agency tracker."""
    changed = pa.arr != pb.arr
    if not changed.any():
        return None, []
    region = ndimage.binary_dilation(changed, structure=FOUR)
    ida = {int(i) for i in np.unique(pa.lab[region]) if i}
    idb = {int(i) for i in np.unique(pb.lab[region]) if i}
    A = [pa.comps[i - 1] for i in ida if not pa.comps[i - 1].bg]
    B = [pb.comps[i - 1] for i in idb if not pb.comps[i - 1].bg]
    if not A and not B:
        return ["bgchange"], []
    # 1. unchanged (same colour, shape, position)
    pos = lambda c: (c.colour, c.shape, c.y0, c.x0)  # noqa: E731
    bpos = Counter(pos(b) for b in B)
    apos = Counter(pos(a) for a in A)
    A2 = [a for a in A if not bpos.get(pos(a))]
    B2 = [b for b in B if not apos.get(pos(b))]
    events, moves = [], []
    # 2. moved: same colour + shape, greedy nearest pairing within each type
    bt = {}
    for b in B2:
        bt.setdefault(b.type_key, []).append(b)
    usedA, usedB = set(), set()
    pairs = []
    for a in A2:
        for b in bt.get(a.type_key, ()):
            pairs.append((abs(b.y0 - a.y0) + abs(b.x0 - a.x0), a.id, b.id, a, b))
    for _, ai, bi, a, b in sorted(pairs, key=lambda t: t[:3]):
        if ai in usedA or bi in usedB:
            continue
        usedA.add(ai)
        usedB.add(bi)
        dy, dx = b.y0 - a.y0, b.x0 - a.x0
        events.append(f"mv{_clip(dx):+d}{_clip(dy):+d}")
        moves.append((a.type_key, dy, dx))
    A3 = [a for a in A2 if a.id not in usedA]
    B3 = [b for b in B2 if b.id not in usedB]
    # 3. recoloured in place
    bshape = {}
    for b in B3:
        bshape.setdefault((b.shape, b.y0, b.x0), []).append(b)
    for a in A3:
        for b in bshape.get((a.shape, a.y0, a.x0), ()):
            if b.id not in usedB:
                usedA.add(a.id)
                usedB.add(b.id)
                events.append(f"rc{a.colour}>{b.colour}")
                break
    A4 = [a for a in A3 if a.id not in usedA]
    B4 = [b for b in B3 if b.id not in usedB]
    # 4. same colour, overlapping boxes: resized / reshaped
    for a in A4:
        for b in B4:
            if b.id in usedB or b.colour != a.colour or not _overlap(a, b):
                continue
            usedA.add(a.id)
            usedB.add(b.id)
            events.append("grow" if b.size > a.size else "shrink" if b.size < a.size else "reshape")
            break
    # 5. leftovers
    events += ["van"] * sum(a.id not in usedA for a in A4)
    events += ["app"] * sum(b.id not in usedB for b in B4)
    return events, moves


def canonical(events) -> str:
    cnt = Counter(events)
    parts = []
    for k in sorted(cnt):
        n = cnt[k]
        parts.append(k if n == 1 else f"{k}x{n if n < 3 else '3+'}")
    return "|".join(parts) if parts else "bgchange"


# ---------------------------------------------------------------- per-trace cache

@dataclass
class Step:
    i: int                  # index into the trace's action rows
    row: dict
    pre: list | None        # raw boards (lists) as the harness wrote them
    post: list | None
    reset: bool
    label: str              # canonical object-event label (or nothing / level_clear / game_over)
    moves: list             # [(type_key, dy, dx)] matched moves (agency evidence)
    pa: BoardComps | None   # components of pre (HUD masked)
    events: list | None


@dataclass
class Trace:
    path: str
    run: str
    game: str
    nick: str
    gtype: str
    pass_no: int
    valid: list
    steps: list
    hud_cells: int


def pass_of(path: str) -> int:
    stem = Path(path).name
    for part in stem.split("_"):
        if part.startswith("p") and part[1:].isdigit():
            return int(part[1:])
    return 0


def load(path: str, nick: dict | None = None) -> Trace:
    valid, board, actions = efe.load_trace(path)
    boards = [board] + [a.get("board") for a in actions]
    mask = efe.hud_mask(boards)
    marr = None
    if board and mask:
        marr = np.zeros((len(board), len(board[0])), dtype=bool)
        for y, x in mask:
            marr[y, x] = True
    cache = {}

    def comps(k):
        if k not in cache:
            cache.clear() if len(cache) > 4 else None
            cache[k] = board_comps(boards[k], marr) if boards[k] else None
        return cache[k]

    steps = []
    pre_k = 0
    for i, row in enumerate(actions):
        post_k = i + 1
        pre = boards[pre_k]
        post = boards[post_k]
        if row.get("action_name") == "RESET":
            steps.append(Step(i, row, pre, post, True, "reset", [], None, None))
            pre_k = post_k
            continue
        pa = comps(pre_k) if pre else None
        events, moves = None, []
        if row.get("level_completed"):
            label = "level_clear"
        elif row.get("game_over"):
            label = "game_over"
        elif not pre or not post:
            label = NOVEL
        else:
            pb = comps(post_k)
            events, moves = match_events(pa, pb)
            label = "nothing" if events is None else canonical(events)
        steps.append(Step(i, row, pre, post, False, label, moves, pa, events))
        pre_k = post_k
    game = Path(path).name.split("-")[0]
    nick = nick or {}
    return Trace(path, efe.run_name(path), game, nick.get(game, game), game_type(valid), pass_of(path),
                 valid, steps, len(mask))


def _load_one(args):
    path, nick = args
    t0 = time.time()
    tr = load(path, nick)
    return tr, time.time() - t0


def load_all(paths, workers: int = 1):
    """Load and event-code every trace; returns (traces in input order, cpu seconds)."""
    nick = load_nicknames()
    jobs = [(p, nick) for p in paths]
    if workers > 1:
        import multiprocessing as mp
        with mp.get_context("spawn").Pool(workers) as pool:
            out = pool.map(_load_one, jobs)
    else:
        out = [_load_one(j) for j in jobs]
    return [t for t, _ in out], sum(s for _, s in out)


def main():
    import ebul_perception as ep
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=53)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    t0 = time.time()
    traces, cpu = load_all(ep.trace_paths(args.n), args.workers)
    print(f"{len(traces)} traces event-coded in {time.time() - t0:.1f}s wall ({cpu:.1f}s cpu)")
    by_game = {}
    for tr in traces:
        by_game.setdefault(tr.nick, Counter()).update(s.label for s in tr.steps if not s.reset)
    allc = Counter()
    for c in by_game.values():
        allc.update(c)
    print(f"{len(allc)} distinct labels over {sum(allc.values())} steps")
    for g, c in sorted(by_game.items()):
        print(f"{g:<20} {len(c):4d} labels  top: {', '.join(f'{k} ({v})' for k, v in c.most_common(6))}")


if __name__ == "__main__":
    main()

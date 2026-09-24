# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Stage A1 (and A2) of docs/plans/2026-09-24-soft-agent-roadmap.md: objects by COMMON FATE, learned
#   online from boards only, plus CO-CHANGE links.
#     - Parts = non-background components (distill/object_events), tracked frame to frame per type by nearest
#       position (hdc/stage4_real.Tracker).
#     - Hebbian affinity between every pair of tracks: +1 when both move by the same displacement on the same
#       step, -1 when exactly one of them moves or they move differently. Parts whose affinity reaches
#       MIN_CO co-moves with a co-move share >= SHARE are fused (union-find) into one object.
#     - Co-change affinity (A2): +1 when two tracks both CHANGE on the same step (appear, vanish, recolour,
#       reshape -- anything but a pure move) -- a candidate causal link (switch <-> door).
#   Scoring against the A0 labels (engine sprite masks, used only here), per game over all plays: pairs of
#   parts that moved on the same step are labelled "same sprite" or "different sprites" by which true sprite
#   mask covers them; pair recall = share of same-sprite pairs put in one object; pair precision = share of
#   pairs put in one object that really are one sprite. Baselines: every part its own object (the old
#   perception), and hypotheses.co_movers' type-level rule (the explicit fix from 23-Sep).
#   Output results/soft/a1.json + .md.
#   24-Sep-2026 (HDC integration A/B, OpenMind 10:17 ET): optional revocable fusion (decay) and update_objects()
#   so the live agent (hdc_bridge) feeds its own parsed Scene; score_game also scores PREQUENTIALLY (the grouping
#   as it stood before each step), which is what the agent sees, next to the original end-of-play grouping.
# SRP/DRY check: Pass -- components and tracking are reused; new: the pairwise affinity, the fusion and the
#   pair scoring against sprite masks.
"""A1/A2: common-fate object grouping and co-change links, scored against engine sprite masks."""
from __future__ import annotations

import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

from .. import _distill as D
from ..hdc.stage4_real import Tracker

OUT = Path(__file__).resolve().parent.parent / "results" / "soft"
MIN_CO, SHARE = 2, 0.9


class CommonFate:
    def __init__(self, decay: float | None = None):
        """decay None: cumulative counts (the A1 original; a fusion is permanent in practice). decay in (0, 1):
        revocable fusion (HDC integration A/B, 24-Sep-2026): each time a pair is evaluated both counts are
        multiplied by decay first, so a pair that diverges (a box the player puts down) drops below SHARE at
        once and unfuses, and must co-move a few times again to re-fuse."""
        self.tr = Tracker()
        self.decay = decay
        self.co = defaultdict(float)     # pair -> steps moved together identically
        self.any = defaultdict(float)    # pair -> steps at least one of them moved
        self.chg = defaultdict(int)      # pair -> steps both changed (not a pure move)
        self.cells = {}                  # track -> flat cell indices on the latest board

    def update(self, board):
        bc = D.oe.board_comps(board, None)

        def cells_of(c):
            ys, xs = np.nonzero(bc.lab == c.id)
            return (ys * 64 + xs).tolist()
        return self.update_objects([c for c in bc.comps if not c.bg and c.colour != bc.mode], cells_of)

    def update_objects(self, objs, cells_of=None):
        """update() on an already-parsed object list; cells_of(comp) -> flat cell indices (None: skip cells)."""
        prev_types = {t: k for t, (k, _) in self.tr.tracks.items()}
        mv = self.tr.update_objects(objs)
        self.last_moves = mv                     # every present track's move this step (hdc_bridge.GhostTape)
        self.cells = {}
        if cells_of is not None:
            for t, c in self.tr.comp_of.items():
                self.cells[t] = cells_of(c)
        moving = {t: d for t, d in mv.items() if d != (0, 0) and t in prev_types}
        new = [t for t in mv if t not in prev_types]            # appeared / reshaped (a new track)
        present = [t for t in mv if t in prev_types]            # seen on both boards
        # every pair of present parts where at least one moved: +1 "any"; both moved identically: +1 "co"
        # (the first version only counted pairs where both moved, so "always together" was far too lenient)
        for a in moving:
            for b in present:
                if a == b or (b in moving and b < a):
                    continue
                key = (min(a, b), max(a, b))
                if self.decay is not None:
                    self.any[key] *= self.decay
                    self.co[key] *= self.decay
                self.any[key] += 1
                if b in moving and moving[a] == moving[b]:
                    self.co[key] += 1
        vanished = [t for t in prev_types if t not in self.tr.tracks]
        changed = new + vanished
        for a, b in combinations(sorted(changed), 2):
            self.chg[(a, b)] += 1
        return moving

    def groups(self):
        parent = {}

        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for (a, b), n in self.co.items():
            if n >= MIN_CO and n >= SHARE * self.any[(a, b)]:
                parent[find(a)] = find(b)
        return find


def owner(cells, sprite_masks):
    """The true sprite covering most of these cells (or None)."""
    best, bn = None, 0
    s = set(cells)
    for sid, m in sprite_masks.items():
        n = len(s & m)
        if n > bn:
            best, bn = sid, n
    return best if bn >= max(1, len(s) // 2) else None


def score_game(path: Path, decay: float | None = None):
    tp = fp = fn = 0
    ptp = pfp = pfn = 0       # prequential: the grouping as it stood BEFORE the step (what the agent acts on)
    base_tp = base_fp = base_fn = 0
    type_tp = type_fp = type_fn = 0
    plays = 0
    for line in path.read_text().splitlines():
        play = json.loads(line)
        cf = CommonFate(decay)
        pairs = []            # (track a, track b, same sprite?, type a, type b)
        for s in play["steps"]:
            before = cf.groups()
            moving = cf.update(s["board"])
            masks = {m["sprite"]: set(m["mask"]) for m in s["moved"]}
            own = {t: owner(cf.cells.get(t, []), masks) for t in moving}
            ts = [t for t in moving if own[t] is not None]
            for a, b in combinations(sorted(ts), 2):
                pairs.append((a, b, own[a] == own[b], cf.tr.tracks[a][0], cf.tr.tracks[b][0]))
                same, fused = own[a] == own[b], before(a) == before(b)
                ptp += same and fused
                pfp += (not same) and fused
                pfn += same and not fused
        find = cf.groups()
        # type-level baseline: types that (almost) always move together, fused by type
        type_co, type_any = defaultdict(int), defaultdict(int)
        for a, b, _, ka, kb in pairs:
            type_any[(ka, kb)] += 1
        for (a, b), n in cf.co.items():
            if a in cf.tr.tracks and b in cf.tr.tracks:
                type_co[(cf.tr.tracks[a][0], cf.tr.tracks[b][0])] += n
        for a, b, same, ka, kb in pairs:
            fused = find(a) == find(b)
            tp += same and fused
            fp += (not same) and fused
            fn += same and not fused
            base_fn += same                     # every part its own object: never fuses
            tfused = ka != kb and type_co[(ka, kb)] >= MIN_CO
            type_tp += same and tfused
            type_fp += (not same) and tfused
            type_fn += same and not tfused
        plays += 1
    pr = lambda t, f: t / (t + f) if t + f else float("nan")  # noqa: E731
    return {"plays": plays, "same_sprite_pairs": tp + fn,
            "common_fate": {"recall": pr(tp, fn), "precision": pr(tp, fp)},
            "common_fate_prequential": {"recall": pr(ptp, pfn), "precision": pr(ptp, pfp)},
            "each_part_own_object": {"recall": pr(0, base_fn), "precision": float("nan")},
            "type_level_rule": {"recall": pr(type_tp, type_fn), "precision": pr(type_tp, type_fp)}}


def main():
    res = {}
    for g in ("ls20", "g50t", "wa30", "sp80", "cn04"):
        p = OUT / f"a0_{g}.jsonl"
        if p.exists():
            res[g] = score_game(p)
            print(g, json.dumps(res[g]), flush=True)
    lines = ["| game | same-sprite part pairs | common fate recall / precision | type-level rule recall / precision |",
             "|---|---|---|---|"]
    for g, r in res.items():
        cf, ty = r["common_fate"], r["type_level_rule"]
        lines.append(f"| {g} | {r['same_sprite_pairs']} | {cf['recall']:.3f} / {cf['precision']:.3f} | "
                     f"{ty['recall']:.3f} / {ty['precision']:.3f} |")
    text = "A1: parts grouped into objects by common fate, scored on engine sprite masks\n" + "\n".join(lines)
    print(text)
    (OUT / "a1.json").write_text(json.dumps(res, indent=1))
    (OUT / "a1.md").write_text(text + "\n")


if __name__ == "__main__":
    main()

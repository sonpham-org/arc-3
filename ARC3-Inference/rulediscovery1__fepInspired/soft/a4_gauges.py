# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Stage A4 of docs/plans/2026-09-24-soft-agent-roadmap.md: GAUGES (step bar, timer, lives), learned from
#   boards only, and a fractional-power scalar model that predicts the gauge's next value.
#     - Finder (online, per play): cells that ever changed between consecutive boards (transitions that change more
#       than SCENE of the screen -- level changes -- are skipped) are grouped into 8-connected regions (1-cell
#       dilation). For every region and colour, the colour's pixel count inside the region is a series over the
#       play. A (region, colour) is a gauge when its count moves in one direction in steady small ticks: at least
#       MIN_TICKS changes of the dominant sign, at least TICK_RATIO times as many as of the other sign (rare jumps
#       back = refills), median tick at most TICK_SHARE of the largest count. The region is then widened to the
#       colour's connected pieces (first and latest board) that touch it, so a bar that has drained only a little
#       is read over its full length. Mirror images (the background colour filling what the bar loses: >= 95 % of
#       changes exactly opposite) are dropped in favour of the draining colour, then the smaller region. Counts
#       come from per-colour summed-area tables, so the finder runs every step.
#     - Predictor (phasor VSA, hdc/vsa.py): value n is the fractional-power code G**n. A context is
#       K**k (x) S, with k = steps since the gauge last changed (capped at K_MAX -- this is the clock that lets a
#       "one tick every two actions" timer be learned) and S a random token: EMPTY (count at its end of range),
#       RESET (the action is RESET) or BODY. One memory vector M holds context (x) G**delta; after each step it is
#       updated by the delta rule M += ETA * ctx (x) (G**delta - own), own = the context's read-out cleaned up
#       against the delta codebook, so a context switches to a new drain after two confirmations and ignores a
#       single odd step (ETA between 0.29 and 0.5). Prediction:
#       G**n (x) unbind(M, ctx), cleaned up against the codebook G**0 .. G**max -> the next value; a best match
#       below CONF means "context never seen". Two such memories run side by side, with and without the clock k
#       (a clock helps a timer, but splits a step bar's evidence over rarely seen k); the one with the better
#       recent record of exact predictions answers, an unknown context falls back to the other, then to "no
#       change". A symbolic twin (same delta rule on exact per-context weights) checks the vector decode.
#     - Baseline: "same drain as last step", next = n + (n - previous n).
#   Labels (A0 files, engine values, used only for scoring): a found gauge is certified as Locksmith's step bar /
#   lives or Ghost Twin's timer when its count is an affine function of that label (clamped at zero) on >= 95 %
#   of the play's steps. Prediction is scored on steps after the gauge was found (the history before is replayed
#   through the predictor), on the final region and, as a no-hindsight check, on the region exactly as it stood
#   when the gauge was first found; misses are sorted into causes
#   with the labels (level change, game over / reset, refill jump, nothing happened, a free step, other).
#   Output results/soft/a4.json + a4.md.
# SRP/DRY check: Pass -- VSA from hdc/vsa.py; efe_trace_analysis.hud_mask only masks whole border lines changing on
#   > 60 % of steps (misses a timer ticking every second action) and reads no value, so region finding is new here.
"""A4: gauges found from boards, value as a fractional-power scalar, next value predicted."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import ndimage

from ..hdc.vsa import VSA

OUT = Path(__file__).resolve().parent.parent / "results" / "soft"
NC = 16                                   # colours 0..15
SCENE = 0.15                              # a transition changing more than this share of the screen is a scene change
MIN_TICKS, TICK_RATIO, TICK_SHARE = 6, 4, 0.25
K_MAX, ETA = 3, 0.4
CONF, CLEAN, SCORE_DECAY = 0.2, 0.1, 0.9     # read-out below CONF = unknown context; below CLEAN = crosstalk
EIGHT = np.ones((3, 3), bool)
LABELS = {"ls20": ("steps", "lives"), "g50t": ("timer_x",)}
CONTACT = ("free_step", "refill_jump", "level_change")   # misses caused by touching something / a level change


def sat(board) -> np.ndarray:
    """Per-colour summed-area table, shape (NC, 65, 65)."""
    b = np.asarray(board)
    oh = (b[None] == np.arange(NC)[:, None, None]).astype(np.int32)
    t = np.zeros((NC, 65, 65), np.int32)
    t[:, 1:, 1:] = oh.cumsum(1).cumsum(2)
    return t


class GaugeFinder:
    def __init__(self, tmax: int):
        self.S = np.zeros((tmax, NC, 65, 65), np.int32)
        self.boards = []
        self.E = np.zeros((64, 64), bool)
        self.scene = []                     # per transition t-1 -> t: True if a scene change

    def observe(self, board):
        t = len(self.boards)
        b = np.asarray(board)
        self.S[t] = sat(b)
        if self.boards:
            d = b != self.boards[-1]
            big = d.mean() > SCENE
            self.scene.append(bool(big))
            if not big:
                self.E |= d
        self.boards.append(b)

    def count(self, region, c):
        y0, y1, x0, x1 = region                 # inclusive bounds
        T = len(self.boards)
        S = self.S[:T, c]
        return S[:, y1 + 1, x1 + 1] - S[:, y0, x1 + 1] - S[:, y1 + 1, x0] + S[:, y0, x0]

    def _monotone(self, n):
        d = np.diff(n)
        ok = ~np.asarray(self.scene, bool)
        d = d[ok]
        neg, pos = d[d < 0], d[d > 0]
        sign = -1 if len(neg) >= len(pos) else 1
        main, other = (neg, pos) if sign < 0 else (pos, neg)
        if len(main) < MIN_TICKS or len(main) < TICK_RATIO * len(other) or n.max() == 0:
            return None
        if np.median(np.abs(main)) > TICK_SHARE * n.max():
            return None
        return sign, len(main), len(other)

    def _widen(self, region, c, comp_mask):
        y0, y1, x0, x1 = region
        for b in (self.boards[0], self.boards[-1]):
            lab, _ = ndimage.label(b == c, structure=EIGHT)
            for i in np.unique(lab[comp_mask & (lab > 0)]):
                ys, xs = np.nonzero(lab == i)
                y0, y1, x0, x1 = min(y0, ys.min()), max(y1, ys.max()), min(x0, xs.min()), max(x1, xs.max())
        return int(y0), int(y1), int(x0), int(x1)

    def gauges(self):
        if len(self.boards) < MIN_TICKS + 1:
            return []
        lab, k = ndimage.label(ndimage.binary_dilation(self.E, EIGHT), structure=EIGHT)
        found = []
        for i in range(1, k + 1):
            m = lab == i
            ys, xs = np.nonzero(m)
            raw = (int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max()))
            for c in range(NC):
                n = self.count(raw, c)
                if self._monotone(n) is None:
                    continue
                region = self._widen(raw, c, m)
                n = self.count(region, c)
                mono = self._monotone(n)
                if mono is None:
                    continue
                area = (region[1] - region[0] + 1) * (region[3] - region[2] + 1)
                found.append({"region": region, "colour": c, "sign": mono[0], "ticks": mono[1],
                              "jumps": mono[2], "area": area, "series": n})
        # mirror images: two gauges whose changes are exact negatives on >= 95 % of steps are one gauge;
        # keep the draining one (the bar itself, present from the first board), then the smaller region
        keep = []
        for g in sorted(found, key=lambda g: (g["sign"] > 0, g["area"])):
            dg = np.diff(g["series"])
            if any(np.mean(dg == -np.diff(h["series"])) >= 0.95 for h in keep):
                continue
            keep.append(g)
        return keep


class DeltaMemory:
    """One context-keyed memory of value changes: vector form (M) and its exact symbolic twin."""

    def __init__(self, p: "GaugePredictor", clocked: bool):
        self.p, self.clocked = p, clocked
        self.M = np.zeros(p.v.D, complex)
        self.twin = defaultdict(lambda: defaultdict(float))   # context -> delta -> weight

    def key(self, k, s):
        return (min(k, K_MAX), s) if self.clocked else (0, s)

    def read(self, n, key):
        """(vector prediction or None if the context is unknown, twin prediction or None)."""
        p = self.p
        q = p.code(n) * p.v.unbind(self.M, p.ctx(key))
        sims = p.v.sim(p.book, q)
        vec = int(np.argmax(sims)) if sims.max() >= CONF else None
        w = self.twin[key]
        sym = n + max(w, key=w.get) if w else None
        return vec, sym

    def write(self, key, delta):
        """Delta rule on the context's OWN content: its read-out cleaned up against the delta codebook (weights
        below CLEAN dropped as crosstalk). Subtracting the raw read-out instead makes the contexts fight over
        every vector element, and stored weights stall near a third of their true size (first version)."""
        p = self.p
        c = p.ctx(key)
        w = p.v.sim(p.dbook, p.v.unbind(self.M, c))
        keep = np.abs(w) >= CLEAN
        own = (w[keep, None] * p.dbook[keep]).sum(0)
        self.M += ETA * c * (p.code(delta) - own)
        w = self.twin[key]
        for d in list(w):
            w[d] *= 1 - ETA
        w[delta] += ETA


class GaugePredictor:
    """Fractional-power value code; two delta memories (with and without the clock k), the one with the better
    recent exact-prediction record answers; unknown context -> the other memory -> "no change"."""

    def __init__(self, vsa: VSA, vmax: int, sign: int):
        self.v = vsa
        self.G, self.K = vsa.rand(), vsa.rand()
        self.tok = {s: vsa.rand() for s in ("BODY", "EMPTY", "RESET")}
        self.vmax, self.sign = vmax, sign
        self.book = np.stack([self.code(i) for i in range(vmax + 1)])            # values 0 .. vmax
        self.dbook = np.stack([self.code(d) for d in range(-vmax, vmax + 1)])   # changes -vmax .. vmax
        self.mems = [DeltaMemory(self, True), DeltaMemory(self, False)]
        self.score = {"vec": [0.0, 0.0], "sym": [0.0, 0.0]}   # recent exactness per memory (moving average)
        self.k = K_MAX
        self.last = None

    def code(self, x):
        return self.v.power(self.G, x)

    def state(self, n, action):
        return "RESET" if action == "RESET" else ("EMPTY" if (n == 0 if self.sign < 0 else n >= self.vmax) else "BODY")

    def ctx(self, key):
        return self.v.power(self.K, key[0]) * self.tok[key[1]]

    def predict(self, n, action):
        s = self.state(n, action)
        reads = [m.read(n, m.key(self.k, s)) for m in self.mems]
        self.last = reads
        out = []
        for j, kind in enumerate(("vec", "sym")):
            order = sorted(range(2), key=lambda i: -self.score[kind][i] + 1e-9 * (i == 0))  # tie -> no clock
            val = next((reads[i][j] for i in order if reads[i][j] is not None), n)
            out.append(val)
        return tuple(out)

    def learn(self, n, action, n_next):
        s = self.state(n, action)
        if self.last is not None:
            for j, kind in enumerate(("vec", "sym")):
                for i in range(2):
                    hit = self.last[i][j] == n_next
                    self.score[kind][i] = SCORE_DECAY * self.score[kind][i] + (1 - SCORE_DECAY) * hit
        self.last = None
        for m in self.mems:
            m.write(m.key(self.k, s), n_next - n)
        self.k = 1 if n_next != n else self.k + 1


def certify(series, label):
    """Share of steps where the count equals round(a * label + b) clamped at 0, a/b fitted on unclamped steps."""
    lab = np.array([np.nan if x is None else x for x in label], float)
    ok = ~np.isnan(lab) & (series > 0)
    if ok.sum() < 5 or np.ptp(lab[ok]) == 0:
        return 0.0
    a, b = np.polyfit(lab[ok], series[ok], 1)
    have = ~np.isnan(lab)
    pred = np.clip(np.round(a * lab[have] + b), 0, None)
    return float(np.mean(pred == series[have]))


def miss_cause(steps, t, n, n_next, sign):
    """Why the step t -> t+1 was not a plain tick (labels used here only)."""
    s0, s1 = steps[t], steps[t + 1]
    if s1["levels"] != s0["levels"] or (t > 0 and s0["levels"] != steps[t - 1]["levels"]):
        return "level_change"                   # the refill, or the first tick at the new level's rate"
    if s1["state"] != "NOT_FINISHED" or s1["action"] == "RESET" or s0["state"] != "NOT_FINISHED":
        return "game_over_or_reset"
    d = n_next - n
    if d * sign < 0:
        return "refill_jump"
    if d == 0:
        # the screen did not change at all (the action did nothing), or something happened but cost nothing
        return "nothing_happened" if s0["board"] == s1["board"] else "free_step"
    return "other"


def run_game(game, vsa):
    plays = [json.loads(l) for l in (OUT / f"a0_{game}.jsonl").read_text().splitlines()]
    plays = [p for p in plays if p["steps"]]                 # skip empty plays (first line of four files)
    res = {"plays": len(plays), "gauges": [], "labels": {}}
    labels = LABELS.get(game, ())
    tallies = {lab: Counter() for lab in labels}
    causes = {lab: Counter() for lab in labels}
    found_at = {lab: [] for lab in labels}
    region_stable = {lab: Counter() for lab in labels}
    other_tally = Counter()
    for p in plays:
        steps = p["steps"]
        T = len(steps)
        f = GaugeFinder(T)
        first = {}                                   # (colour, region) -> first step it was reported
        for t, s in enumerate(steps):
            f.observe(s["board"])
            for g in f.gauges():
                first.setdefault((g["colour"], g["region"]), t)
        final = f.gauges()
        for g in final:
            key = (g["colour"], g["region"])
            # found at: first step any gauge of this colour overlapping this region was reported
            y0, y1, x0, x1 = g["region"]
            overl = sorted((tt, r) for (c, r), tt in first.items()
                           if c == g["colour"] and not (r[1] < y0 or r[0] > y1 or r[3] < x0 or r[2] > x1))
            t0, r0 = overl[0]
            n = g["series"]
            n_frozen = f.count(r0, g["colour"])      # the region exactly as it stood when first found (no hindsight)
            match = None
            for lab in labels:
                share = certify(n, [s["gauges"].get(lab) for s in steps])
                if share >= 0.95:
                    match = lab
            res["gauges"].append({"trace": Path(p["trace"]).name, "colour": g["colour"], "region": g["region"],
                                  "direction": "drains" if g["sign"] < 0 else "fills", "ticks": g["ticks"],
                                  "jumps": g["jumps"], "found_at_step": t0, "steps": T, "label": match})
            # predict the next value on every step after the gauge was found
            pr = GaugePredictor(vsa, int(g["area"]), g["sign"])
            area0 = (r0[1] - r0[0] + 1) * (r0[3] - r0[2] + 1)
            pr0 = GaugePredictor(vsa, int(area0), g["sign"])
            tally = tallies[match] if match else other_tally
            for t in range(T - 1):
                act = steps[t + 1]["action"]
                # the history before t0 is replayed through the predictor (the finder holds it when the gauge is
                # found), so each memory's record exists at t0; only predictions from t0 on are scored
                vec, sym = pr.predict(int(n[t]), act)
                vec0, _ = pr0.predict(int(n_frozen[t]), act)
                if t >= t0:
                    tally["frozen_model"] += vec0 == n_frozen[t + 1]
                    base = int(n[t] + (n[t] - n[t - 1])) if t > 0 else int(n[t])
                    tally["n"] += 1
                    tally["model"] += vec == n[t + 1]
                    tally["twin"] += sym == n[t + 1]
                    tally["decode_agrees"] += vec == sym
                    tally["baseline"] += base == n[t + 1]
                    if match and vec != n[t + 1]:
                        causes[match][miss_cause(steps, t, int(n[t]), int(n[t + 1]), g["sign"])] += 1
                pr.learn(int(n[t]), act, int(n[t + 1]))
                pr0.learn(int(n_frozen[t]), act, int(n_frozen[t + 1]))
            if match:
                found_at[match].append(t0)
                region_stable[match]["same_region_at_first_report"] += key in first and first[key] == t0
        for lab in labels:
            region_stable[lab]["plays"] += 1
    for lab in labels:
        tl = tallies[lab]
        res["labels"][lab] = {
            "plays_found": len(found_at[lab]), "plays": len(plays),
            "found_at_step_median": float(np.median(found_at[lab])) if found_at[lab] else None,
            "region_same_as_when_found": region_stable[lab]["same_region_at_first_report"],
            "predicted_steps": tl["n"], "model_exact": tl["model"] / max(tl["n"], 1),
            "baseline_exact": tl["baseline"] / max(tl["n"], 1), "symbolic_twin_exact": tl["twin"] / max(tl["n"], 1),
            "vector_decode_agrees_with_twin": tl["decode_agrees"] / max(tl["n"], 1),
            "model_exact_region_frozen_when_found": tl["frozen_model"] / max(tl["n"], 1),
            # hypothetical: as if contact events (free step, refill, level change) were supplied from outside
            "exact_if_contact_events_known": (tl["model"] + sum(causes[lab][c] for c in CONTACT)) / max(tl["n"], 1),
            "misses_by_cause": dict(causes[lab])}
    if other_tally["n"]:
        res["unlabelled_gauges"] = {"predicted_steps": other_tally["n"],
                                    "model_exact": other_tally["model"] / other_tally["n"],
                                    "baseline_exact": other_tally["baseline"] / other_tally["n"]}
    return res


NOTES = """Notes (24-Sep-2026):
- Gate: step bar and timer found in every play (yes). Next value exact >= 95 %: Ghost Twin yes, Locksmith no.
- Locksmith's misses are steps the bar's own history cannot foresee: "nothing_happened" = the action changed
  nothing on screen and cost nothing; "free_step" = the player stepped onto the key-rotation tile, which the
  game does not charge for (engine: no step is counted when the move touches that tile); "refill_jump" = a
  refill pickup filling the bar back to full, or a life lost at an empty bar; "level_change" = the refill and
  the first tick at the new level's rate (level two drains two per move). Knowing WHEN these happen needs
  object contact (B1 transition memory, E1 drain/refill per pickup), not a better gauge model.
- Lives (Locksmith) are not found: they drop at most twice per play, below the six-tick minimum.
- Ghost Twin's baseline is near zero only because the timer ticks every second action, so "same change as
  last step" is wrong on almost every step; the clock context (steps since the last tick) is what learns it.
- Regions spanning the whole board (wa30, cn04) are the bar merged with the play area into one changed
  region; the count still follows the bar, but the region is not a clean gauge."""


def summarise_regions(gs):
    """Group found gauges across plays by (colour, region) -> number of plays."""
    c = Counter((g["colour"], tuple(g["region"]), g["direction"], g["label"]) for g in gs)
    return [{"colour": k[0], "rows": [k[1][0], k[1][1]], "cols": [k[1][2], k[1][3]], "direction": k[2],
             "label": k[3], "plays": v} for k, v in c.most_common()]


def main():
    vsa = VSA(2048, seed=0)
    res = {}
    for g in ("ls20", "g50t", "wa30", "sp80", "cn04"):
        p = OUT / f"a0_{g}.jsonl"
        if p.exists():
            r = run_game(g, vsa)
            r["regions"] = summarise_regions(r["gauges"])
            res[g] = r
            print(g, json.dumps({k: v for k, v in r.items() if k != "gauges"})[:1500], flush=True)
    lines = ["| game | gauge | found in plays | found at step (median) | predicted steps | model exact | baseline exact | "
             "model, region frozen when found | if contact events known | vector = twin | misses by cause |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for g, r in res.items():
        for lab, x in r["labels"].items():
            if not x["plays_found"]:
                lines.append(f"| {g} | {lab} | 0 / {x['plays']} (not found) | - | - | - | - | - | - | - | - |")
                continue
            lines.append(f"| {g} | {lab} | {x['plays_found']} / {x['plays']} | {x['found_at_step_median']} | "
                         f"{x['predicted_steps']} | {x['model_exact']:.3f} | {x['baseline_exact']:.3f} | "
                         f"{x['model_exact_region_frozen_when_found']:.3f} | {x['exact_if_contact_events_known']:.3f} | "
                         f"{x['vector_decode_agrees_with_twin']:.3f} | {x['misses_by_cause']} |")
    lines += ["", "Regions found (colour, rows, cols, direction, certified label, plays):"]
    for g, r in res.items():
        top = "; ".join(f"c{x['colour']} r{x['rows'][0]}-{x['rows'][1]} c{x['cols'][0]}-{x['cols'][1]} "
                        f"{x['direction']} {x['label'] or '-'} x{x['plays']}" for x in r["regions"][:8])
        extra = r.get("unlabelled_gauges")
        lines.append(f"- {g} ({r['plays']} plays): {top or 'none'}"
                     + (f"  [unlabelled: {extra['predicted_steps']} steps, model {extra['model_exact']:.3f}, "
                        f"baseline {extra['baseline_exact']:.3f}]" if extra else ""))
    lines += ["", NOTES]
    text = "A4: gauges found from boards, next value predicted (fractional-power code)\n" + "\n".join(lines)
    print(text)
    (OUT / "a4.json").write_text(json.dumps(res, indent=1, default=int))
    (OUT / "a4.md").write_text(text + "\n")


if __name__ == "__main__":
    main()

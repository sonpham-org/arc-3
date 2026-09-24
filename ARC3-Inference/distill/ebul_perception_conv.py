#!/usr/bin/env python3
# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Second round of the learned-perception test for the FEP-style trace analysis, asked by
#   OpenMind in #arc-3 on 23-Sep-2026 18:19 ET. Three changes over ebul_perception.py:
#   1. OUTCOMES ARE PERCEIVED TOO. Every step's change (board after vs before, HUD lines masked) is
#      cropped to a 9x9 window at the centre of the changed area and encoded by an EBUL-trained
#      net; its ternary code is the outcome class, replacing the "how many cells changed" bucket.
#      The outcome coder is trained once and held FIXED across all context arms, so the arms are
#      compared on the same outcome alphabet. Its Dirichlet support is fixed: the codes seen in
#      training plus one "<novel>" class for codes never seen in training.
#   2. HARD-CODED CONVOLUTION FRONT END before the nets: simple difference kernels along x, y and
#      both diagonals, plus "hat" (Ricker / Mexican-hat) kernels of sizes 3, 5, 7 laid along x, y
#      and both diagonals, plus isotropic 2D hats of sizes 3 and 5 -- 18 kernels. They run on base
#      channels (board: colour index and "not the background colour"; change: changed-mask, colour
#      before, colour after), responses are pooled as mean |response| over a grid, and appended to
#      the raw features from ebul_perception.py. Maps are computed once per board, and patch
#      features are crops of them, so candidate scoring stays cheap.
#   3. WIDER NETS: two hidden layers of WIDTH (default 120) units instead of 12 and 8.
#   Arms, all with the same learned outcome coder: flat (one context for everything: the
#   no-information baseline), none, handmade, handstate, ebul-narrow (last round's nets), random
#   wide conv nets (control), EBUL wide conv nets. Score: nats/step of prequential surprisal, and
#   information gained over the flat arm (flat nats minus arm nats) -- how much the context tells
#   about what the action will do. Reads files only; launches nothing; no harness change.
#   Caveat: all nets are trained on the same 53 traces they are scored on (unsupervised, no labels).
#   Round three (23-Sep-2026, OpenMind): the trained encoders and the outcome coder's alphabet are
#   pickled to <out>/encoders.pkl with the trace list and settings; --load skips training and refuses
#   encoders trained on other traces/settings. --prior {flat,backoff} picks the Dirichlet prior
#   (backoff = hierarchical back-off to the trace's global outcome distribution, see
#   efe_trace_analysis.Beliefs). --wide-gens sets GA generations for the width-WIDTH layers only
#   (outcome and narrow nets stay at 60). Scoring runs every (arm, trace) pair in --workers
#   processes (same numbers as the serial loop); per-arm seconds are now summed CPU seconds, and
#   wall time is reported per stage. Arms file: <out>/arms.json, or arms_<tag>.json with --tag.
# SRP/DRY check: Pass -- features/encoders/arms of round one are imported from ebul_perception.py,
#   the Dirichlet analysis from efe_trace_analysis.py (which gained outcome_fn/outcome_vocab hooks),
#   and the learner is ebul.py unchanged. This file adds only the kernel bank, the change coder and
#   the wide conv perception.
"""Round two: EBUL perception with a hard-coded convolution front end, wide nets, learned outcomes.

Usage:
    python distill/ebul_perception_conv.py --n 53 --width 120 --out distill/results/efe_trace_analysis/conv53
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import pickle
import statistics as st
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import convolve

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ebul  # noqa: E402
import ebul_perception as ep  # noqa: E402
import efe_trace_analysis as efe  # noqa: E402

N_TRAIN = 1000
NOVEL = "<novel>"


# ---------------------------------------------------------------- kernel bank

def ricker1d(size: int) -> np.ndarray:
    """Mexican-hat profile sampled on `size` points, zero mean."""
    sigma = size / 4
    x = np.arange(size) - size // 2
    w = (1 - (x / sigma) ** 2) * np.exp(-(x ** 2) / (2 * sigma ** 2))
    return w - w.mean()


def line_kernel(profile: np.ndarray, direction: str) -> np.ndarray:
    n = len(profile)
    k = np.zeros((n, n))
    c = n // 2
    for i, v in enumerate(profile):
        d = i - c
        y, x = {"x": (c, i), "y": (i, c), "xy": (i, i), "yx": (i, n - 1 - i)}[direction]
        k[y, x] = v
    return k


def kernel_bank() -> list[tuple[str, np.ndarray]]:
    bank = [("dx", np.array([[-1.0, 0.0, 1.0]])), ("dy", np.array([[-1.0], [0.0], [1.0]])),
            ("dxy", np.array([[-1.0, 0, 0], [0, 0, 0], [0, 0, 1.0]])),
            ("dyx", np.array([[0, 0, -1.0], [0, 0, 0], [1.0, 0, 0]]))]
    for size in (3, 5, 7):
        prof = ricker1d(size)
        for d in ("x", "y", "xy", "yx"):
            bank.append((f"hat{size}{d}", line_kernel(prof, d)))
    for size in (3, 5):
        r = ricker1d(size)
        g = np.outer(np.ones(size), r) + np.outer(r, np.ones(size))
        bank.append((f"hat{size}iso", g - g.mean()))
    return bank


BANK = kernel_bank()


def response_maps(channels: list[np.ndarray]) -> np.ndarray:
    """(len(channels) * len(BANK), H, W) absolute responses."""
    return np.stack([np.abs(convolve(ch, k, mode="constant", cval=0.0)) for ch in channels for _, k in BANK])


def pool(maps: np.ndarray, grid: int) -> np.ndarray:
    """Mean over a grid x grid tiling of each map."""
    n, h, w = maps.shape
    ys = np.linspace(0, h, grid + 1).astype(int)
    xs = np.linspace(0, w, grid + 1).astype(int)
    out = [maps[:, ys[i]:ys[i + 1], xs[j]:xs[j + 1]].mean(axis=(1, 2)) for i in range(grid) for j in range(grid)]
    return np.stack(out, axis=1).ravel()


def crop(maps: np.ndarray, r: int, c: int, size: int = ep.PATCH) -> np.ndarray:
    h = size // 2
    pad = np.pad(maps, ((0, 0), (h, h), (h, h)))
    return pad[:, r:r + size, c:c + size]


# ---------------------------------------------------------------- per-board cache

class BoardMaps:
    """Base channels and kernel responses of one board, computed once."""

    def __init__(self, board):
        b = np.asarray(board, dtype=float)
        mode = np.bincount(np.asarray(board, dtype=int).ravel(), minlength=ep.N_COLOURS).argmax()
        self.board = board
        self.maps = response_maps([b / (ep.N_COLOURS - 1), (b != mode).astype(float)])

    def board_feat(self):
        return np.concatenate([ep.board_feat(self.board), pool(self.maps, 4)])

    def patch_feat(self, r, c):
        return np.concatenate([ep.patch_feat(self.board, r, c), pool(crop(self.maps, r, c), 3)])


_CACHE: dict[int, BoardMaps] = {}


def maps_of(board) -> BoardMaps:
    key = id(board)
    bm = _CACHE.get(key)
    if bm is None or bm.board is not board:
        if len(_CACHE) > 64:
            _CACHE.clear()
        bm = _CACHE[key] = BoardMaps(board)
    return bm


# ---------------------------------------------------------------- change features

def change_feat(pre, post, mask):
    """Features of one step's change, or None if nothing outside the HUD changed."""
    a = np.asarray(pre, dtype=int)
    b = np.asarray(post, dtype=int)
    ch = a != b
    for y, x in mask:
        ch[y, x] = False
    if not ch.any():
        return None
    ys, xs = np.nonzero(ch)
    r, c = int((ys.min() + ys.max()) // 2), int((xs.min() + xs.max()) // 2)
    base = [ch.astype(float), a / (ep.N_COLOURS - 1), b / (ep.N_COLOURS - 1)]
    maps = response_maps(base)
    raw = crop(np.stack(base), r, c).ravel()
    glob = np.concatenate([[np.log2(ch.sum()) / 12, (ys.max() - ys.min() + 1) / 64, (xs.max() - xs.min() + 1) / 64],
                           ep.colour_hist(a[ch]), ep.colour_hist(b[ch])])
    return np.concatenate([raw, pool(crop(maps, r, c), 3), glob])


class OutcomeCoder:
    """EBUL-trained change coder; the outcome label is 'd' + ternary code, or <novel>."""

    def __init__(self, enc: ep.Encoder, known: set):
        self.enc, self.known = enc, known

    def __call__(self, pre, post, row, mask):
        if row.get("level_completed"):
            return "level_clear"
        if row.get("game_over"):
            return "game_over"
        if not pre or not post:
            return NOVEL
        f = change_feat(pre, post, mask)
        if f is None:
            return "nothing"
        label = "d" + "".join("+0-"[1 - v] for v in self.enc.code(f))
        return label if label in self.known else NOVEL

    def vocab(self):
        return sorted(self.known) + [NOVEL]


# ---------------------------------------------------------------- wide conv perception

class ConvNetPerception(ep.NetPerception):
    def _board_code(self, pre):
        if self._cache_board is not pre:          # object identity, not id() (see ep.NetPerception)
            self._cache_board, self._cache = pre, self.benc.code(maps_of(pre).board_feat())
        return self._cache

    def context(self, row, pre):
        name = row.get("action_name")
        if not pre:
            return (name, "nopre")
        if name == "ACTION6":
            m = efe.MOUSE_RE.search(row.get("action_display", ""))
            r, c = (int(m.group(1)), int(m.group(2))) if m else (-1, -1)
            if not (0 <= r < len(pre) and 0 <= c < len(pre[0])):
                return ("M", "off")
            return ("M", "p") + self.penc.code(maps_of(pre).patch_feat(r, c))
        return (name, "b") + self._board_code(pre)

    def candidates(self, pre, buttons, clicking):
        if not pre:
            return set(buttons)
        code = self._board_code(pre)
        out = {(b[0], "b") + code for b in buttons}
        if clicking:
            centres = ep.object_centres(pre)
            if centres:
                bm = maps_of(pre)
                X = np.stack([bm.patch_feat(r, c) for r, c in centres])
                out |= {("M", "p") + tuple(int(v) for v in t) for t in self.penc.code_matrix(X)}
        return out


class Flat:
    name = "flat"

    def context(self, row, pre):
        return ("any",)

    def candidates(self, pre, buttons, clicking):
        return {("any",)}


# ---------------------------------------------------------------- data

def collect(paths, rng):
    boards, clicks, changes = [], [], []
    for p in paths:
        _, board, actions = efe.load_trace(p)
        mask = efe.hud_mask([board] + [a.get("board") for a in actions])
        pre = board
        for a in actions:
            post = a.get("board")
            if pre:
                boards.append(pre)
                if a.get("action_name") == "ACTION6":
                    m = efe.MOUSE_RE.search(a.get("action_display", ""))
                    if m:
                        clicks.append((pre, int(m.group(1)), int(m.group(2))))
                if post and a.get("action_name") != "RESET" and not a.get("level_completed"):
                    changes.append((pre, post, mask))
            pre = post
    return boards, clicks, changes


def sample(items, n, rng):
    idx = rng.choice(len(items), size=min(n, len(items)), replace=False)
    return [items[i] for i in idx]


def train(args, paths, rng):
    """Features, then the outcome coder and narrow nets (60 gens), then the wide nets (args.wide_gens)."""
    timings = {}
    t0 = time.time()
    boards, clicks, changes = collect(paths, rng)
    Xb_raw, Xp_raw = ep.training_sets(paths, rng)           # last round's raw features (narrow arm)
    Xb = np.stack([maps_of(b).board_feat() for b in sample(boards, N_TRAIN, rng)])
    pts = list(clicks)
    for b in sample(boards, 100, rng):
        pts += [(b, r, c) for r, c in ep.object_centres(b)]
    Xp = np.stack([maps_of(b).patch_feat(r, c) for b, r, c in sample(pts, N_TRAIN, rng)])
    feats = [change_feat(*x) for x in sample(changes, 3 * N_TRAIN, rng)]
    Xo = np.stack([f for f in feats if f is not None][:N_TRAIN])
    timings["features_s"] = round(time.time() - t0, 1)
    print(f"features {timings['features_s']}s: board {Xb.shape}, patch {Xp.shape}, change {Xo.shape}", flush=True)

    ep.HIDDEN, ep.GENS = (12, 8), 60
    t0 = time.time()
    oenc = ep.Encoder(Xo, True, 500 + args.seed)            # outcome coder: conv front end, 12/8
    known = {"d" + "".join("+0-"[1 - v] for v in t) for t in oenc.code_matrix(Xo)}
    nb_raw, np_raw = ep.Encoder(Xb_raw, True, 100 + args.seed), ep.Encoder(Xp_raw, True, 200 + args.seed)
    timings["train_outcome_and_narrow_s"] = round(time.time() - t0, 1)
    print("timings so far:", timings, flush=True)
    ep.HIDDEN, ep.GENS, ep.GA_VERBOSE = (args.width, args.width), args.wide_gens, True
    t0 = time.time()
    print(f"wide board net, {args.wide_gens} generations per layer:", flush=True)
    wb = ep.Encoder(Xb, True, 300 + args.seed)
    timings["train_wide_board_s"] = round(time.time() - t0, 1)
    print(f"wide patch net, {args.wide_gens} generations per layer:", flush=True)
    wp = ep.Encoder(Xp, True, 400 + args.seed)
    timings["train_wide_s"] = round(time.time() - t0, 1)
    ep.GENS, ep.GA_VERBOSE = 60, False
    rb, rp = ep.Encoder(Xb, False, 600 + args.seed), ep.Encoder(Xp, False, 700 + args.seed)
    return {"meta": {"n": args.n, "seed": args.seed, "width": args.width, "wide_gens": args.wide_gens,
                     "paths": paths, "timings": timings},
            "enc": {"outcome": oenc, "narrow_board": nb_raw, "narrow_patch": np_raw, "wide_board": wb,
                    "wide_patch": wp, "random_board": rb, "random_patch": rp},
            "known": sorted(known)}


def load_bundle(path, args, paths):
    """Load pickled encoders; refuse if they were trained on a different trace set or settings."""
    with open(path, "rb") as fh:
        bundle = pickle.load(fh)
    meta = bundle["meta"]
    want = {"n": args.n, "seed": args.seed, "width": args.width, "paths": paths}
    if args.wide_gens_given:
        want["wide_gens"] = args.wide_gens
    bad = [k for k, v in want.items() if meta.get(k) != v]
    if bad:
        raise SystemExit(f"{path}: encoders do not match this run on {bad}; retrain instead of --load")
    return bundle


# ---------------------------------------------------------------- parallel scoring

_JOB = {}   # per-worker: arms, coder, paths, prior, beta (set once by _init_scorer)


def _init_scorer(arms, coder, paths, prior, beta):
    _JOB.update(arms=arms, coder=coder, paths=paths, prior=prior, beta=beta)


def _score(job):
    ai, pi = job
    t0 = time.time()
    coder = _JOB["coder"]
    r = efe.analyse(_JOB["paths"][pi], None, _JOB["arms"][ai], coder, coder.vocab(),
                    prior=_JOB["prior"], beta=_JOB["beta"])
    s = [x for x in r["steps"] if not x.get("reset")]
    bad = sum(not (np.isfinite(x["surprisal"]) and np.isfinite(x["bayes_surprise"])) for x in s)
    return ai, pi, efe.summary(r), sum(x["outcome"] == NOVEL for x in s), bad, time.time() - t0


def score_arms(arms, coder, paths, prior, beta, workers):
    """Every (arm, trace) pair in a process pool; results identical to the serial loop."""
    jobs = [(ai, pi) for ai in reversed(range(len(arms))) for pi in range(len(paths))]  # heavy arms first
    out = {}
    if workers > 1:
        with mp.get_context("spawn").Pool(workers, _init_scorer, (arms, coder, paths, prior, beta)) as procs:
            for ai, pi, sm, nov, bad, secs in procs.imap_unordered(_score, jobs):
                out[ai, pi] = (sm, nov, bad, secs)
    else:
        _init_scorer(arms, coder, paths, prior, beta)
        for job in jobs:
            ai, pi, sm, nov, bad, secs = _score(job)
            out[ai, pi] = (sm, nov, bad, secs)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=53)
    ap.add_argument("--width", type=int, default=120)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--workers", type=int, default=12, help="processes for EBUL fitness and for scoring")
    ap.add_argument("--wide-gens", type=int, default=None,
                    help="GA generations per layer for the wide nets only (default 60, as round two)")
    ap.add_argument("--prior", choices=("flat", "backoff"), default="flat",
                    help="per-context Dirichlet prior in the analysis (efe_trace_analysis.Beliefs)")
    ap.add_argument("--beta", type=float, default=efe.BACKOFF_BETA, help="back-off prior strength")
    ap.add_argument("--load", action="store_true", help="skip training; load <out>/encoders.pkl")
    ap.add_argument("--tag", default="", help="arms file name suffix: arms_<tag>.json (default arms.json)")
    args = ap.parse_args()
    args.wide_gens_given = args.wide_gens is not None
    if args.wide_gens is None:
        args.wide_gens = 60
    ep.WORKERS = args.workers
    rng = np.random.default_rng(args.seed)
    paths = ep.trace_paths(args.n)
    out = Path(args.out) if args.out else None
    enc_path = out / "encoders.pkl" if out else None
    print(f"{len(paths)} traces; kernels: {len(BANK)} ({', '.join(n for n, _ in BANK)}); prior {args.prior}"
          + (f" beta {args.beta}" if args.prior == "backoff" else ""), flush=True)
    t_all = time.time()

    if args.load:
        if not enc_path:
            raise SystemExit("--load needs --out (the encoders live in <out>/encoders.pkl)")
        t0 = time.time()
        bundle = load_bundle(enc_path, args, paths)
        print(f"loaded {enc_path} in {time.time() - t0:.1f}s (trained with wide_gens "
              f"{bundle['meta']['wide_gens']}; training timings {bundle['meta']['timings']})", flush=True)
    else:
        bundle = train(args, paths, rng)
        if enc_path:
            out.mkdir(parents=True, exist_ok=True)
            with open(enc_path, "wb") as fh:
                pickle.dump(bundle, fh)
            print(f"saved encoders to {enc_path}", flush=True)
    timings = dict(bundle["meta"]["timings"]) if not args.load else {}
    e = bundle["enc"]
    coder = OutcomeCoder(e["outcome"], set(bundle["known"]))
    width = bundle["meta"]["width"]
    stats = {}
    for nm, key in (("outcome 12/8", "outcome"), ("narrow board", "narrow_board"), ("narrow patch", "narrow_patch"),
                    (f"wide board {width}", "wide_board"), (f"wide patch {width}", "wide_patch"),
                    ("random wide board", "random_board"), ("random wide patch", "random_patch")):
        stats[key] = {"gzip_bits_per_sample": e[key].train_bits, "distinct_codes": e[key].train_codes}
        print(f"  {nm:<20} gzip {e[key].train_bits:6.2f} bits/sample, {e[key].train_codes:4d} distinct codes")
    print(f"  outcome alphabet: {len(coder.known)} learned change codes + nothing/level_clear/game_over/novel")
    print("training timings:", bundle["meta"]["timings"], flush=True)

    arms = [Flat(), ep.NoPerception(), efe.HandmadePerception(), ep.HandState(),
            ep.NetPerception("ebul-narrow", e["narrow_board"], e["narrow_patch"]),
            ConvNetPerception(f"random-conv{width}", e["random_board"], e["random_patch"]),
            ConvNetPerception(f"ebul-conv{width}", e["wide_board"], e["wide_patch"])]
    t0 = time.time()
    scored = score_arms(arms, coder, paths, args.prior, args.beta, args.workers)
    timings["analysis_wall_s"] = round(time.time() - t0, 1)
    rows, per = [], {}
    for ai, arm in enumerate(arms):
        res = [scored[ai, pi] for pi in range(len(paths))]
        sums = [r[0] for r in res]
        steps = sum(s["steps"] for s in sums)
        per[arm.name] = [s["surprisal_per_step"] for s in sums]
        nonfinite = sum(r[2] for r in res)
        if nonfinite:
            print(f"WARNING: {arm.name}: {nonfinite} steps with non-finite surprisal or Bayesian surprise")
        rows.append({"arm": arm.name, "seconds_cpu": round(sum(r[3] for r in res), 1),
                     "nats_per_step": sum(s["surprisal_per_step"] * s["steps"] for s in sums) / steps,
                     "median_trace_nats_per_step": st.median(per[arm.name]),
                     "top_eig_median": st.median(s["chose_top_eig_share"] for s in sums),
                     "novel_outcome_share": sum(r[1] for r in res) / steps, "nonfinite_steps": nonfinite})
    flat = rows[0]["nats_per_step"]
    print(f"\n{'arm':<16}{'nats/step':>10}{'gain vs flat':>14}{'beats handmade':>16}{'topEIG':>8}{'cpu s':>8}")
    for row in rows:
        wins = sum(a < b - 1e-9 for a, b in zip(per[row["arm"]], per["handmade"]))
        row["gain_vs_flat"] = flat - row["nats_per_step"]
        row["beats_handmade_traces"] = wins
        print(f"{row['arm']:<16}{row['nats_per_step']:>10.3f}{row['gain_vs_flat']:>14.3f}"
              f"{str(wins) + '/' + str(len(paths)):>16}{row['top_eig_median']:>8.2f}{row['seconds_cpu']:>8.1f}")
    print(f"novel-outcome share (same for every arm): {rows[0]['novel_outcome_share']:.3f}")
    timings["total_wall_s"] = round(time.time() - t_all, 1)
    print("timings:", timings, flush=True)
    if out:
        out.mkdir(parents=True, exist_ok=True)
        name = f"arms_{args.tag}.json" if args.tag else "arms.json"
        (out / name).write_text(json.dumps({"rows": rows, "per_trace_nats": per, "timings": timings,
                                            "training_timings": bundle["meta"]["timings"],
                                            "encoder_stats": stats, "prior": args.prior, "beta": args.beta,
                                            "width": width, "wide_gens": bundle["meta"]["wide_gens"],
                                            "loaded": args.load, "paths": paths}, indent=1))


if __name__ == "__main__":
    main()

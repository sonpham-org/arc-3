#!/usr/bin/env python3
# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Adds a learned perception to the FEP-style trace analysis (efe_trace_analysis.py) and
#   asks whether it is better than the hand-built one. Requested by OpenMind in #arc-3,
#   23-Sep-2026: "a small nn with two hidden layers, use the EBUL", run on the first 53 traces.
#   Perception = a network with two hidden layers (tanh, 12 then 8 units) trained WITHOUT labels
#   by EBUL (ebul.py: greedy layer-wise genetic search pushing the gzip entropy of each layer's
#   ternarised code toward a target). The ternary code of the second hidden layer is the percept.
#   Two such nets are trained on the traces' own boards:
#   - a board net (input: 8x8 block-mode colours + colour histogram) -> the situation a button is
#     pressed in, so button contexts become (button, board code);
#   - a patch net (input: 9x9 window around a point + its colour histogram) -> what a click lands
#     on, so click contexts become the code of the patch under the click; candidate clicks are the
#     codes of the patches centred on every object on the board.
#   Arms compared on the same traces, same Dirichlet model, same outcome classes:
#     none      - button id only, all clicks one context (no perception)
#     handmade  - button id; click -> object shape type (the current default)
#     handstate - handmade plus exact coarse-board hash for buttons (hand-built "situation")
#     random    - the same two-hidden-layer nets with untrained random weights (control)
#     ebul      - the same nets trained by EBUL
#   "Better" is judged by prequential code length: the mean surprisal -ln p(outcome | context)
#   of each step BEFORE it is observed, under the online Dirichlet. A perception that carves the
#   world into contexts that predict what actions do scores lower; one that splits too finely pays
#   the prior cost of every fresh context, so the measure penalises both lumping and over-splitting.
#   Also reported: the top-EIG choice share and the clear vs no-clear split, per arm.
#   Reads files only; launches nothing; no harness change.
#   23-Sep-2026 round three: GENS / GA_VERBOSE module settings pass through to ebul.evolve_layer
#   (defaults 60 / False = unchanged behaviour), and the board-code cache holds the board object
#   instead of comparing id(), which could go stale when a freed board's id was reused.
# SRP/DRY check: Pass -- trace reading, HUD masking, Dirichlet model and analysis loop are imported
#   from efe_trace_analysis.py; the learner is ebul.py unchanged; this file only adds features,
#   encoders, perception classes and the comparison driver.
"""Compare perception arms (none / handmade / handstate / random net / EBUL net) on ARC-3 traces.

Usage:
    python distill/ebul_perception.py --n 53 --out distill/results/efe_trace_analysis/perception53
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ebul  # noqa: E402
import efe_trace_analysis as efe  # noqa: E402
from novelty_vs_solves import coarse_signature  # noqa: E402

HOME = Path.home()
K = HOME / "bubba-workspace/arc3-kaggle"
TRACE_GLOBS = [K / "best-7.36/output/artifacts", K / "arms/results/armA/output/artifacts",
               K / "arms/results/armB/output/artifacts", K / "arms/results/armC/output/artifacts",
               HOME / "arc3-job-output/arc3-job1-control/artifacts"]
# 23-Sep-2026 round six: the other Flash-Next prompt-matrix jobs are appended AFTER the original list,
# so trace_paths(n) for n <= 77 returns exactly the same traces as before.
TRACE_GLOBS += sorted(p for p in (HOME / "arc3-job-output").glob("arc3-job*/artifacts")
                      if p.parent.name != "arc3-job1-control")
HIDDEN = (12, 8)             # two hidden layers, as asked
TARGETS = (8.0, 5.0)         # EBUL target gzip bits per sample for layer 1 and layer 2
TRIT_K = 0.5                 # ternarisation threshold in units of the unit's std
N_TRAIN = 1500               # training samples per net
PATCH = 9
N_COLOURS = 16
WORKERS = 1                  # processes for EBUL fitness (ebul.evolve_layer workers=)
GENS = 60                    # GA generations per layer (ebul.evolve_layer default); callers may raise it
GA_VERBOSE = False           # print the GA's progress every 10 generations


# ---------------------------------------------------------------- features

def colour_hist(cells) -> np.ndarray:
    h = np.bincount(np.clip(np.asarray(cells, dtype=int).ravel(), 0, N_COLOURS - 1), minlength=N_COLOURS)
    return h / max(h.sum(), 1)


def board_feat(board) -> np.ndarray:
    b = np.asarray(board, dtype=int)
    blocks = []
    for by in range(0, b.shape[0], 8):
        for bx in range(0, b.shape[1], 8):
            blocks.append(np.bincount(b[by:by + 8, bx:bx + 8].ravel(), minlength=N_COLOURS).argmax())
    return np.concatenate([np.asarray(blocks) / (N_COLOURS - 1), colour_hist(b)])


def patch_feat(board, r, c) -> np.ndarray:
    b = np.asarray(board, dtype=int)
    h = PATCH // 2
    pad = np.pad(b, h, constant_values=-1)
    win = pad[r:r + PATCH, c:c + PATCH]
    return np.concatenate([win.ravel() / (N_COLOURS - 1), colour_hist(win[win >= 0])])


def object_centres(board):
    """Centre cell of every non-background object (via efe.component_cells)."""
    h, w = len(board), len(board[0])
    seen, out = set(), []
    for y in range(h):
        for x in range(w):
            if (y, x) in seen:
                continue
            cells = efe.component_cells(board, y, x)
            if cells is None:
                # flood the background once so we don't restart from each of its pixels
                colour, stack = board[y][x], [(y, x)]
                seen.add((y, x))
                while stack:
                    cy, cx = stack.pop()
                    for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                        if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and board[ny][nx] == colour:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                continue
            seen |= cells
            ys = sorted(y for y, _ in cells)
            xs = sorted(x for _, x in cells)
            out.append((ys[len(ys) // 2], xs[len(xs) // 2]))
    return out


# ---------------------------------------------------------------- encoders

class Encoder:
    """Two hidden tanh layers; percept = ternary code of layer 2 with frozen training stats."""

    def __init__(self, X, trained: bool, seed: int):
        self.mu_x = X.mean(0)
        self.sd_x = X.std(0) + 1e-6
        Z = (X - self.mu_x) / self.sd_x
        self.layers = []
        rng = np.random.default_rng(seed)
        inp = Z
        for li, (n_out, tgt) in enumerate(zip(HIDDEN, TARGETS)):
            n_in = inp.shape[1]
            if trained:
                params, _, _ = ebul.evolve_layer(inp, n_out, tgt, k=TRIT_K, seed=seed + li, gens=GENS,
                                                  verbose=GA_VERBOSE, workers=WORKERS)
            else:
                params = rng.normal(0, 1 / np.sqrt(n_in), n_in * n_out + n_out)
            self.layers.append((params, n_in, n_out))
            inp = ebul.layer_forward(inp, params, n_in, n_out)
        self.mu_h = inp.mean(0)
        self.sd_h = inp.std(0) + 1e-12
        T = self.code_matrix(X)
        self.train_bits = ebul.gzip_bits(T) / len(X)
        self.train_codes = len({tuple(t) for t in T})

    def forward(self, X):
        h = (np.atleast_2d(X) - self.mu_x) / self.sd_x
        for params, n_in, n_out in self.layers:
            h = ebul.layer_forward(h, params, n_in, n_out)
        return h

    def code_matrix(self, X):
        H = self.forward(X)
        T = np.zeros(H.shape, dtype=np.int8)
        T[H > self.mu_h + TRIT_K * self.sd_h] = 1
        T[H < self.mu_h - TRIT_K * self.sd_h] = -1
        return T

    def code(self, x) -> tuple:
        return tuple(int(v) for v in self.code_matrix(x)[0])


# ---------------------------------------------------------------- perceptions

class NoPerception:
    name = "none"

    def context(self, row, pre):
        return ("M", "any") if row.get("action_name") == "ACTION6" else (row.get("action_name"),)

    def candidates(self, pre, buttons, clicking):
        return set(buttons) | ({("M", "any")} if clicking else set())


class HandState(efe.HandmadePerception):
    name = "handstate"

    def context(self, row, pre):
        ctx = efe.context_of(row, pre)
        return ctx if ctx[0] == "M" else (ctx[0], "s", coarse_signature(pre) if pre else "nopre")

    def candidates(self, pre, buttons, clicking):
        sig = coarse_signature(pre) if pre else "nopre"
        return {(b[0], "s", sig) for b in buttons} | (efe.objects_on(pre) if clicking else set())


class NetPerception:
    def __init__(self, name, board_enc: Encoder, patch_enc: Encoder):
        self.name, self.benc, self.penc = name, board_enc, patch_enc
        self._cache_board, self._cache = None, None

    def _board_code(self, pre):
        # keyed on the board object itself, not id(): a freed board's id can be reused by the next
        # trace's first board, which would hand it a stale code
        if self._cache_board is not pre:
            self._cache_board, self._cache = pre, self.benc.code(board_feat(pre))
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
            return ("M", "p") + self.penc.code(patch_feat(pre, r, c))
        return (name, "b") + self._board_code(pre)

    def candidates(self, pre, buttons, clicking):
        if not pre:
            return set(buttons)
        code = self._board_code(pre)
        out = {(b[0], "b") + code for b in buttons}
        if clicking:
            centres = object_centres(pre)
            if centres:
                X = np.stack([patch_feat(pre, r, c) for r, c in centres])
                out |= {("M", "p") + tuple(int(v) for v in t) for t in self.penc.code_matrix(X)}
        return out


# ---------------------------------------------------------------- data

def trace_paths(n):
    paths = []
    for d in TRACE_GLOBS:
        paths += sorted(str(p) for p in Path(d).glob("*_events.jsonl"))
    out = []
    for p in paths:
        _, _, actions = efe.load_trace(p)
        if any(a.get("action_name") != "RESET" for a in actions):
            out.append(p)
        if len(out) >= n:
            break
    return out


def training_sets(paths, rng):
    boards, patches = [], []
    for p in paths:
        _, board, actions = efe.load_trace(p)
        pre = board
        for a in actions:
            if pre:
                boards.append(pre)
                if a.get("action_name") == "ACTION6":
                    m = efe.MOUSE_RE.search(a.get("action_display", ""))
                    if m:
                        patches.append((pre, int(m.group(1)), int(m.group(2))))
            pre = a.get("board")
    pick = rng.choice(len(boards), size=min(N_TRAIN, len(boards)), replace=False)
    Xb = np.stack([board_feat(boards[i]) for i in pick])
    # patches: clicked points plus object centres on a sample of boards, so candidates are covered
    for i in rng.choice(len(boards), size=min(150, len(boards)), replace=False):
        patches += [(boards[i], r, c) for r, c in object_centres(boards[i])]
    pick = rng.choice(len(patches), size=min(N_TRAIN, len(patches)), replace=False)
    Xp = np.stack([patch_feat(*patches[i]) for i in pick])
    return Xb, Xp


# ---------------------------------------------------------------- driver

def run_arm(perception, paths):
    t0 = time.time()
    res = [efe.analyse(p, None, perception) for p in paths]
    secs = time.time() - t0
    sums = [efe.summary(r) for r in res]
    steps = sum(s["steps"] for s in sums)
    nats = sum(s["surprisal_per_step"] * s["steps"] for s in sums)
    clear = [s for s in sums if s["levels_cleared"] > 0]
    noclr = [s for s in sums if s["levels_cleared"] == 0]
    ctxs = set()
    for r in res:
        ctxs |= {x["action"] for x in r["steps"] if not x.get("reset")}
    return {
        "arm": perception.name, "seconds": round(secs, 1), "traces": len(res), "steps": steps,
        "nats_per_step": nats / steps,
        "median_trace_nats_per_step": st.median(s["surprisal_per_step"] for s in sums),
        "top_eig_median": st.median(s["chose_top_eig_share"] for s in sums),
        "top_eig_clear_vs_none": (st.median(s["chose_top_eig_share"] for s in clear),
                                  st.median(s["chose_top_eig_share"] for s in noclr)),
        "per_trace_nats": [s["surprisal_per_step"] for s in sums],
    }, res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=53)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    paths = trace_paths(args.n)
    print(f"{len(paths)} traces")

    t0 = time.time()
    Xb, Xp = training_sets(paths, rng)
    t_feat = time.time() - t0
    t0 = time.time()
    benc, penc = Encoder(Xb, True, 100 + args.seed), Encoder(Xp, True, 200 + args.seed)
    t_train = time.time() - t0
    rb, rp = Encoder(Xb, False, 300 + args.seed), Encoder(Xp, False, 400 + args.seed)
    print(f"features {t_feat:.1f}s ({len(Xb)} boards, {len(Xp)} patches); EBUL training {t_train:.1f}s")
    for nm, e in (("EBUL board", benc), ("EBUL patch", penc), ("random board", rb), ("random patch", rp)):
        print(f"  {nm:<13} gzip {e.train_bits:.2f} bits/sample, {e.train_codes} distinct codes on train")

    arms = [NoPerception(), efe.HandmadePerception(), HandState(),
            NetPerception("random", rb, rp), NetPerception("ebul", benc, penc)]
    rows, per = [], {}
    for arm in arms:
        row, res = run_arm(arm, paths)
        rows.append(row)
        per[arm.name] = row.pop("per_trace_nats")
        print(json.dumps({k: (round(v, 4) if isinstance(v, float) else
                              [round(x, 3) for x in v] if isinstance(v, tuple) else v)
                          for k, v in row.items()}))
    base = per["handmade"]
    for name, v in per.items():
        if name != "handmade":
            wins = sum(a < b - 1e-9 for a, b in zip(v, base))
            print(f"{name:<10} lower surprisal than handmade on {wins}/{len(v)} traces")
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "arms.json").write_text(json.dumps({"rows": rows, "per_trace_nats": per,
                                                   "paths": paths, "train_seconds": t_train}, indent=1))


if __name__ == "__main__":
    main()

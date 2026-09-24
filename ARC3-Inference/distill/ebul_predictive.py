#!/usr/bin/env python3
# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Round four, expert-debate plan item 4 (OpenMind, #arc-3): "give EBUL a job". A SMALL learned
#   head on the FIXED conv features of ebul_perception_conv.py (board features for button steps,
#   9x9-patch features at the click for click steps), searched by an antithetic evolution strategy,
#   with a PREDICTIVE fitness instead of EBUL's entropy-only one. ebul.py stays untouched; its layer
#   (dense + tanh), ternarisation rule and gzip entropy measure are imported.
#   Pipeline per training fold (never sees the test traces):
#     1. PCA of the training fold's conv features to PCA_DIM whitened dimensions (board and patch
#        separately; unsupervised, fixed).
#     2. Two heads, PCA_DIM -> UNITS tanh units each, ternarised against their training-batch mean and
#        std (k = 0.5, as EBUL); the percept is the ternary code. Parameters: 2 * (24*6 + 6) = 300.
#        Context of a step = (button, board code) or ("M", patch code).
#     3. Fitness on training steps, one of
#        "dm":      predictive compression in nats/step = code length of the outcome labels given
#                   the action alone minus code length given (action, code), both as the Dirichlet-
#                   multinomial marginal likelihood with the same back-off base (beta * p_global) the
#                   yardstick uses -- i.e. the prequential code length, which is order-free under a
#                   fixed prior -- minus LAMBDA * |H(code) - H_TARGET| (bits, per head, step-weighted)
#                   as the entropy regulariser the debate kept;
#        "gzip":    the literal version: gzip bits/step of the outcome sequence sorted (stably) by
#                   action minus gzip bits/step sorted by (action, code), same regulariser;
#        "entropy": EBUL's own objective on the same head (gzip bits/sample of the ternary code
#                   pushed to GZ_TARGET), the control for "does the predictive job matter".
#     4. Antithetic ES (OpenAI-ES style: centred ranks, Adam), ITERS iterations of POP_PAIRS pairs;
#        the kept parameters are the iterate with the best fitness on a validation quarter of the
#        training traces (early stopping), frozen with their training ternarisation stats.
#   A "random" head (initial weights, no search) is the control. Outcomes are the hand-built object
#   events of object_events.py. Reads files only; launches nothing; no harness change.
# SRP/DRY check: Pass -- conv features from ebul_perception_conv.py (maps_of / BoardMaps), dense layer,
#   ternarisation k and gzip measure from ebul.py, back-off constants from efe_trace_analysis.py.
#   Nothing in distill/ searches a head with a predictive fitness.
"""Predictive EBUL head (round four, item 4)."""
from __future__ import annotations

import gzip
import time

import numpy as np
from scipy.special import gammaln

import ebul
import ebul_perception_conv as epc
import efe_trace_analysis as efe

PCA_DIM = 24
UNITS = 6
TRIT_K = 0.5
LAMBDA = 0.02          # nats per bit of |H(code) - H_TARGET|
H_TARGET = 3.0         # bits per head
GZ_TARGET = 5.0        # "entropy" objective: gzip bits/sample per head (EBUL narrow layer-two target)
ITERS = 300
POP_PAIRS = 20
SIGMA = 0.08
LR = 0.03
BUTTON_IDX = {"ACTION1": 0, "ACTION2": 1, "ACTION3": 2, "ACTION4": 3, "ACTION5": 4, "ACTION7": 5}
CLICK_IDX = 6
NCODE = 3 ** UNITS


# ---------------------------------------------------------------- features

def step_features(trace):
    """{step index: ("b", action idx, board feat) | ("p", CLICK_IDX, patch feat) | ("off"/"nopre", ...)}."""
    out = {}
    for s in trace.steps:
        if s.reset:
            continue
        name = s.row.get("action_name")
        if not s.pre:
            out[s.i] = ("nopre", name, None)
            continue
        bm = epc.maps_of(s.pre)
        if name == "ACTION6":
            m = efe.MOUSE_RE.search(s.row.get("action_display", ""))
            r, c = (int(m.group(1)), int(m.group(2))) if m else (-1, -1)
            if not (0 <= r < len(s.pre) and 0 <= c < len(s.pre[0])):
                out[s.i] = ("off", name, None)
            else:
                out[s.i] = ("p", CLICK_IDX, bm.patch_feat(r, c).astype(np.float32))
        else:
            out[s.i] = ("b", BUTTON_IDX.get(name, 5), bm.board_feat().astype(np.float32))
    return out


def _feat_job(trace):
    t0 = time.time()
    return trace.path, step_features(trace), time.time() - t0


# ---------------------------------------------------------------- PCA + head

class PCA:
    def __init__(self, X, dim):
        self.mu = X.mean(0)
        self.sd = X.std(0) + 1e-6
        Z = (X - self.mu) / self.sd
        _, s, vt = np.linalg.svd(Z, full_matrices=False)
        self.v = vt[:dim].T
        self.scale = s[:dim] / np.sqrt(len(X)) + 1e-6

    def __call__(self, X):
        # numpy 2 + macOS Accelerate raise bogus matmul FP warnings (see ebul.layer_forward); check instead
        with np.errstate(all="ignore"):
            Z = ((np.atleast_2d(X) - self.mu) / self.sd) @ self.v / self.scale
        if not np.isfinite(Z).all():
            raise FloatingPointError("non-finite PCA projection")
        return Z


def n_params():
    return 2 * (PCA_DIM * UNITS + UNITS)


def split_theta(theta):
    h = PCA_DIM * UNITS + UNITS
    return theta[:h], theta[h:]


def trits(Z, p, stats=None):
    """Ternary code matrix of one head, via ebul.layer_forward; stats = frozen (mu, sd) or None."""
    H = ebul.layer_forward(Z, p, PCA_DIM, UNITS)
    mu, sd = stats if stats is not None else (H.mean(0), H.std(0) + 1e-12)
    T = np.zeros(H.shape, dtype=np.int8)
    T[H > mu + TRIT_K * sd] = 1
    T[H < mu - TRIT_K * sd] = -1
    return T, (mu, sd)


POW3 = 3 ** np.arange(UNITS)


def code_ids(T):
    return (T.astype(np.int64) + 1) @ POW3


# ---------------------------------------------------------------- fitness

class Data:
    """Training (or validation) steps of one fold for the head search.
    items: [(kind, action idx, feature or None, outcome index)] in trace order."""

    def __init__(self, items, pca_b, pca_p, K, p_global, beta):
        kinds = [k for k, *_ in items]
        self.bmask = np.array([k == "b" for k in kinds])
        self.pmask = np.array([k == "p" for k in kinds])
        self.a = np.array([a if k in ("b", "p") else 7 for k, a, _, _ in items])
        self.o = np.array([o for _, _, _, o in items])
        self.Zb = pca_b(np.stack([f for k, _, f, _ in items if k == "b"])) if self.bmask.any() else None
        self.Zp = pca_p(np.stack([f for k, _, f, _ in items if k == "p"])) if self.pmask.any() else None
        self.K = K
        self.alpha = beta * p_global
        self.beta = beta
        self.n = len(items)
        base_ctx = self.a.astype(np.int64) * NCODE
        self.nll0 = self.dm_nll(base_ctx)
        self.gz0 = self.gz_bits(base_ctx)

    def dm_nll(self, ctx):
        pairs = ctx * self.K + self.o
        u, cnt = np.unique(pairs, return_counts=True)
        oo = u % self.K
        ll = (gammaln(self.alpha[oo] + cnt) - gammaln(self.alpha[oo])).sum()
        _, nc = np.unique(ctx, return_counts=True)
        ll += (gammaln(self.beta) - gammaln(self.beta + nc)).sum()
        return -ll

    def gz_bits(self, ctx):
        order = np.argsort(ctx, kind="stable")
        raw = self.o[order].astype(np.uint16).tobytes()
        return 8 * len(gzip.compress(raw, compresslevel=9, mtime=0))

    def contexts(self, theta, stats=None):
        pb, pp = split_theta(theta)
        ctx = self.a.astype(np.int64) * NCODE
        tb = tp = None
        st = [None, None]
        if self.Zb is not None:
            tb, st[0] = trits(self.Zb, pb, stats[0] if stats else None)
            ctx[self.bmask] += code_ids(tb)
        if self.Zp is not None:
            tp, st[1] = trits(self.Zp, pp, stats[1] if stats else None)
            ctx[self.pmask] += code_ids(tp)
        return ctx, tb, tp, st

    def fitness(self, theta, objective, stats=None):
        ctx, tb, tp, _ = self.contexts(theta, stats)
        if objective == "entropy":
            err = 0.0
            for T in (tb, tp):
                if T is not None and len(T):
                    err += abs(ebul.gzip_bits(T) / len(T) - GZ_TARGET)
            return -err
        if objective == "dm":
            gain = (self.nll0 - self.dm_nll(ctx)) / self.n
        else:
            gain = (self.gz0 - self.gz_bits(ctx)) / self.n * np.log(2)     # bits -> nats
        reg = 0.0
        for T, m in ((tb, self.bmask), (tp, self.pmask)):
            if T is not None and len(T):
                _, c = np.unique(code_ids(T), return_counts=True)
                p = c / c.sum()
                reg += m.mean() * abs(-(p * np.log2(p)).sum() - H_TARGET)
        return gain - LAMBDA * reg

    def diagnostics(self, theta, stats=None):
        ctx, tb, tp, _ = self.contexts(theta, stats)
        return {"dm_gain_nats": float((self.nll0 - self.dm_nll(ctx)) / self.n),
                "codes_board": int(len(np.unique(code_ids(tb)))) if tb is not None else 0,
                "codes_patch": int(len(np.unique(code_ids(tp)))) if tp is not None else 0}


def es_search(train: Data, val: Data, objective: str, seed: int, iters=ITERS):
    rng = np.random.default_rng(seed)
    P = n_params()
    theta = rng.normal(0, 1 / np.sqrt(PCA_DIM), P)
    if objective == "random":
        return theta, {"iters": 0}
    m = np.zeros(P)
    v = np.zeros(P)
    best, best_val, best_it = theta.copy(), -np.inf, 0
    hist = []
    for it in range(iters):
        eps = rng.normal(0, 1, (POP_PAIRS, P))
        fp = np.array([train.fitness(theta + SIGMA * e, objective) for e in eps])
        fm = np.array([train.fitness(theta - SIGMA * e, objective) for e in eps])
        allf = np.concatenate([fp, fm])
        ranks = np.empty(len(allf))
        ranks[np.argsort(allf)] = np.arange(len(allf))
        ranks = ranks / (len(allf) - 1) - 0.5
        g = ((ranks[:POP_PAIRS] - ranks[POP_PAIRS:])[:, None] * eps).sum(0) / (2 * POP_PAIRS * SIGMA)
        m = 0.9 * m + 0.1 * g
        v = 0.999 * v + 0.001 * g * g
        theta = theta + LR * (m / (1 - 0.9 ** (it + 1))) / (np.sqrt(v / (1 - 0.999 ** (it + 1))) + 1e-8)
        # validation: codes use the TRAINING batch stats of this iterate, as at test time
        _, _, _, st = train.contexts(theta)
        fv = val.fitness(theta, objective, st)
        if fv > best_val:
            best, best_val, best_it = theta.copy(), fv, it
        if it % 25 == 0 or it == iters - 1:
            hist.append((it, float(train.fitness(theta, objective)), float(fv)))
    return best, {"iters": iters, "best_iter": best_it, "best_val_fitness": float(best_val), "history": hist}


# ---------------------------------------------------------------- perception for the scorer

class HeadPerception:
    """Context = (button, board code) or ("M", patch code); codes for a whole trace are computed at
    begin(trace) from the cached features {trace path: step_features(trace)}."""

    def __init__(self, name, pca_b, pca_p, theta, stats, feats):
        self.name, self.pca_b, self.pca_p, self.stats, self.feats = name, pca_b, pca_p, stats, feats
        self.pb, self.pp = split_theta(theta)
        self.cur = {}

    def reset(self):
        pass

    def observe(self, step):
        pass

    def begin(self, trace):
        f = self.feats[trace.path]
        self.cur = {}
        for kind, head, pca, stats in (("b", self.pb, self.pca_b, self.stats[0]),
                                       ("p", self.pp, self.pca_p, self.stats[1])):
            idx = [i for i, (k, _, _) in f.items() if k == kind]
            if idx:
                T, _ = trits(pca(np.stack([f[i][2] for i in idx])), head, stats)
                self.cur.update(zip(idx, (int(c) for c in code_ids(T))))
        self.kinds = {i: k for i, (k, _, _) in f.items()}

    def context(self, step):
        name = step.row.get("action_name")
        kind = self.kinds[step.i]
        if kind == "nopre":
            return (name, "nopre")
        if kind == "off":
            return ("M", "off")
        return ((name if kind == "b" else "M"), "h", self.cur[step.i])

#!/usr/bin/env python3
# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Round four, expert-debate plan items 1, 5 and 7 (OpenMind, #arc-3): the held-out yardstick
#   for comparing perception arms on ARC-3 traces.
#   - Scoring = prequential code length (nats/step) of the object-event outcome (object_events.py)
#     under the per-context Dirichlet with the hierarchical BACK-OFF prior from
#     efe_trace_analysis.Beliefs(prior="backoff") (alpha_c = count_c + beta * p_global); this file
#     re-uses that class and only subclasses base() for the type prior (below).
#   - Splits: "pass" (as asked: two folds by pass parity, p0/p2 vs p1/p3, cross-fitted so every trace
#     is scored exactly once by a model trained on the other fold) and "game" (stricter: two folds of
#     whole games, balanced by game type). Anything learned -- EBUL heads, PCA, the outcome support,
#     the game-type prior, the pragmatic table -- sees only the training fold.
#   - Outcome support: "fixed" = labels seen in the training fold + <novel> (pass split, as specified);
#     "open" = the training labels plus any new label joining the vocabulary online through the
#     Beliefs unseen slot (game split, where three quarters of test labels never occur in the other
#     games and a fixed support would turn most outcomes into <novel>).
#   - Item 7, carry: carry=True keeps one Beliefs (and the agency tracker) per game across its test
#     traces in run-then-pass order, so counts persist across levels, passes and runs; prime=True
#     also feeds that game's training-fold traces through it first (unscored). type_prior=True backs
#     the trace-level distribution off to the outcome distribution of the same game TYPE (click /
#     button / mixed) on the training fold instead of to uniform.
#   - Item 5, pragmatic: with a table C(o) = p(level clear within k steps | outcome o) from the
#     training fold, each step's pragmatic value is sum_o p(o | context) C(o) under the beliefs BEFORE
#     the outcome; clear_auc() scores it against real clears on the test fold.
#   - Item 1 statistics: paired bootstrap over traces (every replicate recomputes both arms on the same
#     resample, step-weighted), plus a game-cluster bootstrap for the headline; per game type.
#   Reads trace files only; launches nothing; no harness change.
# SRP/DRY check: Pass -- Beliefs, perceptions (none / handmade / handstate / flat) and trace parsing
#   are imported from efe_trace_analysis.py, ebul_perception.py and ebul_perception_conv.py; this
#   file adds the fold logic, the type-prior/carry scorer, the bootstrap and the AUC.
"""Held-out prequential yardstick (round four)."""
from __future__ import annotations

import math
from collections import Counter, defaultdict

import numpy as np

import efe_trace_analysis as efe
import object_events as oe

NOVEL = oe.NOVEL
GAME_FOLD0 = {"Toggle Navigator", "Sliding Indicator", "Trail Unwind", "Skewer Kebabs", "Coded Notches",
              "Deck Control", "Streaming Purple"}          # fold 1: Functional Tiles, Locksmith,
#                                                             Buoyant Pontoons, Mirror Rendezvous
PRAG_K = 5


# ---------------------------------------------------------------- folds

def folds(traces, split: str):
    """[(train, test)] for the two cross-fitted folds; input order (run, then pass) is kept."""
    if split == "pass":
        key = lambda t: t.pass_no % 2  # noqa: E731
    elif split == "game":
        key = lambda t: 0 if t.nick in GAME_FOLD0 else 1  # noqa: E731
    else:
        raise ValueError(split)
    return [([t for t in traces if key(t) != f], [t for t in traces if key(t) == f]) for f in (0, 1)]


def support_of(train) -> list:
    """Fixed support: labels seen in the training fold (the base classes are added by Beliefs)."""
    labs = Counter(s.label for t in train for s in t.steps if not s.reset)
    return sorted(labs) + [NOVEL]


def type_counts(train, support_set) -> dict:
    out = defaultdict(Counter)
    for t in train:
        out[t.gtype].update(s.label if s.label in support_set else NOVEL for s in t.steps if not s.reset)
    return out


# ---------------------------------------------------------------- beliefs with a type prior

class TypePriorBeliefs(efe.Beliefs):
    """efe.Beliefs(prior="backoff") whose trace-level distribution backs off to a training-fold
    distribution over outcomes instead of to uniform. With top=None it is exactly the parent:
    p_global(o) = (G(o) + ALPHA * K * top(o)) / (N + ALPHA * K), top uniform = 1/K."""

    def __init__(self, vocab, beta, top: Counter | None = None):
        super().__init__(vocab, "backoff", beta)
        self.top = top
        self.top_n = sum(top.values()) if top else 0

    def base(self):
        if not self.top:
            return super().base()
        k = len(self.vocab) + 1
        w = efe.ALPHA_PRIOR * k
        z = self.global_n + w
        tz = self.top_n + k                      # add-one smoothing of the type distribution
        g, t = self.global_counts, self.top
        out = [self.beta * (g[o] + w * (t[o] + 1) / tz) / z for o in self.vocab]
        return out + [self.beta * w * 1 / tz / z]


# ---------------------------------------------------------------- perception adapters

class RowPerception:
    """Wrap a context(row, pre) perception (efe / ep / conv arms) for step-based scoring."""

    def __init__(self, inner, name=None):
        self.inner, self.name = inner, name or inner.name

    def reset(self):
        pass

    def context(self, step):
        return self.inner.context(step.row, step.pre)

    def observe(self, step):
        pass


# ---------------------------------------------------------------- scorer

def _map(label, support_set, open_vocab):
    if open_vocab or label in support_set or label in efe.BASE_OUTCOMES:
        return label
    return NOVEL


def clear_soon(trace, k=PRAG_K):
    """Per non-reset step: 1 if a level clear happens at this step or within the next k-1 actions."""
    steps = [s for s in trace.steps if not s.reset]
    clears = [s.label == "level_clear" for s in steps]
    return [int(any(clears[i:i + k])) for i in range(len(steps))]


def score(tests, perception, support, beta=efe.BACKOFF_BETA, open_vocab=False, carry=False, prime=None,
          type_top=None, C=None):
    """Prequential nats of each test trace. tests: traces in run-then-pass order.
    prime: {game: [training traces]} fed (unscored) through a game's beliefs before its first test
    trace (only with carry). type_top: {gtype: Counter} training-fold outcome counts per game type.
    C: {label: p(clear soon | label)} -> also returns per-step pragmatic value and p(clear | ctx).
    Returns [{"trace", "nats", "steps", "surprisal": [...], "prag": [...], "pclear": [...]}]."""
    support_set = set(support)
    vocab = [s for s in support if s not in efe.BASE_OUTCOMES and not (open_vocab and s == NOVEL)]
    per_game = {}
    out = []
    for t in tests:
        fresh = not carry or t.game not in per_game
        if fresh:
            top = type_top.get(t.gtype) if type_top else None
            beliefs = TypePriorBeliefs(vocab, beta, top)
            perception.reset()
            per_game[t.game] = beliefs
            if carry and prime:
                for pt in prime.get(t.game, ()):
                    if hasattr(perception, "begin"):
                        perception.begin(pt)
                    for s in pt.steps:
                        if s.reset:
                            continue
                        beliefs.update(perception.context(s), _map(s.label, support_set, open_vocab))
                        perception.observe(s)
        beliefs = per_game[t.game]
        if hasattr(perception, "begin"):
            perception.begin(t)
        sur, prag, pcl = [], [], []
        for s in t.steps:
            if s.reset:
                continue
            ctx = perception.context(s)
            o = _map(s.label, support_set, open_vocab)
            if C is not None:
                a = beliefs.alpha(ctx)
                z = sum(a)
                cv = [C.get(v, C.get(NOVEL, 0.0)) for v in beliefs.vocab] + [C.get(NOVEL, 0.0)]
                prag.append(sum(ai * ci for ai, ci in zip(a, cv)) / z)
                pcl.append(beliefs.p(ctx, "level_clear"))
            sur.append(-math.log(beliefs.p(ctx, o)))
            beliefs.update(ctx, o)
            perception.observe(s)
        out.append({"trace": t, "nats": sum(sur), "steps": len(sur), "surprisal": sur, "prag": prag,
                    "pclear": pcl})
    return out


# ---------------------------------------------------------------- pragmatic table

def level_age(trace):
    """Per non-reset step: actions since the level started (a clear or RESET starts a new level)."""
    out, age = [], 0
    for s in trace.steps:
        if s.reset:
            age = 0
            continue
        out.append(age)
        age = 0 if s.label == "level_clear" else age + 1
    return out


def clear_table(train, support_set, k=PRAG_K, prior_n=5.0) -> dict:
    """C(o) = p(clear within k steps | this step's outcome o) on the training fold, shrunk toward the
    base rate with prior_n pseudo-steps."""
    hits, n = Counter(), Counter()
    for t in train:
        y = clear_soon(t, k)
        steps = [s for s in t.steps if not s.reset]
        for s, yi in zip(steps, y):
            o = s.label if s.label in support_set else NOVEL
            n[o] += 1
            hits[o] += yi
    base = sum(hits.values()) / max(sum(n.values()), 1)
    return {o: (hits[o] + prior_n * base) / (n[o] + prior_n) for o in n} | {"__base__": base,
                                                                           NOVEL: (hits[NOVEL] + prior_n * base) / (n[NOVEL] + prior_n)}


def auc(scores, labels) -> float:
    from scipy.stats import rankdata
    s = np.asarray(scores, float)
    y = np.asarray(labels, int)
    pos, neg = y.sum(), len(y) - y.sum()
    if pos == 0 or neg == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[y == 1].sum() - pos * (pos + 1) / 2) / (pos * neg))


# ---------------------------------------------------------------- bootstrap

def per_trace(results) -> dict:
    """{trace path: (nats, steps)} from score() output (both folds concatenated)."""
    return {r["trace"].path: (r["nats"], r["steps"]) for r in results}


def paired_boot(arm: dict, ref: dict, keys, n_boot=2000, seed=0, clusters=None):
    """Point estimate and 95% percentile CIs of arm nats/step and of gain = ref - arm (paired).
    clusters: {key: cluster id} -> resample clusters (games) instead of traces."""
    rng = np.random.default_rng(seed)
    keys = list(keys)
    a = np.array([arm[k][0] for k in keys])
    r = np.array([ref[k][0] for k in keys])
    n = np.array([arm[k][1] for k in keys], float)
    point = a.sum() / n.sum()
    gain = (r.sum() - a.sum()) / n.sum()
    if clusters:
        cl = sorted({clusters[k] for k in keys})
        members = [np.array([i for i, k in enumerate(keys) if clusters[k] == c]) for c in cl]
    bs, bg = [], []
    for _ in range(n_boot):
        if clusters:
            idx = np.concatenate([members[j] for j in rng.integers(0, len(members), len(members))])
        else:
            idx = rng.integers(0, len(keys), len(keys))
        ns = n[idx].sum()
        bs.append(a[idx].sum() / ns)
        bg.append((r[idx].sum() - a[idx].sum()) / ns)
    q = lambda v: (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5)))  # noqa: E731
    return {"nats": point, "nats_ci": q(bs), "gain": gain, "gain_ci": q(bg), "traces": len(keys),
            "steps": int(n.sum())}


def within_auc(per_trace_scores) -> float:
    """AUC over positive/negative pairs from the SAME trace only (pair-weighted mean of per-trace
    AUCs), so a score that merely tells clear-rich traces from clear-poor ones gets no credit."""
    num = den = 0.0
    for s, y in per_trace_scores:
        y = np.asarray(y)
        pos = y.sum()
        neg = len(y) - pos
        if pos and neg:
            num += auc(s, y) * pos * neg
            den += pos * neg
    return num / den if den else float("nan")


def boot_within_auc(per_trace_scores, n_boot=1000, seed=0):
    rng = np.random.default_rng(seed)
    point = within_auc(per_trace_scores)
    bs = [within_auc([per_trace_scores[i] for i in rng.integers(0, len(per_trace_scores), len(per_trace_scores))])
          for _ in range(n_boot)]
    bs = [b for b in bs if not math.isnan(b)]
    return point, (float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)))


def boot_auc(per_trace_scores, n_boot=1000, seed=0):
    """per_trace_scores: [(scores, labels)] per test trace -> AUC and trace-bootstrap 95% CI."""
    rng = np.random.default_rng(seed)
    allv = lambda idx: (np.concatenate([per_trace_scores[i][0] for i in idx]),  # noqa: E731
                        np.concatenate([per_trace_scores[i][1] for i in idx]))
    s, y = allv(range(len(per_trace_scores)))
    point = auc(s, y)
    bs = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(per_trace_scores), len(per_trace_scores))
        v = auc(*allv(idx))
        if not math.isnan(v):
            bs.append(v)
    return point, (float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))) if bs else (None, None)

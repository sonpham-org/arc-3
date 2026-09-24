#!/usr/bin/env python3
# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Offline evidence for a per-turn "think hard vs think light" router (Son's ask, 23-Sep-2026)
#   on the recorded Flash-Next plays. Reads the turn table written by think_router_turns.py
#   (results/think_router/turns.jsonl) and answers three questions:
#   (a) does longer thinking on a turn go with better outcomes (a new outcome label, a level clear
#       soon), and is that concentrated in high-surprise / level-start / stalled turns? Within-play
#       AUC of thinking measures (total reasoning chars, the FIRST request's reasoning chars -- the
#       only thinking that precedes every tool result of the turn -- chars per request, request
#       count) per stratum; within-play quintile dose-response; whether the model already thinks
#       longer in those situations; and a held-out increment test (logistic on the cheap state vs the
#       same plus log thinking, whole games held out). Observational: thinking was always on.
#   (b) what share of turns is "predictable" (low surprisal of the last outcome, low predictive
#       entropy over candidate actions, no stall, not a level start), how much thinking is spent
#       there, and how many informative turns fall there (a pre-registered rule plus a grid).
#   (c) a gate that predicts "this turn's outcome is informative / progress" from pre-turn features
#       only: single-feature threshold rules (direction chosen on the training fold), the (b) rule,
#       and a tiny L2 logistic model (numpy IRLS; standardisation and fit on training folds only),
#       evaluated on held-out whole games (round5_combo.balanced_game_folds) and held-out passes;
#       within-play and pooled AUC with play- and game-cluster bootstrap CIs; operating points
#       (30% / 50% of turns routed light: thinking share saved, informative turns and clears missed).
#   The play's first turn is excluded from (a) and (c) (its first outcome is new by construction).
#   Output: results/think_router/report.md, summary.json (incl. gate coefficients), timings.json.
#   Reads the turn table only; no harness, prompt, Kaggle or Jethro change; no existing file edited.
# SRP/DRY check: Pass -- AUC from heldout_yardstick.auc, game folds from round5_combo.balanced_game_folds,
#   turn extraction in think_router_turns.py; this file adds the cluster bootstraps, the IRLS
#   logistic, the strata and the report.
"""Think-hard router: offline evidence from the per-turn table."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import warnings
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import heldout_yardstick as hy  # noqa: E402
import round5_combo as r5  # noqa: E402

OUT = Path(__file__).parent / "results/think_router"
# numpy 2 on macOS Accelerate emits spurious "divide by zero / overflow in matmul" warnings on finite
# inputs; the IRLS fit was checked against scipy L-BFGS on the same objective (coefficients agree to 1e-3).
warnings.filterwarnings("ignore", message=".*encountered in matmul")
N_BOOT = 1000
LAM = 1.0                       # L2 on standardised coefficients (intercept unpenalised)
CHARS_PER_TOKEN = None          # filled from calibration.json
# pre-registered "predictable turn" rule (fixed before looking at outcomes; grid reported beside it)
PRED_SURP, PRED_ENT, PRED_STALL = 1.0, 1.5, 10
HIGH_SURP = 3.0                 # nats: last outcome had p <= 5% under the chain back-off
STALL = 10                      # actions since the last new outcome or clear
LIGHT_SHARES = (0.3, 0.5)
TARGETS = ("info", "clear10", "clear5", "new")

STATE = ["last_surp", "no_prev", "prev_max_surp", "prev_mean_surp", "ent_mean", "ent_min", "ent_max",
         "pnovel_mean", "pnovel_max", "untried_btn_share", "l_untried_click", "first_turn", "just_cleared",
         "after_reset", "level_start", "l_stall_actions", "l_stall_turns", "l_actions_in_level", "l_turn_idx",
         "level", "l_last_batch", "g_click", "g_button", "l_vocab"]
PLAIN = {
    "last_surp": "surprisal of the last outcome", "no_prev": "no previous outcome", "prev_max_surp": "max surprisal last turn",
    "prev_mean_surp": "mean surprisal last turn", "ent_mean": "mean predictive entropy over candidates",
    "ent_min": "lowest candidate entropy", "ent_max": "highest candidate entropy", "pnovel_mean": "mean unseen-outcome mass",
    "pnovel_max": "max unseen-outcome mass", "untried_btn_share": "share of buttons never pressed",
    "l_untried_click": "clickable object types never clicked (log)", "first_turn": "first turn of the play",
    "just_cleared": "previous turn cleared a level", "after_reset": "after RESET / game over", "level_start": "level start (any of the three)",
    "l_stall_actions": "actions since last new outcome (log)", "l_stall_turns": "turns since last informative turn (log)",
    "l_actions_in_level": "actions into the level (log)", "l_turn_idx": "turn index (log)", "level": "level index",
    "l_last_batch": "actions issued last turn (log)", "g_click": "click-only game", "g_button": "button-only game",
    "l_vocab": "outcome labels seen so far (log)", "elapsed_k": "wall seconds since play start / 1000",
    "l_think_total": "log reasoning chars, whole turn", "l_think_first": "log reasoning chars, first request",
    "l_requests": "log request count"}


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- data

def load(path: Path):
    rows = [json.loads(line) for line in open(path)]
    el = [r["elapsed_s"] for r in rows if r.get("elapsed_s") is not None]
    el_med = float(np.median(el)) if el else 0.0
    for r in rows:
        r["no_prev"] = int(r["last_surp"] is None)
        r["last_surp"] = r["last_surp"] if r["last_surp"] is not None else 0.0
        for k in ("prev_max_surp", "prev_mean_surp", "untried_btn_share"):
            r[k] = r[k] if r[k] is not None else 0.0
        r["l_untried_click"] = math.log1p(r["untried_click_types"] or 0)
        for k in ("stall_actions", "stall_turns", "actions_in_level", "turn_idx", "last_batch", "vocab"):
            r["l_" + k] = math.log1p(r[k])
        r["level"] = min(r["level"] or 1, 5)
        r["g_click"] = int(r["gtype"] == "click")
        r["g_button"] = int(r["gtype"] == "button")
        r["elapsed_k"] = (r["elapsed_s"] if r.get("elapsed_s") is not None else el_med) / 1000.0
        r["l_think_total"] = math.log1p(r["think_total"])
        r["l_think_first"] = math.log1p(r["think_first"])
        r["l_requests"] = math.log1p(r["n_requests"])
        r["think_per_req"] = r["think_total"] / r["n_requests"] if r["n_requests"] else 0.0
        r["predictable"] = int(r["last_surp"] < PRED_SURP and r["ent_mean"] < PRED_ENT and r["stall_actions"] < PRED_STALL
                               and not r["level_start"] and not r["no_prev"])
        r["high_surp"] = int(r["last_surp"] >= HIGH_SURP)
        r["stalled"] = int(r["stall_actions"] >= STALL)
    return rows


def by_play(rows):
    d = defaultdict(list)
    for r in rows:
        d[r["path"]].append(r)
    return d


# ---------------------------------------------------------------- AUC + bootstraps

def per_play_auc(groups, score_fn, y_key):
    """[(auc, weight, game)] per play; weight = positive x negative pairs (within-play AUC pieces)."""
    out = []
    for plays in groups:
        s = np.array([score_fn(r) for r in plays], float)
        y = np.array([r[y_key] for r in plays], int)
        pos = int(y.sum())
        neg = len(y) - pos
        if pos and neg:
            out.append((hy.auc(s, y), pos * neg, plays[0]["nick"]))
    return out


def within(pieces):
    w = sum(p[1] for p in pieces)
    return sum(p[0] * p[1] for p in pieces) / w if w else float("nan")


def boot_within(pieces, cluster=False, n=N_BOOT, seed=0, paired=None):
    """95% CI of the within-play AUC (or of a paired difference when paired= is a second piece list
    over the same plays). cluster=True resamples games (all their plays) instead of plays."""
    rng = np.random.default_rng(seed)
    a = np.array([p[0] for p in pieces])
    w = np.array([p[1] for p in pieces], float)
    b = np.array([p[0] for p in paired]) if paired is not None else None
    if cluster:
        games = sorted({p[2] for p in pieces})
        members = [np.array([i for i, p in enumerate(pieces) if p[2] == g]) for g in games]
    vals = []
    for _ in range(n):
        if cluster:
            idx = np.concatenate([members[j] for j in rng.integers(0, len(members), len(members))])
        else:
            idx = rng.integers(0, len(pieces), len(pieces))
        ww = w[idx]
        if ww.sum() == 0:
            continue
        v = (a[idx] * ww).sum() / ww.sum()
        if b is not None:
            v -= (b[idx] * ww).sum() / ww.sum()
        vals.append(v)
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def pooled_boot(rows, score_fn, y_key, cluster=False, n=N_BOOT, seed=0):
    groups = by_play(rows)
    keys = sorted(groups)
    s = {k: np.array([score_fn(r) for r in groups[k]], float) for k in keys}
    y = {k: np.array([r[y_key] for r in groups[k]], int) for k in keys}
    point = hy.auc(np.concatenate([s[k] for k in keys]), np.concatenate([y[k] for k in keys]))
    rng = np.random.default_rng(seed)
    if cluster:
        games = sorted({groups[k][0]["nick"] for k in keys})
        members = [[k for k in keys if groups[k][0]["nick"] == g] for g in games]
    vals = []
    for _ in range(n):
        if cluster:
            ks = [k for j in rng.integers(0, len(members), len(members)) for k in members[j]]
        else:
            ks = [keys[j] for j in rng.integers(0, len(keys), len(keys))]
        v = hy.auc(np.concatenate([s[k] for k in ks]), np.concatenate([y[k] for k in ks]))
        if not math.isnan(v):
            vals.append(v)
    return point, (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)))


def auc_block(rows, score_fn, y_key, seed=0):
    """Within-play AUC with play and game CIs, plus pooled AUC with play and game CIs."""
    pieces = per_play_auc(by_play(rows).values(), score_fn, y_key)
    wp = within(pieces)
    out = {"within": wp, "within_ci_play": boot_within(pieces, seed=seed),
           "within_ci_game": boot_within(pieces, cluster=True, seed=seed), "plays_with_pairs": len(pieces),
           "turns": len(rows), "positives": int(sum(r[y_key] for r in rows))}
    p, ci = pooled_boot(rows, score_fn, y_key, seed=seed)
    _, cig = pooled_boot(rows, score_fn, y_key, cluster=True, seed=seed)
    out.update({"pooled": p, "pooled_ci_play": ci, "pooled_ci_game": cig})
    return out


def fmt(v, ci=None, d=3):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "n/a"
    s = f"{v:.{d}f}"
    if ci:
        s += f" [{ci[0]:.{d}f}, {ci[1]:.{d}f}]"
    return s


# ---------------------------------------------------------------- logistic (IRLS, L2)

def fit_logit(X, y, lam=LAM, iters=50):
    n, k = X.shape
    Xi = np.hstack([np.ones((n, 1)), X])
    w = np.zeros(k + 1)
    pen = np.full(k + 1, lam)
    pen[0] = 0.0
    for _ in range(iters):
        z = Xi @ w
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        g = Xi.T @ (p - y) + pen * w
        H = (Xi * (p * (1 - p))[:, None]).T @ Xi + np.diag(pen) + 1e-9 * np.eye(k + 1)
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return w


class Logit:
    def __init__(self, feats, lam=LAM):
        self.feats, self.lam = feats, lam

    def fit(self, rows, y_key):
        X = np.array([[r[f] for f in self.feats] for r in rows], float)
        self.mu, self.sd = X.mean(0), X.std(0)
        self.sd[self.sd == 0] = 1.0
        self.w = fit_logit((X - self.mu) / self.sd, np.array([r[y_key] for r in rows], float), self.lam)
        return self

    def score(self, r):
        x = (np.array([r[f] for f in self.feats], float) - self.mu) / self.sd
        return float(self.w[0] + x @ self.w[1:])


# ---------------------------------------------------------------- folds

def folds(rows, split):
    plays = by_play(rows)
    if split == "game":
        objs = [SimpleNamespace(nick=v[0]["nick"], gtype=v[0]["gtype"], path=k) for k, v in plays.items()]
        fl, fold_of = r5.balanced_game_folds(objs)
        key = lambda r: fold_of[r["nick"]]  # noqa: E731
    else:
        fold_of = None
        key = lambda r: r["pass"] % 2  # noqa: E731
    out = []
    for f in (0, 1):
        out.append(([r for r in rows if key(r) != f], [r for r in rows if key(r) == f]))
    return out, fold_of


def cross_fit(rows, split, make_scorer, y_key):
    """Fit on one fold, score the other; returns {id(row): score} for every row exactly once."""
    fl, _ = folds(rows, split)
    scores = {}
    for train, test in fl:
        sc = make_scorer(train, y_key)
        for r in test:
            scores[id(r)] = sc(r)
    return scores


# ---------------------------------------------------------------- question (a)

def question_a(A, rep, S):
    rep.append("## (a) Does longer thinking go with better outcomes?\n")
    rep.append("The play's first turn is left out of (a) and (c): its first outcome is new by construction (every "
               "first turn is 'informative'), and it runs many short requests, which made a spurious level-start "
               "result in the first draft. A router should simply treat the first turn as hard.\n")
    rep.append("Within-play AUC: for pairs of turns from the SAME play, one with the outcome and one without, "
               "how often the turn with the outcome had more thinking (0.5 = no association). "
               "95% CIs: play bootstrap / game-cluster bootstrap.\n")
    strata = {
        "all acting turns": lambda r: True,
        "level start (not the first turn)": lambda r: r["level_start"] == 1,
        "  just cleared": lambda r: r["just_cleared"] == 1,
        "  after RESET / game over": lambda r: r["after_reset"] == 1,
        "high surprise (last outcome p <= 5%)": lambda r: r["high_surp"] == 1 and not r["level_start"],
        "stalled (>= 10 actions without a new outcome)": lambda r: r["stalled"] == 1 and not r["level_start"],
        "predictable (rule of b)": lambda r: r["predictable"] == 1,
        "other": lambda r: not (r["level_start"] or r["high_surp"] or r["stalled"] or r["predictable"]),
        "single-action turns": lambda r: r["n_actions"] == 1,
    }
    measures = {"total reasoning chars": "think_total", "first request's chars": "think_first",
                "chars per request": "think_per_req", "request count": "n_requests"}
    S["a_auc"] = {}
    for y_key, yname in (("info", "new outcome label or clear in the turn"), ("clear10", "level clear within 10 actions"),
                         ("new", "new outcome label in the turn")):
        rep.append(f"\n### Target: {yname} (base rate {np.mean([r[y_key] for r in A]):.3f})\n")
        rep.append("| stratum | turns | " + " | ".join(measures) + " |")
        rep.append("|---|---|" + "---|" * len(measures))
        for sname, sf in strata.items():
            sub = [r for r in A if sf(r)]
            cells = []
            for mname, mk in measures.items():
                pieces = per_play_auc(by_play(sub).values(), lambda r, mk=mk: r[mk], y_key)
                v = within(pieces)
                ci = boot_within(pieces) if pieces else None
                cig = boot_within(pieces, cluster=True) if pieces else None
                S["a_auc"][f"{y_key}|{sname}|{mname}"] = {"within": v, "ci_play": ci, "ci_game": cig, "plays": len(pieces),
                                                          "turns": len(sub)}
                cells.append(f"{fmt(v)} [{fmt(ci[0]) if ci else ''}, {fmt(ci[1]) if ci else ''}] / [{fmt(cig[0]) if cig else ''}, {fmt(cig[1]) if cig else ''}]")
            npl = len(per_play_auc(by_play(sub).values(), lambda r: 0.0, y_key))
            rep.append(f"| {sname} | {len(sub)} ({npl} plays with pairs) | " + " | ".join(cells) + " |")

    # dose-response by within-play quintile of total thinking
    rep.append("\n### Dose-response: within-play quintile of total reasoning chars\n")
    rep.append("| quintile (1 = least in its play) | turns | median chars | new or clear | clear within 10 | "
               "actions issued (mean) | new labels per action | requests (mean) |")
    rep.append("|---|---|---|---|---|---|---|---|")
    q_of = {}
    for plays in by_play(A).values():
        v = np.array([r["think_total"] for r in plays], float)
        ranks = v.argsort().argsort() / max(len(v) - 1, 1)
        for r, q in zip(plays, ranks):
            q_of[id(r)] = min(int(q * 5), 4)
    S["a_dose"] = []
    for q in range(5):
        sub = [r for r in A if q_of[id(r)] == q]
        newpa = sum(r["new"] for r in sub) / max(sum(r["n_actions"] for r in sub), 1)
        row = {"q": q + 1, "turns": len(sub), "median_chars": float(np.median([r["think_total"] for r in sub])),
               "info": float(np.mean([r["info"] for r in sub])), "clear10": float(np.mean([r["clear10"] for r in sub])),
               "actions": float(np.mean([r["n_actions"] for r in sub])), "new_per_action": newpa,
               "requests": float(np.mean([r["n_requests"] for r in sub]))}
        S["a_dose"].append(row)
        rep.append(f"| {q + 1} | {len(sub)} | {row['median_chars']:.0f} | {row['info']:.3f} | {row['clear10']:.3f} | "
                   f"{row['actions']:.2f} | {row['new_per_action']:.3f} | {row['requests']:.2f} |")

    # does the model already think longer in these situations?
    rep.append("\n### Does the model already spend more thinking in these situations?\n")
    rep.append("Mean within-play percentile of total reasoning chars (0.5 = the play's typical turn), with play-bootstrap CI.\n")
    rep.append("| situation | turns | percentile when true | when false |")
    rep.append("|---|---|---|---|")
    pct = {}
    for plays in by_play(A).values():
        v = np.array([r["think_total"] for r in plays], float)
        from scipy.stats import rankdata
        rk = (rankdata(v) - 1) / max(len(v) - 1, 1)
        for r, p in zip(plays, rk):
            pct[id(r)] = p
    S["a_already"] = {}
    rng = np.random.default_rng(0)
    groups = list(by_play(A).values())
    for name, f in (("level start (not the first turn)", "level_start"), ("just cleared", "just_cleared"),
                    ("after RESET / game over", "after_reset"), ("high surprise", "high_surp"), ("stalled", "stalled"),
                    ("predictable", "predictable")):
        t = [pct[id(r)] for r in A if r[f]]
        fz = [pct[id(r)] for r in A if not r[f]]
        bs = []
        for _ in range(N_BOOT):
            gi = rng.integers(0, len(groups), len(groups))
            tt = [pct[id(r)] for j in gi for r in groups[j] if r[f]]
            if tt:
                bs.append(np.mean(tt))
        ci = (float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)))
        S["a_already"][name] = {"true": float(np.mean(t)) if t else None, "ci": ci, "false": float(np.mean(fz)), "n": len(t)}
        rep.append(f"| {name} | {len(t)} | {fmt(float(np.mean(t)) if t else None, ci)} | {np.mean(fz):.3f} |")
    # rank correlation with continuous features
    from scipy.stats import spearmanr
    rep.append("\nWithin-play Spearman of total reasoning chars with (median over plays with >= 10 turns): " +
               ", ".join(f"{PLAIN.get(f, f)} {np.nanmedian([spearmanr([r['think_total'] for r in g], [r[f] for r in g])[0] for g in groups if len(g) >= 10]):+.2f}"
                         for f in ("last_surp", "ent_mean", "l_stall_actions", "l_turn_idx", "elapsed_k", "n_actions")) + ".\n")

    # held-out increment of thinking over the cheap state
    rep.append("\n### Does thinking add anything once the pre-turn state is known? (held-out whole games)\n")
    rep.append("Logistic on the pre-turn state (+ wall seconds since play start as the budget proxy), with and "
               "without log thinking; fit on one game fold, scored on the other. Within-play AUC; delta with paired "
               "play / game-cluster CIs.\n")
    rep.append("| target | state only | + first request's chars | delta | + whole-turn chars | delta | + request count | delta |")
    rep.append("|---|---|---|---|---|---|---|---|")
    S["a_increment"] = {}
    base_feats = STATE + ["elapsed_k"]
    for y_key in ("info", "clear10"):
        res = {}
        for name, feats in (("state", base_feats), ("first", base_feats + ["l_think_first"]),
                            ("total", base_feats + ["l_think_total"]), ("requests", base_feats + ["l_requests"])):
            sc = cross_fit(A, "game", lambda tr, yk, feats=feats: Logit(feats).fit(tr, yk).score, y_key)
            res[name] = per_play_auc(by_play(A).values(), lambda r, sc=sc: sc[id(r)], y_key)
        cells = [fmt(within(res["state"]))]
        S["a_increment"][y_key] = {"state": within(res["state"])}
        for name in ("first", "total", "requests"):
            d = within(res[name]) - within(res["state"])
            ci = boot_within(res[name], paired=res["state"])
            cig = boot_within(res[name], cluster=True, paired=res["state"])
            S["a_increment"][y_key][name] = {"auc": within(res[name]), "delta": d, "ci_play": ci, "ci_game": cig}
            cells += [fmt(within(res[name])), f"{d:+.3f} [{ci[0]:+.3f}, {ci[1]:+.3f}] / [{cig[0]:+.3f}, {cig[1]:+.3f}]"]
        rep.append(f"| {y_key} | " + " | ".join(cells) + " |")
    m = Logit(base_feats + ["l_think_total", "l_think_first", "l_requests"]).fit(A, "clear10")
    mi = Logit(base_feats + ["l_think_total", "l_think_first", "l_requests"]).fit(A, "info")
    S["a_think_coefs"] = {"clear10": dict(zip(("total", "first", "requests"), map(float, m.w[-3:]))),
                          "info": dict(zip(("total", "first", "requests"), map(float, mi.w[-3:])))}
    rep.append("\nSign check (all turns, standardised, state + all three thinking terms): clear within 10: whole-turn "
               f"{m.w[-3]:+.2f}, first request {m.w[-2]:+.2f}, requests {m.w[-1]:+.2f}; new-or-clear: whole-turn "
               f"{mi.w[-3]:+.2f}, first request {mi.w[-2]:+.2f}, requests {mi.w[-1]:+.2f}.\n")

    # censoring: a request time-out loses that request's reasoning (the longest-thinking case), and a
    # yield splits a turn over rows; check the headline without those turns and with flags as covariates
    rep.append("\n### Robustness: time-outs and yields (censored thinking)\n")
    rep.append("| turns used | turns | whole-turn AUC, new-or-clear [play] [game] | whole-turn AUC, clear within 10 [play] [game] |")
    rep.append("|---|---|---|---|")
    S["a_censor"] = {}
    for name, f in (("all", lambda r: True), ("drop turns with a time-out", lambda r: r["timeouts"] == 0),
                    ("drop turns with a time-out or a yield", lambda r: r["timeouts"] == 0 and r["yields"] == 0)):
        sub = [r for r in A if f(r)]
        cells = []
        for yk in ("info", "clear10"):
            pc = per_play_auc(by_play(sub).values(), lambda r: r["think_total"], yk)
            ci, cig = boot_within(pc), boot_within(pc, cluster=True)
            S["a_censor"][f"{name}|{yk}"] = {"auc": within(pc), "ci_play": ci, "ci_game": cig, "turns": len(sub)}
            cells.append(f"{fmt(within(pc), ci)} / [{fmt(cig[0])}, {fmt(cig[1])}]")
        rep.append(f"| {name} | {len(sub)} | " + " | ".join(cells) + " |")
    for r in A:
        r["timed_out"] = int(r["timeouts"] > 0)
        r["yielded"] = int(r["yields"] > 0)
    fl = base_feats + ["timed_out", "yielded"]
    sc_s = cross_fit(A, "game", lambda tr, yk: Logit(fl).fit(tr, yk).score, "clear10")
    sc_t = cross_fit(A, "game", lambda tr, yk: Logit(fl + ["l_think_total"]).fit(tr, yk).score, "clear10")
    ps = per_play_auc(by_play(A).values(), lambda r: sc_s[id(r)], "clear10")
    pt = per_play_auc(by_play(A).values(), lambda r: sc_t[id(r)], "clear10")
    ci = boot_within(pt, cluster=True, paired=ps)
    mf = Logit(fl + ["l_think_total"]).fit(A, "clear10")
    S["a_censor"]["increment_clear10_with_flags"] = {"delta": within(pt) - within(ps), "ci_game": ci, "coef_total": float(mf.w[-1])}
    rep.append(f"\nWith time-out and yield flags in the state: adding whole-turn thinking changes held-out within-play AUC for "
               f"clear within 10 by {within(pt) - within(ps):+.3f} [{ci[0]:+.3f}, {ci[1]:+.3f}] (game CI); its coefficient "
               f"{mf.w[-1]:+.2f} (all turns, standardised). {sum(r['timed_out'] for r in A)} acting turns had a time-out, "
               f"{sum(r['yielded'] for r in A)} a yield.\n")

    rep.append("\n### By game type (from the valid-action list)\n")
    rep.append("| type | turns | share of thinking | new-or-clear rate | clear within 10 rate | "
               "thinking AUC for new-or-clear (within play) | thinking AUC for clear within 10 |")
    rep.append("|---|---|---|---|---|---|---|")
    S["a_type"] = {}
    tot = sum(r["think_total"] for r in A)
    for gt in ("click", "button", "mixed"):
        sub = [r for r in A if r["gtype"] == gt]
        pi = per_play_auc(by_play(sub).values(), lambda r: r["think_total"], "info")
        pc = per_play_auc(by_play(sub).values(), lambda r: r["think_total"], "clear10")
        d = {"turns": len(sub), "think_share": sum(r["think_total"] for r in sub) / tot,
             "info": float(np.mean([r["info"] for r in sub])), "clear10": float(np.mean([r["clear10"] for r in sub])),
             "auc_info": within(pi), "auc_info_ci": boot_within(pi), "auc_clear10": within(pc), "auc_clear10_ci": boot_within(pc)}
        S["a_type"][gt] = d
        rep.append(f"| {gt} | {len(sub)} | {d['think_share']:.3f} | {d['info']:.3f} | {d['clear10']:.3f} | "
                   f"{fmt(d['auc_info'], d['auc_info_ci'])} | {fmt(d['auc_clear10'], d['auc_clear10_ci'])} |")


# ---------------------------------------------------------------- question (b)

def question_b(R, A, rep, S):
    rep.append("\n## (b) How much thinking goes into predictable turns?\n")
    tot = sum(r["think_total"] for r in R)
    tok = tot / CHARS_PER_TOKEN
    rep.append(f"All {len(R)} turns (incl. {sum(1 for r in R if not r['n_actions'])} that issued no action, mostly time-outs "
               f"and yields); reasoning chars {tot:,} (about {tok / 1e6:.1f} M reasoning tokens at {CHARS_PER_TOKEN:.2f} chars/token).\n")
    rep.append(f"Pre-registered rule: predictable = last outcome surprisal < {PRED_SURP} nat AND mean candidate entropy < "
               f"{PRED_ENT} nats AND fewer than {PRED_STALL} actions since the last new outcome AND not a level start "
               "(first turn, just cleared, after RESET) AND a previous outcome exists.\n")

    def row_for(pred):
        sub = [r for r in R if pred(r)]
        suba = [r for r in A if pred(r)]
        rest = [r for r in A if not pred(r)]
        th = sum(r["think_total"] for r in sub)
        wall = [r["turn_wall_s"] for r in sub if r.get("turn_wall_s") is not None]
        wall_all = [r["turn_wall_s"] for r in R if r.get("turn_wall_s") is not None]
        return {"turn_share": len(sub) / len(R), "think_share": th / tot, "wall_share": sum(wall) / sum(wall_all),
                "info_rate_in": float(np.mean([r["info"] for r in suba])) if suba else None,
                "info_rate_out": float(np.mean([r["info"] for r in rest])) if rest else None,
                "share_of_info_turns": sum(r["info"] for r in suba) / max(sum(r["info"] for r in A), 1),
                "share_of_clear_turns": sum(r["clear"] for r in suba) / max(sum(r["clear"] for r in A), 1),
                "share_of_clear10": sum(r["clear10"] for r in suba) / max(sum(r["clear10"] for r in A), 1),
                "median_chars_in": float(np.median([r["think_total"] for r in suba])) if suba else None,
                "median_chars_out": float(np.median([r["think_total"] for r in rest])) if rest else None}

    rule = lambda r: r["predictable"] == 1  # noqa: E731
    head = row_for(rule)
    S["b_rule"] = head
    rep.append("| rule | share of turns | share of thinking | share of wall time | new-or-clear rate inside / outside | "
               "share of all new-or-clear turns inside | share of clears inside | median chars inside / outside |")
    rep.append("|---|---|---|---|---|---|---|---|")

    def line(name, h):
        return (f"| {name} | {h['turn_share']:.3f} | {h['think_share']:.3f} | {h['wall_share']:.3f} | "
                f"{fmt(h['info_rate_in'])} / {fmt(h['info_rate_out'])} | {h['share_of_info_turns']:.3f} | "
                f"{h['share_of_clear_turns']:.3f} | {fmt(h['median_chars_in'], d=0)} / {fmt(h['median_chars_out'], d=0)} |")
    rep.append(line(f"pre-registered (surp<{PRED_SURP}, ent<{PRED_ENT}, stall<{PRED_STALL})", head))
    S["b_grid"] = []
    for s in (0.5, 1.0, 2.0):
        for e in (1.0, 1.5, 2.0):
            for st in (5, 10, 20):
                if (s, e, st) == (PRED_SURP, PRED_ENT, PRED_STALL):
                    continue
                f = lambda r, s=s, e=e, st=st: (r["last_surp"] < s and r["ent_mean"] < e and r["stall_actions"] < st  # noqa: E731
                                                and not r["level_start"] and not r["no_prev"])
                h = row_for(f)
                h.update({"surp": s, "ent": e, "stall": st})
                S["b_grid"].append(h)
    for h in sorted(S["b_grid"], key=lambda h: -h["turn_share"])[:10]:
        rep.append(line(f"surp<{h['surp']}, ent<{h['ent']}, stall<{h['stall']}", h))
    rep.append("\n(Grid: the ten loosest of 26 other threshold settings; all in summary.json.) Components alone: "
               + "; ".join(f"{n} {row_for(f)['turn_share']:.2f} of turns, {row_for(f)['think_share']:.2f} of thinking"
                           for n, f in (("last surprisal < 1", lambda r: r["last_surp"] < 1 and not r["no_prev"]),
                                        ("mean entropy < 1.5", lambda r: r["ent_mean"] < 1.5),
                                        ("no stall (< 10)", lambda r: r["stall_actions"] < 10),
                                        ("not a level start", lambda r: not r["level_start"]))) + ".\n")


# ---------------------------------------------------------------- question (c)

def question_c(A, rep, S):
    rep.append("\n## (c) A gate: predict an informative / progress turn before it happens\n")
    rep.append("Fit on one fold, scored on the other (every turn scored once, by a model that never saw its game "
               "(game split) or its pass (pass split)). Within-play AUC first (a router chooses among turns of the "
               "same play), pooled AUC second; CIs play / game-cluster bootstrap.\n")
    S["c"] = {}
    for split in ("game", "pass"):
        for y_key, yname in (("info", "new outcome or clear in the turn"), ("clear10", "level clear within 10 actions")):
            rep.append(f"\n### Split {split}, target: {yname} (base rate {np.mean([r[y_key] for r in A]):.3f})\n")
            rep.append("| gate | within-play AUC [play] [game] | pooled AUC [play] [game] |")
            rep.append("|---|---|---|")
            res = {}
            # single-feature rules: direction from the training fold
            for f in STATE + ["elapsed_k"]:
                def mk(train, yk, f=f):
                    a = hy.auc([r[f] for r in train], [r[yk] for r in train])
                    sgn = 1.0 if (math.isnan(a) or a >= 0.5) else -1.0
                    return lambda r: sgn * r[f]
                sc = cross_fit(A, split, mk, y_key)
                res["rule: " + PLAIN.get(f, f)] = auc_block(A, lambda r, sc=sc: sc[id(r)], y_key)
            res["rule of (b): not predictable"] = auc_block(A, lambda r: 1 - r["predictable"], y_key)

            # single feature chosen on the TRAINING fold (best within-play AUC distance from 0.5), so the
            # winner is not read off the held-out table
            picked = []

            def mk_sel(train, yk, picked=picked):
                best = None
                for f in STATE + ["elapsed_k"]:
                    a = within(per_play_auc(by_play(train).values(), lambda r, f=f: r[f], yk))
                    if not math.isnan(a) and (best is None or abs(a - 0.5) > abs(best[1] - 0.5)):
                        best = (f, a)
                picked.append(PLAIN.get(best[0], best[0]))
                sgn = 1.0 if best[1] >= 0.5 else -1.0
                return lambda r, f=best[0]: sgn * r[f]
            sc = cross_fit(A, split, mk_sel, y_key)
            res["single rule picked on training fold (" + " / ".join(picked) + ")"] = auc_block(A, lambda r, sc=sc: sc[id(r)], y_key)
            for name, feats in (("logistic: pre-turn state", STATE), ("logistic: state + wall seconds", STATE + ["elapsed_k"])):
                sc = cross_fit(A, split, lambda tr, yk, feats=feats: Logit(feats).fit(tr, yk).score, y_key)
                res[name] = auc_block(A, lambda r, sc=sc: sc[id(r)], y_key)
                if name == "logistic: pre-turn state":
                    S["c"][f"{split}|{y_key}|scores"] = sc
            S["c"][f"{split}|{y_key}"] = res
            order = sorted(res, key=lambda k: -res[k]["within"] if not math.isnan(res[k]["within"]) else 0)
            for k in order:
                b = res[k]
                if k.startswith("rule: ") and order.index(k) >= 8:
                    continue
                rep.append(f"| {k} | {fmt(b['within'], b['within_ci_play'])} / [{fmt(b['within_ci_game'][0])}, {fmt(b['within_ci_game'][1])}] | "
                           f"{fmt(b['pooled'], b['pooled_ci_play'])} / [{fmt(b['pooled_ci_game'][0])}, {fmt(b['pooled_ci_game'][1])}] |")
            rep.append(f"\n(Top eight single-feature rules shown; all {len(STATE) + 1} in summary.json. Rows starting "
                       "'rule:' are ranked on the held-out table itself, so the best of them is optimistic; the "
                       "training-picked rule and the logistic are the honest held-out numbers.)")

    # operating points on the game split, logistic state gate, target info
    rep.append("\n### Operating points (game split, logistic pre-turn state gate)\n")
    rep.append("Threshold chosen on the training fold so that the given share of ITS turns would be routed light; "
               "applied to the held-out games. 'Missed' = share of the held-out turns with the outcome that the gate "
               "routed light (a random gate misses the light share). Thinking saved assumes a light turn would cost "
               "nothing and keep its outcome -- the part offline data cannot test.\n")
    rep.append("| target | light share (train) | light share (test) | thinking in light turns [play CI] | "
               "missed outcome turns [play CI] | random gate would miss | missed clears in the turn |")
    rep.append("|---|---|---|---|---|---|---|")
    S["c_ops"] = []
    fl, _ = folds(A, "game")
    for y_key in ("info", "clear10"):
        for share in LIGHT_SHARES:
            light = {}
            for train, test in fl:
                m = Logit(STATE).fit(train, y_key)
                thr = np.quantile([m.score(r) for r in train], share)
                for r in test:
                    light[id(r)] = m.score(r) < thr
            res = op_point(A, light, y_key)
            res.update({"target": y_key, "share": share})
            S["c_ops"].append(res)
            rep.append(f"| {y_key} | {share:.2f} | {res['light_share']:.3f} | {fmt(res['think_saved'], res['think_saved_ci'])} | "
                       f"{fmt(res['missed'], res['missed_ci'])} | {res['light_share']:.3f} | {fmt(res['missed_clear'])} |")


def op_point(A, light, y_key, n=N_BOOT, seed=0):
    groups = list(by_play(A).values())

    def stats(gs):
        rows = [r for g in gs for r in g]
        th = sum(r["think_total"] for r in rows)
        pos = [r for r in rows if r[y_key]]
        cl = [r for r in rows if r["clear"]]
        return (sum(r["think_total"] for r in rows if light[id(r)]) / th if th else float("nan"),
                sum(1 for r in pos if light[id(r)]) / len(pos) if pos else float("nan"),
                sum(1 for r in cl if light[id(r)]) / len(cl) if cl else float("nan"),
                sum(1 for r in rows if light[id(r)]) / len(rows))
    ts, ms, mc, ls = stats(groups)
    rng = np.random.default_rng(seed)
    bt, bm = [], []
    for _ in range(n):
        gs = [groups[j] for j in rng.integers(0, len(groups), len(groups))]
        a, b, _, _ = stats(gs)
        bt.append(a)
        bm.append(b)
    q = lambda v: (float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5)))  # noqa: E731
    return {"think_saved": ts, "think_saved_ci": q(bt), "missed": ms, "missed_ci": q(bm), "missed_clear": mc,
            "light_share": ls}


def coefs(A, rep, S):
    rep.append("\n### What the gate leans on (logistic on all acting turns, standardised coefficients)\n")
    S["coefs"] = {}
    for y_key in ("info", "clear10"):
        m = Logit(STATE).fit(A, y_key)
        cs = sorted(zip(STATE, m.w[1:]), key=lambda t: -abs(t[1]))
        S["coefs"][y_key] = {f: float(c) for f, c in cs}
        rep.append(f"- {y_key}: " + "; ".join(f"{PLAIN.get(f, f)} {c:+.2f}" for f, c in cs[:8]))


# ---------------------------------------------------------------- main

def main():
    global CHARS_PER_TOKEN, OUT
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    OUT = Path(args.out)
    T = {}
    t0 = time.time()
    cal = json.loads((OUT / "calibration.json").read_text())
    CHARS_PER_TOKEN = float(np.mean([v["chars_per_token_all"] for v in cal.values() if v["chars_per_token_all"]]))
    R = load(OUT / "turns.jsonl")
    A = [r for r in R if r["n_actions"] > 0]
    rep = ["# Think-hard router: offline evidence (results)\n",
           f"{len(by_play(R))} plays, {len({r['nick'] for r in R})} games, {len(R)} turns ({len(A)} issued at least one action). "
           f"Chars per generated token (vLLM totals of nine jobs): {CHARS_PER_TOKEN:.2f}; logged requests match vLLM request "
           f"counts in every job. Observational: thinking was always on; nothing here is a counterfactual.\n"]
    S = {"plays": len(by_play(R)), "games": len({r["nick"] for r in R}), "turns": len(R), "acting_turns": len(A),
         "chars_per_token": CHARS_PER_TOKEN, "base_rates": {k: float(np.mean([r[k] for r in A])) for k in TARGETS + ("clear",)}}
    first = [r for r in A if r["first_turn"]]
    AE = [r for r in A if not r["first_turn"]]
    rep.append(f"First turns: {len(first)}, {sum(r['think_total'] for r in first) / sum(r['think_total'] for r in R):.3f} of all "
               f"reasoning chars, new-or-clear rate {np.mean([r['info'] for r in first]):.2f} (by construction). "
               f"(a) and (c) use the other {len(AE)} acting turns.\n")
    S["first_turns"] = {"n": len(first), "think_share": sum(r["think_total"] for r in first) / sum(r["think_total"] for r in R)}
    S["eval_turns"] = len(AE)
    question_a(AE, rep, S)
    T["a_s"] = round(time.time() - t0, 1)
    question_b(R, A, rep, S)
    T["b_s"] = round(time.time() - t0 - T["a_s"], 1)
    question_c(AE, rep, S)
    coefs(AE, rep, S)
    T["total_s"] = round(time.time() - t0, 1)
    for k in list(S["c"]):
        if k.endswith("|scores"):
            del S["c"][k]
    (OUT / "report.md").write_text("\n".join(rep) + "\n")
    (OUT / "summary.json").write_text(json.dumps(S, indent=1, default=float))
    (OUT / "timings.json").write_text(json.dumps(T, indent=1))
    log("\n".join(rep))
    log(json.dumps(T))


if __name__ == "__main__":
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    main()

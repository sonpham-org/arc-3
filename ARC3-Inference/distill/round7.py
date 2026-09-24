#!/usr/bin/env python3
# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Round seven of the FEP-style offline trace analysis (OpenMind in #arc-3, 20:04 ET): are there
#   hand-craftable features beyond the clicked thing's colour? On the first 250 plays
#   (ebul_perception.trace_paths(250), 20 games) this driver
#     1. event-codes every step (object_events.py) and computes every hand-crafted detector of
#        feature_detectors.py once per play (prequential: values before each outcome), cached;
#     2. writes a per-game descriptive table: for each detector, the prequential gain of adding it
#        to the handcolour key, over ALL plays of that game (description for the write-up only; it is
#        never used for selection);
#     3. per split ("pass": p0/p2 vs p1/p3; "game": round5_combo.balanced_game_folds) and fold, on the
#        TRAINING traces only: ranks detectors by plug-in conditional information I(outcome; detector |
#        handcolour key) and by prequential gain, then greedy forward selection of detectors into the
#        context key, choosing each round's detector by fit-part gain and stopping when the validation
#        quarter (training traces j % 4 == 3, as round4._head) stops improving. Two predictors are
#        selected separately: "crafted" (the key backs off to the play's pooled outcome distribution,
#        exactly the yardstick's back-off prior) and "crafted-chain" (the key backs off to the
#        handcolour key, which backs off to the pooled distribution: a guard against over-splitting);
#     4. trains EBUL predictive dm heads on the same folds (round4._head, seeds 0 and 1);
#     5. scores on the test folds, within one play, back-off prior, object-event outcomes: flat,
#        handcolour, crafted, crafted-chain, EBUL dm alone, mix / bma (EBUL, crafted), mix (EBUL,
#        handcolour) as the round-six reference; paired trace bootstrap (and game-cluster) vs
#        handcolour and vs crafted, per game type; the test-fold gain of each selected detector in
#        selection order; timings.
#   Scoring uses an O(1)-per-step re-implementation of heldout_yardstick.score's back-off Dirichlet
#   (only the observed outcome's probability is needed); it is checked against hy.score on two arms
#   before anything is reported, and the script stops if they differ.
#   Post-hoc diagnostics (labelled "post-" in the table): the set selected under the flat back-off re-used
#   under the chain back-off, with last_label in front of or behind it, and mixed with EBUL.
#   Output: <out>/table.md, results.json, selection.json, per_game.txt, timings.json, detectors.pkl,
#   heads_dm.pkl.
#   Reads trace files only; launches nothing else; no harness change; no existing file edited.
# SRP/DRY check: Pass -- detectors in feature_detectors.py; traces/events object_events.py; folds,
#   support and bootstrap heldout_yardstick.py; heads, features, boot_table round4.py; game folds
#   round5_combo.py; this file adds the fast scorer, the selection loop and the reporting.
"""Round seven: hand-crafted detectors, selected on training folds, evaluated on 250 plays."""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import pickle
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ebul_perception as ep  # noqa: E402
import ebul_predictive as epr  # noqa: E402
import efe_trace_analysis as efe  # noqa: E402
import feature_detectors as fd  # noqa: E402
import heldout_yardstick as hy  # noqa: E402
import object_events as oe  # noqa: E402
import round4 as r4  # noqa: E402
import round5_combo as r5  # noqa: E402

OUT = Path(__file__).parent / "results/efe_trace_analysis/round7"
SEEDS = (0, 1)
BETA = efe.BACKOFF_BETA
MIN_VAL_GAIN = 1e-4          # nats/step the validation quarter must improve by to accept a detector
MAX_ROUNDS = 12
G = {}                       # fork-shared: traces, det (path -> rows), folds


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- fast prequential scorer

class Model:
    """heldout_yardstick.TypePriorBeliefs(prior="backoff", top=None) for one play, O(1) per step.
    chain=True: key is a tuple of levels (k0, k1, ...); level i backs off to level i-1 with the same
    beta, level 0 backs off to the pooled distribution."""

    def __init__(self, vocab0, chain=False):
        self.vocab = set(vocab0)
        self.K = len(self.vocab) + 1
        self.G = Counter()
        self.N = 0
        self.chain = chain
        self.cnt = defaultdict(Counter)
        self.n = Counter()

    def p(self, key, o):
        pg = ((self.G[o] + 1) if o in self.vocab else 1) / (self.N + self.K)
        if not self.chain:
            return (self.cnt[key][o] + BETA * pg) / (self.n[key] + BETA)
        p = pg
        for lev in key:
            p = (self.cnt[lev][o] + BETA * p) / (self.n[lev] + BETA)
        return p

    def update(self, key, o):
        if o not in self.vocab:
            self.vocab.add(o)
            self.K += 1
        for lev in (key if self.chain else (key,)):
            self.cnt[lev][o] += 1
            self.n[lev] += 1
        self.G[o] += 1
        self.N += 1


def vocab_of(support, open_vocab):
    return list(efe.BASE_OUTCOMES) + [s for s in support if s not in efe.BASE_OUTCOMES and not (open_vocab and s == hy.NOVEL)]


def score_play(outs, keysets, vocab0, mode="single", chain=(False,)):
    """outs: mapped outcomes of one play; keysets: one key list per model. Returns nats."""
    ms = [Model(vocab0, c) for c in (chain * len(keysets) if len(chain) == 1 else chain)]
    nats = 0.0
    ll = [0.0] * len(ms)
    for i, o in enumerate(outs):
        ps = [m.p(ks[i], o) for m, ks in zip(ms, keysets)]
        if mode == "single":
            q = ps[0]
        elif mode == "mix":
            q = sum(ps) / len(ps)
        else:                                     # bma: weights = running likelihood within the play
            mx = max(ll)
            w = [math.exp(v - mx) for v in ll]
            q = sum(wi * pi for wi, pi in zip(w, ps)) / sum(w)
        nats -= math.log(q)
        for j, (m, ks) in enumerate(zip(ms, keysets)):
            ll[j] += math.log(ps[j])
            m.update(ks[i], o)
    return nats


def mapped(path, sset, open_vocab):
    return [hy._map(lab, sset, open_vocab) for _, lab, _ in G["det"][path]]


def keys_for(path, dets, chain=False):
    rows = G["det"][path]
    if not chain:
        return [(ctx,) + tuple(v[d] for d in dets) for ctx, _, v in rows]
    return [tuple((ctx,) + tuple(v[d] for d in dets[:k]) for k in range(len(dets) + 1)) for ctx, _, v in rows]


def total(traces, dets, sset, open_vocab, vocab0, chain=False):
    nats = steps = 0
    for t in traces:
        outs = mapped(t.path, sset, open_vocab)
        nats += score_play(outs, [keys_for(t.path, dets, chain)], vocab0, chain=(chain,))
        steps += len(outs)
    return nats, steps


# ---------------------------------------------------------------- workers

def _det(i):
    t = G["traces"][i]
    t0 = time.time()
    return t.path, fd.run_trace(t), time.time() - t0


def _per_game(nick):
    """Descriptive: gain of handcolour + one detector over handcolour, all plays of one game (open
    vocabulary, fresh per play)."""
    ts = [t for t in G["traces"] if t.nick == nick]
    vocab0 = list(efe.BASE_OUTCOMES)
    base, steps = total(ts, [], set(), True, vocab0)
    out = {}
    for d in fd.DETECTORS:
        n, _ = total(ts, [d], set(), True, vocab0)
        out[d] = (base - n) / steps
    return nick, steps, base / steps, out


def cmi(traces, d):
    """Plug-in I(outcome; detector | handcolour key), pooled over the given plays, nats."""
    c3, c2a, c2b, c1 = Counter(), Counter(), Counter(), Counter()
    for t in traces:
        for ctx, lab, v in G["det"][t.path]:
            x = v[d]
            c3[ctx, x, lab] += 1
            c2a[ctx, x] += 1
            c2b[ctx, lab] += 1
            c1[ctx] += 1
    n = sum(c1.values())
    return sum(k / n * math.log(k * c1[c] / (c2a[c, x] * c2b[c, o])) for (c, x, o), k in c3.items())


def _select(job):
    """Greedy forward selection on one training fold. Returns the selection log."""
    split, fold, chain = job
    t0 = time.time()
    fdd = G["folds"][split][fold]
    train = fdd["train"]
    val = [t for j, t in enumerate(train) if j % 4 == 3]
    fit = [t for j, t in enumerate(train) if j % 4 != 3]
    sset, ov = fdd["support_set"], fdd["open"]
    vocab0 = vocab_of(fdd["support"], ov)
    rank = {}
    if not chain:                                    # the ranking is the same for both predictors
        b_all, s_all = total(train, [], sset, ov, vocab0)
        for d in fd.DETECTORS:
            n_all, _ = total(train, [d], sset, ov, vocab0)
            rank[d] = {"cmi_nats": cmi(train, d), "preq_gain": (b_all - n_all) / s_all}
    sel = []
    cur_fit, s_fit = total(fit, sel, sset, ov, vocab0, chain)
    cur_val, s_val = total(val, sel, sset, ov, vocab0, chain)
    rounds = []
    for _ in range(MAX_ROUNDS):
        cand = {}
        for d in fd.DETECTORS:
            if d in sel:
                continue
            nf, _ = total(fit, sel + [d], sset, ov, vocab0, chain)
            nv, _ = total(val, sel + [d], sset, ov, vocab0, chain)
            cand[d] = ((cur_fit - nf) / s_fit, (cur_val - nv) / s_val, nf, nv)
        best = max(cand, key=lambda d: (cand[d][0], d))
        g_fit, g_val, nf, nv = cand[best]
        top = sorted(cand, key=lambda d: -cand[d][0])[:6]
        rec = {"picked": best, "fit_gain": g_fit, "val_gain": g_val,
               "top_by_fit": [(d, round(cand[d][0], 4), round(cand[d][1], 4)) for d in top],
               "n_keys_fit": len({k for t in fit for k in keys_for(t.path, sel + [best])})}
        if g_fit <= 0 or g_val < MIN_VAL_GAIN:
            rec["accepted"] = False
            rounds.append(rec)
            break
        rec["accepted"] = True
        rounds.append(rec)
        sel.append(best)
        cur_fit, cur_val = nf, nv
    return job, {"selected": sel, "rounds": rounds, "rank": rank, "seconds": round(time.time() - t0, 1),
                 "fit_traces": len(fit), "val_traces": len(val)}


def _ebul_keys(job):
    """EBUL head contexts for every test play of one (split, fold, seed)."""
    split, fold, seed = job
    P = r4.make_perception(f"ebul-dm-s{seed}", split, fold)
    out = {}
    for t in G["folds"][split][fold]["test"]:
        P.begin(t)
        out[t.path] = [P.context(s) for s in t.steps if not s.reset]
    return job, out


# post-hoc diagnostics (labelled as such in the table): the detector set selected under the FLAT
# back-off, re-used under the chain back-off, with and without last_label in front of / behind it
POST_ARMS = ("post-chain-crafted", "post-chain-ll-crafted", "post-chain-crafted-ll")


def post_dets(arm, sel):
    rest = [d for d in sel if d != "last_label"]
    return {"post-chain-crafted": list(sel), "post-chain-ll-crafted": ["last_label"] + rest,
            "post-chain-crafted-ll": rest + ["last_label"]}[arm]


def _score_arm(job):
    split, fold, arm = job
    fdd = G["folds"][split][fold]
    sset, ov = fdd["support_set"], fdd["open"]
    vocab0 = vocab_of(fdd["support"], ov)
    sel = G["selected"][split, fold, False]
    selc = G["selected"][split, fold, True]
    rows = []
    for t in fdd["test"]:
        outs = mapped(t.path, sset, ov)
        hc = keys_for(t.path, [])
        cr = keys_for(t.path, sel)
        ch = keys_for(t.path, selc, chain=True)
        if arm == "flat":
            n = score_play(outs, [[("any",)] * len(outs)], vocab0)
        elif arm == "handcolour":
            n = score_play(outs, [hc], vocab0)
        elif arm == "crafted":
            n = score_play(outs, [cr], vocab0)
        elif arm == "crafted-chain":
            n = score_play(outs, [ch], vocab0, chain=(True,))
        elif arm.startswith("prefix"):               # handcolour + the first k selected detectors
            k = int(arm.split("-")[1])
            n = score_play(outs, [keys_for(t.path, sel[:k])], vocab0) if k <= len(sel) else None
        elif arm.startswith("cprefix"):              # chain: handcolour + the first k chain-selected detectors
            k = int(arm.split("-")[1])
            n = score_play(outs, [keys_for(t.path, selc[:k], chain=True)], vocab0, chain=(True,)) \
                if k <= len(selc) else None
        elif arm in POST_ARMS:                       # post-hoc: fold-selected sets under the chain back-off
            n = score_play(outs, [keys_for(t.path, post_dets(arm, sel), chain=True)], vocab0, chain=(True,))
        elif arm.startswith("post-mixchain2"):
            eb = G["ebul"][split, fold, int(arm.rsplit("-s", 1)[1])][t.path]
            n = score_play(outs, [eb, keys_for(t.path, post_dets("post-chain-ll-crafted", sel), chain=True)], vocab0,
                           mode="mix", chain=(False, True))
        else:
            kind, seed = arm.rsplit("-s", 1)
            eb = G["ebul"][split, fold, int(seed)][t.path]
            if kind == "ebul-dm":
                n = score_play(outs, [eb], vocab0)
            elif kind in ("mix", "bma"):
                n = score_play(outs, [eb, cr], vocab0, mode=kind)
            elif kind == "mixhc":
                n = score_play(outs, [eb, hc], vocab0, mode="mix")
            elif kind in ("mixchain", "bmachain"):
                n = score_play(outs, [eb, ch], vocab0, mode=kind[:-5], chain=(False, True))
            else:
                raise ValueError(arm)
        if n is not None:
            rows.append((t.path, n, len(outs)))
    return job, rows


# ---------------------------------------------------------------- check against the yardstick

def check_scorer():
    """The fast scorer must reproduce heldout_yardstick.score exactly (handcolour, pass fold 0, fixed
    support; EBUL dm seed 0, game fold 0, open support)."""
    out = {}
    for split, fold, arm in (("pass", 0, "handcolour"), ("game", 0, "ebul-dm-s0")):
        fdd = G["folds"][split][fold]
        ref = hy.score(fdd["test"], r4.make_perception(arm, split, fold), fdd["support"], open_vocab=fdd["open"])
        ref_n = sum(r["nats"] for r in ref)
        vocab0 = vocab_of(fdd["support"], fdd["open"])
        fast_n = 0.0
        for t in fdd["test"]:
            outs = mapped(t.path, fdd["support_set"], fdd["open"])
            keys = keys_for(t.path, []) if arm == "handcolour" else G["ebul"][split, fold, 0][t.path]
            fast_n += score_play(outs, [keys], vocab0)
        out[f"{split}/{fold}/{arm}"] = (ref_n, fast_n)
        if abs(ref_n - fast_n) > 1e-6 * max(1.0, abs(ref_n)):
            sys.exit(f"fast scorer disagrees with hy.score on {split}/{fold}/{arm}: {ref_n} vs {fast_n}")
    return out


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=250)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    workers = min(args.workers, 10)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ctx = mp.get_context("fork")
    T = {}
    t_all = time.time()

    t0 = time.time()
    traces, _ = oe.load_all(ep.trace_paths(args.n), workers)
    G["traces"] = r4.G["traces"] = traces
    T["load_event_code_s"] = round(time.time() - t0, 1)
    log(f"{len(traces)} plays, {len({t.nick for t in traces})} games, "
        f"{sum(1 for t in traces for s in t.steps if not s.reset)} steps; {T['load_event_code_s']} s")

    t0 = time.time()
    with ctx.Pool(workers) as pool:
        G["det"] = {p: rows for p, rows, _ in pool.imap_unordered(_det, range(len(traces)))}
    T["detectors_s"] = round(time.time() - t0, 1)
    with open(out / "detectors.pkl", "wb") as fh:
        pickle.dump(G["det"], fh)
    errs = Counter((d, v[1]) for rows in G["det"].values() for _, _, vals in rows for d, v in vals.items()
                   if isinstance(v, tuple) and v and v[0] == "err")
    log(f"detectors: {T['detectors_s']} s; errors {dict(errs) or 'none'}")

    # per-game description (all plays; not used for selection)
    t0 = time.time()
    with ctx.Pool(workers) as pool:
        per_game = sorted(pool.map(_per_game, sorted({t.nick for t in traces})))
    T["per_game_s"] = round(time.time() - t0, 1)
    gtype = {t.nick: t.gtype for t in traces}
    pg_lines = ["per game: gain (nats/step) of handcolour + ONE detector over handcolour alone, all plays "
                "of that game, fresh per play, open vocabulary (descriptive, not used for selection)"]
    for nick, steps, base, gains in per_game:
        top = sorted(gains.items(), key=lambda kv: -kv[1])[:5]
        pg_lines.append(f"{nick:<22} {gtype[nick]:<6} {steps:5d} steps, handcolour {base:.3f}: " +
                        ", ".join(f"{d} {g:+.3f}" for d, g in top))
    (out / "per_game.txt").write_text("\n".join(pg_lines) + "\n")
    log("\n".join(pg_lines))

    # folds + EBUL features
    t0 = time.time()
    with ctx.Pool(workers) as pool:
        r4.G["feats"] = {p: f for p, f, _ in pool.imap_unordered(r4._features, range(len(traces)))}
    r4.G["iters"] = epr.ITERS
    game_folds, fold_of = r5.balanced_game_folds(traces)
    G["folds"] = r4.G["folds"] = {}
    for split in r4.SPLITS:
        G["folds"][split] = []
        pairs = game_folds if split == "game" else hy.folds(traces, split)
        for train, test in pairs:
            support = hy.support_of(train)
            G["folds"][split].append({"train": train, "test": test, "support": support,
                                      "support_set": set(support), "open": split == "game"})
    T["features_folds_s"] = round(time.time() - t0, 1)
    log("game folds:", json.dumps(fold_of))

    # selection (training folds only) and heads, in one pool
    t0 = time.time()
    sel_jobs = [(s, f, c) for s in r4.SPLITS for f in (0, 1) for c in (False, True)]
    head_jobs = [(s, f, seed, "dm") for s in r4.SPLITS for f in (0, 1) for seed in SEEDS]
    selection, head_info = {}, {}
    r4.G["heads"] = {}
    with ctx.Pool(workers) as pool:
        hres = pool.imap_unordered(r4._head, head_jobs)
        for job, res in pool.imap_unordered(_select, sel_jobs):
            selection[job] = res
            log(f"selection {job}: {res['selected']} ({res['seconds']} s)")
        for job, head, info in hres:
            r4.G["heads"][job] = head
            head_info["/".join(map(str, job))] = {k: info.get(k) for k in ("seconds", "val_diag", "best_iter")}
    T["selection_and_heads_s"] = round(time.time() - t0, 1)
    G["selected"] = {k: v["selected"] for k, v in selection.items()}
    with open(out / "heads_dm.pkl", "wb") as fh:
        pickle.dump({"/".join(map(str, k)): v for k, v in r4.G["heads"].items()}, fh)
    (out / "selection.json").write_text(json.dumps({"/".join(map(str, k)): v for k, v in selection.items()},
                                                   indent=1, default=str))

    t0 = time.time()
    with ctx.Pool(workers) as pool:
        G["ebul"] = dict(pool.map(_ebul_keys, [(s, f, seed) for s in r4.SPLITS for f in (0, 1) for seed in SEEDS]))
    check = check_scorer()
    T["ebul_keys_and_check_s"] = round(time.time() - t0, 1)
    log("scorer check (hy.score, fast):", json.dumps(check))

    t0 = time.time()
    arms = ["flat", "handcolour", "crafted", "crafted-chain"] + [f"ebul-dm-s{s}" for s in SEEDS] + \
           [f"{k}-s{s}" for k in ("mix", "bma", "mixhc", "mixchain", "bmachain") for s in SEEDS]
    arms += list(POST_ARMS) + [f"post-mixchain2-s{s}" for s in SEEDS]
    kmax = max(len(v) for v in G["selected"].values())
    prefixes = [f"prefix-{k}" for k in range(1, kmax + 1)] + [f"cprefix-{k}" for k in range(1, kmax + 1)]
    per = {sp: defaultdict(dict) for sp in r4.SPLITS}
    with ctx.Pool(workers) as pool:
        for (split, fold, arm), rows in pool.imap_unordered(
                _score_arm, [(sp, f, a) for sp in r4.SPLITS for f in (0, 1) for a in arms + prefixes]):
            for path, n, k in rows:
                per[split][arm if "prefix" not in arm else f"{arm}/f{fold}"][path] = (n, k)
    T["scoring_s"] = round(time.time() - t0, 1)

    t0 = time.time()
    lines, res = [], {"selection": {}, "splits": {}, "per_game_descriptive": per_game, "heads": head_info,
                      "scorer_check": check, "game_folds": fold_of}
    for split in r4.SPLITS:
        P = {a: per[split][a] for a in arms}
        tabs = {ref: r4.boot_table(P, traces, ref=ref) for ref in ("flat", "handcolour", "crafted", "crafted-chain")}
        steps = sum(v[1] for v in P["flat"].values())
        lines.append(f"\n## split {split} (within one play, back-off prior, event outcomes; {len(P['flat'])} plays, "
                     f"{steps} steps)")
        for f in (0, 1):
            lines.append(f"- fold {f} selected (crafted): {', '.join(G['selected'][split, f, False]) or '(none)'}; "
                         f"(crafted-chain): {', '.join(G['selected'][split, f, True]) or '(none)'}")
        lines.append("")
        lines.append("| arm | nats/step | gain vs handcolour | game-cluster CI | gain vs crafted | gain vs crafted-chain | "
                     "click | button | mixed (vs handcolour) |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        res["splits"][split] = {}
        for a in arms:
            nps = sum(v[0] for v in P[a].values()) / steps
            h, c, cc = tabs["handcolour"][a], tabs["crafted"][a], tabs["crafted-chain"][a]
            res["splits"][split][a] = {"nats_per_step": nps, "vs_flat": tabs["flat"][a]["all"],
                                       "vs_handcolour": h["all"], "vs_handcolour_game_cluster": h["all_game_cluster"],
                                       "vs_crafted": c["all"], "vs_crafted_chain": cc["all"],
                                       "per_play": P[a],
                                       "types_vs_handcolour": {g: h[g] for g in ("click", "button", "mixed") if g in h},
                                       "types_vs_crafted": {g: c[g] for g in ("click", "button", "mixed") if g in c}}
            ty = " | ".join(r4.fmt_ci(h[g]["gain"], h[g]["gain_ci"]) if g in h else "-" for g in ("click", "button", "mixed"))
            gc = h["all_game_cluster"]["gain_ci"]
            lines.append(f"| {a} | {nps:.3f} | {r4.fmt_ci(h['all']['gain'], h['all']['gain_ci'])} | "
                         f"[{gc[0]:+.3f}, {gc[1]:+.3f}] | {r4.fmt_ci(c['all']['gain'], c['all']['gain_ci'])} | "
                         f"{r4.fmt_ci(cc['all']['gain'], cc['all']['gain_ci'])} | {ty} |")
        # test-fold gain of each selected detector, in selection order (per fold, on that fold's test plays)
        lines.append("\ntest-fold gain of each selected detector, added in selection order (nats/step over the "
                     "previous prefix, 95% CI over plays):")
        res["splits"][split]["prefix"] = {}
        for pre, chain in (("prefix", False), ("cprefix", True)):
            for f in (0, 1):
                sel = G["selected"][split, f, chain]
                test_paths = {t.path for t in G["folds"][split][f]["test"]}
                prev = {p: per[split]["handcolour"][p] for p in test_paths}
                parts = []
                for k, d in enumerate(sel, 1):
                    cur = per[split][f"{pre}-{k}/f{f}"]
                    b = hy.paired_boot(cur, prev, cur.keys(), seed=7)
                    parts.append(f"{d} {r4.fmt_ci(b['gain'], b['gain_ci'])}")
                    res["splits"][split]["prefix"][f"{pre}/f{f}/{k}/{d}"] = b
                    prev = cur
                lines.append(f"- {'crafted-chain' if chain else 'crafted'}, fold {f}: " +
                             ("; ".join(parts) or "(nothing selected)"))
        # per game: gain vs handcolour of the main arms (95% CI over that game's plays)
        games = sorted({t.nick for t in traces})
        pg_arms = ("crafted", "crafted-chain", "mix-s0", "mixchain-s0", "post-chain-ll-crafted")
        lines.append("\nper game, gain vs handcolour (nats/step, 95% CI over plays):\n")
        lines.append("| game | type | plays | " + " | ".join(pg_arms) + " |")
        lines.append("|---|---|---|" + "---|" * len(pg_arms))
        res["splits"][split]["per_game"] = {}
        for g in games:
            ks = [t.path for t in traces if t.nick == g]
            cells = []
            for a in pg_arms:
                b = hy.paired_boot(per[split][a], per[split]["handcolour"], ks, seed=8)
                res["splits"][split]["per_game"][f"{g}/{a}"] = b
                cells.append(r4.fmt_ci(b["gain"], b["gain_ci"], 2))
            lines.append(f"| {g} | {gtype[g]} | {len(ks)} | " + " | ".join(cells) + " |")
    T["statistics_s"] = round(time.time() - t0, 1)
    T["total_s"] = round(time.time() - t_all, 1)
    for k, v in selection.items():
        res["selection"]["/".join(map(str, k))] = v
    res["timings"] = T
    lines.insert(0, f"{len(traces)} plays, {len({t.nick for t in traces})} games; crafted = handcolour + detectors "
                    f"selected on each training fold; dm heads retrained on these folds")
    lines.append(f"\ntimings: {json.dumps(T)}")
    text = "\n".join(lines)
    log(text)
    (out / "table.md").write_text(text + "\n")
    (out / "results.json").write_text(json.dumps(res, indent=1, default=str))
    (out / "timings.json").write_text(json.dumps(T, indent=1))


if __name__ == "__main__":
    main()

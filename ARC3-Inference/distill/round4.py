#!/usr/bin/env python3
# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Driver for round four of the FEP-style offline trace analysis (OpenMind in #arc-3, expert
#   debate items 1, 2, 3, 4, 5, 7). On the same 53 traces as rounds one to three
#   (ebul_perception.trace_paths(53)) it:
#     1. event-codes every step with the hand-built object-event coder (object_events.py, item 2);
#     2. computes the fixed conv features (ebul_perception_conv.maps_of) of every step's pre board for
#        the learned heads;
#     3. checks how much the stale "pre" board in efe_trace_analysis.analyse (it is never advanced
#        after a normal step, so every step is compared with the level's first board) moved the
#        earlier rounds' numbers, by scoring round one's size-bucket outcome both ways;
#     4. for each split ("pass": p0/p2 vs p1/p3, as asked; "game": two folds of whole games) and fold,
#        builds everything learned from the training fold only (outcome support, game-type prior,
#        pragmatic table, PCA + ES heads for two seeds and three objectives, item 4);
#     5. scores every arm on the test fold with the back-off yardstick (heldout_yardstick.py): flat,
#        none, handmade, handstate, agency (+ ablations, item 3), EBUL heads; item 7 variants (type
#        prior, carry across levels/passes/runs, carry + prime from training passes); item 5 AUCs;
#     6. paired trace bootstrap (and game-cluster bootstrap) of nats/step and gain vs flat, overall
#        and per game type; wall-clock timing of every stage.
#   Output: <out>/results.json, table.md, labels.txt, heads.json, timings.json.
#   Parallel: a fork pool of --workers processes (default 8, cap 12 by request) for features, head
#   searches and scoring. Reads trace files only; launches nothing else; no harness change.
# SRP/DRY check: Pass -- every model piece lives in its own module (object_events, agency_contexts,
#   heldout_yardstick, ebul_predictive, and the earlier efe_trace_analysis / ebul_perception /
#   ebul_perception_conv); this file only wires folds, jobs, statistics and reports.
"""Round four: object events, agency, predictive EBUL, carry-over, pragmatic AUC.

Usage:
    OMP_NUM_THREADS=1 python distill/round4.py --out distill/results/efe_trace_analysis/round4
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import statistics as st
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agency_contexts as ag  # noqa: E402
import ebul_perception as ep  # noqa: E402
import ebul_perception_conv as epc  # noqa: E402
import ebul_predictive as epr  # noqa: E402
import efe_trace_analysis as efe  # noqa: E402
import heldout_yardstick as hy  # noqa: E402
import object_events as oe  # noqa: E402

G = {}               # shared state for fork workers: traces, feats, folds, heads
SPLITS = ("pass", "game")
OBJECTIVES = ("dm", "gzip", "entropy", "random")
BASE_ARMS = ("flat", "none", "handmade", "handcolour", "handstate", "agency", "agency-buttons", "agency-clicks",
             "agency-colour")
PAIRS = [("handmade", "none"), ("agency", "handmade"), ("agency-buttons", "handmade"), ("agency-clicks", "handmade"),
         ("handcolour", "handmade"), ("agency-colour", "agency")] + \
        [(f"ebul-dm-s{s}", ref) for s in (0, 1) for ref in ("handmade", "handcolour", "agency", "agency-colour",
                                                              f"ebul-entropy-s{s}", f"ebul-gzip-s{s}", f"ebul-random-s{s}")]
CARRY_ARMS = ("flat", "none", "handmade", "agency")
PRAG_ARMS = ("flat", "none", "handmade", "agency")


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- workers

def _features(i):
    t = G["traces"][i]
    t0 = time.time()
    return t.path, epr.step_features(t), time.time() - t0


def _stale_check(i):
    """Round-one outcome (efe.outcome_class, coarse size buckets), back-off prior, three arms:
    efe.analyse as it stands (stale pre) vs the step scorer with the correct pre board."""
    t = G["traces"][i]
    out = {}
    boards = [t.steps[0].pre] + [s.post for s in t.steps] if t.steps else []
    mask = efe.hud_mask(boards)
    coarse = [f"changed~2^{k}" for k in range(efe.SIZE_BUCKETS)]
    for name, P in (("flat", epc.Flat()), ("none", ep.NoPerception()), ("handmade", efe.HandmadePerception())):
        r = efe.analyse(t.path, None, P, prior="backoff")
        stale = sum(x["surprisal"] for x in r["steps"] if not x.get("reset"))
        stale_nothing = sum(x["outcome"] == "nothing" for x in r["steps"] if not x.get("reset"))
        b = hy.TypePriorBeliefs(coarse, efe.BACKOFF_BETA)
        nats, n, nothing = 0.0, 0, 0
        for s in t.steps:
            if s.reset:
                continue
            o = efe.outcome_class(s.pre, s.post, s.row, mask)
            ctx = P.context(s.row, s.pre)
            nats -= np.log(b.p(ctx, o))
            b.update(ctx, o)
            n += 1
            nothing += o == "nothing"
        out[name] = {"stale": stale, "correct": nats, "steps": n, "stale_nothing": stale_nothing,
                     "correct_nothing": nothing}
    return t.path, out


def _items(traces, outs_idx, support_set, open_vocab):
    items = []
    for t in traces:
        f = G["feats"][t.path]
        for s in t.steps:
            if s.reset:
                continue
            kind, a, feat = f[s.i]
            o = hy._map(s.label, support_set, open_vocab)
            items.append((kind, a, feat, outs_idx.get(o, outs_idx[hy.NOVEL])))
    return items


def _head(job):
    split, fold, seed, objective = job
    t0 = time.time()
    fd = G["folds"][split][fold]
    train = fd["train"]
    val = [t for j, t in enumerate(train) if j % 4 == 3]
    fit = [t for j, t in enumerate(train) if j % 4 != 3]
    outs = efe.BASE_OUTCOMES + [o for o in fd["support"] if o not in efe.BASE_OUTCOMES]
    idx = {o: i for i, o in enumerate(outs)}
    it_fit = _items(fit, idx, fd["support_set"], fd["open"])
    it_val = _items(val, idx, fd["support_set"], fd["open"])
    Xb = np.stack([f for k, _, f, _ in it_fit if k == "b"])
    Xp = np.stack([f for k, _, f, _ in it_fit if k == "p"])
    pca_b, pca_p = epr.PCA(Xb, epr.PCA_DIM), epr.PCA(Xp, epr.PCA_DIM)
    K = len(outs)
    cnt = np.bincount([o for *_, o in it_fit], minlength=K).astype(float)
    p_global = (cnt + 1) / (cnt.sum() + K)
    dfit = epr.Data(it_fit, pca_b, pca_p, K, p_global, efe.BACKOFF_BETA)
    dval = epr.Data(it_val, pca_b, pca_p, K, p_global, efe.BACKOFF_BETA)
    rng_seed = 1000 * seed + 17 * fold + (0 if split == "pass" else 7)
    theta, info = epr.es_search(dfit, dval, objective, rng_seed, G["iters"])
    _, _, _, stats = dfit.contexts(theta)
    info.update({"train_diag": dfit.diagnostics(theta), "val_diag": dval.diagnostics(theta, stats),
                 "seconds": round(time.time() - t0, 1), "n_fit": dfit.n, "n_val": dval.n, "K": K,
                 "params": epr.n_params()})
    return job, (pca_b, pca_p, theta, stats), info


def _agency_diag(i):
    """Fresh-per-trace agency contexts: share of button steps per placeholder, controlled object."""
    t = G["traces"][i]
    P = ag.AgencyPerception()
    kinds = Counter()
    for s in t.steps:
        if s.reset:
            continue
        c = P.context(s)
        if c[0] != "M":
            kinds[c[1] if len(c) > 1 else "plain"] += 1
        P.observe(s)
    return t.nick, t.path, dict(kinds), P.describe()


def make_perception(name, split, fold):
    if name == "flat":
        return hy.RowPerception(epc.Flat())
    if name == "none":
        return hy.RowPerception(ep.NoPerception())
    if name == "handmade":
        return hy.RowPerception(efe.HandmadePerception())
    if name == "handstate":
        return hy.RowPerception(ep.HandState())
    if name == "agency":
        return ag.AgencyPerception()
    if name == "agency-buttons":
        return ag.AgencyPerception(name, buttons=True, clicks=False)
    if name == "agency-clicks":
        return ag.AgencyPerception(name, buttons=False, clicks=True)
    if name == "handcolour":
        return ag.AgencyPerception(name, buttons=False, clicks=False, click_colour=True)
    if name == "agency-colour":
        return ag.AgencyPerception(name, click_colour=True)
    if name.startswith("ebul-"):
        _, objective, seed = name.split("-")
        pca_b, pca_p, theta, stats = G["heads"][split, fold, int(seed[1:]), objective]
        return epr.HeadPerception(name, pca_b, pca_p, theta, stats, G["feats"])
    raise ValueError(name)


def _score(job):
    split, fold, arm, variant = job
    t0 = time.time()
    fd = G["folds"][split][fold]
    P = make_perception(arm, split, fold)
    kw = {"open_vocab": fd["open"]}
    if "type" in variant:
        kw["type_top"] = fd["type_top"]
    if "carry" in variant:
        kw["carry"] = True
    if "prime" in variant:
        kw["carry"] = True
        kw["prime"] = fd["prime"]
    if variant == "prag":
        kw["C"] = fd["C"]
    res = hy.score(fd["test"], P, fd["support"], **kw)
    slim = [{"path": r["trace"].path, "nats": r["nats"], "steps": r["steps"],
             "prag": r["prag"], "pclear": r["pclear"]} for r in res]
    return job, slim, time.time() - t0


# ---------------------------------------------------------------- reporting helpers

def arm_key(arm, variant):
    return arm if variant == "fresh" else f"{arm}+{variant}"


def boot_table(per, traces, ref="flat"):
    """per: {arm key: {path: (nats, steps)}} -> rows with overall and per-type bootstrap."""
    types = {t.path: t.gtype for t in traces}
    games = {t.path: t.nick for t in traces}
    rows = {}
    for key, d in per.items():
        row = {"all": hy.paired_boot(d, per[ref], d.keys(), seed=1),
               "all_game_cluster": hy.paired_boot(d, per[ref], d.keys(), seed=2, clusters=games)}
        for gt in ("click", "button", "mixed"):
            ks = [k for k in d if types[k] == gt]
            if ks:
                row[gt] = hy.paired_boot(d, per[ref], ks, seed=3)
        rows[key] = row
    return rows


def fmt_ci(v, ci, digits=3):
    return f"{v:+.{digits}f} [{ci[0]:+.{digits}f}, {ci[1]:+.{digits}f}]"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=53)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1])
    ap.add_argument("--iters", type=int, default=epr.ITERS)
    ap.add_argument("--out", default=str(Path(__file__).parent / "results/efe_trace_analysis/round4"))
    args = ap.parse_args()
    args.workers = min(args.workers, 12)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    T = {}
    t_all = time.time()
    ctx = mp.get_context("fork")

    # 1. traces + object events
    t0 = time.time()
    paths = ep.trace_paths(args.n)
    traces, cpu = oe.load_all(paths, args.workers)
    T["load_and_event_code_s"] = round(time.time() - t0, 1)
    log(f"{len(traces)} traces, {sum(len(t.steps) for t in traces)} rows; event coding {T['load_and_event_code_s']}s")
    G["traces"] = traces
    G["iters"] = args.iters

    # label report (item 2)
    lab_lines = []
    allc = Counter()
    for t in traces:
        allc.update(s.label for s in t.steps if not s.reset)
    lab_lines.append(f"{len(allc)} distinct labels over {sum(allc.values())} steps (all 53 traces)")
    by_game = defaultdict(Counter)
    for t in traces:
        by_game[t.nick].update(s.label for s in t.steps if not s.reset)
    for g, c in sorted(by_game.items()):
        lab_lines.append(f"{g:<20} {len(c):4d} labels; top: " + ", ".join(f"{k} ({v})" for k, v in c.most_common(5)))

    # 2. features (fork pool)
    t0 = time.time()
    with ctx.Pool(args.workers) as pool:
        feats = {}
        fcpu = 0.0
        for path, f, secs in pool.imap_unordered(_features, range(len(traces))):
            feats[path] = f
            fcpu += secs
    G["feats"] = feats
    T["conv_features_s"] = round(time.time() - t0, 1)
    log(f"conv features {T['conv_features_s']}s wall ({fcpu:.0f}s cpu)")

    # 3. stale-pre check
    t0 = time.time()
    with ctx.Pool(args.workers) as pool:
        stale = dict(pool.map(_stale_check, range(len(traces))))
    T["stale_pre_check_s"] = round(time.time() - t0, 1)
    stale_sum = {}
    for arm in ("flat", "none", "handmade"):
        n = sum(v[arm]["steps"] for v in stale.values())
        stale_sum[arm] = {"stale_nats_per_step": sum(v[arm]["stale"] for v in stale.values()) / n,
                          "correct_nats_per_step": sum(v[arm]["correct"] for v in stale.values()) / n,
                          "stale_nothing_share": sum(v[arm]["stale_nothing"] for v in stale.values()) / n,
                          "correct_nothing_share": sum(v[arm]["correct_nothing"] for v in stale.values()) / n}
    log("stale-pre check:", json.dumps(stale_sum))

    # 3b. agency diagnostics (item 3)
    t0 = time.time()
    with ctx.Pool(args.workers) as pool:
        adiag = pool.map(_agency_diag, range(len(traces)))
    T["agency_diag_s"] = round(time.time() - t0, 1)
    agg = defaultdict(Counter)
    found = defaultdict(list)
    for nick, _, kinds, desc in adiag:
        agg[nick].update(kinds)
        found[nick].append(desc["colour"] if desc else None)
    ag_lines = []
    for nick in sorted(agg):
        n = sum(agg[nick].values())
        if n:
            ag_lines.append(f"{nick:<20} button steps {n:4d}: " + ", ".join(
                f"{k} {v / n:.2f}" for k, v in agg[nick].most_common()) + f"; controlled colour per trace {found[nick]}")
    (out / "agency.txt").write_text("\n".join(ag_lines) + "\n")
    log("\n".join(ag_lines))

    # 4. folds
    G["folds"] = {}
    novel = {}
    for split in SPLITS:
        G["folds"][split] = []
        nv = tot = 0
        for f, (train, test) in enumerate(hy.folds(traces, split)):
            support = hy.support_of(train)
            sset = set(support)
            fd = {"train": train, "test": test, "support": support, "support_set": sset,
                  "open": split == "game", "type_top": hy.type_counts(train, sset),
                  "C": hy.clear_table(train, sset),
                  "prime": {g: [t for t in train if t.game == g] for g in {t.game for t in test}}}
            G["folds"][split].append(fd)
            for t in test:
                for s in t.steps:
                    if not s.reset:
                        tot += 1
                        nv += s.label not in sset and s.label not in efe.BASE_OUTCOMES
            lab_lines.append(f"split {split} fold {f}: train {len(train)} traces / test {len(test)}; "
                             f"support {len(support)} labels")
        novel[split] = nv / tot
        lab_lines.append(f"split {split}: share of test steps whose label is not in the training support: {nv / tot:.3f}")
    (out / "labels.txt").write_text("\n".join(lab_lines) + "\n")
    log("\n".join(lab_lines[-6:]))

    # 5. heads (item 4)
    t0 = time.time()
    jobs = [(s, f, seed, o) for s in SPLITS for f in (0, 1) for seed in args.seeds for o in OBJECTIVES]
    G["heads"] = {}
    head_info = {}
    with ctx.Pool(args.workers) as pool:
        for job, head, info in pool.imap_unordered(_head, jobs):
            G["heads"][job] = head
            head_info["/".join(map(str, job))] = info
            log(f"head {job}: {info.get('seconds')}s val {info.get('val_diag')} best_iter {info.get('best_iter')}")
    T["heads_s"] = round(time.time() - t0, 1)
    (out / "heads.json").write_text(json.dumps(head_info, indent=1))

    # 6. scoring
    t0 = time.time()
    head_arms = [f"ebul-{o}-s{s}" for o in OBJECTIVES for s in args.seeds]
    jobs = []
    for split in SPLITS:
        for f in (0, 1):
            for arm in BASE_ARMS + tuple(head_arms):
                jobs.append((split, f, arm, "fresh"))
            for arm in CARRY_ARMS:
                for v in ("type", "carry", "carry+type") + (("prime",) if split == "pass" else ()):
                    jobs.append((split, f, arm, v))
            for arm in PRAG_ARMS:
                jobs.append((split, f, arm, "prag"))
    scored = defaultdict(dict)       # (split, key) -> {path: (nats, steps)}
    prag = defaultdict(list)         # (split, arm) -> [(prag scores, pclear, labels)]
    cpu = defaultdict(float)
    with ctx.Pool(args.workers) as pool:
        for job, slim, secs in pool.imap_unordered(_score, jobs):
            split, f, arm, variant = job
            cpu[split, arm_key(arm, variant)] += secs
            if variant == "prag":
                trs = {t.path: t for t in G["folds"][split][f]["test"]}
                for r in slim:
                    t = trs[r["path"]]
                    prag[split, arm].append((r["prag"], r["pclear"], hy.clear_soon(t), t.gtype, hy.level_age(t)))
                continue
            for r in slim:
                scored[split, arm_key(arm, variant)][r["path"]] = (r["nats"], r["steps"])
    T["scoring_s"] = round(time.time() - t0, 1)
    log(f"scoring {len(jobs)} jobs: {T['scoring_s']}s wall")

    # 7. statistics
    t0 = time.time()
    results = {"stale_pre_check": stale_sum, "novel_share": novel, "splits": {}, "agency_diag": ag_lines}
    for split in SPLITS:
        per = {k: v for (s, k), v in scored.items() if s == split}
        rows = boot_table(per, traces)
        # item 7: gain of each variant over the same arm fresh (paired)
        carry = {}
        for arm in CARRY_ARMS:
            for v in ("type", "carry", "carry+type", "prime"):
                k = f"{arm}+{v}"
                if k in per:
                    carry[k] = hy.paired_boot(per[k], per[arm], per[k].keys(), seed=4)
        # heads: mean over seeds and per-seed
        aucs = {}
        for arm in PRAG_ARMS:
            recs = prag[split, arm]
            pr = [(np.array(p), np.array(y)) for p, _, y, _, _ in recs]
            aucs[arm] = {"pragmatic": hy.boot_auc(pr), "pragmatic_within": hy.boot_within_auc(pr),
                         "p_clear_ctx": hy.boot_auc([(np.array(c), np.array(y)) for _, c, y, _, _ in recs]),
                         "p_clear_ctx_within": hy.boot_within_auc([(np.array(c), np.array(y)) for _, c, y, _, _ in recs])}
            for gt in ("click", "button", "mixed"):
                sub = [(np.array(p), np.array(y)) for p, _, y, g, _ in recs if g == gt]
                if sub:
                    aucs[arm][f"within_{gt}"] = hy.boot_within_auc(sub)
            if arm == "flat":
                la = [(np.array(a, float), np.array(y)) for _, _, y, _, a in recs]
                aucs["level_age_baseline"] = {"pooled": hy.boot_auc(la), "within": hy.boot_within_auc(la)}
        types = {t.path: t.gtype for t in traces}
        pairs = {}
        for a, b in PAIRS:
            if a in per and b in per:
                d = {"all": hy.paired_boot(per[a], per[b], per[a].keys(), seed=5)}
                for gt in ("click", "button", "mixed"):
                    ks = [k for k in per[a] if types[k] == gt]
                    if ks:
                        d[gt] = hy.paired_boot(per[a], per[b], ks, seed=6)
                pairs[f"{a} vs {b}"] = d
        results["splits"][split] = {"arms": rows, "carry_vs_fresh": carry, "auc": aucs, "pairs": pairs,
                                    "per_trace": {k: v for k, v in per.items()},
                                    "cpu_s": {k: round(v, 1) for (s, k), v in cpu.items() if s == split}}
    T["statistics_s"] = round(time.time() - t0, 1)
    T["total_s"] = round(time.time() - t_all, 1)
    results["timings"] = T
    (out / "results.json").write_text(json.dumps(results, indent=1, default=str))
    (out / "timings.json").write_text(json.dumps(T, indent=1))

    # 8. table
    lines = []
    for split in SPLITS:
        R = results["splits"][split]["arms"]
        lines += [f"## split: {split} (novel label share {novel[split]:.3f})", "",
                  "| arm | nats/step [95% CI] | gain vs flat [95% CI] | game-cluster CI | click gain | button gain | mixed gain |",
                  "|---|---|---|---|---|---|---|"]
        base = list(BASE_ARMS) + [f"ebul-{o}-s{sd}" for o in OBJECTIVES for sd in args.seeds]
        order = [k for k in base if k in R] + sorted(k for k in R if k not in base)
        for k in order:
            r = R[k]
            a = r["all"]
            cells = [f"{a['nats']:.3f} [{a['nats_ci'][0]:.3f}, {a['nats_ci'][1]:.3f}]", fmt_ci(a["gain"], a["gain_ci"]),
                     f"[{r['all_game_cluster']['gain_ci'][0]:+.3f}, {r['all_game_cluster']['gain_ci'][1]:+.3f}]"]
            for gt in ("click", "button", "mixed"):
                cells.append(fmt_ci(r[gt]["gain"], r[gt]["gain_ci"]) if gt in r else "-")
            lines.append(f"| {k} | " + " | ".join(cells) + " |")
        lines += ["", "carry / type-prior gain over the same arm fresh:", ""]
        for k, v in results["splits"][split]["carry_vs_fresh"].items():
            lines.append(f"- {k}: {fmt_ci(v['gain'], v['gain_ci'])} nats/step")
        lines += ["", "paired differences (gain = second arm's nats minus first arm's; positive = first arm better):", ""]
        for k, d in results["splits"][split]["pairs"].items():
            lines.append(f"- {k}: all {fmt_ci(d['all']['gain'], d['all']['gain_ci'])}; " + "; ".join(
                f"{gt} {fmt_ci(d[gt]['gain'], d[gt]['gain_ci'])}" for gt in ("click", "button", "mixed") if gt in d))
        lines += ["", "clear-soon AUC (clear within 5 actions, test fold; pooled and within-trace):", ""]
        ci_s = lambda v: f"{v[0]:.3f} [{v[1][0]:.3f}, {v[1][1]:.3f}]"  # noqa: E731
        for arm, v in results["splits"][split]["auc"].items():
            if arm == "level_age_baseline":
                lines.append(f"- steps-since-level-start baseline: pooled {ci_s(v['pooled'])}; within {ci_s(v['within'])}")
                continue
            extra = "; ".join(f"{k.split('_')[1]} {vv[0]:.3f}" for k, vv in v.items() if k.startswith("within_"))
            lines.append(f"- {arm}: pragmatic pooled {ci_s(v['pragmatic'])}, within {ci_s(v['pragmatic_within'])}; "
                         f"p(clear|ctx) pooled {ci_s(v['p_clear_ctx'])}, within {ci_s(v['p_clear_ctx_within'])}; "
                         f"pragmatic within by type: {extra}")
        lines.append("")
    lines += ["stale-pre check (round-one size outcome, back-off, all 53, in-sample):", json.dumps(stale_sum, indent=1),
              "", "timings: " + json.dumps(T)]
    (out / "table.md").write_text("\n".join(lines) + "\n")
    log("\n".join(lines))


if __name__ == "__main__":
    main()

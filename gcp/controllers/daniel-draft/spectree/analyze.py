"""Analyze spectree_sim.py output (rows.npz): chains, static and dynamic trees, confidence-cut depth, batch-level
width, through a LOCKSTEP replay and a step-time model at 13 lanes (3-Oct-2026, daniel-draft spectree). numpy only.

  C:/Python312/python.exe analyze.py RESULT_DIR [--lanes 13] [--reps 3] [--json OUT.json]

Replay: each sampled request window is a lane; G lanes step together. At a step every lane is at a row p (its last
verified token is p+1); the policy picks each lane's draft depth / tree, the lane keeps `acc` drafts (the longest
prefix of the real continuation the drafts contain; for rejection sampling a coin per draft with min(1, q/p)) and
moves to p + 1 + acc. Step starts therefore fall where the policy puts them, as live (the greedy width-4 replay
reproduces the capture's own accept length). A batch ends when any lane runs out of rows.
Step time T (ms) for a batch: V(verify tokens) + 0.5 per draft step (x (1 + 0.15 (k - 1)) for a topk-k tree, an
assumption), with V anchored on measured runs:
  k13ctl (13 slots, 12.4 busy, kv4, width 4): 822 tok/s at accept 2.794 -> 42.0 ms = V(4 x lanes) 40.5 + 3 x 0.5;
  10-lane width ladder (qsaring, T0.7): width 4/5/6/8 -> 38/42/46/52 ms: per extra position one draft step (~0.5 ms;
  profile: draft 1.5 ms for 3 steps) + its verify tokens: ~0.35 ms per token up to width 6, ~0.25 beyond.
  ragged = verify tokens are the sum of each lane's own width (needs per-request verify lengths: not in the fork for
  NEXTN/QSA/GDN); uniform = every lane verifies the batch's widest (today's fixed-shape CUDA graphs).
Trees are costed like a chain of the same verify width (the tree mask itself assumed free).
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

BIG = 1 << 20


class Model:
    TOK, TOK_HI, DRAFT = 0.35, 0.25, 0.5  # ms per verify token (to 6 per lane, beyond), ms per draft step

    def __init__(self, lanes):
        self.lanes = lanes

    def V(self, tokens):
        a, b6 = 4 * self.lanes, 6 * self.lanes
        if tokens <= b6:
            return 40.5 + self.TOK * (tokens - a)
        return 40.5 + self.TOK * (b6 - a) + self.TOK_HI * (tokens - b6)

    def T(self, verify_tokens, draft_steps, k=1):
        return self.V(verify_tokens) + self.DRAFT * draft_steps * (1 + 0.15 * (k - 1))


def lead(ok):
    """Leading True count per row of a bool [n, S] array."""
    return np.cumprod(ok, 1).sum(1)


def static_tree(rank_fit, N, cap=8):
    """Best static tree of N-1 draft nodes (rank tuples, prefix-closed) by visit frequency on rank_fit."""
    cnt = Counter()
    for r in rank_fit:
        pre = ()
        for x in r:
            if x >= cap:
                break
            pre = pre + (int(x),)
            cnt[pre] += 1
    chosen = set()
    for node, _ in sorted(cnt.items(), key=lambda kv: (-kv[1], len(kv[0]))):
        if len(chosen) >= N - 1:
            break
        if len(node) == 1 or node[:-1] in chosen:
            chosen.add(node)
    return chosen


def tree_acc(rank, chosen):
    out = np.zeros(len(rank), dtype=np.int64)
    for i, r in enumerate(rank):
        pre = ()
        for x in r:
            pre = pre + (int(x),)
            if pre not in chosen:
                break
            out[i] += 1
    return out


class Replay:
    def __init__(self, z, lanes, G, reps, seed=0):
        self.req = z["req"]
        self.pos = z["pos"]
        self.S = z["rank"].shape[1]
        self.m = Model(lanes)
        self.G = G
        # windows: contiguous rows of one request
        starts = np.flatnonzero(np.r_[True, (self.req[1:] != self.req[:-1]) | (self.pos[1:] != self.pos[:-1] + 1)])
        ends = np.r_[starts[1:], len(self.req)]
        self.win = list(zip(starts, ends))
        rng = np.random.default_rng(seed)
        self.groups = []
        for _ in range(reps):
            order = rng.permutation(len(self.win))
            for g in range(len(order) // G):
                self.groups.append([self.win[i] for i in order[g * G:(g + 1) * G]])

    def run(self, policy, seed=1):
        """policy(rows [G], rng) -> (acc [G], verify widths [G] (1 + drafts), draft_steps, k).
        Returns tokens/step per lane, ragged and uniform tok/s, mean verify width."""
        rng = np.random.default_rng(seed)
        tok = steps = 0
        t_rag = t_uni = 0.0
        vsum = 0
        for grp in self.groups:
            cur = np.array([s for s, e in grp])
            end = np.array([e for s, e in grp])
            while True:
                acc, width, dsteps, k = policy(cur, rng)
                tok += int((1 + acc).sum())
                steps += 1
                vsum += int(width.sum())
                t_rag += self.m.T(width.sum(), dsteps, k)
                t_uni += self.m.T(width.max() * len(width), dsteps, k)
                cur = cur + 1 + acc
                if (cur >= end).any():
                    break
        G = self.G
        return {"tokens_per_step": tok / steps / G, "verify_width": vsum / steps / G,
                "tps_ragged": tok / t_rag * 1000, "tps_uniform": tok / t_uni * 1000, "batch_steps": steps}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("res", type=Path)
    ap.add_argument("--lanes", type=int, default=13)
    ap.add_argument("--reps", type=int, default=3, help="random lane groupings")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--tok-ms", type=float, default=0.35)
    ap.add_argument("--tok-ms-hi", type=float, default=0.25)
    ap.add_argument("--draft-ms", type=float, default=0.5)
    ap.add_argument("--deep-haircut", type=float, default=1.0,
                    help="multiply the conditional acceptance at draft depths >= 4 by this (sensitivity)")
    a = ap.parse_args()
    Model.TOK, Model.TOK_HI, Model.DRAFT = a.tok_ms, a.tok_ms_hi, a.draft_ms
    z = np.load(a.res / "rows.npz")
    rank, pt, qrst, qmax, req = z["rank"], z["pt"], z["qrst"], z["qmax"], z["req"]
    n, S = rank.shape
    G = a.lanes
    acc_rs = np.minimum(1.0, qrst / np.maximum(pt, 1e-9))
    H = np.ones(S)
    H[3:] = a.deep_haircut
    acc_rs = acc_rs * H[None, :]
    lead0_det = lead(rank == 0)

    class Lead0:  # greedy chain acceptance; with a haircut, each depth >= 4 acceptance is thinned at random
        def __getitem__(self, rows):
            if a.deep_haircut >= 1.0:
                return lead0_det[rows]
            return lead((rank[rows] == 0) & (_rng.random((len(rows), S)) < H[None, :]))
    _rng = np.random.default_rng(7)
    lead0 = Lead0()
    conf_g = z["bconf1"][:, :S]                 # the served free-running greedy chain's top-1 probabilities
    R = Replay(z, G, G, a.reps)
    out = {"rows": int(n), "requests": int(req.max() + 1), "lanes": G, "windows": len(R.win),
           "lane_groups": len(R.groups)}
    print(f"rows {n}, request windows {len(R.win)}, {len(R.groups)} batches of {G} lanes; "
          f"p(t)=0 share {float((pt <= 0).mean()):.4f}")

    def rs_acc(rows, d, rng):
        u = rng.random((len(rows), S))
        ok = u < acc_rs[rows]
        return np.minimum(lead(ok), d)

    def chain(W, mode):
        def pol(rows, rng):
            d = W - 1
            acc = np.minimum(lead0[rows], d) if mode == "greedy" else rs_acc(rows, d, rng)
            return acc, np.full(len(rows), W), d, 1
        return pol

    # ---- calibration: greedy width-4 replay vs the live capture ----
    st = z["srv_acc"] >= 0
    if st.any():
        ct, sd = z["chain_tok"][st][:, :3], z["srv_drf"][st]
        cal = {"live_tokens_per_step": float(z["srv_acc"][st].mean()),
               "replay_greedy_w4": R.run(chain(4, "greedy"))["tokens_per_step"],
               "copy_equals_served_draft_by_depth": [round(float((ct[:, j] == sd[:, j]).mean()), 4) for j in range(3)],
               "verify_starts_seen": int(st.sum())}
        out["calibration"] = cal
        print(f"calibration: live tokens/step {cal['live_tokens_per_step']:.3f} (capture, greedy width 4) vs replay "
              f"{cal['replay_greedy_w4']:.3f}; copy==served draft by depth {cal['copy_equals_served_draft_by_depth']}")

    ref = R.run(chain(4, "rs"))
    REF = ref["tps_uniform"]
    out["ref_rs_w4"] = ref
    pct = lambda x: f"{x / REF - 1:+.1%}"  # noqa: E731
    print(f"\nreference = RS chain width 4: {ref['tokens_per_step']:.3f} tokens/step, model {REF:.0f} tok/s at {G} lanes")

    print("\nCHAINS")
    print("  width  greedy tok/step  tok/s   vs ref |  RS tok/step  tok/s   vs ref")
    out["chains"] = {}
    for W in range(2, S + 2):
        g, r_ = R.run(chain(W, "greedy")), R.run(chain(W, "rs"))
        out["chains"][W] = {"greedy": g, "rs": r_}
        print(f"  {W}      {g['tokens_per_step']:.3f}        {g['tps_uniform']:5.0f}  {pct(g['tps_uniform'])} |  "
              f"{r_['tokens_per_step']:.3f}       {r_['tps_uniform']:5.0f}  {pct(r_['tps_uniform'])}")

    # ---- static trees: fit on even request ids, replay on odd and vice versa ----
    print("\nSTATIC TREES (target-only verify; rank-tuple tree fit on the other half of the requests)")
    print("  width N  tok/step  tok/s   vs ref   nodes per depth (fit on even)")
    out["static_trees"] = {}
    ev = req % 2 == 0
    for N in range(3, 11):
        t_even, t_odd = static_tree(rank[ev], N), static_tree(rank[~ev], N)
        acc_st = np.where(ev, tree_acc(rank, t_odd), tree_acc(rank, t_even))
        depth = max(max(len(x) for x in t_even), max(len(x) for x in t_odd))

        def pol(rows, rng, acc_st=acc_st, N=N, depth=depth):
            return acc_st[rows], np.full(len(rows), N), depth, 2
        r_ = R.run(pol)
        shape = dict(sorted(Counter(len(x) for x in t_even).items()))
        out["static_trees"][N] = {**r_, "shape_even": shape}
        print(f"  {N:2d}      {r_['tokens_per_step']:.3f}    {r_['tps_uniform']:5.0f}  {pct(r_['tps_uniform'])}   {shape}")

    # ---- dynamic trees (sglang topk k) ----
    out["dynamic_trees"] = {}
    for key in sorted(k for k in z.files if k.startswith("brank")):
        k = int(key[5:])
        if k == 1:
            continue
        D = z[key].shape[1]
        trees = {D: z[key]}
        for Dp in range(2, D):
            if f"bshal{k}_{Dp}" in z.files:
                trees[Dp] = z[f"bshal{k}_{Dp}"]
        print(f"\nDYNAMIC TREE topk {k} (sglang beam + rerank, target-only verify; best level count per width)")
        print("  width N  levels  tok/step  tok/s   vs ref")
        res = {}
        for N in range(3, 13):
            best = None
            for Dp, b in sorted(trees.items()):
                if N - 1 > k + (Dp - 1) * k * k:
                    continue
                okd = b < N - 1

                def pol(rows, rng, okd=okd, N=N, Dp=Dp):
                    o = okd[rows] & (rng.random((len(rows), okd.shape[1])) < H[None, :okd.shape[1]])
                    return lead(o), np.full(len(rows), N), Dp, k
                r_ = R.run(pol)
                if best is None or r_["tps_uniform"] > best[1]["tps_uniform"]:
                    best = (Dp, r_)
            Dp, r_ = best
            res[N] = {"levels": Dp, **r_}
            print(f"  {N:2d}       {Dp}     {r_['tokens_per_step']:.3f}    {r_['tps_uniform']:5.0f}  {pct(r_['tps_uniform'])}")
        out["dynamic_trees"][k] = res

    # ---- confidence-cut depth (per lane) ----
    print("\nCONFIDENCE CUT (per lane: draft step s kept while the product of the draft's top-1 probabilities >= tau;"
          f" max {S} steps; RS uses the teacher-forced draft confidence)")
    print("  mode   min  tau   tok/step  width |  ragged tok/s  vs ref |  uniform tok/s  vs ref")
    out["cut"] = {}
    for mode, conf in (("greedy", conf_g), ("rs", qmax)):
        cum = np.cumprod(conf, 1)
        for mind in (1, 2, 3):
            for tau in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7):
                keep = cum >= tau
                keep[:, :mind] = True
                dd = lead(keep)

                def pol(rows, rng, dd=dd, mode=mode):
                    d = dd[rows]
                    acc = np.minimum(lead0[rows], d) if mode == "greedy" else np.minimum(rs_acc(rows, S, rng), d)
                    return acc, 1 + d, int(d.max()), 1
                r_ = R.run(pol)
                out["cut"][f"{mode}_min{mind}_tau{tau}"] = r_
                print(f"  {mode:6s}  {mind}  {tau:.1f}   {r_['tokens_per_step']:.3f}   {r_['verify_width']:.2f} |  "
                      f"{r_['tps_ragged']:5.0f}  {pct(r_['tps_ragged'])} |  {r_['tps_uniform']:5.0f}  "
                      f"{pct(r_['tps_uniform'])}")

    # ---- batch-level width per step (one width for all lanes, picked each step from the drafts' confidence) ----
    print("\nBATCH-LEVEL WIDTH PER STEP (all lanes one width each step: max over W of sum_lanes Ehat(W) / T(W), "
          "Ehat from the draft's cumulative top-1 probabilities x scale)")
    out["batch_width"] = {}
    m = R.m
    for mode, conf in (("greedy", conf_g), ("rs", qmax)):
        cum = np.cumprod(conf, 1)
        for scale in (0.8, 1.0, 1.2):
            def pol(rows, rng, cum=cum, scale=scale, mode=mode):
                best, bw = -1.0, 2
                for W in range(2, S + 2):
                    ehat = (1 + scale * cum[rows, : W - 1].sum(1)).sum()
                    v = ehat / m.T(W * len(rows), W - 1)
                    if v > best:
                        best, bw = v, W
                d = bw - 1
                acc = np.minimum(lead0[rows], d) if mode == "greedy" else rs_acc(rows, d, rng)
                return acc, np.full(len(rows), bw), d, 1
            r_ = R.run(pol)
            out["batch_width"][f"{mode}_x{scale}"] = r_
            print(f"  {mode:6s} x{scale}: tok/step {r_['tokens_per_step']:.3f}  width {r_['verify_width']:.2f}  "
                  f"tok/s {r_['tps_uniform']:.0f}  {pct(r_['tps_uniform'])}")
    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()

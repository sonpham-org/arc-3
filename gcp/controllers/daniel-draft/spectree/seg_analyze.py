"""Analyze segment_sim.py output: acceptance by segment and the gain of segment-keyed draft width (4-Oct-2026,
daniel-draft spectree). numpy only.

  C:/Python312/python.exe seg_analyze.py RESULT_DIR [--json OUT.json]

Per segment (row segment = segment of the first drafted token): share of generated tokens (all captured data),
conditional acceptance alpha_s = P_s / P_(s-1) with P_s = mean prod_(j<=s) min(1, q_rs(t_j) / p(t_j)) (rejection
sampling as served, teacher-forced chain), expected tokens per step 1 + sum_(s<W) P_s at widths 4/6/8, the target's
top-1 probability under the served transform (T 0.7, top-k 20, top-p 0.95) at the first drafted position, and the
greedy-draft (target-only verify) width-4 number next to the live capture's own tokens/step for that segment.
Step mix: every captured decode step's lanes by segment.
Gains (vs width 4 everywhere), step time T(W) = T4 + c (W - 4) per decode step, two settings:
  coordinator: T4 40 ms, c 3.9 ms per extra position;  measured (3-Oct live, 13 lanes): T4 43.5 ms, c 5.0 ms.
  (i) batch-wide width per step from the lanes' segments (the fork can switch one width for the whole batch):
      W* = argmax_W sum_lanes E_seg(W) / T(W), on the captured steps' real segment mix;
  (ii) per-lane widths by segment (needs a ragged-verify port): lane l verifies W_seg(l); verify cost per lane-token
      (c - 0.5) / 13 and 0.5 ms per draft step up to the deepest lane; best W per segment by grid search.
"""
import argparse
import itertools
import json
from pathlib import Path

import numpy as np

NAMES = ["think", "wrap", "body", "other"]
TOOL = (1, 2)
WS = list(range(2, 10))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("res", type=Path)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--lanes", type=int, default=13)
    ap.add_argument("--deep-haircut", type=float, default=1.0,
                    help="multiply the acceptance at draft depths >= 4 by this (calibration to the live width ladder)")
    ap.add_argument("--haircut-from", type=int, default=4, help="first draft depth the haircut applies to")
    ap.add_argument("--expect", action="store_true",
                    help="per-position acceptance = sum_x min(p, q_rs) (expectation given the context) instead of the "
                    "coupling estimate on the sampled token; needed when --temp differs from the capture's sampling")
    ap.add_argument("--cost", default="ladder10",
                    help="ladder10 = 8-bit, 10 lanes, live 3-Oct width ladder (qsaring runs): T(4..8) = 38/42/46/49/52 ms;"
                    " lanes13 = 13 lanes measured (43.5 + 5.0 per position) and coordinator (40 + 3.9)")
    ap.add_argument("--fit-ladder", action="store_true",
                    help="scale the survival at depth d by h^(d-1), h fitted so the greedy (no RS) lane-weighted width "
                    "ratios match the live 8-bit 10-lane T0.7 ladder 2.83/3.12/3.32/3.54 (the copy runs optimistic deep)")
    ap.add_argument("--fit-from", type=int, default=2, help="first depth the ladder fit scales")
    a = ap.parse_args()
    z = np.load(a.res / "rows.npz")
    st = np.load(a.res / "steps.npz")
    stats = json.loads((a.res / "segstats.json").read_text())
    seg0 = z["seg"][:, 0]
    S = z["rank"].shape[1]
    acc_rs = np.minimum(1.0, z["qrst"] / np.maximum(z["pt"], 1e-9))
    if a.expect:
        acc_rs = np.clip(z["rsexp"].astype(float), 0, 1)
    acc_rs[:, a.haircut_from - 1:] *= a.deep_haircut
    gen = stats["generated_tokens"]
    tot = sum(gen.values())
    out = {"generated_tokens": gen, "params": stats["params"], "segments": {}}
    print(f"generated tokens {tot:,}: " + ", ".join(f"{k} {v / tot:.1%}" for k, v in gen.items())
          + f" | parameter names {stats['params']}")
    print(f"rows {len(seg0):,} (by segment: " + ", ".join(f"{NAMES[s]} {(seg0 == s).sum():,}" for s in range(4)) + ")")
    lab, lacc, step = st["lab"], st["acc"], st["step"]
    share = np.bincount(np.where(lab < 0, 3, lab), minlength=4) / len(lab)
    hvec = np.ones(S)
    if a.fit_ladder:
        tgt = np.array([3.116, 3.318, 3.544]) / 2.820
        Pg0 = {s: np.cumprod(z["rank"][seg0 == s] == 0, 1).mean(0) for s in range(4) if (seg0 == s).sum() >= 50}
        best = None
        for h in np.arange(0.80, 1.0001, 0.0025):
            hv = h ** np.maximum(0, np.arange(S) - (a.fit_from - 2))
            Gw0 = {W: sum(share[s] * (1 + (Pg0[s] * hv)[: W - 1].sum()) for s in Pg0) for W in (4, 5, 6, 8)}
            err = float(((np.array([Gw0[5], Gw0[6], Gw0[8]]) / Gw0[4] - tgt) ** 2).sum())
            if best is None or err < best[0]:
                best = (err, h)
        hvec = best[1] ** np.maximum(0, np.arange(S) - (a.fit_from - 2))
        out["fit_ladder_h"] = float(best[1])
        print(f"fit to the live ladder: survival at each depth >= {a.fit_from} x {best[1]:.4f}")
    E = {}
    print("\nseg     share  alpha_1..alpha_8 (RS)                          E w4    w6    w8   | greedy w4  live w4"
          " | p_top1 median  >0.9")
    for s in range(4):
        m = seg0 == s
        if m.sum() < 50:
            continue
        P = np.cumprod(acc_rs[m], 1).mean(0)
        alpha = P / np.r_[1.0, P[:-1]]             # measured (before any ladder fit)
        P = P * hvec
        Es = {W: 1 + P[: W - 1].sum() for W in WS}
        E[s] = Es
        g4 = 1 + np.cumprod(z["rank"][m][:, :3] == 0, 1).sum(1).mean()
        lv = float(lacc[lab == s].mean()) if (lab == s).any() else float("nan")
        pm = z["pmax"][m][:, 0]
        row = {"share": gen[NAMES[s]] / tot, "rows": int(m.sum()), "alpha": alpha.round(4).tolist(),
               "E": {W: round(float(v), 4) for W, v in Es.items()}, "greedy_w4": float(g4), "live_w4": lv,
               "p_top1_median": float(np.median(pm)), "p_top1_gt09": float((pm > 0.9).mean()),
               "draft_top1_conf_median": float(np.median(z["qmax"][m][:, 0]))}
        out["segments"][NAMES[s]] = row
        print(f"{NAMES[s]:6s} {row['share']:5.1%}  " + " ".join(f"{x:.3f}" for x in alpha)
              + f"   {Es[4]:.3f} {Es[6]:.3f} {Es[8]:.3f} | {g4:.3f}     {lv:.3f}   | {row['p_top1_median']:.3f}"
              f"        {row['p_top1_gt09']:.1%}")
    m = np.isin(seg0, list(E))
    P = np.cumprod(acc_rs[m], 1).mean(0) * hvec
    Eall = {W: 1 + P[: W - 1].sum() for W in WS}
    print(f"all rows (oversampled tool calls)  E w4 {Eall[4]:.3f} w6 {Eall[6]:.3f} w8 {Eall[8]:.3f}")
    Ew = {W: sum(share[s] * E[s][W] for s in E) for W in WS}
    print(f"lane-weighted (live mix) E w4 {Ew[4]:.3f} w5 {Ew[5]:.3f} w6 {Ew[6]:.3f} w8 {Ew[8]:.3f}; E5/E4 {Ew[5] / Ew[4]:.3f} "
          f"E6/E4 {Ew[6] / Ew[4]:.3f} E8/E4 {Ew[8] / Ew[4]:.3f}")
    G = {}
    for s in E:
        mm = seg0 == s
        Pg = np.cumprod(z["rank"][mm] == 0, 1).mean(0) * hvec
        G[s] = {W: 1 + Pg[: W - 1].sum() for W in WS}
    Gw = {W: sum(share[s] * G[s][W] for s in G) for W in WS}
    print(f"greedy draft, target-only verify (no RS), lane-weighted: w4 {Gw[4]:.3f} w5 {Gw[5]:.3f} w6 {Gw[6]:.3f} "
          f"w8 {Gw[8]:.3f}; ratios {Gw[5] / Gw[4]:.3f} {Gw[6] / Gw[4]:.3f} {Gw[8] / Gw[4]:.3f} "
          f"(live 3-Oct 8-bit 10 lanes T0.7 no RS: 2.820/3.116/3.318/3.544 = 1.105 1.177 1.257)")

    # ---- step mix ----
    nst = int(step.max()) + 1
    cnt = np.zeros((nst, 5), dtype=np.int64)
    np.add.at(cnt, (step, np.where(lab < 0, 4, lab)), 1)
    bs = cnt.sum(1)
    busy = bs >= 8
    tool_frac = (cnt[:, 1] + cnt[:, 2]) / np.maximum(bs, 1)
    think_frac = cnt[:, 0] / np.maximum(bs, 1)
    mix = {"steps": nst, "busy_steps(>=8 lanes)": int(busy.sum()), "mean_lanes": float(bs.mean()),
           "lane_share": {NAMES[s]: float(cnt[:, s].sum() / cnt.sum()) for s in range(4)},
           "steps_tool_ge_77pct": float((tool_frac[busy] >= 10 / 13).mean()),
           "steps_tool_ge_50pct": float((tool_frac[busy] >= 0.5).mean()),
           "steps_tool_zero": float((tool_frac[busy] == 0).mean()),
           "steps_think_ge_77pct": float((think_frac[busy] >= 10 / 13).mean()),
           "steps_think_all": float((think_frac[busy] == 1).mean()),
           "tool_lanes_per_step_quantiles": np.quantile(cnt[busy][:, 1] + cnt[busy][:, 2], [.1, .25, .5, .75, .9]).tolist()}
    out["step_mix"] = mix
    print(f"\nSTEP MIX: {nst:,} captured decode steps, mean {bs.mean():.1f} lanes; busy steps (>= 8 lanes) "
          f"{busy.sum():,}. Lane share: " + ", ".join(f"{k} {v:.1%}" for k, v in mix["lane_share"].items()))
    print(f"  busy steps with >= 10/13 of lanes in a tool call: {mix['steps_tool_ge_77pct']:.1%}; >= half: "
          f"{mix['steps_tool_ge_50pct']:.1%}; none: {mix['steps_tool_zero']:.1%}; >= 10/13 in reasoning: "
          f"{mix['steps_think_ge_77pct']:.1%} (all lanes: {mix['steps_think_all']:.1%}); tool lanes per step "
          f"q10..q90 {mix['tool_lanes_per_step_quantiles']}")

    # ---- gains ----
    segs = sorted(E)
    Earr = np.array([[E[s][W] if s in E else Eall[W] for W in WS] for s in range(4)])  # [4, len(WS)]
    C = cnt[busy][:, :4].astype(float) + cnt[busy][:, 4:5] * np.array([0, 0, 0, 1.0])  # unknown -> other
    out["gains"] = {}
    if a.cost == "ladder10":
        # 3-Oct runs qr8s3b/qr8s4/qr12s5/qr12s7 (8-bit, 10 lanes, T0.7, first 40 min): step = busy x accept / tok/s
        ladder = {2: 29.5, 3: 33.3, 4: 37.1, 5: 41.4, 6: 44.6, 7: 48.5, 8: 52.4, 9: 56.3}
        settings = [("8-bit 10 lanes, live ladder T(4/5/6/8) = 37.1/41.4/44.6/52.4 ms", ladder)]
    else:
        settings = [(f"{nm}: T4 {T4} ms, +{c} ms per position", {W: T4 + c * (W - 4) for W in WS})
                    for nm, T4, c in (("coordinator", 40.0, 3.9), ("measured", 43.5, 5.0))]
    for name, tab in settings:
        T = np.array([tab[W] for W in WS])
        T4 = tab[4]
        c = None
        tok = C @ Earr                                      # [steps, W]: expected tokens per step at width W
        i4 = WS.index(4)
        base = tok[:, i4].sum() / (T[i4] * len(C))
        fixed = {W: tok[:, j].sum() / (T[j] * len(C)) / base - 1 for j, W in enumerate(WS)}
        bestfix = max(fixed, key=fixed.get)
        j = np.argmax(tok / T[None, :], 1)                  # (i) batch-wide per step
        gi = tok[np.arange(len(C)), j].sum() / T[j].sum() / base - 1
        wdist = np.bincount(j, minlength=len(WS)) / len(j)
        # (ii) per-lane widths by segment (ragged)
        d = 0.5
        Vx = {W: tab[W] - tab[4] - d * (W - 4) for W in WS}  # verify-only extra ms of a uniform width W
        best = (-1, None)
        for combo in itertools.product(WS, repeat=4):
            w = np.array(combo)
            tk = (C * np.array([Earr[s, WS.index(combo[s])] for s in range(4)])[None, :]).sum()
            present = C > 0
            dmax = np.where(present, w[None, :], 0).max(1)
            vx = np.array([Vx[x] for x in combo])
            Tt = (T4 + (C * vx[None, :]).sum(1) / C.sum(1) + d * (dmax - 4)).sum()
            r_ = tk / Tt / base - 1
            if r_ > best[0]:
                best = (r_, combo)
        g = {"fixed_width_gain": {W: round(float(v), 4) for W, v in fixed.items()}, "best_fixed": bestfix,
             "batch_switch_gain": float(gi), "batch_switch_width_share": {W: round(float(x), 3) for W, x in zip(WS, wdist)},
             "per_lane_gain": float(best[0]), "per_lane_widths": dict(zip(NAMES, best[1]))}
        out["gains"][name] = g
        print(f"\nGAIN vs width 4 ({name}): best fixed width {bestfix} "
              f"{fixed[bestfix]:+.1%} (w5 {fixed[5]:+.1%}, w6 {fixed[6]:+.1%}); (i) batch-wide switch by segment mix "
              f"{gi:+.1%} (widths used: " + ", ".join(f"{W}:{x:.0%}" for W, x in zip(WS, wdist) if x > 0.005)
              + f"); (ii) per-lane widths {best[0]:+.1%} with " + ", ".join(f"{NAMES[s]} {best[1][s]}" for s in range(4)))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()

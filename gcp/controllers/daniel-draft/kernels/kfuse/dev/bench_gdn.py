"""GDN recovery micro-benchmark + exactness check (3-Oct-2026, daniel-draft kfuse). Pre-server script, free GPU.

Mirrors his RecoverSSM commit for one 13-lane step on all 36 GDN layers: per layer the boundary pass
(init = working slot, out = track slot or reserved slot 0 for rows crossing no track boundary, steps = boundary
step) then the in-place recovery (init = out = working slot, steps = accepted step), with flashinfer's
gated_delta_rule_mtp exactly as hybrid_linear_attn_backend._fi_recovery_launch calls it (k/v strided views of a
[B, T, conv_dim] buffer, q == k, disable_output, accepted_steps). Original module vs kfuse_gdn (slot-0 CTAs skipped).
Exactness: every non-zero slot of every layer bitwise equal after one commit, from identical starting pools.
Timing: CUDA graph over the 36 layers, cold (1.6 GB of states), for 0 / 1 / 13 crossing rows, and with a pad row.
"""
import json
import os
import sys
import time
import traceback

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kfuse_gdn  # noqa: E402

DEV = torch.device("cuda")
T0 = time.time()
L, B, T, HV, H, D = 36, 13, 4, 48, 16, 128
QD, KD, VD = H * D, H * D, HV * D
CONV = QD + KD + VD
NSLOT = 1 + 2 * B  # slot 0 reserved, working 1..B, track B+1..2B


def emit(**kw):
    kw["t"] = round(time.time() - T0, 1)
    print(json.dumps(kw), flush=True)


def graph_time(fn, reps=10):
    s = torch.cuda.Stream()
    s.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(s):
        fn()
    torch.cuda.current_stream().wait_stream(s)
    torch.cuda.synchronize()
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g):
        fn()
    g.replay(); g.replay()
    torch.cuda.synchronize()
    e0, e1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    e0.record()
    for _ in range(reps):
        g.replay()
    e1.record()
    torch.cuda.synchronize()
    del g
    return e0.elapsed_time(e1) * 1e3 / reps


def main():
    from flashinfer.gdn_kernels import gdn_decode_bf16_state as orig
    t = time.time()
    pat = kfuse_gdn.load()
    emit(kind="patched_module_loaded", seconds=round(time.time() - t, 1))
    gen = torch.Generator(device=DEV).manual_seed(0)
    pools = [(torch.randn(NSLOT, HV, D, D, device=DEV, generator=gen) * 0.05).bfloat16() for _ in range(L)]
    A_log = [torch.log(torch.rand(HV, device=DEV, generator=gen) * 15 + 1).float() for _ in range(L)]
    dt_bias = [torch.randn(HV, device=DEV, generator=gen).bfloat16() for _ in range(L)]
    persist = [torch.randn(B, T, CONV, device=DEV, generator=gen).bfloat16() for _ in range(L)]
    a_st = [torch.randn(B, T, HV, device=DEV, generator=gen).bfloat16() for _ in range(L)]
    b_st = [torch.randn(B, T, HV, device=DEV, generator=gen).bfloat16() for _ in range(L)]
    state_idx = torch.arange(1, B + 1, dtype=torch.int32, device=DEV)
    acc = torch.randint(0, T, (B,), dtype=torch.int32, device=DEV, generator=gen)
    track_idx = torch.zeros(B, dtype=torch.int32, device=DEV)
    track_steps = torch.zeros(B, dtype=torch.int32, device=DEV)

    def kv(l, n):
        mixed = persist[l][:n].reshape(n * T, CONV)
        k = mixed[:, QD:QD + KD].view(n, T, H, D)
        v = mixed[:, QD + KD:].view(n, T, HV, D)
        return k, v

    def commit(fn, pl, n, boundary=True, recovery=True):
        si, tr, ts, ac = state_idx[:n], track_idx[:n], track_steps[:n], acc[:n]
        for l in range(L):
            k, v = kv(l, n)
            if boundary:
                fn(A_log=A_log[l], a=a_st[l][:n], dt_bias=dt_bias[l], q=k, k=k, v=v, b=b_st[l][:n],
                   initial_state_source=pl[l], initial_state_indices=si, output_state_indices=tr,
                   accepted_steps=ts, disable_state_update=False, disable_output=True,
                   use_qk_l2norm_in_kernel=True, scale=None, output=None)
            if recovery:
                fn(A_log=A_log[l], a=a_st[l][:n], dt_bias=dt_bias[l], q=k, k=k, v=v, b=b_st[l][:n],
                   initial_state_source=pl[l], initial_state_indices=si, output_state_indices=si,
                   accepted_steps=ac, disable_state_update=False, disable_output=True,
                   use_qk_l2norm_in_kernel=True, scale=None, output=None)

    def set_crossing(nc, pad=False):
        track_idx.zero_(); track_steps.zero_()
        for r in range(nc):
            track_idx[r] = B + 1 + r
            track_steps[r] = int(acc[r].item()) // 2
        if pad:  # last row = CUDA-graph pad row: slot 0 everywhere
            state_idx[B - 1] = 0
        else:
            state_idx[B - 1] = B

    fails = []
    # ---- exactness: identical starting pools, one commit each, compare all slots but 0
    for nc, pad in ((1, False), (0, False), (B, False), (2, True)):
        set_crossing(nc, pad)
        pa = [p.clone() for p in pools]
        pb = [p.clone() for p in pools]
        commit(orig.gated_delta_rule_mtp, pa, B)
        commit(pat.gated_delta_rule_mtp, pb, B)
        torch.cuda.synchronize()
        eq = all(torch.equal(x[1:], y[1:]) for x, y in zip(pa, pb))
        changed = sum(int((x[1:] != p[1:]).any().item()) for x, p in zip(pa, pools))
        slot0_orig = sum(int((x[0] != p[0]).any().item()) for x, p in zip(pa, pools))
        slot0_pat = sum(int((y[0] != p[0]).any().item()) for y, p in zip(pb, pools))
        emit(kind="gdn_exact", crossing=nc, pad_row=pad, nonzero_slots_bitwise_equal=eq, layers_changed=changed,
             slot0_written_orig_layers=slot0_orig, slot0_written_kfuse_layers=slot0_pat)
        if not eq or slot0_pat:
            fails.append(("exact", nc, pad))
        del pa, pb
    torch.cuda.empty_cache()
    # ---- timing (cold: 36 layers' pools = 1.6 GB)
    res = {}
    for nc, pad in ((1, False), (0, False), (B, False), (1, True)):
        set_crossing(nc, pad)
        for name, fn in (("orig", orig.gated_delta_rule_mtp), ("kfuse", pat.gated_delta_rule_mtp)):
            both = graph_time(lambda: commit(fn, pools, B))
            rec = graph_time(lambda: commit(fn, pools, B, boundary=False))
            bnd = graph_time(lambda: commit(fn, pools, B, recovery=False))
            res[f"{name} crossing={nc} pad={pad}"] = dict(commit_ms=round(both / 1e3, 3), recovery_ms=round(rec / 1e3, 3),
                                                       boundary_ms=round(bnd / 1e3, 3))
            emit(kind="gdn_time", impl=name, crossing=nc, pad_row=pad, commit_ms=round(both / 1e3, 3),
                 recovery_only_ms=round(rec / 1e3, 3), boundary_only_ms=round(bnd / 1e3, 3),
                 state_MB_per_layer=round(B * HV * D * D * 2 / 1e6, 1))
    emit(verdict="PASS" if not fails else "FAIL", fails=fails, summary=res)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        emit(kind="fatal", tb=traceback.format_exc()[-4000:])

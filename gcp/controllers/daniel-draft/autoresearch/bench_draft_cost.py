"""Measured serving cost of a drafter architecture change (drafter autoresearch, 4-Oct-2026).

Times the drafter's 7-guess decode sequence at 10 rows (10 lanes) on the lab GPU: base vs each variant, every sequence
CUDA-graph captured, the weights rotated over --copies (>= 4) independent copies so they come from HBM, not the 128 MB
L2, median of >= 200 replays per variant (variants interleaved round by round, so clock drift hits all alike).
extra_ms_per_guess = (median variant - median base) / 7.

What one guess runs here (draft_torch.Draft methods, bf16, the variant's own modules included): fuse -> attn_hc.mix ->
q/k/v (+ RoPE) -> gated attention over a fixed 2,112-key context plus the keys drafted so far -> o_proj -> attn_hc.combine
-> mlp_hc.mix -> shared expert (+ any extra columns) -> mlp_hc.combine -> mixer.mix -> hot-map lm_head (65,536 x 2,560)
-> argmax -> next input token. Routed experts are left out of base and variant alike (serving runs them as Marlin INT4;
skip_routed): the DELTA of a dense module is representative, the absolute PyTorch time is not. A change that adds
expert/MoE work needs a bytes estimate on top. Sanity: the base's weight bytes per second are reported (HBM is ~1.8 TB/s
peak; a number far above that means the weights were L2-warm).

  python bench_draft_cost.py --variants '[{"name": "shx1920", "sh_extra": 1920}, {"name": "untie_all", "untie": [...]}]'

Variant keys: sh_extra (int), untie (list of Draft attribute paths), untie_groups (int), step_adapter (rank).
Also importable: run(variants, copies=4, rounds=64, rows=10) -> dict.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

import torch
import torch.nn.functional as F

for _p in (Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent / "mtp"):
    if (_p / "draft_torch.py").exists():
        sys.path.insert(0, str(_p))
import draft_torch as dt  # noqa: E402

N_HOT, STEPS, CTX = 65536, 7, 2112


def make_copy(cfg, embed, dev):
    """One independent drafter copy (bf16, random weights at a sane scale) with the variant's modules."""
    d = dt.Draft(1).to(dev)  # one routed slot: routed experts are skipped anyway
    with torch.no_grad():
        for _, p in d.named_parameters():
            p.normal_(0, 0.02)
    if cfg.get("step_adapter"):
        d.add_step_adapter(STEPS, int(cfg["step_adapter"]))
    if cfg.get("sh_extra"):
        d.add_sh_extra(int(cfg["sh_extra"]))
    if cfg.get("untie"):
        d.add_untie(list(cfg["untie"]), int(cfg.get("untie_groups", 1)))
    d = d.to(torch.bfloat16)
    d.embed = embed
    d.skip_routed = True
    return d


def run(variants, copies=4, rounds=64, rows=10, emit=print):
    dev = torch.device("cuda")
    torch.manual_seed(0)
    variants = [{"name": "base"}] + [v for v in variants if v.get("name") != "base"]
    embed = (torch.randn(N_HOT, dt.H, device=dev) * 0.02).to(torch.bfloat16)
    W = [(torch.randn(N_HOT, dt.H, device=dev) * 0.02).to(torch.bfloat16) for _ in range(copies)]
    x0 = torch.randn(rows, dt.HC * dt.H, device=dev).to(torch.bfloat16)
    tok0 = torch.randint(0, N_HOT, (rows,), device=dev)
    ck = torch.randn(CTX, dt.NKV, dt.HD, device=dev).to(torch.bfloat16)
    cv = torch.randn(CTX, dt.NKV, dt.HD, device=dev).to(torch.bfloat16)
    mask = torch.ones(rows, CTX, dtype=torch.bool, device=dev)
    pos0 = torch.full((rows,), 6000, dtype=torch.long, device=dev)
    out = torch.zeros(rows, dtype=torch.long, device=dev)

    def seq(d, w):
        x, tok, ek, ev = x0, tok0, [], []
        for s in range(1, STEPS + 1):
            with d.guess_params(s):
                ys, res = d.attn_hc.mix(d.step_adapt(d.fuse(None, x, d.embed[tok]), s))
                q, gate, k, v = d.row_qkv(ys, pos0 + (s - 1))
                ek.append(k)
                ev.append(v)
                x = d.block_rest(d.attend(q, gate, ck, cv, mask, ek, ev), res)
                m = d.mixer.mix(x)[0]
            tok = F.linear(m, w).argmax(-1)
        out.copy_(tok)

    graphs, wbytes = {}, {}
    with torch.no_grad():
        for v in variants:
            gl = []
            for c in range(copies):
                d = make_copy(v, embed, dev)
                st = torch.cuda.Stream()
                st.wait_stream(torch.cuda.current_stream())
                with torch.cuda.stream(st):
                    for _ in range(3):
                        seq(d, W[c])
                torch.cuda.current_stream().wait_stream(st)
                g = torch.cuda.CUDAGraph()
                with torch.cuda.graph(g):
                    seq(d, W[c])
                gl.append((g, d))
            graphs[v["name"]] = gl
            dense = sum(p.numel() * p.element_size() for _, p in gl[0][1].named_parameters())
            wbytes[v["name"]] = dense
        for gl in graphs.values():  # warm the clocks
            for g, _ in gl:
                g.replay()
        torch.cuda.synchronize()
        ev = {name: [] for name in graphs}
        order = list(graphs)
        for r in range(rounds):
            order = order[1:] + order[:1]  # rotate which variant goes first
            for name in order:
                for g, _ in graphs[name]:
                    a, b = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
                    a.record()
                    g.replay()
                    b.record()
                    ev[name].append((a, b))
        torch.cuda.synchronize()
    med = {n: statistics.median(a.elapsed_time(b) for a, b in e) for n, e in ev.items()}
    base = med["base"]
    # bytes the base reads per sequence: dense weights once per guess (+ the hot lm_head) x 7
    gbps = (wbytes["base"] + N_HOT * dt.H * 2) * STEPS / (base / 1e3) / 1e9
    res = {"rows": rows, "copies": copies, "replays_per_variant": rounds * copies,
           "seq_ms": {n: round(m, 4) for n, m in med.items()},
           "extra_ms_per_guess": {n: round((m - base) / STEPS, 4) for n, m in med.items() if n != "base"},
           "dense_bytes": wbytes, "base_weight_GBps": round(gbps, 1),
           "note": "routed experts excluded from all variants; delta of dense modules only"}
    emit(res)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default='[{"name": "shx1920", "sh_extra": 1920}]')
    ap.add_argument("--copies", type=int, default=4)
    ap.add_argument("--rounds", type=int, default=64)
    ap.add_argument("--rows", type=int, default=10)
    a = ap.parse_args()
    run(json.loads(a.variants), a.copies, a.rounds, a.rows, emit=lambda r: print(json.dumps(r), flush=True))

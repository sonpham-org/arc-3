"""Unit test of the batch-aware reroute in his patched topk.py (runs in his SGLang venv on the GPU; 3-Oct-2026).
Checks, on random and on skewed router logits at 40/88 tokens: each token keeps its own top-k0 experts, the batch's
distinct experts never grow, weights keep their per-token sum, refilled slots come from the batch's loaded set, padded
rows are untouched, and the function replays inside a CUDA graph. Prints one JSON line; exit 1 on failure."""
import json
import os
import sys

os.environ.setdefault("SGLANG_BA_K0", "6")
import torch  # noqa: E402

from sglang.srt.layers.moe import topk as T  # noqa: E402


class Cfg:
    num_fused_shared_experts = 0


def baseline(logits, k):
    p = torch.softmax(logits.float(), dim=1)
    w, ids = p.topk(k, dim=1)
    return T.StandardTopKOutput(w / w.sum(1, keepdim=True), ids.to(torch.int32), logits)


def run(n_tok, skew, k0, dev):
    T._BA_K0 = k0
    g = torch.Generator(device=dev).manual_seed(n_tok * 7 + k0)
    pop = torch.randn(512, device=dev, generator=g) * skew           # popular experts
    # float32: bf16 logits tie often, and the reroute's own top-k may then break a tie at rank k0 differently from
    # the baseline's (equal logits, equal weights: harmless, but it fails the exact core comparison)
    logits = torch.randn(n_tok, 512, device=dev, generator=g) * 2 + pop
    base = baseline(logits, 10)
    pad = torch.tensor(n_tok - 3, device=dev)                         # last 3 rows are graph padding
    out = T._batch_aware_reroute(base, Cfg, pad)
    ok = {}
    ids0, ids1 = base.topk_ids.long(), out.topk_ids.long()
    real = n_tok - 3
    ok["core_kept"] = bool((ids1[:real, :k0].sort(1).values == ids0[:real, :k0].sort(1).values).all())
    u0 = len(set(ids0[:real].flatten().tolist()))
    u1 = len(set(ids1[:real][out.topk_weights[:real] > 0].flatten().tolist()))
    core = set(ids0[:real, :k0].flatten().tolist())
    extra = ids1[:real, k0:][out.topk_weights[:real, k0:] > 0]
    ok["extra_in_core"] = all(x in core for x in extra.flatten().tolist())
    ok["union_not_larger"] = u1 <= u0
    ok["sum_kept"] = bool(torch.allclose(out.topk_weights[:real].float().sum(1), base.topk_weights[:real].float().sum(1),
                                         atol=1e-3))
    ok["pad_untouched"] = bool((ids1[real:] == ids0[real:]).all()) and bool(
        torch.equal(out.topk_weights[real:], base.topk_weights[real:]))
    # CUDA graph replay
    if dev == "cuda":
        static = T.StandardTopKOutput(base.topk_weights.clone(), base.topk_ids.clone(), logits.clone())
        s = torch.cuda.Stream()
        s.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(s):
            for _ in range(2):
                T._batch_aware_reroute(static, Cfg, pad)
        torch.cuda.current_stream().wait_stream(s)
        graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(graph):
            gout = T._batch_aware_reroute(static, Cfg, pad)
        graph.replay()
        torch.cuda.synchronize()
        ok["graph_matches"] = bool(torch.equal(gout.topk_ids, out.topk_ids)) and bool(
            torch.allclose(gout.topk_weights.float(), out.topk_weights.float()))
    dropped_mass = float((base.topk_weights[:real].float() * ~torch.isin(ids0[:real], ids1[:real])).sum(1).mean())
    return {"tokens": n_tok, "skew": skew, "k0": k0, "experts_before": u0, "experts_after": u1,
            "orig_weight_mass_rerouted": round(dropped_mass, 4), **ok}


def main():
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    rows = [run(n, sk, k0, dev) for n in (40, 88) for sk in (0.0, 1.5) for k0 in (4, 6, 8)]
    fails = [r for r in rows if not all(v for k, v in r.items() if isinstance(v, bool))]
    print(json.dumps({"ok": not fails, "device": dev, "rows": rows}))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

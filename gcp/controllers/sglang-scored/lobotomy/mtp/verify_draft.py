"""Does the PyTorch draft copy (draft_torch.py) reproduce the SERVED draft? Checked on stitched V4 capture.

  python verify_draft.py --cap <capture dir> --ckpt <model dir> --mask <prune mask.pt> --hot <hot_tokens_64k.pt>
                         [--requests 24] [--out verify.json]

For every verify step k of a stitched request, the served draft's step-1 proposal (draft_token[1] of step k) was made
at position p = seq_k - 1 from (target hc at p, token p+1). The copy recomputes that proposal with the request's full
context (all positions 0..p, QSA selection included) and the run's own hot-token map. Reports, overall and by context
length: agreement with the served proposal, and step-1 accuracy (proposal == the token that really came) for the copy
and for the served draft. Also checks the prefill chunk ids against the stitched tokens.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_io import load_capture, load_embeddings, load_hc, read_tensor, rope_positions, stitch  # noqa: E402
from draft_torch import load_draft  # noqa: E402

BUCKETS = ((0, 2048), (2048, 2304), (2304, 3072), (3072, 6000), (6000, 20000), (20000, 60000), (60000, 10 ** 9))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--mask", required=True)
    ap.add_argument("--hot", required=True)
    ap.add_argument("--requests", type=int, default=24)
    ap.add_argument("--out", default="verify.json")
    ap.add_argument("--dense", action="store_true", help="dense attention in the copy (diagnostic)")
    ap.add_argument("--nvfp4", action="store_true", help="fake-quantize the copy's MoE like serving (diagnostic)")
    ap.add_argument("--fp8-kv", action="store_true", help="round the copy's K/V through fp8 e4m3 (diagnostic)")
    ap.add_argument("--fp8-idx", action="store_true", help="round the copy's QSA index keys through fp8 (diagnostic)")
    a = ap.parse_args()
    import draft_torch
    draft_torch.FORCE_DENSE = a.dense
    draft_torch.FAKE_FP8_KV, draft_torch.FAKE_FP8_IDX = a.fp8_kv, a.fp8_idx
    t0 = time.time()
    reqs = load_capture(a.cap)
    failed = stitch(reqs)
    ok = [r for r in reqs.values() if r.segments and len(r.steps) >= 4]
    print(json.dumps({"requests": len(reqs), "stitched_with_decode": len(ok), "failed": len(failed),
                      "fail_reasons": sorted({v for v in failed.values()})[:6], "load_s": round(time.time() - t0, 1)}),
          flush=True)
    ok.sort(key=lambda r: r.segments[-1][1])
    step = max(1, len(ok) // a.requests)
    chosen = ok[::step][: a.requests]
    hot = torch.load(a.hot) if a.hot.endswith(".pt") else json.load(open(a.hot))
    draft = load_draft(a.ckpt, a.mask, hot, dtype=torch.bfloat16, device="cuda", nvfp4=a.nvfp4).eval()
    rows_out, id_mismatch = [], 0
    for r in chosen:
        for cpos, n, path, head in r.chunks[:3]:  # prefill ids are token p+1 at row p
            ids = read_tensor(path, head, "ids").long().numpy()
            m = min(n - 1, len(r.tokens) - cpos - 1)
            id_mismatch += int((ids[:m] != r.tokens[cpos + 1: cpos + 1 + m]).sum())
        L = min(r.segments[-1][1], len(r.tokens) - 1)
        qs, served, truth = [], [], []
        for seq, acc, pred, drf, *_ in r.steps:
            p = seq - 1
            if p >= L or p + 2 >= len(r.tokens):
                break
            qs.append(p)
            served.append(int(drf[1]))
            truth.append(int(r.tokens[p + 2]))
        if not qs:
            continue
        t1 = time.time()
        hc = load_hc(r, L).cuda()
        e_in, einfo = load_embeddings(r, L, draft.embed)
        with torch.no_grad():
            _, mixed = draft(hc, None, rows=torch.as_tensor(qs).cuda(), e_in=e_in,
                             rpos=rope_positions(r, L).cuda())
            prop = draft.propose(mixed).cpu()
        served_t, truth_t = torch.tensor(served), torch.tensor(truth)
        rows_out.append({"rid": r.rid[:12], "context": L, "queries": len(qs),
                         "agree": round((prop == served_t).float().mean().item(), 4),
                         "copy_acc": round((prop == truth_t).float().mean().item(), 4),
                         "served_acc": round((served_t == truth_t).float().mean().item(), 4),
                         "first_q": qs[0], "last_q": qs[-1], "sec": round(time.time() - t1, 1), **einfo, "mrope": r.mpos is not None,
                         "_q": qs, "_agree": (prop == served_t).tolist(),
                         "_copy_ok": (prop == truth_t).tolist(), "_served_ok": (served_t == truth_t).tolist()})
        print(json.dumps({k: v for k, v in rows_out[-1].items() if not k.startswith("_")}), flush=True)
        del hc, e_in
        torch.cuda.empty_cache()
    summary = {"prefill_id_mismatches": id_mismatch, "buckets": {}}
    for lo, hi in BUCKETS:
        ag, co, so = [], [], []
        for row in rows_out:
            for q, g, c, s in zip(row["_q"], row["_agree"], row["_copy_ok"], row["_served_ok"]):
                if lo <= q < hi:
                    ag.append(g), co.append(c), so.append(s)
        if ag:
            summary["buckets"][f"{lo}-{hi}"] = {"n": len(ag), "agree": round(sum(ag) / len(ag), 4),
                                                "copy_acc": round(sum(co) / len(co), 4),
                                                "served_acc": round(sum(so) / len(so), 4)}
    for name, sel in (("no_approx_images", [r for r in rows_out if r["approx_image_rows"] == 0]),
                      ("with_approx_images", [r for r in rows_out if r["approx_image_rows"] > 0])):
        xs = [x for row in sel for x in row["_agree"]]
        summary[name] = {"requests": len(sel), "queries": len(xs), "agree": round(sum(xs) / len(xs), 4) if xs else None}
    allq = [x for row in rows_out for x in row["_agree"]]
    summary["overall_agree"] = round(sum(allq) / max(len(allq), 1), 4)
    summary["queries"] = len(allq)
    print(json.dumps(summary, indent=1), flush=True)
    Path(a.out).write_text(json.dumps({"summary": summary, "requests": [
        {k: v for k, v in row.items() if not k.startswith("_")} for row in rows_out]}, indent=1))


if __name__ == "__main__":
    main()

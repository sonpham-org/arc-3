"""kfuse check in the PATCHED install (3-Oct-2026, daniel-draft kfuse). Pre-server script, free GPU.

Runs the dev micro-benchmarks against the code the server will import:
  GDN  bench_gdn.py with hybrid_linear_attn_backend._kfuse_gated_delta_rule_mtp (patched install) as the candidate
  QSA  bench_qsa.py with qsa.sparse_attn.qwen_sparse_nvfp4_fused_decode_triton (patched install, its own tactics)
  HC   bench_hc.py's checks with hyperconnection's kfuse mix path (if present in the install)
Each prints its JSON lines; the last line is {"verdict": ...} per part.
"""
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
T0 = time.time()


def emit(**kw):
    kw["t"] = round(time.time() - T0, 1)
    print(json.dumps(kw), flush=True)


def part_gdn():
    import types

    import bench_gdn
    import kfuse_gdn
    from sglang.srt.layers.attention import hybrid_linear_attn_backend as H

    fn = H._kfuse_gated_delta_rule_mtp()
    mod = sys.modules.get("kfuse_gdn_decode_bf16_state")
    assert mod is not None and fn is mod.gated_delta_rule_mtp, "patched install did not load the kfuse GDN module"
    kfuse_gdn.load = lambda *a, **k: types.SimpleNamespace(gated_delta_rule_mtp=fn)
    emit(part="gdn", installed_kernel=getattr(mod, "__file__", "?"))
    bench_gdn.main()


def part_qsa():
    import bench_qsa
    import torch
    from sglang.srt.layers.attention.qsa import sparse_attn as S

    def fused(q, nvfp4, r2t, row_req, idx, seq, vcnt, scale, **cfg):
        return S.qwen_sparse_nvfp4_fused_decode_triton(q, nvfp4, r2t, row_req, idx, seq, vcnt, scale, True,
                                                       q.shape[0])
    bench_qsa.qsa_nvfp4_fused_decode = fused
    emit(part="qsa", installed=S.__file__)
    bench_qsa.main()


def part_hc():
    from sglang.srt.layers import hyperconnection as HC
    if not hasattr(HC, "_kfuse_hc_mix"):
        emit(part="hc", skipped="no kfuse HC path in this install")
        return
    import bench_hc
    bench_hc.KFUSE_INSTALLED = HC._kfuse_hc_mix
    emit(part="hc", installed=HC.__file__)
    bench_hc.main()


if __name__ == "__main__":
    for f in (part_gdn, part_qsa, part_hc):
        try:
            f()
        except Exception:
            emit(part=f.__name__, fatal=traceback.format_exc()[-3000:])

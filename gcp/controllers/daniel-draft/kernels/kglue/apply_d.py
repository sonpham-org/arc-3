"""kglue small exact glue removals (5-Oct-2026, Kernel optimizations thread). Idempotent: rebuilds each patched file
from its base (his wheel file, or kidx's patched mqa.py) and copies his original into orig/.
  python apply_d.py
Each change has its own off-switch (env read at import):
  SGLANG_KGLUE_IDXFILL=0   mqa.py: indexer logits buffer back to torch.full(-inf) (now torch.empty)
  SGLANG_KGLUE_ROWSTART=0  fast_topk.py: row_starts back to a fresh torch.zeros per call (now a persistent zero slice)
  SGLANG_KGLUE_KVSCALE=0   memory_pool.py: the in-place k/v divides by a unit scale come back
  SGLANG_KGLUE_ALOG=0      gdn_flashinfer.py: A_log back to .detach().float() per call (re-casts to bf16 every call)
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
WHEEL = HERE.parent.parent / "wheel" / "full"


def build(rel, base, subs):
    s = base.read_text(encoding="utf-8")
    for sub in subs:
        old, new, n = (*sub, 1) if len(sub) == 2 else sub
        assert s.count(old) == n, (rel, old[:70], s.count(old))
        s = s.replace(old, new)
    out = HERE / "patched" / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(s, encoding="utf-8")
    orig = HERE / "orig" / rel
    orig.parent.mkdir(parents=True, exist_ok=True)
    orig.write_bytes((WHEEL / rel).read_bytes())
    compile(s, str(out), "exec")
    print("wrote", out)


# 1. indexer logits: every position a row's top-k reads ([0, compressed_lengths[row])) is written by the scoring
# kernel (per-row and kidx grouped), fast_topk never reads past lengths[row] (and for lengths <= 512 reads no score
# at all), so the -inf fill of the whole [rows, max_model_len] fp32 buffer (1.4M elements, 3.4 us per QSA layer on
# the indexer's critical stream) changes nothing that is read.
build("sglang/srt/layers/attention/qsa/mqa.py",
      HERE.parent / "kidx" / "patched" / "sglang/srt/layers/attention/qsa/mqa.py", [
    ("""    logits = torch.full(
        (q.shape[0], max_model_len),
        -float("inf"),
        dtype=torch.float32,
        device=q.device,
    )
    if not q.shape[0] or not max_model_len:
        return logits""",
     """    # kglue (5-Oct-2026): no -inf fill; only [0, context_lens[row]) is written and only that is read by the top-k
    # (fast_topk reads [row_start, row_start + lengths[row]) with lengths = these context lengths).
    # SGLANG_KGLUE_IDXFILL=0 restores the fill.
    if _KGLUE_IDXFILL:
        logits = torch.empty((q.shape[0], max_model_len), dtype=torch.float32, device=q.device)
    else:
        logits = torch.full(
            (q.shape[0], max_model_len),
            -float("inf"),
            dtype=torch.float32,
            device=q.device,
        )
    if not q.shape[0] or not max_model_len:
        return logits"""),
    ('_KIDX_ENABLED = os.environ.get("SGLANG_KIDX", "1") != "0"',
     '_KIDX_ENABLED = os.environ.get("SGLANG_KIDX", "1") != "0"\n'
     '_KGLUE_IDXFILL = os.environ.get("SGLANG_KGLUE_IDXFILL", "1") != "0"  # kglue (5-Oct-2026)'),
])

# 2. fast_topk row_starts: the kernel needs a [B] int32 zero vector when the caller passes None; a fresh
# torch.zeros per call is a 1-block fill kernel on the indexer stream (13 per step). A persistent zero buffer,
# allocated once (before graph capture: the first call is eager) and never written, gives the same values.
build("sglang/kernels/ops/elementwise/fast_topk.py",
      WHEEL / "sglang/kernels/ops/elementwise/fast_topk.py", [
    ("""    if row_starts is None:
        row_starts = torch.zeros(batch, dtype=torch.int32, device=score.device)""",
     """    if row_starts is None:
        # kglue (5-Oct-2026): slice of a persistent, never-written zero buffer instead of a fill per call.
        # SGLANG_KGLUE_ROWSTART=0 restores the per-call torch.zeros.
        zeros = _KGLUE_ZERO_STARTS.get(score.device) if _KGLUE_ROWSTART else None
        if zeros is None and _KGLUE_ROWSTART:
            zeros = torch.zeros(_KGLUE_ZERO_STARTS_LEN, dtype=torch.int32, device=score.device)
            _KGLUE_ZERO_STARTS[score.device] = zeros
        if zeros is not None and batch <= zeros.shape[0]:
            row_starts = zeros[:batch]
        else:
            row_starts = torch.zeros(batch, dtype=torch.int32, device=score.device)"""),
    ("""def fast_topk(""",
     """import os as _kglue_os

_KGLUE_ROWSTART = _kglue_os.environ.get("SGLANG_KGLUE_ROWSTART", "1") != "0"
_KGLUE_ZERO_STARTS = {}
_KGLUE_ZERO_STARTS_LEN = 1 << 16


def fast_topk("""),
])

# 3. FP8 KV write: HybridLinearKVPool.set_kv_buffer defaults k_scale = v_scale = 1.0 and the MHA pool divides k and v
# in place by them before the FP8 cast (two elementwise kernels per QSA layer). x / 1.0 == x exactly (bf16 in, fp32
# math, bf16 out), so skipping a unit divide changes no byte.
build("sglang/srt/mem_cache/memory_pool.py",
      WHEEL / "sglang/srt/mem_cache/memory_pool.py", [
    ("""        if cache_k.dtype != self.dtype:
            if k_scale is not None:
                cache_k.div_(k_scale)
            if v_scale is not None:
                cache_v.div_(v_scale)
            cache_k = cache_k.to(self.dtype)
            cache_v = cache_v.to(self.dtype)""",
     """        if cache_k.dtype != self.dtype:
            # kglue (5-Oct-2026): a divide by a unit scale is the identity; skip its kernel.
            # SGLANG_KGLUE_KVSCALE=0 restores it.
            if k_scale is not None and not (_KGLUE_KVSCALE and _kglue_unit(k_scale)):
                cache_k.div_(k_scale)
            if v_scale is not None and not (_KGLUE_KVSCALE and _kglue_unit(v_scale)):
                cache_v.div_(v_scale)
            cache_k = cache_k.to(self.dtype)
            cache_v = cache_v.to(self.dtype)""", 2),   # MHATokenToKVPool and its sibling pool: same code
])

# 4. GDN verify A_log: gdn_flashinfer passes A_log.detach().float(), a NEW object every call, so flashinfer's
# id-keyed _cached_bf16 misses and re-casts [48] fp32 -> bf16 inside every captured step (36 tiny kernels per step).
# Passing the layer's fp32 parameter itself makes the cache hit; the bf16 values are the same cast of the same data.
build("sglang/srt/layers/attention/linear/kernels/gdn_flashinfer.py",
      WHEEL / "sglang/srt/layers/attention/linear/kernels/gdn_flashinfer.py", [
    ("""                output_wy = gated_delta_rule_mtp_wy_output_only(
                    A_log=A_log.detach().float(),""",
     """                output_wy = gated_delta_rule_mtp_wy_output_only(
                    # kglue (5-Oct-2026): the persistent fp32 parameter, so flashinfer's id-keyed bf16 cache hits.
                    A_log=(A_log if _KGLUE_ALOG and A_log.dtype == torch.float32 else A_log.detach().float()),"""),
])

# memory_pool.py / gdn_flashinfer.py module-level switches (appended after the imports block: first blank line after
# the last top-level import is fragile, so append at module end; the names are only read at call time)
for rel, tail in (
    ("sglang/srt/mem_cache/memory_pool.py",
     '\n\n# kglue (5-Oct-2026)\nimport os as _kglue_os\n\n_KGLUE_KVSCALE = _kglue_os.environ.get("SGLANG_KGLUE_KVSCALE", "1") != "0"\n\n\n'
     'def _kglue_unit(scale) -> bool:\n    return isinstance(scale, (int, float)) and not isinstance(scale, bool) and float(scale) == 1.0\n'),
    ("sglang/srt/layers/attention/linear/kernels/gdn_flashinfer.py",
     '\n\n# kglue (5-Oct-2026)\nimport os as _kglue_os\n\n_KGLUE_ALOG = _kglue_os.environ.get("SGLANG_KGLUE_ALOG", "1") != "0"\n'),
):
    p = HERE / "patched" / rel
    s = p.read_text(encoding="utf-8").rstrip("\n") + "\n" + tail
    compile(s, str(p), "exec")
    p.write_text(s, encoding="utf-8")
    print("switch appended", rel)

# kfuse8: the 8-bit-KV-safe subset of kfuse (4-Oct-2026, daniel-draft kernels)

Son 4-Oct: "convert all the innovations we did to an 8-bit KV cache version" (4-bit KV played ~3-4 points weaker
per action; tonight's Kaggle slot goes to the best 8-bit build). This set holds ONLY the two kfuse files that do not
depend on 4-bit KV or on the qsaring/qsakv4 patch sets; both are byte-identical to `..\kfuse\patched\`:

| file | change | switch |
|---|---|---|
| `sglang/srt/layers/attention/hybrid_linear_attn_backend.py` | GDN RecoverSSM commit skips CTAs whose output slot is the padding slot 0 (boundary pass + graph pad rows); real states bit-identical | `SGLANG_KFUSE_GDN_SKIP=0` |
| `sglang/srt/model_executor/forward_batch_info.py` | async M-RoPE upload: fresh pinned tensor + `non_blocking=True` in `compute_spec_mrope_positions` (image prompts make every batch mixed); verified bit-exact on 40,448 uploads | `SGLANG_KFUSE_ASYNC_MROPE=0` |

Left out (4-bit only): kfuse's `qsa/sparse_attn.py` + `qwen_sparse_attn_backend.py` (fused NVFP4 QSA decode; they carry
qsakv4 + qsaring changes and need those sets) and `..\..\kvshrink\draftkv4\` (exact nvfp4_qsa pool budget; FP8 pools
already use an exact formula).

Use on an 8-bit (fp8_e4m3 KV) build, with kfast (KV-independent):

    make_bench_notebook.py ... --patch-set D:/codex-work/daniel-draft/kernels/kfast --patch-set D:/codex-work/daniel-draft/kernels/kfuse8

Originals checked against his wheel (sha256 prefixes): hybrid_linear_attn_backend.py c0521e84f2c2,
forward_batch_info.py 6d03226fdc2c.

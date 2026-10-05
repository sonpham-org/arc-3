# kgdn: GDN target verify reads q/k/v in place (4/5-Oct-2026, Kernel optimizations thread)

No code patch: one env flag, `FLASHINFER_GDN_WY_STRIDED_QKV=1` (flashinfer's own switch in
`gdn_kernels/gdn_decode_bf16_wy_output_only.py`, default off). Remove the flag to restore his behaviour.

## What it does
In target verify, q/k/v are torch.split views of the conv output (qkv_dim 10240 > MAX_FUSED_QKV_SPLIT_DIM 8192), so
`gated_delta_rule_mtp_wy_output_only` made 3 .contiguous() copies per linear-attention layer (36 layers, 108 copies
per step). With the flag it passes the row stride and reads q/k/v where they are.

## Evidence
- check_kgdn.py (daniel-bench-kgdn-1004 pre-script): output bitwise equal (max diff 0.0) at T = 4 and 8, B = 9 and 10;
  CUDA-graph replay equal. Microbench (36 calls) 24.8 -> 14.5 us per layer (said -0.37 ms/step; overstated, cold copies).
- In-server (daniel-bench-kgdn-1004 vs control daniel-bench-kprof2-1004, same stack kfast + kfuse8 + kq8, W4, 10 lanes):
  the 4,360 copy kernels per 40 steps (elementwise_kernel nocast, 1.8 us) are gone, the GDN kernel itself is unchanged
  (13.5 us); norm/elementwise 1.96 -> 1.77 ms/step in both profiles = **-0.19 ms GPU per step**. tok/s 799 vs 766, accept
  2.97 vs 2.99 (one pair, inside noise). serve.log clean.

## Use
    make_bench_notebook.py ... --env FLASHINFER_GDN_WY_STRIDED_QKV=1

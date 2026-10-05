# kglue: exact glue removals and merges (5-Oct-2026, Kernel optimizations thread)

Son 5-Oct: "do 1, 2, 3, 4 and get that 3%". Targets from the per-iteration kernel inventory of the 8-bit shipping
stack (W4, 10 lanes; kernels/kglue/exposed.py, seq.py, gaps.py on daniel-bench-kgdn-1004 m20): 1,547 small kernels per
decode iteration, 2.1 ms of exposed GPU time, 0.83 ms fully idle (gaps of ~0.47 us).
Every change is meant to leave every output byte unchanged; each has its own off-switch.

Supersedes (same his-original sha, carries their changes): khc's hyperconnection.py, kidx/kidxr's mqa.py (identical in
both), kfast's fused_marlin_moe.py. Use INSTEAD of khc; with kfast + kfuse8 + kq8 + kidx (or kidxr).
The kfast GEMM's PDL launch lives in two separate one-file sets so it pairs with either GEMM table:
../kpdl (kfast + PDL, W4) or ../kpdl128 (kfast128 + PDL, W8); each supersedes its base's sm120_lowm_bf16_gemm.py.

| change | file | switch (default on) |
|---|---|---|
| HC combine apply + the next mix's per-branch norm in one kernel (JIT CUDA, the norm kernel's own code; successor learned at runtime) | hyperconnection.py | SGLANG_KGLUE_HCNORM=0 |
| QSA indexer logits: no -inf fill of [rows, max_len] fp32 (only [0, len) is written and read) | mqa.py | SGLANG_KGLUE_IDXFILL=0 |
| fast_topk row_starts: persistent zero slice instead of a fill per call | fast_topk.py | SGLANG_KGLUE_ROWSTART=0 |
| FP8 KV write: skip k/v.div_(1.0) (unit scale = identity) | memory_pool.py | SGLANG_KGLUE_KVSCALE=0 |
| GDN verify: pass the fp32 A_log parameter so flashinfer's id-keyed bf16 cache hits (no cast per layer per step) | gdn_flashinfer.py | SGLANG_KGLUE_ALOG=0 |
| MoE: routed top-k sum done inside the shared-expert gate kernel (topk_sum kernel gone) | fused_marlin_moe.py, qwen2_moe.py | SGLANG_KGLUE_GATESUM=0 |
| PDL launch for the kfast skinny GEMM (~255 launches/step; sets ../kpdl, ../kpdl128) and the fused-mix kernels | sm120_lowm_bf16_gemm.py, hyperconnection.py | SGLANG_KGLUE_PDL=0 |
| khc fused HC mix made EXACT and on by default: down projection split into cuBLAS's own 20 K slices (33..64 rows), proven per shape at first eager use against the compiled chain (6 random inputs, down projection and output); other row counts keep the compiled chain | hyperconnection.py | SGLANG_KGLUE_MIX_EXACT=0 (fixed split, not exact), SGLANG_KHC_MIX_MAX_ROWS=0 (off) |

Build: apply_hc.py (from khc), apply_d.py, apply_c.py, apply_pdl.py; all idempotent. Check: check_kglue.py (pre-script).
Looked at and left alone: Marlin's per-call workspace zeros and intermediate_cache13 zeros (the fork's comments cite
capture deadlocks and masked rows; small gain, real risk); the shared-expert input clone (off the critical path);
GDN a/b stash copies (needs a hook into the projection; ~0.04 ms).

## Evidence (5-Oct-2026)
Bitwise checks (check_kglue.py, pre-server, real served weights; runs daniel-bench-kglue1/2/3-1005, kmix-1005):
- combine + norm: out and normed bitwise equal at 1..64 rows, deterministic; module path learns the link and the
  second forward launches the fused kernel (one norm left: the first layer's input); CUDA-graph replay equal.
  Cold microbench 6.12 -> 5.29 us per boundary at 40 rows.
- top-k sum in the gate kernel: bitwise equal at 1..80 rows with the real shared_expert_gate weight (top-k 10).
  Only all-denormal inputs (|x| ~ 1e-39) differ: topk_sum is built with --use_fast_math (flush to zero), Triton is
  not; expert outputs never sit there. Microbench (one stream) 3.65 -> 2.20 us per layer at 40 rows.
- small removals: fast_topk returns the same index sets with NaN / inf / 1e30 garbage past each row's length (40 x
  34,816 and 80 x 34,816 rows, lengths up to the full row); x.div_(1.0) is the identity on all 65,536 bf16 patterns;
  GDN WY output with the fp32 A_log parameter equals .detach().float() bitwise and the repeat call launches no cast.
- PDL: kfast skinny output bitwise equal with and without PDL on all 6 tactic shapes x 10/40/64 rows; a 108-kernel
  dependent chain replays equal in a CUDA graph; chain 1,877.7 -> 1,861.4 us (~0.23 us per transition).
- exact fused mix: the 0.05% of differing elements came only from the down projection's split-K order. With cuBLAS's
  20 slices the down projection equals F.linear and the output equals the compiled chain at every row count 33..64
  (48 shapes, fresh inputs) and for all 72 tile / warp / stage tactics tried; 17..32 rows have no bitwise split and
  keep the compiled chain. A looser first check (any of 8 splits, 2 inputs) accepted a wrong split at 22 rows: now
  only cuBLAS's split and 6 inputs. Fastest exact tactic 16.6 us vs the compiled chain 20.1 us per boundary at 40
  rows (-0.35 ms per step); the one-launch down+reduce variant (arrival counter) was slower (23.8 us), off.

In-server (10 lanes, W4, 8-bit route, kfast + kfuse8 + kq8 + kidx + strided GDN flag; control daniel-bench-kctl-1005
= same with khc; per decode iteration, median of 24, minutes 10 and 20; compare_runs.py):
- kglue1 (combine+norm + small removals): HC norms 109 -> 8 per iteration, combine+norm busy 705 -> 540-580 us;
  the -inf fill (13 x 3.7 us), unit divides (30 x 1.7 us), A_log casts (36 x 1.2 us) and 13 zero fills are gone;
  2,575 -> 2,404 kernels per iteration. Greedy vs control: mean |dlogprob| 0.035 / 0.048 (identical-server floor
  0.051 / 0.058). serve.log clean.
- kglue2 (+ top-k sum in gate + PDL): topk_sum gone (-130 us, gate +31 us), 2,331 kernels per iteration. Greedy
  0.049 / 0.029. serve.log clean.
Run-level wall time cannot resolve these (MoE and indexer time move 1 ms between runs with routing and context).

## Combined result (kglue + kpdl + klmh vs today's exact stack), 5-Oct
Runs daniel-bench-kalla-1005 / kallb-1005 (nb-bench/kall-1005) vs controls kctl-1005 / kctlb-1005 (nb-bench/kctl-1005 =
kfast + kfuse8 + kq8 + kidx + khc + FLASHINFER_GDN_WY_STRIDED_QKV=1), minutes 10 and 20, compare_runs.py:
- wall minus routing/context-dependent kernels (Marlin, indexer, attention, index top-k) per decode iteration:
  controls 14.07 / 14.70 / 14.09 / 14.15 ms, kglue+klmh 13.41 / 13.38 / 13.47 / 13.39 ms: about -0.84 ms (~2.7%
  of a ~30.9 ms step). Kernels per iteration 2,575 -> 2,131; fully idle 0.89 -> 0.65 ms.
- per family: HC mix chain 1,895 us -> 1,650 (exact fused mix, 300 kernels instead of 515); lm_head 889 -> 701;
  topk_sum gone (gate +31 us); the fills / divides / casts above gone.
- greedy vs control: 0.062 / 0.071 and 0.032 / 0.040 (control vs control 0.037 / 0.038; earlier identical pairs up to
  0.063). tok/s 813 / 836 vs 818 / 789 (one 25-min run each: noise). serve.log clean; klmh on in both.

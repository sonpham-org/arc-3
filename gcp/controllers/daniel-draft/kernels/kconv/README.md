# kconv: GDN verify conv in one tile per block (4-Oct-2026, daniel-draft kernels)

Patch set for `make_bench_notebook.py --patch-set D:\codex-work\daniel-draft\kernels\kconv` (orig/ = his bytes from
the wheel, sha256 77c8a9ce1ebe; patched/ = ours). One file: `sglang/kernels/ops/mamba/causal_conv1d_triton.py`.
Composes with every other set (no file overlap). Lossless: outputs, rolled conv states and intermediate windows are
**bit-identical** to his kernel (checked).

## What was slow

His `_causal_conv1d_update_kernel` (the target-verify conv of the 36 GDN layers) took 8.4 / 21.6 / 41.4 / 63.6 us
per call at verify width 4 / 8 / 12 / 16 in the server (traces kw4r / kw8rb / kw12r / kw16r), i.e. 0.18 ms per
extra draft position per verify. It walks the W tokens one by one per (request, 256-channel block), and after each
token stores the token's conv window into his **deduplicated** intermediate-window pool
(`memory_pool._allocate_deduplicated_conv_window`: step stride = window stride = 1, one `[D + 2]` row per channel).
That is 3 x W overlapping 2-byte stores per channel, each one sector at a 2(D + 2)-byte stride, so it gets worse as
W grows. (A microbench with a dense window layout does not show it: 18 us at W16.)

## Change

New `_kconv_update_chain_kernel`, used by `causal_conv1d_update` when: seqlen > 1, width 4, no eagle tree
(`retrieve_next_token is None`, topk = 1), no `num_accept_tokens`, no `cache_seqlens`, conv state dtype = x dtype,
continuous batching. All W tokens of a block are one `[tokens, channels]` tile; same products in the same
order (bias + x[t-3] w0 + x[t-2] w1 + x[t-1] w2 + x[t] w3, input-dtype products into an fp32 sum), same SiLU, same
conv-state roll. With the dedup pool each window position is written once (x[i - 2], history columns for i < 2) as a
row-contiguous tile; with a dense pool the three window columns are written as tiles. Channel block 64, 2 warps.

Switches (server env): `SGLANG_KCONV=0` (his kernel), `SGLANG_KCONV_BLOCK_N`, `SGLANG_KCONV_WARPS`.

## Checked (run daniel-bench-kchk2-1004, `check_kconv.py`, his venv, RTX PRO 6000)

- Exactness: 60 / 60 cases bitwise equal (out, conv states, window pool) for W = 2..16, channel blocks 32-256, both
  pool layouts, a PAD slot row, `out=None`; CUDA-graph capture + replay with fresh inputs equal to his eager kernel.
- us per call, served layout, 10 requests, CUDA graph over 36 layer copies:

| W | his | kconv (64 ch, 2 warps) |
|---|---|---|
| 4 | 8.5 | 4.1 |
| 6 | 15.3 | 5.8 |
| 8 | 23.9 | 6.7 |
| 12 | 45.4 | 8.0 |
| 16 | 68.9 | 9.4 |

Per verify (x 36): -0.16 ms at W4, -0.62 ms at W8, -1.35 ms at W12, -2.15 ms at W16; the per-position growth of this
kernel drops from ~0.18 ms to ~0.015 ms. Bench A/B: see the session report.

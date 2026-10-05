# kdsamp: draft proposal top-k first (4-Oct-2026, daniel-draft kernels)

Patch set for `make_bench_notebook.py --rs --patch-set D:\codex-work\daniel-draft\kernels\kdsamp`. One file:
`sglang/srt/speculative/spec_utils.py`, which **supersedes the rs set's copy** (orig/ = his bytes, sha256
0c5b2fce32cf, the same orig as rs/; patched/ = rs's patched file + kdsamp), so it needs `--rs`.

## What was slow

Under rejection sampling every chained draft step (and the eager first-token draw after draft extend) runs the rs
proposal: softmax(logits / T) over the 64k hot vocab, flashinfer top-k renorm, top-p renorm (5 kernels), then a
Gumbel draw over all 64k ids (exp / clamp / div / argmax / gather). At 10 rows that is ~125 us per call, all latency:
1-3 CTAs per row on 188 SMs for 2.6 MB of data.

## Change

`sample_draft_proposal` (same signature and outputs: dense q [B, V] fp32, q(X) [B, 1], X [B, 1] int64) now:
1. per 1024-id chunk, the max logit;
2. every logit >= the 32nd largest chunk max is a candidate (that bound always contains the whole top 32; the q row is
   zeroed in the same pass);
3. one program per row sorts its candidates (packed value + id keys, ties to the lower id), takes top-k, computes
   softmax(x / T) over them, top-p (smallest prefix with mass >= p), renormalizes, writes q, and draws X by the same
   exponential race restricted to the kept ids (exponentials from torch's CUDA generator, so CUDA-graph replays draw
   fresh numbers).

Exactness does not rest on this matching the old q: rejection sampling is exact for any q that X is drawn from and
that the verify sees, and this returns exactly that q. For top-k <= 32 it is the same truncation as before (checked:
same support, max |dq| 7e-7). A top-k above 32 (or none) gives a draft q over the top 32 ids: still exact, the target
decides; the ARC harness uses top-k 20 / top-p 0.95 / T 0.6.

Switches (server env): `SGLANG_KDSAMP=0` (the rs path), `SGLANG_KDSAMP_CH` (chunk, 1024), `SGLANG_KDSAMP_CAP` (512).

## Checked (run daniel-bench-kdcchk-1004, `check_kdsamp.py`)

- q vs the rs path: ARC settings, greedy, top-k 5 / top-p 0.5, mixed rows, int64 top-k: same support, max |dq| <= 7.5e-7.
- Draws: 409,600 draws chi-square z = -0.67, none outside the support; topk_p == q[X] exactly.
- CUDA graph: replay equals eager q, draws vary between replays.
- Candidates per row (synthetic drafter-like logits): mean 44, max 60 at chunk 1024, cap 512 never hit.
- Time per call (CUDA graph, V 65536): 1 row 114 -> 11 us; 10 rows 126 -> 12.8 us; 13 rows 131 -> 13.6 us.

Expected: -0.11 ms per draft step (= per extra position) plus -0.11 ms per iteration for the draft-extend draw.

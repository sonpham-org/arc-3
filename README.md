# ARC-3 Duck Harness Lab

A working fork of [Tufa Labs' ARC-AGI-3 Duck Harness](https://www.kaggle.com/code/jeroencottaar/tufa-labs-duck-harness-june-30-milestone-winner)
(June 30 milestone winner), instrumented for local (DGX Spark) and GCP spot (RTX PRO 6000)
experiments, plus the full logs of every benchmark run and a static log-review site.

## Log review site

The GitHub Pages site for this repo is the run inspector: pick a run, pick a game, scrub
through every board state and read the agent's full decision trace per turn. Static data
from finished runs only — no live streaming.

## Runs included (logs/ + docs/data/)

| Run | Hardware | Config | Avg score | Levels |
|---|---|---|---|---|
| `a424-study-ft09` | GB10 | single-game deep study (partial) | — | — |
| `a424-control-25game` | GB10 | fixes, 32k, no thinking | 0.232 | 2 |
| `a424-think3x-uncapped` | GB10 | thinking uncapped, 3x clock — pathology exhibit | 0.000 | 0 |
| `g4-v1-fullstack-32k` | RTX PRO 6000 spot | full modified stack, 32k | 0.297 | 3 |
| `g4-v2-ledger-64k` | RTX PRO 6000 spot | + two-tier ledger, 64k | 0.244 | 4 |

Reference points: Tufa's public-set score with this harness is **1.6002**; their
semi-private milestone score was 1.21.

## The reproduction matrix (all on spot RTX PRO 6000, Tufa tempo, pristine agent)

| Run | Server | Weights | Spec decode | Avg score | Tokens |
|---|---|---|---|---|---|
| tufa-exact (rung 0) | vLLM 0.19 (their wheelhouse) | vrfai | no | **0.679** | 1.46M |
| rung 1c | vLLM 0.25 | official Qwen FP8 | yes | **0.644** | 676k |
| rung 1b | vLLM 0.25 | vrfai | no | 0.306 | 425k |
| rung 1 | vLLM 0.25 | vrfai | yes | 0.000 | 98k |

Findings: the vrfai compressed-tensors quant hits a pathological kernel path on vLLM
0.25 (3.4x slower than 0.19; ngram spec decode amplifies it to unusable), while
spec decode + official weights is statistically tied with the pristine stack. Separately,
our agent-side modifications (required ledger, outline renders, 900s yield) cost ~2.2x
on identical serving (0.644 pristine vs 0.297 modified) -- the tempo regime (60s yield,
act-look-act) dominates everything else at this model scale.

Log review site: **https://arc3.sonpham.net** (also in [sonpham-org/arc3](https://github.com/sonpham-org/arc3)).

Big raw request logs (`*_requests.jsonl`, multi-GB for thinking runs) live in
`gs://cellens-ai-artifacts/arc3-duck/` rather than git; a424-run request logs are included
gzipped.

## Layout

- `ARC3-Inference/`, `tufa-arc-agi-framework/` — the harness (upstream + our changes; see git log)
- `gcp/` — spot-safe GCP launch kit: restartable runs, GCS log sync, crash-loop guards
- `logs/` — complete artifacts of finished runs (transcripts, prompts, events, benchmark.json)
- `docs/` — the static log-review site (GitHub Pages)
- `kaggle/` — the exact upstream notebook + its launch metadata
- Commit `a2dddac` is pristine upstream; every divergence since is one reviewed commit.

Upstream harness by Tufa Labs (Harold Bessis, Jeroen Cottaar, Isaiah Pressman, Andries
Smit, Michal Tesnar, Stefano Viel), MIT-licensed. Competition environment files are not
redistributed here.

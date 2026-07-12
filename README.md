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
semi-private milestone score was 1.21. The `tufa-exact` reproduction run (their pristine
code, their vrfai quant, their pinned vllm 0.19 stack, on the same GPU) is in flight and
will be added when it finishes.

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

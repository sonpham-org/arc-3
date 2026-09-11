# FlashNext harness: machine-switch handoff

**Updated: 2026-09-11 00:13 UTC (September 10 evening, New York).**

The user is switching machines. This is a compact handoff, not a complete local
workspace backup or a production deployment. Start here and read
[ACTIVE_RUNS.json](ACTIVE_RUNS.json) for exact VM/config/source identities and
content-addressed recovery objects. The longer project history is in
[CONVERSATION_LOG.md](CONVERSATION_LOG.md).

## What to do next

1. Check the THREE existing 132-minute repeats below, without launching anything.
2. Report fresh score, elapsed GAMEPLAY minutes, actions and completed levels.
   Confirm actual installed prompt/config receipts, not just a running VM.
3. Check whether the minimal ordinary retry was used in real play. Missing uploaded
   events do not prove zero retries. At completion, compare each repeat with its
   own original result and verify its exact VM is off.
4. The user is considering re-submitting the verified Kaggle v3. They have NOT
   authorized another submission. Do not submit, rebuild or replace it without
   a fresh explicit instruction.
5. 264-minute experiments are ON HOLD until the user explicitly revisits them.
   All three recent 264-minute VMs already completed and are off. Do not extend
   the current repeats, start another arm, or restart old jobs.

The user corrected “double up”: exactly ONE additional run, two total per idea.
All three repeat allocations have happened. There is no remaining allocation,
replacement or extra-control authorization. Preserve original insertion intents,
source/config hashes and historical failed attempts.

## Current scores: snapshots, not finals

All three exact VMs were RUNNING at 00:13 UTC, with installed config/prompt gates
passed, real actions, zero observer read errors and no health warnings.

| Repeat | Sample UTC | Gameplay min | All-25 mean score | Actions | Levels |
|---|---|---:|---:|---:|---:|
| Strategy-reminder removal | 00:11:14 | 21 | 4.9720116618 | 579 | 18 |
| MOUSE-reminder removal | 00:12:28 | 24 | 2.4905825968 | 712 | 13 |
| Minimal retry coaching | 00:12:44 | 24 | 2.1743809152 | 584 | 12 |

Only seven games are reporting in these early samples; the denominator is still
all 25. These are not Kaggle scores or linear forecasts. Startup is excluded
from the gameplay budget. Earlier snapshot differences do not prove superiority.
The historical observer `wins` field has a WIN/won naming mismatch: do not claim
no games were won merely because that field is zero; score/levels are separate.

### Exact run identities

Project **cellensml**, zone **us-east4-c** for all three:

| Arm | Run | VM | Exact instance ID |
|---|---|---|---|
| Strategy | g4run-strategyrep132-w7-20260910-0cd4d8cb42 | arc3-g4-strategyrep132-0cd4d8cb42 | 1769178353154031625 |
| MOUSE | g4run-mouserep132-w7-20260910-7b863d2e3e | arc3-g4-mouserep132-7b863d2e3e | 4148461476313465337 |
| Minimal retry | g4run-minretryrep132-w7-20260910-9a269274de | arc3-g4-minretryrep132-9a269274de | 6712035830758539718 |

Their first actual gameplay was already reported to the user. Do not announce
that milestone again. Ordinary retry adoption in this repeat remains unobserved
as of the last dedicated event read at September 10 23:56 UTC.

## Exact recipes and the actual removals

Shared: RadixArk/Qwen3.8-Flash-Next-NVFP4 revision
`7b719225242aacd3dbd3f9407468c2ee9a9d2594`, NVFP4/native CPU FP8 PLE/FP8 KV,
W7 (seven lanes), 102985 context / 94281 input tokens per lane, full-history
trimming, action cap14, 108k advisory GENERATED-token target per game. All25 local
games, **132 gameplay minutes after startup**, **2061 seconds per game**, Spot,
14400-second hard VM guard and automatic stop. Do not change these live runs.

Every repeat keeps transition removal ON. It removes only the repeated later-turn
sentence: “Inspect the newest transition in Python and distinguish gameplay
change from HUD-only change.” It does not remove observations or the game state.

- Strategy arm additionally removes the repeated “Use compact inspection/search
  code, revise the carried world model in brief assistant text when needed, then
  execute the shortest reliable valid action or batch via `action(actions)`.”
  Terminal and MOUSE rules remain.
- MOUSE arm instead removes only the repeated “If you use MOUSE, include integer
  row and col arguments.” System/tool coordinate rules and parser remain.
- Minimal-retry arm instead replaces ordinary no-tool-call coaching with:
  **“No tool call was executed in your last response. Continue using the `python` tool.”**
  Malformed-markup repair stays unchanged. Strategy/MOUSE removals remain OFF.

No search/scorer removal, time-only guidance, summary, coarse swap, new symbolic
tool or composed segmentation is enabled in these three. They are unchanged
replications of their respective originals, not combined treatments. 188 local
checks passed; 21 unique cloud objects were downloaded and byte-verified before
allocation. Installed runtime receipts and real gameplay were then checked too.

## Read-only recovery on another machine

The VMs run independently of this PC. A local Codex heartbeat does NOT migrate
automatically with a Git checkout. Use the new machine's already-authorized GCP
identity; do not copy tokens or credentials into Git. If authorization is missing,
ask the user to connect their account. No service-account key is supplied here.

`ACTIVE_RUNS.json` contains each artifact prefix, pinned config, source hash and
every small uploaded source/selftest/probe/config object with SHA256 and size.
The exact player code is recoverable from its `candidate.tgz`; it is not lost
when the original Windows workspace is unavailable. Download only needed code
objects and verify their SHA256 before using them. Do not execute historical
launch scripts or erase insertion records to “resume” an already running job.

Example read-only commands, substituting the exact run/VM from the table:

```sh
gcloud compute instances describe arc3-g4-minretryrep132-9a269274de --project=cellensml --zone=us-east4-c --format='json(id,status,lastStartTimestamp)'
gcloud storage cat gs://cellens-ai-artifacts/arc3-duck/g4run-minretryrep132-w7-20260910-9a269274de/runs/score-observer/score-latest.json
gcloud storage cat gs://cellens-ai-artifacts/arc3-duck/g4run-minretryrep132-w7-20260910-9a269274de/config-audit/CONFIG_RUNTIME_RECEIPT.json
gcloud storage cat gs://cellens-ai-artifacts/arc3-duck/g4run-minretryrep132-w7-20260910-9a269274de/config-audit/PROMPT_RUNTIME_RECEIPT.json
```

Also inspect `runs/score-observer/score-final.json`, `DONE`, `FAILED` and
`HARD_TIMEOUT` under each run prefix. Missing final/DONE during play is normal.
Final resolution requires a terminal result and confirmation that the exact VM
is TERMINATED, not merely a finished upload. Observer timing can include a few
seconds of finalization beyond the nominal budget.

Retry event sidecars are under `runs/artifacts/*_retry_events.jsonl`. Read at most
25 files, max2MiB each; distinguish ordinary vs malformed, issued/requested/
answered retries, parsed Python calls and actual gameplay dispatches. Verify the
ordinary prompt hash against the exact minimal text above. Ignore an incomplete
last JSONL line. Parsed Python does not prove tool success or a gameplay action.
Never manufacture a retry to exercise the feature.

Use small uploaded diagnostics/Compute metadata, not SSH or serving/gameplay
endpoints for scores. A replaced mutable GCS generation can produce a transient
404: one fresh-metadata retry is enough. Flag stale observers after6minutes,
no action progress after10minutes or startup without gameplay after30minutes.
Do not declare failure solely from unavailable monitoring.

## Completed comparisons (all-25 local means)

These are the historical values used in this conversation, NOT ex-ft09 scores.
The repository prefers ex-ft09 analysis; recompute that separately from original
per-game data rather than relabelling these numbers. The public25 are a small,
non-representative development set, not evidence of hidden-game generalization.

| 132-minute recipe | Final score(s) | Mean when repeated |
|---|---|---|
| Transition removal | 17.3159629162,13.8540014155 | 15.5849821659 |
| + Minimal retry (first) | 17.1546050675;57levels;2878actions | Repeat running |
| + MOUSE removal (first) | 16.5312606620;54levels;3286actions | Repeat running |
| + Strategy removal (first) | 14.9099822095;56levels;2932actions | Repeat running |
| Search/scorer removal ALONE | 14.2694602346,15.2056160535 | 14.7375381441 |
| Transition +50% retention swap, no summary | 16.8165614690,14.3099238424 | 15.5632426557 |
| Transition +30% retained | 12.5624688980 | — |
| Transition +70% retained | 14.1336609759 | — |
| Transition + search/scorer removal | 11.1620480991 | — |
| Transition + half-context summary | 10.2919711129 | — |
| Coordinate restriction removed | 12.9839928769 | — |
| Segmentation preference removed | 10.6283783717 | — |
| Planning routine removed | 10.4103775595 | — |
| Background/edge heuristics removed | 9.2535622469 | — |

264-minute transition originals:18.3301716524 and16.1893426696(mean17.2597571610).
Time-only guidance264 finished19.5886122696,62levels,5908actions. All are complete,
off and already reported. They use different per-game budgets from132m; do not
use their suite-minute132 snapshot as a matched132m run. User paused this line.

Original minimal retry really was exercised:47ordinary responses,47contained
parsed Python,0next no-tool,0malformed,13gameplay dispatches,0request errors;
512.251847693seconds summed retry inference,11581completion tokens. That verifies
treatment use, not causal improvement. Its final/off/adoption were reported.

## Kaggle: ready existing candidate, no new submission permission

[PLE Prefetch Pilot v3](https://www.kaggle.com/code/sonphamorg/arc3-flash-next-ple-prefetch-pilot?scriptVersionId=348690284)
is **transition removal + CPU PLE prefetch**. It does NOT include the newer
strategy/MOUSE/minimal-retry removals, time-only guidance or half-context swap.
Kernel133779628,version3,scriptVersion348690284,submission56143530,COMPLETE,
**publicScore5.44**. The original submission was external/user-made, not made by
this agent. Live exact version/source match was reconfirmed23:55UTC September10.

Notebook SHA256:
`7be5155f94caee2319da9248f87cbb404079f3d16532ed2809d0d4bc3c42d514`.
Source config:a506f655fc9441b513f48da1c383a76492d5a8b53fcf32b3a0a40fcc8fcd4e53.
Outer launch config:8cdd99c8c0ce5b0e1ece01d108e1629ac4773a90476dde103b01bfc1cb6cde1d.

Readiness passed on exactv3:22m40startup,15m07post-startup gameplay,441actions
across7lanes; prefetch completed without errors; serving descendants exited
BEFORE disposable runtime removal; nonempty valid-schema `submission.parquet`
listed as a SEPARATE Kaggle output. COMPLETE alone is not readiness. The private
offline parquet is a placeholder, NOT a file to upload as scored predictions.
Kaggle uses preconverted BF16 CPU PLE, unlike native FP8 in GCP. Keep gateway
keepalive, all110 live competition games,9h total cap, cleanup and source identity.

The user said they are inclined to retry this version, but only asked for
confirmation. **Do not treat that as a fresh submission instruction.**

## Publication backfill: unfinished and LOCAL worker is no longer running

At00:14UTC September11 the local status check found **68verified,28blocked,
128pending;workers_alive=false;batch_paused=null**. The reason the worker ended
has not been diagnosed. Do not claim the backfill completed or silently restart.
The earlier recent19 subset was already reconciled. Original inventory545:
161directly published+123renamed matches,224completed missing,37incomplete.
Of224missing,196have pinned model identity;28blocked identities must not be guessed.

Source archives remain in `gs://cellens-ai-artifacts/arc3-duck/`; published originals
are on [arc3.sonpham.net](https://arc3.sonpham.net/internal.html). A continuation on
another machine must reconcile the live catalog and immutable source manifests
before any retry, avoiding duplicates. Keep full trace downloads off small disks.
Do not upload partial active runs as finals. Transfer receipt migration is NOT
included in this compact handoff. Obtain the old local state or reconstruct it
read-only from the catalog/GCS, then obtain direction before resuming uploads.

## Original local locations (for retrieval, not portable dependencies)

- Main workspace:`C:/Users/celle/Documents/Codex/2026-09-06/okay-bro-let-s-do-the`.
- Supporting Astra workspace:`C:/Users/celle/Documents/Codex/2026-09-04/alright-astra-take-a-look-at`.
- Current repeat owner:`work/reminder-repeats-132-20260910`.
- Groups:`work/repeated-guidance-repeat132-20260910`, `work/retry-coaching-repeat132-20260910`.
- Kaggle evidence:`work/kaggle-ple-prefetch-v3-9h-20260910`.
- Publication code:`work/publish-missing-runs-20260910`;state:
  `D:/codex-work/missing-run-publication-20260910` (keep originals/VERIFIED receipts).
- Local heartbeat:`monitor-repaired-prompt-ablations`,every5min,same Codex task
  `01a076cb-d590-77d1-8289-274b7d6bd3d2`. It is read-only, monitors the3repeats and
  publication, and stays quiet for healthy progress. Do not assume it runs on the
  new machine or create overlapping launch/upload workers. New monitoring should
  notify only material failure, actual retry adoption, final result/off or required
  decisions; first gameplay for all3 was already reported.

The abandoned full-workspace exporter was stopped after the user's clarification.
No full archive was exported or pushed, and no production code was changed.
This handoff plus its content-addressed cloud recovery pointers is the deliverable.

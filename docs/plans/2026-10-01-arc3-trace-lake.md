<!--
Author: Claude Opus 5.5, for Son Pham
Date: 1-October-2026
PURPOSE: Design for one durable store of every ARC-3 trace we generate (scored runs, RL tries, replays, human and
teacher paths) so any future training (SFT, expert iteration, GRPO, DPO, per-turn values, a new base model) can reuse
them without re-playing. Son asked 1-Oct: "Have you planned our infrastructure, so that the training can be reused
somehow? ... take advantage of GCS and Firestore". Layout, the canonical episode format, the Firestore index, who
writes what, costs, build order. Nothing here is built yet beyond the RL tree (rl_tree.py) and the G0 records.
SRP/DRY check: Pass. The RL loop and its tree are docs/plans/2026-10-01-rl-on-burst-games.md §6 (rl_moments / rl_tries
/ rl_groups / rl_rounds stay as they are and link into this store). The annotated decision-step corpus
(datasets/decision-steps/) is an eval set with its own schema; it can be derived from this store, not replaced by it.
Run scores stay in Firestore arc3_runs (gcp/arc3_firestore_scores.py).
-->

# ARC-3 trace lake: store every trace once, reuse it for any training

**Status:** design, 1-Oct-2026. Not built.

## 0. The short version

- **Every game played lands in one place,** in one format, with enough detail to retrain on it later under a
  different method, a different harness prompt or even a different base model, without playing it again.
- **GCS holds the traces, Firestore holds the index,** the same split as the run scores and the RL tree.
- **Each trace records who played it (model build), where (harness version), on what (game version) and how
  (scored run, RL try, replay, human, teacher).** That is what makes an old trace safe to reuse: filter by it.
- **Forks never copy their past:** a try stores where it forked from plus its own turns, so 8 tries of a 100k-token
  moment cost 8 short suffixes, not 8 full histories.
- **Text and images, not only token ids:** messages are stored in the chat format the harness sent, so a new tokenizer
  or a new base model can re-render them. Token ids and log-probs are stored too when the server gives them (needed for
  RL ratios on the same model).
- **Training sets are manifests** (which traces, which turns, which weights, which filter, which code), and every
  adapter records its manifest. Any adapter can be rebuilt, compared or rolled back; any dataset re-made.

## 1. What exists today

| what | where | reusable as is? |
|---|---|---|
| raw run output (transcripts, events, viewer data; request logs only when on) | `gs://cellens-ai-artifacts/arc3-duck/<run>/...`, ~1,000 runs (857 full 25-game runs counted 28-Sep) | raw yes; no exact prompts for our runs (request logs off) |
| run scores | Firestore `arc3_runs` | per game only, not per level |
| RL tree (moments) | Firestore `rl_moments` (254, campaign rl-1001a) | yes, but provenance is thin (harness name, policy "base") |
| round-0 records | `gs://.../arc3-rl/rl-1001a/g0/<run>/records/` | yes for this model; full message list per stretch (no dedupe) |
| site runs | Railway Postgres behind arc3.sonpham.net | published runs only |

Gaps: model/harness/game versions on every record; per-level index across all runs; prefix and image dedupe; exact
prompts for our runs; dataset and adapter lineage; labels.

## 2. Layout (GCS, us-central1, next to the bucket we already use)

```
gs://cellens-ai-artifacts/arc3-lake/v1/
  blobs/<sha256[:2]>/<sha256>.png          frames and images, stored once (level starts repeat across every run)
  episodes/<source>/<yyyymmdd>/<episode_id>.jsonl.gz   one per game played (scored_run, rl_try, replay, human, teacher)
  datasets/<dataset_id>/spec.json + manifest.jsonl.gz + stats.json
  policies/<policy_id>/POLICY.json + adapter/ + merge reports
  exports/firestore/<date>/                 periodic index export (optional BigQuery)
```

Raw run output stays where it is and immutable; episodes point back to it.

## 3. The canonical episode (one gzipped JSONL per game played)

**Header line**
- `schema_version`, `episode_id`
- `source`: kind (`scored_run` | `rl_try` | `replay` | `human` | `teacher`), run id / try id / recording guid
- `game`: id (e.g. `sp80-589a99af`) and version (source sha for community games, which the cron rewrites)
- `harness`: id = hash of (bundle sha, knob set), plus the render profile that reproduces exact prompts
  (e.g. `sglang-0.5.19`, measured 1-Oct)
- `policy`: id = hash of (base checkpoint, expert cut, repair net, draft, adapter, temperature/top-p/top-k)
- `parent`: episode id + turn, for forks (the replayed past is not copied)
- `teacher`: `none` | `gemini-3.8-flash` | `human` | ... (so teacher-derived data can be filtered out wholesale)
- `fenced`: true for the test five and as66 (never trained)

**One line per model call**
- turn, request index, action number and level at the start
- `msgs_delta`: the messages appended since the previous call (previous reply, tool results, the new user prompt),
  images replaced by blob hashes; a full message list only where the context was rebuilt (compaction, half-swap)
- `reply`: reasoning, content, tool calls; `usage`; finish reason; latency
- actions executed, frame blob hash after each, level events
- optional: prompt/completion token ids and log-probs (when the server logs them), routed experts (sampled)

**Footer line:** per level cleared / actions / level score, game score, tokens, wall time.

Everything training needs is a pure function of this: round-0 records, expert-iteration records, GRPO groups, DPO
pairs, per-turn values, the decision-step eval set.

## 4. Firestore index (database `ai-namespace`)

| collection | one doc per | answers |
|---|---|---|
| `lake_episodes` | game played | "all giant-harness episodes of sp80 since 1-Oct", URIs |
| `lake_levels` | episode x level | "every win of ls20 L3 within 1.5x human moves", the frontier map for any subset |
| `rl_moments`, `rl_tries`, `rl_groups`, `rl_rounds` | (exist) | the RL tree; tries link to their episode |
| `lake_policies` | model build or adapter | lineage: parent policy, dataset, training config, eval runs |
| `lake_harnesses` | harness version | bundle sha, knobs, render profile, date |
| `lake_datasets` | training set | filter spec, manifest URI, counts, code sha |
| `lake_labels` | human or judge label | "luck" flags, ratings, notes, attached to an episode/level/turn |

Small documents only (Firestore caps a document at 1 MiB); payloads stay in GCS.

## 5. Who writes

| writer | when | what |
|---|---|---|
| scored-run VMs | at run end | episodes + index, from request logs (needs save_request_logs on; asked the Main thread 1-Oct) |
| RL try runner | per try | the try's suffix episode + `rl_tries` |
| replay job (CPU) | backfill | exact prompts for old runs: replays recorded replies through the real harness without a model |
| trainer | per round | dataset manifest + policy (adapter) with lineage |
| people / judges | any time | labels |

## 6. Cost

Text is small and images repeat. Rough sizes: ~1-2 MB per game episode after image dedupe, ~0.2 MB per RL try (suffix
only). 25,000 historical game episodes ~25-50 GB; 10,000 tries ~2 GB. GCS standard ~$0.02 per GB-month, so about a dollar
a month. Firestore: ~25k episode + ~100k level documents to backfill, well under a dollar of writes. The cost is the
replay CPU time for exact prompts (a few CPU-hours for the giant runs).

## 7. Build order

| step | what | needs |
|---|---|---|
| A | schema + writer/reader library + tests; convert the 220 round-0 records into episodes | CPU, ~half a day |
| B | per-level index of every historical run from viewer data (no prompts needed) | CPU VM, ~1 h |
| C | replay backfill: exact prompts for the giant runs (and any run we will train on) | CPU VM, a few hours |
| D | the RL try runner writes episodes | with the runner port |
| E | trainer reads manifests; adapters registered as policies | with step 1 of the RL plan |
| F | optional: Firestore export to BigQuery for SQL over everything | later |

## 8. Not verified

- That replay reproduces exact prompts for every historical run (verified on 3 games of our 336 arm, 30-Sep; the
  giant adds the Daniel-subset knobs).
- That our golden SGLang image needs the same render profile as Daniel's 0.5.19 build.
- Sizes above are estimates from one run's logs.

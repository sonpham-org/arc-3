<!--
Author: Claude Opus 5 (Bubba)
Date: 17-September-2026
PURPOSE: Explain what the vendor-coherence corpus is, why it is NOT the decision-step corpus,
and which tool writes each path. Exists because the two corpora come off the same API endpoint
and were confused once already.
SRP/DRY check: Pass — datasets/decision-steps/README.md documents the raw corpus; this file
documents only the compact one and states the boundary between them.
-->

# Vendor-agent coherence corpus

Compact per-step records for **public vendor-agent replays** — the runs ARC publishes for
gpt-6-astra, gpt-5-6 and its variants, claude-opus-5, grok-4-5/4-6. Built to answer one
question: how much of an agent's reasoning does its harness actually retain, per action.

Everything here is re-pullable from the public API with unauthenticated `GET`. Nothing in this
directory is committed except this README.

## This is not the decision-step corpus

Both come from `GET /api/recordings/<game_id>/<guid>`. They keep opposite halves of it.

| | `datasets/decision-steps/v0/recordings/` | `datasets/vendor-coherence/replays/` |
|---|---|---|
| Written by | `tools/replay_scrape.py` | `tools/harvest_replays.py` |
| Layout | `<game_id>/<guid>.ndjson` | `<vendor-config>/<guid>__<game_id>.jsonl` |
| Frames | kept, byte-for-byte | dropped, replaced by an `fhash` fingerprint |
| Size | 70–140 MB per recording | ~1–2 MB per session |
| Contract | `datasets/decision-steps/SCHEMA.md`, enforced by `validate.py` | this README |

Do not point `validate.py` at this tree — the records are a different shape and it will
correctly reject them. Do not move these files under `v0/recordings/` for the same reason.

## Layout

```
replays/<vendor-config>/<guid>__<game_id>.jsonl   one record per step, frames stripped
replays/<vendor-config>/<guid>.meta.json          the /api/sessions document for that run
reasoning/                                        reasoning-only distillation + per-run index
samples/                                          a handful of RAW recordings, kept for
                                                  fidelity-checking the stripper
```

## Pipeline

```bash
python3.13 tools/harvest_replays.py          # fetch + strip  -> replays/
python3.13 tools/distill_reasoning.py        # keep only reasoning-bearing steps -> reasoning/
python3.13 tools/analyze_coherence.py        # per-config rates, straight off replays/
python3.13 tools/coherence_on_corpus.py      # continuity stats, off the distillation only
```

## The one number people get wrong

`summary_rate` — the share of actions carrying reasoning-summary text — is a property of the
**harness adapter**, not of the model. A provider-adapter config can report 0.0% summary while
spending 100% reasoning tokens, and an Anthropic-style adapter carries its working memory in
the visible `output` field instead. `analyze_coherence.py` reports summary / reasoning-token /
prose rates as three separate columns for exactly this reason. Read all three or read none.

Full write-up: `docs/trace-findings/2026-09-17-vendor-replay-coherence.md`.

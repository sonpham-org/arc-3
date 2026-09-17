<!--
Author: Claude Opus 5 (sub-agent for Bubba)
Date: 2026-09-17
PURPOSE: Findings from harvesting the PUBLIC ARC Prize vendor-agent replays (unauthenticated,
GET only) and measuring per-action reasoning retention ("coherence") across vendors, harness
families, and reasoning-effort settings. Documents method, validation anchors, the corpus
inventory, and the reframe of the "Astra is 3% coherent" number.
SRP/DRY check: Pass - new analysis; tooling lives in tools/, no duplicate harvester existed.
-->

# ARC-3 public vendor replays: what "coherence" actually measures

**Status:** complete. Numbers below are from the full harvested corpus (see Inventory).
**Scope:** public vendor-agent replays only. The Boss's own scorecards are explicitly out of
scope and no authenticated request was made — every fetch was an unauthenticated `GET`.

## Headline

The "3% coherent" figure is real, reproduces exactly, and is **not a measure of the model's
reasoning.** It measures whether the harness *retained a reasoning-summary string* on each
action. Across 799 sessions that retention rate spans **0.0% to 96.8%** — and it tracks the
harness and the effort setting, not how well the agent played.

| model | summary retention | actions |
|---|---:|---:|
| grok-4.5 | **96.8%** | 16,475 |
| grok-4.6 | 5.1% | 8,439 |
| gpt-6-astra | 1.6% | 143,016 |
| gpt-5-6-sol / terra / luna | 0.0% | 89,398 |
| claude-opus-5 | 0.0% | 10,500 |

A 0% row does **not** mean the agent stopped reasoning. Three different things produce it:

1. **Reasoning moved into the visible channel.** Non-adapter configs emit full prose reasoning
   inside `output` on nearly every action. `claude-opus-5-high` is the extreme case: 0.0%
   summary retention, but **100% prose rate and a mean visible output of 1,391 characters** —
   it carries an explicit rolling working-memory block (`**Context notes (carry forward):**`)
   on every single action. It is the most legibly "coherent" agent in the corpus and scores
   zero on the summary metric.
2. **The summary was produced and discarded.** `gpt-6-astra-*-provider-adapter` emits a bare
   action token as `output` (`"ACTION6 40 33"`, mean **9 chars**) and puts reasoning in the
   separate `reasoning` field — which is populated on only 3–12% of actions even when the model
   demonstrably spent reasoning tokens on 27–96% of them.
3. **No reasoning tokens were spent — or the field simply isn't populated.** `astra-none`
   shows `rtok% = 0.0`, which is coherent: its effort setting is literally `none`.
   `claude-opus-5-high` also shows `rtok% = 0.0`, but that reading comes from
   `usage.output_tokens_details.reasoning_tokens` — an **OpenAI-shaped field** — applied to an
   Anthropic model whose own config says `high`. It may mean the Anthropic adapter never
   populates that field rather than that no thinking occurred. **Unresolved from public data.**
   Supporting signal: for Grok, `summ%` and `rtok%` track each other almost exactly
   (95.6/95.7, 97.3/97.4, 97.5/97.5) — summaries are retained essentially whenever tokens were
   spent. A flat zero on *both* fields for one vendor reads more like an unpopulated field than
   a behavioural zero.

So the Boss's 3% is the low-effort end of one OpenAI harness family. Grok-4.5 running the same
benchmark retains 96.8%. Reading the summary rate as a coherence score ranks the single most
context-carrying agent in the corpus (Claude Opus 5) dead last.

## The one clean within-family trend

Holding model and harness fixed and varying only reasoning effort, retention rises
monotonically — and the two pre-measured anchor sessions are exactly its two ends:

| effort | summ% | rtok% | actions |
|---|---:|---:|---:|
| none | 0.0% | 17.9% | 8,184 |
| low | **3.4%** | 26.6% | 7,587 |
| medium | 4.0% | 32.9% | 7,014 |
| high | 5.9% | 55.1% | 7,078 |
| xhigh | 8.9% | 70.9% | 6,810 |
| max | **11.7%** | 95.8% | 6,481 |

(`openai-gpt-6-astra-*-provider-adapter`.) Retention and reasoning-token spend move together,
but retention stays roughly 8× lower — the harness drops most summaries even at `max`.

## Three separately-labelled metrics

| metric | definition | what it actually tells you |
|---|---|---|
| `summ%` | actions with non-null `reasoning.reasoning` summary text | summary **retention** by the harness |
| `rtok%` | actions with `usage.output_tokens_details.reasoning_tokens > 0` | whether the model **spent** reasoning tokens |
| `prose%` | actions whose visible `output` exceeds a bare action token (>40 chars) | whether reasoning is carried **in the visible channel** |

`fchg%` (frame changed vs previous action) is a **diagnostic** column, computed from a frame
hash rather than retained grids. It answers "did the action do anything?" Every config
aggregates above 77%, so no harness is systematically flailing against a dead grid — though
individual sessions range from 0.5% to 100%, so it is useful for isolating stuck runs. It is
not a coherence measure and is not used in any claim above.

## Method

1. `https://arcprize.org/results` → 19 model result groups (server-rendered).
2. `https://arcprize.org/results/<group>` → session guids via `replay/<guid>` links.
3. `GET /api/sessions/<guid>` → model, runner, config, tags, `environments[].runs[].id`.
4. `GET /api/recordings/<game_id>/<guid>` → JSONL recording, **streamed and stripped**.

Raw recordings are 2–86 MB each and are **not persisted**. Each is parsed line-by-line into a
compact per-action record (step, timestamp, state, levels, available actions, full_reset,
action id + x/y, the parsed reasoning object, and a frame **fingerprint**) with the raw frame
grids dropped. Observed compaction on the largest sample: **85.8 MB → 241 KB (~356×)**.

Tooling: `tools/harvest_replays.py`, `tools/analyze_coherence.py`.
Compact corpus: `datasets/vendor-coherence/replays/<group>/<guid>__<game_id>.jsonl` + `<guid>.meta.json`
(gitignored). GET only; no game was ever started or reset.

### Integrity

Every recording is checked against the session API's own action count
(`lines == run.actions + 1`). This is what rules out truncated fetches on large unauthenticated
payloads. Compact output is written to `.tmp` and atomically renamed; a session counts as done
only when its meta records `_complete`.

### Validation anchors

Two independently pre-measured sessions were reproduced exactly before the sweep ran:

| session | game | actions | non-null summaries | rate |
|---|---|---|---|---|
| `150eaeb5-32e2-4c96-88ea-40b38638b375` | `vc33-5430563c` | 196 | 24 | 12.2% |
| `041c99f2-f842-4166-8f6b-3922da331f40` | `bp35-0a0ad940` | 510 | 17 | 3.3% |

Both are GPT-6 Astra; they are the `max` and `low` ends of the *same* provider-adapter family.

## Full results

799 unique sessions, 267,828 actions, 8 result groups. **0 integrity mismatches, 0 unparseable
reasoning payloads.**

```
config                                         sess   acts  summ%  rtok% prose%  fchg% outlen win%* bad
--------------------------------------------------------------------------------------------------------
openai-gpt-6-astra-low                           25  20599    0.0   27.1   89.7   94.8    192    16   0
openai-gpt-6-astra-none                          25  20588    0.0    0.0   92.9   93.8    164    40   0
openai-gpt-6-astra-medium                        25  18018    0.0   44.4   98.1   94.5    218    40   0
openai-gpt-6-astra-xhigh                         25  15807    0.0   99.6   99.9   96.4    190    40   0
openai-gpt-6-astra-high                          25  14034    0.0   91.8   99.2   95.0    194    44   0
openai-gpt-6-astra-max                           25  10816    0.0  100.0  100.0   95.9    242    48   0
openai-gpt-5-6-sol-max                           25  10536    0.0  100.0   99.4   97.0    123     4   0
anthropic-claude-opus-5-high                     25  10500    0.0    0.0  100.0   93.6   1391    24   0
openai-gpt-5-6-sol-high                          25   8815    0.0  100.0   98.6   94.1    117     0   0
xai-grok-4-6-xhigh                               25   8439    5.1  100.0  100.0   91.9    357     0   0
openai-gpt-6-astra-none-provider-adapter         25   8184    0.0   17.9    0.0   98.9      9    96   0
openai-gpt-5-6-sol-xhigh                         25   8061    0.0  100.0   99.0   95.1    120     0   0
openai-gpt-6-astra-low-provider-adapter          25   7587    3.4   26.6    0.0   99.6      9   100   0
openai-gpt-6-astra-high-provider-adapter         25   7078    5.9   55.1    0.0   99.6      9   100   0
openai-gpt-6-astra-medium-provider-adapter       25   7014    4.0   32.9    0.0   99.5      9   100   0
openai-gpt-6-astra-xhigh-provider-adapter        25   6810    8.9   70.9    0.0   99.6      9   100   0
openai-gpt-5-6-sol-medium                        25   6797    0.0  100.0   89.1   92.2    103     0   0
openai-gpt-5-6-terra-max                         24   6795    0.0  100.0   98.2   93.5    173     0   0
openai-gpt-5-6-terra-xhigh                       25   6755    0.0  100.0   91.3   93.5    118     0   0
openai-gpt-6-astra-max-provider-adapter          25   6481   11.7   95.8    0.0   99.8      9   100   0
xai-grok-4-5-medium                              25   5947   95.6   95.7  100.0   87.2    476     0   0
openai-gpt-5-6-sol-low                           25   5851    0.0   98.4   52.5   87.5     62     0   0
xai-grok-4-5-high                                25   5577   97.3   97.4  100.0   88.7    475     0   0
openai-gpt-5-6-terra-high                        25   5370    0.0  100.0   89.2   88.5    117     0   0
xai-grok-4-5-low                                 25   4951   97.5   97.5   99.8   82.1    322     0   0
openai-gpt-5-6-terra-medium                      25   4853    0.0   98.4   64.7   87.1     75     0   0
openai-gpt-5-6-luna-medium                       25   4451    0.0  100.0   94.9   77.3    150     0   0
openai-gpt-5-6-luna-xhigh                        25   4361    0.0  100.0   88.7   80.5    152     0   0
openai-gpt-5-6-luna-high                         25   4357    0.0  100.0   86.3   77.8    155     0   0
openai-gpt-5-6-luna-low                          25   4343    0.0   99.9   89.7   79.2    130     0   0
openai-gpt-5-6-terra-low                         25   4075    0.0   67.8   18.5   82.7     28     0   0
openai-gpt-5-6-luna-max                          25   3978    0.0  100.0   90.0   84.6    154     0   0
```

`win%` is not comparable across harness families — see Caveats.

### Adapter schemas seen

```
  [cost,output,reasoning,usage]        -> 26 configs, 224,674 actions
  [cost,output,reasoning,state,usage]  ->  6 configs,  43,154 actions
```

The split is by **harness family, not vendor**: the `state` key (which carries
`history_items_before_prune` / `after_prune`, i.e. context compaction) appears only in the six
`*-provider-adapter` configs. Claude sits in the same keyset bucket as non-adapter OpenAI runs.
Keysets are instrumented precisely so an unreadable schema can never be reported as a 0%.




## Caveats

- **`win%` is not comparable across harness families.** Every `*-provider-adapter` config reads
  100% win. That is almost certainly a publication filter on the public results page rather
  than a harness-quality effect. Unpublished sessions are invisible from an unauthenticated
  endpoint, so this is recorded as **unresolved** and no adapter-performs-better claim is made.
- **Retention is not uniform within the non-adapter family either.** Grok-4.5 retains ~97% of
  summaries across all three of its effort settings; Grok-4.6-xhigh retains 5.1%; every GPT-5.6
  variant and Claude Opus 5 retain 0%. Harness family alone does not predict retention.
- 11 of the 19 result groups publish **no ARC-3 replays at all** (verified: zero `replay/`
  links, not a scrape failure). Those groups are ARC-AGI-1/2 results only.
- `openai-gpt-5-6` is an **umbrella group** equal to the union of its luna/sol/terra variant
  groups (374 = 125+125+124). Rows are deduped on `(guid, game_id)`; `config` from the session
  API is the real discriminator.

## Inventory

| group | sessions |
|---|---:|
| openai-gpt-5-6 *(umbrella = luna+sol+terra)* | 374 |
| openai-gpt-6-astra | 300 |
| openai-gpt-5-6-luna | 125 |
| openai-gpt-5-6-sol | 125 |
| openai-gpt-5-6-terra | 124 |
| xai-grok-4-5 | 75 |
| anthropic-claude-opus-5 | 25 |
| xai-grok-4-6 | 25 |
| **unique sessions** | **799** |

1,173 run-fetches, **0 errors**. 267,828 actions. Compact corpus ≈213 MB on disk; the raw
recordings it was distilled from totalled **13.0 GB** of transient download (summed from each
run's recorded `raw_bytes`), none persisted. Free space never dropped below 105 GB — the 60 GB
guard never fired.

Of those 1,173 fetches, **374 were redundant re-downloads** of luna/sol/terra sessions via the
`openai-gpt-5-6` umbrella group, deduped away at analysis time. Anyone re-harvesting should
pull the three variant groups and skip the umbrella.

Five raw recordings were retained under `datasets/vendor-coherence/samples/` (~34 MB) for fidelity checking,
spread across vendors and harness families:

| guid | game | vendor / family |
|---|---|---|
| `02d44a10-0bee-40db-a1c2-05c2633a7bd1` | `sk48-d8078629` | gpt-6-astra |
| `04374bba-34df-4118-939b-0cfba5c1b5a7` | `m0r0-492f87ba` | gpt-6-astra |
| `086c9f8f-5a86-4582-8517-8edb90b718cd` | `wa30-ee6fef47` | claude-opus-5 (non-adapter, prose) |
| `0653efb1-2f47-49bf-a9cc-ebac9cb5ba09` | `re86-8af5384d` | grok-4.5 (97% retention) |
| `048f6957-5709-4c84-8692-b7a897f10ab3` | `vc33-5430563c` | gpt-5-6-luna |

> Note: an unrelated process (`tools/replay_scrape.py bulk --guid-file guids-human.txt`,
> started 11:38 ET by another session) writes raw *human-run* replays flat into
> `datasets/decision-steps/v0/recordings/`. Those files are not part of this corpus and were left untouched; this
> analysis reads only `datasets/vendor-coherence/replays/<group>/` subdirectories.

## Reproducing

```bash
cd ~/GitHub/arc-3/datasets/vendor-coherence
python3 tools/harvest_replays.py <group>        # resumable; skips completed sessions
python3 tools/analyze_coherence.py              # rebuilds the tables above
```

<!--
Author: Claude Opus 5 (Bubba sub-agent, arc3-lora-round4-spec)
Date: 19-September-2026
PURPOSE: Specification for ARC-3 LoRA round 4. Rounds 1-3 trained on teachers that carried
no reasoning: rounds 1/2 on the model's own traces, round 3 on the Boss's human replays
(moves only). Round 3 regressed gameplay on the held-out fence, 7 levels -> 2. This document
specifies round 4, which conditions training on the Boss's written reasoning
(`playerObservations` in arc-explainer), states a falsifiable hypothesis in round 3's own
terms, fixes gameplay as the primary metric, specifies the data builder concretely enough to
implement, and gates the whole round behind a cheap prompt-time control arm.
SRP/DRY check: Pass -- round 1 lives in docs/2026-09-17-arc3-lora-round1.md, round 2 in
docs/2026-09-19-arc3-lora-round2.md (Bubba workspace), round 3's eval in PR #59. This file is
the round-4 spec only and cites those rather than restating them. No existing spec covers
this corpus; §3 records that no branch or PR through #59 has built it.
-->

# ARC-3 LoRA round 4 — spec

**Status:** spec only. No training launched, no eval run, no GPU touched. A GPU run is a
separate approval.
**Boxes (for planning, read-only when inspected):** `gx10-a424` (`son@100.106.31.61`) for
training, `gx10-a108` for gameplay eval.
**Prior rounds:** round 1/2 — `docs/2026-09-17-arc3-lora-round1.md`,
`docs/2026-09-19-arc3-lora-round2.md`. Round 3 eval — PR #59.

---

## 1. Why round 4 exists

Rounds 1 through 3 trained on the wrong teacher, three times, and the Boss caught it rather
than we did. That is the honest framing and the rest of this document is built on it.

| round | teacher | what it carried | result |
|---|---|---|---|
| 1 / 2 | the model's own game traces | the model's existing behaviour | held-out CE −0.0173 (40/40 records). Gameplay never measured. |
| 3 | the Boss's 18 winning human replays | **moves only, no rationale** | gameplay **collapsed**: 7 levels → 2, score 20.78 → 0.71, 0/7 improved |

Round 3's diagnosis, and the premise of round 4: **the recordings carry moves only.** A
human who already knows a game moves fast. The model copied the *fast* without the *knows*.
It learned decisiveness without understanding.

That diagnosis is now quantified rather than asserted. From round 3's own
`train_report.json` on a424 (read 19-Sep-2026):

> **94,012 supervised tokens across 2,281 assistant turns — 41.2 supervised tokens per turn.**

Forty-one tokens per turn is an action call and nothing else. Round 3 spent 5.13 hours of
GB10 time teaching the model to emit tool calls it could already emit. There was no reasoning
in the supervision signal because there was no reasoning in the teacher.

### 1.1 Correcting round 3's headline: "deliberates half as long" is a derived quantity

PR #59 reports mean turn wall time 307.2s (base) vs 161.5s (adapter) and reads it as the
adapter deliberating less. The direction is right but the quantity is not free, and the spec
must not build a falsifier on it. Checked in this repo:

- Every `environment.max_steps` in `ARC3-Inference/configs/*.json` is `null` — **there is no
  action cap.** The budget is `environment.max_runtime_minutes`.
- Base: 123 turns × 307.2s = **37,785.6s**. Adapter: 234 turns × 161.5s = **37,791.0s**. Two
  independent runs, with different models and roughly 2× different turn counts, agreeing to
  **5.4 seconds out of 37,790** — 0.014%.

That equality is the evidence, and it needs no config value to stand: two runs do not land
within five seconds of each other by chance. **Both arms ran to a hard wall-clock deadline.**

A per-game budget follows as a derived figure: 37,786 ÷ 7 ÷ 60 ≈ **90 minutes per game**.
That matches the config PR #59 names, `configs/a108.qwen38.baseline.json`, which lives only in
a108's (non-git) tree and sets `max_runtime_minutes: 90`, `pinned_max_runtime_minutes_per_game:
90` and `concurrent_jobs: 7`. Both round-3 `run_config.json` files on a108 confirm
`concurrent_jobs: 7`, `game_count: 7`, `analyzer_timeout_seconds: 900` (read 19-Sep, after the
first cut of this spec). The in-tree a108 configs (`a108.qwen36.json`, `.nvfp4`, `.safe`) are
for a different model and say 20 minutes; they are not what the eval ran and are irrelevant
here. Nobody re-running the eval should use them.

**Both arms burned their full wall-clock budget.** Seconds-per-turn is therefore
`budget ÷ turns`, an identity, not an independent measurement. The real and still-damning
finding is the one underneath it:

> The adapter took **roughly twice as many turns** in the same wall clock and cleared
> **five fewer levels**. It did not think less per unit of thinking; it thought faster and
> worse, and it had *more* attempts to show for it.

The round-4 falsifier is stated in §4 in terms that are not pinned by the budget.

---

## 2. The gap — the Boss's reasoning has been on disk the whole time

`~/GitHub/arc-explainer/shared/arc3Games/` holds 26 per-game `.ts` files plus
`humanPlay.generated.json`, `gameLevels.ts`, `humanDifficulty.ts`, `slipperySeven.ts`,
`types.ts`, `index.ts`. Two of the per-game structures matter here, and they are different in
kind.

Verified against the tree on 19-Sep-2026:

- `recordings_to_sft.py` reads arc-explainer **only for run identity** — which guid cleared
  which level — via `--human-play humanPlay.generated.json`. It never opens a per-game `.ts`
  file and never reads the write-up prose.
- `extract_sft.py` and the rest of `distill/` never touch arc-explainer at all.
- The only consumer of the write-ups is `render_rulebooks.py` → `inference/agent/oracle_rules.py`,
  which is the **prompt-injection** arm, not training.

**No branch on `sonpham-org/arc-3` and no PR through #59 has built a trainer that reads the
write-ups.** This has not been tried and then abandoned; it has not been tried.

---

## 3. Corpus anatomy — measured, and two of the brief's numbers corrected

All counts below were produced by bracket-matching the `mechanicsBreakdown` and
`playerObservations` arrays in each per-game `.ts` and counting fields inside them. Counting
`category:` with a bare `grep` over the whole file overcounts by 28, because each game's
top-level metadata also has a `category` field.

### 3.1 `mechanicsBreakdown` — 297 entries. **Excluded from training.**

This is "what the game IS": rules traced to game source lines. It is the oracle rulebook by
another name. `extract_sft.py:421` deliberately fences the rulebook out of training data as
answer-key leakage, and **that fence is correct.** Round 4 does not train on rule points.

Two corrections to the task brief:

- Total is **297** ✓ (brief correct).
- "**126 level-tagged**" is **wrong**. There are **zero** `level:` fields inside
  `mechanicsBreakdown` — `MechanicPoint` has no `level` in `types.ts`. **200** of the 297
  entries sit under a `// ---- Level N ----` **comment** header. Level scoping here is a
  comment convention, not schema. Any builder that tries to filter mechanics by level
  programmatically will get nothing back from a field lookup and must parse comments. Since
  round 4 excludes mechanics entirely this does not bite us, but it would bite the next
  person.

### 3.2 `playerObservations` — 63 entries. **This is round 4's target, and it is thinner than hoped.**

Schema (`types.ts:124-141`): `player`, `date`, `level?`, `saw`, `did?`, `expected?`,
`happened`, `inCode?`.

| field | present | of 63 |
|---|---|---|
| `saw` + `happened` (required) | 63 | 100% |
| `level` | **28** | 44% |
| `did` | **22** | 35% |
| `expected` | **5** | **8%** |
| `inCode` | 18 | 29% |

**This is the single most important measurement in this document, and it cuts against the
plan.** `expected` — "what he thought would happen" — is the field that carries an actual
mental model. It exists in **5 notes of 63**. Three of those five are on non-fence games
(`cn04`, `s5i5`, `sk48`); the other two are on `tr87`, which is fenced. Restricted further to
games that have replay turns to join onto (§3.4), **`expected` survives on exactly two
notes.**

A note with only `saw` + `happened` is much closer to a statement of the mechanic than to a
line of reasoning — which is to say, it is a rule point wearing a play-note costume. That is
not a hypothetical failure mode to guard against; it is the **majority shape** of this
corpus. §6.3 specifies the detector, and it is a structural one first.

### 3.3 The fence survives — and round 3 held it by construction, with an optional flag

Held-out fence: `ar25 re86 sb26 su15 tr87 tu93 vc33`. All seven have write-up files.

Per-game `playerObservations`, measured (`*` = fenced):

```
bp35 8 | tr87 5* | sk48 5 | lf52 5 | wa30 4 | su15 4* | s5i5 4 | ls20 3 | vc33 2*
tu93 2* | sb26 2* | r11l 2 | m0r0 2 | g50t 2 | cn04 2 | ar25 2* | tn36 1 | sp80 1
sc25 1 | re86 1* | lp85 1 | ka59 1 | ft09 1 | dc22 1 | cd82 1 | as66 0
```

Totals: **63 = 18 on the fence + 45 off it.** The brief's counts are confirmed exactly.
Training on non-fence write-ups only leaves the fence intact and keeps the round-3 ↔ round-4
comparison legal.

**Did round 3 itself honour the fence?** Yes, and by construction:

1. `recordings_to_sft.py` has an `--exclude-games` flag (bare game codes to drop, applied in
   `build_records` before any record is built). It is **optional with no default**, so the
   fence is enforced only when the caller passes it.
2. Round 3's corpus was built with it. `docs/trace-findings/2026-09-18-human-demos-to-sft.md`
   §10 records the exact command, `--exclude-games vc33,ar25,sb26,re86,su15,tr87,tu93,as66`,
   and §9 there records what it did: the unfenced converter output is 130 records, and the
   fence drops exactly the 41 records on `ar25 sb26 su15 tu93 vc33`, leaving the 89 that were
   trained. (`re86` has no winning recording, `tr87`'s recording is missing, `as66` never
   appears.)
3. The corpus that was trained — 89 records — covers **12 games, none of them fenced**:
   `bp35 cd82 cn04 dc22 ft09 g50t ka59 lp85 ls20 m0r0 r11l s5i5`. **Zero fence records.**
   Confirmed against `train_report.json` on a424: `records_in: 89`, `records_trained: 89`.

**The round-3 result stands.** The residual weakness is that the flag is optional: a builder
invoked without it silently produces the 130-record unfenced corpus, and five fenced games
*do* have winning recordings. **Round 4's builder makes the fence required** (§6.4) so a
missing flag is an error rather than a leak. This is a hardening of the current tooling, not
a correction of a past error.

> Correction to the first cut of this spec, which said the converter had "no fence filter"
> and that round 3 held the fence "by luck". Both were wrong: the flag exists and was used.

### 3.4 The join — this is the number that decides the round

The proposal is to treat the notes as a **rationale source**, not a corpus: join them onto
round 3's existing replay turns by game (and level, where available), so round 4 = round 3 +
the *why*. Coverage, computed over the 89 records:

| join key | records covered | assistant turns covered |
|---|---|---|
| **game** | **89 / 89 (100%)** | **2,281 / 2,281 (100%)** |
| game + level | **10 / 89 (11%)** | 289 / 2,281 (13%) |

The game+level join matches on only five games (`bp35` 4 records, `s5i5` 3, `cn04`/`m0r0`/`r11l`
1 each), because only 11 of the 28 notes on trainable games carry a level, and those levels
frequently are not levels the Boss's winning run recorded.

**The game-scoped join is the only one with usable coverage, and it has total coverage.**
That settles the granularity question: round 4 conditions each record on a *game-scoped*
rationale block, with level-specific notes marked inline where a level tag exists.

Note what this reframes. "45 play notes is not an SFT corpus" is true if the notes are
records. They are not records. They are **12 game-scoped rationale blocks** broadcast across
89 existing records and 2,281 existing turns. The corpus size is round 3's corpus size. What
changes is what is in the context and what is supervised.

### 3.5 What is not reachable

| bucket | notes | why |
|---|---|---|
| on the 12 round-3 training games | **28** (11 level-tagged, 11 `did`, 11 `inCode`, **2 `expected`**) | usable |
| non-fence, but no replay turns exist (`as66 lf52 sc25 sk48 sp80 tn36 wa30`) | **17** | nothing to join onto |
| fenced | 18 | must not be touched |

So of the 45 non-fence notes the brief counted as available, **17 are unjoinable** under any
key, because those games have no human replay in the corpus. The workable set is **28 notes**,
and its reasoning-bearing subset is much smaller than 28.

---

## 4. Hypothesis and falsifier

**Hypothesis.** Round 3 taught the model to act like someone who already knew the game, without
teaching it what that person knew. Given the same replay turns conditioned on the Boss's
written reasoning for that game, round 4 will produce a model that reasons more per turn and
clears more levels than the round-3 adapter, and at least matches base.

**Stated against round 3's numbers.** Round 3 used ~2× the turns of base within an identical
90-min-per-game budget and cleared 2 levels to base's 7. Round 4 predicts **fewer, longer,
better turns**: reasoning tokens per turn up relative to round 3, and levels cleared up.

**Falsifier — write it down and honour it:**

> **If round 4 again produces shorter per-turn reasoning without improving clearance, the
> hypothesis is dead and the teacher is not the problem.**

Additional kill conditions, pre-registered:

- Round 4 fails to beat the **round-3 adapter** on levels cleared → rationale conditioning
  adds nothing; stop pursuing the human-demo direction.
- Round 4 beats round 3 but does not reach **base** (7 levels) → the human-demo teacher is
  net-negative regardless of rationale; stop.
- The **prompt-time control arm (§5)** matches or beats the trained arm → the information is
  usable but does not need to be trained in. **That is a real finding, not a failure**, and it
  would redirect the program toward retrieval/injection and away from LoRA entirely.

Because seconds-per-turn is pinned by the wall-clock budget (§1.1), the deliberation side of
the falsifier is measured as **reasoning tokens per assistant turn**, parsed from the traces.
That quantity is not an identity of the budget. Turns-per-game is reported alongside it.

---

## 5. Arms, and the gate that comes before all of them

### 5.1 Arm O — prompt-time rationale (control). **Run this first. It gates the round.**

The machinery already exists: `render_rulebooks.py` → `oracle_rules.py` injects per-game text
at prompt time. Pointing it at `playerObservations` instead of `mechanicsBreakdown` is a
rendering change, **no training at all**, and costs one eval pass per arm.

This is not a menu item. It is a **gate**:

> If handing the model the Boss's reasoning for free does not move gameplay, then training
> that same reasoning in is very unlikely to work.

Cost if it kills the round: ~1.5h of a108. Cost if we skip it and it would have killed the
round: a 5h train plus a ~9h eval. Run the gate.

Caveat to state plainly: arm O injects on **fenced** games, which is legitimate for
`playerObservations` (the Boss's process notes) in a way it would **not** be for
`mechanicsBreakdown` (the answer key). Any note that trips the rule-leak detector (§6.3) is
excluded from arm O as well as from training. If arm O only works with leaked rule points in
it, that is an oracle result, not a reasoning result, and must be reported as one.

### 5.2 Arm R — rationale-conditioned SFT. **The recommended primary arm.**

Round 3's 89 records, unchanged, each conditioned on a game-scoped rationale block built from
that game's `playerObservations`. 100% record coverage (§3.4). Supervision stays on the
action turns; the rationale enters as context. Variant **R+** additionally supervises a short
rationale preamble on turns whose level has a level-tagged note (10 records) — small, and
reported separately rather than mixed in.

**Recommended primary: arm R**, conditional on arm O showing any movement.

Why R over the alternatives:

| alternative | verdict |
|---|---|
| **Reasoning-only set, heavy regularization** | 28 notes, ~2 with `expected`. Not enough signal to LoRA on at any regularization strength. **Rejected on measured counts**, not on principle. |
| **LLM-expanded rationale from the notes** | Would manufacture volume from 28 notes. We would be training on a model's guess at the Boss's reasoning — the *exact* failure of rounds 1/2 (training on the model's own output) wearing a new costume, and this time laundered through the Boss's name. **Rejected.** If it is ever revisited it must be a separately-labelled arm with human review of every expansion. |
| **Prompt-time only (arm O)** | Not an alternative — it is the gate, and possibly the answer. |
| **Rationale-augmented turns (R+)** | Folded into R as a reported variant; 10 records is too few to stand alone. |

### 5.3 Honest statement of arm R's weakness

Arm R conditions 2,281 turns on 12 rationale blocks built from 28 notes, of which perhaps a
third carry real reasoning rather than restated mechanics. The rationale-to-turn ratio is
extremely low and every turn on a given game sees an identical block. There is a live risk
that the block is treated as boilerplate and contributes nothing, in which case round 4
reproduces round 3. This is stated here rather than discovered later; the arm-O gate exists
partly because it probes the same question for a fraction of the cost.

### 5.4 Arm W — full-write-up-conditioned SFT. **Launched 19-Sep, on the Boss's call.**

Added after review, not in the first cut. §3.1 excluded `mechanicsBreakdown` as "answer
key", by analogy with `extract_sft.py`'s rulebook fence. That analogy is wrong for training:
the rulebook fence exists because the oracle hands the agent the rules of *the game it is
being scored on*. Putting bp35's rules into bp35's *training* context leaks nothing into an
`ar25` eval. The real question is whether a model trained with the write-up in context can
use anything it learned once the write-up is absent at test time, and that is an empirical
question, not a leakage one. The Boss asked for the arm; it is the maximal version, so arms
R and W bracket "how much of the write-up matters".

**Data.** `ARC3-Inference/distill/writeup_to_sft.py`. Round 3's 89 records, unchanged, with
the full per-game write-up appended once to the system prompt: `simpleExplanation`,
`mechanicsExplanation`, every `mechanicsBreakdown` rule grouped by `introducedOnLevel`, and
every `playerObservation` with all fields including `inCode`. Left out: `informalName`,
`officialTitle`, `source` citations, images. `--fence` required; 0 records dropped.
Manifest: `/home/son/arc3-round4/data/sft_writeup_manifest.json`.

Measured by the trainer's own corpus pass on a424 (19-Sep 22:03 UTC):

| | round 3 | arm W |
|---|---|---|
| records / turns / images | 89 / 2,281 / 2,281 | 89 / 2,281 / 2,281 |
| supervised tokens | 94,012 | **94,012** (unchanged) |
| total tokens | 1,037,092 | 1,171,516 (+13%) |
| tokens max | 13,495 | 15,678 |
| over cap | 0 | 0 |
| write-up per game | — | 4,239–9,084 chars (cd82 … bp35) |

**Training.** Round 3's recipe with `--epochs 2 --save-every 22` (§7.2), launched from
`/home/son/arc3-round4/run_lora_round4w.sh`, log `train.log`, ledger `queue.log`, adapter
to `/home/son/arc3-round4/ckpt`. Trainer ETA 2.69h at round 3's throughput.

**Eval.** Same as §8: gameplay on the 7 fenced games with `base`, `round3` and `round4-W` as
arms, n=3, 90 min/pass at 7 lanes. The fenced games get **no** write-up at eval time. Held-out
CE is a smoke test only.

**Correction to §3.1.** `MechanicPoint` does have a level field: `introducedOnLevel`, present
on 214 of 297 entries. "Level scoping is a comment convention, not schema" was wrong; the
`// ---- Level N ----` comments and the field agree, and the builder uses the field.

---

## 6. Data-build spec

### 6.1 Location and shape

**New file:** `ARC3-Inference/distill/rationale_to_sft.py`.

Not a modification of `recordings_to_sft.py`. That file's job is recordings → SFT and it is
the artifact round 3 is reproducible from; changing it in place would make round 3
unreproducible. The new builder **consumes round 3's output** and annotates it, which also
keeps the round-3/round-4 diff to exactly one transformation.

### 6.2 Inputs / outputs

```
rationale_to_sft.py
  --corpus        scratch/sft_human_windowed.jsonl      # round 3's 89 records, verbatim
  --arc3-games    ~/GitHub/arc-explainer/shared/arc3Games/   # 26 per-game .ts
  --human-play    ~/GitHub/arc-explainer/shared/arc3Games/humanPlay.generated.json
  --fence         ar25,re86,sb26,su15,tr87,tu93,vc33    # REQUIRED, no default
  --out           scratch/sft_rationale.jsonl
  --manifest      scratch/sft_rationale_manifest.json
  --quarantine    scratch/sft_rationale_quarantine.json
```

**Join key:** `record.game_id[:4]` → per-game `.ts` basename. Verified to match for all 12
training games. Level, where present on a note, is rendered inline as a marker, not used as a
join key (§3.4).

**Parsing the `.ts`:** these are TypeScript source, not JSON. Extract the
`playerObservations: [ ... ]` array by bracket matching from the literal `playerObservations: [`
and count nesting depth — the method used for every measurement in this document. The builder
must **fail loudly** on a game whose array will not parse, never silently emit a record with
an empty rationale block. `mechanicsBreakdown` is never read.

### 6.3 Rule-point exclusion and the leaked-rule detector

Round 4 must not train on rules. `mechanicsBreakdown` is excluded wholesale by never reading
it. The harder problem is a play note that is a rule point in disguise — which §3.2 shows is
the *common* case, not the edge case.

**Stage 1 — structural (implementable, auditable, runs first).** Two different operations;
do not conflate them.

**Field-level strip — never removes a note:**

| rule | rationale |
|---|---|
| `inCode` is present (11 of the 28 trainable notes) | `inCode` is by definition "what the game source says" — it is a rule point. **Drop the field** from the rendered block. The rest of the note survives and remains eligible. Treating this as a quarantine rule would discard 11 of 28 notes and trip the abort condition below on the first run. |

**Note-level quarantine — removes the note entirely:**

| rule | rationale |
|---|---|
| `did` absent **and** `expected` absent | Nothing the player *did* or *believed*. `saw` + `happened` alone describes the mechanic, not the reasoning. **Quarantine.** |
| `saw`/`happened` text matches any `mechanicsBreakdown.text` on the same game above a similarity threshold | The note restates a rule point verbatim. **Quarantine.** Compare against mechanics **without training on them** — read-for-comparison only. |

Applying rule 2 alone to the 28 trainable notes retains the **11** with `did` plus the 2 with
`expected` (overlapping), i.e. of order **11-13 notes across 12 games**. The builder must
print this number; if it lands below ~10, arm R does not have enough teacher to be worth a
GB10 run and the round should stop at arm O. **This is a pre-registered abort condition.**

**Stage 2 — semantic (second pass, advisory).** An LLM classifier over survivors:
*"Does this describe what a player thought, or what the game does?"* Disagreements with stage 1
are written to the quarantine file for human review, **not** auto-resolved. Semantic
classification does not get to overrule the structural filter in the permissive direction.

### 6.4 Fence filter

`--fence` is **required**, with no default. The builder:

1. drops any record whose `game_id[:4]` is fenced;
2. drops any note sourced from a fenced game, even if the record is not fenced;
3. writes both counts into the manifest;
4. **exits non-zero** if either count is greater than zero *and* `--allow-fence-drop` was not
   passed, so that a fence hit is a loud event rather than a log line.

Given round 3's corpus this should drop **zero** records — there are no fence records in it.
The filter is required rather than optional because §3.3 shows the current converter only
fences when the caller remembers the flag, and five fenced games do have winning recordings.

### 6.5 Record format

Each output record is a round-3 record with one added system-adjacent block and unchanged
messages:

```json
{
  "id": "human/bp35-0a0ad940/c935ca1b/L4",
  "game_id": "bp35-0a0ad940",
  "level": 4,
  "rationale": {
    "source": "arc-explainer/shared/arc3Games/bp35.ts#playerObservations",
    "notes_used": 5,
    "notes_quarantined": 3,
    "level_tagged_for_this_level": 1,
    "text": "<rendered block>"
  },
  "messages": [ ... unchanged from round 3 ... ]
}
```

**Rendered block** — plain prose, no headers, no JSON, levels marked inline; `inCode` never
rendered:

```
How this game went for a human player:
- He saw the shaft split into branches (level 2). He stepped left or right and let the
  forced slide carry him. Which way you step decides which branch you end up in.
- On level 4, what worked earlier stopped working: this level needs you to sink, not rise.
  He floated up and explored past the edge of the starting view. His read: a human explores
  and finds it; an agent that sticks with what worked earlier probably does not.
```

The block is inserted **once per record**, appended to the system prompt, not repeated per
turn. Repeating it 17-40 times inside a windowed record would blow the sequence cap (round 3's
measured cap was 13,495 tokens) and teach position, not content.

### 6.6 Expected counts

| quantity | value | confidence |
|---|---|---|
| records in | 89 | **measured** |
| records out | 89 | **measured** (game join = 100%) |
| assistant turns | 2,281 | **measured** |
| games | 12 | **measured** |
| fence records dropped | 0 | **measured** |
| notes read (non-fence, joinable) | 28 | **measured** |
| notes surviving structural filter | ~11-13 | **derived from field counts**, not yet run |
| rationale block length | 150-400 tokens/game | **estimated**, unverified |
| added tokens per record | ~150-400 | **estimated** |
| total corpus tokens | 1,037,092 + ~13k-36k ≈ **1.05-1.07M** | **derived** from round 3's measured 1,037,092 |
| supervised tokens (arm R) | 94,012, unchanged | **measured** (supervision unchanged) |

Note the last row. Arm R changes what the model **conditions on**, not what it is
**supervised on**. Supervised signal stays at 41.2 tokens/turn. Whether conditioning alone
shifts behaviour is precisely what the round tests — and is the same doubt §5.3 raises.

---

## 7. Training spec

### 7.1 The ladder lesson is epoch-normalized, not step-absolute

Round 2's "the gain was done by step 16" is the most-cited result in this program and it is
the easiest to mis-transplant. Round 2 ran **29 records at grad_accum 2 = 14.5 optimiser
steps per epoch**, so **step 16 ≈ 1.1 epochs**. Round 3 ran **89 records = 44.5 steps per
epoch** (178 steps / 4 epochs, from `train_report.json`).

**Copying "stop at step 16" onto round 4's corpus would stop training at 0.36 epochs.** Spec
the ladder in epoch fractions:

| checkpoint | round-4 step (89 records, grad_accum 2) |
|---|---|
| 0.5 epoch | ~22 |
| 1.0 epoch | ~45 |
| 1.5 epoch | ~67 |
| **2.0 epochs — hard cap** | **~89** |

**Epoch cap: 2. Not 4.** Round 2 measured epochs 3-4 as a consistent regression (step48 vs
step32: 0/12 records improved). Round 3 ran 4 epochs anyway. Round 4 does not.

`--save-every 22` yields checkpoints at approximately each ladder rung.

### 7.2 Configuration

Unchanged from round 3 except epochs, so that round 4 vs round 3 is a clean teacher
experiment and not a hyperparameter experiment:

| | value | vs round 3 |
|---|---|---|
| base | `Qwen3.8-27B-BF16` | same |
| LoRA r / α | 16 / 32, 208 modules, 39,583,744 params | same |
| lr / schedule / seed | 1e-4 / cosine / 0 | same |
| grad_accum / batch | 2 / 1 | same |
| **epochs** | **2** | **4 → 2** |
| save_every | 22 | 24 → 22 |
| corpus | `sft_rationale.jsonl` | **the one intended change** |

**Sequence cap is the risk to watch.** Round 3's probe measured a cap of **13,495 tokens** and
dropped zero records. Adding 150-400 rationale tokens to every record pushes the longest
records toward that cap. The builder must report the post-join token distribution, and if any
record would be dropped by the cap, that must be resolved by **shortening the rationale block**,
never by dropping records — dropping records would change the corpus and break the round-3
comparison.

### 7.3 Wall clock

From round 3's measured `wall_seconds: 18462.2` (5.13h) for 4 epochs at 224.7 tok/s, plus
`load_seconds: 834.9`:

- 2 epochs on a corpus ~2-3% larger ≈ **2.7h ± 0.3h** on a424, plus ~0.25h load.
- **Estimate, derived from round 3's measured throughput.** Not verified for round 4.

---

## 8. Evaluation spec

### 8.1 Primary metric: gameplay on the 7 fenced games

**Levels cleared and total score on `ar25 re86 sb26 su15 tr87 tu93 vc33`**, same harness, same
`max_runtime_minutes: 90`, same protocol as PR #59, on a108.

### 8.2 Held-out CE is a secondary sanity check only, and here is why

CE is discredited as a proxy **by our own data**, twice:

- **Round 2:** −0.0173 CE, 40/40 records improved, t = −12.25. Gameplay never measured. A
  clean CE win that told us nothing about capability.
- **Round 3:** +0.0093 CE (39/40 worsened) — and gameplay collapsed 7 → 2. The CE sign was
  *correct* here, but it was **pre-registered as uninformative** because round 3 trained on
  human demos while the CE corpus is model traces. A metric that is uninformative whenever the
  teacher changes is useless for exactly the question this program keeps asking.

Round 4 changes the teacher again. CE will therefore again be off-distribution and again
uninformative in magnitude. It is run **only** to confirm the adapter loaded and is doing
something — a smoke test, reported as such, never as a result.

Structural limit, stated: round 2's CE eval covered **6 of the 7 fenced games**. `tr87` has no
CE records because it has zero solved levels. CE structurally cannot cover the full fence.

### 8.3 Passes per arm — n=1 is not repeated

Round 3's gameplay result was **n=1 per arm at temperature 1.0**. The direction was solid
(0/7 improved is not luck); the magnitude is unusable, and two of seven adapter games lost
40-72% of their budget to vLLM read timeouts.

**Spec: n = 3 passes per arm.** Arms: `base`, `round3`, `round4`. Including `round3` is
non-negotiable — without it we cannot tell a round-4 improvement from round-3 run-to-run
variance, which is the single largest unknown in this program.

**Wall clock — resolved against the round-3 run artifacts.**

One pass consumed **37,786s = 10.5 hours of game budget** (§1.1, measured), but the eval ran
all seven games at once: `concurrent_jobs: 7` in both round-3 `run_config.json` files and in
`a108.qwen38.baseline.json`. So one pass is **90 minutes of wall clock** (PR #59 measured
12:01→13:31 and 13:34→15:04), and:

| passes | wall clock |
|---|---|
| 1 pass, 1 arm | 1.5h |
| 3 arms × 3 passes (this spec) | **~13.5h** |
| 2 arms × 3 passes (PR #59's recommendation) | ~9h — consistent with #59 |

The first cut of this spec priced a pass at 5.25–10.5h from the in-tree a108 configs
(`concurrent_jobs` 1–2); those configs are for a different model and were not what ran.
n=3 per arm is affordable overnight. The open cost risk is not wall clock but the 900s vLLM
read timeouts (§9.4): two adapter games in #59 lost 40–72% of their budget to them at 7 lanes,
and a repeat at 7 lanes may do so again. If lanes are reduced to tame that, wall clock scales
up in proportion (4 lanes ≈ 2 passes' worth of games per 90 min → ~27h for 9 passes).

If anything has to be cut, cut **passes before cutting arms** — 2 passes × 3 arms beats
3 passes × 2 arms, because without the round-3 arm a round-4 improvement cannot be distinguished from
round-3 run-to-run variance. **Do not drop the round-3 arm.**

Reported per arm: levels cleared, total score, per-game deltas, **reasoning tokens per
assistant turn**, turns per game, tool validity, and timeout-affected games flagged and
reported both included and excluded.

### 8.4 Order of operations

1. Build `sft_rationale.jsonl`. Check the surviving-note count against §6.3's abort condition.
2. **Arm O (prompt-time) gate** — 1 pass, ~1.5h. If gameplay does not move, **stop and report.**
3. If the gate passes: train arm R, 2 epochs, ~2.7h on a424.
4. Ladder CE smoke test across rungs; pick the rung to carry forward.
5. Gameplay eval, 3 arms × 3 passes on a108.

Steps 2 through 5 each require their own approval. This document authorises none of them.

---

## 9. Not verified / open questions

1. **Whether conditioning without supervision changes anything.** Arm R adds ~150-400 context
   tokens per record and supervises the same 94,012 tokens. The mechanism by which this
   changes gameplay is a hypothesis, not a known quantity. **This is the biggest open
   question in the spec.**
2. **How many notes actually survive the structural filter.** Derived as ~11-13 from field
   counts; not run, because the builder does not exist.
3. **Round-3 run-to-run variance is completely unknown.** n=1. We do not know whether a second
   round-3 pass would clear 2 levels or 6. Every round-4 magnitude claim is hostage to this
   until §8.3's round-3 arm is run.
4. **Round 3's two timeout-affected games (`tr87`, `tu93`) were never triaged.** Cause unknown.
   They may recur in round 4 and contaminate the comparison.
5. **Resolved after the first cut: the per-game budget.** `a108.qwen38.baseline.json` on
   a108 and both round-3 `run_config.json` files were read on 19-Sep: 90 minutes per game,
   7 lanes, 900s analyzer timeout. §1.1 and §8.3 carry the corrected numbers. What is still
   not verified is whether 7 lanes is what *causes* the 900s read timeouts (item 4).
6. **Rationale block token length is an estimate** (150-400/game). Measurable only once the
   renderer exists. If it runs long, the 13,495-token cap becomes a live constraint (§7.2).
7. **`slipperySeven.ts`, `gameLevels.ts`, `humanDifficulty.ts` were not examined for
   additional reasoning content.** The brief scoped them as outcome labels for filtering and
   weighting; this spec does not use them for weighting at all, and that may be leaving signal
   on the table.
8. **Whether the fence is the right eval set for a rationale arm.** The Boss wrote notes on
   fenced games too (18 of them). Round 4 cannot train on those, but it also means the fenced
   games are ones the Boss has played and written about — they are not arbitrary held-out
   games. Not obviously a problem; not obviously not one.
9. **Arm O's legitimacy on fenced games** rests on `playerObservations` being process rather
   than answer key. §3.2 shows the majority of notes are closer to answer key than we assumed.
   If the rule-leak detector is not tight, arm O quietly becomes an oracle run.
10. **No gameplay number exists for rounds 1 or 2.** The only gameplay data points in this
    entire program are base (7 levels) and round 3 (2 levels), each n=1.

---

## 10. Summary

- Rounds 1-3 trained on teachers with no reasoning in them. Round 3's 41.2 supervised tokens
  per turn is the measurement that makes that concrete.
- The Boss's written reasoning has been on disk in arc-explainer the whole time and **no
  builder in this repo has ever read it.**
- It joins onto round 3's corpus at **100% record coverage by game**, and 11% by game+level.
  Game-scoped is the join.
- It is **much thinner than the brief assumed**: 63 notes, of which 28 are joinable and ~11-13
  survive a structural rule-leak filter. Two carry an `expected` field.
- **Recommended primary arm: R — rationale-conditioned SFT over round 3's 89 records, 2 epochs,
  gated behind the cheap prompt-time control arm O.**
- **Primary metric is gameplay on the 7 fenced games, n=3 per arm, with round 3 as an arm.**
  CE is a smoke test.
- **Falsifier:** if round 4 again produces shorter per-turn reasoning without improving
  clearance, the hypothesis is dead and the teacher is not the problem.

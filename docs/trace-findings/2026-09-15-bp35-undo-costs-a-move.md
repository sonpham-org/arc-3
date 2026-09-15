<!--
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Deep-dive on what bp35 traces actually say about ACTION7 (undo) and RESET, correcting an
earlier finding in this repo and testing the Retrodict harness's "prefer undo over RESET, never two
RESETs in a row" heuristic against measured trace data. Feeds the decision-step corpus (step 4) and
any harness prompt that coaches recovery behaviour.
SRP/DRY check: Pass - this is the only document in docs/trace-findings/ covering bp35 recovery
mechanics. It corrects, and links back to, the ACTION7 claim embedded in the labelled episode at
datasets/decision-steps/v0/episodes/bp35-...-l5-death-undo-reset-00.jsonl.
-->

# bp35: undo costs a move, RESET refunds the level

**Status:** measured. Every number below is reproduced from recordings on disk, and every source
claim cites a line in `docs/static/games/src/`.

**Recordings used:** `bp35-0a0ad940/c935ca1b-…` (1,030 rows, human, WIN 9/9) and the fifteen
January `as66-821a4dcad9c2` recordings (2 human, 13 gpt-5-nano).

---

## 1. The headline: bp35 has a per-level move budget, and undo spends from it

`Bp35.urzvqcxbsz` increments a move counter `hbqwwgceeqp` on **every** action including ACTION7
(`bp35.py:4528`), and sets it to **zero** on RESET (`bp35.py:4533`). `on_set_level` also zeroes it
(`bp35.py:4543`).

The counter is rendered as a bar on grid row 63 and is checked against a **level-dependent budget**
in `render_interface`:

| `qswcochjodb` (level number) | budget | loss check |
|---|---|---|
| 1–6 | 64 | `bp35.py:4413`, `bp35.py:4421` |
| 7–9 | 128 | `bp35.py:4436` |
| 10 | 192 | `bp35.py:4404` |

`qswcochjodb` is `_current_level_index + 1` (`bp35.py:4537`). The recording's `levels_completed`
field *is* that level index, so the chain is
`levels_completed: 8` → `_current_level_index = 8` → `qswcochjodb = 9` → budget 128.
(bp35's `win_levels` is 9, so the 192 branch is unreachable in this game and is listed for
completeness only.)

**Verified across all 1,030 rows.** Reconstructing the counter (increment per action, zero on RESET
and on level change) gives a maximum per level index of:

```
level_idx   0   1   2   3   4   5    6    7    8    9
max ctr    16  42  33  18  31  48   77  105  128    1
budget     64  64  64  64  64  64  128  128  128  192
```

Zero rows exceed budget. The counter reaches its budget **exactly twice**, and both are `GAME_OVER`:

- row **806**, `ACTION6`, counter 128
- row **936**, `ACTION7`, counter 128 — **an undo that ended the level**

That is the falsifiable prediction this whole exercise wants: the budget rule says a loss must occur
at exactly the budget and never above it, and 1,030 rows agree.

### What this means for "prefer undo over RESET"

The Retrodict harness (`ryanbbrown/Retrodict`) coaches its agent to prefer undo over RESET. On bp35
that is a real tradeoff, not free advice, and the axis its prompt does not model is the budget:

- an error costs 1 move; undoing it costs **another** move, and the counter is never refunded
- RESET costs 1 move and then zeroes the counter — it **buys back the entire level budget**
- so a mistake-plus-undo cycle burns 2 of 128, and a run that recovers by undo repeatedly can
  starve itself to death. Row 936 is that death, observed.

RESET is not strictly better: it discards level progress and the undo stack (`bp35.py:4533`,
`eubgwokpez` at `bp35.py:447`). The correct statement is that **the choice is a budget decision**,
and any harness prompt that ranks undo above RESET unconditionally is coaching against the meter
drawn on screen.

---

## 2. Correction: the empty ACTION7 rows are refusals, not undo returning nothing

An earlier claim in this repo — and the `outcome.observed` text of the labelled negative record at
`datasets/decision-steps/v0/episodes/bp35-0a0ad940__c935ca1b-…__l5-death-undo-reset-00.jsonl` —
said the engine "returned an empty frame list" when ACTION7 was pressed on a dead board, and
attributed it to ACTION7 being the one branch that does not first push an undo snapshot (the
`case GameAction.ACTION7` block at `bp35.py:4524` has no `vlyikbzinq()` call, where the six blocks
above it do at `:4496 :4501 :4506 :4511 :4516 :4521`).

**The snapshot observation is true and the attribution is wrong.** The game code cannot produce an
empty frame list: `svmaaixutx` at `bp35.py:1455` ends `… or [self.srlqyenmue().copy()]`, so it
always returns at least one grid. `eubgwokpez` at `bp35.py:1460` does the same.

The discriminating signal is in the row itself. bp35 rows carry `win_levels: 9` on 1,029 of 1,030
rows. The five ACTION7-on-a-dead-board rows carry:

```json
{"state": "GAME_OVER", "levels_completed": 0, "win_levels": 0, "frame": []}
```

`win_levels: 0` is not a game state — it is an unpopulated envelope. The action was **refused above
the game**, at the engine/API layer, and echoed back as an empty response object. It is not an undo
that executed and had no effect.

This matters for the corpus because the two readings imply different agent behaviour. "Undo executed
and did nothing" invites trying it again; "the request was refused while GAME_OVER" says the action
is unavailable in this state and the agent should change state first. The record's `observed` field
has been corrected accordingly; its `rationale` has not, because "ACTION7 pops the snapshot pushed by
the previous action" is a correct statement of what a reasonable player believed at that moment,
which is what a rationale is for.

### Decomposition of bp35's 16 `GAME_OVER` rows

- **11 real deaths** — an action that killed the board (9 in-game deaths, 2 budget exhaustion at
  exactly 128: rows 806 and 936)
- **5 refused envelopes** — ACTION7 pressed on an already-dead board (rows 215, 370, 390, 572, 807)

An earlier summary said "five times in your bp35 run," counting only the refusals. That undercounted
the deaths.

On the 11 deaths the human pressed ACTION7 first 5 times and went straight to RESET 6 times, in the
order tried / straight / straight / tried / tried / straight / tried / straight / tried / straight /
(budget). There is no learning curve in that ordering; it alternates. The counts are reported here
without a story attached to them.

---

## 3. RESET: what a second one actually does

The Retrodict prompt claims a second RESET in a row restarts from level 1. **Confirmed, and the rule
is sharper than "two in a row."**

Tested against the 302 non-initial RESET rows in the fifteen as66 recordings (the only traces on
disk where an agent mashes RESET). For each RESET: score before, score after, previous action, and
whether the previous action completed a level.

| case | count | score dropped? |
|---|---|---|
| previous action was RESET **and** score already 0 | 287 | no — nothing left to drop |
| previous action was an ordinary move mid-level | 12 | no |
| previous action was RESET, score was 1 | 2 | **yes, 1 → 0** |
| previous action **completed a level**, score was 1 | 1 | **yes, 1 → 0** |

Zero exceptions in 302 rows.

**The rule:** RESET restores the current level's start snapshot. If the board is *already* at that
snapshot — because the previous action was itself a RESET, or because the previous action just
completed a level and opened a fresh one — there is nothing to restore, and RESET escalates to a
**full game restart back to level 1**.

The source mechanism is visible in bp35 (a different game, so this is engine behaviour inferred
cross-game and observed in as66 traces): `eubgwokpez` at `bp35.py:447` opens
`if not self.unoawxnzfx: return []` — no level snapshot, empty return — and the layer above escalates.

**Retrodict's heuristic catches 2 of the 3 observed cases and misses the third.** "Never two RESETs
in a row" does not stop a single RESET issued immediately after completing a level, which is
`6fec51cb` row 4: score 0 → 1 on an ACTION2 that cleared level 1, then a single RESET, score back to
0. The correct guard is *"never RESET a board you have not yet changed,"* not *"never RESET twice."*

Caveat on that guid: `6fec51cb-…` is the same recording flagged earlier for a scorecard aggregation
discrepancy (one guid reported under two run rows, a 3-action gap). The score sequence used here is
read directly from the recording rows, not from the scorecard aggregate, but the guid is not clean
and the finding rests on it for 1 of its 3 cases.

---

## 4. The preview set had no undo

Directly confirmed. The January as66 rows carry `"available_actions": [1, 2, 3, 4, 6]` — no 7 — and
use the older row schema (`score`/`win_score` rather than `levels_completed`/`win_levels`, integer
action ids). RESET is present throughout as action id 0, 317 rows of it.

So ACTION7 was added after the preview, and RESET has always existed. Any harness rule that assumes
undo is available is assuming a post-preview build.

---

## 5. Not observed: RESET as a no-op

The source admits it — `eubgwokpez` at `bp35.py:447` returns `[]` when there is no level snapshot —
but **no instance was found in our six modern recordings**. Scanning every RESET row in bp35, cd82,
cn04, dc22, ft09 and g50t for one whose settled frame equals the prior settled frame returns nothing
in all six.

The mechanism is real in source; we have no trace of it. Stated here as unconfirmed rather than
allowed to pass as an observation.

---

## Open items this raises for step 4

1. The move budget is a *latent mechanic* of exactly the kind
   `LATENT_MECHANICS_IN_THE_PUBLIC_25.md` catalogues: a resource meter drawn on one row of the grid,
   never named, whose exhaustion is indistinguishable from an ordinary death in the trace. Worth a
   vocabulary entry.
2. Segmentation should treat a budget death and an in-game death as different `boundary_reason`
   values. Today both land on `death`, and they call for opposite corrections — one says "take a
   different route," the other says "take a shorter one."
3. Nothing here is checked against the other 24 games. The budget is a bp35 mechanic until measured
   elsewhere.

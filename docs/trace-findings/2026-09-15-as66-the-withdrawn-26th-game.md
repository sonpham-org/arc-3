<!--
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: What is retrievable for as66-821a4dcad9c2, an ARC-3 environment that is absent from
the live 25-game lineup but whose recordings still serve. Records the 15 recoverable runs, the
older recording schema they use, the two blockers on using them for the decision-step corpus,
and the one thing this game has that no other game we hold does. Written for a fresh session
and for a reviewer joining cold.
SRP/DRY check: Pass — the corpus plan and its step-4 execution plan hold the build; this holds
only the as66 finding. The reconcile rule it tests against lives in
datasets/decision-steps/README.md and is cited, not restated.
-->

# as66 — the environment that is not in the lineup

**One line:** `as66-821a4dcad9c2` is absent from the live game list and absent from the ARC
blog's 250 published replays, but `three.arcprize.org` still serves its recordings, and **15
runs on it are reachable from the Boss's own scorecards** — 2 human and 13 agent, all from
7–15 January 2026.

## 1. What was checked, and what it returned

| check | result |
|---|---|
| `GET three.arcprize.org/api/games` (authenticated) | **25 games. as66 is not among them.** |
| as66 in `datasets/decision-steps/published-replays.json` (the blog's 250) | **no** |
| `GET /api/sessions/<as66 guid>` | **200** |
| `GET /api/recordings/as66-821a4dcad9c2/<guid>` | **200** |
| source at `docs/static/games/src/as66*` | **absent** |
| `POST arcprize.org/api/leaderboards/as66` (unauthenticated, 15-Sep-2026) | **200, empty array — zero rows, while all 25 current builds return exactly 10.** Recorded in [`human-leaderboards.json`](../../datasets/decision-steps/human-leaderboards.json); an independent surface that omits as66, not an explanation of why. |

The live 25 are `ar25 bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l re86 s5i5
sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30`. as66 is a 26th id that our data has
touched and that lineup does not contain.

**Deliberately not claimed here:** *why* it is absent. Withdrawn, held back, renamed, or never
promoted past a preview are all consistent with what was observed, and nothing checked
distinguishes them. What is established is the absence and the retrievability, which is the
part that matters for the corpus.

## 2. The 15 runs

All pulled 15-Sep-2026 to `datasets/decision-steps/v0/recordings/as66-821a4dcad9c2/`
(gitignored), 28 MB total.

| kind | state | levels | actions | resets | rows | guid |
|---|---|---|---|---|---|---|
| **human** | GAME_OVER | 6 | 108 | 9 | 114 | `6fec51cb-…` |
| **human** | NOT_FINISHED | 1 | 3 | 0 | 5 | `67161f0a-…` |
| agent | GAME_OVER | 1 | 57 | 0 | 59 | `4767ea19-…` |
| agent | GAME_OVER | 1 | 35 | 0 | 37 | `5427ad54-…` |
| agent | GAME_OVER | 1 | 29 | 0 | 31 | `5f7f2805-…` |
| agent | GAME_OVER | 1 | 22 | 0 | 24 | `142a4395-…` |
| agent | NOT_FINISHED | 1 | 103 | 1 | 298 | `75928ec9-…` |
| agent | NOT_FINISHED | 1 | 101 | 1 | 199 | `4a218928-…` |
| agent | NOT_FINISHED | 1 | 89 | 1 | 91 | `f89e1d10-…` |
| agent | NOT_FINISHED | 2 | 24 | 0 | 26 | `91c763fc-…` |
| agent | NOT_FINISHED | 1 | 12 | 0 | 14 | `9d47d529-…` |
| agent | NOT_FINISHED | 1 | 8 | 0 | 10 | `52d72955-…` |
| agent | NOT_FINISHED | 1 | 5 | 0 | 7 | `3af3cead-…` |
| agent | NOT_FINISHED | 0 | 2 | 0 | 4 | `21eff675-…` |
| agent | NOT_FINISHED | 0 | 1 | 0 | 3 | `a04a1cea-…` |

Twelve of the agent runs carry `tags: ["as66-821a4dcad9c2","gold-agent","gpt-5-nano","agent"]`;
`21eff675` carries the arc-explainer playground tags. These are the same 11–12 rows that
`first-party-replays.json` excludes by design, because that file claims human play. The two
human rows are already in it.

There is no enumeration endpoint, so **15 is what is reachable from this account**, not what
exists. Other players' as66 guids are not discoverable from here.

## 3. What the game is, read off the recordings

- 64×64 grid, as everything else.
- `win_score: 9` — **nine levels to win**, where most of the public set is six or seven.
- `available_actions: [1, 2, 3, 4, 6]` — four directions and a click. **No ACTION5 and no
  ACTION7**, so this environment has no rotate and, more to the point, **no undo**. The only
  recovery from a bad state is `RESET`.
- The old rows carry `score` where current rows carry `levels_completed`; on the human run the
  score sequence is `0 1 0 1 2 3 4 5 6` — the `1 → 0` step is a level lost and retaken.

**The best human result on it is 6 of 9, and it is a loss.** Nobody in our data has won as66.

## 4. Two blockers on using this for the corpus

### (a) No game source, so no acceptance-compliant gold records

`docs/static/games/src/` has no `as66*` directory. Plan §5 step 4 requires every tier-1
record's `action_role` to cite a specific line or rule in the game source. **Without the
source, as66 cannot produce a gold record that meets acceptance** — no matter how good the
play is. This is the same constraint that governs 16 of 36 builds in
`docs/plans/2026-09-15-step4-segment-and-label-execution.md` §1(a), and here there is no
sibling build to fall back on: as66 appears under exactly one build id.

### (b) The January recordings use an older row schema

The reconcile rule in `datasets/decision-steps/README.md` —
`rows = 1 + api.actions + rows submitted while GAME_OVER` — holds on all six September
recordings and **does not hold on any of the fifteen as66 ones**. The rows differ structurally:

| | September rows | as66 January rows |
|---|---|---|
| `action_input.id` | string — `"ACTION3"`, `"RESET"` | **integer** — `0`–`6`, where `0` is RESET |
| level counter | `levels_completed` | **absent**; `score` carries it |
| `win_levels` | present | **absent**; `win_score` instead |
| row 0 | `full_reset: true` | `full_reset: false` — **no boot-reset marker** |
| last row | a normal row | **a trailing row with every field null** |

Candidate rules were tested and none covers all fifteen. `rows − null row − RESET rows`
accounts for 11 of 15 exactly and is off by one on the three agent runs that report one reset,
and off by six on the human run that reports nine. **The row-to-action mapping for this schema
is unresolved and is recorded as unresolved**, per the plan's rule that a mismatch is a
finding rather than something to smooth over.

Any future segmenter must branch on schema version. It cannot assume the September shape.

## 5. The one thing as66 has that nothing else we hold does

**It is the only environment where we have human play and a dozen agent attempts on the same
game**, and the agent is a known quantity (`gpt-5-nano`, gold-agent harness).

The comparison is stark and it is in the table above. The human reached level 6 and used 9
resets doing it. **Eleven of the thirteen agent runs never got past level 1**, and the best
reached level 2.

Two agent runs are worth a closer look by anyone studying failure modes: `4a218928` is 199
rows carrying 101 counted actions, of which **98 are RESET**, and `75928ec9` is 298 rows for
103 actions with **195 RESETs**. Those are not runs that explored and failed; they are runs
that hammered the reset key. On an environment with no undo, reset is the only recovery verb —
and the agent used it as its whole strategy.

That is a negative-tier observation the corpus would want, and blocker (a) is the only thing
standing between it and a record. **If the as66 source can be obtained, this game becomes the
single most valuable environment in the set** — matched human and agent play on a nine-level
game with no undo. Worth asking ARC for.

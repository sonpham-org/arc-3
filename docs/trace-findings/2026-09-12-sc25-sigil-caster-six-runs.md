<!--
Author: Claude Opus 5 (Bubba)
Date: 12-September-2026
PURPOSE: Trace findings for sc25-635fd71a ("Sigil Caster") across six published runs, checked
against the game source at docs/static/games/src/sc25-635fd71a/sc25.py. Records what separates
the runs that clear levels from the ones that score zero, and kills a tempting-but-wrong
explanation (system-prompt block removal) with a within-family control.
SRP/DRY check: Pass — new game, no existing sc25 doc. Sibling docs cover bp35, sk48, wa30.
-->

# sc25-635fd71a "Sigil Caster" — six runs, one wall

All figures recomputed from the published artifacts (`/data/<run>/game-16*.json`), not read off
the viewer. Mechanics cited by line number in `docs/static/games/src/sc25-635fd71a/sc25.py`.

## 1. The two runs the Boss linked

| | `sym264-w7-…b1ae6209c0` | `prompt-transition264-20260910` |
|---|---|---|
| score | **34.72** | **0.00** |
| levels cleared | 4 of 6 | 0 |
| actions | 219 | 454 (all on level 1) |
| turns | 70 | 109 |
| thinking chars | 265,135 | 235,960 |
| `def` statements | 29 | 99 |
| rune-pad toggles | 95 | **373** |
| self-inflicted GAME_OVER | 1 | **9** |

## 2. The explanation that looked obvious and is wrong

The two runs' system prompts differ by exactly one deletion — 3,692 chars, three blocks, nothing
added, and the prompt is constant across every turn of both runs (md5-checked, 70/70 and 109/109):

- **Persistent game model** — `remember(confirmed_rules, uncertainties, plan, expected_next, …)`
- **Confirmation and execution** — `ready=True`, plan cursor, host-checked execute lease
- **Confidence-gated symbolic search** — `symbolic_search(spec, …)`

Tempting story: strip the scaffolding, the agent flails. Four sibling runs kill it.

| run | prompt family | sc25 score | levels | actions |
|---|---|---|---|---|
| `sym264-w7-…b1ae` | full | 34.72 | 4 | 219 |
| `prompt-transition132-20260910` | **lean** | **28.57** | **3** | 158 |
| `sym264-w7-…f857` | full | 18.64 | 3 | 241 |
| `sym264-w11` | full | **0.00** | 0 | 366 |
| `sym264-w5` | full | **0.00** | 0 | 142 |
| `prompt-transition264-20260910` | **lean** | **0.00** | 0 | 454 |

The lean-prompt family has both a 3-level clear and a zero. The full-prompt family has a 4-level
clear and two zeros. **The prompt blocks do not explain this game's outcomes.** There is also a
build confound — the two families ran on different dates and different `artifact_run_dir` trees
(`arc3-site-action-pace-20260906` vs `missing-run-publication-20260910`) — so even a real prompt
effect could not be isolated from these six runs. Do not cite the block diff as the cause.

## 3. Ground truth from the source

- **Rune pad.** A 3×3 toggle grid at display `x ∈ {25,30,35} × y ∈ {50,55,60}` (`sc25.py:1728-1736`).
  A click flips one cell (`:2666`). Three spell patterns (`:1650-1665`):
  `tevyeq` = `XXO/OXO/OOO`, `sieesc_chwjgc` = `OXO/XOX/OXO` (diamond), `fibcey` = `OXO/OXO/OXO`.
  When the lit set exactly equals an *unlocked* pattern the spell fires and the pad clears
  (`:1925-1943`). Level 1 unlocks only `sieesc_chwjgc` (`:1390`).
- **The diamond is not a scoring action — it is grow/shrink.** `sieesc_chwjgc` dispatches to
  `xvsktydkiu()` (`:2239`, `:2089`), which toggles the player between `scale 1` and `scale 2`,
  nudging position when a grow would clip a wall (`:2115`). Movement step size follows size:
  4 cells per press at scale 2, 2 cells at scale 1 (`:2694`).
- **The win is a destination, not a cast count.** Level 1 places the player `pluyoo` at (39,19)
  at scale 2 and the goal `exydhv` at (12,17) (`:1379-1381`).
- **The budget is a toggle budget, and arrows are free.** `rrinmfkkstu` increments only on a pad
  toggle (`:2666`) and on a resolving fireball (`:1870`); exceeding `slfh` calls `lose()`
  (`:2668`). Level budgets are 50/25/50/35/65/60 (`:1389-1617`). Arrow keys never touch the
  counter. The on-screen bar is `cpllfxzbpj()` filling proportional to `rrinmfkkstu / slfh`
  (`:1853-1866`) — it is a *clicks-spent* meter, not a step timer.
- **Budget refills exist.** `enjehv-pahtoz` sprites refund 10 toggles when the player walks or
  grows into them (`:2297`, `:2726`, `cribhxjrvp = 10` at `:1630`). They appear on levels 4, 5
  and 6 (`:1498`, `:1540`, `:1593-1594`) — not level 1. No trace read here mentions them.
- **The game will demo a pattern for you.** Clicking a `sptivk-` spell icon selects it; clicking
  the already-selected icon plays back its lit cells one at a time (`:2634-2645`, `slots_to_demo`,
  rendered by `tzsjpgohez()` at `:2351`). A separate auto-demo on level entry is gated to
  `_current_level_index < 3` (`:1807`). *Not verified which branch any run triggered* — the
  winners clicked the icon region (15,4)/(26,4)/(4,4) 18 times total, the zero run 0 times, but
  select-vs-replay cannot be told apart from the published trace.

## 4. What actually separated the runs

Every one of the six found that the diamond casts. The split is what they think a cast *is*.

**The winners treat the cast as a move and then walk.** `sym264-w7` clears level 1 at turn 23
(`:step 22`): *"The marker is now adjacent to the head … One more UP would push it into the head
→ probably level complete!"* `prompt-transition132` clears it at turn 19: *"Now the key is fully
inserted! … Let me press LEFT once more to push it into the handle."* Both spend most of their
actions on arrow keys — which cost nothing.

**The zero run treats the cast as the scoring event.** Its carried world model at turn 72 is
mechanically correct and strategically inverted:

> exact diamond set = accepted → instant pad clear + plug creep … right strip = step bar
> (~1.4 rows/action → GAME_OVER → fresh level-1 reset)

Two errors compound:

1. **It priced every action against the bar.** "~1.4 rows/action" is the per-*toggle* rate applied
   to all actions, so it believed it had ~42 actions per life when in fact it had unlimited
   movement and 50 toggles.
2. **It made re-casting the objective.** 373 of its 383 clicks are pad toggles. It lost the level
   to its own toggle budget nine times, and batched the four diamond cells two and three times in
   a single `action([...])` call (turns 40, 44, 63) — after the 4th click the pad clears, so
   clicks 5-12 re-light cells and pay for the privilege.

Its own closing note: *"level 2 was never reached — the gate appears to need either far more
accepted codes than one step bar affords (~42 actions vs ~90 clicks for full plug travel)."*
It concluded the level was unwinnable under a budget it had mispriced.

**And it had already been standing on the answer.** Turn 21: *"the tip is now at cols 17-18 …
the image shows the tip adjacent to the handle."* That is the same square `prompt-transition132`
won from one LEFT press later. It went back to entering codes instead.

## 5. What this adds to the harness findings

- **Fourth game in a row** where the bar the prompt calls a distraction is the loss condition
  (bp35, sk48, wa30, sc25). Here it is worse than a distraction: mispricing it as a per-action
  timer is what made the agent conclude the level was impossible.
- **Batched actions are unsafe against toggle semantics.** Nothing in the prompt warns that a
  queued batch keeps executing after the state it was planned against has been consumed. sk48
  showed the same shape; sc25 shows it costing budget as well as progress.
- **No run distinguished "the action that changes me" from "the action that scores."** The
  winners got there by accident of exploration order, not by a stated prior.

## 6. Caveats

- n=6 runs, one game, one pass each. Family labels are two runs vs four.
- The prompt-family comparison is confounded with build date; see §2.
- `MULTIMODAL_STYLE` is not recorded in any of these traces.
- Spell-icon select-vs-replay is not distinguishable from the published artifacts (§3).

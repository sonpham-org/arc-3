# sk48 — why almost every run scores 0, and what the two that didn't had in common

**Game:** `sk48-d8078629` (8 levels)
**Read on:** 11 September 2026, from published viewer artifacts
**Runs compared:** three, all `RadixArk/Qwen3.8-Flash-Next-NVFP4@7b719225`

## The distribution first, because "randomly scores 8" is misleading

363 runs have played sk48. **324 score exactly 0.** Score on this game is nothing but
cleared-level count: 2.78 = one level, 8.33 = two levels. Only **2 of 363** runs ever
cleared two.

| | runs |
|---|---|
| 0 levels | 324 (89%) |
| 1 level | 37 |
| 2 levels | 2 |

So it is not a lucky 8 against a baseline of 0. It is a wall that 89% of attempts do not
get over, and the "8" is the only two attempts that got over it twice.

## The three runs

| | `astra-fctx-comb-w5-r4` | `sym264-w5` | `sym264-w7` |
|---|---|---|---|
| score | 8.33 | 8.33 | 0 |
| levels | 2 | 2 | 0 |
| turns | 22 | 32 | 26 |
| thinking chars | 86,325 | 165,362 | 160,586 |
| `def` statements | 8 | 49 | 38 |
| `vision.*` calls | 12 | 0 | 0 |
| prompt has `vision` / `helpers.save` | yes | **no** | **no** |
| prompt has `remember(...)` | no | yes | yes |
| run's overall average | 19.93 | 18.67 | 26.11 |

## A hypothesis that did not survive

The first two traces read (`astra-fctx` at 8.33, `sym264-w7` at 0) differ in toolset: the
winner has a `vision` library and `helpers.save()`, which persists functions across turns,
levels and context rotation. The loser has neither, and its system prompt says outright
*"Snippets are not saved, so re-import or redefine needed helpers."* It wrote 38 `def`
statements in 26 turns and never got past level 1. That looked decisive.

**It is not.** The second 8.33 run, `sym264-w5`, is the *same harness family as the
zero* — no `vision`, no `helpers.save`, same `remember(...)` game model — and it wrote
**49** `def` statements, spent **165k** characters of thinking, and cleared two levels
anyway. Redefining helpers every turn is expensive, but it is not what decides this game.

## What actually separates them

`sym264-w5` and `sym264-w7` are the controlled pair: same prompt, same toolset, same
model, same game, near-identical thinking budget spent (165k vs 160k). One cleared two
levels, the other cleared none. The difference is visible in what they were reasoning
*about*.

**`sym264-w5` abstracted the board into a small discrete state and reasoned in it.**
Turn 23, the turn before it cleared level 1:

> L0: group at 1,2,3 · RIGHT (L=1): nothing · RIGHT (L=2): push → 2,3,4 · RIGHT (L=3):
> blocked push → stays · ... LEFT (L=3): affected ≤3 → all three shift left → 0,1,2 ✓ GOAL
> Total 7 actions.

Slot indices 0–6 and a counter `L`, with an explicit transition rule ("affected = slots
≤ L−1") it then tested. By turn 25 the abstraction is written down as constants:
`NR=7; NS=7; LMAX=7; PANEL=('R','O','b','N')`.

**`sym264-w7` never left the 64×64 pixel grid.** Turn 23, at the same depth of the run:

> green at (2,24), the head at 2, tip 28, embedded ✓ ... the gap at cols 22-23 shows the
> rod, and the rod stops at 28, inside green (24-27)

Same careful mechanical reasoning, conducted entirely in raw coordinates.

Measured across each run's full thinking:

| | coordinate pairs per 1k chars |
|---|---|
| `sym264-w5` (2 levels) | **0.4** |
| `sym264-w7` (0 levels) | **1.5** |

Nearly four times the pixel-coordinate reasoning, for nothing. The winner spent its
tokens deriving a rule over seven slots; the loser spent its tokens tracking where things
were.

## Caveats

- Three traces. `n=3` cannot carry a harness decision on its own; this is a direction to
  test, not a result.
- The zero run's harness family has the **highest** overall run average of the three
  (26.11). It is not a worse harness — it loses this particular game.
- `astra-fctx` is the best family on sk48 (2 of 5 runs non-zero, mean 1.83) but that is
  five runs.
- The `astra-fctx` winner shows a *high* coordinate density (3.0/1k). Its `vision.crop`
  returns coordinates, so that figure is confounded and is not evidence against the
  abstraction reading — but it is not evidence for it either. The controlled claim rests
  on the `sym264` pair alone.
- The `astra-fctx` winner also wrote its own BFS. It was not handed pathfinding.

## What would be worth testing

Whether prompting for an explicit compact state model — name the state variables, state
the transition rule, then plan in that space — moves the 324 zeros to non-zero. The
scoring is level-quantised, so on this game the whole prize is getting over the first
wall: 324 runs moving from 0 to 2.78 is worth far more than the two runs that reached
8.33.

Note that the zero run's harness already has `remember(...)` with `symbolic_rules` and a
`symbolic_search(spec, ...)` facility for exactly this kind of declarative model, and did
not reach for either. The capability is present and unused, which makes this cheaper to
test than it looks.

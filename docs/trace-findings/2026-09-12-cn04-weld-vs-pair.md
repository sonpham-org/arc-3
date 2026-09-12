<!--
Author: Claude Opus 5 (Bubba)
Date: 12-September-2026
PURPOSE: cn04-2fe56bfb findings — the losing run calls the mechanic "welding" and the winning
run never uses the word. Welding implies permanence; the source recomputes the pairing from
scratch on every check, so the constraint is simultaneous and pairs can be un-made. Compares
g4run-astra-grid2-b476 (0.98, 1 level) against g4run-astra-fctx-meta-w11-r1 (47.62, 4 levels).
SRP/DRY check: Pass — no existing cn04 doc; siblings cover bp35, sk48, wa30, sc25, r11l.
-->

# cn04-2fe56bfb — "weld" is the wrong word, and it costs the level

## The rule, from source

`docs/static/games/src/cn04-2fe56bfb/cn04.py`.

Notches are pixels of colour **8** or **13** — two distinct types. On every evaluation
(`:925-966`) the game rebuilds three dictionaries from scratch, bucketing every notch of every
visible sprite by its **absolute grid cell** (`sprite.x + x`, `sprite.y + y`). A notch is
recorded as satisfied only when its cell holds **exactly two** notches of the *same* type:

```python
for meivkrsgum, yazvvwzuhr in rnogpwdbcy.items():   # the colour-8 bucket
    if len(yazvvwzuhr) == 2:                        # exactly two, not >= 2
        ...self.iahpylgry[sprite.name].add((x, y))
```

The win check `sjwqloivve()` (`:1000-1025`) then copies each sprite's original pixel mask,
blanks the satisfied notches, and returns False if **any** 8 or 13 survives anywhere.

Three consequences the traces never state:

1. **Nothing is stored.** `iahpylgry` is rebuilt every pass. A pair you made is only a pair
   while the pieces are still superposed — move either one and it silently un-pairs.
2. **The constraint is simultaneous, not cumulative.** Every notch on the board must be paired
   at the same instant.
3. **Exactly two.** Stacking a third notch on a satisfied cell breaks it (`len == 2`).

## "Weld" vs "coincide"

| | `astra-grid2-b476-w11-recovery-r2` | `astra-fctx-meta-w11-r1` |
|---|---|---|
| score | 0.98 | **47.62** |
| levels | 1 / 6 | **4** / 6 |
| actions per level | 64, 71 | 32, 56, 33, 44, 7 |
| thinking chars | 307,126 | **188,888** |
| "weld" | **347** | **0** |
| "coincide" | 0 | 60 |
| "pair" | 120 | 71 |

The better run does 40% less thinking and clears four times the levels, and the single
sharpest difference in vocabulary is that it never reaches for "weld".

### The losing run proved welding false and then went back to it

Step 15, level 1 — correct, and explicitly tested:

> the weld broke (gray → red) ✓ meaning **no permanent weld**; coincidence was just overlap
> rendering

Six turns later, step 21, level 2:

> The white object moved down 6 and the two prongs became gray = WELD ✓ … the level completes
> when **ALL objects are welded**

That second sentence is nearly the real rule — and the word carries the one false implication
that matters. A weld is permanent, so progress accumulates; under that model you pair A-B, walk
away to pair C-D, and never suspect you broke A-B on the way. The source says you did.

The grey rendering is the trap: it looks like state being committed. It is a live read of a
dictionary that is thrown away and rebuilt on the next check.

### What the winning run believed instead

Step 4, level 1:

> the level completes when the piece's red dots **coincide** with the target red dots

Step 7 — it tests the conjunction directly rather than treating matches as banked:

> maybe the level needs both dots matched (they both matched **simultaneously**) → should
> complete. It didn't. Let's probe

Step 14, level 2 — the only place in either trace that the pairing arity is named:

> In level 1, there were **exactly TWO** objects … the win came when the piece's pins plugged
> into the ring's sockets

"Pins plug into sockets" is a *reversible* image. "Weld" is not. Neither run ever writes down
that a third notch on the same cell breaks the pair.

## Where the population sits

347 runs played cn04. Levels cleared: **126 at zero, 187 at one**, 28 at two, 5 at three,
1 at four. Every run above two levels is in the table above or one step below it. The wall is
level 1→2, same shape as r11l.

## Proposed

- The prompt has nothing to say about constraints that must hold **simultaneously** versus
  goals that accumulate. Three games now turn on it. One sentence — *"a condition you satisfied
  earlier may no longer hold; re-verify the whole win condition, not the part you just changed"*
  — is cheap and testable.
- A no-op/regression signal would have caught this directly: the losing run had no way to learn
  that its level-2 move un-did a level-2 pair.

## Caveats

- n = 2 traces read in full; the vocabulary counts are over reasoning sections only.
- The `ydfurpdwv` set (mixed 8/13 bucket, `:966-971`) is populated but its consumer was not
  traced; it is likely render-only and is **not** claimed here to affect the win check.
- Level-6 behaviour is unobserved — no run has cleared past level 4.

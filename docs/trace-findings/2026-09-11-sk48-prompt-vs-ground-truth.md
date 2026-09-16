# sk48 level 6 — the system prompt against the game's actual source

The game source is in this repo: `docs/static/games/src/sk48-d8078629/sk48.py`. Everything
below is read from it, not inferred from traces or screenshots. Names in the source are
obfuscated; the mapping is given where it matters.

## Ground truth

**Actions.** `ACTION1-4` are up/down/left/right. `ACTION6` is MOUSE/click. `ACTION7` is
**undo**.

**Movement.** Each head has a facing. Moving along the facing **extends** the rod by one
segment; moving against it **retracts**. Moving perpendicular slides the whole loaded
skewer, and is legal *only* where a rail sprite (`irkeobngyh`) exists.

**Click selects which skewer you drive.**
```python
if clicked := self.current_level.get_sprite_at(x, y, "sys_click"):
    for head, hud_twin in self.xpmcmtbcv.items():
        if clicked in [head, hud_twin] and head != self.vzvypfsnt:
            self.crbbymputr(head)   # this head becomes the controlled one
```
Each board head is paired with the HUD head of the same colour, so **clicking the head's
twin in the bottom strip is a legal way to take control of it**. On single-skewer levels
there is nothing to switch to and clicking is a no-op — which is why it reads as inert.

**The win condition compares two loaded skewers.** `gvtmoopqgy()` walks each rod segment
by segment, collects the block sitting on it, and compares your rod's block colours
positionally against the blocks on the HUD skewer. The bottom strip is not a legend. It is
a second skewer whose load you must reproduce in order.

**Budget.** 196 moves per level, decremented only by the four direction actions;
`lose()` at zero. **Click and undo are free.**

**The HUD reports per-slot progress, live.** For every segment of every HUD skewer,
`on_set_level()` places a small marker sprite (`kevthtkmzm`) and hides it. `gvtmoopqgy()`
then runs after each action and sets marker `i` visible exactly when your rod's block at
position `i` matches the HUD's block at position `i`:

```python
elif self.vjfbwggsd[head][i].pixels[1, 1] == self.vjfbwggsd[hud_twin][i].pixels[1, 1]:
    marker.set_visible(True)
else:
    marker.set_visible(False)
    solved = False
```

So the bottom strip lights a pip per correctly-placed block, in the frame, every turn. A
state with two of three reds lit is one action from clearing the level and says so on
screen. **This is a dense progress signal and no trace read so far uses it** — every run
treats level completion as the only feedback, which is the sparsest possible reading of a
game that is telling them their score slot by slot.

It is also a third reason not to write the bottom strip off as a legend: it is the goal
specification, a click target for switching skewers, *and* the progress meter.

## Level 6, as defined in source

```
head  ejlpqgojjt @ (5,26)  rotation 0    -> rod points RIGHT   (magenta)
head  udbuodqlxv @ (29,2)  rotation 90   -> rod points DOWN    (purple)
rail  x=7,  y=10,16,22,28,34,40                (vertical, left edge)
rail  y=4,  x=13,19,25,31,37,43  rot 90        (horizontal, TOP edge)
wall  mkgqjopcjn @ (29,26)
blue  blocks @ (35,26) (41,26) (47,26)         (horizontal run, right of the wall)
red   blocks @ (29,32) (29,38) (29,44)         (vertical run, below the wall)
HUD   magenta twin @ (5,56)  + blue,blue,blue @ 11,17,23
HUD   purple  twin @ (35,56) + red,red,red   @ 41,47,53
```

Two skewers, perpendicular to each other, each with its own required load, sharing one
board and one wall.

## Line by line against the live prompt

Prompt text quoted from the `cleanrem132-w11-r3-20260909` trace.

| prompt says | level 6 reality |
|---|---|
| "a long horizontal or vertical line **near an edge** is a timer or remaining-steps bar ... do not ... treat it as core gameplay state" | There are two. A vertical rail at x=7 hugging the left edge and a horizontal rail at y=4 hugging the top edge. **Both are the tracks the heads ride.** Without them the heads cannot move perpendicular at all. |
| "It often **shrinks or changes each step**." — offered as the diagnostic *for* a timer bar | The rod is a segmented line that **grows or shrinks by one segment on almost every action**. The prompt's tell for "ignore this" is an exact description of the game's central object. |
| "If a repeated strip of small blocks sits flush against the ... border ... classify it as HUD/timer state, not as an object **to click through segment by segment**. DON'T DO THIS!" | The bottom strip is the goal specification, and its head sprites are `sys_click` targets — **clicking them is one of the two supported ways to switch skewers**. The prompt forbids, in its most emphatic sentence, an interaction the game implements. |
| "Some games ... have no explicit player avatar ... Do not assume a player exists" | The opposite failure is the live one here: there are **two** player avatars and control transfers between them. Nothing in the prompt raises the possibility of more than one controllable entity, or that an action might change *which* one you drive. |
| "For `MOUSE`, pass `row` and `col` integer arguments." | That is the entire guidance on click. Nothing suggests a click might select rather than actuate. Every trace read so far treats MOUSE as "do something at this cell". |
| "Re-ground on the newest frame after any score increase or abrupt scene change" | Correct and useful, and level 6 changes the *control scheme* mid-game rather than the scene. A level advance here can add a second skewer and a second rail orientation. |

## The shape of the problem

The visual-game guidance is a list of priors learned from other games, stated as
appearance rules with no evidence gate. Three of them collide with sk48, and they collide
hardest on exactly the elements that carry the mechanic: the rails, the rod, and the goal
strip. The one emphatic prohibition in the block — `DON'T DO THIS!` — lands on a legal and
sometimes necessary action.

Suggested direction, unchanged from the companion doc but now with source backing:

1. **Gate the HUD rule on evidence, not appearance.** "If actions change only this strip
   and nothing else for N turns" is checkable. "A long line near an edge" is not, and is
   wrong here three times over.
2. **Say that control may transfer.** One sentence — a game may have more than one
   controllable entity, and an action may switch between them — costs nothing and is the
   difference between finding `sys_click` and not.
3. **Say that `ACTION7`/undo may exist and may be free.** Every sk48 trace read so far had
   `ACTION7` in its valid-action list. None of them identified it as undo, and in this game
   it costs no budget, which makes exploration cheap in a way no run exploited.

Source of truth for all of the above: `docs/static/games/src/sk48-d8078629/sk48.py`,
`step()` at line 683, `hgivzuhjvj()` at 746, `gvtmoopqgy()` at 820, `uqclctlhyh()` at 848,
`qzvlbxkjgk()` at 938, level 6 at 446.

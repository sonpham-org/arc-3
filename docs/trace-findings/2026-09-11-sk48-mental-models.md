# sk48 — the three mental models, against the actual mechanic

Companion to `2026-09-11-sk48-zero-vs-eight.md`. Same three traces, read for *what the
agent thought the game was* rather than how much it spent thinking it.

## The actual mechanic

Established by a human playing it, not inferred from traces:

The magenta head carries a rigid rod that extends and retracts. The strip along the
bottom of the screen shows the **required order** — head, then red, orange, blue, green.
You cannot collect a block by approaching it; approaching pushes it. You have to trap a
block against a wall and drive the rod through it, at which point it is **skewered** and
travels with the rod, like meat on a barbecue skewer. The rod is solid: a skewered load
can be used to push other blocks around.

Two facts carry the whole game: the bottom strip is a required order, and contact has two
distinct outcomes — push, or skewer — depending on geometry.

## What each run decided it was

Word-boundary counts over each run's complete thinking.

| run | levels | governing metaphor | count |
|---|---|---|---|
| `astra-fctx-comb-w5-r4` | 2 | **a pen drawing a dashed line** | `pen` 239 |
| `sym264-w5` | 2 | **a wire that impales blocks** | `impaled` 16, `threaded` 19, `thread` 15 |
| `sym264-w7` | 0 | **a chameleon's tongue** | `tongue` 270, `rod` 343, `snake` 19 |

### `sym264-w5` — got it

> when the wire's cells overlap a block's cells, the block is "impaled" (glued). When the
> wire's tip is at the block's left edge (adjacent, no overlap), extension **pushes** it.

That is the mechanic, including the push-versus-skewer distinction, derived from play. It
follows with the consequence:

> impaled blocks follow the tip

### `sym264-w7` — close on the verb, wrong on the goal

> the "tail" is an extending probe/tongue from the head. RIGHT extends the tongue; LEFT
> retracts it; UP/DOWN moves the head (and tongue moves with it).

Extension and retraction are correct. But the objective it derived from that was contact,
not carriage:

> So the goal: extend the tongue to reach each colored block

Touching the blocks in sequence, rather than collecting them onto the rod. It spent the
rest of the run planning reaches.

### `astra-fctx-comb` — wrong metaphor, two levels anyway

> maybe the icon at rows 36-41 cols 11-16 is a "pen/stamp" and the dashed line is a cursor
> path

> this is a "drawing" game where the pen draws a dashed line, and the dashes represent the
> drawn path

It never arrived at a rod, a skewer or a carry rule, and still cleared two levels. Worth
holding onto: on the early levels of this game, a correct model is not strictly required.

## The bottom strip: all three saw it, one committed to it

This is the sharper finding. Every run noticed the HUD strip and every run guessed
correctly what it was — then two of them hedged and moved on.

`sym264-w7`:
> This looks like an order: player then red, green, blue? **Or maybe** a queue indicating
> the order to collect.

and later:
> The HUD likely shows a required collection order. **Or it's just a legend** of "collect
> these".

`astra-fctx-comb`:
> The bottom bar shows the target sequence: pink, red, green, blue.

then downgrades it:
> a legend/palette ... likely a HUD showing the palette of colors in order, **or it's
> showing "current" state**

`sym264-w5` wrote it into code as a constant and planned against it:
```
NR=7; NS=7; LMAX=7; PANEL=('R','O','b','N')
```
`R`,`O`,`b`,`N` = red, orange, blue, green — the correct required order.

The discriminator is not perception. All three perceived it. The discriminator is whether
a suspected rule gets committed to something the run can plan against, or stays a hedge
that every later turn has to re-litigate.

## Why this matters for the 324 zeros

The zero run was not short of reasoning — 160k characters, comparable to the winner's
165k. It had extension and retraction correct by turn 10. It lost because it converted a
correct observation into the wrong objective (touch, not carry) and because it kept the
bottom strip in the "or maybe it's just a legend" bucket for the whole run.

That suggests the cheap intervention is not more capability but forced commitment: make
the agent write down a named state model and a named objective early, and make later
turns test it rather than re-derive it. `sym264-w5` did this unprompted at turn 25 and
cleared the level it had been stuck on.

Same caveat as the companion doc: three traces. This is a direction to test.

<!--
Author: Claude Opus 5 (Bubba)
Date: 13-September-2026
PURPOSE: Correction of record. Earlier docs on this branch name g50t's ACTION5 "rewind".
That is the side effect, not the mechanic. ACTION5 casts a ghost that replays your recorded
path; the rewind-to-start is the price you pay for casting it. Correction raised by the Boss
in #arc-3, verified against g50t.py.
SRP/DRY check: Pass — single correction note; prior docs are annotated in place, not rewritten.
-->

# g50t ACTION5 is not "rewind" — it spawns a ghost

## What the source says

`g50t.py:2802` → `pmlawcgvcp()` (`:2698`). That method snapshots the full recorded move
list (`uocsatwnyt = list(areahjypvy)`), then unwinds it one move per tick via `tqzseunaxh()`
(`:2676`). Reading stops there and you get "rewind."

The mechanic is what happens when the unwind *finishes*, in `step()` at `:2745`:

```python
geujdtqvdo = self.dzxunlkwxt            # the body you were driving
self.dzxunlkwxt = geujdtqvdo.clone()    # you get a fresh clone to drive
self.rloltuowth[geujdtqvdo] = list(self.uocsatwnyt)   # old body keeps your recorded path
geujdtqvdo.bwuyldyhdx()
```

The body you just walked becomes a **ghost**, keyed to the exact move list you recorded.
From then on, every move you make replays one step of each ghost's stored path in lockstep
(`move()`, `:2660`). The grey thing on screen is not debris and not a second player — it is
a recording of you, cast deliberately, that you are now playing alongside.

## Why it matters — ghosts hold plates

Pressure plates (`lqtxaumfed.kzlgpmhyzf`, `:2101`) track a **set** of occupants
(`vbqvjbxkfm`). A plate stays down while *any* body stands on it, ghost or player. So a
level that needs two bodies in two places at once is not solvable by one walker. The
sequence is: walk the path that parks a body on the plate → ACTION5 to cast it as a ghost →
walk yourself through the door it holds open.

The rewind is the cost of casting, not the purpose of the button.

## Correction to prior docs on this branch

- `2026-09-12-astra-grid2-b476-run-floor.md` §3
- `2026-09-12-bottom-seven-what-each-one-is.md` (g50t row)
- `2026-09-13-g50t-human-win-vs-our-zero.md`

All three call ACTION5 "rewind." The observational findings in them stand — the human used
ACTION5 at action 16 on level 1 and on every level after; our trace didn't name it at all
until step 73 of 109. What changes is the *target concept*. "Names the rewind late" was
already generous: the agent never reached the real concept, because rewind is reachable by
watching your body slide back to start, and **ghost-casting is not** — it only shows up if
you connect the leftover grey body to the plate that stays down.

Consequence for the arm-C mechanics list: this is **control-transfer plus self-cooperation**,
and it is a cleaner instance of `indirect-body-control` than the entry currently written in
`LATENT_MECHANICS_IN_THE_PUBLIC_25.md`. A game may require you to cooperate with a recording
of yourself.

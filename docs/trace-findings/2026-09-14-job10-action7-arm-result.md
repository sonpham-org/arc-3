<!--
Author: Claude Opus 5 (Bubba)
Date: 14-September-2026
PURPOSE: Result of job 10, the ACTION7 round-trip arm (arm H), measured on the bottom seven
against the arm-B deletion baseline it stacks on. Records the arm provenance and the
three-way proof that only the ACTION7 variable shipped, the first committed ACTION7 presses
in the whole arm series, the passes-0-2 level readout, the failure of the pre-registered
prediction, and the reading that the entire 15 -> 11 drop sits in lanes the fix cannot reach.
SRP/DRY check: Pass — companion to 2026-09-14-job6-glyph-arm.md and
2026-09-13-job2-deletion-arm-result.md, and amends the exposure list in
2026-09-14-action7-is-unexecutable.md. No new scoring convention.
-->

# Job 10 — the ACTION7 fix took, and the arm still lost four levels

**Date:** 14-Sep-2026
**Author:** Claude Opus 5 (Bubba)
**Job:** `markbarney/arc3-job10-action7-roundtrip`, COMPLETE
**Arm:** H — ACTION7 round-trip, stacked on the deletion arm (B)

## The intervention

Two edits against the arm-B bundle, no more: the `"ACTION7": "ACTION7"` entry in
`action_names.py`, and one line in `prompts.py` stating ACTION7 is executable and
game-specific. Nothing from the animation half of `harnesses/action7-anim`.

## The fix took — and this is the headline

**32 committed ACTION7 presses**, against **zero** in every arm A through G.

| Game | ACTION7 presses p0–2 | p3 | total | `board_changed` |
|---|---|---|---|---|
| bp35 | 10 | 3 | 13 | 13 / 13 true |
| lf52 | 10 | 1 | 11 | 11 / 11 true |
| sk48 | 7 | 1 | 8 | 8 / 8 true |
| g50t, ls20, tn36, wa30 | 0 | 0 | 0 | — |
| **total** | **27** | **5** | **32** | **32 / 32 true** |

`Unknown action at index 1` appears **zero times** in the entire run output. Every press
was accepted, and every single one changed the board. The action is not merely invokable
now; it is effectful. Arms A–G offered the agent a control it could not use — this one
does not.

## Arm purity — one variable, proved three ways

Job 10's in-log provenance, verbatim:

```
EXP_SETTINGS arm=H-action7-roundtrip lanes=7 passes=4 per_game_s=1980.0 budget_s=7920.0 concurrency=7
ARM_PROVENANCE arm=H-action7-roundtrip
ARM_PROVENANCE prompts_py_sha256=8192f5e8861d9b6a02a637053bd39e88f137db0628a3e34c28331f69fa127056
ARM_PROVENANCE system_prompt_chars=12234 sha256=f2f94cf130ded7f9e2bec54d3186c4e0037640a79ee56b4d297d87b9d3f1f2e8
ARM_PROVENANCE color_chars='WwgGcBMPRbSYOrNp' rendered_row='WwgGcBMPRbSYOrNp'
ARM_PROVENANCE color_legend=W=white, w=light gray, g=gray, G=dark gray, c=charcoal, B=black, M=magenta, P=pink, R=red, b=blue, S=sky blue, Y=yellow, O=orange, r=dark red, N=light green, p=purple
ARM_PROVENANCE probe="DON'T DO THIS" present=False
ARM_PROVENANCE probe='remaining-steps bar' present=False
ARM_PROVENANCE probe='64 x 64' present=False
ARM_PROVENANCE probe='puzzle' present=False
ARM_PROVENANCE marker[C-mechanics] present=False
ARM_PROVENANCE marker[D-glyph-consonants] present=False
ARM_PROVENANCE marker[E-image-first-turn] present=False
ARM_PROVENANCE marker[F-commit-prompt] present=False
ARM_PROVENANCE marker[G-visual-first] present=False
ARM_PROVENANCE marker[H-action7-roundtrip] present=True
ARM_PROVENANCE withhold_text_board_until_step=0
```

Arm B's deletion is intact (all four probes `present=False`), the control glyph table is
unchanged, and every other arm's marker is absent. On top of that:

1. **Character arithmetic.** Arm B ran at `system_prompt_chars=11991`. Arm H runs at
   `12234`. The shipped ACTION7 line is 243 characters. `11991 + 243 = 12234`, exact.
   There is no room in the prompt for a second change.
2. **The animation keys are absent everywhere.** The patch's animation half emits
   `animation_frame_count`, `animation_changed`, `animation_only_changed`,
   `animation_changed_cell_count`, `animation_changed_bbox`, `animation_transition_count`.
   A recursive search of the entire job 10 output — log, prompts, transcripts, artifacts —
   returns zero hits on all six.
3. **The prompt line was rewritten to drop the animation clause.** The patch's version
   ends "...the returned before/after and animation metadata rather than assuming...".
   The shipped line reads:

   > `- `ACTION7` is a valid, executable game action whenever it appears in
   > `valid_actions`. Its meaning is not fixed across games; infer it from a safe probe
   > and the returned before/after state rather than assuming it means undo, confirm, or
   > back.`

   The animation reference is gone, not merely unshipped in code.

This is the cleanest arm-purity evidence in the series. Arm H is one variable.

## Result

Level clears, passes 0–2, bottom seven:

| Game | Control (A) | Deletion (B) | **ACTION7 (H)** | Δ vs B |
|---|---|---|---|---|
| sk48 | 1 | 0 | **1, 0, 0** = 1 | +1 |
| bp35 | 1 | 2 | **1, 0, 1** = 2 | 0 |
| ls20 | 1 | 3 | **1, 1, 0** = 2 | −1 |
| g50t | 0 | 2 | **0, 0, 0** = 0 | −2 |
| lf52 | 3 | 4 | **1, 1, 2** = 4 | 0 |
| wa30 | 2 | 2 | **0, 1, 1** = 2 | 0 |
| tn36 | 2 | 2 | **0, 0, 0** = 0 | −2 |
| **total** | **10** | **15** | **11** | **−4** |

Mean score, passes 0–2: **1.085** (control 0.960, deletion 1.535).

Per-game scores, passes 0–2:

```
bp35  2.222  0.000  0.583
g50t  0.000  0.000  0.000
lf52  1.818  1.818  5.455
ls20  3.571  3.571  0.000
sk48  0.641  0.000  0.000
tn36  0.000  0.000  0.000
wa30  0.000  0.877  2.222
```

## Reading it

**The whole −4 sits in lanes the fix cannot reach.** The one variable has two channels:
the map entry only bites where ACTION7 is exposed, but the prompt line ships in all seven
lanes. Split the deltas on that line and the pattern is unambiguous.

- **Pressed ACTION7** (bp35, lf52, sk48): 0, 0, +1. No gain where the map entry can act.
- **Never pressed** (g50t, ls20, tn36, wa30): −2, −1, −2, 0. The entire loss.

So it is either the +243-char prompt line costing lanes that have no use for the action, or
it is run variance. Both readings are bad for the arm and neither is worth picking on n=3.
What is settled is that making ACTION7 executable did not buy a level anywhere it became
executable.

**Against the pre-registered criterion this is a negative result**, the same call job 6 got
at 12. 11 against the deletion arm's 15: that ties arm E for the joint-lowest of arms B
through H, with only the control sitting below at 10.

**g50t and tn36 are the two-pass moves** and are the real content of the drop; both went
from 2 to hard zeros across all three passes. ls20 −1 and sk48 +1 are one pass wide and
should not be quoted alone.

**lf52 is the one bright spot in the score column**, `1.818, 1.818, 5.455` — the flat
control ceiling twice, then a 5.455 — above the 4.169 arm B posted, which the job 6 doc
records as the only prior break of lf52's flat ceiling — and the only pass in the set that
cleared two levels. lf52 is also the heaviest ACTION7
user at 10 presses in the window. That is a thread, not a result: it is one pass, and the
level total held at 4, unchanged from arm B.

## The pre-registered prediction failed on both halves

`2026-09-14-action7-is-unexecutable.md` registered, before the run: the gain lands on
bp35, lf52 and tn36, and the four games not exposing ACTION7 do not move.

Neither half held. **No gain on bp35 (0), lf52 (0) or tn36 (−2).** And **three of the four
games that were supposed to sit still moved**: g50t −2, ls20 −1, sk48 +1.

## Amendment to the exposure list

The action7-anim MANIFEST names bp35, lf52, tn36, vc33, lp85 and ar25 as the games
exposing ACTION7. Measured against committed presses, that list is wrong in both
directions within our seven: **tn36 committed zero presses**, and **sk48 — not on the list
— committed eight**.

Stated limit: the artifacts carry transcripts and events, not the raw `valid_actions`
payloads, so exposure per game **cannot be verified directly from this run**. ACTION7 is
mentioned in all seven games' transcripts (g50t 25 times, tn36 33) — that is the new
prompt line making the agent reason about the action, not evidence that the action was
offered. What can be asserted is the press count, and with zero refusals anywhere, a lane
with zero presses is a lane where the agent never committed one.

## Run health

Clean. `NVIDIA RTX PRO 6000 Blackwell Server Edition, 97887 MiB, 580.159.04`. Watchdog
`restart_attempts: 0`, started and stopped normally, no failure events. All seven lanes
ran passes 0–2 to the full 1980s cap, and **pass 3 was `cancelled` in all seven** at
~6705–6729s against the 7920s budget — the standing shape, which is why pass 3 is excluded.
Teardown reported `shutdown_ok: false` with one GPU survivor, after all artifacts were
preserved; it does not touch the measurement.

## Standing after job 10

| Arm | Job | Level clears (p0–2) |
|---|---|---|
| A — control | 1 | 10 |
| B — pure deletion | 2 | **15** |
| C — mechanics possibility | 4 | **16** |
| D — glyph consonants | 6 | 12 |
| E — image-first | 7 | 11 |
| F — commit-prompt | 8 | 13 |
| H — ACTION7 round-trip | 10 | 11 |
| G — visual-first | 9 | running |

The standing reading survives job 10 intact: only the two arms that changed what the model
is permitted to *believe* have moved the number up. Arm H fixed a real harness defect — the
32 presses and zero refusals prove that much, and the fix should stay — but repairing a
broken control did not, on its own, buy a level.

n=3 per game. Single-game deltas are one pass wide and should not be quoted alone.

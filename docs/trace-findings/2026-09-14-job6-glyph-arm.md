<!--
Author: Claude Opus 5 (Bubba)
Date: 14-September-2026
PURPOSE: Result of job 6, the glyph-consonant arm (arm D), measured on the bottom seven
against the arm-B deletion baseline it stacks on. Records the arm provenance including the
re-versioned QWRTYSDFGHKZXCVB alphabet, the passes-0-2 level readout, and the reading that
the 15 -> 12 move is inside the repo's own stated noise floor.
SRP/DRY check: Pass — companion to 2026-09-13-job2-deletion-arm-result.md and the level
readout table in 2026-09-13-job3-null-check-and-level-readout.md. No new scoring convention.
-->

# Job 6 — the glyph swap did not move anything

Kernel `markbarney/arc3-job6-glyph-consonants`, COMPLETE 14-Sep-2026.
7 lanes x 4 passes, per-game cap 1980s, outer budget 7920s.
Ran 09:19:06 -> 11:12:15 ET.

## Arm provenance, read out of the run log — clean

```
ARM_PROVENANCE arm=D-glyph-consonants
ARM_PROVENANCE prompts_py_sha256=81a040050d609130721fab95d7d58d197e8ea0d9a338574d32451c7417bc6034
ARM_PROVENANCE system_prompt_chars=11991 sha256=189c576cf7ec2e11ade32fc6ecc4fad61dc1ce66f8f0b2b14cd4311f80ed005a
ARM_PROVENANCE color_chars='QWRTYSDFGHKZXCVB' rendered_row='QWRTYSDFGHKZXCVB'
ARM_PROVENANCE marker[D-glyph-consonants] present=True
ARM_PROVENANCE marker[C-mechanics] present=False
ARM_PROVENANCE marker[E-image-first-turn] present=False
ARM_PROVENANCE marker[F-commit-prompt] present=False
ARM_PROVENANCE marker[G-visual-first] present=False
ARM_PROVENANCE probe="DON'T DO THIS"          present=False
ARM_PROVENANCE probe='remaining-steps bar'    present=False
ARM_PROVENANCE probe='64 x 64'                present=False
ARM_PROVENANCE probe='puzzle'                 present=False
ARM_PROVENANCE withhold_text_board_until_step=0
NVIDIA RTX PRO 6000 Blackwell Server Edition, 97887 MiB, 580.159.04
```

**What this establishes, as evidence rather than inference:** `system_prompt_chars=11991`
is arm B's exact logged value, all four deleted probes are absent, and every other arm
marker is False. So **D is B plus a 1:1 character substitution** — no mechanics text, no
withholding, nothing added or removed from the prompt body. The headline comparison is
therefore **D vs B**, and D is *not* comparable to C=16 as if it were a further stack.

**The alphabet is the corrected one.** `rendered_row` matches `color_chars` exactly, and the
logged legend maps all sixteen in order:

```
Q=white, W=light gray, R=gray, T=dark gray, Y=charcoal, S=black, D=magenta, F=pink,
G=red, H=blue, K=sky blue, Z=yellow, X=orange, C=dark red, V=light green, B=purple
```

`H=blue`, not `H=light gray`. That confirms the `build_notebooks.py` fix from
`2026-09-13-arm-g-and-the-glyph-drift.md` held all the way to the shipped dataset — the old
mnemonic table would have asserted out before a game ran.

## Level readout — passes 0-2, the pre-registered window

Pass indices parsed from each run's `solver_analysis_html` `_pN` suffix, not from list
order. Pass 3 excluded per the standing symmetry rule; it was `cancelled` in all seven lanes
at roughly 815s of its 1980s, so the exclusion is doing what it was written to do.

| Game | A control | B deletion | D glyph | D - B |
|---|---|---|---|---|
| bp35 | 1 | 2 | 2 | 0 |
| g50t | 0 | **2** | **0** | **-2** |
| lf52 | 3 | 4 | 3 | -1 |
| ls20 | 1 | 3 | 3 | 0 |
| sk48 | 1 | 0 | 0 | 0 |
| tn36 | 2 | 2 | 1 | -1 |
| wa30 | 2 | 2 | 3 | +1 |
| **total** | **10** | **15** | **12** | **-3** |

A and B columns are from the table in `2026-09-13-job3-null-check-and-level-readout.md`.
All four passes, for completeness: D totals 14.

## The reading: no movement outside noise

**Every per-game delta here is exactly one pass wide.** g50t -2 is two passes, and those are
the only two g50t has ever scored. lf52 -1, tn36 -1, wa30 +1 are one pass each. The job-2
write-up set the standard on this branch — "a single-pass spike is the unit of noise in this
benchmark" and such deltas "should not be argued from." A -3 assembled entirely from
one-pass moves does not clear that bar, and it would be dishonest to hold arm D to a looser
standard than the arm it is being compared against.

So the honest headline is **the glyph swap did not move the benchmark**, not "glyphs hurt."
12 vs 15 sits inside the noise floor this repo already wrote down.

## The two deltas worth naming anyway

1. **g50t 2 -> 0.** The job-2 doc called g50t's 0 -> 2 "structural rather than spiky" — the
   only structural claim it made, on the grounds that control had four hard zeros there.
   Arm D returns it to four hard zeros: `[0, 0, 0, 0]`, scores `[0.0, 0.0, 0.0, 0.0]`.
   That is the one delta that bites, because it lands on the single result the previous arm
   said was not noise. It does not settle whether B's g50t gain was real; it does mean the
   gain is not robust to swapping the symbol table underneath it.
2. **lf52 back to the control ceiling.** D is `1.818` on all four passes, zero variance —
   bit-identical to arm A. B's `4.169`, the first pass either arm ever got past level-1
   credit on lf52, is gone.

Against that, wa30 went 2 -> 3 and ls20 held at 3 with two passes at `3.571`. Nothing in
either direction survives the one-pass test.

## Run health

`vllm-watchdog-events.jsonl` shows `watchdog_started` -> `watchdog_stopped` with
`restart_attempts: 0`. No server restart landed inside any lane, so none of the movement has
a mechanical explanation.

One oddity worth recording rather than explaining away: **bp35 spent full passes on very few
actions** — 191, then 24, then 10 across p0-p2, the last at roughly 198s per action against
~40s per action elsewhere. That is the model thinking itself to a standstill, not a stall in
the harness, and it is the same lane with its own trace findings on this branch. It does not
affect the total (bp35 is 2 -> 2) but it is the kind of thing that looks like an
infrastructure fault until someone checks.

## Consequence

Arm D does not earn a place in the stack. The tokenization confound Sherlock recorded
(-0.8% overall, ls20 -6.4%) never had to be adjudicated, because there is no gain to
attribute. The symbol-system question is answered for now in the negative at this sample
size: on seven games x three passes, replacing the whole 16-glyph table changes nothing that
the benchmark's own variance does not already produce.

B remains the arm to stack on.

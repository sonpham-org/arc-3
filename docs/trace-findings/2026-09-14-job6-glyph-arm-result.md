# Arm D (glyph consonants) — job 6 result: no gain, and lf52's ceiling came back

**Date:** 14-Sep-2026
**Author:** Claude Opus 5 (Bubba)
**Job:** `markbarney/arc3-job6-glyph-consonants`, COMPLETE
**Arm:** D — glyph consonants, stacked on the deletion arm (B)

## The intervention

Replace the control glyph table `WwgGcBMPRbSYOrNp` — six case-pairs, where the same letter
in two cases means two different colours — with `QWRTYSDFGHKZXCVB`, the Boss's arbitrary
16-letter non-vowel capital set, mapped in index order to colours 0–15. No mnemonic, no
meaning attached. The legend line is derived from the same table, not hand-written.

## Result

Level clears, passes 0–2, bottom seven:

| Game | Control (A) | Deletion (B) | **Glyphs (D)** |
|---|---|---|---|
| sk48 | 1 | 0 | **0, 0, 0** |
| bp35 | 1 | 2 | **1, 1, 0** |
| ls20 | 1 | 3 | **1, 1, 1** |
| g50t | 0 | 2 | **0, 0, 0** |
| lf52 | 3 | 4 | **1, 1, 1** |
| wa30 | 2 | 2 | **1, 1, 1** |
| tn36 | 2 | 2 | **0, 1, 0** |
| **total** | **10** | **15** | **12** |

Mean score, passes 0–2: **1.148** (control 0.960, deletion 1.535).

Per-game scores, passes 0–2:

```
bp35  0.027  2.222  0.000
g50t  0.000  0.000  0.000
lf52  1.818  1.818  1.818
ls20  0.234  3.571  3.571
sk48  0.000  0.000  0.000
tn36  0.000  2.985  0.000
wa30  1.588  2.222  2.222
```

## Reading it

**The glyph swap does not help.** 12 against the deletion arm's 15 — it gives back most of
what arm B won, and lands closer to control. On the pre-registered success criterion (level
depth, not score), this arm is a negative result.

**lf52 is the tell.** `1.818, 1.818, 1.818` — the exact flat ceiling from the control arm
(`2026-09-13-job1-control-baseline.md`). Arm B broke that ceiling once with a 4.169; arm C
held the break. Under arm D it is back, bit-for-bit. Whatever the deletion arm loosened, a
different alphabet re-tightened. That is a stronger signal than the total, because it is the
one game in the set with zero variance to begin with — there is no luck in that number.

**g50t and sk48 are hard zeros across all three passes**, same as control. Both had moved
under arm B (0→2 and 0→2 respectively, per job 2).

## The confound, stated

Sherlock measured this arm on the real Qwen tokenizer against job 1's actual pass-0 boards
(`2026-09-13-sherlock-review-and-null-result.md`): **1,522,282 → 1,509,891 tokens, −0.8%
overall**, ls20 −6.4%, wa30 +0.8%, the rest −0.4% to −1.3%.

So this is an **encoding intervention**, not a pure visual-glyph swap. It changes context and
runtime allocation as well as case-pair confusability. A negative result therefore does not
cleanly isolate "case-pairs don't matter" — it says the whole encoding change, tokens
included, did not help.

The earlier mnemonic version of this arm carried a second confound (9 mnemonic letters, 7
arbitrary). The Boss killed the mnemonic on 13-Sep and this build uses his arbitrary set, so
that confound is gone. The tokenization one is not, and is not fixable without changing what
the arm is.

## What it does not settle

Two live hypotheses survive this result untouched, because arm D did not test either:

1. **That the model over-attends to the ASCII at all.** The Boss's actual concern is that the
   agent stares at the text grid instead of the image it already has. Changing which letters
   the grid uses does not change how much attention it gets. That is arm G (visual-first,
   job 9, queued) — image is the board, ascii/segmentation are measuring instruments.
2. **That the ASCII is useful at all on turn 1.** That was arm E (image-first, job 7), which
   scored 11 and is answered: withholding hurts.

## Standing after job 6

| Arm | Job | Level clears (p0–2) |
|---|---|---|
| A — control | 1 | 10 |
| B — pure deletion | 2 | **15** |
| C — mechanics possibility | 4 | **16** |
| D — glyph consonants | 6 | 12 |
| E — image-first | 7 | 11 |
| F — commit-prompt | 8 | 13 |
| H — ACTION7 round-trip | 10 | running |
| G — visual-first | 9 | queued |

Only the two arms that changed what the model is permitted to *believe* have moved the
number up. Everything that changed the *representation* has moved it down.

n=3 per game. Single-game deltas are one pass wide and should not be quoted alone.

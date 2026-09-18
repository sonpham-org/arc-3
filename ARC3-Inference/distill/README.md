<!--
Author: Claude Opus 5 (Bubba subagent)
Date: 18-September-2026
PURPOSE: The exclusion list for the distillation pipeline -- every corpus that must never
reach `extract_sft.py`, why, and whether the fence is enforced by code or by the caller.
Created because docs/plans/2026-09-18-oracle-test-plan.md section 5 requires the oracle
run-dir pattern to be recorded here before the first oracle run, and this directory had no
README to record it in.
SRP/DRY check: Pass -- this is a fence register, not pipeline documentation. How the
pipeline works lives in extract_sft.py's own module docstring and in
docs/how-this-feeds-kaggle.md; the as66 rule is owned by datasets/test-only-games/README.md
and cited, not restated.
-->

# distill/ — what must never enter a training corpus

`extract_sft.py` turns run artifacts into SFT records. Three classes of material must never
reach it. Two of the three are the caller's responsibility; one is refused by the tool.

## 1. Oracle run directories — `*-oracle-*` — REFUSED BY THE TOOL

The oracle test (`docs/plans/2026-09-18-oracle-test-plan.md`) injects each game's **full
rulebook** into the agent's first user turn and re-sends it every turn. Those transcripts
contain the answer key. A model trained on them would be learning the answers to the public
25, not how to find them — and the leak is undetectable after the fact, because the rulebook
sits inside ordinary-looking user turns rather than in any field a later audit would think to
check.

Plan section 5 requires this fence to exist **before the first oracle run**, not after.

`extract_sft.py` refuses, with exit code 2 and no output written, when any `--run-dir`'s own
name or its immediate parent's name matches `*-oracle-*` (case-insensitive). There is
deliberately **no override flag**: a legitimate reason to read an oracle run — scoring,
paired comparison, trace reading — belongs in an analysis script, never in the SFT builder.

Name oracle run dirs so they match, e.g. `20260919_HHMMSS_qwen38-27b-oracle-p0`. The guard is
the backstop, not the naming convention's replacement.

## 2. `as66`, the test-only game — CALLER-ENFORCED

Owned by [`datasets/test-only-games/README.md`](../../datasets/test-only-games/README.md),
"The rule: never train on it". Pass it in `--exclude-games` whenever the run played it. The
fence matches the bare code, so `as66` catches `as66-v1`.

## 3. The seven held-out games — CALLER-ENFORCED

`datasets/splits/public25-train-test-split.json`: `vc33, ar25, sb26, re86, su15, tr87, tu93`.
Combined with as66 that is the standard fence:

```
--exclude-games vc33,ar25,sb26,re86,su15,tr87,tu93,as66
```

`--only-games` is the inverse selector, used to build the held-out **eval** corpus. It is
mutually exclusive with `--exclude-games`.

Note that the oracle test runs the slippery seven (`dc22 g50t m0r0 sc25 sk48 tn36 tr87`), of
which exactly one — `tr87` — is also in the held-out split above. That does not breach the
split: `tr87` is being *measured* there, not trained on, and section 1 is what keeps the
distinction true. The other 18 public games are a follow-up run only if the seven move.

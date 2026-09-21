<!--
Author: Claude Opus 5 (Bubba subagent)
Date: 21-September-2026
PURPOSE: Registry entry for the deliberately-overfit sk48 local arm run on the Mac Mini on
21-Sep-2026. Records what it derives from, the one-line prompt diff it carries, where its
treatment text comes from, and the fence that keeps its transcripts out of training.
SRP/DRY check: Pass -- harnesses/README.md requires one MANIFEST per variant; this is that file
for this variant. The result and the verbatim treatment text live in
docs/trace-findings/2026-09-21-sk48-overfit-local-run.md and are cited, not restated.
-->

# sk48-overfit — local Mac Mini diagnostic

**Not a benchmark arm.** The model is told the game's name and full mechanics up front. Its
score is not comparable to any held-out arm. See
`docs/trace-findings/2026-09-21-sk48-overfit-local-run.md` for the run, the result and the
verdict.

## Derives from

Arm O, `harnesses/oracle-rules/`, whose injection mechanism (`inference/agent/oracle_rules.py`,
selected by `ARC3_ORACLE_RULES_DIR`) is reused unchanged. Nothing about the injection path was
reinvented.

## The diff — one line

`patch/prompts.py.patch` removes a single line from `VISUAL_GAME_ADDENDUM` telling the model
that a repeated strip of small blocks flush against a border is HUD/timer state, "DON'T DO
THIS!". In sk48 that strip **is** the win condition — it is the reference skewer showing the
wanted colour order.

It is kept as a patch rather than committed to `main` on purpose: it would otherwise change the
default prompt for every other arm, including the concurrent a424 runs.

## Treatment

`datasets/explainer-games/rulebooks-sk48-overfit/sk48.txt`, 9,611 characters, hand-built from
the Boss's own write-up at `arc-explainer` HEAD (`shared/arc3Games/sk48.ts`). It is **not** the
arm-O rulebook set, which was left untouched. `datasets/explainer-games/` is gitignored, so the
text is reproduced verbatim in Appendix A of the trace-findings doc.

## Launch

`scripts/run_sk48_overfit_local.sh`.

## Contamination fence

Run dirs are named `*-oracle-*`, so `distill/extract_sft.py` refuses them with exit code 2 and
no override. These transcripts contain the answer key to sk48. Not renamed, not worked around.

## Score

No level cleared and no game action taken as of 17:40 EDT; run 4 (harness defaults restored) is still going. The three earlier runs were confounded by an imposed tool-step ceiling -- see the trace-findings doc. The 0.00 carries no information about the model and must not be quoted beside the a108 sk48 0.00.
information about the model and must not be quoted beside the a108 sk48 0.00.

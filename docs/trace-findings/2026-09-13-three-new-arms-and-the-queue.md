# Three new arms, and a queue that reports itself

Date: 13-September-2026
Author: Claude Opus 5 (Bubba)
Branch: `docs/bp35-trace-findings` (PR #7)

## What was asked

The Boss asked for several experiments built and queued to run on a schedule:

1. Swap the board's 16 glyphs for prominent, distinct consonant capitals, from the
   allowed set `QWRTYSDFGHKZXCVBM` — is the symbol choice worth anything?
2. Withhold the text board on the first turn, so the first hypothesis has to come off
   the image the model already receives.
3. Commit to a hypothesis: stop exploring once one is formed, plan, execute, and treat
   failure to reach the next level as the refutation signal.

## Reference arm is B, not A

Every new arm is built **on top of arm B** (the sparse deletion), because B is the
measured reference: it beat control 10 -> 15 level clears on the pre-registered window.
Stacking on A would measure against a base we already know is worse. Same seven lanes,
same `n_passes=4`, same 1980s per-game cap as job 2, so each new job is directly
comparable to job 2 and to job 4 (arm C).

Primary readout is `levels_completed` out of `benchmark.json`. Not `score.json` — reading
score alone is what hid the arm-B effect for a week.

## Arm D — glyph consonants (job 6)

Control set is `WwgGcBMPRbSYOrNp`: six of the sixteen are the same letter in two cases
(`W/w`, `g/G`, `B/b`, `R/r`, `N/n`-adjacent, `P/p`). That is the confusable part.

Replacement is `WHGDCBMKRTSYFVZX` — 16 distinct non-vowel capitals, all from the Boss's
allowed set. `Q` is dropped: he listed 17 letters for 16 slots. Initial-letter mnemonics
are kept wherever the initial is free (W, G, D, C, B, M, R, S, Y); the remaining six
colors take leftovers in color order, so `T=blue` and `F=orange` carry no mnemonic. That
is a known cost of the arm and it is stated rather than hidden.

**This is not a cosmetic ascii change.** `ARC_COLOR_CHARS` is imported by
`python_tool_sandbox.py:18` and passed to `segment_layer` at `:139`, and the prompt names
`segmentation` as the *primary* view. So the arm swaps the whole symbol system, not just
the ascii rendering. "Does the ascii alphabet matter" and "does the symbol system matter"
are different claims; this measures the second.

The legend is **derived** from the same table the characters come from
(`ARC_COLOR_LEGEND = ", ".join(...)`), not hand-written. A hand-written legend against a
swapped table would make the prompt lie about the board, and no probe on `prompts.py`
would catch it — that is exactly how the word "puzzle" survived in two files.

Known confound, not controlled: a run of consonant capitals may tokenize differently than
the mixed-case set. The rendered row and the served glyphs are logged per run so it can be
checked after the fact.

## Arm E — image-first turn (job 7)

Withholds **both** text renderings until one action has been executed. Gating `.ascii`
alone is a no-op, because `prompts.py:50` tells the model to prefer `.segmentation`.

Implementation is in `_ascii_frame_view_payload` (tool_agent.py): while `frame.step <
_WITHHOLD_TEXT_BOARD_UNTIL_STEP`, `ascii` returns a short notice and `grid` returns `[]`.
The sandbox's `segmentation` property returns that same notice when the grid is empty,
so a withheld board never reads as an *empty* board. `.step`, `.level`, `.shape` and
`valid_actions` stay live, so the agent can still act its way out.

Verified before launch: `serving_setup.py:2945` sets `MULTIMODAL_CONTEXT=current_grid`, so
the image really is in the turn-0 user message. Without that this arm would be dead on
arrival, with the model blind in both channels.

The gate is "until you have acted once", not "turn 1", because several thinking turns can
precede the first action. One prompt line tells the model the rule and that both views
return next turn.

## Arm F — commit to hypothesis (job 8)

Prompt-only, three lines: exploration is for building one hypothesis, not collecting
observations; once one hypothesis explains every action so far, write the plan it implies
and execute it; **reaching the next level is the test** — if the plan ran out and the level
did not change, name the part of the hypothesis the outcome refutes and replace it.

This is deliberately the *prompt-only* version of what the Boss described. The enforced
version — a hard exploration cap wired into the agent loop with a plan-execute-assess
mode — is a control-flow change, and control-flow changes are where the bug lands that
eats a 2.2h slot. They are also two different questions: can the model self-regulate, and
does capping help. Prompt version runs now; the enforced version is spec'd and gated on a
local dry-run before it gets a slot.

## What the pre-flight caught

A local dry-run executes each generated notebook's provenance cell against its own bundle,
in a clean subprocess, before anything is pushed. It failed arm E: the marker probed
`"text board withheld until you have executed"`, which lives in the *code constant*, not in
the assembled system prompt. On Kaggle that is nine minutes of vLLM boot followed by a
`RuntimeError` on the arm's own probe, and a dead slot. Fixed to probe a phrase the prompt
actually carries.

The same run exposed a second thing: `subprocess.run(..., check=False)` still raises
`FileNotFoundError` when `nvidia-smi` is absent, which made the dry-run unable to pass
anywhere off-Kaggle. Wrapped, so the pre-flight is a real gate rather than a formality.

Also verified: arm B rebuilds byte-identical to the shipped bundle (only README and
upload metadata differ), and each new arm differs from B in exactly the intended files —
D in `grid_utils.py` only, F in `prompts.py` only, E in `prompts.py`, `tool_agent.py`,
`python_tool_sandbox.py`.

Note on the regenerated notebooks: jobs 0-4 ran the previous provenance cell. The
regeneration changes assertions only — no prompt, bundle, run shape, or cap moved — and
each of those runs recorded its own arm identity in its Kaggle log.

## The queue (`tools/arc3/arc3_job_queue.py` in bubba-workspace)

The repeated failure in this experiment has not been the science. Jobs 1 and 3 both
finished and sat unread for hours. So the queue reports itself: an OpenClaw cron fires
every 20 minutes into the main session, runs the queue script, and posts only when
something changed. One invocation does at most one thing — report a finished job, or
launch the next — and it pulls `levels_completed` per game out of `benchmark.json` rather
than making anyone go look.

Order: job 5 (null control, first because job 3's null check has no baseline until its
control runs), then 7 image-first, then 8 commit, then 6 glyphs.

The first run of it caught its own design bug: Kaggle will run two GPU kernels at once, so
"did I launch it" is not the same question as "is anything running". It launched job 5
alongside job 4, which was already in flight from outside the queue. Both are wanted jobs
and both are within Kaggle's concurrency limit, so they were left to run — but the guard
now asks the server about every experiment kernel, not just the one the state file
remembers. An `ERROR` status holds the queue instead of launching on top of a failure.

## Budget

~8.8h of the 30h spent or committed after jobs 4 and 5. Four remaining jobs at 2.2h each
puts the total near 17.6h, leaving ~12h before the Thursday 18-Sep refresh.

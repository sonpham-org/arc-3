<!--
Author: Claude Opus 5 (Bubba subagent, label no-score-pressure-wide)
Date: 21-September-2026
PURPOSE: Registry entry for the "no score pressure" wide arm run on gx10-a424 on 21-Sep-2026.
Records what it derives from, the exact subtractive prompt diff it carries, why it ships a
matched control arm instead of reusing an existing baseline, and the serving settings it pins.
SRP/DRY check: Pass -- harnesses/README.md requires one MANIFEST per variant; this is that file.
The result and the behavioural read live in
docs/trace-findings/2026-09-21-no-score-pressure-wide.md and are cited, not restated.
-->

# no-score-pressure — wide arm, all 25 public duck games

The agent's system prompt currently asks the model to manage its own action-efficiency score
and to stay vigilant about HUD counters, timers and progress bars. A person playing these games
thinks about none of that. This arm removes that material and reframes the opening line, and
changes nothing else.

**Subtractive plus one reframe.** No new mechanics advice, no hints, no replacement rules, and
nothing added that tells the model what a bar or strip on screen means in either direction.

## The diff — four deletions and one reframed line

`patch/prompts.py.patch` removes four bullets from repo HEAD, verbatim:

1. `GAME_OVERVIEW_ADDENDUM` — the action-efficiency bullet carrying the
   `min(human_actions / agent_actions, 1.0)` squared scoring formula.
2. `GAME_OVERVIEW_ADDENDUM` — the "test for false goals" bullet (a HUD counter, timer or
   progress bar cannot be the objective; pursuing it is "the worst possible efficiency").
3. `VISUAL_GAME_ADDENDUM` — "a long horizontal or vertical line near an edge is a timer or
   remaining-steps bar".
4. The python-tool guidance — "after every action, verify whether ... only a timer, progress
   bar, or remaining-step bar moved".

`patch/tool_agent.py.patch` changes the opening system line in `_build_system_prompt` from
"You are a coding agent solving a grid-based puzzle game." to "You are playing a video game. You
figure out the controls and the rules by playing."

**The reframe is not in `prompts.py`.** It lives in `inference/agent/tool_agent.py`. A patch
that touched only `prompts.py` would silently drop half this arm.

### Deliberately retained

- The mechanical note that mid-run level completion shows up as a score increase. That is
  feedback the environment gives the player, not pressure to manage.
- The `VISUAL_GAME_ADDENDUM` line beginning "A common failure mode is to mistake a segmented
  edge bar for clickable puzzle pieces ... DON'T DO THIS!". This is a fifth HUD-vigilance
  instruction of the same family and it was **not** in the specified removal set. It is present
  in **both** arms, so it is held constant and cannot confound this comparison. Flipping it is
  the obvious next arm; it is called out here rather than silently absorbed.

Patches are kept out of `main` on purpose: committing them would change the default prompt for
every other arm.

## Why this arm ships its own control

The existing a424 baseline (`r4w-a424-base-p1/p2`, `~/GitHub/arc-3` tree on that box) **cannot**
serve as the control. That tree predates the current prompt: bullets 1 and 2 above do not exist
in it at all, and its bullet 1 reads only "Optimize for as few in-game actions as possible while
still being reliable." Measured, not assumed — the tree on a424 is not a git checkout, so both
files were hashed and diffed against clean repo HEAD. It also covers only the seven held-out
games, not 25.

The 25-game a108 baseline is on a different box with an older harness, and this repo's own r4w
config carries the note "Do not compare numbers across boxes."

So both arms are run here, back to back, on one server:

- `ARM=stripped` — the patched prompt.
- `ARM=control` — clean repo HEAD, unmodified.

Same tree, same server process, same seed, same lane count, same wall, and the **same explicit
25-game list in the same order** so that a truncated arm still yields matched pairs.

## Provenance of the harness tree

`~/arc3-nosp/ARC3-Inference` on a424 is a copy of `~/arc3-sk48-overfit/ARC3-Inference`, verified
byte-identical to clean repo HEAD across all 30 files under `inference/` **except**
`prompts.py`, which each arm overwrites from `variants/` at launch.

Because that tree came from the sk48 overfit arm, `run_nosp_a424.sh` explicitly unsets
`ARC3_ORACLE_RULES_DIR`. A leaked export would hand both arms the sk48 answer key. Run dirs do
not carry `-oracle-`: this is not an oracle arm and must stay eligible for SFT extraction.

## Serving

`serve_nosp_a424.sh` — stock BF16 `Qwen3.8-27B`, vLLM, port 1234, `--seed 0`, qwen3 reasoning
parser, hermes tool-call parser, single-instance guard on port and process.

It keeps the seed, reasoning parser and guard established earlier the same day but raises
`gpu-memory-utilization` to 0.85 and turns prefix caching **on**. The sk48 arm's settings (0.62
util, caching off, 4 sequences) were why it decoded at roughly two tokens a second and could not
finish; that arm was killed to free this box. Prefix caching matters because the harness resends
a long system prompt every turn.

`hermes` is used rather than the r4w baseline's `qwen3_coder`: hermes is verified parsing
correctly against current-HEAD `tool_agent.py` on this box today, and since this arm carries its
own control the parser is identical on both sides either way.

## Launch

`~/arc3-nosp/run_nosp_a424.sh`, `ARM=stripped` first, then `ARM=control`.

## Result

See `docs/trace-findings/2026-09-21-no-score-pressure-wide.md`.

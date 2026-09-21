<!--
Author: Claude Opus 5 (Bubba subagent)
Date: 21-September-2026
PURPOSE: Registry entry for the sk48 "act-first" diagnostic probe run on the Mac Mini on
21-Sep-2026. Records what it derives from, the three deliberate simultaneous changes it
carries, the endpoint quirk that made one of those changes possible at all, and the fence
that keeps its transcripts out of training.
SRP/DRY check: Pass -- harnesses/README.md requires one MANIFEST per variant; this is that
file. The per-action result and the verdict live in
docs/trace-findings/2026-09-21-sk48-act-first.md and are cited, not restated.
-->

# sk48-act-first — local Mac Mini diagnostic probe

**Not a benchmark arm, and not a controlled comparison.** It changes three things at once on
purpose, to find out quickly whether this model can ever play sk48. Do not quote its score
beside any held-out arm. See `docs/trace-findings/2026-09-21-sk48-act-first.md`.

## Why it exists

Four sk48 oracle runs on 21-Sep-2026 produced **zero game actions**. The model spent every
turn measuring the board and never committed a move. sk48 is the wrong game to measure: the
rod moves a fixed amount per press, the board is fully visible, and there is no randomness.
Measurement was not just wasted, it was the failure mode.

## Derives from

`harnesses/sk48-overfit/`, whose prompt patch and oracle injection are carried unchanged,
which in turn derives from arm O `harnesses/oracle-rules/`.

## The diff — three deliberate changes

1. **Act-first phase.** For the first ten environment actions: thinking off, a hard ceiling of
   one tool probe per turn plus one forced retry, one action per `action(...)` call, and a
   blunt "press a button NOW" retry on *both* non-acting paths (no-tool-call and
   python-ran-but-never-acted). After action ten, thinking and the default twelve-step probe
   budget return so the agent can study what its own moves did.
   The one-action-per-turn cap is load-bearing: without it the phase is trivially escaped by
   batching. It **reports the dropped actions back to the model** (`stop_reason:
   act_first_one_action_per_turn`). An earlier build dropped them silently and manufactured a
   miscount the model then reasoned from — see the findings doc.
2. **Efficiency pressure removed.** `GAME_OVERVIEW_ADDENDUM` lost the bullet scoring action
   efficiency as `min(human_actions/agent_actions, 1.0)` squared. Asking a model to experiment
   while telling it every action is expensive is a contradiction.
3. **Player framing.** The system prompt's opening line changed from "You are a coding agent
   solving a grid-based puzzle game" to a player learning the controls by pressing them.

**Change 2 has since landed on `main` independently.** While this probe was running, the Boss's
own prompt rewrite (plus the `no-score-pressure` arm) removed the efficiency bullet from
`GAME_OVERVIEW_ADDENDUM` on main. `patch/prompts.py.patch` was therefore deleted rather than
kept as a stale no-op; only `patch/tool_agent.py.patch` remains, taken against the
pre-probe file so it describes the whole arm regardless of what main has absorbed.

## The endpoint quirk that matters

`thinking_override=False` alone does **nothing** on this endpoint. `build_chat_payload` encodes
it as `chat_template_kwargs={"enable_thinking": False}` for provider `vllm`, and LM Studio
silently ignores that key: measured 21-Sep-2026, true vs false returned byte-identical
reasoning text and the same completion-token count. The knob LM Studio honours is
`reasoning_effort: "none"`, which zeroes reasoning and leaves tool-calling intact. The patch
sets it in `_chat_completion` rather than in `utils/openai_compat.py`, so no other arm's
payload changes. **Anyone porting a thinking-off arm to LM Studio must check this first** —
otherwise the arm silently never runs and its null is meaningless.

## Kept unchanged

The sk48 rulebook injection (`ARC3_ORACLE_RULES_DIR`, the same file the prior four runs used,
untouched since before them), the model and the already-warm LM Studio endpoint, the game
instance `sk48-d8078629`, and full per-turn capture of reasoning, tool calls, boards and
actions.

## Guard rails added

The solver's `not step_executed` branch is a bare `continue`, so a model that never acts is
retried forever — that is precisely how the four prior runs burned their budgets at action one.
`ARC3_ACT_FIRST_MAX_STALL` aborts after six consecutive non-acting turns so "it will not act"
becomes a reported finding instead of a silent multi-hour null. All act-first knobs default to
off, so an unset environment leaves every other arm byte-identical.

## Launch

`scripts/run_sk48_act_first_local.sh`. Per-action summary:
`scripts/summarize_sk48_act_first.py <run_dir>`.

## Contamination fence

Run dirs keep `-oracle-`, so `distill/extract_sft.py` refuses them with exit code 2 and no
override. These transcripts contain the answer key to sk48. Not renamed, not worked around.

## Repo state during this probe — read before reproducing

This arm was built and run while other agents were actively committing to the same repo. Two
consequences worth knowing:

- The act-first code in `inference/agent/tool_agent.py` was **committed and pushed to `main` by
  another agent** who swept the dirty working tree into their commits, despite the brief saying
  to keep it out of main. It was not committed deliberately here. It is behaviourally inert
  with the environment unset (`ARC3_ACT_FIRST_ACTIONS` defaults to zero), so it should not
  disturb other arms, but it is on main and someone should decide whether to keep it there.
- `prompts.py` was substantially rewritten on main mid-probe. Runs launched after that rewrite
  are **not** replications of the primary run and must not be compared to it.

## Next candidate, deliberately NOT changed here

`GAME_OVERVIEW_ADDENDUM` still carries the false-goal bullet warning that a value ticking up a
fixed amount per action cannot be the objective. In sk48 the rod *does* move a fixed amount per
press. That is the same anti-pattern as the HUD line the overfit patch already removed, and it
is the obvious single-variable arm to run next. It was left in because this probe was scoped to
three changes.

<!--
Author: Claude Opus 5 (Bubba subagent, label no-score-pressure-wide)
Date: 21-September-2026
PURPOSE: The "no score pressure" wide arm on gx10-a424 -- what was removed from the agent's
system prompt, why the existing baseline could not serve as its control, how both arms were
served and run, the per-game level progress, and a plain read on whether removing the
scoring and HUD material changed how the model plays.
SRP/DRY check: Pass -- the arm's registry entry, its patches and its launch scripts live in
harnesses/no-score-pressure/ and are cited, not restated. This doc holds only the run and the
verdict.
-->

# Taking the scoreboard away — the no-score-pressure arm on a424

**Status: IN PROGRESS.** Setup and method below are final and artifact-backed. Results and
verdict land when both arms finish.

## 0. The question

The agent's system prompt tells the model to optimise its own action-efficiency score, gives it
the exact scoring formula, and then in three further places tells it to be suspicious of
anything on screen that looks like a counter, timer or progress bar. A person playing these
games thinks about none of that. They press things and watch what happens.

So: **take that material out, tell the model it is playing a video game, and see whether it
plays differently.**

Not "does it score better" — one pass per game at temperature 1.0 on 25 games cannot answer
that, and this repo has already documented how much a single sample moves
(`2026-09-17-seed-variance-and-the-sb26-jackpot.md`). The question is behavioural: does it act
sooner, does it experiment, does it stop chasing or avoiding bars.

## 1. What changed — four deletions and one reframed line

Removed from `GAME_OVERVIEW_ADDENDUM`:

1. The action-efficiency bullet, carrying `min(human_actions / agent_actions, 1.0)` squared and
   the warning that "once a level is solved every extra action hurts sharply".
2. The "test for false goals" bullet — a HUD counter, timer or progress bar "cannot be the
   objective", and pursuing one is "the worst possible efficiency".

Removed from `VISUAL_GAME_ADDENDUM`:

3. "a long horizontal or vertical line near an edge is a timer or remaining-steps bar".

Removed from the python-tool guidance:

4. "After every action, verify whether ... only a timer, progress bar, or remaining-step bar
   moved."

And the opening system line became "You are playing a video game. You figure out the controls
and the rules by playing." instead of "You are a coding agent solving a grid-based puzzle game."

**Nothing was added.** No replacement rule, no hint, and in particular nothing telling the model
what a bar or strip on screen means in either direction. This arm is pure subtraction plus one
reframe, so that whatever moves can be attributed to the absence of the pressure rather than to
a new instruction.

**The reframe is not in `prompts.py`.** It lives in `inference/agent/tool_agent.py`. A patch
touching only `prompts.py` would have silently dropped half the arm.

### Two things deliberately left in

- The mechanical note that mid-run level completion shows up as a score increase. That is
  feedback the environment hands the player, not pressure to manage.
- The `VISUAL_GAME_ADDENDUM` line ending "classify it as HUD/timer state ... DON'T DO THIS!".
  This is a fifth HUD-vigilance instruction of the same family, and it was not in the specified
  removal set. It is present in **both** arms, so it is held constant and cannot confound the
  comparison — but it does mean this arm does not measure a prompt with *all* HUD coaching gone.
  Flipping that one line is the obvious next arm.

There is a third constraint worth naming: the world-model ledger the harness makes the model
fill in every turn has a field literally named `hud_map`. Both arms carry it. So even the
stripped arm is still prompted, structurally, to maintain a HUD map. The reframe can only go so
far while that field exists.

## 2. Why this arm had to run its own control

The obvious comparator was the existing a424 baseline, `r4w-a424-base-p1/p2`. **It cannot serve
as the control.** The tree it ran from (`~/GitHub/arc-3` on a424) is not a git checkout, so both
prompt files were hashed and diffed against clean repo HEAD rather than assumed. That tree
predates the current prompt: removals 1 and 2 above **do not exist in it at all**, and its
efficiency bullet reads only "Optimize for as few in-game actions as possible while still being
reliable." Subtracting something a baseline never had is not a measurement. It also covers only
the seven held-out games, not 25.

The 25-game baseline (`2026-09-16-qwen38-27b-baseline-result.md`) is on a108, on an older
harness, and this repo's own round-4W config carries the instruction "Do not compare numbers
across boxes."

So both arms were run here, back to back, on one server: `stripped` (the patched prompt) and
`control` (the prompt at `819b2260d`, unmodified). The prompt is the only variable.

## 3. Setup

- **Box:** `gx10-a424`, NVIDIA GB10, 121 GiB unified, aarch64.
- **Model:** stock `Qwen3.8-27B-BF16`, no adapter. The LoRA comparison is postponed and no
  adapter arm was run.
- **Server:** vLLM 0.19.0, one process serving both arms, `--seed 0`, qwen3 reasoning parser,
  hermes tool-call parser, prefix caching on, `--gpu-memory-utilization 0.85`, KV cache 191,296
  tokens, `--max-num-seqs 32`.
- **Run:** all 25 public duck games, one pass each, 25 lanes, 150-minute per-game wall,
  900-second analyzer timeout, temperature 1.0. The 25-game list is passed explicitly and in the
  same order to both arms, so a truncated arm still yields matched pairs.

### Taking the box over

An `sk48` overfit arm was occupying a424, decoding at roughly two tokens a second and timing out
its analyzer calls at 1800 seconds without completing a turn. It was superseded and could not
finish, so it was killed along with its server, and its cause was diagnosed rather than
inherited: it ran at `--gpu-memory-utilization 0.62` with prefix caching **off** and four
sequences. Raising utilisation, enabling prefix caching and batching 25 lanes took aggregate
throughput from about 3 tokens a second to a steady 27.5.

### Why the lane count and wall were chosen by measurement

Per-lane decode rate on this box is roughly flat at about 1.1 tokens a second whether 7, 16 or
25 sequences are in flight — the round-4W run recorded 9.15 aggregate over 7 lanes, a 16-lane
probe here gave 17.6, and 25 lanes gives 27.5. Batching raises aggregate, not per-lane. So
tokens-per-game is set by the wall alone, and running all 25 games in **one** wave rather than
two buys twice the wall for the same wall-clock. An initial 16-lane launch was discarded 13
minutes in for exactly this reason, and the run relaunched at 25 lanes with a 150-minute wall.

This is still a token-starved regime, around ten thousand generated tokens per game, and the
report below says so wherever it matters. It is what BF16 27B on a GB10 does; the a108 baseline's
much larger per-game budgets came from an NVFP4 copy that does not exist on this box.

### Contamination fence

The harness tree was copied from the sk48 overfit arm, whose oracle rulebook injection activates
off `ARC3_ORACLE_RULES_DIR`. The launcher explicitly unsets it, and the run logs were checked to
contain no `oracle rules loaded` line — a leak would have handed both arms the sk48 answer key.
The tree is otherwise byte-identical to clean repo HEAD across all 30 files under `inference/`
except `prompts.py`, which each arm overwrites at launch from a hashed variant. Run directories
deliberately do not carry `-oracle-`: this is not an oracle arm and stays eligible for SFT
extraction.

## 4. Not the same change that landed on `main`

While this arm was running, `ed5fd27e4` ("prompts: remove scoring pressure and gauge-suspicion
coaching") landed on `main` and edited the same material. **The two are different treatments.**
That commit removes more, and it **adds** a replacement line explaining that some displays report
moves left or the level, others are part of the puzzle, and one may show the arrangement to
produce. This arm is specifically barred from adding anything of that kind. It isolates removing
the pressure; `ed5fd27e4` tests removing it and explaining displays instead. Read separately.

Independently, that commit reframed the opening line to "You are playing a video game. You learn
the controls the way any player does: ..." — arrived at separately, near-identical in intent to
this arm's reframe.

## 5. A serving defect found while running this, which blocks every arm on this box

The first launch of the stripped arm produced **zero game actions in 25 games** and every game
sat on turn 1 retrying forever. That is not a model result. It is a tool-call parser mismatch,
and it is worth more than this arm is.

The server was started with `--tool-call-parser hermes`. **The model does not emit hermes
format.** It emits Qwen's XML:

    <tool_call>
    <function=python>
    <parameter=code>
    print(1+1)
    </parameter>
    </function>
    </tool_call>

Confirmed directly against the running server with a single three-hundred-token request and a
trivial tool definition: `finish_reason: stop`, **native `tool_calls`: zero**, the entire call
delivered as `content` text. Not inferred from the run — reproduced on demand.

Across all 27 answered turns of the voided launch, every single one logged
`tool_call_markup_in_text: yes` and `tool_calls_recovered_from_markup: yes`. The harness's
markup-recovery fallback rescued **100%** of them. That fallback is why the runs look like they
are working, and it is why this went unnoticed: turn 1 completes and looks healthy.

The damage shows on the **second** request of a turn, the one that carries the tool result back.
Request 1 returned for 25 of 25 games, short and clean, 327–499 tokens. Request 2 returned for
2 and timed out at the 900-second analyzer limit for the rest, each timeout costing about 1,220
seconds of the game's wall before the harness retried the turn from `action_count=0` — forever.
With the stop condition never recognised natively, the generation does not end where the tool
call ends.

This is the same signature the sk48 BF16 arm recorded and attributed to an uncapped output
budget (`2026-09-21-sk48-overfit-a424.md` §5.2). That arm used `hermes` too. The corrected
configuration proposed there — a larger `LOCAL_ANALYZER_MAX_OUTPUT` and a longer per-request
timeout — treats the symptom. **The parser is the cause.** The round-4W baseline on this box
used `qwen3_coder` and did issue actions, which fits.

`qwen3_coder` and `qwen3_xml` are both registered in this vLLM build (0.19.0). `qwen3_coder` is
the one the emitted markup matches and the one the round-4W baseline used.

The first launch is retained as `VOID-hermesparser-stripped` and no number from it is quoted.

## 6. Results

_Pending — see §8 on box contention._

## 7. Verdict

_Pending._

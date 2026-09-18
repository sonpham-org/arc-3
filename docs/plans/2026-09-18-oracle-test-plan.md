<!--
Author: Claude Fable 5.1 (Dr. Fable)
Date: 18-September-2026
PURPOSE: The oracle test. Hand the agent the actual rules of each public game and measure
whether it can then play. Splits the failure on the games we never clear into "cannot
generate the idea" versus "cannot execute the idea", which decides whether the next dollar
goes to harness vocabulary and probing or to training. Boss approved the test on 18-Sep and
ruled out the alternative (a genre menu in the prompt) as too likely to lock the agent into a
wrong frame. This is the plan to run it; nothing is built yet.
SRP/DRY check: Pass. The rulebook lives in arc-explainer and is fetched by
tools/fetch_explainer_games.py (PR #46); the harness variant rules live in harnesses/README.md;
the measurement rules live in trace-findings/2026-09-17-seed-variance-and-the-sb26-jackpot.md.
This holds only the experiment.
-->

# The oracle test: does the agent play when it is told the idea?

**Status:** plan, 18-Sep-2026. Approved by Boss. Not started.

## 0. The question

On the games we never clear (the slippery seven for the 27B: dc22, g50t, m0r0, sc25, sk48,
tn36, tr87), we do not know which of two things is wrong:

- **Idea generation.** The mechanic never enters the agent's head. Boss's own description of
  how he gets stuck: once someone tells him the idea he can execute it; the idea just never
  arrived. sk48 (ordered carriage), bp35 and lf52 (moving camera), g50t (rewind) are the
  canonical cases.
- **Execution.** The agent could not play the game even with the idea in hand: search,
  coordinates, multi-step plans, holding state across a level.

These need opposite investments. Idea generation is a harness problem: vocabulary, probing,
memory. Execution is a training problem. Every prompt arm to date has poked at the first
without ever measuring the second. This test measures both at once, on the public games only.

## 1. Why not a genre menu instead

Deleting "puzzle" from the prompt beat control (arm B). The obvious next step, telling the
agent it is playing "a video game" and listing genre possibilities, was proposed and **Boss
rejected it on 18-Sep**: a menu is a claim about the game, and a wrong claim locks the agent
into a wrong frame, the same failure the HUD rule and the 64x64 line caused. Arm C already
carries six possibility-phrased lines and is the one arm with a real signal; a longer list is
more risk for an unknown gain.

The oracle test comes first because it tells us whether more vocabulary is even the lever. If
the agent plays well when handed the rules, the whole game is idea generation and we know the
ceiling any vocabulary work could reach. If it still fails, no menu would have helped.

## 2. The arms

| arm | prompt | what it answers |
|---|---|---|
| **B** (control) | sparse-deletion, unchanged | the number to beat, re-run alongside so it shares the day |
| **O** (oracle) | B plus the game's full rulebook injected at the start of the run | can it execute when told everything |

One change between the arms: the rulebook text. Nothing else moves.

**Rulebook source.** `datasets/explainer-games/games.json`, produced by
`tools/fetch_explainer_games.py` from arc-explainer's `/api/arc3/dataset`. Per game, the
`newRules` of every level, concatenated in level order, rendered as plain sentences with the
level each rule starts on. No images, no Boss notes, no runs, no code citations: rules only.
Boss's play notes are a separate arm if this one moves; keep them out so the effect is
attributable.

**Injection point.** Not the frozen system prompt (built once, no game id). The first user
turn of each game, before the first frame, as a block headed "Rules of this game, from a
verified source." The implementer picks the exact hook in `tool_agent.py`; the requirement is
that the text is in context from action 1 and survives compaction (the compaction ledger
already carries `action_semantics` and `win_pattern`; the injected block must be re-sent or
pinned, not left to eviction).

**Per-level variant, later.** Injecting only the rules in force so far (levels 1..N) is more
realistic and is the second run if the full-rulebook arm moves. Full rulebook first because it
is the maximal "told the idea" condition and the cleanest split.

## 3. Games, model, box

- **Games:** all 25 public games. The slippery seven are the ones that answer the question;
  the other 18 show whether rules hurt games the agent already clears (a rulebook that lowers
  a score on a cleared game is a finding too). as66 excluded, always.
- **Model:** Qwen3.8-27B-NVFP4, the model being trained. The answer has to be about the model
  we are investing in, not Flash-Next.
- **Box:** a108, after the compact-reasoning multipass finishes (late 18-Sep). Not Kaggle:
  the weekly GPU quota is better spent on arms that could ship, and this is a diagnostic.
- **Passes:** four per arm, alternating B/O/B/O so time of day cannot bias it. Per-game cap
  as the multipass used (5,400 s). Roughly two days of box time for both arms.

## 4. The decision rule, written before the run

Measured paired by game, four passes, level clears first and score second, exactly as
`2026-09-17-seed-variance-and-the-sb26-jackpot.md` requires. No arm totals.

| result on the slippery seven | reading | next dollar goes to |
|---|---|---|
| O clears levels on most of the seven where B clears none | idea generation is the bottleneck | harness: probing protocol, memory, possibility vocabulary (with Boss's caution) |
| O clears on some, fails on others | split by game; write down which | both, game-class by game-class |
| O clears nothing B does not | execution is the bottleneck | training: demonstrations, then RL |

Secondary: on the 18 games B already clears, does O clear more levels or fewer? Fewer means
rulebook text is displacing the agent's own reading, and per-level injection is the fix.

Three things are not results: a single pass, an arm total, or any game whose four O passes
disagree with each other more than they disagree with B.

## 5. Contamination rules

- The public 25 only. The private set is untouched by construction.
- **Oracle transcripts never enter training.** They contain the answer key. Run dirs are named
  `*-oracle-*` and `extract_sft.py` is never pointed at them. Add the run-dir pattern to the
  distill README's exclusion list before the first run starts, not after.
- The seven held-out split games get rules too; they are being measured, not trained, so the
  fence in `datasets/splits/public25-train-test-split.json` is not breached.

## 6. Steps and owners

1. **Rulebook renderer** (harness track). Script reads `games.json`, emits one plain-text
   rulebook per game. Check three by eye against the pages on arc3.markbarney.net.
2. **Harness variant** `harnesses/oracle-rules/` per the README rules: copy of the arm-B base,
   env toggle `ARC3_ORACLE_RULES_DIR`, MANIFEST.md with the diff. Injection in the first user
   turn, pinned across compaction. Prompt-log check that the block appears exactly once per game
   in O and zero times in B, the same treatment-marker guard the multipass driver uses.
3. **Exclusion** added to the distill docs before any run.
4. **Driver**: reuse `run_style_multipass.sh` with the arm toggle swapped. Four passes, B/O/B/O.
5. **Analysis**: reuse `multipass_compare.py`; it already does paired per-game deltas with and
   without sb26.
6. **Write-up** in `docs/trace-findings/`, results against the table in §4, and the
   not-verified list.

Nothing on this list needs Boss.

## 7. Not decided here

- Whether rules go in as prose sentences or as the structured rule objects. Prose first; it
  is what a human would be told.
- Whether a third arm with Boss's play notes runs. Only if O moves.
- The per-level variant (§2). Only if O moves.

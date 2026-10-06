# Plan: put back the prompt parts our own line carried, one at a time, on the 28.94 notebook

Written 5-Oct-2026 by Bubba (Claude Opus 5.5) for the Boss and Son, at the Boss's request in #arc-3
(5-Oct 22:00 ET: "restore the winning parts that we had ... the parts from the system and the user prompt.
We need to look at what got lost and what we can be injecting").
Status: PLAN. Read-only research; nothing was run on a GPU, nothing submitted, no harness edited.


> **Correction, 5-Oct 23:40 ET (Boss: "read it again").** This plan was checked against the 28.94
> notebook, but our best is now Son's 31.63 notebook (`sonphamorg/arc3-daniel-sb-t06-toolfast-rs-hicache11-kq8-ct1`,
> shared 5-Oct, pulled to `~/bubba-workspace/arc3-kaggle/son-31p6/`). Diffed cell by cell: the harness patch is
> byte-identical, and the prompt flags are the same (border rule still off, memory sections off). It differs in
> two ways. **(1) The animation feed is gone.** So "the feed is still on" below is wrong for the 31.63 base,
> and the feed itself joins the lost list. **(2) Everything else Son added is speed**: an ARC hot-token map
> for the drafter, the tuned MTP drafter, temperature 0.6 (was 0.7), toolfast, 11 streams over 10 slots with
> a 32 GB host cache, and rejection sampling over the hot draft vocab. The instructions are identical, so the
> 28.94→31.63 difference is not from instructions; but both scores are single submissions and the unchanged
> Franzen code swings 27.6–31.5 on reruns, so the speed changes are NOT proven to be the cause either. Repeat runs decide. All candidates below should be tested against the **31.63** notebook.

## Bottom line first

- The 28.94 notebook (Son's "Daniel Noborder Animfeed Ftdraft CT1") sends **Daniel Franzen's prompts, not
  ours**. Moving to his base dropped every prompt line our 18.99 line had added, plus the prompt arms we
  measured in practice.
- **That move was a gain, not a loss: 18.99 went to 28.94.** Nothing we hold shows that a dropped line cost
  score. So the list below is an *inventory of candidates to re-add and test*, not recovered winnings.
- Most of what we measured was **inside run-to-run noise**. Only a few parts have any positive signal, and
  none is decisive. Two parts have evidence *against* restoring them (the carried labelled notes, and the
  attribution RULE lines).
- Six candidates are ranked below. Four can go in with **no code change** (one notebook setting, or text
  in the system-prompt prefix setting). Test each alone against the unchanged 28.94 notebook on the
  repeat-pass yardstick, several passes each, never promoted on one pass.
- Timing: prompt and harness changes have to be **frozen before Son's final training round**, because the
  model learns the harness it is trained in (the multi-harness lesson). So this testing belongs in
  Sprints 1-2 and stops at the Sprint 3 harness freeze.

## What was checked

| Source | What it gave |
|---|---|
| Son's 28.94 notebook (`~/bubba-workspace/arc3-kaggle/son-daniel-ct1/`, Kaggle `sonphamorg/arc3-daniel-noborder-animfeed-ftdraft-ct1`) | Its harness patch is byte-identical to Franzen's public notebook patch; its setup cell sets the prompt flags (listed below); its port cell turns the border rule off and adds the animation feed. |
| Franzen's GitHub tree (`da-fr/arc-agi-3-solution`, the patched Duck harness) | The patch reverse-applies cleanly, so this tree is what the notebook runs. The 28.94 system prompt was rendered from it with the notebook's exact flags. |
| `arc3-kaggle/prompt-diff-20261005/` (made earlier on 5-Oct) | Its "today" side is byte-identical to that render (checked), and its "sep30" side equals the 18.99 notebook's attested prompts (`prompt_arms/ste/original/EXPECTED_PROMPTS_1899.json`). |
| Arm records in `~/bubba-workspace/docs/` (15-Sep matrix, 23-Sep to 28-Sep arms, 1-Oct before/after and STE arms, 2-Oct post-mortem) and `kaggle/experiments/sparse-deletion/build_bundles.py` here | The texts of the arms and their results. |
| Franzen's WRITEUP.md and CONFIGURATION.md | What he measured himself, and which settings exist. |
| Provenance memory, project:arc3 | Cross-check of the arm results. |

The exact prompt texts are saved beside this file in `2026-10-05-restore-winning-prompt-parts/`:
`2894-system.txt`, `2894-first_user.txt`, `2894-user.txt`, `2894-retry.txt`, `2894-tool.txt`,
`2894-level-start-and-game-over.txt`, the same five surfaces for 18.99 (`1899-*.txt`), and the line diff
(`diff-1899-vs-2894.txt`).

## What the 28.94 notebook sends (short form)

Flags set in its setup cell that shape the text: level-transfer guidance on, action info on, frame-difference
hint on, diff image on, animation frames on, persistent functions (whole game, with imports) on, UNDO
exposed, **structured memory sections off**, tool output about 3,072 tokens. The port cell then turns
off the border rule and its prompt explanation, and turns on Son's animation feed (log mode).

| Surface | Where it is built | What it says, in brief |
|---|---|---|
| System prompt | `tool_agent.py` `_build_system_prompt` with `prompts.py` addenda | Game overview with Franzen's level-transfer line; long runtime-variable list; multimodal plus diff-image note; visual-game guidance with the bar line "do not get distracted by it"; action meanings with UNDO; Python guidance with the BFS/search lines, flag semantics ("count remaining budget into your plans") and the `frame_diff` description; tool-session rules with kept functions. No world-model lines. |
| First user message | `_build_user_prompt` | "No previous sequence has been executed yet", state, valid actions, then nine lines of tool reminders. |
| Per-turn user message | `_build_user_prompt` | What executed, the animation line, guard notes, "still on the same level", then the same tool reminders and "separate gameplay-object changes from HUD-only changes". No carried world model. |
| Level start | `LEVEL_START_USER_PROMPT` | "Start from the mechanics you established ... Inspect the new board for unfamiliar elements ... prioritize small, informative tests ... Reassess the goal". |
| Game over | `_build_user_prompt` | The BAR RULE diagnosis and "Do NOT re-submit this same series of moves". |
| Retry coaching | the follow-up prompt near `tool_agent.py:6983` | "You have not acted yet. Investigate first ..." and **still asks for `World model:` / `Goal model:` ... lines, although memory is off** (see candidate 6). |
| Tool description | tool schema | One paragraph of globals and `.segmentation`-first advice. |

Injection points that need **no code change**:
- **Any `ARC3_*` / `EXPOSE_*` flag** in the setup cell's `setup_env`.
- **`ARC3_SYSTEM_PROMPT_PREFIX`**: read at call time, put verbatim as the first lines of the system prompt.
  It can only **add** text; it cannot remove or replace a Franzen line. There is no matching hook for the
  user, level-start, retry or tool surfaces.

Anything else (replace a line, change the per-turn or retry text, add a stuck gate) needs an **anchored
text edit in a notebook cell**, the way Son's animation-feed cell already edits the copied bundle before
import (bundle dataset unchanged, but it is a code change), or a new hook.

## The lost list

Two buckets. Bucket A is what the 18.99 prompt actually shipped and 28.94 does not. Bucket B is arms that
only ever ran in practice and were never in a submission.

How to read the evidence: "pass" = one play of the game set. Same-prompt passes on the hard seven swing by
about three levels; on all 25 games by four or five. Anything smaller than that from one or two passes is noise.

### Bucket A — in the 18.99 prompt, absent or weakened in 28.94

**A1. Carried labelled notes.** 18.99, Python guidance:
> Keep your notes in reply text, outside the tool call, as labelled lines: `Goal model:` (goal hypotheses,
> each marked open, confirmed or refuted with the test that decided it), `Action model:` (what each action
> does, with the step that showed it), `Plan:`, and `Cross-level notes:` (rules likely to hold on later
> levels). The host carries these lines to later turns even after old history is trimmed; only
> `Cross-level notes:` survives a level change. Update them whenever a test decides something.

plus "Keep a compact world model: entities, action effects, likely goal, uncertainties, and shortest
reliable plan." and, in every user message, the carried block ending "End of carried world model."
- Plain words: the model writes short labelled notes and the harness re-inserts them every turn, so they
  survive trims.
- Evidence: only ever measured as part of the "hard-games fixes" bundle (notes + test discipline + hard
  budget). The three 29-Sep practice runs with that prompt and no honest restart cleared 101, 101 and 98
  levels against 99, 101 and 104 for the old prompt the same day: no gain, one run each. **Against it:**
  Franzen writes that switching the structured world model off entirely was his "largest improvement in this
  area" once context was larger; and our arm F (pinning the model's RULE lines in every message, 24-Sep)
  cleared 5.3 levels per pass against 7.2 for the unchanged prompt over three passes.
- Franzen covers it another way: larger context (the conversation keeps the evidence) and kept Python
  functions.
- Where: flag only (`ARC3_MEMORY_SECTIONS` on, or `slim`). **Not ranked for testing**: two independent
  negatives.

**A2. Test discipline.** 18.99, Python guidance:
> Test discipline: list goal hypotheses of different kinds (where things are, what is attached or in what
> order, what a counter or indicator shows) and run the cheapest test that tells them apart. Probe one action
> at a time from a known state and never batch opposite actions in a probe. A test refutes a hypothesis only
> if its setup held; otherwise mark it inconclusive. On a new level, anything that did nothing before is
> untested again. If objects move without your input, find what moves them before planning around them.
- Plain words: how to run a fair test, and two specific traps (things that did nothing may work on a new
  level; something moving on its own needs explaining first).
- Evidence: same bundle as A1, so no separate measure; that bundle alone showed no gain at test scale
  (one run each). The 18.99 submission carried it, but also the honest restart, tool fixes and a new model
  cut, so the 15.68 to 18.99 step cannot be credited to it.
- Franzen covers part: the level-start message says "prioritize small, informative tests" and the Python
  guidance says "If confidence is low, program a discriminating probe". **Not covered**: one action at a
  time from a known state, a test only counts if its setup held, "did nothing before is untested again",
  find what moves things on their own.
- Where: system prompt, **text only through the prefix setting** (the uncovered sentences only).

**A3. The bar as a hard budget.** 18.99, visual-game guidance:
> In many games, a long horizontal or vertical line near an edge is a move budget or remaining-steps bar. If
> it shrinks or fills once per action, measure its rate on each level and treat it as a hard budget: count
> the actions left, cost each plan in actions before running it, and expect running out to end the attempt
> until evidence shows otherwise.

28.94 has instead: "...a timer or remaining-steps bar ... do not get distracted by it or treat it as core
gameplay state unless there is concrete evidence that it interacts with the puzzle mechanics."
- Plain words: count the moves the bar allows and price every plan in moves before running it.
- Evidence: same bundle as A1, no separate measure.
- Franzen covers about half: his flag-semantics line already says "count remaining budget into your
  plans", and his game-over BAR RULE says a depleted bar means "reach the goal in fewer actions". **Lost
  half:** measure the bar's rate on each level and cost each plan before running it. 28.94 also contradicts
  itself today (one line says ignore the bar, another says count it).
- Where: system prompt. Adding through the prefix would leave the "do not get distracted" line in place,
  so the contradiction gets worse. Doing it properly needs an **anchored notebook-cell edit** that
  replaces Franzen's bar line.

**A4. Animation feed explanation.** 18.99, Python guidance:
> A long animation may pause a queued sequence and paste resized ASCII frames directly into the tool
> result. Similar long animations continue with a short reminder. If something moves during an action and
> returns before the board settles, the output says so; a settled frame that looks unchanged does not prove
> the action did nothing.
- Plain words: tells the model ahead of time that a long animation can stop its batch and print a small
  storyboard, and that "looks unchanged" is not "did nothing".
- 28.94 runs Son's animation feed (storyboards printed by `action()`, batch stopped) but **its system
  prompt never mentions storyboards**; the model learns it from the stop message the first time it
  happens. Franzen's transient-cells line covers "changed and changed back" for his own animation fields.
- Evidence: the feed itself was measured with this explanation present (Son, the old harness, ten
  animation-heavy games, four runs each, up from 31.4 to 38.9) and is already in 28.94. Whether the
  explanation adds anything on its own: never measured.
- Where: system prompt, **text only through the prefix setting**.

**A5. Search wording removed.** 18.99 ran with Son's search ablation on, which deleted the "IMPORTANT ...
write an explicit search algorithm such as BFS" and "stop probing and search in the inferred state space"
lines and "programs a small search or scorer" from the retry. 28.94 has all three back.
- Evidence: none in our records; this was Son's choice. Not a candidate until Son says what it was based on.

Covered by Franzen another way (no action): re-ground after a score increase (his level-start message),
"strategies may transfer loosely" (his level-transfer line), ACTION7 is undo (UNDO exposed and described),
game-over reading (his BAR RULE and "do not re-submit").

### Bucket B — practice-only arms that never reached a submission

**B1. Mechanics-possibility block** (arm C, 13/14-Sep, on the Tufa Duck harness, the same family Franzen
built on; Flash-Next). Appended to the game overview:
> - The visible board may be a window onto a larger world, and that window can move. If the whole scene
>   shifts at once, the frame moved, not the contents; the same row/col may not mean the same place as it
>   did last turn.
> - What you control may change. An action may hand control to a different object instead of acting on
>   the board, so do not assume there is exactly one controllable thing for the whole game.
> - State that decides the outcome may not be drawn on the board: what is being carried, what was
>   collected, or what happened on an earlier attempt can change what the same action does now.
> - Order can matter as much as position. A set of things in the right places may still be wrong if they
>   are read in a sequence.
> - Something that looks solved can come un-solved by a later action, and parts of the board may act on
>   their own between your actions, with or against you.
> - Control may be indirect: you may move something that drags what you care about, or set values that
>   are read together as a code rather than acting one at a time.
- Plain words: six kinds of hidden rule the public games really use, each stated as a possibility.
- Evidence: the best single prompt signal we have, and still not decisive. Seven games, four passes: arm C
  1.55 mean score against 0.86 for the control. **But C was stacked on arm B** (B deleted the word "puzzle",
  "64 x 64" and the two edge-strip warnings), and B alone scored 1.22. So the block's own step is about
  +0.33, roughly 1.4 standard errors, not the 2.9 the matrix doc's headline implies. On the bottom-seven
  passes the clears were control 10, B 15, C 16. The lines were written from mechanics in the public 25;
  the competition is scored on hidden games.
- Franzen covers a little: "New levels often introduce additional mechanics, sometimes through unfamiliar
  board elements." Not the six specific possibilities.
- Where: system prompt, **text only through the prefix setting**.

**B2. RESET offered when stuck** (arm G, 24-Sep, on Son's 7.36 harness): RESET listed only after 60
actions on a level with no progress, plus the user-message line "RESET is available now: it restarts the
current level from its starting state; levels already completed stay completed."
- Evidence: levels flat (7.3 per pass against 7.2, three passes against five). The one behaviour change of
  that day: RESET went from never used to used 14 times, sometimes right before a clear. The record called
  it the one change worth more passes.
- Franzen built an always-on version (`EXPOSE_RESET`: RESET described in the system prompt, must be the
  first action of a snippet) and left it **off** in the notebook. That is a different treatment from
  arm G's stuck gate.
- Where: **flag only** for Franzen's always-on version. Arm G's gated version would need a solver hook.

**Measured and not worth restoring** (each at or below its control, or inside noise): the Boss's full
prompt on Flash-Next (14 levels against 19 over two passes); removing the edge-strip warnings alone
(33 against 36 over five passes); attribution RULE lines (5.3 against 7.2 per pass); level-clear
debrief-and-prune (73 against 79 levels); picture-first board (5.3 per pass); board facts block (6.3 per
pass); answer key and streamer opener (no matched baseline; the 25-Sep trace study found no gain);
Simplified Technical English harness, video-game opener, stuck audit (all one pass, none above either
control pass); commit-to-hypothesis (arm F of 14-Sep, equal to its base B); glyph consonants, image-first
turn, ACTION7 round-trip (inside noise).

## Ranked injection candidates

Order: the cleanest test first (no code change), then evidence. Each is one arm against the unchanged
28.94 notebook, everything else identical.

| # | Candidate | Surface | Change needed | Evidence for | Why this rank |
|---|---|---|---|---|---|
| 1 | B1 mechanics-possibility block | system | prefix text only | +0.33 over its own base, about 1.4 SE, four passes, Duck harness; 16 vs 15 clears | Largest single prompt signal we have, same harness family, zero code. |
| 2 | B2 RESET exposed (Franzen's always-on) | system + actions | one flag, `EXPOSE_RESET=on` | Arm G: clear behaviour change, flat levels | Free to try; Franzen already wrote and guarded it. If it helps, arm G's gate is the follow-up. |
| 3 | A2 test discipline, uncovered sentences only | system | prefix text only | Shipped in 18.99; no separate measure | Zero code; targets the traps the hard games fall into. |
| 4 | A4 animation storyboard explanation | system | prefix text only | Feed measured with it present; line alone never measured | Zero code, short, removes a surprise the model meets mid-batch. |
| 5 | A3 bar as a hard budget, replacing Franzen's bar line | system | anchored notebook-cell edit | Shipped in 18.99; no separate measure | Needs code; also fixes 28.94's own contradiction. |
| 6 | Stale note requests removed (retry text and game-over "record ... in your world model") | retry, game over | anchored notebook-cell edit | None; consistency fix | 28.94 asks for labelled notes that nothing reads back, on every retry. Cheap clean-up, smallest expected effect. |

Prefix texts to use (exact, each arm alone):
- **Arm 1:** the six B1 bullets above, under the heading `Possible hidden mechanics (possibilities, not
  facts about this game):`.
- **Arm 3:** `Test discipline: probe one action at a time from a known state and never batch opposite
  actions in a probe. A test refutes a hypothesis only if its setup held; otherwise mark it inconclusive.
  On a new level, anything that did nothing before is untested again. If objects move without your input,
  find what moves them before planning around them.`
- **Arm 4:** `When an action produces an unusually long animation, the rest of the batch is stopped and a
  small storyboard of the animation is printed by action(); read its frames in time order before planning
  the next move. A settled frame that looks unchanged does not prove the action did nothing.`

The prefix lands above "You are a coding agent solving a grid-based puzzle game." That is the only place the
setting can put text. It also changes the cached prompt start, so first-turn cost moves slightly for every game.

## How to test (the repeat-pass yardstick, Sprint 1 item)

1. Control first: the unchanged 28.94 notebook, at least two passes on the hard games at competition timing,
   spread written down (the Sprint 1 yardstick item). No arm is judged before this exists.
2. One arm at a time, same games, same clock, same account and card, **at least three passes**; only the
   setup cell (flag or prefix) or one anchored cell differs. Check the rendered system prompt in the log
   matches the intended text before reading any score.
3. Promote only if the arm beats the control by more than the control's own pass-to-pass spread, on levels,
   and does not lose a game the control clears every pass. One pass never promotes.
4. Winners are combined only after each has won alone; the combination gets its own repeat passes.
5. Stop at the Sprint 3 harness freeze (Sun 25-Oct). Whatever prompt is chosen must be the one Son's final
   training round is run in.

## Not done / open

- No GPU run, no Kaggle push, no harness or notebook edit.
- The 28.94 per-turn, retry and tool texts are taken from the 5-Oct diff file's "today" side, which matched the
  rendered system prompt byte for byte; they were not rendered separately.
- Ask Son: why the search wording was removed in the 18.99 line (A5), and whether he has any repeat-pass
  numbers for the fixes prompt on its own.

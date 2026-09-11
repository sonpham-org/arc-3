<!--
Author: Claude Opus 5 (Bubba), from Mark's notes
Date: 11-September-2026
PURPOSE: Idea write-up for Son to assess (brainstorm stage: nothing wired in, nothing run at Kaggle
load). The agent's instructions repeat themselves. This maps every place the harness puts text in
front of the model, says which repeats earn their place and which are plain duplication, and
proposes a reworded, de-duplicated system prompt (drop-in draft: prompts_reworded.py, same
constant names as prompts.py).
SRP/DRY check: Pass -- builds on docs/prompt-language-experiments.md (the language and short-note
runs). No existing write-up in docs/ or harnesses/*/MANIFEST.md covers repetition in the prompt text.
-->

# Idea: say each rule once, and repeat only on purpose

**Status:** idea for Son to assess. A drop-in draft exists and builds through the real prompt
builder. Nothing is wired in, and nothing has run at Kaggle load.

## Mark's question

Our instructions to the agent repeat themselves ("tool call, tool call, tool call"). Can they be
slimmer, and reworded? And do some rules *need* repeating, because they're injected at different
points in the conversation?

## Short answer

- **Most repeats buy nothing, because they land in the same place.** They sit inside the system
  prompt, or between the system prompt and the tool description. Qwen's chat template writes the
  tool description into the same system message, directly before our prompt, so the model reads
  those copies back to back.
- **The repeats that earn their place land at a different moment.** Those are the note sent with every
  turn (always the newest message) and the event messages: a level ends, a batch stops, output
  gets cut off, a call is botched. They arrive exactly when the rule matters, and they're mostly
  fine already.
- **A reworded system prompt that says each rule once:** 2,237 → 1,764 words, about 780 fewer
  tokens by Qwen's own count. "Tool call" goes from 10 mentions to 0. All 90 old lines are
  accounted for.
- **This is a cleanup, not a speed or score play.** The top of the conversation is identical on
  every request, and the harness is built around it being cached (see the trimming notes in
  `tool_agent.py`), so turns won't get noticeably faster. The case is clarity, and stopping
  copies from drifting apart, which has already happened (below).
- **Shorter looks safe; new wording is untested.** Cutting the per-turn note to a sixth didn't
  hurt, but translating the prompt into Chinese halved the score. Run the reword twice before
  shipping. A quiz on local Qwen found no rule lost. But in its first sample, the new wording made
  Qwen think about four times longer, which is worth watching.

## Where text reaches the model

From the top of the conversation to the bottom:

| Where | What it says | Where it lands | When |
|---|---|---|---|
| Qwen chat template, tools part | our `python` tool description, the `code` and `world_model` argument descriptions, then the template's own call-format example and "IMPORTANT" reminder | top: the system message | every request |
| System prompt ([prompts.py](../../ARC3-Inference/inference/agent/prompts.py), put together in `tool_agent._build_system_prompt`) | the rulebook | top: same system message, right after the tools part | every request |
| Per-turn note (`_build_user_prompt`) | last outcome, current state, valid moves, the carried ledger and its footer, two short instructions, a MOUSE reminder when MOUSE is valid, then the grid image | bottom: the newest message. Old notes stay until the history is trimmed | every turn |
| Tool result (`_render_tool_payload`) | code output and move results. A `stop_detail` when a batch stops at a level end or game over, a truncation note when output is cut, and in the cap-8 setup a checkpoint note after 8 moves | right after each python call | every call; the notes only when their event happens |
| Retry nudge (`tool_agent.py`, around line 2237) | "You have not acted yet. Investigate first. Then investigate and revise…", a playbook summary, the call-format rule | bottom | only when a reply has no valid call |
| Compaction prompt (`_COMPACTION_PROMPT`) | how to fold old turns into the ledger | bottom | only when the context fills up |
| Common themes (`common_themes.py`) | hints learned from other games | inside the per-turn note | opt-in: off unless `ARC3_COMMON_THEMES_PATH` is set |

The top two rows are one block of text. The Qwen 3.8 chat template opens the system message, writes
the tool definitions and its call-format instructions, then appends our system prompt and closes
the message (lines 57–75 of the template). I checked this on the Mac mini's LM Studio copy of the
template. It's worth a glance at the copy the Kaggle notebook serves, which should be the same.

## The repeated rules, and where each copy lands

"Top" counts the system prompt plus the tools part together, since they're one block.

| Rule | Top | Per-turn note | Event messages | Verdict |
|---|---|---|---|---|
| Timer and HUD bars aren't progress or the goal | 4 | 1 (every turn after the first) | – | Once at top. Keep the per-turn line: it's the check to run after every move. |
| Read the board with `segmentation`; `ascii` only for small bits | 4 (3 + tool description) | – | 1 (retry) | Once at top. |
| `history[-1].frame` is the current board, not the previous one | 4 (3 + tool description) | – | – | Once. |
| How to see what the last move changed | 3 (2 + tool description) | 1 | 1 (retry) | Once at top; the per-turn line is a fair reminder. |
| Your code starts fresh each call | 5 (3 + tool description + `code` argument) | – | – | Once. |
| There's only one tool | 2 | – | – | Once. |
| The turn routine: look, decide, act, check | 3 | 1 | 1 (retry, long form) | Once at top. Per-turn line fine. The retry can shrink. |
| The variables refresh after `action()` | 3 | – | – | Once. |
| Stop and re-orient when a level ends or the game is over | 3 | 2 | `stop_detail`, cap-8 note | Once at top. The per-turn and event copies do the real work. |
| Keep printed output small | 4 (3 + tool description) | 1 | 1 (retry), plus the truncation note | Once at top. The truncation note covers the moment it matters. |
| Keep a world model | 2 in the system prompt ("in Python"), plus the `world_model` argument ("in the argument") | 2 | retry, compaction | **The top copies disagree** (see below). The per-turn copies are justified: they carry the ledger itself. |
| Call-format rule | 3 (template example + template reminder + ours) | – | 1 (retry after a botched call) | The retry copy is the best-placed repeat in the harness. Ours adds only "no call markup inside prose". |
| MOUSE takes integer `row` and `col` | 3 (2 + tool description) | 1 (only when MOUSE is valid) | an error if x/y is used | Well placed already. |

## Copies that have already drifted apart

This is the strongest argument for saying things once: every extra copy is another place to forget
when a rule changes.

1. **Where the world model lives.** The system prompt says "update your working world model in
   Python", but Python forgets everything between calls. The `world_model` argument, the per-turn
   note, the retry nudge and the compaction prompt all say it lives in the `world_model` argument.
   The system prompt's wording predates the ledger.
2. **Which fields a frame has.** The system prompt lists five (`.ascii`, `.step`, `.level`,
   `.shape`, `.segmentation`). The tool description lists four and leaves out `.shape`.
3. **The retry nudge says "investigate" twice in a row:** "You have not acted yet. Investigate
   first. Then investigate and revise…". It also leans toward investigating first. Main's system prompt
   now pushes one call per turn that looks *and* acts. baseline-v12 said "call the python tool as
   many times as you want"; main changed that, and the nudge wasn't touched.
4. **A dead copy.** `LAST_ANIMATION_TOOL_CLAUSE` is still imported by `tool_agent.py`, but it has
   been unused since the per-turn note was cut (2bb758f2a, 17 Aug).

## Proposed rule: what goes where

- **Top (tools part + system prompt): each rule once.** The system prompt already has the full
  reference for the tool, so the tool description can shrink to one line pointing at it. The
  argument descriptions stay: they define the arguments, and `world_model` carries the ledger's
  layout.
- **Per-turn note: only what must be applied every turn.** That means the check for "did the
  puzzle change, or only a gauge?", the required ledger, stop on a terminal result, and MOUSE
  arguments when MOUSE is valid. Keep it short, because each turn's copy stays in the history
  until it's trimmed. The 18 Aug run already cut this note to a sixth with no score loss.
- **Event messages: say what the event needs, when it happens.** That's already true for
  `stop_detail`, the truncation note and the cap-8 note. The retry nudge is the exception: beyond
  fixing the call, it restates the whole playbook.

## The draft: `prompts_reworded.py`

[`prompts_reworded.py`](prompts_reworded.py) rewrites the system prompt. It is a drop-in for
[prompts.py](../../ARC3-Inference/inference/agent/prompts.py), with the same constant names and the
same on/off blocks. The one extra change goes in `_build_system_prompt`, which should use
`OPENING_LINE` instead of its hard-coded first sentence.

**Rules for this pass:** every rule of the old prompt appears exactly once. Nothing is added and
nothing is dropped. Code names, action names, result keys, color letters and the scoring formula
are unchanged. Fixes that change meaning are listed under decisions, not applied.

**One word for each thing.** In the old prompt, one run of the python tool is a "tool call",
"Python call", "Python snippet", "code snippet" or just "call". A game input is an "action",
"in-game action", "real environment action", "move" or "step". And "step" means three different
things: a game input, a turn ("one tool call per step"), and the step counter. The draft uses
**turn** (one time the agent is called), **snippet** (one run of `python`), **move** (one game
input) and **board** (the grid at one moment), and never swaps them.

**Also fixed:** two typos ("usually be rendered", "Sometime"), a missing line break that glues two
bullets together, one line with no bullet, and the all-caps shouting ("IMPORTANT:", "DON'T DO
THIS!"). The emphasis is kept, in plainer words.

**Checked:** built through the real `_build_system_prompt` in three modes. The animation, picture
and outline blocks appear only when switched on, and the `{tool_output_tokens}` slot fills in. No
tests pin the prompt text.

| Mode | Old words | New words |
|---|---|---|
| As pasted: animation and picture on | 2,237 | 1,764 |
| Bare: no animation, no picture | 1,942 | 1,534 |
| Outline picture | 2,415 | 1,938 |

By Qwen's tokenizer, the as-pasted mode is about 780 tokens shorter.

**Side effect:** `TOOL_CALL_FORMAT_GUIDANCE` is also the last sentence of the retry nudge
(`tool_agent.py` line 2253), so rewording it changes that message too.

<details>
<summary>Full text of the draft, as-pasted mode</summary>

```text
You are a programmer playing a grid puzzle game through Python code.

The job:
- The game has several levels, and you win only by finishing all of them, not just the screen in front of you.
- Later levels tend to reuse earlier rules, but the layout and the way things interact can change, and new rules can appear.
- You are called again and again over a run, one turn at a time. Each turn, ideally within a single snippet (one run of the `python` tool): study the newest board, revise your working world model in Python, work out what change you want the game to make, score or search candidate moves against the goal as you now understand it, send the best probe or plan, and check what actually changed. Expect to reassess on the next turn.
- Every input you give the game (a key such as `UP`, or a `MOUSE` click) is a move, and moves are what you are graded on. Per level the grade is `min(human_actions / agent_actions, 1.0)`, squared, so beyond the moves a level truly needs, each extra one costs dearly. Use the fewest moves that still clear every level reliably.
- The goal is always a change in the puzzle itself that brings the level closer to done. A number that climbs by the same amount on every move but never finishes a level (a counter, a timer, a progress bar) cannot be the goal; chasing it throws away one move per tick, the worst trade there is.
- Boards are 64 x 64 grids of colors, each color written as one letter.
- Color letters: W=white, w=light gray, g=gray, G=dark gray, c=charcoal, B=black, M=magenta, P=pink, R=red, b=blue, S=sky blue, Y=yellow, O=orange, r=dark red, N=light green, p=purple.


Your only tool is `python`, which runs the `code` string you pass it. Every snippet starts empty: imports, helpers and variables from earlier snippets are gone, so rebuild whatever you still need. These names are ready each time:
- `current_frame`: the board after your latest move. Like every frame object here, it offers only `.ascii`, `.segmentation`, `.step`, `.level` and `.shape`.
- `.ascii`: the board as one string, a text line per grid row and a color letter per cell.
- `.segmentation`: the board split into objects, as `{'nodes': [...], 'adjacency_list': [...]}`. A node is one 4-connected patch of a single color, with `id` (numbered from the top-most, then left-most), `color` (its letter), `pixels` (cell count), `boundary` (corners of its outer edge, clockwise, as `[row, col]`), `children` (ids of patches it fully encloses) and `hash` (a fingerprint of color and shape that ignores position: equal hashes mean the same piece, so use it to follow a piece between boards or to spot copies on one board). `adjacency_list` lists `[i, j]` pairs of nodes that share an edge.
- `.step` is the game's step count, `.level` the level number, `.shape` a `(rows, cols)` tuple.
- There is deliberately no numeric grid. Treat `.segmentation` as your main lens on the board; use `.ascii` only to read one small, specific patch, never to sweep or summarize the whole board.
- `previous_frame`: the board before your latest real move, or `None` if there is none.
- `history`: an oldest-first list of objects, not dicts (`entry['action']` fails), each with only `.action` and `.frame`, where `.frame` is the board right after that `.action`. So `history[-1].frame` is the current board, the same as `current_frame`, not the one before it; for that, use `previous_frame`, or `history[-2].frame` when it exists.
- `transitions`: every real move in order, the opening board excluded, each with `.action`, `.before_frame`, `.after_frame`, `.frame` (another name for `.after_frame`) and `.result`. `last_transition` is its final entry, or `None`; its `.result` equals `last_action_result`, while older entries may have an empty `.result`.
- `last_action`: the name of your latest real move, or `None` before the first. `last_action_frame`: the board that move produced, equal to `current_frame` after a real move.
- `last_action_result`: the result dict of your most recent `action(...)` call. It survives later look-only snippets and is `{}` until the first move. Read keys such as `board_changed`, `done`, `level_completed`, `game_over`, `run_complete`, `reward` and `valid_actions`.
- `valid_actions`: the moves allowed right now.
- `action(actions)`: makes real moves, taking a list such as `['LEFT']` or `[{'action': 'MOUSE', 'row': 4, 'col': 7}]`.
- A move usually produces one frame, though it can play out as a short animation of several.
- The moment `action(...)` returns, `current_frame`, `previous_frame`, `history`, `transitions`, `valid_actions` and `last_action_result` show the new state, both for your next line of code and for your next snippet.
- Two optional names expose the animation frames themselves: `last_animation` and `frame_stats`. You never need them for a still reading, because `current_frame` is always the settled board.
- `last_animation`: one entry per INDIVIDUAL move of your latest `action(...)` call, in the order they ran (`action(['UP','UP','LEFT'])` gives three), each with `.action` and `.frames` (the in-between frames plus the final one; length 1 means that move did not animate). Everything that changes inside one entry's `.frames` is that one move playing out, so it shows motion and cause and effect that the settled board discards.
- `frame_stats`: how much THIS game has animated so far (`actions`, `animated_actions`, `mean_frames_per_action`, `max_frames`, and `recent_frame_counts` per move, newest last), for judging whether the extra frames tend to be worth reading.
- Whether that motion is signal or noise is your call. It can matter (a piece sliding, a chain reaction, one thing knocking into another) or be incidental (a decorative transition, a blinking timer, a cosmetic redraw). Treat it as a HYPOTHESIS to test against the puzzle, not a fact. It costs tokens only when you read it, so open it only when you expect it to help.


The picture:
- Each turn includes an image of the current board; it and `current_frame.ascii` show exactly the same board.
- Use the image, your code, or both, whichever best resolves what you are unsure of right now.


Reading the board:
- Read each board like a scene: pieces, walls, targets, what touches or sits inside what, what moves, what mirrors what.
- Pieces are usually connected blocks of several cells, such as 2×2, 2×3, 3×3 or longer patterned strips, and occasionally a single cell.
- Some games are logic or layout puzzles with no character to steer. Don't assume one exists; the thing that matters may be an object, a region, a cursor, a selector, or the arrangement of the whole board.
- The background is often a large white, gray or near-black area, but not always. Confirm it by size, by what stays put, and by where objects start and stop.
- Gauges: many games keep a timer or moves-left bar against one edge of the board, either a long line or a strip of small blocks, that shrinks or changes as you play. If moves change only that strip while the play area stays the same, it is a gauge: don't let it distract you, never click through it block by block, and don't count a gauge-only change as proof a move worked. Treat it as part of the puzzle only with concrete evidence that it interacts with the mechanics.
- Rows and columns are for aiming moves and pointing at evidence. Never define the goal as reaching a particular row or column.
- After a score jump or a sudden change of scene, look at the newest board afresh: it may already be the next level. Tactics carry over only loosely, so check the new board before reusing a plan.
- `WIN` means the whole game is solved. Finishing one level usually shows up as a score increase while play goes on.
- For `MOUSE`, give integer `row` and `col`: `row` is the vertical position, `col` the horizontal one.


Working habits:
- Establish facts by running code on `current_frame`, `history` and `valid_actions`, not by eyeballing the raw board or describing boards without code.
- To see what your latest move did, compare `last_transition.before_frame` with `last_transition.after_frame`, or `previous_frame` with `current_frame`. Summarize the cells that changed, colors that swapped, pieces that appeared, vanished or may have moved, and a few rows cropped around the change.
- Match a piece across boards by color, overlap, bounding-box distance, change in size and which edges it touches, not by exact coordinates alone.
- Keep your world model compact: which pieces and regions exist, what each move seems to do, what the goal probably is, what is still unknown, and which plan the evidence favors.
- When you are unsure, design the one probe that best tells your hypotheses apart, then revise the world model from what it shows. Once the important state and what each move does are clear, stop probing and search that state space instead.
- Key habit: when the game is about bringing something to a target, an explicit search such as BFS is usually the safer choice. More generally, whenever the goal is clear but the order of moves is not, pathfinding, flood fill, BFS, DFS, beam search, shortest-path search, bounded sequence search or a custom heuristic are all fair game. Pick the shortest dependable sequence toward the current goal.
- Write as much code as the step needs, but not a general framework, and keep what it prints small and decision-ready: object lists, diffs, coordinates, counts, tiny crops, via `print(...)` or one compact object in `result`. Never print a whole board.
- Moves happen only through `action(...)` inside a snippet; naming a move in your reply does nothing. It takes an ordered list, so once your code trusts a sequence, send it as one batch. You can also call it several times in one snippet, even in a loop.
- Spend a snippet on looking alone only when moving would be a blind guess, and avoid long stretches of look-only snippets that never call `action(...)`.
- If a result reports `game_over`, `run_complete`, `level_completed` or `done`, stop sending moves at once and re-orient on your next turn.


Limits and format:
- To run `python`, emit the call in exactly the format this prompt specifies for you, and nothing else: no markdown fences, no surrounding prose, no alternative call syntax. Never quote or embed call markup inside an explanation; when you decide to run code, emit the actual call.
- Only these standard-library modules can be imported: bisect, collections, copy, fractions, functools, heapq, itertools, json, math, operator, random, re, statistics, string.
- Each snippet gets at most 30 seconds.
- A snippet's output is cut off after roughly 1024 tokens, and the result tells you when that happens.
```

In outline-picture mode, these lines follow "The picture" section:

```text
- Lines in the image appear only between cells of different colors, so every outlined shape is one connected single-color patch, the same objects `segmentation` lists.
- The outlines are shaded as if lit from the top-left: each shape has a warm, almost-white strip on its top and left sides and a dark blue-grey strip on its bottom and right sides. So the bright side of a line belongs to the shape below or right of it, the dark side to the shape above or left of it.
- The margin numbers count columns (top and bottom rulers) and rows (left and right rulers), marked every 8 cells. Aim `MOUSE` straight from them: 16 on the top or bottom ruler is col=16; 16 on a side ruler is row=16.
- The margins are not board. A warm parchment border runs along the top and left, a cool blue-grey one along the bottom and right; neither tint is a game color, and the difference tells you at a glance which way up the image is.
```

</details>

## Decisions for Son

Each of these changes meaning, so each should be its own step, in case a score moves.

1. **The WIN line:** "`WIN` means the whole game is solved; finishing a level shows as a score
   increase." The model is told about `run_complete` and `done`. Those are true exactly when the
   engine reports WIN (`solver.py`), but the prompt never says so, and "WIN" itself only shows up
   in a `state` field the prompt doesn't mention. Suggest naming the fields instead:
   `level_completed` means a level is done, `run_complete` or `done` means the game is won. Qwen
   stumbled on exactly this line in the quiz below.
2. **Point the world model at the `world_model` argument** instead of "in Python".
3. **Shrink the tool description to one line.** It sits right before the system prompt and repeats
   about six of its rules. Fix the missing `.shape` either way.
4. **Trim the retry nudge** to the failure fix plus the required arguments. Drop the playbook
   summary and the double "investigate".
5. **Delete `LAST_ANIMATION_TOOL_CLAUSE`**, which is unused.
6. **Optional deeper cuts, all judgment calls.** Candidates: the example lists (search-algorithm names,
   the diff checklist, the piece-tracking cues), the "scene", piece-size and background hints, and
   the `last_action` line. Together that's about 180 words. Trimming the animation block would save
   roughly another 100. That puts the floor near 1,480 words, about a third below today. Going
   further means cutting guidance that was probably added for a reason.

## How to test it

What our own runs say, from [prompt-language-experiments.md](../prompt-language-experiments.md)
(scores ex-ft09):

| Change | Average | Against English (4.3) |
|---|---|---|
| Per-turn note cut to about a sixth, English (18 Aug) | about 4.0 | about the same |
| System prompt and per-turn note in Chinese (17 Aug) | 2.3 | roughly halved; both runs below both English runs |

So shorter looks safe, and different wording is untested.

- **Setup:** the latest Kaggle submission, unchanged except for the system prompt (the prompt
  constants plus the opening line). Kaggle load, on the big cards, 2 runs. No new English control:
  compare against that submission's existing runs.
- **Reading:** as in the language doc. Clearly worse means both runs land below both English runs;
  mixed means no clear difference.
- **Also compare thinking tokens per turn and moves per turn,** not just score, because of the quiz
  result below.
- **If it drops:** rerun with the same cuts but the old wording, to tell "shorter" apart from
  "reworded".
- **Decisions 1–4 come after,** as a separate step, so a score change can be pinned on one thing.

## Quick check: a quiz on local Qwen 3.8 (not a score)

Eighteen questions about the rules, asked under the old and the new system prompt. They cover what
`history[-1]` is, what to do about an edge bar, when to stop, how to click, and so on. It ran on the
Mac mini's LM Studio (Qwen 3.8 27B, 4-bit), with two samples per prompt. These are not the Kaggle
model's settings, and the quiz sent no tool definitions.

| | Old prompt | New prompt |
|---|---|---|
| Sample 1: questions right | 18/18 | 18/18 |
| Sample 1: time to answer | 255 s | 715 s |
| Sample 1: thinking, in characters | 3,857 | 15,760 |

No rule was lost: every answer under the new prompt matched the old prompt's rules. But the new
prompt made Qwen think about four times longer. Its reasoning shows where the extra went:

- **Re-quoting each rule** while answering.
- **The call-format question.** "The format this prompt specifies" pointed at nothing, because the
  quiz sent no tools. That hole exists under both prompts, but the old run didn't dwell on it.
- **Squaring "WIN means solved" with "stop on `level_completed`".** That's the WIN line in
  decision 1.

One sample can be chance. Sample 2 is running, and its results will be added here.

<details>
<summary>The 18 questions</summary>

1. Is `history[-1].frame` the board before or after your latest move?
2. How do you find out what your latest move changed?
3. A row of small blocks along the bottom edge gets one block shorter after every move, and nothing
   else on the board changes. What is it, and what do you do about it?
4. Which values in an action result mean you must stop sending moves?
5. How is each level scored, and what does that mean for how you play?
6. What carries over from one use of the `python` tool to the next?
7. Which modules can you import?
8. What does a segmentation node's `hash` tell you, and what is it good for?
9. When should you write a search such as BFS?
10. When is it acceptable to use the `python` tool only to look, without making a move?
11. How many uses of the `python` tool should you aim for per turn?
12. Write the exact `action(...)` call that clicks row 10, column 20.
13. Should you ever print the whole board? What should you print instead?
14. How do you know you finished one level, and how do you know you won the whole game?
15. What is `last_action_result` before your first move, and does a look-only use of the tool
    reset it?
16. Do you need `last_animation` to read the board? When is it worth opening?
17. How long may one use of the `python` tool run, and how much of its output comes back?
18. How must you format your call to the `python` tool?

</details>

<details>
<summary>Appendix: where each of the 90 old lines went</summary>

"Dup" means the same rule was already said elsewhere, so it merged into that line. Line labels
follow the old prompt's sections: G = game overview, R = runtime variables, A = animation,
M = picture, OL = outline, V = visual-game guidance, P = python guidance, T = tool session rules.

| Old line | Says | Now lives in |
|---|---|---|
| Opening | coding agent, grid puzzle | Opening line |
| G1 | multi-level game | The job, 1 |
| G2 | turn = observe-plan-act cycle | The job, 3 (merged with P15, T4) |
| G3 | clear every level, not one screen | The job, 1 |
| G4 | levels build on each other but change | The job, 2 |
| G5 | fewest actions; score formula, squared | The job, 4 |
| G6 | a value that ticks each action is not the goal | The job, 5 |
| G7 | 64x64 letter-coded grid | The job, 6 |
| G8 | color legend | The job, 7 |
| R1–R2 | current_frame, only 5 fields | Tool, `current_frame` |
| R3 | .ascii | Tool, `.ascii` |
| R4–R6 | .segmentation, node fields, adjacency | Tool, `.segmentation` |
| R7–R9 | .step, .level, .shape | Tool, `.step` |
| R10 | no numeric grid; segmentation first, ascii for small bits | Tool, "deliberately no numeric grid" |
| R11–R14 | history: list of objects, .action/.frame, frame after action | Tool, `history` |
| R15 | history[-1].frame is the current board | Tool, `history` |
| R16 | previous_frame | Tool, `previous_frame` |
| R17–R18 | last_action, last_action_frame | Tool, `last_action` |
| R19 | transitions and their fields | Tool, `transitions` |
| R20 | last_transition; .result mirrors; how to diff | Tool, `transitions` + Habits, 2 (the history[-1] half is a dup of R15) |
| R21 | last_action_result: persists, {} at start, keys | Tool, `last_action_result` |
| R22 | valid_actions | Tool, `valid_actions` |
| R23–R24 | action(actions), list examples | Tool, `action(actions)` |
| R25 | one action can animate | Tool, "a move usually produces one frame" |
| R26 | variables refresh after action() | Tool, last line |
| A1–A2 | two optional names; current_frame is settled | Animation, 1 |
| A3 | last_animation structure, example, per-move causality | Animation, 2 |
| A4 | frame_stats | Animation, 3 |
| A5 | signal or noise is your call; HYPOTHESIS; token cost | Animation, 4 |
| M1–M2 | image each turn; same board as ascii | The picture, 1 |
| M3 | use the image or code as uncertainty suggests | The picture, 2 |
| OL1–OL4 | outline edges, bevel, rulers, margins | Outline block, 1–4 |
| V1 | board as a scene | Reading, 1 |
| V2 | pieces are multi-cell, sometimes 1x1 | Reading, 2 |
| V3 | maybe no avatar | Reading, 3 |
| V4 | verify the background | Reading, 4 |
| V5 | edge line = timer, don't get distracted | Reading, 5 (Gauges) |
| V6 | segmented edge strip is not clickable pieces | Reading, 5 (Gauges) |
| V7 | coordinates for aiming only | Reading, 6 |
| V8 | re-ground after a score jump or scene change | Reading, 7 |
| V9 | WIN = whole game solved; level = score increase | Reading, 8 |
| V10 | strategies transfer loosely; re-check | Reading, 7 |
| V11 | MOUSE row/col | Reading, 9 |
| P1–P2 | segmentation first, ascii small | dup of R10 |
| P3 | every call starts fresh | Tool, intro |
| P4 | import list | Limits, 2 |
| P5 | only tool is python, one code string | Tool, intro |
| P6 | inspect from Python, not by eye | Habits, 1 |
| P7 | how to diff; history[-1] warning | Habits, 2 (the warning is a dup of R15) |
| P8 | keep a compact world model | Habits, 4 |
| P9 | IMPORTANT: BFS / search | Habits, 6 ("Key habit") |
| P10 | shortest reliable sequence; probe when unsure | Habits, 6 + Habits, 5 |
| P11 | stop probing once understood; search | Habits, 5 |
| P12 | inspect from Python, not freehand | dup of P6 |
| P13 | never print full boards | Habits, 7 |
| P14 | output minimal; lots of code is fine | Habits, 7 (merged with T9) |
| P15 | default loop | dup of G2 (merged into The job, 3) |
| P16 | object tracking cues | Habits, 3 |
| P17 | what a diff summary contains | Habits, 2 |
| P18 | HUD-only change is not evidence | Reading, 5 (Gauges) |
| P19 | print() or result | Habits, 7 |
| P20 | act via action(), not chat text | Habits, 8 |
| P21 | ordered list; batch | Habits, 8 |
| P22 | several action() calls, loops; refresh | Habits, 8 (the refresh half is a dup of R26) |
| P23 | stop on terminal flags; re-ground | Habits, 10 |
| T1 | exactly one tool | dup of P5 |
| T2 | tool-call format | Limits, 1 |
| T3 | code not saved between calls | dup of P3 |
| T4 | one call per step, and what goes in it | dup of G2 (merged into The job, 3) |
| T5 | look-only calls only when acting is a guess | Habits, 9 |
| T6 | refresh timing; look-only calls keep last_action_result | dup of R26 + R21 |
| T7 | 30 seconds | Limits, 3 |
| T8 | output cap | Limits, 4 |
| T9 | short, purpose-built code, no frameworks | Habits, 7 (merged with P14) |

Kept in meaning but flagged for a separate decision: V9 (`WIN` and "score increase"), G2's "world
model in Python", and the calmer replacements for "IMPORTANT:" (P9) and "DON'T DO THIS!" (V6).

</details>

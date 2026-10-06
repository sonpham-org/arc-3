<!--
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: Plan and record of the Spark runner's prompt dedup (Astra's notes, approved by the Boss in #arc-3 at 17:07 ET):
  every instruction the runner's prompts carried, whether it is standing or per-turn, where it went, every duplicate
  that was removed, the old and new texts side by side, and the duplicate check on the real rendered requests.
  Code: tools/spark_runner/prompt_profiles.py (the "dedup" profile), dupcheck.py, render_requests.py; page:
  docs/mode-explorer.html, docs/static/js/{mode-explorer,mode-library,spark-runner}.js,
  docs/static/data/prompt-profiles.json; modes: docs/static/data/modes.json and the site's mode store.
SRP/DRY check: Pass - this file documents; the texts in its appendix are copied from the runner's own renders
  (docs/static/data/prompt-profiles.json), which are the source.
-->

# Prompt dedup for the Spark runner (6-Oct-2026)

## Scope and decisions

- **Spec (Astra, approved by the Boss 17:07 ET):** no duplicated instruction anywhere in what the model receives. Every
  standing instruction lives in the system prompt, once. The user message carries only this turn's information and the
  selected mode's instructions. Mode instructions say only what changes that turn. This is the normal behaviour for
  every mode, Stock included. The optional "Lean" toggle and the "Stock (lean)" mode are removed.
- **How:** a prompt profile applied by the runner at run time, never an edit of Franzen's bundle:
  `tools/spark_runner/prompt_profiles.py`, profile **dedup** (default for every job, harvest too). The previous behaviour
  stays selectable as **original**, only so results from before today stay interpretable and can be re-run like for
  like. Every job and sample records its profile (`prompt_profile` in spec, job and result; a job queued before the
  profiles existed is stamped with the default when its first sample starts, with the time).
- **Harness hooks used (all on the agent instance or the tool_agent module, after any checkpoint restore):** system
  prompt (`agent._system_prompt`), tool schema (`_PYTHON_TOOL_DESCRIPTION` and the `code` parameter description),
  per-turn message (the runner's existing `_build_user_prompt` hook filters the harness's own lines; nothing is
  rebuilt), retained-function line (`_retained_function_context`), tool-result stop details
  (`_terminal_action_stop_detail`), retry nudge and image captions (`_append_context_message`), yielded turns
  (`ARC3_YIELD_RESUME_PROMPT=state_only`, the harness's own option), carried history (old turn messages in a rebuilt
  snapshot or older checkpoint get the same per-turn treatment; assistant messages are never touched).
- **Checkpoint safety:** checkpoints stored the system prompt with the agent's state, so a restore could have handed a
  job another profile's system prompt. `_system_prompt` and the profile's wrappers are now in
  `checkpoints.AGENT_SKIP`, and the profile is installed after the start is in place. Checkpoint meta records the
  profile; an exact start's first-request comparison says which profile the saved request was built with.
- **Flags:** the dedup system prompt is written for the 31.63 notebook's flag set (Son's and Franzen's wordings; they
  differ by one line, the `board_changed` / `gameplay_changed` note, which the dedup prompt keeps conditionally).
  `check_flags()` refuses to run dedup under any other flag set rather than describe tools the harness is not running.
- **Edge-bar contradiction resolved:** the original said both "a bar near an edge is a timer; do not get distracted by
  it or treat it as gameplay state" and "count remaining budget into your plans" and, on a death, the BAR RULE. The
  dedup prompt reads it one way throughout: the bar is HUD, not a puzzle object and not progress, AND it is the step
  budget, to read and plan within; a death is a budget death only if the bar is (almost) fully depleted in the death
  frame.

## Inventory: where every original instruction went

Original system prompt (Son's wording; Franzen's adds one line), by section. "→" is where it is now; "dup of" marks
an instruction already said elsewhere, which now exists once.

| Original (section: instruction) | Kind | Now |
|---|---|---|
| Role line | standing | system, first line |
| Overview: multi-level game; clear every level | standing | system "Game and goal" |
| Overview: each turn an observe-plan-act cycle | standing | system "Game and goal" (merged with the per-turn "Focus on what changed" line) |
| Overview: levels build on earlier mechanics | standing | system "Game and goal", merged with the level-start paragraph's guidance |
| Overview: fewest actions while reliable | standing | system "Game and goal"; dup of Python guidance "shortest reliable sequence" |
| Overview: 64 x 64 grid, colour legend | standing | system "Board representations" |
| Runtime: `current_frame` and its five fields (said 3x: system twice, tool schema) | standing | system "The `python` tool" globals line, once |
| Runtime: `.ascii`, `.segmentation`, node fields, adjacency | standing | system "Board representations" |
| Runtime: raw numeric grid not exposed (also per-turn line, tool schema) | standing | system "Board representations", once |
| Runtime: segmentation primary, ascii only for a small region (said 5x: runtime, Python guidance twice, tool schema, every turn message) | standing | system "Board representations", once |
| Runtime: `history` list, attributes, `history[i].frame` after `history[i].action` | standing | system "History and frame comparisons" |
| Runtime: `history[-1].frame` is the current board (said 5x: runtime twice, Python guidance, tool schema, every turn message) | standing | system "History and frame comparisons", once |
| Runtime: `previous_frame`, `transitions`, `last_transition`, refused action | standing | system "History and frame comparisons" |
| Runtime: compare `previous_frame` to `current_frame` (said 4x incl. tool schema, every turn message) | standing | system, once |
| Runtime: `last_action`, `last_action_frame` | standing | system globals line |
| Runtime: `last_action_call_result` (also Tool session: inspection calls do not clear it) | standing | system "Actions", merged |
| Runtime: after automatic RESET; `automatic` flag; RESET keeps last call result | standing | system "Actions" and "Step budget and deaths" |
| Runtime: `valid_actions`; call `action(actions)`; list format | standing | system globals line and "Actions" |
| Runtime: an action can animate (said 2x) | standing | system "History and frame comparisons", once |
| Runtime: refreshed after `action()` (said 2x incl. Tool session) | standing | system "Actions", once |
| Runtime: animation result, `last_animation_frames`, `last_animation_timeline` | standing | system "History and frame comparisons" |
| Multimodal: current grid image, same frame as ascii, use either | standing | system "Board representations" |
| Multimodal: diff image and how it is drawn (also in every diff caption) | standing | system once; caption keeps only "Diff image (step a -> b):" |
| Visual guidance: scene, entities, no avatar, backgrounds | standing | system "How to play well" |
| Visual guidance: edge bar is a timer, do not get distracted; segmented strip is HUD | standing | system "Step budget and deaths", merged with the budget reading (contradiction resolved) |
| Visual guidance: coordinates only to target | standing | system "How to play well" |
| Visual guidance: `WIN` means solved | standing | system "Game and goal" |
| Action meanings: directions, SPACE, MOUSE row/col (MOUSE said 4x: actions, Runtime list example, tool schema, every turn message), UNDO | standing | system "Actions", once |
| Python: variables reset (said 2x) | standing | system "The `python` tool", once |
| Python: importable modules | standing | system "The `python` tool" |
| Python: only tool is `python` (said 3x: Python guidance, Tool session, every turn message) | standing | system, once |
| Python: inspect from Python, not by eye (said 2x) | standing | system, once |
| Python: shortest reliable sequence; discriminating probe | standing | system "How to play well" |
| Python: BFS and search (said 2x in one bullet) | standing | system "How to play well", one sentence |
| Python: stop probing and search | standing | system "How to play well" |
| Python: never print full boards; compact output (said 3x incl. every turn message, tool schema "print(...)") | standing | system "The `python` tool", once |
| Python: strong default loop; object tracking; frame-diff summaries | standing | system "How to play well" |
| Python: after every action, gameplay vs HUD change (said 3x: Python guidance, Tool session, every turn message) | standing | system "Step budget and deaths", once |
| Python: call `action()` inside Python (also every turn message) | standing | system "Actions", once |
| Python: batching (also every turn message) | standing | system "Actions", once |
| Python: several `action()` calls per snippet (also every turn message) | standing | system "Actions", once |
| Python: stop on `game_over`/`run_complete`/`done` | standing | system "Actions" (now also `level_completed`, which the harness stops on) |
| Python: flag semantics; deaths from action or budget; count budget | standing | system "Actions" (flags) and "Step budget and deaths" |
| Python: `frame_diff` and its fields | standing | system "History and frame comparisons" |
| Tool session: one tool (dup) | standing | removed (said in system once) |
| Tool session: tool-call format (also every turn message, every retry nudge) | standing | system "The `python` tool", once |
| Tool session: retained functions, dependencies | standing | system "The `python` tool" |
| Tool session: call as many times as needed; do not ration | standing | system "The `python` tool" |
| Tool session: 30-second limit; output cap | standing | system "The `python` tool" |
| Tool session: short snippets | standing | system "The `python` tool" |

Per-turn message (the harness's `_build_user_prompt`), every line:

| Original line | Kind | Now |
|---|---|---|
| "The code executed N actions..." / "Executed actions: ..." | per-turn fact | kept |
| Animation line ("animated over N frames ...") | event | kept; its closing "`last_animation_timeline` shows them." / "Whatever this action did is visible only there - read ... before concluding it failed." / "Those cells are in neither history[-3] nor history[-2] ..." moved to the system prompt |
| No-op and stale-state guard notes (Franzen's flags) | event | kept; "Do not count submitted or executed actions ... re-locate from current_frame." moved to system |
| "You are still on the same level." / "You have completed the run!" | per-turn fact | kept |
| Level start: three paragraphs of LEVEL_START_USER_PROMPT | event + standing | event kept as one line ("You cleared the previous level. `current_frame` now shows the starting board of the new level."); the two paragraphs of guidance moved to system "Game and goal" (they also duplicated the system's level-transfer line) |
| GAME OVER paragraph (what a game over is, which history frame is which, the BAR RULE) | event + standing | event kept as one line ("GAME OVER during the previous sequence: this attempt failed and the level was automatically reset to its starting board (completed levels are kept)."); the explanation moved to system "Step budget and deaths" (it also duplicated the flag semantics) |
| "The game over occurred immediately after action X. Apply the BAR RULE above ..." | event + standing | "The fatal action was X." |
| Per-action trace of the previous sequence | event | kept |
| "Do NOT re-submit this same series of moves ..." | standing | system "Step budget and deaths" |
| "No previous action sequence was captured." / "No previous sequence has been executed yet." | per-turn fact | kept |
| "Current state: step N, level L." / "Valid actions right now: ..." | per-turn fact | kept |
| "Only tool: `python`. It receives ..." | standing (dup) | removed; system |
| "Only letter-coded board views ...; raw numeric color IDs are not available." | standing (dup) | removed; system |
| "Keep tool output compact: ..." | standing (dup) | removed; system |
| "For the most recent change, compare ..." | standing (dup) | removed; system |
| "Use Python to inspect the evidence from the newest history, and search or score ..." | standing (dup) | removed; system "Game and goal" / "How to play well" |
| "Focus on what changed most recently in `history` ..." (first turn: "Ground yourself in `current_frame` ...") | standing | system "Game and goal" and "What each turn message contains" |
| "When ready, call `action(actions)` from inside the `python` tool ..." | standing (dup) | removed; system "Actions" |
| "You may call `action(actions)` more than once ..." | standing (dup) | removed; system "Actions" |
| Tool-call format sentence | standing (dup) | removed; system |
| "If you use MOUSE, include integer row and col arguments." | standing (dup) | removed; system "Actions" |
| Retained functions: "Your retained functions ...: f(a), g(b). These are your previous definitions ... revise them ..." | per-turn fact + standing | the list kept; the caveat moved to system. Not repeated on a resumed turn (the opener above lists them) |
| "Your retained functions remain available from previous levels. Check level-specific assumptions ..." | event + standing | first sentence kept; the check moved to system |
| Image captions (diff, death frame, fatal step diff) | per-turn label + standing | the label kept ("Diff image (step a -> b):"); how the image is drawn said once in system; "inspect the budget bar here for the BAR RULE" moved to system |
| (new) "Instructions for this turn (<mode> mode):" + the mode's instructions | per-turn | last text of the message, before the images; absent for Stock |

Other texts:

| Original | Kind | Now |
|---|---|---|
| Tool schema description (globals, frame fields, `history[-1]`, diffs, MOUSE, raw grid, segmentation, print) | standing (all dup) | "Run one Python snippet against the preloaded game state; the system prompt describes the globals and `action(actions)`." |
| `code` parameter: "The snippet is ephemeral and is not saved across tool calls." | standing (dup, and contradicts retained functions) | "Python code to run." |
| Retry nudge: event sentence + world-model paragraph + tool manual + tool-call format | event + standing | event sentence kept, then "Call the `python` tool now." |
| Yielded turn: a full copy of the turn message (`ARC3_YIELD_RESUME_PROMPT` "full", the default) | per-turn dup | the harness's "state_only" resume: one continuation sentence, "Nothing has been executed since the turn opener above ...", the board image |
| Tool-result stop details ("... GAME_OVER (attempt failed; the run is NOT finished) ... Cause is either ...") | event + standing | the reason only ("No further actions were executed: that action ended the attempt (GAME OVER); the level is reset before your next turn.") |
| Level-start and game-over texts | see per-turn table | |

## Mode instructions: old vs new

Each built-in mode was rewritten to only what changes that turn (a new version in the site's store, history kept). The
same text is used with both wordings. Removed from every mode: the "Mode: X." prefix (the runner's header names the
mode), references to the BAR RULE, and Franzen-wording lines that restated the tool manual or the budget advice.

| Mode | Before (lines added to Stock; Son's / Franzen's extra line) | Now (both wordings) |
|---|---|---|
| Stock | (none) | (none) |
| Probe | Mode: PROBE. This turn is for learning, not for winning. Take one or two actions only, each chosen to answer one specific question about the rules or the objective of this level. Before acting, write the question and what each possible outcome would tell you. After acting, say in one line what you learned. — Franzen's adds: Probe one action at a time from a known board state and read its effect with `frame_diff(last_transition.before_frame, last_transition.after_frame)`. Do not batch a route this turn. | This turn is for learning, not for winning. Take one or two actions only, one at a time, each chosen to answer one specific question about the rules or the objective of this level; do not batch a route this turn. Before acting, write the question and what each possible outcome would tell you. After acting, say in one line what you learned. |
| Hypothesize | Mode: HYPOTHESIZE. Write one concrete hypothesis about the goal or a mechanic of this level, in one line. Then predict what the board will look like after your next action or short batch if the hypothesis is true, and what it would look like if it is false. Take that action (at most three), then say whether the prediction held. — Franzen's adds: Compute the predicted change in Python before calling `action(actions)`, then check it against `frame_diff(previous_frame, current_frame)`. | Write one concrete hypothesis about the goal or a mechanic of this level, in one line. Then compute in Python what the board should look like after your next action or short batch if the hypothesis is true, and what it would look like if it is false. Take that action (at most three), then say whether the prediction held. |
| Execute | Mode: EXECUTE. The plan is set; carry it out as efficiently as possible. Do not re-derive the rules or explore. Compute the full action sequence in Python and submit it in one `action(actions)` call. Stop and re-ground only if a result shows an unexpected change, a level change or a game over. — Franzen's adds: If the bar at the board edge is a step budget, count the actions your sequence needs against what is left before you submit it. | The plan is set: carry it out as efficiently as possible. Do not re-derive the rules or explore this turn. Compute the full action sequence in Python and submit it in one `action(actions)` call. Re-ground only if a result shows an unexpected change, a level change or a game over. |
| Re-examine | Mode: RE-EXAMINE. Before acting, restate your current hypothesis about the goal and the mechanics in one or two lines. List the evidence from `history` that supports it and anything that does not fit. If something does not fit, revise the hypothesis. Then take at most two actions that test its weakest part. — Franzen's adds: Pull the evidence with Python from `transitions` rather than from memory of earlier turns. | Before acting, restate your current hypothesis about the goal and the mechanics in one or two lines. List the evidence from `transitions` that supports it and anything that does not fit, pulled with Python rather than from memory of earlier turns. If something does not fit, revise the hypothesis. Then take at most two actions that test its weakest part. |
| Challenge | Mode: CHALLENGE. Assume your current hypothesis about the goal is wrong. State it in one line, then give the strongest different explanation that fits everything seen so far, including what you have been ignoring. Name one action whose result would differ between the two, and take it (at most two actions). Do not continue the current plan this turn. — Franzen's adds: Check in Python which elements of `current_frame.segmentation` your current plan never touches; the alternative should explain at least one of them. | Assume your current hypothesis about the goal is wrong. State it in one line, then give the strongest different explanation that fits everything seen so far, including board elements your current plan never touches. Name one action whose result would differ between the two explanations and take it (at most two actions). Do not continue the current plan this turn. |
| Recover | Mode: RECOVER. Before any move, say in one line what ended the last attempt: the fatal action or the budget, decided with the BAR RULE above. Then name the change to the plan, made before the fatal point. Take at most three actions this turn, and not the fatal action from the same board state. — Franzen's adds: Compare `history[-3].frame` to `history[-2].frame` with `frame_diff` in Python to find the fatal cell before you decide. | Before any move, say in one line what ended the last attempt: the fatal action or the step budget. Then name the change to the plan, made before the fatal point. Take at most three actions this turn, and not the fatal action from the same board state. |
| Level start | Mode: LEVEL START. List in one line each the mechanics from the previous level you expect still to hold, then each element on this board you have not seen before. Spend this turn testing the newest element, one action at a time, at most three actions. — Franzen's adds: Compare this board with the previous level's starting board in Python to list what is new. | List in one line each the mechanics from the previous level you expect still to hold, then each element on this board you have not seen before. Spend this turn testing the newest element, one action at a time, at most three actions. |
| Stock (lean) | Stock with the four tool-call reminder lines left out | removed (hidden in the store, history kept): every mode now leaves every standing line out |

## Duplicate check on the real rendered requests

`tools/spark_runner/render_requests.py --check-all` runs each case as a real job (`sample.main`: the harness, the
start, the profile, the mode slots) with a scripted stand-in for the model, so it reaches every kind of turn a game
meets and keeps every request body the runner would post:

1. first turn, an inspect-only snippet that reports 3000 generated tokens, so the turn yields;
2. the resumed turn, which plays the first action of the level's recorded winning line;
3. a turn whose reply has no tool call, so the harness sends its retry nudge;
4. the rest of the winning line, so the level is cleared;
5. the level-start turn, which submits one action repeated in a long batch to run out the step budget;
6. the turn after the game over.

Each case runs the mode queue Probe, Execute, Level start, Recover, Hypothesize, Re-examine, Challenge, so mode blocks
appear on every kind of turn (`datasets/spark-runner-prompt-dedup/slots.json`). `dupcheck.py` checks the WHOLE request
each time: the tool schema, the system prompt and every user and tool message. It looks for the same sentence twice
(exactly or nearly), a standing sentence repeated in a message, a sentence repeated inside one message or across
messages (per-turn facts such as the state line are allowed to recur across turns), and the same standing instruction
in different words (27 instructions, each with a pattern for all its original wordings). Tool messages are checked
on the harness's own fields only.

Cases: carried starts of every kind (exact checkpoints bp35 level 2, cd82 level 3, ft09 level 3; rebuilt snapshots
with their conversation rebuilt from transcripts lf52 level 3, ls20 level 4, ka59 level 3 Franzen's wording; fresh game
sk48 level 1) and No-context starts (lf52 level 3 both wordings, ls20 level 2, ft09 level 1 Franzen's, cd82 level 4,
wa30 level 2). Every case reached all six kinds of turn except the two lf52/ka59 Franzen's-wording runs, where the
batch no-op guard stops the death batch early, so their sixth request is an ordinary turn.

| Profile | Cases | Requests checked | Same sentence in the standing text | Standing sentence repeated in a message | Repeated inside a message | Repeated across messages | Same instruction, other words | Result |
|---|---|---|---|---|---|---|---|---|
| dedup | 13 | 78 | 0 | 0 | 0 | 0 | 0 | all clean |
| original | 13 | 78 | 156 | 3,329 | 0 | 1,324 | 1,465 | every request has repeats |

Full results: `datasets/spark-runner-prompt-dedup/dedup-checks.json`. The original profile is byte-identical to what
the runner sent before today (checked: a No-context first request against the old code's render, and the first
request after restoring the exact checkpoints for bp35 level 2 and cd82 level 3 against the saved requests: only the
stand-in model name differs).

What dedup sends, measured on the same lf52 level 3 render: system prompt 13,739 characters (was 18,274), tool
schema description one sentence (was about 900 characters), first turn message 3 lines plus the image (was 13 lines). A
resumed turn now re-opens with one sentence and the board instead of a full copy of the turn message.

## Page

- Prompts view: "What the model receives" in three labelled parts: 1 System prompt (read-only, the same for every
  mode), 2 This turn (the user message as the harness fills it in, read-only; a real example per kind of turn), 3 Mode
  instructions (the end of the same user message, the only part a mode sets). "Full prompt" is gone. "Preview
  request" asks the runner for the exact first request Play would send for the game, level, wording and context chosen
  in the Queue view, rendered by the real harness with no model, and shows every message in order with the mode's
  instructions marked and the runner's duplicate check of that request.
- Mode editor: the same three parts; the instructions box is the only editable text (one text for both wordings);
  Preview request with the unsaved text. The lean switch and wording tabs are gone.
- Play row: a select keeps "Original prompts (old runs)"; default Dedup. Results: every job carries a "dedup prompts"
  or "original prompts" chip; the carried Stock tally line and each job's "vs stock" figure say they were measured with
  the original prompts until fresh dedup Stock runs exist; the No-context Stock pool counts only jobs of the same
  profile.
- Data: `docs/static/data/prompt-profiles.json` (system prompts per wording, tool schema, example turn messages per
  profile, rendered by `render_requests.py --page-data`); `system-prompts.json` removed. `modes.json` built-ins carry
  `instructions`; Stock (lean) removed.

## TODO / status

- [x] Inventory and classification (above)
- [x] dedup profile in the runner, default for every job; original kept; profile recorded per job, sample, checkpoint
- [x] Lean flag and Stock (lean) removed (runner, site store, page)
- [x] Duplicate check on real rendered requests: dedup clean in every case and request
- [x] Page: three parts, preview, profile labels, Stock-tally caveat
- [x] Site store: built-in modes saved as new instruction-only versions; Stock (lean) hidden (history kept)
- [x] Runner deployed with a backup while no Play sample ran; quick live check
- [ ] Fresh Stock baselines with the dedup prompts once Cletus is back (the old Stock numbers used the original prompts)

## Appendix A: the dedup system prompt (Son's wording)

Franzen's wording adds the `board_changed` / `gameplay_changed` line under "Actions".

```text
You are a coding agent solving a grid-based puzzle game.

Game and goal:
- The game has several levels. Your job is to clear every level, not just the current screen, in as few in-game actions as you can while staying reliable. `WIN` means the whole game is solved.
- You are called once per turn. Each turn is one observe-plan-act cycle: re-understand the newest frame (focus on what changed most recently and update the target change you are after), update your working model in Python, choose the best next action or short sequence against the goal as you currently understand it, execute it, and re-evaluate next turn.
- Levels usually build on mechanics learned in earlier levels, especially the most recent one. When a new level starts, build a new plan for its board rather than continuing the previous level's sequence. Carry the established mechanics forward as a starting hypothesis instead of rediscovering them, re-check anything new evidence contradicts, and inspect the board for unfamiliar elements or arrangements: new elements often bring the mechanics needed for the level, so test them with small, informative probes. Reassess the goal: it may stay the same and need the new mechanics, or it may change.

What each turn message contains:
- What your previous sequence executed and any events since (game over, level cleared, guard stops, animations), the current step and level, the valid actions right now, the functions you have retained, and images of the board. On a game's first turn there is no previous sequence: ground yourself in `current_frame` with a compact structural summary rather than restating the frame.
- Some turns end with instructions for this turn only, under a mode name. Follow them for that turn; where they differ from the general guidance here (for example a smaller action budget), they win.

Board representations:
- A board is a 64 x 64 grid of letter-coded ARC colours. Legend: W=white, w=light gray, g=gray, G=dark gray, c=charcoal, B=black, M=magenta, P=pink, R=red, b=blue, S=sky blue, Y=yellow, O=orange, r=dark red, N=light green, p=purple. Raw numeric colour IDs are not available.
- Each turn message attaches an image of the current grid; it and `current_frame.ascii` are the same frame. A diff image shows the cells that changed since your previous turn in their new colour, with unchanged cells dimmed to a dark navy that is not a game colour. After a game over two more images follow: the death frame (read the budget bar there) and a fatal-step diff image (last alive frame to death frame, drawn like the diff image). Use the images and the Python views together, whichever helps with the current uncertainty.
- `.segmentation` is your primary view of a frame. It returns `{'nodes': [...], 'adjacency_list': [...]}`. Each node is one 4-connected same-colour object with `id` (ordered top-most, left-most), `color`, `hash` (colour and shape, ignoring position AND rotation: equal hashes mean matching shape up to rotation, not the same object), `rotation` (degrees clockwise from the canonical orientation: 0/90/180/270, reduced to 0/90 for 2-fold symmetric shapes, `None` for fully symmetric ones), `rotational_symmetry` (1, 2 or 4), `pose_hash` (rotation-sensitive), `shape_hash` (colour-independent pose shape), `pixels` (cell count), `boundary` (clockwise outer-perimeter corner points as `[row, col]`) and `children` (ids of objects fully enclosed by this one). `adjacency_list` holds `[i, j]` pairs of objects that share an edge.
- `.ascii` is the frame as one newline-delimited string. Use it only to read a small, specific region; never scan or summarise the whole board with it.

The `python` tool:
- `python` is your only tool. Call it with one `code` string, in exactly the tool-call format shown elsewhere in this prompt for this model: no markdown fences, prose wrappers or other tool-call syntax, and never tool-call markup inside explanatory text. When you decide to call the tool, emit the call itself.
- Globals, refreshed for every call: `current_frame`, `previous_frame`, `history`, `transitions`, `last_transition`, `last_action_call_result`, `last_action` (the name of the most recent real action, or `None`), `last_action_frame` (its post-action frame), `last_animation_frames`, `last_animation_timeline`, `valid_actions`, `frame_diff(before=None, after=None)` and `action(actions)`. Every frame view exposes only `.ascii`, `.segmentation`, `.step`, `.level` and `.shape` (a `(rows, cols)` tuple).
- Python variables reset between calls. Eligible functions you define are retained for later calls throughout this game, including across level changes, and cleared when a new game starts; call them directly and redefine one to change it. A retained function's dependencies must also be available next call: pass snippet-specific data as arguments; use builtins, the provided globals, other retained functions, and explicit top-level imports (restored with the function) or imports inside it; plain top-level definitions without decorators or annotations, literal defaults. Tool results report which functions were retained and why any was rejected. A retained function is your earlier definition, not proof that it is correct: revise it when new evidence contradicts its assumptions, and after a level change check its level-specific assumptions against the new board before reusing it.
- Importable standard-library modules: bisect, collections, copy, fractions, functools, heapq, itertools, json, math, operator, random, re, statistics, string.
- Each call has a hard limit of 30 seconds. Tool results are capped at about 3072 tokens and say when they were cut.
- Output: print compact, decision-oriented summaries (object lists, diffs, coordinates, counts, tiny local crops) with `print(...)`, or assign a compact final object to `result`. Never print or echo whole boards. Writing a lot of code is fine; keep its output short. Keep snippets purpose-built rather than whole frameworks.
- Call `python` as many times per turn as you need, until your code has a clear probe or plan; reading and computing cost no in-game actions. Do not ration calls while the state is unclear: inspect `current_frame`, `history` and `valid_actions` from Python rather than reasoning about the board by eye.

History and frame comparisons:
- `history` is a chronological Python list of entries with `.action`, `.frame` and `.result` (attributes, not dict keys); `history[i].frame` is the board after `history[i].action`. `history[-1].frame` is the CURRENT board, the same as `current_frame`, not the previous one.
- `previous_frame` is the board before the most recent real action (`None` if there is none). `transitions` lists the real actions after the initial frame, each with `.action`, `.before_frame`, `.after_frame` (alias `.frame`) and `.result`; `last_transition` is the last of them or `None`. A refused action creates no transition.
- For the most recent change, compare `previous_frame` to `current_frame`, or `last_transition.before_frame` to `last_transition.after_frame`. Comparing `history[-1].frame` to `current_frame` compares the board with itself.
- `frame_diff(before, after)` compares two frames (defaults: `previous_frame`, `current_frame`) and returns `changed_cell_count` and the lists `moved`, `rotated`, `appeared`, `disappeared`, `changed_color` and `resized`; unchanged objects are omitted. It matches same-colour 4-connected components, so one game object may be split in several and touching same-colour objects may merge; with several similar components the matching can be wrong. `moved` entries that also turned carry `rotated_by` (degrees clockwise); `rotated` is rotation in place. `changed_color` needs identical cells with a new colour and gives `at`, `pixels`, `before_color`, `after_color`, `before_hash`, `after_hash`. `resized` covers same-colour components with overlapping footprints whose size changed, budget bars and backgrounds included (`at_before`, `at_after`). `appeared` and `disappeared` give `bbox` as `[r0, c0, r1, c1]`. Example: `frame_diff(history[-3].frame, history[-2].frame)`.
- One action can play a short animation; `current_frame` is its final frame. When the last executed action of your latest call animated, `last_action_call_result['animation']` gives `frames`, `transient_pixels` and `transient_bbox`: cells that changed and changed BACK, which appear in no other frame. `last_animation_frames` holds that action's frames as views (index 0 first, the last one the settled board; after a death they are the FATAL action's frames, not the reset's); crop their `.ascii` yourself. `last_animation_timeline` is a dict with `action`, `frames` and `steps`, one entry per step that changed anything, each with `step`, `changed`, `bbox`, and either `changes` (`old>new @ (row,col)`) or `transitions` (counts per colour change). Reading them costs no action; they are empty when nothing animated. An action that animated but left the board area unchanged still did something: read its animation before concluding it failed.

Actions:
- Use only the actions valid right now. `UP`, `DOWN`, `LEFT` and `RIGHT` are directional controls; what they move depends on the game. `SPACE` performs a game-specific action (interact, select, rotate, attach/detach, execute): test it rather than assume. `MOUSE` clicks a cell: pass integer `row` and `col` fields from 0 to 63, zero-based from the top-left, `row` downward and `col` rightward (x/y fields are rejected). `UNDO` reverses a previous action, usually the last turn; check what it restores. It cannot undo a game over.
- Execute actions only by calling `action(actions)` inside Python, never as text in your reply. It takes an ordered list such as `['LEFT']` or `[{'action': 'MOUSE', 'row': 4, 'col': 7}]` and returns `last_action_call_result` (batch totals, executed and skipped actions, stop reasons; `{}` before any call), which stays available, across turns too, until the next action call. After it returns, every global is refreshed before your next statement.
- Once your code has found a reliable sequence, batch it in one call. You may call `action(...)` several times in one snippet, including in a search or control loop.
- If a result reports `game_over`, `level_completed`, `run_complete` or `done`, stop acting in that snippet; the next turn shows the new state.
- Results are flags: `game_over` = this attempt FAILED (it never means the run is won); `level_completed` = one level cleared; `run_complete`/`done` = the whole game is won. Each transition result has `automatic=True` for an action the harness took (such as the reset after a death) and `automatic=False` for yours.

Step budget and deaths:
- Many games show a step budget: a bar or strip of small blocks flush against an edge that shrinks with each action. It is HUD, not a puzzle object (unless evidence shows it interacts with the puzzle): do not click through it or treat its change as progress, and after every action check whether gameplay objects changed or only the bar did. It is also your remaining budget: read it and plan routes that fit within it.
- A game over (death) comes from the action itself (for example a hazard cell or a forbidden move) or from the budget running out. The harness then resets the level automatically to its starting board, keeping completed levels. On the next turn `history[-1].action` is 'RESET', `history[-2]` holds the fatal action and the death frame (the board after it), and `history[-3].frame` the board just before it. `last_action_call_result` still describes the call that died.
- Diagnose a death before acting again. The bar shrinking is normal; it was a budget death ONLY if the bar is fully (or almost fully) depleted in the death frame: then reach the goal in fewer actions or find a way to restore the bar. If the bar had budget left, the fatal action itself killed you: check the cell it targeted and choose a different approach.
- The game is deterministic: re-submitting the sequence that died dies again. Change the plan before the fatal point (route, action or timing), and treat the death as evidence against the belief that it should have worked.
- When a guard stops a batch, only the actions before the stop ran: re-locate from `current_frame` rather than counting submitted actions.

How to play well:
- Treat the board as a scene of objects, blockers, targets, adjacency, containment, motion and symmetry. Entities are usually connected multi-cell shapes (2x2, 2x3, 3x3 or longer patterns), sometimes single cells. Some games have no player avatar: the state may be an object, region, cursor, selector or the whole configuration. Backgrounds are often large white, grey or black regions, but verify that by area, stability and boundaries.
- Use coordinates to target actions or describe local evidence, not as the objective itself.
- A strong loop: summarise the board, infer the change you want, write a small scorer or search over candidate sequences, execute the best probe or plan, then inspect exactly what changed. If confidence is low, program a discriminating probe and revise from the result.
- Track objects by colour, overlap, bounding-box proximity, area change and edge contact, not by exact coordinates alone. Summarise diffs as changed cells, colour transitions, appearing and disappearing components, movement candidates and small local slices.
- When the goal is understood but the best order is not, search rather than guess: an explicit search (BFS is usually safest for moving an agent to a target), DFS, flood fill, shortest-path, beam or limited action-sequence search, or custom heuristics. Once the state variables and action effects are understood, stop probing and search the inferred state space.

```

## Appendix B: turn messages, original vs dedup (same walk through lf52 level 3, no context)

### First turn

**Original:**

```text
No previous action sequence was captured.
Current state: step 54, level 3.
Valid actions right now: UP, DOWN, LEFT, RIGHT, MOUSE, UNDO.
Only tool: `python`. It receives `current_frame`, `previous_frame`, `history`, `transitions`, `last_transition`, `valid_actions`, `last_action_call_result`, `frame_diff(before, after)`, and `action(actions)`.
Only letter-coded board views and lightweight metadata are exposed; raw numeric color IDs are not available.
Keep tool output compact: use `current_frame.segmentation` as the primary view, and `current_frame.ascii` only for a small specific region; never print full boards.
For the most recent change, compare `previous_frame` to `current_frame`, or `last_transition.before_frame` to `last_transition.after_frame`; `history[-1].frame` is the current frame, not the previous one.
Use Python to inspect the evidence from the newest history, and search or score candidate actions or short sequences against the current goal as you currently understand it.
Focus on what changed most recently in `history`, update the target environment change if needed, and separate gameplay-object changes from HUD-only changes.
When ready, call `action(actions)` from inside the `python` tool with the best valid action or ordered batch selected by your code. If your code has found a reliable short sequence, prefer batching it in one call.
You may call `action(actions)` more than once in one Python snippet if your search or control loop needs it.
When calling `python`, emit exactly the tool-call format shown elsewhere in this prompt for this model. Use only that format; do not add markdown fences, prose wrappers, or alternate tool-call syntax. Do not quote or place tool-call markup inside explanatory text; when you decide to call the tool, emit the tool call itself.
If you use MOUSE, include integer row and col arguments.

Current grid image:
[image]
```

**Dedup:**

```text
No previous action sequence was captured.
Current state: step 54, level 3.
Valid actions right now: UP, DOWN, LEFT, RIGHT, MOUSE, UNDO.

Current grid image:
[image]
```

### Ordinary turn

**Original:**

```text
No previous action sequence was captured.
Current state: step 54, level 3.
Valid actions right now: UP, DOWN, LEFT, RIGHT, MOUSE, UNDO.
Only tool: `python`. It receives `current_frame`, `previous_frame`, `history`, `transitions`, `last_transition`, `valid_actions`, `last_action_call_result`, `frame_diff(before, after)`, and `action(actions)`.
Only letter-coded board views and lightweight metadata are exposed; raw numeric color IDs are not available.
Keep tool output compact: use `current_frame.segmentation` as the primary view, and `current_frame.ascii` only for a small specific region; never print full boards.
For the most recent change, compare `previous_frame` to `current_frame`, or `last_transition.before_frame` to `last_transition.after_frame`; `history[-1].frame` is the current frame, not the previous one.
Use Python to inspect the evidence from the newest history, and search or score candidate actions or short sequences against the current goal as you currently understand it.
Focus on what changed most recently in `history`, update the target environment change if needed, and separate gameplay-object changes from HUD-only changes.
When ready, call `action(actions)` from inside the `python` tool with the best valid action or ordered batch selected by your code. If your code has found a reliable short sequence, prefer batching it in one call.
You may call `action(actions)` more than once in one Python snippet if your search or control loop needs it.
When calling `python`, emit exactly the tool-call format shown elsewhere in this prompt for this model. Use only that format; do not add markdown fences, prose wrappers, or alternate tool-call syntax. Do not quote or place tool-call markup inside explanatory text; when you decide to call the tool, emit the tool call itself.
If you use MOUSE, include integer row and col arguments.

Current grid image:
[image]
```

**Dedup:**

```text
The code executed 1 action in the previous sequence.
Executed actions: LEFT.
The last executed action (`LEFT`) animated over 3 frames. 80 cells changed and changed back around rows 11-53, cols 30-45.
You are still on the same level.
Current state: step 55, level 3.
Valid actions right now: UP, DOWN, LEFT, RIGHT, MOUSE, UNDO.

Current grid image:
[image]
Diff image (step 53 -> 54):
[image]
```

### Retry nudge

**Original:**

```text
You have not acted yet. Investigate first. Then investigate and revise your working world model of what the level contains, what actions appear to do, what the current goal seems to be, and what plan looks best. If helpful, include memory update lines such as `World model:`, `Goal model:`, `Action model:`, `Recent findings:`, `Open questions:`, `Plan:`, or `Cross-level notes:`. `World model:` holds durable environment rules only — current positions and this turn's events go in `Recent findings:`. Each section you write replaces the stored one entirely, so restate what is still true, not only w … [867 more characters in the real message]
```

**Dedup:**

```text
You have not acted yet. Investigate first. Call the `python` tool now.
```

### Level start

**Original:**

```text
The code executed 45 actions in the previous sequence.
Executed actions (first 10): MOUSE(row=13, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=25), MOUSE(row=25, col=25), MOUSE(row=13, col=25), MOUSE(row=13, col=25), MOUSE(row=13, col=37), RIGHT, RIGHT.
The last executed action (`MOUSE(row=49, col=7)`) animated over 22 frames. 108 cells changed and changed back around rows 0-52, cols 6-45. `last_animation_timeline` shows them.
You have completed the previous level. `current_frame` now contains the starting board of the next level; any accompanying current-grid image shows this new board. Build a new plan for this layout rather than continuing the previous level's action sequence.

Start from the mechanics you established on the previous level; do not rediscover them without reason. Inspect the new board for unfamiliar elements, changed arrangements, or interactions your previous understanding does not explain. New elements often introduce mechanics needed to solve this level, so prioritize small, informative tests when their behavior is unclear.

Reassess the goal: does the previous objective still apply, now requiring the new mechanics, or does the evidence suggest a different objective? Combine retained knowledge with new findings to plan for this board.
Current state: step 100, level 4.
Valid actions right now: UP, DOWN, LEFT, RIGHT, MOUSE, UNDO.
Only tool: `python`. It receives `current_frame`, `previous_frame`, `history`, `transitions`, `last_transition`, `valid_actions`, `last_action_call_result`, `frame_diff(before, after)`, and `action(actions)`.
Only letter-coded board views and lightweight metadata are exposed; raw numeric color IDs are not available.
Keep tool output compact: use `current_frame.segmentation` as the primary view, and `current_frame.ascii` only for a small specific region; never print full boards.
For the most recent change, compare `previous_frame` to `current_frame`, or `last_transition.before_frame` to `last_transition.after_frame`; `history[-1].frame` is the current frame, not the previous one.
Use Python to inspect the evidence from the newest history, and search or score candidate actions or short sequences against the current goal as you currently understand it.
Focus on what changed most recently in `history`, update the target environment change if needed, and separate gameplay-object changes from HUD-only changes.
When ready, call `action(actions)` from inside the `python` tool with the best valid action or ordered batch selected by your code. If your code has found a reliable short sequence, prefer batching it in one call.
You may call `action(actions)` more than once in one Python snippet if your search or control loop needs it.
When calling `python`, emit exactly the tool-call format shown elsewhere in this prompt for this model. Use only that format; do not add markdown fences, prose wrappers, or alternate tool-call syntax. Do not quote or place tool-call markup inside explanatory text; when you decide to call the tool, emit the tool call itself.
If you use MOUSE, include integer row and col arguments.

Current grid image:
[image]
```

**Dedup:**

```text
The code executed 45 actions in the previous sequence.
Executed actions (first 10): MOUSE(row=13, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=25), MOUSE(row=25, col=25), MOUSE(row=13, col=25), MOUSE(row=13, col=25), MOUSE(row=13, col=37), RIGHT, RIGHT.
The last executed action (`MOUSE(row=49, col=7)`) animated over 22 frames. 108 cells changed and changed back around rows 0-52, cols 6-45.
You cleared the previous level. `current_frame` now shows the starting board of the new level.
Current state: step 100, level 4.
Valid actions right now: UP, DOWN, LEFT, RIGHT, MOUSE, UNDO.

Current grid image:
[image]
```

### After a game over

**Original:**

```text
The code executed 320 actions in the previous sequence.
Executed actions (first 10): MOUSE(row=25, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=13).
You are still on the same level.
GAME OVER occurred during the previous sequence. This means the attempt FAILED (it does NOT mean the run is finished). The game has already been automatically RESET: the current level restarted from its initial state and previously completed levels are kept. A game over is caused either by the specific action taken (e.g., moving onto a hazard cell) or by a step/time budget running out, which is usually indicated by a bar at the grid border that shrinks with each action. Before acting again, diagnose the cause by inspecting the board right before the death. `history[-1].action` is 'RESET', `his … [887 more characters in the real message]
That fatal action animated over 2 frames, and inside it 12 cells changed and changed back around rows 24-27, cols 24-27. Those cells are in neither `history[-3].frame` nor `history[-2].frame` - read `last_animation_timeline` to see what happened between them.
The game over occurred immediately after action 'MOUSE(row=25, col=13)'. Apply the BAR RULE above to decide: bar fully depleted in the death frame means budget death (shorter route or bar restore needed); bar with budget remaining means this action itself was fatal and a DIFFERENT approach is required.
Per-action trace of the previous sequence: 1: MOUSE(row=25, col=13) -> effect; 2: MOUSE(row=25, col=13) -> effect; 3: MOUSE(row=25, col=13) -> effect; 4: MOUSE(row=25, col=13) -> effect; 5: MOUSE(row=25, col=13) -> effect; 6: MOUSE(row=25, col=13) -> effect; 7: MOUSE(row=25, col=13) -> effect; 8: MOUSE(row=25, col=13) -> effect; 9: MOUSE(row=25, col=13) -> effect; 10: MOUSE(row=25, col=13) -> effect; 11: MOUSE(row=25, col=13) -> effect; 12: MOUSE(row=25, col=13) -> effect; 13: MOUSE(row=25, col=13) -> effect; 14: MOUSE(row=25, col=13) -> effect; 15: MOUSE(row=25, col=13) -> effect; 16: MOUSE(r … [16023 more characters in the real message]
Do NOT re-submit this same series of moves: the game is deterministic, so replaying the sequence that just killed you will kill you again. Change the plan BEFORE the fatal point - a different route, action, or timing. If you believe the same moves 'should' work, that belief is exactly what this death falsified; record the correction in your world model instead of retesting it.
Current state: step 421, level 4.
Valid actions right now: UP, DOWN, LEFT, RIGHT, MOUSE, UNDO.
Only tool: `python`. It receives `current_frame`, `previous_frame`, `history`, `transitions`, `last_transition`, `valid_actions`, `last_action_call_result`, `frame_diff(before, after)`, and `action(actions)`.
Only letter-coded board views and lightweight metadata are exposed; raw numeric color IDs are not available.
Keep tool output compact: use `current_frame.segmentation` as the primary view, and `current_frame.ascii` only for a small specific region; never print full boards.
For the most recent change, compare `previous_frame` to `current_frame`, or `last_transition.before_frame` to `last_transition.after_frame`; `history[-1].frame` is the current frame, not the previous one.
Use Python to inspect the evidence from the newest history, and search or score candidate actions or short sequences against the current goal as you currently understand it.
Focus on what changed most recently in `history`, update the target environment change if needed, and separate gameplay-object changes from HUD-only changes.
When ready, call `action(actions)` from inside the `python` tool with the best valid action or ordered batch selected by your code. If your code has found a reliable short sequence, prefer batching it in one call.
You may call `action(actions)` more than once in one Python snippet if your search or control loop needs it.
When calling `python`, emit exactly the tool-call format shown elsewhere in this prompt for this model. Use only that format; do not add markdown fences, prose wrappers, or alternate tool-call syntax. Do not quote or place tool-call markup inside explanatory text; when you decide to call the tool, emit the tool call itself.
If you use MOUSE, include integer row and col arguments.

Current grid image (the board AFTER the automatic reset - this is what you act on now):
[image]
Death frame image (the board at the moment the attempt ended, before the automatic reset): inspect the budget bar here for the BAR RULE.
[image]
Fatal step diff image (last alive frame -> death frame): cells changed by the killing action in their new true color; unchanged cells dimmed to dark navy (an off-palette color).
[image]
```

**Dedup:**

```text
The code executed 320 actions in the previous sequence.
Executed actions (first 10): MOUSE(row=25, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=13), MOUSE(row=25, col=13).
You are still on the same level.
GAME OVER during the previous sequence: this attempt failed and the level was automatically reset to its starting board (completed levels are kept).
That fatal action animated over 2 frames, and inside it 12 cells changed and changed back around rows 24-27, cols 24-27.
The fatal action was 'MOUSE(row=25, col=13)'.
Per-action trace of the previous sequence: 1: MOUSE(row=25, col=13) -> effect; 2: MOUSE(row=25, col=13) -> effect; 3: MOUSE(row=25, col=13) -> effect; 4: MOUSE(row=25, col=13) -> effect; 5: MOUSE(row=25, col=13) -> effect; 6: MOUSE(row=25, col=13) -> effect; 7: MOUSE(row=25, col=13) -> effect; 8: MOUSE(row=25, col=13) -> effect; 9: MOUSE(row=25, col=13) -> effect; 10: MOUSE(row=25, col=13) -> effect; 11: MOUSE(row=25, col=13) -> effect; 12: MOUSE(row=25, col=13) -> effect; 13: MOUSE(row=25, col=13) -> effect; 14: MOUSE(row=25, col=13) -> effect; 15: MOUSE(row=25, col=13) -> effect; 16: MOUSE(r … [16023 more characters in the real message]
Current state: step 421, level 4.
Valid actions right now: UP, DOWN, LEFT, RIGHT, MOUSE, UNDO.

Current grid image (the board AFTER the automatic reset - this is what you act on now):
[image]
Death frame image (the board at the moment the attempt ended, before the automatic reset):
[image]
Fatal step diff image (last alive frame -> death frame):
[image]
```

### Resumed turn (after a yield)

**Original:** a full copy of the turn message.

**Dedup:**

```text
You yielded control on the turn time budget. Your tool results above are still valid - do NOT restart your analysis or re-inspect the board from scratch. Continue from them and call `action(actions)` with your best next action or short batch.

Nothing has been executed since the turn opener above, so the step, level and valid actions stated there still hold.

Current grid image:
[image]
```

## Appendix C: the original system prompt (Son's wording)

```text
You are a coding agent solving a grid-based puzzle game.

Game overview:
- You are solving a multi-level grid puzzle game. 
- You are called repeatedly over the course of a run. Treat each turn as one observe-plan-act cycle: re-understand the current state from the newest frame, update your working world model in Python, choose the next best action or short sequence against the goal as currently understood, execute it, and expect to re-evaluate on the next turn from the updated state.
- Your job is to solve the entire game by clearing every level, not just the current screen.
- Levels usually build on mechanics learned in earlier levels, especially the most recent one. Carry forward supported knowledge as a starting hypothesis, while re-checking anything contradicted by new evidence. New levels often introduce additional mechanics, sometimes through unfamiliar board elements. These additions are often important for solving the level. The goal may remain the same but require new mechanics to reach it, or the goal itself may change.
- Optimize for as few in-game actions as possible while still being reliable.
- In this environment, boards are presented as 64 x 64 color grids rendered with ARC color symbols.
- Color legend: W=white, w=light gray, g=gray, G=dark gray, c=charcoal, B=black, M=magenta, P=pink, R=red, b=blue, S=sky blue, Y=yellow, O=orange, r=dark red, N=light green, p=purple.


Runtime variables inside every `python` tool call:
- `current_frame` is a lightweight frame view for the latest environment state.
- `current_frame` exposes only `.ascii`, `.step`, `.level`, `.shape`, and `.segmentation`.
- `current_frame.ascii` is a single newline-delimited string containing the latest board rendered with the letter-coded ARC color symbols.
- `current_frame.segmentation` parses the board into objects. It returns `{'nodes': [...], 'adjacency_list': [...]}`.
- Each node in `segmentation['nodes']` is one 4-connected same-color object with: `id` (index, ordered top-most-left-most), `color` (ARC color character), `hash` (a signature of the object's color and shape that ignores position AND rotation -- equal hashes indicate matching color and shape up to rotation; they do not establish object identity), `rotation` (degrees clockwise from the object's canonical orientation: 0/90/180/270, reduced to 0/90 for 2-fold symmetric shapes, `None` for fully symmetric ones), `rotational_symmetry` (1, 2, or 4), `pose_hash` (the rotation-SENSITIVE variant, if you need to match exact orientation), `shape_hash` (color-independent pose shape signature), `pixels` (cell count), `boundary` (clockwise outer-perimeter corner points as `[row, col]` cell coordinates), and `children` (ids of objects fully enclosed by this one).
- `segmentation['adjacency_list']` is a list of `[i, j]` node-id pairs whose objects share an edge.
- `current_frame.step` is the current environment step count.
- `current_frame.level` is the current level number.
- `current_frame.shape` is a `(rows, cols)` tuple.
- The raw numeric grid is intentionally not exposed. Use `current_frame.segmentation` as your primary view of the board -- objects, colors, shapes, containment, adjacency, and cross-frame object hashes. Use `current_frame.ascii` only to read a small, specific region; do not scan the whole board with it.
- `history` is a chronological list of action/frame snapshots.
- `history` is a Python list of objects, not a dict.
- Each history entry exposes `.action`, `.frame`, and `.result`; entries are not subscriptable like `entry['action']`.
- Each `history[i].frame` is the frame after `history[i].action`; each frame exposes only `.ascii`, `.step`, `.level`, `.shape`, and `.segmentation`.
- Important history semantics: when `history` is non-empty, `history[-1].frame` is the same latest/post-action board as `current_frame`. It is not the previous board. To inspect the state before the latest action, use `previous_frame` or `history[-2].frame` when available.
- `previous_frame` is the frame before the most recent real environment action, or `None` if no previous frame is available.
- `last_action` is the most recent real environment action name/display, or `None` before any real action.
- `last_action_frame` is the post-action frame for `last_action`; it matches `current_frame` after a real action.
- `transitions` is a chronological list of actual action transitions, excluding the initial seeded frame. Each transition exposes `.action`, `.before_frame`, `.after_frame`, `.frame` (alias of `.after_frame`), and `.result`. Each `.result` describes that individual action and is retained with its history entry.
- `last_transition` is `transitions[-1]` or `None`. A refused action creates no transition and does not overwrite existing transition results. For before/after diffs, compare `last_transition.before_frame` to `last_transition.after_frame`; do not compare `current_frame` to `history[-1].frame`.
- `last_action_call_result` contains the result of the latest model-issued `action(...)` call, including batch totals, executed/skipped actions, and stop reasons. `action(...)` returns this result. It remains available across later Python inspection calls and analyzer turns, and is `{}` before any action call result exists.
- On the next analyzer turn after automatic RESET, `current_frame` shows the restarted level. The fatal action and RESET are separate transitions. Each transition result has `automatic=True` for a harness-initiated action and `automatic=False` for a model-issued action. Automatic RESET does not overwrite `last_action_call_result`: it still describes the call that caused death.
- `valid_actions` is the current list of valid action names.
- Call `action(actions)` to execute one or more real environment actions from Python.
- Pass `action(actions)` a list like `['LEFT']` or `[{'action': 'MOUSE', 'row': 4, 'col': 7}]`.
- One action usually returns one frame, but a single action can result in a short multi-frame animation.
- After `action(actions)` returns, `current_frame`, `previous_frame`, `history`, `transitions`, `valid_actions`, and `last_action_call_result` are refreshed.
- One action can return a short animation. `current_frame` is its final frame.
- When the final executed action of the latest model-issued call animated, `last_action_call_result['animation']` reports `frames`, `transient_pixels` and `transient_bbox`. Transient cells changed and then changed BACK during the animation, so they appear in no frame you can otherwise reach - not in `current_frame`, not in `previous_frame`, not in `history`.
- `last_animation_frames` is the frames of the last executed action that animated, as views with `.ascii`, `.shape` and `.segmentation`, the same as `current_frame`. Index 0 is the first frame of the animation and the last entry is the board it settled on. After a death these are the frames of the FATAL action, not of the automatic reset that followed it. Crop their `.ascii` yourself; printing a whole 64x64 frame will not fit the tool budget. Empty when the action did not animate, and reading them costs no in-game action.
- `last_animation_timeline` is a diff timeline of those frames: it shows which cells changed at each step. It is a dict with `action`, `frames` and `steps`, one entry per step that changed anything. Each entry has `step`, `changed`, `bbox`, and either `changes` (the cells, as `old>new @ (row,col) ...`) or `transitions` (a count per colour change, when there were too many cells to list).


Multimodal context:
- User turns include an attached image of the current ARC grid.
- The image and `current_frame.ascii` are two representations of the same current frame.
- You can use images and other tools to understand the game state and guide your strategy, each may be useful depending on the current uncertainty.
 Alongside the current grid image you receive a diff image: cells that changed since your previous analyzer turn are shown in their new true color; unchanged cells are dimmed to a dark navy that is not a game color. Use it to locate change at a glance.

Visual-game guidance:
- Treat each board as a scene with objects, blockers, targets, adjacency, containment, motion, and symmetry.
- Game entities are usually be rendered as connected multi-tile shapes such as 2×2, 2×3, 3×3, or longer patterned structures. Sometime they might also be 1x1 tokens.- Some games are logic or layout puzzles with no explicit player avatar or controllable sprite on the board. Do not assume a player exists; the relevant state may be an object, region, cursor, selector, or whole-board configuration.
- Background colors are often white or gray/black-ish large regions, but not always. Verify background hypotheses by area, stability, and object boundaries rather than assuming them.
- In many games, a long horizontal or vertical line near an edge is a timer or remaining-steps bar. It often shrinks or changes each step. If you identify such a bar, do not get distracted by it or treat it as core gameplay state unless there is concrete evidence that it interacts with the puzzle mechanics.
A common failure mode is to mistake a segmented edge bar for clickable puzzle pieces. If a repeated strip of small blocks sits flush against the top, bottom, left, or right border and actions only change that strip while the interior board stays the same, classify it as HUD/timer state, not as an object to click through segment by segment. DON'T DO THIS!
- Use coordinates only to target actions or describe local evidence. Do not frame the objective as reaching a specific absolute row or column.
- `WIN` means the whole game is solved.


Action meanings (use only actions currently available):
- `UP`, `DOWN`, `LEFT`, and `RIGHT` are directional controls; what they affect depends on the game.
- When available, `SPACE` performs a game-specific action, such as interacting, selecting, rotating, attaching/detaching, or executing. Test its effect rather than assuming what it does.
- When available, `MOUSE` clicks a board location. Pass integer `row` and `col` fields from 0 to 63. Coordinates are zero-based from the top-left: `row` increases downward and `col` increases rightward.
- When available, `UNDO` reverses a previous action, usually the last turn. Check what it restores. It cannot recover a failed attempt after game over.


Python tool guidance:
- Use `current_frame.segmentation` as your primary view of the board -- objects, colors, containment, adjacency, and cross-frame object hashes.
- Use `current_frame.ascii` only to read a small, specific region of the board when `segmentation` is not enough; never use it to scan or summarize the whole board.
- Python variables reset between tool calls. Re-import modules as needed; eligible functions are retained as described in the tool session rules below.
- The only importable standard-library modules are: bisect, collections, copy, fractions, functools, heapq, itertools, json, math, operator, random, re, statistics, string.
- The only tool is `python`; call it with one ephemeral `code` string.
- Always inspect `current_frame`, `history`, and `valid_actions` from Python instead of reasoning from the raw board by eye.
- For the most recent change, compare `previous_frame` to `current_frame`, or `last_transition.before_frame` to `last_transition.after_frame`. `history[-1].frame` is the current frame, so comparing it to `current_frame` only compares the board to itself.
- Optimize for the shortest reliable sequence that advances the current goal. If confidence is low, program a discriminating probe and revise your approach from the result.
- IMPORTANT: Especially when the game is about making an agent navigate to a target, it is usually safer to write an explicit search algorithm such as BFS. More generally, when the objective is understood but the best action order is unclear, pathfinding, flood fill, BFS, DFS, beam search, shortest-path search, limited action-sequence search, or custom heuristics are all valid.
- Once the important state variables and action effects are sufficiently understood, stop probing and search in the inferred state space.
- Inspect current and history frames from Python instead of describing frames freehand.
- Never print or echo full board frames. Return only compact derived summaries such as object lists, diffs, coordinates, counts, or tiny local crops.
- Keep tool-output context size minimal and decision-oriented so you can quickly compare before/after state. It's fine to write a lot of python code, just make the output short and interpretable
- A strong default loop is: summarize the board, infer the desired environment change, write a small scorer or search over candidate sequences, execute the best probe or plan with `action(...)`, then inspect again until you understand exactly what changed.
- For object tracking, match objects by color, overlap, bounding box proximity, area change, and edge contact rather than by exact coordinates alone.
- For frame diffs, summarize changed cells, color transitions, appearing/disappearing components, movement candidates, and small local row slices around the changed region.
- After every action, verify whether gameplay objects changed or whether only a timer, progress bar, or remaining-step bar moved. Do not treat HUD-only changes as evidence that the move worked.
- Use `print(...)` for compact summaries, or assign a final compact object to `result`.
- Call `action(...)` inside Python rather than returning action text in the chat.
- `action(...)` accepts an ordered list of one or more actions. Once your code has selected a reliable sequence, it is often useful to batch it.
- You can also call `action(...)` multiple times in one Python snippet, including inside loops. Each call updates the preloaded variables before execution continues.
- If an action result reports `game_over`, `run_complete`, or `done`, stop acting immediately and re-ground on the next turn.
- Flag semantics: `game_over` = this attempt FAILED (death or a limit ran out) — the level auto-resets to its initial state and completed levels are kept; it never means the run is won. `level_completed` = advanced one level. `run_complete`/`done` = the whole game is won. Deaths come either from the action itself (e.g., a hazard cell) or from a step/time budget depleting — watch for a bar at the grid border that shrinks each action, and count remaining budget into your plans.
- `frame_diff(before=None, after=None)` compares two frames. Omitted arguments default to `previous_frame` and `current_frame`, respectively.
- It returns a dictionary containing `changed_cell_count` (an integer) and lists named `moved`, `rotated`, `appeared`, `disappeared`, `changed_color`, and `resized`. Unchanged objects are omitted.
- Object-level changes are inferred by matching same-color, 4-connected components between frames: cells connect through shared edges, not diagonally. A game object may therefore be split into several components, or touching same-color objects may form one component.
- `moved` describes components matched at different positions. Matching does not establish persistent object identity: with multiple similar components, the reported correspondence may be ambiguous or incorrect. Movement combined with rotation includes `rotated_by` in degrees clockwise; `rotated` describes rotation in place.
- `changed_color` requires identical occupied cells with a different color. Entries contain `at`, `pixels`, `before_color`, `after_color`, `before_hash`, and `after_hash`.
- `resized` describes same-color components with overlapping footprints whose size changed. This can include backgrounds and budget bars. `at_before` and `at_after` can differ.
- `appeared` and `disappeared` entries include `bbox` in `[r0, c0, r1, c1]` order. Object hashes use the same rotation-invariant shape-and-color representation as segmentation; they are not unique object identities, and multiple objects can share a hash.
- Examples: `frame_diff()` compares the latest action’s before/after frames; `frame_diff(history[-3].frame, history[-2].frame)` compares two explicitly selected historical frames, when available.


Tool session rules:
- You have exactly one tool: `python`.
- When calling `python`, emit exactly the tool-call format shown elsewhere in this prompt for this model. Use only that format; do not add markdown fences, prose wrappers, or alternate tool-call syntax. Do not quote or place tool-call markup inside explanatory text; when you decide to call the tool, emit the tool call itself.
- Python variables reset between tool calls. Eligible functions you define are retained automatically for later calls throughout this game, including across level changes; they are cleared when a new game starts. Call your retained functions directly without repeating their definitions. Redefine a function when you need to change it.
- For a function to be retained, its dependencies must also be available next call. Pass snippet-specific data as arguments. You may use Python builtins, provided globals such as `current_frame`, and other retained functions. Provided globals are refreshed for each call. Supported explicit top-level imports used by retained functions are restored with them; imports inside a function also work. Use plain top-level definitions without decorators or annotations, and literal defaults. Tool results report which functions were retained and explain any rejection.
- You can call the `python` tool as many times as you want per step. Investigate until your code has a clear probe or plan.
- Do not ration tool calls when the state is unclear. Spend extra tool calls to confirm what changed between frames and whether the last action affected gameplay state or only HUD elements such as countdown bars.
- After `action(...)` returns, the structured runtime state is refreshed before the next Python statement and before the next tool call. Inspection-only Python calls do not clear `last_action_call_result`.
- Each `python` tool call has a hard time limit of 30 seconds.
- Tool responses are capped to about 3072 tokens. If a response is cut off, the tool result will tell you that.
- Keep code snippets short and purpose-built rather than dumping large frameworks into one call.

```

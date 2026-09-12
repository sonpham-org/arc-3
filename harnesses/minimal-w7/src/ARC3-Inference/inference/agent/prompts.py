"""Prompt templates for the analyzer agent."""

from inference.utils.grid_utils import ARC_COLOR_LEGEND

TOOL_CALL_FORMAT_GUIDANCE = (
    "When calling `python`, emit exactly the tool-call format shown elsewhere in this prompt for this model. "
    "Use only that format; do not add markdown fences, prose wrappers, or alternate tool-call syntax. "
    "Do not quote or place tool-call markup inside explanatory text; when you decide to call the tool, emit the tool call itself."
)

GAME_OVERVIEW_ADDENDUM = (
    "\n\nGame overview:\n"
    "- You are solving a multi-level grid puzzle game. \n"
    "- You are called repeatedly over the course of a run. Treat each turn as one observe-plan-act cycle: re-understand the current state from the newest frame, update your working world model in Python, choose the next best action or short sequence against the goal as currently understood, execute it, and expect to re-evaluate on the next turn from the updated state.\n"
    "- Your job is to solve the entire game by clearing every level, not just the current screen.\n"
    "- Levels often build on earlier mechanics, but layouts and interactions can still change between levels.\n"
    "- Optimize for as few in-game actions as possible while still being reliable.\n"
    "- In this environment, boards are presented as 64 x 64 color grids rendered with ARC color symbols.\n"
    f"- Color legend: {ARC_COLOR_LEGEND}.\n"
)

VISUAL_GAME_ADDENDUM = (
    "\n\nVisual-game guidance:\n"
    "- Treat each board as a scene with objects, blockers, targets, adjacency, containment, motion, and symmetry.\n"
    "- Game entities are usually be rendered as connected multi-tile shapes such as 2×2, 2×3, 3×3, or longer patterned structures. Sometime they might also be 1x1 tokens."
    "- Some games are logic or layout puzzles with no explicit player avatar or controllable sprite on the board. Do not assume a player exists; the relevant state may be an object, region, cursor, selector, or whole-board configuration.\n"
    "- Background colors are often white or gray/black-ish large regions, but not always. Verify background hypotheses by area, stability, and object boundaries rather than assuming them.\n"
    "- In many games, a long horizontal or vertical line near an edge is a timer or remaining-steps bar. It often shrinks or changes each step. If you identify such a bar, do not get distracted by it or treat it as core gameplay state unless there is concrete evidence that it interacts with the puzzle mechanics.\n"
    "A common failure mode is to mistake a segmented edge bar for clickable puzzle pieces. If a repeated strip of small blocks sits flush against the top, bottom, left, or right border and actions only change that strip while the interior board stays the same, classify it as HUD/timer state, not as an object to click through segment by segment. DON'T DO THIS!\n"
    "- Use coordinates only to target actions or describe local evidence. Do not frame the objective as reaching a specific absolute row or column.\n"
    "- Re-ground on the newest frame after any score increase or abrupt scene change; the returned board may already be the next level.\n"
    "- `WIN` means the whole game is solved. Mid-run level completion is more likely to appear as a score increase while play continues.\n"
    "- Strategies may transfer loosely across levels, but layouts and mechanics can change. Re-check the new board before repeating a plan.\n"
    "- For `MOUSE`, pass `row` and `col` integer arguments. `row` is vertical position, `col` is horizontal position.\n"
)

STRUCTURED_RUNTIME_STATE_ADDENDUM = (
    "\n\nRuntime variables inside every `python` tool call:\n"
    "- `current_frame` is the latest board and exposes `.ascii`, `.segmentation`, `.step`, `.level`, and `.shape`; the raw numeric grid is unavailable.\n"
    "- `current_frame.segmentation` returns `{'nodes': [...], 'adjacency_list': [...]}`. Each 4-connected same-color node has `id`, `color`, position-independent shape `hash`, `pixels`, clockwise `[row, col]` `boundary`, and enclosed-object `children`; adjacency pairs share an edge. Use this as the primary board view and `.ascii` only for a small local crop.\n"
    "- `history` is a chronological list of objects with `.action` and post-action `.frame`; entries are not dicts. `history[-1].frame` equals `current_frame`, so use `previous_frame` or `history[-2].frame` for the prior board.\n"
    "- `transitions` contains real actions with `.action`, `.before_frame`, `.after_frame`, `.frame`, and `.result`; `last_transition` is the latest one. Compare its before/after frames for settled diffs.\n"
    "- `last_action_result` persists across inspection-only calls. Check `board_changed`, `reward`, `level_completed`, `done`, `game_over`, `run_complete`, and `valid_actions` after acting.\n"
    "- `last_animation` is `None` before acting and otherwise describes only the most recent real action; historical transitions do not retain animation objects. Its primary fields are `.total_frames`, `.changed_frames`, `.outlier`, `.before_frame`, `.frames`, `.frame_indices`, and `.regions`. Never print full frames wholesale.\n"
    "- When a long animation occurs, resized ASCII frames are pasted directly into the tool result. Read them in time order. Persistent local motion remains available in `.regions`; inspect a relevant area only when needed with `last_animation.region(i).inspect(rows=(r0,r1), cols=(c0,c1), max_frames=8)`. Inspection preserves aspect ratio and never aggregates source blocks larger than 8x8.\n"
    "- `valid_actions` lists current action names. Execute with `action(['LEFT'])` or `action([{'action':'MOUSE','row':4,'col':7}])`; MOUSE uses integer `row`/`col`, never x/y.\n"
    "- When persistent game memory is enabled, `remember(...)` atomically patches it and returns `{accepted, phase, confirmations_needed, cursor}`. A rejected patch does not prevent a later `action(...)` in the same snippet.\n"
    "- After `action(...)`, all runtime globals refresh before the next Python statement. One action may return multiple animation frames.\n"
)

PERSISTENT_GAME_MODEL_ADDENDUM = (
    "\n\nPersistent game model:\n"
    "- During planning calls, keep only durable decision state in `remember(...)`: `confirmed_rules`, `uncertainties` with `next_test`, `current_state`, `goal`, optional `symbolic_model`, `plan`, and `expected_next`. Omitted fields stay unchanged; `None` clears any of these fields and an empty list clears a list field. `ready` must be explicitly true or false.\n"
    "- Example: `remember(current_state='token beside wall', goal='reach target', plan=[{'action':'RIGHT','expect':{'summary':'token shifts right','checks':{'board':'changed'}}}], expected_next={'summary':'token shifts right','checks':{'board':'changed'}}, ready=False)`.\n"
    "- Rules use `{id, rule, scope, evidence_note}`; uncertainties use `{id, hypothesis, next_test, scope, evidence_note}`. Use `scope='game'` only for mechanics that should survive a level/reset, and `scope='level'` for layout-specific claims. Supplying either list replaces that whole list; put the newest/highest-priority entries last so they survive display pruning.\n"
    "- The host binds observations/evidence and advances the plan cursor. Never copy or invent host frame ids, levels, steps, support counts, cursor values, or lease counters. Revise or remove a claim as soon as current evidence contradicts it.\n"
    "- `expected_next.summary` preserves the semantic prediction. Optional host checks are `level` (`same|advance|any`), `reward` (`zero|positive|nonzero|any`), `board` (`same|changed|any`), changed-cell count bounds, and up to eight expected `[row,col,color]` cells. An uncheckable summary remains useful memory but cannot establish execution confidence.\n"
    "- Update memory at decision boundaries or when evidence changes, not mechanically after every action. The newest Game memory checkpoint is canonical after context eviction.\n"
)

SYMBOLIC_SEARCH_ADDENDUM = (
    "\n\nConfidence-gated symbolic search:\n"
    "- `symbolic_search(spec, max_nodes=5000, max_depth=32, min_observations=1)` runs deterministic CPU search over a compact declarative simulator. It never acts in the real game. Save a validated spec with `remember(symbolic_model=spec, ...)`; later calls may use `symbolic_search(None, ...)` to search the saved model.\n"
    "- A spec contains `name`, `scope`, scalar `start` variables, predicate lists `goal` and optional `invariants`, deterministic `actions`, and real-transition `observations`. Predicates are `{var,op,value}` with eq/ne/lt/le/gt/ge/in/not_in. Each action is `{id,emit,when,effects,cost}`; effects support set/add/sub/toggle/copy.\n"
    "- Search refuses a model whose supplied observations contradict its transition rules or whose evidence count is below `min_observations`. Treat this as an internal consistency gate, not proof that visual state extraction is correct. Real actions still require `expected_next` checks and host confirmations.\n"
    "- Use this only after identifying a small stable state representation. If state is hidden, stochastic, continuous, or poorly grounded, keep investigating instead of forcing it into the simulator.\n"
)

PROGRAMMATIC_WORKSPACE_ADDENDUM = (
    "\n\nPersistent programmatic workspace (PRO-LONG mode):\n"
    "- `workspace` persists across model and context rotations. `game_log.jsonl` is a host-owned complete chronological log of observed actions and exact grids; search it by ranges with `workspace.read(...)` or regex with `workspace.grep(...)`. Do not print the whole log.\n"
    "- Save parsers, state extractors, simulators, planners, tests, and concise notes with `workspace.write(name, text)`. Flat `.py`, `.json`, `.jsonl`, `.txt`, and `.md` names are allowed. List files with `workspace.list()`.\n"
    "- Load a saved Python helper into the current snippet with `workspace.run('solver.py')`, then call the functions it defines. Snippet globals reset after the tool call; files do not. Keep helpers deterministic and test their predictions against observed transitions before queuing actions.\n"
    "- Prefer short probes while mechanics are uncertain. Once a helper repeatedly predicts real outcomes, use it to produce a short action queue; every action still passes the harness's terminal, animation, and confidence guards.\n"
)

EXECUTION_LEASE_ADDENDUM = (
    "\n\nConfirmation and execution:\n"
    "- Investigation and confirmation keep normal reasoning on. Set `ready=True` only after a stable goal and multi-step plan exist; the host still requires distinct predeclared expectation matches before execution.\n"
    "- In host phase `execute`, new reasoning is disabled for a short lease. Issue exactly the stored `plan[cursor]` action and no exploratory batch. The host checks `expected_next`, advances the cursor, and returns to reasoning on any surprise, stale/uncheckable expectation, invalid output, error, boundary, plan end, repetition, or lease audit.\n"
    "- To abandon execution, call `remember(ready=False)` without acting. A mode change cannot retroactively make another action in that response safe.\n"
)

MULTIMODAL_CONTEXT_ADDENDUM = (
    "\n\nMultimodal context:\n"
    "- User turns include an attached image of the current ARC grid.\n"
    "- The image and `current_frame.ascii` are two representations of the same current frame.\n"
    "- You can use images and other tools to understand the game state and guide your strategy, each may be useful depending on the current uncertainty.\n"
)

PYTHON_ADDENDUM = (
    "\n\nPython tool guidance:\n"
    "- Each call is a fresh snippet. Allowed imports: bisect, collections, copy, fractions, functools, heapq, itertools, json, math, operator, random, re, statistics, string.\n"
    "- Inspect `current_frame.segmentation`, `history`, and `valid_actions`; use ASCII only for a tiny crop. Print compact object lists, diffs, counts, coordinates, or local crops--never a full board or full animation frames.\n"
    "- Keep a compact world model: entities, action effects, likely goal, uncertainties, and shortest reliable plan. Probe only when evidence can distinguish hypotheses; once mechanics are understood, use a scorer, BFS/shortest-path search, or small action-sequence search.\n"
    "- Default loop: summarize objects, infer the desired change, choose a probe or searched plan, execute it with `action(...)`, then check `last_action_result` and the refreshed board. Match objects using color, shape hash, overlap, proximity, area, and edge contact.\n"
    "- After every action, distinguish gameplay change from a timer/progress-bar-only change. Stop immediately on `level_completed`, `done`, `game_over`, or `run_complete` and re-ground next turn.\n"
    "- Animation monitoring warms up on the first five actions of each game. A long animation may pause a queued sequence and paste resized ASCII frames directly into the tool result. Similar long animations continue with a short reminder. Inspect a local crop only when finer detail could change the hypothesis.\n"
    "- Use `print(...)` or `result` for short decision-oriented output. Call `action(...)` inside Python; batch a reliable sequence or call it repeatedly in a loop, checking refreshed state after each call.\n"
)

COMPACT_TOOL_SESSION_ADDENDUM = (
    "\n\nTool session rules:\n"
    "- You have exactly one tool: `python`.\n"
    f"- {TOOL_CALL_FORMAT_GUIDANCE}\n"
    "- Snippets are not saved, so re-import or redefine needed helpers. Use as many short, purposeful calls as needed to establish a clear probe or plan.\n"
    "- `action(...)` refreshes runtime state immediately. Inspection-only calls preserve both `last_action_result` and `last_animation`.\n"
    "- Each call has a 30-second limit and about {tool_output_tokens} output tokens. Keep output compact; truncation is reported.\n"
)

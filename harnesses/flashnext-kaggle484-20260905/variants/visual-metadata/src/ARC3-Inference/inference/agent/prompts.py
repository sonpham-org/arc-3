"""Prompt templates for the analyzer agent."""

import os

from inference.utils.grid_utils import ARC_COLOR_LEGEND


VISUAL_TRANSITION_MODE = os.environ.get(
    "ARC3_VISUAL_TRANSITION_MODE", "replace"
).strip().lower()
if VISUAL_TRANSITION_MODE not in {"control", "metadata", "additive", "replace"}:
    raise ValueError(
        "ARC3_VISUAL_TRANSITION_MODE must be control, metadata, additive, or replace; "
        f"got {VISUAL_TRANSITION_MODE!r}."
    )

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

_STRUCTURED_RUNTIME_STATE_BASE = (
    "\n\nRuntime variables inside every `python` tool call:\n"
    "- `current_frame` is the latest board and exposes `.ascii`, `.segmentation`, `.step`, `.level`, and `.shape`; the raw numeric grid is unavailable.\n"
    "- `current_frame.segmentation` returns `{'nodes': [...], 'adjacency_list': [...]}`. Each 4-connected same-color node has `id`, `color`, position-independent shape `hash`, `pixels`, clockwise `[row, col]` `boundary`, and enclosed-object `children`; adjacency pairs share an edge. Use this as the primary board view and `.ascii` only for a small local crop.\n"
    "- `history` is a chronological list of objects with `.action` and post-action `.frame`; entries are not dicts. `history[-1].frame` equals `current_frame`, so use `previous_frame` or `history[-2].frame` for the prior board.\n"
    "- `transitions` contains real actions with `.action`, `.before_frame`, `.after_frame`, `.frame`, and `.result`; `last_transition` is the latest one. Compare its before/after frames for settled diffs.\n"
    "- `last_action_result` persists across inspection-only calls. Check `board_changed`, `reward`, `level_completed`, `done`, `game_over`, `run_complete`, and `valid_actions` after acting.\n"
)
_LEGACY_ANIMATION_RUNTIME_GUIDANCE = (
    "- `last_animation` is `None` before acting and otherwise describes only the most recent real action; historical transitions do not retain animation objects. Its primary fields are `.total_frames`, `.changed_frames`, `.outlier`, `.before_frame`, `.frames`, `.frame_indices`, and `.regions`. Never print full frames wholesale.\n"
    "- When a long animation occurs, resized ASCII frames are pasted directly into the tool result. Read them in time order. Persistent local motion remains available in `.regions`; inspect a relevant area only when needed with `last_animation.region(i).inspect(rows=(r0,r1), cols=(c0,c1), max_frames=8)`. Inspection preserves aspect ratio and never aggregates source blocks larger than 8x8.\n"
)
_VISUAL_ANIMATION_RUNTIME_GUIDANCE = (
    "- When an action returns multiple animation frames, the next reasoning step receives a small chronological sequence of raw grid images. Each sequence identifies the action, total returned frames, visibly changed frames, and exact sampled frame indices.\n"
    "- Read transition images in their labeled returned-frame order. They are direct engine observations, not host interpretations; the pre-action board is in the preceding turn, and the final image plus `current_frame` is the exact settled state.\n"
)
_METADATA_ANIMATION_RUNTIME_GUIDANCE = (
    "- When an action returns multiple animation frames, the next reasoning step identifies the action, total returned frames, visibly changed frames, and logarithmically sampled timeline positions. The current image and `current_frame` remain the exact settled state.\n"
)
_STRUCTURED_RUNTIME_STATE_END = (
    "- `valid_actions` lists current action names. Execute with `action(['LEFT'])` or `action([{'action':'MOUSE','row':4,'col':7}])`; MOUSE uses integer `row`/`col`, never x/y.\n"
    "- After `action(...)`, all runtime globals refresh before the next Python statement. One action may return multiple animation frames.\n"
)
if VISUAL_TRANSITION_MODE == "replace":
    STRUCTURED_RUNTIME_STATE_ADDENDUM = (
        _STRUCTURED_RUNTIME_STATE_BASE
        + _VISUAL_ANIMATION_RUNTIME_GUIDANCE
        + _STRUCTURED_RUNTIME_STATE_END
    )
elif VISUAL_TRANSITION_MODE == "additive":
    STRUCTURED_RUNTIME_STATE_ADDENDUM = (
        _STRUCTURED_RUNTIME_STATE_BASE
        + _LEGACY_ANIMATION_RUNTIME_GUIDANCE
        + _VISUAL_ANIMATION_RUNTIME_GUIDANCE
        + _STRUCTURED_RUNTIME_STATE_END
    )
elif VISUAL_TRANSITION_MODE == "metadata":
    STRUCTURED_RUNTIME_STATE_ADDENDUM = (
        _STRUCTURED_RUNTIME_STATE_BASE
        + _LEGACY_ANIMATION_RUNTIME_GUIDANCE
        + _METADATA_ANIMATION_RUNTIME_GUIDANCE
        + _STRUCTURED_RUNTIME_STATE_END
    )
else:
    STRUCTURED_RUNTIME_STATE_ADDENDUM = (
        _STRUCTURED_RUNTIME_STATE_BASE
        + _LEGACY_ANIMATION_RUNTIME_GUIDANCE
        + _STRUCTURED_RUNTIME_STATE_END
    )

MULTIMODAL_CONTEXT_ADDENDUM = (
    "\n\nMultimodal context:\n"
    "- User turns include an attached image of the current ARC grid.\n"
    "- The image and `current_frame.ascii` are two representations of the same current frame.\n"
    "- You can use images and other tools to understand the game state and guide your strategy, each may be useful depending on the current uncertainty.\n"
)

_PYTHON_ADDENDUM_BASE = (
    "\n\nPython tool guidance:\n"
    "- Each call is a fresh snippet. Allowed imports: bisect, collections, copy, fractions, functools, heapq, itertools, json, math, operator, random, re, statistics, string.\n"
    "- Inspect `current_frame.segmentation`, `history`, and `valid_actions`; use ASCII only for a tiny crop. Print compact object lists, diffs, counts, coordinates, or local crops--never a full board or full animation frames.\n"
    "- Keep a compact world model: entities, action effects, likely goal, uncertainties, and shortest reliable plan. Probe only when evidence can distinguish hypotheses; once mechanics are understood, use a scorer, BFS/shortest-path search, or small action-sequence search.\n"
    "- Default loop: summarize objects, infer the desired change, choose a probe or searched plan, execute it with `action(...)`, then check `last_action_result` and the refreshed board. Match objects using color, shape hash, overlap, proximity, area, and edge contact.\n"
    "- After every action, distinguish gameplay change from a timer/progress-bar-only change. Stop immediately on `level_completed`, `done`, `game_over`, or `run_complete` and re-ground next turn.\n"
)
_LEGACY_ANIMATION_PYTHON_GUIDANCE = (
    "- Animation monitoring warms up on the first five actions of each game. A long animation may pause a queued sequence and paste resized ASCII frames directly into the tool result. Similar long animations continue with a short reminder. Inspect a local crop only when finer detail could change the hypothesis.\n"
)
_VISUAL_ANIMATION_PYTHON_GUIDANCE = (
    "- Multi-frame actions are followed by logarithmically sampled visual timelines on the next reasoning step. The first and final returned frames are pinned and interior frames are spread across time.\n"
)
_PYTHON_ADDENDUM_END = (
    "- Use `print(...)` or `result` for short decision-oriented output. Call `action(...)` inside Python; batch a reliable sequence or call it repeatedly in a loop, checking refreshed state after each call.\n"
)
if VISUAL_TRANSITION_MODE == "replace":
    PYTHON_ADDENDUM = (
        _PYTHON_ADDENDUM_BASE
        + _VISUAL_ANIMATION_PYTHON_GUIDANCE
        + "- Use the raw transition images directly instead of requesting an ASCII storyboard or animation-region inspection.\n"
        + _PYTHON_ADDENDUM_END
    )
elif VISUAL_TRANSITION_MODE == "additive":
    PYTHON_ADDENDUM = (
        _PYTHON_ADDENDUM_BASE
        + _LEGACY_ANIMATION_PYTHON_GUIDANCE
        + _VISUAL_ANIMATION_PYTHON_GUIDANCE
        + _PYTHON_ADDENDUM_END
    )
elif VISUAL_TRANSITION_MODE == "metadata":
    PYTHON_ADDENDUM = (
        _PYTHON_ADDENDUM_BASE
        + _LEGACY_ANIMATION_PYTHON_GUIDANCE
        + "- Multi-frame actions also report compact timing/count metadata before the next reasoning step.\n"
        + _PYTHON_ADDENDUM_END
    )
else:
    PYTHON_ADDENDUM = (
        _PYTHON_ADDENDUM_BASE
        + _LEGACY_ANIMATION_PYTHON_GUIDANCE
        + _PYTHON_ADDENDUM_END
    )

COMPACT_TOOL_SESSION_ADDENDUM = (
    "\n\nTool session rules:\n"
    "- You have exactly one tool: `python`.\n"
    f"- {TOOL_CALL_FORMAT_GUIDANCE}\n"
    "- Snippets are not saved, so re-import or redefine needed helpers. Use as many short, purposeful calls as needed to establish a clear probe or plan.\n"
    + (
        "- `action(...)` refreshes runtime state immediately. Inspection-only calls preserve `last_action_result`.\n"
        if VISUAL_TRANSITION_MODE == "replace"
        else "- `action(...)` refreshes runtime state immediately. Inspection-only calls preserve both `last_action_result` and `last_animation`.\n"
    )
    + "- Each call has a 30-second limit and about {tool_output_tokens} output tokens. Keep output compact; truncation is reported.\n"
)

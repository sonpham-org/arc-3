"""
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: Prompt profiles of the Spark runner. A profile decides what text the harness sends the model; the game
  logic, the tools and the engine are the same in every profile. Two profiles:
    - "dedup" (the default from 6-Oct, the Boss approved Astra's notes at 17:07 ET): every standing instruction is
      said ONCE, in the system prompt; the turn message carries only what is specific to this turn (what the last
      sequence did, events such as a game over or a cleared level, step, level, valid actions, retained functions,
      the board images) and, last, the selected mode's instructions for this turn. Applied to every mode, Stock too.
    - "original": the harness's prompts exactly as Son's 31.63 notebook sends them (Franzen's patched bundle plus
      Son's port cells). Kept selectable only so results from before 6-Oct stay interpretable.
  The bundle on disk is never edited: install() swaps the profile in at run time, through the same narrow hooks
  sample.py already uses, on the module (tool_agent) and on the agent instance:
    system prompt   agent._system_prompt = dedup_system_prompt(); set AFTER any checkpoint restore (a checkpoint
                    stores the system prompt it was captured with), and kept out of checkpoint restores
                    (checkpoints.AGENT_SKIP).
    tool schema     ta._PYTHON_TOOL_DESCRIPTION and the code parameter's description: one short sentence each; the
                    full manual is the system prompt.
    turn message    dedup_turn_message(): drops the standing lines the harness appends to every opener, shortens the
                    game-over, level-start and retained-function texts to the facts of this turn, then adds the
                    mode block (mode_block()).
    tool results    ta._terminal_action_stop_detail: the reason a batch stopped, without re-explaining game over.
    retry nudge     the harness's "you did not call a tool" follow-up keeps its first, event-specific sentence(s)
                    and drops the restated tool manual (dedup_nudge()).
    yielded turn    ARC3_YIELD_RESUME_PROMPT=state_only: a resumed turn re-opens with one continuation sentence and
                    the current board image instead of a full copy of the turn message (the harness's own option).
    carried history dedup_history(): when a job carries a conversation that was built under the original prompts
                    (a rebuilt snapshot or an older exact checkpoint), its user and tool messages get the same
                    turn-message and tool-result treatment, so the old standing lines are not resent every turn.
  The system prompt is written for the flag set of the 31.63 notebook (son and daniel variants; they differ only in
  the gameplay_changed explanation, which daniel's flags turn on). check_flags() refuses to run dedup under any
  other flag set rather than describe tools or mechanics the harness is not running.
  docs/plans/2026-10-06-prompt-dedup.md lists every original instruction, where it went, and every removed copy.
SRP/DRY check: Pass - prompt text only; the harness still builds every per-turn fact (lines are filtered, never
  rebuilt), sample.py still owns the play loop, modes.py the original profile's per-mode diff. The colour legend
  is read from the harness (grid_utils.ARC_COLOR_LEGEND), not retyped.
"""
from __future__ import annotations

import os
import re

PROFILES = ("dedup", "original")
DEFAULT_PROFILE = "dedup"

# The flags the dedup system prompt was written for (31.63 notebook, both variants). A different value means a
# different set of tools or messages, which this text would then misdescribe.
EXPECTED_FLAGS = {
    "MULTIMODAL_CONTEXT": "current_grid", "ARC3_DIFF_IMAGE": "1", "ARC3_ANIMATION": "1",
    "ARC3_MEMORY_SECTIONS": "off", "ARC3_PERSISTENT_FUNCTIONS": "1", "ARC3_PERSISTENT_FUNCTIONS_SCOPE": "game",
    "ARC3_PERSISTENT_FUNCTIONS_IMPORTS": "1", "ARC3_ACTION_INFO": "1", "EXPOSE_UNDO": "on",
    "ARC3_FRAME_DIFF_HINT": "1", "ARC3_LEVEL_TRANSFER_GUIDANCE": "1", "LOCAL_ANALYZER_TOOL_TIMEOUT": "30",
    "ARC3_GAMEOVER_DIFF_IMAGE": "1",
}
# Mechanisms the dedup text does not describe: they must stay off (unset counts as off).
EXPECTED_OFF = ("ARC3_ANIMATION_IMAGE", "ARC3_AUTO_FRAME_DIFF", "ARC3_DEATH_LEDGER", "ARC3_GAMEOVER_DIFF",
                "ARC3_SUMMARY_INTERVAL_TOKENS", "ARC3_WM_NUDGE_TURNS", "ARC3_STEP_VERIFICATION_HINT",
                "ARC3_PREFER_TOOL_CALLS", "ARC3_OPENER_COMMIT_HINT", "EXPOSE_RESET")

TOOL_DESCRIPTION = ("Run one Python snippet against the preloaded game state; the system prompt describes the "
                    "globals and `action(actions)`.")

CODE_DESCRIPTION = "Python code to run."

MODE_HEADER = "Instructions for this turn ({name} mode):"


def check_flags(env=os.environ) -> None:
    wrong = {k: env.get(k) for k, v in EXPECTED_FLAGS.items() if (env.get(k) or "").strip().lower() != v}
    wrong.update({k: env.get(k) for k in EXPECTED_OFF
                  if (env.get(k) or "").strip().lower() not in ("", "0", "off", "false", "no")})
    if wrong:
        raise RuntimeError(f"the dedup prompt profile was written for the 31.63 notebook's flags; these differ: {wrong}")


def dedup_system_prompt(ta, *, tool_output_tokens: int) -> str:
    """The whole standing manual, each instruction once. `ta` is the harness's tool_agent module (flags, legend)."""
    from inference.utils.grid_utils import ARC_COLOR_LEGEND
    border = ta._get_env_int("ARC3_NOOP_GUARD_BORDER", 4)
    gameplay_changed = (
        f"- `last_action_call_result` and each transition result carry `board_changed` (ANY cell differs, including "
        f"cells within {border} cells of the edge, where a step-budget bar usually sits) and `gameplay_changed` (a cell "
        "further in differs). An action that only moves the budget bar sets `board_changed` but not "
        "`gameplay_changed`.\n"
        if ta._explain_gameplay_changed() else "")
    return (
        "You are a coding agent solving a grid-based puzzle game.\n"
        "\n"
        "Game and goal:\n"
        "- The game has several levels. Your job is to clear every level, not just the current screen, in as few "
        "in-game actions as you can while staying reliable. `WIN` means the whole game is solved.\n"
        "- You are called once per turn. Each turn is one observe-plan-act cycle: re-understand the newest frame "
        "(focus on what changed most recently and update the target change you are after), update your working "
        "model in Python, choose the best next action or short sequence against the goal as you currently "
        "understand it, execute it, and re-evaluate next turn.\n"
        "- Levels usually build on mechanics learned in earlier levels, especially the most recent one. When a new "
        "level starts, build a new plan for its board rather than continuing the previous level's sequence. Carry "
        "the established mechanics forward as a starting hypothesis instead of rediscovering them, re-check anything "
        "new evidence contradicts, and inspect the board for unfamiliar elements or arrangements: new elements often "
        "bring the mechanics needed for the level, so test them with small, informative probes. Reassess the goal: "
        "it may stay the same and need the new mechanics, or it may change.\n"
        "\n"
        "What each turn message contains:\n"
        "- What your previous sequence executed and any events since (game over, level cleared, guard stops, "
        "animations), the current step and level, the valid actions right now, the functions you have retained, and "
        "images of the board. On a game's first turn there is no previous sequence: ground yourself in "
        "`current_frame` with a compact structural summary rather than restating the frame.\n"
        "- Some turns end with instructions for this turn only, under a mode name. Follow them for that turn; where "
        "they differ from the general guidance here (for example a smaller action budget), they win.\n"
        "\n"
        "Board representations:\n"
        f"- A board is a 64 x 64 grid of letter-coded ARC colours. Legend: {ARC_COLOR_LEGEND}. Raw numeric colour "
        "IDs are not available.\n"
        "- Each turn message attaches an image of the current grid; it and `current_frame.ascii` are the same frame. "
        "A diff image shows the cells that changed since your previous turn in their new colour, with unchanged "
        "cells dimmed to a dark navy that is not a game colour. After a game over two more images follow: the death "
        "frame (read the budget bar there) and a fatal-step diff image (last alive frame to death frame, drawn like "
        "the diff image). Use the images and the Python views together, whichever "
        "helps with the current uncertainty.\n"
        "- `.segmentation` is your primary view of a frame. It returns `{'nodes': [...], 'adjacency_list': [...]}`. "
        "Each node is one 4-connected same-colour object with `id` (ordered top-most, left-most), `color`, `hash` "
        "(colour and shape, ignoring position AND rotation: equal hashes mean matching shape up to rotation, not the "
        "same object), `rotation` (degrees clockwise from the canonical orientation: 0/90/180/270, reduced to 0/90 "
        "for 2-fold symmetric shapes, `None` for fully symmetric ones), `rotational_symmetry` (1, 2 or 4), "
        "`pose_hash` (rotation-sensitive), `shape_hash` (colour-independent pose shape), `pixels` (cell count), "
        "`boundary` (clockwise outer-perimeter corner points as `[row, col]`) and `children` (ids of objects fully "
        "enclosed by this one). `adjacency_list` holds `[i, j]` pairs of objects that share an edge.\n"
        "- `.ascii` is the frame as one newline-delimited string. Use it only to read a small, specific region; "
        "never scan or summarise the whole board with it.\n"
        "\n"
        "The `python` tool:\n"
        "- `python` is your only tool. Call it with one `code` string, in exactly the tool-call format shown "
        "elsewhere in this prompt for this model: no markdown fences, prose wrappers or other tool-call syntax, and "
        "never tool-call markup inside explanatory text. When you decide to call the tool, emit the call itself.\n"
        "- Globals, refreshed for every call: `current_frame`, `previous_frame`, `history`, `transitions`, "
        "`last_transition`, `last_action_call_result`, `last_action` (the name of the most recent real action, or "
        "`None`), `last_action_frame` (its post-action frame), `last_animation_frames`, `last_animation_timeline`, "
        "`valid_actions`, `frame_diff(before=None, after=None)` and `action(actions)`. Every frame view exposes "
        "only `.ascii`, `.segmentation`, `.step`, `.level` and `.shape` (a `(rows, cols)` tuple).\n"
        "- Python variables reset between calls. Eligible functions you define are retained for later calls "
        "throughout this game, including across level changes, and cleared when a new game starts; call them "
        "directly and redefine one to change it. A retained function's dependencies must also be available next "
        "call: pass snippet-specific data as arguments; use builtins, the provided globals, other retained "
        "functions, and explicit top-level imports (restored with the function) or imports inside it; plain "
        "top-level definitions without decorators or annotations, literal defaults. Tool results report which "
        "functions were retained and why any was rejected. A retained function is your earlier definition, not "
        "proof that it is correct: revise it when new evidence contradicts its assumptions, and after a level "
        "change check its level-specific assumptions against the new board before reusing it.\n"
        "- Importable standard-library modules: bisect, collections, copy, fractions, functools, heapq, itertools, "
        "json, math, operator, random, re, statistics, string.\n"
        f"- Each call has a hard limit of 30 seconds. Tool results are capped at about {tool_output_tokens} tokens "
        "and say when they were cut.\n"
        "- Output: print compact, decision-oriented summaries (object lists, diffs, coordinates, counts, tiny local "
        "crops) with `print(...)`, or assign a compact final object to `result`. Never print or echo whole boards. "
        "Writing a lot of code is fine; keep its output short. Keep snippets purpose-built rather than whole "
        "frameworks.\n"
        "- Call `python` as many times per turn as you need, until your code has a clear probe or plan; reading and "
        "computing cost no in-game actions. Do not ration calls while the state is unclear: inspect "
        "`current_frame`, `history` and `valid_actions` from Python rather than reasoning about the board by eye.\n"
        "\n"
        "History and frame comparisons:\n"
        "- `history` is a chronological Python list of entries with `.action`, `.frame` and `.result` (attributes, "
        "not dict keys); `history[i].frame` is the board after `history[i].action`. `history[-1].frame` is the "
        "CURRENT board, the same as `current_frame`, not the previous one.\n"
        "- `previous_frame` is the board before the most recent real action (`None` if there is none). "
        "`transitions` lists the real actions after the initial frame, each with `.action`, `.before_frame`, "
        "`.after_frame` (alias `.frame`) and `.result`; `last_transition` is the last of them or `None`. A refused "
        "action creates no transition.\n"
        "- For the most recent change, compare `previous_frame` to `current_frame`, or `last_transition."
        "before_frame` to `last_transition.after_frame`. Comparing `history[-1].frame` to `current_frame` compares "
        "the board with itself.\n"
        "- `frame_diff(before, after)` compares two frames (defaults: `previous_frame`, `current_frame`) and returns "
        "`changed_cell_count` and the lists `moved`, `rotated`, `appeared`, `disappeared`, `changed_color` and "
        "`resized`; unchanged objects are omitted. It matches same-colour 4-connected components, so one game "
        "object may be split in several and touching same-colour objects may merge; with several similar "
        "components the matching can be wrong. `moved` entries that also turned carry `rotated_by` (degrees "
        "clockwise); `rotated` is rotation in place. `changed_color` needs identical cells with a new colour and "
        "gives `at`, `pixels`, `before_color`, `after_color`, `before_hash`, `after_hash`. `resized` covers "
        "same-colour components with overlapping footprints whose size changed, budget bars and backgrounds "
        "included (`at_before`, `at_after`). `appeared` and `disappeared` give `bbox` as `[r0, c0, r1, c1]`. "
        "Example: `frame_diff(history[-3].frame, history[-2].frame)`.\n"
        "- One action can play a short animation; `current_frame` is its final frame. When the last executed "
        "action of your latest call animated, `last_action_call_result['animation']` gives `frames`, "
        "`transient_pixels` and `transient_bbox`: cells that changed and changed BACK, which appear in no other "
        "frame. `last_animation_frames` holds that action's frames as views (index 0 first, the last one the "
        "settled board; after a death they are the FATAL action's frames, not the reset's); crop their `.ascii` "
        "yourself. `last_animation_timeline` is a dict with `action`, `frames` and `steps`, one entry per step that "
        "changed anything, each with `step`, `changed`, `bbox`, and either `changes` (`old>new @ (row,col)`) or "
        "`transitions` (counts per colour change). Reading them costs no action; they are empty when nothing "
        "animated. An action that animated but left the board area unchanged still did something: read its "
        "animation before concluding it failed.\n"
        "\n"
        "Actions:\n"
        "- Use only the actions valid right now. `UP`, `DOWN`, `LEFT` and `RIGHT` are directional controls; what "
        "they move depends on the game. `SPACE` performs a game-specific action (interact, select, rotate, "
        "attach/detach, execute): test it rather than assume. `MOUSE` clicks a cell: pass integer `row` and `col` "
        "fields from 0 to 63, zero-based from the top-left, `row` downward and `col` rightward (x/y fields are "
        "rejected). `UNDO` reverses a previous action, usually the last turn; check what it restores. It cannot "
        "undo a game over.\n"
        "- Execute actions only by calling `action(actions)` inside Python, never as text in your reply. It takes an "
        "ordered list such as `['LEFT']` or `[{'action': 'MOUSE', 'row': 4, 'col': 7}]` and returns "
        "`last_action_call_result` (batch totals, executed and skipped actions, stop reasons; `{}` before any call), "
        "which stays available, across turns too, until the next action call. After it returns, every global is "
        "refreshed before your next statement.\n"
        "- Once your code has found a reliable sequence, batch it in one call. You may call `action(...)` several "
        "times in one snippet, including in a search or control loop.\n"
        "- If a result reports `game_over`, `level_completed`, `run_complete` or `done`, stop acting in that "
        "snippet; the next turn shows the new state.\n"
        "- Results are flags: `game_over` = this attempt FAILED (it never means the run is won); `level_completed` = "
        "one level cleared; `run_complete`/`done` = the whole game is won. Each transition result has "
        "`automatic=True` for an action the harness took (such as the reset after a death) and `automatic=False` "
        "for yours.\n"
        f"{gameplay_changed}"
        "\n"
        "Step budget and deaths:\n"
        "- Many games show a step budget: a bar or strip of small blocks flush against an edge that shrinks with "
        "each action. It is HUD, not a puzzle object (unless evidence shows it interacts with the puzzle): do not "
        "click through it or treat its change as progress, and "
        "after every action check whether gameplay objects changed or only the bar did. It is also your remaining "
        "budget: read it and plan routes that fit within it.\n"
        "- A game over (death) comes from the action itself (for example a hazard cell or a forbidden move) or from "
        "the budget running out. The harness then resets the level automatically to its starting board, keeping "
        "completed levels. On the next turn `history[-1].action` is 'RESET', `history[-2]` holds the fatal action "
        "and the death frame (the board after it), and `history[-3].frame` the board just before it. "
        "`last_action_call_result` still describes the call that died.\n"
        "- Diagnose a death before acting again. The bar shrinking is normal; it was a budget death ONLY if the bar "
        "is fully (or almost fully) depleted in the death frame: then reach the goal in fewer actions or find a way "
        "to restore the bar. If the bar had budget left, the fatal action itself killed you: check the cell it "
        "targeted and choose a different approach.\n"
        "- The game is deterministic: re-submitting the sequence that died dies again. Change the plan before the "
        "fatal point (route, action or timing), and treat the death as evidence against the belief that it should "
        "have worked.\n"
        "- When a guard stops a batch, only the actions before the stop ran: re-locate from `current_frame` rather "
        "than counting submitted actions.\n"
        "\n"
        "How to play well:\n"
        "- Treat the board as a scene of objects, blockers, targets, adjacency, containment, motion and symmetry. "
        "Entities are usually connected multi-cell shapes (2x2, 2x3, 3x3 or longer patterns), sometimes single "
        "cells. Some games have no player avatar: the state may be an object, region, cursor, selector or the "
        "whole configuration. Backgrounds are often large white, grey or black regions, but verify that by area, "
        "stability and boundaries.\n"
        "- Use coordinates to target actions or describe local evidence, not as the objective itself.\n"
        "- A strong loop: summarise the board, infer the change you want, write a small scorer or search over "
        "candidate sequences, execute the best probe or plan, then inspect exactly what changed. If confidence is "
        "low, program a discriminating probe and revise from the result.\n"
        "- Track objects by colour, overlap, bounding-box proximity, area change and edge contact, not by exact "
        "coordinates alone. Summarise diffs as changed cells, colour transitions, appearing and disappearing "
        "components, movement candidates and small local slices.\n"
        "- When the goal is understood but the best order is not, search rather than guess: an explicit search "
        "(BFS is usually safest for moving an agent to a target), DFS, flood fill, shortest-path, beam or limited "
        "action-sequence search, or custom heuristics. Once the state variables and action effects are understood, "
        "stop probing and search the inferred state space.\n"
    )


# ------------------------------------------------------------------ turn message

# Lines the harness appends to every turn message that the dedup system prompt says once (exact text as built by
# ToolAgent._build_user_prompt in the 31.63 bundle; prompts.TOOL_CALL_FORMAT_GUIDANCE).
STANDING_LINES = frozenset({
    "Only tool: `python`. It receives `current_frame`, `previous_frame`, `history`, `transitions`, `last_transition`, "
    "`valid_actions`, `last_action_call_result`, `frame_diff(before, after)`, and `action(actions)`.",
    "Only letter-coded board views and lightweight metadata are exposed; raw numeric color IDs are not available.",
    "Keep tool output compact: use `current_frame.segmentation` as the primary view, and `current_frame.ascii` only "
    "for a small specific region; never print full boards.",
    "For the most recent change, compare `previous_frame` to `current_frame`, or `last_transition.before_frame` to "
    "`last_transition.after_frame`; `history[-1].frame` is the current frame, not the previous one.",
    "Use Python to inspect the evidence from the newest history, and search or score candidate actions or short "
    "sequences against the current goal as you currently understand it.",
    "Focus on what changed most recently in `history`, update the target environment change if needed, and separate "
    "gameplay-object changes from HUD-only changes.",
    "Ground yourself in `current_frame` before acting, but start with a compact structural summary rather than "
    "restating the full frame.",
    "When ready, call `action(actions)` from inside the `python` tool with the best valid action or ordered batch "
    "selected by your code. If your code has found a reliable short sequence, prefer batching it in one call.",
    "You may call `action(actions)` more than once in one Python snippet if your search or control loop needs it.",
    "You may call `action(actions)` more than once in one Python snippet if your search or control loop needs it, "
    "but stop immediately if a result reports `game_over`, `run_complete`, `level_completed`, or `done`.",
    "When calling `python`, emit exactly the tool-call format shown elsewhere in this prompt for this model. Use only "
    "that format; do not add markdown fences, prose wrappers, or alternate tool-call syntax. Do not quote or place "
    "tool-call markup inside explanatory text; when you decide to call the tool, emit the tool call itself.",
    "If you use MOUSE, include integer row and col arguments.",
    "Do NOT re-submit this same series of moves: the game is deterministic, so replaying the sequence that just "
    "killed you will kill you again. Change the plan BEFORE the fatal point - a different route, action, or timing. "
    "If you believe the same moves 'should' work, that belief is exactly what this death falsified; record the "
    "correction in your world model instead of retesting it.",
})

GAME_OVER_START = "GAME OVER occurred during the previous sequence. This means the attempt FAILED"
GAME_OVER_NOTICE = ("GAME OVER during the previous sequence: this attempt failed and the level was automatically reset "
                    "to its starting board (completed levels are kept).")
LEVEL_START_START = "You have completed the previous level. `current_frame` now contains the starting board"
LEVEL_START_NOTICE = "You cleared the previous level. `current_frame` now shows the starting board of the new level."
FATAL_LINE = re.compile(r"^The game over occurred immediately after action (.+?)\. Apply the BAR RULE above.*$")
RETAINED = re.compile(r"^(Your retained functions from earlier Python calls [^:]*: .*?)\. These are your previous "
                      r"definitions, available to call directly\. Their presence does not mean they are correct; "
                      r"revise them if new evidence contradicts their assumptions\.$")
# Image captions: the name and what the picture is of stay; how the picture is drawn is said once, in the system prompt.
IMAGE_CAPTION = re.compile(r"^((?:Diff|Death frame|Fatal step diff) image(?: \([^)]*\))?):\s.+$")
# Sentences inside event lines that restate a standing rule; the event's facts stay, the rule is in the system prompt.
SENTENCE_DROPS = [re.compile(p) for p in (
    r" Do not count submitted or executed actions to update your position; re-locate from current_frame\.",
    r" Those cells are in neither `history\[-3\]\.frame` nor `history\[-2\]\.frame` - read `[a-z_]+` to see "
    r"what happened between them\.",
    r" Whatever this action did is visible only there - read `[a-z_]+` before concluding it failed\.",
    r" `last_animation_(?:timeline|frames)` shows them\.",
    r" Check level-specific assumptions against the new board before reusing them\.",
)]


def dedup_turn_lines(text: str) -> tuple[str, int]:
    """The harness's turn message with every standing line removed or shortened to this turn's facts. Returns the
    text and how many lines were dropped or shortened. Idempotent: already-dedup text comes back unchanged."""
    out, changed = [], 0
    for line in text.split("\n"):
        if line in STANDING_LINES:
            changed += 1
            continue
        if line.startswith(GAME_OVER_START):
            out.append(GAME_OVER_NOTICE)
            changed += 1
            continue
        if line.startswith(LEVEL_START_START):
            out.append(LEVEL_START_NOTICE)
            changed += 1
            continue
        m = FATAL_LINE.match(line)
        if m:
            out.append(f"The fatal action was {m.group(1)}.")
            changed += 1
            continue
        m = RETAINED.match(line)
        if m:
            out.append(m.group(1) + ".")
            changed += 1
            continue
        m = IMAGE_CAPTION.match(line)
        if m:
            out.append(m.group(1) + ":")
            changed += 1
            continue
        for rx in SENTENCE_DROPS:
            line, n = rx.subn("", line)
            changed += n
        out.append(line)
    # LEVEL_START_USER_PROMPT is three paragraphs: the notice replaced the first; drop the other two
    text = "\n".join(out)
    for para in ("\n\nStart from the mechanics you established on the previous level;",
                 "\n\nReassess the goal: does the previous objective still apply,"):
        i = text.find(para)
        if i >= 0:
            j = text.find("\n", i + 2)
            text = text[:i] + (text[j:] if j >= 0 else "")
            changed += 1
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip("\n") if text.strip() else text, changed


def mode_block(name: str, instructions: str) -> str:
    """The selected mode's turn-only instructions, as the last part of the turn message. Empty for Stock."""
    body = (instructions or "").strip()
    return f"{MODE_HEADER.format(name=name)}\n{body}" if body else ""


# ------------------------------------------------------------------ tool results, nudge, history

def terminal_stop_detail(reason):
    """ta._terminal_action_stop_detail without re-explaining what a game over is (system prompt says it once)."""
    return {
        "run_complete": "No further actions were executed: the run is complete.",
        "game_over": "No further actions were executed: that action ended the attempt (GAME OVER); the level is "
                     "reset before your next turn.",
        "level_completed": "No further actions were executed: that action completed the level.",
        "done": "No further actions were executed: the environment reported done.",
    }.get(reason, "No further actions were executed: the previous action reached a terminal state.")


NUDGE_SPLIT = "Then investigate and revise your working world model"


def dedup_nudge(content: str) -> str:
    """The harness's no-tool-call follow-up: keep its event sentence(s), drop the restated manual."""
    if not isinstance(content, str) or NUDGE_SPLIT not in content:
        return content
    head = content.split(NUDGE_SPLIT, 1)[0].strip()
    return f"{head} Call the `python` tool now.".strip()


def _map_text(content, fn):
    if isinstance(content, str):
        return fn(content)
    if isinstance(content, list):
        return [{**p, "text": fn(p["text"])} if isinstance(p, dict) and p.get("type") == "text"
                and isinstance(p.get("text"), str) else p for p in content]
    return content


def dedup_text_any(text: str) -> str:
    """Turn-message treatment for any carried user or tool text (no mode block: past turns keep what they had)."""
    text = dedup_nudge(text)
    new, _ = dedup_turn_lines(text)
    for reason in ("run_complete", "game_over", "level_completed", "done"):
        old = ORIGINAL_STOP_DETAILS.get(reason)
        if old and old in new:
            new = new.replace(old, terminal_stop_detail(reason))
    return new


def dedup_history(messages: list) -> tuple[list, int]:
    """Carried conversation built under the original prompts, with the same per-turn treatment. Returns the new
    list and how many messages changed. Assistant messages (the model's own words) are never touched."""
    out, changed = [], 0
    for m in messages:
        if isinstance(m, dict) and m.get("role") in ("user", "tool"):
            new = _map_text(m.get("content"), dedup_text_any)
            if new != m.get("content"):
                m = {**m, "content": new}
                changed += 1
        out.append(m)
    return out, changed


ORIGINAL_STOP_DETAILS: dict = {}


def install(profile: str, ta, agent, *, reasons=("run_complete", "game_over", "level_completed", "done")) -> dict:
    """Switch an agent (and the harness module) to a profile. Call after any checkpoint restore. Returns a record
    for the sample's result. In dedup, the caller's _build_user_prompt hook calls turn_message(), which leaves the
    mode block in agent._dedup_turn; the retained-functions wrapper below appends it, so the mode instructions are
    the last text before the board images."""
    if profile not in PROFILES:
        raise ValueError(f"unknown prompt profile {profile!r}")
    if profile == "original":
        return {"prompt_profile": "original"}
    check_flags()
    if not ORIGINAL_STOP_DETAILS:
        ORIGINAL_STOP_DETAILS.update({r: ta._terminal_action_stop_detail(r) for r in reasons})
    os.environ["ARC3_YIELD_RESUME_PROMPT"] = "state_only"
    ta._PYTHON_TOOL_DESCRIPTION = TOOL_DESCRIPTION
    ta._terminal_action_stop_detail = terminal_stop_detail
    agent._system_prompt = dedup_system_prompt(ta, tool_output_tokens=agent._tool_output_tokens)
    history, n = dedup_history(list(getattr(agent, "_history_messages", []) or []))
    agent._history_messages = history
    agent._dedup_turn = {"block": "", "resuming": False}
    original_append = agent._append_context_message
    original_retained = agent._retained_function_context

    original_tools = agent._tools

    def append_context_message(messages, message):
        # every user message the harness adds (opener, resume, nudge, images): the same idempotent treatment
        if isinstance(message, dict) and message.get("role") == "user":
            message["content"] = _map_text(message.get("content"), dedup_text_any)
        return original_append(messages, message)

    def tools(state_path):
        out = original_tools(state_path)
        for t in out:
            props = ((t.get("function") or {}).get("parameters") or {}).get("properties") or {}
            if "code" in props:
                props["code"]["description"] = CODE_DESCRIPTION
        return out

    def retained_function_context():
        turn = agent._dedup_turn
        text = original_retained()          # always called: it also clears the harness's one-shot notice
        if turn["resuming"]:
            text = ""                       # a resumed turn's opener above already lists them
        else:
            text = "\n".join(RETAINED.sub(r"\1.", ln) for ln in text.split("\n"))
        block, turn["block"] = turn["block"], ""
        return text + (f"\n\n{block}" if block else "")
    agent._append_context_message = append_context_message
    agent._tools = tools
    agent._retained_function_context = retained_function_context
    return {"prompt_profile": "dedup", "carried_messages_rewritten": n}


def turn_message(agent, text: str, name: str, instructions: str) -> tuple[str, dict]:
    """dedup turn message for this invocation of _build_user_prompt; the mode block is queued for the opener only
    (a resumed turn re-opens with the harness's short continuation, the opener with the block is still above)."""
    resuming = bool(getattr(agent, "_resume_after_yield", False))
    new, changed = dedup_turn_lines(text)
    block = "" if resuming else mode_block(name, instructions)
    agent._dedup_turn = {"block": block, "resuming": resuming}
    return new, {"profile": "dedup", "standing_lines_removed": changed,
                 "mode_lines": len(block.splitlines()) - 1 if block else 0, "resuming": resuming}

"""
Author: Claude Opus 5 (Bubba)
Date: 13-September-2026
PURPOSE: Build the prompt-arm Kaggle dataset bundles from the duck control bundle, so
every arm is a recorded, re-runnable edit rather than a hand-patched upload. Arm B is
the control minus four assertions; arms C/D/E/F each stack exactly one further change on
top of B, because B is the measured reference arm (it beat control 10 -> 15 level clears).
C adds a mechanics-possibility block, D swaps the 16 board glyphs for distinct consonant
capitals, E withholds the text board until one action has been executed, F adds a
commit-to-hypothesis rule. I (16-Sep-2026, Dr. Fable's step-5 call 1.2) offers RESET to
the model behind a rate guard enforced in the solver. Consumes the unpacked control bundle
(keithtyser/duck-qwen38-nvfp4-mtp-vllm-smoke-v1). Emits a bundle directory per arm,
ready for `kaggle datasets create/version`.
SRP/DRY check: Pass - single definition of what each arm changes; build_notebooks.py
consumes the resulting dataset slugs and never re-states an edit.
"""

import pathlib
import shutil
import sys

PROMPTS = "src/ARC3-Inference/inference/agent/prompts.py"
TOOL_AGENT = "src/ARC3-Inference/inference/agent/tool_agent.py"
GRID_UTILS = "src/ARC3-Inference/inference/utils/grid_utils.py"
SANDBOX = "src/ARC3-Inference/inference/agent/python_tool_sandbox.py"
ACTION_NAMES = "src/ARC3-Inference/inference/agent/action_names.py"
SOLVER = "src/ARC3-Inference/inference/framework/solver.py"

STACKED_ON_B = ("C", "D", "E", "F", "G", "H", "I")

# Arm B: the word "puzzle" also appears in the base system prompt line in tool_agent.py,
# so deleting it from prompts.py alone leaves the assembled prompt carrying it and the
# in-process probe fails. Caught by a full-tree manifest diff against the shipped bundle.
TOOL_AGENT_DELETIONS = [
    ('prompt = "You are a coding agent solving a grid-based puzzle game."',
     'prompt = "You are a coding agent solving a grid-based game."'),
]

# Arm B: four deletions, nothing added. Each is (old, new) applied to prompts.py.
DELETIONS = [
    ("- You are solving a multi-level grid puzzle game.",
     "- You are solving a multi-level grid game."),
    ("boards are presented as 64 x 64 color grids",
     "boards are presented as color grids"),
    ("- Some games are logic or layout puzzles with no explicit player avatar",
     "- Some games are logic or layout games with no explicit player avatar"),
    ('    "- In many games, a long horizontal or vertical line near an edge is a timer or '
     'remaining-steps bar. It often shrinks or changes each step. If you identify such a bar, '
     'do not get distracted by it or treat it as core gameplay state unless there is concrete '
     'evidence that it interacts with the puzzle mechanics.\\n"\n'
     '    "A common failure mode is to mistake a segmented edge bar for clickable puzzle pieces. '
     'If a repeated strip of small blocks sits flush against the top, bottom, left, or right '
     'border and actions only change that strip while the interior board stays the same, '
     'classify it as HUD/timer state, not as an object to click through segment by segment. '
     'DON\'T DO THIS!\\n"\n',
     ""),
]

# Arm C: appended to the game-overview bullets. Every line is phrased as a possibility,
# never as a diagnosis of the current game, and each one names a mechanic the public 25
# actually exercise (LATENT_MECHANICS_IN_THE_PUBLIC_25.md) that the prompt has no word for.
MECHANICS_BLOCK = (
    '    "- The visible board may be a window onto a larger world, and that window can move. '
    'If the whole scene shifts at once, the frame moved, not the contents; the same row/col '
    'may not mean the same place as it did last turn.\\n"\n'
    '    "- What you control may change. An action may hand control to a different object '
    'instead of acting on the board, so do not assume there is exactly one controllable thing '
    'for the whole game.\\n"\n'
    '    "- State that decides the outcome may not be drawn on the board: what is being carried, '
    'what was collected, or what happened on an earlier attempt can change what the same action '
    'does now.\\n"\n'
    '    "- Order can matter as much as position. A set of things in the right places may still '
    'be wrong if they are read in a sequence.\\n"\n'
    '    "- Something that looks solved can come un-solved by a later action, and parts of the '
    'board may act on their own between your actions, with or against you.\\n"\n'
    '    "- Control may be indirect: you may move something that drags what you care about, or '
    'set values that are read together as a code rather than acting one at a time.\\n"\n'
)

# Arm F: commit-to-hypothesis. No claim about any particular game's mechanics; it is a
# rule about how to spend turns, and it names level transition as the test signal.
COMMIT_BLOCK = (
    '    "- Exploration is for building one hypothesis, not for collecting observations. '
    'Once a single hypothesis explains every action you have taken so far, stop probing: '
    'write down the plan of actions that hypothesis says will complete the level, and execute '
    'that plan.\\n"\n'
    '    "- Reaching the next level is the test. If the plan runs to the end and the level did '
    'not change, the hypothesis was wrong -- say which part of it the outcome refutes and replace '
    'it, rather than resuming undirected probing or repeating the same plan.\\n"\n'
    '    "- Prefer a short plan you can falsify over a long one you cannot. A plan whose failure '
    'tells you nothing is worse than a plan half its length whose failure names the wrong '
    'assumption.\\n"\n'
)

# Arm D: the 16 board glyphs. The control set is "WwgGcBMPRbSYOrNp" -- six case-pairs
# (W/w, g/G, B/b, R/r, N/n-ish, P/p) that are the same letter in two cases, which is the
# confusable part. Replacement is the Boss's own allowed set QWRTYSDFGHKZXCVBM in his own
# order, first 16 letters, assigned to colors 0..15 in index order. NO MNEMONIC -- the
# characters carry no meaning and are not supposed to; the legend in the system prompt is
# what tells the model the mapping. Boss directive 13-Sep-2026: "forget the fucking
# mnemonic, they can just be literally whatever." Keeping them arbitrary also removes the
# confound in the last build, where seven of sixteen were arbitrary and nine were not.
_BOSS_GLYPHS = "QWRTYSDFGHKZXCVBM"[:16]
_COLOR_NAMES = (
    "white", "light gray", "gray", "dark gray", "charcoal", "black",
    "magenta", "pink", "red", "blue", "sky blue", "yellow",
    "orange", "dark red", "light green", "purple",
)
GLYPH_COLORS = tuple(zip(_COLOR_NAMES, _BOSS_GLYPHS))
GLYPH_CHARS = "".join(char for _, char in GLYPH_COLORS)

GRID_UTILS_OLD = '''ARC_COLOR_CHARS = "WwgGcBMPRbSYOrNp"
ARC_COLOR_LEGEND = (
    "W=white, w=light gray, g=gray, G=dark gray, c=charcoal, B=black, "
    "M=magenta, P=pink, R=red, b=blue, S=sky blue, Y=yellow, O=orange, "
    "r=dark red, N=light green, p=purple"
)'''

# The legend is DERIVED from the same table the chars come from. A hand-written legend is
# how "puzzle" survived in two files; a stale legend here would make the prompt lie about
# the board in a way no probe on prompts.py would ever catch.
GRID_UTILS_NEW = '''ARC_COLOR_NAMES = (
    {names}
)
ARC_COLOR_CHARS = "".join(char for _, char in ARC_COLOR_NAMES)
ARC_COLOR_LEGEND = ", ".join(f"{{char}}={{name}}" for name, char in ARC_COLOR_NAMES)'''.format(
    names="\n    ".join(f'("{name}", "{char}"),' for name, char in GLYPH_COLORS)
)

# Arm E: withhold both text renderings of the board until one action has been executed,
# so the first hypothesis has to come off the image that is already in the user message.
# Gating .ascii alone is a no-op -- prompts.py names .segmentation as the PRIMARY view --
# so the grid the sandbox segments from is withheld in the same place.
WITHHOLD_OLD = '''def _ascii_frame_view_payload(frame: Frame | None) -> dict[str, Any] | None:
    view = _to_ascii_frame_view(frame)
    if view is None:
        return None
    return {
        "ascii": view.ascii,
        "step": view.step,
        "level": view.level,
        "shape": [int(view.shape[0]), int(view.shape[1])],
        "grid": [list(row) for row in frame.grid],
    }'''

WITHHOLD_NEW = '''_WITHHOLD_TEXT_BOARD_UNTIL_STEP = 1
_WITHHOLD_TEXT_BOARD_MESSAGE = (
    "(text board withheld until you have executed at least one action -- read the grid image "
    "in the user message, say what you think this game is, then act)"
)


def _ascii_frame_view_payload(
    frame: Frame | None, *, withhold: bool = False
) -> dict[str, Any] | None:
    view = _to_ascii_frame_view(frame)
    if view is None:
        return None
    if withhold and view.step < _WITHHOLD_TEXT_BOARD_UNTIL_STEP:
        return {
            "ascii": _WITHHOLD_TEXT_BOARD_MESSAGE,
            "step": view.step,
            "level": view.level,
            "shape": [int(view.shape[0]), int(view.shape[1])],
            "grid": None,
        }
    return {
        "ascii": view.ascii,
        "step": view.step,
        "level": view.level,
        "shape": [int(view.shape[0]), int(view.shape[1])],
        "grid": [list(row) for row in frame.grid],
    }'''

# This builder is shared by three payload paths: current_frame, every history frame, and
# every animation frame. Gating on step alone withholds the step-0 frame FOREVER, so at
# turn 50 the agent still could not read the starting position out of `history[0]` -- a
# far stronger manipulation than "no text board on the first turn", and one that would
# plausibly hurt for a reason having nothing to do with first-turn hypothesis forming.
# The withhold is therefore requested at the current_frame call site only.
WITHHOLD_CALLSITE_OLD = (
    "            current_frame_payload = _ascii_frame_view_payload(refreshed_frame)"
)
WITHHOLD_CALLSITE_NEW = (
    "            current_frame_payload = _ascii_frame_view_payload(\n"
    "                refreshed_frame, withhold=True\n"
    "            )"
)

# With an empty grid the sandbox would hand segment_layer nothing and return an empty
# structure, which reads as "the board is empty" rather than "the board is withheld".
# grid is None rather than [] so a withheld board is unambiguous even to code that pokes
# the private _grid attribute (Sherlock, 13-Sep-2026); the guard tests `is None` so a
# genuinely empty board could never be mistaken for a withheld one.
SANDBOX_OLD = '''        @property
        def segmentation(self):
            if self._segmentation is None:
                self._segmentation = segment_layer(self._grid, COLOR_CHARS)
            return self._segmentation'''

SANDBOX_NEW = '''        @property
        def segmentation(self):
            if self._grid is None:
                return self.ascii
            if self._segmentation is None:
                self._segmentation = segment_layer(self._grid, COLOR_CHARS)
            return self._segmentation'''

WITHHOLD_PROMPT_BLOCK = (
    '    "- On the first turn only, `current_frame.ascii` and `current_frame.segmentation` are '
    'withheld for the current frame and return a short notice instead of the board. The grid image in the user message '
    'is the board. State what you think the game is from the image, then execute an action; both '
    'text views are available from the next turn on.\\n"\n'
)


# Arm G: make the IMAGE the default view and demote both text renderings to measuring
# instruments. Boss directive 13-Sep-2026: the worry is the model fixates on the text board
# and ignores the perfectly good picture it already has, then burns the budget doing
# arithmetic on a grid whose answer was obvious at a glance. Unlike arm E this withholds
# nothing -- ascii and segmentation stay available every turn; only the instruction about
# WHEN to reach for them changes. The two shipped lines below both assert segmentation is
# the primary view, which is the assertion under test, so both are replaced, not appended to.
IMAGE_FIRST_OLD_1 = (
    "    \"- The raw numeric grid is intentionally not exposed. Use `current_frame.segmentation` "
    "as your primary view of the board -- objects, colors, shapes, containment, adjacency, and "
    "cross-frame object hashes. Use `current_frame.ascii` only to read a small, specific region; "
    "do not scan the whole board with it.\\n\"\n"
)
IMAGE_FIRST_NEW_1 = (
    "    \"- The grid image in the user message is your primary view of the board. Look at it "
    "first and read what the board is doing from it. `current_frame.segmentation` and "
    "`current_frame.ascii` are measuring instruments, not the board: reach for them when you "
    "need an exact cell-by-cell or line-and-grid measurement the picture cannot settle -- "
    "coordinates, pixel counts, alignment, whether two things are adjacent. Most of the time a "
    "glance at the image is enough to tell whether your hypothesis is holding. The raw numeric "
    "grid is intentionally not exposed.\\n\"\n"
)
IMAGE_FIRST_OLD_2 = (
    "    \"- Use `current_frame.segmentation` as your primary view of the board -- objects, "
    "colors, containment, adjacency, and cross-frame object hashes.\\n\"\n"
    "    \"- Use `current_frame.ascii` only to read a small, specific region of the board when "
    "`segmentation` is not enough; never use it to scan or summarize the whole board.\\n\"\n"
)
IMAGE_FIRST_NEW_2 = (
    "    \"- Read the board off the image first. Use `current_frame.segmentation` and "
    "`current_frame.ascii` only when you need an exact measurement the image cannot settle.\\n\"\n"
)
IMAGE_FIRST = ((IMAGE_FIRST_OLD_1, IMAGE_FIRST_NEW_1), (IMAGE_FIRST_OLD_2, IMAGE_FIRST_NEW_2))


ANCHOR = '    f"- Color legend: {ARC_COLOR_LEGEND}.\\n"\n'


# Arm H: ACTION7 is listed in valid_actions on every step of every game that exposes it,
# because to_model_action() falls back to the raw string. But ENGINE_TO_MODEL_ACTION never
# maps it, so to_engine_action() returns None and solver.py rejects the call with
# "Unknown action at index 1". The agent tries it and is refused - 22 attempts across 12
# bp35 passes, zero committed. See docs/trace-findings/2026-09-14-action7-is-unexecutable.md.
# The neutral round-trip below is exactly the first half of harnesses/action7-anim; the
# animation-metadata half of that patch is deliberately NOT taken, so this arm is one
# variable.
ACTION_NAMES_OLD = '    "ACTION6": "MOUSE",\n    "RESET": "RESET",'
ACTION_NAMES_NEW = (
    '    "ACTION6": "MOUSE",\n'
    '    # ACTION7 is exposed by the engine and valid in several games, but was missing\n'
    '    # here -- so the model could see it in valid_actions yet to_engine_action()\n'
    '    # returned None and the call was rejected. Neutral round-trip makes it\n'
    '    # executable; its game-specific meaning is left to the model to probe.\n'
    '    "ACTION7": "ACTION7",\n'
    '    "RESET": "RESET",'
)

# Anchored on the action() contract bullets, not the colour legend, because this is a
# statement about how actions work. Phrased as executable-and-unknown, never as "undo" -
# the Boss's point stands that undo is not what ACTION7 means in every game.
ACTION7_PROMPT_OLD = (
    '    "- After `action(actions)` returns, `current_frame`, `previous_frame`, `history`, '
    '`transitions`, `valid_actions`, and `last_action_result` are refreshed.\\n"'
)
ACTION7_PROMPT_NEW = ACTION7_PROMPT_OLD + (
    '\n    "- `ACTION7` is a valid, executable game action whenever it appears in '
    '`valid_actions`. Its meaning is not fixed across games; infer it from a safe probe and '
    'the returned before/after state rather than assuming it means undo, confirm, or back.\\n"'
)


# Arm I: RESET offered to the model behind a guard (docs/plans/
# 2026-09-16-dr-fable-calls-on-the-step5-review.md, call 1.2). Two facts from the source
# shape this patch:
# 1. RESET is hidden, not blocked. TAAF's GameState.available_actions always includes id 0,
#    to_engine_action("RESET") resolves, and step_env only checks available_actions -- so a
#    model that typed RESET in arms A-H would have executed it. None did: every RESET in
#    jobs 1, 2, 4 and 10 followed a GAME_OVER. The guard therefore lives in step_env, and
#    the menu only advertises what step_env will accept.
# 2. On Kaggle every RESET is a level reset. The notebook pins ONLY_RESET_LEVELS=true, so
#    arcengine never escalates to a full restart; the provenance cell asserts the pin.
# "Never two in a row" counts the harness's own auto-reset after GAME_OVER as the previous
# RESET (a second RESET on a just-reset level only spends an action), and the game's
# opening counts too. The one-per-20 window counts model-chosen RESETs only, so a death
# never uses up the model's budget.
SOLVER_NAMES_OLD = '''def _engine_action_names(game: taaf.game.Game) -> list[str]:
    names: list[str] = []
    for action_id in game.current_state.available_actions:
        try:
            name = arcengine.GameAction.from_id(int(action_id)).name
        except Exception:
            continue
        if name == "RESET":
            continue'''
SOLVER_NAMES_NEW = '''# RESET guard: a model-chosen RESET is refused when the previous executed action was a
# RESET (including the harness auto-reset and the game's opening), or when it would land
# within _RESET_MIN_ACTION_GAP actions of the last model-chosen RESET.
_RESET_MIN_ACTION_GAP = 20


def _engine_action_names(
    game: taaf.game.Game, *, include_reset: bool = False
) -> list[str]:
    names: list[str] = []
    for action_id in game.current_state.available_actions:
        try:
            name = arcengine.GameAction.from_id(int(action_id)).name
        except Exception:
            continue
        if name == "RESET" and not include_reset:
            continue'''

SOLVER_FIELDS_OLD = '''    last_engine_action: str | None = None
    token_baseline: int = 0
'''
SOLVER_FIELDS_NEW = '''    last_engine_action: str | None = None
    token_baseline: int = 0
    model_reset_positions: list[int] = field(default_factory=list)
    reset_refusals: int = 0
'''

SOLVER_METHODS_OLD = '''    _viewer_events_flushed: int = field(default=0, init=False, repr=False)

    def current_frame(self) -> Frame:'''
SOLVER_METHODS_NEW = '''    _viewer_events_flushed: int = field(default=0, init=False, repr=False)

    def reset_refusal(self) -> str | None:
        if self.last_engine_action in (None, "RESET"):
            return (
                "RESET refused: the previous action was already a RESET, so the level "
                "is at its starting state."
            )
        if self.model_reset_positions:
            gap = self.action_count + 1 - self.model_reset_positions[-1]
            if gap < _RESET_MIN_ACTION_GAP:
                return (
                    f"RESET refused: at most one RESET per {_RESET_MIN_ACTION_GAP} actions, "
                    f"and the last one was {gap - 1} actions ago."
                )
        return None

    def model_action_names(self) -> list[str]:
        return _engine_action_names(
            self.game, include_reset=self.reset_refusal() is None
        )

    def log_reset_guard(self, outcome: str, detail: str = "") -> None:
        run = self.game.game_run
        game_id = run.game_id if run is not None else self.game_index
        print(
            f"RESET_GUARD {outcome} game={game_id} pass={self.pass_index} "
            f"action_num={self.action_count} {detail}".rstrip(),
            flush=True,
        )

    def current_frame(self) -> Frame:'''

SOLVER_ANALYZER_OLD = "                        valid_actions=_engine_action_names(self.game),"
SOLVER_ANALYZER_NEW = "                        valid_actions=self.model_action_names(),"

# Both remaining call sites (_error_payload and the per-action payload) are session methods.
SOLVER_PAYLOAD_OLD = '"valid_actions": to_model_actions(_engine_action_names(self.game)),'
SOLVER_PAYLOAD_NEW = '"valid_actions": to_model_actions(self.model_action_names()),'

SOLVER_STEP_INIT_OLD = '''        stop_reason: str | None = None
        batch_size = len(requested_actions)
'''
SOLVER_STEP_INIT_NEW = '''        stop_reason: str | None = None
        reset_refusal_detail: str | None = None
        batch_size = len(requested_actions)
'''

SOLVER_STEP_GUARD_OLD = '''            if action.id.value not in self.game.current_state.available_actions:
                message = f"{_format_action_display(action.id.name, dict(action.data))} is not valid right now."'''
SOLVER_STEP_GUARD_NEW = '''            if action.id == arcengine.GameAction.RESET:
                reset_refusal_detail = self.reset_refusal()
                if reset_refusal_detail is not None:
                    self.reset_refusals += 1
                    self.log_reset_guard("refused", reset_refusal_detail)
                    if executed_payloads:
                        stop_reason = "reset_rate_limited"
                        break
                    refused_payload = self._error_payload(reset_refusal_detail)
                    refused_payload["stop_reason"] = "reset_rate_limited"
                    return refused_payload
''' + SOLVER_STEP_GUARD_OLD

SOLVER_STEP_ACCEPT_OLD = '''            executed_payloads.append(payload)
            total_reward += float(payload.get("reward", 0.0) or 0.0)
'''
SOLVER_STEP_ACCEPT_NEW = '''            executed_payloads.append(payload)
            total_reward += float(payload.get("reward", 0.0) or 0.0)
            if action.id == arcengine.GameAction.RESET:
                self.model_reset_positions.append(self.action_count)
                self.log_reset_guard("accepted")
'''

SOLVER_STEP_DETAIL_OLD = '''        if stop_reason is not None:
            final_payload["stop_reason"] = stop_reason
        self.write_viewer_payload()'''
SOLVER_STEP_DETAIL_NEW = '''        if stop_reason is not None:
            final_payload["stop_reason"] = stop_reason
        if stop_reason == "reset_rate_limited" and reset_refusal_detail:
            final_payload["stop_detail"] = reset_refusal_detail
        self.write_viewer_payload()'''

SOLVER_SUMMARY_OLD = '''                run.solver_note = f"tokens={total_tokens}"
            self._finish_if_needed()
'''
SOLVER_SUMMARY_NEW = '''                run.solver_note = f"tokens={total_tokens}"
            self._finish_if_needed()
            print(
                f"RESET_GUARD_SUMMARY game={run.game_id} pass={self.pass_index} "
                f"model_resets={len(self.model_reset_positions)} "
                f"refused={self.reset_refusals} actions={self.action_count}",
                flush=True,
            )
'''

SOLVER_EDITS = (
    ("names", SOLVER_NAMES_OLD, SOLVER_NAMES_NEW, 1),
    ("fields", SOLVER_FIELDS_OLD, SOLVER_FIELDS_NEW, 1),
    ("methods", SOLVER_METHODS_OLD, SOLVER_METHODS_NEW, 1),
    ("analyzer call site", SOLVER_ANALYZER_OLD, SOLVER_ANALYZER_NEW, 1),
    ("payload call sites", SOLVER_PAYLOAD_OLD, SOLVER_PAYLOAD_NEW, 2),
    ("step_env init", SOLVER_STEP_INIT_OLD, SOLVER_STEP_INIT_NEW, 1),
    ("step_env guard", SOLVER_STEP_GUARD_OLD, SOLVER_STEP_GUARD_NEW, 1),
    ("step_env accept", SOLVER_STEP_ACCEPT_OLD, SOLVER_STEP_ACCEPT_NEW, 1),
    ("step_env detail", SOLVER_STEP_DETAIL_OLD, SOLVER_STEP_DETAIL_NEW, 1),
    ("summary", SOLVER_SUMMARY_OLD, SOLVER_SUMMARY_NEW, 1),
)

# The one prompt line. States only what is true on every game under the pinned harness:
# a level reset that keeps completed levels and costs an action. What it restores (lives,
# a step meter) differs by game, so that is left to the model to probe.
RESET_PROMPT_NEW = ACTION7_PROMPT_OLD + (
    '\n    "- `RESET` restarts the current level from its starting state; completed levels '
    'stay completed, and it counts as an action. It is rate-limited: never twice in a row, '
    'at most once per 20 actions, and it is absent from `valid_actions` while unavailable.\\n"'
)


def build(src: pathlib.Path, out: pathlib.Path, arm: str) -> None:
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src, out)
    ta_path = out / TOOL_AGENT
    ta_text = ta_path.read_text()
    for old, new in TOOL_AGENT_DELETIONS:
        if old not in ta_text:
            raise SystemExit(f"{arm}: tool_agent anchor missing: {old[:60]!r}")
        ta_text = ta_text.replace(old, new, 1)

    path = out / PROMPTS
    text = path.read_text()

    for old, new in DELETIONS:
        if old not in text:
            raise SystemExit(f"{arm}: deletion anchor missing: {old[:60]!r}")
        text = text.replace(old, new, 1)

    if arm in ("C", "D", "E", "F", "G") and ANCHOR not in text:
        raise SystemExit(f"{arm}: color-legend anchor missing")

    if arm == "C":
        text = text.replace(ANCHOR, ANCHOR + MECHANICS_BLOCK, 1)

    if arm == "F":
        text = text.replace(ANCHOR, ANCHOR + COMMIT_BLOCK, 1)

    if arm == "G":
        for old, new in IMAGE_FIRST:
            if old not in text:
                raise SystemExit(f"G: image-first anchor missing: {old[:70]!r}")
            text = text.replace(old, new, 1)

    if arm == "H":
        an_path = out / ACTION_NAMES
        an_text = an_path.read_text()
        if ACTION_NAMES_OLD not in an_text:
            raise SystemExit("H: action_names map anchor missing")
        an_path.write_text(an_text.replace(ACTION_NAMES_OLD, ACTION_NAMES_NEW, 1))
        if ACTION7_PROMPT_OLD not in text:
            raise SystemExit("H: action() contract anchor missing")
        text = text.replace(ACTION7_PROMPT_OLD, ACTION7_PROMPT_NEW, 1)

    if arm == "I":
        solver_path = out / SOLVER
        solver_text = solver_path.read_text()
        for label, old, new, count in SOLVER_EDITS:
            found = solver_text.count(old)
            if found != count:
                raise SystemExit(f"I: solver {label} anchor found {found}x, expected {count}")
            solver_text = solver_text.replace(old, new)
        solver_path.write_text(solver_text)
        if ACTION7_PROMPT_OLD not in text:
            raise SystemExit("I: action() contract anchor missing")
        text = text.replace(ACTION7_PROMPT_OLD, RESET_PROMPT_NEW, 1)

    if arm == "D":
        gu_path = out / GRID_UTILS
        gu_text = gu_path.read_text()
        if GRID_UTILS_OLD not in gu_text:
            raise SystemExit("D: grid_utils color-table anchor missing")
        gu_path.write_text(gu_text.replace(GRID_UTILS_OLD, GRID_UTILS_NEW, 1))

    if arm == "E":
        if WITHHOLD_OLD not in ta_text:
            raise SystemExit("E: _ascii_frame_view_payload anchor missing")
        ta_text = ta_text.replace(WITHHOLD_OLD, WITHHOLD_NEW, 1)
        if WITHHOLD_CALLSITE_OLD not in ta_text:
            raise SystemExit("E: current_frame payload call site missing")
        ta_text = ta_text.replace(WITHHOLD_CALLSITE_OLD, WITHHOLD_CALLSITE_NEW, 1)
        sb_path = out / SANDBOX
        sb_text = sb_path.read_text()
        if SANDBOX_OLD not in sb_text:
            raise SystemExit("E: sandbox segmentation anchor missing")
        sb_path.write_text(sb_text.replace(SANDBOX_OLD, SANDBOX_NEW, 1))
        text = text.replace(ANCHOR, ANCHOR + WITHHOLD_PROMPT_BLOCK, 1)

    ta_path.write_text(ta_text)
    path.write_text(text)

    # Assert the arm is what it claims before anything is uploaded.
    probes = ("DON'T DO THIS", "remaining-steps bar", "64 x 64", "puzzle")
    still = [p for p in probes if p in text]
    if still:
        raise SystemExit(f"{arm}: prompts.py still carries {still}")
    # tool_agent.py's module docstring says "ARC puzzle runs" and never reaches a prompt,
    # so probe the prompt-bearing line specifically rather than the whole file.
    if 'grid-based puzzle game' in ta_text:
        raise SystemExit(f"{arm}: tool_agent base prompt still says puzzle")

    exclusive = {
        "C": ("window onto a larger world", text),
        "F": ("Exploration is for building one hypothesis", text),
        "E": ("_WITHHOLD_TEXT_BOARD_UNTIL_STEP", ta_text),
        "D": ("ARC_COLOR_NAMES", (out / GRID_UTILS).read_text()),
        "G": ("measuring instruments, not the board", text),
        "H": ("valid, executable game action", text),
        "I": ("_RESET_MIN_ACTION_GAP", (out / SOLVER).read_text()),
        "I-prompt": ("restarts the current level from its starting state", text),
    }
    for probe_arm, (needle, haystack) in exclusive.items():
        present = needle in haystack
        if (arm == probe_arm.split("-")[0]) != present:
            raise SystemExit(f"{arm}: arm-{probe_arm} marker present={present}")

    if arm == "E":
        # The withhold is three coupled edits across two files; a partial apply would
        # leak the board or render it as empty rather than withheld.
        for needle, haystack, label in (
            ('"grid": None', ta_text, "withheld payload grid is None"),
            ("withhold=True", ta_text, "current_frame call site requests withholding"),
            ("if self._grid is None:", (out / SANDBOX).read_text(), "sandbox withhold guard"),
            ("withheld for the current frame", text, "prompt names the withholding"),
        ):
            if needle not in haystack:
                raise SystemExit(f"E: {label} missing ({needle!r})")
        if "_ascii_frame_view_payload(refreshed_frame)" in ta_text:
            raise SystemExit("E: an ungated current_frame payload call site remains")

    if arm == "D":
        # The whole arm is the symbol set, and the legend must be derived from it rather
        # than restated. Render a known grid through both text paths and prove it.
        import importlib.util

        spec = importlib.util.spec_from_file_location(f"gu_{arm}", out / GRID_UTILS)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rendered = module.format_grid_ascii([list(range(16))])
        if rendered != GLYPH_CHARS:
            raise SystemExit(f"D: ascii render {rendered!r} != {GLYPH_CHARS!r}")
        for name, char in GLYPH_COLORS:
            if f"{char}={name}" not in module.ARC_COLOR_LEGEND:
                raise SystemExit(f"D: legend missing {char}={name}")
        if len(set(GLYPH_CHARS)) != 16:
            raise SystemExit("D: glyph set is not 16 distinct characters")
        print(f"arm D: chars={GLYPH_CHARS} legend={module.ARC_COLOR_LEGEND}")

    if arm == "H":
        # The whole arm is that ACTION7 round-trips. Import the shipped module and prove
        # it, rather than trusting a string match on the table.
        import importlib.util

        spec = importlib.util.spec_from_file_location(f"an_{arm}", out / ACTION_NAMES)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if module.to_engine_action("ACTION7") != "ACTION7":
            raise SystemExit("H: to_engine_action('ACTION7') does not round-trip")
        if module.to_model_action("ACTION7") != "ACTION7":
            raise SystemExit("H: to_model_action('ACTION7') does not round-trip")
        for other in ("ACTION1", "ACTION6", "RESET"):
            if module.to_engine_action(module.to_model_action(other)) != other:
                raise SystemExit(f"H: {other} round-trip broken")
        if "undo" not in text.lower():
            raise SystemExit("H: prompt line lost the do-not-assume-undo clause")
        print("arm H: to_engine_action('ACTION7') -> ACTION7, other actions unchanged")

    if arm == "I":
        # The guard is code, so a string match proves little. The shipped solver must parse,
        # and no call site may still build the menu without asking the guard. The behaviour
        # itself is exercised against a real offline game by test_reset_guard.py.
        solver_text = (out / SOLVER).read_text()
        compile(solver_text, str(out / SOLVER), "exec")
        if "_engine_action_names(self.game)" in solver_text:
            raise SystemExit("I: an unguarded _engine_action_names call site remains")
        if solver_text.count("self.model_action_names()") != 3:
            raise SystemExit("I: expected 3 guarded menu call sites")
        print("arm I: solver compiles, 3 guarded menu call sites, guard in step_env")

    # Arms other than H must not carry the ACTION7 map entry.
    an_shipped = (out / ACTION_NAMES).read_text()
    if ('"ACTION7"' in an_shipped) != (arm == "H"):
        raise SystemExit(f"{arm}: ACTION7 map entry present={not (arm == 'H')}")

    print(f"arm {arm}: {out} prompts.py {len(text)} chars")


if __name__ == "__main__":
    control = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/armctl")
    # Optional arm list, so building a new arm does not rmtree the already-uploaded bundle
    # directories (and their dataset-metadata.json) of every earlier arm.
    for arm in (sys.argv[2:] or ("B",) + STACKED_ON_B):
        build(control, pathlib.Path(f"/tmp/bundle-{arm}"), arm)

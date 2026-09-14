"""
Author: Claude Opus 5 (Bubba)
Date: 13-September-2026
PURPOSE: Build the prompt-arm Kaggle dataset bundles from the duck control bundle, so
every arm is a recorded, re-runnable edit rather than a hand-patched upload. Arm B is
the control minus four assertions; arms C/D/E/F each stack exactly one further change on
top of B, because B is the measured reference arm (it beat control 10 -> 15 level clears).
C adds a mechanics-possibility block, D swaps the 16 board glyphs for distinct consonant
capitals, E withholds the text board until one action has been executed, F adds a
commit-to-hypothesis rule. Consumes the unpacked control bundle
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

STACKED_ON_B = ("C", "D", "E", "F")

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
# confusable part. Replacement is 16 distinct consonant capitals drawn from the Boss's
# allowed set QWRTYSDFGHKZXCVBM (Q dropped -- 17 letters, 16 slots). Initial-letter
# mnemonics are kept wherever the initial is free (W/G/D/C/B/M/R/S/Y); the remaining six
# colors take leftovers in color order.
GLYPH_COLORS = (
    ("white", "W"), ("light gray", "H"), ("gray", "G"), ("dark gray", "D"),
    ("charcoal", "C"), ("black", "B"), ("magenta", "M"), ("pink", "K"),
    ("red", "R"), ("blue", "T"), ("sky blue", "S"), ("yellow", "Y"),
    ("orange", "F"), ("dark red", "V"), ("light green", "Z"), ("purple", "X"),
)
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

ANCHOR = '    f"- Color legend: {ARC_COLOR_LEGEND}.\\n"\n'


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

    if arm in ("C", "D", "E", "F") and ANCHOR not in text:
        raise SystemExit(f"{arm}: color-legend anchor missing")

    if arm == "C":
        text = text.replace(ANCHOR, ANCHOR + MECHANICS_BLOCK, 1)

    if arm == "F":
        text = text.replace(ANCHOR, ANCHOR + COMMIT_BLOCK, 1)

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
    }
    for probe_arm, (needle, haystack) in exclusive.items():
        present = needle in haystack
        if (arm == probe_arm) != present:
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

    print(f"arm {arm}: {out} prompts.py {len(text)} chars")


if __name__ == "__main__":
    control = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/armctl")
    for arm in ("B", "C", "D", "E", "F"):
        build(control, pathlib.Path(f"/tmp/bundle-{arm}"), arm)

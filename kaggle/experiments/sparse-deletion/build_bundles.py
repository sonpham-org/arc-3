"""
Author: Claude Opus 5 (Bubba)
Date: 13-September-2026
PURPOSE: Build the prompt-arm Kaggle dataset bundles from the duck control bundle, so
every arm is a recorded, re-runnable edit rather than a hand-patched upload. Arm B is
the control minus four assertions; arm C is arm B plus a mechanics-possibility block.
Consumes the unpacked control bundle (keithtyser/duck-qwen38-nvfp4-mtp-vllm-smoke-v1).
Emits a bundle directory per arm, ready for `kaggle datasets create/version`.
SRP/DRY check: Pass - the arm edits lived only in a hand-edited upload until now; this
is the single definition of what each arm changes, and build_notebooks.py consumes the
resulting dataset slugs.
"""

import pathlib
import shutil
import sys

PROMPTS = "src/ARC3-Inference/inference/agent/prompts.py"
TOOL_AGENT = "src/ARC3-Inference/inference/agent/tool_agent.py"

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
    ta_path.write_text(ta_text)

    path = out / PROMPTS
    text = path.read_text()

    for old, new in DELETIONS:
        if old not in text:
            raise SystemExit(f"{arm}: deletion anchor missing: {old[:60]!r}")
        text = text.replace(old, new, 1)

    if arm == "C":
        if ANCHOR not in text:
            raise SystemExit("C: color-legend anchor missing")
        text = text.replace(ANCHOR, ANCHOR + MECHANICS_BLOCK, 1)

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
    has_block = "window onto a larger world" in text
    if (arm == "C") != has_block:
        raise SystemExit(f"{arm}: mechanics block present={has_block}")
    print(f"arm {arm}: {out} prompts.py {len(text)} chars mechanics_block={has_block}")


if __name__ == "__main__":
    control = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/armctl")
    build(control, pathlib.Path("/tmp/bundle-B"), "B")
    build(control, pathlib.Path("/tmp/bundle-C"), "C")

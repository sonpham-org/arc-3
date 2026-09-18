"""Oracle arm: hand the agent the game's own rulebook.

The oracle test (docs/plans/2026-09-18-oracle-test-plan.md) splits the failure on the games
we never clear into "cannot generate the idea" and "cannot execute the idea". Arm O is arm B
plus one thing: the rules of the game it is playing, injected as text. Nothing else moves.

Selected by `ARC3_ORACLE_RULES_DIR`, pointing at the directory
`tools/render_rulebooks.py` writes (one `<code>.txt` per public game). Unset -- the default --
is arm B, byte-identical to the untreated harness. A single checkout therefore runs either
arm, the same way ARC3_REASONING_STYLE does, with no separate patched tree.

Two deliberate hard failures, because the failure mode that ruins this experiment is arm O
quietly running without its treatment and being read as arm B's equal:

  - the directory is set but the game's rulebook is missing  -> raise
  - the directory is set but the game code cannot be resolved -> raise

Rulebooks contain the answer key to the public 25. Any run launched with this variable set
must be named `*-oracle-*` so `ARC3-Inference/distill/extract_sft.py` refuses it
(ARC3-Inference/distill/README.md).
"""
from __future__ import annotations

import os
from pathlib import Path

from inference.agent.runtime_state import RUNTIME_STATE_FILENAME

# The treatment marker. Per-turn guards count games whose prompt log contains this exact
# string (scripts/check_oracle_marker.sh), so it must not be reworded without updating them.
ORACLE_RULES_HEADING = "Rules of this game, from a verified source."

_RUNTIME_STATE_SUFFIX = f"_{Path(RUNTIME_STATE_FILENAME).stem}"


def oracle_rules_dir() -> Path | None:
    """The rulebook directory, or None when this is arm B."""
    raw = os.environ.get("ARC3_ORACLE_RULES_DIR", "").strip()
    return Path(raw).expanduser() if raw else None


def oracle_rules_enabled() -> bool:
    return oracle_rules_dir() is not None


def game_code_from_state_path(state_path: Path) -> str:
    """Bare game code from a runtime-state path, e.g. dc22.

    `solver._play_one` names it `<artifact_stem(game_id)>_p<N>_tool_runtime_state.json`, so
    the stem is `dc22-fdcac232_p0`. The code is everything before the content hash, matching
    `distill/extract_sft.py:game_code`. Returns "" when the harness wrote the single-game
    default name, which carries no game id at all.
    """
    stem = state_path.stem
    if stem.endswith(_RUNTIME_STATE_SUFFIX):
        stem = stem[: -len(_RUNTIME_STATE_SUFFIX)]
    elif stem == Path(RUNTIME_STATE_FILENAME).stem:
        return ""
    return stem.split("-", 1)[0].split("_", 1)[0].strip().lower()


def load_rulebook(state_path: Path) -> str:
    """The rendered rulebook for this game, or "" when the arm is off.

    Raises when the arm is on and the rulebook cannot be produced: an arm-O game that
    silently runs without its treatment is a wrong number, not a degraded one.
    """
    rules_dir = oracle_rules_dir()
    if rules_dir is None:
        return ""
    code = game_code_from_state_path(state_path)
    if not code:
        raise RuntimeError(
            f"ARC3_ORACLE_RULES_DIR is set but no game code could be read from {state_path}. "
            "The oracle arm needs per-game runtime-state files "
            f"(<game>_p<N>_{RUNTIME_STATE_FILENAME})."
        )
    path = rules_dir / f"{code}.txt"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(
            f"ARC3_ORACLE_RULES_DIR is set but {path} is unreadable ({exc}). Render the "
            "rulebooks with `python3.13 tools/render_rulebooks.py` first."
        ) from exc
    if not text:
        raise RuntimeError(f"{path} is empty; the oracle arm has no treatment for {code}.")
    return text


BLOCK_FOOTER = "End of the rules of this game."


def render_block(rulebook: str) -> str:
    """The injected block, exactly as it enters the user turn."""
    if not rulebook:
        return ""
    return f"{ORACLE_RULES_HEADING}\n{rulebook}\n{BLOCK_FOOTER}"


def strip_block(text: str, block: str) -> str:
    """`text` without a leading rulebook block.

    The block is re-sent in full on every turn, so it must NOT also sit in the retained
    history: the largest rulebook is ~5,800 characters, which `_estimate_tokens` charges at
    ~1,930 tokens, and thirty retained turns of it would exceed the whole 32,768-token
    window on its own. Arm O would then hold far less real history than arm B and the two
    arms would differ by two things instead of one.

    Stripping it as the turn is filed into history keeps exactly one copy in context -- the
    live one -- and leaves the older messages byte-stable from request to request, so the
    server's prefix cache still hits everything up to the previous turn.
    """
    if not block or not text.startswith(block):
        return text
    return text[len(block):].lstrip("\n")

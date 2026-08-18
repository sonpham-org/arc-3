"""Read the optional cross-game sidecar ledger for analyzer prompts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


_DEFAULT_MAX_CHARS = 1800


def _clean_statement(value: Any, *, max_chars: int = 320) -> str:
    text = " ".join(str(value or "").split())
    return text[:max_chars].rstrip()


def _supported_items(payload: dict[str, Any], key: str) -> list[str]:
    rendered: list[str] = []
    values = payload.get(key)
    if not isinstance(values, list):
        return rendered
    for value in values:
        if not isinstance(value, dict):
            continue
        statement = _clean_statement(value.get("statement"))
        support_games = value.get("support_games")
        if not statement or not isinstance(support_games, list):
            continue
        distinct_games = sorted({str(game).strip() for game in support_games if str(game).strip()})
        if len(distinct_games) < 2:
            continue
        confidence = _clean_statement(value.get("confidence", "hypothesis"), max_chars=24).lower()
        rendered.append(f"- [{confidence}; {len(distinct_games)} games] {statement}")
    return rendered


def render_common_themes_prompt(path: str | Path | None = None) -> str:
    """Return a bounded advisory prompt section, or an empty string when disabled.

    The sidecar is opt-in through ``ARC3_COMMON_THEMES_PATH``. Only statements
    supported by at least two distinct games are surfaced; malformed or partially
    written snapshots fail closed.
    """

    configured = str(path or os.environ.get("ARC3_COMMON_THEMES_PATH", "")).strip()
    if not configured:
        return ""
    try:
        payload = json.loads(Path(configured).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""

    themes = _supported_items(payload, "themes")
    predicates = _supported_items(payload, "predicates")
    cautions = _supported_items(payload, "cautions")
    if not (themes or predicates or cautions):
        return ""

    lines = [
        "Common themes and predicates learned from other games (advisory hypotheses only):",
        "Use these as priors, never as facts; current-game evidence always wins.",
    ]
    if themes:
        lines.extend(["Themes:", *themes])
    if predicates:
        lines.extend(["Predicates:", *predicates])
    if cautions:
        lines.extend(["Cautions:", *cautions])
    text = "\n".join(lines)
    try:
        max_chars = max(256, int(os.environ.get("ARC3_COMMON_THEMES_MAX_CHARS", _DEFAULT_MAX_CHARS)))
    except ValueError:
        max_chars = _DEFAULT_MAX_CHARS
    return text[:max_chars].rstrip()

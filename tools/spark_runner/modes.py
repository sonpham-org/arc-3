"""
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: Turn a Mode explorer mode into an edit of the harness's real per-turn prompt. The prompts in
  docs/static/data/modes.json are renderings: values that change every turn are written {like_this} and lines that
  appear only sometimes start with "[when ...]". Sending that text to the model would hand it literal braces, so the
  runner never does. Instead it diffs the mode's text against the Stock text of the same surface and variant (the
  same line-level longest-common-subsequence the page's diff view uses) and applies only that delta to the prompt
  the harness actually built this turn (ToolAgent._build_user_prompt):
    - removed Stock lines must be literal (no placeholder, no condition) and are removed where they occur;
    - added lines must be literal and are inserted after the nearest preceding unchanged line, found in the real
      prompt by turning the template line into a pattern ({x} matches anything; a missing [when] line is skipped).
  If no anchor is found (for example a Level start mode scheduled on an ordinary mid-level turn), the added lines go
  just before the "When ready, call `action(actions)`" line, or at the end. Every application returns a small report
  (lines removed, lines inserted, anchor or fallback) that is written into the sample's trajectory.
  Lean turn message (the Boss, #arc-3 6-Oct 16:39 ET: "Stuff like the Python tool calling belongs in the system
  prompt and shouldn't get duplicated in the user prompt"): a slot sent with lean = true has the harness's stock
  tool-call reminders (LEAN_LINES, the closing lines of ToolAgent._build_user_prompt, each also said in the system
  prompt) left out of its turn message by apply_lean, after the mode's delta is applied. Off by default, so every
  existing mode builds the same prompt as before; the page's "Stock (lean)" mode tests the difference against Stock.
  docs/static/data/modes.json meta.tool_reminders lists the same lines in their template form for the page.
SRP/DRY check: Pass - mode text comes only from modes.json or the page's custom mode; the harness builds the prompt;
  this module only computes and applies the difference.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

PLACEHOLDER = re.compile(r"\{[^{}\s]+\}")
CONDITION = re.compile(r"^\[when [^\]]*\]\s*")
FALLBACK_ANCHOR = "When ready, call `action(actions)`"
# The stock per-turn tool-call reminders exactly as the harness writes them (tool_agent.py _build_user_prompt and
# prompts.py TOOL_CALL_FORMAT_GUIDANCE); the system prompt already carries each of them.
LEAN_LINES = (
    "When ready, call `action(actions)` from inside the `python` tool with the best valid action or ordered batch "
    "selected by your code. If your code has found a reliable short sequence, prefer batching it in one call.",
    "You may call `action(actions)` more than once in one Python snippet if your search or control loop needs it.",
    "When calling `python`, emit exactly the tool-call format shown elsewhere in this prompt for this model. Use only "
    "that format; do not add markdown fences, prose wrappers, or alternate tool-call syntax. Do not quote or place "
    "tool-call markup inside explanatory text; when you decide to call the tool, emit the tool call itself.",
    "If you use MOUSE, include integer row and col arguments.",
)


class ModeError(ValueError):
    """A mode prompt that cannot be applied safely (would leak template markup into the model's prompt)."""


def diff_ops(a: list[str], b: list[str]) -> list[tuple[str, str | None, str | None]]:
    n, m = len(a), len(b)
    L = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            L[i][j] = L[i + 1][j + 1] + 1 if a[i] == b[j] else max(L[i + 1][j], L[i][j + 1])
    ops, i, j = [], 0, 0
    while i < n or j < m:
        if i < n and j < m and a[i] == b[j]:
            ops.append(("same", a[i], b[j])); i += 1; j += 1
        elif j < m and (i == n or L[i][j + 1] >= L[i + 1][j]):
            ops.append(("add", None, b[j])); j += 1
        else:
            ops.append(("del", a[i], None)); i += 1
    return ops


def is_literal(line: str) -> bool:
    return not PLACEHOLDER.search(line) and not CONDITION.match(line)


def line_pattern(template_line: str) -> re.Pattern:
    body = CONDITION.sub("", template_line)
    parts = PLACEHOLDER.split(body)
    return re.compile("^" + ".*?".join(re.escape(p) for p in parts) + "$", re.S)


@dataclass
class Hunk:
    anchor: str | None            # last unchanged template line before the change (None = top of prompt)
    removed: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)


@dataclass
class ModeDelta:
    mode: str
    hunks: list[Hunk]

    @property
    def empty(self) -> bool:
        return not any(h.removed or h.added for h in self.hunks)


def build_delta(mode: str, stock_template: str, mode_template: str) -> ModeDelta:
    ops = diff_ops(stock_template.split("\n"), mode_template.split("\n"))
    hunks: list[Hunk] = []
    anchor: str | None = None
    cur: Hunk | None = None
    for kind, left, right in ops:
        if kind == "same":
            anchor, cur = left, None
            continue
        if cur is None:
            cur = Hunk(anchor=anchor)
            hunks.append(cur)
        if kind == "del":
            if not is_literal(left):
                raise ModeError(f"mode {mode!r} removes a templated Stock line ({left[:60]!r}); "
                                "only literal lines can be removed")
            cur.removed.append(left)
        else:
            if not is_literal(right):
                raise ModeError(f"mode {mode!r} adds a line with a placeholder or [when] marker ({right[:60]!r}); "
                                "added lines must be plain text")
            cur.added.append(right)
    return ModeDelta(mode=mode, hunks=hunks)


def apply_delta(delta: ModeDelta, prompt: str) -> tuple[str, dict]:
    lines = prompt.split("\n")
    report = {"mode": delta.mode, "removed": 0, "inserted": 0, "anchors": [], "fallback": False}
    if delta.empty:
        return prompt, report
    for h in delta.hunks:
        pos = None
        if h.anchor is not None:
            pat = line_pattern(h.anchor)
            hits = [k for k, ln in enumerate(lines) if pat.match(ln)]
            if hits:
                pos = hits[0] + 1
        elif h.removed and h.removed[0] in lines:
            pos = lines.index(h.removed[0])
        for r in h.removed:
            if r in lines:
                k = lines.index(r)
                if pos is not None and k < pos:
                    pos -= 1
                if pos is None:
                    pos = k
                del lines[k]
                report["removed"] += 1
        if not h.added:
            continue
        if pos is None:
            fb = next((k for k, ln in enumerate(lines) if ln.startswith(FALLBACK_ANCHOR)), len(lines))
            pos = fb
            report["fallback"] = True
        else:
            report["anchors"].append((h.anchor or "")[:48])
        lines[pos:pos] = h.added
        report["inserted"] += len(h.added)
    return "\n".join(lines), report


def apply_lean(prompt: str) -> tuple[str, int]:
    """The turn message without the stock tool-call reminders (LEAN_LINES); returns the text and how many lines went."""
    lines = prompt.split("\n")
    kept = [ln for ln in lines if ln not in LEAN_LINES]
    return "\n".join(kept), len(lines) - len(kept)

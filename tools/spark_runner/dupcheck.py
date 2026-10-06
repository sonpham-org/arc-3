#!/usr/bin/env python3
"""
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: Duplicate check over a FULL rendered chat request (what the runner posts to the model: system prompt, tool
  schema, every message), for the prompt dedup work (Astra's notes, approved by the Boss 6-Oct 17:07 ET: "check the
  final rendered requests for duplication, not just stored templates").
  Units are sentences (split on sentence ends, newlines and bullets), normalised: lower case, backticks and quotes
  dropped, digits folded to '#', whitespace collapsed; units under five words are ignored. Sources: the tool schema
  descriptions, the system prompt, and every user and tool message (text parts). Assistant messages are the model's
  own words and are not checked; tool messages are checked only against the standing text (they carry the model's
  printed output, which may repeat itself legitimately).
  Four failure classes; a request passes when all four are empty:
    standing_internal   a standing unit (system prompt or tool schema) said twice there, exactly or nearly
    standing_repeated   a user or tool message unit that repeats a standing unit, exactly or nearly
                        (difflib ratio >= 0.8 for units of six words or more, or a standing unit of ten words or
                        more contained in it)
    within_message      a unit said twice inside one user message
    across_messages     a unit repeated across user messages that is not a per-turn fact, an event notice, or the
                        selected mode's instructions (each turn carries its own mode's block; a queue can run the
                        same mode on two turns)
    concepts            the same standing instruction said in DIFFERENT words: each entry of CONCEPTS is one
                        standing instruction with a pattern that matches any of its wordings (taken from every
                        wording in the original prompts). Fails when a concept is said in more than one unit of the
                        standing text, or in the standing text and in any user or tool message, or (absent from
                        the standing text) in more than one message. Tool messages are checked on the harness's own
                        fields only (the model's printed output is left out).
  Per-turn facts and event notices that recur across turns (each about its own turn: the state line, valid actions,
  executed actions, a game-over notice, a resume caption) are listed separately as "allowed_recurring", with counts.
  Usage: dupcheck.py <request.json[.gz]> ...   prints one JSON report per file; exit 1 if any fails.
SRP/DRY check: Pass - reads requests only; the renderer (render_requests.py) produces them through the real harness.
"""
from __future__ import annotations

import difflib
import gzip
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

MIN_WORDS = 5
NEAR_WORDS = 6
NEAR_RATIO = 0.8
CONTAIN_WORDS = 10

# Per-turn facts and event notices: allowed to recur ACROSS turns (each instance describes its own turn).
ALLOWED_RECURRING = [re.compile(p) for p in (
    r"^current state: step #+, level #+", r"^valid actions right now:", r"^executed actions",
    r"^the code executed #+ actions? in the previous sequence", r"^you are still on the same level",
    r"^current grid image", r"^no previous (action )?sequence", r"^your retained functions",
    r"^game over during the previous sequence", r"^this attempt failed and the level was automatically reset",
    r"^diagnose the cause before acting again", r"^the fatal action was", r"^you cleared the previous level",
    r"^current_frame now shows the starting board", r"^nothing has been executed since the turn opener",
    r"^you yielded control", r"^your tool results above are still valid", r"^continue from them",
    r"^your last python snippet executed no actions", r"^you have not acted yet", r"^call the python tool now",
    r"^instructions for this turn", r"^the last executed action", r"^that sequence (changed|produced)",
    r"^last_animation_frames shows them", r"^cells that changed since your previous", r"^diff image",
    r"^per-action trace", r"^note: a batched sequence was stopped", r"^note: the sequence was stopped",
    r"^that action is included in the executed list", r"^only the first #+ executed",
    r"^the remaining #+ action", r"^for reference, the most recent executed sequence",
    r"^reminder", r"^you have progressed to a new level", r"^you have completed the run",
    r"^no further actions were executed", r"^the board after the automatic reset",
)]


# One standing instruction each, matched in any of its wordings (normalised text). Written from the inventory in
# docs/plans/2026-10-06-prompt-dedup.md: every instruction the original prompts said more than once.
CONCEPTS = {
    "history[-1] is the current frame": r"history\[-#\]\.frame (is|=) (the )?(current|same latest)",
    "compare previous_frame to current_frame": r"compare previous_frame to current_frame",
    "segmentation is the primary view": r"segmentation[^.]{0,20}(as )?(the|your) primary view|is your primary view",
    "ascii only for a small region": r"ascii only (to read |for )?a small",
    "python is the only tool": r"only tool[^.]{0,6}python|exactly one tool|python is your only tool|the only tool is",
    "python variables reset between calls": r"python variables reset between",
    "tool-call format": r"tool-call format",
    "mouse takes integer row and col": r"mouse[^.]{0,40}integer row and col|integer row and col (arguments|fields)",
    "batch a reliable sequence": r"prefer batching|batch it in one call|useful to batch",
    "action() may be called several times": r"action\((actions|\.\.\.)\)[^.]{0,30}(more than once|several times|multiple times)",
    "stop acting on a terminal flag": r"(stop acting|stop immediately)[^.]{0,40}(game_over|result reports)|if a result reports game_over",
    "game over never means the run is won": r"(does not|never) means? the run",
    "budget-bar rule for deaths": r"(fully|almost fully) depleted",
    "deterministic: do not resubmit the fatal sequence": r"deterministic",
    "hud changes are not progress": r"hud[- ]only|hud/timer|hud, not",
    "raw numeric ids unavailable": r"raw numeric",
    "never print whole boards": r"never (print|echo)[^.]{0,30}(full|whole) board|never print full boards",
    "act only through action() in python": r"(call|execute)[^.]{0,30}action\([^)]*\)[^.]{0,20}inside (the )?python",
    "retained functions may be wrong": r"(presence does not mean|not proof)[^.]{0,30}correct",
    "carry mechanics to a new level": r"levels usually build on|start from the mechanics you established",
    "reassess the goal on a new level": r"reassess the goal",
    # the advice to search, not a function the model named bfs (retained-function lists and retention notes)
    "search algorithms (bfs)": r"\bbfs\b[^.]{0,40}(dfs|safest|flood)|(search|such as)[^.]{0,20}\bbfs\b",
    "re-locate rather than count actions": r"re-locate from current_frame",
    "an action can animate": r"(single|one) action can (result in|play|return) a short",
    "frame views expose only five fields": r"expose(s)? only[^.]{0,20}ascii",
    "inspect from python, not by eye": r"by eye",
    "tool output cap": r"capped (to|at) about",
    "how the diff image is drawn": r"unchanged cells (are )?dimmed",
    "how the animation image is drawn": r"last colou?r it held before reverting",
    "budget bar is hud, not a puzzle object": r"(timer|budget|remaining-steps) bar[^.]{0,60}(not|hud)",
    "code is ephemeral / not saved": r"(ephemeral|not saved across)",
}
CONCEPT_RE = {k: re.compile(v) for k, v in CONCEPTS.items()}
MODEL_FIELDS = ("stdout", "stderr", "result", "error", "traceback", "printed", "output")


def harness_text_of_tool(text: str) -> str:
    """A tool message's harness-written fields; the model's own printed output and values are dropped."""
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return text
    if not isinstance(payload, dict):
        return ""
    keep = []
    for k, v in payload.items():
        if k in MODEL_FIELDS:
            continue
        if isinstance(v, str):
            keep.append(v)
        elif isinstance(v, dict):
            keep += [x for kk, x in v.items() if isinstance(x, str) and kk not in MODEL_FIELDS]
    return "\n".join(keep)


MODE_HEADER = "Instructions for this turn ("


def norm(s: str) -> str:
    s = s.lower().replace("`", "").replace('"', "").replace("'", "")
    s = re.sub(r"\d+", "#", s)
    s = re.sub(r"\s+", " ", s).strip(" -*:;,.")
    return s


def units(text: str) -> list[str]:
    out = []
    for line in (text or "").split("\n"):
        line = re.sub(r"^\s*[-*]\s+", "", line)
        for part in re.split(r"(?<=[.!?])\s+(?=[A-Z`'\"(])", line):
            n = norm(part)
            if len(n.split()) >= MIN_WORDS:
                out.append(n)
    return out


def message_texts(m: dict) -> list[str]:
    c = m.get("content")
    if isinstance(c, str):
        return [c]
    if isinstance(c, list):
        return [p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"]
    return []


def tool_schema_texts(tools) -> list[str]:
    out = []
    for t in tools or []:
        f = (t or {}).get("function") or {}
        out.append(f.get("description") or "")
        for p in ((f.get("parameters") or {}).get("properties") or {}).values():
            out.append((p or {}).get("description") or "")
    return out


def near(a: str, b: str) -> bool:
    if len(a.split()) < NEAR_WORDS or len(b.split()) < NEAR_WORDS:
        return False
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return sm.real_quick_ratio() >= NEAR_RATIO and sm.quick_ratio() >= NEAR_RATIO and sm.ratio() >= NEAR_RATIO


def allowed(u: str) -> bool:
    return any(p.search(u) for p in ALLOWED_RECURRING)


def check(body: dict) -> dict:
    msgs = body.get("messages") or []
    standing: list[tuple[str, str]] = []      # (where, unit)
    for i, t in enumerate(tool_schema_texts(body.get("tools"))):
        standing += [(f"tools[{i}]", u) for u in units(t)]
    for i, m in enumerate(msgs):
        if m.get("role") == "system":
            for t in message_texts(m):
                standing += [(f"messages[{i}].system", u) for u in units(t)]
    report = {"standing_internal": [], "standing_repeated": [], "within_message": [], "across_messages": [],
              "allowed_recurring": {}, "units_checked": 0, "messages": len(msgs)}
    for a in range(len(standing)):
        for b in range(a + 1, len(standing)):
            ua, ub = standing[a][1], standing[b][1]
            if ua == ub or near(ua, ub):
                report["standing_internal"].append({"a": standing[a], "b": standing[b]})
    std_units = [u for _, u in standing]
    std_long = [u for u in std_units if len(u.split()) >= CONTAIN_WORDS]
    seen_across: dict[str, list[int]] = defaultdict(list)
    mode_units: set[str] = set()      # units inside a mode block ("Instructions for this turn (<mode> mode):")
    for i, m in enumerate(msgs):
        role = m.get("role")
        if role not in ("user", "tool"):
            continue
        mine: dict[str, int] = defaultdict(int)
        for t in message_texts(m):
            if role == "user" and MODE_HEADER in t:
                block = t[t.index(MODE_HEADER):].split("\n\n", 1)[0]
                mode_units.update(units(block))
            for u in units(t):
                report["units_checked"] += 1
                hit = next((s for s in std_units if u == s or near(u, s)), None) \
                    or next((s for s in std_long if s in u), None)
                if hit:
                    report["standing_repeated"].append({"message": i, "role": role, "unit": u, "standing": hit})
                if role != "user":
                    continue
                mine[u] += 1
                if mine[u] == 2:
                    report["within_message"].append({"message": i, "unit": u})
        for u in mine:
            seen_across[u].append(i)
    for u, where in seen_across.items():
        if len(where) < 2:
            continue
        if allowed(u) or u in mode_units:
            # a per-turn fact, or the selected mode's instructions on each turn that mode runs (a queue may run
            # the same mode twice); still checked against the standing text above
            report["allowed_recurring"][u[:90]] = len(where)
        else:
            report["across_messages"].append({"unit": u, "messages": where})
    # concepts: where each standing instruction is said, in any wording
    hits: dict[str, list[str]] = defaultdict(list)
    for where, u in standing:
        for name, rx in CONCEPT_RE.items():
            if rx.search(u):
                hits[name].append(where.split(".")[0] if where.startswith("tools") else "system")
    for i, m in enumerate(msgs):
        role = m.get("role")
        if role not in ("user", "tool"):
            continue
        texts = message_texts(m) if role == "user" else [harness_text_of_tool(t) for t in message_texts(m)]
        for t in texts:
            for u in units(t):
                for name, rx in CONCEPT_RE.items():
                    if rx.search(u):
                        hits[name].append(f"messages[{i}].{role}")
    report["concepts"] = []
    report["concept_map"] = {k: v for k, v in hits.items()}
    for name, where in hits.items():
        std = [w for w in where if not w.startswith("messages")]
        msg = sorted(set(w for w in where if w.startswith("messages")))
        if len(std) > 1 or (std and msg) or (not std and len(msg) > 1):
            report["concepts"].append({"concept": name, "standing": len(std), "messages": msg[:12],
                                       "message_count": len(msg)})
    report["fail_counts"] = {k: len(report[k]) for k in
                             ("standing_internal", "standing_repeated", "within_message", "across_messages",
                              "concepts")}
    report["ok"] = not any(report["fail_counts"].values())
    return report


def load(path: Path) -> dict:
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


if __name__ == "__main__":
    bad = 0
    for p in sys.argv[1:]:
        r = check(load(Path(p)))
        bad += not r["ok"]
        print(json.dumps({"file": p, **r}, indent=1))
    sys.exit(1 if bad else 0)

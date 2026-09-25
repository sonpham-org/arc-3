"""Parse a harness transcript (transcripts/<game>_p0.txt) back into the exact sequence of model
responses, so a fresh game can be replayed turn by turn without a model.

Grammar (tool_agent._append_transcript_section): every section is `[LABEL]\n<content.strip()>\n\n`.
Per solver turn:
  --- analysis_step=K | action=A | HH:MM:SS | tool-agent ---
  [SYSTEM PROMPT] [USER PROMPT]
  per request: [RUNTIME BUDGET] [MODEL RESPONSE META] [THINKING]? [ASSISTANT]?
               ([TOOL CALL: python] [TOOL RESULT: python])* [USER PROMPT]?(follow-up)
  [ANALYZER STATUS]  ->  "message: Step executed." | "message: Yielded control to solver: <why>."
                         | "request_error: ..." (the request after the last META failed)

Validation: reasoning_chars / content_chars in the META must equal the parsed THINKING / ASSISTANT
lengths, and the tool-call count must match. Tool-call arguments come from the META JSON when it is
complete (it is trimmed at 4000 chars) and otherwise from the TOOL CALL markup (code lines exact,
trailing newlines lost, which cannot change what the snippet does).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

LABELS = ("SYSTEM PROMPT", "USER PROMPT", "RUNTIME BUDGET", "MODEL RESPONSE META", "THINKING", "ASSISTANT",
          "TOOL CALL: python", "TOOL RESULT: python", "ANALYZER STATUS", "LEDGER COMPACTION")
_HEADER = re.compile(r"^--- analysis_step=(\d+) \| action=(\d+) \| (\d\d:\d\d:\d\d) \| tool-agent ---$", re.M)
_SECTION = re.compile(r"(?:^|\n\n)\[(" + "|".join(re.escape(x) for x in LABELS) + r")\]\n")


@dataclass
class Request:
    finish_reason: str
    reasoning: str
    content: str
    tool_calls: list[dict]          # OpenAI shape: {id, type, function:{name, arguments(json str)}}
    time_left_s: int | None = None  # from [RUNTIME BUDGET]
    args_source: str = "meta"       # meta | markup


@dataclass
class Turn:
    step: int
    action_at_start: int
    clock: str
    requests: list[Request] = field(default_factory=list)
    outcome: str = ""               # executed | yield:<why> | request_error | no_action | error
    status_detail: str = ""


def _sections(text: str) -> list[tuple[str, str]]:
    out = []
    marks = list(_SECTION.finditer(text))
    for i, m in enumerate(marks):
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((m.group(1), text[start:end].strip("\n")))
    return out


def _parse_meta(meta: str) -> tuple[str, int, int, int, list[dict] | None, list[str]]:
    fr = re.search(r"^finish_reason: (.*)$", meta, re.M).group(1).strip()
    tc = int(re.search(r"^tool_call_count: (\d+)$", meta, re.M).group(1))
    cc = int(re.search(r"^content_chars: (\d+)$", meta, re.M).group(1))
    rc = int(re.search(r"^reasoning_chars: (\d+)$", meta, re.M).group(1))
    calls = None
    ids = re.findall(r'"id": "([^"]+)"', meta)
    if "raw_tool_calls:" in meta:
        raw = meta.split("raw_tool_calls:", 1)[1].strip()
        try:
            calls = json.loads(raw)
            for c in calls:  # arguments must be a decodable JSON object string
                a = c["function"]["arguments"]
                if isinstance(a, str):
                    json.loads(a)
        except (json.JSONDecodeError, KeyError, TypeError):
            calls = None
    return fr, tc, cc, rc, calls, ids


def _parse_markup(markup: str) -> tuple[str, dict]:
    m = re.match(r"<tool_call>\n<function=(\w+)>\n(.*)</function>\n</tool_call>$", markup, re.S)
    if not m:
        raise ValueError("unparseable tool call markup: " + markup[:120])
    name, body = m.group(1), m.group(2)
    args = {}
    for pm in re.finditer(r"<parameter=(\w+)>\n(.*?)\n?</parameter>\n", body, re.S):
        args[pm.group(1)] = pm.group(2)
    return name, args


def parse_transcript(path: Path) -> list[Turn]:
    text = path.read_text(encoding="utf-8")
    heads = list(_HEADER.finditer(text))
    turns: list[Turn] = []
    for hi, h in enumerate(heads):
        body = text[h.end():heads[hi + 1].start() if hi + 1 < len(heads) else len(text)]
        turn = Turn(step=int(h.group(1)), action_at_start=int(h.group(2)), clock=h.group(3))
        secs = _sections(body)
        cur: Request | None = None
        pending_markups: list[tuple[str, dict]] = []
        time_left = None

        def close_request():
            nonlocal cur, pending_markups
            if cur is None:
                return
            if cur.tool_calls is None:  # META JSON was trimmed: rebuild from markup
                calls = []
                for k, (name, args) in enumerate(pending_markups):
                    calls.append({"id": cur_ids[k] if k < len(cur_ids) else f"replay-{turn.step}-{len(turn.requests)}-{k}",
                                  "type": "function", "function": {"name": name, "arguments": json.dumps(args)}})
                cur.tool_calls = calls
                cur.args_source = "markup"
            assert len(cur.tool_calls) == cur_tc, (path.name, turn.step, len(cur.tool_calls), cur_tc)
            assert len(cur.reasoning) == cur_rc, (path.name, turn.step, "reasoning", len(cur.reasoning), cur_rc)
            assert len(cur.content) == cur_cc, (path.name, turn.step, "content", len(cur.content), cur_cc)
            assert len(pending_markups) == cur_tc, (path.name, turn.step, "markups", len(pending_markups), cur_tc)
            turn.requests.append(cur)
            cur = None
            pending_markups = []

        cur_tc = cur_cc = cur_rc = 0
        cur_ids: list[str] = []
        for label, content in secs:
            if label == "RUNTIME BUDGET":
                m = re.search(r"time left (\d+)s", content)
                time_left = int(m.group(1)) if m else None
            elif label == "MODEL RESPONSE META":
                close_request()
                fr, cur_tc, cur_cc, cur_rc, calls, cur_ids = _parse_meta(content)
                cur = Request(finish_reason=fr, reasoning="", content="", tool_calls=calls, time_left_s=time_left)
            elif label == "THINKING":
                cur.reasoning = content
            elif label == "ASSISTANT":
                cur.content = content
            elif label == "TOOL CALL: python":
                pending_markups.append(_parse_markup(content))
            elif label == "ANALYZER STATUS":
                close_request()
                if content.startswith("request_error:"):
                    turn.outcome = "request_error"; turn.status_detail = content[:200]
                elif content.startswith("error:"):
                    turn.outcome = "error"; turn.status_detail = content[:200]
                else:
                    m = re.search(r"^message: (.*)$", content, re.M)
                    msg = m.group(1) if m else ""
                    if msg.startswith("Step executed"):
                        turn.outcome = "executed"
                    elif msg.startswith("Yielded control to solver: "):
                        turn.outcome = "yield:" + msg[len("Yielded control to solver: "):].rstrip(".")
                    elif msg.startswith("No action"):
                        turn.outcome = "no_action"
                    else:
                        turn.outcome = "unknown"; turn.status_detail = msg
        close_request()
        if not turn.outcome:
            turn.outcome = "truncated"  # transcript ended mid-turn (run killed)
        turns.append(turn)
    return turns


def turns_to_json(turns: list[Turn]) -> list[dict]:
    return [asdict(t) for t in turns]


if __name__ == "__main__":
    import sys
    from collections import Counter
    root = Path(sys.argv[1])
    for p in sorted(root.glob("*.txt")):
        turns = parse_transcript(p)
        nreq = sum(len(t.requests) for t in turns)
        src = Counter(r.args_source for t in turns for r in t.requests)
        print(f"{p.name[:4]} turns={len(turns)} requests={nreq} outcomes={dict(Counter(t.outcome for t in turns))} args={dict(src)}")

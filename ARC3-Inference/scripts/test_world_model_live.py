"""Does the live model actually emit the required `world_model` argument?

The unit tests only prove the harness *accepts* one. In the a424 run the model
never sent it, because it was optional. This asks the real server, with the real
tool schema, and checks what comes back.
"""

import json
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:1234/v1"
MODEL = "Qwen/Qwen3.6-27B-FP8"
key_path = Path(".cache/arc3_runtime/server-api-key")
key = key_path.read_text().strip().splitlines()[0] if key_path.is_file() else ""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "python",
            "description": "Run one ephemeral Python snippet against preloaded ASCII game state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to run."},
                    "world_model": {
                        "type": "object",
                        "description": "Your revised understanding of the game, carried to every later turn.",
                        "properties": {
                            "world_model": {"type": "string"},
                            "goal_model": {"type": "string"},
                            "action_model": {"type": "string"},
                            "recent_findings": {"type": "string"},
                            "open_questions": {"type": "string"},
                            "current_plan": {"type": "string"},
                            "cross_level_notes": {"type": "string"},
                        },
                    },
                },
                "required": ["code", "world_model"],
            },
        },
    }
]

messages = [
    {"role": "system", "content": "You are a coding agent solving a grid-based puzzle game. Your only tool is `python`."},
    {
        "role": "user",
        "content": (
            "The board shows a red 6x2 block at rows 2-7, cols 12-17, on a black background, "
            "with blue regions either side. Valid actions right now: MOUSE.\n"
            "Inspect the frame and take your best probe action.\n"
            "Pass your revised understanding as the `world_model` argument alongside `code`."
        ),
    },
]

payload = {
    "model": MODEL,
    "messages": messages,
    "tools": TOOLS,
    "tool_choice": "auto",
    "max_tokens": 700,
    "temperature": 0.6,
    "chat_template_kwargs": {"enable_thinking": False},
}
req = urllib.request.Request(
    f"{BASE}/chat/completions",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
)
with urllib.request.urlopen(req, timeout=600) as resp:
    data = json.loads(resp.read())

msg = data["choices"][0]["message"]
calls = msg.get("tool_calls") or []
print(f"tool_calls returned : {len(calls)}")
if not calls:
    print("NO TOOL CALL. content:", (msg.get("content") or "")[:400])
    raise SystemExit(1)

args_raw = calls[0]["function"]["arguments"]
print(f"arguments type      : {type(args_raw).__name__}")
try:
    args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
except json.JSONDecodeError as exc:
    print(f"ARGUMENTS DID NOT PARSE: {exc}")
    print(args_raw[:600])
    raise SystemExit(1)

print(f"keys                : {sorted(args)}")
has_code = bool(str(args.get("code", "")).strip())
wm = args.get("world_model")
print(f"has code            : {has_code}")
print(f"world_model type    : {type(wm).__name__}")
if isinstance(wm, str):
    try:
        wm = json.loads(wm)
        print("  (parsed from JSON string)")
    except json.JSONDecodeError:
        pass
if isinstance(wm, dict):
    for k, v in wm.items():
        if v:
            print(f"  {k}: {str(v)[:90]}")

ok = has_code and bool(wm)
print()
print("RESULT:", "PASS - model emits code AND a populated world_model" if ok else "FAIL")
raise SystemExit(0 if ok else 1)

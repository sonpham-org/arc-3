"""Find the constant gap between our rendered prompt and the server's logged prompt_tokens (G0 finding, 1-Oct:
every record rendered 11 tokens short). Renders the first requests of one request log under several
server-side normalizations and prints which one matches the logged count exactly.

Run on the G0 VM: python probe_template_gap.py --log /opt/rl/out/<run>/cache/<game>_p0_requests.jsonl --hf /opt/rl/hf
"""
import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_records as br  # noqa: E402
import render  # noqa: E402
import seed_moments as sm  # noqa: E402


def sglang_tools(tools):
    """Tools as SGLang's pydantic models dump them: Tool(type, function=Function(description, name, parameters,
    strict=False)), field order of the model, not of the request."""
    out = []
    for t in tools:
        f = t.get("function", {})
        out.append({"type": t.get("type", "function"),
                    "function": {"description": f.get("description"), "name": f.get("name"),
                                 "parameters": f.get("parameters"), "strict": False}})
    return out


def sglang_tools_full(tools):
    """Tool.model_dump() in SGLang 0.5.19 (pennyroyal): Function drops defer_loading when None (its own serializer)
    but keeps strict=False; Tool has no such serializer, so "defer_loading": null stays on the wrapper."""
    return [dict(t, defer_loading=None) for t in sglang_tools(tools)]


VARIANTS = {
    "sglang_tools_full": lambda r: dict(r, tools=sglang_tools_full(r["tools"])),
    "as_logged": lambda r: r,
    "sglang_tools": lambda r: dict(r, tools=sglang_tools(r["tools"])),
    "tools_fn_only": lambda r: dict(r, tools=[t.get("function", t) for t in r["tools"]]),
    "sglang_fn_only": lambda r: dict(r, tools=[t["function"] for t in sglang_tools(r["tools"])]),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--hf", required=True)
    ap.add_argument("--n", type=int, default=3)
    args = ap.parse_args()
    from transformers import AutoProcessor
    proc = AutoProcessor.from_pretrained(args.hf)
    rows = br.attach_usage(list(sm.iter_jsonl(args.log)))
    reqs = [r for r in rows if r.get("event") == "request" and r.get("_usage")][:args.n]
    for r in reqs:
        logged = r["_usage"].get("prompt_tokens")
        rec = {"messages": r["messages"], "tools": r.get("tools"), "train": [False] * len(r["messages"]),
               "chat_template_kwargs": r.get("chat_template_kwargs") or {}}
        line = {"step": r.get("analysis_step"), "logged": logged,
                "image_tokens": (r["_usage"].get("prompt_tokens_details") or {}).get("image_tokens")}
        for name, fn in VARIANTS.items():
            try:
                n = len(render.render(proc, fn(copy.deepcopy(rec)), add_generation_prompt=True)["input_ids"])
                line[name] = n - logged
            except Exception as e:  # noqa: BLE001
                line[name] = f"ERR {type(e).__name__}: {str(e)[:80]}"
        print(json.dumps(line), flush=True)
    r0 = reqs[0]
    text = proc.apply_chat_template(render.normalize_messages(r0["messages"]), tools=r0.get("tools"), tokenize=False,
                                    add_generation_prompt=True, **(r0.get("chat_template_kwargs") or {}))
    i = text.find("<tools>")
    print("TOOLS BLOCK AS RENDERED:", text[i:i + 700].replace("\n", "\\n"))


if __name__ == "__main__":
    main()

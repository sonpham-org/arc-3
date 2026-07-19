"""Export docs/data/tool-calls.json: per-run tool-call summary for the site.

The harness exposes ONE tool to the LLM (`python`); inside it the agent calls
sandbox helpers (`action`, `.segmentation`, `.ascii`, `show_animation_by_objects`,
`show_animation_by_bbox`, `predict`, ...). We count ACTUAL calls, i.e. only what
appears inside the agent's `<parameter=code>` blocks -- the system prompt (re-sent
every turn and mentioning these names) would otherwise dominate a naive grep.

Source: each run's logs/<run>/artifacts/*_events.jsonl `analysis` events carry the
per-step `transcript`. Writes {run_name: {counts}}. Run once when publishing runs.
"""
import glob
import json
import os
import re
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "data" / "tool-calls.json"
CODE_RE = re.compile(r"<parameter=code>(.*?)</parameter>", re.DOTALL)

# label -> substring counted inside agent code blocks
HELPERS = {
    "action": "action(",
    "segmentation": ".segmentation",
    "ascii": ".ascii",
    "objects": ".objects",
    "show_animation_by_objects": "show_animation_by_objects(",
    "show_animation_by_bbox": "show_animation_by_bbox(",
    "render_objects": "render_objects(",
    "render_bbox": "render_bbox(",
    "predict": "predict(",
    "frame_from_state": "frame_from_state(",
}


def summarize_run(run_dir: Path) -> dict:
    counts = {k: 0 for k in HELPERS}
    py_calls = 0            # LLM `python` tool calls
    llm_turns = 0          # analysis events
    for f in glob.glob(str(run_dir / "artifacts" / "*_events.jsonl")):
        for line in open(f, errors="replace"):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("type") != "analysis":
                continue
            t = d.get("transcript", "")
            if not t:
                continue
            llm_turns += 1
            py_calls += t.count("[TOOL CALL: python]")
            for m in CODE_RE.finditer(t):
                code = m.group(1)
                for label, needle in HELPERS.items():
                    if needle in code:
                        counts[label] += code.count(needle)
    return {"llm_turns": llm_turns, "python": py_calls,
            **{k: v for k, v in counts.items() if v}}


def main() -> None:
    out = {}
    for bench in sorted(glob.glob("logs/*/benchmark.json")):
        run_dir = Path(bench).parent
        if not glob.glob(str(run_dir / "artifacts" / "*_events.jsonl")):
            continue
        out[run_dir.name] = summarize_run(run_dir)
        print(f"  {run_dir.name}: {out[run_dir.name]}")
    OUT.write_text(json.dumps(out, indent=1))
    print(f"wrote {len(out)} runs -> {OUT}")


if __name__ == "__main__":
    main()

"""Tests for fork_replay.py on a logged play of Daniel's notebook (no harness, no GPU).

    python test_fork_replay.py <requests.jsonl of one play>

Checks: every answered call has a reply and the usage his trimmer and yield need; the comparator calls identical
messages exact, a clock reading change 'clock', and a changed board / tool output 'diverged' (mutation: a check
that passes both before and after a real change proves nothing).
"""
import copy
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fork_replay as fr  # noqa: E402


def main(path: str) -> int:
    t0 = time.time()
    seq = fr.load_sequence(path)
    answered = [r for r in seq if r["usage"] is not None]
    print(f"{len(seq)} calls, {len(answered)} answered, {sum(r['failed'] for r in seq)} failed, "
          f"{sum(r['reply'] is not None for r in seq)} with a reply, steps {seq[0]['step']}..{seq[-1]['step']} "
          f"({time.time() - t0:.1f}s)")
    missing = [(r["step"], r["idx"]) for r in answered[:-1] if r["reply"] is None]
    assert not missing, f"answered calls without a reply: {missing[:5]}"
    assert all("prompt_tokens" in r["usage"] and "completion_tokens" in r["usage"] for r in answered), "usage lacks counts"
    replies_ok = sum(1 for r in answered[:-1] if r["reply"].get("role") == "assistant"
                     and (r["reply"].get("tool_calls") or r["reply"].get("content") or r["reply"].get("reasoning_content")))
    print(f"replies with a body: {replies_ok}/{len(answered) - 1}")

    probe = next((r for r in seq if "elapsed_seconds" in json.dumps(r["messages"])), seq[len(seq) // 2])
    m = probe["messages"]
    t1 = time.time()
    assert fr.compare(copy.deepcopy(m), m)["verdict"] == "exact"
    text = json.dumps(m)
    edited = re.sub(r"(elapsed_seconds\W{0,4})\d+(\.\d+)?", r"\g<1>12.5", text, count=1)
    if edited != text:
        v = fr.compare(json.loads(edited), m)["verdict"]
        assert v == "clock", v
        print("clock reading changed -> clock")
    # mutation: change a board/tool output the model saw -> must not pass as exact or clock
    mut = copy.deepcopy(m)
    k = max(i for i, x in enumerate(mut) if isinstance(x.get("content"), str) and len(x["content"]) > 200)
    mut[k]["content"] = mut[k]["content"][:100] + "ZZZZ" + mut[k]["content"][104:]
    v = fr.compare(mut, m)
    assert v["verdict"] in ("near", "diverged"), v
    mut2 = copy.deepcopy(m)
    mut2[k]["content"] = "a different board entirely " * 40
    v2 = fr.compare(mut2, m)
    assert v2["verdict"] == "diverged", v2
    dropped = fr.compare(m[:-1], m)
    assert dropped["verdict"] == "diverged", dropped
    print(f"comparator: 4-char edit -> {v['verdict']}, rewritten message -> diverged, missing message -> diverged "
          f"({time.time() - t1:.1f}s)")
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

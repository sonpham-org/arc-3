"""Exercise the Tier-A harness fixes against real payloads.

1. Image parts must be costed as vision tokens, not as the length of their base64.
2. A world model sent as a `python` tool argument must survive into later turns
   (the followup prompts forbid assistant text, which is the only other path).
"""

import json
import os
import sys

os.environ.setdefault("MULTIMODAL_CONTEXT", "current_grid")
os.environ.setdefault("MULTIMODAL_UPSCALE", "4")

from inference.agent import tool_agent as ta
from inference.agent.runtime_state import Frame
from inference.agent.vision_context import frame_to_png_data_url

FAIL = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}{(' - ' + detail) if detail else ''}")
    if not cond:
        FAIL.append(name)


print("=" * 72)
print("1. Image token accounting")
print("=" * 72)

grid = tuple(tuple((r * 7 + c * 3) % 16 for c in range(64)) for r in range(64))
frame = Frame(grid=grid, step=1, level=0)
data_url = frame_to_png_data_url(frame, upscale=4)

message = {
    "role": "user",
    "content": [
        {"type": "text", "text": "Current grid image:"},
        {"type": "image_url", "image_url": {"url": data_url}},
    ],
}

naive = max(1, (len(json.dumps(message, ensure_ascii=True, sort_keys=True, default=str)) + 2) // 3)
fixed = ta._estimate_tokens(message)

print(f"  base64 data URL     : {len(data_url):,} chars")
print(f"  OLD estimate (len/3): {naive:,} tokens")
print(f"  NEW estimate        : {fixed:,} tokens")
print(f"  overcharge removed  : {naive - fixed:,} tokens ({naive / max(fixed, 1):.1f}x)")

check("image no longer costed by base64 length", fixed < naive / 4, f"{fixed} vs {naive}")
check("image still costs something", fixed >= ta._IMAGE_TOKEN_ESTIMATE)

# 30 turns of history, the persistent-history window the agent actually carries.
history = [message] * 30
naive_h = max(1, (len(json.dumps(history, ensure_ascii=True, sort_keys=True, default=str)) + 2) // 3)
fixed_h = ta._estimate_tokens(history)
budget = 32768 - 512 - 512
print(f"\n  30-turn history, OLD: {naive_h:,} tokens ({100 * naive_h / budget:.0f}% of the {budget:,} budget)")
print(f"  30-turn history, NEW: {fixed_h:,} tokens ({100 * fixed_h / budget:.0f}% of the {budget:,} budget)")
check("images used to eat most of the budget", naive_h > budget / 2, f"{naive_h:,} > {budget // 2:,} (half of budget)")
check("images now cost a small fraction of it", fixed_h < budget / 4, f"{fixed_h:,} < {budget // 4:,} (quarter of budget)")

print()
print("=" * 72)
print("2. World model via tool argument")
print("=" * 72)

agent = ta.ToolAgent.__new__(ta.ToolAgent)
agent._summarized_knowledge = ta._empty_world_model()

# The tool schema must actually advertise the parameter, or the model can't send it.
tools_src = json.dumps(ta.ToolAgent._tools.__code__.co_consts, default=str)
check("tool schema advertises `world_model`", "world_model" in tools_src)

updated = agent._update_summarized_knowledge_from_tool_arguments(
    {
        "code": "print(current_frame.step)",
        "world_model": {
            "world_model": "Board has a 3x3 movable block and a fixed goal tile.",
            "action_model": "UP/DOWN/LEFT/RIGHT translate the block by one cell.",
            "current_plan": "Push the block onto the goal tile.",
        },
    }
)
check("structured world model accepted", updated)

lines = agent._summarized_knowledge_lines()
blob = "\n".join(lines)
check("world model carried into the next prompt", "3x3 movable block" in blob)
check("action model carried", "translate the block" in blob)
check("plan carried", "Push the block" in blob)

# The exact scenario that froze it: tool call, no assistant text.
agent2 = ta.ToolAgent.__new__(ta.ToolAgent)
agent2._summarized_knowledge = ta._empty_world_model()
agent2._update_summarized_knowledge_from_assistant("")  # obeying "no assistant text"
check("text path alone leaves it EMPTY (the old bug)", not agent2._summarized_knowledge_lines())
agent2._update_summarized_knowledge_from_tool_arguments({"world_model": {"world_model": "Learned something."}})
check("tool-arg path updates it anyway (the fix)", bool(agent2._summarized_knowledge_lines()))

# Omitted fields must not wipe existing knowledge.
agent._update_summarized_knowledge_from_tool_arguments({"world_model": {"recent_findings": "SPACE does nothing."}})
blob2 = "\n".join(agent._summarized_knowledge_lines())
check("partial update preserves untouched fields", "3x3 movable block" in blob2 and "SPACE does nothing" in blob2)

# Junk must not crash the turn.
check("non-dict world_model ignored safely", agent._update_summarized_knowledge_from_tool_arguments({"world_model": "junk"}) is False)
check("absent world_model ignored safely", agent._update_summarized_knowledge_from_tool_arguments({"code": "x=1"}) is False)

print()
print("=" * 72)
print(f"RESULT: {'ALL PASSED' if not FAIL else 'FAILED: ' + ', '.join(FAIL)}")
print("=" * 72)
sys.exit(1 if FAIL else 0)

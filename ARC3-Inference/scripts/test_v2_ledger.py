"""V2 knowledge ledger + trim-time compaction: unit checks.

Covers the two-tier schema, level-transition wipe semantics, the prose scraper's
legacy aliases, prompt/schema self-consistency, and the compaction request path
(mocked model, both success and failure).
"""

import json
import os
import sys

os.environ.setdefault("MULTIMODAL_CONTEXT", "current_grid")
os.environ.setdefault("MULTIMODAL_UPSCALE", "8")

from inference.agent import tool_agent as ta

FAIL = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}{(' - ' + detail) if detail else ''}")
    if not cond:
        FAIL.append(name)


def fresh_agent():
    agent = ta.ToolAgent.__new__(ta.ToolAgent)
    agent._summarized_knowledge = ta._empty_world_model()
    return agent


print("=" * 72)
print("1. Two-tier schema")
print("=" * 72)
keys = set(ta._empty_world_model())
game, level = set(ta._LEDGER_GAME_KEYS), set(ta._LEDGER_LEVEL_KEYS)
check("12 fields total", len(keys) == 12, str(sorted(keys)))
check("tiers are disjoint and cover all fields", game | level == keys and not (game & level))
check("failed_probes is level-tier", "failed_probes" in level)
check("action_semantics is game-tier", "action_semantics" in game)

print()
print("=" * 72)
print("2. Level transition wipes level tier, keeps game tier")
print("=" * 72)
agent = fresh_agent()
agent._summarized_knowledge.update(
    {
        "action_semantics": "UP moves avatar 1 cell (VERIFIED step 7)",
        "level_log": "L1: 12 actions, pushed block onto tile",
        "failed_probes": "MOUSE(44,48): no change (step 31)",
        "current_plan": "reach the door",
    }
)
agent._last_step_summary = {"level_transition": True}
agent._update_summarized_knowledge_from_step_summary()
kn = agent._summarized_knowledge
check("game tier survives", kn["action_semantics"].startswith("UP moves") and kn["level_log"].startswith("L1"))
check("level tier wiped", not kn["failed_probes"] and not kn["current_plan"])

print()
print("=" * 72)
print("3. Scraper: new labels + legacy aliases")
print("=" * 72)
note = ta._extract_scientist_note(
    "Action model: SPACE toggles doors.\nFailed probes: clicked corners, nothing.\nHUD map: bottom strip is a timer."
)
check("legacy 'Action model:' folds into action_semantics", "SPACE toggles" in note.get("action_semantics", ""))
check("Failed probes scraped", "corners" in note.get("failed_probes", ""))
check("HUD map scraped", "timer" in note.get("hud_map", ""))

print()
print("=" * 72)
print("4. Injection renders two sections")
print("=" * 72)
blob = "\n".join(agent._summarized_knowledge_lines())
check("game section header", "Game knowledge (persists across levels):" in blob)
check("VERIFIED/HYPOTHESIS guidance", "VERIFIED(step N)" in blob)
agent._summarized_knowledge["failed_probes"] = "MOUSE(1,1): no change (step 4)"
blob = "\n".join(agent._summarized_knowledge_lines())
check("level section appears when populated", "Current level:" in blob and "MOUSE(1,1)" in blob)

print()
print("=" * 72)
print("5. Prompt/schema self-consistency (every field named everywhere)")
print("=" * 72)
tools_desc = json.dumps(ta.ToolAgent._tools.__code__.co_consts, default=str)
for key in sorted(ta._empty_world_model()):
    check(f"{key} in compaction prompt", key in ta._COMPACTION_PROMPT)
    check(f"{key} in tool schema description", key in tools_desc)

print()
print("=" * 72)
print("6. Compaction request path (mocked model)")
print("=" * 72)
agent = fresh_agent()
agent._system_prompt = "system"
canned = json.dumps(
    {
        "action_semantics": "LEFT slides row left (VERIFIED step 9)",
        "failed_probes": "MOUSE(0,0): no change (step 2)",
    }
)
agent._chat_completion = lambda messages, **kw: ta._ChatCompletionResult(message={"content": canned})
ok = agent._compact_history_into_ledger([{"role": "user", "content": "old turn"}], request_timeout_seconds=5)
check("compaction folds JSON into ledger", ok and "slides row left" in agent._summarized_knowledge["action_semantics"])
check("failed probes captured", "MOUSE(0,0)" in agent._summarized_knowledge["failed_probes"])

agent2 = fresh_agent()
agent2._system_prompt = "system"


def boom(messages, **kw):
    raise RuntimeError("server down")


agent2._chat_completion = boom
ok2 = agent2._compact_history_into_ledger([{"role": "user", "content": "x"}], request_timeout_seconds=5)
check("compaction failure is non-fatal and returns False", ok2 is False)
check("empty history is a no-op", fresh_agent()._compact_history_into_ledger([], request_timeout_seconds=5) is False)

print()
print("=" * 72)
print("RESULT:", "ALL PASSED" if not FAIL else f"FAILED: {FAIL}")
print("=" * 72)
sys.exit(1 if FAIL else 0)

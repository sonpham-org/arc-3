"""How often does the trimmer invalidate the server's prefix cache?

vLLM reuses KV only for the longest COMMON PREFIX of consecutive requests. Every
time the trimmer drops a message from the front, every later token shifts and the
whole request misses. This simulates a game's worth of turns and counts, for each
policy, how many requests could actually reuse the previous request's prefix.
"""

import os
import sys

os.environ.setdefault("MULTIMODAL_CONTEXT", "current_grid")
os.environ.setdefault("MULTIMODAL_UPSCALE", "4")

from inference.agent import tool_agent as ta

TURNS = 60


def make_agent(low_water):
    agent = ta.ToolAgent.__new__(ta.ToolAgent)
    agent._context_budget_tokens = 31744
    agent._reply_reserve_tokens = 512
    agent._low_water = low_water
    return agent


def common_prefix_len(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def simulate(low_water):
    """Replay TURNS turns, trimming with the given low-water mark, and count cache hits."""
    original = ta._CONTEXT_TRIM_LOW_WATER
    ta._CONTEXT_TRIM_LOW_WATER = low_water
    try:
        agent = make_agent(low_water)
        system = {"role": "system", "content": "You are a coding agent. " * 200}
        history = []
        prev_sent = None
        hits = 0
        trims = 0
        sent_sizes = []
        for turn in range(TURNS):
            history.append({"role": "user", "content": f"Turn {turn}: board state. " * 60})
            history.append({"role": "assistant", "content": f"Analysis for turn {turn}. " * 40})
            history.append({"role": "tool", "tool_call_id": f"c{turn}", "content": f"Result {turn}. " * 40})

            sent = agent._trim_messages_for_context([system, *history], tools=None)
            sent_sizes.append(agent._estimate_request_input_tokens(sent, tools=None))

            if prev_sent is not None:
                shared = common_prefix_len(prev_sent, sent)
                # A cache hit means the previous request's messages are still an intact
                # prefix of this one: nothing was dropped from the front.
                if shared >= len(prev_sent):
                    hits += 1
                else:
                    trims += 1
            history = [m for m in sent[1:]]
            prev_sent = sent
        return hits, trims, sent_sizes
    finally:
        ta._CONTEXT_TRIM_LOW_WATER = original


print("=" * 74)
print(f"Simulating {TURNS} turns of a game; counting prefix-cache reuse")
print("=" * 74)

# 1.0 == the old behaviour: trim to exactly the budget.
old_hits, old_trims, old_sizes = simulate(1.0)
new_hits, new_trims, new_sizes = simulate(0.6)

total = TURNS - 1
print(f"\nOLD (trim to 100% of budget — the shipped behaviour):")
print(f"  prefix reused : {old_hits}/{total} turns ({100 * old_hits / total:.0f}%)")
print(f"  cache-busting trims: {old_trims}")
print(f"  peak request size  : {max(old_sizes):,} tokens")

print(f"\nNEW (trim to {int(100 * ta._CONTEXT_TRIM_LOW_WATER)}% low-water mark):")
print(f"  prefix reused : {new_hits}/{total} turns ({100 * new_hits / total:.0f}%)")
print(f"  cache-busting trims: {new_trims}")
print(f"  peak request size  : {max(new_sizes):,} tokens")

budget = 31744
ok = True


def check(name, cond, detail=""):
    global ok
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}{(' - ' + detail) if detail else ''}")
    if not cond:
        ok = False


print()
check("cache-busting trims cut by >5x", old_trims >= new_trims * 5, f"{old_trims} -> {new_trims}")
check("new policy reuses the prefix on >=90% of turns", new_hits >= total * 0.9, f"{100 * new_hits / total:.0f}%")
check("new policy still never exceeds the budget", max(new_sizes) <= budget, f"{max(new_sizes):,} <= {budget:,}")

print()
print("=" * 74)
print("RESULT:", "ALL PASSED" if ok else "FAILED")
print("=" * 74)
sys.exit(0 if ok else 1)

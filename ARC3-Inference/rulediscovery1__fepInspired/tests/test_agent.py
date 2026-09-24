# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Tests (written, NOT run) for rulediscovery1__fepInspired/agent.py: the full act -> env -> observe loop on
#   a synthetic mover keeps the perceived board equal to the latest frame and each transition's pre
#   board equal to the previous frame (pre = post advance through the agent, not only the Perceiver);
#   the text summary for the harness model mentions hypotheses; the harness adapter emits the payload
#   the sandbox's action() accepts (model names, MOUSE with row/col).
# SRP/DRY check: Pass -- fixtures from synth.py; action names from the harness map.
from __future__ import annotations

from rulediscovery1__fepInspired.agent import AgentConfig, HarnessAdapter, RuleDiscoveryAgent, TextSummaryAdvisor
from rulediscovery1__fepInspired.perception import Action
from rulediscovery1__fepInspired.tests.synth import MoverEnv

VALID = ["ACTION1", "ACTION2", "ACTION3", "ACTION4"]


def test_agent_loop_keeps_the_board_current():
    env = MoverEnv(x=18, wall_x=26, timer_every=2)
    agent = RuleDiscoveryAgent(AgentConfig(propose_every=4, seed=1))
    prev = env.board()
    agent.start_play(prev, VALID)
    for _ in range(12):
        a = agent.act()
        assert a.name in VALID
        grid, lc, go = env.step(a)
        rep = agent.observe(a, grid, lc, go)
        assert rep.transition.pre.raw == prev
        assert agent.perceiver.current.raw == grid
        prev = grid
    text = TextSummaryAdvisor().summarize(agent)
    assert "hypothesis 1" in text and "posterior entropy" in text


def test_harness_payloads():
    assert HarnessAdapter.to_harness(Action("ACTION1")) == {"action": "UP"}
    assert HarnessAdapter.to_harness(Action("ACTION6", 3, 4)) == {"action": "MOUSE", "row": 3, "col": 4}
    assert HarnessAdapter.to_harness(Action("ACTION7")) == {"action": "ACTION7"}

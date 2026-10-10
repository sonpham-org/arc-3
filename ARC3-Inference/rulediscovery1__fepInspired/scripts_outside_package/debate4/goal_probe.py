# Author: Claude Opus 5.5 (Bubba)
# Date: 25-September-2026
# PURPOSE: Scratch probe (debate four, pick 2 design): play d3_hb on one game/seed and print the goal posterior's top
#   group every N steps, plus how many goals are tied, to see what goal babbling will sample from. Scoring only.
# SRP/DRY check: Pass -- uses game_sweep's arm table, env and agent as they are.
import sys, collections
from rulediscovery1__fepInspired.agent import AgentConfig, RuleDiscoveryAgent
from rulediscovery1__fepInspired.env import GameEnv
from rulediscovery1__fepInspired.game_sweep import TL_ARMS
from rulediscovery1__fepInspired.curiosity import CuriosityConfig, CuriosityDrive, load_encoder
from rulediscovery1__fepInspired.explore import ObjectContactExplorer

game, build, seed, n = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
env = GameEnv(game, build); obs = env.reset()
valid = lambda o: o.valid_actions + ["RESET"]
agent = RuleDiscoveryAgent(AgentConfig(seed=seed, dl_weight=0.25, **TL_ARMS["d3_hb"]),
                           curiosity=CuriosityDrive(load_encoder(), CuriosityConfig(temperature=1.0), seed=seed),
                           explorer=ObjectContactExplorer())
agent.start_play(obs.grid, valid(obs), level=0)
g = agent.slow.goals
print("n goals", len(g.goals), "colours", agent.perceiver.current.colours())
for t in range(1, n + 1):
    a = agent.act(); obs = env.step(a)
    agent.observe(a, obs.grid, level_completed=obs.level_completed, game_over=obs.state == "GAME_OVER",
                  level=obs.levels_completed, valid_actions=valid(obs))
    if t % 100 == 0 or obs.level_completed:
        post = g.posterior(); top = sorted(post.items(), key=lambda kv: -kv[1])
        pmax = top[0][1]
        tied = [k for k, p in top if p >= 0.5 * pmax]
        print(t, "levels", obs.levels_completed, "tied", len(tied), "pmax", round(pmax, 3))
        for k, p in top[:12]:
            gg = g.goals[k]
            print("   ", round(p, 3), gg.describe(), "prog", round(gg.progress(agent.perceiver.current, g.base), 3), "dl", round(gg.description_length(), 2))
    if obs.done: break

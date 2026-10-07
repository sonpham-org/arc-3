# Author: Claude Opus 5.5 (Bubba)
# Date: 25-September-2026
# PURPOSE: Probe (outside the package) of what OpenMind's agent keeps across a RESET, a lost life and a level clear in
#   the kept configuration d4_opt: at each such event log the MAP rule set, the self's learned moves, top goals, and 10
#   steps later whether the pre-event MAP rule set is still among the hypotheses. Scoring only, agent untouched.
# SRP/DRY check: Pass -- reuses game_sweep's arm table and loop pieces.
import sys, json
sys.path.insert(0, "/Users/macmini/GitHub/arc-3/ARC3-Inference")
from rulediscovery1__fepInspired import game_sweep as gs
from rulediscovery1__fepInspired.agent import AgentConfig, RuleDiscoveryAgent
from rulediscovery1__fepInspired.env import GameEnv
from rulediscovery1__fepInspired.curiosity import CuriosityConfig, CuriosityDrive, load_encoder
from rulediscovery1__fepInspired.explore import ObjectContactExplorer

game, build, seed, arm, budget = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], int(sys.argv[5])
env = GameEnv(game, build); obs = env.reset()
valid = lambda o: o.valid_actions + ["RESET"]
drive = CuriosityDrive(load_encoder(), CuriosityConfig(temperature=1.0), seed=seed)
cfg = AgentConfig(seed=seed, dl_weight=0.25, **gs.TL_ARMS[arm])
ag = RuleDiscoveryAgent(cfg, curiosity=drive, explorer=ObjectContactExplorer())
ag.start_play(obs.grid, valid(obs), level=0)
pending, surv = [], 0
for n in range(1, budget + 1):
    a = ag.act(); obs = env.step(a)
    rep = ag.observe(a, obs.grid, level_completed=obs.level_completed, game_over=obs.state == "GAME_OVER",
                     level=obs.levels_completed, valid_actions=valid(obs))
    b = ag.budget; life = b is not None and b.survived_ends > surv
    if b is not None: surv = b.survived_ends
    ev = "clear" if obs.level_completed else "reset" if a.name == "RESET" else "life" if life else None
    s = ag.slow
    for p in list(pending):
        if n - p["n"] == 10:
            keys = {h.ruleset.key() for h in s.beliefs.hyps}
            p["map_kept_10"] = p["key"] in keys; p["map_is_map_10"] = s.beliefs.map_hypothesis().ruleset.key() == p["key"]
            p["dirs_10"] = {k: list(v) for k, v in (s.ctx.selfm.dirs().items() if s.ctx.selfm else [])}
            del p["key"]; print(json.dumps(p)); pending.remove(p)
    if ev:
        m = s.beliefs.map_hypothesis()
        pending.append({"n": n, "ev": ev, "mode": ag.last_decision.mode if ag.last_decision else None,
                        "level": obs.levels_completed, "n_hyps": len(s.beliefs.hyps), "map_rules": len(m.ruleset),
                        "map": [d[:70] for d in m.ruleset.describe()[:4]], "key": m.ruleset.key(),
                        "dirs": {k: list(v) for k, v in (s.ctx.selfm.dirs().items() if s.ctx.selfm else [])},
                        "tries": dict(ag.explorer.tries), "goals": [g.describe() for g, _ in s.goals.top(2)]})
    if obs.done: break
print("END", n, obs.levels_completed, obs.state)

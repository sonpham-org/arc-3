"""Full native world-model loop:

  probe -> synthesize + exact-replay-verify (CEGIS) -> hypothesize goal ->
  plan-by-simulation over the verified model -> execute the plan on the real game.

This is OPINE's act/synthesize/verify/plan loop reproduced in our own code, driven
by any /v1/chat/completions model (Ollama for dev, Qwen3.6 vLLM for prod).
"""
from __future__ import annotations

import env as envmod
import planner
import wm


def solve_level(game_name, env_root, n_transitions=16, max_depth=25, log=print):
    E = envmod.ArcEnv(game_name, env_root=env_root)
    E.reset()
    actions = [a for a in E.available_actions() if a not in (0, 7)]

    # 1. CEGIS: admit an exactly-replaying transition function.
    res = wm.cegis(E, n_transitions=n_transitions, log=log)
    status = "admitted" if res["admitted"] else f"best {res['passed']}/{res['total']}"
    log(f"[loop] transition model: {status}")
    try:
        tfn = wm._sandbox_exec(res["code"])
    except Exception as e:
        log(f"[loop] transition model won't load: {e}")
        return {"solved": False, "stage": "synthesis"}

    # 2. Hypothesize the goal (win condition).
    try:
        goal_code = planner.synthesize_goal(res["buffer"], actions, res["code"])
        is_goal = planner.load_is_goal(goal_code)
    except Exception as e:
        log(f"[loop] goal synthesis failed: {e}")
        return {"solved": False, "stage": "goal", "model_admitted": res["admitted"]}
    log("[loop] goal hypothesized (is_goal synthesized)")

    # 3. Plan by simulating in the verified model from the CURRENT real state.
    start = E.extract_state()
    plan = planner.plan(tfn, is_goal, start, actions, max_depth=max_depth)
    if plan is None:
        log(f"[loop] no plan found within depth {max_depth} (goal hypothesis may be wrong)")
        return {"solved": False, "stage": "plan", "model_admitted": res["admitted"]}
    log(f"[loop] plan found: {len(plan)} actions {plan[:20]}")

    # 4. Validate the plan against the real game.
    advanced, steps, reward = planner.execute_plan(E, plan, log=log)
    log(f"[loop] plan executed on real game: advanced={advanced} steps={steps} reward={reward}")
    return {"solved": advanced, "stage": "execute", "plan_len": len(plan),
            "model_admitted": res["admitted"], "reward": reward}


if __name__ == "__main__":
    import sys
    game = sys.argv[1] if len(sys.argv) > 1 else "ls20"
    root = sys.argv[2] if len(sys.argv) > 2 else "environment_files"
    out = solve_level(game, root)
    print("\n=== LOOP RESULT ===")
    print(out)

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


def solve_level(game_name, env_root, n_transitions=16, max_depth=25, goal_rounds=5,
                explore_budget=300, log=print):
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

    # 2. Grounded goal discovery FIRST: use the verified model to novelty-search
    # the real game until it advances (reward observed). No guessing required.
    E.step(0)  # reset level for a clean budget
    solved, steps, nvis = planner.explore_for_reward(E, tfn, actions, budget=explore_budget, log=log)
    if solved:
        log(f"[loop] SOLVED by grounded exploration in {steps} steps ({nvis} states visited).")
        return {"solved": True, "stage": "explore", "steps": steps,
                "states_visited": nvis, "model_admitted": res["admitted"]}
    log(f"[loop] exploration ({explore_budget} steps, {nvis} states) found no reward; "
        f"falling back to goal hypothesis + planning.")

    # 3-5. Fallback -- iterative goal refinement: hypothesize goal -> plan-by-simulation ->
    # validate on the real game -> if it doesn't advance, feed the failure back and
    # re-hypothesize a DIFFERENT goal. The verified transition model is fixed; only
    # the (unobserved) goal is being searched, grounded by real-game validation.
    failed = []
    for g in range(goal_rounds):
        E.step(0)  # reset the level for a clean planning start
        start = E.extract_state()
        try:
            goal_code = planner.synthesize_goal(res["buffer"], actions, res["code"], failed=failed)
            is_goal = planner.load_is_goal(goal_code)
        except Exception as e:
            log(f"[loop] goal round {g+1}: synthesis failed: {e}")
            failed.append({"error": str(e)})
            continue
        plan = planner.plan(tfn, is_goal, start, actions, max_depth=max_depth)
        if plan is None:
            log(f"[loop] goal round {g+1}: no plan within depth {max_depth}; re-hypothesizing")
            failed.append({"goal_head": goal_code.splitlines()[:6], "outcome": "no reachable goal state"})
            continue
        log(f"[loop] goal round {g+1}: plan {len(plan)} actions {plan[:20]}")
        advanced, steps, reward = planner.execute_plan(E, plan, log=log)
        if advanced:
            log(f"[loop] SOLVED on goal round {g+1}: real game advanced the level.")
            return {"solved": True, "stage": "execute", "goal_rounds": g + 1,
                    "plan_len": len(plan), "model_admitted": res["admitted"]}
        reached = E.extract_state()
        movers = [(o["name"], o["x"], o["y"]) for o in reached
                  if o["name"] in {m["name"] for m in start if (m["x"], m["y"]) !=
                                   next(((r["x"], r["y"]) for r in reached if r["name"] == m["name"]), None)}]
        failed.append({"goal_head": goal_code.splitlines()[:8],
                       "plan_len": len(plan), "reached_movers": movers[:4],
                       "outcome": "real game did NOT advance"})
        log(f"[loop] goal round {g+1}: plan reached a state but level did not advance; refining")
    return {"solved": False, "stage": "goal-refine", "goal_rounds": goal_rounds,
            "model_admitted": res["admitted"]}


if __name__ == "__main__":
    import sys
    game = sys.argv[1] if len(sys.argv) > 1 else "ls20"
    root = sys.argv[2] if len(sys.argv) > 2 else "environment_files"
    out = solve_level(game, root)
    print("\n=== LOOP RESULT ===")
    print(out)

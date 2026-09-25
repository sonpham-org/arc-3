"""Build the branch plan for one recorded run: for every solved level and every turn i of that level,
a job per reasoning effort that replays the recording through turn i and plays live from turn i+1.

usage: python build_plan.py <run_dir> <out_pack_dir> [--efforts xhigh,high,medium,low] [--max-points N]
  run_dir: transcripts/, artifacts/ (events.jsonl, viewer_data.json), benchmark.json (downloaded from the bucket)
Writes <out_pack_dir>/plan.json, turns/<game>.json, actions/<game>.json, levels.json.
"""
from __future__ import annotations

import argparse, json, re, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from branch_parse import parse_transcript, turns_to_json  # noqa: E402

GAME_S = 7920


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir"); ap.add_argument("out")
    ap.add_argument("--efforts", default="high:2,medium:2,low:2,xhigh:1", help="effort:replicates per checkpoint")
    ap.add_argument("--xhigh-every", type=int, default=1, help="schedule the xhigh control only at every k-th checkpoint")
    ap.add_argument("--long-level-points", type=int, default=16, help="levels with more turns than this get this many evenly spaced points")
    ap.add_argument("--max-points", type=int, default=0, help="0 = every turn; else at most N evenly spaced branch points per level (always incl. i=0 and i=N-1)")
    ap.add_argument("--min-remaining-turns", type=int, default=1, help="skip branch points whose original remaining turns < this")
    a = ap.parse_args()
    run = Path(a.run_dir); out = Path(a.out); (out / "turns").mkdir(parents=True, exist_ok=True); (out / "actions").mkdir(exist_ok=True)
    efforts = [(e.split(":")[0], int(e.split(":")[1]) if ":" in e else 1) for e in a.efforts.split(",")]
    plan, levels_summary = [], []
    for tp in sorted((run / "transcripts").glob("*_p0.txt")):
        game_id = tp.name[:-len("_p0.txt")]
        turns = parse_transcript(tp)
        (out / "turns" / f"{game_id}.json").write_text(json.dumps(turns_to_json(turns)), encoding="utf-8")
        ev = [json.loads(l) for l in (run / "artifacts" / f"{game_id}_p0_events.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        acts = [r for r in ev if r.get("type") == "action"]
        (out / "actions" / f"{game_id}.json").write_text(json.dumps([{"n": r["action_num"], "a": r["action_display"], "level": r["level"], "step": r["analysis_step"], "lc": bool(r.get("level_completed"))} for r in acts]), encoding="utf-8")
        vd = json.loads((run / "artifacts" / f"{game_id}_p0_viewer_data.json").read_text(encoding="utf-8"))
        solved = int(vd["levels_completed"]); apl = vd["actions_per_level"]
        cum = 0
        # per-turn (analysis step) bookkeeping: chars generated, time_left at first request
        step_chars = defaultdict(int); step_time = {}
        for t in turns:
            for r in t.requests:
                step_chars[t.step] += len(r.reasoning) + len(r.content) + sum(len(c["function"]["arguments"]) for c in r.tool_calls)
                if t.step not in step_time and r.time_left_s is not None:
                    step_time[t.step] = r.time_left_s
        steps_all = sorted({t.step for t in turns})
        for L in range(1, solved + 1):
            lo, hi = cum + 1, cum + apl[L - 1]          # action numbers of level L
            cum = hi
            lvl_acts = [r for r in acts if lo <= r["action_num"] <= hi]
            assert lvl_acts and lvl_acts[-1].get("level_completed"), (game_id, L)
            first_step = min(r["analysis_step"] for r in lvl_acts); last_step = max(r["analysis_step"] for r in lvl_acts)
            steps = [s for s in steps_all if first_step <= s <= last_step]
            N = len(steps)
            # branch points: after step S = steps[i-1] for i=1..N-1, plus i=0 = after the step before first_step
            points = list(range(0, N))   # i = number of level turns already replayed
            cap = a.max_points or (a.long_level_points if N > a.long_level_points * 2 else 0)
            if cap and len(points) > cap:
                import numpy as np
                idx = sorted({int(round(x)) for x in np.linspace(0, N - 1, cap)})
                points = [points[k] for k in idx]
            # wall clock of the level's remainder: time_left at the branch turn minus time_left at the completing turn
            t_end = step_time.get(last_step)
            for pi, i in enumerate(points):
                S = steps[i - 1] if i > 0 else first_step - 1          # replay through analysis step S
                next_step = steps[i]                                  # the turn that goes live
                remaining = [r for r in lvl_acts if r["analysis_step"] > S]
                if len([s for s in steps if s > S]) < a.min_remaining_turns:
                    continue
                orig_rem_actions = len(remaining)
                orig_rem_turns = len([s for s in steps if s > S])
                orig_rem_chars = sum(step_chars[s] for s in steps if s > S)
                t_branch = step_time.get(next_step)
                seg_wall = (t_branch - t_end) if (t_branch is not None and t_end is not None) else None
                exp_action_count = lo - 1 + (apl[L - 1] - orig_rem_actions)   # actions taken before the live turn
                group = f"{game_id[:4]}-L{L}-i{i:03d}"
                for e, reps in efforts:
                    if e == "xhigh" and pi % a.xhigh_every:
                        continue
                    for rep in range(reps):
                        plan.append({
                        "job_id": f"{group}-{e}{rep}", "group": group, "frac": round(i / N, 3), "game_id": game_id, "level": L, "i": i, "n_turns": N,
                        "replay_through_step": S, "live_from_step": next_step, "effort": e,
                        "expected_action_count": exp_action_count, "expected_levels_completed": L - 1,
                        "orig_remaining_actions": orig_rem_actions, "orig_remaining_turns": orig_rem_turns,
                        "orig_remaining_chars": orig_rem_chars, "orig_segment_wall_s": seg_wall,
                        "time_left_s": t_branch, "level_action_lo": lo, "level_action_hi": hi,
                        # Son: play until level solve / 2x more turns / 2x more actions; the time cap is only a VM-budget safety net
                        "action_cap_extra": 2 * orig_rem_actions, "turn_cap": 2 * orig_rem_turns,
                        "time_cap_s": max(3 * seg_wall if seg_wall else 0, 900),
                        })
            levels_summary.append({"game_id": game_id, "level": L, "turns": N, "actions": apl[L - 1], "first_step": first_step, "last_step": last_step,
                                   "points": len(points), "level_wall_s": (step_time.get(first_step) - t_end) if (t_end is not None and first_step in step_time) else None})
    groups = sorted({j["group"] for j in plan}, key=lambda g: (round(next(j["frac"] for j in plan if j["group"] == g) * 8) / 8, g))
    order = {g: k for k, g in enumerate(groups)}
    plan.sort(key=lambda j: (order[j["group"]], j["effort"] != "xhigh", j["effort"], j["job_id"]))
    for j in plan: j["group_index"] = order[j["group"]]
    (out / "plan.json").write_text(json.dumps(plan, indent=0), encoding="utf-8")
    (out / "levels.json").write_text(json.dumps(levels_summary, indent=1), encoding="utf-8")
    tot_turns = sum(j["orig_remaining_turns"] for j in plan)
    print(f"levels={len(levels_summary)} checkpoints={len(groups)} jobs={len(plan)} sum(orig_remaining_turns)={tot_turns} "
          f"~{tot_turns*50/3600/7:.1f} VM-hours at 50 s/turn on 7 lanes")
    for l in levels_summary: print(l)


if __name__ == "__main__":
    main()

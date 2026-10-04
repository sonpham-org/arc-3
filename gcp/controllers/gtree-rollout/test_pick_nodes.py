"""Tests for the offline node picker on the REAL seed master files (no GCS: a local copy of a few of them).

Author: Claude Opus 5.5 (3-Oct-2026).

  C:/Python312/python.exe test_pick_nodes.py [--store D:/codex-work/gtree-rollout-test/seed-store]

The store holds rollouts/daniel-hicache-sbt06-b-1003/ (all 20 games) and sb26 / ls20 / ft09 of runs c, d, e
(downloaded from gs://cellens-ai-artifacts/arc3-gtree/v1/rollouts/). Checks: level starts and backward nodes found,
only restartable nodes, fenced games absent, the N cap respected, the assignment rule (stock anchor, least-sampled
modes, policy tie-break, design probabilities), the stop budget, and snapshot restart points (state index for a seed
node, state_ref on a campaign try's step). 3-Oct pilot fixes: every game in a round's first pass, least-sampled games
first (ties rotate by round), queued nodes skipped, a blocked restart point replaced by another seed play of the same
node, a blocked node never picked, the token cap on each job.
"""
from __future__ import annotations

import argparse
import copy
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pick_nodes as pn  # noqa: E402
import rl_common as rc  # noqa: E402

RESULTS = []


def check(ok, name, detail=""):
    RESULTS.append((bool(ok), name))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=r"D:\codex-work\gtree-rollout-test\seed-store")
    a = ap.parse_args()
    seed = set(rc.SEED_RUNS)
    plays = rc.load_plays(rc.sync_masters(a.store, sorted(seed), Path(a.store) / "_cache"))
    check(len(plays) >= 25, "seed master files load", f"{len(plays)} plays")
    steps = {(p["rollout"]["id"], s["seq"]): s for p in plays for s in p["steps"]}
    by_n1 = {}
    for p in plays:
        for s in p["steps"]:
            by_n1.setdefault(s["n1"], []).append((p["rollout"], s))

    # a fenced play smuggled in must never be picked
    fenced = copy.deepcopy(plays[0])
    fenced["rollout"].update(game="dc22", id="daniel-hicache-sbt06-b-1003:dc22_p0")
    fenced["rollout"]["result"] = dict(fenced["rollout"]["result"], game_id="dc22-fdcac232")
    for s in fenced["steps"]:
        s.update(game="dc22", n1="dc22:" + s["n1"].split(":", 1)[1], n5="dc22:" + s["n5"].split(":", 1)[1])
    jobs, rep = pn.pick(plays + [fenced], campaign="pt", round_=1, seed_runs=seed, limit=400, per_game=40,
                        backward_depth=4, K=5, N=4)
    print("   report", {k: v for k, v in rep.items() if k != "per_game"})
    check(not [j for j in jobs if j["game_id"].startswith(tuple(rc.FENCED))], "fenced games never picked")
    cls = Counter(j["pick"]["class"] for j in jobs)
    check(cls["level_start"] > 0 and cls["backward"] > 0 and cls["uncertain"] > 0, "all three classes present",
          str(dict(cls)))
    ok = True
    for j in jobs:
        src = steps.get((j["source"]["rollout_id"], j["origin"]["seq"]))
        ok &= bool(src and src["resumable"] and src["ctx_before"] and src["n1"] == j["origin"]["t1"]
                   and int(src["detail"].get("part") or 1) == 1 and j["mode"] == "replay_exact"
                   and j["source"]["requests"].endswith(f"{j['game_id']}_p{j['pass']}_requests.jsonl"))
    check(ok, "every origin is a resumable seed step (ctx_before, turn start) with its request log named")
    # level starts: sb26 levels 1..8 of run b each start a level, and they come first for the game
    sb = [j for j in jobs if j["game_id"].startswith("sb26")]
    starts = sorted({j["origin"]["level"] for j in sb if j["pick"]["class"] == "level_start"})
    check(starts == list(range(1, 9)) and all(j["origin"]["moves"] == 0 for j in sb
                                                if j["pick"]["class"] == "level_start" and not j["pick"]["shifted"]),
          "sb26: a level-start node for each of its 8 levels (moves 0 after a clear, or the root)", str(starts))
    order = [j["pick"]["class"] for j in sb]
    check(order == sorted(order, key=["level_start", "backward", "uncertain"].index),
          "per game: level starts, then backward, then uncertain", str(Counter(order)))
    # backward: depth 1 of a level = the clearing step of that level's fewest-moves seed path
    bw = [j for j in sb if j["pick"]["class"] == "backward" and j["pick"]["score"] == 1]
    good = 0
    for j in bw:
        s = steps[(j["source"]["rollout_id"], j["origin"]["seq"])]
        lvl_best = min(rc.level_moves(x) or 10**9 for (rid, _), x in steps.items()
                       if x["game"] == "sb26" and x["level"] == s["level"] and x["moves"] == 0 and rid.split(":")[0] in seed)
        good += (s["outcome"]["moves_to_clear"] == s["moves_step"] and j["pick"]["level_moves"] == lvl_best)
    check(bw and good == len(bw), "backward depth 1 = the clearing step of the level's best known seed path",
          f"{good}/{len(bw)}")
    # assignment
    j0 = jobs[0]
    asg = j0["assignments"]
    check(asg[0]["mode"] == "stock" and asg[0]["anchor"] and abs(sum(x["design_prob"] for x in asg) -
                                                                  sum(1 / len(asg) for _ in asg)) < 1e-9
          and len({x["mode"] for x in asg[1:]}) == len(asg) - 1 and all(x["design_prob"] == 0.2 for x in asg),
          "assignment: try 0 = stock anchor, then distinct least-sampled modes, design prob = share of tries",
          str([(x["mode"], x["design_prob"]) for x in asg]))
    check(all(30 <= j["stop"]["move_budget"] <= 200 and j["stop"]["turn_cap"] == 60 for j in jobs)
          and all(j["stop"]["move_budget"] == max(30, min(200, 2 * j["pick"]["best_from_node"]))
                  for j in jobs if j["pick"]["best_from_node"]),
          "stop: move budget = 2 x best known moves from the node (30..200), turn cap 60")
    # policy tie-break: among modes equally used so far (node AND campaign-wide), the policy's favourite goes first;
    # the next fresh node then spreads to other modes (campaign-wide least-assigned comes before the policy)
    pol = {"version": "p", "table": {}, "default": {"search": 0.6, "stock": 0.4}}
    jobs_p, _ = pn.pick(plays, campaign="pt", round_=1, seed_runs=seed, limit=3, per_game=1, pol=pol)
    check(jobs_p[0]["assignments"][1]["mode"] == "search" and jobs_p[0]["assignments"][1]["policy_prob"] == 0.6
          and all(j["assignments"][1]["mode"] != "search" for j in jobs_p[1:]),
          "ties among least-sampled modes broken by the policy's probability",
          str([[x["mode"] for x in j["assignments"]] for j in jobs_p]))
    # N cap: fake campaign samples at the sb26 root (every non-stock mode at N except probe at N-1)
    root = "sb26:t1:root"
    camp = []
    for m in rc.MODES:
        if m == "stock":
            continue
        for i in range(4 if m != "probe" else 3):
            camp.append({"rollout": {"id": f"gtr-pt:sb26_p0.x.{m}{i}", "run": "gtr-pt", "game": "sb26",
                                     "origin_kind": "replay_exact", "result": {"stop_reason": "move_budget"}},
                         "steps": [{"n1": root, "n5": "x", "action": m, "game": "sb26", "level": 1, "seq": 1,
                                    "moves": 0, "outcome": {}}]})
    jobs_n, _ = pn.pick(plays + camp, campaign="pt", round_=2, seed_runs=seed, limit=200, per_game=40,
                        campaign_restarts=False)
    rj = [j for j in jobs_n if j["origin"]["t1"] == root]
    check(len(rj) == 1 and [x["mode"] for x in rj[0]["assignments"]] == ["stock", "probe"],
          "N cap: only probe (3 of 4) is still open at the sb26 root -> stock anchor + one probe try",
          str([[x["mode"] for x in j["assignments"]] for j in rj]))
    camp.append(copy.deepcopy(camp[-1]))
    camp[-1]["steps"][0]["action"] = "probe"
    jobs_n2, _ = pn.pick(plays + camp, campaign="pt", round_=2, seed_runs=seed, limit=200, per_game=40,
                         campaign_restarts=False)
    check(not [j for j in jobs_n2 if j["origin"]["t1"] == root], "N cap: a node with every mode at N is not picked")
    # snapshots: an index entry turns a seed node into a snapshot job; a campaign try's state_ref is a restart point
    s_id = (jobs[0]["source"]["rollout_id"], jobs[0]["origin"]["seq"])
    idx = {s_id: {"sha": "a" * 64, "rollout_id": s_id[0], "seq": s_id[1]}}
    tri = copy.deepcopy([p for p in plays if p["rollout"]["game"] == "ls20"][0])
    tri["rollout"].update(id="gtr-pt:ls20_p0.j.k0", run="gtr-pt", origin_kind="replay_exact",
                          result=dict(tri["rollout"]["result"], stop_reason="cleared", origin_actions_before=0))
    for s in tri["steps"]:
        s.update(resumable=False, ctx_before=None, n1=s["n1"] + "x", n5=s["n5"] + "x")
    tri["steps"][3]["state_ref"] = "b" * 64
    jobs_s, rep_s = pn.pick(plays + [tri], campaign="pt", round_=3, seed_runs=seed, limit=2000, per_game=200,
                            state_index=idx, store="gs://bucket/v1")
    js = [j for j in jobs_s if (j["source"]["rollout_id"], j["origin"]["seq"]) == s_id]
    jt = [j for j in jobs_s if j["source"]["rollout_id"] == tri["rollout"]["id"]]
    check(js and js[0]["mode"] == "snapshot" and js[0]["source"]["state"] == "gs://bucket/v1/state/" + "a" * 64 +
          ".pkl.gz" and js[0]["source"].get("requests") and js[0]["source"]["ctx_before"],
          "a seed node in the state index becomes a snapshot job (request log kept as the fallback)",
          str(js[0]["source"] if js else None)[:200])
    check(len(jt) == 1 and jt[0]["mode"] == "snapshot" and jt[0]["origin"]["seq"] == 4 and not jt[0]["source"].get(
        "requests"), "a campaign try's snapshotted step is a restart point (snapshot only, no logs)",
          f"{len(jt)} jobs from the try; restore kinds {rep_s['by_restore']}")
    # game order (3-Oct pilot: every round began ar25, bp35, cd82, cn04 and the VM never got further)
    g1, q1 = pn.pick(plays, campaign="pt", round_=1, seed_runs=seed, limit=40, per_game=4)
    g2, q2 = pn.pick(plays, campaign="pt", round_=2, seed_runs=seed, limit=40, per_game=4)
    n_games = len(q1["games"])
    check(sorted({j["game_id"][:4] for j in g1[:n_games]}) == sorted(q1["games"]) and n_games >= 15
          and q1["game_order"][0] != q2["game_order"][0],
          "game order: the first pass of a round has one job for EVERY game; ties rotate with the round",
          f"{n_games} games; round 1 starts {q1['game_order'][:3]}, round 2 starts {q2['game_order'][:3]}")
    seen_games = q1["game_order"][:3]
    camp_g = [{"rollout": {"id": f"gtr-pt:{g}_p0.x.k{i}", "run": "gtr-pt", "game": g, "origin_kind": "replay_exact",
                           "result": {"stop_reason": "cleared"}},
               "steps": [{"n1": f"{g}:t1:fake{i}", "n5": f"{g}:t5:fake{i}", "action": "probe", "game": g, "level": 1,
                          "seq": 1, "moves": 0, "outcome": {}}]}
              for n, g in enumerate(seen_games) for i in range(3 - n)]
    g3, q3 = pn.pick(plays + camp_g, campaign="pt", round_=1, seed_runs=seed, limit=40, per_game=4,
                     campaign_restarts=False)
    check(q3["game_order"][-3:] == seen_games[::-1] and g3[0]["game_id"][:4] not in seen_games,
          "game order: the games the campaign sampled most go last (least-sampled first)",
          f"order tail {q3['game_order'][-3:]}, first job {g3[0]['game_id'][:4]}")
    # pending jobs: their nodes are not picked again, their games count as sampled
    pend = [{"game": g1[0]["game_id"][:4], "t1": g1[0]["origin"]["t1"]}]
    g4, q4 = pn.pick(plays, campaign="pt", round_=1, seed_runs=seed, limit=40, per_game=4, pending=pend)
    check(pend[0]["t1"] not in {j["origin"]["t1"] for j in g4} and q4["skipped_pending"] >= 1
          and q4["game_order"][-1] == pend[0]["game"],
          "pending: a node with a job still queued is skipped and its game goes last",
          f"skipped {q4['skipped_pending']}, order tail {q4['game_order'][-1]}")
    # blocked restart points (a restore that diverged): the same node comes from another seed play
    allj, _ = pn.pick(plays, campaign="pt", round_=1, seed_runs=seed, limit=400, per_game=400)
    root = [j for j in allj if j["origin"]["t1"] == "sb26:t1:root"]
    key = pn.restart_key(root[0]["source"]["rollout_id"], root[0]["origin"]["seq"]) if root else "none"
    g5, q5 = pn.pick(plays, campaign="pt", round_=1, seed_runs=seed, limit=400, per_game=400, blocked={key: "diverged"})
    r5 = [j for j in g5 if j["origin"]["t1"] == "sb26:t1:root"]
    check(root and len(r5) == 1 and pn.restart_key(r5[0]["source"]["rollout_id"], r5[0]["origin"]["seq"]) != key
          and q5["skipped_blocked"] >= 1,
          "blocked restart point: skipped, and the node is picked from another seed play instead",
          f"blocked {key} -> {r5[0]['source']['rollout_id'] if r5 else None}")
    g6, q6 = pn.pick(plays, campaign="pt", round_=1, seed_runs=seed, limit=400, per_game=400,
                     blocked_nodes={"sb26:t1:root": "restore failed from 2 source plays"})
    check(not [j for j in g6 if j["origin"]["t1"] == "sb26:t1:root"], "blocked node: never picked from any source")
    # token cap per try
    g7, _ = pn.pick(plays, campaign="pt", round_=1, seed_runs=seed, limit=5, token_cap=200000)
    check(all(j["stop"]["token_cap"] == 200000 for j in g7) and all(j["stop"]["token_cap"] is None for j in g1),
          "stop: token_cap per try when given (None otherwise)")
    # modes spread across fresh nodes (rl2 round 1 gave every level start the same probe/rethink/execute/brief)
    g8, _ = pn.pick(plays, campaign="pt", round_=1, seed_runs=seed, limit=5)
    firsts = [a["mode"] for j in g8 for a in j["assignments"] if a["mode"] != "stock"]
    check(len(g8) == 5 and len(set(firsts)) == min(len(firsts), len(rc.MODES) - 1),
          "assign: fresh nodes in one round get different modes (campaign-wide least-assigned first)",
          f"{len(set(firsts))} distinct of {len(firsts)}")
    pend8 = [{"t1": "none", "game": "x", "assignments": [{"mode": m} for m in rc.MODES if m not in ("stock", "probe")]}]
    g9, _ = pn.pick(plays, campaign="pt", round_=1, seed_runs=seed, limit=1, pending=pend8)
    check(g9 and g9[0]["assignments"][1]["mode"] == "probe",
          "assign: modes already queued elsewhere go after the ones the campaign has not tried")
    # class mix: level starts alone filled every rl2 round; with a mix the other classes get their share
    g10, r10 = pn.pick(plays, campaign="pt", round_=1, seed_runs=seed, limit=20,
                       mix={"level_start": 0.4, "backward": 0.3, "uncertain": 0.3})
    g11, r11 = pn.pick(plays, campaign="pt", round_=1, seed_runs=seed, limit=20)
    check(len(g10) == 20 and r10["by_class"].get("level_start", 0) <= 8 and r10["by_class"].get("backward", 0) >= 1
          and r11["by_class"].get("level_start", 0) > r10["by_class"].get("level_start", 0),
          "mix: each class gets its share of the round (no mix: level starts first)",
          f"mix {r10['by_class']} / none {r11['by_class']}")
    bad = [n for ok, n in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed" + (f"; FAILED: {bad}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

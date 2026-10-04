"""Tests for the RL learner loop on synthetic sibling records (no GCS: a local store).

Author: Claude Opus 5.5 (3-Oct-2026).

  C:/Python312/python.exe test_rl_loop.py

Store: the real sb26 seed master (run b) + synthetic campaign tries: 3 nodes (levels 1, 2, 3 at different phases)
x 4 rounds x 5 siblings (stock, probe, execute, brief, rethink); execute clears in the fewest moves, rethink never
clears. Checks: init writes policy v0 + round 1; a round computes each branch step's advantage against its siblings
at the same t1 node (stratified per action), trains v1 toward execute, writes current.json (seq 1) and the archive,
prints the report, and refills round 2 from the picker; the next round trains v2 from v1 (KL prior) and keeps it.
Queue and failures (3-Oct pilot): no refill while enough jobs are unstarted; a server summary with a diverged job
blocks that restart point (the diff read from the run's result.json), round 2 skips it and the still-queued nodes.
Token charge: score_returns / train get token_alpha and tokens-to-clear over every step; jobs carry the token cap.
"""
from __future__ import annotations

import gzip
import json
import random
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rl_common as rc  # noqa: E402
import rl_loop  # noqa: E402

SEED = Path(r"D:\codex-work\gtree-rollout-test\seed-store\rollouts\daniel-hicache-sbt06-b-1003\sb26_p0.jsonl.gz")
RUN = "daniel-hicache-sbt06-b-1003"
MOVES = {"stock": 16, "probe": 20, "execute": 8, "brief": 18, "rethink": None}
NODES = [("sb26:t1:synA", 1, 0, 0), ("sb26:t1:synB", 2, 14, 20), ("sb26:t1:synC", 3, 30, 80)]
RESULTS = []


def check(ok, name, detail=""):
    RESULTS.append((bool(ok), name))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


def write_try(store: Path, n: int, node, mode: str, rng: random.Random) -> None:
    n1, level, moves, ail = node
    m = MOVES[mode]
    mtc = None if m is None else max(1, m + rng.randint(-2, 2))
    rid = f"gtr-syn:sb26_p0.syn-{n}.k{n % 5}"
    rollout = {"kind": "rollout", "id": rid, "game": "sb26", "run": "gtr-syn", "build": "gtree-rollout",
               "origin_kind": "replay_exact", "origin_state": n1, "policy": "policy@syn-v0",
               "result": {"game_id": "sb26-7fbdac44", "pass": 0, "cleared": mtc is not None, "moves_to_clear": mtc,
                          "stop_reason": "cleared" if mtc is not None else "move_budget", "job": f"syn-{n // 5}",
                          "try": n % 5, "origin_actions_before": 0}}
    step = {"kind": "step", "id": f"{rid}:1", "rollout_id": rid, "seq": 1, "game": "sb26", "level": level,
            "moves": moves, "screen_hash": "x", "action": mode,
            "detail": {"source": "coach", "assigned": True, "design_prob": 0.2, "turn": 5, "part": 1, "policy": "syn-v0"},
            "features": {"level": level, "actions_in_level": ail, "actions_total": ail + 10 * level},
            "outcome": {"moves_to_clear": mtc, "cleared_level": int(mtc is not None), "level_weight": level},
            "n1": n1, "n5": n1.replace(":t1:", ":t5:"), "moves_step": 1, "resumable": False, "ctx_before": None}
    p = store / "rollouts" / "gtr-syn" / f"sb26_p0.syn-{n}.k{n % 5}.jsonl.gz"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gzip.compress((json.dumps(rollout) + "\n" + json.dumps(step) + "\n").encode()))


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="rl-loop-test-"))
    store = tmp / "store"
    (store / "rollouts" / RUN).mkdir(parents=True)
    shutil.copy(SEED, store / "rollouts" / RUN / SEED.name)
    common = ["--min-ess", "0", "--min-steps", "10", "--campaign", "syn", "--store", str(store), "--seed-runs", RUN, "--cache", str(tmp / "cache"),
              "--epochs", "150", "--limit", "6"]
    rl_loop.init(rl_loop.args(["init", *common]))
    rls = rc.Store(str(store / "rl" / "syn"))
    v0 = json.loads(rls.get("policy/current.json"))
    r1 = sorted(rls.list("jobs/round-0001/"))
    check(v0["version"] == "syn-v0" and v0["seq"] == 0 and r1, "init: policy v0 (stock) and round 1 jobs",
          f"{len(r1)} jobs")
    r1_jobs = [json.loads(rls.get(x)) for x in r1]
    check(all(j["stop"]["token_cap"] == 200000 for j in r1_jobs), "init: jobs carry the token cap (default 200k)")
    rng = random.Random(7)
    n = 0
    for _ in range(4):
        for node in NODES:
            for mode in MOVES:
                write_try(store, n, node, mode, rng)
                n += 1
    # the queue is not low (no server has played anything): no refill (3-Oct pilot: a new round every 15 minutes)
    out0 = rl_loop.iterate(rl_loop.args(["run", *common, "--once", "--refill-below", str(len(r1))]), write=False)
    check(not out0["jobs"] and any("refill: not yet" in x for x in out0["report"]),
          "no refill while the queue holds enough unstarted jobs", [x for x in out0["report"] if "queue" in x])
    # a server played two round-1 jobs; one of them diverged at its restore (status only, as the pilot's summary)
    import time as _time
    done_j, div_j = r1_jobs[0], r1_jobs[1]
    rc.write_json(rls, "results/arc3-rl-a/summary.json", {"updated_at": _time.time(), "results": [
        {"job": done_j["job_id"], "try": k, "status": "done", "stop": "cleared"} for k in range(5)] + [
        {"job": div_j["job_id"], "try": k, "status": "diverged", "stop": "diverged"} for k in range(5)]})
    rls.put(f"runs/rl-syn-a/gtree-rollout/{div_j['job_id']}/k0/result.json", json.dumps({
        "status": "diverged", "diverged": {"kind": "origin_messages", "call": 0, "first": {
            "message": 1, "sent": "No previous sequence has been executed yet.",
            "logged": "No previous action sequence was captured."}}}).encode(), once=False)
    import learn_awr
    seen = {}
    real_sr, real_tr = learn_awr.score_returns, learn_awr.train

    def sr(steps, human=None, best=None, tok=None, token_alpha=0.0):
        seen.setdefault("sr", []).append((tok, token_alpha))
        return real_sr(steps, human, best, tok, token_alpha)

    def tr(*a, **kw):
        seen["tr"] = (kw.get("tok"), kw.get("token_alpha"))
        return real_tr(*a, **kw)
    learn_awr.score_returns, learn_awr.train = sr, tr
    try:
        out = rl_loop.iterate(rl_loop.args(["run", *common, "--once"]))
    finally:
        learn_awr.score_returns, learn_awr.train = real_sr, real_tr
    print("\n".join(out["report"]))
    check(out["trained"] and out["version"] == "syn-v1", "round 1 trained policy syn-v1", out["version"])
    tok0 = (seen.get("sr") or [(None, None)])[0][0]
    check(seen.get("sr") and all(a == 0.5 for _, a in seen["sr"]) and isinstance(tok0, dict)
          and any(k.startswith(RUN) for k in tok0) and seen.get("tr") == (tok0, 0.5)
          and any("token_alpha 0.5" in x and "token_cap 200000" in x for x in out["report"]),
          "token charge: score_returns and train get token_alpha 0.5 and tokens-to-clear over EVERY step "
          "(seed steps included), and the log says so", f"{len(tok0 or {})} steps with tokens to clear")
    st0 = json.loads(rls.get("learner/state.json"))
    bkey = f"{div_j['source']['rollout_id']}#{div_j['origin']['seq']}"
    blk = (st0.get("blocked") or {}).get(bkey) or {}
    check(blk.get("tries") == 5 and blk.get("why") == "diverged" and (blk.get("detail") or {}).get("diverged")
          and any("blocked restart points" in x for x in out["report"])
          and any("No previous sequence" in x for x in out["report"]),
          "a restart point whose restore diverged is blocked, with the diff read from the run's result.json",
          json.dumps(blk)[:300])
    # sibling advantages
    import learn_awr
    plays = rc.load_plays(rc.sync_masters(str(store), [RUN, "gtr-syn"], tmp / "cache"))
    train = rl_loop.branch_steps(plays, "syn")
    best = learn_awr.best_known([s for p in plays for s in p["steps"]])
    G = learn_awr.score_returns(train, None, best)
    keep = [(s, g) for s, g in zip(train, G) if g is not None]
    base = learn_awr.baselines([s for s, _ in keep], [g for _, g in keep])
    i = next(k for k, (s, _) in enumerate(keep) if s["n1"] == NODES[0][0] and s["action"] == "execute")
    groups = {}
    for k, (s, g) in enumerate(keep):
        if s["n1"] == NODES[0][0] and k != i:
            groups.setdefault(s["action"], []).append(g)
    expect = sum(sum(v) / len(v) for v in groups.values()) / len(groups)
    check(len(train) == 60 and abs(base[i] - expect) < 1e-9 and keep[i][1] - base[i] > 0,
          "advantage = G - the mean over sibling actions at the same t1 node (stratified, itself excluded)",
          f"G {keep[i][1]:.3f} baseline {base[i]:.3f} (expected {expect:.3f}); 60 branch steps")
    pol = json.loads(rls.get("policy/current.json"))
    arch = rls.get("policy/syn-v1.json")
    dists = [rc.mode_dist(pol, s["features"]) for s in train]
    mean = {m: sum(d[m] for d in dists) / len(dists) for m in rc.MODES}
    top = max(mean, key=mean.get)
    check(pol["seq"] == 1 and arch and top == "execute" and mean["execute"] > 2 / len(rc.MODES)
          and mean["rethink"] < mean["execute"],
          "the policy moved toward the fastest sibling action (execute); current.json = v1 (seq 1), archived",
          {k: round(v, 3) for k, v in mean.items()})
    check(any("most-sampled nodes" in x for x in out["report"]) and any("execute" in x and "clear 100%" in x
                                                                        for x in out["report"]),
          "report: clear rate and moves per action at the most-sampled nodes")
    r2 = sorted(rls.list("jobs/round-0002/"))
    st = json.loads(rls.get("learner/state.json"))
    check(r2 and st["round"] == 2 and st["version"] == 1, "refill: round 2 jobs written from the picker",
          f"{len(r2)} jobs, state {st['round']}/{st['version']}")
    j = json.loads(rls.get(r2[0]))
    check(j["policy"]["version"] == "syn-v1" and j["assignments"][0]["mode"] == "stock",
          "round 2 jobs carry the new policy version (ties) and the stock anchor")
    r2_jobs = [json.loads(rls.get(x)) for x in r2]
    unstarted = {x["origin"]["t1"] for x in r1_jobs[2:]}
    check(not [x for x in r2_jobs if f"{x['source']['rollout_id']}#{x['origin']['seq']}" == bkey]
          and not [x for x in r2_jobs if x["origin"]["t1"] in unstarted]
          and all(x["stop"]["token_cap"] == 200000 for x in r2_jobs),
          "round 2 skips the blocked restart point and the nodes still queued in round 1; token cap kept",
          f"{len(r2_jobs)} jobs")
    out2 = rl_loop.iterate(rl_loop.args(["run", *common, "--once", "--refill-below", "1"]))
    check(not list(rls.list("jobs/round-0003/")) and any("refill: not yet" in x for x in out2["report"]),
          "next round: rounds 1 + 2 still queued, no new round", [x for x in out2["report"] if "queue" in x])
    pol2 = json.loads(rls.get("policy/current.json"))
    d2 = [rc.mode_dist(pol2, s["features"]) for s in train]
    m2 = {m: sum(d[m] for d in d2) / len(d2) for m in rc.MODES}
    check(out2["version"] == "syn-v2" and pol2["seq"] == 2 and max(m2, key=m2.get) == "execute",
          "round 2 trains v2 from v1 (KL prior): still execute first", {k: round(v, 3) for k, v in m2.items()})
    shutil.rmtree(tmp, ignore_errors=True)
    bad = [nm for ok, nm in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed" + (f"; FAILED: {bad}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

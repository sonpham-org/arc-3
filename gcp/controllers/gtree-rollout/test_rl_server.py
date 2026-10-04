"""Local tests for the RL rollout server: Daniel's real harness on Windows, a stub model, no GPU.

Author: Claude Opus 5.5 (3-Oct-2026).

  D:/codex-work/_branch/venv/Scripts/python.exe test_rl_server.py [--work DIR]

Source play: the fork-dev dc22 request log (test_rollout.py's). dc22 is FENCED: test data only, never published.
A. sibling job, K=5, K-replay fallback (what Windows can run for real): 5 tries from the identical restored state;
   each first live request carries its assigned mode's focus line (stock: none); records carry the assignment,
   design probability and policy version; the master file reads back.
B. policy reload: the @file policy is re-read between tries (v1 -> v2), and a stale (lower seq) file is refused.
C. fork path with a fake fork (Windows has no os.fork): the parent restores once, warms the cache, copies the restore
   dir, "forks" (fake pids for k0..k3, the thread itself becomes sibling k4), the child relocates every path to k4/
   (no reference to restore/ left), plays its assignment, writes its records and exits (fake exit). The warm-up
   request = the child's first live request minus the coach line; the restore dir is not written after the fork.
D. the parent's wait: fake waitpid, exit codes collected, children killed past deadline + grace.
G. lanes per sibling: 3 siblings on 2 lanes fork as lanes come back; at the deadline unstarted siblings are listed.
E. a root whose source play began with the notebook's warmup RESET (testdata/ar25_b1003_root_*: the head of
   daniel-hicache-sbt06-b-1003's ar25 play; 3-Oct pilot: all 40 ar25 root tries diverged): the RESET is replayed and
   the first request matches the log; with the pilot's code path the same divergence reproduces; the origin snapshot
   taken after the RESET restores too.
F. serve() with a fake run_node: the newest two rounds are played oldest first (a newer round does not drop the older
   round's unstarted jobs), older rounds are dropped; summary rows name the restart point and carry a diverged try's
   (cut) diff; the running jobs are listed.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import local_env as le  # noqa: E402

SRC_REQ = Path(r"D:\codex-work\rl-20261001\fork-dev\dc22-fdcac232_p0_requests.jsonl")
GAME_ID = "dc22-fdcac232"
STUB_CODE = ("a = valid_actions[0] if valid_actions else 'UP'\n"
             "r = action([{'action': a}])\n"
             "print('stub moved', a)")
ORIGIN_TURN = 3
MODES5 = ["stock", "probe", "execute", "brief", "rethink"]
RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> bool:
    RESULTS.append((bool(ok), name, detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)
    return bool(ok)


class _FakeExit(BaseException):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default=r"D:\codex-work\gtree-rollout-test\rl")
    ap.add_argument("--base-cell", help="port cell to build the bundle on (default: the coach arms' cell); e.g. "
                    "the harness part of a scored build + the coach hooks (local_env.harness_cell)")
    a = ap.parse_args()
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    pol_path = work / "policy" / "current.json"
    pol_path.parent.mkdir(parents=True, exist_ok=True)

    def write_policy(version, seq, dist):
        pol_path.write_text(json.dumps({"version": version, "seq": seq, "table": {}, "default": dist}) + " " * seq,
                            encoding="utf-8")

    write_policy("v1", 1, {"stock": 0.5, "probe": 0.5})
    stub = le.StubModel(STUB_CODE)
    os.environ.update(le.notebook_env(stub.url))
    os.environ.update({"ARC3_ROLLOUT": "server", "ARC3_COACH": "policy", "ARC3_COACH_POLICY": "@" + str(pol_path),
                       "ARC3_COACH_LOG": str(work / "coach-decisions.jsonl"), "ARC3_MAX_ACTIVE_STREAMS": "0"})
    (work / "coach-decisions.jsonl").unlink(missing_ok=True)
    bundle = le.prepare_bundle(work / "bundle", **({"base_cell": Path(a.base_cell)} if a.base_cell else {}))
    le.put_on_path(bundle)
    le.windows()
    import rollout_core as core
    import rollout_driver as rd
    from inference.agent import tool_agent as ta
    from inference.utils import arc3_coach as coach
    check(hasattr(coach.Coach, "assign_next") and hasattr(coach.Coach, "pin_policy"),
          "the bundle's coach is the RL coach (assign_next, pin_policy, @file reload)")
    solver = le.solver_template(bundle)
    spec = le.arcade_spec()
    out = work / "tries"
    seq = core.fr.load_sequence(SRC_REQ)
    first_of = {}
    for i, r in enumerate(seq):
        first_of.setdefault(r["step"], i)
    logged = seq[first_of[ORIGIN_TURN]]["messages"]
    want_digest = core.digest(ta._strip_control_keys(copy.deepcopy(logged)))
    lines = {m: coach.MODES[m].line.strip() for m in coach.MODES}

    def job(job_id, modes):
        n = len(modes)
        return {"job_id": job_id, "campaign": "localtest", "round": 1, "game_id": GAME_ID, "pass": 0,
                "mode": "replay_exact",
                "source": {"run": "fork-dev", "rollout_id": "fork-dev:dc22_p0", "requests": str(SRC_REQ)},
                "origin": {"turn": ORIGIN_TURN,
                           "screen_hash": core.logged_screen_hash(logged, rd.PALETTE)},
                "tries": n, "assignments": [
                    {"k": k, "mode": m, "anchor": k == 0, "cap": None,
                     "design_prob": Counter(modes)[m] / n, "cap_design_prob": 1.0, "policy_prob": None}
                    for k, m in enumerate(modes)],
                "stop": {"turn_cap": 2, "move_budget": 30, "stop_on_game_over": False},
                "coach": {"spec": "policy", "cap": None}}

    def first_lives(bodies):
        return [b for b in bodies if core.digest(b["messages"]) == want_digest]

    # ---- A. K=5 siblings, K-replay fallback -------------------------------------------------------------------------
    n0 = len(stub.requests)
    lanes = rd.Lanes(5)
    res = rd.run_node(job("sib-k5", MODES5), solver, spec, out, lanes=lanes, fork=False, allow_fenced=True)
    check(len(res) == 5 and all(r["status"] == "done" for r in res), "A: 5 sibling tries done (K-replay fallback)",
          str([(r["try"], r["status"], r["stop_reason"]) for r in res]))
    check(lanes.free == 5, "A: every lane given back", f"free {lanes.free}")
    os_ = [r["origin"] for r in res]
    check(len({(o["screen_hash"], o["level"], o["actions_before"], o["context_digest"]) for o in os_}) == 1
          and os_[0]["context_digest"] == want_digest,
          "A: all 5 start from the identical restored state (board, level, moves, context digest)",
          str({(o["screen_hash"], o["level"], o["actions_before"], o["context_digest"][:12]) for o in os_}))
    fl = first_lives(stub.requests[n0:])
    tails = Counter(core.split_tail(b["messages"])[1].strip() for b in fl)
    check(len(fl) == 5 and tails == Counter(lines[m] for m in MODES5),
          "A: the 5 first live requests carry exactly the assigned modes' focus lines (stock: none)",
          f"{len(fl)} first requests; tails {[t[:30] for t in tails]}")
    check(all(core.split_tail(b["messages"])[0] == core.split_tail(fl[0]["messages"])[0] for b in fl),
          "A: apart from the focus line the 5 first requests are byte-identical")
    check(all((r.get("first_live") or {}).get("tail", "") == lines[MODES5[r["try"]]][:80] for r in res),
          "A: each try's own first request carries its own assignment",
          str([((r.get("first_live") or {}).get("tail") or "")[:25] for r in res]))
    recs = []
    for r in res:
        p = out / "sib-k5" / f"k{r['try']}" / "master.jsonl.gz"
        recs.append(core_read(p) if p.exists() else None)
    ok = all(recs)
    det = []
    for k, rec in enumerate(recs):
        if not rec:
            continue
        ro, st = rec["rollout"], rec["steps"][0]
        d = st["detail"]
        det.append((k, st["action"], d.get("assigned"), d.get("design_prob"), d.get("policy"),
                    ro["result"].get("policy_version")))
        ok &= (st["action"] == MODES5[k] and d.get("assigned") is True and d.get("design_prob") == 0.2
               and d.get("policy") == "v1" and ro["result"]["assignment"]["mode"] == MODES5[k]
               and ro["result"]["policy_version"] == "v1" and ro["policy"] == "policy@v1"
               and d.get("policy_dist") == {"stock": 0.5, "probe": 0.5} and ro["origin_state"] == st["n1"])
    check(ok, "A: master records carry the assignment, design probability 0.2, policy version and distribution",
          str(det))
    later = [s for rec in recs if rec for s in rec["steps"][1:]]
    check(all(s["detail"].get("policy") == "v1" and not s["detail"].get("assigned") for s in later),
          "A: steps after the branch are the policy's own (sampled, not assigned)",
          str([(s["action"], s["detail"].get("prob")) for s in later][:6]))
    check(all(r.get("restore_s") is not None and (r.get("first_live") or {}).get("prompt_tokens") for r in res),
          "A: restore seconds and first-request prompt tokens logged per try",
          str([(r.get("restore_s"), (r.get("first_live") or {}).get("prompt_tokens"),
                (r.get("first_live") or {}).get("cached_tokens")) for r in res]))

    # ---- B. policy reload between tries -----------------------------------------------------------------------------
    write_policy("v2", 2, {"stock": 0.1, "probe": 0.9})
    rb = rd.run_try(job("reload-v2", ["stock", "probe"]), 1, solver, spec, out, allow_fenced=True)
    write_policy("v0", 0, {"stock": 1.0})          # lower seq: refused
    rc_ = rd.run_try(job("reload-stale", ["stock", "probe"]), 1, solver, spec, out, allow_fenced=True)
    check(rb.get("policy_version") == "v2" and rc_.get("policy_version") == "v2",
          "B: the next try picks up the new policy file (v1 -> v2); a lower-seq file is refused (stays v2)",
          f"{rb.get('policy_version')} {rc_.get('policy_version')}")
    rows = [json.loads(x) for x in (work / "coach-decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    by_job = Counter((r.get("assign_job"), r.get("policy")) for r in rows if r.get("assigned"))
    check(by_job[("sib-k5", "v1")] == 5 and by_job[("reload-v2", "v2")] == 1,
          "B: the coach log names the policy version each assigned decision used", str(dict(by_job)))

    # ---- C. fork path, fake fork ------------------------------------------------------------------------------------
    write_policy("v3", 3, {"stock": 0.5, "probe": 0.5})
    pids = iter(range(9001, 9100))
    K = 5

    def fake_fork():
        n = next(pids)
        return 0 if n == 9001 + K - 1 else n             # k0..k3 "forked", the thread becomes k4

    def fake_exit(code):
        raise _FakeExit(code)

    n0 = len(stub.requests)
    lanes = rd.Lanes(5)
    t_start = time.time()
    code = None
    try:
        rd.run_node(job("fork-k5", MODES5), solver, spec, out, lanes=lanes, fork=True, allow_fenced=True,
                    group_kw={"forker": fake_fork, "exit_fn": fake_exit, "real_fork": False, "warm": True})
    except _FakeExit as e:
        code = e.code
    check(code == 0, "C: the sibling ran to the end and exited with 0 (fake exit)", f"exit {code}")
    k4 = out / "fork-k5" / "k4"
    r4 = json.loads((k4 / "result.json").read_text(encoding="utf-8")) if (k4 / "result.json").exists() else {}
    fk = r4.get("fork") or {}
    check(r4.get("status") == "done" and r4.get("role") == "child" and (r4.get("assignment") or {}).get("mode")
          == "rethink" and r4.get("policy_version") == "v3",
          "C: the child is sibling k4 with its own assignment (rethink) and the policy pinned at the fork (v3)",
          f"{r4.get('status')} {r4.get('role')} {(r4.get('assignment') or {}).get('mode')} {r4.get('policy_version')}")
    check(fk.get("relocated", 0) > 0 and fk.get("leftover_refs") == [],
          "C: relocation moved every session / agent / solver / coach path to k4/ (none left under restore/)",
          f"relocated {fk.get('relocated')} leftover {fk.get('leftover_refs')}")
    restore = out / "fork-k5" / "restore"
    late = [str(p.relative_to(restore)) for p in restore.rglob("*") if p.is_file()
            and p.stat().st_mtime > fk.get("forked_at", 0)]
    check(not late, "C: nothing under restore/ was written after the fork", str(late[:5]))
    new = stub.requests[n0:]
    warm = [b for b in new if b.get("max_tokens") == 1]
    live = [b for b in first_lives(new) if b.get("max_tokens") != 1]
    check(len(warm) == 1 and len(live) == 1 and
          ta._strip_control_keys(core.split_tail(live[0]["messages"])[0]) == warm[0]["messages"]
          and core.split_tail(live[0]["messages"])[1].strip() == lines["rethink"],
          "C: one warm-up request (max_tokens 1) = the sibling's first live request minus its focus line",
          f"warm {len(warm)} live {len(live)}; warm usage {json.dumps((fk.get('warm') or {}))[:160]}")
    req_lines = (k4 / "requests.jsonl").read_text(encoding="utf-8").count('"event": "request"') + \
        (k4 / "requests.jsonl").read_text(encoding="utf-8").count('"event":"request"')
    rst_lines = (restore / "requests.jsonl").read_text(encoding="utf-8").count('"event": "request"') + \
        (restore / "requests.jsonl").read_text(encoding="utf-8").count('"event":"request"')
    check(req_lines > rst_lines >= first_of[ORIGIN_TURN],
          "C: the child's request log = the restored prefix + its own live requests", f"{rst_lines} -> {req_lines}")
    rec = core_read(k4 / "master.jsonl.gz") if (k4 / "master.jsonl.gz").exists() else None
    check(bool(rec) and rec["steps"][0]["action"] == "rethink" and rec["steps"][0]["detail"].get("assigned")
          and (r4.get("records") or {}).get("t1_match") is True and rec["rollout"]["result"]["fork"]["siblings"] == 5,
          "C: the child's master record: origin step = its assigned mode, t1 = the source's, fork info kept",
          json.dumps(r4.get("records"))[:200])
    check(lanes.free == 0, "C: the node took its 5 lanes at the origin (the fake child never gives them back)",
          f"free {lanes.free}")

    # ---- D. the parent's wait ------------------------------------------------------------------------------------
    calls = Counter()

    def fake_wait(pid, flags):
        calls[pid] += 1
        if pid == 101 and calls[pid] >= 1:
            return pid, 0
        if pid == 102 and calls[pid] >= 1:
            return pid, 256                             # exit code 1
        return 0, 0

    killed = []
    g = rd.Group({"job_id": "w"}, [0, 1, 2], out, rd.Lanes(3), deadline=time.time() - 10, grace_s=1.5,
                 waitpid=fake_wait, kill=lambda pid: killed.append(pid), real_fork=False)
    g.children = {0: 101, 1: 102, 2: 103}
    state = {"killed": False}

    def wait_103(pid, flags):
        if pid == 103:
            return (pid, 9) if killed else (0, 0)
        return fake_wait(pid, flags)
    g.waitpid = wait_103
    ctl = rd.TryController({"job_id": "w", "mode": "replay_actions", "stop": {}, "coach": {"spec": "off"},
                            "origin": {"turn": 1}}, None, plan=None, facts={"turn": 1})
    ctl.group = g
    ctl.wait_children()
    ec = g.exit_codes
    check(ec.get(0) == 0 and killed == [103] and 2 in ec and (ec.get(1) in (1, 256)),
          "D: the parent collects every child's exit code and kills the one still running past deadline + grace",
          f"exit codes {ec} killed {killed}")
    _ = state

    # ---- G. lanes come back per sibling (4-Oct: holding all K until the slowest ended idled ~36% of lane time) -----
    src_dir = work / "lanes-src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "x.txt").write_text("x", encoding="utf-8")

    def lanes_case(n_lanes, ks, polls_to_exit, deadline_s, grace_s=60.0):
        gl = rd.Lanes(n_lanes)
        pidc = iter(range(7001, 7100))
        log_ = {"forks": [], "exited": 0, "killed": []}
        polls: Counter = Counter()

        def g_fork():
            pid = next(pidc)
            log_["forks"].append((pid, gl.free, log_["exited"]))     # lanes free after this sibling's, exits so far
            return pid

        def g_wait(pid, flags):
            polls[pid] += 1
            if pid in log_["killed"] or (polls_to_exit is not None and polls[pid] >= polls_to_exit):
                log_["exited"] += 1
                return pid, 0
            return 0, 0

        gg = rd.Group({"job_id": "lanes"}, list(ks), out, gl, deadline=time.time() + deadline_s, grace_s=grace_s,
                      forker=g_fork, waitpid=g_wait, kill=lambda pid: log_["killed"].append(pid), real_fork=False,
                      warm=False)
        c2 = rd.TryController({"job_id": "lanes", "mode": "replay_actions", "stop": {}, "coach": {"spec": "off"},
                               "origin": {"turn": 1}}, None, plan=None, facts={"turn": 1})
        c2.group, c2.try_dir = gg, src_dir
        c2.fork_siblings()
        return gl, gg, c2, log_

    gl, gg, c2, lg = lanes_case(2, [0, 1, 2], polls_to_exit=2, deadline_s=60)
    check(len(lg["forks"]) == 3 and lg["forks"][2][2] >= 1 and gl.free == 2 and c2.lanes_held == 0
          and sorted(gg.exit_codes) == [0, 1, 2] and gg.unforked == [] and not c2.aborted
          and all((gg.child_dir(k) / "x.txt").exists() for k in (0, 1, 2)),
          "G: 3 siblings on 2 lanes: the third forks once a sibling exits and gives its lane back; all lanes returned",
          f"forks (pid, free, exits) {lg['forks']} free {gl.free} held {c2.lanes_held} exits {gg.exit_codes}")
    gl, gg, c2, lg = lanes_case(1, [0, 1, 2], polls_to_exit=None, deadline_s=1.0, grace_s=0.5)
    check(len(lg["forks"]) == 1 and gg.unforked == [1, 2] and "not started" in str(c2.aborted)
          and lg["killed"] == [7001] and gl.free == 1 and c2.lanes_held == 0,
          "G: deadline before a lane: unstarted siblings are listed, the running one is killed, its lane returned",
          f"forks {lg['forks']} unforked {gg.unforked} aborted {c2.aborted} killed {lg['killed']} free {gl.free}")

    # ---- E. a root whose source play began with the warmup RESET (3-Oct pilot: every ar25 root try diverged) -------
    # Fixture: the first request/response and the first events of daniel-hicache-sbt06-b-1003's ar25 play, whose
    # first action is the notebook's warmup RESET (turn 0, automatic); the tree's step 1 swallows it.
    import gzip
    fx = work / "ar25-fixture"
    fx.mkdir(parents=True, exist_ok=True)
    for name in ("ar25_b1003_root_requests.jsonl", "ar25_b1003_root_events.jsonl"):
        (fx / name).write_bytes(gzip.decompress((HERE / "testdata" / (name + ".gz")).read_bytes()))
    ar_seq = core.fr.load_sequence(fx / "ar25_b1003_root_requests.jsonl")
    ar_logged = ar_seq[0]["messages"]

    def ar25_job(job_id, mode="replay_exact", **src):
        return {"job_id": job_id, "campaign": "localtest", "round": 1, "game_id": "ar25-0c556536", "pass": 0,
                "mode": mode, "source": {"run": "daniel-hicache-sbt06-b-1003",
                                         "rollout_id": "daniel-hicache-sbt06-b-1003:ar25_p0", **src},
                "origin": {"seq": 1, "turn": 1, "t1": "ar25:t1:root", "screen_hash": "45e68446d37f", "level": 1,
                           "actions_before": 0, "moves": 0},
                "tries": 1, "assignments": [{"k": 0, "mode": "stock", "anchor": True, "cap": None, "design_prob": 1.0,
                                             "cap_design_prob": 1.0, "policy_prob": None}],
                "stop": {"turn_cap": 1, "move_budget": 30, "stop_on_game_over": False}, "coach": {"spec": "off"}}
    logs = {"requests": str(fx / "ar25_b1003_root_requests.jsonl"), "events": str(fx / "ar25_b1003_root_events.jsonl")}
    check(core.lead_resets_from_requests(ar_seq) == 1 and
          core.origin_facts(core.normalize_job(ar25_job("x", **logs)),
                            core.read_lines(logs["events"]))["lead_resets"] == 0,
          "E: fixture = the pilot's case: the request log shows the warmup RESET, the root's event prefix does not")
    re_ = rd.run_try(ar25_job("ar25-root", **logs), 0, solver, spec, out)
    o = re_.get("origin") or {}
    check(re_["status"] == "done" and o.get("request_verdict") in core.SAME and o.get("actions_before") == 1
          and o.get("lead_in_origin") == 1 and o.get("mismatch") == {},
          "E: the warmup RESET is replayed: the root's first request = the logged one, 1 action at the origin",
          f"{re_['status']} verdict {o.get('request_verdict')} actions {o.get('actions_before')} "
          f"{json.dumps(re_.get('diverged'))[:300]}")
    check((re_.get("records") or {}).get("t1_match") is True and (re_.get("records") or {}).get("steps") == 1,
          "E: its records start at the root (the origin step is found despite the RESET inside it)",
          json.dumps(re_.get("records"))[:200])
    real_lead = core.lead_resets_from_requests
    core.lead_resets_from_requests = lambda seq_: 0          # the pilot's code path: no lead RESET seen
    try:
        old = rd.run_try(ar25_job("ar25-root-old", **logs), 0, solver, spec, out)
    finally:
        core.lead_resets_from_requests = real_lead
    check(old["status"] == "diverged" and (old.get("diverged") or {}).get("kind") == "origin_messages"
          and "No previous action sequence was captured" in json.dumps(old.get("diverged")),
          "E: without the lead RESET the pilot's divergence reproduces (origin_messages, 'step 2' vs 'step 1')",
          json.dumps(old.get("diverged"))[:300])
    snaps = sorted((out / "ar25-root" / "k0" / "state").glob("*.pkl.gz"))
    om = fx / "origin_messages.json"
    om.write_text(json.dumps(ar_logged), encoding="utf-8")
    rs = rd.run_try(ar25_job("ar25-root-snap", "snapshot", state=str(snaps[0]) if snaps else "missing",
                             origin_messages=str(om)), 0, solver, spec, out) if snaps else {"status": "no snapshot"}
    so = rs.get("origin") or {}
    check(rs.get("status") == "done" and so.get("request_verdict") in core.SAME and so.get("actions_before") == 1
          and so.get("lead_in_origin") == 1,
          "E: the root's origin snapshot (taken after the RESET) restores and matches the logged request too",
          f"{rs.get('status')} {so.get('request_verdict')} {json.dumps(rs.get('aborted') or rs.get('diverged'))[:300]}")

    # ---- F. the server's queue: kept rounds played oldest first, older rounds dropped, failures reported ----------
    jobs_dir = work / "serve-jobs"
    import shutil
    shutil.rmtree(jobs_dir, ignore_errors=True)
    files = {1: ["a", "b"], 2: ["c", "d-ar25"], 3: ["e", "f"]}
    for rnd, ids in files.items():
        for pri, jid in enumerate(ids):
            p = jobs_dir / f"round-{rnd:04d}" / f"{rnd:04d}-{pri:05d}-{jid}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"job_id": jid, "game_id": "sb26-x", "round": rnd, "tries": 1,
                                     "origin": {"t1": f"sb26:t1:{jid}", "seq": 3},
                                     "source": {"rollout_id": f"src:{jid}"}}), encoding="utf-8")
    played: list[str] = []
    real_run_node = rd.run_node

    def fake_run_node(job_, *a, **kw):
        played.append(job_["job_id"])
        if job_["job_id"] == "d-ar25":
            return [{"job": job_["job_id"], "try": 0, "status": "diverged", "stop_reason": "diverged",
                     "diverged": {"kind": "origin_messages", "call": 0, "first": {"sent": "x" * 2000}}}]
        return [{"job": job_["job_id"], "try": 0, "status": "done", "stop_reason": "cleared", "cleared": True}]
    rd.run_node = fake_run_node
    try:
        summ = rd.serve(jobs_dir, solver, spec, work / "serve-out", lanes=5, restorers=1, poll_s=0.1, once=True,
                        keep_rounds=2, fork=False)
    finally:
        rd.run_node = real_run_node
    check(played == ["c", "d-ar25", "e", "f"] and sorted(summ["skipped_old_round"]) == ["0001-00000-a.json",
                                                                                         "0001-00001-b.json"],
          "F: the newest two rounds are played oldest first (round 2's unstarted jobs are NOT dropped for round 3); "
          "round 1 is dropped", f"played {played} skipped {summ['skipped_old_round']}")
    rows = {r["job"]: r for r in summ["results"]}
    dv = rows.get("d-ar25") or {}
    check(dv.get("node") == "sb26:t1:d-ar25" and dv.get("source") == "src:d-ar25" and dv.get("seq") == 3
          and (dv.get("diverged") or {}).get("kind") == "origin_messages"
          and len(json.dumps(dv["diverged"])) < 1000 and "diverged" not in rows["c"]
          and summ["running"] == {"nodes": 0, "tries": 0, "jobs": []},
          "F: summary rows name the restart point; a diverged try carries its (cut) diff; running jobs listed",
          json.dumps(dv)[:300])
    return finish(stub, work)


def core_read(path: Path) -> dict:
    import gzip
    rec = {"rollout": None, "steps": []}
    for line in gzip.decompress(path.read_bytes()).decode("utf-8").splitlines():
        d = json.loads(line)
        if d["kind"] == "rollout":
            rec["rollout"] = d
        elif d["kind"] == "step":
            rec["steps"].append(d)
    return rec


def finish(stub, work: Path) -> int:
    stub.close()
    bad = [n for ok, n, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed" + (f"; FAILED: {bad}" if bad else ""))
    (work / "test_results.json").write_text(json.dumps([{"ok": o, "name": n, "detail": d} for o, n, d in RESULTS],
                                                       indent=1), encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

"""Tests for the Training-view status document (rl_loop.status_doc / vm_rows / publish-status --dry-run).

Author: Claude Opus 5.5 (3-Oct-2026). Synthetic inputs only: a local store, no GCS, no gcloud, no site.

  C:/Python312/python.exe -m unittest test_rl_status
"""
from __future__ import annotations

import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rl_common as rc  # noqa: E402
import rl_loop  # noqa: E402

C = "syn"
MOVES = {"stock": 16, "probe": 20, "execute": 8, "brief": 18, "rethink": None}
NODES = [("sb26:t1:synA", 1, 0, 0), ("sb26:t1:synB", 2, 14, 20)]


def try_records(n: int, node, mode: str, rnd: int, stop: str | None = None, restore: str = "replay_exact"):
    n1, level, moves, ail = node
    mtc = MOVES[mode]
    job = f"{C}-r{rnd:03d}-sb26-{n1[-4:]}"
    rid = f"gtr-{C}:sb26_p0.{job}.k{n % 5}"
    rollout = {"kind": "rollout", "id": rid, "game": "sb26", "run": f"gtr-{C}", "build": "gtree-rollout",
               "origin_kind": restore, "origin_state": n1,
               "result": {"game_id": "sb26-7fbdac44", "pass": 0, "cleared": mtc is not None, "moves_to_clear": mtc,
                          "stop_reason": stop or ("cleared" if mtc is not None else "move_budget"), "job": job,
                          "try": n % 5, "round": rnd, "turns": 6, "tokens": 9000, "policy_version": f"{C}-v{rnd - 1}",
                          "assignment": {"mode": mode}, "origin_actions_before": 0}}
    step = {"kind": "step", "id": f"{rid}:1", "rollout_id": rid, "seq": 1, "game": "sb26", "level": level,
            "moves": moves, "screen_hash": "x", "action": mode,
            "detail": {"source": "coach", "assigned": True, "turn": 5, "part": 1},
            "features": {"level": level, "actions_in_level": ail, "actions_total": ail + 10 * level},
            "outcome": {"moves_to_clear": mtc, "cleared_level": int(mtc is not None), "level_weight": level},
            "n1": n1, "n5": n1.replace(":t1:", ":t5:"), "moves_step": 1, "resumable": False, "ctx_before": None}
    return rollout, step, job


def play_of(rollout, step):
    return {"rollout": {k: v for k, v in rollout.items() if k != "kind"},
            "steps": [{k: v for k, v in step.items() if k != "kind"}]}


def synthetic():
    """Round 1: both nodes x 5 modes; round 2: node A again with one censored (deadline) try."""
    plays, jobs, n = [], {}, 0
    for rnd, nodes in ((1, NODES), (2, NODES[:1])):
        for node in nodes:
            for mode in MOVES:
                r, s, job = try_records(n, node, mode, rnd)
                plays.append(play_of(r, s))
                jobs[job] = {"job_id": job, "round": rnd, "class": "level_start" if rnd == 1 else "uncertain",
                             "mode": "replay_exact", "tries": 5, "priority": n // 5}
                n += 1
    r, s, _ = try_records(n, NODES[0], "brief", 2, stop="deadline")
    plays.append(play_of(r, s))
    return plays, jobs


POLICY = {"version": f"{C}-v1", "seq": 1, "kind": "table", "default": {"stock": 0.5, "execute": 0.5},
          "table": {"stuck|L2+": {"rethink": 1.0}}, "stats": {"ess": 7.5}}
STATE = {"version": 1, "round": 3, "created": 1000.0,
         "history": [{"t": 2000.0, "version": f"{C}-v1", "round": 2, "train": 10, "tries": 10, "trained": True},
                     {"t": 3000.0, "version": f"{C}-v1", "round": 3, "train": 15, "tries": 16, "trained": False,
                      "nodes_with_siblings": 2, "ess": None, "jobs": 1, "job_tries": 5}]}


class StatusDoc(unittest.TestCase):
    def setUp(self):
        self.plays, self.jobs = synthetic()
        self.doc = rl_loop.status_doc(C, plays=self.plays, state=STATE, policy=POLICY,
                                      policies={f"{C}-v1": POLICY}, jobs=self.jobs, job_counts={1: 2, 2: 1, 3: 1},
                                      vms=[{"name": "arc3-rl-a"}], human={}, now=0)

    def test_shape(self):
        d = self.doc
        for k in ("campaign", "generated_at", "harness", "vms", "rounds", "policy", "nodes", "totals",
                  "advantage_by_action"):
            self.assertIn(k, d)
        self.assertEqual(d["campaign"], C)
        self.assertEqual(d["generated_at"], "1970-01-01T00:00:00Z")
        json.dumps(d)                                             # serialisable

    def test_rounds(self):
        rows = {r["round"]: r for r in self.doc["rounds"]}
        self.assertEqual(sorted(rows), [1, 2, 3])
        self.assertEqual(rows[1]["version"], f"{C}-v0")
        self.assertEqual(rows[2]["ess"], 7.5, "ESS of an old round comes from the archived policy")
        self.assertEqual((rows[1]["jobs"], rows[1]["tries"]), (2, 10))
        self.assertEqual((rows[2]["jobs"], rows[2]["tries"]), (1, 6), "round 2: 5 tries + 1 censored")
        self.assertEqual(rows[3]["nodes_with_siblings"], 2)

    def test_nodes_newest_first_with_best_and_stock(self):
        nodes = self.doc["nodes"]
        self.assertEqual([n["node"] for n in nodes], ["sb26:t1:synA", "sb26:t1:synB"])
        a = nodes[0]
        self.assertEqual(len(a["tries"]), 11)
        self.assertEqual((a["best_moves"], a["stock_moves"], a["class"], a["level"]), (8, 16, "uncertain", 1))
        self.assertTrue(any(t.get("censored") for t in a["tries"]))
        t = a["tries"][0]
        for k in ("action", "cleared", "moves_to_clear", "turns", "tokens", "policy_version"):
            self.assertIn(k, t)

    def test_totals_skip_censored(self):
        tot = self.doc["totals"]
        self.assertEqual((tot["tries"], tot["censored"]), (15, 1))
        self.assertEqual(tot["cleared"], 12)
        ex = tot["by_first_action"]["execute"]
        self.assertEqual((ex["n"], ex["clear_rate"], ex["mean_moves"]), (3, 1.0, 8.0))
        self.assertEqual(tot["by_first_action"]["rethink"]["clear_rate"], 0.0)

    def test_advantage_ranks_fast_first_actions_up(self):
        adv = self.doc["advantage_by_action"]
        self.assertGreater(adv["execute"]["mean_adv"], 0)
        self.assertLess(adv["rethink"]["mean_adv"], 0)
        self.assertGreater(adv["execute"]["mean_adv"], adv["stock"]["mean_adv"])

    def test_policy_points(self):
        pts = {p["label"]: p["dist"] for p in self.doc["policy"]["mode_dist_at"]}
        self.assertEqual(len(pts), 5)
        self.assertEqual(pts["level start, level 1"], {"stock": 0.5, "execute": 0.5})
        self.assertEqual(pts["stuck"], {"rethink": 1.0})

    def test_empty_campaign(self):
        d = rl_loop.status_doc(C, plays=[], state={}, policy={}, now=0)
        self.assertEqual((d["nodes"], d["rounds"], d["totals"]["tries"], d["advantage_by_action"]), ([], [], 0, {}))
        self.assertEqual(d["policy"]["mode_dist_at"][0]["dist"], {})

    def test_nodes_cap(self):
        d = rl_loop.status_doc(C, plays=self.plays, state=STATE, policy=POLICY, human={}, nodes_cap=1, now=0)
        self.assertEqual((len(d["nodes"]), d["nodes_total"]), (1, 2))


class QueueAndBlocks(unittest.TestCase):
    """3-Oct pilot fixes: the learner refills only when the queue runs low; restore failures block restart points."""
    NAMES = [f"jobs/round-{r:04d}/{r:04d}-{p:05d}-{C}-r{r:03d}-g{p}-n{p}.json" for r in (1, 2, 3) for p in range(3)]

    def test_queue_state(self):
        summ = {"arc3-rl-a": {"updated_at": 1000.0, "results": [{"job": f"{C}-r002-g0-n0"}],
                              "running": {"jobs": [f"{C}-r003-g0-n0"]},
                              "skipped_old_round": [f"0002-00002-{C}-r002-g2-n2.json"]},
                "arc3-rl-b": {"updated_at": 1000.0, "ended_at": 1000.0, "results": []}}
        q = rl_loop.queue_state(self.NAMES, summ, keep_rounds=2, now=1100.0)
        self.assertEqual(q["rounds"], [2, 3], "the servers keep the newest two rounds")
        self.assertEqual(q["pending"], [f"{C}-r002-g1-n1", f"{C}-r003-g1-n1", f"{C}-r003-g2-n2"])
        self.assertEqual((q["done"], q["running"], q["vms_active"]), (1, 1, 1), "an ended VM is not active")
        self.assertEqual(rl_loop.job_id_of(self.NAMES[0]), f"{C}-r001-g0-n0")

    def test_blocked_points(self):
        jobs = {"j1": {"source": "runB:ar25_p0", "seq": 1, "t1": "ar25:t1:root", "game": "ar25"},
                "j2": {"source": "runC:ar25_p0", "seq": 1, "t1": "ar25:t1:root", "game": "ar25"},
                "j3": {"source": "runB:bp35_p0", "seq": 1, "t1": "bp35:t1:root", "game": "bp35"}}
        summ = {"arc3-rl-a": {"results": [
            {"job": "j1", "try": 0, "status": "diverged", "diverged": {"kind": "origin_messages", "call": 0}},
            {"job": "j1", "try": 1, "status": "diverged"},
            {"job": "j3", "try": 0, "status": "aborted", "stop": "deadline before lanes were free"},
            {"job": "j3", "try": 1, "status": "done", "stop": "cleared"}]}}
        b, nodes, new = rl_loop.blocked_points(summ, jobs, None, now=5.0)
        self.assertEqual(sorted(b), ["runB:ar25_p0#1"], "only the restore failure blocks; a deadline abort does not")
        self.assertEqual((b["runB:ar25_p0#1"]["tries"], b["runB:ar25_p0#1"]["detail"]["diverged"]["kind"]),
                         (2, "origin_messages"))
        self.assertEqual((nodes, new), ({}, ["runB:ar25_p0#1"]))
        summ["arc3-rl-b"] = {"results": [{"job": "j2", "try": 0, "status": "aborted",
                                          "aborted": "origin_mismatch {'screen_hash': ...}"}]}
        b2, nodes2, new2 = rl_loop.blocked_points(summ, jobs, b, now=9.0)
        self.assertEqual(sorted(b2), ["runB:ar25_p0#1", "runC:ar25_p0#1"])
        self.assertEqual(b2["runB:ar25_p0#1"]["since"], 5.0, "kept from the previous round")
        self.assertIn("ar25:t1:root", nodes2, "restore failed from 2 source plays: the node is blocked")
        self.assertEqual(new2, ["runC:ar25_p0#1"])
        b3, _, _ = rl_loop.blocked_points(summ, jobs, None, min_tries=3)
        self.assertEqual(b3, {}, "min_tries")

    def test_status_doc_params_and_blocked(self):
        st = dict(STATE, blocked={"runB:ar25_p0#1": {"t1": "ar25:t1:root", "game": "ar25", "why": "diverged",
                                                     "tries": 40, "jobs": ["j1"], "detail": None, "since": 0.0}},
                  queue={"pending": 3})
        plays, _ = synthetic()
        d = rl_loop.status_doc(C, plays=plays, state=st, policy=POLICY, human={}, now=0, token_alpha=0.5,
                               params={"token_cap": 200000})
        self.assertEqual(d["params"], {"token_alpha": 0.5, "token_cap": 200000})
        self.assertEqual((d["blocked"][0]["restart_point"], d["blocked"][0]["tries"], d["queue"]),
                         ("runB:ar25_p0#1", 40, {"pending": 3}))
        json.dumps(d)


class VmRows(unittest.TestCase):
    INST = [{"name": "arc3-rl-a", "status": "RUNNING", "metadata": {"items": [
                {"key": "arc3-campaign", "value": C}, {"key": "arc3-run-id", "value": f"rl-{C}-a"}]}},
            {"name": "arc3-rl-z", "status": "RUNNING", "metadata": {"items": [{"key": "arc3-campaign", "value": "other"}]}}]
    PHASES = {f"rl-{C}-a": "2026-10-03T17:00:00Z\tstart\n2026-10-03T17:50:47Z\tserver_ready attempt_1\n",
              f"rl-{C}-b": "2026-10-03T16:00:00Z\tfinish (notebook_rc_0)\n"}
    SUMMARY = {"arc3-rl-a": {"tries": 7, "nodes": 2, "cleared": 3, "errors": [], "updated_at": 0,
                             "running": {"nodes": 1, "tries": 5},
                             "results": [{"job": "j1", "restore_s": 4.0, "first_cached": 90000, "first_prompt": 100000},
                                         {"job": "j1", "restore_s": 4.0, "first_cached": 92000, "first_prompt": 100000},
                                         {"job": "j2", "restore_s": 120.0, "first_cached": None}]}}

    def test_rows(self):
        rows = {r["name"]: r for r in rl_loop.vm_rows(C, self.INST, self.PHASES, self.SUMMARY,
                                                       {"j1": "snapshot", "j2": "replay_exact"})}
        self.assertEqual(sorted(rows), ["arc3-rl-a", "arc3-rl-b"], "other campaigns' VMs left out")
        a = rows["arc3-rl-a"]
        self.assertEqual((a["status"], a["last_phase"], a["phase_time"]),
                         ("RUNNING", "server_ready attempt_1", "2026-10-03T17:50:47Z"))
        self.assertEqual((a["tries_done"], a["tries_running"]), (7, 5))
        self.assertEqual(a["restores"], {"replay_exact": 1, "snapshot": 1})
        self.assertEqual(a["mean_restore_s"], 62.0)
        self.assertEqual(a["cached_tokens_first_request"], 91000.0)
        b = rows["arc3-rl-b"]
        self.assertEqual((b["status"], b["last_phase"], b["tries_done"]), ("gone", "finish (notebook_rc_0)", None))

    def test_listing_failed(self):
        rows = rl_loop.vm_rows(C, None, self.PHASES, {}, {})
        self.assertTrue(all(r["status"] == "unknown" for r in rows))


class DryRun(unittest.TestCase):
    def test_publish_status_dry_run_on_a_local_store(self):
        tmp = Path(tempfile.mkdtemp(prefix="rl-status-test-"))
        store = tmp / "store"
        plays, jobs = synthetic()
        for i, p in enumerate(plays):
            f = store / "rollouts" / f"gtr-{C}" / f"sb26_p0.t{i}.jsonl.gz"
            f.parent.mkdir(parents=True, exist_ok=True)
            rows = [{"kind": "rollout", **p["rollout"]}] + [{"kind": "step", **s} for s in p["steps"]]
            f.write_bytes(gzip.compress("\n".join(json.dumps(r) for r in rows).encode()))
        rls = rc.Store(str(store / "rl" / C))
        rc.write_json(rls, "learner/state.json", STATE)
        rc.write_json(rls, "policy/current.json", POLICY)
        rc.write_json(rls, f"policy/{C}-v1.json", POLICY)
        for j in jobs.values():
            rc.write_json(rls, f"jobs/round-{j['round']:04d}/{j['round']:04d}-{j['priority']:05d}-{j['job_id']}.json",
                          {"job_id": j["job_id"], "round": j["round"], "mode": "snapshot", "tries": 5,
                           "priority": j["priority"], "pick": {"class": j["class"]}})
        rls.put(f"runs/rl-{C}-a/phases.tsv", b"2026-10-03T17:00:00Z\tstart\n", once=False)
        rc.write_json(rls, "results/arc3-rl-a/summary.json", {"tries": 3, "results": [{"job": jobs and next(iter(jobs)),
                                                                                       "restore_s": 2.0}]})
        cfg = rl_loop.args(["publish-status", "--campaign", C, "--store", str(store), "--seed-runs", "",
                            "--cache", str(tmp / "cache"), "--dry-run", "--no-vms", "--out", str(tmp / "out")])
        cfg.no_human = True
        msg = rl_loop.publish_status(cfg)
        self.assertIn("dry run", msg)
        doc = json.loads((tmp / "out" / f"rl-campaign-{C}.json").read_text(encoding="utf-8"))
        idx = json.loads((tmp / "out" / "rl-campaigns.json").read_text(encoding="utf-8"))
        self.assertEqual([c["name"] for c in idx["campaigns"]], [C])
        self.assertEqual(doc["totals"]["tries"], 15)
        self.assertEqual(doc["vms"][0]["restores"], {"replay_exact": 0, "snapshot": 1})
        self.assertEqual(doc["vms"][0]["status"], "unknown")
        self.assertEqual(doc["nodes"][0]["class"], "uncertain")
        self.assertIsNone(rc.Store(str(store / "rl")).get("published-campaigns.json"), "a dry run writes nothing")

    def test_bad_campaign_name(self):
        cfg = rl_loop.args(["publish-status", "--campaign", "Bad Name", "--dry-run"])
        with self.assertRaises(SystemExit):
            rl_loop.publish_status(cfg)


if __name__ == "__main__":
    unittest.main()

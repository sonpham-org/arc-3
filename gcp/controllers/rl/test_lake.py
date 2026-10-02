"""Tests for lake.py (trace lake episodes). Run: python test_lake.py

The real-data test round-trips Daniel's 30-Sep re86 request log (local review folder) when present: every request's
message list must come back byte-identical from the episode + blobs, and the episode must be much smaller than the log.
"""
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lake  # noqa: E402
import rl_reward as rr  # noqa: E402

REAL = Path(r"D:\codex-work\arc3-franzen-review-20260930\output")
RE86 = "re86-8af5384d"


def img(n):
    return {"type": "image_url", "image_url": {"url": "data:image/png;base64," + ("QUJD" * 50) + str(n)}}


def req(step, msgs, ri=1):
    return {"event": "request", "analysis_step": step, "request_index_within_turn": ri, "action": step,
            "messages": msgs, "tools": [{"type": "function", "function": {"name": "python"}}],
            "chat_template_kwargs": {"preserve_thinking": True}}


def resp(step, reply=None, ri=1):
    r = {"event": "response", "analysis_step": step, "request_index_within_turn": ri, "finish_reason": "tool_calls",
         "usage": {"prompt_tokens": 100 * step, "completion_tokens": 10}}
    if reply is not None:
        r["response_message"] = reply
    return r


def header(eid="scored_run.r1.g1"):
    return {"episode_id": eid, "source": {"kind": "scored_run", "run_id": "r1"}, "game": {"id": "sp80-589a99af"},
            "harness": {"id": "har-x"}, "policy": {"id": "pol-y"}, "parent": None, "teacher": "none"}


class TestLake(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.blobs = lake.LocalBlobs(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip_with_reset_and_replies(self):
        s = {"role": "system", "content": "S"}
        u1 = {"role": "user", "content": [{"type": "text", "text": "f1"}, img(1)]}
        a1 = {"role": "assistant", "reasoning_content": "r1", "tool_calls": [{"function": {"name": "python", "arguments": "{}"}}]}
        t1 = {"role": "tool", "content": "T1"}
        u2 = {"role": "user", "content": [{"type": "text", "text": "f2"}, img(1)]}      # same image again
        a2 = {"role": "assistant", "reasoning_content": "r2", "tool_calls": []}
        summary = {"role": "user", "content": [{"type": "text", "text": "SUMMARY"}, img(2)]}
        a3 = {"role": "assistant", "reasoning_content": "r3", "tool_calls": []}
        m1 = [s, u1]
        m2 = [s, u1, a1, t1, u2]
        m3 = [s, summary]                                                                   # compaction: reset
        rows = [req(1, m1), resp(1, a1), req(2, m2), resp(2, a2), req(3, m3), resp(3, a3)]
        lines = lake.episode_lines(header(), rows, self.blobs, human=[3, 4])
        calls = [l for l in lines if l["kind"] == "call"]
        self.assertEqual([c["reset"] for c in calls], [True, False, True])
        self.assertEqual([c["reply_in_next"] for c in calls], [True, False, False])
        got = list(lake.call_messages(lines, self.blobs.get))
        for (c, msgs, reply), want_msgs, want_reply in zip(got, [m1, m2, m3], [a1, a2, a3]):
            self.assertEqual(lake._canon(msgs), lake._canon(want_msgs))
            self.assertEqual(lake._canon(reply), lake._canon(want_reply))
        n_blobs = sum(1 for _ in Path(self.tmp.name, "blobs").rglob("*") if _.is_file())
        self.assertEqual(n_blobs, 2)                                                        # img(1) stored once
        p = lake.write_episode(self.tmp.name, lake.episode_uri("scored_run.r1.g1", "scored_run"), lines)
        self.assertEqual(lake.read_episode(p), lines)

    def test_levels_and_docs(self):
        ev = [{"type": "action", "action_num": n, "analysis_step": 1, "action_name": "ACTION1", "board": [[n]],
               "level_completed": n == 4} for n in range(1, 7)]
        lines = lake.episode_lines(header(), [req(1, [{"role": "user", "content": "x"}]), resp(1)], self.blobs,
                                   events=ev, human=[3, 9])
        foot = lines[-1]
        self.assertEqual(foot["levels"][0], {"level": 1, "cleared": True, "actions": 4, "human": 3,
                                             "score": rr.level_score(3, 4)})
        self.assertFalse(foot["levels"][1]["cleared"])
        doc = lake.episode_doc(lines, "episodes/x.jsonl.gz")
        self.assertEqual(doc["levels_cleared"], 1)
        self.assertAlmostEqual(doc["game_score"], rr.game_score(1, [4], [3, 9]))
        # a level never reached still counts in the score's weights (bug caught 1-Oct: re86 showed 71.4, not <=41.7)
        lines3 = lake.episode_lines(header(), [req(1, [{"role": "user", "content": "x"}]), resp(1)], self.blobs,
                                    events=ev, human=[3, 9, 20])
        doc3 = lake.episode_doc(lines3, "episodes/y.jsonl.gz")
        self.assertAlmostEqual(doc3["game_score"], rr.game_score(1, [4], [3, 9, 20]))
        self.assertEqual(doc3["n_levels"], 3)
        lv = lake.level_docs(lines)
        self.assertEqual([d["id"] for d in lv], ["scored_run.r1.g1.L1", "scored_run.r1.g1.L2"])
        self.assertTrue(all("/" not in d["id"] for d in lv))

    def test_ids(self):
        a = {"base": "radixark-nvfp4", "prune": "k336g", "temperature": 0.6}
        self.assertEqual(lake.policy_id(a), lake.policy_id(dict(a)))
        self.assertNotEqual(lake.policy_id(a), lake.policy_id(dict(a, temperature=0.7)))
        self.assertTrue(lake.harness_id({"bundle": "b", "knobs": {"x": 1}}).startswith("har-"))
        self.assertEqual(lake.episode_id("rl_try", "sp80-a1b2.t0012", "pol/x"), "rl_try.sp80-a1b2-t0012.pol_x")
        with self.assertRaises(ValueError):
            lake.episode_id("unknown", "x")

    @unittest.skipUnless((REAL / f"{RE86}_p0_requests.jsonl").exists(), "re86 log not on this box")
    def test_real_log_round_trip(self):
        import seed_moments as sm
        raw = (REAL / f"{RE86}_p0_requests.jsonl").read_bytes()
        rows = [json.loads(l) for l in raw.decode("utf-8").splitlines() if l.strip()]
        events = list(sm.iter_jsonl(REAL / "artifacts" / f"{RE86}_p0_events.jsonl"))
        human = list(sm._observer().BASE_ACTIONS[RE86])
        lines = lake.episode_lines(header(), rows, self.blobs, events=events, human=human)
        reqs = [r for r in rows if r.get("event") == "request"]
        got = list(lake.call_messages(lines, self.blobs.get))
        self.assertEqual(len(got), len(reqs))
        for (c, msgs, _), r in zip(got, reqs):
            self.assertEqual(lake._canon(msgs), lake._canon(r["messages"]))
        p = lake.write_episode(self.tmp.name, "episodes/test/re86.jsonl.gz", lines)
        blob_bytes = sum(f.stat().st_size for f in Path(self.tmp.name, "blobs").rglob("*") if f.is_file())
        stored = p.stat().st_size + blob_bytes
        print(f"\n  re86: log {len(raw)/1e6:.1f} MB -> episode {p.stat().st_size/1e6:.2f} MB + blobs "
              f"{blob_bytes/1e6:.2f} MB ({100*stored/len(raw):.1f}% of the log)")
        self.assertLess(stored, len(raw) / 5)


if __name__ == "__main__":
    unittest.main(verbosity=1)

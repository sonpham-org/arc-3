"""Unit tests for the RL core (rl_reward, rl_tree, seed_moments, build_records). Run: python test_rl_core.py

The real-data tests use Daniel's re86 logs from the 30-Sep review folder when present and are skipped otherwise.
"""
import json
import random
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_records as br  # noqa: E402
import rl_reward as rr  # noqa: E402
import rl_tree as rt  # noqa: E402
import seed_moments as sm  # noqa: E402

REAL = Path(r"D:\codex-work\arc3-franzen-review-20260930\output")
RE86 = "re86-8af5384d"


# ------------------------------------------------------------------------------------------------ reward
class TestReward(unittest.TestCase):
    def test_game_score_matches_observer(self):
        obs = sm._observer()
        rng = random.Random(7)
        for _ in range(300):
            n = rng.randint(1, 10)
            base = [rng.randint(5, 300) for _ in range(n)]
            done = rng.randint(0, n)
            acts = [rng.randint(1, 900) for _ in range(rng.randint(done, n))]
            self.assertAlmostEqual(rr.game_score(done, acts, base), obs.game_score(done, acts, base), places=9)

    def test_try_reward(self):
        self.assertEqual(rr.try_reward(cleared=False, human_actions=20, prefix_level_actions=0, try_actions=5), 0.0)
        self.assertEqual(rr.try_reward(cleared=True, human_actions=20, prefix_level_actions=0, try_actions=5,
                                       over_token_cap=True), 0.0)
        self.assertAlmostEqual(rr.try_reward(cleared=True, human_actions=20, prefix_level_actions=10, try_actions=30),
                               0.25)                                    # (20/40)^2: the prefix counts
        self.assertEqual(rr.try_reward(cleared=True, human_actions=20, prefix_level_actions=0, try_actions=2), 1.15)

    def test_level_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(rr.level_weight(k, 7) for k in range(1, 8)), 1.0)

    def test_advantages(self):
        self.assertEqual(rr.grpo_advantages([0.5, 0.5, 0.5]), [0.0, 0.0, 0.0])
        adv = rr.grpo_advantages([0.0, 1.0, 0.0, 0.5])
        self.assertAlmostEqual(sum(adv), 0.0, places=6)
        self.assertGreater(adv[1], adv[3])
        self.assertGreater(adv[3], adv[0])
        # mutation: flipping the rewards must flip every advantage
        flipped = rr.grpo_advantages([-0.0, -1.0, -0.0, -0.5])
        for a, b in zip(adv, flipped):
            self.assertAlmostEqual(a, -b, places=6)

    def test_expert_pick(self):
        tries = [{"id": "a", "reward": 0.0}, {"id": "b", "reward": 0.6, "tokens": 900},
                 {"id": "c", "reward": 0.6, "tokens": 500}, {"id": "d", "reward": 0.1}]
        pick = rr.expert_pick(tries, k=2)
        self.assertEqual([t["id"] for t in pick], ["c", "b"])           # fewer tokens first on a tie
        self.assertTrue(all(t["reward"] > 0 and t["weight"] > 0 for t in pick))
        self.assertEqual(rr.expert_pick([{"reward": 0.4}, {"reward": 0.4}]), [])    # unmixed: nothing
        self.assertEqual(rr.expert_pick([{"reward": 0.0}, {"reward": 0.0}]), [])
        tries[2]["excluded"] = True                                        # a human flagged it as luck
        self.assertEqual([t["id"] for t in rr.expert_pick(tries, k=2)], ["b"])

    def test_extra_tries(self):
        self.assertEqual(rr.extra_tries([0] * 8, won_before=True), 8)          # all lost on a winnable moment
        self.assertEqual(rr.extra_tries([0.4] * 8, won_before=True), 8)        # all won: break the tie too
        self.assertEqual(rr.extra_tries([0] * 8, won_before=False), 0)         # never won: a dead end, not more dice
        self.assertEqual(rr.extra_tries([0, 0.2] + [0] * 6, won_before=True), 0)   # mixed: enough signal
        self.assertEqual(rr.extra_tries([0] * 16, won_before=True), 0)         # already extended
        self.assertEqual(rr.extra_tries([0] * 4, won_before=True), 0)          # base not played yet

    def test_round_health(self):
        h = rr.round_health([[0, 0, 0, 0], [0, 1, 0, 1]])
        self.assertEqual(h["mixed_share"], 0.5)
        self.assertEqual(h["clear_rate"], 0.25)


# ------------------------------------------------------------------------------------------------ tree
def _moment(store, turn=10, level=3, game="sp80-0605ab9e", source="run-x", before=5, rem=20):
    m = rt.new_moment(source_kind="run", source=source, game_id=game, level=level, turn=turn, action_num=40,
                      level_actions_before=before, human_actions=30, n_levels=6, harness="h", policy="base",
                      ref_remaining_actions=rem, ref_remaining_tokens=20000, ref_cleared=True, campaign="t")
    store.put("rl_moments", m)
    return m


def _play(store, m, outcomes, policy="p0", kind="plain"):
    for i, (cleared, acts) in enumerate(outcomes):
        t = rt.new_try(moment=m, policy=policy, kind=kind, index=i, campaign="t")
        t = rt.finish_try(t, moment=m, cleared=cleared, try_actions=acts, turns=5, tokens=9000,
                          over_token_cap=False, finish="cleared" if cleared else "cap")
        store.put("rl_tries", t)


class TestTree(unittest.TestCase):
    def test_ids(self):
        self.assertEqual(rt.state_key("sp80-x", ["UP", "LEFT"]), rt.state_key("sp80-x", ["UP", "LEFT"]))
        self.assertNotEqual(rt.state_key("sp80-x", ["UP", "LEFT"]), rt.state_key("sp80-x", ["LEFT", "UP"]))
        m = rt.moment_id("run-a", "sp80-x", 7)
        self.assertTrue(m.startswith("sp80-") and m.endswith("t0007"))
        g = rt.group_id(m, "pol", "plain")
        self.assertTrue(rt.try_id(g, 3).endswith(".03"))
        self.assertNotIn("/", rt.try_id(g, 3))

    def test_fence(self):
        store = rt.MemoryStore()
        for g in ("tn36-ab", "su15-cd", "as66-ef"):
            with self.assertRaises(ValueError):
                _moment(store, game=g)

    def test_finish_try_reward(self):
        store = rt.MemoryStore()
        m = _moment(store, before=10)
        t = rt.finish_try(rt.new_try(moment=m, policy="p", kind="plain", index=0), moment=m, cleared=True,
                          try_actions=30, turns=4, tokens=100, over_token_cap=False, finish="cleared")
        self.assertAlmostEqual(t["reward"], (30 / 40) ** 2)

    def test_refresh_and_dead(self):
        store = rt.MemoryStore()
        m = _moment(store)
        _play(store, m, [(True, 20), (False, 50), (True, 25), (False, 50)])
        m2 = rt.refresh_moment(store, m["id"])
        self.assertEqual((m2["tries"], m2["clears"], m2["value"]), (4, 2, 0.5))
        g = store.query("rl_groups", moment_id=m["id"])
        self.assertEqual(len(g), 1)
        self.assertTrue(g[0]["mixed"])
        dead = _moment(store, turn=11)
        _play(store, dead, [(False, 50)] * 8)
        self.assertEqual(rt.refresh_moment(store, dead["id"])["status"], "dead")

    def test_select(self):
        store = rt.MemoryStore()
        ms = []
        for i in range(10):
            ms.append(_moment(store, turn=i + 1, game="sp80-0605ab9e"))
            ms.append(_moment(store, turn=i + 1, game="wa30-ee6fef47", level=4))
        solved = _moment(store, turn=99)
        _play(store, solved, [(True, 5)] * 8)                     # measured p ~ 1: no signal left
        ms.append(rt.refresh_moment(store, solved["id"]))
        pick = rt.select_moments(ms, 10, max_game_share=0.5)
        self.assertEqual(len(pick), 10)
        self.assertNotIn(solved["id"], [m["id"] for m in pick])
        self.assertLessEqual(max(sum(m["game"] == g for m in pick) for g in ("sp80", "wa30")), 5)

    def test_value_cliffs(self):
        a = {"source": "r", "level": 2, "turn": 5, "tries": 8, "value": 0.75}
        b = {"source": "r", "level": 2, "turn": 9, "tries": 8, "value": 0.125}
        c = {"source": "r", "level": 2, "turn": 12, "tries": 8, "value": 0.0}
        cl = rt.value_cliffs([c, a, b])
        self.assertEqual([(x["turn"], y["turn"]) for x, y in cl], [(5, 9)])

    def test_priors(self):
        pri = rt.priors_from_frontier({"games": {"sp80": {"reach": [1.0, 0.43, 0.33]}}})
        self.assertAlmostEqual(pri[("sp80", 2)], 0.43)
        self.assertAlmostEqual(pri[("sp80", 3)], 0.33 / 0.43)


# ------------------------------------------------------------------------------------------------ seeding
def _events():
    """Synthetic events with the real log's quirk: the analysis row comes AFTER its turn's actions and carries
    the turn's last action and the level after it. Turns: 1 = a1; 2 = a2-a4 (a4 clears level 1); 3 = inspect
    only; 4 = a5-a6; 5 = a7 (clears level 2)."""
    ev = [{"type": "initial", "action_num": 0, "analysis_step": None, "level": 1}]

    def act(n, step, done=False):
        ev.append({"type": "action", "action_num": n, "analysis_step": step, "action_name": "ACTION1",
                   "level_completed": done})

    act(1, 1); ev.append({"type": "analysis", "analysis_step": 1, "action_num": 1, "level": 1})
    act(2, 2); act(3, 2); act(4, 2, True); ev.append({"type": "analysis", "analysis_step": 2, "action_num": 4, "level": 2})
    ev.append({"type": "analysis", "analysis_step": 3, "action_num": 4, "level": 2})
    act(5, 4); act(6, 4); ev.append({"type": "analysis", "analysis_step": 4, "action_num": 6, "level": 2})
    act(7, 5, True); ev.append({"type": "analysis", "analysis_step": 5, "action_num": 7, "level": 3})
    return ev


class TestSeed(unittest.TestCase):
    def test_level_spans(self):
        sp = sm.level_spans(_events())
        self.assertEqual(sp["clear"], {1: 4, 2: 7})
        self.assertEqual(sp["start"], {1: 1, 2: 5, 3: 8})
        self.assertEqual(sp["turn_start"], {1: (1, 1), 2: (2, 1), 3: (5, 2), 4: (5, 2), 5: (7, 2)})
        # mutation: the analysis rows' own action_num/level (the trap) would give different starts
        naive = {e["analysis_step"]: (e["action_num"], e["level"]) for e in _events() if e["type"] == "analysis"}
        self.assertNotEqual(naive, sp["turn_start"])

    def test_check_turn_starts(self):
        sp = sm.level_spans(_events())
        good = {1: {"action": 1}, 2: {"action": 2}, 4: {"action": 5}}
        self.assertEqual(sm.check_turn_starts(sp, good), [])
        self.assertEqual(sm.check_turn_starts(sp, {2: {"action": 4}}), [2])

    def test_moments(self):
        sp = sm.level_spans(_events())
        tokens = {1: {"action": 1, "tokens": 100}, 2: {"action": 2, "tokens": 200}, 3: {"action": 5, "tokens": 50},
                  4: {"action": 5, "tokens": 300}, 5: {"action": 7, "tokens": 400}}
        ms = sm.moments_for_game(run_id="r1", game_id="sp80-0605ab9e", spans=sp, tokens=tokens, levels=[2],
                                 human=[3, 4, 5], harness="h", policy="base", campaign="c")
        self.assertEqual([m["turn"] for m in ms], [3, 4, 5])
        m5 = ms[-1]
        self.assertEqual((m5["level_actions_before"], m5["ref_remaining_actions"], m5["ref_remaining_tokens"]),
                         (2, 1, 400))
        self.assertEqual(ms[0]["ref_remaining_tokens"], 750)
        self.assertEqual(ms[0]["state_key"], rt.state_key("sp80-0605ab9e", ["ACTION1"] * 4))

    def test_spread(self):
        self.assertEqual(sm.spread(list(range(10)), 3), [0, 4, 9])   # round half to even: 4.5 -> 4
        self.assertEqual(sm.spread([1, 2], 6), [1, 2])

    @unittest.skipUnless((REAL / "artifacts" / f"{RE86}_p0_events.jsonl").exists(), "re86 logs not on this box")
    def test_real_turn_starts_agree(self):
        sp = sm.level_spans(sm.iter_jsonl(REAL / "artifacts" / f"{RE86}_p0_events.jsonl"))
        tok = sm.turn_tokens(sm.iter_jsonl(REAL / f"{RE86}_p0_requests.jsonl"))
        self.assertGreater(len(tok), 20)
        self.assertEqual(sm.check_turn_starts(sp, tok), [])
        self.assertEqual(sp["clear"], {1: 32, 2: 75, 3: 134})          # viewer: [32, 43, 59, 93]


# ------------------------------------------------------------------------------------------------ records
def _req(step, msgs):
    return {"event": "request", "analysis_step": step, "action": step, "messages": msgs, "tools": [{"t": 1}],
            "chat_template_kwargs": {"preserve_thinking": True}}


class TestRecords(unittest.TestCase):
    def test_segments_and_mask(self):
        s, u = {"role": "system", "content": "S"}, {"role": "user", "content": "U1"}
        a1 = {"role": "assistant", "reasoning_content": "r1", "tool_calls": [1]}
        t1 = {"role": "tool", "content": "T1"}
        a2 = {"role": "assistant", "reasoning_content": "r2", "tool_calls": [2]}
        u2 = {"role": "user", "content": "U2"}
        rows = [_req(1, [s, u]), {"event": "response"}, _req(1, [s, u, a1, t1]), _req(2, [s, u, a1, t1, a2, u2]),
                _req(3, [s, {"role": "user", "content": "SUMMARY"}])]      # compaction -> new stretch
        segs = br.segments(rows)
        self.assertEqual([len(x) for x in segs], [3, 1])
        rec = br.record_from_segment(segs[0], keep=lambda r: True, meta={"run": "x"})
        self.assertEqual(rec["train"], [False, False, True, False, True, False])
        self.assertEqual(rec["meta"]["n_trained"], 2)
        only2 = br.record_from_segment(segs[0], keep=lambda r: r["analysis_step"] == 2)
        self.assertIsNone(only2)          # turn 2's reply would sit in a later request: not in the log
        only1 = br.record_from_segment(segs[0], keep=lambda r: r["analysis_step"] == 1)
        self.assertEqual(only1["train"], [False, False, True, False, True, False])

    def test_logged_reply_recovers_last_turn(self):
        s, u = {"role": "system", "content": "S"}, {"role": "user", "content": "U1"}
        a1 = {"role": "assistant", "reasoning_content": "r1", "tool_calls": [1]}
        rows = br.attach_usage([_req(1, [s, u]), {"event": "response", "analysis_step": 1, "usage": {"prompt_tokens": 9},
                                                  "response_message": a1}])
        for r in rows:
            r.setdefault("request_index_within_turn", None)
        rows = br.attach_usage(rows)
        rec = br.record_from_segment(br.segments(rows)[0], keep=lambda r: True)
        self.assertEqual(rec["messages"][-1]["reasoning_content"], "r1")
        self.assertEqual(rec["train"], [False, False, True])
        self.assertEqual(rec["meta"]["logged_prompt_tokens"], 9)

    def test_efficiency_weights(self):
        """Son 1-Oct: winning turns weigh by their level's score. _events(): L1 won in 4 moves, L2 in 3."""
        sp = sm.level_spans(_events())
        msgs = [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}]
        rows = []
        for step in range(1, 6):
            rows.append(_req(step, list(msgs)))
            msgs += [{"role": "assistant", "reasoning_content": f"r{step}", "tool_calls": [step]},
                     {"role": "tool", "content": f"T{step}"}]
        recs = br.records_for_game(rows, sp, {1, 2}, {"run": "x"}, human=[3, 4, 5])
        self.assertEqual(len(recs), 1)
        r = recs[0]
        got = {m["reasoning_content"]: w for m, w, t in zip(r["messages"], r["weights"], r["train"]) if t}
        self.assertAlmostEqual(got["r1"], (3 / 4) ** 2)             # level 1: 4 moves vs human 3
        self.assertAlmostEqual(got["r2"], (3 / 4) ** 2)
        self.assertAlmostEqual(got["r3"], 1.15)                      # level 2: 3 moves vs human 4, capped
        self.assertAlmostEqual(got["r4"], 1.15)
        self.assertNotIn("r5", got)                                  # its reply is not in the log
        uniform = br.records_for_game(rows, sp, {1, 2}, {"run": "x"})[0]
        self.assertEqual({w for w, t in zip(uniform["weights"], uniform["train"]) if t}, {1.0})

    def test_never_trains_non_assistant(self):
        s, u, t = {"role": "system", "content": "S"}, {"role": "user", "content": "U"}, {"role": "tool", "content": "T"}
        rec = br.record_from_segment([_req(1, [s, u]), _req(2, [s, u, t, u])], keep=lambda r: True)
        self.assertIsNone(rec)            # the appended message is a tool result, never trained

    def test_kept_levels(self):
        sp = sm.level_spans(_events())
        self.assertEqual(br.kept_levels(sp, [3, 4, 5], mode="cleared", min_level_score=0.25), {1, 2})
        self.assertEqual(br.kept_levels(sp, [1, 1, 5], mode="cleared", min_level_score=0.25), set())
        self.assertEqual(br.kept_levels(sp, [1, 1, 5], mode="cleared", min_level_score=0.25, frontier=[2]), {2})

    @unittest.skipUnless((REAL / f"{RE86}_p0_requests.jsonl").exists(), "re86 logs not on this box")
    def test_real_records(self):
        sp = sm.level_spans(sm.iter_jsonl(REAL / "artifacts" / f"{RE86}_p0_events.jsonl"))
        reqs = list(sm.iter_jsonl(REAL / f"{RE86}_p0_requests.jsonl"))
        recs = br.records_for_game(reqs, sp, {1, 2, 3}, {"run": "franzen-30sep"})
        self.assertGreater(len(recs), 0)
        for r in recs:
            for m, tr in zip(r["messages"], r["train"]):
                if tr:
                    self.assertEqual(m["role"], "assistant")
                    self.assertTrue(m.get("tool_calls") or m.get("content") or m.get("reasoning_content"))
            self.assertLessEqual(max(r["meta"]["turns"]), max(s for s, (_, l) in sp["turn_start"].items() if l <= 3))


if __name__ == "__main__":
    unittest.main(verbosity=1)

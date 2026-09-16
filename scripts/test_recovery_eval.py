"""
Author: Claude Opus 5
Date: 16-September-2026
PURPOSE: Guards on tools/recovery_eval.py and its frozen questions in
datasets/decision-steps/v0/recovery-eval/items.jsonl. Three layers:
  - answer parsing, which needs nothing;
  - the committed questions: the no-history prompt carries no history, neither prompt names the
    winning choice or quotes a pass-D record's rationale, RESET is never offered, and every item
    passed its engine check when it was built;
  - the engine, when the recordings and the game builds are on disk: answering with the recorded
    failed choice must score repeated_failed and the recorded winning choice matched_win on every
    item, and rebuilding the questions must reproduce the committed file byte for byte.
The engine layer is skipped, not faked, without the recordings or $ARC3_ENVIRONMENTS_DIR (the exact
builds are ~/flash-next-work/environment_files-11p44 on a108).
SRP/DRY check: Pass - test_segment.py and test_decision_step_validator.py own the records; this
owns only the eval's questions and scoring.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import recovery_eval as ev  # noqa: E402

ITEMS = ev.EVAL_DIR / "items.jsonl"
ENV_DIR = os.environ.get("ARC3_ENVIRONMENTS_DIR")


def load_items() -> list[dict]:
    return ev.read_jsonl(ITEMS)


class ParseAnswerTests(unittest.TestCase):
    def test_keyboard_label_maps_to_engine_action(self):
        self.assertEqual(ev.parse_answer("thinking...\nACTION: LEFT"), {"id": "ACTION3", "data": {}})

    def test_mouse_row_col_maps_to_x_y(self):
        self.assertEqual(ev.parse_answer("ACTION: MOUSE row=12 col=40"), {"id": "ACTION6", "data": {"x": 40, "y": 12}})

    def test_last_answer_line_wins(self):
        self.assertEqual(ev.parse_answer("ACTION: UP\nno, better:\nACTION: down")["id"], "ACTION2")

    def test_engine_name_and_comma_accepted(self):
        self.assertEqual(ev.parse_answer("ACTION: ACTION6 row=1, col=2"), {"id": "ACTION6", "data": {"x": 2, "y": 1}})

    def test_mouse_without_coordinates_is_unparsed(self):
        self.assertIsNone(ev.parse_answer("ACTION: MOUSE")["id"])

    def test_reset_and_unknown_names_are_unparsed(self):
        self.assertIsNone(ev.parse_answer("ACTION: RESET")["id"])
        self.assertIsNone(ev.parse_answer("ACTION: JUMP")["id"])

    def test_no_answer_line(self):
        self.assertIsNone(ev.parse_answer("I would move left."))
        self.assertIsNone(ev.parse_answer(None))


class FrozenItemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = load_items()

    def test_items_exist_and_ids_are_unique(self):
        self.assertGreater(len(self.items), 0)
        ids = [i["item_id"] for i in self.items]
        self.assertEqual(len(ids), len(set(ids)))

    def test_prompt_version_is_current(self):
        for item in self.items:
            self.assertEqual(item["prompt_version"], ev.PROMPT_VERSION, item["item_id"])

    def test_no_history_prompt_carries_no_history(self):
        for item in self.items:
            p = item["prompts"]["no_history"]
            self.assertNotIn("WHAT HAPPENED EARLIER", p, item["item_id"])
            self.assertNotIn("earlier attempt", p, item["item_id"])
            self.assertIn(f"chose {item['failed']['text']}.", item["prompts"]["with_history"], item["item_id"])

    def test_prompts_differ_only_by_the_history_block(self):
        for item in self.items:
            w, n = item["prompts"]["with_history"], item["prompts"]["no_history"]
            start = w.index("\n\nWHAT HAPPENED EARLIER ON THIS LEVEL.")
            end = w.index("\n\nACTIONS YOU CAN TAKE NOW:")
            self.assertEqual(w[:start] + w[end:], n, item["item_id"])

    def test_winning_choice_is_never_named(self):
        for item in self.items:
            for p in item["prompts"].values():
                self.assertNotIn(f"chose {item['win']['text']}", p, item["item_id"])
                if item["win"]["text"].startswith("MOUSE"):
                    self.assertNotIn(item["win"]["text"], p, item["item_id"])

    def test_reset_is_never_offered(self):
        for item in self.items:
            self.assertNotIn("RESET", item["offered"], item["item_id"])
            self.assertNotIn("RESET;", item["prompts"]["no_history"], item["item_id"])

    def test_record_judgments_do_not_leak(self):
        for item in self.items:
            if not item["record"]:
                continue
            records = ev.read_jsonl(ev.EPISODES / item["record"])
            rec = next(r for r in records if r["source"]["row_index"] == item["win"]["row"])
            for p in item["prompts"].values():
                self.assertNotIn(rec["decision"]["rationale"][:60], p, item["item_id"])
                self.assertNotIn(rec["decision"]["expected_observation"][:60], p, item["item_id"])

    def test_every_item_passed_its_engine_check(self):
        for item in self.items:
            self.assertIn("engine_check", item, item["item_id"])
            self.assertTrue(all(item["engine_check"].values()), (item["item_id"], item["engine_check"]))


@unittest.skipUnless(ENV_DIR and Path(ENV_DIR).is_dir(), "needs $ARC3_ENVIRONMENTS_DIR with the exact game builds")
class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = load_items()
        missing = [i["item_id"] for i in cls.items
                   if not (ev.DEFAULT_RECORDINGS / i["game_id"] / f"{i['recording_guid']}.ndjson").exists()]
        if missing:
            raise unittest.SkipTest(f"recordings not on disk for {len(missing)} item(s)")
        cls.engine = ev.Engine(Path(ENV_DIR))

    def test_recorded_choices_score_as_themselves(self):
        for item in self.items:
            failed = ev.classify(self.engine, item, {"content": f"ACTION: {item['failed']['text']}", "finish_reason": "stop"})
            win = ev.classify(self.engine, item, {"content": f"ACTION: {item['win']['text']}", "finish_reason": "stop"})
            self.assertEqual(failed["bucket"], "repeated_failed", item["item_id"])
            self.assertEqual(win["bucket"], "matched_win", item["item_id"])

    def test_unoffered_action_and_truncated_reply(self):
        item = next(i for i in self.items if "ACTION6" not in i["offered"])
        self.assertEqual(ev.classify(self.engine, item, {"content": "ACTION: MOUSE row=1 col=1"})["bucket"], "not_offered")
        self.assertEqual(ev.classify(self.engine, item, {"content": "", "finish_reason": "length"})["bucket"], "no_answer")

    def test_rebuild_reproduces_the_committed_items(self):
        items, _ = ev.build(ev.DEFAULT_RECORDINGS, Path(ENV_DIR))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "items.jsonl"
            out.write_text("".join(json.dumps(i) + "\n" for i in items))
            self.assertEqual(out.read_text(), ITEMS.read_text())


if __name__ == "__main__":
    unittest.main()

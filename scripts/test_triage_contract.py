"""Regression checks for cited diagnoses, safe routing, and immutable identities."""
import copy
import unittest

from railway.triage_contract import digest, fenced_game, make_item, validate_assessment, validate_item


def sample():
    packet = {"game": "bp35", "build": "0a0ad940", "level": 1, "path_id": "run:bp35_p0:L1", "step": 8,
              "trace_sha256": "a" * 64, "reference_sha256": "b" * 64, "context_complete": True,
              "evidence": [{"id": "t7", "kind": "thinking", "text": "This route cannot work."},
                           {"id": "t8", "kind": "result", "text": "A passage is visible."}],
              "reference": [{"id": "rule1", "kind": "rule", "text": "The map extends beyond the viewport."}]}
    assessment = {"status": "issue", "category": "unsupported_certainty", "summary": "An untested route was rejected.",
                  "claim": {"ref": "t7", "quote": "This route cannot work."},
                  "support": {"ref": "t8", "quote": "A passage is visible."},
                  "reference": {"ref": "rule1", "quote": "The map extends beyond the viewport."},
                  "alternative": "The passage may be blocked beyond the view.", "solver_knew": "unknown",
                  "route": "human", "human_question": "Does the observed passage justify exploring?",
                  "next_action": "Compare a continuation that explores the passage.", "impact": "high"}
    return packet, assessment, {"model": "gpt-6-luna", "prompt_version": "test-v1"}


class TriageContractTests(unittest.TestCase):
    def test_exact_citations_are_required(self):
        packet, assessment, judge = sample()
        for key in ("claim", "support", "reference"):
            bad = copy.deepcopy(assessment)
            bad[key]["quote"] = "The judge invented this."
            with self.subTest(key=key), self.assertRaises(ValueError):
                make_item(packet, bad, judge)

    def test_known_reference_errors_and_missing_context_do_not_reach_humans(self):
        packet, assessment, _ = sample()
        assessment["category"] = "reference_conflict"
        self.assertEqual(validate_assessment(packet, assessment)["route"], "assistant")
        assessment["category"] = "contradiction"
        packet["context_complete"] = False
        self.assertEqual(validate_assessment(packet, assessment)["route"], "assistant")

    def test_no_issue_never_becomes_a_human_task(self):
        packet, assessment, _ = sample()
        assessment["status"] = "no_issue"
        self.assertEqual(validate_assessment(packet, assessment)["route"], "discard")

    def test_low_impact_allegation_does_not_spend_human_attention(self):
        packet, assessment, _ = sample()
        assessment["impact"] = "low"
        self.assertEqual(validate_assessment(packet, assessment)["route"], "discard")

    def test_repeating_claim_is_not_independent_support_for_human_review(self):
        packet, assessment, _ = sample()
        assessment["support"] = assessment["claim"]
        self.assertEqual(validate_assessment(packet, assessment)["route"], "assistant")

    def test_changed_support_does_not_inherit_an_old_resolution(self):
        packet, assessment, judge = sample()
        first = make_item(packet, assessment, judge)
        packet["evidence"][1]["text"] = "A different passage is visible."
        assessment["support"]["quote"] = "A different passage is visible."
        self.assertNotEqual(first["cluster_key"], make_item(packet, assessment, judge)["cluster_key"])

    def test_human_task_needs_a_concrete_question_and_followup(self):
        packet, assessment, _ = sample()
        assessment["next_action"] = ""
        with self.assertRaises(ValueError):
            validate_assessment(packet, assessment)

    def test_repeated_evidence_groups_without_losing_identity(self):
        packet, assessment, judge = sample()
        first = make_item(packet, assessment, judge)
        packet["trace_sha256"] = "c" * 64
        packet["path_id"] = "another:bp35_p0:L1"
        second = make_item(packet, assessment, judge)
        self.assertEqual(first["cluster_key"], second["cluster_key"])
        self.assertNotEqual(first["id"], second["id"])
        packet["reference_sha256"] = "d" * 64
        self.assertNotEqual(second["cluster_key"], make_item(packet, assessment, judge)["cluster_key"])

    def test_publisher_cannot_relabel_or_approve_item(self):
        original = make_item(*sample())
        self.assertEqual(validate_item(original), original)
        for key, val in (("id", "0" * 64), ("priority", 9999), ("training_approved", True), ("game", "ka59")):
            bad = {**original, key: val}
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_item(bad)

    def test_test_only_families_and_legacy_fences_cannot_enter(self):
        for game in ("as66", "ah66", "vc33", "vz33", "az25", "lf52", "tn36"):
            self.assertTrue(fenced_game(game))
            packet, assessment, judge = sample()
            packet["game"] = game
            with self.subTest(game=game), self.assertRaises(ValueError):
                make_item(packet, assessment, judge)
        self.assertFalse(fenced_game("bp35"))

    def test_packet_duplicates_and_script_urls_rejected(self):
        packet, assessment, judge = sample()
        packet["reference"][0]["id"] = "t7"
        with self.assertRaises(ValueError):
            make_item(packet, assessment, judge)
        packet, assessment, judge = sample()
        packet["notes_url"] = "javascript:alert(1)"
        with self.assertRaises(ValueError):
            make_item(packet, assessment, judge)


if __name__ == "__main__":
    unittest.main()

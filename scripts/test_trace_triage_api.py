"""Focused triage API checks; no database server or permanent test files required."""
from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import Mock, patch

from railway.trace_triage import (
    MAX_PUBLICATION, TraceTriageApi, TriageProblem, clean_decision, clean_publication,
    decide, export, publish, queue,
)
from railway.triage_contract import make_item

TEAM = "reviewer@example.com"
TOKEN = {"Authorization": "Bearer test-token"}
SIGNED_IN = {"X-Forwarded-Email": TEAM}
PREFIX = TraceTriageApi.PREFIX


def fixture():
    packet = {
        "game": "ka59", "build": "test-build", "level": 1, "path_id": "run:ka59:L1", "step": 3,
        "trace_sha256": "a" * 64, "reference_sha256": "b" * 64, "context_complete": True,
        "evidence": [{"id": "e1", "kind": "thinking", "text": "The wall never moves."},
                     {"id": "e2", "kind": "observation", "text": "The wall moved right."}],
        "reference": [{"id": "r1", "kind": "human_note", "text": "Walls can move after activation."}],
    }
    assessment = {
        "status": "issue", "category": "contradiction", "summary": "Claim conflicts with observed motion.",
        "claim": {"ref": "e1", "quote": "The wall never moves."},
        "support": {"ref": "e2", "quote": "The wall moved right."},
        "reference": {"ref": "r1", "quote": "Walls can move after activation."},
        "alternative": "The camera may have moved.", "solver_knew": "yes", "route": "human",
        "human_question": "Was this camera motion?", "next_action": "Compare motion against the frame edge.",
        "impact": "high",
    }
    return make_item(packet, assessment, {"model": "gpt-6-luna", "prompt_version": "test-v1"},
                     created_at="2026-10-05T12:00:00Z")


def request(api, method, action, headers=None, body=None):
    raw = json.dumps(body).encode() if body is not None else b""
    headers = dict(headers or {})
    headers.setdefault("Content-Length", str(len(raw)))
    response = api.handle(method, PREFIX + "/" + action, headers, lambda n: raw[:n])
    return response.status, json.loads(response.body)


class AccessAndValidation(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict("os.environ", {"ALLOWED_EMAILS": TEAM})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.db = Mock(side_effect=AssertionError("request must fail before DB access"))
        self.api = TraceTriageApi(self.db, "test-token")

    def test_machine_and_human_authority_are_separate(self):
        for method, action in (("PUT", "publication"), ("GET", "export")):
            for headers in ({}, SIGNED_IN, {"Authorization": "Bearer wrong"},
                            {"Authorization": "Bearer test-token "}):
                self.assertEqual(request(self.api, method, action, headers)[0], 401)
        for action in ("queue", "item?id=" + "a" * 64):
            self.assertEqual(request(self.api, "GET", action, TOKEN)[0], 401)
            self.assertEqual(request(self.api, "GET", action, {"X-Forwarded-Email": "outsider@example.com"})[0], 403)
        self.assertFalse(TraceTriageApi.owns("/api/v1/public/review/triage/queue"))
        self.assertFalse(TraceTriageApi.owns(PREFIX + "-other"))

    def test_routes_reject_wrong_methods_and_invalid_queries(self):
        for action in ("queue?route=discard", "queue?limit=21", "queue?limit=NaN", "item?id=../secrets",
                       "queue?exclude=bad", "queue?exclude=" + ",".join(["a" * 64] * 101)):
            self.assertEqual(request(self.api, "GET", action, SIGNED_IN)[0], 400)
        self.assertEqual(request(self.api, "POST", "queue", SIGNED_IN)[0], 405)
        self.assertEqual(request(self.api, "GET", "publication", TOKEN)[0], 405)
        self.assertEqual(request(self.api, "GET", "publication/queue", TOKEN)[0], 401)
        self.assertEqual(request(self.api, "GET", "export?after=bad", TOKEN)[0], 400)

    def test_publication_is_bounded_and_evidence_checked_before_db(self):
        self.assertEqual(request(self.api, "PUT", "publication", {**TOKEN, "Content-Length": str(MAX_PUBLICATION + 1)})[0], 413)
        bad = fixture()
        bad["assessment"]["claim"]["quote"] = "Invented claim"
        self.assertEqual(request(self.api, "PUT", "publication", TOKEN, {"items": [bad]})[0], 400)
        self.assertEqual(request(self.api, "PUT", "publication", TOKEN, {"items": []})[0], 400)
        self.assertEqual(request(self.api, "PUT", "publication", {**TOKEN, "Content-Encoding": "gzip"}, {"items": [fixture()]})[0], 415)
        self.assertEqual(clean_publication({"items": [fixture(), fixture()]}), [fixture()])

    def test_decision_rejects_invalid_values(self):
        valid = {"id": fixture()["id"], "verdict": "confirmed", "seconds": 20}
        for change in ({"verdict": "skip"}, {"verdict": []}, {"seconds": True}, {"seconds": -1},
                       {"seconds": 86401}, {"note": "x" * 4001}, {"note": "\0"}, {"id": "bad"}):
            with self.assertRaises(TriageProblem):
                clean_decision({**valid, **change})
        self.assertEqual(clean_decision(valid)["note"], "")


class PublicationAndDecisions(unittest.TestCase):
    def test_same_publication_is_a_noop_and_changes_conflict(self):
        item = fixture()
        cursor = Mock()
        cursor.fetchone.return_value = (copy.deepcopy(item),)
        self.assertEqual(publish(cursor, [item])["inserted"], 0)
        self.assertEqual(publish(cursor, [{**item, "created_at": "2026-10-06T00:00:00+00:00"}])["inserted"], 0)
        self.assertFalse(any("INSERT" in call.args[0] for call in cursor.execute.call_args_list))
        changed = copy.deepcopy(item)
        changed["assessment"]["summary"] += " changed"
        with self.assertRaises(TriageProblem) as problem:
            publish(cursor, [changed])
        self.assertEqual(problem.exception.status, 409)

    def test_a_later_occurrence_inherits_reviewed_status(self):
        cursor = Mock()
        cursor.fetchone.side_effect = [None, ("resolved", "assistant")]
        self.assertEqual(publish(cursor, [fixture()])["inserted"], 1)
        insertion = cursor.execute.call_args
        self.assertEqual(insertion.args[1][5], "resolved")
        self.assertFalse(any("trace_triage_decisions" in call.args[0] for call in cursor.execute.call_args_list))

    def test_review_keeps_provenance_and_resolves_whole_cluster(self):
        item = fixture()
        cursor = Mock()
        cursor.fetchone.side_effect = [(item["cluster_key"],), ("open",)]
        cursor.fetchall.return_value = []
        decision = clean_decision({"id": item["id"], "verdict": "reasonable", "note": "Camera scroll", "seconds": 17})
        result = decide(cursor, decision, TEAM)
        self.assertFalse(result["training_approved"])
        insert = [call for call in cursor.execute.call_args_list if "INSERT" in call.args[0]][0]
        self.assertEqual(insert.args[1], (item["id"], item["cluster_key"], TEAM, "reasonable", "Camera scroll", 17))
        self.assertEqual(cursor.execute.call_args.args[1], ("resolved", item["cluster_key"]))
        self.assertIn("WHERE cluster_key", cursor.execute.call_args.args[0])

    def test_another_review_cannot_silently_overwrite_first(self):
        item = fixture()
        cursor = Mock()
        cursor.fetchone.side_effect = [(item["cluster_key"],), ("resolved",)]
        cursor.fetchall.return_value = [(item["id"], "other@example.com", "confirmed", "", 10, "now")]
        with self.assertRaises(TriageProblem) as problem:
            decide(cursor, clean_decision({"id": item["id"], "verdict": "reasonable"}), TEAM)
        self.assertEqual(problem.exception.code, "already_reviewed")
        self.assertFalse(any("INSERT" in call.args[0] for call in cursor.execute.call_args_list))

    def test_insufficient_hands_cluster_to_assistants_and_retry_ignores_time(self):
        item = fixture()
        cursor = Mock()
        cursor.fetchone.side_effect = [(item["cluster_key"],), ("open",)]
        cursor.fetchall.return_value = []
        decision = clean_decision({"id": item["id"], "verdict": "insufficient", "seconds": 17})
        decide(cursor, decision, TEAM)
        self.assertIn("route = 'assistant'", cursor.execute.call_args.args[0])
        self.assertEqual(cursor.execute.call_args.args[1], (item["cluster_key"],))
        later = Mock()
        later.fetchone.side_effect = [None, ("open", "assistant")]
        publish(later, [item])
        self.assertEqual(later.execute.call_args.args[1][3], "assistant")
        retry = Mock()
        retry.fetchone.side_effect = [(item["cluster_key"],), ("open",)]
        retry.fetchall.return_value = [(item["id"], TEAM, "insufficient", "", 17, "now")]
        self.assertEqual(decide(retry, {**decision, "seconds": 31}, TEAM)["status"], "saved")
        self.assertFalse(any("INSERT" in c.args[0] for c in retry.execute.call_args_list))

    def test_failed_transaction_rolls_back_and_closes(self):
        connection = Mock()
        connection.cursor.return_value.__enter__ = Mock(return_value=Mock())
        connection.cursor.return_value.__exit__ = Mock(return_value=False)
        api = TraceTriageApi(lambda: connection, "token")
        with self.assertRaises(TriageProblem):
            with api._cursor(write=True):
                raise TriageProblem(409, "conflict", "conflict")
        connection.rollback.assert_called_once()
        connection.close.assert_called_once()
        connection.commit.assert_not_called()

    def test_export_carries_diagnostic_and_decision_but_never_reward(self):
        item = fixture()
        cursor = Mock()
        cursor.fetchall.side_effect = [[(item, "resolved", item["cluster_key"], "assistant")],
                                      [(item["id"], TEAM, "confirmed", "observed", 12, "now")]]
        result = export(cursor, "", 10)
        self.assertEqual(result["items"][0]["packet"], item["packet"])
        self.assertEqual(result["items"][0]["decisions"][0]["reviewer"], TEAM)
        self.assertFalse(result["items"][0]["training_approved"])
        self.assertIsNone(result["next_cursor"])

    def test_queue_response_exposes_recurrence_and_cluster_counts(self):
        cursor = Mock()
        cursor.fetchall.side_effect = [[(fixture(), "open", 9)], []]
        cursor.fetchone.return_value = (2, 3, 4)
        result = queue(cursor, "human", 5, ["a" * 64])
        self.assertEqual(result["items"][0]["occurrences"], 9)
        self.assertEqual(result["counts"], {"human": 2, "assistant": 3, "resolved": 4})
        selection = cursor.execute.call_args_list[0]
        self.assertEqual(selection.args[1], ("human", ["a" * 64], 5))
        self.assertIn("skipped.cluster_key = candidate.cluster_key", selection.args[0])
        self.assertNotIn("exclude", cursor.execute.call_args.args[0])


if __name__ == "__main__":
    unittest.main()

"""Tests for railway/trace_feedback.py: thumbs up / thumbs down on the model's output in a run.

The pure checks (validation, the text hash, who may call what, what the image ships) always
run. The database round trip runs only when ARC3_TEST_DATABASE_URL points at a disposable
Postgres: it DROPS and recreates arc3_trace_feedback there, so never point it at a real catalog.

    python3.13 -m unittest scripts.test_trace_feedback
    ARC3_TEST_DATABASE_URL=postgresql://... python3.13 -m unittest scripts.test_trace_feedback
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unittest
from pathlib import Path

from railway.trace_feedback import (
    MAX_CONTENT_CHARS,
    TraceFeedbackApi,
    TraceFeedbackProblem,
    canonical_text,
    clean_vote,
    content_sha256,
    export_votes,
    list_votes,
    set_vote,
)

ROOT = Path(__file__).resolve().parents[1]
RUN = "20260930-new-harness"


def body(**changes) -> dict:
    payload = {
        "run": RUN,
        "gameIndex": 3,
        "gameId": "g042",
        "stepIndex": 14,
        "turn": 9,
        "sectionIndex": 5,
        "sectionLabel": "THINKING",
        "content": "Maybe clicking a plant converts it to water.",
        "vote": "down",
        "reason": "The plants are not the goal; it never tested this against the fish.",
    }
    payload.update(changes)
    return payload


class Headers(dict):
    def get(self, key, default=None):  # case-insensitive like http.client's message
        for name, value in self.items():
            if name.lower() == key.lower():
                return value
        return default


class ValidationTests(unittest.TestCase):
    def test_a_vote_carries_the_hash_of_the_exact_text(self) -> None:
        item = clean_vote(body())
        self.assertEqual(item["content_sha256"], hashlib.sha256(body()["content"].encode()).hexdigest())
        self.assertEqual((item["run_id"], item["game_index"], item["step_index"], item["section_index"]), (RUN, 3, 14, 5))
        self.assertEqual((item["vote"], item["section_label"], item["turn"]), ("down", "THINKING", 9))

    def test_text_is_kept_exactly_but_made_storable(self) -> None:
        # Leading/trailing whitespace is part of what the model wrote; NULs and lone surrogates
        # cannot be stored, and the browser hashes them the same way (trace-votes.js).
        item = clean_vote(body(content="  a\x00b\ud800c\n"))
        self.assertEqual(item["content"], "  ab�c\n")
        self.assertEqual(item["content_sha256"], hashlib.sha256("  ab�c\n".encode()).hexdigest())
        self.assertEqual(content_sha256("a\x00b"), content_sha256("ab"))
        self.assertEqual(canonical_text("ok \U0001F44D"), "ok \U0001F44D")  # a real pair is untouched

    def test_clearing_and_optional_fields(self) -> None:
        item = clean_vote(body(vote=None, reason="", turn=None, gameId=None))
        self.assertEqual((item["vote"], item["reason"], item["turn"], item["game_id"]), (None, None, None, None))

    def test_bad_bodies_are_refused(self) -> None:
        for changes, code in (
            ({"vote": "meh"}, "invalid_vote"),
            ({"vote": 1}, "invalid_vote"),
            ({"run": "../etc"}, "invalid_run"),
            ({"run": None}, "invalid_run"),
            ({"gameIndex": -1}, "invalid_gameIndex"),
            ({"gameIndex": True}, "invalid_gameIndex"),
            ({"stepIndex": "14"}, "invalid_stepIndex"),
            ({"sectionIndex": None}, "invalid_sectionIndex"),
            ({"turn": 1.5}, "invalid_turn"),
            ({"sectionLabel": ""}, "invalid_sectionLabel"),
            ({"content": "   "}, "invalid_content"),
            ({"content": None}, "invalid_content"),
            ({"content": "x" * (MAX_CONTENT_CHARS + 1)}, "invalid_content"),
            ({"reason": "x" * 4001}, "invalid_reason"),
            ({"reason": 7}, "invalid_reason"),
        ):
            with self.subTest(changes=list(changes)):
                with self.assertRaises(TraceFeedbackProblem) as caught:
                    clean_vote(body(**changes))
                self.assertEqual(caught.exception.code, code)
        with self.assertRaises(TraceFeedbackProblem):
            clean_vote(["not", "an", "object"])


class RouteAuthTests(unittest.TestCase):
    """Who may call what, checked before any database access (connect() must never run)."""

    def setUp(self) -> None:
        def no_database():
            raise AssertionError("the database must not be touched")

        self.api = TraceFeedbackApi(no_database, "secret-token")

    def call(self, method: str, path: str, headers: dict, payload: bytes = b"") -> tuple[int, dict]:
        headers = Headers(headers)
        if payload:
            headers["Content-Length"] = str(len(payload))
        response = self.api.handle(method, path, headers, lambda n: payload[:n])
        return response.status, json.loads(response.body)

    def test_voting_needs_the_proxy_identity(self) -> None:
        for method in ("GET", "POST"):
            for headers in ({}, {"Authorization": "Bearer secret-token"}, {"X-Forwarded-Email": "not-an-email"}):
                with self.subTest(method=method, headers=headers):
                    status, payload = self.call(method, "/api/v1/traces/feedback", headers, b"{}")
                    self.assertEqual((status, payload["error"]), (401, "sign_in_required"))

    def test_export_needs_the_token_and_ignores_identity(self) -> None:
        for headers in ({}, {"Authorization": "Bearer wrong"}, {"X-Forwarded-Email": "son@example.com"}):
            with self.subTest(headers=headers):
                status, payload = self.call("GET", "/api/v1/traces/feedback-export", headers)
                self.assertEqual((status, payload["error"]), (401, "unauthorized"))
        status, payload = self.call("POST", "/api/v1/traces/feedback-export", {"Authorization": "Bearer secret-token"})
        self.assertEqual((status, payload["error"]), (405, "method_not_allowed"))

    def test_a_signed_in_bad_vote_fails_before_the_database(self) -> None:
        who = {"X-Forwarded-Email": "Mark@Example.com"}
        status, payload = self.call("POST", "/api/v1/traces/feedback", who, json.dumps(body(vote="meh")).encode())
        self.assertEqual((status, payload["error"]), (400, "invalid_vote"))
        status, payload = self.call("POST", "/api/v1/traces/feedback", who, b"not json")
        self.assertEqual((status, payload["error"]), (400, "invalid_json"))
        status, payload = self.call("POST", "/api/v1/traces/feedback", who)
        self.assertEqual((status, payload["error"]), (400, "invalid_body"))
        status, payload = self.call("GET", "/api/v1/traces/feedback?run=bad/run&game=0", who)
        self.assertEqual((status, payload["error"]), (400, "invalid_run"))
        status, payload = self.call("GET", f"/api/v1/traces/feedback?run={RUN}", who)
        self.assertEqual((status, payload["error"]), (400, "invalid_game"))
        status, payload = self.call("PUT", "/api/v1/traces/feedback", who)
        self.assertEqual((status, payload["error"]), (405, "method_not_allowed"))
        status, payload = self.call("GET", "/api/v1/traces/elsewhere", who)
        self.assertEqual((status, payload["error"]), (404, "not_found"))

    def test_owns_only_the_traces_prefix(self) -> None:
        self.assertTrue(TraceFeedbackApi.owns("/api/v1/traces/feedback"))
        self.assertTrue(TraceFeedbackApi.owns("/api/v1/traces/feedback-export"))
        self.assertFalse(TraceFeedbackApi.owns("/api/v1/tracesx"))
        self.assertFalse(TraceFeedbackApi.owns("/api/v1/games/feedback"))
        self.assertFalse(TraceFeedbackApi.owns("/api/v1/runs/x/publication"))


class ShippingTests(unittest.TestCase):
    """The parts that are easy to forget: the image, the proxy, the cache tags, the page."""

    def test_proxy_opens_only_the_token_export(self) -> None:
        entrypoint = (ROOT / "railway" / "entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn('--skip-auth-route="^/api/v1/traces/feedback-export$"', entrypoint)
        self.assertNotIn('--skip-auth-route="^/api/v1/traces/"', entrypoint)
        self.assertNotIn('--skip-auth-route="^/api/v1/traces/feedback$"', entrypoint)

    def test_server_ships_and_loads_the_module(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        server = (ROOT / "railway" / "catalog_server.py").read_text(encoding="utf-8")
        schema = (ROOT / "railway" / "catalog_schema.sql").read_text(encoding="utf-8")
        self.assertIn("COPY railway/trace_feedback.py /trace_feedback.py", dockerfile)
        self.assertIn("from trace_feedback import TraceFeedbackApi", server)
        for method in ("GET", "POST"):
            self.assertIn(f'if self.handle_trace_feedback("{method}"):', server)
        self.assertIn("CatalogHandler.trace_feedback_api = TraceFeedbackApi(", server)
        self.assertIn("CREATE TABLE IF NOT EXISTS arc3_trace_feedback", schema)
        self.assertIn("UNIQUE (run_id, game_index, step_index, section_index, content_sha256, reviewer)", schema)

    def test_the_viewer_reaches_the_new_code_past_the_cache(self) -> None:
        js = ROOT / "docs" / "static" / "js"
        decision = (js / "decision.js").read_text(encoding="utf-8")
        main = (js / "main.js").read_text(encoding="utf-8")
        tag = re.search(r'"\./trace-votes\.js\?v=([^"]+)"', decision)
        self.assertIsNotNone(tag)
        # main.js must import the decision panel under a tag newer than the pre-votes one, and
        # viewer.html must load that main.js, or a cached copy keeps the thumbs off the page.
        self.assertNotIn("decision.js?v=20260817-literal", main)
        self.assertIn("feedback: {", main)
        viewer = (ROOT / "docs" / "viewer.html").read_text(encoding="utf-8")
        self.assertNotIn("main.js?v=20260911-turn-links", viewer)
        self.assertIn("/api/v1/traces/feedback", (js / "trace-votes.js").read_text(encoding="utf-8"))

    def test_every_page_with_thumbs_loads_their_script_and_styles(self) -> None:
        docs = ROOT / "docs"
        css = (docs / "static" / "css" / "trace-votes.css").read_text(encoding="utf-8")
        for rule in (".vote-btn", ".vote-note", ".literal-record-head:has(> .vote)", ".vote-row-head"):
            self.assertIn(rule, css)
        # One copy of the styles: a second set left behind in app.css would drift.
        self.assertNotIn(".vote-btn", (docs / "static" / "css" / "app.css").read_text(encoding="utf-8"))
        for page in ("viewer.html", "trace.html"):
            self.assertIn("./static/css/trace-votes.css", (docs / page).read_text(encoding="utf-8"))
        trace = (docs / "static" / "js" / "trace.js").read_text(encoding="utf-8")
        self.assertIn('from "./trace-votes.js', trace)
        self.assertIn("installVoteRows(voteTarget);", trace)
        self.assertNotIn("trace.js?v=20260824-trace-tokens", (docs / "trace.html").read_text(encoding="utf-8"))
        decision = (docs / "static" / "js" / "decision.js").read_text(encoding="utf-8")
        self.assertIn("renderLiteral(step, votes)", decision)


@unittest.skipUnless(os.environ.get("ARC3_TEST_DATABASE_URL"), "set ARC3_TEST_DATABASE_URL to a disposable Postgres")
class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import psycopg2

        cls.url = os.environ["ARC3_TEST_DATABASE_URL"]
        cls.connect = staticmethod(lambda: psycopg2.connect(cls.url))
        schema = (ROOT / "railway" / "catalog_schema.sql").read_text(encoding="utf-8")
        with cls.connect() as connection, connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS arc3_trace_feedback CASCADE")
            cursor.execute(schema)
            cursor.execute(schema)  # the server re-runs the schema on every start

    def setUp(self) -> None:
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute("TRUNCATE arc3_trace_feedback RESTART IDENTITY")
        self.api = TraceFeedbackApi(self.connect, "secret-token")

    def query(self, fn, *args, **kwargs):
        connection = self.connect()
        try:
            with connection, connection.cursor() as cursor:
                return fn(cursor, *args, **kwargs)
        finally:
            connection.close()

    def vote(self, reviewer: str = "mark@example.com", **changes) -> dict:
        return self.query(set_vote, clean_vote(body(**changes)), reviewer=reviewer)

    def listed(self, viewer: str = "mark@example.com", **query) -> list[dict]:
        params = {"run": [RUN], "game": ["3"], **{key: [str(value)] for key, value in query.items()}}
        return self.query(list_votes, params, viewer=viewer)["votes"]

    def test_one_mark_per_reviewer_per_section_and_it_can_change(self) -> None:
        first = self.vote()
        self.assertEqual((first["status"], first["vote"], first["value"], first["mine"]), ("saved", "down", -1, True))
        again = self.vote(vote="up", reason="On reflection this was the right read.")
        self.assertEqual(again["feedbackId"], first["feedbackId"])
        self.assertEqual((again["vote"], again["value"]), ("up", 1))
        self.assertGreaterEqual(again["updatedAt"], first["createdAt"])
        self.assertEqual(len(self.listed()), 1)

        self.vote(reviewer="son@example.com", vote="down", reason=None)
        votes = self.listed(viewer="son@example.com", step=14)
        self.assertEqual([(v["reviewer"], v["vote"], v["mine"]) for v in votes],
                         [("mark@example.com", "up", False), ("son@example.com", "down", True)])
        self.assertNotIn("content", votes[0])  # the list is for the viewer; text stays out of it

        self.assertEqual(self.vote(vote=None)["status"], "cleared")
        self.assertEqual([v["reviewer"] for v in self.listed()], ["son@example.com"])
        self.assertEqual(self.vote(vote=None)["status"], "cleared")  # clearing nothing is not an error

    def test_a_republished_run_does_not_re_aim_an_old_mark(self) -> None:
        old = self.vote()
        new = self.vote(content="A different thought now sits at this position.", vote="up", reason="fine")
        self.assertNotEqual(old["feedbackId"], new["feedbackId"])
        self.assertNotEqual(old["contentSha256"], new["contentSha256"])
        exported = {r["contentSha256"]: r for r in self.query(export_votes, {})}
        self.assertEqual(exported[old["contentSha256"]]["content"], body()["content"])
        self.assertEqual(exported[old["contentSha256"]]["vote"], "down")
        self.assertEqual(exported[new["contentSha256"]]["vote"], "up")

    def test_marks_are_scoped_to_their_step_and_game(self) -> None:
        self.vote()
        self.vote(stepIndex=15, sectionIndex=2, sectionLabel="ASSISTANT", content="I will click the fish.", vote="up")
        self.vote(gameIndex=4, content="Another game entirely.")
        self.assertEqual([v["stepIndex"] for v in self.listed()], [14, 15])
        self.assertEqual([v["sectionLabel"] for v in self.listed(step=15)], ["ASSISTANT"])
        self.assertEqual(self.listed(step=99), [])

    def test_export_is_a_training_record_and_filters(self) -> None:
        self.vote()
        self.vote(reviewer="son@example.com", stepIndex=15, content="Click the crate.", vote="up", reason=None)
        records = self.query(export_votes, {})
        self.assertEqual(len(records), 2)
        record = records[0]
        self.assertEqual(
            (record["run"], record["gameId"], record["gameIndex"], record["stepIndex"], record["turn"],
             record["sectionIndex"], record["sectionLabel"], record["vote"], record["value"], record["reviewer"]),
            (RUN, "g042", 3, 14, 9, 5, "THINKING", "down", -1, "mark@example.com"),
        )
        self.assertEqual(record["content"], body()["content"])
        self.assertEqual(record["contentSha256"], content_sha256(record["content"]))
        self.assertEqual(record["reason"], body()["reason"])
        self.assertNotIn("mine", record)

        self.assertEqual([r["vote"] for r in self.query(export_votes, {"vote": ["up"]})], ["up"])
        self.assertEqual(len(self.query(export_votes, {"reviewer": ["Son@Example.com"]})), 1)
        self.assertEqual(self.query(export_votes, {"run": ["some-other-run"]}), [])
        self.assertEqual(len(self.query(export_votes, {"since": ["2020-01-01T00:00:00Z"]})), 2)
        self.assertEqual(self.query(export_votes, {"since": ["2999-01-01T00:00:00Z"]}), [])
        self.assertNotIn("content", self.query(export_votes, {"content": ["0"]})[0])
        with self.assertRaises(TraceFeedbackProblem):
            self.query(export_votes, {"since": ["yesterday"]})

    def test_the_http_surface_end_to_end(self) -> None:
        def call(method: str, path: str, headers: dict, payload: bytes = b""):
            headers = Headers(headers)
            if payload:
                headers["Content-Length"] = str(len(payload))
            return self.api.handle(method, path, headers, lambda n: payload[:n])

        who = {"X-Forwarded-Email": "Mark@Example.com"}
        saved = call("POST", "/api/v1/traces/feedback", who, json.dumps(body()).encode())
        self.assertEqual((saved.status, json.loads(saved.body)["reviewer"]), (200, "mark@example.com"))

        listed = json.loads(call("GET", f"/api/v1/traces/feedback?run={RUN}&game=3&step=14", who).body)
        self.assertEqual((listed["me"], len(listed["votes"]), listed["votes"][0]["mine"]), ("mark@example.com", 1, True))

        for response in (
            call("GET", "/api/v1/traces/feedback-export", {"Authorization": "Bearer secret-token"}),
            call("GET", "/api/v1/traces/feedback?format=jsonl", who),
        ):
            self.assertEqual((response.status, response.content_type), (200, "application/x-ndjson; charset=utf-8"))
            lines = response.body.decode().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["content"], body()["content"])

        cleared = call("POST", "/api/v1/traces/feedback", who, json.dumps(body(vote=None)).encode())
        self.assertEqual(json.loads(cleared.body)["status"], "cleared")
        empty = call("GET", "/api/v1/traces/feedback-export", {"Authorization": "Bearer secret-token"})
        self.assertEqual(empty.body, b"")


if __name__ == "__main__":
    unittest.main()

"""Tests for railway/games_store.py: the Games page's evolution trees and feedback API.

The pure checks (validation, rate limiting, line numbering, who may call what) always run.
The database round trip runs only when ARC3_TEST_DATABASE_URL points at a disposable Postgres:
it DROPS and recreates the arc3_game* tables there, so never point it at a real catalog.

    python -m unittest scripts.test_games_store
    ARC3_TEST_DATABASE_URL=postgresql://... python -m unittest scripts.test_games_store
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from railway.games_store import (
    GamesApi,
    GamesProblem,
    SlidingWindowLimiter,
    assign_lines,
    clean_comment,
    clean_feedback,
    clean_publication,
    export_feedback,
    insert_comment,
    insert_feedback,
    list_comments,
    list_ideas,
    list_trees,
    next_version,
    publish_version,
    set_train_ok,
    training_set,
    tree_detail,
    tree_notes,
    update_idea,
    upsert_ideas,
)

ROOT = Path(__file__).resolve().parents[1]
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def source(tag: str) -> bytes:
    return f"from arcengine import ARCBaseGame\n\nclass Game(ARCBaseGame):\n    TAG = {tag!r}\n".encode()


def upload(game_id: str, tag: str, **version) -> dict:
    body = source(tag)
    return {
        "game": {"game_id": game_id, "family": version.pop("family", "custom"), "title": version.pop("title", None)},
        "version": {
            "source_b64": base64.b64encode(body).decode(),
            "src_file": "game.py",
            "class_name": "Game",
            "reason": version.pop("reason", f"make {tag}"),
            **version,
        },
    }


def vid(game_id: str, tag: str) -> str:
    return f"{game_id}@{hashlib.sha256(source(tag)).hexdigest()[:12]}"


class Headers(dict):
    def get(self, key, default=None):  # case-insensitive like http.client's message
        for name, value in self.items():
            if name.lower() == key.lower():
                return value
        return default


class ValidationTests(unittest.TestCase):
    def test_publication_is_content_addressed(self) -> None:
        item = clean_publication(upload("ng01", "a"))
        self.assertEqual(item["version_id"], vid("ng01", "a"))
        self.assertEqual(item["sha256"], hashlib.sha256(source("a")).hexdigest())

    def test_publication_rejects_bad_input(self) -> None:
        cases = [
            ({"sha256": "0" * 64}, "sha256_mismatch"),
            ({"thumb_png_b64": base64.b64encode(b"GIF89a").decode()}, "invalid_thumbnail"),
            ({"kind": "seed", "parent_version_id": vid("ng01", "a")}, "invalid_kind"),
            ({"src_file": "../../etc/passwd"}, "invalid_src_file"),
            ({"author": {"kind": "robot"}}, "invalid_author_kind"),
            ({"reason": "   "}, "missing_reason"),
        ]
        for override, code in cases:
            payload = upload("ng01", "a")
            payload["version"].update(override)
            with self.subTest(code=code):
                with self.assertRaises(GamesProblem) as caught:
                    clean_publication(payload)
                self.assertEqual(caught.exception.code, code)
        payload = upload("../x", "a")
        with self.assertRaises(GamesProblem):
            clean_publication(payload)

    def test_feedback_needs_substance_and_valid_fields(self) -> None:
        base = {"game_id": "g009", "version_id": vid("g009", "a")}
        with self.assertRaises(GamesProblem) as caught:
            clean_feedback(base)
        self.assertEqual(caught.exception.code, "empty_feedback")
        self.assertEqual(clean_feedback({**base, "fun": 4})["fun"], 4)
        for bad in ({"fun": 6}, {"fun": True}, {"flags": ["hacked"]}, {"outcome": "rage_quit"}, {"verdict": "burn"}):
            with self.subTest(bad=bad):
                with self.assertRaises(GamesProblem):
                    clean_feedback({**base, "fun": 3, **bad})
        with self.assertRaises(GamesProblem) as caught:
            clean_feedback({**base, "fun": 3, "website": "spam.example"})
        self.assertEqual(caught.exception.code, "rejected")
        with self.assertRaises(GamesProblem) as caught:
            clean_feedback({"game_id": "g010", "version_id": vid("g009", "a"), "fun": 3})
        self.assertEqual(caught.exception.code, "version_game_mismatch")

    def test_feedback_version_can_come_from_the_played_bytes(self) -> None:
        digest = hashlib.sha256(source("a")).hexdigest()
        item = clean_feedback({"game_id": "g009", "source_sha256": digest, "flags": ["enjoyed_it", "solved_it"]})
        self.assertEqual(item["version_id"], vid("g009", "a"))
        self.assertEqual(item["flags"], ["solved_it", "enjoyed_it"])  # canonical order, deduped

    def test_limiter_blocks_then_forgets(self) -> None:
        limiter = SlidingWindowLimiter(2, 10)
        self.assertTrue(limiter.allow("v", now=0))
        self.assertTrue(limiter.allow("v", now=1))
        self.assertFalse(limiter.allow("v", now=2))
        self.assertTrue(limiter.allow("other", now=2))
        self.assertTrue(limiter.allow("v", now=11.5))


class LineTests(unittest.TestCase):
    def test_revisions_continue_a_line_even_across_ids_and_branches_start_one(self) -> None:
        rows = [
            {"version_id": "q1-v1@a", "parent_version_id": None, "kind": "seed"},
            {"version_id": "q1-v1@b", "parent_version_id": "q1-v1@a", "kind": "revision"},
            {"version_id": "q1-v2@c", "parent_version_id": "q1-v1@b", "kind": "revision"},
            {"version_id": "g5@d", "parent_version_id": "q1-v1@b", "kind": "branch"},
            {"version_id": "g5@e", "parent_version_id": "g5@d", "kind": "revision"},
            {"version_id": "x@f", "parent_version_id": "hidden@z", "kind": "revision"},
        ]
        lines = assign_lines(rows)
        self.assertEqual(lines["q1-v2@c"], ("q1-v1@a", 3))
        self.assertEqual(lines["g5@d"], ("g5@d", 1))
        self.assertEqual(lines["g5@e"], ("g5@d", 2))
        self.assertEqual(lines["x@f"], ("x@f", 1))  # orphan keeps its own line instead of vanishing


class RouteAuthTests(unittest.TestCase):
    """Who may call what, checked before any database access (connect() must never run)."""

    def setUp(self) -> None:
        def no_database():
            raise AssertionError("the database must not be touched")

        self.api = GamesApi(no_database, Path(tempfile.gettempdir()), "secret-token")

    def call(self, method: str, path: str, headers: dict, body: bytes = b"") -> tuple[int, dict]:
        headers = Headers(headers)
        if body:
            headers["Content-Length"] = str(len(body))
        response = self.api.handle(method, path, headers, lambda n: body[:n])
        return response.status, json.loads(response.body)

    def test_team_routes_need_the_proxy_identity(self) -> None:
        for method, path in (
            ("GET", "/api/v1/games/me"),
            ("GET", "/api/v1/games/trees/ng01/notes"),
            ("GET", "/api/v1/games/next"),
            ("GET", "/api/v1/games/feedback"),
            ("POST", "/api/v1/games/feedback"),
            ("POST", "/api/v1/games/feedback/3/hidden"),
            ("GET", "/api/v1/games/ideas"),
            ("POST", "/api/v1/games/ideas/gpt:q001"),
        ):
            with self.subTest(path=path):
                status, body = self.call(method, path, {})
                self.assertEqual((status, body["error"]), (401, "sign_in_required"))

    def test_me_echoes_the_proxy_identity(self) -> None:
        status, body = self.call("GET", "/api/v1/games/me", {"X-Forwarded-Email": "Son@Example.com"})
        self.assertEqual((status, body["email"], body["reviewerClass"]), (200, "son@example.com", "team"))

    def test_machine_routes_need_the_token(self) -> None:
        for headers in ({}, {"Authorization": "Bearer wrong"}, {"X-Forwarded-Email": "son@example.com"}):
            for method, path in (
                ("PUT", "/api/v1/games/publication"),
                ("GET", "/api/v1/games/feedback-export"),
                ("PUT", "/api/v1/games/ideas/publication"),
            ):
                with self.subTest(path=path, headers=headers):
                    status, body = self.call(method, path, headers)
                    self.assertEqual((status, body["error"]), (401, "unauthorized"))

    def test_public_prefix_never_reaches_team_handlers(self) -> None:
        status, body = self.call("GET", "/api/v1/public/games/me", {"X-Forwarded-Email": "son@example.com"})
        self.assertEqual((status, body["error"]), (404, "not_found"))
        status, body = self.call(
            "POST", "/api/v1/public/games/feedback", {"X-Forwarded-Email": "son@example.com"}, b'{"game_id":"g1"}'
        )
        self.assertEqual(status, 400)  # validated as a public review; the header is never read

    def test_owns_only_the_games_prefixes(self) -> None:
        self.assertTrue(GamesApi.owns("/api/v1/games/me"))
        self.assertTrue(GamesApi.owns("/api/v1/public/games/trees"))
        self.assertFalse(GamesApi.owns("/api/v1/runs/x/publication"))
        self.assertFalse(GamesApi.owns("/api/v1/gamesx"))


class ProxyConfigTests(unittest.TestCase):
    def test_entrypoint_opens_exactly_the_public_and_token_routes(self) -> None:
        entrypoint = (ROOT / "railway" / "entrypoint.sh").read_text(encoding="utf-8")
        for route in (
            '--skip-auth-route="^/api/v1/public/"',
            '--skip-auth-route="^/api/v1/games/publication$"',
            '--skip-auth-route="^/api/v1/games/feedback-export$"',
            '--skip-auth-route="^/api/v1/games/ideas/publication$"',
            '--skip-auth-route="^/data/_games/"',
        ):
            self.assertIn(route, entrypoint)
        self.assertNotIn('--skip-auth-route="^/api/v1/games/"', entrypoint)
        self.assertNotIn('--skip-auth-route="^/data/"', entrypoint)

    def test_server_ships_and_loads_the_games_module(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        server = (ROOT / "railway" / "catalog_server.py").read_text(encoding="utf-8")
        self.assertIn("COPY railway/games_store.py /games_store.py", dockerfile)
        self.assertIn("COPY railway/games_schema.sql /games_schema.sql", dockerfile)
        self.assertIn("if self.handle_games(\"POST\"):", server)
        self.assertIn('header /data/_games/* Cache-Control "public, max-age=31536000, immutable"',
                      (ROOT / "railway" / "Caddyfile").read_text(encoding="utf-8"))


@unittest.skipUnless(os.environ.get("ARC3_TEST_DATABASE_URL"), "set ARC3_TEST_DATABASE_URL to a disposable Postgres")
class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import psycopg2

        cls.url = os.environ["ARC3_TEST_DATABASE_URL"]
        cls.connect = staticmethod(lambda: psycopg2.connect(cls.url))
        with cls.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "DROP TABLE IF EXISTS arc3_game_comments, arc3_game_idea_games, arc3_game_ideas, "
                "arc3_game_version_parents, arc3_game_feedback, arc3_game_versions, arc3_games, "
                "arc3_game_trees CASCADE"
            )
            cursor.execute((ROOT / "railway" / "games_schema.sql").read_text(encoding="utf-8"))
        cls.data = Path(tempfile.mkdtemp(prefix="arc3-games-test-"))

    def publish(self, payload: dict) -> dict:
        return publish_version(self.connect, self.data, payload)

    def query(self, fn, *args, **kwargs):
        connection = self.connect()
        try:
            with connection, connection.cursor() as cursor:
                return fn(cursor, *args, **kwargs)
        finally:
            connection.close()

    def test_a_tree_grows_revisions_renames_and_branches(self) -> None:
        png = base64.b64encode(PNG).decode()
        seed = self.publish(upload("q1-v1", "a", created_at="2026-09-01T00:00:00Z", family="ai-generated",
                                   thumb_png_b64=png, author={"kind": "gpt", "model": "GPT-5"}))
        self.assertEqual((seed["status"], seed["kind"], seed["treeId"]), ("published", "seed", "q1-v1"))
        self.assertTrue((self.data / "_games" / "q1-v1" / vid("q1-v1", "a")[-12:] / "game.py").read_bytes() == source("a"))

        again = self.publish(upload("q1-v1", "a"))
        self.assertEqual(again["status"], "unchanged")

        rev = self.publish(upload("q1-v1", "b", created_at="2026-09-02T00:00:00Z", author={"kind": "claude"}))
        self.assertEqual((rev["kind"], rev["parentVersionId"]), ("revision", vid("q1-v1", "a")))

        renamed = self.publish(upload("q1-v2", "c", created_at="2026-09-03T00:00:00Z", kind="revision",
                                      parent_version_id=vid("q1-v1", "b")))
        self.assertEqual((renamed["kind"], renamed["treeId"]), ("revision", "q1-v1"))

        branch = self.publish(upload("g500", "d", created_at="2026-09-04T00:00:00Z", family="contributed-glowup",
                                     title="A Spoiler Name", parent_version_id=vid("q1-v1", "b")))
        self.assertEqual((branch["kind"], branch["treeId"]), ("branch", "q1-v1"))

        for bad, code in (
            (upload("q1-v1", "z", parent_version_id=vid("g500", "d")), "parent_in_other_game"),
            (upload("q1-v1", "y", kind="branch"), "branch_needs_new_game"),
            (upload("q1-v1", "v", kind="seed"), "already_seeded"),
            (upload("q1-v1", "x", created_at="2026-08-01T00:00:00Z"), "created_before_parent"),
            (upload("n1", "w", parent_version_id="n1@000000000000"), "parent_not_found"),
        ):
            with self.subTest(code=code):
                with self.assertRaises(GamesProblem) as caught:
                    self.publish(bad)
                self.assertEqual(caught.exception.code, code)

        detail = self.query(tree_detail, "q1-v1")
        by_id = {v["versionId"]: v for v in detail["versions"]}
        self.assertEqual(detail["headVersionId"], vid("q1-v2", "c"))  # the renamed revision is the current one
        self.assertEqual(by_id[vid("q1-v2", "c")]["number"], 3)
        self.assertEqual((by_id[vid("g500", "d")]["number"], by_id[vid("g500", "d")]["isLineHead"]), (1, True))
        self.assertIsNotNone(by_id[vid("q1-v1", "a")]["thumbUrl"])
        g500 = next(g for g in detail["games"] if g["gameId"] == "g500")
        self.assertEqual(g500["title"], "g500")  # blind family: the name never reaches the page

        listing = self.query(list_trees, {"q": ["q1"]})
        tree = listing["trees"][0]
        self.assertEqual((tree["head"]["versionId"], tree["head"]["number"]), (vid("q1-v2", "c"), 3))
        self.assertEqual((tree["versionCount"], tree["branchCount"]), (4, 1))
        self.assertEqual(tree["authors"]["gpt"], 1)

        # Feedback: team reviews rank first, and a team reviewer is not sent back to what they reviewed.
        def review(cursor, cls, reviewer, version_id, **fields):
            item = clean_feedback({"game_id": version_id.split("@")[0], "version_id": version_id, **fields})
            return insert_feedback(cursor, item, reviewer_class=cls, reviewer=reviewer, ip_hint=None,
                                   static_game_ids=frozenset())

        self.query(review, "public", "anon", vid("q1-v2", "c"), fun=2)
        self.query(review, "team", "son@example.com", vid("q1-v2", "c"), fun=5, suggestion="more levels")
        with self.assertRaises(GamesProblem):
            self.query(review, "public", None, "zz9@000000000000", fun=1)  # not a playable game
        pick = self.query(next_version, {"pool": ["all"]}, reviewer="son@example.com")
        self.assertNotEqual(pick["version"]["versionId"], vid("q1-v2", "c"))
        records = self.query(lambda c: list(export_feedback(c, {"tree_id": ["q1-v1"]}, include_ip=False)))
        self.assertEqual([r["reviewerClass"] for r in records], ["team", "public"])
        self.assertEqual(records[0]["version"]["reason"], "make c")

    def test_a_crossover_keeps_both_parents_and_ideas_track_what_was_built(self) -> None:
        self.publish(upload("x-a", "xa", created_at="2026-09-01T00:00:00Z"))
        self.publish(upload("x-b", "xb", created_at="2026-09-01T00:00:00Z"))
        upsert = lambda payload: self.query(upsert_ideas, payload)  # noqa: E731
        seeded = upsert({"ideas": [
            {"idea_id": "test:one", "source": "test", "title": "One", "pitch": "Push blocks.", "game_ids": ["x-a"]},
            {"idea_id": "test:two", "source": "test", "title": "Two", "pitch": "Swap colours."},
            {"idea_id": "test:three", "source": "test", "title": "Three", "pitch": "Never built."},
        ]})
        self.assertEqual((seeded["inserted"], seeded["linked"]), (3, 1))

        child = self.publish(upload("x-c", "xc", created_at="2026-09-02T00:00:00Z",
                                    parent_version_ids=[vid("x-a", "xa"), vid("x-b", "xb")],
                                    idea_ids=["test:two"], author={"kind": "claude"}))
        self.assertEqual((child["kind"], child["treeId"], child["parentVersionId"]), ("branch", "x-a", vid("x-a", "xa")))
        detail = self.query(tree_detail, "x-a")
        crossover = next(v for v in detail["versions"] if v["gameId"] == "x-c")
        self.assertEqual(crossover["extraParentVersionIds"], [vid("x-b", "xb")])
        notes = self.query(tree_notes, "x-a")
        self.assertEqual([i["ideaId"] for i in notes["ideas"]["x-c"]], ["test:two"])
        with self.assertRaises(GamesProblem) as caught:
            self.publish(upload("x-d", "xd", parent_version_ids=[vid("x-a", "xa"), "x-z@000000000000"]))
        self.assertEqual(caught.exception.code, "parent_not_found")
        with self.assertRaises(GamesProblem) as caught:
            self.publish(upload("x-e", "xe", idea_ids=["test:nope"]))
        self.assertEqual(caught.exception.code, "idea_not_found")

        board = self.query(list_ideas, {"source": ["test"]})
        self.assertEqual(board["counts"], {"unexplored": 1, "exploring": 0, "explored": 2, "dropped": 0})
        self.query(update_idea, "test:three", {"status": "dropped", "note": "done before"}, email="son@example.com")
        upsert({"ideas": [{"idea_id": "test:three", "source": "test", "title": "Three", "pitch": "Reworded."}]})
        column = self.query(list_ideas, {"source": ["test"], "status": ["dropped"]})["ideas"]
        self.assertEqual([(i["ideaId"], i["pitch"], i["updatedBy"]) for i in column],
                         [("test:three", "Reworded.", "son@example.com")])  # re-seeding never undoes a move

    def test_comments_and_the_training_tick(self) -> None:
        self.publish(upload("c1-v1", "a", created_at="2026-09-05T00:00:00Z", family="evolution"))
        self.publish(upload("c1-v1", "b", created_at="2026-09-06T00:00:00Z"))
        first, second = vid("c1-v1", "a"), vid("c1-v1", "b")

        # A comment is free text about a game, optionally about one version.
        item = clean_comment({"game_id": "c1-v1", "version_id": second, "body": " level 2 drags "})
        self.assertEqual(item["body"], "level 2 drags")
        added = self.query(insert_comment, item, author="son@example.com")
        self.assertEqual((added["treeId"], added["versionId"]), ("c1-v1", second))
        self.query(insert_comment, clean_comment({"game_id": "c1-v1", "body": "the palette works"}), author="son@example.com")

        comments = self.query(list_comments, "c1-v1")
        self.assertEqual([c["body"] for c in comments], ["the palette works", "level 2 drags"])  # newest first
        self.assertEqual(comments[0]["author"], "son@example.com")

        for bad, code in (
            ({"game_id": "c1-v1"}, "missing_body"),
            ({"game_id": "c1-v1", "body": ""}, "missing_body"),
            ({"game_id": "c1-v1", "body": "x" * 2001}, "body_too_long"),
            ({"game_id": "c1-v1", "body": "x", "version_id": vid("other", "a")}, "version_game_mismatch"),
        ):
            with self.subTest(code=code):
                with self.assertRaises(GamesProblem) as caught:
                    clean_comment(bad)
                self.assertEqual(caught.exception.code, code)
        with self.assertRaises(GamesProblem) as caught:
            self.query(insert_comment, clean_comment({"game_id": "nope", "body": "hi"}), author="son@example.com")
        self.assertEqual(caught.exception.code, "game_not_found")

        # The tick is per version: ticking the new one leaves the old one alone.
        self.assertEqual(self.query(training_set)["count"], 0)
        ticked = self.query(set_train_ok, second, True, email="son@example.com")
        self.assertEqual((ticked["trainOk"], ticked["trainOkBy"]), (True, "son@example.com"))
        chosen = self.query(training_set)
        self.assertEqual([v["versionId"] for v in chosen["versions"]], [second])
        self.assertTrue(chosen["versions"][0]["sourceUrl"].startswith(f"/data/_games/c1-v1/{second[-12:]}/"))

        notes = self.query(tree_notes, "c1-v1")
        self.assertTrue(notes["notes"][second]["trainOk"])
        self.assertIsNone(notes["notes"][first]["trainOk"])
        self.assertEqual(len(notes["comments"]), 2)

        # Unticking clears the name with it, and an unknown version is a 404.
        self.assertFalse(self.query(set_train_ok, second, False, email="son@example.com")["trainOk"])
        self.assertEqual(self.query(training_set)["count"], 0)
        with self.assertRaises(GamesProblem) as caught:
            self.query(set_train_ok, "c1-v1@000000000000", True, email="son@example.com")
        self.assertEqual(caught.exception.code, "version_not_found")


if __name__ == "__main__":
    unittest.main()

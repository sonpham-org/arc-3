"""Tests for railway/rl_review.py: trace review (raters compare paths forward from one point) and the RL data.

The pure checks (validation, who may call what, what the image and the pages ship) always run. The database round
trip runs only when ARC3_TEST_DATABASE_URL points at a disposable Postgres: it DROPS and recreates the rl_review_*
tables there, so never point it at a real catalog.

    python3.13 -m unittest scripts.test_rl_review
    ARC3_TEST_DATABASE_URL=postgresql://... python3.13 -m unittest scripts.test_rl_review
"""

from __future__ import annotations

import gzip
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

from railway.rl_review import (
    RlReviewApi,
    ReviewProblem,
    _order,
    clean_rating,
    pair_priority,
)

ROOT = Path(__file__).resolve().parents[1]
PATHS = ["run-a:ka59_p0:L2", "run-a:ka59_p1:L2"]
TEAM = "son@example.com"


class Headers(dict):
    def get(self, key, default=None):
        for k, v in self.items():
            if k.lower() == key.lower():
                return v
        return default


def no_db():
    raise AssertionError("this request must be refused before any database work")


def call(api, method, path, headers=None, body=None):
    raw = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    h = Headers(headers or {})
    if raw:
        h["Content-Length"] = str(len(raw))
    response = api.handle(method, path, h, lambda n: raw[:n])
    try:
        payload = json.loads(response.body.decode("utf-8")) if response.body else None
    except json.JSONDecodeError:
        payload = response.body
    return response.status, payload


class RatingValidation(unittest.TestCase):
    def test_a_full_rating_is_kept(self) -> None:
        item = clean_rating({"choice": PATHS[1], "confidence": 2, "scores": {PATHS[0]: 2, PATHS[1]: 5},
                             "marks": [{"path": PATHS[0], "step": 7, "verdict": "down", "note": "walked into the wall"}],
                             "comment": "right side tested the rule first", "seconds": 95}, PATHS)
        self.assertEqual(item["choice"], PATHS[1])
        self.assertEqual(item["marks"][0]["note"], "walked into the wall")

    def test_tie_and_neither_are_answers(self) -> None:
        for choice in ("tie", "neither"):
            self.assertEqual(clean_rating({"choice": choice}, PATHS)["choice"], choice)

    def test_bad_ratings_are_refused(self) -> None:
        bad = [
            {"choice": "run-a:ka59_p9:L2"},
            {"choice": PATHS[0], "confidence": 4},
            {"choice": PATHS[0], "confidence": True},
            {"choice": PATHS[0], "scores": {PATHS[0]: 6}},
            {"choice": PATHS[0], "scores": {"other": 3}},
            {"choice": PATHS[0], "marks": [{"path": "other", "step": 1, "verdict": "up"}]},
            {"choice": PATHS[0], "marks": [{"path": PATHS[0], "step": -1, "verdict": "up"}]},
            {"choice": PATHS[0], "marks": [{"path": PATHS[0], "step": 1, "verdict": "maybe"}]},
            {"choice": PATHS[0], "seconds": 10**6},
            {"choice": PATHS[0], "comment": "x" * 5000},
            [],
        ]
        for payload in bad:
            with self.assertRaises(ReviewProblem, msg=str(payload)[:80]):
                clean_rating(payload, PATHS)

    def test_an_empty_mark_is_dropped(self) -> None:
        item = clean_rating({"choice": "tie", "marks": [{"path": PATHS[0], "step": 3, "verdict": None, "note": " "}]},
                            PATHS)
        self.assertEqual(item["marks"], [])


class Ordering(unittest.TestCase):
    def test_left_right_is_fixed_per_rater_and_differs_across_raters(self) -> None:
        self.assertEqual(_order(PATHS, "team:a@x.io", "s1"), _order(PATHS, "team:a@x.io", "s1"))
        orders = {tuple(_order(PATHS, f"r_{i:012x}", "s1")) for i in range(40)}
        self.assertEqual(len(orders), 2, "position must not stand for anything: both orders should occur")

    def test_pairs_across_models_and_outcomes_come_first(self) -> None:
        base = {"model": "base", "cleared": True, "actions": 40}
        same = pair_priority(base, {"model": "base", "cleared": True, "actions": 40})
        outcome = pair_priority(base, {"model": "base", "cleared": False, "actions": 40})
        model = pair_priority(base, {"model": "r0", "cleared": True, "actions": 40})
        self.assertLess(same, outcome)
        self.assertLess(outcome, model)


class Access(unittest.TestCase):
    """Who may call what, checked before any database access (connect() must never run)."""

    def setUp(self) -> None:
        os.environ["ALLOWED_EMAILS"] = f"{TEAM}, mark@example.com"
        self.api = RlReviewApi(no_db, Path(tempfile.mkdtemp()), "secret-token")

    def test_routes_it_owns(self) -> None:
        for path in ("/api/v1/review/next", "/api/v1/public/review/next", "/api/v1/rl/dashboard",
                     "/api/v1/review/publication"):
            self.assertTrue(RlReviewApi.owns(path), path)
        for path in ("/api/v1/reviewer", "/api/v1/traces/feedback", "/api/v1/public/games/feedback"):
            self.assertFalse(RlReviewApi.owns(path), path)

    def test_team_routes_need_a_team_email(self) -> None:
        self.assertEqual(call(self.api, "GET", "/api/v1/review/next")[0], 401)
        status, payload = call(self.api, "GET", "/api/v1/review/next", {"X-Forwarded-Email": "stranger@gmail.com"})
        self.assertEqual((status, payload["error"]), (403, "not_on_team"))
        self.assertEqual(call(self.api, "GET", "/api/v1/rl/dashboard")[0], 401)

    def test_machine_routes_need_the_token(self) -> None:
        for method, path in (("PUT", "/api/v1/review/publication"), ("GET", "/api/v1/review/export"),
                             ("PUT", "/api/v1/rl/dashboard-publication")):
            self.assertEqual(call(self.api, method, path, {"Authorization": "Bearer nope"}, {"x": 1})[0], 401, path)
            # a signed-in team member is not a machine either
            self.assertEqual(call(self.api, method, path, {"X-Forwarded-Email": TEAM}, {"x": 1})[0], 401, path)

    def test_public_routes_need_a_well_formed_key_first(self) -> None:
        self.assertEqual(call(self.api, "GET", "/api/v1/public/review/next")[0], 401)
        self.assertEqual(call(self.api, "GET", "/api/v1/public/review/next", {"X-Review-Key": "short"})[0], 401)
        # the forwarded email is never trusted on the public prefix
        self.assertEqual(call(self.api, "GET", "/api/v1/public/review/next", {"X-Forwarded-Email": TEAM})[0], 401)

    def test_dashboard_round_trip_on_disk(self) -> None:
        api = RlReviewApi(no_db, Path(tempfile.mkdtemp()), "secret-token")
        doc = {"updated": "2026-10-02T18:00:00Z", "train": {"done": 3}}
        status, _ = call(api, "PUT", "/api/v1/rl/dashboard-publication", {"Authorization": "Bearer secret-token"},
                         gzip.compress(json.dumps(doc).encode()))
        self.assertEqual(status, 200)
        status, payload = call(api, "GET", "/api/v1/rl/dashboard", {"X-Forwarded-Email": TEAM})
        self.assertEqual((status, payload), (200, doc))


class ShippedFiles(unittest.TestCase):
    def test_skip_auth_routes_are_exact(self) -> None:
        entry = (ROOT / "railway" / "entrypoint.sh").read_text(encoding="utf-8")
        for route in ("^/review\\.html$", "^/api/v1/review/publication$", "^/api/v1/review/export$",
                      "^/api/v1/rl/dashboard-publication$"):
            self.assertIn(f'--skip-auth-route="{route}"', entry)
        # nothing that would open the team routes or the RL data
        for pattern in re.findall(r'--skip-auth-route="([^"]+)"', entry):
            self.assertFalse(pattern.startswith("^/api/v1/review/") and not pattern.endswith("$"), pattern)
            self.assertNotIn(pattern, ("^/api/v1/review/", "^/api/v1/rl/", "^/api/v1/rl/dashboard$"))

    def test_image_ships_the_module_and_pages(self) -> None:
        docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY railway/rl_review.py /rl_review.py", docker)
        self.assertIn("RlReviewApi", (ROOT / "railway" / "catalog_server.py").read_text(encoding="utf-8"))
        for page in ("review.html", "rl.html", "tree.html"):
            self.assertTrue((ROOT / "docs" / page).is_file(), page)

    def test_site_nav_has_rl_and_review_not_harness_lab(self) -> None:
        pages = [p for p in (ROOT / "docs").glob("*.html") if 'class="sitetabs"' in p.read_text(encoding="utf-8")]
        self.assertGreater(len(pages), 5)
        for page in pages:
            text = page.read_text(encoding="utf-8")
            nav = text[text.index('class="sitetabs"'):]
            nav = nav[:nav.index("</nav>")]
            self.assertIn('href="./rl.html"', nav, page.name)
            self.assertIn('href="./review.html"', nav, page.name)
            self.assertIn('href="./tree.html"', nav, page.name)
            self.assertNotIn("Harness Lab", nav, page.name)


@unittest.skipUnless(os.environ.get("ARC3_TEST_DATABASE_URL"), "set ARC3_TEST_DATABASE_URL to a disposable Postgres")
class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import psycopg2

        cls.url = os.environ["ARC3_TEST_DATABASE_URL"]
        cls.connect = staticmethod(lambda: psycopg2.connect(cls.url))
        schema = (ROOT / "railway" / "catalog_schema.sql").read_text(encoding="utf-8")
        with cls.connect() as connection, connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS rl_review_ratings, rl_review_raters, rl_review_splits, "
                           "rl_review_paths, rl_review_nodes CASCADE")
            cursor.execute(schema)
            cursor.execute(schema)  # the server re-runs the schema on every start

    def setUp(self) -> None:
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute("TRUNCATE rl_review_ratings, rl_review_raters, rl_review_splits, rl_review_paths, "
                           "rl_review_nodes RESTART IDENTITY CASCADE")
        os.environ["ALLOWED_EMAILS"] = TEAM
        os.environ.pop("ARC3_REVIEW_FENCED", None)
        self.root = Path(tempfile.mkdtemp())
        self.api = RlReviewApi(self.connect, self.root, "secret-token")
        self.machine = {"Authorization": "Bearer secret-token"}
        self.team = {"X-Forwarded-Email": TEAM}

    @staticmethod
    def content(level: int, n: int, tag: str = "run-a") -> dict:
        return {"level": level, "start": ["0" * 64] * 64,
                "turns": [{"step": s, "thinking": f"{tag} turn {s}", "said": "", "code": [f"action('UP') # {s}"],
                           "moves": [{"n": s, "action": "UP", "changed": True, "level_up": False, "diff": {}}]}
                          for s in range(1, n + 1)]}

    def bundle(self, run: str = "run-a", model: str = "base", game: str = "ka59", plays=(0, 1, 2), level: int = 1,
               kind: str = "level_start") -> dict:
        node = f"{game}:L{level}:abc123" if kind == "level_start" else f"{run}:{game}_p0:T7"
        paths = [{"id": f"{run}:{game}_p{k}:L{level}" + ("" if kind == "level_start" else ":b"), "node": node, "run": run,
                  "play": f"{game}_p{k}", "model": model, "level": level, "cleared": k % 2 == 0, "turns": 3 + k,
                  "actions": 10 + 5 * k, "first_action": 20, "last_action": 30 + 5 * k,
                  "content": self.content(level, 3 + k, run)} for k in plays]
        return {"source": "test", "nodes": [{"id": node, "kind": kind, "game": game, "level": level,
                                             "meta": {"start": ["0" * 64] * 64}}], "paths": paths}

    def publish(self, bundle: dict, gz: bool = True):
        raw = json.dumps(bundle).encode()
        return call(self.api, "PUT", "/api/v1/review/publication", self.machine, gzip.compress(raw) if gz else raw)

    def test_publication_makes_every_pair_once(self) -> None:
        status, result = self.publish(self.bundle())
        self.assertEqual((status, result["paths"], result["splitsMade"]), (200, 3, 3))
        self.assertEqual(self.publish(self.bundle(), gz=False)[1]["splitsMade"], 0, "republishing is idempotent")
        # a LoRA run of the same game reaches the same level start: new cross-model pairs, and they come first
        status, result = self.publish(self.bundle(run="run-b", model="r0", plays=(0,)))
        self.assertEqual(result["splitsMade"], 3)
        status, view = call(self.api, "GET", "/api/v1/review/next", self.team)
        self.assertEqual(status, 200)
        self.assertEqual(sorted(p["model"] for p in view["paths"]), ["base", "r0"])
        self.assertEqual(len(list((self.root / "_review" / "paths").glob("*.json"))), 4)

    def test_pairs_only_where_the_context_is_shared(self) -> None:
        # a later level start is the same board reached with different histories: no pairs
        status, result = self.publish(self.bundle(level=2))
        self.assertEqual((status, result["splitsMade"]), (200, 0))
        # a fork shares the forked play's history: its branches are paired
        status, result = self.publish(self.bundle(run="run-f", kind="fork", level=2))
        self.assertEqual((status, result["splitsMade"]), (200, 3))
        _, view = call(self.api, "GET", "/api/v1/review/next", self.team)
        self.assertEqual(view["node"]["kind"], "fork")

    def test_held_out_games_are_refused_whole(self) -> None:
        status, payload = self.publish(self.bundle(game="tn36"))
        self.assertEqual((status, payload["error"]), (422, "fenced_game"))
        status, stats = call(self.api, "GET", "/api/v1/review/stats", self.team)
        self.assertEqual((stats["nodes"], stats["paths"]), (0, 0))

    def test_rate_next_and_export(self) -> None:
        self.publish(self.bundle())
        _, view = call(self.api, "GET", "/api/v1/review/next", self.team)
        split, left, right = view["split"]["id"], view["paths"][0]["id"], view["paths"][1]["id"]
        status, content = call(self.api, "GET", f"/api/v1/review/path?id={left}", self.team)
        self.assertEqual((status, content["turns"][0]["thinking"]), (200, "run-a turn 1"))
        status, saved = call(self.api, "POST", "/api/v1/review/rating", self.team, {
            "split": split, "choice": right, "confidence": 3, "scores": {left: 2, right: 4},
            "marks": [{"path": left, "step": 2, "verdict": "down", "note": "repeats a failed move"}],
            "comment": "right side reads the rule", "seconds": 61})
        self.assertEqual((status, saved["choice"]), (200, right))
        _, again = call(self.api, "GET", "/api/v1/review/next", self.team)
        self.assertNotEqual(again["split"]["id"], split, "a rated split is not served again to the same rater")
        _, mine = call(self.api, "GET", f"/api/v1/review/split?id={split}", self.team)
        self.assertEqual(mine["mine"]["choice"], right)
        status, body = call(self.api, "GET", "/api/v1/review/export", self.machine)
        lines = [json.loads(x) for x in body.decode().splitlines()] if isinstance(body, bytes) else [body]
        self.assertEqual(len(lines), 1)
        self.assertEqual((lines[0]["raterKind"], lines[0]["choice"], len(lines[0]["paths"])), ("team", right, 2))
        self.assertEqual(lines[0]["marks"][0]["note"], "repeats a failed move")

    def test_outside_rater_invite_rate_and_revoke(self) -> None:
        self.publish(self.bundle())
        status, invite = call(self.api, "POST", "/api/v1/review/raters", self.team, {"name": "Ada (outside)"})
        self.assertEqual(status, 200)
        key = {"X-Review-Key": invite["key"]}
        status, me = call(self.api, "GET", "/api/v1/public/review/me", key)
        self.assertEqual((status, me["name"], me["team"]), (200, "Ada (outside)", False))
        _, view = call(self.api, "GET", "/api/v1/public/review/next", key)
        status, _ = call(self.api, "POST", "/api/v1/public/review/rating", key,
                         {"split": view["split"]["id"], "choice": "neither", "comment": "both loop"})
        self.assertEqual(status, 200)
        # outside raters cannot see stats or manage raters
        self.assertEqual(call(self.api, "GET", "/api/v1/public/review/stats", key)[0], 404)
        status, raters = call(self.api, "GET", "/api/v1/review/raters", self.team)
        self.assertEqual(raters["raters"][0]["ratings"], 1)
        call(self.api, "POST", "/api/v1/review/raters/revoke", self.team, {"raterId": invite["raterId"]})
        self.assertEqual(call(self.api, "GET", "/api/v1/public/review/me", key)[0], 401)

    def test_rating_a_path_outside_the_split_is_refused(self) -> None:
        self.publish(self.bundle())
        _, view = call(self.api, "GET", "/api/v1/review/next", self.team)
        status, payload = call(self.api, "POST", "/api/v1/review/rating", self.team,
                               {"split": view["split"]["id"], "choice": "run-z:ka59_p7:L1"})
        self.assertEqual((status, payload["error"]), (400, "invalid_choice"))

    def test_tree_links_levels_and_counts_ratings(self) -> None:
        self.publish(self.bundle())
        # the same plays' next level: p0 and p2 cleared level 2 (even k), so their level-3 paths follow from a new node
        nxt = {"source": "test", "nodes": [{"id": "ka59:L2:def456", "kind": "level_start", "game": "ka59", "level": 2}],
               "paths": [{"id": f"run-a:ka59_p{k}:L2", "node": "ka59:L2:def456", "run": "run-a", "play": f"ka59_p{k}",
                          "model": "base", "level": 2, "cleared": False, "turns": 2, "actions": 4,
                          "content": self.content(2, 2, f"run-a-{k}")} for k in (0, 2)]}
        self.publish(nxt)
        _, view = call(self.api, "GET", "/api/v1/review/next", self.team)
        winner = view["paths"][0]["id"]
        call(self.api, "POST", "/api/v1/review/rating", self.team, {"split": view["split"]["id"], "choice": winner,
             "marks": [{"path": winner, "step": 1, "verdict": "up", "note": "good probe"}]})
        status, tree = call(self.api, "GET", "/api/v1/review/tree?game=ka59", self.team)
        self.assertEqual(status, 200)
        self.assertEqual([n["level"] for n in tree["nodes"]], [1, 2])
        paths = {p["id"]: p for p in tree["paths"]}
        self.assertEqual(paths["run-a:ka59_p0:L1"]["next"], "ka59:L2:def456")
        self.assertIsNone(paths["run-a:ka59_p1:L1"]["next"], "a path that did not clear leads nowhere")
        self.assertEqual(paths[winner]["wins"], 1)
        self.assertEqual(paths[winner]["marks"], {"up": 1, "down": 0, "notes": 1})
        self.assertEqual(sum(p["losses"] for p in tree["paths"]), 1)
        self.assertEqual(call(self.api, "GET", "/api/v1/review/tree?game=zz99", self.team)[0], 404)

    def test_stats_count_everything(self) -> None:
        self.publish(self.bundle())
        status, stats = call(self.api, "GET", "/api/v1/review/stats", self.team)
        self.assertEqual((status, stats["nodes"], stats["paths"], stats["splits"], stats["ratings"]), (200, 1, 3, 3, 0))
        self.assertEqual(stats["games"][0]["game"], "ka59")


if __name__ == "__main__":
    unittest.main()

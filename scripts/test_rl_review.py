"""Tests for railway/rl_review.py: trace review (raters compare paths forward from one point) and the RL data.

The pure checks (validation, who may call what, what the image and the pages ship) always run. The database round
trip runs only when ARC3_TEST_DATABASE_URL points at a disposable Postgres: it DROPS and recreates the rl_review_*
tables there, so never point it at a real catalog.

    python3.13 -m unittest scripts.test_rl_review
    ARC3_TEST_DATABASE_URL=postgresql://... python3.13 -m unittest scripts.test_rl_review
"""

from __future__ import annotations

import gzip
import hashlib
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
    clean_tree_bundle,
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


class Rl2Documents(unittest.TestCase):
    """RL2 named documents: PUT /api/v1/rl2/publication/<name> (token), GET /api/v1/rl2/doc/<name> (team)."""

    def setUp(self) -> None:
        os.environ["ALLOWED_EMAILS"] = TEAM
        self.root = Path(tempfile.mkdtemp())
        self.api = RlReviewApi(no_db, self.root, "secret-token")
        self.machine = {"Authorization": "Bearer secret-token"}
        self.team = {"X-Forwarded-Email": TEAM}

    def test_the_prefix_is_claimed(self) -> None:
        for path in ("/api/v1/rl2/doc/dashboard", "/api/v1/rl2/publication/run-a", "/api/v1/rl2"):
            self.assertTrue(RlReviewApi.owns(path), path)
        self.assertFalse(RlReviewApi.owns("/api/v1/rl2x/doc/dashboard"))

    def test_bad_names_are_refused_before_disk(self) -> None:
        bad = ["", "Dashboard", "../dashboard", "..", ".hidden", "-x", "a/b", "a%2Fb", "a b", "x" * 122, "a\\b"]
        for name in bad:
            for method, prefix, headers in (("PUT", "publication", self.machine), ("GET", "doc", self.team)):
                status, payload = call(self.api, method, f"/api/v1/rl2/{prefix}/{name}", headers, {"x": 1})
                self.assertIn(status, (400, 404), name)
                if status == 400:
                    self.assertEqual(payload["error"], "invalid_name", name)
        self.assertFalse((self.root / "_rl2").exists(), "nothing written for a bad name")
        self.assertEqual(call(self.api, "GET", "/api/v1/rl2/doc/../_rl/dashboard", self.team)[0], 400)

    def test_good_names(self) -> None:
        for name in ("dashboard", "run-daniel-coach-random50-a-1003", "a.b_c-1", "x" * 121):
            status, _ = call(self.api, "PUT", f"/api/v1/rl2/publication/{name}", self.machine, {"x": 1})
            self.assertEqual(status, 200, name)

    def test_publication_needs_the_token(self) -> None:
        path = "/api/v1/rl2/publication/dashboard"
        self.assertEqual(call(self.api, "PUT", path, {"Authorization": "Bearer nope"}, {"x": 1})[0], 401)
        self.assertEqual(call(self.api, "PUT", path, self.team, {"x": 1})[0], 401)
        self.assertEqual(call(self.api, "GET", path, self.machine)[0], 405)
        self.assertEqual(call(self.api, "PUT", path, self.machine, [1, 2])[0], 400)

    def test_docs_need_a_team_email(self) -> None:
        self.assertEqual(call(self.api, "GET", "/api/v1/rl2/doc/dashboard")[0], 401)
        self.assertEqual(call(self.api, "GET", "/api/v1/rl2/doc/dashboard", self.machine)[0], 401)
        status, payload = call(self.api, "GET", "/api/v1/rl2/doc/dashboard", self.team)
        self.assertEqual((status, payload["error"]), (404, "no_document"))

    def test_round_trip_on_disk(self) -> None:
        doc = {"generated_at": "2026-10-03T05:30:00Z", "builds": [{"id": "animft", "parent": None}]}
        run = {"run": "daniel-coach-a", "games": {"ka59": [{"d": 1, "mode": "probe"}]}}
        self.assertEqual(call(self.api, "PUT", "/api/v1/rl2/publication/dashboard", self.machine,
                              gzip.compress(json.dumps(doc).encode()))[0], 200)
        self.assertEqual(call(self.api, "PUT", "/api/v1/rl2/publication/run-daniel-coach-a", self.machine, run)[0], 200)
        self.assertEqual(call(self.api, "GET", "/api/v1/rl2/doc/dashboard", self.team), (200, doc))
        self.assertEqual(call(self.api, "GET", "/api/v1/rl2/doc/run-daniel-coach-a", self.team), (200, run))
        self.assertEqual(sorted(p.name for p in (self.root / "_rl2").iterdir()),
                         ["dashboard.json", "run-daniel-coach-a.json"], "no temp files left behind")


def tree_trace(tag: str, steps: int = 2) -> dict:
    return {"start": ["0" * 64] * 64,
            "turns": [{"step": s, "thinking": f"{tag} thinks {s}", "said": "", "code": [f"move('UP')  # {s}"],
                       "moves": [{"n": s, "action": "UP", "changed": True, "level_up": s == steps,
                                  "diff": {"3": "1" * 64}}]} for s in range(1, steps + 1)]}


def tree_sha(content: dict) -> str:
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


START = "ka59:L1:aaaaaaaaaaaa"
MID = "ka59:L1:bbbbbbbbbbbb"
NEXT = "ka59:L2:cccccccccccc"


def tree_bundle(run: str = "run-a", modes=("probe", "stock"), build: str = "animft/coach1", with_traces: bool = True) -> dict:
    """One run, one play per mode: START --mode--> MID --execute--> NEXT (level 2) --stock--> end."""

    nodes = [{"id": START, "game": "ka59", "level": 1, "board_hash": "a" * 12, "board": ["0" * 64] * 64},
             {"id": MID, "game": "ka59", "level": 1, "board_hash": "b" * 12, "board": None},
             {"id": NEXT, "game": "ka59", "level": 2, "board_hash": "c" * 12, "board": ["5" * 64] * 64}]
    branches, traces = [], {}
    for p, mode in enumerate(modes):
        content = tree_trace(f"{run}-{mode}")
        sha = tree_sha(content)
        traces[sha] = content
        play = f"ka59_p{p}"
        common = {"run": run, "play": play, "build": build, "policy": None}
        branches += [
            {**common, "id": f"{run}:{play}:d1", "node": START, "child": MID, "decision": 1, "mode": mode, "cap": 6,
             "prob": 0.5, "features": {"level": 1, "actions_in_level": 0}, "trace_sha": sha,
             "outcome": {"acts": 6, "lvl30": p == 0, "cleared_level": p == 0, "go_turn": False}},
            {**common, "id": f"{run}:{play}:d2", "node": MID, "child": NEXT, "decision": 2, "mode": "execute",
             "cap": 20, "prob": 0.9, "features": {"level": 1, "actions_in_level": 6}, "trace_sha": sha,
             "outcome": {"acts": 12, "lvl30": True, "cleared_level": True, "go_turn": False}},
            {**common, "id": f"{run}:{play}:d3", "node": NEXT, "child": None, "decision": 3, "mode": "stock",
             "cap": None, "prob": None, "features": {"level": 2, "actions_in_level": 0}, "trace_sha": None,
             "outcome": {"acts": 3, "lvl30": False, "cleared_level": None, "go_turn": True}},
        ]
    return {"run": run, "build": build, "policy": None, "nodes": nodes, "branches": branches,
            "traces": traces if with_traces else {}}


class Rl2Tree(unittest.TestCase):
    """RL2 decision tree: validation and who may call what, before any database work."""

    def setUp(self) -> None:
        os.environ["ALLOWED_EMAILS"] = TEAM
        self.root = Path(tempfile.mkdtemp())
        self.api = RlReviewApi(no_db, self.root, "secret-token")
        self.machine = {"Authorization": "Bearer secret-token"}
        self.team = {"X-Forwarded-Email": TEAM}

    def test_a_good_bundle_is_kept(self) -> None:
        item = clean_tree_bundle(tree_bundle())
        self.assertEqual((item["run"], len(item["nodes"]), len(item["branches"]), len(item["traces"])),
                         ("run-a", 3, 6, 2))
        self.assertEqual(item["branches"][0]["build"], "animft/coach1")
        sha, raw = next(iter(item["traces"].items()))
        self.assertEqual(hashlib.sha256(raw).hexdigest(), sha)

    def test_bad_bundles_are_refused(self) -> None:
        def mutate(fn):
            b = tree_bundle()
            fn(b)
            return b
        first_sha = lambda b: next(iter(b["traces"]))  # noqa: E731
        bad = {
            "invalid_body": [],
            "invalid_run": mutate(lambda b: b.update(run="../x")),
            "invalid_node": mutate(lambda b: b["nodes"][0].update(id="KA59:L1:aaaaaaaaaaaa")),
            "invalid_board": mutate(lambda b: b["nodes"][0].update(board=["zz"] * 64)),
            "invalid_child": mutate(lambda b: b["branches"][0].update(child="nowhere")),
            "invalid_mode": mutate(lambda b: b["branches"][0].update(mode="Probe!")),
            "invalid_prob": mutate(lambda b: b["branches"][0].update(prob=1.5)),
            "invalid_decision": mutate(lambda b: b["branches"][0].update(decision=-1)),
            "invalid_cap": mutate(lambda b: b["branches"][0].update(cap=True)),
            "invalid_features": mutate(lambda b: b["branches"][0].update(features={"x": "y" * 9000})),
            "invalid_branch": mutate(lambda b: b["branches"][0].update(id="run-b:ka59_p0:d1")),
            "duplicate_branch": mutate(lambda b: b["branches"].append(dict(b["branches"][0]))),
            "trace_sha_mismatch": mutate(lambda b: b["traces"][first_sha(b)]["turns"].append({"step": 9})),
            "invalid_trace": mutate(lambda b: b["traces"].update({first_sha(b): {"no": "turns"}})),
            "invalid_trace_sha": mutate(lambda b: b["branches"][0].update(trace_sha="abc")),
        }
        # the node id must agree with its game, level and board hash (key padded: same code as above)
        bad["invalid_node "] = mutate(lambda b: b["nodes"][0].update(level=2))
        for code, bundle in bad.items():
            with self.assertRaises(ReviewProblem, msg=code) as ctx:
                clean_tree_bundle(bundle)
            self.assertEqual(ctx.exception.code, code.strip(), code)

    def test_the_routes_are_claimed_and_guarded(self) -> None:
        for path in ("/api/v1/rl2/tree/games", "/api/v1/rl2/tree/publication", f"/api/v1/rl2/tree/node/{START}"):
            self.assertTrue(RlReviewApi.owns(path), path)
        pub = "/api/v1/rl2/tree/publication"
        self.assertEqual(call(self.api, "PUT", pub, {"Authorization": "Bearer nope"}, tree_bundle())[0], 401)
        self.assertEqual(call(self.api, "PUT", pub, self.team, tree_bundle())[0], 401)
        self.assertEqual(call(self.api, "GET", pub, self.machine)[0], 405)
        status, payload = call(self.api, "PUT", pub, self.machine, gzip.compress(json.dumps([1]).encode()))
        self.assertEqual((status, payload["error"]), (400, "invalid_body"))
        bad = tree_bundle()
        bad["branches"][0]["mode"] = "NOPE"
        self.assertEqual(call(self.api, "PUT", pub, self.machine, bad)[1]["error"], "invalid_mode",
                         "a bad body is refused before the database")
        for path in ("/api/v1/rl2/tree/games", f"/api/v1/rl2/tree/node/{START}", "/api/v1/rl2/tree/trace/" + "a" * 64):
            self.assertEqual(call(self.api, "GET", path)[0], 401, path)
            self.assertEqual(call(self.api, "GET", path, self.machine)[0], 401, path)
            self.assertEqual(call(self.api, "GET", path, {"X-Forwarded-Email": "x@gmail.com"})[0], 403, path)
            self.assertEqual(call(self.api, "PUT", path, self.team, {"x": 1})[0], 405, path)
        for path in ("/api/v1/rl2/tree/node/ka59:L1:short", "/api/v1/rl2/tree/node/../x",
                     "/api/v1/rl2/tree/trace/../../etc", "/api/v1/rl2/tree/trace/" + "A" * 64):
            self.assertEqual(call(self.api, "GET", path, self.team)[0], 400, path)
        self.assertEqual(call(self.api, "GET", "/api/v1/rl2/tree/trace/" + "a" * 64, self.team)[0], 404)
        self.assertEqual(call(self.api, "GET", "/api/v1/rl2/tree/nothing", self.team)[0], 404)

    def test_a_stored_trace_is_served(self) -> None:
        content = tree_trace("x")
        sha = tree_sha(content)
        (self.root / "_rl2" / "traces").mkdir(parents=True)
        (self.root / "_rl2" / "traces" / f"{sha}.json").write_bytes(json.dumps(content).encode())
        self.assertEqual(call(self.api, "GET", f"/api/v1/rl2/tree/trace/{sha}", self.team), (200, content))


class ShippedFiles(unittest.TestCase):
    def test_skip_auth_routes_are_exact(self) -> None:
        entry = (ROOT / "railway" / "entrypoint.sh").read_text(encoding="utf-8")
        for route in ("^/review\\.html$", "^/api/v1/review/publication$", "^/api/v1/review/export$",
                      "^/api/v1/rl/dashboard-publication$", "^/api/v1/rl2/publication/[a-z0-9][a-z0-9._-]*$",
                      "^/api/v1/rl2/tree/publication$"):
            self.assertIn(f'--skip-auth-route="{route}"', entry)
        # nothing that would open the team routes or the RL data
        for pattern in re.findall(r'--skip-auth-route="([^"]+)"', entry):
            self.assertFalse(pattern.startswith("^/api/v1/review/") and not pattern.endswith("$"), pattern)
            self.assertNotIn(pattern, ("^/api/v1/review/", "^/api/v1/rl/", "^/api/v1/rl/dashboard$", "^/api/v1/rl2/",
                                       "^/api/v1/rl2/doc/", "^/api/v1/rl2/tree/"))
            self.assertFalse(pattern.startswith("^/api/v1/rl2/doc"), pattern)
            self.assertFalse(pattern.startswith("^/api/v1/rl2/tree/") and pattern != "^/api/v1/rl2/tree/publication$",
                             pattern)

    def test_image_ships_the_module_and_pages(self) -> None:
        docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY railway/rl_review.py /rl_review.py", docker)
        self.assertIn("RlReviewApi", (ROOT / "railway" / "catalog_server.py").read_text(encoding="utf-8"))
        for page in ("review.html", "rl.html", "rl2.html", "tree.html"):
            self.assertTrue((ROOT / "docs" / page).is_file(), page)

    def test_site_nav_has_rl_and_review_not_harness_lab(self) -> None:
        pages = [p for p in (ROOT / "docs").glob("*.html") if 'class="sitetabs"' in p.read_text(encoding="utf-8")]
        self.assertGreater(len(pages), 5)
        for page in pages:
            text = page.read_text(encoding="utf-8")
            nav = text[text.index('class="sitetabs"'):]
            nav = nav[:nav.index("</nav>")]
            self.assertIn('href="./rl.html"', nav, page.name)
            self.assertIn('href="./rl2.html"', nav, page.name)
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


@unittest.skipUnless(os.environ.get("ARC3_TEST_DATABASE_URL"), "set ARC3_TEST_DATABASE_URL to a disposable Postgres")
class Rl2TreeDatabase(unittest.TestCase):
    """The RL2 tree round trip: publish runs, merge at shared nodes, read games, nodes and traces back."""

    @classmethod
    def setUpClass(cls) -> None:
        import psycopg2

        cls.url = os.environ["ARC3_TEST_DATABASE_URL"]
        cls.connect = staticmethod(lambda: psycopg2.connect(cls.url))
        schema = (ROOT / "railway" / "catalog_schema.sql").read_text(encoding="utf-8")
        with cls.connect() as connection, connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS rl2_tree_branches, rl2_tree_nodes CASCADE")
            cursor.execute(schema)
            cursor.execute(schema)  # the server re-runs the schema on every start

    def setUp(self) -> None:
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute("TRUNCATE rl2_tree_branches, rl2_tree_nodes")
        os.environ["ALLOWED_EMAILS"] = TEAM
        self.root = Path(tempfile.mkdtemp())
        self.api = RlReviewApi(self.connect, self.root, "secret-token")
        self.machine = {"Authorization": "Bearer secret-token"}
        self.team = {"X-Forwarded-Email": TEAM}

    def publish(self, bundle: dict, gz: bool = True):
        raw = json.dumps(bundle).encode()
        return call(self.api, "PUT", "/api/v1/rl2/tree/publication", self.machine, gzip.compress(raw) if gz else raw)

    def test_runs_merge_at_shared_nodes(self) -> None:
        status, result = self.publish(tree_bundle())
        self.assertEqual((status, result["nodes"], result["branches"], result["tracesWritten"]), (200, 3, 6, 2))
        # republishing the run replaces its branches; nothing doubles
        status, result = self.publish(tree_bundle(), gz=False)
        self.assertEqual((status, result["branches"], result["branchesReplaced"], result["tracesWritten"]),
                         (200, 6, 6, 0))
        # a second run, another build, reaches the same states: one start node, more branches
        self.assertEqual(self.publish(tree_bundle(run="run-b", modes=("rethink",), build="coach2"))[0], 200)
        status, games = call(self.api, "GET", "/api/v1/rl2/tree/games", self.team)
        self.assertEqual(status, 200)
        self.assertEqual([g["game"] for g in games["games"]], ["ka59"])
        levels = {lv["level"]: lv for lv in games["games"][0]["levels"]}
        self.assertEqual((levels[1]["nodes"], levels[1]["branches"], levels[1]["start_nodes"]), (2, 6, [START]))
        self.assertEqual(levels[2]["start_nodes"], [NEXT])

        status, view = call(self.api, "GET", f"/api/v1/rl2/tree/node/{START}", self.team)
        self.assertEqual(status, 200)
        self.assertEqual((view["node"]["branches"], view["node"]["arrivals"], view["parents"]), (3, 0, []))
        self.assertEqual(len(view["node"]["board"]), 64, "the first board is kept")
        self.assertEqual(view["by_mode"]["probe"], {"n": 1, "lvl30": 1.0, "cleared": 1.0, "acts": 6.0, "go": 0.0})
        self.assertEqual(view["by_mode"]["stock"]["lvl30"], 0.0)
        self.assertEqual(sorted(view["by_mode"]), ["probe", "rethink", "stock"])
        first = view["branches"][0]
        self.assertNotIn("content", first)
        self.assertEqual((first["child"], first["child_info"]["arrivals"], first["child_info"]["published"]),
                         (MID, 3, True), "three plays merged into the next node")

        status, mid = call(self.api, "GET", f"/api/v1/rl2/tree/node/{MID}", self.team)
        self.assertEqual((mid["node"]["arrivals"], mid["parents"], mid["by_mode"]["execute"]["n"]), (3, [START], 3))
        self.assertIsNone(mid["node"]["board"])
        _, last = call(self.api, "GET", f"/api/v1/rl2/tree/node/{NEXT}", self.team)
        self.assertIsNone(last["by_mode"]["stock"]["cleared"], "null outcomes are ignored")
        self.assertEqual(last["by_mode"]["stock"]["go"], 1.0)

        status, trace = call(self.api, "GET", f"/api/v1/rl2/tree/trace/{first['trace_sha']}", self.team)
        self.assertEqual((status, trace["turns"][0]["thinking"][-8:]), (200, "thinks 1"))
        self.assertEqual(call(self.api, "GET", "/api/v1/rl2/tree/node/zz99:L1:000000000000", self.team)[0], 404)

    def test_a_smaller_republication_drops_the_old_branches(self) -> None:
        self.publish(tree_bundle(modes=("probe", "stock", "search")))
        self.publish(tree_bundle(modes=("probe",)))
        _, view = call(self.api, "GET", f"/api/v1/rl2/tree/node/{START}", self.team)
        self.assertEqual([b["mode"] for b in view["branches"]], ["probe"])

    def test_branches_need_published_nodes_and_traces(self) -> None:
        orphan = tree_bundle()
        orphan["nodes"] = []
        status, payload = self.publish(orphan)
        self.assertEqual((status, payload["error"]), (400, "unknown_node"))
        base = tree_bundle()
        self.publish(base)
        # once the nodes and traces are stored, a later publication may refer to them without resending
        again = tree_bundle(run="run-c", with_traces=False)
        again["nodes"] = []
        for mine, stored in zip(again["branches"], base["branches"]):
            mine["trace_sha"] = stored["trace_sha"]
        status, result = self.publish(again)
        self.assertEqual((status, result["branches"]), (200, 6), result)
        missing = tree_bundle(run="run-d", modes=("brief",), with_traces=False)
        status, payload = self.publish(missing)
        self.assertEqual((status, payload["error"]), (400, "unknown_trace"))
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM rl2_tree_branches WHERE run = 'run-d'")
            self.assertEqual(cursor.fetchone()[0], 0, "a refused publication changes nothing")


if __name__ == "__main__":
    unittest.main()

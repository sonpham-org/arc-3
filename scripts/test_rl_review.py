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
from urllib.parse import quote

from railway.rl_review import (
    RlReviewApi,
    ReviewProblem,
    _order,
    clean_gtree_bundle,
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


SCREEN_A, SCREEN_B, SCREEN_C, SCREEN_D = "a" * 12, "b" * 12, "c" * 12, "d" * 12
ROOT_IDS = {k: f"ka59:t{k}:root" for k in (1, 2, 3, 4, 5)}
TREES = (1, 2, 3, 4, 5)


def gt_node(k: int, *parts) -> str:
    """The publisher's node id (any 16 hex will do for the server; this mimics hashing the node's key)."""

    return f"ka59:t{k}:" + hashlib.sha256("|".join(map(str, (k, *parts))).encode()).hexdigest()[:16]


def gt_nodes_at(level: int, moves: int, screen: str, path: tuple) -> dict:
    """A position's node in each tree: t1 the path of actions since the game start, t2 screen + moves, t3 level +
    screen, t4 screen, t5 level + screen + moves // 6 (the restart grid). The game start (empty path) is every tree's
    root."""

    if not path:
        return {f"n{k}": ROOT_IDS[k] for k in TREES}
    return {"n1": gt_node(1, *path), "n2": gt_node(2, screen, moves), "n3": gt_node(3, level, screen),
            "n4": gt_node(4, screen), "n5": gt_node(5, level, screen, moves // 6)}


def gt_node_rows(level: int, moves: int, screen: str, path: tuple) -> list:
    ids = gt_nodes_at(level, moves, screen, path)
    if not path:
        return [{"id": ids[f"n{k}"]} for k in TREES]
    parent = gt_nodes_at(0, 0, "", path[:-1])["n1"]
    return [{"id": ids["n1"], "tree": 1, "level": level, "moves": moves, "screen_hash": screen, "parent": parent,
             "depth": len(path)}] + [{"id": ids[f"n{k}"], "level": level, "moves": moves, "screen_hash": screen}
                                     for k in (2, 3, 4, 5)]


def gt_step(rid: str, seq: int, at: tuple, action: str, to: tuple | None, moves_step: int = 1, **extra) -> dict:
    level, moves, screen, _path = at
    step = {"rollout_id": rid, "seq": seq, "level": level, "moves": moves, "screen_hash": screen, "action": action,
            "moves_step": moves_step, **gt_nodes_at(*at), **extra}
    if to is not None:
        step.update({"next_level": to[0], "next_moves": to[1], "next_screen_hash": to[2]})
        step.update({f"c{k}": v for k, v in zip(TREES, gt_nodes_at(*to).values())})
    return step


def gt_bundle(run: str = "run-a", choices=("probe", "stock"), build: str = "animft/coach1",
              with_traces: bool = True) -> dict:
    """One full play per choice, from the game start: root --choice--> screen B (level 1, 6 moves) --execute-->
    screen C (level 2, 0 moves) --stock--> end. In t1 each choice is its own path; in t2..t4 the plays merge at B."""

    screens = [{"screen_hash": SCREEN_A, "board": ["0" * 64] * 64}, {"screen_hash": SCREEN_B, "board": None},
               {"screen_hash": SCREEN_C, "board": ["5" * 64] * 64}]
    rollouts, steps, nodes, traces = [], [], gt_node_rows(1, 0, SCREEN_A, ()), {}
    for p, choice in enumerate(choices):
        content = tree_trace(f"{run}-{choice}")
        sha = tree_sha(content)
        traces[sha] = content
        rid = f"{run}:ka59_p{p}"
        rollouts.append({"id": rid, "game": "ka59", "run": run, "build": build, "model": "flash-next",
                         "harness": "daniel-v3", "policy": None, "status": "finished",
                         "result": {"levels": 1, "score": 12.5, "actions": 21}})
        a, b, c = (1, 0, SCREEN_A, ()), (1, 6, SCREEN_B, (choice,)), (2, 0, SCREEN_C, (choice, "execute"))
        nodes += gt_node_rows(*b) + gt_node_rows(*c)
        steps += [
            gt_step(rid, 0, a, choice, b, detail={"cap": 6, "prob": 0.5, "decision": 1}, trace_sha=sha,
                    features={"level": 1, "actions_in_level": 0}, hidden_ref=f"gs://bucket/round0/{run}.npz#{p}",
                    outcome={"acts": 6, "lvl30": p == 0, "cleared_level": p == 0, "go_turn": False,
                             "level_score": 0.1 + 0.1 * p}),
            gt_step(rid, 1, b, "execute", c, detail={"cap": 20}, trace_sha=sha,
                    outcome={"acts": 12, "lvl30": True, "cleared_level": True, "go_turn": False}),
            gt_step(rid, 2, c, "stock", None, outcome={"acts": 3, "lvl30": False, "cleared_level": None, "go_turn": True}),
        ]
    return {"rollouts": rollouts, "screens": screens, "nodes": nodes, "steps": steps,
            "traces": traces if with_traces else {}}


MID_FROM = gt_node(1, "probe")          # run-a's p0 after its first action (screen B)


def gt_mid(rid: str = "run-m:ka59_r0", origin: str = MID_FROM) -> dict:
    """A rollout restarted from run-a p0's t1 node after 'probe' (stored by that play), replaying its actions: B --probe-->
    C --execute--> D. Nodes already stored are not resent."""

    b, c, d = (1, 6, SCREEN_B, ("probe",)), (2, 0, SCREEN_C, ("probe", "probe")), (2, 9, SCREEN_D, ("probe", "probe", "execute"))
    return {"rollouts": [{"id": rid, "game": "ka59", "run": "run-m", "build": "animft/coach1", "model": "flash-next",
                          "harness": "daniel-v3", "policy": "pol-v1", "origin_state": origin,
                          "origin_edge": "run-a:ka59_p0:0", "origin_kind": "replay_actions",
                          "status": "finished", "result": {"levels": 1}}],
            "screens": [{"screen_hash": SCREEN_D, "board": ["7" * 64] * 64}],
            "nodes": gt_node_rows(*c)[:1] + gt_node_rows(*d),
            "steps": [gt_step(rid, 0, b, "probe", c, outcome={"acts": 4, "cleared_level": 0}),
                      gt_step(rid, 1, c, "execute", d, outcome={"acts": 9, "cleared_level": 1, "level_score": 0.3})]}


CTX = hashlib.sha256(b"context before").hexdigest()


def gt_value_bundle() -> dict:
    """Three plays of level 1 for the value and shortest-path reads (game moves in brackets):

      p0  start -left(3)-> X -solve(10)-> cleared       13 moves
      p1  start -right(9)-> X -jump(2)-> cleared        11 moves
      p2  start -left(4)-> Y -left(4)-> (ends)          never cleared

    In t3 (level + screen) and t4 (screen) both plays reach the same X, so the screen graph knows start -left(3)-> X
    -jump(2)-> cleared: 5 moves, shorter than either play. In t5 (moves // 6) X at 3 moves and X at 9 moves are
    different cells, so no merge: the best is p1's 11."""

    rollouts = [{"id": f"run-v:ka59_p{p}", "game": "ka59", "run": "run-v", "build": "animft/coach1",
                 "model": "flash-next", "harness": "daniel-v3", "status": "finished", "result": {}} for p in range(3)]
    start, c = (1, 0, SCREEN_A, ()), (2, 0, SCREEN_C, ("next",))
    x0, x1, y = (1, 3, SCREEN_B, ("left",)), (1, 9, SCREEN_B, ("right",)), (1, 4, SCREEN_D, ("left", "p2"))
    nodes = gt_node_rows(*start) + gt_node_rows(*x0) + gt_node_rows(*x1) + gt_node_rows(*y) + gt_node_rows(*c)
    out = lambda mtc: {"moves_to_clear": mtc, "cleared_level": int(mtc is not None), "level_weight": 1,  # noqa: E731
                       "human_moves": 12, "level_score": None if mtc is None else min(1.0, 12 / mtc)}
    steps = [
        gt_step("run-v:ka59_p0", 0, start, "left", x0, 3, outcome=out(13), tokens=100, ctx_before=CTX, resumable=True),
        gt_step("run-v:ka59_p0", 1, x0, "solve", c, 10, outcome=out(10)),
        gt_step("run-v:ka59_p1", 0, start, "right", x1, 9, outcome=out(11)),
        gt_step("run-v:ka59_p1", 1, x1, "jump", c, 2, outcome=out(2)),
        gt_step("run-v:ka59_p2", 0, start, "left", y, 4, outcome=out(None)),
        gt_step("run-v:ka59_p2", 1, y, "left", None, 4, outcome=out(None)),
    ]
    return {"rollouts": rollouts, "screens": [{"screen_hash": h, "board": None} for h in
                                              (SCREEN_A, SCREEN_B, SCREEN_C, SCREEN_D)],
            "nodes": nodes, "steps": steps}


class Gtree(unittest.TestCase):
    """The universal game tree: validation and who may call what, before any database work."""

    def setUp(self) -> None:
        os.environ["ALLOWED_EMAILS"] = TEAM
        self.root = Path(tempfile.mkdtemp())
        self.api = RlReviewApi(no_db, self.root, "secret-token")
        self.machine = {"Authorization": "Bearer secret-token"}
        self.team = {"X-Forwarded-Email": TEAM}

    def test_held_out_games_are_refused(self) -> None:
        bundle = gt_bundle()
        for ro in bundle["rollouts"]:
            ro["game"] = "as66"
        with self.assertRaises(ReviewProblem) as ctx:
            clean_gtree_bundle(bundle)
        self.assertEqual(ctx.exception.code, "fenced_game")

    def test_a_good_bundle_is_kept(self) -> None:
        item = clean_gtree_bundle(gt_bundle())
        self.assertEqual((len(item["rollouts"]), len(item["screens"]), len(item["steps"]), len(item["traces"])),
                         (2, 3, 6, 2))
        # nodes: 5 roots, then per play B and C in each tree, merged in t2..t5: 5 + 2 * 2 (t1) + 2 * 4 (t2..t5)
        self.assertEqual(len(item["nodes"]), 17)
        first = item["steps"][0]
        self.assertEqual((first["id"], first["n1"], first["c2"]), ("run-a:ka59_p0:0", ROOT_IDS[1],
                                                                   gt_node(2, SCREEN_B, 6)))
        self.assertIsNone(item["steps"][2]["c3"], "the rollout's end leads nowhere")
        self.assertEqual(item["rollouts"][0]["origin_kind"], "start")
        mid = clean_gtree_bundle(gt_mid())
        self.assertEqual((mid["rollouts"][0]["origin_state"], mid["rollouts"][0]["origin_kind"]),
                         (MID_FROM, "replay_actions"))

    def test_bad_bundles_are_refused(self) -> None:
        def mutate(fn, base=gt_bundle):
            b = base()
            fn(b)
            return b
        first_sha = lambda b: next(iter(b["traces"]))  # noqa: E731
        ro = lambda b: b["rollouts"][0]  # noqa: E731
        st = lambda b: b["steps"][0]  # noqa: E731
        t1 = lambda b: next(n for n in b["nodes"] if ":t1:" in n["id"] and not n["id"].endswith("root"))  # noqa: E731
        t2 = lambda b: next(n for n in b["nodes"] if ":t2:" in n["id"] and not n["id"].endswith("root"))  # noqa: E731
        bad = [
            ("invalid_body", []),
            ("invalid_body", {"rollouts": [], "steps": []}),
            ("invalid_body", mutate(lambda b: b.update(steps={"x": 1}))),
            ("invalid_rollout", mutate(lambda b: ro(b).update(id="../x"))),
            ("duplicate_rollout", mutate(lambda b: b["rollouts"].append(dict(ro(b))))),
            ("invalid_game", mutate(lambda b: ro(b).update(game="KA59"))),
            ("invalid_build", mutate(lambda b: ro(b).update(build="a b"))),
            ("invalid_model", mutate(lambda b: ro(b).update(model=None))),
            ("invalid_harness", mutate(lambda b: ro(b).update(harness="x" * 300))),
            ("invalid_status", mutate(lambda b: ro(b).update(status="done!"))),
            ("invalid_result", mutate(lambda b: ro(b).update(result={"x": "y" * 40000}))),
            ("invalid_origin_kind", mutate(lambda b: ro(b).update(origin_kind="teleport"))),
            ("invalid_origin", mutate(lambda b: ro(b).update(origin_kind="restore"))),
            ("invalid_origin", mutate(lambda b: ro(b).update(origin_kind="start"), gt_mid)),
            ("invalid_origin", mutate(lambda b: ro(b).update(origin_state="sb26:t1:" + "0" * 16), gt_mid)),
            ("invalid_origin", mutate(lambda b: ro(b).update(origin_state=gt_node(2, SCREEN_B, 6)), gt_mid)),
            ("invalid_origin", mutate(lambda b: ro(b).update(origin_edge="run-a:ka59_p0:0"))),
            ("invalid_origin_state", mutate(lambda b: ro(b).update(origin_state="ka59:L1:aaaaaaaaaaaa"), gt_mid)),
            ("invalid_origin_edge", mutate(lambda b: ro(b).update(origin_edge="../x"), gt_mid)),
            ("invalid_screen", mutate(lambda b: b["screens"].append("aaaa"))),
            ("invalid_screen_hash", mutate(lambda b: b["screens"][0].update(screen_hash="A" * 12))),
            ("invalid_board", mutate(lambda b: b["screens"][0].update(board=["zz"] * 64))),
            ("invalid_node", mutate(lambda b: b["nodes"].append({"id": "ka59:t6:root"}))),
            ("invalid_node", mutate(lambda b: b["nodes"].append({"id": "ka59:t1:abc"}))),
            ("invalid_node", mutate(lambda b: t2(b).update(tree=1))),
            ("invalid_node", mutate(lambda b: t2(b).update(depth=2))),
            ("invalid_node", mutate(lambda b: b["nodes"][0].update(screen_hash=SCREEN_A))),
            ("invalid_parent", mutate(lambda b: t1(b).update(parent=ROOT_IDS[2]))),
            ("invalid_level", mutate(lambda b: t1(b).update(level=-1))),
            ("invalid_depth", mutate(lambda b: t1(b).update(depth="1"))),
            ("unknown_rollout", mutate(lambda b: st(b).update(rollout_id="run-z:ka59_p0"))),
            ("invalid_seq", mutate(lambda b: st(b).update(seq=-1))),
            ("invalid_seq", mutate(lambda b: st(b).update(seq=True))),
            ("invalid_step", mutate(lambda b: st(b).update(id="run-a:ka59_p0:9"))),
            ("invalid_step", mutate(lambda b: st(b).update(game="sb26"))),
            ("invalid_step", mutate(lambda b: st(b).update(c4=None))),
            ("duplicate_step", mutate(lambda b: b["steps"].append(dict(st(b))))),
            ("invalid_action", mutate(lambda b: st(b).update(action="probe now"))),
            ("invalid_action", mutate(lambda b: st(b).update(action="x" * 41))),
            ("invalid_n1", mutate(lambda b: st(b).pop("n1"))),
            ("invalid_n2", mutate(lambda b: st(b).update(n2=ROOT_IDS[1]))),
            ("invalid_n3", mutate(lambda b: st(b).update(n3="sb26:t3:root"))),
            ("invalid_c4", mutate(lambda b: st(b).update(c4="ka59:t4:short"))),
            ("invalid_level", mutate(lambda b: st(b).update(level=None))),
            ("invalid_moves", mutate(lambda b: st(b).update(moves=-2))),
            ("invalid_screen_hash", mutate(lambda b: st(b).update(screen_hash=None))),
            ("invalid_next_screen_hash", mutate(lambda b: st(b).update(next_screen_hash="xyz"))),
            ("invalid_next_level", mutate(lambda b: st(b).update(next_level=1.5))),
            ("invalid_detail", mutate(lambda b: st(b).update(detail={"x": "y" * 9000}))),
            ("invalid_features", mutate(lambda b: st(b).update(features=[1]))),
            ("invalid_outcome", mutate(lambda b: st(b).update(outcome={"x": "y" * 9000}))),
            ("invalid_hidden_ref", mutate(lambda b: st(b).update(hidden_ref="gs://a\nb"))),
            ("invalid_hidden_ref", mutate(lambda b: st(b).update(hidden_ref="x" * 501))),
            ("invalid_trace_sha", mutate(lambda b: st(b).update(trace_sha="abc"))),
            ("trace_sha_mismatch", mutate(lambda b: b["traces"][first_sha(b)]["turns"].append({"step": 9}))),
            ("invalid_trace", mutate(lambda b: b["traces"].update({first_sha(b): {"no": "turns"}}))),
            # t5 and the moves fields
            ("invalid_n5", mutate(lambda b: st(b).pop("n5"))),
            ("invalid_n5", mutate(lambda b: st(b).update(n5=ROOT_IDS[4]))),
            ("invalid_step", mutate(lambda b: st(b).update(c5=None))),
            ("invalid_moves_step", mutate(lambda b: st(b).pop("moves_step"))),
            ("invalid_moves_step", mutate(lambda b: st(b).update(moves_step=-1))),
            ("invalid_moves_step", mutate(lambda b: st(b).update(moves_step=2.5))),
            ("invalid_tokens", mutate(lambda b: st(b).update(tokens=-5))),
            ("invalid_tokens", mutate(lambda b: st(b).update(tokens="100"))),
            ("invalid_ctx_before", mutate(lambda b: st(b).update(ctx_before="abc"))),
            ("invalid_ctx_after", mutate(lambda b: st(b).update(ctx_after="A" * 64))),
            ("invalid_state_ref", mutate(lambda b: st(b).update(state_ref=12))),
            ("invalid_resumable", mutate(lambda b: st(b).update(resumable="yes"))),
            ("invalid_resumable", mutate(lambda b: st(b).update(resumable=True))),
            ("invalid_outcome", mutate(lambda b: st(b).update(outcome={"moves_to_clear": -1}))),
            ("invalid_outcome", mutate(lambda b: st(b).update(outcome={"moves_to_clear": "5"}))),
            ("invalid_outcome", mutate(lambda b: st(b).update(outcome={"moves_to_clear": True}))),
            ("invalid_outcome", mutate(lambda b: st(b).update(moves_step=6, outcome={"moves_to_clear": 5}))),
            ("invalid_outcome", mutate(lambda b: st(b).update(outcome={"cleared_level": 2}))),
            ("invalid_outcome", mutate(lambda b: st(b).update(outcome={"cleared_level": "1"}))),
            ("invalid_outcome", mutate(lambda b: st(b).update(outcome={"moves_to_clear": 9, "cleared_level": 0}))),
            ("invalid_outcome", mutate(lambda b: st(b).update(outcome={"moves_to_clear": None, "cleared_level": 1}))),
            ("invalid_outcome", mutate(lambda b: st(b).update(outcome={"level_score": -0.5}))),
            ("invalid_outcome", mutate(lambda b: st(b).update(outcome={"level_score": True}))),
            ("invalid_outcome", mutate(lambda b: st(b).update(outcome={"human_moves": 2.5}))),
            ("invalid_outcome", mutate(lambda b: st(b).update(outcome={"level_weight": -1}))),
        ]
        for code, bundle in bad:
            with self.assertRaises(ReviewProblem, msg=code) as ctx:
                clean_gtree_bundle(bundle)
            self.assertEqual(ctx.exception.code, code, f"{code}: {ctx.exception.message}")
        # what is allowed: build paths, actions with ':' and '+', any mid-tree origin kind, a node sent twice
        ok = gt_bundle(build="animft/coach-random50")
        ok["steps"][0]["action"] = "probe+cap:6"
        ok["nodes"].append({"id": ROOT_IDS[1], "level": 1})
        self.assertEqual(next(n for n in clean_gtree_bundle(ok)["nodes"] if n["id"] == ROOT_IDS[1])["level"], 1)
        for kind in ("replay_exact", "replay_actions", "restore"):
            clean_gtree_bundle(mutate(lambda b: ro(b).update(origin_kind=kind), gt_mid))
        # the new step fields are kept as sent; booleans pass for cleared_level; the defaults
        item = clean_gtree_bundle(gt_value_bundle())
        first, last = item["steps"][0], item["steps"][-1]
        self.assertEqual((first["moves_step"], first["tokens"], first["ctx_before"], first["resumable"],
                          first["n5"], first["c5"]), (3, 100, CTX, True, ROOT_IDS[5], gt_node(5, 1, SCREEN_B, 0)))
        self.assertEqual((last["tokens"], last["ctx_after"], last["state_ref"], last["resumable"], last["c5"]),
                         (None, None, None, False, None))
        self.assertEqual(item["steps"][1]["outcome"]["moves_to_clear"], 10)
        clean_gtree_bundle(mutate(lambda b: st(b).update(outcome={"moves_to_clear": 1, "cleared_level": True})))
        clean_gtree_bundle(mutate(lambda b: st(b).update(state_ref=CTX, ctx_after=CTX, moves_step=0, tokens=0)))

    def test_the_routes_are_claimed_and_guarded(self) -> None:
        node = gt_node(2, SCREEN_B, 6)
        for path in ("/api/v1/gtree/games", "/api/v1/gtree/publication", f"/api/v1/gtree/node/{node}",
                     "/api/v1/gtree/frontier", "/api/v1/gtree/stats", "/api/v1/gtree"):
            self.assertTrue(RlReviewApi.owns(path), path)
        self.assertFalse(RlReviewApi.owns("/api/v1/gtreex/games"))
        pub = "/api/v1/gtree/publication"
        self.assertEqual(call(self.api, "PUT", pub, {"Authorization": "Bearer nope"}, gt_bundle())[0], 401)
        self.assertEqual(call(self.api, "PUT", pub, self.team, gt_bundle())[0], 401)
        self.assertEqual(call(self.api, "GET", pub, self.machine)[0], 405)
        self.assertEqual(call(self.api, "GET", pub, self.team)[0], 401, "the publication route is for machines only")
        status, payload = call(self.api, "PUT", pub, self.machine, gzip.compress(json.dumps([1]).encode()))
        self.assertEqual((status, payload["error"]), (400, "invalid_body"))
        bad = gt_bundle()
        bad["steps"][0]["action"] = "NOPE NOPE"
        self.assertEqual(call(self.api, "PUT", pub, self.machine, bad)[1]["error"], "invalid_action",
                         "a bad body is refused before the database")
        reads = ("/api/v1/gtree/games", "/api/v1/gtree/stats", f"/api/v1/gtree/node/{node}",
                 "/api/v1/gtree/rollout/run-a:ka59_p0", "/api/v1/gtree/trace/" + "a" * 64,
                 "/api/v1/gtree/frontier?game=ka59", "/api/v1/gtree/value/ka59:t5:root",
                 "/api/v1/gtree/shortest?game=ka59&level=1")
        for path in reads:
            self.assertEqual(call(self.api, "GET", path)[0], 401, path)
            self.assertEqual(call(self.api, "GET", path, self.machine)[0], 401, path)
            self.assertEqual(call(self.api, "GET", path, {"X-Forwarded-Email": "x@gmail.com"})[0], 403, path)
            self.assertEqual(call(self.api, "PUT", path, self.team, {"x": 1})[0], 405, path)
        for path, code in (("/api/v1/gtree/node/ka59:t6:root", "invalid_node"),
                           ("/api/v1/gtree/node/ka59:t1:abc", "invalid_node"),
                           ("/api/v1/gtree/node/ka59:L1:aaaaaaaaaaaa", "invalid_node"),
                           ("/api/v1/gtree/node/..%2F..%2Fx", "invalid_node"),
                           ("/api/v1/gtree/rollout/..%2Fx", "invalid_rollout"),
                           ("/api/v1/gtree/trace/../../etc", "invalid_trace_sha"),
                           ("/api/v1/gtree/trace/" + "A" * 64, "invalid_trace_sha"),
                           ("/api/v1/gtree/frontier", "invalid_game"),
                           ("/api/v1/gtree/frontier?game=ka59&tree=6", "invalid_tree"),
                           ("/api/v1/gtree/frontier?game=ka59&tree=0", "invalid_tree"),
                           ("/api/v1/gtree/frontier?game=ka59&mode=forward", "invalid_mode"),
                           ("/api/v1/gtree/value/ka59:t6:root", "invalid_node"),
                           ("/api/v1/gtree/value/..%2Fx", "invalid_node"),
                           ("/api/v1/gtree/value/ka59:t1:root?penalty=-1", "invalid_penalty"),
                           ("/api/v1/gtree/value/ka59:t1:root?penalty=abc", "invalid_penalty"),
                           ("/api/v1/gtree/value/ka59:t1:root?penalty=nan", "invalid_penalty"),
                           ("/api/v1/gtree/value/ka59:t1:root?pi=%7Bbad", "invalid_pi"),
                           ("/api/v1/gtree/value/ka59:t1:root?pi=%5B1%5D", "invalid_pi"),
                           ("/api/v1/gtree/value/ka59:t1:root?pi=%7B%22a%22%3A-1%7D", "invalid_pi"),
                           ("/api/v1/gtree/value/ka59:t1:root?pi=%7B%22a%22%3A0%7D", "invalid_pi"),
                           ("/api/v1/gtree/value/ka59:t1:root?pi=%7B%22a%20b%22%3A1%7D", "invalid_pi"),
                           ("/api/v1/gtree/shortest?level=1", "invalid_game"),
                           ("/api/v1/gtree/shortest?game=ka59", "invalid_level"),
                           ("/api/v1/gtree/shortest?game=ka59&level=-1", "invalid_level"),
                           ("/api/v1/gtree/shortest?game=ka59&level=1&tree=9", "invalid_tree"),
                           ("/api/v1/gtree/frontier?game=ka59&tree=t1", "invalid_tree"),
                           ("/api/v1/gtree/frontier?game=ka59&N=0", "invalid_N"),
                           ("/api/v1/gtree/frontier?game=ka59&N=1001", "invalid_N"),
                           ("/api/v1/gtree/frontier?game=ka59&limit=0", "invalid_limit"),
                           ("/api/v1/gtree/frontier?game=ka59&limit=-3", "invalid_limit"),
                           ("/api/v1/gtree/frontier?game=ka59&actions=probe,a%20b", "invalid_actions")):
            status, payload = call(self.api, "GET", path, self.team)
            self.assertEqual((status, payload["error"]), (400, code), path)
        self.assertEqual(call(self.api, "GET", "/api/v1/gtree/trace/" + "a" * 64, self.team)[0], 404)
        self.assertEqual(call(self.api, "GET", "/api/v1/gtree/nothing", self.team)[0], 404)
        self.assertEqual(call(self.api, "GET", "/api/v1/gtree", self.team)[0], 404)


class ShippedFiles(unittest.TestCase):
    def test_skip_auth_routes_are_exact(self) -> None:
        entry = (ROOT / "railway" / "entrypoint.sh").read_text(encoding="utf-8")
        for route in ("^/review\\.html$", "^/api/v1/review/publication$", "^/api/v1/review/export$",
                      "^/api/v1/rl/dashboard-publication$", "^/api/v1/rl2/publication/[a-z0-9][a-z0-9._-]*$",
                      "^/api/v1/rl2/tree/publication$", "^/api/v1/gtree/publication$"):
            self.assertIn(f'--skip-auth-route="{route}"', entry)
        # nothing that would open the team routes or the RL data
        for pattern in re.findall(r'--skip-auth-route="([^"]+)"', entry):
            self.assertFalse(pattern.startswith("^/api/v1/review/") and not pattern.endswith("$"), pattern)
            self.assertNotIn(pattern, ("^/api/v1/review/", "^/api/v1/rl/", "^/api/v1/rl/dashboard$", "^/api/v1/rl2/",
                                       "^/api/v1/rl2/doc/", "^/api/v1/rl2/tree/"))
            self.assertFalse(pattern.startswith("^/api/v1/rl2/doc"), pattern)
            self.assertFalse(pattern.startswith("^/api/v1/rl2/tree/") and pattern != "^/api/v1/rl2/tree/publication$",
                             pattern)
            # the universal tree: only the machines' publication skips sign-in
            self.assertFalse("gtree" in pattern and pattern != "^/api/v1/gtree/publication$", pattern)

    def test_image_ships_the_module_and_pages(self) -> None:
        docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY railway/rl_review.py /rl_review.py", docker)
        self.assertIn("RlReviewApi", (ROOT / "railway" / "catalog_server.py").read_text(encoding="utf-8"))
        for page in ("review.html", "rl.html", "rl2.html", "tree.html"):
            self.assertTrue((ROOT / "docs" / page).is_file(), page)

    def test_rl2_page_has_every_view(self) -> None:
        page = (ROOT / "docs" / "rl2.html").read_text(encoding="utf-8")
        script = (ROOT / "docs" / "static" / "js" / "rl2.js").read_text(encoding="utf-8")
        views = re.search(r"const VIEWS = \[([^\]]*)\]", script).group(1)
        for view in ("builds", "decisions", "sampling", "tree", "training"):
            self.assertIn(f'data-view="{view}"', page, view)
            self.assertIn(f'id="view-{view}"', page, view)
            self.assertIn(f'"{view}"', views, view)
        fixture = json.loads((ROOT / "docs" / "static" / "data" / "rl2-fixture.json").read_text(encoding="utf-8"))
        names = [c["name"] for c in fixture["docs"]["rl-campaigns"]["campaigns"]]
        self.assertTrue(any(f"rl-campaign-{n}" in fixture["docs"] for n in names), "a fake campaign for ?fixture=1")

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


@unittest.skipUnless(os.environ.get("ARC3_TEST_DATABASE_URL"), "set ARC3_TEST_DATABASE_URL to a disposable Postgres")
class GtreeDatabase(unittest.TestCase):
    """The universal tree round trip: one step table read as four trees, republish per rollout, restart mid-tree."""

    @classmethod
    def setUpClass(cls) -> None:
        import psycopg2

        cls.url = os.environ["ARC3_TEST_DATABASE_URL"]
        cls.connect = staticmethod(lambda: psycopg2.connect(cls.url))
        schema = (ROOT / "railway" / "catalog_schema.sql").read_text(encoding="utf-8")
        with cls.connect() as connection, connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS gt_edges, gt_states, gt_steps, gt_rollouts, gt_nodes, gt_screens CASCADE")
            cursor.execute(schema)
            cursor.execute(schema)  # the server re-runs the schema on every start

    def setUp(self) -> None:
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute("TRUNCATE gt_steps, gt_rollouts, gt_nodes, gt_screens")
        os.environ["ALLOWED_EMAILS"] = TEAM
        self.root = Path(tempfile.mkdtemp())
        self.api = RlReviewApi(self.connect, self.root, "secret-token")
        self.machine = {"Authorization": "Bearer secret-token"}
        self.team = {"X-Forwarded-Email": TEAM}

    def publish(self, bundle: dict, gz: bool = True):
        raw = json.dumps(bundle).encode()
        return call(self.api, "PUT", "/api/v1/gtree/publication", self.machine, gzip.compress(raw) if gz else raw)

    def get(self, path: str):
        status, payload = call(self.api, "GET", "/api/v1/gtree/" + path, self.team)
        self.assertEqual(status, 200, f"{path}: {payload}")
        return payload

    def count(self, sql: str, *args) -> int:
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute(sql, args)
            return cursor.fetchone()[0]

    def test_four_trees_over_the_same_steps(self) -> None:
        status, result = self.publish(gt_bundle())
        self.assertEqual((status, result["rollouts"], result["nodes"], result["steps"], result["tracesWritten"]),
                         (200, 2, 17, 6, 2))
        # a second run, another build: in t1 its path is its own, in t2..t4 it merges with run-a at screens B and C
        self.assertEqual(self.publish(gt_bundle(run="run-b", choices=("rethink",), build="coach2"))[0], 200)
        games = self.get("games")
        self.assertEqual(games["trees"]["1"], "path (context-aware)")
        g = games["games"][0]
        self.assertEqual((g["game"], g["rollouts"], g["mid_rollouts"], g["steps"]), ("ka59", 3, 0, 9))
        self.assertEqual({k: t["nodes"] for k, t in g["trees"].items()}, {"1": 7, "2": 3, "3": 3, "4": 3, "5": 3})
        self.assertEqual({k: t["start"] for k, t in g["trees"].items()}, {str(k): v for k, v in ROOT_IDS.items()})
        self.assertEqual(g["trees"]["3"]["deepest"], 2)

        root = self.get(f"node/{ROOT_IDS[2]}")
        self.assertEqual((root["tree"], root["node"]["screen_hash"], root["node"]["screen_shown"]), (2, None, SCREEN_A))
        self.assertEqual(len(root["node"]["board"]), 64, "a root shows the screen its steps start from")
        self.assertEqual(root["by_action"]["probe"], {"n": 1, "lvl30": 1.0, "cleared": 1.0, "acts": 6.0, "go": 0.0,
                                                      "level_score": 0.1, "moves_to_clear": None, "ended": 0,
                                                      "children": [{"id": gt_node(2, SCREEN_B, 6), "n": 1}]})
        self.assertEqual(sorted(root["by_action"]), ["probe", "rethink", "stock"])
        first = root["steps"][0]
        self.assertNotIn("content", first)
        self.assertEqual((first["run"], first["build"], first["origin_kind"], first["hidden_ref"], first["child"]),
                         ("run-a", "animft/coach1", "start", "gs://bucket/round0/run-a.npz#0", gt_node(2, SCREEN_B, 6)))
        self.assertEqual((first["child_info"]["arrivals"], first["child_info"]["steps"], first["child_info"]["moves"]),
                         (3, 3, 6), "three plays merged at screen B in t2")

        b2 = self.get(f"node/{gt_node(2, SCREEN_B, 6)}")
        self.assertEqual((b2["node"]["arrivals"], b2["node"]["arrival_rollouts"], b2["parents"]),
                         (3, 3, [{"id": ROOT_IDS[2], "n": 3}]))
        self.assertEqual(b2["by_action"]["execute"]["children"], [{"id": gt_node(2, SCREEN_C, 0), "n": 3}])
        self.assertIsNone(b2["node"]["board"], "screen B was sent without a board")
        # the same position in t1 is one play's path only
        p1 = self.get(f"node/{gt_node(1, 'probe')}")
        self.assertEqual((p1["node"]["arrivals"], p1["node"]["parent"], p1["node"]["depth"], p1["parents"]),
                         (1, ROOT_IDS[1], 1, [{"id": ROOT_IDS[1], "n": 1}]))
        self.assertEqual(self.get(f"node/{gt_node(4, SCREEN_C)}")["by_action"]["stock"]["ended"], 3)
        # a browser may encode the ':' of an id
        self.assertEqual(self.get(f"node/{ROOT_IDS[3].replace(':', '%3A')}")["node"]["id"], ROOT_IDS[3])
        self.assertEqual(call(self.api, "GET", "/api/v1/gtree/node/zz99:t1:root", self.team)[0], 404)

        stats = self.get("stats")
        self.assertEqual((stats["rollouts"], stats["steps"], stats["games"], stats["screens"]), (3, 9, 1, 3))
        self.assertEqual({k: t["nodes"] for k, t in stats["trees"].items()}, {"1": 7, "2": 3, "3": 3, "4": 3, "5": 3})

    def test_republishing_is_idempotent(self) -> None:
        self.publish(gt_bundle())
        status, result = self.publish(gt_bundle(), gz=False)
        self.assertEqual((status, result["steps"], result["stepsReplaced"], result["tracesWritten"]), (200, 6, 6, 0))
        self.assertEqual([self.count(f"SELECT count(*) FROM {t}") for t in ("gt_steps", "gt_rollouts", "gt_nodes",
                                                                            "gt_screens")], [6, 2, 17, 3])

    def test_a_smaller_republication_drops_that_rollouts_steps(self) -> None:
        self.publish(gt_bundle(choices=("probe", "stock", "search")))
        smaller = gt_bundle(choices=("probe",))
        smaller["steps"] = smaller["steps"][:1]
        status, result = self.publish(smaller)
        self.assertEqual((status, result["steps"], result["stepsReplaced"]), (200, 1, 3))
        ro = self.get("rollout/run-a:ka59_p0")
        self.assertEqual([s["id"] for s in ro["steps"]], ["run-a:ka59_p0:0"])
        # rollouts not in the publication keep their steps
        self.assertEqual(self.count("SELECT count(*) FROM gt_steps WHERE rollout_id <> 'run-a:ka59_p0'"), 6)

    def test_a_rollout_restarted_mid_tree(self) -> None:
        self.publish(gt_bundle())
        status, result = self.publish(gt_mid())
        self.assertEqual((status, result["rollouts"], result["nodes"], result["steps"]), (200, 1, 6, 2), result)
        at = self.get(f"node/{MID_FROM}")
        self.assertEqual([(r["id"], r["origin_kind"], r["origin_edge"]) for r in at["started_here"]],
                         [("run-m:ka59_r0", "replay_actions", "run-a:ka59_p0:0")])
        restarted = [s for s in at["steps"] if s["rollout_id"] == "run-m:ka59_r0"]
        self.assertEqual([(s["action"], s["origin_kind"], s["origin_state"], s["policy"]) for s in restarted],
                         [("probe", "replay_actions", MID_FROM, "pol-v1")])
        self.assertEqual(self.get(f"node/{ROOT_IDS[1]}")["started_here"], [])
        ro = self.get("rollout/run-m:ka59_r0")
        self.assertEqual((ro["rollout"]["origin_state"], ro["rollout"]["result"], [s["seq"] for s in ro["steps"]]),
                         (MID_FROM, {"levels": 1}, [0, 1]))
        self.assertEqual(self.get("games")["games"][0]["mid_rollouts"], 1)
        self.assertEqual(call(self.api, "GET", "/api/v1/gtree/rollout/run-z:ka59_p0", self.team)[0], 404)
        # a restart from a node nobody stored is refused
        status, payload = self.publish(gt_mid(rid="run-m:ka59_r1", origin=gt_node(1, "nowhere")))
        self.assertEqual((status, payload["error"]), (400, "unknown_node"))

    def test_action_stats_ignore_nulls(self) -> None:
        self.publish(gt_bundle())
        self.publish(gt_mid())
        view = self.get(f"node/{gt_node(2, SCREEN_C, 0)}")
        stock = view["by_action"]["stock"]
        self.assertEqual((stock["n"], stock["cleared"], stock["go"], stock["acts"], stock["level_score"]),
                         (2, None, 1.0, 3.0, None), "null and missing outcomes are ignored")
        execute = view["by_action"]["execute"]
        self.assertEqual((execute["n"], execute["lvl30"], execute["cleared"], execute["acts"], execute["go"],
                          execute["level_score"]), (1, None, 1.0, 9.0, None, 0.3))
        at_start = self.get(f"node/{ROOT_IDS[1]}")["by_action"]
        self.assertEqual((at_start["probe"]["level_score"], at_start["stock"]["level_score"]), (0.1, 0.2))

    def test_frontier_ranking(self) -> None:
        self.publish(gt_bundle())
        self.publish(gt_bundle(run="run-b", choices=("rethink",), build="coach2"))
        self.publish(gt_mid())
        front = self.get("frontier?game=ka59&tree=2&N=4&limit=50")
        self.assertEqual((front["tree"], front["N"], front["deepest"], front["candidates"]), (2, 4, 2, 4))
        self.assertEqual(front["actions"], ["execute", "probe", "rethink", "stock"])
        rows = {r["id"]: r for r in front["nodes"]}
        root, b, c, d = ROOT_IDS[2], gt_node(2, SCREEN_B, 6), gt_node(2, SCREEN_C, 0), gt_node(2, SCREEN_D, 9)
        # root: 3 steps out (few), a root is level 0, probe/rethink cleared and stock not (spread 1), no arrivals
        self.assertEqual(rows[root]["parts"], {"few": 1.0, "depth": 0.0, "spread": 1.0, "merge": 0.0})
        self.assertEqual(rows[root]["open"], {"execute": 4, "probe": 3, "rethink": 3, "stock": 3})
        # B: 4 out, execute 1.0 vs the restart's probe 0.0, three rollouts arrive; the restart started at its t1 node
        self.assertEqual(rows[b]["parts"], {"few": 0.0, "depth": 0.5, "spread": 1.0, "merge": 0.5})
        self.assertEqual((rows[b]["samples"], rows[b]["missing"]), ({"execute": 3, "probe": 1}, 1 + 3 + 4 + 4))
        # C: 4 out, only execute has a cleared value (stock's are null), four rollouts arrive
        self.assertEqual((rows[c]["score"], rows[c]["parts"]["spread"], rows[c]["arrival_rollouts"]), (1.5, 0.0, 4))
        # D: nothing leaves it yet, deepest level, one rollout arrived
        self.assertEqual((rows[d]["score"], rows[d]["out"], rows[d]["arrivals"]), (2.0, 0, 1))
        # three tie at 2.0: the higher level goes first, then more arrivals
        self.assertEqual([r["id"] for r in front["nodes"]], [d, b, root, c])
        # up to N per (node, action): with N=1 for 'execute', B (3) and C (1) are full
        self.assertEqual([r["id"] for r in self.get("frontier?game=ka59&tree=2&N=1&actions=execute")["nodes"]], [d, root])
        self.assertEqual(len(self.get("frontier?game=ka59&tree=2&limit=2")["nodes"]), 2)
        # tree 1 (the default) keeps every path apart: 9 nodes, all short of 4 samples of some action
        t1 = self.get("frontier?game=ka59")
        self.assertEqual((t1["tree"], t1["candidates"]), (1, 9))
        self.assertEqual(next(r for r in t1["nodes"] if r["id"] == MID_FROM)["started_here"], 1)
        self.assertEqual(call(self.api, "GET", "/api/v1/gtree/frontier?game=zz99", self.team)[0], 404)

    def test_value_in_moves(self) -> None:
        status, _ = self.publish(gt_value_bundle())
        self.assertEqual(status, 200)
        # at the start, by hand: left = [p0 cleared in 13, p2 never] and right = [p1 cleared in 11]
        v = self.get(f"value/{ROOT_IDS[3]}")
        self.assertEqual((v["tree"], v["penalty"], v["n"], v["pi_source"]), (3, 200, 3, "empirical"))
        self.assertEqual(v["actions"]["left"], {"n": 2, "cleared": 1, "clear_rate": 0.5, "mean_moves_to_clear": 13.0,
                                                "q": -106.5, "tokens": 100.0, "moves_step": 3.5})
        self.assertEqual(v["actions"]["right"], {"n": 1, "cleared": 1, "clear_rate": 1.0, "mean_moves_to_clear": 11.0,
                                                 "q": -11.0, "tokens": None, "moves_step": 9.0})
        self.assertEqual(v["pi"], {"left": round(2 / 3, 6), "right": round(1 / 3, 6)})
        self.assertAlmostEqual(v["V"], 2 / 3 * -106.5 + 1 / 3 * -11, places=3)
        self.assertEqual(v["best"], {"moves_to_clear": 11, "step_id": "run-v:ka59_p1:0", "rollout_id": "run-v:ka59_p1",
                                     "seq": 0, "action": "right"})
        # a penalty and a policy: pi is renormalised over the actions seen here; an unseen one is listed
        pi = quote(json.dumps({"left": 0.25, "right": 0.75, "wait": 1}))
        v = self.get(f"value/{ROOT_IDS[3]}?penalty=100&pi={pi}")
        self.assertEqual((v["penalty"], v["actions"]["left"]["q"], v["pi_source"], v["pi_ignored"]),
                         (100, -56.5, "query", ["wait"]))
        self.assertEqual(v["pi"], {"left": 0.25, "right": 0.75})
        self.assertAlmostEqual(v["V"], 0.25 * -56.5 + 0.75 * -11, places=3)
        # any tree: in t1 the start is the same node; a node never cleared from has no best path
        self.assertEqual(self.get(f"value/{ROOT_IDS[1]}")["V"], self.get(f"value/{ROOT_IDS[3]}")["V"])
        y = self.get(f"value/{gt_node(5, 1, SCREEN_D, 0)}")
        self.assertEqual((y["actions"]["left"]["q"], y["actions"]["left"]["clear_rate"], y["best"]), (-200.0, 0.0, None))
        x = self.get(f"value/{gt_node(4, SCREEN_B)}")
        self.assertEqual((x["best"]["moves_to_clear"], x["best"]["action"]), (2, "jump"))
        self.assertEqual(call(self.api, "GET", "/api/v1/gtree/value/zz99:t3:root", self.team)[0], 404)
        # the step fields come back on the node view
        first = next(s for s in self.get(f"node/{ROOT_IDS[3]}")["steps"] if s["id"] == "run-v:ka59_p0:0")
        self.assertEqual((first["moves_step"], first["tokens"], first["ctx_before"], first["resumable"], first["n5"]),
                         (3, 100, CTX, True, ROOT_IDS[5]))
        # republishing changes nothing
        before = self.get(f"value/{ROOT_IDS[3]}")
        status, result = self.publish(gt_value_bundle())
        self.assertEqual((status, result["stepsReplaced"]), (200, 6))
        self.assertEqual(self.get(f"value/{ROOT_IDS[3]}"), before)

    def test_shortest_merges_rollouts(self) -> None:
        self.publish(gt_value_bundle())
        x3, y3 = gt_node(3, 1, SCREEN_B), gt_node(3, 1, SCREEN_D)
        sp = self.get("shortest?game=ka59&level=1")
        self.assertEqual((sp["tree"], sp["steps_read"], sp["truncated"], sp["goal_steps"], sp["reachable"]),
                         (3, 6, False, 2, 2))
        # p0's first step to X, then p1's jump: 3 + 2 = 5 moves, shorter than either play (13, 11)
        self.assertEqual((sp["best"]["start"], sp["best"]["moves"]), (ROOT_IDS[3], 5))
        self.assertEqual([s["id"] for s in sp["best"]["steps"]], ["run-v:ka59_p0:0", "run-v:ka59_p1:1"])
        self.assertEqual([(n["id"], n["distance"], n["step"]) for n in sp["nodes"]],
                         [(x3, 2, "run-v:ka59_p1:1"), (ROOT_IDS[3], 5, "run-v:ka59_p0:0"), (y3, None, None)])
        self.assertEqual([(n["id"], n["start"]) for n in sp["starts"]], [(ROOT_IDS[3], True)])
        self.assertEqual(sp["nodes"][0]["t1"], gt_node(1, "right"), "the t1 node a rollout can restart from")
        self.assertEqual(self.get("shortest?game=ka59&level=1&tree=4")["best"]["moves"], 5)
        # t5 keeps X at 3 moves and X at 9 moves apart: no merge, the best is p1 alone
        t5 = self.get("shortest?game=ka59&level=1&tree=5")
        self.assertEqual((t5["best"]["moves"], [s["id"] for s in t5["best"]["steps"]]),
                         (11, ["run-v:ka59_p1:0", "run-v:ka59_p1:1"]))
        self.assertEqual(call(self.api, "GET", "/api/v1/gtree/shortest?game=ka59&level=7", self.team)[0], 404)

    def test_frontier_modes(self) -> None:
        self.publish(gt_value_bundle())
        x3, y3, c3 = gt_node(3, 1, SCREEN_B), gt_node(3, 1, SCREEN_D), gt_node(3, 2, SCREEN_C)
        cov = self.get("frontier?game=ka59&tree=3")
        self.assertEqual((cov["mode"], [r["id"] for r in cov["nodes"]]), ("coverage", [c3, x3, y3, ROOT_IDS[3]]))
        unc = self.get("frontier?game=ka59&tree=3&mode=uncertain")
        rows = {r["id"]: r for r in unc["nodes"]}
        # the start: left cleared 1 of 2, right 1 of 1, so p = 2/3; 3 steps out
        self.assertEqual(rows[ROOT_IDS[3]]["parts"], {"few": 1.0, "depth": 0.0, "spread": 0.5, "merge": 0.0,
                                                      "uncertain": 0.2222, "explore": 0.5})
        self.assertEqual((rows[y3]["parts"]["uncertain"], rows[y3]["parts"]["explore"]), (0.0, 0.7071))
        self.assertEqual((rows[c3]["score"], rows[x3]["score"]), (3.5, 2.5774))
        self.assertEqual([r["id"] for r in unc["nodes"]], [c3, x3, ROOT_IDS[3], y3], "the start passes Y")
        back = self.get("frontier?game=ka59&tree=3&mode=backward")
        self.assertEqual([(r["id"], r["distance"], r["action"], r["t1"]) for r in back["nodes"]],
                         [(x3, 2, "jump", gt_node(1, "right")), (ROOT_IDS[3], 5, "left", ROOT_IDS[1])])
        self.assertEqual(back["nodes"][0]["open"], {"left": 4, "right": 4, "solve": 3, "jump": 3})
        # t5: no merge, so the backward list follows p1 alone
        self.assertEqual([r["distance"] for r in self.get("frontier?game=ka59&tree=5&mode=backward")["nodes"]], [2, 11])

    def test_a_refused_body_changes_nothing(self) -> None:
        base = gt_bundle()
        self.publish(base)
        tables = ("gt_screens", "gt_nodes", "gt_rollouts", "gt_steps")
        before = [self.count(f"SELECT count(*) FROM {t}") for t in tables]
        bad = gt_bundle(choices=("probe", "stock", "brief"), with_traces=False)
        bad["rollouts"][0]["status"] = "changed"
        bad["screens"].append({"screen_hash": "e" * 12, "board": None})
        for step, stored in zip(bad["steps"], base["steps"]):
            step["trace_sha"] = stored.get("trace_sha")
        status, payload = self.publish(bad)          # the third rollout's trace is neither sent nor stored
        self.assertEqual((status, payload["error"]), (400, "unknown_trace"))
        orphan = gt_bundle(run="run-o")
        orphan["steps"][1]["n3"] = gt_node(3, "nowhere")
        status, payload = self.publish(orphan)       # a step's t3 node is neither sent nor stored
        self.assertEqual((status, payload["error"]), (400, "unknown_node"))
        after = [self.count(f"SELECT count(*) FROM {t}") for t in tables]
        self.assertEqual(before, after)
        self.assertEqual(self.count("SELECT count(*) FROM gt_rollouts WHERE status = 'changed' OR run = 'run-o'"), 0)
        self.assertFalse(any(p.name.startswith(".") for p in (self.root / "_gtree" / "traces").iterdir()))

    def test_traces_round_trip(self) -> None:
        base = gt_bundle()
        self.publish(base)
        sha = base["steps"][0]["trace_sha"]
        status, trace = call(self.api, "GET", f"/api/v1/gtree/trace/{sha}", self.team)
        self.assertEqual((status, trace), (200, base["traces"][sha]))
        self.assertEqual(sorted(p.name for p in (self.root / "_gtree" / "traces").iterdir()),
                         sorted(f"{s}.json" for s in base["traces"]), "no temp files left behind")
        raw = (self.root / "_gtree" / "traces" / f"{sha}.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), sha)
        # once stored, a later publication may refer to traces, nodes and screens without resending them
        again = gt_bundle(run="run-c", with_traces=False)
        again["nodes"], again["screens"] = [], []
        for mine, stored in zip(again["steps"], base["steps"]):
            mine["trace_sha"] = stored.get("trace_sha")
        status, result = self.publish(again)
        self.assertEqual((status, result["steps"], result["tracesWritten"]), (200, 6, 0), result)


if __name__ == "__main__":
    unittest.main()

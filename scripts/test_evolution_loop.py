"""Tests for the evolution loop's arithmetic (scripts/evolution_loop.py).

Run: python -m pytest -q scripts/test_evolution_loop.py
"""

import json

from scripts import evolution_loop as loop

A = {"primary": "push-crates-onto-targets", "secondary": ["one-way-doors", "ice-slide"], "core_verb": "push",
     "controlled_subject": "avatar", "control": "keyboard-4dir", "topology": "square-grid", "temporal": "turn-based",
     "information": "full", "objective": "cover/fill"}
B = {"primary": "route-a-beam-with-mirrors", "secondary": ["colour-filters", "splitters"], "core_verb": "rotate",
     "controlled_subject": "object", "control": "click", "topology": "free-pixel", "temporal": "commit-then-simulate",
     "information": "preview-of-consequence", "objective": "route-flow"}


def test_distance_is_zero_for_the_same_game_and_one_for_unrelated_games():
    assert loop.distance(A, A)["distance"] == 0.0
    assert loop.distance(A, B)["mechanic"] == 1.0
    assert loop.distance(A, B)["distance"] > 0.9


def test_primary_mechanics_weigh_more_than_secondary():
    shares_primary = dict(B, primary="push-crates-onto-targets")
    shares_secondary = dict(B, secondary=["one-way-doors", "splitters"])
    assert loop.mechanic_distance(A, shares_primary) < loop.mechanic_distance(A, shares_secondary)


def test_rank_puts_the_nearest_first():
    near = dict(A, secondary=["one-way-doors", "conveyor-belts"])
    ranked = loop.rank(A, {"far": dict(B, tree_id="far"), "near": dict(near, tree_id="near")})
    assert [r["tree_id"] for r in ranked] == ["near", "far"]


def test_draws_and_the_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(loop, "LEDGER", tmp_path / "ledger.jsonl")
    assert loop.main(["draw", "--game", "zz01", "--seed", "1", "--record"]) == 0
    rows = [json.loads(line) for line in (tmp_path / "ledger.jsonl").read_text().splitlines()]
    assert rows[0]["event"] == "mechanic-draw" and len(set(rows[0]["candidates"])) == 3
    # A family drawn in v4 is less likely next time: its weight drops from the ledger.
    loop.log_event({"event": "anchor", "tree_ids": ["zz01", "g009"]})
    assert loop.recent_samples() == ["zz01", "g009"]

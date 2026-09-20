"""Tests for the difficulty-curve score (scripts/curve_score.py).

Run: python -m pytest -q scripts/test_curve_score.py
"""

import json

import pytest

from scripts.curve_score import check_felt, score, shape_matches, spearman


def curriculum(roles, mechanics=None):
    """One entry per role letter; every introduced mechanic is used again by the next level."""
    mechanics = mechanics or {}
    entries = []
    for index, role in enumerate(roles):
        introduces = mechanics.get(index, [])
        entries.append({
            "level": index + 1,
            "role": role,
            "introduces": introduces,
            "uses": [m for i, ms in mechanics.items() if i <= index for m in ms],
            "why_harder": "" if index == 0 else f"asks more than level {index}",
        })
    return entries


GOOD_ROLES = ["teach", "stretch", "introduce", "combine", "combine", "turn", "compose", "compose", "finale"]
GOOD_MECHANICS = {0: ["carry"], 2: ["tide"], 5: ["fog"]}
RISING = [6, 12, 14, 19, 22, 26, 31, 34, 42]


def test_the_shape_grammar_accepts_the_documented_shapes():
    assert shape_matches("TICXPP")  # the shortest legal game
    assert shape_matches("TSSICCXPPF")
    assert shape_matches("TSICICXPP")  # two introduce/combine cycles
    assert not shape_matches("TSSSICXPP")  # three stretches
    assert not shape_matches("TICXP")  # one compose
    assert not shape_matches("ITCXPP")  # teaching second
    assert not shape_matches("TICXPPFF")  # two finales


def test_spearman_reads_the_direction_of_the_curve():
    assert spearman([1.0, 2.0, 3.0, 4.0]) == 1.0
    assert spearman([4.0, 3.0, 2.0, 1.0]) == -1.0
    assert spearman([5.0, 5.0, 5.0, 5.0]) == 0.0


def test_a_climbing_game_passes():
    report = score(RISING, curriculum(GOOD_ROLES, GOOD_MECHANICS), "glowup")
    assert report["verdict"] == "pass", report["checks"]
    assert report["score"] >= 75
    assert all(c["status"] == "pass" for c in report["checks"].values()), report["checks"]


def test_a_flat_game_fails_on_plateau_and_growth():
    flat = [6] + [25] * 8  # every level after the tutorial costs the same
    report = score(flat, curriculum(GOOD_ROLES, GOOD_MECHANICS), "glowup")
    assert report["verdict"] == "fail"
    assert report["checks"]["no_plateau"]["status"] == "warn"
    assert report["checks"]["growth"]["status"] in ("warn", "fail")


def test_a_bumpy_game_fails_the_trend():
    bumpy = [8, 32, 28, 32, 29, 27, 35, 28, 41]
    report = score(bumpy, curriculum(GOOD_ROLES, GOOD_MECHANICS), "glowup")
    assert report["checks"]["rising"]["status"] == "fail"
    assert report["verdict"] == "fail"


def test_a_long_level_one_fails_the_hard_gate():
    report = score([20, 22, 24, 26, 30, 34, 38, 42, 50], curriculum(GOOD_ROLES, GOOD_MECHANICS), "glowup")
    assert report["checks"]["teach_first"]["status"] == "fail"
    assert report["verdict"] == "fail"


def test_shape_problems_are_named():
    missing = score(RISING, [], "glowup")
    assert missing["checks"]["shape"]["status"] == "fail" and missing["verdict"] == "fail"
    # A seed may not have declared its curriculum yet; the measured checks still apply.
    assert score(RISING, [], "seed")["checks"]["rising"]["status"] == "pass"
    orphan = curriculum(GOOD_ROLES, {0: ["carry"], 2: ["tide"], 8: ["fog"]})  # introduced in the last level
    report = score(RISING, orphan, "glowup")
    assert "never used again" in report["checks"]["shape"]["detail"]
    assert report["checks"]["shape"]["status"] == "warn"


def test_the_report_carries_what_the_ledger_records():
    report = score(RISING, curriculum(GOOD_ROLES, GOOD_MECHANICS), "glowup")
    assert report["actions_per_level"] == RISING
    assert report["levels"] == 9
    assert json.dumps(report)  # serialisable for the ledger and the version's provenance


def felt(demands, verdict="climbs"):
    return {"played_by": "agent", "verdict": verdict,
            "levels": [{"level": i + 1, "demand": d, "what_it_adds": "more", "solved": True} for i, d in enumerate(demands)]}


def test_a_played_reading_can_fail_a_game_the_numbers_liked():
    # Perfect measured curve, but every level felt the same to the player.
    report = score(RISING, curriculum(GOOD_ROLES, GOOD_MECHANICS), "glowup", felt=felt([2] * 9, "flat"))
    assert report["score"] == 100
    assert report["verdict"] == "fail"
    assert report["checks"]["felt_rising"]["status"] == "fail"
    assert report["checks"]["felt_verdict"]["status"] == "fail"


def test_a_played_reading_that_climbs_passes():
    report = score(RISING, curriculum(GOOD_ROLES, GOOD_MECHANICS), "glowup", felt=felt([1, 1, 2, 2, 3, 3, 4, 4, 5]))
    assert report["verdict"] == "pass"
    assert report["checks"]["felt_rising"]["status"] == "pass"


def test_a_felt_report_needs_enough_levels():
    rising, _ = check_felt(felt([1, 3]))
    assert rising["status"] == "fail" and "at least three" in rising["detail"]

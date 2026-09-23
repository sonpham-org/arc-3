"""Tests for the vetting gate (scripts/vet_game.py) and publish's use of it.

Run: python -m pytest -q scripts/test_vet_game.py   (needs arcengine 0.9.3)
"""

import hashlib
import json
from pathlib import Path

import pytest

pytest.importorskip("arcengine")

from scripts.publish_game_versions import vet_summary  # noqa: E402
from scripts.vet_game import vet  # noqa: E402

TEMPLATE = Path(__file__).resolve().parents[1] / "research" / "game-evolution" / "template"
SOURCE = (TEMPLATE / "skeleton.py").read_text(encoding="utf-8")
TRACE = json.loads((TEMPLATE / "skeleton.trace.json").read_text(encoding="utf-8"))


def run(tmp_path, source=SOURCE, trace=TRACE, profile="seed"):
    src = tmp_path / "game.py"
    src.write_text(source, encoding="utf-8")
    tr = tmp_path / "game.trace.json"
    tr.write_text(json.dumps(trace), encoding="utf-8")
    report = vet(src, tr, profile, None, time_budget=8, seed=1, strips=None)
    return report, {name: check["status"] for name, check in report["checks"].items()}


def test_skeleton_passes_as_a_seed(tmp_path):
    report, status = run(tmp_path)
    assert report["verdict"] == "pass", report["checks"]
    assert report["levels"] == 3
    for name in ("win_trace", "determinism", "deepcopy", "reset", "level1_short", "level1_safe", "early_death", "fuzz"):
        assert status[name] == "pass", (name, report["checks"][name])
    # A seed's levels may still be random-clearable: that is a warning, not a failure.
    assert status["random_resistance"] == "warn"


def test_glowup_profile_needs_seven_levels_and_resistance(tmp_path):
    report, status = run(tmp_path, profile="glowup")
    assert report["verdict"] == "fail"
    assert status["level_count"] == "fail"


def test_a_trace_that_does_not_win_fails(tmp_path):
    trace = {"levels": [{"actions": [4, 4, 4]}, *TRACE["levels"][1:]]}
    report, status = run(tmp_path, trace=trace)
    assert status["win_trace"] == "fail" and report["verdict"] == "fail"


def test_a_trace_with_actions_after_the_win_fails(tmp_path):
    trace = {"levels": [{"actions": [4, 4, 4, 4, 3]}, *TRACE["levels"][1:]]}
    _, status = run(tmp_path, trace=trace)
    assert status["win_trace"] == "fail"


def test_hidden_randomness_fails_determinism(tmp_path):
    noisy = SOURCE.replace(
        "        mover.set_position(x, y)",
        "        import random as _r\n        mover.set_position(x, y)\n        self.current_level.get_sprites_by_name('goal')[0].pixels[0][0] = _r.choice([14, 11])",
    )
    report, status = run(tmp_path, source=noisy)
    assert status["determinism"] == "fail"


def test_dying_on_level_one_fails(tmp_path):
    deadly = SOURCE.replace(
        "                # Refused: a visible 1-pixel nudge toward the wall and back. Nothing in the rules changes.",
        "                self.lose()",
    )
    report, status = run(tmp_path, source=deadly)
    assert status["level1_safe"] == "fail"
    assert status["early_death"] == "fail"
    assert report["verdict"] == "fail"


def test_forbidden_imports_fail(tmp_path):
    _, status = run(tmp_path, source="import os\n" + SOURCE)
    assert status["imports"] == "fail"


def test_publish_gate_binds_the_report_to_the_bytes(tmp_path):
    report, _ = run(tmp_path)
    path = tmp_path / "vet.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    source = SOURCE.encode("utf-8")
    assert hashlib.sha256(source).hexdigest() == report["source_sha256"]
    summary = vet_summary(str(path), source)
    assert summary["verdict"] == "pass" and summary["profile"] == "seed" and summary["checks"]["win_trace"] == "pass"
    with pytest.raises(SystemExit, match="other bytes"):
        vet_summary(str(path), source + b"# changed\n")
    report["verdict"] = "fail"
    report["checks"]["win_trace"]["status"] = "fail"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(SystemExit, match="did not pass"):
        vet_summary(str(path), source)

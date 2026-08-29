import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_catalog import (
    prepare_run_submission,
    validate_catalog_consistency,
)


class RunCatalogTests(unittest.TestCase):
    def entry(self) -> dict:
        return {
            "run": "run-1",
            "games": 1,
            "avg_score": 1.25,
            "levels": 1,
            "actions": 3,
            "tokens": 40,
            "per_game": [
                {
                    "id": "game-a",
                    "score": 1.25,
                    "levels": 1,
                    "levels_total": 4,
                    "actions": 3,
                }
            ],
            "has_execution_trace": True,
        }

    def timeline(self) -> dict:
        return {
            "schemaVersion": 2,
            "run": "run-1",
            "startedAt": "2026-08-21T00:00:00Z",
            "endedAt": "2026-08-21T00:01:00Z",
            "durationSeconds": 60,
            "scoreCurve": {
                "points": [
                    {"at": "2026-08-21T00:00:00Z", "meanScore": 0, "kind": "start"},
                    {
                        "at": "2026-08-21T00:01:00Z",
                        "meanScore": 1.25,
                        "kind": "end",
                        "cumulativeActions": 3,
                    },
                ],
                "tokenPoints": [
                    {
                        "at": "2026-08-21T00:01:00Z",
                        "meanScore": 1.25,
                        "kind": "end",
                        "cumulativeGeneratedTokens": 40,
                    }
                ],
                "finalMeanScore": 1.25,
                "finalActions": 3,
                "finalGeneratedTokens": 40,
            },
        }

    def test_rejects_score_mismatch(self) -> None:
        entry = self.entry()
        entry["avg_score"] = 9
        with self.assertRaisesRegex(ValueError, "score mismatch"):
            validate_catalog_consistency("run-1", entry, self.timeline())

    def test_accepts_sub_millipoint_rounding_difference(self) -> None:
        entry = self.entry()
        entry["avg_score"] = 6.884
        timeline = self.timeline()
        timeline["scoreCurve"]["finalMeanScore"] = 6.883480144
        timeline["scoreCurve"]["points"][-1]["meanScore"] = 6.883480144
        validate_catalog_consistency("run-1", entry, timeline)

    def test_submission_contains_validated_catalog_and_artifact_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_dir = root / "run-1"
            run_dir.mkdir()
            (run_dir / "run-overview.json").write_text("{}", encoding="utf-8")
            (run_dir / "run-timeline.json").write_text(
                json.dumps(self.timeline()), encoding="utf-8"
            )
            index_path = root / "runs-index.json"
            index_path.write_text(
                json.dumps(
                    {
                        "baseline": "run-0",
                        "biases": {},
                        "runs": [self.entry()],
                    }
                ),
                encoding="utf-8",
            )

            submission = prepare_run_submission(run_dir, index_path, "unit-test")
            self.assertTrue((run_dir / "run-submission.json").is_file())
            self.assertEqual(submission["scoreCurve"]["finalMeanScore"], 1.25)
            self.assertEqual(submission["createdAt"], "2026-08-21T00:01:00Z")
            self.assertEqual(
                {row["path"] for row in submission["artifacts"]},
                {"run-overview.json", "run-timeline.json"},
            )


if __name__ == "__main__":
    unittest.main()

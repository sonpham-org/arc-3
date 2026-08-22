import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_catalog import (
    build_catalog_sql,
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

    def test_submission_and_sql_cover_every_catalog_table(self) -> None:
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
            sql = build_catalog_sql(
                "SELECT 1;", submission, "a" * 64, 3, 100
            ).decode()
            for table in (
                "arc3_runs",
                "arc3_game_scores",
                "arc3_score_events",
                "arc3_run_artifacts",
                "arc3_publications",
            ):
                self.assertIn(table, sql)
            self.assertIn("arc3_refresh_catalog_snapshot", sql)
            self.assertIn("BEGIN;", sql)
            self.assertIn("COMMIT;", sql)


if __name__ == "__main__":
    unittest.main()

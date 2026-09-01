import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from railway.publication_store import (
    PublicationProblem,
    _replace_catalog_rows,
    load_package,
    publication_decision,
)
from scripts.publish_railway_data import build_archive, build_manifest, sha256_file
from scripts.run_catalog import prepare_run_submission


class PublicationStoreTests(unittest.TestCase):
    def entry(self) -> dict:
        return {
            "run": "run-1",
            "games": 1,
            "avg_score": 1.25,
            "levels": 1,
            "actions": 3,
            "tokens": 40,
            "model": {
                "id": "RadixArk/Qwen3.8-Flash-Next-NVFP4",
                "revision": "7b719225242aacd3dbd3f9407468c2ee9a9d2594",
            },
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

    def make_package(self, root: Path):
        run = root / "run-1"
        run.mkdir()
        (run / "run-overview.json").write_text(
            json.dumps({"run": "run-1"}), encoding="utf-8"
        )
        (run / "run-timeline.json").write_text(
            json.dumps(self.timeline()), encoding="utf-8"
        )
        index = root / "runs-index.json"
        index.write_text(json.dumps({"runs": [self.entry()]}), encoding="utf-8")
        prepare_run_submission(run, index, "unit-test")
        manifest, _ = build_manifest(run, "run-1")
        manifest_hash = hashlib.sha256(manifest.encode()).hexdigest()
        stage = root / "stage"
        stage.mkdir()
        archive = stage / "publication.tgz"
        build_archive(run, "run-1", manifest, archive)
        return stage, archive, manifest_hash

    def test_valid_package_verifies_every_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            stage, archive, manifest_hash = self.make_package(Path(temp))
            package = load_package(
                stage,
                archive,
                "run-1",
                sha256_file(archive),
                manifest_hash,
                100,
                100_000_000,
            )
            self.assertEqual(package.run_id, "run-1")
            self.assertEqual(package.manifest_sha256, manifest_hash)
            self.assertEqual(package.file_count, 3)

    def test_database_write_covers_every_catalog_table_with_bound_parameters(self) -> None:
        class Cursor:
            def __init__(self):
                self.statements = []

            def execute(self, statement, parameters=None):
                parameters = parameters or ()
                self.assertions(statement, parameters)
                self.statements.append(statement)

            @staticmethod
            def assertions(statement, parameters):
                if parameters:
                    assert statement.count("%s") == len(parameters)

        with tempfile.TemporaryDirectory() as temp:
            stage, archive, manifest_hash = self.make_package(Path(temp))
            package = load_package(
                stage,
                archive,
                "run-1",
                sha256_file(archive),
                manifest_hash,
                100,
                100_000_000,
            )
            cursor = Cursor()
            _replace_catalog_rows(cursor, package, lambda value: value)
            sql = "\n".join(cursor.statements)
            for table in (
                "arc3_runs",
                "arc3_game_scores",
                "arc3_score_events",
                "arc3_run_artifacts",
                "arc3_publications",
            ):
                self.assertIn(table, sql)
            self.assertIn("arc3_refresh_catalog_snapshot", sql)

    def test_archive_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "bad.tgz"
            with tarfile.open(archive, "w:gz") as tar:
                info = tarfile.TarInfo("../outside")
                info.size = 1
                tar.addfile(info, io.BytesIO(b"x"))
            stage = root / "stage"
            stage.mkdir()
            with self.assertRaisesRegex(PublicationProblem, "unsafe path"):
                load_package(
                    stage,
                    archive,
                    "run-1",
                    sha256_file(archive),
                    "a" * 64,
                    100,
                    100_000_000,
                )

    def test_same_manifest_is_idempotent(self) -> None:
        manifest = "a" * 64
        self.assertEqual(
            publication_decision(manifest, manifest, False, None, True),
            "already_published",
        )

    def test_stale_replacement_cannot_overwrite_newer_run(self) -> None:
        with self.assertRaisesRegex(PublicationProblem, "changed since") as raised:
            publication_decision("b" * 64, "c" * 64, True, "a" * 64, True)
        self.assertEqual(raised.exception.status, 412)

    def test_blind_overwrite_is_rejected(self) -> None:
        with self.assertRaises(PublicationProblem) as raised:
            publication_decision("b" * 64, "c" * 64, False, None, True)
        self.assertEqual(raised.exception.status, 409)


if __name__ == "__main__":
    unittest.main()

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from publish_railway_data import (
    build_manifest,
    parse_args,
    validate_run_name,
    validate_upload_script,
)


class PublishRailwayDataTests(unittest.TestCase):
    def test_validate_run_name(self) -> None:
        self.assertEqual(validate_run_name("20260820_run-p1"), "20260820_run-p1")
        for invalid in ("", "../run", "run/name", "run name", ".hidden"):
            with self.assertRaises(Exception):
                validate_run_name(invalid)

    def test_manifest_is_sorted_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = root / "docs" / "data" / "run-1"
            run.mkdir(parents=True)
            (run / "z.json").write_text("z", encoding="utf-8")
            (run / "a.json").write_text("a", encoding="utf-8")
            index = root / "docs" / "data" / "runs-index.json"
            index.write_text(json.dumps({"runs": [{"id": "run-1"}]}), encoding="utf-8")

            manifest, total = build_manifest(run, "run-1", index)

            expected_a = hashlib.sha256(b"a").hexdigest()
            expected_z = hashlib.sha256(b"z").hexdigest()
            lines = manifest.splitlines()
            self.assertEqual(lines[0], f"{expected_a}  run-1/a.json")
            self.assertEqual(lines[1], f"{expected_z}  run-1/z.json")
            self.assertTrue(lines[2].endswith("  runs-index.json"))
            self.assertEqual(total, 2 + index.stat().st_size)

    def test_parse_args_defaults_railway_directory_to_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            args = parse_args(["run-1", "--repo-root", temp, "--dry-run"])
            self.assertEqual(args.repo_root, Path(temp).resolve())
            self.assertEqual(args.railway_cwd, Path(temp).resolve())
            self.assertTrue(args.dry_run)

    def test_validate_upload_is_scoped_to_unique_stage(self) -> None:
        args = parse_args(["run-1", "--validate-upload-only"])
        script = validate_upload_script(args, "/srv/data/.incoming/run-1.1234").decode()
        self.assertIn("rm -rf \"$stage\"", script)
        self.assertIn("stage='/srv/data/.incoming/run-1.1234'", script)
        self.assertNotIn("rm -rf /srv/data", script)

    def test_finalize_uses_lock_and_fixed_data_root(self) -> None:
        from publish_railway_data import finalize_script

        args = parse_args(["run-1"])
        script = finalize_script(
            args, "/srv/data/.incoming/run-1.1234", "1234"
        ).decode()
        self.assertIn("lock=\"$data_root/.publish-lock\"", script)
        self.assertIn("data_root='/srv/data'", script)
        self.assertIn("sha256sum -cs MANIFEST.sha256", script)


if __name__ == "__main__":
    unittest.main()

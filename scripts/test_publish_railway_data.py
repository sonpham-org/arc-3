import hashlib
import io
import os
import tarfile
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from scripts.publish_railway_data import (
    build_archive,
    build_manifest,
    parse_args,
    railway_executable,
    validate_run_name,
)


class PublishRailwayDataTests(unittest.TestCase):
    def test_validate_run_name(self) -> None:
        self.assertEqual(validate_run_name("20260820_run-p1"), "20260820_run-p1")
        for invalid in ("", "../run", "run/name", "run name", ".hidden"):
            with self.assertRaises(Exception):
                validate_run_name(invalid)

    def test_manifest_is_sorted_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run-1"
            run.mkdir()
            (run / "z.json").write_text("z", encoding="utf-8")
            (run / "a.json").write_text("a", encoding="utf-8")
            manifest, total = build_manifest(run, "run-1")

            expected_a = hashlib.sha256(b"a").hexdigest()
            expected_z = hashlib.sha256(b"z").hexdigest()
            self.assertEqual(
                manifest.splitlines(),
                [
                    f"{expected_a}  run-1/a.json",
                    f"{expected_z}  run-1/z.json",
                ],
            )
            self.assertEqual(total, 2)

    def test_archive_contains_run_and_manifest_but_no_generated_sql(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = root / "run-1"
            run.mkdir()
            (run / "run-overview.json").write_text("{}", encoding="utf-8")
            manifest, _ = build_manifest(run, "run-1")
            archive_path = root / "run.tgz"
            build_archive(run, "run-1", manifest, archive_path)
            with tarfile.open(archive_path, "r:gz") as archive:
                names = set(archive.getnames())
            self.assertIn("run-1/run-overview.json", names)
            self.assertIn("MANIFEST.sha256", names)
            self.assertNotIn("CATALOG.sql", names)

    def test_parse_args_defaults_to_api_transport(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            args = parse_args(["run-1", "--repo-root", temp, "--dry-run"])
            self.assertEqual(args.repo_root, Path(temp).resolve())
            self.assertEqual(args.railway_cwd, Path(temp).resolve())
            self.assertEqual(args.api_url, "https://arc3.sonpham.net")
            self.assertEqual(args.service, "arc3-viewer")
            self.assertTrue(args.dry_run)

    def test_resolves_windows_npm_cli_shim(self) -> None:
        resolved = railway_executable("railway")
        if os.name == "nt":
            self.assertTrue(resolved.lower().endswith("railway.cmd"))

    def test_replacement_requires_a_valid_expected_manifest_if_supplied(self) -> None:
        args = parse_args(["run-1", "--replace", "--expected-manifest", "none"])
        self.assertEqual(args.expected_manifest, "none")
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parse_args(["run-1", "--replace", "--expected-manifest", "bad"])


if __name__ == "__main__":
    unittest.main()

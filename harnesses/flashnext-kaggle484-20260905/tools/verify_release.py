"""Fail-closed audit for the locked champion + Stall-140 release."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"
BASE = ROOT / "base"
CANDIDATE = ROOT / "candidate"
SOURCE_ARCHIVE = ROOT / "champion-source.tgz"
BASE_ARCHIVE = ROOT / "champion-gcp-wrapper.tgz"
RELEASE = ROOT / (
    "bundle-q38-flashnext-rtdv12-cap14-"
    "kaggle11p44-stall140-only-gcp-r1-20260904.tgz"
)
RUNNER = ROOT / (
    "v12-run-kaggle11p44-"
    "2fc2be2e8d0db29b23d588413603d5bc5f36096b5e9fe092f9a3a38f3f1d4ee2.py"
)
SOLVER = "src/ARC3-Inference/inference/framework/solver.py"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    }


def delta(left: dict[str, str], right: dict[str, str]) -> dict[str, list[str]]:
    return {
        "added": sorted(set(right) - set(left)),
        "removed": sorted(set(left) - set(right)),
        "changed": sorted(
            name for name in set(left) & set(right) if left[name] != right[name]
        ),
    }


def main() -> None:
    expected_hashes = {
        SOURCE_ARCHIVE: "04a25a5b6cc8a22891fcb81ca26a7d56626f0d51ecfaef7ed0d5153d868f2d62",
        BASE_ARCHIVE: "2ed1e758d07880fb4a9c764e57b4943e20c676cfdc881ce8bc1d8f2bcb1a5bd2",
        RELEASE: "b38dcb598f27f5031a32b014f0bed7e3dbf2c80ff710a758252579371aa952eb",
        RUNNER: "2fc2be2e8d0db29b23d588413603d5bc5f36096b5e9fe092f9a3a38f3f1d4ee2",
    }
    for path, expected in expected_hashes.items():
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"Hash mismatch for {path.name}: {actual}")

    source_files = tree(SOURCE)
    base_files = tree(BASE)
    candidate_files = tree(CANDIDATE)
    source_to_base = delta(source_files, base_files)
    base_to_candidate = delta(base_files, candidate_files)
    if source_to_base != {
        "added": ["pre_harness_warmup.py"],
        "removed": [],
        "changed": [],
    }:
        raise RuntimeError(f"Champion GCP wrapper drift: {source_to_base}")
    if base_to_candidate != {
        "added": [],
        "removed": [],
        "changed": [SOLVER],
    }:
        raise RuntimeError(f"Stall-only candidate drift: {base_to_candidate}")

    if base_files["pre_harness_warmup.py"] != (
        "758453bcbf5776c27705e9bf8ad8a174db4980e62a75d5db7c0e26d908d09156"
    ):
        raise RuntimeError("Champion warmup hash mismatch")

    solver_source = (CANDIDATE / SOLVER).read_text(encoding="utf-8")
    for required in (
        "STALL_ACTION_LIMIT = 140",
        "def current_level_action_count(self) -> int:",
        "def stall_action_limit_reached(self) -> bool:",
        "if self.stall_action_limit_reached():",
    ):
        if required not in solver_source:
            raise RuntimeError(f"Missing Stall-140 behavior: {required}")
    for forbidden in (
        "ARC3_MAX_RUNTIME_S_PER_GAME",
        "ARC3_BENCHMARK_CONCURRENCY",
        "ARC3_REPLAY_ENABLED",
        "ARC3_DYNAMIC_SLACK_ENABLED",
        "ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED",
    ):
        if forbidden in solver_source:
            raise RuntimeError(f"Unrelated solver mechanism present: {forbidden}")

    with tarfile.open(RELEASE, "r:gz") as archive:
        members = [member for member in archive.getmembers() if member.isfile()]
        member_names = [member.name for member in members]
        if len(members) != 78 or sorted(member_names) != sorted(candidate_files):
            raise RuntimeError("Release archive membership mismatch")
        for member in members:
            stream = archive.extractfile(member)
            if stream is None or sha256_bytes(stream.read()) != candidate_files[member.name]:
                raise RuntimeError(f"Release member mismatch: {member.name}")

    subprocess.run(
        [sys.executable, "-m", "unittest", "-v", str(ROOT / "test_stall140_only.py")],
        cwd=ROOT,
        check=True,
    )

    print(
        json.dumps(
            {
                "status": "passed",
                "source_to_gcp": source_to_base,
                "gcp_to_stall140": base_to_candidate,
                "archive_files": 78,
                "tests": 5,
                "release_sha256": expected_hashes[RELEASE],
                "runner_sha256": expected_hashes[RUNNER],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

"""Audit and package the champion Dynamic Slack experiment arms."""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BASE = ROOT / "base"
REFERENCE = ROOT / "dynamic-reference"
DYNAMIC = ROOT / "candidate-dynamicslack"
COMBINED = ROOT / "candidate-stall140-dynamicslack"
STALL_ONLY = ROOT / "candidate"
SOLVER = Path("src/ARC3-Inference/inference/framework/solver.py")
DYNAMIC_OUTPUT = ROOT / (
    "bundle-q38-flashnext-rtdv12-cap14-"
    "kaggle11p44-dynamicslack-gcp-r1-20260904.tgz"
)
COMBINED_OUTPUT = ROOT / (
    "bundle-q38-flashnext-rtdv12-cap14-"
    "kaggle11p44-stall140-dynamicslack-gcp-r1-20260904.tgz"
)


def digest(path: Path, algorithm: str = "sha256") -> str:
    checksum = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    if algorithm == "md5":
        return base64.b64encode(checksum.digest()).decode("ascii")
    return checksum.hexdigest()


def files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    }


def delta(left: Path, right: Path) -> dict[str, list[str]]:
    left_files = files(left)
    right_files = files(right)
    return {
        "added": sorted(set(right_files) - set(left_files)),
        "removed": sorted(set(left_files) - set(right_files)),
        "changed": sorted(
            name
            for name in set(left_files) & set(right_files)
            if digest(left_files[name]) != digest(right_files[name])
        ),
    }


def parsed_solver(root: Path) -> ast.Module:
    return ast.parse((root / SOLVER).read_text(encoding="utf-8"))


def top_node(module: ast.Module, name: str) -> ast.AST:
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == name:
            return node
    raise KeyError(name)


def class_node(module: ast.Module, class_name: str, member_name: str) -> ast.AST:
    cls = top_node(module, class_name)
    assert isinstance(cls, ast.ClassDef)
    for node in cls.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == member_name:
            return node
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == member_name:
                return node
    raise KeyError(f"{class_name}.{member_name}")


def same_ast(left: ast.AST, right: ast.AST, label: str) -> None:
    if ast.dump(left, include_attributes=False) != ast.dump(right, include_attributes=False):
        raise RuntimeError(f"Mechanism transplant drift: {label}")


def build_archive(tree: Path, output: Path) -> dict[str, str | int]:
    if output.exists():
        raise RuntimeError(f"Refusing to overwrite {output}")
    tree_files = files(tree)
    with tarfile.open(output, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for name, path in sorted(tree_files.items()):
            archive.add(path, arcname=name, recursive=False)
    with tarfile.open(output, "r:gz") as archive:
        members = [member for member in archive.getmembers() if member.isfile()]
        if sorted(member.name for member in members) != sorted(tree_files):
            raise RuntimeError(f"Archive membership mismatch: {output.name}")
        for member in members:
            stream = archive.extractfile(member)
            if stream is None:
                raise RuntimeError(f"Unreadable archive member: {member.name}")
            if hashlib.sha256(stream.read()).hexdigest() != digest(tree_files[member.name]):
                raise RuntimeError(f"Archive member mismatch: {member.name}")
    return {
        "name": output.name,
        "files": len(tree_files),
        "size": output.stat().st_size,
        "sha256": digest(output),
        "md5_base64": digest(output, "md5"),
    }


def run_test(candidate: str, test: str) -> None:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["ARC3_TEST_CANDIDATE"] = candidate
    subprocess.run(
        [sys.executable, "-m", "unittest", "-v", str(ROOT / test)],
        cwd=ROOT,
        env=environment,
        check=True,
    )


def main() -> None:
    expected_delta = {"added": [], "removed": [], "changed": [SOLVER.as_posix()]}
    for tree, label in ((DYNAMIC, "dynamic"), (COMBINED, "combined")):
        actual = delta(BASE, tree)
        if actual != expected_delta:
            raise RuntimeError(f"{label} is not a solver-only delta: {actual}")

    reference = parsed_solver(REFERENCE)
    dynamic = parsed_solver(DYNAMIC)
    combined = parsed_solver(COMBINED)
    stall_only = parsed_solver(STALL_ONLY)

    for name in ("_env_bool", "_bounded_env_float", "_DynamicSlackAllocator"):
        expected = top_node(reference, name)
        same_ast(expected, top_node(dynamic, name), f"dynamic.{name}")
        same_ast(expected, top_node(combined, name), f"combined.{name}")

    session_methods = (
        "runtime_limit_reached",
        "timing_payload",
        "request_timeout_seconds",
    )
    solver_members = (
        "dynamic_slack_enabled",
        "dynamic_slack_grant_fraction",
        "dynamic_slack_max_extra_seconds",
        "_dynamic_slack_allocator",
        "__getstate__",
        "__setstate__",
        "__deepcopy__",
        "_teardown",
        "_run_games",
        "runtime_limit_seconds_for_game",
        "_play_one",
    )
    for name in session_methods:
        expected = class_node(reference, "_HarnessGameSession", name)
        same_ast(expected, class_node(dynamic, "_HarnessGameSession", name), name)
        same_ast(expected, class_node(combined, "_HarnessGameSession", name), name)
    for name in solver_members:
        expected = class_node(reference, "HarnessSolver", name)
        same_ast(expected, class_node(dynamic, "HarnessSolver", name), name)
        same_ast(expected, class_node(combined, "HarnessSolver", name), name)

    for name in ("stall_guard_triggered", "current_level_action_count", "stall_action_limit_reached", "should_stop"):
        expected = class_node(stall_only, "_HarnessGameSession", name)
        same_ast(expected, class_node(combined, "_HarnessGameSession", name), f"stall.{name}")

    combined_source = (COMBINED / SOLVER).read_text(encoding="utf-8")
    dynamic_source = (DYNAMIC / SOLVER).read_text(encoding="utf-8")
    if "STALL_ACTION_LIMIT" in dynamic_source:
        raise RuntimeError("Stall behavior leaked into Dynamic-Slack-only arm")
    for source, label in ((dynamic_source, "dynamic"), (combined_source, "combined")):
        for required in (
            '"ARC3_DYNAMIC_SLACK_ENABLED"',
            '"ARC3_DYNAMIC_SLACK_GRANT_FRACTION"',
            '"ARC3_DYNAMIC_SLACK_MAX_EXTRA_SECONDS"',
        ):
            if required not in source:
                raise RuntimeError(f"{label} missing {required}")
        if "ARC3_BENCHMARK_CONCURRENCY" in source:
            raise RuntimeError(f"{label} contains unrelated concurrency override")

    run_test("candidate-dynamicslack", "test_dynamic_slack.py")
    run_test("candidate-stall140-dynamicslack", "test_dynamic_slack.py")
    run_test("candidate-stall140-dynamicslack", "test_stall140_only.py")

    result = {
        "status": "passed",
        "baseline_sha256": digest(ROOT / "champion-gcp-wrapper.tgz"),
        "reference_dynamic_slack_sha256": digest(ROOT / "dynamic-slack-reference.tgz"),
        "dynamic_slack_policy": {
            "baseline_seconds": 6480,
            "grant_fraction": 0.75,
            "max_extra_seconds": 1200,
            "suite_deadline_seconds": 7920,
        },
        "tree_delta_from_champion": expected_delta,
        "dynamic_slack": build_archive(DYNAMIC, DYNAMIC_OUTPUT),
        "stall140_dynamic_slack": build_archive(COMBINED, COMBINED_OUTPUT),
        "tests_passed": 15,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

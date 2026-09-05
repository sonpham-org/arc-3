"""Build the immutable four-mode visual-transition experiment bundle."""

from __future__ import annotations

import ast
import base64
import copy
import hashlib
import io
import json
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "bundle-q38-flashnext-rtdv12-cap14-kaggle-winner-gcp.tgz"
CANDIDATE = ROOT / "candidate-visual-transitions-r1"
OUTPUT = ROOT / (
    "bundle-q38-flashnext-rtdv12-cap14-kaggle11p44-"
    "visual-transition-matrix-gcp-r1-20260905.tgz"
)
EXPECTED_CHANGED = {
    "./EXPERIMENT_MANIFEST.json",
    "./MANIFEST.md",
    "./src/ARC3-Inference/inference/agent/prompts.py",
    "./src/ARC3-Inference/inference/agent/tool_agent.py",
    "./src/ARC3-Inference/inference/framework/solver.py",
}


def digest_bytes(data: bytes, algorithm: str = "sha256") -> str:
    value = hashlib.new(algorithm, data).digest()
    return base64.b64encode(value).decode("ascii") if algorithm == "md5" else value.hex()


def digest_file(path: Path, algorithm: str = "sha256") -> str:
    checksum = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return (
        base64.b64encode(checksum.digest()).decode("ascii")
        if algorithm == "md5"
        else checksum.hexdigest()
    )


def candidate_path(member_name: str) -> Path:
    relative = member_name[2:] if member_name.startswith("./") else member_name
    return CANDIDATE / Path(relative)


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError(f"Refusing to overwrite immutable release: {OUTPUT}")

    changed: set[str] = set()
    expected_hashes: dict[str, str] = {}
    source_file_names: set[str] = set()
    with tarfile.open(SOURCE, "r:gz") as source, tarfile.open(
        OUTPUT, "w:gz", format=tarfile.PAX_FORMAT
    ) as target:
        source_members = source.getmembers()
        for original in source_members:
            info = copy.copy(original)
            if not original.isfile():
                target.addfile(info)
                continue
            source_file_names.add(original.name)
            source_stream = source.extractfile(original)
            if source_stream is None:
                raise RuntimeError(f"Unreadable source member: {original.name}")
            source_data = source_stream.read()
            path = candidate_path(original.name)
            if not path.is_file():
                raise RuntimeError(f"Candidate is missing source member: {original.name}")
            data = path.read_bytes()
            if data != source_data:
                changed.add(original.name)
            if original.name.endswith(".py"):
                ast.parse(data.decode("utf-8"), filename=original.name)
            info.size = len(data)
            expected_hashes[original.name] = digest_bytes(data)
            target.addfile(info, io.BytesIO(data))

    if changed != EXPECTED_CHANGED:
        raise RuntimeError(
            "Unexpected candidate delta: "
            + json.dumps(
                {
                    "missing": sorted(EXPECTED_CHANGED - changed),
                    "extra": sorted(changed - EXPECTED_CHANGED),
                },
                indent=2,
            )
        )

    candidate_files = {
        "./" + path.relative_to(CANDIDATE).as_posix()
        for path in CANDIDATE.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    }
    extra_files = candidate_files - source_file_names
    if extra_files:
        raise RuntimeError(f"Candidate has extra material files: {sorted(extra_files)}")

    with tarfile.open(OUTPUT, "r:gz") as archive, tarfile.open(
        SOURCE, "r:gz"
    ) as source:
        members = archive.getmembers()
        source_names = [member.name for member in source.getmembers()]
        if [member.name for member in members] != source_names:
            raise RuntimeError("Archive membership or ordering drift")
        for member in members:
            if not member.isfile():
                continue
            stream = archive.extractfile(member)
            if stream is None or digest_bytes(stream.read()) != expected_hashes[member.name]:
                raise RuntimeError(f"Archive verification failed: {member.name}")

    print(
        json.dumps(
            {
                "status": "passed",
                "source": SOURCE.name,
                "source_sha256": digest_file(SOURCE),
                "output": OUTPUT.name,
                "changed_members": sorted(changed),
                "modes": ["control", "metadata", "additive", "replace"],
                "files": len(expected_hashes),
                "size": OUTPUT.stat().st_size,
                "sha256": digest_file(OUTPUT),
                "md5_base64": digest_file(OUTPUT, "md5"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

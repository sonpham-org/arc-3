"""Build the exact champion bundle with one configurable history-limit delta."""

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
OUTPUT = ROOT / "bundle-q38-flashnext-rtdv12-cap14-kaggle11p44-context-sweep-r1-20260905.tgz"
TARGET_SUFFIX = "src/ARC3-Inference/inference/agent/tool_agent.py"
OLD = b"_PERSISTENT_HISTORY_ASSISTANT_TURNS = 30"
NEW = (
    b'_PERSISTENT_HISTORY_ASSISTANT_TURNS = max(1, _get_env_int('
    b'"ARC3_PERSISTENT_HISTORY_ASSISTANT_TURNS", 30))'
)


def digest_bytes(data: bytes, algorithm: str = "sha256") -> str:
    value = hashlib.new(algorithm, data).digest()
    return base64.b64encode(value).decode("ascii") if algorithm == "md5" else value.hex()


def digest_file(path: Path, algorithm: str = "sha256") -> str:
    checksum = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return base64.b64encode(checksum.digest()).decode("ascii") if algorithm == "md5" else checksum.hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError(f"Refusing to overwrite immutable release: {OUTPUT}")

    changed: list[str] = []
    expected_hashes: dict[str, str] = {}
    with tarfile.open(SOURCE, "r:gz") as source, tarfile.open(
        OUTPUT, "w:gz", format=tarfile.PAX_FORMAT
    ) as target:
        for original in source.getmembers():
            info = copy.copy(original)
            if not original.isfile():
                target.addfile(info)
                continue
            stream = source.extractfile(original)
            if stream is None:
                raise RuntimeError(f"Unreadable member: {original.name}")
            data = stream.read()
            if original.name.lstrip("./").endswith(TARGET_SUFFIX):
                if data.count(OLD) != 1:
                    raise RuntimeError("History-limit anchor drift")
                data = data.replace(OLD, NEW)
                ast.parse(data.decode("utf-8"), filename=original.name)
                changed.append(original.name)
                info.size = len(data)
            expected_hashes[original.name] = digest_bytes(data)
            target.addfile(info, io.BytesIO(data))

    if len(changed) != 1:
        raise RuntimeError(f"Expected one behavioral file delta, got {changed}")

    with tarfile.open(OUTPUT, "r:gz") as archive:
        members = archive.getmembers()
        source_names = []
        with tarfile.open(SOURCE, "r:gz") as source:
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
                "output": OUTPUT.name,
                "changed_members": changed,
                "history_env": "ARC3_PERSISTENT_HISTORY_ASSISTANT_TURNS",
                "default_history_turns": 30,
                "files": sum(1 for value in expected_hashes),
                "size": OUTPUT.stat().st_size,
                "sha256": digest_file(OUTPUT),
                "md5_base64": digest_file(OUTPUT, "md5"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

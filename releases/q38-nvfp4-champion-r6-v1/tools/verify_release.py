from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str) -> None:
    raise RuntimeError(message)


def main() -> None:
    lock = json.loads((ROOT / "CHAMPION_LOCK.json").read_text(encoding="utf-8"))
    for item in lock["objects"]:
        path = ROOT / item["path"]
        if not path.is_file():
            fail(f"missing {path}")
        if path.stat().st_size != item["bytes"]:
            fail(f"size drift {path}: {path.stat().st_size} != {item['bytes']}")
        actual = sha256(path)
        if actual != item["sha256"]:
            fail(f"SHA-256 drift {path}: {actual} != {item['sha256']}")

    startup = ROOT / "gcp" / "startup.sh"
    if not startup.is_file() or sha256(startup) != lock["gcp"]["startup_sha256"]:
        fail("exact GCP startup is missing or drifted")

    setup = (ROOT / "kaggle" / "kaggle_nvfp4_world_model_setup.py").read_text(encoding="utf-8")
    forbidden = ['"--linear-backend", "cutlass"', "PLU2"]
    for marker in forbidden:
        if marker in setup:
            fail(f"forbidden Kaggle parity marker present: {marker}")
    required = [
        "install_exact_arc_runtime()",
        "arc_agi-0.9.8-py3-none-any.whl",
        "arcengine-0.9.3-py3-none-any.whl",
        lock["serving_runtime"]["requirements_lock_sha256"],
        lock["model"]["revision"],
    ]
    for marker in required:
        if marker not in setup:
            fail(f"required Kaggle parity marker missing: {marker}")
    print(f"OK: {lock['release_id']} is complete and hash-clean")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


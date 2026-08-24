from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
LOCK_PATH = ROOT / "CHAMPION_LOCK.json"
GCLOUD = "gcloud.cmd" if os.name == "nt" else "gcloud"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(*args: str) -> bytes:
    return subprocess.check_output(args)


def write_exact(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_bytes() == payload:
        return
    path.write_bytes(payload)


def main() -> None:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    template_name = lock["gcp"]["instance_template"]
    template_raw = run(
        GCLOUD, "compute", "instance-templates", "describe", template_name, "--format=json"
    )
    template = json.loads(template_raw)
    if str(template["id"]) != lock["gcp"]["instance_template_id"]:
        raise RuntimeError("GCP template id drift")
    items = {item["key"]: item["value"] for item in template["properties"]["metadata"]["items"]}
    startup = items["startup-script"].encode("utf-8")
    actual_startup = hashlib.sha256(startup).hexdigest()
    if actual_startup != lock["gcp"]["startup_sha256"]:
        raise RuntimeError(f"GCP startup drift: {actual_startup}")
    write_exact(ROOT / "gcp" / "startup.sh", startup)
    write_exact(ROOT / "gcp" / "shutdown.sh", items["shutdown-script"].encode("utf-8"))
    write_exact(
        ROOT / "gcp" / "instance-template.json",
        (json.dumps(template, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )

    canonical_setup = (
        REPO_ROOT
        / "work"
        / "kaggle-nvfp4-world-model-submit-20260821"
        / "dataset-v18-wheelname-repair"
        / "kaggle_nvfp4_world_model_setup.py"
    )
    if not canonical_setup.is_file():
        raise FileNotFoundError(f"Corrected canonical Kaggle setup is missing: {canonical_setup}")
    (ROOT / "kaggle").mkdir(parents=True, exist_ok=True)
    shutil.copy2(canonical_setup, ROOT / "kaggle" / canonical_setup.name)

    for item in lock["objects"]:
        destination = ROOT / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file() and destination.stat().st_size == item["bytes"]:
            if sha256(destination) == item["sha256"]:
                continue
        with tempfile.TemporaryDirectory(prefix="arc3-champion-") as temporary:
            downloaded = Path(temporary) / destination.name
            subprocess.run(
                [GCLOUD, "storage", "cp", f"{item['gcs']}#{item['generation']}", str(downloaded)],
                check=True,
            )
            actual = sha256(downloaded)
            if downloaded.stat().st_size != item["bytes"] or actual != item["sha256"]:
                raise RuntimeError(f"Artifact drift: {item['gcs']}#{item['generation']} = {actual}")
            os.replace(downloaded, destination)
    print(f"Champion snapshot reconstructed and verified at {ROOT}")


if __name__ == "__main__":
    main()

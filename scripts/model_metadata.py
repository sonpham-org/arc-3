"""Extract and validate immutable model identity from preserved run manifests."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")


class ModelMetadataError(ValueError):
    """Raised when a run does not carry a trustworthy model identity."""


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelMetadataError(f"invalid model metadata file: {path}") from exc
    if not isinstance(value, dict):
        raise ModelMetadataError(f"model metadata must be a JSON object: {path}")
    return value


def _file_evidence(path: Path) -> dict[str, str]:
    return {
        "file": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def validate_model_metadata(value: Any, *, require_revision: bool = True) -> dict[str, Any]:
    """Return normalized model metadata or raise with a publication-safe error."""

    if not isinstance(value, dict):
        raise ModelMetadataError("catalog entry is missing structured model metadata")
    model_id = value.get("id")
    revision = value.get("revision")
    if not isinstance(model_id, str) or not MODEL_ID_RE.fullmatch(model_id):
        raise ModelMetadataError("model.id must be a non-empty repository/model identifier")
    if require_revision and (not isinstance(revision, str) or not REVISION_RE.fullmatch(revision)):
        raise ModelMetadataError("model.revision must be the full 40-character lowercase commit SHA")
    if revision not in (None, "") and (
        not isinstance(revision, str) or not REVISION_RE.fullmatch(revision)
    ):
        raise ModelMetadataError("model.revision must be the full 40-character lowercase commit SHA")

    normalized = dict(value)
    normalized["id"] = model_id.strip()
    if revision:
        normalized["revision"] = revision
        normalized["display"] = f"{normalized['id']}@{revision[:8]}"
    else:
        normalized.pop("revision", None)
        normalized["display"] = normalized["id"]
    quantization = normalized.get("quantization")
    if quantization is not None and not isinstance(quantization, str):
        raise ModelMetadataError("model.quantization must be a string when present")
    evidence = normalized.get("evidence")
    if evidence is not None and not isinstance(evidence, list):
        raise ModelMetadataError("model.evidence must be a list when present")
    return normalized


def extract_model_metadata(run_dir: Path, *, require_revision: bool = True) -> dict[str, Any]:
    """Read model identity from LAUNCH_STATE/model-info preserved with a run.

    The two files are written by the launch system and copied by publish_run.sh.
    Their content hashes make the catalog claim auditable without publishing local
    paths or relying on a run-name convention.
    """

    run_dir = Path(run_dir)
    launch_path = run_dir / "LAUNCH_STATE.json"
    info_path = run_dir / "model-info.json"
    if not launch_path.is_file() and not info_path.is_file():
        raise ModelMetadataError(
            f"{run_dir.name}: missing LAUNCH_STATE.json/model-info.json; refusing an unlabelled upload"
        )

    model_id: Any = None
    revision: Any = None
    quantization: Any = None
    evidence: list[dict[str, str]] = []
    if launch_path.is_file():
        launch = _read_object(launch_path)
        model = launch.get("model") or {}
        if not isinstance(model, dict):
            raise ModelMetadataError(f"model must be an object in {launch_path}")
        model_id = model.get("id")
        revision = model.get("revision")
        quantization = model.get("quantization") or model.get("routed_experts")
        evidence.append(_file_evidence(launch_path))
    if info_path.is_file():
        info = _read_object(info_path)
        info_id = info.get("model_id") or info.get("id")
        info_revision = info.get("revision")
        if model_id and info_id and model_id != info_id:
            raise ModelMetadataError("LAUNCH_STATE.json and model-info.json disagree on model id")
        if revision and info_revision and revision != info_revision:
            raise ModelMetadataError("LAUNCH_STATE.json and model-info.json disagree on revision")
        model_id = model_id or info_id
        revision = revision or info_revision
        quantization = info.get("quantization") or quantization
        evidence.append(_file_evidence(info_path))

    value: dict[str, Any] = {
        "id": model_id,
        "revision": revision,
        "evidence": evidence,
    }
    if quantization:
        value["quantization"] = str(quantization)
    return validate_model_metadata(value, require_revision=require_revision)

"""Prepare the exact Qwen3.8 xhigh checkpoint-8 Chinese-prompt submission.

The source kernel is the downloaded artifact behind Kaggle submission 55551321.
The source dataset is its Qwen3.8 xhigh checkpoint-8 dataset.  The only agent
replacement is the two-file Chinese prompt implementation already running in
the GCP replicas launched at 2026-08-17 23:45:18 UTC.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATASET = ROOT / "work" / "kaggle-taaf-native-cap8-qwen38-xhigh-dataset"
SOURCE_KERNEL = ROOT / "work" / "kaggle-submission-55551321-v342637750"
SOURCE_NOTEBOOK = SOURCE_KERNEL / "arc3-qwen3-8-xhigh-taaf-native-checkpoint-cap8.ipynb"
CHINESE_AGENT = (
    ROOT
    / "work"
    / "q38-taaf-cap8-zh-20260817"
    / "bundle"
    / "src"
    / "ARC3-Inference"
    / "inference"
    / "agent"
)

OUT_DATASET = ROOT / "work" / "kaggle-taaf-native-cap8-qwen38-zh-dataset"
OUT_KERNEL = ROOT / "work" / "kaggle-qwen38-zh-submit"
OUT_NOTEBOOK = OUT_KERNEL / "arc3-qwen38-xhigh-taaf-native-cap8-zh.ipynb"

OLD_DATASET_REF = "sonphamorg/taaf-source-native-cap8-qwen38-xhigh"
NEW_DATASET_REF = "sonphamorg/taaf-source-native-cap8-qwen38-zh"
KERNEL_ID = "sonphamorg/arc3-qwen3-8-xhigh-taaf-native-cap8-zh"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_dataset() -> dict[str, str]:
    if OUT_DATASET.exists():
        raise FileExistsError(f"Refusing to overwrite {OUT_DATASET}")
    shutil.copytree(SOURCE_DATASET, OUT_DATASET)

    target_agent = OUT_DATASET / "src" / "ARC3-Inference" / "inference" / "agent"
    source_files = {
        "tool_agent.py": CHINESE_AGENT / "tool_agent.py",
        "prompts_zh.py": CHINESE_AGENT / "prompts_zh.py",
    }
    hashes: dict[str, str] = {}
    for name, source in source_files.items():
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copy2(source, target_agent / name)
        hashes[name] = sha256(source)
        if sha256(target_agent / name) != hashes[name]:
            raise RuntimeError(f"Hash mismatch after copying {name}")

    tool_agent = (target_agent / "tool_agent.py").read_text(encoding="utf-8")
    prompts = (target_agent / "prompts_zh.py").read_text(encoding="utf-8")
    solver = (
        OUT_DATASET
        / "src"
        / "ARC3-Inference"
        / "inference"
        / "framework"
        / "solver.py"
    ).read_text(encoding="utf-8")
    if solver.count("batch_checkpoint_limit = 8") != 1:
        raise RuntimeError("Expected exactly one checkpoint-8 literal")
    if "你是一个正在解决网格谜题游戏的编程智能体" not in tool_agent + prompts:
        raise RuntimeError("Chinese system prompt marker is missing")

    metadata_path = OUT_DATASET / "dataset-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update(
        {
            "title": "TAAF checkpoint8 Qwen3.8 xhigh Chinese prompts",
            "id": NEW_DATASET_REF,
        }
    )
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "derived_from_submission": 55551321,
        "derived_from_script_version_id": 342637750,
        "model": "Qwen/Qwen3.8-27B-FP8",
        "model_revision": "017b9c7af6b5689d5dd426a76e0bc077eb5ca20a",
        "reasoning_effort": "xhigh",
        "preserve_thinking": True,
        "harness": "native TAAF plus checkpoint cap-8",
        "prompt_language": "Simplified Chinese",
        "analyzer_concurrency": 28,
        "sampling": {"temperature": 0.6, "top_p": 0.95, "top_k": 20},
        "source_gcp_runs": [
            "g4run-q38-taaf-cap8-zh-p1-20260817-234518",
            "g4run-q38-taaf-cap8-zh-p2-20260817-234518",
        ],
        "source_file_sha256": hashes,
    }
    (OUT_DATASET / "QWEN38_CHINESE_PROMPT_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return hashes


def prepare_kernel() -> None:
    if OUT_KERNEL.exists():
        raise FileExistsError(f"Refusing to overwrite {OUT_KERNEL}")
    OUT_KERNEL.mkdir(parents=True)

    notebook = json.loads(SOURCE_NOTEBOOK.read_text(encoding="utf-8"))
    serialized = json.dumps(notebook)
    count = serialized.count(OLD_DATASET_REF)
    if count < 1:
        raise RuntimeError(f"Notebook is missing dataset reference {OLD_DATASET_REF}")
    serialized = serialized.replace(OLD_DATASET_REF, NEW_DATASET_REF)
    notebook = json.loads(serialized)

    marker = (
        "# Prompt-language ablation: exact Qwen3.8 xhigh native-TAAF "
        "checkpoint-8 harness with faithful Simplified Chinese system/user prompts.\n"
    )
    notebook["cells"][12]["source"] = [marker, *notebook["cells"][12]["source"]]
    for cell in notebook["cells"]:
        cell.pop("id", None)
        if cell.get("cell_type") == "code":
            cell["outputs"] = []
            cell["execution_count"] = None
    OUT_NOTEBOOK.write_text(json.dumps(notebook, indent=1) + "\n", encoding="utf-8")

    metadata = json.loads((SOURCE_KERNEL / "kernel-metadata.json").read_text(encoding="utf-8"))
    metadata.pop("id_no", None)
    metadata.update(
        {
            "id": KERNEL_ID,
            "title": "ARC3 Qwen3.8 xhigh TAAF checkpoint8 Chinese",
            "code_file": OUT_NOTEBOOK.name,
            "is_private": True,
        }
    )
    metadata["dataset_sources"] = [
        NEW_DATASET_REF if source == OLD_DATASET_REF else source
        for source in metadata["dataset_sources"]
    ]
    (OUT_KERNEL / "kernel-metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )

    rendered = OUT_NOTEBOOK.read_text(encoding="utf-8")
    if OLD_DATASET_REF in rendered or NEW_DATASET_REF not in rendered:
        raise RuntimeError("Notebook dataset reference replacement failed")


def main() -> None:
    hashes = prepare_dataset()
    prepare_kernel()
    print(json.dumps({"dataset": str(OUT_DATASET), "kernel": str(OUT_KERNEL), "hashes": hashes}, indent=2))


if __name__ == "__main__":
    main()

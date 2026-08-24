from __future__ import annotations

import argparse
import json
from pathlib import Path


DATASET_REF = "sonphamorg/arc3-q38-champion-hermetic-v1"
WHEELHOUSE_REF = "sonphamorg/arc3-vllm-wheelhouse-v0271-gcp-cu130-exact"
MODEL_REF = "sonphamorg/qwen3-8-27b-nvfp4-gcp-exact/PyTorch/gcp-exact/1"
KERNEL_ID = "sonphamorg/arc3-q38-champion-hermetic-audit"
NOTEBOOK_NAME = "arc3-q38-champion-hermetic-audit.ipynb"


def source_text(cell: dict) -> str:
    value = cell.get("source", "")
    return "".join(value) if isinstance(value, list) else str(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite {args.output}")
    args.output.mkdir(parents=True)

    notebook = json.loads(args.template.read_text(encoding="utf-8"))
    replacements = 0
    for cell in notebook["cells"]:
        text = source_text(cell)
        updated = text.replace(
            'DATASET_SOURCES = ["sonphamorg/taaf-q38-nvfp4-world-model-curator", "sonphamorg/arc3-vllm-wheelhouse-v0271-gcp-cu130-exact"]',
            f'DATASET_SOURCES = ["{DATASET_REF}", "{WHEELHOUSE_REF}"]',
        )
        updated = updated.replace('        "arc-agi",', '        "arc-agi==0.9.8",')
        if updated != text:
            replacements += 1
            cell["source"] = updated
        if cell.get("cell_type") == "code":
            cell["outputs"] = []
            cell["execution_count"] = None
    if replacements != 2:
        raise RuntimeError(f"Expected two notebook parity replacements, got {replacements}")
    rendered = json.dumps(notebook, indent=1) + "\n"
    required = [DATASET_REF, WHEELHOUSE_REF, "arc-agi==0.9.8", "7920.0", "concurrency = 28"]
    for marker in required:
        if marker not in rendered:
            raise RuntimeError(f"Notebook parity marker missing: {marker}")
    if "PLU2" in rendered:
        raise RuntimeError("Champion notebook must not mention PLU2")
    (args.output / NOTEBOOK_NAME).write_text(rendered, encoding="utf-8")

    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    metadata.update(
        {
            "id": KERNEL_ID,
            "title": "ARC3 Q38 champion hermetic audit",
            "code_file": NOTEBOOK_NAME,
            "is_private": True,
            "dataset_sources": [DATASET_REF, WHEELHOUSE_REF],
            "model_sources": [MODEL_REF],
        }
    )
    metadata.pop("id_no", None)
    (args.output / "kernel-metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"kernel": KERNEL_ID, "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()

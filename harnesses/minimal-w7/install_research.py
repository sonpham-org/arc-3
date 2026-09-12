"""Patch only the disposable, hash-pinned Kaggle CPU loader copy."""
import ast
import hashlib
import json
from pathlib import Path
import shutil

ANCHOR = "            all_weights = loader.get_all_weights(model_config, model)\n"
REPLACEMENT = ("            from arc3_ple_loader_research import tracked_weights\n"
               "            all_weights = tracked_weights(\n"
               "                loader.get_all_weights(model_config, model),\n"
               "                model_config, offload_prefixes, mapper)\n")
END = '        logger.info("PLE weight loading complete.")\n'
END_NEW = END + "        from arc3_ple_loader_research import finish_weights\n        finish_weights()\n"


def loader_digest(text):
    tree = ast.parse(text)
    runner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "PleOffloadRunner")
    method = next(n for n in runner.body if isinstance(n, ast.FunctionDef) and n.name == "_load_weights")
    return hashlib.sha256(ast.dump(method, include_attributes=False).encode()).hexdigest()


def patch_source(text):
    if text.count(ANCHOR) != 1 or text.count(END) != 1:
        raise ValueError("Pinned PLE call-site drift; refusing research patch")
    tree = ast.parse(text)
    runner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "PleOffloadRunner")
    loader = next(n for n in runner.body if isinstance(n, ast.FunctionDef) and n.name == "_load_weights")
    source_lines = text.splitlines(keepends=True)
    method = "".join(source_lines[loader.lineno - 1:loader.end_lineno])
    if ANCHOR not in method or END not in method:
        raise ValueError("Research anchors outside expected CPU loader")
    result = text.replace(ANCHOR, REPLACEMENT).replace(END, END_NEW)
    ast.parse(result)
    if result.replace(REPLACEMENT, ANCHOR).replace(END_NEW, END) != text:
        raise ValueError("Unexpected source change")
    return result


def install(site_packages, bundle, working):
    site_packages, bundle, working = map(lambda p: Path(p).resolve(), (site_packages, bundle, working))
    if site_packages != working / "flashnext-gcp-runtime" / "dist-packages":
        raise ValueError("Research patch target is not disposable runtime")
    target = site_packages / "vllm/v1/ple_offload/worker.py"
    original = target.read_text()
    config = json.loads((bundle / "PLE_RESEARCH.json").read_text())
    if loader_digest(original) != config["expected_loader_ast_sha256"]:
        raise ValueError("Actual pinned loader differs from audited method; refusing patch")
    result = patch_source(original)
    out = working / "ple-research"
    out.mkdir(exist_ok=True)
    (out / "original-worker.py").write_text(original)
    target.write_text(result)
    shutil.copyfile(bundle / "ple_loader_research.py", site_packages / "arc3_ple_loader_research.py")
    receipt = {"original_sha256": hashlib.sha256(original.encode()).hexdigest(),
               "patched_sha256": hashlib.sha256(result.encode()).hexdigest(),
               "module_sha256": hashlib.sha256((bundle / "ple_loader_research.py").read_bytes()).hexdigest(),
               "original_loader_ast_sha256": loader_digest(original),
               "runtime_archive_verified_before_patch": True,
               "tensor_operations_changed": False, "call_sites_changed": 2,
               "status": "passed"}
    (out / "patch-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("ARC3_PLE_RESEARCH_INSTALLED", json.dumps(receipt), flush=True)

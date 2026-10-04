"""CPU test of ple_cache.model_view (4-Oct-2026): a fake checkpoint whose files mix dense weights with BF16 experts and
n-gram table shards (as the HF Flash-Next checkpoint does). The view must index only the kept tensors, rewrite mixed
files with exactly those (bit-identical), symlink files that are all kept, and leave out files with nothing kept:
transformers reads every tensor of each file it opens, so no dropped tensor may sit in any file of the view.

  python test_model_view.py      (needs torch, safetensors)
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import torch
from safetensors import safe_open
from safetensors.torch import save_file

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ple_cache  # noqa: E402

RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, name: str) -> None:
    RESULTS.append((bool(ok), name))
    print(("PASS " if ok else "FAIL ") + name, flush=True)


def main() -> int:
    L = "model.language_model.layers"
    files = {
        "model-00001-of-00004.safetensors": {f"{L}.0.self_attn.q_proj.weight": (8, 4),
                                             f"{L}.0.mlp.experts.gate_up_proj": (4, 8, 4)},             # mixed
        "model-00002-of-00004.safetensors": {f"{L}.1.ple.key_proj.weight": (8, 4),
                                             f"{L}.1.ple.ple_embedding.ngram_embedding.shard_0.weight": (16, 4)},   # mixed
        "model-00003-of-00004.safetensors": {f"{L}.1.linear_attn.out_proj.weight": (4, 4)},             # all kept
        "model-00004-of-00004.safetensors": {f"{L}.1.ple.ple_embedding.ngram_embedding.shard_1.weight": (16, 4)},  # none
    }
    g = torch.Generator().manual_seed(0)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        src, out = Path(tmp) / "ckpt", Path(tmp) / "ckpt-view"
        src.mkdir()
        wm = {}
        for f, spec in files.items():
            save_file({k: torch.randn(*shape, generator=g).to(torch.bfloat16) for k, shape in spec.items()}, str(src / f))
            wm.update({k: f for k in spec})
        (src / "model.safetensors.index.json").write_text(json.dumps({"metadata": {}, "weight_map": wm}))
        (src / "config.json").write_text("{}")
        ple_cache.model_view(src, out, drop_table=True, drop_experts=True)
        idx = json.loads((out / "model.safetensors.index.json").read_text())["weight_map"]
        want = {f"{L}.0.self_attn.q_proj.weight", f"{L}.1.ple.key_proj.weight", f"{L}.1.linear_attn.out_proj.weight"}
        check(set(idx) == want, "the view indexes exactly the kept tensors")
        present = {}
        for f in {p.name for p in out.glob("*.safetensors")}:
            with safe_open(str(out / f), framework="pt") as sf:
                present.update({k: f for k in sf.keys()})
        check(set(present) == want, "no file of the view holds a dropped tensor (experts, table shards)")
        same = True
        for k, f in idx.items():
            with safe_open(str(out / f), framework="pt") as a, safe_open(str(src / wm[k]), framework="pt") as b:
                same &= torch.equal(a.get_tensor(k), b.get_tensor(k))
        check(same, "kept tensors are bit-identical to the source")
        check((out / "model-00003-of-00004.safetensors").exists()
              and not (out / "model-00004-of-00004.safetensors").exists()
              and (out / "view-model-00001-of-00004.safetensors").exists() and (out / "config.json").exists(),
              "all-kept files linked as is, nothing-kept files left out, mixed files rewritten, config linked")
        check(ple_cache.default_view_dir("/opt/m/bf16", True, True).name == "bf16-view-notable-noexperts",
              "default view dir next to the model, named by what it drops")
    bad = [n for ok, n in RESULTS if not ok]
    print(f"{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed" + (f"; FAILED {bad}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

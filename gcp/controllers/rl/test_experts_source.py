"""CPU test of nvfp4_experts' expert sources (4-Oct-2026): a tiny fake GPTQ checkpoint, stacked once
(stack_layers), mapped read-only (load_packed source="mmap" reads these files), must give the exact tensors the
checkpoint reader gives, and NVFP4Experts.weights() on them must equal the direct unpack. No GPU, no transformers.

  python test_experts_source.py      (needs torch, numpy, safetensors)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["ARC3_GPTQ_GROUP"] = "32"
import torch
from safetensors.torch import save_file

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nvfp4_experts as ne  # noqa: E402

H, I, E, LAYERS = 64, 32, 4, (0, 1)
RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, name: str) -> None:
    RESULTS.append((bool(ok), name))
    print(("PASS " if ok else "FAIL ") + name, flush=True)


def fake_ckpt(d: Path) -> None:
    g = torch.Generator().manual_seed(0)
    tensors, wm = {}, {}
    for layer in LAYERS:
        for e in range(E):
            for proj, (n_in, n_out) in (("gate_proj", (H, I)), ("up_proj", (H, I)), ("down_proj", (I, H))):
                pre = f"model.language_model.layers.{layer}.mlp.experts.{e}.{proj}."
                tensors[pre + "qweight"] = torch.randint(-2**31, 2**31 - 1, (n_in // 8, n_out), generator=g, dtype=torch.int64).to(torch.int32)
                tensors[pre + "qzeros"] = torch.randint(-2**31, 2**31 - 1, (n_in // 32, n_out // 8), generator=g, dtype=torch.int64).to(torch.int32)
                tensors[pre + "scales"] = (torch.rand(n_in // 32, n_out, generator=g) * 0.01).to(torch.float16)
    f = "model-00001-of-00001.safetensors"
    save_file(tensors, str(d / f))
    wm = {k: f for k in tensors}
    (d / "model.safetensors.index.json").write_text(json.dumps({"weight_map": wm}))
    (d / "config.json").write_text(json.dumps({"text_config": {"num_experts": E}}))


def experts_with(packed: dict) -> ne.NVFP4Experts:
    ex = ne.NVFP4Experts.__new__(ne.NVFP4Experts)
    torch.nn.Module.__init__(ex)
    for k, v in packed.items():
        setattr(ex, k, v)
    ex.fmt = "gptq"
    return ex


def main() -> int:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:   # Windows keeps mapped files open
        ck, st = Path(tmp) / "ckpt", Path(tmp) / "ckpt-stacked"
        ck.mkdir()
        fake_ckpt(ck)
        rep = ne.stack_layers(ck, st)
        check(rep["layers"] == len(LAYERS) and (st / "index.json").exists(), "stack_layers writes every layer + index")
        index = json.loads((st / "index.json").read_text())
        wm = json.loads((ck / "model.safetensors.index.json").read_text())["weight_map"]
        for layer in LAYERS:
            ref = ne.read_layer_gptq(ck, layer, E, wm)
            mapped = {k: ne._mapped(st, meta) for k, meta in index["layers"][str(layer)].items()}
            check(set(ref) == set(mapped) and all(torch.equal(ref[k], mapped[k]) and ref[k].dtype == mapped[k].dtype
                                                  for k in ref), f"layer {layer}: mapped tensors == checkpoint reader")
            import numpy as np
            meta = index["layers"][str(layer)]["g_qw"]
            arr = np.memmap(st / meta["file"], dtype=np.uint8, mode="r")
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                t = torch.from_numpy(arr)
            check(t.data_ptr() == arr.ctypes.data and not arr.flags.writeable,
                  f"layer {layer}: a mapped tensor is the read-only mapping itself (zero-copy: one page-cache copy)")
            a, b = experts_with(ref).weights(), experts_with(mapped).weights("cpu")
            check(torch.equal(a[0], b[0]) and torch.equal(a[1], b[1]),
                  f"layer {layer}: weights() on the mapped experts == on the reader's (gate_up {tuple(a[0].shape)})")
            direct = ne.dequant_gptq(ref["d_qw"], ref["d_qz"], ref["d_s"])
            check(torch.equal(direct, a[1]), f"layer {layer}: weights() down == dequant_gptq")
    bad = [n for ok, n in RESULTS if not ok]
    print(f"{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed" + (f"; FAILED {bad}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

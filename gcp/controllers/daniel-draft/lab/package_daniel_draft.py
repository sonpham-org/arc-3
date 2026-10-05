"""Package a fine-tuned draft for Daniel Franzen's stack (2-Oct-2026, daniel-draft lab).

OUT = a copy of his drafter dir in which mtp-dense.safetensors carries the trained dense mtp.* tensors (train_draft.py's
draft_ft.pt, checkpoint names, bf16) and everything else is byte-identical: embed_tokens, lm_head, the INT4 routed
experts file, config.json (compressed-tensors setup), tokenizer files, index. The trained tensors have his tensors'
names, dtypes and shapes, so they are written in place over a copy of his file (same header, same offsets).

  python package_daniel_draft.py --drafter DRAFTER_DIR --ft draft_ft.pt --out OUT_DIR
"""
import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path

import torch

DENSE = "mtp-dense.safetensors"
NP = {"BF16": torch.bfloat16, "F16": torch.float16, "F32": torch.float32}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drafter", type=Path, required=True)
    ap.add_argument("--ft", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    ft = torch.load(a.ft, map_location="cpu")
    a.out.mkdir(parents=True, exist_ok=True)
    for p in sorted(a.drafter.iterdir()):
        if p.is_file() and p.name != DENSE:
            shutil.copy2(p, a.out / p.name)
    dst = a.out / DENSE
    shutil.copyfile(a.drafter / DENSE, dst)
    with open(dst, "r+b") as f:
        (hl,) = struct.unpack("<Q", f.read(8))
        head = json.loads(f.read(hl))
        base = 8 + hl
        changed = {}
        for n, t in sorted(ft.items()):
            info = head[n]  # KeyError = a tensor his drafter does not have: refuse
            dt = NP[info["dtype"]]
            assert list(t.shape) == info["shape"], (n, tuple(t.shape), info["shape"])
            a0, b0 = info["data_offsets"]
            f.seek(base + a0)
            old = torch.frombuffer(bytearray(f.read(b0 - a0)), dtype=dt).reshape(info["shape"])
            new = t.to(dt).contiguous()
            raw = new.view(torch.uint8).numpy().tobytes() if dt != torch.bfloat16 else new.view(torch.int16).numpy().tobytes()
            assert len(raw) == b0 - a0, (n, len(raw), b0 - a0)
            f.seek(base + a0)
            f.write(raw)
            changed[n] = round(float((new.float() - old.float()).norm() / old.float().norm().clamp_min(1e-12)), 6)
    assert not any(n in ft for n in ("lm_head.weight", "model.language_model.embed_tokens.weight")), "shared tensors"
    report = {"source": str(a.drafter), "ft": str(a.ft), "tensors_replaced": len(changed),
              "max_rel_change": max(changed.values()) if changed else 0.0,
              "rel_change": changed, "mtp_dense_sha256": sha256(dst)}
    (a.out / "TUNED.json").write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k != "rel_change"}), flush=True)


if __name__ == "__main__":
    main()

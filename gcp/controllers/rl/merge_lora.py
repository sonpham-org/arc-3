"""Merge a LoRA adapter into a served checkpoint's BF16 tensors in place (plan §3 and §9 B7).

The adapter's targets (full attention, linear attention, shared expert) are BF16 in every served form: the
RadixArk / NVIDIA NVFP4 checkpoints and Intel's W4A16 (checked 1-Oct: Intel's --ignore_layers list). So a merge
only rewrites those tensors' bytes; every other byte of every shard, and every shard without a target, stays
identical. The safetensors header is never rewritten: each target is overwritten at its own data offset.

Checks built in:
- zero adapter (B = 0) must give byte-identical shards (`--expect-identical`);
- per tensor, the share of the update that survives rounding to BF16: ||merged - W|| / ||dW||. Small RL updates
  can round away in BF16 (a weight's last-bit step is ~0.4% of it); `--stochastic` rounds without bias.

Usage:
  python merge_lora.py --adapter adapters/r0 --checkpoint /mnt/m/intel-w4a16 --out /mnt/m/intel-w4a16-r0 [--stochastic]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
from pathlib import Path

import torch
from safetensors import safe_open


def read_header(path: Path) -> tuple[dict, int]:
    with open(path, "rb") as fh:
        n = struct.unpack("<Q", fh.read(8))[0]
        header = json.loads(fh.read(n))
    return header, 8 + n


def lora_pairs(adapter_dir: Path) -> tuple[dict[str, tuple[torch.Tensor, torch.Tensor]], float]:
    """{checkpoint tensor name: (A [r, in], B [out, r])} and the scale alpha / r."""
    cfg = json.loads((adapter_dir / "adapter_config.json").read_text())
    scale = float(cfg["lora_alpha"]) / float(cfg["r"])
    tensors = {}
    for f in sorted(adapter_dir.glob("adapter_model*.safetensors")):
        with safe_open(str(f), framework="pt") as sf:
            for k in sf.keys():
                tensors[k] = sf.get_tensor(k)
    pairs = {}
    for k, a in tensors.items():
        if ".lora_A." not in k:
            continue
        b = tensors[k.replace(".lora_A.", ".lora_B.")]
        name = re.sub(r"^base_model\.model\.", "", k.replace(".lora_A.weight", ".weight"))
        pairs[name] = (a.float(), b.float())
    return pairs, scale


def to_bf16(x: torch.Tensor, stochastic: bool, gen: torch.Generator | None = None) -> torch.Tensor:
    if not stochastic:
        return x.to(torch.bfloat16)
    bits = x.contiguous().view(torch.int32)
    noise = torch.randint(0, 1 << 16, bits.shape, dtype=torch.int32, generator=gen)
    return ((bits + noise) & ~0xFFFF).view(torch.float32).to(torch.bfloat16)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def merge(adapter: Path, checkpoint: Path, out: Path, *, stochastic: bool, mult: float, seed: int) -> dict:
    pairs, scale = lora_pairs(adapter)
    index = json.loads((checkpoint / "model.safetensors.index.json").read_text())["weight_map"]
    missing = [n for n in pairs if n not in index]
    if missing:
        raise KeyError(f"{len(missing)} adapter targets not in the checkpoint, e.g. {missing[:3]}")
    out.mkdir(parents=True, exist_ok=True)
    by_shard: dict[str, list[str]] = {}
    for n in pairs:
        by_shard.setdefault(index[n], []).append(n)
    for f in checkpoint.iterdir():                     # untouched files: copied as they are
        if f.is_file() and f.name not in by_shard:
            shutil.copy2(f, out / f.name)
    gen = torch.Generator().manual_seed(seed)
    report = {"scale": scale, "mult": mult, "stochastic": stochastic, "tensors": {}}
    for shard, names in sorted(by_shard.items()):
        src, dst = checkpoint / shard, out / shard
        shutil.copy2(src, dst)
        header, base = read_header(src)
        with open(dst, "r+b") as fh:
            for n in names:
                meta = header[n]
                if meta["dtype"] != "BF16":
                    raise TypeError(f"{n} is {meta['dtype']}, not BF16: this checkpoint quantized a target")
                start, end = meta["data_offsets"]
                fh.seek(base + start)
                raw = bytearray(fh.read(end - start))
                w = torch.frombuffer(raw, dtype=torch.bfloat16).reshape(meta["shape"]).float()
                a, b = pairs[n]
                dw = (b @ a) * scale * mult
                if tuple(dw.shape) != tuple(w.shape):
                    raise ValueError(f"{n}: dW {tuple(dw.shape)} vs W {tuple(w.shape)}")
                merged = to_bf16(w + dw, stochastic, gen)
                kept = (merged.float() - w).norm().item() / max(dw.norm().item(), 1e-30)
                fh.seek(base + start)
                fh.write(merged.contiguous().view(torch.uint8).numpy().tobytes())
                report["tensors"][n] = {"dw_norm": dw.norm().item(), "w_norm": w.norm().item(),
                                        "kept_share": kept if dw.norm().item() > 0 else None}
    shards = sorted({*index.values()})
    report["sha256"] = {s: sha256(out / s) for s in shards}
    kept = [t["kept_share"] for t in report["tensors"].values() if t["kept_share"] is not None]
    report["kept_share_mean"] = sum(kept) / len(kept) if kept else None
    (out / "MERGE_REPORT.json").write_text(json.dumps(report, indent=1))
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--stochastic", action="store_true")
    ap.add_argument("--mult", type=float, default=1.0, help="dial the adapter's strength (1 = as trained)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--expect-identical", action="store_true", help="zero check: every shard must match the input")
    args = ap.parse_args()
    rep = merge(Path(args.adapter), Path(args.checkpoint), Path(args.out), stochastic=args.stochastic,
                mult=args.mult, seed=args.seed)
    print(f"merged {len(rep['tensors'])} tensors, mean kept share {rep['kept_share_mean']}")
    if args.expect_identical:
        bad = [s for s in rep["sha256"] if rep["sha256"][s] != sha256(Path(args.checkpoint) / s)]
        print("zero check:", "PASS" if not bad else f"FAIL {bad[:5]}")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

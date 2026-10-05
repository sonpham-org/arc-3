"""Rebuild a merged RL model's shards from Daniel's base shards + the model's hot-swap delta (5-Oct-2026).

The box keeps only the last 3 merged models; an older model's merged shards can be rebuilt without the trainer: its
delta (extract_delta.py: the ~300 LoRA-target tensors with their merged values) is copied, byte for byte, over the same
tensors in a copy of each base shard. Same dtype and shape, so every shard keeps its size (Daniel's input manifest
checks sizes) and its header; the result is the shard merge_lora.py --only-changed wrote, if the delta came from it
(check: --verify rebuilds one shard of a model whose merged shards still exist and compares sha256).
Pure Python (safetensors = 8-byte header length + JSON header + raw data), no torch.
  python patch_shards.py --delta <delta.safetensors> --base <dir of base shards> --report <a MERGE_REPORT.json>
                         --out <dir> [--only model-00001-of-00017.safetensors] [--expect-report <MERGE_REPORT.json>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path


def header(path: Path) -> tuple[int, dict]:
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        return 8 + n, json.loads(f.read(n))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--delta", required=True)
    ap.add_argument("--base", required=True, help="dir with Daniel's base shards")
    ap.add_argument("--report", required=True, help="a MERGE_REPORT.json of the same LoRA targets (changed_shards)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="", help="comma list of shards (default: the report's changed_shards)")
    ap.add_argument("--expect-report", default="", help="compare sha256 with this report (verification)")
    a = ap.parse_args()
    dstart, dh = header(Path(a.delta))
    dh.pop("__metadata__", None)
    rep = json.loads(Path(a.report).read_text(encoding="utf-8"))
    shards = [s for s in a.only.split(",") if s] or rep["changed_shards"]
    expect = json.loads(Path(a.expect_report).read_text(encoding="utf-8"))["sha256"] if a.expect_report else {}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    done, sha = set(), {}
    with open(a.delta, "rb") as df:
        for s in shards:
            src, dst = Path(a.base) / s, out / s
            shutil.copyfile(src, dst)
            bstart, bh = header(dst)
            n = 0
            with open(dst, "r+b") as f:
                for name, meta in bh.items():
                    if name == "__metadata__" or name not in dh:
                        continue
                    d = dh[name]
                    assert d["dtype"] == meta["dtype"] and d["shape"] == meta["shape"], (name, d, meta)
                    b0, b1 = meta["data_offsets"]
                    s0, s1 = d["data_offsets"]
                    assert b1 - b0 == s1 - s0, name
                    df.seek(dstart + s0)
                    f.seek(bstart + b0)
                    f.write(df.read(s1 - s0))
                    done.add(name)
                    n += 1
            h = hashlib.sha256()
            with open(dst, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 24), b""):
                    h.update(chunk)
            sha[s] = h.hexdigest()
            ok = "" if s not in expect else (" matches" if expect[s] == sha[s] else " DIFFERS")
            print(f"{s}: {n} tensors patched, sha256 {sha[s][:16]}{ok}", flush=True)
    missing = sorted(set(dh) - done)
    if not a.only and missing:
        raise SystemExit(f"{len(missing)} delta tensors found in no shard, e.g. {missing[:3]}")
    if not a.only:
        (out / "MERGE_REPORT.json").write_text(json.dumps({
            "rebuilt_from_delta": a.delta, "tensors": {k: {} for k in sorted(dh)}, "changed_shards": shards,
            "sha256": sha}, indent=1), encoding="utf-8")
    if expect and any(expect.get(s) != sha[s] for s in sha):
        raise SystemExit("sha256 differs from the expected report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

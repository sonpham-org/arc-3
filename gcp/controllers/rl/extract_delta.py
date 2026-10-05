"""The hot-swap delta of a merged RL model (4-Oct-2026; gtree-rollout/hotswap.py, rl/box/README.md).

merge_lora.py --only-changed rewrites the LoRA-target tensors (~300 plain bf16 projection weights, MERGE_REPORT.json
"tensors") inside the changed shards. A rollout server that stays up between rounds needs only those tensors: this
copies them, with their merged values, into one small safetensors file that hotswap.py apply loads in place. The
values are absolute (base + this round's adapter), so the file turns ANY earlier round's server into this round's.
  /opt/rl/venv/bin/python extract_delta.py --merged /opt/m/work/out/<merge job>/merged --out <dir>/delta.safetensors
Prints one JSON line (tensors, bytes, seconds); writes <out>.json next to it with the same, plus the report's sha256s.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--merged", required=True, help="merge_lora.py --out dir (MERGE_REPORT.json + changed shards)")
    ap.add_argument("--out", required=True, help="delta .safetensors to write")
    ap.add_argument("--names-from", default="", help="take the tensor names from this MERGE_REPORT.json instead "
                    "(e.g. --merged /opt/m/daniel: the BASE values of the same tensors, to swap a server back)")
    a = ap.parse_args()
    from safetensors import safe_open
    from safetensors.torch import save_file
    t = time.time()
    merged = Path(a.merged)
    rep = json.loads(Path(a.names_from or merged / "MERGE_REPORT.json").read_text(encoding="utf-8"))
    want = set(rep["tensors"])
    got: dict = {}
    for shard in sorted(merged.glob("*.safetensors")):
        with safe_open(str(shard), framework="pt", device="cpu") as f:
            for k in f.keys():
                if k in want:
                    got[k] = f.get_tensor(k).contiguous()
    missing = sorted(want - set(got))
    if missing:
        raise SystemExit(f"{len(missing)} report tensors not in the merged shards, e.g. {missing[:3]}")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    save_file(got, str(tmp), metadata={"source": str(merged)})
    os.replace(tmp, out)
    meta = {"tensors": len(got), "bytes": sum(v.numel() * v.element_size() for v in got.values()),
            "dtypes": sorted({str(v.dtype) for v in got.values()}), "s": round(time.time() - t, 1),
            "merged": str(merged), "shards_sha256": rep.get("sha256")}
    out.with_name(out.name + ".json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps({k: meta[k] for k in ("tensors", "bytes", "dtypes", "s")}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

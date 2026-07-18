#!/usr/bin/env python3
"""Normalize a resource-usage capture into docs/data/<run>/usage.json for the
usage visualizer. Handles both capture formats:

  - GCP sampler `resource.log`:
      ts_utc,gpu_util_pct,gpu_mem_used_mib,gpu_mem_total_mib,gpu_power_w,
      cpu_util_pct,mem_used_mib,mem_total_mib      (aggregate CPU, single GPU)
  - Kaggle `resource_profiler.py` CSV:
      ts_epoch,iso_time,elapsed_s,cpu_total_pct,cpu0_pct..cpuN_pct,ram_pct,
      ram_used_gb,ram_total_gb,gpu0_*..,disk_*,sampler_cpu_s   (per-core, per-GPU, disk)

Usage: python scripts/export_usage.py <capture.csv|resource.log> <run-name>
"""
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _elapsed_from_utc(rows):
    ts = [datetime.strptime(r["ts_utc"].replace("Z", ""), "%Y-%m-%dT%H:%M:%S") for r in rows]
    t0 = ts[0]
    return [round((t - t0).total_seconds() / 60.0, 3) for t in ts]


def normalize(path: Path, run: str) -> dict:
    rows = list(csv.DictReader(open(path)))
    if not rows:
        raise SystemExit(f"no rows in {path}")
    hdr = set(rows[0].keys())
    out = {"run": run, "n": len(rows)}

    if "ts_utc" in hdr:  # GCP sampler
        out["source"] = "gcp-resource-log"
        out["t_min"] = _elapsed_from_utc(rows)
        out["cpu_total_pct"] = [_f(r["cpu_util_pct"]) for r in rows]
        out["per_core_pct"] = None
        mt = _f(rows[0]["mem_total_mib"]) or 1.0
        out["ram_total_gb"] = round(mt / 1024, 1)
        out["ram_used_gb"] = [round((_f(r["mem_used_mib"]) or 0) / 1024, 2) for r in rows]
        out["ram_pct"] = [round((_f(r["mem_used_mib"]) or 0) / mt * 100, 1) for r in rows]
        gt = _f(rows[0]["gpu_mem_total_mib"]) or 1.0
        out["gpu"] = [{
            "util_pct": [_f(r["gpu_util_pct"]) for r in rows],
            "mem_used_gb": [round((_f(r["gpu_mem_used_mib"]) or 0) / 1024, 2) for r in rows],
            "mem_total_gb": round(gt / 1024, 1),
            "power_w": [_f(r["gpu_power_w"]) for r in rows],
        }]
        out["disk_used_pct"] = None
        out["disk_write_mbps"] = None
    else:  # Kaggle profiler
        out["source"] = "kaggle-profiler"
        out["t_min"] = [round((_f(r["elapsed_s"]) or 0) / 60.0, 3) for r in rows]
        out["cpu_total_pct"] = [_f(r["cpu_total_pct"]) for r in rows]
        cores = sorted((c for c in hdr if c.startswith("cpu") and c.endswith("_pct") and c != "cpu_total_pct"),
                       key=lambda c: int(c[3:-4]))
        out["per_core_pct"] = [[_f(r[c]) for r in rows] for c in cores] if cores else None
        out["ram_total_gb"] = _f(rows[0].get("ram_total_gb"))
        out["ram_used_gb"] = [_f(r.get("ram_used_gb")) for r in rows]
        out["ram_pct"] = [_f(r.get("ram_pct")) for r in rows]
        gpus = []
        g = 0
        while f"gpu{g}_util_pct" in hdr:
            gpus.append({
                "util_pct": [_f(r[f"gpu{g}_util_pct"]) for r in rows],
                "mem_used_gb": [round((_f(r[f"gpu{g}_mem_used_mb"]) or 0) / 1024, 2) for r in rows],
                "mem_total_gb": round((_f(rows[0][f"gpu{g}_mem_total_mb"]) or 0) / 1024, 1),
                "power_w": [_f(r[f"gpu{g}_power_w"]) for r in rows],
            })
            g += 1
        out["gpu"] = gpus
        out["disk_used_pct"] = [_f(r.get("disk_used_pct")) for r in rows] if "disk_used_pct" in hdr else None
        out["disk_write_mbps"] = [_f(r.get("disk_write_mbps")) for r in rows] if "disk_write_mbps" in hdr else None

    tm = out["t_min"]
    out["interval_s"] = round((tm[1] - tm[0]) * 60, 1) if len(tm) > 1 else 0
    out["duration_min"] = round(tm[-1], 1) if tm else 0
    return out


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: export_usage.py <capture.csv|resource.log> <run-name>")
    src, run = Path(sys.argv[1]), sys.argv[2]
    data = normalize(src, run)
    outdir = ROOT / "docs" / "data" / run
    outdir.mkdir(parents=True, exist_ok=True)
    json.dump(data, open(outdir / "usage.json", "w"))
    ncore = len(data["per_core_pct"]) if data["per_core_pct"] else 0
    print(f"wrote {outdir}/usage.json  source={data['source']} samples={data['n']} "
          f"interval={data['interval_s']}s dur={data['duration_min']}min cores={ncore} gpus={len(data['gpu'])}")


if __name__ == "__main__":
    main()

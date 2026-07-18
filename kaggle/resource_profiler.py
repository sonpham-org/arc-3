#!/usr/bin/env python3
"""Low-overhead resource sampler for the ARC-3 Kaggle harness.

Runs as a SEPARATE process (started via subprocess, niced to 19) so it never
contends with the harness for the GIL or a CPU core. Every ``--interval`` seconds
it records per-core CPU %, RAM, per-GPU utilisation/memory/power/temp (one
``nvidia-smi`` query), and storage, appending one CSV row that is flushed
immediately -- so the data survives even if the notebook is cut short.

Why this is ~zero overhead (NVIDIA/psutil guidance: *sample, don't trace*):
- ``psutil.cpu_percent(percpu=True)`` is a non-blocking delta read of /proc/stat.
- one ``nvidia-smi`` subprocess per sample (~30 ms) at a 10 s cadence is well
  under 0.5 % of a single core, and it is a read-only query that does not touch
  the GPU compute path.
- each row also logs the sampler's own accumulated CPU seconds, so the overhead
  is *measured*, not assumed.
"""
from __future__ import annotations

import argparse
import csv
import shutil
import signal
import subprocess
import time

try:
    import psutil
except Exception:  # pragma: no cover - psutil is present on Kaggle images
    psutil = None

_STOP = False


def _request_stop(*_):
    global _STOP
    _STOP = True


signal.signal(signal.SIGTERM, _request_stop)
signal.signal(signal.SIGINT, _request_stop)

_GPU_FIELDS = (
    "index,utilization.gpu,utilization.memory,memory.used,memory.total,"
    "power.draw,temperature.gpu"
)


def gpu_sample() -> list[list[str]]:
    """One nvidia-smi query -> list of per-GPU field lists (empty if no GPU)."""
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={_GPU_FIELDS}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return [[c.strip() for c in ln.split(",")] for ln in out.splitlines() if ln.strip()]
    except Exception:
        return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="CSV output path")
    ap.add_argument("--interval", type=float, default=10.0, help="seconds between samples")
    ap.add_argument("--disk", default="/kaggle/working", help="path to report free space for")
    ap.add_argument("--max-seconds", type=float, default=7200.0, help="self-terminate after this long")
    args = ap.parse_args()

    ncpu = psutil.cpu_count(logical=True) if psutil else 0
    if psutil:
        psutil.cpu_percent(percpu=True)  # prime: the first read is since-boot, discard it
    ngpu = len(gpu_sample())

    cols = ["ts_epoch", "iso_time", "elapsed_s", "cpu_total_pct"]
    cols += [f"cpu{i}_pct" for i in range(ncpu)]
    cols += ["ram_pct", "ram_used_gb", "ram_total_gb"]
    for g in range(ngpu):
        cols += [
            f"gpu{g}_util_pct", f"gpu{g}_mem_util_pct", f"gpu{g}_mem_used_mb",
            f"gpu{g}_mem_total_mb", f"gpu{g}_power_w", f"gpu{g}_temp_c",
        ]
    cols += ["disk_used_pct", "disk_free_gb", "disk_read_mbps", "disk_write_mbps", "sampler_cpu_s"]

    fh = open(args.out, "w", newline="")
    writer = csv.writer(fh)
    writer.writerow(cols)
    fh.flush()

    t0 = time.time()
    proc = psutil.Process() if psutil else None
    io0 = psutil.disk_io_counters() if psutil else None
    tio0 = time.time()

    while not _STOP and (time.time() - t0) < args.max_seconds:
        start = time.time()
        row = [round(start, 2), time.strftime("%Y-%m-%dT%H:%M:%S"), round(start - t0, 1)]

        if psutil:
            per = psutil.cpu_percent(percpu=True)
            row.append(round(sum(per) / max(1, len(per)), 1))
            row += [round(x, 1) for x in per]
            vm = psutil.virtual_memory()
            row += [round(vm.percent, 1), round(vm.used / 1e9, 2), round(vm.total / 1e9, 2)]
        else:
            row += [""] * (1 + ncpu + 3)

        gs = gpu_sample()
        for g in range(ngpu):
            p = gs[g] if g < len(gs) else []
            row += (p[1:7] if len(p) >= 7 else [""] * 6)

        if psutil:
            du = shutil.disk_usage(args.disk)
            row += [round(du.used / du.total * 100, 1), round(du.free / 1e9, 2)]
            io1 = psutil.disk_io_counters()
            tio1 = time.time()
            dt = max(1e-6, tio1 - tio0)
            row += [
                round((io1.read_bytes - io0.read_bytes) / dt / 1e6, 2),
                round((io1.write_bytes - io0.write_bytes) / dt / 1e6, 2),
            ]
            io0, tio0 = io1, tio1
            ct = proc.cpu_times()
            row.append(round(ct.user + ct.system, 2))
        else:
            row += ["", "", "", "", ""]

        writer.writerow(row)
        fh.flush()

        # Sleep the remainder of the interval, waking ~1 s at a time to honor SIGTERM promptly.
        while (time.time() - start) < args.interval and not _STOP:
            time.sleep(min(1.0, args.interval - (time.time() - start)))

    fh.close()


if __name__ == "__main__":
    main()

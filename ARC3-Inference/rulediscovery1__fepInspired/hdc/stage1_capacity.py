# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Stage 1 measurement (roadmap docs/plans/2026-09-24-hdc-ghost-roadmap.md): capacity curve of a phasor
#   key-value bundle -- store N (key, value) bindings in one vector, read every value back with its key and a
#   cleanup over a codebook of M values; accuracy per (D, N). Output results/hdc/stage1_capacity.json + table.
# SRP/DRY check: Pass -- uses hdc/vsa.py only.
"""Stage 1: bundle capacity per dimension."""
from __future__ import annotations

import json
from pathlib import Path

from .vsa import VSA

OUT = Path(__file__).resolve().parent.parent / "results" / "hdc"


def capacity(D: int, N: int, M: int = 64, trials: int = 5) -> float:
    ok = tot = 0
    for t in range(trials):
        v = VSA(D, seed=1000 * t + N)
        book, keys = v.rand(M), v.rand(N)
        idx = v.rng.integers(0, M, size=N)
        mem = v.bundle([v.bind(keys[i], book[idx[i]]) for i in range(N)])
        for i in range(N):
            ok += v.cleanup(v.unbind(mem, keys[i]), book) == idx[i]
            tot += 1
    return ok / tot


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    res = {D: {N: capacity(D, N) for N in (25, 50, 100, 200, 400, 800)} for D in (256, 1024, 4096)}
    lines = ["| D | " + " | ".join(f"N={n}" for n in res[256]) + " |", "|---|" + "---|" * len(res[256])]
    for D, row in res.items():
        lines.append(f"| {D} | " + " | ".join(f"{a:.3f}" for a in row.values()) + " |")
    text = "stage 1: bundle read-back accuracy, codebook of 64 values\n" + "\n".join(lines)
    print(text)
    (OUT / "stage1_capacity.json").write_text(json.dumps(res))
    (OUT / "stage1_capacity.md").write_text(text + "\n")


if __name__ == "__main__":
    main()

# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Stage 2 of docs/plans/2026-09-24-hdc-ghost-roadmap.md: a run's moves stored as ONE vector ("tape"),
#   tape = sum_k shift(move(dy_k, dx_k), k), and read back step k with shift(tape, -k) + cleanup over the move
#   codebook. Moves are grid displacements (Ghost Twin: 6 px per step in four directions, or no move), encoded
#   with fractional powers (vsa.disp). Measures exact read-back accuracy per (D, tape length). Gate: >= 99 % at
#   length 200 for the chosen D. Output results/hdc/stage2_tape.json + .md.
#   Also defines Tape (append / read / readout vector), reused by stages 3 and 4.
# SRP/DRY check: Pass -- vector operations are hdc/vsa.py; this adds only the tape and its measurement.
"""Stage 2: sequence tape by cyclic shift."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .vsa import VSA

OUT = Path(__file__).resolve().parent.parent / "results" / "hdc"
STEP = 6
MOVES = [(0, 0), (-STEP, 0), (STEP, 0), (0, -STEP), (0, STEP)]    # none, up, down, left, right (dy, dx)


class Tape:
    """One run's moves in one vector. Index k = k-th entry appended."""

    def __init__(self, vsa: VSA):
        self.v = vsa
        self.vec = np.zeros(vsa.D, dtype=complex)
        self.n = 0

    def append(self, dy: float, dx: float) -> None:
        self.vec = self.vec + self.v.shift(self.v.move(dy, dx), self.n)
        self.n += 1

    def readout(self, k: int) -> np.ndarray:
        """Noisy vector for entry k (compare with sim, or clean up)."""
        return self.v.shift(self.vec, -k)


def book(vsa: VSA) -> np.ndarray:
    return np.stack([vsa.move(dy, dx) for dy, dx in MOVES])


def accuracy(D: int, L: int, trials: int = 5) -> float:
    ok = tot = 0
    for t in range(trials):
        v = VSA(D, seed=7 * t + L)
        b = book(v)
        seq = v.rng.integers(0, len(MOVES), size=L)
        tape = Tape(v)
        for i in seq:
            tape.append(*MOVES[i])
        for k, i in enumerate(seq):
            ok += v.cleanup(tape.readout(k), b) == i
            tot += 1
    return ok / tot


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    res = {D: {L: accuracy(D, L) for L in (50, 100, 200, 400, 800)} for D in (256, 1024, 4096)}
    lines = ["| D | " + " | ".join(f"length {L}" for L in res[256]) + " |", "|---|" + "---|" * len(res[256])]
    for D, row in res.items():
        lines.append(f"| {D} | " + " | ".join(f"{a:.4f}" for a in row.values()) + " |")
    text = "stage 2: exact read-back of a move tape (5 possible moves)\n" + "\n".join(lines)
    print(text)
    (OUT / "stage2_tape.json").write_text(json.dumps(res))
    (OUT / "stage2_tape.md").write_text(text + "\n")


if __name__ == "__main__":
    main()

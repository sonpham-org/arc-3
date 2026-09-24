# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Stage 7 of docs/plans/2026-09-24-hdc-ghost-roadmap.md: does a resonator network (Frady, Kent,
#   Olshausen & Sommer 2020) beat brute force at "which earlier sequence does this object copy, and with which
#   lag"? Synthetic, so the answer is known. Time is encoded by BINDING with a time phasor (fractional power
#   T**k) instead of a cyclic shift, so a lag becomes one more binding factor:
#       tape_r = sum_k T**k * move_rk          (candidate source sequences r = 0..R-1)
#       obs    = sum_k T**k * move_{r*, k - L*} over the observed steps  ~=  T**L* * tape_r*   (+ noise)
#   Brute force: score every (r, L) pair, sim(obs, T**L * tape_r) -> R * nL similarities.
#   Resonator: alternate  L <- cleanup over lags of obs * conj(tape_r_hat),  r <- cleanup over sources of
#   obs * conj(T**L_hat), with soft (similarity-weighted) superposition estimates, ITER iterations ->
#   (R + nL) similarities per iteration.
#   Sweep: number of candidate sources R, lags nL, observed steps n. Reports accuracy and similarity count for
#   both. Output results/hdc/stage7_resonator.json + .md.
# SRP/DRY check: Pass -- vector ops from hdc/vsa.py; new: time-phasor tapes and the resonator loop.
"""Stage 7: resonator network vs brute force for (source, lag) factorization."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .stage2_tape import MOVES
from .vsa import VSA

OUT = Path(__file__).resolve().parent.parent / "results" / "hdc"
D = 4096
ITER = 20


def trial(v: VSA, R: int, nL: int, n: int, rng):
    T = v.rand()
    Tpow = np.stack([v.power(T, L) for L in range(nL)])               # lag codebook
    length = n + nL + 5
    seqs = rng.integers(0, len(MOVES), size=(R, length))
    code = np.stack([v.move(*m) for m in MOVES])
    tk = np.stack([v.power(T, k) for k in range(length + nL)])
    tapes = np.stack([(tk[:length] * code[seqs[r]]).sum(0) for r in range(R)])
    r_true, L_true = int(rng.integers(R)), int(rng.integers(nL))
    # the copier's move at time k is source r_true's move at k - L_true; observed for k = L_true .. L_true+n-1
    ks = np.arange(L_true, L_true + n)
    obs = (tk[ks] * code[seqs[r_true, ks - L_true]]).sum(0)
    # brute force
    scores = np.real(np.conj(Tpow[:, None, :] * tapes[None, :, :]) @ obs) / D   # (nL, R)
    bl, br = np.unravel_index(np.argmax(scores), scores.shape)
    brute_ok = (br == r_true) and (bl == L_true)
    # resonator with soft estimates
    r_hat = tapes.mean(0)
    L_hat = Tpow.mean(0)
    for _ in range(ITER):
        sL = np.real(np.conj(Tpow) @ (obs * np.conj(r_hat))) / D
        wL = np.exp((sL - sL.max()) * 20)
        L_hat = (wL[:, None] * Tpow).sum(0) / wL.sum()
        sR = np.real(np.conj(tapes) @ (obs * np.conj(L_hat))) / D
        wR = np.exp((sR - sR.max()) * 20)
        r_hat = (wR[:, None] * tapes).sum(0) / wR.sum()
    res_ok = (int(np.argmax(sR)) == r_true) and (int(np.argmax(sL)) == L_true)
    return brute_ok, res_ok


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    v = VSA(D, seed=0)
    rows = []
    for R, nL in ((5, 8), (20, 16), (50, 32)):
        for n in (4, 8, 16):
            bo = ro = 0
            N = 40
            for _ in range(N):
                b, r = trial(v, R, nL, n, rng)
                bo += b
                ro += r
            rows.append({"sources": R, "lags": nL, "observed_steps": n, "brute_acc": bo / N, "resonator_acc": ro / N,
                         "brute_sims": R * nL, "resonator_sims": ITER * (R + nL)})
    lines = ["| sources | lags | observed steps | brute force right | resonator right | brute similarities | resonator similarities |",
             "|---|---|---|---|---|---|---|"]
    lines += [f"| {r['sources']} | {r['lags']} | {r['observed_steps']} | {r['brute_acc']:.2f} | {r['resonator_acc']:.2f} | "
              f"{r['brute_sims']} | {r['resonator_sims']} |" for r in rows]
    text = "stage 7: resonator vs brute force, synthetic (source, lag) factorization, D=4096\n" + "\n".join(lines)
    print(text)
    (OUT / "stage7_resonator.json").write_text(json.dumps(rows, indent=1))
    (OUT / "stage7_resonator.md").write_text(text + "\n")


if __name__ == "__main__":
    main()

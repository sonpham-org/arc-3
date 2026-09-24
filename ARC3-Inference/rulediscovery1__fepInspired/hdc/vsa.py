# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Stage 1 of docs/plans/2026-09-24-hdc-ghost-roadmap.md: the smallest phasor vector-symbolic core
#   (Fourier holographic reduced representations; Plate) the time-model stages build on. Vectors are complex
#   unit phasors of dimension D.
#     - rand(n): n random phasor vectors;  bind(a, b) = a*b;  unbind(a, b) = a*conj(b) (exact inverse of bind)
#     - bundle(vs): superposition (plain sum, not normalised, so weights and counts are kept)
#     - shift(v, k): cyclic permutation by k (the time index of a sequence), exact inverse shift(v, -k)
#     - Space: fractional power encoding (Komer & Eliasmith's spatial semantic pointers): a base phasor B
#       raised to a real power x, B**x = exp(i*theta*x). power(B, x) * power(B, dx) == power(B, x + dx) holds
#       exactly (up to float rounding), so a displacement is a single binding.
#     - Displacement code: disp(dy, dx) = power(Y, dy) * power(X, dx); (0, 0) is the all-ones vector.
#       move(dy, dx) = MOVE * disp(dy, dx) is the item form used in sequences (all-ones is shift-invariant).
#     - sim(a, b): real part of the normalised inner product (1 = identical, ~0 = unrelated, noise ~ 1/sqrt(D)).
#     - cleanup(v, book): index of the codebook row most similar to v.
#   Pure numpy, seeded, no learning.
# SRP/DRY check: Pass -- no vector-symbolic code existed in the repo (searched ARC3-Inference and harnesses).
"""Minimal phasor VSA: bind, unbind, bundle, shift, fractional powers, cleanup."""
from __future__ import annotations

import numpy as np


class VSA:
    def __init__(self, dim: int = 1024, seed: int = 0):
        self.D = dim
        self.rng = np.random.default_rng(seed)
        self.X = self.rand()                 # base phasors for the two spatial axes
        self.Y = self.rand()
        self.MOVE = self.rand()              # role vector for "a move": keeps the no-move code random

    def rand(self, n: int | None = None) -> np.ndarray:
        shape = (self.D,) if n is None else (n, self.D)
        return np.exp(1j * self.rng.uniform(-np.pi, np.pi, size=shape))

    @staticmethod
    def bind(a, b):
        return a * b

    @staticmethod
    def unbind(a, b):
        return a * np.conj(b)

    @staticmethod
    def bundle(vs):
        return np.sum(np.asarray(vs), axis=0)

    @staticmethod
    def shift(v, k: int):
        return np.roll(v, k, axis=-1)

    @staticmethod
    def power(base, x: float):
        return np.exp(1j * np.angle(base) * x)

    def disp(self, dy: float, dx: float):
        return self.power(self.Y, dy) * self.power(self.X, dx)

    def move(self, dy: float, dx: float):
        """A displacement as an ITEM: MOVE bound with disp. disp(0, 0) alone is the all-ones vector, which a
        cyclic shift leaves unchanged, so inside a shifted sequence it would add the same constant at every
        position and swamp the read-out (found in stage 2)."""
        return self.MOVE * self.disp(dy, dx)

    def sim(self, a, b):
        return np.real(np.sum(a * np.conj(b), axis=-1)) / self.D

    def cleanup(self, v, book) -> int:
        return int(np.argmax(self.sim(book, v)))

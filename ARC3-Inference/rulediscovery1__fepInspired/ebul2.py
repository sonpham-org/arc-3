# Author: Claude Opus 5.5 (Bubba)
# Date: 26-September-2026
# PURPOSE: EBUL only, pulled out of the rule discovery agent into one self-contained file, asked by
#   OpenMind in #experimentalmessing (26-Sep-2026 10:25 ET): "copy only EBUL from my ARC agent into a
#   new file ebul2.py". Everything the agent uses of EBUL, with nothing else of the agent attached:
#     - the learner (distill/ebul.py): dense tanh layer, per-unit ternarisation to -1/0/+1 against the
#       batch mean and std, gzip bits of the ternary code as the entropy, Shannon bits for reference,
#       and the genetic algorithm (elitism, tournament, uniform crossover, Gaussian mutation, optional
#       worker processes) that pushes each layer's gzip bits per sample toward a target;
#     - the encoder the agent perceives with (distill/ebul_perception.py): two hidden layers (12 then 8
#       units) trained greedily by EBUL, input z-scored, last-layer code thresholded with frozen
#       training stats; plus its 9x9 patch features and the object-centre finder that picks patches;
#     - the curiosity drive (curiosity.py): EBULMeter (entropy a new board adds to the play's code
#       history, gzip bits of the stacked last-layer codes) and CuriosityDrive (expected entropy gain
#       per percept and action, optimistic for untried pairs, per-action moving-average backoff, and
#       re-weighting of a policy decision).
#   Logic is copied unchanged. The only edits are the ones needed to stand alone: object_centres
#   carries its own component flood fill (was efe_trace_analysis.component_cells, same 512-cell
#   background cut from novelty_vs_solves), the meter calls the local gzip_bits, and the drive keys an
#   action by action.key() when it has one, else by the action itself (was perception.Action only).
#   Trace loading and encoder training on trace boards stay in the agent (curiosity.train_encoder),
#   since they read the harness's files. The cached encoder pickle in results/ references
#   ebul_perception.Encoder, so it loads through curiosity.load_encoder, not through this file.
#   Pure numpy plus stdlib. The demo at the bottom trains on random boards only to show it runs.
# SRP/DRY check: Pass -- a deliberate standalone copy on request; the originals are untouched and the
#   agent still imports them, so this file changes no behaviour.
"""EBUL (Entropy Based Unsupervised Learning) as used by the rule discovery agent, standalone."""
from __future__ import annotations

import gzip
import multiprocessing as mp
from collections import Counter
from dataclasses import dataclass
from typing import Optional

import numpy as np

# ---------------------------------------------------------------- settings (ebul_perception.py)
HIDDEN = (12, 8)             # two hidden layers
TARGETS = (8.0, 5.0)         # EBUL target gzip bits per sample for layer 1 and layer 2
TRIT_K = 0.5                 # ternarisation threshold in units of the unit's std
PATCH = 9
N_COLOURS = 16
WORKERS = 1                  # processes for EBUL fitness
GENS = 60                    # GA generations per layer
GA_VERBOSE = False           # print the GA's progress every 10 generations
BACKGROUND_AREA = 512        # a component bigger than 1/8 of a 64x64 board is background


# ================================================================ learner (ebul.py)
_W = {}   # per-worker data for parallel fitness (set by _init_worker)


def _init_worker(X, n_in, n_out, k, target):
    _W.update(X=X, n_in=n_in, n_out=n_out, k=k, target=target)


def _fitness_worker(p):
    T = ternarize(layer_forward(_W["X"], p, _W["n_in"], _W["n_out"]), _W["k"])
    bps = gzip_bits(T) / len(_W["X"])
    return -abs(bps - _W["target"]), bps


def layer_forward(X, params, n_in, n_out):
    """Dense layer + tanh. params is a flat vector [W (n_in*n_out), b (n_out)]."""
    W = params[: n_in * n_out].reshape(n_in, n_out)
    b = params[n_in * n_out:]
    # numpy 2.0 + macOS Accelerate emits bogus matmul FP warnings; results are finite.
    with np.errstate(all="ignore"):
        return np.tanh(X @ W + b)


def ternarize(H, k=0.5):
    """Map each latent component to -1/0/+1 using its own batch mean and std."""
    mu = H.mean(axis=0, keepdims=True)
    sd = H.std(axis=0, keepdims=True) + 1e-12
    T = np.zeros(H.shape, dtype=np.int8)
    T[H > mu + k * sd] = 1
    T[H < mu - k * sd] = -1
    return T


def gzip_bits(T):
    """Compressed size in bits of the ternary code (one byte per trit, row-major).
    gzip's fixed header/trailer overhead is subtracted so an all-constant code
    lands near zero."""
    raw = (T + 1).astype(np.uint8).tobytes()          # {-1,0,1} -> {0,1,2}
    overhead = len(gzip.compress(b"", compresslevel=9, mtime=0))
    return 8 * max(len(gzip.compress(raw, compresslevel=9, mtime=0)) - overhead, 0)


def shannon_bits(T):
    """Sum over components of the empirical entropy of the {-1,0,+1} histogram."""
    total = 0.0
    for col in T.T:
        p = np.bincount(col + 1, minlength=3) / len(col)
        p = p[p > 0]
        total += -(p * np.log2(p)).sum()
    return total


def evolve_layer(X, n_out, target_bits_per_sample, k=0.5, pop=40, gens=60,
                 elite=4, tour=3, sigma=0.1, seed=0, verbose=True, workers=1):
    """Evolve one layer so gzip bits/sample of its ternary code approaches target."""
    rng = np.random.default_rng(seed)
    n_in = X.shape[1]
    dim = n_in * n_out + n_out
    P = rng.normal(0, 1 / np.sqrt(n_in), size=(pop, dim))

    def fitness(p):
        T = ternarize(layer_forward(X, p, n_in, n_out), k)
        bps = gzip_bits(T) / len(X)
        return -abs(bps - target_bits_per_sample), bps

    pool = None
    if workers > 1:
        pool = mp.get_context("spawn").Pool(workers, _init_worker,
                                            (X, n_in, n_out, k, target_bits_per_sample))
    for g in range(gens):
        scored = pool.map(_fitness_worker, list(P)) if pool else [fitness(p) for p in P]
        fit = np.array([s[0] for s in scored])
        bps = np.array([s[1] for s in scored])
        order = np.argsort(-fit)
        P, fit, bps = P[order], fit[order], bps[order]
        if verbose and (g % 10 == 0 or g == gens - 1):
            print(f"  gen {g:3d}  best bits/sample {bps[0]:8.3f}  "
                  f"target {target_bits_per_sample:.3f}  |err| {-fit[0]:.3f}")

        children = [P[i].copy() for i in range(elite)]           # elitism
        while len(children) < pop:
            # tournament selection of two parents
            a = min(rng.integers(0, pop, tour))                  # lower index = fitter
            b = min(rng.integers(0, pop, tour))
            mask = rng.random(dim) < 0.5                         # uniform crossover
            child = np.where(mask, P[a], P[b])
            child = child + rng.normal(0, sigma, dim)            # Gaussian mutation
            children.append(child)
        P = np.array(children)

    if pool:
        pool.close()
        pool.join()
    return P[0], n_in, n_out


# ================================================================ features (ebul_perception.py)

def colour_hist(cells) -> np.ndarray:
    h = np.bincount(np.clip(np.asarray(cells, dtype=int).ravel(), 0, N_COLOURS - 1), minlength=N_COLOURS)
    return h / max(h.sum(), 1)


def patch_feat(board, r, c) -> np.ndarray:
    b = np.asarray(board, dtype=int)
    h = PATCH // 2
    pad = np.pad(b, h, constant_values=-1)
    win = pad[r:r + PATCH, c:c + PATCH]
    return np.concatenate([win.ravel() / (N_COLOURS - 1), colour_hist(win[win >= 0])])


def component_cells(board, r, c):
    """4-connected same-colour cells under (r, c); None if it is background (too big)."""
    h, w = len(board), len(board[0])
    colour, seen, stack = board[r][c], {(r, c)}, [(r, c)]
    while stack:
        y, x = stack.pop()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and board[ny][nx] == colour:
                seen.add((ny, nx))
                stack.append((ny, nx))
                if len(seen) > BACKGROUND_AREA:
                    return None
    return seen


def object_centres(board):
    """Centre cell of every non-background object."""
    h, w = len(board), len(board[0])
    seen, out = set(), []
    for y in range(h):
        for x in range(w):
            if (y, x) in seen:
                continue
            cells = component_cells(board, y, x)
            if cells is None:
                # flood the background once so we don't restart from each of its pixels
                colour, stack = board[y][x], [(y, x)]
                seen.add((y, x))
                while stack:
                    cy, cx = stack.pop()
                    for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                        if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and board[ny][nx] == colour:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                continue
            seen |= cells
            ys = sorted(y for y, _ in cells)
            xs = sorted(x for _, x in cells)
            out.append((ys[len(ys) // 2], xs[len(xs) // 2]))
    return out


# ================================================================ encoder (ebul_perception.py)

class Encoder:
    """Two hidden tanh layers; percept = ternary code of layer 2 with frozen training stats."""

    def __init__(self, X, trained: bool, seed: int):
        self.mu_x = X.mean(0)
        self.sd_x = X.std(0) + 1e-6
        Z = (X - self.mu_x) / self.sd_x
        self.layers = []
        rng = np.random.default_rng(seed)
        inp = Z
        for li, (n_out, tgt) in enumerate(zip(HIDDEN, TARGETS)):
            n_in = inp.shape[1]
            if trained:
                params, _, _ = evolve_layer(inp, n_out, tgt, k=TRIT_K, seed=seed + li, gens=GENS,
                                            verbose=GA_VERBOSE, workers=WORKERS)
            else:
                params = rng.normal(0, 1 / np.sqrt(n_in), n_in * n_out + n_out)
            self.layers.append((params, n_in, n_out))
            inp = layer_forward(inp, params, n_in, n_out)
        self.mu_h = inp.mean(0)
        self.sd_h = inp.std(0) + 1e-12
        T = self.code_matrix(X)
        self.train_bits = gzip_bits(T) / len(X)
        self.train_codes = len({tuple(t) for t in T})

    def forward(self, X):
        h = (np.atleast_2d(X) - self.mu_x) / self.sd_x
        for params, n_in, n_out in self.layers:
            h = layer_forward(h, params, n_in, n_out)
        return h

    def code_matrix(self, X):
        H = self.forward(X)
        T = np.zeros(H.shape, dtype=np.int8)
        T[H > self.mu_h + TRIT_K * self.sd_h] = 1
        T[H < self.mu_h - TRIT_K * self.sd_h] = -1
        return T

    def code(self, x) -> tuple:
        return tuple(int(v) for v in self.code_matrix(x)[0])


# ================================================================ curiosity (curiosity.py)

class EBULMeter:
    """Last-layer EBUL patch codes of a board, and the gzip entropy of the play's code history."""

    def __init__(self, encoder):
        self.enc = encoder
        self.rows: list[np.ndarray] = []          # history: one ternary row per (board, code)
        self.bits = 0.0

    def reset(self) -> None:
        self.rows, self.bits = [], 0.0

    def codes(self, grid, mask: Optional[np.ndarray] = None) -> np.ndarray:
        b = np.asarray(grid, dtype=int)
        if mask is not None and mask.any():
            b = b.copy()
            b[mask] = np.bincount(b[~mask].ravel()).argmax()
        board = b.tolist()
        centres = object_centres(board)
        if not centres:
            return np.zeros((0, self.enc.layers[-1][2]), dtype=np.int8)
        T = self.enc.code_matrix(np.stack([patch_feat(board, y, x) for y, x in centres]))
        return np.unique(T, axis=0)             # the set of codes, in a canonical order

    def gain(self, codes: np.ndarray) -> float:
        """Entropy (gzip bits of the last-layer code matrix) this board adds to the history; commits it."""
        if len(codes) == 0:
            return 0.0
        self.rows.append(codes)
        new = float(gzip_bits(np.concatenate(self.rows)))
        g, self.bits = new - self.bits, new
        return g


@dataclass
class CuriosityConfig:
    temperature: float = 4.0       # bits of expected gain worth one nat of policy log-probability
    optimism: float = 8.0          # bonus (bits) for an untried (percept, action) pair
    pure: bool = False             # ignore the policy, act on curiosity alone
    backoff: bool = True           # untried pair -> this action's recent gain (EMA) instead of a flat prior
    ema: float = 0.3               # weight of the newest gain in the per-action recent mean


class CuriosityDrive:
    def __init__(self, encoder, cfg: Optional[CuriosityConfig] = None, seed: int = 0):
        self.meter = EBULMeter(encoder)
        self.cfg = cfg or CuriosityConfig()
        self.rng = np.random.default_rng(seed)
        self.sum: Counter = Counter()
        self.n: Counter = Counter()
        self.best_mean = 0.0
        self.percept = None
        self.rewards: list[float] = []
        self.recent: dict = {}         # action key -> exponential moving average of its entropy gain

    def start(self, grid, mask=None) -> None:
        self.meter.reset()
        self.sum.clear()
        self.n.clear()
        self.best_mean, self.rewards = 0.0, []
        self.recent = {}
        codes = self.meter.codes(grid, mask)
        self.meter.gain(codes)
        self.percept = codes.tobytes()

    @staticmethod
    def _akey(a) -> tuple:
        return a.key() if hasattr(a, "key") else a

    def value(self, a) -> float:
        k = (self.percept, self._akey(a))
        if self.n[k] == 0:
            ak = self._akey(a)
            if self.cfg.backoff and ak in self.recent:
                return self.recent[ak] + self.cfg.optimism / 2
            return self.best_mean + self.cfg.optimism
        return self.sum[k] / self.n[k]

    def observe(self, action, grid, mask=None) -> float:
        codes = self.meter.codes(grid, mask)
        r = self.meter.gain(codes)
        k = (self.percept, self._akey(action))
        self.sum[k] += r
        self.n[k] += 1
        self.best_mean = max(self.best_mean, self.sum[k] / self.n[k])
        ak = self._akey(action)
        self.recent[ak] = r if ak not in self.recent else (1 - self.cfg.ema) * self.recent[ak] + self.cfg.ema * r
        self.percept = codes.tobytes()
        self.rewards.append(r)
        return r

    def rechoose(self, decision):
        """Re-weight the policy's scored actions by expected entropy gain; sample the result.
        decision needs .scores (items with .action and .log_p), .action and .mode."""
        scores = decision.scores
        if not scores:
            return decision
        logits = []
        for s in scores:
            base = 0.0 if self.cfg.pure else s.log_p
            logits.append(base + self.value(s.action) / self.cfg.temperature)
        m = max(logits)
        p = np.exp(np.array(logits) - m)
        p /= p.sum()
        i = int(self.rng.choice(len(scores), p=p))
        decision.action = scores[i].action
        decision.mode = "curious" if self.cfg.pure else decision.mode + "+curious"
        return decision


# ================================================================ demo
if __name__ == "__main__":
    # Runs end to end on random blocky boards, just to show the pieces fit. Train on real trace
    # patches (curiosity.train_encoder) for anything that matters.
    rng = np.random.default_rng(0)

    def random_board(n_objects=12):
        b = np.zeros((64, 64), dtype=int)
        for _ in range(n_objects):
            y, x = rng.integers(0, 60, 2)
            hh, ww = rng.integers(1, 5, 2)
            b[y:y + hh, x:x + ww] = rng.integers(1, N_COLOURS)
        return b

    boards = [random_board() for _ in range(40)]
    Xp = np.stack([patch_feat(b.tolist(), y, x) for b in boards for y, x in object_centres(b.tolist())])
    GENS = 20
    enc = Encoder(Xp, trained=True, seed=0)
    print(f"encoder: {len(Xp)} patches, gzip {enc.train_bits:.2f} bits/sample, {enc.train_codes} distinct codes")

    drive = CuriosityDrive(enc)
    drive.start(boards[0])
    for t, b in enumerate(boards[1:6], 1):
        print(f"step {t}: entropy gain {drive.observe(('ACTION1',), b):.0f} bits")

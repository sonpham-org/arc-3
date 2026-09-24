"""
Author: Claude Opus 5.5 (Bubba)
Date: 23-September-2026
PURPOSE: EBUL — Entropy Based Unsupervised Learning (idea by OpenMind).
  A single dense layer maps inputs to a latent vector. Each latent component is
  ternarized to {-1, 0, +1} by thresholding against that component's batch mean
  and standard deviation (value > mean + k*std -> +1, value < mean - k*std -> -1,
  else 0). The entropy of the ternary code is measured two ways:
    1) gzip: the ternary matrix is packed to bytes, gzip-compressed, and the
       compressed size in bits is the entropy estimate that drives fitness
       (divided by the number of samples -> bits per sample).
    2) Shannon: per-component empirical entropy of the {-1,0,+1} histogram,
       summed over components (printed for reference / sanity check).
  A simple genetic algorithm (elitism + tournament selection + uniform crossover
  + Gaussian mutation) optimises the layer's weights and biases so the gzip
  entropy moves toward a target entropy. Layers can be stacked greedily:
  train layer 1, freeze it, feed its output into layer 2, and so on.
  Pure numpy + stdlib gzip. No gradients anywhere.
  Copied into ARC3-Inference/distill on 23-Sep-2026 from bubba-workspace/scratch/ebul/ebul.py
  (unchanged logic) so ebul_perception.py can import it as the perception learner. Only addition:
  evolve_layer(workers=N) scores the population in N processes (same GA, same fitness), because
  gzip-9 of a wide layer's code dominates run time (~130 ms per candidate at 120 units).
SRP/DRY check: Pass — standalone script, no existing EBUL code in workspace.
"""
import gzip
import multiprocessing as mp
import numpy as np

_W = {}   # per-worker data for parallel fitness (set by _init_worker)


def _init_worker(X, n_in, n_out, k, target):
    _W.update(X=X, n_in=n_in, n_out=n_out, k=k, target=target)


def _fitness_worker(p):
    T = ternarize(layer_forward(_W["X"], p, _W["n_in"], _W["n_out"]), _W["k"])
    bps = gzip_bits(T) / len(_W["X"])
    return -abs(bps - _W["target"]), bps


# ---------------------------------------------------------------- layer ----
def layer_forward(X, params, n_in, n_out):
    """Dense layer + tanh. params is a flat vector [W (n_in*n_out), b (n_out)]."""
    W = params[: n_in * n_out].reshape(n_in, n_out)
    b = params[n_in * n_out:]
    # numpy 2.0 + macOS Accelerate emits bogus matmul FP warnings; results are finite.
    with np.errstate(all="ignore"):
        return np.tanh(X @ W + b)


# -------------------------------------------------------------- entropy ----
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


# ------------------------------------------------------------------- GA ----
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


# ----------------------------------------------------------------- demo ----
def make_data(n=400, d=16, clusters=5, seed=0):
    """Toy unlabeled data: Gaussian clusters in d dimensions. Swap in your own X."""
    rng = np.random.default_rng(seed)
    centers = rng.normal(0, 3, size=(clusters, d))
    idx = rng.integers(0, clusters, n)
    X = centers[idx] + rng.normal(0, 1, size=(n, d))
    return (X - X.mean(0)) / X.std(0)


if __name__ == "__main__":
    X = make_data()
    layer_sizes = [12, 8]          # stack of latent widths, trained greedily
    targets = [8.0, 4.0]           # target gzip bits per sample for each layer
    k = 0.5

    inp = X
    for li, (n_out, tgt) in enumerate(zip(layer_sizes, targets), 1):
        print(f"\n=== layer {li}: {inp.shape[1]} -> {n_out}, target {tgt} bits/sample ===")

        # baseline: random (untrained) layer, for comparison
        rng = np.random.default_rng(123 + li)
        p0 = rng.normal(0, 1 / np.sqrt(inp.shape[1]), inp.shape[1] * n_out + n_out)
        T0 = ternarize(layer_forward(inp, p0, inp.shape[1], n_out), k)
        print(f"  random layer : gzip {gzip_bits(T0)} bits "
              f"({gzip_bits(T0)/len(inp):.3f}/sample), "
              f"shannon {shannon_bits(T0):.3f} bits/sample")

        best, n_in, n_out = evolve_layer(inp, n_out, tgt, k=k, seed=li)
        H = layer_forward(inp, best, n_in, n_out)
        T = ternarize(H, k)
        print(f"  evolved layer: gzip {gzip_bits(T)} bits "
              f"({gzip_bits(T)/len(inp):.3f}/sample), "
              f"shannon {shannon_bits(T):.3f} bits/sample")
        inp = H                     # frozen layer output feeds the next layer

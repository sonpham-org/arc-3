# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: A minimal tensor-logic engine in numpy (Domingos 2025, "Tensor Logic: The Language of AI", arXiv
#   2510.12269; guide at ~/bubba-workspace/library/tensor-logic/GUIDE.md), for OpenMind's rule-discovery agent
#   (#arc-3, 24-Sep-2026: "overhaul toward tensor logic so it stops being limited to hand-written templates").
#   The one idea of the paper: a relation is a sparse Boolean tensor and a Datalog rule is a join (product on
#   shared indices) followed by a projection (sum over the indices missing from the head) and a step function.
#     - Rel: a sparse tensor with NAMED indices (coords + values). join() multiplies two relations on their
#       shared indices (a database natural join), project() sums (or maxes) out indices, apply() is the
#       elementwise nonlinearity. Datalog `Aunt(x,z) <- Sister(x,y), Parent(y,z)` is
#       equation(("x","z"), Sister, Parent) with T = 0.
#     - nonlin(x, T): the per-equation temperature of the paper's section 5: T = 0 is the step function
#       (purely deductive), T > 0 is sigmoid(x / T) (increasingly analogical as T grows).
#     - Program / forward_chain: equations with the same head are summed, then thresholded; run as linear code
#       until nothing new is derived (fixpoint). Recursive rules (transitive closure) work.
#     - SparseEq: a learnable multilinear tensor equation L[n,e] += sum_entries v * P1[i1] * P2[i2] ...
#       (one sparse DATA factor = the join of the relations, already materialised as entries, times dense
#       PARAMETER factors; optionally one parameter carries a dense head axis e). Its gradient with respect to
#       one parameter is the same equation with that factor left out (the paper: "the gradient of a tensor
#       logic program is itself a tensor logic program"), computed here with bincount / sparse products.
#     - softmax_xent (softmax over the head index with a temperature), Adam with an L1 proximal step (the
#       description-length / sparsity penalty: weights that do not pay for themselves become exactly zero).
#   Used by tl/learner.py (rule learning), tl/plan.py (reachability as forward chaining) and tests/test_tl.py.
#   No torch: the gradients are written out.
# SRP/DRY check: Pass -- nothing in the package did joins, projections or gradients of tensor equations; the
#   numerics are numpy / scipy.sparse only.
"""Minimal tensor logic: sparse relations, joins, projection, temperature, forward chaining, gradients."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional, Sequence

import numpy as np
import scipy.sparse as sp


# ---------------------------------------------------------------- nonlinearity with temperature

def nonlin(x, T: float = 0.0, kind: str = "step"):
    """kind "step": T = 0 -> Heaviside (x > 0), T > 0 -> sigmoid(x / T). kind "relu" / "none" ignore T."""
    x = np.asarray(x, dtype=float)
    if kind == "none":
        return x
    if kind == "relu":
        return np.maximum(x, 0.0)
    if T <= 0.0:
        return (x > 0).astype(float)
    return 1.0 / (1.0 + np.exp(-np.clip(x / T, -60, 60)))


# ---------------------------------------------------------------- sparse relations

class Rel:
    """Sparse tensor with named indices. coords: int array [m, k]; vals: float array [m]. Elements default to 0."""

    def __init__(self, idx: Sequence[str], coords=None, vals=None):
        self.idx = tuple(idx)
        k = len(self.idx)
        self.coords = np.zeros((0, k), dtype=np.int64) if coords is None else np.asarray(coords, dtype=np.int64).reshape(-1, k)
        self.vals = np.ones(len(self.coords)) if vals is None else np.asarray(vals, dtype=float).reshape(-1)
        if len(self.vals) != len(self.coords):
            raise ValueError("coords and vals differ in length")

    # -- construction
    @classmethod
    def of(cls, idx: Sequence[str], facts: Iterable, vals: Optional[Iterable[float]] = None) -> "Rel":
        """Rel.of(("x","y"), [(0,1), (1,2)]) -- Boolean facts (value 1) unless vals are given."""
        facts = [tuple(f) if isinstance(f, (tuple, list)) else (f,) for f in facts]
        return cls(idx, np.array(facts, dtype=np.int64).reshape(-1, len(idx)),
                   None if vals is None else np.array(list(vals), dtype=float))

    @classmethod
    def from_dense(cls, idx: Sequence[str], arr) -> "Rel":
        arr = np.asarray(arr, dtype=float)
        nz = np.argwhere(arr != 0)
        return cls(idx, nz, arr[tuple(nz.T)] if len(nz) else np.zeros(0))

    def to_dense(self, shape: Sequence[int]) -> np.ndarray:
        out = np.zeros(shape)
        if len(self.coords):
            np.add.at(out, tuple(self.coords.T), self.vals)
        return out

    def facts(self) -> set:
        """The set of index tuples with a non-zero value (the Boolean reading)."""
        return {tuple(int(v) for v in c) for c, x in zip(self.coords, self.vals) if x != 0}

    def __len__(self) -> int:
        return int((self.vals != 0).sum())

    # -- algebra
    def coalesce(self) -> "Rel":
        """Sum duplicate coordinates; drop zeros."""
        if not len(self.coords):
            return self
        u, inv = np.unique(self.coords, axis=0, return_inverse=True)
        v = np.bincount(inv.reshape(-1), weights=self.vals, minlength=len(u))
        keep = v != 0
        return Rel(self.idx, u[keep], v[keep])

    def join(self, other: "Rel") -> "Rel":
        """Natural join: product of values on equal shared indices; the result carries the union of indices
        (left order, then the right's new ones). No shared index = outer product."""
        shared = [i for i in self.idx if i in other.idx]
        rest = [i for i in other.idx if i not in self.idx]
        out_idx = self.idx + tuple(rest)
        if not len(self.coords) or not len(other.coords):
            return Rel(out_idx)
        ls = [self.idx.index(i) for i in shared]
        rs = [other.idx.index(i) for i in shared]
        rr = [other.idx.index(i) for i in rest]
        buckets: dict = {}
        for j, c in enumerate(other.coords):
            buckets.setdefault(tuple(c[rs]), []).append(j)
        lc, lv, rc_, rv = [], [], [], []
        for i, c in enumerate(self.coords):
            for j in buckets.get(tuple(c[ls]), ()):
                lc.append(i)
                rc_.append(j)
        if not lc:
            return Rel(out_idx)
        lc, rc_ = np.array(lc), np.array(rc_)
        coords = np.concatenate([self.coords[lc], other.coords[rc_][:, rr]], axis=1)
        return Rel(out_idx, coords, self.vals[lc] * other.vals[rc_])

    def project(self, keep: Sequence[str], how: str = "sum") -> "Rel":
        """Sum (or max) out every index not in keep; the result's indices are keep, in that order."""
        keep = tuple(keep)
        cols = [self.idx.index(i) for i in keep]
        if not len(self.coords):
            return Rel(keep)
        sub = self.coords[:, cols]
        u, inv = np.unique(sub, axis=0, return_inverse=True)
        inv = inv.reshape(-1)
        if how == "sum":
            v = np.bincount(inv, weights=self.vals, minlength=len(u))
        elif how == "max":
            v = np.full(len(u), -np.inf)
            np.maximum.at(v, inv, self.vals)
        else:
            raise ValueError(how)
        return Rel(keep, u, v)

    def apply(self, T: float = 0.0, kind: str = "step") -> "Rel":
        """Elementwise nonlinearity on the stored (non-zero) elements. Elements that are 0 stay 0, which is
        exact for the step function (H(0) = 0); for sigmoid the implicit zeros would be 0.5, so equations meant
        to be soft are evaluated densely by their callers."""
        return Rel(self.idx, self.coords, nonlin(self.vals, T, kind)).coalesce()

    def rename(self, *names: str) -> "Rel":
        return Rel(names, self.coords, self.vals)

    def __add__(self, other: "Rel") -> "Rel":
        """Same head: equations with the same left-hand side are summed (reorders other to self's indices)."""
        if set(other.idx) != set(self.idx):
            raise ValueError(f"cannot add {self.idx} and {other.idx}")
        perm = [other.idx.index(i) for i in self.idx]
        return Rel(self.idx, np.concatenate([self.coords, other.coords[:, perm]]),
                   np.concatenate([self.vals, other.vals])).coalesce()


def equation(head: Sequence[str], *rhs: Rel, T: float = 0.0, kind: str = "step") -> Rel:
    """One tensor equation: join the right-hand side, project onto the head indices, apply the nonlinearity."""
    acc = rhs[0]
    for r in rhs[1:]:
        acc = acc.join(r)
    return acc.project(head).apply(T, kind)


# ---------------------------------------------------------------- forward chaining

@dataclass
class Rule:
    """head(idx) <- body: [(relation name, idx), ...]. Equations with the same head are summed."""
    head: str
    head_idx: tuple
    body: list


@dataclass
class Program:
    rules: list = field(default_factory=list)

    def add(self, head: str, head_idx: Sequence[str], *body: tuple) -> "Program":
        self.rules.append(Rule(head, tuple(head_idx), [(n, tuple(i)) for n, i in body]))
        return self

    def step(self, db: dict, T: float = 0.0) -> dict:
        """One pass: every head recomputed from the current database (plus its old facts: monotone)."""
        new = dict(db)
        sums: dict = {}
        for r in self.rules:
            if not all(n in db for n, _ in r.body):
                continue
            rels = [db[n].rename(*i) for n, i in r.body]
            s = rels[0]
            for x in rels[1:]:
                s = s.join(x)
            s = s.project(r.head_idx).rename(*[f"_{i}" for i in range(len(r.head_idx))])   # positional head
            sums[r.head] = s if r.head not in sums else sums[r.head] + s
        for h, s in sums.items():
            old = db.get(h)
            if old is not None:
                s = s + old.rename(*s.idx)
            new[h] = s.apply(T, "step")
        return new

    def forward_chain(self, db: dict, max_iter: int = 100) -> tuple[dict, int]:
        """Run to fixpoint (nothing new derived). Returns (database, passes)."""
        for it in range(1, max_iter + 1):
            new = self.step(db)
            if all(h in db and new[h].facts() == db[h].facts() for h in new):
                return new, it
            db = new
        return db, max_iter


# ---------------------------------------------------------------- learnable multilinear equations

@dataclass
class Param:
    name: str
    value: np.ndarray
    l1: float = 0.0                     # description-length (sparsity) weight on |value|
    simplex: bool = False               # value = softmax(logits): a soft choice (e.g. a learned lag)
    m: Optional[np.ndarray] = None      # Adam moments
    v: Optional[np.ndarray] = None

    def __post_init__(self):
        self.value = np.asarray(self.value, dtype=float)
        self.m = np.zeros_like(self.value)
        self.v = np.zeros_like(self.value)

    def eff(self) -> np.ndarray:
        """The value used in equations (softmax of the logits for a simplex parameter)."""
        if not self.simplex:
            return self.value
        z = self.value - self.value.max()
        e = np.exp(z)
        return e / e.sum()


SMALL = 4096                              # entries below which a dense-head equation scatter-adds instead of a sparse product


class SparseEq:
    """L[n, e] += sum over entries k of vals[k] * prod_j P_j.flat[idx_j[k]] (scalar parameters), and when
    head_param is set, the entry's product multiplies the row head_param[idx_head[k], :] (a dense head axis e)
    instead of landing on one (n, e) cell. Every parameter is an einsum factor; the data factor (entries) is
    the materialised join of the relations. Gradients are the same equation with one factor left out."""

    def __init__(self, name: str, n: np.ndarray, vals: np.ndarray, scalar: dict, e: Optional[np.ndarray] = None,
                 head: Optional[tuple] = None):
        """scalar: {param name: flat index array}; e: head index per entry (None with a dense head);
        head: (param name, row index array) for the dense-head parameter."""
        self.name = name
        self.n = np.asarray(n, dtype=np.int64)
        self.vals = np.asarray(vals, dtype=float)
        self.scalar = {k: np.asarray(v, dtype=np.int64) for k, v in scalar.items()}
        self.e = None if e is None else np.asarray(e, dtype=np.int64)
        self.head = None if head is None else (head[0], np.asarray(head[1], dtype=np.int64))
        if (self.e is None) == (self.head is None):
            raise ValueError("exactly one of e (scalar head) or head (dense head parameter) must be given")

    def _prod(self, P: dict, skip: Optional[str] = None) -> np.ndarray:
        p = self.vals.copy()
        for k, ix in self.scalar.items():
            if k != skip:
                p *= P[k].eff().reshape(-1)[ix]
        return p

    def forward(self, P: dict, L: np.ndarray) -> None:
        N, E = L.shape
        p = self._prod(P)
        if self.head is None:
            L += np.bincount(self.n * E + self.e, weights=p, minlength=N * E).reshape(N, E)
        else:
            name, rows = self.head
            W = P[name].eff().reshape(-1, E)
            if len(p) <= SMALL:                   # small (prediction-time) equations: plain scatter-add
                np.add.at(L, self.n, p[:, None] * W[rows])
            else:
                S = sp.csr_matrix((p, (self.n, rows)), shape=(N, W.shape[0]))
                L += S @ W

    def backward(self, P: dict, dL: np.ndarray, G: dict) -> None:
        """Accumulate dLoss/d(effective value) of every parameter into G (same shapes as eff())."""
        N, E = dL.shape
        if self.head is None:
            up = dL.reshape(-1)[self.n * E + self.e]                      # upstream per entry
        else:
            name, rows = self.head
            W = P[name].eff().reshape(-1, E)
            up = np.einsum("ke,ke->k", dL[self.n], W[rows])                # dL[n,:] . W[row,:]
            p = self._prod(P)
            S = sp.csr_matrix((p, (rows, self.n)), shape=(W.shape[0], N))
            G[name] = G.get(name, 0) + (S @ dL).reshape(P[name].value.shape)
        for k, ix in self.scalar.items():
            g = np.bincount(ix, weights=up * self._prod(P, skip=k), minlength=P[k].value.size)
            G[k] = G.get(k, 0) + g.reshape(P[k].value.shape)


def softmax_xent(L: np.ndarray, y: np.ndarray, T: float = 1.0, w: Optional[np.ndarray] = None):
    """Mean (weighted) cross-entropy of softmax(L / T) against class indices y. Returns (loss, dL, probs)."""
    Z = L / T
    Z = Z - Z.max(axis=1, keepdims=True)
    P = np.exp(Z)
    P /= P.sum(axis=1, keepdims=True)
    N = len(y)
    w = np.ones(N) if w is None else np.asarray(w, dtype=float)
    ws = w.sum() or 1.0
    loss = float(-(w * np.log(np.maximum(P[np.arange(N), y], 1e-300))).sum() / ws)
    dZ = P.copy()
    dZ[np.arange(N), y] -= 1.0
    dL = dZ * (w / ws)[:, None] / T
    return loss, dL, P


def simplex_grad(p: Param, g_eff: np.ndarray) -> np.ndarray:
    """Chain rule through softmax for a simplex parameter: d/dlogits = p * (g - <p, g>)."""
    q = p.eff()
    return q * (g_eff - float((q * g_eff).sum()))


class Adam:
    """Adam on the parameters' raw values, then the L1 proximal step (soft threshold) for parameters with l1 > 0,
    so weights that do not pay for their description length are exactly zero."""

    def __init__(self, lr: float = 0.1, b1: float = 0.9, b2: float = 0.999, eps: float = 1e-8):
        self.lr, self.b1, self.b2, self.eps = lr, b1, b2, eps
        self.t = 0

    def step(self, params: dict, G: dict) -> None:
        self.t += 1
        for k, p in params.items():
            if k not in G:
                continue
            g = simplex_grad(p, G[k]) if p.simplex else G[k]
            p.m = self.b1 * p.m + (1 - self.b1) * g
            p.v = self.b2 * p.v + (1 - self.b2) * g * g
            mh = p.m / (1 - self.b1 ** self.t)
            vh = p.v / (1 - self.b2 ** self.t)
            step = self.lr * mh / (np.sqrt(vh) + self.eps)
            p.value = p.value - step
            if p.l1 > 0 and not p.simplex:
                # proximal L1 with Adam's per-coordinate step size
                lam = self.lr * p.l1 / (np.sqrt(vh) + self.eps)
                p.value = np.sign(p.value) * np.maximum(np.abs(p.value) - lam, 0.0)


def logits(eqs: Sequence[SparseEq], P: dict, N: int, E: int) -> np.ndarray:
    L = np.zeros((N, E))
    for q in eqs:
        q.forward(P, L)
    return L


def grads(eqs: Sequence[SparseEq], P: dict, dL: np.ndarray) -> dict:
    G: dict = {}
    for q in eqs:
        q.backward(P, dL, G)
    return G


def numeric_grad(f: Callable[[], float], p: Param, h: float = 1e-5) -> np.ndarray:
    """Central differences on p.eff() (tests)."""
    base = p.value.copy()
    out = np.zeros_like(base)
    if p.simplex:
        raise ValueError("numeric_grad works on plain parameters")
    for i in range(base.size):
        p.value = base.copy()
        p.value.flat[i] += h
        a = f()
        p.value = base.copy()
        p.value.flat[i] -= h
        b = f()
        out.flat[i] = (a - b) / (2 * h)
    p.value = base
    return out


def ln_code_real(w: float, quantum: float = 0.5) -> float:
    """Nats to send one non-zero weight rounded to `quantum` (sign + Elias-gamma on the magnitude in quanta)."""
    q = max(int(round(abs(w) / quantum)), 1)
    return math.log(2.0) + (2 * math.floor(math.log2(q)) + 1) * math.log(2.0)

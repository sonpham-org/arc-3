# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Rule LEARNING with tensor logic for OpenMind's rule-discovery agent (#arc-3, 24-Sep-2026, items 3, 5
#   and 6 of the approved proposal): instead of fitting a fixed list of hand-written rule templates, fix only a
#   small bank of JOIN SHAPES (tensor equations over the relations of tl/relations.py), learn their weights by
#   gradient, and threshold the weights at temperature 0 into explicit rules (tl/rule.TLRule) that the existing
#   MDL posterior (beliefs.py) scores and selects like any other rule.
#     Bank (all feed one softmax over each object's effect: none / move / vanish / recolour / resize; the world
#     row predicts appear):
#       A  own features x action          L[o,e] += Own(o,f) Act(a) WA[f,a,e]
#       B  neighbour in the move direction L[o,e] += Ahead(o,e,c) WB[ctl(o),c]   (the move index e is shared)
#       P  own relation x action          L[o,e] += Rel(o,r) Colour(o,c) Act(a) WP[r,c,a,e]   (pushed, clicked)
#       K  linked object                  L[o,e] += Rel(o',r) Colour(o',c') Colour(o,c) WK[r,c',c,e]  (switch->door)
#       H  own history, soft lag          L[o,e] += LagH[tau] Hist(o,tau,e') WH[e',e]   (persistence, counters)
#       G  previous run, soft lag         L[o,e] += LagG[l] Tape(l,e) Own(o,f) WG[f]    (the ghost copies a run)
#     Structure: the program starts with A and B; an equation joins when some of its weights would pay for its
#     description length (the L1 optimality test at zero: |dLoss/dW| > lambda) -- checked at every re-fit and in
#     particular on surprise spikes (the gradient of the surprising step's loss with respect to the inactive
#     equations = backward chaining to the relation facts that could explain it; explain() lists them).
#     Weights: full-batch Adam with an L1 proximal step (lambda = beta / rows: beta nats per unit weight over the
#     play), warm-started at every re-fit; negatives are free (every unchanged object is a "none" row).
#     Export at T = 0: weights rounded to half units, lags hardened to their argmax; per-rule temperature
#     T = T0 / (1 + support / n0) (few examples: analogical, an object type without evidence borrows the rules of
#     a type sharing its colour or shape; many examples: deductive). One rule over all actions (full program),
#     one lean rule (A + B only), one rule per action, and one modifier carrying only history / tape effects.
#     mover_model(): the controlled sprite's arrows and learned walls from the hardened program, for the
#     explorer's trips when the templates are off.
#   Called by hypotheses.HypothesisProposer (propose -> fit -> export) and explore.ObjectContactExplorer.
# SRP/DRY check: Pass -- relations and rows from tl/relations.py, the equation algebra and gradients from
#   tl/engine.py, the exported rule from tl/rule.py; nothing here duplicates the template fitter.
"""Tensor-logic rule learner: join-shape bank, sparse gradient fit, structure by gradient test, T=0 export."""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .engine import Adam, Param, SparseEq, grads, logits, softmax_xent
from .relations import (ACTIONS, LINK_RELS, SELF_RELS, E_MAX, F_BIAS, F_COL, F_CTL, F_TYPE, K_HIST, N_ACT, N_COL, N_F, NONE, OTHER,
                        TAPE_LAGS, Rows, mv_delta)

EQUATIONS = ("A", "B", "P", "K", "H", "G")
HEADS = ("WA", "WP", "WK", "WH")        # parameters with a dense effect axis: column 0 ("none") is the fixed reference
FAMILIES = {"move": lambda nm: nm.startswith("mv"),
            "change": lambda nm: nm in ("van", "grow", "shrink", "reshape") or nm.startswith("rc>"),
            "appear": lambda nm: nm == "app"}
SHAPES = {"W0": (1,), "WA": (N_F * N_ACT, E_MAX), "WB": (2 * N_COL,), "WP": (len(SELF_RELS) * N_COL * N_ACT, E_MAX),
          "WK": (len(LINK_RELS) * N_COL * N_COL, E_MAX), "LagH": (K_HIST,), "WH": (E_MAX, E_MAX),
          "LagG": (len(TAPE_LAGS),), "WG": (N_F,)}
EQ_PARAMS = {"Z": ("W0",), "A": ("WA",), "B": ("WB",), "P": ("WP",), "K": ("WK",), "H": ("LagH", "WH"), "G": ("LagG", "WG")}


@dataclass
class TLConfig:
    beta: float = 1.0            # nats per unit of |weight| (L1 = description length), over the whole play
    lr: float = 0.15
    iters_first: int = 80
    iters: int = 20
    max_steps: int = 400         # training window (steps)
    T0: float = 1.0              # export temperature for a rule with no support
    n0: float = 8.0              # support at which the temperature halves
    t_min: float = 0.1           # below this the rule is exact (T = 0)
    quantum: float = 0.5         # weight rounding at export
    start: tuple = ("A", "B")    # equations active from the start
    structure_check: bool = True
    prune: bool = True           # after thresholding, drop weights that fix fewer than min_gain training decisions
    min_gain: int = 2            # (the templates' min_support, as a reduction test on the hardened program)
    prune_window: int = 150      # steps the reduction test looks at


def _eqs_for(rows_list, active: frozenset, E_used: int):
    """Stack a list of (row offset, Rows) into SparseEq objects (the batch index n is the global row). Equation Z is
    the shared default "nothing changes": every event class of every row gets -W0 (one weight for the program)."""
    acc = {k: [] for k in ("A", "B", "P", "K", "H", "G")}
    n_rows = 0
    for off, rows in rows_list:
        n_rows = off + rows.n
        for k in acc:
            for t in getattr(rows, k):
                acc[k].append((t[0] + off,) + tuple(t[1:]))
    eqs = []
    if n_rows and E_used > 1:
        n = np.repeat(np.arange(n_rows), E_used - 1)
        e = np.tile(np.arange(1, E_used), n_rows)
        eqs.append(SparseEq("Z", n, -np.ones(len(n)), {"W0": np.zeros(len(n), dtype=np.int64)}, e=e))
    if "A" in active and acc["A"]:
        a = np.array(acc["A"], dtype=float)
        eqs.append(SparseEq("A", a[:, 0], a[:, 2], {}, head=("WA", a[:, 1])))
    if "B" in active and acc["B"]:
        a = np.array(acc["B"], dtype=float)
        eqs.append(SparseEq("B", a[:, 0], a[:, 3], {"WB": a[:, 2]}, e=a[:, 1]))
    if "P" in active and acc["P"]:
        a = np.array(acc["P"], dtype=float)
        eqs.append(SparseEq("P", a[:, 0], a[:, 2], {}, head=("WP", a[:, 1])))
    if "K" in active and acc["K"]:
        a = np.array(acc["K"], dtype=float)
        eqs.append(SparseEq("K", a[:, 0], a[:, 2], {}, head=("WK", a[:, 1])))
    if "H" in active and acc["H"]:
        a = np.array(acc["H"], dtype=float)
        eqs.append(SparseEq("H", a[:, 0], a[:, 3], {"LagH": a[:, 1]}, head=("WH", a[:, 2])))
    if "G" in active and acc["G"]:
        a = np.array(acc["G"], dtype=float)
        eqs.append(SparseEq("G", a[:, 0], a[:, 4], {"LagG": a[:, 2], "WG": a[:, 3]}, e=a[:, 1]))
    return eqs


def family_ok(family: str):
    """Membership test of an effect name in a family: move / change / appear / all, or one effect "e:<name>"."""
    if family.startswith("e:"):
        return lambda nm, x=family[2:]: nm == x
    return FAMILIES.get(family, lambda nm: True)


def class_mask(E_used: int) -> np.ndarray:
    m = np.zeros(E_MAX)
    m[E_used:] = -1e9
    return m


class TLLearner:
    def __init__(self, cfg: Optional[TLConfig] = None):
        self.cfg = cfg or TLConfig()
        self.params = {k: Param(k, np.zeros(s), simplex=k.startswith("Lag")) for k, s in SHAPES.items()}
        self.params["W0"].value[:] = 3.0             # start from "nothing changes"
        self.opt = Adam(self.cfg.lr)
        self.steps: deque = deque(maxlen=self.cfg.max_steps)     # (serial, Rows, y, action name)
        self.active = set(self.cfg.start)
        self.activated: list = []           # (step serial, equation, gradient, reason)
        self.explanations: list = []        # backward-chaining explanations of surprising steps
        self.support: dict = {}             # action -> non-none target rows seen
        self.seen_ahead: set = set()        # (ctl, colour) met in a move strip during training
        self.fits = 0
        self.seconds = 0.0
        self.n_classes = 3
        self.last_loss = None
        self.dirs: dict = {}
        self.vocab_size = 3
        self._prune_memo: dict = {}

    def E_used(self) -> int:
        return max(self.n_classes, self.vocab_size)

    # -- data
    def add_step(self, serial: int, rows: Rows, y: list, action, dirs: dict) -> None:
        self.steps.append((serial, rows, np.asarray(y, dtype=np.int64), action.name))
        nn = int(sum(1 for v in y if v != 0))
        self.support[action.name] = self.support.get(action.name, 0) + nn
        for t in rows.B:
            self.seen_ahead.add(int(t[2]))
        self.dirs = dict(dirs)
        self.n_classes = max(self.n_classes, int(max(y)) + 1)

    def batch(self, active: frozenset, last: Optional[int] = None):
        steps = list(self.steps)[-last:] if last else list(self.steps)
        off, rl, ys = 0, [], []
        for _, rows, y, _ in steps:
            rl.append((off, rows))
            ys.append(y)
            off += rows.n
        y = np.concatenate(ys) if ys else np.zeros(0, dtype=np.int64)
        return _eqs_for(rl, active, self.E_used()), y, off

    def lam(self, N: int) -> float:
        return self.cfg.beta / max(N, 1)

    # -- fitting
    def loss_and_grads(self, eqs, y, N, E_used: int):
        P = self.params
        L = logits(eqs, P, N, E_MAX) + class_mask(E_used)
        loss, dL, prob = softmax_xent(L, y)
        return loss, grads(eqs, P, dL), prob

    def fit(self, n_iter: Optional[int] = None, vocab_size: Optional[int] = None) -> Optional[float]:
        if not self.steps:
            return None
        t0 = time.time()
        self.vocab_size = max(self.vocab_size, vocab_size or 0)
        E_used = self.E_used()
        if self.cfg.structure_check:
            self.check_structure(E_used)
        eqs, y, N = self.batch(frozenset(self.active))
        lam = self.lam(N)
        for p in self.params.values():
            p.l1 = 0.0 if (p.simplex or p.name == "W0") else lam
        n = n_iter if n_iter is not None else (self.cfg.iters_first if self.fits == 0 else self.cfg.iters)
        loss = None
        for _ in range(n):
            loss, G, _ = self.loss_and_grads(eqs, y, N, E_used)
            for k in HEADS:
                if k in G:
                    G[k].reshape(-1, E_MAX)[:, 0] = 0.0       # "none" is the reference class: its column stays 0
            self.opt.step(self.params, G)
        self.fits += 1
        self.last_loss = loss
        self.seconds += time.time() - t0
        return loss

    def check_structure(self, E_used: int, reason: str = "refit", last: Optional[int] = None) -> list:
        """Activate each inactive equation whose zero-weight gradient beats the L1 price (KKT at zero)."""
        inactive = [q for q in EQUATIONS if q not in self.active]
        if not inactive:
            return []
        eqs_all, y, N = self.batch(frozenset(self.active) | frozenset(inactive), last)
        if N == 0:
            return []
        act = [q for q in eqs_all if q.name in self.active or q.name == "Z"]
        L = logits(act, self.params, N, E_MAX) + class_mask(E_used)
        _, dL, _ = softmax_xent(L, y)
        n_all = self.n_rows()
        lam = self.lam(n_all)
        on = []
        for q in eqs_all:
            if q.name not in inactive:
                continue
            G: dict = {}
            q.backward(self.params, dL, G)
            main = EQ_PARAMS[q.name][-1]
            g = float(np.abs(G.get(main, np.zeros(1))).max()) * (N / max(n_all, 1))
            if g > lam:
                self.active.add(q.name)
                on.append((q.name, g))
                self.activated.append((self.steps[-1][0], q.name, round(g / lam, 2), reason))
        return on

    def n_rows(self) -> int:
        return sum(r.n for _, r, _, _ in self.steps)

    def on_surprise(self, serial: int, E_used: int) -> None:
        """A surprising step: structure check on the recent steps (gradient pointed at the surprise), and a
        backward-chaining explanation of the step (which inactive / active relation facts carry gradient)."""
        if not self.steps:
            return
        self.check_structure(E_used, reason="surprise", last=3)
        exp = self.explain(E_used)
        if exp:
            self.explanations.append((serial, exp))
            self.explanations = self.explanations[-50:]

    def explain(self, E_used: int, top: int = 4) -> list:
        """The relation facts of the last step with the largest |gradient| on the weights they touch."""
        eqs, y, N = self.batch(frozenset(EQUATIONS), last=1)
        if N == 0:
            return []
        act = [q for q in eqs if q.name in self.active or q.name == "Z"]
        L = logits(act, self.params, N, E_MAX) + class_mask(E_used)
        _, dL, _ = softmax_xent(L, y)
        out = []
        for q in eqs:
            G: dict = {}
            q.backward(self.params, dL, G)
            for k, g in G.items():
                if self.params[k].simplex or k == "W0":
                    continue
                if k in HEADS:
                    g = g.copy()
                    g.reshape(-1, E_MAX)[:, 0] = 0.0     # the "none" column is the fixed reference
                i = int(np.abs(g).argmax())
                out.append((float(np.abs(g).flat[i]), q.name, k, np.unravel_index(i, g.shape)))
        out.sort(key=lambda t: -t[0])
        return [(round(a, 4), b, c, tuple(int(v) for v in d)) for a, b, c, d in out[:top]]

    # -- reading the hardened program
    def hardened(self) -> dict:
        """Rounded weights (T = 0): {param: array}; lags as one-hot argmax."""
        q = self.cfg.quantum
        out = {}
        for k, p in self.params.items():
            if p.simplex:
                v = np.zeros_like(p.value)
                v[int(np.argmax(p.eff()))] = 1.0
            else:
                v = np.round(p.value / q) * q
            out[k] = v
        return out

    def prune(self, H: dict, family: str, effects: tuple) -> dict:
        """Model reduction on the hardened program for one effect family: try removing each weight (smallest
        first); keep the removal unless it costs min_gain or more correct T=0 decisions on the recent training rows
        (a decision is correct when it names the row's effect, or "none" when the effect is outside the family)."""
        fam_ok = family_ok(family)
        fam_cols = np.array([e > 0 and fam_ok(nm) for e, nm in enumerate(effects)] + [False] * (E_MAX - len(effects)))
        key = (family, len(effects), tuple(sorted((k, v.tobytes()) for k, v in H.items())))
        if key in self._prune_memo:
            return self._prune_memo[key]
        eqs, y, N = self.batch(frozenset(self.active), last=self.cfg.prune_window)
        P = {k: Param(k, v.copy()) for k, v in H.items()}
        mask = np.where(fam_cols, 0.0, -1e9)
        mask[0] = 0.0
        tgt = np.where(fam_cols[y], y, 0)
        L = logits(eqs, P, N, E_MAX) + mask
        ok = L.argmax(axis=1) == tgt
        base = floor = int(ok.sum())
        # where each prunable weight enters: (rows n, head column e, coefficient) -- removing weight w subtracts w * coef
        touch: dict = {}
        for q in eqs:
            if q.head is not None:
                k, hr = q.head
                coef = q._prod(P)
                if k not in HEADS:
                    continue
                cols_ = [int(c) for c in np.flatnonzero(fam_cols)]
                for r in np.unique(hr):
                    m = hr == r
                    for e in cols_:
                        i = int(r) * E_MAX + e
                        if P[k].value.flat[i] != 0:
                            touch.setdefault((k, i), []).append((q.n[m], np.full(int(m.sum()), e), coef[m]))
            else:
                for k, ix in q.scalar.items():
                    if k not in ("WB", "WG"):
                        continue
                    coef = q._prod(P, skip=k)
                    for i in np.unique(ix):
                        if P[k].value.flat[int(i)] != 0:
                            m = ix == i
                            touch.setdefault((k, int(i)), []).append((q.n[m], q.e[m], coef[m]))
        cands = []
        for k in ("WA", "WB", "WP", "WK", "WH", "WG"):
            for i in np.flatnonzero(P[k].value):
                i = int(i)
                if not (k in HEADS and not fam_cols[i % E_MAX]):
                    cands.append((abs(float(P[k].value.flat[i])), k, i))
        for _, k, i in sorted(cands):
            w = float(P[k].value.flat[i])
            parts = touch.get((k, i))
            if not parts:
                P[k].value.flat[i] = 0.0              # no support in the window: it fixes nothing
                continue
            n_all = np.concatenate([t[0] for t in parts])
            e_all = np.concatenate([t[1] for t in parts])
            c_all = np.concatenate([t[2] for t in parts])
            rows_ = np.unique(n_all)
            Lr = L[rows_].copy()
            pos = np.searchsorted(rows_, n_all)
            np.add.at(Lr, (pos, e_all), -w * c_all)
            ok_new = Lr.argmax(axis=1) == tgt[rows_]
            c = base - int(ok[rows_].sum()) + int(ok_new.sum())
            if c > base - self.cfg.min_gain and c >= floor - 2 * self.cfg.min_gain:
                P[k].value.flat[i] = 0.0              # accept the reduction
                L[rows_] = Lr
                ok[rows_] = ok_new
                base = c
        out = {k: p.value for k, p in P.items()}
        if len(self._prune_memo) > 32:
            self._prune_memo.clear()
        self._prune_memo[key] = out
        return out

    def temperature(self, support: int) -> float:
        T = self.cfg.T0 / (1.0 + support / self.cfg.n0)
        return 0.0 if T < self.cfg.t_min else round(T, 2)

    def export(self, types: tuple, effects: tuple, movable: frozenset) -> list:
        """TLRules from the hardened program, split by what they predict (so the posterior can adopt the cheap,
        useful part): the MOVE family as primary rules (whole program; lean A+B; one per action), the CHANGE
        (vanish / recolour / resize) and APPEAR families as modifiers, and a LAG modifier carrying only the effects
        that the history / tape equations are responsible for."""
        from .rule import TLRule
        H = self.hardened()
        E = len(effects)
        cols = {f: {e for e, nm in enumerate(effects) if ok(nm)} for f, ok in FAMILIES.items()}
        cols["all"] = set(range(1, E))
        for e, nm in enumerate(effects):
            if e > 0 and not nm.startswith("mv") and nm != "other":
                cols[f"e:{nm}"] = {e}
        acts = frozenset(a for _, _, _, a in self.steps)
        dirs = tuple(sorted((a, int(d[0]), int(d[1])) for a, d in self.dirs.items() if d is not None))
        common = dict(effects=effects, types=types, movable=movable, dirs=dirs, seen_ahead=frozenset(self.seen_ahead),
                      lags=(int(np.argmax(H["LagH"])), int(np.argmax(H["LagG"]))))

        pruned = {f: (self.prune(H, f, effects) if self.cfg.prune else H) for f in ("move", "change", "appear", "all")}
        for f in cols:
            if f.startswith("e:"):
                pruned[f] = pruned["change"] if f != "e:app" else pruned["appear"]

        def weights(active: frozenset, family: str, only_action: Optional[str] = None) -> tuple:
            out = []
            fam = cols[family]
            Hf = pruned[family]
            ai = ACTIONS.index(only_action) if only_action in ACTIONS else None
            for q in ("Z",) + tuple(sorted(active)):
                for k in EQ_PARAMS[q]:
                    if k.startswith("Lag"):
                        continue
                    if k in ("WB", "WG") and not (fam & cols["move"]):
                        continue                      # Ahead and the tape only speak about moves
                    v = Hf[k]
                    for i in np.flatnonzero(v):
                        i = int(i)
                        if k in HEADS and (i % E_MAX) not in fam:
                            continue                  # another family's clause
                        if ai is not None and k in ("WA", "WP") and (i // E_MAX) % N_ACT != ai:
                            continue                  # another action's clause
                        out.append((k, i, float(v.flat[i])))
            return tuple(sorted(out))

        full = frozenset(self.active)
        lean = frozenset(q for q in full if q in ("A", "B"))
        total = sum(self.support.values())
        T = self.temperature(total)
        rules = []

        def add(scope, structure, family, active, acts_, support, modifier=False, T_=None, only=None):
            w = weights(active, family, only)
            if any(k != "W0" for k, _, _ in w) or (family == "move" and not modifier):
                rules.append(TLRule(scope=scope, structure=structure, family=family, active=active, weights=w,
                                    T=T if T_ is None else T_, actions=acts_, support=support, modifier=modifier,
                                    **common))

        add("all", "full", "move", full, acts, total)
        if lean != full:
            add("all", "lean", "move", lean, acts, total)
        for a in sorted(acts):
            if a in ACTIONS:
                s_ = self.support.get(a, 0)
                add(a, "full", "move", full, frozenset([a]), s_, T_=self.temperature(s_), only=a)
        add("all", "full", "change", full, acts, total, modifier=True)
        add("all", "full", "appear", full, acts, total, modifier=True)
        for f in sorted(cols):                        # one small modifier per kind of change, so the posterior can
            if f.startswith("e:"):                    # adopt the cheap useful ones (a ticking bar) on their own
                add("all", "full", f, full, acts, total, modifier=True)
        if full & {"H", "G"} and any(k in ("WH", "WG") for k, _, _ in weights(full, "all")):
            add("lag", "full", "all", full, acts, total, modifier=True, T_=0.0)
        return rules

    def mover_model(self, ctl_type: tuple, colour: int, types: tuple, effects: tuple) -> Optional[tuple]:
        """({button: (dy, dx)}, blocker colours, passable colours) of the controlled sprite under the (pruned)
        hardened move program. Per button: the move class the own-feature clauses favour; a colour met in the
        sprite's move strips is passable when a strip of that colour alone lets the move win over "none", else it
        is a learned wall (the invented predicate "wall" = the thresholded Ahead weight)."""
        H = self.hardened()
        if self.cfg.prune:
            H = self.prune(H, "move", effects)
        WA = H["WA"].reshape(N_F, N_ACT, E_MAX)
        WB = H["WB"].reshape(2, N_COL)
        feats = [F_COL + colour, F_BIAS, F_CTL]
        if ctl_type in types:
            feats.append(F_TYPE + types.index(ctl_type))
        seen = [c for c in range(N_COL) if N_COL + c in self.seen_ahead]
        moves, blockers, passable = {}, set(), set()
        E = len(effects)
        for ai, a in enumerate(ACTIONS):
            if a == "ACTION6":
                continue
            L = WA[feats, ai, :E].sum(axis=0)
            L[1:] -= H["W0"][0]                       # the shared default: nothing changes
            own = WA[feats[:1] + feats[2:], ai, :E].sum(axis=0)   # evidence about THIS piece (colour, ctl, type)
            best, e_best = -np.inf, None
            for e, nm in enumerate(effects):
                d = mv_delta(nm)
                if d is None or abs(d[0]) + abs(d[1]) > 16 or own[e] <= 0:
                    continue                          # a jump (respawn / rewind) is not an arrow move
                if L[e] > best:
                    best, e_best = L[e], e
            if e_best is None or best + max(WB[1].max(), 0.0) <= 0:
                continue
            moves[a] = mv_delta(effects[e_best])
            for c in seen:
                (passable if best + WB[1, c] > 0 else blockers).add(c)
        if not moves:
            return None
        return moves, blockers - passable, passable

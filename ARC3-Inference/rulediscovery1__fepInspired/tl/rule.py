# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: TLRule -- a learned tensor-logic program thresholded at temperature 0 and frozen into a rules.Rule, so
#   the existing MDL posterior (beliefs.BeliefState) prices, scores (exact prequential replay) and selects it next
#   to (or, in the tl_only arm, instead of) the hand-written templates (OpenMind, #arc-3, 24-Sep-2026).
#     - Frozen: the rounded weights, the hardened lags, the registries it was learned with (effect classes, object
#       types, movable types, the controlled sprite's button displacements) and its temperature are all fields,
#       so key() changes whenever the program changes and beliefs.PredictionCache stays exact.
#     - predict(rc): builds the step's relation entries with tl/relations.build_rows (the same function the
#       learner trained on), evaluates the equations with tl/engine (join -> projection -> argmax over effects
#       = the T = 0 step), then FORWARD CHAINS once: if the controlled sprite is predicted to move, the
#       player-move-clock tape entries (the ghost) are added and the program re-evaluated. Output: one Effect per
#       object whose hardened effect is not "none" (moves, vanish, recolour, resize; appear from the world row).
#       Silent (None) for an action it never saw, and -- at T = 0 -- when a predicted move's strip holds a colour
#       it never met (as rules.MoveRule stays silent before an unmet obstacle). At T > 0 (few examples) it
#       predicts there anyway and an object type without evidence borrows the rules of a type sharing its colour
#       or shape with weight exp(-1/T): analogical, the paper's section 5.
#     - scope "all" (every action), one action, or "lag" (a modifier that adds only the effects the history /
#       tape equations are responsible for, so it can ride on template rules in the touch_tl arm).
#     - description_length: literal code lengths from the DLContext alphabets + a universal code per rounded
#       weight (engine.ln_code_real), the same currency as the templates' prices.
#     - clauses() / describe(): the weights in plain words ("ACTION1: the controlled piece -> moves (-5,+0)").
# SRP/DRY check: Pass -- relations from tl/relations.py, evaluation from tl/engine.py, Effect / Rule / DL helpers
#   from perception.py and rules.py. New: the frozen program and its readable form.
"""TLRule: a thresholded tensor-logic program as a rule the posterior can score."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar, Optional

import numpy as np

from ..perception import Effect
from ..rules import Rule, ln_int
from .engine import Param, ln_code_real, logits
from .learner import SHAPES, _eqs_for, family_ok
from .relations import (ACTIONS, E_MAX, EDGE, F_BIAS, F_COL, F_CTL, F_TYPE, F_WORLD, K_HIST, LINK_RELS, N_ACT,
                        N_COL, N_F, SELF_RELS, TAPE_LAGS, build_rows, mv_delta)


def effect_words(name: str) -> str:
    d = mv_delta(name)
    if d is not None:
        return f"moves ({d[0]:+d},{d[1]:+d})"
    if name == "van":
        return "vanishes"
    if name.startswith("rc>"):
        return f"turns colour {name[3:]}"
    if name == "app":
        return "something appears"
    return {"none": "stays as it is", "grow": "grows", "shrink": "shrinks", "reshape": "changes shape"}.get(name, name)


def to_effect(name: str, comp) -> Optional[Effect]:
    d = mv_delta(name)
    if comp is None:
        return Effect("appear", None, part="app") if name == "app" else None
    if d is not None:
        return Effect("move", comp.id, d[1], d[0])
    if name == "van":
        return Effect("vanish", comp.id)
    if name.startswith("rc>"):
        return Effect("recolour", comp.id, to_colour=int(name[3:]), from_colour=comp.colour)
    if name in ("grow", "shrink", "reshape"):
        return Effect(name, comp.id)
    return None


@dataclass(frozen=True)
class TLRule(Rule):
    template: ClassVar[str] = "tl"
    scope: str
    structure: str
    family: str                     # which effects it predicts: move | change | appear | all
    active: frozenset
    weights: tuple                  # ((param name, flat index, rounded value), ...)
    T: float
    actions: frozenset
    support: int
    effects: tuple
    types: tuple
    movable: frozenset
    dirs: tuple                     # ((button, dy, dx), ...)
    lags: tuple                     # (hardened own-history lag index, hardened tape lag index)
    seen_ahead: frozenset
    modifier: bool = False

    @property
    def kind(self) -> str:                      # type: ignore[override]
        return "modifier" if self.modifier else "primary"

    # -- the frozen program as engine parameters (built once per rule)
    def _params(self) -> dict:
        P = self.__dict__.get("_P")
        if P is None:
            vals = {k: np.zeros(s) for k, s in SHAPES.items()}
            for k, i, w in self.weights:
                vals[k].flat[i] = w
            vals["LagH"][self.lags[0]] = 1.0
            vals["LagG"][self.lags[1]] = 1.0
            P = {k: Param(k, v) for k, v in vals.items()}
            self.__dict__["_P"] = P
            wt = set()
            for k, i, _ in self.weights:
                if k == "WA":
                    f = (i // E_MAX) // N_ACT
                elif k == "WG":
                    f = i
                else:
                    continue
                if F_TYPE <= f < F_TYPE + len(self.types):
                    wt.add(self.types[f - F_TYPE])
            self.__dict__["_wtypes"] = tuple(sorted(wt))
            fam = np.full(E_MAX, -1e9)
            fam[0] = 0.0
            ok = family_ok(self.family)
            for e, nm in enumerate(self.effects):
                if ok(nm):
                    fam[e] = 0.0
            self.__dict__["_fam"] = fam
            self.__dict__["_reg"] = ({k: i for i, k in enumerate(self.types)},
                                     {k: i for i, k in enumerate(self.effects)}, dict((a, (dy, dx)) for a, dy, dx in self.dirs))
        return P

    def _rows(self, rc):
        P = self._params()
        types, effects, dirs = self.__dict__["_reg"]
        soft = (self.T, self.__dict__["_wtypes"]) if self.T > 0 else None
        cache = rc.scene.__dict__.setdefault("_tl_rows", {})
        view = getattr(rc, "tl", None)
        key = (rc.action.key(), rc.agent.id if rc.agent is not None else None, id(view), self.effects, self.types,
               self.movable, self.dirs, soft, self.active)
        rows = cache.get(key)
        if rows is None:
            rows = build_rows(rc.scene, rc.action, rc.agent, types=types, effects=effects, movable=self.movable,
                              dirs=dirs, view=view, soft=soft, active=self.active)
            if len(cache) > 64:
                cache.clear()
            cache[key] = rows
        return rows, P

    def _eval(self, rows, P, active) -> np.ndarray:
        cache = rows.__dict__.setdefault("_eqs", {})           # the step's equations, built once per (active, E)
        k = (frozenset(active), len(self.effects))
        eqs = cache.get(k)
        if eqs is None:
            eqs = cache[k] = _eqs_for([(0, rows)], k[0], k[1])
        return logits(eqs, P, rows.n, E_MAX) + self.__dict__["_fam"]

    def _decide(self, rc, active) -> tuple:
        rows, P = self._rows(rc)
        L = self._eval(rows, P, active)
        dec = L.argmax(axis=1)
        if rows.Gmv and "G" in active:
            # forward chaining: the player-move-clock tape fires only if the controlled sprite moves this step
            if any(rows.ctl[n] and self.effects[dec[n]].startswith("mv") for n in range(rows.n)):
                import dataclasses
                g_rows = dataclasses.replace(rows, A=[], B=[], P=[], K=[], H=[], G=list(rows.Gmv), Gmv=[])
                eqs = [q for q in _eqs_for([(0, g_rows)], frozenset("G"), len(self.effects)) if q.name == "G"]
                L = L + logits(eqs, P, rows.n, E_MAX)
                dec = L.argmax(axis=1)
        return rows, dec

    def predict(self, rc):
        if rc.action.name not in self.actions:
            return None
        if self.modifier and self.scope == "lag":
            # only the effects the history / tape equations are responsible for (never the controlled sprite's)
            rows, dec = self._decide(rc, self.active)
            _, base = self._decide(rc, frozenset(q for q in self.active if q not in ("H", "G")))
            out = []
            for n, c in enumerate(rows.comps):
                if rows.ctl[n] or dec[n] == base[n] or dec[n] == 0:
                    continue
                e = to_effect(self.effects[dec[n]], c)
                if e is not None:
                    out.append(e)
            return out or None
        rows, dec = self._decide(rc, self.active)
        out = []
        for n, c in enumerate(rows.comps):
            e = int(dec[n])
            if e == 0:
                continue
            name = self.effects[e]
            if self.T == 0 and name.startswith("mv"):
                cols = rows.ahead_cols.get((n, e))
                if cols and any(int(rows.ctl[n]) * N_COL + cc not in self.seen_ahead for cc in cols):
                    return None                     # an obstacle this program never met: stay silent
            eff = to_effect(name, c)
            if eff is not None:
                out.append(eff)
        if self.modifier:
            return out or None
        return out

    # -- price and words
    def description_length(self, dl):
        nf = math.log(dl.n_colours + dl.n_types + 3)
        na = dl.ln(dl.n_actions)
        ne = math.log(max(len(self.effects), 2))
        lit = {"W0": 0.0, "WA": nf + na + ne, "WB": math.log(2 * N_COL), "WP": math.log(len(SELF_RELS) * N_COL) + na + ne,
               "WK": math.log(len(LINK_RELS) * N_COL * N_COL) + ne, "WH": 2 * ne, "WG": nf}
        cost = dl.ln(6) + ln_int(len(self.weights) + 1) + math.log(4)          # template, count, scope
        for k, _, w in self.weights:
            cost += lit[k] + ln_code_real(w, 1.0)
        if any(k == "WH" for k, _, _ in self.weights):
            cost += math.log(K_HIST)
        if any(k == "WG" for k, _, _ in self.weights):
            cost += math.log(len(TAPE_LAGS))
        if self.T > 0:
            cost += math.log(4)
        return cost

    def _feature(self, f: int) -> str:
        if F_COL <= f < F_COL + N_COL:
            return "an edge-coloured piece" if f - F_COL == EDGE else f"a colour-{f - F_COL} piece"
        if F_TYPE <= f < F_TYPE + len(self.types):
            k = self.types[f - F_TYPE]
            return f"piece type {k[0]}/{k[1] & 0xFFFF:04x}"
        return {F_CTL: "the controlled piece", F_WORLD: "the board", F_BIAS: "any piece"}.get(f, f"feature {f}")

    def clauses(self) -> list:
        """(|weight|, plain-words clause) per non-zero weight, largest first."""
        out = []
        for k, i, w in self.weights:
            if k in ("WA", "WP", "WK", "WH"):
                row, e = divmod(i, E_MAX)
                if e >= len(self.effects):
                    continue
                eff = effect_words(self.effects[e])
            if k == "WA":
                f, a = divmod(row, N_ACT)
                s = f"{ACTIONS[a] if a < len(ACTIONS) else 'other'}: {self._feature(f)} -> {eff}"
            elif k == "WB":
                ctl, c = divmod(i, N_COL)
                who = "the controlled piece" if ctl else "a piece"
                s = f"colour {'edge' if c == EDGE else c} ahead of {who} -> the move is {'blocked' if w < 0 else 'favoured'}"
            elif k == "WP":
                rc_, a = divmod(row, N_ACT)
                r, c = divmod(rc_, N_COL)
                what = {"contact": "is run into by the controlled piece", "on": "is stood on", "clicked": "is clicked",
                        "adjacent": "is next to the controlled piece",
                        "comoved": "moved along with the controlled piece last step"}[SELF_RELS[r]]
                s = f"{ACTIONS[a] if a < len(ACTIONS) else 'other'}: a colour-{c} piece that {what} -> {eff}"
            elif k == "WK":
                rc2, c = divmod(row, N_COL)
                r, c2 = divmod(rc2, N_COL)
                rel = {"contact": "is run into", "on": "is stood on", "clicked": "is clicked",
                       "changed": "changed on the last step", "adjacent": "is next to the controlled piece"}[LINK_RELS[r]]
                s = f"when a colour-{c2} piece {rel} -> colour-{c} pieces {eff}"
            elif k == "WH":
                e2 = row
                s = (f"a piece that {effect_words(self.effects[e2]) if e2 < len(self.effects) else '?'} "
                     f"{self.lags[0] + 1} step(s) ago -> {eff}")
            elif k == "WG":
                clock, sh = TAPE_LAGS[self.lags[1]]
                s = (f"{self._feature(i)} (not the controlled one) copies the controlled piece's previous run "
                     f"({'per player move' if clock == 'mv' else 'per action'}, shift {sh})")
            else:
                continue
            out.append((abs(w), f"{s} [{w:+.1f}]"))
        out.sort(key=lambda t: -t[0])
        return [s for _, s in out]

    def describe(self):
        cl = self.clauses()
        head = (f"tensor-logic {'modifier' if self.modifier else 'program'} ({self.family}, {self.scope}, {self.structure}, "
                f"equations {''.join(sorted(self.active))}, T={self.T}, {len(self.weights)} weights)")
        return head + (": " + "; ".join(cl[:4]) if cl else "")

# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026 (debate three and four 25-September-2026)
# PURPOSE: Debate pick 3 (docs 2026-09-24-warehouse-expert-debate.md, OpenMind #arc-3 22:49 ET): epistemic value that
#   depends on WHERE the agent is, fed into the expected-free-energy policy (policy.EFEPolicy).
#     - sample_hypotheses: Thompson-style draws of rule sets from the MDL posterior the agent already keeps
#       (beliefs.BeliefState), at a temperature: weights proportional to exp(log score / tau) (a fractional posterior, so
#       rule sets that are behind but not dead still get drawn).
#     - disagreement: for one candidate action in the current context, how much the sampled rule sets disagree about the
#       outcome = H[mean of their predictive distributions] - mean H[each] (the Jensen-Shannon information of an
#       ensemble; Plan2Explore's disagreement with the posterior as the ensemble). It is computed on the RuleContext of
#       the action on the current board, so a rule that is conditioned on what the agent faces (debate pick 2) makes the
#       disagreement local: it is high in front of a box and zero in an empty field.
#     - LocalNovelty: the count-based backstop, over (action, soft local context). The local context of a button is the
#       set of colours in the strip the controlled piece would newly cover by that button's learned move, or, for a
#       button with no learned move (an "interact"), by the facing move. Its code is a normalised bundle of fixed random
#       phasor colour vectors (hdc/vsa.VSA), so two contexts sharing colours overlap in proportion (the similarity of the
#       codes is |A n B| / sqrt(|A| |B|) up to noise); per action a memory vector sums the codes seen, the soft visit
#       count of a context is its similarity with that memory, and novelty = 1 / (1 + soft count).
#   Nothing here reads game internals; the colours come from the board, the moves from the agent's own learning.
#   25-Sep-2026 debate three, pick 2 (docs 2026-09-25-warehouse-expert-debate-3.md, OpenMind #arc-3 05:47 ET; Claude Opus
#   5.5 (Bubba)): ContactContext, the context of a button that does not move the self (an "interact"): the soft phasor code
#   of the colours in the self's CONTACT NEIGHBOURHOOD = the strips the self would newly cover by each of its learned
#   moves (all sides; unit steps before any move is learned), plus the strip ahead in the facing direction bound with a
#   FACE role vector (so "facing a box" and "a box behind" are different contacts); the floor (the board's mode colour)
#   is left out, and touching nothing is its own EMPTY code. Per button two soft memories: visits (novelty = 1 / (1 +
#   soft count), as LocalNovelty) and outcome (codes where the press changed something vs did nothing). The belief
#   "this button changes something in this contact" is Beta(1 + soft changed, 1 + soft nothing), soft counts = similarity
#   of the code with each memory, so a contact like one where the button worked inherits the evidence and a never-met
#   contact is uncertain; its epistemic value is the expected information gain of one press about that Beta
#   (H[mean] - E[H], digamma closed form). "Changed something" = the outcome label has a part that is not AMBIENT; a part
#   is ambient when it came up on at least ambient_share of this play's scored steps, whatever the action (a step bar or
#   timer ticking), counted from min_steps scored steps on (before that any part counts). The policy uses both for
#   non-moving buttons (policy.EFEPolicy.epistemic, PolicyConfig.w_ceig; AgentConfig.contact_context). Off = nothing here
#   is built.
#   25-Sep-2026 debate four, pick 3 (docs 2026-09-25-warehouse-expert-debate-4.md, OpenMind #arc-3 11:24 ET; Claude Opus 5.5
#   (Bubba)): ContactContext.open, a gate the agent sets before each decision (AgentConfig.contact_gated): the policy uses
#   the contact terms only while it is open (every button pressed at least gate_tries times this play), and still only
#   for a button with no learned move. The memories keep learning while it is closed. open_presses counts non-moving
#   button presses made while it was open; open_at is the step it first opened. Default open = debate three's behaviour.
# SRP/DRY check: Pass -- entropy / mixture are beliefs.py's, phasor vectors hdc/vsa.py's, the ahead strip
#   tl/relations.SceneRel's (the same strip the Ahead relation uses). New: posterior sampling at a temperature, the
#   ensemble disagreement and the phasor count memory; the contact code and the soft Beta outcome memory (debate three).
"""Sampled-posterior disagreement and soft local-context novelty for the EFE policy."""
from __future__ import annotations

import math
import random
from typing import Callable, Optional

import numpy as np

from .beliefs import entropy, mixture
from .hdc.vsa import VSA

N_CODES = 17                     # colours 0..15 and the edge / HUD sentinel (tl.relations.EDGE)


def sample_hypotheses(beliefs, rng: random.Random, k: int, tau: float) -> list:
    """k indices into beliefs.hyps drawn with replacement from the posterior tempered by tau."""
    s = [h.log_score / tau for h in beliefs.hyps]
    m = max(s)
    w = [math.exp(v - m) for v in s]
    return rng.choices(range(len(beliefs.hyps)), weights=w, k=k)


def disagreement(dists: list, sample: list) -> float:
    """Jensen-Shannon information of the sampled predictive distributions (0 when they all agree)."""
    if not sample:
        return 0.0
    ds = [dists[i] for i in sample]
    w = [1.0 / len(ds)] * len(ds)
    return max(entropy(mixture(ds, w)) - sum(entropy(d) for d in ds) / len(ds), 0.0)


def self_members(rc) -> tuple:
    """The controlled piece's parts on rc.scene: the contingency self when on, else the controlled instance plus its
    common-fate / relational group partners."""
    objs = {c.id: c for c in rc.scene.objects()}
    if rc.self_ids:
        return tuple(objs[i] for i in sorted(rc.self_ids) if i in objs)
    if rc.agent is None or rc.agent.id not in objs:
        return ()
    ids = {rc.agent.id}
    if rc.tl is not None:
        ids |= set(rc.tl.group.get(rc.agent.id, ()))
    if rc.fate:
        ids |= set(rc.fate.get(rc.agent.id, ()))
    return tuple(objs[i] for i in sorted(ids) if i in objs)


class LocalNovelty:
    def __init__(self, dim: int = 512, seed: int = 20260924):
        self.vsa = VSA(dim, seed)
        self.colours = self.vsa.rand(N_CODES)
        self.mem: dict = {}                    # action name -> summed context codes
        self.observed = 0

    def local_colours(self, rc, direction: Callable[[str], Optional[tuple]]) -> Optional[frozenset]:
        a = rc.action
        if not a.is_button:
            return None
        d = direction(a.name)
        if d is None and rc.facing is not None:
            d = rc.facing[:2]
        members = self_members(rc)
        if d is None or not members:
            return None
        from .tl.relations import SceneRel
        return SceneRel.of(rc.scene).ahead(members, int(d[0]), int(d[1]))

    def code(self, cols: Optional[frozenset]) -> Optional[np.ndarray]:
        if not cols:
            return None
        v = self.colours[sorted(min(int(c), N_CODES - 1) for c in cols)].sum(axis=0)
        return v / math.sqrt(len(cols))

    def novelty(self, rc, direction) -> float:
        x = self.code(self.local_colours(rc, direction))
        if x is None:
            return 0.0
        m = self.mem.get(rc.action.name)
        n = 0.0 if m is None else max(float(self.vsa.sim(m, x)), 0.0)
        return 1.0 / (1.0 + n)

    def observe(self, rc, direction) -> None:
        x = self.code(self.local_colours(rc, direction))
        if x is None:
            return
        k = rc.action.name
        self.mem[k] = x.copy() if k not in self.mem else self.mem[k] + x
        self.observed += 1


# ---------------------------------------------------------------- debate three, pick 2: contact neighbourhood

UNIT_SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))


def beta_eig(a: float, b: float) -> float:
    """Expected information gain (nats) about p ~ Beta(a, b) from one Bernoulli(p) observation:
    H[Bernoulli(E p)] - E[H[Bernoulli(p)]], with E[H] = psi(a+b+1) - m psi(a+1) - (1-m) psi(b+1), m = a / (a+b)."""
    from scipy.special import digamma
    m = a / (a + b)
    h = -(m * math.log(m) + (1 - m) * math.log(1 - m)) if 0 < m < 1 else 0.0
    eh = float(digamma(a + b + 1) - m * digamma(a + 1) - (1 - m) * digamma(b + 1))
    return max(h - eh, 0.0)


class ContactContext:
    def __init__(self, dim: int = 512, seed: int = 20260925, ambient_share: float = 0.3, min_steps: int = 10):
        self.vsa = VSA(dim, seed)
        self.colours = self.vsa.rand(N_CODES)
        self.ambient_share, self.min_steps = ambient_share, min_steps
        self.part_steps: dict = {}                   # label part -> scored steps it came up on (any action)
        self.steps = 0
        self.face = self.vsa.rand()                  # role: the colour is in the strip the self faces
        self.empty = self.vsa.rand()                 # the self touches nothing but floor
        self.visits: dict = {}                       # button -> summed codes of the contexts it was pressed in
        self.changed: dict = {}                      # button -> summed codes where the press changed something
        self.nothing: dict = {}                      # button -> summed codes where it did nothing
        self.observed = 0
        self.changes = 0
        self.open = True                             # debate four pick 3: the agent's gate (contact_gated); True = ungated
        self.open_presses = 0
        self.open_at = None

    @staticmethod
    def applies(rc, direction: Callable[[str], Optional[tuple]]) -> bool:
        """A button (not RESET, not a click) with no learned move of the self: an 'interact'."""
        a = rc.action
        return a.is_button and a.name != "RESET" and direction(a.name) is None

    @staticmethod
    def sides(direction) -> set:
        from .perception import BUTTONS
        ds = set()
        for b in BUTTONS:
            d = direction(b)
            if d is not None and tuple(d[:2]) != (0, 0):
                ds.add((int(d[0]), int(d[1])))
        return ds or set(UNIT_SIDES)

    def contact(self, rc, direction) -> Optional[tuple]:
        """(colours touched on all sides, colours in the facing strip), floor left out; None without a self."""
        members = self_members(rc)
        if not members:
            return None
        from .tl.relations import SceneRel
        rel = SceneRel.of(rc.scene)
        floor = int(rc.scene.comps.mode)
        touch: set = set()
        for dy, dx in self.sides(direction):
            touch |= rel.ahead(members, dy, dx)
        touch.discard(floor)
        face: set = set()
        if rc.facing is not None and (int(rc.facing[0]), int(rc.facing[1])) != (0, 0):
            face = set(rel.ahead(members, int(rc.facing[0]), int(rc.facing[1]))) - {floor}
        return frozenset(touch), frozenset(face)

    def code(self, rc, direction) -> Optional[np.ndarray]:
        c = self.contact(rc, direction)
        if c is None:
            return None
        touch, face = c
        idx = lambda s: sorted(min(int(x), N_CODES - 1) for x in s)  # noqa: E731
        n = len(touch) + len(face)
        if n == 0:
            return self.empty.copy()
        v = np.zeros(self.vsa.D, dtype=complex)
        if touch:
            v = v + self.colours[idx(touch)].sum(axis=0)
        if face:
            v = v + self.face * self.colours[idx(face)].sum(axis=0)
        return v / math.sqrt(n)

    def _soft(self, mem: dict, k: str, x) -> float:
        m = mem.get(k)
        return 0.0 if m is None else max(float(self.vsa.sim(m, x)), 0.0)

    def novelty(self, rc, direction) -> float:
        x = self.code(rc, direction)
        if x is None:
            return 0.0
        return 1.0 / (1.0 + self._soft(self.visits, rc.action.name, x))

    def p_change(self, rc, direction) -> Optional[tuple]:
        """(a, b) of the Beta belief that pressing here changes something, or None without a self."""
        x = self.code(rc, direction)
        if x is None:
            return None
        k = rc.action.name
        return 1.0 + self._soft(self.changed, k, x), 1.0 + self._soft(self.nothing, k, x)

    def eig(self, rc, direction) -> float:
        ab = self.p_change(rc, direction)
        return 0.0 if ab is None else beta_eig(*ab)

    def changed_something(self, parts) -> bool:
        """Any outcome part that is not ambient (see the header)."""
        if self.steps < self.min_steps:
            return bool(parts)
        return any(self.part_steps.get(p, 0) < self.ambient_share * self.steps for p in parts)

    def observe(self, rc, tr, direction) -> None:
        """rc: the context the action was chosen in (before the outcome); tr: its transition. Every scored step feeds the
        ambient-part counts; only non-moving button presses feed the memories."""
        if tr.reset or not tr.scored:
            return
        parts = set(tr.parts())
        changed = self.changed_something(parts)
        self.steps += 1
        for p in parts:
            self.part_steps[p] = self.part_steps.get(p, 0) + 1
        if not self.applies(rc, direction):
            return
        x = self.code(rc, direction)
        if x is None:
            return
        k = rc.action.name
        self.visits[k] = x.copy() if k not in self.visits else self.visits[k] + x
        mem = self.changed if changed else self.nothing
        mem[k] = x.copy() if k not in mem else mem[k] + x
        self.observed += 1
        self.changes += int(changed)
        self.open_presses += int(self.open)

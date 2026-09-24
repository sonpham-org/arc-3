# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026 (tensor-logic hooks 24-September-2026)
# PURPOSE: The small rule language of the rule discovery prototype (OpenMind, #arc-3, 23-Sep-2026
#   21:03 ET). A Rule looks at (board, action, what happened before) and either stays SILENT (None:
#   "I have nothing to say here", the back-off count model then predicts) or returns a list of
#   Effects (possibly empty = "nothing happens"). Rules are deterministic; the stochastic part of a
#   hypothesis is its learned miss rate and the back-off (beliefs.py).
#   Templates (all frozen dataclasses with a description length in nats for the MDL prior):
#     MoveRule        button B moves object type T by (dx, dy) unless the target holds a blocker colour
#                     or the board edge; unknown obstacle colour -> silent
#     ClickToggleRule click on shape S of colour a recolours it to b
#     ContactRule     button B drives mover T into colour Y -> push / collect / convert / stop (+ extra parts)
#     CounterRule     modifier: label part(s) P appear every Nth step in a scope (any / buttons / clicks)
#                     (Ghost Twin, Locksmith, Coded Notches: a bar that ticks on alternate presses)
#     NoOpRule        this action key does nothing
#     PersistRule     the previous outcome (of any action, or of this same context) repeats, or maps
#                     through a fitted table prev -> next (toggles that alternate, pushes that
#                     continue: round seven's biggest single gain was the previous outcome)
#     CodeRule        wrapper for model-written Python predictors: a fixed call signature
#                     fn(view: dict) -> list[label part] | None, run through a CodeSandbox. Only an
#                     in-process sandbox and a STUB provider exist here; no language model is called.
#   RuleSet: ordered decision list of primary rules (specific before general: code, contact, toggle,
#   move, noop, persist; the first primary that speaks decides) plus additive modifiers. It predicts
#   one outcome label in the object_events alphabet and the effects needed to imagine the next board.
#   RuleContext / ContextBuilder: everything a rule may read, built BEFORE the outcome (prequential)
#   from feature_detectors.PlayState (agency tracker, last label, last label per handcolour context,
#   level, level age) exactly as feature_detectors.run_trace orders it, plus per-scope "steps since
#   part P" counters for CounterRule.
#   Not run yet: only py_compile was used.
#   24-Sep-2026 HDC integration A/B (OpenMind 10:17 ET): RuleContext carries frozen hdc_bridge values (tape, walls,
#   fate) built by ContextBuilder when AgentConfig.use_hdc is on; TapeRule (modifier: an object repeats an earlier
#   run); MoveRule asks the soft wall map where its colour sets are silent, and group FATE takes the sprite's parts
#   from common fate. With use_hdc off every new field is None and every rule predicts exactly as before.
#   24-Sep-2026 tensor-logic overhaul (OpenMind 12:26 ET): RuleContext.tl carries the frozen relation view of
#   tl/relations.TLState (AgentConfig.use_tl; None otherwise or on imagined boards); ContextBuilder keeps the TLState and
#   hands it each finished step with the context it was predicted with; tl/rule.TLRule sits in the decision list
#   before the move templates (PRIMARY_ORDER "tl"). With use_tl off nothing changes.
# SRP/DRY check: Pass -- look-ahead and touching from agency_contexts; play history, handcolour context
#   and View from feature_detectors; labels from object_events via perception.py. The rule classes,
#   decision-list semantics and description lengths are new (nothing in distill/ has rules).
"""A small rule language: rules predict next-step events from (state, action, previous events)."""
from __future__ import annotations

import dataclasses
import math
import zlib

import numpy as np
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Iterable, Optional, Protocol

from ._distill import ag, fd, oe
from .perception import (TERMINAL_LABELS, Action, Effect, Scene, Transition, label_of, label_parts,
                         parts_to_effects)

SCOPES = ("any", "buttons", "clicks")
LN2 = math.log(2.0)


# ---------------------------------------------------------------- context a rule may read

@dataclass
class RuleContext:
    """Everything known before the outcome of `action` on `scene`."""
    scene: Scene
    action: Action
    hc_ctx: tuple                        # handcolour context (agency_contexts, click colour on)
    clicked: Optional[Any]               # oe.Comp under the click (non-background), else None
    agent: Optional[Any]                 # oe.Comp of the controlled object on this board, else None
    agent_type: Optional[tuple]          # its (colour, shape) type key
    last_label: Optional[str]            # previous step's outcome in this play
    last_same: Optional[str]             # outcome the last time this handcolour context was taken
    last_action: Optional[str]
    since: dict                          # (scope, part) -> steps since that part was last seen
    level: int
    level_age: int
    # HDC integration A/B (24-Sep-2026): frozen per-step values from hdc_bridge.HdcState; None when use_hdc is off
    # or the scene is imagined. tape = (ghost component id, dy, dx, clock); walls = hdc_bridge.WallView;
    # fate = {component id: partner component ids} (common-fate groups on this board).
    tape: Optional[tuple] = None
    walls: Optional[Any] = None
    fate: Optional[dict] = None
    tl: Optional[Any] = None             # tl/relations.TLView (tensor-logic overhaul, AgentConfig.use_tl)

    def replace(self, **kw) -> "RuleContext":
        return dataclasses.replace(self, **kw)


def scopes_of(action: Action) -> tuple[str, ...]:
    if action.is_click:
        return ("any", "clicks")
    if action.is_button:
        return ("any", "buttons")
    return ("any",)


class ContextBuilder:
    """Builds RuleContexts and advances the play history. Mirrors feature_detectors.run_trace: the
    context is computed first, then hc.observe, PlayState.observe, last_by_ctx."""

    def __init__(self, hdc: Optional[Any] = None, tl: Optional[Any] = None):
        self.hdc = hdc                   # hdc_bridge.HdcState or None (AgentConfig.use_hdc)
        self.tl = tl                     # tl/relations.TLState or None (AgentConfig.use_tl)
        self.reset_play()

    def begin(self, scene: Scene) -> None:
        """The play's first board (only the HDC / tensor-logic states need it)."""
        if self.hdc is not None:
            self.hdc.begin(scene)
        if self.tl is not None:
            self.tl.begin(scene)

    def reset_play(self) -> None:
        self.state = fd.PlayState()
        self.hc = ag.AgencyPerception("handcolour", buttons=False, clicks=False, click_colour=True)
        self.hc.reset()
        self.since: dict = {}
        self.last_action: Optional[str] = None

    def context(self, scene: Scene, action: Action, **override) -> RuleContext:
        step = scene.probe_step(action)
        view = fd.View(step, self.state)
        hc_ctx = self.hc.context(step)
        rc = RuleContext(
            scene=scene, action=action, hc_ctx=hc_ctx,
            clicked=view.comp if view.click_kind == "obj" else None,
            agent=view.agent, agent_type=self.state.agency.tracker.controlled(),
            last_label=self.state.last_label, last_same=self.state.last_by_ctx.get(hc_ctx),
            last_action=self.last_action, since=dict(self.since),
            level=self.state.level, level_age=self.state.age,
            **(self.hdc.annotate(scene) if self.hdc is not None else {}),
            **(self.tl.annotate(scene) if self.tl is not None else {}))
        return rc.replace(**override) if override else rc

    def observe(self, tr: Transition) -> None:
        if self.tl is not None:            # before the history advances: the context the step was predicted with
            dirs = {b: self.controlled_direction(b) for b in ag.BUTTONS}
            self.tl.observe(tr, self.context(tr.pre, tr.action) if tr.pre is not None else None, dirs)
        if self.hdc is not None:           # before the play history advances (the agency estimate as it was)
            tr_ = self.state.agency.tracker
            self.hdc.observe(tr, tr_.controlled(), tr_.direction)
        s = tr.step
        if s.reset:
            self.state.observe(s, None)
            self.since = {}
            self.last_action = None
            return
        view = fd.View(s, self.state)
        ctx = self.hc.context(s)
        self.hc.observe(s)
        self.state.observe(s, view)
        self.state.last_by_ctx[ctx] = s.label
        self.last_action = tr.action.name
        if tr.level_completed:
            self.since = {}
            return
        self.since = advance_since(self.since, tr.action, tr.parts())

    def controlled_direction(self, button: str) -> Optional[tuple]:
        return self.state.agency.tracker.direction(button)


def advance_since(since: dict, action: Action, parts: Iterable[str]) -> dict:
    """One step of the per-scope 'steps since part P' counters (pure: used by the planner too)."""
    out = dict(since)
    scopes = scopes_of(action)
    for k in list(out):
        if k[0] in scopes:
            out[k] += 1
    for p in set(parts):
        for sc in scopes:
            out[(sc, p)] = 0
    return out


# ---------------------------------------------------------------- description lengths

@dataclass
class DLContext:
    """Alphabet sizes used to price rule parameters (nats)."""
    n_actions: int = 7
    n_types: int = 8
    n_colours: int = 16
    n_labels: int = 16

    def ln(self, n: int) -> float:
        return math.log(max(n, 2))


def ln_int(n: int) -> float:
    """Elias-gamma-like universal code for a positive integer, in nats."""
    n = max(int(n), 1)
    return (2 * math.floor(math.log2(n)) + 1) * LN2


# ---------------------------------------------------------------- rules

class Rule:
    """Base: predict(rc) -> None (silent) or list[Effect] (empty = nothing happens)."""
    template: ClassVar[str] = "rule"
    kind: ClassVar[str] = "primary"           # primary rules decide; modifiers only add effects

    def predict(self, rc: RuleContext) -> Optional[list[Effect]]:
        raise NotImplementedError

    def key(self) -> tuple:
        """Identity of the rule's content (hashable). Memoised in the instance __dict__, which works
        for frozen dataclasses and leaves eq/hash untouched; the prediction cache calls this a lot."""
        k = self.__dict__.get("_key")
        if k is None:
            k = (self.template,) + tuple(getattr(self, f.name) for f in dataclasses.fields(self))
            self.__dict__["_key"] = k
        return k

    def description_length(self, dl: DLContext) -> float:
        raise NotImplementedError

    def describe(self) -> str:
        return repr(self)


def action_key(rc: RuleContext) -> tuple:
    """What a NoOpRule keys on: the button, or the clicked object's shape and colour."""
    if rc.action.is_click:
        if rc.clicked is None:
            return ("click", "bg")
        return ("click", rc.clicked.shape, rc.clicked.colour)
    return (rc.action.name,)


def _mover(rc: RuleContext, type_key: tuple):
    """The controlled instance if type_key is the controlled type, else the unique instance."""
    if rc.agent is not None and rc.agent_type == type_key:
        return rc.agent
    inst = rc.scene.by_type().get(type_key, [])
    return inst[0] if len(inst) == 1 else None


def contacted_comp(scene: Scene, comp, dy: int, dx: int, colour: int):
    """The first component of `colour` under comp's cells shifted by (dy, dx), or None."""
    ys, xs = scene.cells(comp)
    ys, xs = ys + dy, xs + dx
    h, w = scene.shape
    ok = (ys >= 0) & (ys < h) & (xs >= 0) & (xs < w)
    for y, x in zip(ys[ok], xs[ok]):
        cid = int(scene.comps.lab[y, x])
        if cid and cid != comp.id and scene.comps.comps[cid - 1].colour == colour:
            return scene.comps.comps[cid - 1]
    return None


def partner_comps(scene: Scene, comp, group: tuple) -> Optional[list]:
    """The instances of the partner types in `group` that touch `comp` (the parts of one multi-colour
    sprite that move together, e.g. Locksmith's two-colour block). None if a partner is missing."""
    out = []
    by = scene.by_type()
    for tk in group:
        near = [c for c in by.get(tk, []) if c.id != comp.id and c.y0 <= comp.y1 + 1 and c.y1 >= comp.y0 - 1
                and c.x0 <= comp.x1 + 1 and c.x1 >= comp.x0 - 1]
        if len(near) != 1:
            return None
        out.append(near[0])
    return out


FATE = (("fate",),)                   # MoveRule.group sentinel: partners = the common-fate group on this board


def fate_partners(rc: RuleContext, comp) -> list:
    """The components fused with comp by common fate on rc.scene (hdc_bridge; empty when none / HDC off). Unlike
    partner_comps, a missing partner is not a failure: the sprite may carry a box only some of the time."""
    ids = (rc.fate or {}).get(comp.id, ())
    return [c for c in rc.scene.objects() if c.id in ids]


def sprite_parts(rc: RuleContext, comp, group: tuple) -> Optional[list]:
    """comp plus its partners under a MoveRule group (type-level partners, or the common-fate group)."""
    if group == FATE:
        return [comp] + fate_partners(rc, comp)
    if group:
        partners = partner_comps(rc.scene, comp, group)
        return None if partners is None else [comp] + partners
    return [comp]


def soft_wall(rc: RuleContext, comp, parts: list, dy: int, dx: int) -> Optional[bool]:
    """The soft wall map's verdict for the controlled sprite's move (True blocked / False free / None abstain)."""
    if rc.walls is None or rc.agent is None or comp.id != rc.agent.id:
        return None
    from .hdc_bridge import ahead_cells
    key = (tuple(c.id for c in parts), dy, dx)
    return rc.walls.verdict_for(key, lambda: ahead_cells(rc.scene, parts, dy, dx))


def group_look_ahead(scene: Scene, comps: list, d) -> tuple:
    """agency_contexts.look_ahead for several components that move as one: the cells they would move
    into, minus their own cells (so one part never blocks its partner). Same return shape:
    ("edge",) / ("free",) / ("wall" | "obj", colour)."""
    dy, dx = d
    s = max(abs(dy), abs(dx))
    if s > ag.MAX_LOOK:
        dy, dx = round(dy * ag.MAX_LOOK / s), round(dx * ag.MAX_LOOK / s)
    pa = scene.comps
    h, w = pa.arr.shape
    own = {c.id for c in comps}
    ys_all, xs_all = [], []
    for c in comps:
        ys, xs = np.nonzero(pa.lab[c.y0:c.y1 + 1, c.x0:c.x1 + 1] == c.id)
        ys_all.append(ys + c.y0 + dy)
        xs_all.append(xs + c.x0 + dx)
    ys, xs = np.concatenate(ys_all), np.concatenate(xs_all)
    if (ys < 0).any() or (ys >= h).any() or (xs < 0).any() or (xs >= w).any():
        return ("edge",)
    keep = ~np.isin(pa.lab[ys, xs], list(own))
    ys, xs = ys[keep], xs[keep]
    if ys.size == 0:
        return ("free",)
    vals = pa.arr[ys, xs]
    if (vals == oe.MASKED).any():
        return ("edge",)
    other = vals != pa.mode
    if not other.any():
        # Only the modal colour ahead. agency_contexts.look_ahead calls this plain "free"; here the colour
        # is kept, because in Locksmith the modal colour is the WALL (the floor is a smaller region), so
        # the fitter must be able to learn it as a blocker. Predictions still treat it as open until then.
        return ("free", int(pa.mode))
    cols, cnt = np.unique(vals[other], return_counts=True)
    col = int(cols[cnt.argmax()])
    pick = np.nonzero(other & (vals == col))[0][0]
    cid = int(pa.lab[ys[pick], xs[pick]])
    return ("wall" if pa.comps[cid - 1].bg else "obj", col)


@dataclass(frozen=True)
class MoveRule(Rule):
    template: ClassVar[str] = "move"
    action: str
    type_key: tuple
    dx: int
    dy: int
    blockers: frozenset = frozenset()
    passable: frozenset = frozenset()
    edge_blocks: bool = True
    group: tuple = ()                 # partner types that move with it as one sprite (23-Sep-2026)

    def predict(self, rc):
        if rc.action.name != self.action:
            return None
        if rc.agent is not None and rc.agent_type == self.type_key:
            inst = [rc.agent]
        else:
            inst = rc.scene.by_type().get(self.type_key, [])
        if not inst:
            return None
        out = []
        for comp in inst:
            parts = sprite_parts(rc, comp, self.group)
            if parts is None:
                return None                   # the sprite is not intact here: stay silent
            la = group_look_ahead(rc.scene, parts, (self.dy, self.dx))
            if la[0] == "edge":
                if self.edge_blocks:
                    continue
                return None
            if la[0] == "free" and len(la) > 1 and la[1] in self.blockers:
                continue                      # the modal colour, learned to be a wall
            # HDC integration: where the colour sets have no clean evidence (an unmet colour, or the modal colour
            # not yet known passable) the soft wall map answers if it is decisive; the colour sets always win
            # where they know (the "colour first" guard, best of the a3 guards on all three games).
            unknown = len(la) > 1 and la[1] not in self.passable and la[1] not in self.blockers
            v = soft_wall(rc, comp, parts, self.dy, self.dx) if unknown else None
            if v is True:
                continue
            if la[0] == "free" or la[1] in self.passable or v is False:
                out += [Effect("move", c.id, self.dx, self.dy) for c in parts]
            elif la[1] in self.blockers:
                continue
            else:
                return None                  # an obstacle this rule has never met: stay silent
        return out

    def description_length(self, dl):
        return (dl.ln(6) + dl.ln(dl.n_actions) + dl.ln(dl.n_types) + 2 * math.log(7)
                + ln_int(len(self.blockers) + 1) + ln_int(len(self.passable) + 1)
                + (len(self.blockers) + len(self.passable)) * dl.ln(dl.n_colours) + LN2
                + ln_int(len(self.group) + 1) + len(self.group) * dl.ln(dl.n_types))

    def describe(self):
        blk = ",".join(map(str, sorted(self.blockers))) or "-"
        what = "+".join(f"colour-{k[0]}" for k in (self.type_key,) + tuple(self.group))
        return (f"{self.action} moves {what} piece by ({self.dx:+d},{self.dy:+d}); "
                f"blocked by colours {blk}{' and the edge' if self.edge_blocks else ''}")


@dataclass(frozen=True)
class PadMoveRule(Rule):
    """Several buttons move the same sprite, each by its own displacement, stopped by the same walls
    (a d-pad). One rule, priced once for the sprite and the wall colours plus a small cost per button,
    instead of one MoveRule per arrow (proposal step 2, 23-Sep-2026). Predicts exactly as MoveRule."""
    template: ClassVar[str] = "pad"
    type_key: tuple
    moves: tuple                      # ((action, dx, dy), ...) sorted by action
    blockers: frozenset = frozenset()
    passable: frozenset = frozenset()
    edge_blocks: bool = True
    group: tuple = ()

    def as_move(self, action: str) -> Optional[MoveRule]:
        for a, dx, dy in self.moves:
            if a == action:
                return MoveRule(a, self.type_key, dx, dy, self.blockers, self.passable, self.edge_blocks,
                                self.group)
        return None

    def predict(self, rc):
        mr = self.as_move(rc.action.name)
        return mr.predict(rc) if mr is not None else None

    def description_length(self, dl):
        return (dl.ln(6) + dl.ln(dl.n_types) + ln_int(len(self.moves))
                + len(self.moves) * (dl.ln(dl.n_actions) + 2 * math.log(7))
                + ln_int(len(self.blockers) + 1) + ln_int(len(self.passable) + 1)
                + (len(self.blockers) + len(self.passable)) * dl.ln(dl.n_colours) + LN2
                + ln_int(len(self.group) + 1) + len(self.group) * dl.ln(dl.n_types))

    def describe(self):
        what = "+".join(f"colour-{k[0]}" for k in (self.type_key,) + tuple(self.group))
        blk = ",".join(map(str, sorted(self.blockers))) or "-"
        arrows = ", ".join(f"{a} ({dx:+d},{dy:+d})" for a, dx, dy in self.moves)
        return f"d-pad moves {what} piece: {arrows}; blocked by colours {blk}"


@dataclass(frozen=True)
class ClickToggleRule(Rule):
    template: ClassVar[str] = "toggle"
    shape: int
    from_colour: int
    to_colour: int

    def predict(self, rc):
        c = rc.clicked
        if not rc.action.is_click or c is None or c.shape != self.shape or c.colour != self.from_colour:
            return None
        return [Effect("recolour", c.id, to_colour=self.to_colour, from_colour=self.from_colour)]

    def description_length(self, dl):
        return dl.ln(6) + dl.ln(dl.n_types) + 2 * dl.ln(dl.n_colours)

    def describe(self):
        return f"click on shape #{self.shape & 0xFFFF:04x} turns colour {self.from_colour} into {self.to_colour}"


CONTACT_OPS = ("push", "collect", "convert", "stop")


@dataclass(frozen=True)
class ContactRule(Rule):
    template: ClassVar[str] = "contact"
    action: str
    mover_type: tuple
    dx: int
    dy: int
    contact_colour: int
    op: str                                   # push | collect | convert | stop
    to_colour: Optional[int] = None           # convert only
    extra: tuple = ()                         # label parts that come with the contact (HUD aside)

    def predict(self, rc):
        if rc.action.name != self.action:
            return None
        mover = _mover(rc, self.mover_type)
        if mover is None:
            return None
        la = ag.look_ahead(rc.scene.comps, mover, (self.dy, self.dx))
        if la[0] not in ("obj", "wall") or la[1] != self.contact_colour:
            return None
        hit = contacted_comp(rc.scene, mover, self.dy, self.dx, self.contact_colour)
        if hit is None:
            return None
        out = []
        if self.op == "push":
            if hit.bg:
                return None
            out += [Effect("move", mover.id, self.dx, self.dy), Effect("move", hit.id, self.dx, self.dy)]
        elif self.op == "collect":
            out += [Effect("move", mover.id, self.dx, self.dy), Effect("vanish", hit.id)]
        elif self.op == "convert" and self.to_colour is not None:
            out.append(Effect("recolour", hit.id, to_colour=self.to_colour, from_colour=hit.colour))
        return out + parts_to_effects(self.extra)

    def description_length(self, dl):
        return (dl.ln(6) + dl.ln(dl.n_actions) + dl.ln(dl.n_types) + 2 * math.log(7) + dl.ln(dl.n_colours)
                + math.log(len(CONTACT_OPS)) + (dl.ln(dl.n_colours) if self.to_colour is not None else 0.0)
                + ln_int(len(self.extra) + 1) + len(self.extra) * dl.ln(dl.n_labels))

    def describe(self):
        tail = f" to colour {self.to_colour}" if self.op == "convert" else ""
        return (f"{self.action} drives colour-{self.mover_type[0]} piece into colour {self.contact_colour}: "
                f"{self.op}{tail}" + (f" (+{'|'.join(self.extra)})" if self.extra else ""))


@dataclass(frozen=True)
class CounterRule(Rule):
    template: ClassVar[str] = "counter"
    kind: ClassVar[str] = "modifier"
    parts: tuple                              # label part(s) that tick together, e.g. ("grow", "shrink")
    period: int
    scope: str = "any"                        # any | buttons | clicks

    def predict(self, rc):
        if self.scope not in scopes_of(rc.action):
            return None
        since = rc.since.get((self.scope, self.parts[0]))
        if since is None:
            return None                       # not seen yet in this level: no phase to count from
        return parts_to_effects(self.parts) if since == self.period - 1 else []

    def description_length(self, dl):
        return (dl.ln(6) + ln_int(len(self.parts)) + len(self.parts) * dl.ln(dl.n_labels)
                + ln_int(self.period) + math.log(len(SCOPES)))

    def describe(self):
        return f"'{'|'.join(self.parts)}' every {self.period} steps ({self.scope})"


@dataclass(frozen=True)
class NoOpRule(Rule):
    template: ClassVar[str] = "noop"
    action_key: tuple

    def predict(self, rc):
        return [] if action_key(rc) == self.action_key else None

    def description_length(self, dl):
        extra = (dl.ln(dl.n_types) + dl.ln(dl.n_colours)) if len(self.action_key) == 3 else 0.0
        return dl.ln(6) + dl.ln(dl.n_actions) + extra

    def describe(self):
        return f"{' '.join(map(str, self.action_key))} does nothing"


@dataclass(frozen=True)
class PersistRule(Rule):
    """scope 'last': previous step of the play; 'last_same': last time this same context was taken.
    mapping None = repeat; else a tuple of (prev label, next label) pairs."""
    template: ClassVar[str] = "persist"
    scope: str = "last"
    mapping: Optional[tuple] = None
    actions: Optional[frozenset] = None

    def predict(self, rc):
        if self.actions is not None and rc.action.name not in self.actions:
            return None
        prev = rc.last_label if self.scope == "last" else rc.last_same
        if prev is None or prev == "reset" or prev in TERMINAL_LABELS or prev == oe.NOVEL:
            return None
        if self.mapping is None:
            nxt = prev
        else:
            nxt = dict(self.mapping).get(prev)
            if nxt is None:
                return None
        return parts_to_effects(label_parts(nxt))

    def description_length(self, dl):
        n = len(self.mapping) if self.mapping else 0
        acts = len(self.actions) * dl.ln(dl.n_actions) if self.actions else 0.0
        return dl.ln(6) + LN2 + ln_int(n + 1) + 2 * n * dl.ln(dl.n_labels + 1) + LN2 + acts

    def describe(self):
        what = "repeats" if self.mapping is None else "follows " + ", ".join(f"{a}->{b}" for a, b in self.mapping)
        where = "the previous step" if self.scope == "last" else "the last outcome of the same action"
        return f"{where} {what}" + (f" (only {','.join(sorted(self.actions))})" if self.actions else "")


@dataclass(frozen=True)
class TapeRule(Rule):
    """HDC integration A/B (24-Sep-2026; hdc/stage5_posterior.py measured it in isolation): an object repeats an
    earlier run's moves. The run bookkeeping and the choice of object / run / lag / clock live in
    hdc_bridge.GhostTape (phasor tapes); the rule reads only the frozen rc.tape and predicts that object's move.
    Priced like stage 5: the template plus which object and which (run, clock, lag) of the searched grid.
    On the player-move clock the copy only moves when the player does: RuleSet.predict asks follows_base."""
    template: ClassVar[str] = "tape"
    kind: ClassVar[str] = "modifier"

    def predict(self, rc):
        if rc.tape is None:
            return None
        cid, dy, dx, _ = rc.tape
        return [] if (dy, dx) == (0, 0) else [Effect("move", cid, dx, dy)]

    @staticmethod
    def follows_base(rc: RuleContext, base_parts: list) -> bool:
        return rc.tape is None or rc.tape[3] == "actions" or any(p.startswith("mv") for p in base_parts)

    def description_length(self, dl):
        return dl.ln(6) + dl.ln(dl.n_types) + math.log(3 * 2 * 4)

    def describe(self):
        return "an object repeats an earlier run's moves (phasor tape)"


# ---------------------------------------------------------------- model-written rules (interface only)

class CodeSandbox(Protocol):
    def call(self, fn: Callable[[dict], Any], payload: dict, timeout_s: float) -> Any: ...


class InProcessSandbox:
    """Calls fn in this process; any exception = silence. NOT an isolation boundary.
    TODO(live use): run proposed code through the harness's python tool sandbox process
    (inference/agent/python_tool_sandbox.py) with a hard timeout before trusting model code."""

    def call(self, fn, payload, timeout_s):
        try:
            return fn(payload)
        except Exception:                     # a proposed rule must never kill the agent
            return None


def rule_view(rc: RuleContext) -> dict:
    """The plain-data view handed to CodeRule functions (the fixed call signature)."""
    return {
        "grid": rc.scene.raw,
        "action": rc.action.name, "row": rc.action.row, "col": rc.action.col,
        "objects": [{"id": c.id, "colour": c.colour, "shape": c.shape, "size": c.size,
                     "bbox": (c.y0, c.x0, c.y1, c.x1)} for c in rc.scene.objects()],
        "clicked": rc.clicked.id if rc.clicked is not None else None,
        "agent": rc.agent.id if rc.agent is not None else None,
        "last_label": rc.last_label, "last_same": rc.last_same,
        "level": rc.level, "level_age": rc.level_age,
    }


@dataclass(frozen=True, eq=False)
class CodeRule(Rule):
    """fn(view) -> list of label parts (e.g. ['mv+1+0']) or None. Price = compressed source length."""
    template: ClassVar[str] = "code"
    name: str
    source: str
    fn: Callable[[dict], Optional[list]] = field(repr=False)
    modifier: bool = False
    timeout_s: float = 0.05
    sandbox: Any = field(default_factory=InProcessSandbox, repr=False)

    @property
    def kind(self) -> str:                    # type: ignore[override]
        return "modifier" if self.modifier else "primary"

    def predict(self, rc):
        out = self.sandbox.call(self.fn, rule_view(rc), self.timeout_s)
        if out is None or not isinstance(out, (list, tuple)):
            return None
        return parts_to_effects(str(p) for p in out)

    def key(self):
        return ("code", self.name, zlib.crc32(self.source.encode()))

    def description_length(self, dl):
        return len(zlib.compress(self.source.encode(), 9)) * math.log(256)

    def describe(self):
        return f"code rule {self.name} ({len(self.source)} chars)"


class RuleProvider(Protocol):
    def propose(self, summary: str) -> list[CodeRule]: ...


class StubLLMRuleProvider:
    """Placeholder for the language-model rule proposer (WorldCoder-style). Returns no rules.
    TODO: send `summary` (agent.TextSummaryAdvisor.summarize) to the harness model, ask for small
    Python predictors with the rule_view signature, compile each one inside the sandbox and wrap it
    as CodeRule(name, source, fn). No model call is made in this prototype."""

    def propose(self, summary: str) -> list[CodeRule]:
        return []


# ---------------------------------------------------------------- rule sets

PRIMARY_ORDER = {"code": 0, "contact": 1, "toggle": 2, "tl": 2.5, "move": 3, "noop": 4, "persist": 5}


@dataclass(frozen=True)
class Prediction:
    label: str
    effects: tuple
    primary: Rule


@dataclass(frozen=True)
class RuleSet:
    """Decision list of primaries (specific first) plus additive modifiers."""
    primaries: tuple = ()
    modifiers: tuple = ()

    @staticmethod
    def empty() -> "RuleSet":
        return RuleSet()

    @staticmethod
    def of(rules: Iterable[Rule]) -> "RuleSet":
        rules = list(dict.fromkeys(rules))            # dedupe, keep order
        prim = [r for r in rules if r.kind == "primary"]
        prim.sort(key=lambda r: PRIMARY_ORDER.get(r.template, 9))   # stable: fitting order within a template
        return RuleSet(tuple(prim), tuple(r for r in rules if r.kind == "modifier"))

    def rules(self) -> list[Rule]:
        return list(self.primaries) + list(self.modifiers)

    def __len__(self) -> int:
        return len(self.primaries) + len(self.modifiers)

    def key(self) -> tuple:
        return tuple(r.key() for r in self.rules())

    def with_rule(self, rule: Rule) -> "RuleSet":
        return RuleSet.of(self.rules() + [rule])

    def without(self, rule: Rule) -> "RuleSet":
        return RuleSet.of([r for r in self.rules() if r.key() != rule.key()])

    def predict(self, rc: Optional[RuleContext],
                contrib: Optional[Callable[[Rule], Optional[list]]] = None) -> Optional[Prediction]:
        """None = silent (no primary rule spoke; modifiers alone never make a claim)."""
        contrib = contrib or (lambda r: r.predict(rc))
        base = None
        for r in self.primaries:
            e = contrib(r)
            if e is not None:
                base = (r, list(e))
                break
        if base is None:
            return None
        effects = base[1]
        base_parts = None
        for m in self.modifiers:
            e = contrib(m)
            if e:
                if hasattr(m, "follows_base"):
                    base_parts = base_parts if base_parts is not None else [x.label_part() for x in base[1]]
                    if not m.follows_base(rc, base_parts):
                        continue
                effects = effects + list(e)
        return Prediction(label_of(effects), tuple(effects), base[0])

    def description_length(self, dl: DLContext) -> float:
        return sum(r.description_length(dl) for r in self.rules()) + ln_int(len(self) + 1)

    def describe(self) -> list[str]:
        return [r.describe() for r in self.rules()] or ["(no rules: counts only)"]


def dl_context_for(scene: Optional[Scene], n_labels: int, n_actions: int = 7) -> DLContext:
    """Alphabet sizes from the current board (object types, colours) and the label vocabulary."""
    if scene is None:
        return DLContext(n_actions=n_actions, n_labels=n_labels)
    objs = scene.objects()
    return DLContext(n_actions=n_actions, n_types=max(len({c.type_key for c in objs}), 2),
                     n_colours=16, n_labels=max(n_labels, 2))

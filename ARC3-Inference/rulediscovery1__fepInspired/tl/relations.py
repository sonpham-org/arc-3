# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Perception as a relational database for the tensor-logic overhaul (OpenMind, #arc-3, 24-Sep-2026,
#   item 1 of the approved proposal). Per step, the perceived objects of the board before the action and a
#   handful of sparse Boolean relations over them, which the learner (tl/learner.py) joins in its tensor
#   equations and the exported rules (tl/rule.py) evaluate again at prediction time:
#     Obj(o)                non-background, non-floor components of the Scene (perception.Scene.objects)
#     Colour(o,c)           c in 0..15; Type(o,k) (colour + shape, a per-play registry); Ctl(o) the controlled
#                           instance (agency tracker, disambiguated by position) and its common-fate partners
#     Group(o,o')           common fate (soft/a1_common_fate.CommonFate, permanent fusion)
#     Ahead(o,e,c)          colour c (16 = edge / HUD) in the cells o's group would newly cover if it moved by
#                           the displacement of move effect e (the move index is shared with the head)
#     Contact(o) / On(o)    the controlled group would run into o under this action's learned displacement /
#                           stands on o now (box containment); Clicked(o) the click lands on o
#     Changed(o)            o changed (not a pure move) on the previous step: the co-change link (A2) as a relation
#     Adjacent(o)           o's box touches the controlled group's box (gap <= 1) without being part of it
#     CoMoved(o)            o moved by the same displacement as the controlled sprite on the previous step (carried)
#     Hist(o,tau,e')        o's own effect tau steps ago (tau = 1..K_HIST, this level)
#     Tape(l,e)             the controlled sprite's effect in the PREVIOUS run at clock position l: on the action
#                           clock or on the player-move clock, shifted by s (the lagged join; a run ends when the
#                           sprite jumps back to its level-start position)
#     Action(a)             the button / click
#   Effect targets per object (for learning and scoring only): the object's track in the next board
#   (perception.ObjectTracker ids): none / mv<dy>,<dx> / van / rc><c> / grow / shrink / reshape, and a "world"
#   row per step whose target is app when a new track appears. Nothing here reads the game engine.
#   build_rows() turns one step's relations into sparse equation entries (the materialised joins); it is the
#   single function used both for training rows (TLState.observe) and for prediction (tl/rule.TLRule.predict),
#   so the two can never disagree. TLState is kept by rules.ContextBuilder when AgentConfig.use_tl is on and
#   hands the rules a frozen TLView through RuleContext.tl (the hdc_bridge pattern: exact replay stays exact).
# SRP/DRY check: Pass -- components, look-ahead cap and tracking come from perception.py / _distill; common fate
#   from soft/a1_common_fate.py; the run-boundary jump from hdc/stage4_real.MAX_JUMP. New: the relation
#   vocabulary, per-object effect targets, the entry builder and the online history / tape bookkeeping.
"""Relational perception: per-step sparse relations over objects, and per-object effect targets."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .._distill import ag, oe
from ..hdc.stage4_real import MAX_JUMP
from ..soft.a1_common_fate import CommonFate

EDGE = 16
N_COL = 17
T_MAX = 64                      # types per play with their own feature
E_MAX = 48                      # effect classes per play
K_HIST = 6
ACTIONS = ("ACTION1", "ACTION2", "ACTION3", "ACTION4", "ACTION5", "ACTION6", "ACTION7")
N_ACT = len(ACTIONS) + 1        # + "other"
F_COL, F_TYPE, F_CTL, F_WORLD, F_BIAS = 0, N_COL, N_COL + T_MAX, N_COL + T_MAX + 1, N_COL + T_MAX + 2
N_F = N_COL + T_MAX + 3
SELF_RELS = ("contact", "on", "clicked", "adjacent", "comoved")
LINK_RELS = ("contact", "on", "clicked", "changed", "adjacent")
R_CONTACT, R_ON, R_CLICKED, R_CHANGED, R_ADJ, R_COMOVED = 0, 1, 2, 3, 4, 5   # relation ids in build_rows
TAPE_LAGS = (("act", -1), ("act", 0), ("act", 1), ("mv", -1), ("mv", 0), ("mv", 1), ("mv", 2))
OBJ_CAP = 120
NONE, APP, OTHER = "none", "app", "other"


def act_index(action) -> int:
    return ACTIONS.index(action.name) if action.name in ACTIONS else N_ACT - 1


def mv_name(dy: int, dx: int) -> str:
    return f"mv{int(dy)},{int(dx)}"


def mv_delta(name: str) -> Optional[tuple]:
    if not name.startswith("mv"):
        return None
    a, b = name[2:].split(",")
    return int(a), int(b)


# ---------------------------------------------------------------- per-play registries

@dataclass
class Vocab:
    """Effect classes and object types seen in this play (append-only, so indices are stable)."""
    effects: list = field(default_factory=lambda: [NONE, APP, OTHER])
    types: list = field(default_factory=list)

    def eff(self, name: str) -> int:
        if name in self.effects:
            return self.effects.index(name)
        if len(self.effects) >= E_MAX:
            return self.effects.index(OTHER)
        self.effects.append(name)
        return len(self.effects) - 1

    def typ(self, key: tuple) -> Optional[int]:
        if key in self.types:
            return self.types.index(key)
        if len(self.types) >= T_MAX:
            return None
        self.types.append(key)
        return len(self.types) - 1

    def frozen(self) -> tuple:
        return tuple(self.effects), tuple(self.types)


# ---------------------------------------------------------------- targets

def target_effects(pre, post) -> tuple[dict, int]:
    """{pre component id: effect name} from the tracker's ids (pre.track_ids / post.track_ids), and the number
    of new tracks on the post board (appearances)."""
    by_track = {post.track_ids.get(b.id): b for b in post.objects() if b.id in post.track_ids}
    out = {}
    for o in pre.objects():
        t = pre.track_ids.get(o.id)
        b = by_track.get(t) if t is not None else None
        if b is None:
            out[o.id] = "van"
        elif b.colour != o.colour:
            out[o.id] = f"rc>{b.colour}"
        elif b.shape != o.shape:
            out[o.id] = "grow" if b.size > o.size else "shrink" if b.size < o.size else "reshape"
        elif (b.y0, b.x0) != (o.y0, o.x0):
            out[o.id] = mv_name(b.y0 - o.y0, b.x0 - o.x0)
        else:
            out[o.id] = NONE
    pre_tracks = set(pre.track_ids.values())
    n_app = sum(1 for b in post.objects() if post.track_ids.get(b.id) not in pre_tracks)
    return out, n_app


# ---------------------------------------------------------------- static relations of one board

class SceneRel:
    """Cached per Scene (stored on the Scene instance): objects, their cells, and the Ahead strips."""

    def __init__(self, scene):
        self.scene = scene
        self.objs = scene.objects()[:OBJ_CAP]
        self.by_id = {c.id: c for c in self.objs}
        self._cells: dict = {}
        self._ahead: dict = {}

    @staticmethod
    def of(scene) -> "SceneRel":
        r = scene.__dict__.get("_tl_rel")
        if r is None:
            r = SceneRel(scene)
            scene.__dict__["_tl_rel"] = r
        return r

    def cells(self, c):
        v = self._cells.get(c.id)
        if v is None:
            v = self.scene.cells(c)
            self._cells[c.id] = v
        return v

    def strip(self, members: tuple, dy: int, dx: int):
        """(ys, xs, off-board flag) of the cells members would newly cover moving by (dy, dx) (look-ahead cap)."""
        s = max(abs(dy), abs(dx))
        if s > ag.MAX_LOOK:
            dy, dx = round(dy * ag.MAX_LOOK / s), round(dx * ag.MAX_LOOK / s)
        pa = self.scene.comps
        h, w = pa.arr.shape
        ys = np.concatenate([self.cells(c)[0] for c in members]) + dy
        xs = np.concatenate([self.cells(c)[1] for c in members]) + dx
        ok = (ys >= 0) & (ys < h) & (xs >= 0) & (xs < w)
        off = not bool(ok.all())
        ys, xs = ys[ok], xs[ok]
        own = [c.id for c in members]
        keep = ~np.isin(pa.lab[ys, xs], own)
        return ys[keep], xs[keep], off

    def ahead(self, members: tuple, dy: int, dx: int) -> frozenset:
        key = (tuple(c.id for c in members), dy, dx)
        v = self._ahead.get(key)
        if v is None:
            ys, xs, off = self.strip(members, dy, dx)
            vals = self.scene.comps.arr[ys, xs]
            cols = {int(c) for c in np.unique(vals) if c != oe.MASKED}
            if off or (vals == oe.MASKED).any():
                cols.add(EDGE)
            v = frozenset(cols)
            self._ahead[key] = v
        return v

    def box(self, members) -> tuple:
        return (min(c.y0 for c in members), min(c.x0 for c in members),
                max(c.y1 for c in members), max(c.x1 for c in members))


def _on(a: tuple, b: tuple) -> bool:
    inside = lambda p, q: p[0] >= q[0] and p[1] >= q[1] and p[2] <= q[2] and p[3] <= q[3]  # noqa: E731
    return inside(a, b) or inside(b, a)


# ---------------------------------------------------------------- the frozen per-step view

@dataclass
class TLView:
    """What the rules may read about history on the live board (frozen when built; an imagined board gets none).
    group: {component id: partner ids}; hist: {component id: effects 1..K steps ago}; world_hist: the world row's;
    tape: ((lag index, effect name), ...) for this step; ctl_moves: the actual 'controlled sprite moved' flag
    (only set on training rows, after the outcome)."""
    group: dict
    hist: dict
    world_hist: tuple
    tape: tuple
    changed: frozenset = frozenset()     # component ids that changed (not a pure move) on the previous step
    comoved: frozenset = frozenset()     # component ids that moved with the controlled sprite on the previous step


# ---------------------------------------------------------------- entries (the materialised joins)

@dataclass
class Rows:
    """One step's rows (objects + the world row) and the entries of every equation, with local row numbers.
    Equation layouts (index order = the parameter's flat order):
      A  own x action      head WA[(f, a), :]
      B  ahead             scalar WB[(ctl, c)] on head e = the move class
      P  self relation     head WP[((r, c), a), :]
      K  linked object     head WK[((r, c'), c), :]
      H  own history       scalar LagH[tau] x head WH[e', :]
      G  run tape          scalar LagG[l] x scalar WG[f] on head e = the tape's effect (mv-clock entries gated)"""
    comps: list
    ctl: list
    A: list = field(default_factory=list)      # (n, row)
    B: list = field(default_factory=list)      # (n, e, idx)
    P: list = field(default_factory=list)      # (n, row)
    K: list = field(default_factory=list)      # (n, row)
    H: list = field(default_factory=list)      # (n, tau, e')
    G: list = field(default_factory=list)      # (n, e, lag, f)
    Gmv: list = field(default_factory=list)    # player-move-clock tape entries, used only if the sprite moves
    ahead_cols: dict = field(default_factory=dict)   # (n, e) -> colour set (for the rules' abstention)

    @property
    def n(self) -> int:
        return len(self.comps)


def own_features(c, types: dict, is_ctl: bool, soft: Optional[tuple] = None) -> list:
    """[(feature index, value)]. soft = (T, type keys that carry weights in the rule): analogical Type literal at
    temperature T > 0 -- a type WITHOUT evidence of its own borrows the rules of the evidenced types sharing its
    colour or its shape, with weight exp(-1/T) (T = 0: exact types only)."""
    if c is None:
        return [(F_WORLD, 1.0), (F_BIAS, 1.0)]
    out = [(F_COL + int(c.colour) if 0 <= c.colour < 16 else F_COL + EDGE, 1.0), (F_BIAS, 1.0)]
    k = types.get(c.type_key)
    if k is not None:
        out.append((F_TYPE + k, 1.0))
    if soft is not None and soft[0] > 0 and c.type_key not in soft[1]:
        T = soft[0]
        for key in soft[1]:
            d = int(key[0] != c.colour) + int(key[1] != c.shape)
            if d == 1 and types.get(key) is not None:
                out.append((F_TYPE + types[key], float(np.exp(-1.0 / T))))
    if is_ctl:
        out.append((F_CTL, 1.0))
    return out


_SELF_IDX = {R_CONTACT: 0, R_ON: 1, R_CLICKED: 2, R_ADJ: 3, R_COMOVED: 4}
_LINK_IDX = {R_CONTACT: 0, R_ON: 1, R_CLICKED: 2, R_CHANGED: 3, R_ADJ: 4}


def build_rows(scene, action, agent, *, types: dict, effects: dict, movable: frozenset, dirs: dict,
               view: Optional[TLView], ctl_moves: Optional[bool] = None, soft: Optional[tuple] = None,
               active: frozenset = frozenset("ABPKHG")) -> Rows:
    """The step's relations as equation entries. types / effects: registries as {key: index}; movable: type keys
    that have moved in this play (Ahead is materialised only for them); dirs: {button: (dy, dx)} of the
    controlled sprite; view: TLView of the live board or None (imagined board: no history, no groups)."""
    sr = SceneRel.of(scene)
    group = view.group if view is not None else {}
    ctl_ids: set = set()
    if agent is not None and agent.id in sr.by_id:
        ctl_ids = {agent.id} | set(group.get(agent.id, ()))
    comps = list(sr.objs) + [None]
    rows = Rows(comps, [c is not None and c.id in ctl_ids for c in comps])
    a = act_index(action)
    moves = [(e, mv_delta(nm)) for nm, e in effects.items() if nm.startswith("mv")]

    # relations that link objects: Contact / On / Clicked / Changed
    rel: dict = {}
    if ctl_ids:
        members = tuple(sr.by_id[i] for i in sorted(ctl_ids) if i in sr.by_id)
        d = dirs.get(action.name) if action.is_button else None
        if d is not None:
            ys, xs, _ = sr.strip(members, d[0], d[1])
            hit = {int(v) for v in np.unique(scene.comps.lab[ys, xs]) if v}
            for cid in hit:
                if cid in sr.by_id and cid not in ctl_ids:
                    rel.setdefault(cid, set()).add(R_CONTACT)
        sb = sr.box(members)
        for c in sr.objs:
            if c.id in ctl_ids:
                continue
            cb = (c.y0, c.x0, c.y1, c.x1)
            if _on(sb, cb):
                rel.setdefault(c.id, set()).add(R_ON)
            elif cb[0] <= sb[2] + 1 and sb[0] <= cb[2] + 1 and cb[1] <= sb[3] + 1 and sb[1] <= cb[3] + 1:
                rel.setdefault(c.id, set()).add(R_ADJ)
    if action.is_click and action.row is not None:
        cc = scene.comp_at(action.row, action.col)
        if cc is not None and cc.id in sr.by_id:
            rel.setdefault(cc.id, set()).add(R_CLICKED)
    if view is not None:
        for cid in view.changed:
            if cid in sr.by_id:
                rel.setdefault(cid, set()).add(R_CHANGED)
        for cid in view.comoved:
            if cid in sr.by_id and cid not in ctl_ids:
                rel.setdefault(cid, set()).add(R_COMOVED)

    for n, c in enumerate(comps):
        is_ctl = rows.ctl[n]
        feats = own_features(c, types, is_ctl, soft)
        if "A" in active:
            for f, v in feats:
                rows.A.append((n, f * N_ACT + a, v))
        if c is None:
            if "H" in active and view is not None:
                for tau, e_name in enumerate(view.world_hist[:K_HIST]):
                    if e_name != NONE and e_name in effects:
                        rows.H.append((n, tau, effects[e_name], 1.0))
            continue
        col = int(c.colour) if 0 <= c.colour < 16 else EDGE
        # B: Ahead, only for types that have moved in this play (never-moved objects cannot have a move target)
        if "B" in active and moves and (c.type_key in movable or is_ctl):
            members = (c,) + tuple(sr.by_id[i] for i in group.get(c.id, ()) if i in sr.by_id)
            for e, (dy, dx) in moves:
                cols = sr.ahead(members, dy, dx)
                rows.ahead_cols[(n, e)] = cols
                for cc in cols:
                    rows.B.append((n, e, int(is_ctl) * N_COL + cc, 1.0))
        # P: this object's own relation x its colour x the action
        if "P" in active:
            for r in rel.get(c.id, ()):
                j = _SELF_IDX.get(r)
                if j is not None:
                    rows.P.append((n, (j * N_COL + col) * N_ACT + a, 1.0))
        # K: another object's relation x its colour x this object's colour (projection over o')
        if "K" in active:
            for oid, rs in rel.items():
                if oid == c.id or oid in ctl_ids and c.id in ctl_ids:
                    continue
                o2 = sr.by_id[oid]
                c2 = int(o2.colour) if 0 <= o2.colour < 16 else EDGE
                for r in rs:
                    j = _LINK_IDX.get(r)
                    if j is not None:
                        rows.K.append((n, (j * N_COL + c2) * N_COL + col, 1.0))
        # H: own history with a learned soft lag
        if "H" in active and view is not None:
            for tau, e_name in enumerate(view.hist.get(c.id, ())[:K_HIST]):
                if e_name != NONE and e_name in effects:
                    rows.H.append((n, tau, effects[e_name], 1.0))
        # G: the previous run's tape joined with the object's own features (never the controlled sprite itself)
        if "G" in active and view is not None and view.tape and not is_ctl:
            for li, e_name in view.tape:
                if e_name not in effects:
                    continue
                tgt = rows.Gmv if TAPE_LAGS[li][0] == "mv" else rows.G
                if TAPE_LAGS[li][0] == "mv" and ctl_moves is False:
                    continue
                for f, v in feats:
                    tgt.append((n, effects[e_name], li, f, v))
    if ctl_moves:                                     # training rows: the gate is known
        rows.G += rows.Gmv
        rows.Gmv = []
    return rows


# ---------------------------------------------------------------- online state (kept by ContextBuilder)

class TLState:
    """History, runs and groups over the live play; builds each step's TLView and the training rows."""

    def __init__(self, learner=None):
        self.learner = learner            # tl.learner.TLLearner (receives training rows)
        self.fate = CommonFate(None)
        self.vocab = Vocab()
        self.movable: set = set()
        self.scene = None
        self.view: Optional[TLView] = None
        self.new_level()

    def new_level(self) -> None:
        self.hist: dict = {}              # track id -> deque of effect names (newest first)
        self.world_hist: deque = deque(maxlen=K_HIST)
        self.changed_tracks: set = set()
        self.comoved_tracks: set = set()
        self.start = None                 # the controlled sprite's position at level start
        self.run_act: list = []
        self.run_mv: list = []
        self.prev_act: list = []
        self.prev_mv: list = []
        self.runs = 0

    # -- registries as dicts (what build_rows takes)
    def types(self) -> dict:
        return {k: i for i, k in enumerate(self.vocab.types)}

    def effects(self) -> dict:
        return {k: i for i, k in enumerate(self.vocab.effects)}

    def begin(self, scene) -> None:
        self.fate.update_objects(scene.objects(), None)
        for c in scene.objects():
            self.vocab.typ(c.type_key)
        self.scene = scene
        self.view = self._view(scene)

    def annotate(self, scene) -> dict:
        return {"tl": self.view} if scene is self.scene and self.view is not None else {}

    def partners(self) -> dict:
        find = self.fate.groups()
        by: dict = {}
        for t, c in self.fate.tr.comp_of.items():
            by.setdefault(find(t), []).append(c.id)
        out = {}
        for ids in by.values():
            if len(ids) > 1:
                for i in ids:
                    out[i] = tuple(j for j in ids if j != i)
        return out

    def _tape(self) -> tuple:
        out = []
        i, j = len(self.run_act), len(self.run_mv)
        for li, (clock, s) in enumerate(TAPE_LAGS):
            src, k = (self.prev_act, i - s) if clock == "act" else (self.prev_mv, j - s)
            if 0 <= k < len(src):
                out.append((li, src[k]))
        return tuple(out)

    def _view(self, scene) -> TLView:
        hist = {}
        changed, comoved = set(), set()
        for c in scene.objects():
            t = scene.track_ids.get(c.id)
            if t in self.hist:
                hist[c.id] = tuple(self.hist[t])
            if t in self.changed_tracks:
                changed.add(c.id)
            if t in self.comoved_tracks:
                comoved.add(c.id)
        return TLView(self.partners(), hist, tuple(self.world_hist), self._tape(), frozenset(changed), frozenset(comoved))

    def observe(self, tr, rc, dirs: dict) -> None:
        """One finished step. rc: the context the step was predicted with (its .tl is self.view)."""
        post = tr.post
        if tr.reset or tr.level_completed or post is None or not tr.scored:
            if post is not None:
                self.fate.update_objects(post.objects(), None)
            if tr.reset or tr.level_completed:
                self.new_level()
            self.scene = post
            if post is not None:
                self.view = self._view(post)
            return
        pre = tr.pre
        view = self.view if rc is not None and rc.tl is self.view else None
        targets, n_app = target_effects(pre, post)
        for c in post.objects():
            self.vocab.typ(c.type_key)
        agent = rc.agent if rc is not None else None
        ctl_eff = targets.get(agent.id) if agent is not None else None
        for cid, e in targets.items():
            self.vocab.eff(e)
            if e.startswith("mv"):
                comp = pre.comps.comps[cid - 1]
                self.movable.add(comp.type_key)
        if n_app:
            self.vocab.eff(APP)
        # training rows (only when the context really was built on this board with this view)
        if self.learner is not None and view is not None and pre is rc.scene:
            eff = self.effects()
            rows = build_rows(pre, tr.action, agent, types=self.types(), effects=eff, movable=frozenset(self.movable),
                              dirs=dirs, view=view, ctl_moves=bool(ctl_eff and ctl_eff.startswith("mv")))
            y = [eff.get(targets.get(c.id, NONE), eff[OTHER]) if c is not None else eff[APP if n_app else NONE]
                 for c in rows.comps]
            self.learner.add_step(tr.index, rows, y, tr.action, dirs)
        # history (per track), changed set, world row
        new_hist = {}
        changed = set()
        for o in pre.objects():
            t = pre.track_ids.get(o.id)
            if t is None:
                continue
            e = targets.get(o.id, NONE)
            d = deque(self.hist.get(t, ()), maxlen=K_HIST)
            d.appendleft(e)
            new_hist[t] = d
            if e != NONE and not e.startswith("mv"):
                changed.add(t)
        self.hist = new_hist
        self.changed_tracks = changed
        ctl_ids = {agent.id} | set(view.group.get(agent.id, ())) if (agent is not None and view is not None) else set()
        self.comoved_tracks = {pre.track_ids.get(o.id) for o in pre.objects()
                               if ctl_eff and ctl_eff.startswith("mv") and o.id not in ctl_ids
                               and targets.get(o.id) == ctl_eff} - {None}
        self.world_hist.appendleft(APP if n_app else NONE)
        # runs: the controlled sprite's effect per action, and its successful moves
        if agent is not None:
            pos_pre = (agent.y0, agent.x0)
            if self.start is None:
                self.start = pos_pre
            d = mv_delta(ctl_eff) if ctl_eff else None
            if d is not None and abs(d[0]) + abs(d[1]) > MAX_JUMP and (pos_pre[0] + d[0], pos_pre[1] + d[1]) == self.start:
                self.prev_act, self.prev_mv = self.run_act, self.run_mv       # the run ended: it becomes the tape
                self.run_act, self.run_mv = [], []
                self.runs += 1
            else:
                self.run_act.append(ctl_eff or NONE)
                if d is not None:
                    self.run_mv.append(ctl_eff)
        self.fate.update_objects(post.objects(), None)
        self.scene = post
        self.view = self._view(post)

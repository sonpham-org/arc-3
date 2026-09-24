#!/usr/bin/env python3
# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Round seven of the FEP-style offline trace analysis (OpenMind in #arc-3, 20:04 ET: "I don't
#   think there is just colour as a feature ... look for all kinds of features one can craft detectors
#   for by hand. For everything else we have EBUL."). A library of HAND-CRAFTED DETECTORS: each one is
#   a small function of (pre board as HUD-masked components, the action, the click point, the online
#   controlled-object tracker from agency_contexts.py, and the play's own history so far) that returns
#   a small discrete value. None means "does not apply to this action kind" (a button-only detector on
#   a click step, or the reverse), so adding it to a context key never splits the other kind.
#   Everything is computed PREQUENTIALLY: run_trace() walks one play, asks every detector for its value
#   BEFORE the step's outcome is seen, then updates the play state (agency tracker, last action, last
#   label, level index, per-object click memory, colours seen changing) from the finished step. No
#   state crosses plays (a scored run plays each game once).
#   Detectors (plain meaning in DETECTORS[name][2]):
#     click: colour, shape, size bucket, identical copies, same shape in other colours, objects of the
#       clicked colour, touching colours / count, enclosed by one object, on the border, nearest other
#       object's colour and distance from the click point, which side of the object was clicked, row /
#       column relation to the controlled object, mirror partner, what happened the last time this
#       object was clicked (flag and label), same object as the previous click, background / HUD click,
#       nearest "salient" (seen-changing) colour and distance
#     button: what the controlled object would move into one and two steps ahead, steps until blocked,
#       is the thing ahead something that has moved before (pushable), copies of the controlled type,
#       did it move on the last button press, nearest other object's colour / distance, controlled
#       object on the border, salient colour / distance
#     any: level index, steps since the level started (bucket), action repeated, last outcome label,
#       last outcome kind, number of objects on the board (bucket), per-salient-colour distance profile,
#       and (added after looking at the data: outcomes alternate or repeat per action) the outcome the
#       last time this same handcolour context was taken, full label and kind
#   hand_colour_ctx() is exactly round four's "handcolour" key (agency_contexts.AgencyPerception with
#   buttons=False, clicks=False, click_colour=True), so crafted keys extend the current best.
#   Reads trace objects only; launches nothing; no harness change.
# SRP/DRY check: Pass -- components, HUD masking and the event labels come from object_events.py; the
#   controlled-object tracker, look-ahead and touching test from agency_contexts.py; the click object
#   type from efe_trace_analysis.context_of. Nothing in distill/ had detectors beyond colour, shape,
#   touching and the one-step look-ahead; those are re-used, the rest is new.
"""Hand-crafted situation detectors for ARC-3 trace steps (round seven)."""
from __future__ import annotations

from collections import Counter

import numpy as np
from scipy import ndimage

import agency_contexts as ag
import efe_trace_analysis as efe
import object_events as oe

BUTTONS = ag.BUTTONS


# ---------------------------------------------------------------- small helpers

def bucket_log2(n: int) -> int:
    return int(np.log2(max(n, 1)))


def bucket_count(n: int) -> str:
    return "0" if n == 0 else "1" if n == 1 else "2" if n == 2 else "3-4" if n <= 4 else "5+"


def bucket_dist(g: int | None) -> str:
    if g is None:
        return "none"
    return "0" if g <= 0 else "1-2" if g <= 2 else "3-5" if g <= 5 else "6-11" if g <= 11 else "12+"


def bucket_age(a: int) -> str:
    return "0" if a == 0 else "1-2" if a <= 2 else "3-7" if a <= 7 else "8-15" if a <= 15 else "16-31" if a <= 31 else "32+"


def label_kind(lab: str | None) -> str:
    if lab is None:
        return "start"
    if lab in ("nothing", "level_clear", "game_over", "reset", "bgchange", oe.NOVEL):
        return lab
    parts = {p.split("x")[0][:2] for p in lab.split("|")}
    if parts == {"mv"}:
        return "move"
    if "mv" in parts:
        return "move+"
    if parts == {"rc"}:
        return "recolour"
    return "other"


def gap(a, b) -> int:
    """Cells strictly between two boxes (Chebyshev); 0 = adjacent or overlapping."""
    dy = max(0, b[0] - a[2] - 1, a[0] - b[2] - 1)
    dx = max(0, b[1] - a[3] - 1, a[1] - b[3] - 1)
    return max(dy, dx)


class View:
    """Everything the detectors need about one step, computed once (lazily)."""

    def __init__(self, step, state):
        self.step, self.state = step, state
        self.name = step.row.get("action_name")
        self.pa = step.pa
        self.click = None
        self.comp = None                 # clicked component (oe.Comp), None for HUD
        self.click_kind = None           # "obj" / "bg" / "hud" / "off"
        if self.name == "ACTION6":
            m = efe.MOUSE_RE.search(step.row.get("action_display", ""))
            r, c = (int(m.group(1)), int(m.group(2))) if m else (-1, -1)
            if self.pa is None or not (0 <= r < self.pa.arr.shape[0] and 0 <= c < self.pa.arr.shape[1]):
                self.click_kind = "off"
            else:
                self.click = (r, c)
                cid = int(self.pa.lab[r, c])
                if not cid:
                    self.click_kind = "hud"
                else:
                    self.comp = self.pa.comps[cid - 1]
                    self.click_kind = "bg" if self.comp.bg else "obj"
        self._arr = None
        self.agent, self.agent_state = state.agent_instance(step)
        self.dir = state.agency.tracker.direction(self.name) if self.name in BUTTONS else None

    def boxes(self):
        """Non-background, non-mode-colour components as arrays (y0, x0, y1, x1, colour, id)."""
        if self._arr is None:
            cs = [c for c in self.pa.comps if not c.bg and c.colour != self.pa.mode]
            self._arr = (np.array([[c.y0, c.x0, c.y1, c.x1, c.colour, c.id] for c in cs], dtype=np.int32)
                         if cs else np.zeros((0, 6), np.int32))
        return self._arr

    def nearest(self, box, exclude_id=None, colours=None):
        """(gap, colour) of the nearest listed component to a box, or (None, None)."""
        a = self.boxes()
        if len(a) == 0:
            return None, None
        keep = np.ones(len(a), bool)
        if exclude_id is not None:
            keep &= a[:, 5] != exclude_id
        if colours is not None:
            keep &= np.isin(a[:, 4], list(colours))
        a = a[keep]
        if len(a) == 0:
            return None, None
        dy = np.maximum(0, np.maximum(a[:, 0] - box[2] - 1, box[0] - a[:, 2] - 1))
        dx = np.maximum(0, np.maximum(a[:, 1] - box[3] - 1, box[1] - a[:, 3] - 1))
        g = np.maximum(dy, dx)
        i = int(np.lexsort((a[:, 4], g))[0])        # nearest, ties by colour: deterministic
        return int(g[i]), int(a[i, 4])

    def ref_box(self):
        """Reference box for relational detectors: the click point, or the controlled object."""
        if self.name == "ACTION6":
            return (self.click[0], self.click[1], self.click[0], self.click[1]) if self.click else None
        if self.agent is not None:
            return (self.agent.y0, self.agent.x0, self.agent.y1, self.agent.x1)
        return None

    def field_box(self):
        """Bounding box of all non-background, non-mode-colour objects (the populated play area)."""
        a = self.boxes()
        if len(a) == 0:
            return None
        return (int(a[:, 0].min()), int(a[:, 1].min()), int(a[:, 2].max()), int(a[:, 3].max()))

    def ring_ids(self, comp):
        pa = self.pa
        y0, x0 = max(comp.y0 - 1, 0), max(comp.x0 - 1, 0)
        sub = pa.lab[y0:comp.y1 + 2, x0:comp.x1 + 2]
        me = sub == comp.id
        ring = ndimage.binary_dilation(me, structure=oe.FOUR) & ~me
        return sub[ring]


# ---------------------------------------------------------------- per-play state

class PlayState:
    """History of one play, updated after each step (never looked at before the step is scored)."""

    def __init__(self):
        self.agency = ag.AgencyPerception("fd-agency", buttons=True, clicks=False)
        self.level = 0
        self.age = 0
        self.last_name = None
        self.last_click_key = None
        self.last_label = None
        self.last_moved = None           # did the controlled object move on the last button step
        self.click_mem = {}              # (shape, y0, x0) -> label of the last click on that object
        self.movers = set()              # object types that have moved at least once in this play
        self.salient = Counter()         # colour -> steps on which cells of that colour changed
        self.last_by_ctx = {}            # handcolour context -> label the last time it was taken

    def agent_instance(self, step):
        """The controlled object's component on this pre board (no state change), and a status."""
        tr = self.agency.tracker
        k = tr.controlled()
        if k is None or step.pa is None:
            return None, "noagent"
        inst = step.pa.by_type().get(k, ())
        if len(inst) > 1 and self.agency.last_pos is not None:
            y, x = self.agency.last_pos
            inst = [min(inst, key=lambda c: abs(c.y0 - y) + abs(c.x0 - x))]
        if len(inst) != 1:
            return None, "lost"
        return inst[0], "ok"

    def observe(self, step, view):
        if step.reset:
            self.age = 0
            self.last_label = "reset"
            self.last_name = None
            self.last_click_key = None
            return
        name = step.row.get("action_name")
        if name in BUTTONS and step.pa is not None:
            self.agency.button_context(step, name)        # keeps its last_pos bookkeeping exact
            if view.agent is not None:
                k = view.agent.type_key
                self.last_moved = "moved" if any(m[0] == k for m in step.moves) else "stuck"
        self.agency.observe(step)
        self.movers |= {m[0] for m in step.moves}
        if view.comp is not None:
            self.click_mem[(view.comp.shape, view.comp.y0, view.comp.x0)] = step.label
        if step.pre and step.post and step.pa is not None:
            post = np.asarray(step.post, dtype=np.int16)
            pre = step.pa.arr
            ch = (pre != post) & (pre != oe.MASKED)
            if ch.any():
                cols = set(np.unique(pre[ch]).tolist()) | set(np.unique(post[ch]).tolist())
                ctl = view.agent.colour if view.agent is not None else None
                for c in cols:
                    if c != step.pa.mode and c != ctl:
                        self.salient[int(c)] += 1
        self.last_name = name
        self.last_click_key = (view.comp.shape, view.comp.y0, view.comp.x0) if view.comp is not None else None
        self.last_label = step.label
        if step.label == "level_clear":
            self.level += 1
            self.age = 0
        else:
            self.age += 1


# ---------------------------------------------------------------- detectors

def _click(f):
    """Decorator: click-only detector; HUD / background / off-board clicks get a marker value."""
    def g(v):
        if v.name != "ACTION6":
            return None
        if v.click_kind != "obj":
            return v.click_kind
        return f(v)
    return g


def _button(f):
    def g(v):
        if v.name not in BUTTONS or v.pa is None:
            return None
        return f(v)
    return g


def _look(v, k):
    if v.agent is None:
        return v.agent_state
    if v.dir is None:
        return "nodir"
    return ag.look_ahead(v.pa, v.agent, (v.dir[0] * k, v.dir[1] * k))


def _ahead_comp(v):
    """Component (non-background, not the agent) occupying the first cell ahead, or None."""
    if v.agent is None or v.dir is None:
        return None
    dy, dx = v.dir
    s = max(abs(dy), abs(dx))
    if s > ag.MAX_LOOK:
        dy, dx = round(dy * ag.MAX_LOOK / s), round(dx * ag.MAX_LOOK / s)
    a = v.agent
    ys, xs = np.nonzero(v.pa.lab[a.y0:a.y1 + 1, a.x0:a.x1 + 1] == a.id)
    ys, xs = ys + a.y0 + dy, xs + a.x0 + dx
    h, w = v.pa.arr.shape
    ok = (ys >= 0) & (ys < h) & (xs >= 0) & (xs < w)
    for y, x in zip(ys[ok], xs[ok]):
        cid = int(v.pa.lab[y, x])
        if cid and cid != a.id:
            c = v.pa.comps[cid - 1]
            if not c.bg and c.colour != v.pa.mode:
                return c
    return None


def d_c_colour(v):
    return int(v.pa.arr[v.click])


def d_c_size(v):
    return bucket_log2(v.comp.size)


def d_c_copies(v):
    return bucket_count(len(v.pa.by_type().get(v.comp.type_key, ())))


def d_c_sameshape_other(v):
    n = sum(1 for c in v.pa.comps if not c.bg and c.shape == v.comp.shape and c.colour != v.comp.colour)
    return bucket_count(n)


def d_c_colour_count(v):
    return bucket_count(sum(1 for c in v.pa.comps if not c.bg and c.colour == v.comp.colour))


def _touch_cols(v):
    cols = set()
    for cid in np.unique(v.ring_ids(v.comp)):
        if cid:
            c = v.pa.comps[int(cid) - 1]
            if not c.bg and c.colour != v.pa.mode:
                cols.add(c.colour)
    return cols


def d_c_touch_colours(v):
    return tuple(sorted(_touch_cols(v)))[:3]


def d_c_touch_n(v):
    ids = {int(i) for i in np.unique(v.ring_ids(v.comp)) if i}
    ids = {i for i in ids if not v.pa.comps[i - 1].bg and v.pa.comps[i - 1].colour != v.pa.mode}
    return bucket_count(len(ids))


def d_c_enclosed(v):
    ids = {int(i) for i in np.unique(v.ring_ids(v.comp))}
    if len(ids) == 1 and 0 not in ids:
        o = v.pa.comps[ids.pop() - 1]
        c = v.comp
        if o.y0 <= c.y0 and o.x0 <= c.x0 and o.y1 >= c.y1 and o.x1 >= c.x1:
            return ("in", o.colour)
    return "open"


def _on_border(v, c):
    """"edge" = touches the array edge or the masked HUD; "wall" = touches a background-sized
    component that is not the mode colour (the frame / walls of the play field); "field" = touches the
    outermost row/column of the non-HUD play area's bounding box of non-mode cells; else "inner".
    (The array edge alone almost never fires: the play field is inset and the HUD is masked.)"""
    h, w = v.pa.arr.shape
    ring = v.ring_ids(c)
    if c.y0 == 0 or c.x0 == 0 or c.y1 == h - 1 or c.x1 == w - 1 or (ring == 0).any():
        return "edge"
    for cid in np.unique(ring):
        o = v.pa.comps[int(cid) - 1]
        if o.bg and o.colour != v.pa.mode:
            return "wall"
    fb = v.field_box()
    if fb and (c.y0 <= fb[0] or c.x0 <= fb[1] or c.y1 >= fb[2] or c.x1 >= fb[3]):
        return "field"
    return "inner"


def d_c_border(v):
    return _on_border(v, v.comp)


def d_c_near(v):
    g, col = v.nearest(v.ref_box(), exclude_id=v.comp.id)
    return (col, bucket_dist(g)) if g is not None and g <= 2 else "none"


def d_c_near_dist(v):
    g, _ = v.nearest(v.ref_box(), exclude_id=v.comp.id)
    return bucket_dist(g)


def d_c_side(v):
    c, (r, x) = v.comp, v.click
    cy, cx = (c.y0 + c.y1) / 2, (c.x0 + c.x1) / 2
    hy, hx = max((c.y1 - c.y0) / 4, 0.5), max((c.x1 - c.x0) / 4, 0.5)
    return (int(np.sign(r - cy)) if abs(r - cy) > hy else 0, int(np.sign(x - cx)) if abs(x - cx) > hx else 0)


def d_c_agent_rowcol(v):
    if v.agent is None:
        return v.agent_state
    a, (r, c) = v.agent, v.click
    row, col = a.y0 <= r <= a.y1, a.x0 <= c <= a.x1
    return "on" if row and col else "row" if row else "col" if col else "neither"


def d_c_mirror(v):
    h, w = v.pa.arr.shape
    c = v.comp
    lr = (c.y0, w - 1 - c.x1)
    ud = (h - 1 - c.y1, c.x0)
    found = set()
    for o in v.pa.comps:
        if o.bg or o.id == c.id or o.size != c.size:
            continue
        if abs(o.y0 - lr[0]) <= 1 and abs(o.x0 - lr[1]) <= 1:
            found.add("lr")
        if abs(o.y0 - ud[0]) <= 1 and abs(o.x0 - ud[1]) <= 1:
            found.add("ud")
    return "both" if len(found) == 2 else found.pop() if found else "none"


def d_c_last_click(v):
    lab = v.state.click_mem.get((v.comp.shape, v.comp.y0, v.comp.x0))
    return "never" if lab is None else "nothing" if lab == "nothing" else "changed"


def d_c_last_click_label(v):
    return v.state.click_mem.get((v.comp.shape, v.comp.y0, v.comp.x0), "never")


def d_c_same_obj(v):
    return (v.comp.shape, v.comp.y0, v.comp.x0) == v.state.last_click_key


def d_c_bg(v):
    return "obj"            # the decorator already returns bg / hud / off for the other cases


def _salient_cols(v):
    return {c for c, _ in v.state.salient.most_common(3)}


def d_salient(v):
    box = v.ref_box()
    if box is None or v.pa is None:
        return "noref"
    cols = _salient_cols(v)
    if not cols:
        return "nosal"
    ex = v.comp.id if v.comp is not None else (v.agent.id if v.agent is not None else None)
    g, col = v.nearest(box, exclude_id=ex, colours=cols)
    return (col, bucket_dist(g)) if g is not None else "absent"


def d_salient_profile(v):
    box = v.ref_box()
    if box is None or v.pa is None:
        return "noref"
    out = []
    ex = v.comp.id if v.comp is not None else (v.agent.id if v.agent is not None else None)
    for col in sorted(_salient_cols(v)):
        g, _ = v.nearest(box, exclude_id=ex, colours={col})
        out.append((col, "absent" if g is None else "adj" if g == 0 else "near" if g <= 4 else "far"))
    return tuple(out)


def d_b_look1(v):
    return _look(v, 1)


def d_b_look2(v):
    return _look(v, 2)


def d_b_blocked(v):
    if v.agent is None:
        return v.agent_state
    if v.dir is None:
        return "nodir"
    for k in (1, 2, 3):
        la = ag.look_ahead(v.pa, v.agent, (v.dir[0] * k, v.dir[1] * k))
        if la != ("free",):
            return (k, la[0])
    return "3+"


def d_b_ahead_mover(v):
    if v.agent is None:
        return v.agent_state
    if v.dir is None:
        return "nodir"
    c = _ahead_comp(v)
    if c is None:
        return "clear"
    return "mover" if c.type_key in v.state.movers else "static"


def d_b_agent_copies(v):
    if v.agent is None and v.agent_state == "noagent":
        return "noagent"
    k = v.state.agency.tracker.controlled()
    return bucket_count(len(v.pa.by_type().get(k, ())))


def d_b_last_moved(v):
    if v.agent is None:
        return v.agent_state
    return v.state.last_moved or "first"


def d_b_near(v):
    if v.agent is None:
        return v.agent_state
    g, col = v.nearest(v.ref_box(), exclude_id=v.agent.id)
    return (col, bucket_dist(g)) if g is not None else "none"


def d_b_agent_border(v):
    if v.agent is None:
        return v.agent_state
    return _on_border(v, v.agent)


def d_level(v):
    return min(v.state.level, 3)


def d_age(v):
    return bucket_age(v.state.age)


def d_repeat(v):
    if v.state.last_name is None:
        return "first"
    return v.name == v.state.last_name


def d_last_label(v):
    return v.state.last_label or "start"


def d_last_kind(v):
    return label_kind(v.state.last_label)


def d_last_same(v):
    return v.state.last_by_ctx.get(v.hc_ctx, "never")


def d_last_same_kind(v):
    lab = v.state.last_by_ctx.get(v.hc_ctx)
    return "never" if lab is None else label_kind(lab)


def d_n_objects(v):
    if v.pa is None:
        return "nopre"
    return bucket_log2(sum(1 for c in v.pa.comps if not c.bg))


# name -> (applies to, function, plain meaning)
DETECTORS = {
    "c_colour": ("click", _click(d_c_colour), "colour of the clicked cell (already in handcolour)"),
    "c_size": ("click", _click(d_c_size), "clicked object's size, doubling buckets"),
    "c_copies": ("click", _click(d_c_copies), "how many identical copies (same colour and shape) are on the board"),
    "c_sameshape_other": ("click", _click(d_c_sameshape_other), "how many objects of the same shape but another colour"),
    "c_colour_count": ("click", _click(d_c_colour_count), "how many objects share the clicked colour"),
    "c_touch_colours": ("click", _click(d_c_touch_colours), "which colours the clicked object touches"),
    "c_touch_n": ("click", _click(d_c_touch_n), "how many objects the clicked object touches"),
    "c_enclosed": ("click", _click(d_c_enclosed), "clicked object sits inside one other object (and its colour)"),
    "c_border": ("click", _click(d_c_border), "clicked object on the board edge or HUD / against a wall / on the rim of the populated area / inside"),
    "c_near": ("click", _click(d_c_near), "colour and distance of the nearest other object within two cells of the click point"),
    "c_near_dist": ("click", _click(d_c_near_dist), "distance from the click point to the nearest other object"),
    "c_side": ("click", _click(d_c_side), "which part of the object was clicked (top/bottom, left/right, middle)"),
    "c_agent_rowcol": ("click", _click(d_c_agent_rowcol), "click in the controlled object's row, column, on it, or neither"),
    "c_mirror": ("click", _click(d_c_mirror), "an object of the same size sits at the mirror position (left-right / up-down)"),
    "c_last_click": ("click", _click(d_c_last_click), "did this object change the last time it was clicked (never / nothing / changed)"),
    "c_last_click_label": ("click", _click(d_c_last_click_label), "what happened the last time this object was clicked"),
    "c_same_obj": ("click", _click(d_c_same_obj), "same object as the previous click"),
    "c_bg": ("click", _click(d_c_bg), "click on an object, the background, or the HUD"),
    "salient": ("any", d_salient, "nearest object of a colour that has been changing in this play, and how far"),
    "salient_profile": ("any", d_salient_profile, "distance class to each of the three most-changing colours"),
    "b_look1": ("button", _button(d_b_look1), "what the controlled object would move into (free / edge / wall / object colour)"),
    "b_look2": ("button", _button(d_b_look2), "what lies two moves ahead of the controlled object"),
    "b_blocked": ("button", _button(d_b_blocked), "moves until the path is blocked (1, 2, 3, open) and by what"),
    "b_ahead_mover": ("button", _button(d_b_ahead_mover), "the object ahead has moved before in this play (pushable) or not"),
    "b_agent_copies": ("button", _button(d_b_agent_copies), "how many copies of the controlled object are on the board"),
    "b_last_moved": ("button", _button(d_b_last_moved), "did the controlled object move on the last button press"),
    "b_near": ("button", _button(d_b_near), "nearest other object to the controlled object: colour and distance"),
    "b_agent_border": ("button", _button(d_b_agent_border), "controlled object on the board edge or HUD / against a wall / on the rim of the populated area / inside"),
    "level": ("any", d_level, "level index within the play (0, 1, 2, 3+)"),
    "age": ("any", d_age, "actions since the level started, bucketed"),
    "repeat": ("any", d_repeat, "same action as the previous step"),
    "last_label": ("any", d_last_label, "the previous step's outcome label"),
    "last_kind": ("any", d_last_kind, "the previous step's outcome kind (nothing / move / recolour / clear / other)"),
    "n_objects": ("any", d_n_objects, "number of objects on the board, doubling buckets"),
    # added after the step-one look at the data (outcomes that alternate or repeat per action)
    "last_same": ("any", d_last_same, "what happened the last time this same action (same button, or same "
                                      "clicked shape and colour) was taken in this play"),
    "last_same_kind": ("any", d_last_same_kind, "the kind of that outcome (nothing / move / recolour / other)"),
}


def hand_colour_ctx(step, perception) -> tuple:
    return perception.context(step)


def run_trace(trace, names=None) -> list:
    """[(handcolour context, label, {detector: value})] for every non-reset step, in order."""
    names = list(names or DETECTORS)
    hc = ag.AgencyPerception("handcolour", buttons=False, clicks=False, click_colour=True)
    hc.reset()
    st = PlayState()
    out = []
    for s in trace.steps:
        if s.reset:
            st.observe(s, None)
            continue
        v = View(s, st)
        ctx = hc.context(s)
        v.hc_ctx = ctx
        vals = {}
        for n in names:
            try:
                vals[n] = DETECTORS[n][1](v) if s.pa is not None or DETECTORS[n][0] == "any" else None
            except Exception as e:          # a detector must never kill a play; record the failure
                vals[n] = ("err", type(e).__name__)
        out.append((ctx, s.label, vals))
        hc.observe(s)
        st.observe(s, v)
        st.last_by_ctx[ctx] = s.label
    return out

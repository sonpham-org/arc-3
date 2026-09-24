#!/usr/bin/env python3
# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Round four, expert-debate plan item 3 (OpenMind, #arc-3): object-centric contexts with
#   AGENCY for the prequential Dirichlet yardstick.
#   Button context = (button, what lies next to the controlled object in the direction that button
#   has been seen to move it): "free" (board's mode colour), "edge" (off the board or into the HUD),
#   ("wall", colour) for a background-sized component, ("obj", colour) for a small one. Early steps
#   get explicit placeholders instead of back-filled knowledge: "noagent" (no controllable object
#   identified yet), "nodir" (this button has not moved it yet), "lost" (the controlled type is not
#   uniquely on the board).
#   The controlled object is found ONLINE, from the steps already seen: every object type (colour +
#   shape) that has ever moved after a button press is tracked; on each later button step where it
#   is unique on the pre board its displacement (0,0 if it stayed) is counted under the button.
#   Evidence = N * I(button; displacement), the plug-in mutual information times the sample count
#   (half the G-test statistic, an empowerment-style "the button predicts where it goes"). The type
#   with the most evidence, above AGENCY_MIN_EVIDENCE nats, is the controlled object; if several
#   identical pieces of that type are on the board, the one nearest its last known position is used. An object that
#   drifts the same way whatever is pressed gets I = 0, so a conveyor is not mistaken for an avatar.
#   Click context = (handmade shape type of the clicked object, touching another non-background
#   object or not). Background clicks keep ("M", "bg").
#   Ablations: agency-buttons (agency buttons, handmade clicks) and agency-clicks (handmade buttons,
#   touching-flag clicks). click_colour=True adds the clicked cell's colour to click contexts (the
#   handmade key drops colour on purpose; this control asks whether a learned code wins only by
#   seeing it): "handcolour" = handmade + colour, "agency-colour" = agency + colour. The tracker can persist across traces of the same game (carry=True).
#   Works on object_events.Trace steps; reads nothing else; no harness change.
# SRP/DRY check: Pass -- components, type keys and matched moves come from object_events.py; the
#   click object type is efe_trace_analysis.context_of. Nothing in distill/ estimates agency.
"""Agency-based (object-centric) contexts for round four."""
from __future__ import annotations

import math
from collections import Counter, defaultdict

import numpy as np
from scipy import ndimage

import efe_trace_analysis as efe
import object_events as oe

AGENCY_MIN_EVIDENCE = 3.0     # nats of N * I(button; displacement) before an object counts as controlled
MAX_LOOK = 8                  # cells looked ahead are capped at this displacement
BUTTONS = ("ACTION1", "ACTION2", "ACTION3", "ACTION4", "ACTION5", "ACTION7")


def mi_evidence(table: dict) -> float:
    """N * plug-in I(b; d) from {button: Counter(displacement)}."""
    nb = {b: sum(c.values()) for b, c in table.items()}
    n = sum(nb.values())
    if n == 0:
        return 0.0
    nd = Counter()
    for c in table.values():
        nd.update(c)
    i = 0.0
    for b, c in table.items():
        for d, k in c.items():
            i += k / n * math.log(k * n / (nb[b] * nd[d]))
    return n * i


class AgencyTracker:
    """Online controllable-object estimate for one trace (or one game when carried)."""

    def __init__(self):
        self.stats: dict = defaultdict(lambda: defaultdict(Counter))   # type -> button -> Counter(d)
        self.tracked: set = set()
        self._best = None
        self._dirty = True

    def controlled(self):
        if self._dirty:
            best, ev = None, AGENCY_MIN_EVIDENCE
            for k in sorted(self.tracked):          # sorted: deterministic tie-break
                e = mi_evidence(self.stats[k])
                if e > ev:
                    best, ev = k, e
            self._best, self._dirty = best, False
        return self._best

    def direction(self, button):
        k = self.controlled()
        if k is None:
            return None
        c = Counter({d: n for d, n in self.stats[k][button].items() if d != (0, 0)})
        return c.most_common(1)[0][0] if c else None

    def observe(self, step: oe.Step):
        """Learn from one finished button step (after its context was scored)."""
        name = step.row.get("action_name")
        if step.reset or step.pa is None or name not in BUTTONS:
            return
        moved = {}
        for key, dy, dx in step.moves:
            moved.setdefault(key, []).append((dy, dx))
        self.tracked |= set(moved)
        by_type = step.pa.by_type()
        for k in self.tracked:
            if len(by_type.get(k, ())) != 1:
                continue
            ds = moved.get(k)
            d = ds[0] if ds and len(ds) == 1 else (0, 0) if not ds else None
            if d is not None:
                self.stats[k][name][d] += 1
                self._dirty = True


def look_ahead(pa: oe.BoardComps, comp: oe.Comp, d) -> tuple:
    """What occupies the cells the object would move into under displacement d."""
    dy, dx = d
    s = max(abs(dy), abs(dx))
    if s > MAX_LOOK:
        dy, dx = round(dy * MAX_LOOK / s), round(dx * MAX_LOOK / s)
    h, w = pa.arr.shape
    ys, xs = np.nonzero(pa.lab[comp.y0:comp.y1 + 1, comp.x0:comp.x1 + 1] == comp.id)
    ys, xs = ys + comp.y0 + dy, xs + comp.x0 + dx
    if (ys < 0).any() or (ys >= h).any() or (xs < 0).any() or (xs >= w).any():
        return ("edge",)
    keep = pa.lab[ys, xs] != comp.id
    ys, xs = ys[keep], xs[keep]
    if ys.size == 0:
        return ("free",)
    vals = pa.arr[ys, xs]
    if (vals == oe.MASKED).any():
        return ("edge",)
    other = vals != pa.mode
    if not other.any():
        return ("free",)
    colours = Counter(int(v) for v in vals[other])
    col = colours.most_common(1)[0][0]
    pick = np.nonzero(other & (vals == col))[0][0]
    cid = int(pa.lab[ys[pick], xs[pick]])
    return ("wall" if pa.comps[cid - 1].bg else "obj", col)


def touching(pa: oe.BoardComps, comp: oe.Comp) -> bool:
    y0, x0 = max(comp.y0 - 1, 0), max(comp.x0 - 1, 0)
    sub = pa.lab[y0:comp.y1 + 2, x0:comp.x1 + 2]
    me = sub == comp.id
    ring = ndimage.binary_dilation(me, structure=oe.FOUR) & ~me
    for cid in np.unique(sub[ring]):
        if cid and not pa.comps[int(cid) - 1].bg and pa.comps[int(cid) - 1].colour != pa.mode:
            return True
    return False


class AgencyPerception:
    """Prequential perception: context(step) before the outcome, observe(step) after it."""

    def __init__(self, name="agency", buttons=True, clicks=True, click_colour=False):
        self.name, self.use_buttons, self.use_clicks = name, buttons, clicks
        self.click_colour = click_colour
        self.reset()

    def reset(self):
        self.tracker = AgencyTracker()
        self.last_pos = None

    def button_context(self, step, name):
        tr = self.tracker
        k = tr.controlled()
        if k is None:
            return (name, "noagent")
        inst = step.pa.by_type().get(k, ()) if step.pa else ()
        if len(inst) > 1 and self.last_pos is not None:
            # several identical pieces: the controlled one is the one nearest where it was last seen
            y, x = self.last_pos
            inst = [min(inst, key=lambda c: abs(c.y0 - y) + abs(c.x0 - x))]
        if len(inst) != 1:
            return (name, "lost")
        self.last_pos = (inst[0].y0, inst[0].x0)
        d = tr.direction(name)
        if d is None:
            return (name, "nodir")
        return (name,) + look_ahead(step.pa, inst[0], d)

    def click_context(self, step, relation=True):
        ctx = efe.context_of(step.row, step.pre)
        if ctx[1] != "type" or step.pa is None:
            return ctx
        m = efe.MOUSE_RE.search(step.row.get("action_display", ""))
        r, c = int(m.group(1)), int(m.group(2))
        if self.click_colour:
            ctx = ctx + (int(step.pre[r][c]),)
        if not relation:
            return ctx
        cid = int(step.pa.lab[r, c])
        if not cid:
            return ctx + ("hud",)
        return ctx + ("touch" if touching(step.pa, step.pa.comps[cid - 1]) else "alone",)

    def context(self, step):
        name = step.row.get("action_name")
        if name == "ACTION6":
            return self.click_context(step, relation=self.use_clicks)
        if self.use_buttons and step.pa is not None:
            return self.button_context(step, name)
        return (name,)

    def observe(self, step):
        self.tracker.observe(step)
        k = self.tracker.controlled()
        for key, dy, dx in step.moves:
            if key == k and self.last_pos is not None:
                self.last_pos = (self.last_pos[0] + dy, self.last_pos[1] + dx)
                break

    def describe(self):
        k = self.tracker.controlled()
        return None if k is None else {"colour": k[0], "evidence": round(mi_evidence(self.tracker.stats[k]), 1)}

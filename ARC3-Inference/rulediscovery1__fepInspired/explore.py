# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026 (tensor-logic mover and search 24-September-2026)
# PURPOSE: Proposal step 1 (docs/plans/2026-09-23-rulediscovery-locksmith-score.md, approved by OpenMind in
#   #arc-3 23:21 ET): a goal "go and touch the nearest object not yet touched", planned with the agent's
#   OWN learned movement rules, so the agent makes purposeful trips instead of wandering.
#     - Mover model: the highest-weight hypothesis whose rule set moves the controlled sprite
#       (rules.PadMoveRule or rules.MoveRule, with its partner group). gate="map" demands it be the MAP
#       hypothesis; gate="any" takes the best one that has a mover at all.
#     - Planner: breadth-first search over the sprite's offsets on the CURRENT board. A step is allowed
#       when every cell the sprite would cover is on the board, not HUD, and not a colour the rule has
#       learned as a wall; the final step may enter the target itself. Goal: the sprite's box meets the
#       box of an untouched object (non-background, not the sprite).
#     - Touched: after every step, objects the sprite is ON (one box contains the other; brushing an edge
#       does not count, so walking up to Locksmith's lock frame is not "entering the lock"). When anything
#       away from the sprite changes between two boards (an object appears, vanishes, moves or changes
#       shape; e.g. Locksmith's key display after a rotation tile), the touched set is cleared, so every
#       object becomes worth touching again. Among reachable untouched objects the one touched LEAST
#       recently (never touched first) is chosen, ties by path length, so the agent does not bounce back
#       onto the tile it has just used (in Locksmith that would rotate the key again and again).
#     - A plan is dropped as soon as the sprite does not move the way the rule said; the next step replans
#       with whatever the rule learned from the failure. A trip that fails counts as touching its target
#       (the agent bumped into it or could not get there), so an unreachable object is not chased forever.
#     - Trips start only after every button has been tried a few times (by the EFE / curiosity policy),
#       so the movers exist for all arrows, not just the first one learned.
#   Nothing here reads the game's internals: only the agent's board, its controlled-object estimate and
#   its rule sets.
#   24-Sep-2026 HDC integration A/B: the sprite may come from common fate (group rules.FATE), and search() takes
#   the soft wall map snapshot (hdc_bridge.WallView): where the mover's colour sets are silent about a step's new
#   strip, a decisive "blocked" from the soft map refuses the step. Without HDC both are inert.
#   24-Sep-2026 tensor-logic overhaul: with the templates off (AgentConfig.tl_templates False) or no template mover yet,
#   the mover comes from the learned tensor-logic program (tl.bridge.TLSource.mover: arrows and learned wall colours;
#   the sprite's parts from the relational view's common-fate group), and ExploreConfig.search "tl" plans by
#   forward-chaining reachability (tl/plan.py) instead of the breadth-first search below.
# SRP/DRY check: Pass -- movement and walls come from rules.MoveRule / PadMoveRule and group_look_ahead's
#   conventions, partner parts from rules.partner_comps, the controlled object from the ContextBuilder.
#   New here: the offset search, the touched bookkeeping and the hook the agent calls.
"""Object-contact exploration: plan with the learned movers to the nearest untouched object."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ._distill import oe
from .perception import BUTTONS, Action
from .rules import FATE, MoveRule, PadMoveRule, fate_partners, partner_comps


@dataclass
class ExploreConfig:
    gate: str = "fitted"           # "map": the MAP hypothesis must move the sprite; "any": best surviving one
    #                                that does; "fitted": the template fitter's best current mover for the
    #                                sprite, whether or not it has won posterior weight (counts cannot plan)
    max_nodes: int = 4000
    min_tries: int = 3             # every button is tried this often (by the policy) before trips start
    search: str = "bfs"            # "bfs" (below) or "tl" (tl/plan.py: reachability by forward chaining)


TLGROUP = (("tl",),)               # mover group sentinel: partners = the tensor-logic view's common-fate group


def _box(comps) -> tuple:
    return (min(c.y0 for c in comps), min(c.x0 for c in comps), max(c.y1 for c in comps), max(c.x1 for c in comps))


def _near(a: tuple, b: tuple, gap: int = 1) -> bool:
    return a[0] <= b[2] + gap and b[0] <= a[2] + gap and a[1] <= b[3] + gap and b[1] <= a[3] + gap


def _on(a: tuple, b: tuple) -> bool:
    """The sprite is ON the object: one box contains the other (a small marker under the sprite, or the
    sprite inside a frame such as Locksmith's lock). Brushing an edge does not count."""
    inside = lambda p, q: p[0] >= q[0] and p[1] >= q[1] and p[2] <= q[2] and p[3] <= q[3]  # noqa: E731
    return inside(a, b) or inside(b, a)


class RuleSetLike:
    """A bare list of fitted rules with the one method the mover lookup needs."""

    def __init__(self, rules):
        self._rules = list(rules)

    def rules(self):
        return self._rules


class ObjectContactExplorer:
    def __init__(self, cfg: Optional[ExploreConfig] = None):
        self.cfg = cfg or ExploreConfig()
        self.touched: set = set()         # object keys (type, y0, x0) touched since the world last changed
        self.prev_objs: Optional[set] = None
        self.prev_box: Optional[tuple] = None
        self.plan: list = []
        self.expect: Optional[tuple] = None   # (action, dy, dx) the current plan step should produce
        self.target = None
        self.trips = 0
        self._fit_cache = (-1, [])
        self.last_touch: dict = {}        # object key -> step it was last touched (this level)
        self.t = 0
        self.tries: dict = {}             # button -> times pressed this play
        self.exclude: set = set()         # actions never used as moves (e.g. a learned rewind; hdc stage 6)
        self.passable: set = set()        # colours the chosen mover has passed (HDC wall guard: colour first)

    def reset_level(self) -> None:
        self.touched, self.plan, self.expect, self.target = set(), [], None, None
        self.prev_objs, self.prev_box = None, None
        self.last_touch = {}

    # -- model
    def mover_model(self, agent) -> Optional[tuple]:
        """(moves {action: (dy, dx)}, blockers, group) from the chosen hypothesis, or None."""
        s = agent.slow
        ctl = s.ctx.state.agency.tracker.controlled()
        if ctl is None:
            return None
        if self.cfg.gate == "fitted":
            if self._fit_cache[0] != agent.n_steps:
                templates = getattr(agent.proposer, "templates", True)
                cands = agent.proposer.fitter.propose(s.beliefs.records) if templates else []
                # a d-pad first (it pools the wall evidence), then single movers
                cands = sorted(cands, key=lambda r: not isinstance(r, PadMoveRule))
                self._fit_cache = (agent.n_steps, [(RuleSetLike(cands), 1.0)])
            hyps = self._fit_cache[1]
        else:
            hyps = s.beliefs.top(len(s.beliefs.hyps))
            hyps = [(h.ruleset, w) for h, w in hyps]
            if self.cfg.gate == "map":
                hyps = hyps[:1]
        for rs, _ in hyps:
            moves, blockers, passable, group = {}, set(), set(), ()
            for r in rs.rules():
                mrs = []
                if isinstance(r, PadMoveRule):
                    mrs = [r.as_move(a) for a, _, _ in r.moves]
                elif isinstance(r, MoveRule):
                    mrs = [r]
                for m in mrs:
                    if m.action in self.exclude:
                        continue
                    if (m.type_key == ctl or ctl in m.group) and m.action not in moves:
                        moves[m.action] = (m.dy, m.dx)
                        blockers |= set(m.blockers)
                        passable |= set(m.passable)
                        group = m.group if len(m.group) > len(group) else group
            if moves:
                self.passable = passable - blockers
                return moves, blockers, (ctl, group)
        src = getattr(agent, "tl_source", None)
        if src is not None:                          # no template mover: the learned tensor-logic program's
            m = src.mover(ctl)
            if m is not None:
                moves, blockers, passable = m
                moves = {a: d for a, d in moves.items() if a not in self.exclude}
                if moves:
                    self.passable = set(passable) - set(blockers)
                    return moves, set(blockers), (ctl, TLGROUP)
        return None

    # -- perception helpers
    def sprite(self, agent, scene, ctl, group) -> Optional[list]:
        rc = agent.slow.ctx.context(scene, Action(BUTTONS[0]))
        comp = rc.agent
        if comp is None:
            return None
        if group == FATE:
            return [comp] + fate_partners(rc, comp)
        if group == TLGROUP:
            ids = set(rc.tl.group.get(comp.id, ())) if rc.tl is not None else set()
            return [comp] + [c for c in scene.objects() if c.id in ids]
        others = tuple(t for t in group if t != comp.type_key) if group else ()
        if ctl != comp.type_key and ctl not in (group or ()):
            return None
        parts = partner_comps(scene, comp, others) if others else []
        return [comp] + (parts or [])

    def objects(self, scene, sprite) -> list:
        ids = {c.id for c in sprite}
        return [c for c in scene.objects() if c.id not in ids]


    # -- search
    def search(self, scene, sprite, moves, blockers, untouched, walls=None) -> Optional[tuple]:
        """walls: hdc_bridge.WallView or None. With it, a step whose newly entered strip has no colour the mover
        knows (neither a learned wall nor passed) is refused when the soft map's mean score over the strip says
        blocked beyond its margin (colour rule first, as in rules.MoveRule)."""
        pa = scene.comps
        h, w = pa.arr.shape
        own = {c.id for c in sprite}
        ys, xs = [], []
        for c in sprite:
            yy, xx = np.nonzero(pa.lab[c.y0:c.y1 + 1, c.x0:c.x1 + 1] == c.id)
            ys.append(yy + c.y0)
            xs.append(xx + c.x0)
        ys, xs = np.concatenate(ys), np.concatenate(xs)
        box0 = _box(sprite)
        tboxes = [(c, (c.y0, c.x0, c.y1, c.x1)) for c in untouched]
        blk = np.isin(pa.arr, list(blockers)) if blockers else np.zeros(pa.arr.shape, dtype=bool)
        # the area of every candidate target is optimistically open: the agent may have learned the target's
        # colour as a wall by bumping into it (Locksmith's lock refuses a wrong key), but entering it is
        # exactly what the trip is for
        for c, (y0, x0, y1, x1) in tboxes:
            blk[y0:y1 + 1, x0:x1 + 1] = False
        blk |= pa.arr == oe.MASKED
        soft = None
        if walls is not None:
            smap = walls.score_map(pa.arr)
            own_now = np.zeros(pa.arr.shape, dtype=bool)
            own_now[ys, xs] = True
            known = np.isin(pa.arr, list(self.passable | set(blockers)))
            tmask = np.zeros(pa.arr.shape, dtype=bool)
            for c, (y0, x0, y1, x1) in tboxes:
                tmask[y0:y1 + 1, x0:x1 + 1] = True
            cellset = set(zip(ys.tolist(), xs.tolist()))
            edge = {}                         # move -> the sprite cells that lead into new ground
            for a, (dy, dx) in moves.items():
                e = [i for i, (y, x) in enumerate(zip(ys.tolist(), xs.tolist())) if (y + dy, x + dx) not in cellset]
                edge[a] = np.array(e, dtype=int)
            soft = (smap, own_now, known, tmask, edge)
        start = (0, 0)
        found: dict = {}                      # target id -> (path, comp), shortest path per target
        prev = {start: None}
        q = deque([start])
        while q and len(prev) < self.cfg.max_nodes:
            oy, ox = q.popleft()
            for a, (dy, dx) in moves.items():
                ny, nx = oy + dy, ox + dx
                if (ny, nx) in prev:
                    continue
                cy, cx = ys + ny, xs + nx
                if (cy < 0).any() or (cy >= h).any() or (cx < 0).any() or (cx >= w).any():
                    continue
                box = (box0[0] + ny, box0[1] + nx, box0[2] + ny, box0[3] + nx)
                hit = next((c for c, tb in tboxes if _on(box, tb)), None)
                cover = pa.lab[cy, cx]
                free = ~np.isin(cover, list(own))
                if blk[cy[free], cx[free]].any():
                    continue
                if soft is not None:
                    smap, own_now, known, tmask, edge = soft
                    ey, ex = ys[edge[a]] + ny, xs[edge[a]] + nx
                    keep = ~own_now[ey, ex] & ~tmask[ey, ex]
                    ey, ex = ey[keep], ex[keep]
                    if ey.size and not known[ey, ex].all() and smap[ey, ex].mean() >= walls.tau:
                        continue
                prev[(ny, nx)] = ((oy, ox), a, (dy, dx))
                if hit is not None:
                    if hit.id not in found:
                        path, node = [], (ny, nx)
                        while prev[node] is not None:
                            p, act, d = prev[node]
                            path.append((act, d))
                            node = p
                        found[hit.id] = (list(reversed(path)), hit)
                    continue                          # do not walk through a target
                q.append((ny, nx))
        if not found:
            return None
        key = lambda c: self.last_touch.get((c.type_key, c.y0, c.x0), -1)  # noqa: E731
        return min(found.values(), key=lambda ph: (key(ph[1]), len(ph[0])))

    # -- agent hooks
    def next_action(self, agent) -> Optional[Action]:
        model = self.mover_model(agent)
        if model is None:
            self.plan = []
            return None
        moves, blockers, (ctl, group) = model
        scene = agent.perceiver.current
        buttons = [v for v in agent.valid if v in BUTTONS]
        if not self.plan and any(self.tries.get(b, 0) < self.cfg.min_tries for b in buttons):
            return None                               # let the policy finish trying every button
        if not self.plan:
            sprite = self.sprite(agent, scene, ctl, group)
            if not sprite:
                return None
            untouched = [c for c in self.objects(scene, sprite) if (c.type_key, c.y0, c.x0) not in self.touched]
            if not untouched:
                return None
            walls = agent.slow.ctx.context(scene, Action(BUTTONS[0])).walls
            mv = {a: d for a, d in moves.items() if a in agent.valid}
            if self.cfg.search == "tl" and walls is None:
                from .tl import plan as tl_plan
                found = tl_plan.search(scene, sprite, mv, blockers, untouched, _on,
                                       lambda c: self.last_touch.get((c.type_key, c.y0, c.x0), -1))
            else:
                found = self.search(scene, sprite, mv, blockers, untouched, walls)
            if found is None:
                return None
            self.plan, self.target = found
            self.trips += 1
        act, d = self.plan.pop(0)
        self.expect = (act, d)
        return Action(act)

    def observe(self, agent, action: Action, tr) -> None:
        self.tries[action.name] = self.tries.get(action.name, 0) + 1
        if tr.level_completed or tr.reset:
            self.reset_level()
            return
        ended_target = None
        if self.expect is not None:
            act, (dy, dx) = self.expect
            ok = action.name == act and any((ddy, ddx) == (dy, dx) for _, ddy, ddx in tr.moves)
            if not ok:
                self.plan = []                        # the model was wrong here: replan next step
            if not self.plan:
                # the trip ended (arrived, or failed on the way): the target counts as touched either way.
                # Marked by key, because an object the sprite stands on is covered and cannot be seen.
                ended_target = self.target
            self.expect = None
        model = self.mover_model(agent)
        if model is None:
            return
        _, _, (ctl, group) = model
        scene = agent.perceiver.current
        sprite = self.sprite(agent, scene, ctl, group)
        if not sprite:
            return
        sb = _box(sprite)
        objs = {(c.type_key, c.y0, c.x0): (c.y0, c.x0, c.y1, c.x1) for c in self.objects(scene, sprite)}
        if self.prev_objs is not None:
            boxes = [sb] + ([self.prev_box] if self.prev_box else [])
            far = lambda d: {k for k, b in d.items() if not any(_near(x, b) for x in boxes)}  # noqa: E731
            if far(objs) != far(self.prev_objs):
                self.touched.clear()                  # something away from the sprite changed
        self.t += 1
        if ended_target is not None:
            k = (ended_target.type_key, ended_target.y0, ended_target.x0)
            self.touched.add(k)
            self.last_touch[k] = self.t
        for k, b in objs.items():
            if _on(sb, b):
                self.touched.add(k)
                self.last_touch[k] = self.t
        self.prev_objs, self.prev_box = objs, sb
        if self.target is not None and not self.plan:
            self.target = None

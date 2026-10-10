# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026 (tensor-logic mover and search 24-September-2026, debate three and four 25-September-2026)
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
#   24-Sep-2026 debate pick 1 (Claude Opus 5.5 (Bubba)): with the contingency self (AgentConfig.use_self) the mover is the
#   self's own tallies (selfmodel.ContingentSelf.mover: learned moves, blocked / passable colours) and the sprite is the
#   self's parts on the board, so a trip never targets the agent's own body and survives a sprite that redraws on turning.
#   25-Sep-2026 stage one, the explorer as an OPTION (docs 2026-09-25-warehouse-expert-debate-2.md pick 1; Claude Opus 5.5
#   (Bubba)): with ExploreConfig.handoff a trip is a temporally extended action that terminates and hands control back to
#   the EFE policy (a) on ARRIVAL: the self's box comes into contact (box gap 0) with an object it was not in contact with
#   on the previous board (any object; each (object, self position) pair hands off once per level), (b) on SURPRISE: the
#   posterior's surprisal for the step's outcome is a spike or at least handoff_nats, or the step did not move the self as
#   the trip's mover predicted ("blocked"; with the contingency self the self's own displacement is the test, so a
#   sprite redrawn on turning does not count as blocked), and (c) when the trip reaches its target ("end"). The trip's target is not
#   counted as touched when the trip is cut short. After a hand-off the policy keeps the choice for up to `dwell` steps
#   while the self stays where the hand-off happened (it may press a button that does not move, or turn in place); the
#   next trip starts once the self moves or the dwell runs out. Off by default = the old explorer exactly.
#   25-Sep-2026 debate three, pick 1 (docs 2026-09-25-warehouse-expert-debate-3.md, OpenMind #arc-3 05:47 ET; Claude Opus 5.5
#   (Bubba)): ExploreConfig.interrupt (with handoff; AgentConfig.handoff_efe) makes the trip an INTERRUPTING option (Sutton,
#   Precup & Singh): arrival (new contact), RELATIVE surprise (the step's surprisal is at least z_surprise standard
#   deviations above this play's own running mean over its scored steps, after min_sur_n of them, or a spike), blocked
#   and trip end no longer cut the trip; they only raise a CHECK. At a check the agent (agent._interrupt) scores every
#   candidate with the EFE policy and interrupts only if the best action that does not move the self (a button with no
#   learned move, a click; not RESET) has lower G than every moving action: continuing the trip is worth at least the best
#   one-step move, so only a choice the trip cannot make can beat it. Games whose buttons all move the self never
#   interrupt. Up to `dwell` interrupting actions per check; then the SAME trip resumes: the remaining path if the self
#   is where it was, else a new path to the same target (resume_target) before any other target. Blocked keeps its old
#   meaning (the mover was wrong: the target counts as touched, a new trip is planned). Off = stage one / old explorer.
#   25-Sep-2026 debate four, pick 1 (docs 2026-09-25-warehouse-expert-debate-4.md, OpenMind #arc-3 11:24 ET; Claude Opus 5.5
#   (Bubba)): peek() plans the NEXT trip without committing to it (cached for this step, so next_action takes the same
#   path), which the agent's option-value comparison needs at a check raised on a trip's end or when blocked. With
#   ExploreConfig.try_once, contact CLASSES are the colours of the objects the self comes into contact with (box gap 0),
#   kept for the whole play (not per level, not per position); the first time a trip step brings the self into contact
#   with a colour it has never touched, a check is raised (if none was) and try_pending is set, and the agent then
#   presses the best non-moving button there once. Off = debate three's explorer.
# SRP/DRY check: Pass -- movement and walls come from rules.MoveRule / PadMoveRule and group_look_ahead's
#   conventions, partner parts from rules.partner_comps, the controlled object from the ContextBuilder.
#   New here: the offset search, the touched bookkeeping and the hook the agent calls.
"""Object-contact exploration: plan with the learned movers to the nearest untouched object."""
from __future__ import annotations

import math
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
    handoff: bool = False          # stage one: a trip ends on arrival / surprise and hands the choice to the policy
    handoff_nats: float = 2.5      # surprise: the posterior surprisal of the step's outcome reaches this (or spikes)
    dwell: int = 3                 # policy steps after a hand-off while the self stays put
    interrupt: bool = False        # debate three pick 1: EFE-compared interruption + relative surprise + resume
    z_surprise: float = 2.0        # relative surprise: z-score of the step's surprisal against the play's running mean
    min_sur_n: int = 20            # scored steps before relative surprise can fire
    try_once: bool = False         # debate four pick 1: first contact with a new colour -> try the non-moving buttons once


TLGROUP = (("tl",),)               # mover group sentinel: partners = the tensor-logic view's common-fate group
SELFGROUP = (("self",),)           # mover group sentinel: the sprite = the contingency self's parts (debate pick 1)


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
        # stage one hand-off (ExploreConfig.handoff)
        self.dwell = 0                    # policy steps left after a hand-off
        self.dwell_box: Optional[tuple] = None
        self.prev_adj: Optional[set] = None   # objects in contact with the self on the previous board
        self.handed: set = set()          # (object key, self box) pairs that already handed off this level
        self.handoffs: dict = {}          # trigger -> count
        self.trip_steps = 0               # steps taken by trips (with hand-off on)
        self.dwell_steps = 0              # policy steps inside a dwell
        # debate three pick 1 (ExploreConfig.interrupt)
        self.check: Optional[str] = None  # the trigger of a pending EFE check (arrival / surprise / blocked / end)
        self.resume_target = None         # an interrupted trip's target, re-planned to first when its path broke
        self.sur_n, self.sur_mean, self.sur_m2 = 0, 0.0, 0.0   # running surprisal of this play's scored steps
        self.checks: dict = {}            # trigger -> checks raised
        self.interrupts: dict = {}        # trigger -> interrupting actions taken
        self.resumed = 0                  # trips resumed (same path or same target) after an interruption
        # debate four pick 1
        self.contact_classes: set = set()  # colours the self has been in contact with this play
        self.try_pending = False          # a trip step just met a new contact class: try the non-moving buttons once
        self.new_classes = 0              # new contact classes met on trip steps
        self._peek = (-1, None)           # (agent step, found trip or None) planned by peek() for this step

    def reset_level(self) -> None:
        self.touched, self.plan, self.expect, self.target = set(), [], None, None
        self.prev_objs, self.prev_box = None, None
        self.last_touch = {}
        self.dwell, self.dwell_box, self.prev_adj, self.handed = 0, None, None, set()
        self.check, self.resume_target = None, None
        self.try_pending = False

    # -- model
    def mover_model(self, agent) -> Optional[tuple]:
        """(moves {action: (dy, dx)}, blockers, group) from the chosen hypothesis, or None."""
        s = agent.slow
        sm = getattr(s.ctx, "selfm", None)
        if sm is not None:                           # debate pick 1: the contingency self moves itself
            m = sm.mover()
            if m is not None:
                moves, blockers, passable = m
                moves = {a: d for a, d in moves.items() if a not in self.exclude}
                if moves:
                    self.passable = set(passable) - set(blockers)
                    return moves, set(blockers), (("self",), SELFGROUP)
            return None
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
        if group == SELFGROUP:
            f = agent.slow.ctx.selfm.frame(scene)
            return None if f is None else [scene.comps.comps[i - 1] for i in sorted(f.ids)]
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
        if self.cfg.handoff and not self.cfg.interrupt and self.dwell > 0:
            return None                               # the policy has the choice after a hand-off
        model = self.mover_model(agent)
        if model is None:
            self.plan = []
            return None
        buttons = [v for v in agent.valid if v in BUTTONS]
        if not self.plan and any(self.tries.get(b, 0) < self.cfg.min_tries for b in buttons):
            return None                               # let the policy finish trying every button
        if not self.plan:
            if self._peek[0] == agent.n_steps:        # debate four pick 1: the trip the agent's check already planned
                found, resumed, consumed = self._peek[1]
            else:
                found, resumed, consumed = self._find(agent, model)
            if consumed and self.resume_target is not None:   # the interrupted trip's target was tried first
                self.resume_target = None
                self.resumed += int(resumed)
            if found is None:
                return None
            self.plan, self.target = list(found[0]), found[1]
            self.trips += 1
        act, d = self.plan.pop(0)
        self.expect = (act, d)
        return Action(act)

    def _find(self, agent, model) -> tuple:
        """(the next trip (path, target) or None, whether it goes to the interrupted trip's target, whether a pending
        resume target was looked at (the self was found)). Pure: nothing on the explorer changes, so the agent can look
        at the trip before it starts (peek)."""
        moves, blockers, (ctl, group) = model
        scene = agent.perceiver.current
        sprite = self.sprite(agent, scene, ctl, group)
        if not sprite:
            return None, False, False
        untouched = [c for c in self.objects(scene, sprite) if (c.type_key, c.y0, c.x0) not in self.touched]
        resumed = False
        if self.resume_target is not None:            # debate three pick 1: the interrupted trip's target first
            same = [c for c in untouched if (c.type_key, c.y0, c.x0) == self.resume_target]
            if same:
                untouched, resumed = same, True
        if not untouched:
            return None, False, True
        walls = agent.slow.ctx.context(scene, Action(BUTTONS[0])).walls
        mv = {a: d for a, d in moves.items() if a in agent.valid}
        if self.cfg.search == "tl" and walls is None:
            from .tl import plan as tl_plan
            found = tl_plan.search(scene, sprite, mv, blockers, untouched, _on,
                                   lambda c: self.last_touch.get((c.type_key, c.y0, c.x0), -1))
        else:
            found = self.search(scene, sprite, mv, blockers, untouched, walls)
        return (None, resumed, True) if found is None else ((list(found[0]), found[1]), resumed, True)

    def peek(self, agent) -> Optional[tuple]:
        """Debate four pick 1: the trip (path, target) next_action would start on this board, or None; cached for this
        step so that next_action, if called, starts exactly this trip."""
        if self._peek[0] != agent.n_steps:
            model = self.mover_model(agent)
            buttons = [v for v in agent.valid if v in BUTTONS]
            ready = model is not None and all(self.tries.get(b, 0) >= self.cfg.min_tries for b in buttons)
            self._peek = (agent.n_steps, self._find(agent, model) if ready else (None, False, False))
        return self._peek[1][0]

    def observe(self, agent, action: Action, tr) -> None:
        self.tries[action.name] = self.tries.get(action.name, 0) + 1
        self._scored = bool(tr.scored)
        if tr.level_completed or tr.reset:
            self.reset_level()
            return
        ended_target = None
        acted, trip_end = self.expect is not None, None
        if self.expect is not None:
            act, (dy, dx) = self.expect
            ok = action.name == act and any((ddy, ddx) == (dy, dx) for _, ddy, ddx in tr.moves)
            if not ok and self.cfg.handoff and action.name == act:
                # with the contingency self the self's own displacement decides: a sprite redrawn on turning is
                # no single matched component move, and must not end the option as "blocked"
                sm = getattr(agent.slow.ctx, "selfm", None)
                ok = sm is not None and sm.last_delta == (dy, dx)
            if not ok:
                self.plan = []                        # the model was wrong here: replan next step
                trip_end = "blocked"
            elif not self.plan:
                trip_end = "end"
            if not self.plan:
                # the trip ended (arrived, or failed on the way): the target counts as touched either way.
                # Marked by key, because an object the sprite stands on is covered and cannot be seen.
                ended_target = self.target
            self.expect = None
        model = self.mover_model(agent)
        if model is None:
            if self.cfg.handoff and self.cfg.interrupt:
                self._check(agent, acted, trip_end, None, {})
            elif self.cfg.handoff:
                self._handoff(agent, acted, trip_end, None, {})
            return
        _, _, (ctl, group) = model
        scene = agent.perceiver.current
        sprite = self.sprite(agent, scene, ctl, group)
        if not sprite:
            if self.cfg.handoff and self.cfg.interrupt:
                self._check(agent, acted, trip_end, None, {})
            elif self.cfg.handoff:
                self._handoff(agent, acted, trip_end, None, {})
            return
        sb = _box(sprite)
        objs = {(c.type_key, c.y0, c.x0): (c.y0, c.x0, c.y1, c.x1) for c in self.objects(scene, sprite)}
        if self.cfg.handoff and self.cfg.interrupt:
            self._check(agent, acted, trip_end, sb, objs)
        elif self.cfg.handoff:
            self._handoff(agent, acted, trip_end, sb, objs)
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

    def _handoff(self, agent, acted: bool, trip_end: Optional[str], sb: Optional[tuple], objs: dict) -> None:
        """Stage one: end the trip on arrival / surprise and give the policy the next choices (see the header)."""
        adj = {k for k, b in objs.items() if _near(sb, b)} if sb is not None else set()
        if not acted and self.dwell > 0:              # a policy step inside the dwell
            self.dwell -= 1
            self.dwell_steps += 1
            if sb != self.dwell_box:                  # the self moved away: the next trip may start
                self.dwell = 0
        if acted:
            self.trip_steps += 1
            reason = trip_end
            if reason is None and self.plan:          # the trip goes on unless it arrived somewhere or was surprised
                new = {k for k in adj - (self.prev_adj or set()) if (k, sb) not in self.handed} if sb else set()
                sur = agent.last_surprise
                surprised = sur is not None and (sur.spike or sur.surprisal >= self.cfg.handoff_nats)
                if new or surprised:
                    reason = "arrival+surprise" if (new and surprised) else ("arrival" if new else "surprise")
                    self.handed |= {(k, sb) for k in new}
                    self.plan = []                    # the target is NOT marked touched: the trip was cut short
            if reason is not None:
                self.handoffs[reason] = self.handoffs.get(reason, 0) + 1
                self.dwell, self.dwell_box = self.cfg.dwell, sb
        self.prev_adj = adj

    # -- debate three pick 1: interrupting options
    def _relative_surprise(self, agent) -> bool:
        """The step's surprisal against this play's running mean / sd (updated after the test), or a spike."""
        sur = agent.last_surprise
        if sur is None or not getattr(self, "_scored", True):
            return False
        x = float(sur.surprisal)
        hit = bool(sur.spike)
        if self.sur_n >= self.cfg.min_sur_n:
            sd = math.sqrt(self.sur_m2 / (self.sur_n - 1)) if self.sur_n > 1 else 0.0
            hit = hit or (sd > 0 and (x - self.sur_mean) / sd >= self.cfg.z_surprise)
        self.sur_n += 1                              # Welford
        d = x - self.sur_mean
        self.sur_mean += d / self.sur_n
        self.sur_m2 += d * (x - self.sur_mean)
        return hit

    def _check(self, agent, acted: bool, trip_end: Optional[str], sb: Optional[tuple], objs: dict) -> None:
        """Raise an EFE check on arrival / relative surprise / blocked / trip end; the trip is NOT cut (the agent's
        _interrupt decides). After an interrupting action that moved the self, the trip re-plans to the same target."""
        adj = {k for k, b in objs.items() if _near(sb, b)} if sb is not None else set()
        surprised = self._relative_surprise(agent)
        if not acted and self.dwell > 0:              # an interrupting action was just taken
            self.dwell_steps += 1
            if self.plan and sb != self.dwell_box and self.target is not None:
                t = self.target                       # the path broke: same target, new path
                self.resume_target = (t.type_key, t.y0, t.x0)
                self.plan, self.target = [], None
        classes = set()
        if self.cfg.try_once:                         # debate four: colours never touched this play
            classes = {int(k[0][0]) for k in adj} - self.contact_classes
            self.contact_classes |= classes
        if acted:
            self.trip_steps += 1
            self.try_pending = False                  # a try-once the agent did not get to evaluate is not carried on
            reason = trip_end
            if reason is None and self.plan:
                new = {k for k in adj - (self.prev_adj or set()) if (k, sb) not in self.handed} if sb else set()
                if new or surprised:
                    reason = "arrival+surprise" if (new and surprised) else ("arrival" if new else "surprise")
                    self.handed |= {(k, sb) for k in new}
            if self.cfg.try_once and classes:         # debate four pick 1: first contact with a new kind of object
                self.try_pending = True
                self.new_classes += len(classes)
                reason = reason or "new_class"       # a contact the arrival test had already seen here
            if reason is not None:
                self.check, self.dwell, self.dwell_box = reason, 0, sb
                self.checks[reason] = self.checks.get(reason, 0) + 1
        self.prev_adj = adj

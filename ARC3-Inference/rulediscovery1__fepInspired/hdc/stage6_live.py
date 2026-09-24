# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Stage 6 of docs/plans/2026-09-24-hdc-ghost-roadmap.md: live play of Ghost Twin (g50t) on the exact
#   simulator with the rule-discovery agent plus what stages 2-5 established about the ghost. KISS version of
#   "plan switch -> rewind -> goal": the tape model says a ghost re-walks the previous run and then stays where
#   that run ended, so the agent can PARK a ghost on an object by walking there and rewinding, then explore
#   with the ghost holding it. Controller (on top of RuleDiscoveryAgent + ObjectContactExplorer + curiosity):
#     1. learn: the agent's own policy tries every button a few times; a button after which the player jumps
#        back to its level-start position is learned as the REWIND (perception only; stage-4 tracker idea).
#        From then on the explorer never uses it as a move and the policy may not press it on its own
#        (fixes the compulsive rewinding found in the Ghost Twin diagnosis).
#     2. park: walk (explorer search with the learned mover) onto the nearest object not yet used as a parking
#        spot, then press the rewind -> the ghost will re-walk this path and stay on that object.
#     3. explore: the normal agent + explorer trips, rewind blocked, for up to EXPLORE actions; then go back to
#        2 with the next parking spot. A level clear resets the parking list; a game over is answered with RESET.
#   Arms, 10 seeds x 500 actions each: plain agent (quarter prior), agent + explorer + curiosity, and this
#   parker. Reports levels, first-clear action, game overs, rewinds pressed. No game internals are read by the
#   agent (the controlled object, objects and moves all come from its perception and fitted rules).
#   After the first smoke run: parking spots tried are kept across a RESET of the same level (a reset used to
#   wipe them, so the same nearby icons were retried every life), explore phase 25 actions. Parking targets are
#   the solid PADS of objects (pads()): Ghost Twin's switch, wire and door are one same-colour component, so
#   "stand on the object" was satisfied at a corner of the wire's box, never on the switch. Walls for parking:
#   a colour blocked in >= 3 places and never walked onto (the rule fitter walls a colour after one bump).
#   Known open problem: on a one-ghost level every second rewind ERASES the ghost; the controller cannot yet
#   tell a ghost-making rewind from an erasing one.
#   Output results/hdc/stage6_live.json + .md.
# SRP/DRY check: Pass -- agent/explorer/curiosity/env are the package's; this file adds only the phase
#   controller and the rewind detector.
"""Stage 6: park-a-ghost controller, live on Ghost Twin."""
from __future__ import annotations

import json
import random
import time
from multiprocessing import get_context
from pathlib import Path

import numpy as np

from .. import _distill as D
from ..agent import AgentConfig, RuleDiscoveryAgent
from ..curiosity import CuriosityConfig, CuriosityDrive, load_encoder
from ..env import GameEnv
from ..explore import ObjectContactExplorer, _box
from ..perception import BUTTONS, RESET, Action

OUT = Path(__file__).resolve().parent.parent / "results" / "hdc"
GAME, BUILD = "g50t", "5849a774"
EXPLORE = 25
ONE_CELL = 8


def player_pos(agent, grid):
    """Top-left of the controlled type's single instance on this board (perception only)."""
    ctl = agent.slow.ctx.state.agency.tracker.controlled() if agent.slow else None
    if ctl is None:
        return None
    bc = D.oe.board_comps(grid, None)
    inst = [c for c in bc.comps if c.type_key == ctl]
    return (inst[0].y0, inst[0].x0) if len(inst) == 1 else None


class Pad:
    """A solid part of a component (see pads()). Same fields the explorer's search reads."""

    def __init__(self, comp, y0, x0, y1, x1):
        self.id, self.colour = comp.id, comp.colour
        self.y0, self.x0, self.y1, self.x1 = y0, x0, y1, x1
        self.type_key = (comp.colour, "pad", y1 - y0 + 1, x1 - x0 + 1)


def pads(scene, comps, size: int = 3) -> list:
    """Split sprawling components into their solid pads: cells that are the centre of a full size x size
    block of the component (a 3x3 erosion), grouped 4-connected, each grown back by the erosion radius.
    Thin wires vanish, so a switch pad joined to its door by a wire becomes its own target (Ghost Twin)."""
    lab = scene.comps.lab
    out = []
    r = size // 2
    for c in comps:
        if c.size <= size * size or (c.y1 - c.y0 < size and c.x1 - c.x0 < size):
            out.append(c)
            continue
        m = lab[c.y0:c.y1 + 1, c.x0:c.x1 + 1] == c.id
        core = np.zeros_like(m)
        for y in range(r, m.shape[0] - r):
            for x in range(r, m.shape[1] - r):
                core[y, x] = m[y - r:y + r + 1, x - r:x + r + 1].all()
        seen = np.zeros_like(core)
        for y, x in zip(*np.nonzero(core)):
            if seen[y, x]:
                continue
            stack, cells = [(y, x)], []
            seen[y, x] = True
            while stack:
                cy, cx = stack.pop()
                cells.append((cy, cx))
                for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                    if 0 <= ny < core.shape[0] and 0 <= nx < core.shape[1] and core[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            ys, xs = [q[0] for q in cells], [q[1] for q in cells]
            out.append(Pad(c, c.y0 + min(ys) - r, c.x0 + min(xs) - r, c.y0 + max(ys) + r, c.x0 + max(xs) + r))
    return out


class Parker:
    def __init__(self, agent: RuleDiscoveryAgent, explorer: ObjectContactExplorer):
        self.a, self.ex = agent, explorer
        self.rewind = None
        self.start = None
        self.phase = "learn"
        self.parked = set()
        self.plan = []
        self.explore_left = 0
        self.rewinds = 0
        self.blocked_at: dict = {}          # colour -> set of player positions where a move into it failed
        self.walked: set = set()            # colours the player has moved onto (never walls)

    def new_level(self, grid, cleared: bool = True):
        """cleared: a new level (forget the parking spots tried); False: a RESET of the same level (keep them,
        so the agent moves on to the next spot instead of retrying the first ones every life)."""
        self.start = None
        if cleared:
            self.parked = set()
        self.plan, self.phase = [], ("park" if self.rewind else "learn")
        self._arrived = False

    def act(self) -> Action:
        if self.phase == "park" and self.rewind:
            a = self.park_step()
            if a is not None:
                return a
            self.phase, self.explore_left = "explore", EXPLORE
        a = self.a.act()
        if self.rewind and a.name == self.rewind:
            a = Action(random.choice([b for b in self.a.valid if b in BUTTONS and b != self.rewind]))
        if self.phase == "explore":
            self.explore_left -= 1
            if self.explore_left <= 0:
                self.phase = "park"
        return a

    def park_step(self):
        if self.plan:
            act, _ = self.plan.pop(0)
            return Action(act)
        if self.plan == [] and getattr(self, "_arrived", False):
            self._arrived = False
            self.rewinds += 1
            self.phase, self.explore_left = "explore", EXPLORE
            return Action(self.rewind)
        model = self.ex.mover_model(self.a)
        if model is None:
            return None
        moves, blockers, (ctl, group) = model
        scene = self.a.perceiver.current
        sprite = self.ex.sprite(self.a, scene, ctl, group)
        if not sprite:
            return None
        objs = pads(scene, self.ex.objects(scene, sprite))
        cands = [c for c in objs if (c.type_key, c.y0, c.x0) not in self.parked]
        # a colour counts as wall for PARKING only after the player was blocked by it in >= 3 places (the rule
        # fitter generalises one bump by colour; in Ghost Twin the door and the wire along the corridor share a
        # colour, so one bump into the door walled off the corridor to the switch)
        walls = {c for c in blockers if len(self.blocked_at.get(c, ())) >= 3 and c not in self.walked}
        found = self.ex.search(scene, sprite, {k: v for k, v in moves.items() if k in self.a.valid},
                               walls, cands) if cands else None
        if found is None:
            return None
        path, target = found
        self.parked.add((target.type_key, target.y0, target.x0))
        self.plan = list(path)
        self._arrived = True
        act, _ = self.plan.pop(0)
        return Action(act)

    def observe(self, action: Action, grid, before, after):
        if self.start is None:
            self.start = before
        if action.name in BUTTONS and action.name != self.rewind and before is not None and after is not None \
                and before != after and max(abs(after[0] - before[0]), abs(after[1] - before[1])) <= ONE_CELL:
            g = np.asarray(grid)
            self.walked |= set(np.unique(g[after[0]:after[0] + 5, after[1]:after[1] + 5]).tolist())
        if action.name in BUTTONS and action.name != self.rewind and before is not None and before == after:
            model = self.ex.mover_model(self.a)
            if model and action.name in model[0]:
                dy, dx = model[0][action.name]
                g = np.asarray(grid)
                y0, x0 = before[0] + dy, before[1] + dx
                ahead = g[max(y0, 0):max(y0, 0) + 5, max(x0, 0):max(x0, 0) + 5]
                for c in set(np.unique(ahead).tolist()):
                    self.blocked_at.setdefault(c, set()).add(before)
        if self.rewind is None and before and after and self.start and after == self.start and before != self.start \
                and abs(after[0] - before[0]) + abs(after[1] - before[1]) > ONE_CELL and action.name != RESET:
            self.rewind = action.name
            self.ex.exclude.add(action.name)
            self.phase = "park"


def play(job) -> dict:
    arm, seed, budget = job
    random.seed(seed)
    env = GameEnv(GAME, BUILD)
    obs = env.reset()
    valid = lambda o: o.valid_actions + ["RESET"]  # noqa: E731
    ex = cd = None
    if arm in ("explorer", "parker"):
        ex = ObjectContactExplorer()
        cd = CuriosityDrive(load_encoder(), CuriosityConfig(temperature=1.0), seed=seed)
    agent = RuleDiscoveryAgent(AgentConfig(seed=seed, dl_weight=0.25), curiosity=cd, explorer=ex)
    agent.start_play(obs.grid, valid(obs), level=0)
    parker = Parker(agent, ex) if arm == "parker" else None
    clears, game_overs, rewinds_pressed = [], 0, 0
    t0 = time.time()
    for n in range(1, budget + 1):
        if obs.state == "GAME_OVER":
            a = Action(RESET)
            game_overs += 1
        else:
            a = parker.act() if parker else agent.act()
        before = player_pos(agent, obs.grid)
        level_before = obs.levels_completed
        obs = env.step(a)
        after = player_pos(agent, obs.grid)
        agent.observe(a, obs.grid, level_completed=obs.level_completed, game_over=obs.state == "GAME_OVER",
                      level=obs.levels_completed, valid_actions=valid(obs))
        rewinds_pressed += int(a.name == "ACTION5")
        if parker:
            if obs.levels_completed > level_before or a.name == RESET:
                parker.new_level(obs.grid, cleared=obs.levels_completed > level_before)
            else:
                parker.observe(a, obs.grid, before, after)
        if obs.level_completed:
            clears.append(n)
        if obs.state == "WIN":
            break
    return {"arm": arm, "seed": seed, "levels": obs.levels_completed, "clear_at": clears, "game_overs": game_overs,
            "rewind_presses": rewinds_pressed, "rewind_learned": parker.rewind if parker else None,
            "ghosts_parked": parker.rewinds if parker else None, "seconds": round(time.time() - t0, 1)}


def main(seeds: int = 10, budget: int = 500):
    OUT.mkdir(parents=True, exist_ok=True)
    load_encoder()
    jobs = [(arm, s, budget) for arm in ("agent", "explorer", "parker") for s in range(seeds)]
    with get_context("spawn").Pool(10) as pool:
        rows = pool.map(play, jobs)
    lines = ["| arm | levels (total) | plays clearing level 1 | first clear (median action) | game overs | rewind presses (mean) |",
             "|---|---|---|---|---|---|"]
    for arm in ("agent", "explorer", "parker"):
        rs = [r for r in rows if r["arm"] == arm]
        firsts = sorted(r["clear_at"][0] for r in rs if r["clear_at"])
        lines.append(f"| {arm} | {sum(r['levels'] for r in rs)} | {len(firsts)} | "
                     f"{firsts[len(firsts) // 2] if firsts else '-'} | {sum(r['game_overs'] for r in rs)} | "
                     f"{np.mean([r['rewind_presses'] for r in rs]):.1f} |")
    text = f"stage 6: Ghost Twin live, {seeds} seeds x {budget} actions (language model: level 1 in 10 of 30 recorded plays)\n" + "\n".join(lines)
    print(text)
    (OUT / "stage6_live.json").write_text(json.dumps(rows, indent=1))
    (OUT / "stage6_live.md").write_text(text + "\n")


if __name__ == "__main__":
    main()

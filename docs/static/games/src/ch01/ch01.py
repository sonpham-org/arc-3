# Author: GPT-6 Astra
# Date: 2026-09-28 17:20
# PURPOSE: Crankhouse's deterministic physical gear contacts, bridge state and ARC
# action adapter. The same transition drives real play, smoke solutions and blind
# policies; NumPy draws circular wheels and bounded mechanical animation.
# SRP/DRY check: Pass — inspected gearbox/cam games and existing ARC adapters;
# none provides visible equal-radius gear meshing. Physics is defined once here.
"""Click a wheel, then an axle. ACTION5 cranks clockwise; ACTION7 reverses."""

from collections import namedtuple, deque
from math import atan2, cos, sin, pi, hypot, isfinite

import numpy as np
from arcengine import ARCBaseGame, Camera, GameState, Level, RenderableUserDisplay

RADIUS, TRAVEL = 5, 4
WHITE, SILVER, GRAY, DARK, BLACK = 0, 1, 2, 4, 5
RED, BLUE, SKY, YELLOW, ORANGE, GREEN = 8, 9, 10, 11, 12, 14
PIER_PEGS = ((7, 16), (17, 16), (27, 16), (37, 16), (47, 16),
             (17, 26), (27, 26), (37, 26), (7, 26), (7, 36),
             (17, 36), (27, 36), (37, 36), (47, 36), (57, 36))
LEVELS = [
    dict(name="Missing wheel", pegs=((12, 21), (22, 21), (32, 21)),
         fixed=(0, 2), outputs=((2, 1, "bridge"),), supply=1, stone=(), tutorial=True),
    dict(name="Borrow at the island", pegs=PIER_PEGS, fixed=(0, 4, 9, 11, 14),
         outputs=((4, 1, "bridge"), (14, -1, "bridge"), (9, 1, "haul")),
         supply=5, stone=((27, 16, 6, 6),), spans=((22, 30), (48, 56)),
         cart_goal=29, continuous_bridges=True, tutorial=False),
    dict(name="Gate first", pegs=PIER_PEGS+((47, 26),), fixed=(0, 2, 4, 9, 11, 14),
         outputs=((4, 1, "bridge"), (14, -1, "bridge"), (9, 1, "haul"), (2, -1, "gate")),
         supply=5, stone=((37, 16, 6, 6),), spans=((22, 30), (48, 56)),
         cart_goal=29, continuous_bridges=True, gate_x=42, tutorial=False),
]
State = namedtuple("State", "mask held angles progress caught cart alive done pulse feedback pointer")


def initial(level):
    return State(sum(1 << index for index in level["fixed"]), False,
                 (0,) * len(level["pegs"]), (0,) * len(level["outputs"]),
                 (False,) * len(level["outputs"]), 0, True, False, 0, "ready", (12, 21))


def loose_count(level, state):
    return state.mask.bit_count() - len(level["fixed"])


def rack_count(level, state):
    return level["supply"] - loose_count(level, state) - int(state.held)


def contacts(level, mask):
    """Compute contacts from pitch-circle geometry, never a hidden edge list."""
    graph = {index: [] for index in range(len(level["pegs"])) if mask & (1 << index)}
    for first in graph:
        for second in graph:
            if first < second and abs(hypot(
                    level["pegs"][first][0]-level["pegs"][second][0],
                    level["pegs"][first][1]-level["pegs"][second][1])-2*RADIUS) < .001:
                graph[first].append(second)
                graph[second].append(first)
    return graph


def drive(level, mask):
    graph = contacts(level, mask)
    signs, queue = {0: 1}, deque([0])
    while queue:
        first = queue.popleft()
        for second in graph[first]:
            expected = -signs[first]
            if second in signs and signs[second] != expected:
                return signs, True
            if second not in signs:
                signs[second] = expected
                queue.append(second)
    return signs, False


def fits(level, state, peg):
    x, y = level["pegs"][peg]
    if any(hypot(max(0, abs(x-sx)-width/2), max(0, abs(y-sy)-height/2)) < RADIUS+.65
           for sx, sy, width, height in level["stone"]):
        return False
    return all(index == peg or not state.mask & (1 << index)
               or hypot(x-other[0], y-other[1]) >= 2*RADIUS-.001
               for index, other in enumerate(level["pegs"]))


def settle(level, state):
    """An unlatched disconnected winch lets its counterweight raise the bridge."""
    signs, _ = drive(level, state.mask)
    progress = tuple(value if peg in signs or state.caught[index] else 0
                     for index, (peg, _, _) in enumerate(level["outputs"])
                     for value in (state.progress[index],))
    powered = any(kind == "haul" for _, _, kind in level["outputs"])
    bridge_values = [progress[index] for index, (_, _, kind) in enumerate(level["outputs"]) if kind == "bridge"]
    # Both cart wheels must have a road underneath. The bank/bridge coordinates
    # are shared with the displayed physical crossing, not an action countdown.
    wheels = (state.cart*2, state.cart*2+5)
    spans = level.get("spans", ((24, 44),))
    unsupported = any(left < wheel < right and value < TRAVEL
                      for (left, right), value in zip(spans, bridge_values) for wheel in wheels)
    gate_hit = powered and any(kind == "gate" and progress[index] < TRAVEL
                              and state.cart*2+5 >= level.get("gate_x", 53)-4
                              for index, (_, _, kind) in enumerate(level["outputs"]))
    alive = state.alive and not (powered and unsupported) and not gate_hit
    feedback = "water" if powered and unsupported else "gate" if gate_hit else state.feedback
    finished = all(value == TRAVEL for index, value in enumerate(progress)
                   if level["outputs"][index][2] != "haul" and
                   not (powered and level.get("continuous_bridges") and level["outputs"][index][2] == "bridge"))
    return state._replace(progress=progress, alive=alive, feedback=feedback,
                          done=alive and finished and (not powered or state.cart == level.get("cart_goal", 26)))


def click_at(level, state, point):
    x, y = point
    if not (0 <= x < 64 and 0 <= y < 64):
        return state._replace(feedback="miss")
    if y <= 10 and x >= 25:
        if state.held:
            return state._replace(held=False, feedback="returned")
        if rack_count(level, state):
            return state._replace(held=True, feedback="picked")
        return state._replace(feedback="empty")
    nearest = min(range(len(level["pegs"])),
                  key=lambda index: hypot(x-level["pegs"][index][0], y-level["pegs"][index][1]))
    if hypot(x-level["pegs"][nearest][0], y-level["pegs"][nearest][1]) > 6:
        return state._replace(feedback="miss")
    occupied = bool(state.mask & (1 << nearest))
    if nearest in level["fixed"]:
        return state._replace(feedback="fixed")
    if state.held and not occupied and fits(level, state, nearest):
        return settle(level, state._replace(mask=state.mask | (1 << nearest),
                                           held=False, feedback="placed"))
    if not state.held and occupied:
        return settle(level, state._replace(mask=state.mask & ~(1 << nearest),
                                           held=True, feedback="picked"))
    return state._replace(feedback="blocked")


def transition(level, state, action, point=None):
    if state.done or not state.alive:
        return state
    if action == 6 and point is not None and 1 <= point[0] < 22 and 1 <= point[1] < 10:
        action = 7 if point[0] < 11 else 5
    state = state._replace(pulse=1-state.pulse, feedback="refused")
    if action == 6 and point is not None:
        return click_at(level, state._replace(pointer=point), point)
    if action not in (5, 7):
        return state
    direction = 1 if action == 5 else -1
    signs, jammed = drive(level, state.mask)
    if jammed:
        return state._replace(feedback="jammed", pointer=level["pegs"][0])
    angles = tuple((value + direction*signs.get(index, 0)) % 24
                   for index, value in enumerate(state.angles))
    progress, caught, cart = list(state.progress), list(state.caught), state.cart
    powered = any(kind == "haul" for _, _, kind in level["outputs"])
    for index, (peg, winding, kind) in enumerate(level["outputs"]):
        if peg not in signs or caught[index]:
            continue
        if kind == "haul":
            cart = max(0, min(level.get("cart_goal", 26), cart+direction*signs[peg]*winding))
            continue
        progress[index] = max(0, min(TRAVEL, progress[index]+direction*signs[peg]*winding))
        if (kind == "gate" or powered and kind == "bridge" and not level.get("continuous_bridges")) and progress[index] == TRAVEL:
            caught[index] = True
    return settle(level, state._replace(angles=angles, progress=tuple(progress), caught=tuple(caught), cart=cart,
                                       feedback="turn", pointer=level["pegs"][0]))


def rect(frame, x, y, width, height, color):
    left, top = max(0, round(x)), max(0, round(y))
    right, bottom = min(64, round(x+width)), min(64, round(y+height))
    if left < right and top < bottom:
        frame[top:bottom, left:right] = color


def line(frame, start, end, color, thick=1):
    count = max(1, round(hypot(end[0]-start[0], end[1]-start[1])*2))
    for fraction in np.linspace(0, 1, count+1):
        x, y = start[0]+(end[0]-start[0])*fraction, start[1]+(end[1]-start[1])*fraction
        rect(frame, x, y, thick, thick, color)


def wheel(frame, center, angle, color=WHITE, radius=RADIUS):
    """Actual tooth profile around the same pitch circle used by contacts()."""
    cx, cy = center
    for y in range(max(0, int(cy-radius-2)), min(64, int(cy+radius+3))):
        for x in range(max(0, int(cx-radius-2)), min(64, int(cx+radius+3))):
            distance = hypot(x-cx, y-cy)
            bearing = atan2(y-cy, x-cx)-angle
            outer = radius + .85*cos(8*bearing)
            if distance <= outer:
                frame[y, x] = color if distance >= radius*.43 else DARK
    line(frame, (cx, cy), (cx+radius*.68*cos(angle), cy+radius*.68*sin(angle)), ORANGE)
    rect(frame, cx, cy, 1, 1, SILVER)


def tooth_phases(level, mask):
    """Seat teeth at every actual contact, including non-cardinal pentagon links."""
    graph, phases = contacts(level, mask), {}
    for root in graph:
        if root in phases:
            continue
        phases[root], queue = 0.0, deque([root])
        while queue:
            first = queue.popleft()
            x, y = level["pegs"][first]
            for second in graph[first]:
                if second not in phases:
                    nx, ny = level["pegs"][second]
                    phases[second] = (2*atan2(ny-y, nx-x)-phases[first]-pi/8) % (pi/4)
                    queue.append(second)
    return phases


def arc_button(frame, center, clockwise, lit=False):
    cx, cy = center
    rect(frame, cx-4, cy-3, 9, 7, BLUE if lit else DARK)
    angles = np.linspace(-pi*.7, pi*.65, 15)
    for angle in angles:
        rect(frame, cx+3*cos(angle), cy+2*sin(angle), 1, 1, WHITE)
    end = angles[-1] if clockwise else angles[0]
    x, y = cx+3*cos(end), cy+2*sin(end)
    rect(frame, x-1, y, 3, 1, ORANGE)
    rect(frame, x, y-1 if clockwise else y+1, 1, 2, ORANGE)


class CrankhouseDisplay(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    def render_interface(self, frame):
        game, level, state = self.game, self.game.lvl, self.game.st
        animation = game.animation
        before = animation["before"] if animation else state
        fraction = min(1, animation["index"]/8) if animation else 1
        powered = any(kind == "haul" for _, _, kind in level["outputs"])
        bank = 24 if powered else 20
        frame[:, :] = SKY
        rect(frame, 0, 0, 64, 33, DARK)
        rect(frame, 1, 11, 62, 31, DARK)
        line(frame, (1, 41), (62, 41), GRAY)
        for sx, sy, width, height in level["stone"]:
            rect(frame, sx-width/2, sy-height/2, width, height, GRAY)
            line(frame, (sx-width/2, sy), (sx+width/2-1, sy), SILVER)
        # Shelf stock is drawn as real wheels; a held wheel sits above the machine.
        rect(frame, 27, 10, 35, 1, SILVER)
        for index in range(rack_count(level, state)):
            wheel(frame, (30+index*6, 6), 0, SILVER, 2.5)
        if state.held:
            wheel(frame, (24, 6), 0, YELLOW, 2.5)
        phases = tooth_phases(level, state.mask)
        for index, (x, y) in enumerate(level["pegs"]):
            if state.mask & (1 << index):
                steps = (state.angles[index]-before.angles[index]+12) % 24-12
                angle = (before.angles[index]+steps*fraction)*pi/12
                wheel(frame, (x, y), angle+phases[index], ORANGE if index == 0 else WHITE)
                if index in level["fixed"]:
                    rect(frame, x-1, y-1, 3, 3, GRAY)
            else:
                rect(frame, x-1, y-1, 3, 3, SILVER)
                rect(frame, x, y, 1, 1, BLACK)
        # A hand crank is visibly attached to the input shaft.
        ix, iy = level["pegs"][0]
        a = (before.angles[0]+((state.angles[0]-before.angles[0]+12) % 24-12)*fraction)*pi/12
        handle = (ix+3*cos(a), iy+3*sin(a))
        line(frame, (ix, iy), handle, BLACK)
        rect(frame, handle[0]-1, handle[1]-1, 3, 3, ORANGE)
        arc_button(frame, (6, 6), False)
        arc_button(frame, (16, 6), True)
        rect(frame, bank, 56, 44-bank, 8, BLUE)
        for ripple in (22, 31, 39):
            line(frame, (ripple, 60), (ripple+3, 60), SKY)
        rect(frame, 0, 55, bank, 9, GRAY)
        rect(frame, 44, 55, 20, 9, GRAY)
        line(frame, (0, 55), (bank-1, 55), WHITE)
        line(frame, (44, 55), (63, 55), WHITE)
        if powered:
            rect(frame, 0, 55, 64, 9, GRAY)
            line(frame, (0, 55), (63, 55), WHITE)
            for left, right in level.get("spans", ((24, 44),)):
                rect(frame, left+1, 55, right-left-1, 9, BLUE)
                line(frame, (left+3, 60), (right-3, 60), SKY)
        bridge_outputs = [index for index, output in enumerate(level["outputs"]) if output[2] == "bridge"]
        for index, (peg, _, kind) in enumerate(level["outputs"]):
            value = before.progress[index]+(state.progress[index]-before.progress[index])*fraction
            gx, gy = level["pegs"][peg]
            line(frame, (gx, gy+6), (gx, 34), SILVER)
            if kind == "gate":
                gate_x = level.get("gate_x", 53)
                top = 43-value*2
                rect(frame, gate_x-5, 39, 1, 17, DARK)
                rect(frame, gate_x+5, 39, 1, 17, DARK)
                for bar in range(4):
                    rect(frame, gate_x-4+bar*2, top, 1, 12, BLACK)
                line(frame, (gate_x-5, top), (gate_x+5, top), ORANGE)
                # A visible pawl swings into the raised gate's notch at the end.
                pawl = min(1, max(0, (value-3)*2))
                line(frame, (gate_x+6, 36), (gate_x+6-3*pawl, 39), GREEN if state.caught[index] else ORANGE, 2)
                line(frame, (gx, 34), (gate_x, 34), SILVER)
                line(frame, (gate_x, 34), (gate_x, top), SILVER)
            elif kind == "bridge":
                right = len(bridge_outputs) == 2 and index == bridge_outputs[-1]
                hinge = (44, 55) if right else (bank, 55)
                length = (44-bank)/2 if len(bridge_outputs) == 2 else 44-bank
                if powered:
                    left_bank, right_bank = level.get("spans", ((24, 44),))[bridge_outputs.index(index)]
                    hinge, length = ((right_bank if right else left_bank), 55), right_bank-left_bank
                angle = -pi/4*(1-value/TRAVEL)
                end = (hinge[0]+(-1 if right else 1)*length*cos(angle), hinge[1]+length*sin(angle))
                line(frame, hinge, end, ORANGE, 2)
                # Planks and a raised handrail distinguish the bridge from its chain.
                line(frame, (hinge[0], hinge[1]-4), (end[0], end[1]-4), ORANGE)
                for distance in np.linspace(0, 1, 5):
                    bx = hinge[0]+(end[0]-hinge[0])*distance
                    by = hinge[1]+(end[1]-hinge[1])*distance
                    line(frame, (bx, by-4), (bx, by), ORANGE)
                line(frame, (gx, 34), (hinge[0], 34), SILVER)
                line(frame, (hinge[0], 34), end, SILVER)
                rect(frame, gx-2, 32, 5, 5, SILVER)
                rect(frame, gx-1, 33, 3, 3, BLACK)
                if powered and not level.get("continuous_bridges"):
                    # The caught pawl is attached to this drum, not a detached status lamp.
                    line(frame, (gx+3, 30), (gx+1, 34), GREEN if state.caught[index] else ORANGE)
                line(frame, (hinge[0], 34), (hinge[0], 55), GRAY)
                # The counterweight rises as the bridge lowers; losing drive lets it fall.
                weight_x = 3 if not right else 59
                line(frame, (gx, 34), (weight_x+1, 34), SILVER)
                line(frame, (weight_x+1, 34), (weight_x+1, 53-value*2), SILVER)
                rect(frame, weight_x, 51-value*2, 4, 4, DARK)
            else:
                # The lower haul drum pulls the cart along the road; no input timer moves it.
                cart_position = before.cart+(state.cart-before.cart)*fraction
                rect(frame, gx-3, 40, 7, 4, ORANGE)
                rect(frame, gx-1, 40, 3, 4, BLACK)
                line(frame, (gx, gy+5), (gx, 43), SILVER)
                line(frame, (gx, 43), (55, 43), GRAY)
                line(frame, (55, 43), (55, 50), GRAY)
                line(frame, (55, 50), (cart_position*2+6, 50), GRAY)
        # Receiving shed and open doorway make the far bank an explicit destination.
        rect(frame, 58, 47, 6, 8, ORANGE)
        rect(frame, 59, 49, 4, 6, DARK)
        line(frame, (56, 47), (61, 43), WHITE)
        line(frame, (61, 43), (63, 47), WHITE)
        crossing = (max(0, animation["index"]-8)/12 if animation else 1) if state.done else 0
        cart_x = (before.cart+(state.cart-before.cart)*fraction)*2 if powered else 8+42*min(1, crossing)
        drop = 10*fraction if not state.alive and state.feedback == "water" else 0
        rect(frame, cart_x, 49+drop, 7, 4, RED)
        rect(frame, cart_x+1, 47+drop, 4, 2, WHITE)
        rect(frame, cart_x, 53+drop, 2, 2, BLACK)
        rect(frame, cart_x+5, 53+drop, 2, 2, BLACK)
        if not state.alive and state.feedback == "gate":
            line(frame, (cart_x+7, 47), (cart_x+9, 52), YELLOW, 2)
            line(frame, (cart_x+7, 52), (cart_x+10, 47), YELLOW)
        if state.feedback not in ("ready", "turn"):
            x, y = state.pointer
            color = YELLOW if state.feedback in ("picked", "placed", "returned") else RED
            line(frame, (x-3-state.pulse, y-4), (x+3+state.pulse, y-4), color)
        return frame


class Ch01(ARCBaseGame):
    def __init__(self):
        self.lvl, self.st = LEVELS[0], initial(LEVELS[0])
        self.animation = None
        self.display = CrankhouseDisplay(self)
        levels = [Level(sprites=[], grid_size=(64, 64), data={}, name=level["name"])
                  for level in LEVELS]
        super().__init__("ch01", levels, Camera(0, 0, 64, 64, SKY, SKY, [self.display]),
                         False, len(levels), [5, 6, 7])

    def on_set_level(self, level):
        self.lvl, self.st = LEVELS[self.level_index], initial(LEVELS[self.level_index])
        self.animation = None

    def handle_reset(self):
        if self._state in (GameState.NOT_PLAYED, GameState.WIN):
            self.full_reset()
        else:
            self.level_reset()

    def finish_action(self):
        self.animation = None
        if not self.st.alive:
            self.lose()
        elif self.st.done:
            self.next_level()
        self.complete_action()

    def step(self):
        if self.action.id.value == 0:
            self.complete_action()
            return
        if self.animation is not None:
            self.animation["index"] += 1
            limit = 22 if self.st.done else 9
            if self.animation["index"] >= limit:
                self.finish_action()
            return
        point = None
        if self.action.id.value == 6:
            data = self.action.data or {}
            x, y = data.get("x"), data.get("y")
            if all(isinstance(value, (int, float)) and isfinite(value) for value in (x, y)):
                point = (int(x), int(y))
        before = self.st
        self.st = transition(self.lvl, before, self.action.id.value, point)
        if (self.st.angles != before.angles or self.st.progress != before.progress
                or self.st.cart != before.cart or self.st.alive != before.alive):
            self.animation = {"before": before, "index": 0}
            return
        self.finish_action()

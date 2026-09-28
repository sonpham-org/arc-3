# Author: GPT-6 Astra
# Date: 2026-09-28 20:48
# PURPOSE: Crankhouse's deterministic physical gear contacts, bridge state and ARC
# action adapter. The same transition drives real play, smoke solutions and blind
# policies; NumPy draws recessed steel gears above rear shafts, distinct winches,
# a loaded cart and bounded mechanical motion on the native 64-pixel canvas.
# SRP/DRY check: Pass — inspected gearbox/cam games and existing ARC adapters;
# none provides visible equal-radius gear meshing. Physics is defined once here.
"""Click a wheel, then an axle. ACTION5 cranks clockwise; ACTION7 reverses."""

from collections import namedtuple, deque
from math import atan2, cos, sin, pi, hypot, isfinite

import numpy as np
from arcengine import ARCBaseGame, Camera, GameState, Level, RenderableUserDisplay

RADIUS, TRAVEL = 5, 4
WHITE, SILVER, GRAY, MID, DARK, BLACK = 0, 1, 2, 3, 4, 5
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


def wheel(frame, center, angle, color=SILVER, radius=RADIUS):
    """Actual tooth profile around the same pitch circle used by contacts()."""
    cx, cy = center
    for y in range(max(0, int(cy-radius-2)), min(64, int(cy+radius+3))):
        for x in range(max(0, int(cx-radius-2)), min(64, int(cx+radius+3))):
            distance = hypot(x-cx, y-cy)
            bearing = atan2(y-cy, x-cx)-angle
            outer = radius + .85*cos(8*bearing)
            if distance <= outer:
                frame[y, x] = color if distance >= radius*.60 else DARK
    for spoke in (angle, angle+pi/2, angle+pi, angle+3*pi/2):
        line(frame, (cx, cy), (cx+radius*.68*cos(spoke), cy+radius*.68*sin(spoke)), GRAY)
    line(frame, (cx, cy), (cx+radius*.68*cos(angle), cy+radius*.68*sin(angle)), WHITE)
    rect(frame, cx, cy, 1, 1, DARK)


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


def machine_wheels(frame, level, state, before, fraction):
    """Opaque working wheels sit in front of the rear shafts and supports."""
    phases = tooth_phases(level, state.mask)
    outputs = {peg for peg, _, _ in level["outputs"]}
    for index, (x, y) in enumerate(level["pegs"]):
        if not state.mask & (1 << index):
            rect(frame, x-1, y-1, 3, 3, MID)
            rect(frame, x, y, 1, 1, SILVER)
            continue
        steps = (state.angles[index]-before.angles[index]+12) % 24-12
        angle = (before.angles[index]+steps*fraction)*pi/12
        wheel(frame, (x, y), angle+phases[index], ORANGE if index == 0 else SILVER)
        if index in outputs:
            # Flanges and a rotating winding mark identify a coaxial winch.
            rect(frame, x-2, y-2, 1, 5, ORANGE)
            rect(frame, x+2, y-2, 1, 5, ORANGE)
            rect(frame, x-1, y-1, 3, 3, DARK)
            line(frame, (x, y), (x+cos(angle), y+sin(angle)), WHITE)
        elif index in level["fixed"]:
            rect(frame, x-1, y-1, 3, 3, MID)
            rect(frame, x, y, 1, 1, WHITE)
        else:
            rect(frame, x-1, y-1, 3, 3, BLACK)
            rect(frame, x, y, 1, 1, SILVER)
    # A real crank arm and dark hand grip stand apart from the toothed rim.
    x, y = level["pegs"][0]
    steps = (state.angles[0]-before.angles[0]+12) % 24-12
    angle = (before.angles[0]+steps*fraction)*pi/12
    handle = (x+3*cos(angle), y+3*sin(angle))
    line(frame, (x, y), handle, WHITE)
    rect(frame, handle[0]-1, handle[1]-1, 3, 3, BLACK)
    rect(frame, handle[0], handle[1], 1, 1, ORANGE)


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
        line(frame, (1, 42), (62, 42), MID)
        for sx, sy, width, height in level["stone"]:
            rect(frame, sx-width/2, sy-height/2, width, height, GRAY)
            line(frame, (sx-width/2, sy), (sx+width/2-1, sy), MID)
        # Shelf stock is drawn as real wheels; a held wheel sits above the machine.
        rect(frame, 27, 10, 35, 1, MID)
        for index in range(rack_count(level, state)):
            wheel(frame, (30+index*6, 6), 0, SILVER, 2.5)
        if state.held:
            wheel(frame, (24, 6), 0, YELLOW, 2.5)
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
            # Rear shafts leave the actual output axle. Working wheels are
            # rendered above them so crossing a shaft never hides an axle.
            lane = 45 if kind == "haul" else 43
            line(frame, (gx, gy+6), (gx, lane), MID)
            if kind == "gate":
                gate_x = level.get("gate_x", 53)
                top = 43-value*2
                rect(frame, gate_x-5, 39, 1, 17, MID)
                rect(frame, gate_x+5, 39, 1, 17, MID)
                for bar in range(4):
                    rect(frame, gate_x-4+bar*2, top, 1, 12, BLACK)
                line(frame, (gate_x-5, top), (gate_x+5, top), ORANGE)
                # A visible pawl swings into the raised gate's notch at the end.
                pawl = min(1, max(0, (value-3)*2))
                caught = state.caught[index] and value >= TRAVEL
                line(frame, (gate_x+6, 36), (gate_x+6-3*pawl, 39), GREEN if caught else ORANGE, 2)
                line(frame, (gx, 34), (gate_x, 34), MID)
                line(frame, (gate_x, 34), (gate_x, top), DARK)
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
                line(frame, (gx, lane), (hinge[0], lane), MID)
                line(frame, (hinge[0], lane), end, DARK)
                if powered and not level.get("continuous_bridges"):
                    # The caught pawl is attached to this drum, not a detached status lamp.
                    line(frame, (gx+3, 30), (gx+1, 34), GREEN if state.caught[index] else ORANGE)
                line(frame, (hinge[0], lane), (hinge[0], 55), GRAY)
                # The counterweight rises as the bridge lowers; losing drive lets it fall.
                weight_x = 3 if not right else 59
                line(frame, (gx, lane), (weight_x+1, lane), MID)
                line(frame, (weight_x+1, lane), (weight_x+1, 53-value*2), DARK)
                rect(frame, weight_x, 51-value*2, 4, 4, DARK)
                rect(frame, weight_x+1, 52-value*2, 2, 2, GRAY)
            else:
                # The lower haul drum pulls the cart along the road; no input timer moves it.
                cart_position = before.cart+(state.cart-before.cart)*fraction
                line(frame, (gx, lane), (55, lane), MID)
                line(frame, (55, lane), (55, 51), DARK)
                line(frame, (55, 51), (cart_position*2+6, 51), DARK)
        machine_wheels(frame, level, state, before, fraction)
        # Receiving shed and open doorway make the far bank an explicit destination.
        rect(frame, 57, 45, 7, 10, ORANGE)
        rect(frame, 58, 46, 6, 9, DARK)
        line(frame, (55, 46), (60, 42), RED)
        line(frame, (60, 42), (63, 45), RED)
        line(frame, (58, 55), (63, 55), ORANGE)
        crossing = (max(0, animation["index"]-8)/12 if animation else 1) if state.done else 0
        cart_x = (before.cart+(state.cart-before.cart)*fraction)*2 if powered else 8+42*min(1, crossing)
        drop = 10*fraction if not state.alive and state.feedback == "water" else 0
        rect(frame, cart_x, 49+drop, 7, 1, DARK)
        rect(frame, cart_x, 50+drop, 7, 3, RED)
        rect(frame, cart_x+1, 45+drop, 4, 4, ORANGE)
        line(frame, (cart_x+1, 45+drop), (cart_x+4, 48+drop), DARK)
        rect(frame, cart_x, 53+drop, 2, 2, BLACK)
        rect(frame, cart_x+5, 53+drop, 2, 2, BLACK)
        rect(frame, cart_x, 53+drop, 1, 1, SILVER)
        rect(frame, cart_x+5, 53+drop, 1, 1, SILVER)
        if not state.alive and state.feedback == "gate":
            line(frame, (cart_x+7, 47), (cart_x+9, 52), YELLOW, 2)
            line(frame, (cart_x+7, 52), (cart_x+10, 47), YELLOW)
        if state.feedback not in ("ready", "turn"):
            x, y = state.pointer
            # Keep edge-click feedback visible without changing the hit point.
            x, y = max(4, min(59, x)), max(4, min(63, y))
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

# Author: GPT-6 Astra
# Date: 2026-09-28 11:35
# PURPOSE: Switchyard is a deterministic click-controlled rail shunting game.
# Fixed turnout pairs guide rigid coupled chains; releasing a joint leaves cars
# parked while the locomotive changes approach. One pure transition drives tests.
# SRP/DRY check: Pass — inspected Graft and Conveyor Frame; neither supplies
# reversible rolling-stock chains on fixed turnout tracks. ARC handles frames.

from collections import namedtuple
from math import isfinite

import numpy as np
from arcengine import ARCBaseGame, Camera, GameState, Level, RenderableUserDisplay

WHITE, CREAM, GRAY, MID, DARK, BLACK = 0, 1, 2, 3, 4, 5
RED, BLUE, SKY, ORANGE, GREEN = 8, 9, 10, 12, 14
NODES = tuple((x, 5) for x in range(1, 12)) + (
    (3, 4), (3, 3), (3, 2), (4, 2), (5, 2), (6, 2), (7, 2),
    (8, 2), (9, 2), (9, 3), (9, 4))
EDGES = tuple((node, node + 1) for node in range(10)) + tuple(zip((2,) + tuple(range(11, 22)), tuple(range(11, 22)) + (8,)))
SWITCHES = ((2, 1, 3, 11), (8, 9, 7, 21))
NEIGHBORS = tuple(tuple(other for edge in EDGES if node in edge for other in edge if other != node)
                  for node in range(len(NODES)))
LEVELS = (
    {"name": "Park one wagon", "positions": (3, 4), "back": 2,
     "links": ((0, 1),), "switches": (0, 0), "goals": (6,), "shed": 3},
    {"name": "Change ends", "positions": (1, 3, 4, 5), "back": 0,
     "links": ((1, 2), (2, 3)), "switches": (0, 0), "goals": (0, 10, 16), "shed": 5},
    {"name": "Temporary storage", "positions": (9, 7, 14, 3), "back": 10,
     "links": (), "switches": (0, 1), "goals": (16, 0, 10), "shed": 5},
)
State = namedtuple("State", "positions back links switches won")


def initial(level):
    data = LEVELS[level]
    return State(data["positions"], data["back"], frozenset(data["links"]), data["switches"], False)


def rail_neighbors(state, node):
    for index, (junction, stem, straight, curved) in enumerate(SWITCHES):
        branch = curved if state.switches[index] else straight
        if node == junction:
            return (stem, branch)
    return tuple(other for other in NEIGHBORS[node] if all(
        other != junction or node in (stem, curved if state.switches[index] else straight)
        for index, (junction, stem, straight, curved) in enumerate(SWITCHES)))


def onward(state, node, previous):
    neighbors = rail_neighbors(state, node)
    if previous is not None and previous not in neighbors:
        return None
    remaining = tuple(other for other in neighbors if other != previous)
    return remaining[0] if len(remaining) == 1 else None


def linked(state, vehicle):
    return tuple(other for pair in state.links if vehicle in pair for other in pair if other != vehicle)


def chain(state, first):
    previous, current, output = 0, first, []
    while current is not None:
        output.append(current)
        following = tuple(other for other in linked(state, current) if other != previous)
        previous, current = current, following[0] if following else None
    return output


def drive(state, direction):
    engine = state.positions[0]
    front = onward(state, engine, state.back)
    destination = front if direction == 1 else state.back
    if destination is None or destination not in rail_neighbors(state, engine):
        return state
    attached = linked(state, 0)
    leading_first = next((other for other in attached if state.positions[other] == destination), None)
    trailing_first = next((other for other in attached if other != leading_first), None)
    leading = chain(state, leading_first) if leading_first is not None else []
    trailing = chain(state, trailing_first) if trailing_first is not None else []
    positions = list(state.positions)
    if leading:
        before = engine if len(leading) == 1 else state.positions[leading[-2]]
        advance = onward(state, state.positions[leading[-1]], before)
        if advance is None:
            return state
        for index, vehicle in enumerate(leading):
            positions[vehicle] = advance if index == len(leading) - 1 else state.positions[leading[index + 1]]
    for index, vehicle in enumerate(trailing):
        positions[vehicle] = engine if index == 0 else state.positions[trailing[index - 1]]
    positions[0] = destination
    if len(set(positions)) != len(positions):
        return state
    back = engine if direction == 1 else onward(state, destination, engine)
    return state._replace(positions=tuple(positions), back=back)


def coupling_pairs(state):
    return tuple((first, second) for first in range(len(state.positions))
                 for second in range(first + 1, len(state.positions))
                 if state.positions[second] in rail_neighbors(state, state.positions[first]))


def transition(level, state, command):
    if state.won:
        return state
    kind = command[0]
    after = state
    if kind == "drive":
        after = drive(state, command[1])
    elif kind == "switch" and command[1] in (0, 1):
        index = command[1]
        if SWITCHES[index][0] not in state.positions:
            switches = list(state.switches)
            switches[index] ^= 1
            after = state._replace(switches=tuple(switches))
    elif kind == "couple":
        pair = tuple(sorted(command[1:]))
        if pair in state.links:
            after = state._replace(links=state.links - {pair})
        elif pair in coupling_pairs(state) and all(len(linked(state, car)) < 2 for car in pair):
            # Adjacent trains may join only at their ends, never into a loop.
            pending, seen = [pair[0]], set()
            while pending:
                current = pending.pop()
                if current not in seen:
                    seen.add(current)
                    pending.extend(linked(state, current))
            if pair[1] not in seen:
                after = state._replace(links=state.links | {pair})
    data = LEVELS[level]
    return after._replace(won=after.positions[0] == data["shed"] and after.positions[1:] == data["goals"])


def point(node):
    x, y = NODES[node]
    return 2 + x * 5, 1 + y * 7


def switch_point(index):
    x, y = point(SWITCHES[index][0])
    return x + (-5 if index == 0 else 5), y + 6


def coupling_point(state, pair):
    first, second = (point(state.positions[vehicle]) for vehicle in pair)
    x, y = round((first[0] + second[0]) / 2), round((first[1] + second[1]) / 2)
    return (x, y - 4) if first[1] == second[1] else (x - 4, y)


def controls(state):
    output = [(('drive', 1), (15, 55)), (('drive', -1), (48, 55))]
    output += [(('switch', index), switch_point(index)) for index in range(2)]
    output += [(('couple', *pair), coupling_point(state, pair)) for pair in coupling_pairs(state)]
    return output


def command_at(state, x, y):
    if not all(isinstance(value, (int, float)) and isfinite(value) for value in (x, y)):
        return ('invalid',)
    if 48 <= y <= 62:
        if 3 <= x <= 28:
            return ('drive', 1)
        if 35 <= x <= 60:
            return ('drive', -1)
    candidates = [(abs(px - x) + abs(py - y), command) for command, (px, py) in controls(state)[2:]
                  if abs(px - x) <= 2 and abs(py - y) <= 2]
    return min(candidates)[1] if candidates else ('invalid',)


def rect(frame, x, y, width, height, color):
    left, top = max(0, round(x)), max(0, round(y))
    right, bottom = min(64, round(x + width)), min(64, round(y + height))
    if left < right and top < bottom:
        frame[top:bottom, left:right] = color


def line(frame, first, second, color):
    steps = max(abs(second[0] - first[0]), abs(second[1] - first[1]), 1)
    for step in range(steps + 1):
        rect(frame, first[0] + (second[0] - first[0]) * step / steps,
             first[1] + (second[1] - first[1]) * step / steps, 1, 1, color)


def cargo(frame, vehicle, x, y, color=None):
    color = (ORANGE, BLUE, GREEN)[vehicle - 1] if color is None else color
    if vehicle == 1:
        rect(frame, x - 2, y - 2, 5, 1, color)
        rect(frame, x - 2, y, 5, 1, color)
        rect(frame, x - 2, y + 2, 5, 1, color)
    elif vehicle == 2:
        rect(frame, x - 1, y - 2, 3, 5, color)
        rect(frame, x - 2, y - 1, 5, 3, color)
        rect(frame, x - 1, y, 3, 1, DARK)
    else:
        rect(frame, x - 2, y - 2, 5, 5, color)
        rect(frame, x - 1, y - 1, 3, 3, DARK)
        rect(frame, x, y - 1, 1, 3, color)


class YardDisplay(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    def render_interface(self, frame):
        game, state = self.game, self.game.st
        frame[:, :] = CREAM
        rect(frame, 0, 47, 64, 17, DARK)
        for first, second in EDGES:
            start, end = point(first), point(second)
            active = second in rail_neighbors(state, first)
            line(frame, start, end, BLACK if active else GRAY)
            if start[1] == end[1]:
                line(frame, (start[0], start[1] - 2), (end[0], end[1] - 2), DARK if active else GRAY)
                for x in range(min(start[0], end[0]), max(start[0], end[0]) + 1, 3):
                    rect(frame, x, start[1] - 3, 1, 5, GRAY)
            else:
                line(frame, (start[0] - 2, start[1]), (end[0] - 2, end[1]), DARK if active else GRAY)
        for vehicle, node in enumerate(LEVELS[game.level_index]['goals'], 1):
            x, y = point(node)
            rect(frame, x - 4, y - 11, 9, 8, GRAY)
            rect(frame, x - 3, y - 10, 7, 6, WHITE)
            cargo(frame, vehicle, x, y - 7)
            rect(frame, x - 3, y - 3, 7, 1, ORANGE)
        shed_x, shed_y = point(LEVELS[game.level_index]['shed'])
        # The locomotive parks ON the rails inside a pass-through engine shed.
        rect(frame, shed_x - 4, shed_y - 5, 9, 9, MID)
        rect(frame, shed_x - 3, shed_y - 4, 7, 8, BLACK)
        line(frame, (shed_x - 5, shed_y - 5), (shed_x, shed_y - 8), RED)
        line(frame, (shed_x, shed_y - 8), (shed_x + 5, shed_y - 5), RED)
        line(frame, (shed_x - 4, shed_y), (shed_x + 4, shed_y), GRAY)
        line(frame, (shed_x - 4, shed_y - 2), (shed_x + 4, shed_y - 2), GRAY)
        for index in range(2):
            x, y = switch_point(index)
            rect(frame, x - 2, y + 1, 5, 2, DARK)
            line(frame, (x, y + 1), (x + (2 if state.switches[index] else -2), y - 2), BLACK)
            rect(frame, x + (1 if state.switches[index] else -3), y - 3, 3, 3, RED)
        for vehicle, node in enumerate(state.positions):
            x, y = point(node)
            if game.animation is not None:
                end_x, end_y = point(game.animation['after'].positions[vehicle])
                amount = game.animation['frame'] / 9
                x, y = x + (end_x - x) * amount, y + (end_y - y) * amount
            rect(frame, x - 2, y + 2, 1, 1, BLACK)
            rect(frame, x + 2, y + 2, 1, 1, BLACK)
            if vehicle:
                cargo(frame, vehicle, x, y)
            else:
                rect(frame, x - 2, y - 2, 5, 4, RED)
                rect(frame, x - 1, y - 1, 2, 2, SKY)
                forward = onward(state, node, state.back)
                target = point(forward) if forward is not None else (x + 5, y)
                dx, dy = np.sign(target[0] - x), np.sign(target[1] - y)
                rect(frame, x + 2 * dx, y + 2 * dy, 1, 1, WHITE)
        if game.animation is None:
            for pair in coupling_pairs(state):
                x, y = coupling_point(state, pair)
                first, second = (point(state.positions[vehicle]) for vehicle in pair)
                middle = (round((first[0] + second[0]) / 2), round((first[1] + second[1]) / 2))
                line(frame, (x, y), middle, BLACK)
                rect(frame, x - 2, y - 2, 5, 5, BLACK)
                rect(frame, x - 1, y - 1, 3, 3, ORANGE if pair in state.links else WHITE)
                rect(frame, x, y, 1, 1, BLACK)
        for forward, left in ((True, 3), (False, 35)):
            rect(frame, left, 49, 26, 13, MID)
            rect(frame, left + 9, 51, 10, 6, RED)
            rect(frame, left + 9, 50, 4, 5, RED)
            rect(frame, left + 10, 51, 2, 2, SKY)
            rect(frame, left + 18, 52, 2, 2, WHITE)
            rect(frame, left + 9, 57, 3, 2, BLACK)
            rect(frame, left + 16, 57, 3, 2, BLACK)
            tip = left + (23 if forward else 3)
            line(frame, (left + 5, 60), (left + 22, 60), WHITE)
            rect(frame, tip, 59, 1, 3, WHITE)
            rect(frame, tip + (-1 if forward else 1), 58, 1, 5, WHITE)
        if game.feedback is not None and game.animation is None:
            x, y = game.feedback
            radius = 2 + game.pulse
            color = RED if game.refused else GREEN
            for dx, dy in ((-radius, 0), (radius, 0), (0, -radius), (0, radius)):
                rect(frame, x + dx, y + dy, 1, 1, color)
        return frame


class Yd01(ARCBaseGame):
    def __init__(self):
        self.st, self.history = initial(0), []
        self.feedback, self.animation = None, None
        self.pulse, self.refused = 0, False
        self.display = YardDisplay(self)
        levels = [Level(sprites=[], grid_size=(64, 64), name=data['name']) for data in LEVELS]
        super().__init__('yd01', levels, Camera(0, 0, 64, 64, CREAM, CREAM, [self.display]),
                         False, len(levels), [6, 7])

    def on_set_level(self, level):
        self.st, self.history = initial(self.level_index), []
        self.feedback, self.animation = None, None
        self.pulse, self.refused = 0, False

    def handle_reset(self):
        if self._state in (GameState.NOT_PLAYED, GameState.WIN):
            self.full_reset()
        else:
            self.level_reset()

    def finish(self, after):
        self.st, self.animation = after, None
        if after.won:
            self.next_level()
        self.complete_action()

    def step(self):
        action = self.action.id.value
        if action == 0:
            self.complete_action()
            return
        if self.animation is not None:
            self.animation['frame'] += 1
            if self.animation['frame'] >= 10:
                self.finish(self.animation['after'])
            return
        before = self.st
        self.pulse ^= 1
        if action == 7:
            after = self.history.pop() if self.history else before
            self.feedback = point(before.positions[0])
        else:
            x, y = self.action.data.get('x'), self.action.data.get('y')
            command = command_at(before, x, y) if action == 6 else ('invalid',)
            valid = all(isinstance(value, (int, float)) and isfinite(value) for value in (x, y))
            self.feedback = (max(1, min(62, int(x))), max(1, min(62, int(y)))) if valid else (1, 1)
            after = transition(self.level_index, before, command)
            if after != before:
                self.history.append(before)
        self.refused = after == before
        if after.positions != before.positions:
            self.animation = {'after': after, 'frame': 0}
            return
        self.finish(after)

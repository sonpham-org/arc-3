# Author: GPT-6 Astra
# Date: 2026-09-28 14:40
# PURPOSE: Ironkeep is a deterministic connected fortress. Shielded encounters,
# hooked objects, latching gates and persistent checkpoints share one transition
# function with the real-engine tests. Version 2 gives armor, tools and fortress
# objects distinct material silhouettes. Rendering uses numpy and arcengine only.
# SRP/DRY check: Pass — reuses the engine and Span's checkpoint lifecycle; no
# existing environment implements this fortress's shield and hook interactions.
"""Explore, block, pull and return with both gate cogs."""

from collections import namedtuple
from math import isfinite
import numpy as np
from arcengine import ARCBaseGame, Camera, GameState, Level, RenderableUserDisplay

WHITE, PALE, GRAY, MID, DARK, BLACK = range(6)
RED, BLUE, SKY, GOLD, ORANGE, MAROON, GREEN, PURPLE = range(8, 16)
CELL = 6
DIRECTIONS = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}

# Authored rooms share one boundary row/column. Entity locations below are also
# fixed data. The room join merely decodes this map; it generates no layouts.
ROOMS = (
    ("#########", "#.....#.#", "#.....#.#", "#.....#.#", "#.....g..",
     "#.....#.#", "#.....#.#", "#.....#.#", "#########"),
    ("#########", "#.....#.#", "#.....#.#", "#.....#.#", "......g..",
     "#.....#.#", "#.....#.#", "#.....#.#", "####~####"),
    ("#########", "#.......#", "#.......#", "#.......#", "........#",
     "#.......#", "####g####", "#.......#", "####~####"),
    ("#########", "#..#....#", "#..#....#", "#..#....#", "#..g.....",
     "#..#....#", "#..#....#", "#..#....#", "#########"),
    ("####~####", "#.#.....#", "#.#.....#", "#.#.....#", "..g.....~",
     "#.#.....#", "#.#.....#", "#.#.....#", "#########"),
    ("####~####", "#....#..#", "#....#..#", "#....#..#", "~....g..#",
     "#....#..#", "#....#..#", "#....#..#", "#########"),
)
MAP = tuple(ROOMS[band * 3][row] + ROOMS[band * 3 + 1][row][1:]
            + ROOMS[band * 3 + 2][row][1:]
            for band in range(2) for row in range(0 if band == 0 else 1, 9))
PLATES = ((4, 3), (11, 4), (19, 5), (19, 13), (13, 12), (5, 11))
GATES = ((6, 4), (14, 4), (20, 6), (21, 12), (10, 12), (3, 12))
BRIDGES = ((20, 8), (16, 12), (12, 8))
CHAINS = ((20, 7), (17, 12), (12, 7))
COGS = ((7, 4), (22, 12))
HOOK_CHEST, EXIT = (12, 2), (2, 12)
Guard = namedtuple("Guard", "pos target stun")
State = namedtuple("State", "player facing equipped hook hearts guards crates latches bridges cogs visited turn failed won")


def initial(checkpoint=0):
    guards = tuple(Guard(pos, None, 0) for pos in ((4, 4), (19, 4), (19, 12), (5, 12)))
    state = State((4, 6), 1, 0, False, 3, guards, ((12, 4), (12, 12)),
                  0, 0, 0, 1, 0, False, False)
    if checkpoint >= 1:
        guards = (Guard((4, 3), None, 0),) + guards[1:]
        state = state._replace(player=(7, 4), facing=4, guards=guards, latches=1, cogs=1)
    if checkpoint >= 2:
        guards = (guards[0], Guard((19, 5), None, 0), Guard((19, 13), None, 0), guards[3])
        state = state._replace(player=(22, 12), hook=True, equipped=0, guards=guards,
                               crates=((11, 4), (12, 12)), latches=15, bridges=1, cogs=3, visited=39)
    return state


def plus(position, direction, amount=1):
    return position[0] + direction[0] * amount, position[1] + direction[1] * amount


def terrain_open(state, position):
    x, y = position
    if not (0 <= x < 25 and 0 <= y < 17) or MAP[y][x] == "#":
        return False
    if position in GATES:
        index = GATES.index(position)
        return bool(state.latches & (1 << index)) and (index != 5 or state.cogs == 3)
    if position in BRIDGES:
        return bool(state.bridges & (1 << BRIDGES.index(position)))
    return True


def occupied(state, position, ignore_guard=None):
    return (position in state.crates or any(guard.pos == position for index, guard in enumerate(state.guards)
                                           if index != ignore_guard))


def camera_for(position):
    return min(16, position[0] // 8 * 8), min(8, position[1] // 8 * 8)


def room_bit(position):
    return 1 << (min(2, position[0] // 8) + 3 * min(1, position[1] // 8))


def latch_occupied_plates(state):
    objects = state.crates + tuple(guard.pos for guard in state.guards)
    latches = state.latches
    for index, plate in enumerate(PLATES):
        if plate in objects:
            latches |= 1 << index
    return state._replace(latches=latches)


def select_tool(state, index):
    if index not in (0, 1) or (index == 1 and not state.hook):
        return state
    return state._replace(equipped=index)


def hook_endpoint(state):
    direction = DIRECTIONS[state.facing]
    for distance in range(1, 4):
        target = plus(state.player, direction, distance)
        if not terrain_open(state, target) or any(guard.pos == target for guard in state.guards):
            return target
        if target in state.crates or target in CHAINS:
            return target
    return plus(state.player, direction, 3)


def hook_pull(state):
    target = hook_endpoint(state)
    if not terrain_open(state, target) or any(guard.pos == target for guard in state.guards):
        return state
    if target in state.crates:
        destination = plus(target, DIRECTIONS[state.facing], -1)
        if destination == state.player or occupied(state, destination) or not terrain_open(state, destination):
            return state
        crates = list(state.crates)
        crates[crates.index(target)] = destination
        return state._replace(crates=tuple(crates))
    if target in CHAINS:
        return state._replace(bridges=state.bridges | (1 << CHAINS.index(target)))
    return state


def transition(state, action, data=None):
    """One world turn; tool selection never advances a committed enemy attack."""
    if state.failed or state.won:
        return state
    if action == 6:
        if data is None or len(data) != 2 or not all(isinstance(v, (int, float)) and isfinite(v) for v in data):
            return state
        x, y = data
        return select_tool(state, int(x) // 16) if 0 <= x < 32 and 0 <= y < 9 else state
    if action not in (1, 2, 3, 4, 5, 7):
        return state
    before = state
    bracing = action == 5 and state.equipped == 0
    if action in DIRECTIONS:
        direction = DIRECTIONS[action]
        destination = plus(state.player, direction)
        state = state._replace(facing=action)
        if terrain_open(state, destination) and destination not in state.crates:
            guard_index = next((index for index, guard in enumerate(state.guards)
                                if guard.pos == destination), None)
            if guard_index is None:
                state = state._replace(player=destination)
            else:
                guard = state.guards[guard_index]
                pushed = plus(destination, direction)
                if guard.stun and terrain_open(state, pushed) and not occupied(state, pushed):
                    guards = list(state.guards)
                    guards[guard_index] = guard._replace(pos=pushed, target=None)
                    state = state._replace(player=destination, guards=tuple(guards))
    elif action == 5 and state.equipped == 1:
        state = hook_pull(state)
    state = latch_occupied_plates(state)
    guards, hearts = [], state.hearts
    for guard in state.guards:
        if guard.stun:
            guards.append(guard._replace(stun=guard.stun - 1, target=None))
            continue
        if guard.target == state.player:
            if bracing and plus(state.player, DIRECTIONS[state.facing]) == guard.pos:
                guards.append(guard._replace(target=None, stun=2))
                continue
            hearts -= 1
        # A telegraph's target never follows the player during its resolution.
        # Stationary guards announce only an adjacent strike for the NEXT turn.
        nearby = abs(guard.pos[0] - state.player[0]) + abs(guard.pos[1] - state.player[1]) == 1
        guards.append(guard._replace(target=state.player if nearby else None))
    # The first room is a safe lesson. Later encounters can end the attempt.
    hearts = max(1 if before.cogs == 0 else 0, hearts)
    cogs = state.cogs
    for index, position in enumerate(COGS):
        if state.player == position:
            cogs |= 1 << index
    has_hook = state.hook or state.player == HOOK_CHEST
    won = state.player == EXIT and cogs == 3 and hearts > 0
    return state._replace(hearts=hearts, guards=tuple(guards), cogs=cogs, hook=has_hook,
                          visited=state.visited | room_bit(state.player), turn=state.turn + 1,
                          failed=hearts == 0, won=won)


def rect(frame, x, y, width, height, color):
    left, top = max(0, round(x)), max(0, round(y))
    right, bottom = min(64, round(x + width)), min(64, round(y + height))
    if left < right and top < bottom:
        frame[top:bottom, left:right] = color


def shape(frame, x, y, rows, color):
    for row, bits in enumerate(rows):
        for column, bit in enumerate(bits):
            if bit == "1":
                rect(frame, x + column, y + row, 1, 1, color)


def line(frame, start, end, color):
    distance = max(abs(end[0] - start[0]), abs(end[1] - start[1]), 1)
    for tick in range(round(distance) + 1):
        amount = tick / distance
        rect(frame, start[0] + (end[0] - start[0]) * amount,
             start[1] + (end[1] - start[1]) * amount, 1, 1, color)


def outline(frame, x, y, width, height, color):
    rect(frame, x, y, width, 1, color)
    rect(frame, x, y + height - 1, width, 1, color)
    rect(frame, x, y, 1, height, color)
    rect(frame, x + width - 1, y, 1, height, color)


def armored_figure(frame, x, y, cloth, stride=0):
    """Feet occupy the rule tile; the helmet rises above its floor footprint."""
    # The two-toned helmet, dark visor and separate boots remain recognizable
    # when enlarged by the site without expanding collision or plate geometry.
    shape(frame, x, y - 2, ("011110", "111111", "111111", "011110",
                           "111111", "111111", "011110", "110011"), BLACK)
    rect(frame, x + 1, y - 2, 4, 1, PALE)
    rect(frame, x + 1, y - 1, 4, 1, WHITE)
    rect(frame, x + 1, y, 1, 1, PALE)
    rect(frame, x + 4, y, 1, 1, PALE)
    rect(frame, x + 1, y + 2, 4, 2, cloth)
    rect(frame, x, y + 2, 1, 2, PALE)
    rect(frame, x + 5, y + 2, 1, 2, GRAY)
    rect(frame, x + 2, y + 4, 2, 1, GRAY)
    rect(frame, x + (1 if stride else 4), y + 5, 1, 1, GRAY)


class FortressDisplay(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    def render_interface(self, frame):
        game, state = self.game, self.game.st
        old = game.animation["before"] if game.animation else state
        amount = game.animation["frame"] / 10 if game.animation else 1
        amount = min(1, amount)
        old_view, new_view = camera_for(old.player), camera_for(state.player)
        camera = tuple(old_view[axis] + (new_view[axis] - old_view[axis]) * amount for axis in (0, 1))

        def screen(position):
            return 5 + (position[0] - camera[0]) * CELL, 10 + (position[1] - camera[1]) * CELL

        frame[:, :] = DARK
        for y, row in enumerate(MAP):
            for x, tile in enumerate(row):
                left, top = screen((x, y))
                if left < -6 or left >= 64 or top < -6 or top >= 64:
                    continue
                if tile == "#":
                    rect(frame, left, top, 6, 6, DARK)
                    rect(frame, left, top, 6, 1, GRAY)
                    rect(frame, left, top + 1, 5, 3, MID)
                    rect(frame, left + 2 + (y % 2) * 2, top + 4, 1, 2, MID)
                else:
                    rect(frame, left, top, 6, 6, MID)
        for index, (plate, gate) in enumerate(zip(PLATES, GATES)):
            plate_xy, gate_xy = screen(plate), screen(gate)
            newly_latched = game.animation is not None and bool((state.latches & ~old.latches) & (1 << index))
            arrived = not newly_latched or game.animation["frame"] >= 10
            color = GREEN if state.latches & (1 << index) and arrived else ORANGE
            start, end = (plate_xy[0] + 3, plate_xy[1] + 3), (gate_xy[0] + 3, gate_xy[1] + 3)
            elbow = (end[0], start[1])
            line(frame, start, elbow, color)
            line(frame, elbow, end, color)
            outline(frame, plate_xy[0] + 1, plate_xy[1] + 1, 4, 4, color)
            if not terrain_open(state, gate) or not arrived:
                rect(frame, gate_xy[0], gate_xy[1], 6, 6, DARK)
                for bar in (0, 2, 4):
                    rect(frame, gate_xy[0] + bar, gate_xy[1], 1, 6, PALE)
                rect(frame, gate_xy[0], gate_xy[1] + 2, 6, 1, color)
            else:
                rect(frame, gate_xy[0], gate_xy[1], 6, 1, GREEN)
                if game.animation and not terrain_open(old, gate):
                    opening = min(1, max(0, (game.animation["frame"] - 10) / 3)) if newly_latched else amount
                    height = round(6 * (1 - opening))
                    for bar in (0, 2, 4):
                        rect(frame, gate_xy[0] + bar, gate_xy[1], 1, height, PALE)
        for index, (bridge, chain) in enumerate(zip(BRIDGES, CHAINS)):
            left, top = screen(bridge)
            if state.bridges & (1 << index):
                lowered = max(0, amount * 2 - 1) if game.animation and not old.bridges & (1 << index) else 1
                rect(frame, left, top, 6, 6, BLACK)
                rect(frame, left, top, 6, 6 * lowered, ORANGE)
                for plank in (1, 3, 5):
                    if plank < 6 * lowered:
                        rect(frame, left, top + plank, 6, 1, MAROON)
            else:
                rect(frame, left, top, 6, 6, BLACK)
                rect(frame, left, top + 5, 6, 1, SKY)
            ring = screen(chain)
            line(frame, (ring[0] + 3, ring[1] + 3), (left + 3, top + 3), PALE)
            outline(frame, ring[0] + 1, ring[1] + 1, 4, 4, WHITE)
        for index, position in enumerate(COGS):
            if not state.cogs & (1 << index):
                left, top = screen(position)
                rect(frame, left, top, 6, 6, DARK)
                shape(frame, left + 1, top + 1, ("01110", "11011", "10101", "11011", "01110"), GOLD)
        if not state.hook:
            left, top = screen(HOOK_CHEST)
            rect(frame, left, top + 1, 6, 4, ORANGE)
            outline(frame, left, top + 1, 6, 4, MAROON)
            rect(frame, left + 1, top + 2, 1, 2, GOLD)
            shape(frame, left + 2, top - 1, ("011", "001", "101", "111"), WHITE)
        exit_xy = screen(EXIT)
        rect(frame, exit_xy[0], exit_xy[1] - 2, 6, 8, BLACK)
        rect(frame, exit_xy[0], exit_xy[1] - 2, 6, 1, GRAY)
        for step in range(3):
            rect(frame, exit_xy[0] + step, exit_xy[1] + step * 2, 6 - step, 1, PALE)
        for index, position in enumerate(state.crates):
            previous = old.crates[index]
            # The outward cast reaches the ring halfway through the action;
            # only then does the crate follow the attached hook on its return.
            pulled = max(0, amount * 2 - 1) if game.animation and game.action_kind == 5 else amount
            moving = tuple(previous[axis] + (position[axis] - previous[axis]) * pulled for axis in (0, 1))
            left, top = screen(moving)
            rect(frame, left, top, 6, 5, ORANGE)
            outline(frame, left, top, 6, 5, MAROON)
            rect(frame, left + 1, top + 1, 1, 3, GOLD)
            rect(frame, left + 4, top + 1, 1, 3, MAROON)
            outline(frame, left + 2, top + 1, 3, 3, WHITE)
        for index, guard in enumerate(state.guards):
            previous = old.guards[index]
            position = tuple(previous.pos[axis] + (guard.pos[axis] - previous.pos[axis]) * amount for axis in (0, 1))
            left, top = screen(position)
            if guard.target is not None:
                mark = screen(guard.target)
                outline(frame, mark[0], mark[1], 6, 6, RED)
                rect(frame, mark[0] + 2, mark[1] + 2, 2, 2, ORANGE)
            if guard.stun:
                rect(frame, left, top + 3, 6, 3, BLACK)
                rect(frame, left + 2, top + 3, 3, 2, MAROON)
                rect(frame, left, top + 2, 2, 2, PALE)
                rect(frame, left + (game.pulse % 2) * 4, top, 1, 1, GOLD)
                if game.animation and not previous.stun and amount < 0.6:
                    outline(frame, left - 1, top - 1, 8, 8, WHITE if game.animation['frame'] % 2 else GOLD)
            else:
                armored_figure(frame, left, top, MAROON)
                rect(frame, left + 5, top - 1, 1, 4, PALE)
        position = tuple(old.player[axis] + (state.player[axis] - old.player[axis]) * amount for axis in (0, 1))
        left, top = screen(position)
        armored_figure(frame, left, top, GREEN, game.pulse)
        direction = DIRECTIONS[state.facing]
        shield = (left + 2 + direction[0] * 3, top + 2 + direction[1] * 3)
        if state.equipped == 0:
            color = WHITE if game.action_kind == 5 and game.animation else SKY
            if direction[0]:
                rect(frame, shield[0], shield[1] - 1, 2, 4, BLUE)
                rect(frame, shield[0], shield[1] - 1, 1, 3, color)
            else:
                rect(frame, shield[0], shield[1], 4, 2, BLUE)
                rect(frame, shield[0], shield[1], 4, 1, color)
        else:
            rect(frame, shield[0], shield[1], 2, 2, ORANGE)
        if game.animation and game.animation["frame"] < 10 and game.action_kind == 5 and old.equipped == 1:
            endpoint = hook_endpoint(old)
            moving_crate = next((index for index in range(len(state.crates))
                                 if old.crates[index] != state.crates[index]), None)
            if amount > 0.5 and moving_crate is not None:
                endpoint = tuple(old.crates[moving_crate][axis] +
                                 (state.crates[moving_crate][axis] - old.crates[moving_crate][axis]) * (amount * 2 - 1)
                                 for axis in (0, 1))
            else:
                reach = min(amount * 2, 2 - amount * 2)
                endpoint = tuple(position[axis] + (endpoint[axis] - position[axis]) * reach for axis in (0, 1))
            line(frame, (left + 3, top + 3), tuple(value + 3 for value in screen(endpoint)), WHITE)
        if game.feedback is not None:
            mark = screen(game.feedback)
            outline(frame, mark[0], mark[1], 5 + game.pulse % 2, 5 + game.pulse % 2, RED)
        self.header(frame, state)
        if state.failed:
            outline(frame, 0, 0, 64, 64, RED)
        return frame

    def header(self, frame, state):
        rect(frame, 0, 0, 64, 10, BLACK)
        shape(frame, 5, 1, ("11111", "11111", "11111", "11111", "01110", "00100"), BLUE)
        shape(frame, 5, 1, ("11111", "10100", "10100", "10100", "01100", "00100"), SKY)
        shape(frame, 20, 1, ("00011", "00001", "00001", "10001", "11011", "01110"), PALE if state.hook else MID)
        outline(frame, state.equipped * 16, 0, 16, 9,
                GRAY if self.game.action_kind == 6 and self.game.pulse % 2 else WHITE)
        for heart in range(3):
            shape(frame, 34 + heart * 5, 2, ("101", "111", "111", "010"), RED if heart < state.hearts else MID)
        room = room_bit(state.player)
        for index in range(6):
            color = WHITE if room == 1 << index else GRAY if state.visited & (1 << index) else DARK
            outline(frame, 51 + index % 3 * 4, 1 + index // 3 * 4, 4, 4, color)
        for cog in range(2):
            rect(frame, 35 + cog * 6, 7, 4, 2, GOLD if state.cogs & (1 << cog) else MID)


class Ik01(ARCBaseGame):
    def __init__(self):
        self.st = initial()
        self.entries = {index: initial(index) for index in range(3)}
        self.pending_entry = None
        self.animation, self.feedback = None, None
        self.pulse, self.action_kind = 0, 0
        self.display = FortressDisplay(self)
        levels = [Level(sprites=[], grid_size=(64, 64), name=name, data={"checkpoint": index})
                  for index, name in enumerate(("Courtyard", "Upper fortress", "Return to the gate"))]
        super().__init__("ik01", levels, Camera(0, 0, 64, 64, DARK, DARK, [self.display]),
                         False, 3, [1, 2, 3, 4, 5, 6, 7])

    def on_set_level(self, level):
        index = level.get_data("checkpoint")
        self.animation, self.feedback = None, None
        self.pulse, self.action_kind = 0, 0
        if self.pending_entry == index:
            self.pending_entry = None
            return
        if index == 0:
            self.entries = {number: initial(number) for number in range(3)}
        self.st = self.entries[index]

    def handle_reset(self):
        if self._state in (GameState.NOT_PLAYED, GameState.WIN):
            self.full_reset()
        else:
            self.level_reset()

    def finish_action(self):
        if self.st.failed:
            self.lose()
        else:
            reached = (bool(self.st.cogs & 1) if self.level_index == 0 else
                       self.st.cogs == 3 if self.level_index == 1 else self.st.won)
            if reached:
                if self.level_index < 2:
                    self.pending_entry = self.level_index + 1
                    self.entries[self.pending_entry] = self.st
                self.next_level()
        self.complete_action()

    def step(self):
        if self.action.id.value == 0:
            self.complete_action()
            return
        if self.animation is not None:
            self.animation["frame"] += 1
            if self.animation["frame"] >= self.animation["duration"]:
                self.animation = None
                self.finish_action()
            return
        old = self.st
        action = self.action.id.value
        data = (self.action.data.get("x"), self.action.data.get("y")) if action == 6 else None
        self.st = transition(old, action, data)
        self.pulse ^= 1
        self.action_kind, self.feedback = action, None
        if action in DIRECTIONS and self.st.player == old.player:
            self.feedback = plus(old.player, DIRECTIONS[action])
        elif action == 5 and old.equipped == 1 and old.crates == self.st.crates and old.bridges == self.st.bridges:
            self.feedback = hook_endpoint(old)
        if action == 6:
            self.finish_action()
        else:
            # Commit physics once. Newly latched gates visibly open only after
            # the object reaches its plate; other actions keep their old speed.
            duration = 13 if self.st.latches & ~old.latches else 10
            self.animation = {"before": old, "frame": 0, "duration": duration}

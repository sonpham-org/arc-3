# Author: GPT-6 Astra
# Date: 2026-09-28 14:44
# PURPOSE: Workshop v3 makes deterministic scheduling physical: product tabs show
# enlarged recipes, reservations occupy matching machines, and explicit clock
# ticks animate processing. The immutable rules are shared with verification.
# SRP/DRY check: Pass — reuses v1 scheduling and ARC adapter; physical interpolation
# follows Span/Crease without importing another environment or test helper.
"""Select a product, reserve its machines, then run one tick with ACTION5."""

from collections import namedtuple
from math import isfinite

import numpy as np
from arcengine import ARCBaseGame, Camera, GameState, Level, RenderableUserDisplay

WHITE, SILVER, GRAY, MID, DARK, BLACK = 0, 1, 2, 3, 4, 5
RED, BLUE, GREEN, ORANGE, SKY, BRICK = 8, 9, 14, 12, 10, 13
PRODUCT_COLORS = (BLUE, GREEN, ORANGE, SILVER)
TUTORIAL_LEVELS = 3
ORDERS = (
    {"name": "First parcel", "due": 3, "recipes": (((0, 1), (1, 2)),)},
    {"name": "Work together", "due": 2, "recipes": (((0, 2),), ((1, 1),))},
    {"name": "Swap machines", "due": 3, "recipes": (((0, 2), (1, 1)), ((1, 2), (0, 1)))},
    {"name": "Overlap", "due": 8, "pickups": (4, 7, 6, 8), "recipes": (
        ((1, 1), (0, 2), (2, 1)), ((0, 1), (1, 3), (2, 2)),
        ((0, 1), (2, 1), (1, 1)), ((1, 1), (0, 3), (2, 1)))},
    {"name": "Long lead", "due": 7, "pickups": (7, 7, 4, 3), "recipes": (
        ((0, 2), (1, 2), (2, 1)), ((1, 1), (2, 3), (0, 2)),
        ((0, 1), (2, 1), (1, 1)), ((2, 1), (0, 1), (1, 1)))},
    {"name": "Cross traffic", "due": 8, "pickups": (8, 7, 8, 6), "recipes": (
        ((2, 3), (0, 1), (1, 2)), ((0, 2), (1, 3), (2, 1)),
        ((1, 1), (2, 2), (0, 3)), ((1, 2), (0, 2), (2, 1)))},
    {"name": "Last collection", "due": 9, "pickups": (7, 9, 6, 9), "recipes": (
        ((0, 2), (2, 1), (1, 3)), ((2, 2), (1, 1), (0, 3)),
        ((1, 3), (0, 1), (2, 2)), ((2, 1), (0, 2), (1, 2)))},
)
State = namedtuple("State", "level elapsed selected starts failed won")


def initial(level=0):
    return State(level, 0, 0, tuple(tuple(-1 for _ in row)
                                  for row in ORDERS[level]["recipes"]), False, False)


def jobs(state):
    return tuple((row, stage, machine, duration, state.starts[row][stage])
                 for row, recipe in enumerate(ORDERS[state.level]["recipes"])
                 for stage, (machine, duration) in enumerate(recipe))


def pending_stage(state):
    return next((stage for stage, start in enumerate(state.starts[state.selected]) if start < 0), None)


def transition(state, command):
    """Preserve v1 fit, precedence and pickup rules; every feasible plan can win."""
    if state.failed or state.won:
        return state
    if command[0] == "select":
        return state._replace(selected=command[1]) if 0 <= command[1] < len(state.starts) else state
    if command[0] == "place":
        row, pending = state.selected, pending_stage(state)
        if pending is None:
            return state
        machine, duration = ORDERS[state.level]["recipes"][row][pending]
        start = command[2]
        if command[1] != machine or start < state.elapsed or start + duration > ORDERS[state.level]["due"]:
            return state
        if any(other_machine == machine and other_start >= 0
               and start < other_start + other_duration and other_start < start + duration
               for _, _, other_machine, other_duration, other_start in jobs(state)):
            return state
        starts = [list(values) for values in state.starts]
        starts[row][pending] = start
        return state._replace(starts=tuple(tuple(values) for values in starts))
    if command[0] != "tick":
        return state
    scheduled = jobs(state)
    if any(start < 0 for _, _, _, _, start in scheduled):
        return state
    for row, stage, _, _, start in scheduled:
        if start == state.elapsed:
            for earlier in range(stage):
                earlier_start = state.starts[row][earlier]
                earlier_duration = ORDERS[state.level]["recipes"][row][earlier][1]
                if earlier_start < 0 or earlier_start + earlier_duration > state.elapsed:
                    return state if state.level < TUTORIAL_LEVELS else state._replace(failed=True)
    elapsed = state.elapsed + 1
    pickups = ORDERS[state.level].get("pickups", (ORDERS[state.level]["due"],) * len(state.starts))
    for row, pickup in enumerate(pickups):
        if elapsed >= pickup and any(start < 0 or start + duration > elapsed
                                    for other_row, _, _, duration, start in scheduled if other_row == row):
            return state if state.level < TUTORIAL_LEVELS else state._replace(elapsed=elapsed, failed=True)
    done = all(start >= 0 and start + duration <= elapsed
               for _, _, _, duration, start in scheduled)
    return state._replace(elapsed=elapsed, won=done,
                          failed=elapsed >= ORDERS[state.level]["due"] and not done)


def slot_width(level):
    return min(15, 45 // ORDERS[level]["due"])


def tab_center(row):
    return 7 + row * 16, 5


def slot_center(level, machine, time):
    return 18 + time * slot_width(level) + slot_width(level) // 2, 38 + machine * 10


def command_at(state, x, y):
    if not all(isinstance(value, (int, float)) and isfinite(value) for value in (x, y)):
        return ("invalid",)
    if 0 <= y < 14 and 0 <= x < len(state.starts) * 16:
        return ("select", int(x) // 16)
    if 1 <= x < 16 and 28 <= y < 33:
        return ("tick",)
    width = slot_width(state.level)
    if 18 <= x < 18 + ORDERS[state.level]["due"] * width and 34 <= y < 63:
        machine = (int(y) - 34) // 10
        if int(y) - 34 - machine * 10 < 9:
            return ("place", machine, (int(x) - 18) // width)
    return ("invalid",)


def rect(frame, x, y, width, height, color):
    left, top = max(0, int(x)), max(0, int(y))
    right, bottom = min(64, int(x + width)), min(64, int(y + height))
    if left < right and top < bottom:
        frame[top:bottom, left:right] = color


def outline(frame, x, y, width, height, color):
    rect(frame, x, y, width, 1, color)
    rect(frame, x, y + height - 1, width, 1, color)
    rect(frame, x, y, 1, height, color)
    rect(frame, x + width - 1, y, 1, height, color)


def product_icon(frame, row, x, y, color, scale=1):
    # Chair, goblet, picture frame and handled cup are distinct physical products.
    shapes = ("1000010000111111000110001", "0111001110001000010001110",
              "1111110001100011000111111", "1111010011100111111000000")
    for index, bit in enumerate(shapes[row]):
        if bit == "1":
            rect(frame, x + index % 5 * scale, y + index // 5 * scale, scale, scale, color)


def machine_icon(frame, machine, x, y, color=WHITE, phase=None, product=None):
    """The same physical machine appears on its recipe and timetable lane."""
    if machine == 0:
        rect(frame, x, y + 5, 11, 2, ORANGE)
        rect(frame, x + 1, y + 7, 2, 1, GRAY)
        rect(frame, x + 8, y + 7, 2, 1, GRAY)
        # Individual teeth and the dark axle distinguish the blade from a box.
        rect(frame, x + 3, y + 1, 5, 3, SILVER)
        rect(frame, x + 4, y, 3, 5, SILVER)
        for tooth_x, tooth_y in ((3, 0), (7, 0), (2, 2), (8, 2)):
            rect(frame, x + tooth_x, y + tooth_y, 1, 1, color)
        rect(frame, x + 5, y + 2, 1, 1, BLACK)
        if product is not None:
            separation = 1 if phase is not None and phase >= 7 else 0
            rect(frame, x + 1, y + 4, 4, 1, PRODUCT_COLORS[product])
            rect(frame, x + 5 + separation, y + 4, 4, 1, PRODUCT_COLORS[product])
        if phase is not None:
            rect(frame, x + 4 + phase % 3, y + 1, 1, 1, GRAY)
    elif machine == 1:
        rect(frame, x, y, 11, 2, GRAY)
        rect(frame, x, y, 2, 8, GRAY)
        rect(frame, x + 9, y, 2, 8, GRAY)
        rect(frame, x, y, 11, 1, SILVER)
        rect(frame, x, y + 1, 1, 6, SILVER)
        rect(frame, x, y + 7, 11, 1, SILVER)
        if product is not None:
            rect(frame, x + 3, y + 5, 5, 2, PRODUCT_COLORS[product])
        depth = 2 if phase is None else 2 + min(3, phase % 8, 7 - phase % 8)
        rect(frame, x + 5, y + 1, 1, depth, SILVER)
        rect(frame, x + 3, y + depth, 5, 1, color)
    else:
        rect(frame, x + 1, y + 1, 9, 7, BRICK)
        rect(frame, x + 2, y + 1, 7, 1, ORANGE)
        rect(frame, x + 7, y, 2, 2, BRICK)
        rect(frame, x + 7, y, 2, 1, GRAY)
        rect(frame, x + 2, y + 4, 1, 1, ORANGE)
        rect(frame, x + 8, y + 6, 1, 1, ORANGE)
        rect(frame, x + 3, y + 3, 5, 4, BLACK)
        rect(frame, x + 4, y + 2, 3, 1, BLACK)
        rect(frame, x + 3, y + 7, 5, 1, GRAY)
        if product is not None:
            rect(frame, x + 4, y + 4, 3, 2, PRODUCT_COLORS[product])
        if phase is not None:
            for flame in range(3):
                rect(frame, x + 3 + flame * 2, y + 6 - (phase + flame) % 2, 1, 1, ORANGE)


DIGITS = ("111101101101111", "010110010010111", "111001111100111",
          "111001111001111", "101101111001001", "111100111001111",
          "111100111101111", "111001001001001", "111101111101111",
          "111101111001111")


def digit(frame, value, x, y, color):
    for index, bit in enumerate(DIGITS[value]):
        if bit == "1":
            rect(frame, x + index % 3, y + index // 3, 1, 1, color)


class WorkshopDisplay(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    def recipe(self, frame, state):
        recipes = ORDERS[state.level]["recipes"]
        for row, recipe in enumerate(recipes):
            left = 1 + row * 16
            rect(frame, left, 1, 14, 12, MID)
            product_icon(frame, row, left + 1, 1, PRODUCT_COLORS[row])
            pickup = ORDERS[state.level].get("pickups", (ORDERS[state.level]["due"],) * len(recipes))[row]
            digit(frame, pickup, left + 10, 1, SILVER)
            for stage, start in enumerate(state.starts[row]):
                color = PRODUCT_COLORS[row] if start >= 0 else SILVER
                machine = recipe[stage][0]
                glyph = ("101111111", "111010101", "111101101")[machine]
                for index, bit in enumerate(glyph):
                    if bit == "1":
                        rect(frame, left + stage * 5 + index % 3, 7 + index // 3, 1, 1, color)
                for unit in range(recipe[stage][1]):
                    rect(frame, left + stage * 5 + unit, 11, 1, 1, color)
                if self.game.missing and start < 0:
                    rect(frame, left + stage * 5, 12, 3, 1, RED if self.game.pulse else ORANGE)
            if row == state.selected:
                outline(frame, left - 1, 0, 16, 14, WHITE)
                rect(frame, left + 6, 14, 3, 1, WHITE)
                rect(frame, left + 7, 15, 1, 1, WHITE)
        recipe = recipes[state.selected]
        pending = pending_stage(state)
        for stage, (machine, duration) in enumerate(recipe):
            left = 1 + stage * 15
            rect(frame, left, 17, 13, 9, MID)
            machine_icon(frame, machine, left + 1, 17)
            start = state.starts[state.selected][stage]
            color = PRODUCT_COLORS[state.selected] if start >= 0 else WHITE
            if stage == pending:
                outline(frame, left - 1, 16, 15, 11, RED if self.game.missing else SKY)
            elif start >= 0:
                rect(frame, left, 16, 13, 1, color)
            if stage < len(recipe) - 1:
                rect(frame, left + 13, 21, 2, 1, WHITE)
            for unit in range(duration):
                rect(frame, left + 2 + unit * 3, 25, 2, 2, color)
        # The selected product's collection truck uses the same quantity scale.
        rect(frame, 48, 17, 9, 8, SILVER)
        rect(frame, 57, 20, 5, 5, SILVER)
        rect(frame, 58, 21, 3, 2, SKY)
        rect(frame, 50, 25, 3, 2, BLACK)
        rect(frame, 58, 25, 3, 2, BLACK)
        pickup = ORDERS[state.level].get("pickups", (ORDERS[state.level]["due"],) * len(recipes))[state.selected]
        digit(frame, pickup, 51, 18, DARK)

    def timetable(self, frame, state):
        game, width = self.game, slot_width(state.level)
        due = ORDERS[state.level]["due"]
        pending = pending_stage(state)
        expected = ORDERS[state.level]["recipes"][state.selected][pending] if pending is not None else None
        for time in range(due):
            digit(frame, time, 18 + time * width + max(0, (width - 3) // 2), 27, SILVER)
        for machine in range(3):
            top = 34 + machine * 10
            machine_icon(frame, machine, 2, top)
            for time in range(due):
                left = 18 + time * width
                rect(frame, left, top, width - 1, 9, MID)
                if expected is not None and expected[0] == machine:
                    rect(frame, left, top + 8, width - 1, 1, SKY)
        for row, stage, machine, duration, start in jobs(state):
            if start < 0:
                continue
            top, left = 34 + machine * 10, 18 + start * width
            done = start + duration <= state.elapsed
            rect(frame, left, top, duration * width - 1, 9, GRAY if done else PRODUCT_COLORS[row])
            product_icon(frame, row, left + max(0, (width - 5) // 2), top + 1, WHITE)
            for unit in range(duration):
                rect(frame, left + unit * width, top + 7, width - 1, 1, DARK)
        if state.level == 0 and expected is not None:
            time = 0 if pending == 0 else state.starts[0][pending - 1] + 1
            left = 18 + time * width
            outline(frame, left, 34 + expected[0] * 10, expected[1] * width - 1, 9, WHITE)
            # A faded chair is a physical ghost of the next reservation.
            product_icon(frame, 0, left + 4, 35 + expected[0] * 10, SKY)
        elapsed = state.elapsed
        animation = game.animation
        if animation is not None:
            elapsed += min(1, animation["frame"] / 14)
            for row, _stage, machine, duration, start in jobs(state):
                if start <= state.elapsed < start + duration and start >= 0:
                    top = 34 + machine * 10
                    rect(frame, 0, top, 15, 9, DARK)
                    machine_icon(frame, machine, 2, top, phase=animation["frame"], product=row)
                    # Motion at the reservation ties the active job to the machine.
                    rect(frame, 18 + start * width, top, duration * width - 1, 1, WHITE)
        if elapsed:
            marker = min(63, 18 + int(elapsed * width))
            rect(frame, marker, 32, 1, 31, WHITE)

    def render_interface(self, frame):
        game, state = self.game, self.game.st
        frame[:, :] = DARK
        self.recipe(frame, state)
        self.timetable(frame, state)
        ready = all(start >= 0 for starts in state.starts for start in starts)
        rect(frame, 1, 28, 15, 5, ORANGE if ready else MID)
        outline(frame, 4, 28, 7, 5, WHITE if ready else GRAY)
        rect(frame, 7, 29, 1, 2, WHITE)
        rect(frame, 7, 30, 3, 1, WHITE)
        if state.level == 0 and ready:
            outline(frame, 0, 27, 17, 7, WHITE)
        if game.feedback is not None and game.animation is None:
            x, y = game.feedback
            color = RED if game.rejected else WHITE
            radius = 2 + int(game.pulse)
            outline(frame, x - radius, y - radius, 2 * radius + 1, 2 * radius + 1, color)
        if state.failed:
            outline(frame, 0, 0, 64, 64, RED)
        return frame


class Wk01(ARCBaseGame):
    def __init__(self):
        self.st, self.history = initial(), []
        self.feedback, self.animation = None, None
        self.pulse, self.rejected, self.missing = False, False, False
        self.display = WorkshopDisplay(self)
        levels = [Level(sprites=[], grid_size=(64, 64), name=order["name"]) for order in ORDERS]
        super().__init__("wk01", levels, Camera(0, 0, 64, 64, DARK, DARK, [self.display]),
                         False, len(levels), [5, 6, 7])

    def on_set_level(self, level):
        self.st, self.history = initial(self.level_index), []
        self.feedback, self.animation = None, None
        self.pulse, self.rejected, self.missing = False, False, False

    def handle_reset(self):
        if self._state in (GameState.NOT_PLAYED, GameState.WIN):
            self.full_reset()
        else:
            self.level_reset()

    def finish(self, state):
        self.st, self.animation = state, None
        if state.failed:
            self.lose()
        elif state.won:
            self.next_level()
        self.complete_action()

    def step(self):
        action = self.action.id.value
        if action == 0:
            self.complete_action()
            return
        if self.animation is not None:
            self.animation["frame"] += 1
            if self.animation["frame"] >= 15:
                self.finish(self.animation["after"])
            return
        self.pulse = not self.pulse
        self.missing = False
        old = self.st
        if action == 7:
            after = self.history.pop() if self.history else old
            self.feedback = (7, 29)
        else:
            if action == 6:
                x, y = self.action.data.get("x"), self.action.data.get("y")
                command = command_at(old, x, y)
                valid = all(isinstance(value, (int, float)) and isfinite(value) for value in (x, y))
                self.feedback = (max(1, min(62, int(x))), max(1, min(62, int(y)))) if valid else (1, 1)
            else:
                command = ("tick",) if action == 5 else ("invalid",)
                self.feedback = (7, 29)
            after = transition(old, command)
            self.missing = command[0] == "tick" and any(start < 0 for starts in old.starts for start in starts)
            if after != old:
                self.history.append(old)
            if command[0] == "tick" and after.elapsed != old.elapsed:
                self.animation = {"after": after, "frame": 0}
                self.rejected = False
                return
        self.rejected = after == old
        self.finish(after)

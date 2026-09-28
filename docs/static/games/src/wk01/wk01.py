# Author: GPT-6 Astra
# Date: 2026-09-27 18:53
# PURPOSE: Workshop is a deterministic, turn-based ARC environment. Visible recipes
# occupy shared machines for discrete durations; one explicit clock action advances
# all running jobs. The same immutable scheduling transition drives play and gates.
# SRP/DRY check: Pass — inspected factory/assembly neighbors and arcengine adapters;
# none supplies duration-aware concurrent scheduling or this shared transition.
"""Workshop: select a recipe, place its next job, ACTION5 ticks, ACTION7 undoes."""

from collections import namedtuple

import numpy as np
from arcengine import ARCBaseGame, Camera, GameState, Level, RenderableUserDisplay

WHITE, SILVER, GRAY, DARK, BLACK = 0, 1, 2, 4, 5
RED, BLUE, GREEN, ORANGE = 8, 9, 14, 12
PRODUCT_COLORS = (BLUE, GREEN, ORANGE, SILVER)

# Every row lists required jobs in order. All jobs must occupy their matching
# machine and run after their predecessors. Planning is free of time pressure.
ORDERS = (
    {"name": "First parcel", "due": 9, "recipes": (((0, 1), (1, 2)),)},
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


def transition(state, command):
    """Commands are ('select', row), ('place', machine, time), or ('tick',).

    Placement validates physical fit and overlap. Precedence is visibly validated
    when the clock reaches a job: all of its earlier jobs must already be finished.
    Any feasible schedule is accepted, including intentional idle machine time.
    """
    if state.failed or state.won:
        return state
    if command[0] == "select":
        return state._replace(selected=command[1]) if 0 <= command[1] < len(state.starts) else state
    if command[0] == "place":
        row = state.selected
        pending = next((stage for stage, start in enumerate(state.starts[row]) if start < 0), None)
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
    # Place the entire visible recipe before running the workshop. This keeps
    # planning untimed and makes an empty/missing recipe card a useful refusal.
    if any(start < 0 for _, _, _, _, start in scheduled):
        return state
    for row, stage, _, _, start in scheduled:
        if start == state.elapsed:
            for earlier in range(stage):
                earlier_start = state.starts[row][earlier]
                earlier_duration = ORDERS[state.level]["recipes"][row][earlier][1]
                if earlier_start < 0 or earlier_start + earlier_duration > state.elapsed:
                    return state if state.level == 0 else state._replace(failed=True)
    elapsed = state.elapsed + 1
    pickups = ORDERS[state.level].get("pickups", (ORDERS[state.level]["due"],) * len(state.starts))
    for row, pickup in enumerate(pickups):
        if elapsed >= pickup and any(start < 0 or start + duration > elapsed
                                    for other_row, _, _, duration, start in scheduled if other_row == row):
            return state._replace(elapsed=elapsed, failed=True)
    done = all(start >= 0 and start + duration <= elapsed
               for _, _, _, duration, start in scheduled)
    return state._replace(elapsed=elapsed, won=done,
                          failed=elapsed >= ORDERS[state.level]["due"] and not done)


def card_center(row, stage):
    return 19 + stage * 13, 4 + row * 8


def command_at(state, x, y):
    if 0 <= y < len(state.starts) * 8:
        return ("select", y // 8)
    if 0 <= x < 14 and 33 <= y < 42:
        return ("tick",)
    if 16 <= x < 61 and 42 <= y < 63:
        return ("place", (y - 42) // 7, (x - 16) // 5)
    return ("invalid",)


def machine_icon(frame, machine, x, y, color):
    """Three distinct silhouettes, repeated on recipes and their machine lanes."""
    if machine == 0:
        frame[y + 1:y + 4, x:x + 5] = color
        frame[y, x:x + 5:2] = color
    elif machine == 1:
        frame[y:y + 2, x:x + 5] = color
        frame[y + 2:y + 4, x + 2:x + 3] = color
        frame[y + 4, x:x + 5] = color
    else:
        frame[y:y + 5, x:x + 5] = color
        frame[y + 2:y + 5, x + 1:x + 4] = DARK


def product_icon(frame, row, x, y, color):
    if row == 0:
        frame[y + 1:y + 4, x:x + 5] = color
        frame[y:y + 5, x + 1:x + 4] = color
        frame[y + 2, x + 2] = DARK
    elif row == 1:
        frame[y:y + 3, x + 1:x + 4] = color
        frame[y + 3:y + 5, x + 2] = color
        frame[y + 4, x:x + 5] = color
    elif row == 2:
        frame[y:y + 5, x:x + 5] = color
        frame[y + 1:y + 4, x + 1:x + 4] = DARK
    else:
        frame[y:y + 5, x:x + 5] = color
        frame[y + 1:y + 4, x + 2] = DARK


DIGITS = ("111101101101111", "010110010010111", "111001111100111",
          "111001111001111", "101101111001001", "111100111001111",
          "111100111101111", "111001001001001", "111101111101111",
          "111101111001111")


def digit(frame, value, x, y, color):
    for index, bit in enumerate(DIGITS[value]):
        if bit == "1":
            frame[y + index // 3, x + index % 3] = color


class WorkshopDisplay(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    def render_interface(self, frame):
        game, state = self.game, self.game.st
        frame[:, :] = DARK
        recipes = ORDERS[state.level]["recipes"]
        for row, recipe in enumerate(recipes):
            top = row * 8
            frame[top:top + 7, 1:62] = GRAY
            product_icon(frame, row, 4, top + 1, PRODUCT_COLORS[row])
            if row == state.selected:
                frame[top:top + 7, 0] = WHITE
                frame[top:top + 7, 11] = WHITE
            for stage, (machine, duration) in enumerate(recipe):
                center_x, center_y = card_center(row, stage)
                start = state.starts[row][stage]
                color = WHITE if start < 0 else PRODUCT_COLORS[row]
                frame[top:top + 7, center_x - 5:center_x + 5] = DARK
                machine_icon(frame, machine, center_x - 4, top, color)
                for unit in range(duration):
                    frame[top + 1 + unit * 2, center_x + 2:center_x + 4] = color
                if stage < len(recipe) - 1:
                    frame[top + 3, center_x + 5:center_x + 8] = WHITE
                if start >= 0:
                    frame[top + 6, center_x - 4:center_x + 4] = color
                    if start + duration <= state.elapsed:
                        frame[top + 2:top + 5, center_x - 3:center_x] = GREEN
            product_done = all(start >= 0 and start + recipe[stage][1] <= state.elapsed
                               for stage, start in enumerate(state.starts[row]))
            # A small collection truck carries the row's visible pickup time.
            frame[top + 1:top + 6, 53:61] = WHITE if product_done else SILVER
            frame[top + 6, 54:56] = frame[top + 6, 59:61] = BLACK
            pickup = ORDERS[state.level].get("pickups", (ORDERS[state.level]["due"],) * len(recipes))[row]
            digit(frame, pickup, 55, top + 1, DARK)
        # Clock button and shared time axis. A digit is a time, not an action budget.
        frame[34:41, 1:13] = ORANGE
        frame[35:40, 4:9] = DARK
        frame[35:38, 6] = WHITE
        frame[37, 6:9] = WHITE
        due = ORDERS[state.level]["due"]
        for tick in range(due):
            digit(frame, tick, 17 + tick * 5, 35, WHITE)
        for machine in range(3):
            top = 42 + machine * 7
            machine_icon(frame, machine, 4, top + 1, WHITE)
            frame[top:top + 6, 16:16 + due * 5] = GRAY
            frame[top:top + 6, 16:16 + due * 5:5] = DARK
        for row, stage, machine, duration, start in jobs(state):
            if start < 0:
                continue
            top, left = 42 + machine * 7, 16 + start * 5
            frame[top:top + 6, left:left + duration * 5 - 1] = PRODUCT_COLORS[row]
            for offset in range(duration):
                frame[top + 5, left + offset * 5:left + offset * 5 + 4] = DARK
            product_icon(frame, row, left, top, WHITE)
        if state.elapsed:
            marker = min(62, 15 + state.elapsed * 5)
            frame[41:63, marker] = WHITE
        if game.feedback:
            x, y = game.feedback
            color = (RED if game.rejected else WHITE) if game.pulse else ORANGE
            frame[max(0, y - 1):min(64, y + 2), max(0, x - 1):min(64, x + 2)] = color
        if state.failed:
            frame[33, :] = RED
        return frame


class Wk01(ARCBaseGame):
    def __init__(self):
        self.st = initial()
        self.history = []
        self.feedback = None
        self.pulse = False
        self.rejected = False
        self.display = WorkshopDisplay(self)
        levels = [Level(sprites=[], grid_size=(64, 64), name=order["name"])
                  for order in ORDERS]
        super().__init__("wk01", levels, Camera(0, 0, 64, 64, DARK, DARK, [self.display]),
                         False, len(levels), [5, 6, 7])

    def on_set_level(self, level):
        self.st = initial(self.level_index)
        self.history = []
        self.feedback = None
        self.pulse = False
        self.rejected = False

    def handle_reset(self):
        if self._state in (GameState.NOT_PLAYED, GameState.WIN):
            self.full_reset()
        else:
            self.level_reset()

    def step(self):
        action = self.action.id.value
        if action == 0:
            self.complete_action()
            return
        self.pulse = not self.pulse
        old = self.st
        if action == 7:
            self.st = self.history.pop() if self.history else self.st
            self.feedback = (11, 37)
        else:
            if action == 6:
                x = int(self.action.data.get("x", -1))
                y = int(self.action.data.get("y", -1))
                command = command_at(self.st, x, y)
                self.feedback = (max(0, min(63, x)), max(0, min(63, y)))
            else:
                command = ("tick",) if action == 5 else ("invalid",)
                self.feedback = (6, 37)
            self.st = transition(self.st, command)
            if self.st != old:
                self.history.append(old)
        self.rejected = self.st == old
        if self.st.failed:
            self.lose()
        elif self.st.won:
            self.next_level()
        self.complete_action()

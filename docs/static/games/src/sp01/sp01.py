# Author: GPT-6 Astra
# Date: 2026-09-27 18:40
# PURPOSE: Span's deterministic rigid-body climbing model. The latched endpoint
# defines the reference frame for rotation, telescoping extension and transfer.
# Fixed cliff geometry supplies swept-volume constraints and persistent holds.
# This same transition model drives the real ARC environment and blind policies.
# Visual interpolation shows each committed move without changing the rule state.
# SRP/DRY check: Pass — existing anchor games build bridges or alter scalar heights;
# no reusable rigid climber or swept quarter-turn model exists in those sources.
"""Span: retract, turn around the latched end, extend, and transfer the latch."""

from collections import namedtuple
from functools import lru_cache
import math

import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

ACTION_IDS = (1, 2, 3, 4, 5)
DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))
HOLDS = ((5, 72), (8, 72), (8, 68), (3, 68), (3, 64), (7, 64),
         (7, 61), (4, 61), (4, 57), (9, 57), (9, 53), (5, 53),
         (5, 48), (2, 48), (2, 44), (7, 44), (7, 40), (4, 40), (4, 35))
CHECKPOINTS = ((8, 68), (9, 53), (4, 35))
ROCKS = ((6, 66), (6, 70), (10, 66), (10, 70), (1, 66), (1, 70), (5, 66),
         (5, 70), (1, 62), (5, 62), (9, 62), (9, 66), (5, 59), (5, 63),
         (9, 59), (9, 63), (2, 59), (2, 63), (6, 59), (6, 63), (2, 55),
         (6, 55), (7, 55), (7, 59), (11, 55), (11, 59), (7, 51), (11, 51),
         (3, 51), (3, 55), (3, 46), (3, 50), (7, 46), (7, 50), (4, 46),
         (4, 50), (4, 42), (5, 42), (5, 46), (9, 42), (9, 46), (5, 38),
         (9, 38), (2, 38), (2, 42), (6, 38), (6, 42))
Pose = namedtuple("Pose", "x y direction length end")
START = Pose(5, 72, 0, 2, 0)
ENTRY_POSES = (START, Pose(8, 68, 1, 4, 0), Pose(9, 53, 1, 4, 0))
WORLD_HEIGHT, CELL = 78, 4
# Fixed cliff strata: lower y is higher on the same continuous world.
CLIFF_STRATA = ((0, 37, 5, 58, 2), (37, 46, 2, 61, 3),
                (46, 56, 5, 62, 2), (56, 66, 1, 59, 3), (66, 78, 3, 61, 2))


def tip(pose):
    dx, dy = DIRECTIONS[pose.direction]
    return pose.x + dx * pose.length, pose.y + dy * pose.length


def blocked(x, y):
    return x < 1 or x > 13 or y < 31 or y > 75 or (x, y) in ROCKS


def straight_clear(pose, length):
    dx, dy = DIRECTIONS[pose.direction]
    return all(not blocked(pose.x + dx * distance, pose.y + dy * distance)
               for distance in range(1, length + 1))


def swept_blocker(pose, turn):
    """Return the first protrusion in the complete swept quarter-circle sector.

    Rocks and the rod live on a lattice. A rock occupies one collision point;
    drawing leaves a gap around its edges so this convention stays visible.
    """
    old = DIRECTIONS[pose.direction]
    new = DIRECTIONS[(pose.direction + turn) % 4]
    for dy in range(-pose.length, pose.length + 1):
        for dx in range(-pose.length, pose.length + 1):
            if not 0 < dx * dx + dy * dy <= pose.length * pose.length:
                continue
            if dx * old[0] + dy * old[1] < 0 or dx * new[0] + dy * new[1] < 0:
                continue
            if blocked(pose.x + dx, pose.y + dy):
                return pose.x + dx, pose.y + dy
    return None


@lru_cache(maxsize=None)
def transition(pose, action):
    if action in (1, 2):
        turn = -1 if action == 1 else 1
        if swept_blocker(pose, turn) is None:
            return pose._replace(direction=(pose.direction + turn) % 4)
    elif action == 3 and pose.length > 2:
        return pose._replace(length=pose.length - 1)
    elif action == 4 and pose.length < 5 and straight_clear(pose, pose.length + 1):
        return pose._replace(length=pose.length + 1)
    elif action == 5 and tip(pose) in HOLDS:
        x, y = tip(pose)
        return Pose(x, y, (pose.direction + 2) % 4, pose.length, 1 - pose.end)
    return pose


def reached(pose, checkpoint):
    return (pose.x, pose.y) == CHECKPOINTS[checkpoint]


def camera_top(pose):
    midpoint_y = (pose.y + tip(pose)[1]) * CELL // 2 + 2
    return max(0, min(WORLD_HEIGHT * CELL - 64, midpoint_y - 32))


class SpanDisplay(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    @staticmethod
    def rect(image, x, y, width, height, color):
        left, top, right, bottom = max(0, x), max(0, y), min(64, x + width), min(64, y + height)
        if right > left and bottom > top:
            image[top:bottom, left:right] = color

    def draw_animation(self, image, animation):
        """Draw one physical motion while the committed rule pose stays untouched."""
        before, after = animation["before"], animation["after"]
        fraction = min(1, animation["index"] / animation["body_frames"])
        fraction = fraction * fraction * (3 - 2 * fraction)
        angle = before.direction * math.pi / 2
        length = before.length
        if animation["action"] in (1, 2):
            turn = -1 if animation["action"] == 1 else 1
            angle += turn * fraction * math.pi / 2
        elif animation["action"] in (3, 4):
            length += (after.length - before.length) * fraction
        direction_x, direction_y = math.cos(angle), math.sin(angle)
        x0, y0 = before.x * CELL + 2, before.y * CELL + 2 - self.game.view_y
        x1 = round(x0 + direction_x * length * CELL)
        y1 = round(y0 + direction_y * length * CELL)
        # A dense centerline keeps the diagonal rod connected at this resolution.
        samples = max(abs(x1 - x0), abs(y1 - y0)) * 2 + 1
        points = [(round(x0 + (x1 - x0) * number / samples),
                   round(y0 + (y1 - y0) * number / samples))
                  for number in range(samples + 1)]
        for x, y in points:
            self.rect(image, x - 1, y - 1, 3, 3, 4)
        for x, y in points:
            self.rect(image, x, y, 1, 1, 12)
        for distance in range(1, math.ceil(length)):
            self.rect(image, round(x0 + direction_x * distance * CELL),
                      round(y0 + direction_y * distance * CELL), 1, 1, 0)
        colors = (9, 14)
        self.rect(image, x0 - 2, y0 - 2, 5, 5, colors[before.end])
        self.rect(image, x1 - 2, y1 - 2, 5, 5, colors[1 - before.end])
        if animation["action"] == 5:
            # Receiving jaws close first. Only then does the old grip open.
            receiving_gap = 3 + round(3 * max(0, 1 - fraction * 2))
            self.rect(image, x1 - receiving_gap, y1 - 3, 2, 7, 0)
            self.rect(image, x1 + receiving_gap - 1, y1 - 3, 2, 7, 0)
            release = max(0, fraction * 2 - 1)
            old_gap, old_height = 3 + round(3 * release), round(7 * (1 - release))
            self.rect(image, x0 - old_gap, y0 - old_height // 2, 2, old_height, 0)
            self.rect(image, x0 + old_gap - 1, y0 - old_height // 2, 2, old_height, 0)
            if fraction >= 0.5:
                self.rect(image, x1 - 1, y1 - 1, 3, 3, 5)
                self.rect(image, x0, y0, 1, 1, 0)
            else:
                self.rect(image, x0 - 1, y0 - 1, 3, 3, 5)
                self.rect(image, x1, y1, 1, 1, 0)
        else:
            self.rect(image, x0 - 3, y0 - 3, 2, 7, 0)
            self.rect(image, x0 + 2, y0 - 3, 2, 7, 0)
            self.rect(image, x0 - 1, y0 - 1, 3, 3, 5)
            self.rect(image, x1, y1, 1, 1, 0)

    def render_interface(self, frame):
        game = self.game
        image = np.full((64, 64), 10, dtype=np.int8)
        top = game.view_y
        # Cliff layers stay in world coordinates when the body and camera move.
        for low, high, left, right, color in CLIFF_STRATA:
            self.rect(image, left, low * CELL - top, right - left, (high - low) * CELL, color)
            self.rect(image, left + 1, low * CELL - top, right - left - 2, 1, 1)
        for world_y in range(34, 77, 7):
            left = 2 + (world_y % 3) * 2
            self.rect(image, left, world_y * CELL - top, 8, 1, 4)
            self.rect(image, 51, (world_y + 2) * CELL - top, 7, 1, 4)
        for x, y in ROCKS:
            xx, yy = x * CELL + 2, y * CELL + 2 - top
            self.rect(image, xx - 1, yy - 1, 4, 4, 5)
            self.rect(image, xx - 1, yy - 1, 3, 3, 4)
            self.rect(image, xx - 1, yy - 1, 2, 1, 1)
        for x, y in HOLDS:
            xx, yy = x * CELL + 2, y * CELL + 2 - top
            self.rect(image, xx - 2, yy - 2, 5, 5, 0)
            self.rect(image, xx - 1, yy - 1, 3, 3, 4)
            self.rect(image, xx, yy, 1, 1, 0)
        # Camps are physical landmark pennants, not separate puzzle screens.
        for checkpoint, (x, y) in enumerate(CHECKPOINTS):
            xx, yy = x * CELL + 2, y * CELL + 2 - top
            color = 14 if checkpoint < game._score else 12
            self.rect(image, xx + 3, yy - 7, 1, 8, 0)
            self.rect(image, xx + 4, yy - 7, 5, 3, color)
        if game.animation is not None and game.animation["index"] < game.animation["body_frames"]:
            self.draw_animation(image, game.animation)
        else:
            # Preserve the original renderer exactly at every settled pose.
            x0, y0 = game.pose.x * CELL + 2, game.pose.y * CELL + 2 - top
            end_x, end_y = tip(game.pose)
            x1, y1 = end_x * CELL + 2, end_y * CELL + 2 - top
            self.rect(image, min(x0, x1) - 1, min(y0, y1) - 1,
                      abs(x1 - x0) + 3, abs(y1 - y0) + 3, 4)
            self.rect(image, min(x0, x1), min(y0, y1), abs(x1 - x0) + 1, abs(y1 - y0) + 1, 12)
            dx, dy = DIRECTIONS[game.pose.direction]
            for distance in range(1, game.pose.length):
                self.rect(image, x0 + dx * distance * CELL, y0 + dy * distance * CELL, 1, 1, 0)
            # Physical ends keep their identities; the large jaws mark the current latch.
            colors = (9, 14)
            self.rect(image, x0 - 2, y0 - 2, 5, 5, colors[game.pose.end])
            self.rect(image, x1 - 2, y1 - 2, 5, 5, colors[1 - game.pose.end])
            self.rect(image, x0 - 3, y0 - 3, 2, 7, 0)
            self.rect(image, x0 + 2, y0 - 3, 2, 7, 0)
            self.rect(image, x0 - 1, y0 - 1, 3, 3, 5)
            self.rect(image, x1, y1, 1, 1, 0)
        if game.refusal is not None:
            xx, yy = game.refusal[0] * CELL + 2, game.refusal[1] * CELL + 2 - top
            size = 3 + 2 * game.pulse
            self.rect(image, xx - size // 2, yy - size // 2, size, size, 8)
        return image


class Sp01(ARCBaseGame):
    def __init__(self):
        self.display = SpanDisplay(self)
        self.pose, self.view_y = START, camera_top(START)
        self.entries = {index: pose for index, pose in enumerate(ENTRY_POSES)}
        self.pending_entry = None
        self.refusal, self.pulse = None, 0
        self.animation = None
        levels = [Level(sprites=[], grid_size=(64, 64), data={"checkpoint": index},
                        name=name) for index, name in enumerate(("Foothold", "Overhang", "Summit"))]
        super().__init__("sp01", levels, Camera(0, 0, 64, 64, 10, 10, [self.display]),
                         False, len(levels), list(ACTION_IDS))

    def on_set_level(self, level):
        index = level.get_data("checkpoint")
        self.animation = None
        if self.pending_entry == index:
            # next_level already changed the score. The physical pose/camera stay put.
            self.pending_entry = None
            return
        if index == 0:
            self.entries = {number: pose for number, pose in enumerate(ENTRY_POSES)}
        self.pose = self.entries[index]
        self.view_y = camera_top(self.pose)
        self.refusal, self.pulse = None, 0

    def handle_reset(self):
        # Base reset treats action_count==0 as a full restart. Here a camp is a real
        # save point, including on the very first action after reaching that camp.
        if self._score == len(CHECKPOINTS):
            self.full_reset()
        else:
            self.level_reset()

    def step(self):
        action = self.action.id.value
        if action == 0:
            self.complete_action()
            return
        if self.animation is not None:
            self.advance_animation()
            return
        before = self.pose
        self.pose = transition(before, action)
        self.pulse ^= 1
        self.refusal = None
        if self.pose == before:
            self.refusal = (swept_blocker(before, -1 if action == 1 else 1)
                            if action in (1, 2) else None) or tip(before)
            self.finish_action()
            return
        body_frames = 18 if action in (1, 2) else 10 if action == 5 else 6
        target_camera = camera_top(self.pose)
        pan_frames = (6 if action in (1, 2) else 4) if target_camera != self.view_y else 0
        self.animation = dict(before=before, after=self.pose, action=action, index=0,
                              body_frames=body_frames, pan_frames=pan_frames,
                              old_camera=self.view_y, target_camera=target_camera)
        self.advance_animation()

    def advance_animation(self):
        """Advance only visual state; rule transitions are committed once in step."""
        animation = self.animation
        animation["index"] += 1
        if animation["index"] > animation["body_frames"]:
            fraction = (animation["index"] - animation["body_frames"]) / animation["pan_frames"]
            fraction = fraction * fraction * (3 - 2 * fraction)
            self.view_y = round(animation["old_camera"] + fraction *
                                (animation["target_camera"] - animation["old_camera"]))
        if animation["index"] == animation["body_frames"] + animation["pan_frames"]:
            self.view_y = animation["target_camera"]
            self.animation = None
            self.finish_action()

    def finish_action(self):
        # A checkpoint is credited only after its visible motion has finished.
        if reached(self.pose, self.level_index):
            if self.level_index < len(CHECKPOINTS) - 1:
                self.entries[self.level_index + 1] = self.pose
                self.pending_entry = self.level_index + 1
            self.next_level()
        self.complete_action()

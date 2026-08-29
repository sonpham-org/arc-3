"""Deterministic qualification for GPT-authored q001 Quiet Field.

The planner lives outside the environment source so the game artifact does not
ship its solution. It searches the authored state machine, then replays every
action through arcengine and verifies the rendered frames and level transitions.
"""

from __future__ import annotations

from collections import deque
import hashlib
import importlib.util
import json
from pathlib import Path
import random

import numpy as np
from arcengine import ActionInput, GameAction, GameState


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "static" / "games" / "src" / "q001-v1" / "q001.py"
WIN_RECORDING = ROOT / "research" / "recordings" / "q001-v1-win.json"
LOSS_RECORDING = ROOT / "research" / "recordings" / "q001-v1-loss.json"


def load_game_module():
    spec = importlib.util.spec_from_file_location("q001_qualification", SOURCE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def abstract_start(level):
    return (
        tuple(level["eye"]),
        tuple(bool(item["closed"]) for item in level["shutters"]),
        tuple((int(orb["start"]), orb["kind"]) for orb in level["orbs"]),
    )


def is_visible(module, level, state, cell):
    eye, shutters, _orbs = state
    opaque = set(level["walls"])
    opaque.update(
        tuple(item["cell"])
        for item, closed in zip(level["shutters"], shutters)
        if closed
    )
    return not any(point in opaque for point in list(module._bresenham(eye, cell))[1:-1])


def solved(level, state):
    return all(index == authored["target"] for (index, _kind), authored in zip(state[2], level["orbs"]))


def transitions(module, level, state):
    eye, shutters, orbs = state

    for aid, (dx, dy) in module.DIRS.items():
        moved = (
            max(0, min(module.BOARD_W - 1, eye[0] + dx)),
            max(0, min(module.BOARD_H - 1, eye[1] + dy)),
        )
        if moved != eye:
            yield (aid, {}), (moved, shutters, orbs)

    for index, item in enumerate(level["shutters"]):
        changed = list(shutters)
        changed[index] = not changed[index]
        cell = item["cell"]
        data = {
            "x": module.OX + cell[0] * module.CELL + module.CELL // 2,
            "y": module.OY + cell[1] * module.CELL + module.CELL // 2,
        }
        yield (6, data), (eye, tuple(changed), orbs)

    advanced = []
    for (index, kind), authored in zip(orbs, level["orbs"]):
        pos = authored["path"][index]
        visible = is_visible(module, level, state, pos)
        active = (kind == module.K_BOLD and visible) or (kind == module.K_SHY and not visible)
        if active:
            index = (index + 1) % len(authored["path"])
            if index in authored["flips"]:
                kind = module.K_BOLD if kind == module.K_SHY else module.K_SHY
        advanced.append((index, kind))
    next_state = (eye, shutters, tuple(advanced))
    if next_state != state:
        yield (5, {}), next_state


def find_plan(module, level):
    start = abstract_start(level)
    queue = deque([start])
    parent = {start: None}
    parent_action = {}

    terminal = None
    while queue:
        state = queue.popleft()
        if solved(level, state):
            terminal = state
            break
        for action, next_state in transitions(module, level, state):
            if next_state in parent:
                continue
            parent[next_state] = state
            parent_action[next_state] = action
            queue.append(next_state)

    assert terminal is not None, f"unsolved authored level: {level['name']}"
    plan = []
    while parent[terminal] is not None:
        plan.append(parent_action[terminal])
        terminal = parent[terminal]
    plan.reverse()
    assert len(plan) <= level["budget"], (level["name"], len(plan), level["budget"])
    return plan


def assert_frame(frame_data):
    assert frame_data.frame
    grid = np.asarray(frame_data.frame[-1])
    assert grid.shape == (64, 64)
    assert np.issubdtype(grid.dtype, np.integer)
    assert int(grid.min()) >= 0
    assert int(grid.max()) <= 15


def test_all_known_win_plans_replay():
    module = load_game_module()
    plans = [find_plan(module, level) for level in module.LEVELS]

    game = module.Q001()
    frame = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
    assert_frame(frame)

    for level_index, plan in enumerate(plans):
        assert game.level_index == level_index
        for aid, data in plan:
            frame = game.perform_action(
                ActionInput(id=GameAction.from_id(aid), data=data),
                raw=True,
            )
            assert_frame(frame)

        if level_index < len(plans) - 1:
            assert game.level_index == level_index + 1
            assert frame.state == GameState.NOT_FINISHED
        else:
            assert frame.state == GameState.WIN
            assert frame.levels_completed == len(module.LEVELS)


def test_seeded_action_fuzz_has_valid_frames():
    module = load_game_module()
    rng = random.Random(1001)
    game = module.Q001()
    frame = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
    assert_frame(frame)

    for _ in range(5000):
        if frame.state in (GameState.GAME_OVER, GameState.WIN):
            frame = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
        aid = rng.choice([1, 2, 3, 4, 5, 6])
        data = {}
        if aid == 6:
            data = {"x": rng.randrange(64), "y": rng.randrange(64)}
        frame = game.perform_action(
            ActionInput(id=GameAction.from_id(aid), data=data),
            raw=True,
        )
        assert_frame(frame)


def _decode_recorded_action(encoded):
    aid = int(encoded[0])
    data = {}
    if aid == 6:
        data = {"x": int(encoded[1]), "y": int(encoded[2])}
    return ActionInput(id=GameAction.from_id(aid), data=data)


def test_committed_recordings_replay_exactly():
    module = load_game_module()
    win = json.loads(WIN_RECORDING.read_text(encoding="utf-8"))
    loss = json.loads(LOSS_RECORDING.read_text(encoding="utf-8"))

    game = module.Q001()
    frame = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
    for level in win["levels"]:
        for encoded in level["actions"]:
            frame = game.perform_action(_decode_recorded_action(encoded), raw=True)
        digest = hashlib.sha256(np.asarray(frame.frame[-1]).tobytes()).hexdigest()
        assert digest == level["post_transition_frame_sha256"]
    assert frame.state == GameState.WIN

    game = module.Q001()
    frame = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
    for encoded in loss["actions"]:
        frame = game.perform_action(_decode_recorded_action(encoded), raw=True)
    assert frame.state.value == loss["expected_state"]

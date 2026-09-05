"""Qualify and materialize Cycle 019: q051-v2 and q038-v3.

The qualifier independently rediscovers shortest paths with BFS, proves a
recoverable error and finite loss on every level, evaluates the exact uniform
random policy, checks pure/runtime parity and settled 5--9-frame animation,
fuzzes both games, and deterministically rebuilds recordings and thumbnails.
"""

from __future__ import annotations

import argparse
from collections import deque
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys

import numpy as np
from arcengine import ActionInput, GameAction, GameState
from PIL import Image


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PALETTE = np.asarray([
    (255, 255, 255), (204, 204, 204), (153, 153, 153), (102, 102, 102),
    (51, 51, 51), (0, 0, 0), (229, 58, 163), (255, 123, 204),
    (249, 60, 49), (30, 147, 255), (136, 216, 241), (255, 220, 0),
    (255, 133, 27), (146, 18, 49), (79, 204, 48), (163, 86, 214),
], dtype=np.uint8)

GAMES = {
    "q051": {
        "version": "v2", "class": "Q051", "terminal": 4, "seals": 3,
        "seed": 51019,
        "sha": "451849fa48adc9fa6835b453d3cfe32b877521c5ce5068069c7474e4d054d6f7",
    },
    "q038": {
        "version": "v3", "class": "Q038", "terminal": 6, "seals": 5,
        "seed": 38019,
        "sha": "240a17faa95341e4b8b67aee8e6f099d1b4e69a50eb6c6703a938efaf1032ef6",
    },
}

EXPECTED = {
    "q051": (
        ((6, 13, 32), (6, 37, 26), 5),
        ((6, 8, 30), (6, 25, 18), (6, 47, 22), (6, 8, 38),
         (6, 25, 50), (6, 47, 46), (6, 11, 35), (6, 39, 35), 5),
        ((6, 8, 30), (6, 25, 18), (6, 47, 22), 3, (6, 8, 38),
         (6, 25, 50), (6, 47, 46), 5),
        ((6, 8, 34), (6, 23, 24), (6, 11, 41), (6, 35, 38),
         (6, 47, 22), (6, 38, 43), 5),
        ((6, 8, 34), (6, 11, 41), (6, 38, 43), 3, (6, 23, 24),
         3, (6, 35, 38), (6, 47, 22), 5),
        ((6, 10, 30), (6, 36, 25), (6, 10, 39), (6, 36, 43),
         4, (6, 36, 17), (6, 36, 50), 5),
        ((6, 8, 34), (6, 11, 41), (6, 35, 38), (6, 38, 43),
         4, (6, 23, 24), (6, 47, 22), 5),
        ((6, 7, 30), (6, 7, 39), (6, 24, 49), (6, 48, 19),
         (6, 48, 45), 3, (6, 24, 14), 3, (6, 18, 22), (6, 45, 22), 5),
    ),
    "q038": (
        (5, 5, 6),
        (5, 1, 5, 1, 5, 1, 3, 5, 6),
        (5, 5, 4, 5, 3, 5, 1, 5, 6),
        (1, 4, 5, 1, 5, 3, 5, 3, 5, 6),
        (5, 1, 5, 5, 1, 5, 5, 3, 5, 6),
        (5, 4, 5, 4, 5, 1, 5, 1, 5, 6),
        (5, 4, 5, 3, 5, 4, 5, 6),
        (5, 4, 4, 5, 3, 5, 4, 4, 5, 3, 3, 3, 5, 4, 4, 5, 1, 4, 5, 5, 6),
    ),
}


def paths(code):
    spec = GAMES[code]
    game_id = f"{code}-{spec['version']}"
    return (
        game_id,
        ROOT / "docs" / "static" / "games" / "src" / game_id / f"{code}.py",
        ROOT / "research" / "games" / f"{game_id}.json",
    )


def load(code):
    _game_id, source, _metadata = paths(code)
    spec = importlib.util.spec_from_file_location(f"{code}_cycle019", source)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def actions(code, module, level):
    return module.actions_for_level(level) if code == "q051" else (1, 3, 4, 5, 6)


def terminal(code, state):
    return state[GAMES[code]["terminal"]]


def pure_step(module, level, state, budget, action):
    after = module.transition(level, state, action)
    cost = module.action_cost(state, after)
    assert cost in (0, 1)
    return after, budget - cost


def reconstruct(parent, edge, node):
    plan = []
    while parent[node] is not None:
        plan.append(edge[node]); node = parent[node]
    return list(reversed(plan))


def find_plan(code, module, level):
    root = (module.start_state(level), level["budget"])
    queue = deque([root]); parent = {root: None}; edge = {}
    while queue:
        state, budget = queue.popleft()
        if terminal(code, state) == 2:
            return reconstruct(parent, edge, (state, budget)), len(parent)
        if terminal(code, state) or budget < 0:
            continue
        for action in actions(code, module, level):
            after, left = pure_step(module, level, state, budget, action)
            node = (after, left)
            if after == state or left < 0 or node in parent:
                continue
            parent[node] = (state, budget); edge[node] = action; queue.append(node)
    return None, len(parent)


def execute(code, module, level, plan):
    state = module.start_state(level); budget = level["budget"]
    for action in plan:
        state, budget = pure_step(module, level, state, budget, action)
    return state, budget


def recovery_plan(code, module, level, plan):
    if code == "q051":
        mistake = module.edge_action(level, len(level["edges"]) - 1)
        return [mistake, mistake, *plan]
    return [6, *plan]


def loss_plan(code):
    return [5, 5] if code == "q051" else [6, 6, 6]


def exact_random(code, module, level):
    available = actions(code, module, level)

    @lru_cache(None)
    def probability(state, budget):
        if terminal(code, state) == 2:
            return 1.0
        if terminal(code, state) == 3 or budget < 0:
            return 0.0
        outcomes = []
        for action in available:
            after, left = pure_step(module, level, state, budget, action)
            if after == state:
                continue
            outcomes.append(probability(after, left))
        return sum(outcomes) / len(outcomes) if outcomes else 0.0

    value = probability(module.start_state(level), level["budget"])
    return value, probability.cache_info().currsize


def action_input(action):
    if isinstance(action, (tuple, list)):
        return ActionInput(id=GameAction.from_id(int(action[0])),
                           data={"x": int(action[1]), "y": int(action[2])})
    return ActionInput(id=GameAction.from_id(int(action)))


def digest_grid(grid):
    return hashlib.sha256(np.asarray(grid).tobytes()).hexdigest()


def assert_frames(game, frame, action, metrics):
    assert frame.frame
    hashes = []
    for item in frame.frame:
        grid = np.asarray(item)
        assert grid.shape == (64, 64)
        assert np.issubdtype(grid.dtype, np.integer)
        assert 0 <= int(grid.min()) <= int(grid.max()) <= 15
        hashes.append(digest_grid(grid))
    assert 5 <= len(hashes) <= 9, (action, len(hashes))
    assert len(set(hashes)) >= 2, (action, len(set(hashes)))
    stable = game.camera.render(game.current_level._sprites)
    assert np.array_equal(np.asarray(frame.frame[-1]), np.asarray(stable)), action
    metrics["counts"].append(len(hashes)); metrics["unique"].append(len(set(hashes)))
    return tuple(hashes)


def runtime_state(code, game):
    if code == "q051":
        return game.state
    return (game.values, game.tide, game.cursor, game.reverse, game.stage,
            game.seals, game.terminal)


def replay_campaign(code, module, plans, metrics):
    game = getattr(module, GAMES[code]["class"])()
    reset = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
    reset_digest = digest_grid(reset.frame[-1]); levels = []; transcript = []
    for level_index, (level, plan) in enumerate(zip(module.LEVELS, plans)):
        encoded = []
        for action in plan:
            before = runtime_state(code, game); before_budget = game.budget_left
            after, left = pure_step(module, level, before, before_budget, action)
            frame = game.perform_action(action_input(action), raw=True)
            hashes = assert_frames(game, frame, action, metrics)
            if terminal(code, after) == 2:
                assert frame.levels_completed == level_index + 1
            elif terminal(code, after) == 3:
                assert frame.state == GameState.GAME_OVER
            else:
                assert runtime_state(code, game) == after
                assert game.budget_left == left
            encoded.append(list(action) if isinstance(action, tuple) else [action])
            transcript.append((level_index + 1, action, hashes))
        levels.append({"level": level_index + 1, "actions": encoded,
                       "post_transition_frame_sha256": digest_grid(frame.frame[-1])})
    assert frame.state == GameState.WIN
    return reset, reset_digest, levels, frame, transcript


def replay_single_level(code, module, level_index, plan, metrics):
    game = getattr(module, GAMES[code]["class"])()
    game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
    if level_index:
        game.set_level(level_index)
    frame = None
    for action in plan:
        frame = game.perform_action(action_input(action), raw=True)
        assert_frames(game, frame, action, metrics)
    return game, frame


def fuzz(code, module):
    rng = random.Random(GAMES[code]["seed"])
    game = getattr(module, GAMES[code]["class"])()
    frame = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
    resets = 0
    for _ in range(1000):
        if frame.state in (GameState.GAME_OVER, GameState.WIN):
            frame = game.perform_action(ActionInput(id=GameAction.RESET), raw=True); resets += 1
        if code == "q051" and rng.random() < 0.68:
            action = (6, rng.randrange(64), rng.randrange(64))
        else:
            action = rng.choice((1, 2, 3, 4, 5, 6))
        frame = game.perform_action(action_input(action), raw=True)
        assert frame.frame and len(frame.frame) <= 9
        grid = np.asarray(frame.frame[-1])
        assert grid.shape == (64, 64) and 0 <= int(grid.min()) <= int(grid.max()) <= 15
    return resets


def invariants(code, module):
    rng = random.Random(GAMES[code]["seed"] + 7)
    for level in module.LEVELS:
        state = module.start_state(level)
        total = sum(level["stock"]) if code == "q051" else sum(level["start"])
        for _ in range(1000):
            action = rng.choice(actions(code, module, level))
            state = module.transition(level, state, action)
            if code == "q051":
                assert sum(state[2]) + sum(value != 0 for value in state[1]) <= total
                assert all(0 <= value <= 3 for value in state[1])
            else:
                assert sum(state[0]) == total
                assert all(0 <= value <= cap for value, cap in zip(state[0], level["cap"]))
                assert 0 <= state[2] < len(level["edges"])
            if terminal(code, state):
                state = module.start_state(level)


def write_artifacts(code, reset, levels, loss_actions, loss_digest):
    game_id, _source, _metadata = paths(code)
    win = {"schema_version": 1, "game_id": game_id, "expected_state": "WIN", "levels": levels}
    encoded_loss = [list(action) if isinstance(action, tuple) else [action] for action in loss_actions]
    loss = {"schema_version": 1, "game_id": game_id, "expected_state": "GAME_OVER",
            "actions": encoded_loss, "terminal_frame_sha256": loss_digest}
    record_dir = ROOT / "research" / "recordings"
    (record_dir / f"{game_id}-win.json").write_text(json.dumps(win, indent=2) + "\n", encoding="utf-8")
    (record_dir / f"{game_id}-loss.json").write_text(json.dumps(loss, indent=2) + "\n", encoding="utf-8")
    image = Image.fromarray(PALETTE[np.asarray(reset.frame[-1])].astype(np.uint8), mode="RGB")
    image.save(ROOT / "docs" / "static" / "img" / "games" / f"{game_id}.png", optimize=True)


def qualify(code, write=False, probabilities=True):
    game_id, source, metadata_path = paths(code)
    assert sha(source) == GAMES[code]["sha"]
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["artifacts"]["source_sha256"] == GAMES[code]["sha"]
    module = load(code); assert len(module.LEVELS) == 8
    plans, states = [], []
    for index, level in enumerate(module.LEVELS):
        plan, count = find_plan(code, module, level)
        assert plan is not None and tuple(plan) == EXPECTED[code][index], (code, index + 1, plan)
        won, left = execute(code, module, level, plan)
        assert terminal(code, won) == 2 and left >= 0
        recovery = recovery_plan(code, module, level, plan)
        recovered, recovery_left = execute(code, module, level, recovery)
        assert terminal(code, recovered) == 2 and recovery_left >= 0
        lost, _ = execute(code, module, level, loss_plan(code))
        assert terminal(code, lost) == 3
        plans.append(plan); states.append(count)
    probs = []; probability_states = []
    if probabilities:
        for level in module.LEVELS:
            value, count = exact_random(code, module, level)
            probs.append(value); probability_states.append(count)
        assert all(value < 1 / 10_000 for value in probs[1:]), probs
    metrics = {"counts": [], "unique": []}
    reset, reset_digest, levels, final, first = replay_campaign(code, module, plans, metrics)
    _reset2, reset_digest2, levels2, final2, second = replay_campaign(code, module, plans, metrics)
    assert reset_digest2 == reset_digest and levels2 == levels and second == first
    assert digest_grid(final2.frame[-1]) == digest_grid(final.frame[-1])
    campaign_unique = len({item for _level, _action, hashes in first for item in hashes})
    for level_index, (level, plan) in enumerate(zip(module.LEVELS, plans)):
        game, frame = replay_single_level(code, module, level_index,
                                          recovery_plan(code, module, level, plan), metrics)
        if level_index == 7:
            assert frame.state == GameState.WIN
        else:
            assert game.level_index == level_index + 1
    loss_actions = loss_plan(code)
    loss_game, loss_frame = replay_single_level(code, module, 0, loss_actions, metrics)
    assert loss_frame.state == GameState.GAME_OVER
    loss_digest = digest_grid(loss_frame.frame[-1])
    reset_after_loss = loss_game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
    assert digest_grid(reset_after_loss.frame[-1]) == reset_digest
    invariants(code, module); fuzz_resets = fuzz(code, module)
    if write:
        write_artifacts(code, reset, levels, loss_actions, loss_digest)
    result = {
        "game_id": game_id, "source_sha256": GAMES[code]["sha"],
        "plans": [len(plan) for plan in plans], "search_states": states,
        "probabilities": probs, "probability_states": probability_states,
        "max_random_l2_plus": max(probs[1:]) if probs else None,
        "campaign_unique_frames": campaign_unique,
        "frame_count_range": [min(metrics["counts"]), max(metrics["counts"])],
        "unique_frame_range": [min(metrics["unique"]), max(metrics["unique"])],
        "fuzz_resets": fuzz_resets,
    }
    print(json.dumps(result, indent=2)); return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-artifacts", action="store_true")
    parser.add_argument("--skip-probabilities", action="store_true")
    parser.add_argument("--game", choices=tuple(GAMES))
    args = parser.parse_args()
    selected = (args.game,) if args.game else tuple(GAMES)
    for code in selected:
        qualify(code, write=args.write_artifacts, probabilities=not args.skip_probabilities)


if __name__ == "__main__":
    main()

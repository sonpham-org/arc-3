"""Independent qualification and artifact builder for q031-v2 and q129-v3.

The qualifier rediscovers shortest win and one-error recovery plans with BFS,
evaluates the exact finite-budget uniform random policy, verifies pure/runtime
parity and animation settlement, and deterministically rebuilds recordings and
thumbnails.  q129 night states are quotiented only over fields that its night
transition never reads; this is an exact Markov reduction, not sampling.
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
    "q031": {
        "version": "v2", "class": "Q031", "actions": (1, 2, 3, 4, 5, 6),
        "terminal_index": 6, "recovery_index": 5, "seed": 31018,
        "source_sha256": "27b862cb5c13bb2d3082412c91589495a51ca7989703b713ff348028330ed581",
    },
    "q129": {
        "version": "v3", "class": "Q129", "actions": (1, 2, 3, 4, 5),
        "terminal_index": 14, "recovery_index": 8, "seed": 129018,
        "source_sha256": "eda628aa3bcbc026dc9511f2df1c310d6f1e8acf348ee70227ce6438756e8717",
    },
}

# Filled after an independent BFS discovery and then treated as immutable
# expectations on all write and no-write qualification runs.
EXPECTED_PLANS = {
    "q031": (
        (5, 1, 5, 6),
        (3, 5, 2, 5, 2, 5, 6),
        (5, 2, 3, 5, 3, 5, 2, 3, 5, 3, 5, 6),
        (2, 3, 5, 3, 5, 2, 5, 6),
        (5, 2, 4, 5, 3, 5, 2, 4, 5, 3, 5, 6),
        (5, 5, 5, 2, 5, 5, 6),
        (5, 2, 4, 5, 3, 5, 2, 4, 5, 4, 5, 4, 5, 6),
        (5, 5, 1, 1, 5, 4, 5, 4, 5, 6),
    ),
    "q129": (
        (1, 4, 4, 2, 1, 5, 1, 3, 3),
        (3, 1, 3, 2, 1, 2, 1, 2, 2, 1, 4, 4, 4, 1, 4, 5, 4, 1, 4),
        (1, 3, 3, 4, 2, 2, 3, 4, 3, 4, 3, 4, 4, 4, 4, 3, 4, 5, 2, 3, 3),
        (3, 1, 3, 2, 1, 2, 1, 2, 2, 1, 4, 4, 4, 1, 4, 5, 4, 2, 4),
        (1, 3, 3, 2, 1, 2, 2, 4, 4, 4, 4, 1, 1, 5, 1, 4, 4),
        (1, 3, 3, 2, 1, 2, 1, 2, 1, 2, 2, 4, 4, 4, 4, 5, 2, 3, 3),
        (4, 3, 3, 1, 1, 4, 2, 1, 2, 1, 3, 3, 2, 1, 2, 2, 3, 5, 1, 3, 1, 3),
        (4, 1, 2, 1, 2, 1, 2, 1, 3, 1, 2, 1, 3, 3, 2, 4, 2, 3, 3, 5, 3, 3, 3),
    ),
}


def game_paths(code):
    spec = GAMES[code]
    game_id = f"{code}-{spec['version']}"
    source = ROOT / "docs" / "static" / "games" / "src" / game_id / f"{code}.py"
    metadata = ROOT / "research" / "games" / f"{game_id}.json"
    return game_id, source, metadata


def load_module(code):
    _game_id, source, _metadata = game_paths(code)
    spec = importlib.util.spec_from_file_location(f"{code}_cycle_018_qualification", source)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def terminal_of(code, state):
    return state[GAMES[code]["terminal_index"]]


def is_win(code, state):
    return terminal_of(code, state) == 2


def is_loss(code, state):
    return terminal_of(code, state) == 3


def canonical_state(code, state):
    if code != "q129" or state[0] != 1:
        return state
    # At night, attention, demonstration count, last flower, seen species,
    # and spent-tool flags are historical display data. transition() reads
    # only position, turn, guard mask, chances, free steps, refusals, terminal.
    values = list(state)
    values[3] = (0, 0, 0, 0)
    values[4] = 0
    values[5] = -1
    values[9] = 0
    values[10] = 0
    values[12] = 0
    return tuple(values)


def pure_step(code, module, level, state, budget, action):
    raw_after = module.transition(level, state, action)
    cost = module.action_cost(state, raw_after)
    assert cost in (0, 1), (code, action, cost)
    return canonical_state(code, raw_after), budget - cost


def reconstruct(parent, parent_action, terminal):
    plan = []
    while parent[terminal] is not None:
        plan.append(parent_action[terminal])
        terminal = parent[terminal]
    return list(reversed(plan))


def find_plan(code, module, level, start=None, budget=None, require_recovery=False,
              forbidden_machine=None):
    state = canonical_state(code, module.start_state(level) if start is None else start)
    left = level["budget"] if budget is None else budget
    root = (state, left)
    queue = deque([root])
    parent = {root: None}
    parent_action = {}
    while queue:
        state, left = queue.popleft()
        recovered = state[GAMES[code]["recovery_index"]] == 1
        if is_win(code, state) and (not require_recovery or recovered):
            return reconstruct(parent, parent_action, (state, left)), len(parent)
        if is_loss(code, state) or left < 0:
            continue
        for action in GAMES[code]["actions"]:
            if (forbidden_machine is not None and code == "q031" and action == 5
                    and level["ops"][state[1]] == forbidden_machine):
                continue
            after, after_left = pure_step(code, module, level, state, left, action)
            if after == state or after_left < 0:
                continue
            node = (after, after_left)
            if node not in parent:
                parent[node] = (state, left)
                parent_action[node] = action
                queue.append(node)
    return None, len(parent)


def execute_plan(code, module, level, plan, start=None, budget=None):
    state = canonical_state(code, module.start_state(level) if start is None else start)
    left = level["budget"] if budget is None else budget
    for action in plan:
        state, left = pure_step(code, module, level, state, left, action)
    return state, left


def exact_random_probability(code, module, level):
    actions = GAMES[code]["actions"]

    @lru_cache(None)
    def probability(state, budget):
        if is_win(code, state):
            return 1.0
        if is_loss(code, state) or budget < 0:
            return 0.0
        outcomes = []
        for action in actions:
            after, after_budget = pure_step(code, module, level, state, budget, action)
            if after == state:
                continue
            outcomes.append(probability(after, after_budget))
        return sum(outcomes) / len(outcomes) if outcomes else 0.0

    start = canonical_state(code, module.start_state(level))
    value = probability(start, level["budget"])
    return value, probability.cache_info().currsize


def find_recovery_plan(code, module, level, win_plan):
    if code == "q031":
        start = module.start_state(level)
        rejected, left = pure_step(code, module, level, start, level["budget"], 6)
        assert rejected[GAMES[code]["recovery_index"]] == 1
        tail, states = find_plan(code, module, level, start=rejected, budget=left)
        assert tail is not None
        return [6] + tail, states

    state = canonical_state(code, module.start_state(level))
    left = level["budget"]
    prefix = []
    for action in win_plan:
        state, left = pure_step(code, module, level, state, left, action)
        prefix.append(action)
        if state[0] == 1:
            break
    assert state[0] == 1, level["name"]
    tail, states = find_plan(code, module, level, start=state, budget=left,
                             require_recovery=True)
    assert tail is not None
    return prefix + tail, states


def discover(code, module, probabilities=True):
    assert len(module.LEVELS) == 8
    result = {"plans": [], "recoveries": [], "losses": [], "search_states": [],
              "probabilities": [], "probability_states": [], "remaining_budget": []}
    for index, level in enumerate(module.LEVELS):
        plan, states = find_plan(code, module, level)
        assert plan is not None, (code, index + 1, states)
        expected = EXPECTED_PLANS[code]
        if expected:
            assert tuple(plan) == expected[index], (code, index + 1, plan)
        won, left = execute_plan(code, module, level, plan)
        assert is_win(code, won) and left >= 0

        recovery, recovery_states = find_recovery_plan(code, module, level, plan)
        recovered, recovery_left = execute_plan(code, module, level, recovery)
        assert is_win(code, recovered) and recovery_left >= 0

        loss = [6, 6] if code == "q031" else [5, 5, 5]
        lost, _loss_left = execute_plan(code, module, level, loss)
        assert is_loss(code, lost), (code, index + 1, lost)

        if probabilities:
            probability, probability_states = exact_random_probability(code, module, level)
        else:
            probability, probability_states = None, None
        result["plans"].append(plan)
        result["recoveries"].append(recovery)
        result["losses"].append(loss)
        result["search_states"].append(states)
        result["probabilities"].append(probability)
        result["probability_states"].append(probability_states)
        result["remaining_budget"].append(left)
    if probabilities:
        assert all(value < 1 / 10_000 for value in result["probabilities"][1:]), result["probabilities"]
    return result


def assert_frame(frame_data):
    assert frame_data.frame
    for item in frame_data.frame:
        grid = np.asarray(item)
        assert grid.shape == (64, 64), grid.shape
        assert np.issubdtype(grid.dtype, np.integer), grid.dtype
        assert 0 <= int(grid.min()) <= int(grid.max()) <= 15


def digest_grid(grid):
    return hashlib.sha256(np.asarray(grid).tobytes()).hexdigest()


def digest(frame_data):
    return digest_grid(frame_data.frame[-1])


def stable_grid(game):
    return game.camera.render(game.current_level._sprites)


def replay_action(game, action, metrics):
    frame = game.perform_action(ActionInput(id=GameAction.from_id(action)), raw=True)
    assert_frame(frame)
    hashes = tuple(digest_grid(item) for item in frame.frame)
    assert 5 <= len(hashes) <= 9, (action, len(hashes))
    assert len(set(hashes)) >= 2, (action, len(set(hashes)))
    assert np.array_equal(np.asarray(frame.frame[-1]), np.asarray(stable_grid(game))), action
    metrics["frame_counts"].append(len(hashes))
    metrics["unique_counts"].append(len(set(hashes)))
    metrics["campaign_hashes"].update(hashes)
    return frame, hashes


def assert_runtime_parity(code, game, pure_after, pure_budget, frame, level_index):
    if is_win(code, pure_after):
        assert frame.levels_completed == level_index + 1
    elif is_loss(code, pure_after):
        assert frame.state == GameState.GAME_OVER
        assert canonical_state(code, game.state) == pure_after
    else:
        assert canonical_state(code, game.state) == pure_after
        assert game.budget_left == pure_budget


def replay_campaign(code, module, data, metrics):
    game = getattr(module, GAMES[code]["class"])()
    reset = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
    assert_frame(reset)
    reset_digest = digest(reset)
    levels = []
    transcript = []
    for level_index, (level, plan) in enumerate(zip(module.LEVELS, data["plans"])):
        assert game.level_index == level_index
        encoded = []
        for action in plan:
            before = canonical_state(code, game.state)
            pure_after, pure_budget = pure_step(code, module, level, before, game.budget_left, action)
            frame, hashes = replay_action(game, action, metrics)
            assert_runtime_parity(code, game, pure_after, pure_budget, frame, level_index)
            encoded.append([action])
            transcript.append((level_index + 1, action, hashes))
        levels.append({"level": level_index + 1, "actions": encoded,
                       "post_transition_frame_sha256": digest(frame)})
    assert frame.state == GameState.WIN
    assert frame.levels_completed == len(module.LEVELS)
    return reset, reset_digest, levels, frame, transcript


def verify_recoveries(code, module, data, metrics):
    for level_index, (level, plan) in enumerate(zip(module.LEVELS, data["recoveries"])):
        game = getattr(module, GAMES[code]["class"])()
        game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
        if level_index:
            game.set_level(level_index)
        for action in plan:
            before = canonical_state(code, game.state)
            pure_after, pure_budget = pure_step(code, module, level, before, game.budget_left, action)
            frame, _hashes = replay_action(game, action, metrics)
            if is_win(code, pure_after):
                if level_index == len(module.LEVELS) - 1:
                    assert frame.state == GameState.WIN
                else:
                    assert game.level_index == level_index + 1
            else:
                assert_runtime_parity(code, game, pure_after, pure_budget, frame, level_index)


def verify_losses(code, module, data, reset_digest, metrics):
    artifact_actions = artifact_digest = None
    for level_index, (level, plan) in enumerate(zip(module.LEVELS, data["losses"])):
        game = getattr(module, GAMES[code]["class"])()
        game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
        if level_index:
            game.set_level(level_index)
        for action in plan:
            before = canonical_state(code, game.state)
            pure_after, pure_budget = pure_step(code, module, level, before, game.budget_left, action)
            frame, _hashes = replay_action(game, action, metrics)
            assert_runtime_parity(code, game, pure_after, pure_budget, frame, level_index)
        assert frame.state == GameState.GAME_OVER
        if level_index == 0:
            artifact_actions = [[action] for action in plan]
            artifact_digest = digest(frame)
            reset = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
            assert_frame(reset)
            assert digest(reset) == reset_digest
    return artifact_actions, artifact_digest


def shape_collapse(grid):
    source = np.asarray(grid)
    result = np.zeros(source.shape, dtype=np.uint8)
    result[(source == 2) | (source == 3)] = 1
    result[(source == 4) | (source == 5)] = 2
    result[source >= 6] = 3
    return result


def verify_visual_semantics(code, module):
    game = getattr(module, GAMES[code]["class"])()
    game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
    if code == "q031":
        hashes = []
        for machine in range(8):
            frame = np.full((64, 64), module.INK, dtype=np.int16)
            game.display.machine_icon(frame, (32, 32), machine, module.WHITE)
            crop = shape_collapse(frame[25:40, 24:41])
            assert np.count_nonzero(crop) >= 8
            hashes.append(digest_grid(crop))
        assert len(set(hashes)) == 8
        for level in module.LEVELS:
            assert sum(level["start"]) == sum(level["target"])
        return {"machine_shape_hashes": hashes}

    hashes = []
    for key in module.FLOWERS:
        frame = np.full((64, 64), module.PAPER, dtype=np.int16)
        game.display.flower(frame, key, (32, 32))
        crop = shape_collapse(frame[24:41, 24:41])
        assert np.count_nonzero(crop) >= 12
        hashes.append(digest_grid(crop))
    assert len(set(hashes)) == 4
    assert len({level["grid"] for level in module.LEVELS}) >= 5
    night = module.transition(module.LEVELS[-1], module.start_state(module.LEVELS[-1]), 5)
    # An unready commit changes refusal rather than entering night; derive a
    # real night state from the shortest plan's pre-terminal prefix elsewhere.
    assert night[13] == 1 and night[0] == 0
    return {"flower_shape_hashes": hashes, "distinct_topologies": len({level["grid"] for level in module.LEVELS})}


def verify_progression(code, module):
    if code == "q031":
        checks = {
            1: (module.FLUSH,), 2: (module.SLIDE,), 3: (module.SPLIT,),
            4: (module.PHASE,), 5: (module.MANIFOLD,),
            6: (module.SPLIT, module.SLIDE, module.ROTOR, module.FLUSH),
            7: (module.MANIFOLD, module.PHASE, module.ROTOR),
        }
        explored = {}
        for level_index, machines in checks.items():
            level = module.LEVELS[level_index]
            for machine in machines:
                plan, states = find_plan(code, module, level, forbidden_machine=machine)
                assert plan is None, (level_index + 1, machine, plan)
                explored[f"L{level_index + 1}:{machine}"] = states
        return explored
    assert module.LEVELS[1]["echo"]
    assert module.LEVELS[2]["fade"]
    assert module.LEVELS[3]["guards"] == 2
    assert module.LEVELS[4]["swap"]
    assert module.LEVELS[5]["dew_required"]
    assert module.LEVELS[6]["dew_required"] and module.LEVELS[6]["prism_required"]
    assert module.LEVELS[7]["dew_required"] and module.LEVELS[7]["prism_required"]
    return {"settings": "echo/fade/two-watchers/turn/dew/prism/synthesis pass"}


def verify_fuzz(code, module):
    rng = random.Random(GAMES[code]["seed"])
    game = getattr(module, GAMES[code]["class"])()
    frame = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
    resets = 0
    for _ in range(1000):
        if frame.state in (GameState.GAME_OVER, GameState.WIN):
            frame = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
            resets += 1
        action = rng.choice(GAMES[code]["actions"])
        frame = game.perform_action(ActionInput(id=GameAction.from_id(action)), raw=True)
        assert_frame(frame)
        assert len(frame.frame) <= 9
    return resets


def write_artifacts(code, reset, levels, loss_actions, loss_digest):
    game_id, _source, _metadata = game_paths(code)
    win = {"schema_version": 1, "game_id": game_id, "expected_state": "WIN", "levels": levels}
    loss = {"schema_version": 1, "game_id": game_id, "expected_state": "GAME_OVER",
            "actions": loss_actions, "terminal_frame_sha256": loss_digest}
    recordings = ROOT / "research" / "recordings"
    (recordings / f"{game_id}-win.json").write_text(json.dumps(win, indent=2) + "\n", encoding="utf-8")
    (recordings / f"{game_id}-loss.json").write_text(json.dumps(loss, indent=2) + "\n", encoding="utf-8")
    grid = np.asarray(reset.frame[-1])
    image = Image.fromarray(PALETTE[grid].astype(np.uint8), mode="RGB")
    image.save(ROOT / "docs" / "static" / "img" / "games" / f"{game_id}.png", optimize=True)
    return win, loss


def qualify(code, write=False, probabilities=True):
    game_id, source, metadata_path = game_paths(code)
    before = {source: sha256_file(source), metadata_path: sha256_file(metadata_path)}
    assert before[source] == GAMES[code]["source_sha256"], before[source]
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["artifacts"]["source_sha256"] == before[source]
    module = load_module(code)
    data = discover(code, module, probabilities=probabilities)
    progression = verify_progression(code, module)
    visual = verify_visual_semantics(code, module)
    metrics = {"frame_counts": [], "unique_counts": [], "campaign_hashes": set()}
    reset, reset_digest, levels, final, first_transcript = replay_campaign(code, module, data, metrics)
    _reset2, reset_digest2, levels2, final2, second_transcript = replay_campaign(code, module, data, metrics)
    assert reset_digest2 == reset_digest
    assert levels2 == levels
    assert second_transcript == first_transcript
    assert digest(final2) == digest(final)
    campaign_unique_frames = len({frame_hash for _level, _action, hashes in first_transcript
                                  for frame_hash in hashes})
    verify_recoveries(code, module, data, metrics)
    loss_actions, loss_digest = verify_losses(code, module, data, reset_digest, metrics)
    fuzz_resets = verify_fuzz(code, module)
    if write:
        write_artifacts(code, reset, levels, loss_actions, loss_digest)
    else:
        win_path = ROOT / "research" / "recordings" / f"{game_id}-win.json"
        loss_path = ROOT / "research" / "recordings" / f"{game_id}-loss.json"
        if win_path.exists() and loss_path.exists():
            expected_win = {"schema_version": 1, "game_id": game_id, "expected_state": "WIN", "levels": levels}
            expected_loss = {"schema_version": 1, "game_id": game_id, "expected_state": "GAME_OVER",
                             "actions": loss_actions, "terminal_frame_sha256": loss_digest}
            assert json.loads(win_path.read_text(encoding="utf-8")) == expected_win
            assert json.loads(loss_path.read_text(encoding="utf-8")) == expected_loss
    after = {path: sha256_file(path) for path in before}
    assert after == before
    result = {
        "game_id": game_id,
        "source_sha256": before[source],
        "plans": [len(plan) for plan in data["plans"]],
        "plan_actions": data["plans"],
        "recoveries": [len(plan) for plan in data["recoveries"]],
        "search_states": data["search_states"],
        "remaining_budget": data["remaining_budget"],
        "probabilities": data["probabilities"],
        "probability_states": data["probability_states"],
        "max_random_l2_plus": max(data["probabilities"][1:]) if probabilities else None,
        "campaign_unique_frames": campaign_unique_frames,
        "frame_count_range": [min(metrics["frame_counts"]), max(metrics["frame_counts"])],
        "unique_frame_range": [min(metrics["unique_counts"]), max(metrics["unique_counts"])],
        "progression": progression,
        "visual": visual,
        "fuzz_resets": fuzz_resets,
    }
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-artifacts", action="store_true")
    parser.add_argument("--skip-probabilities", action="store_true")
    parser.add_argument("--game", choices=tuple(GAMES))
    args = parser.parse_args()
    for code in ((args.game,) if args.game else GAMES):
        qualify(code, write=args.write_artifacts, probabilities=not args.skip_probabilities)


if __name__ == "__main__":
    main()

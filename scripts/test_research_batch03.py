"""Deterministic qualification and recording generation for research Batch 03."""

from __future__ import annotations
from collections import deque
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import numpy as np
from arcengine import ActionInput, GameAction, GameState

ROOT = Path(__file__).resolve().parents[1]
CODES = ["q003", "q012", "q022", "q032", "q042", "q052", "q062", "q072", "q082", "q092"]


def load(code):
    path = ROOT / "docs" / "static" / "games" / "src" / f"{code}-v1" / f"{code}.py"; spec = importlib.util.spec_from_file_location(f"{code}_batch03", path); module = importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(module); return module


def bfs(start, solved, expand):
    queue = deque([start]); parent = {start: None}; action = {}
    while queue:
        state = queue.popleft()
        if solved(state):
            out = []
            while parent[state] is not None: out.append(action[state]); state = parent[state]
            return list(reversed(out))
        for move, nxt in expand(state):
            if nxt not in parent: parent[nxt] = state; action[nxt] = move; queue.append(nxt)
    raise AssertionError("authored level is not solvable")


def plans_q003(module):
    result = []
    for level in module.LEVELS:
        walls = set(level["walls"])
        def expand(state):
            tip, trail, facing = state
            for action in module.DIRS: yield (action, {}), (tip, trail, action)
            dx, dy = module.DIRS[module.OPPOSITE[facing]]; nxt = (tip[0] + dx, tip[1] + dy)
            if 0 <= nxt[0] < module.SIZE and 0 <= nxt[1] < module.SIZE and nxt not in walls and nxt not in trail: yield (5, {}), (nxt, trail | {nxt}, facing)
        plan = bfs((level["start"], frozenset([level["start"]]), 3), lambda state: state[0] == level["goal"], expand); assert len(plan) <= level["budget"], (level["name"], len(plan)); result.append(plan)
    return result


def plans_q012(module):
    result = []
    for level in module.LEVELS:
        n = len(level["prefs"]); agent = item = 0; plan = []
        for wanted_agent in range(n):
            right = (wanted_agent - agent) % n; left = (agent - wanted_agent) % n; action = 4 if right <= left else 3; plan.extend([(action, {})] * min(right, left)); agent = wanted_agent
            wanted_item = level["prefs"][wanted_agent]; right = (wanted_item - item) % n; left = (item - wanted_item) % n; action = 2 if right <= left else 1; plan.extend([(action, {})] * min(right, left)); item = wanted_item; plan.append((5, {}))
        assert len(plan) <= level["budget"], (level["name"], len(plan)); result.append(plan)
    return result


def plans_q022(module):
    result = []
    for level in module.LEVELS:
        n = len(level["moves"])
        def expand(state):
            values, cursor = state; yield (3, {}), (values, (cursor - 1) % n); yield (4, {}), (values, (cursor + 1) % n); yield (5, {}), (module.apply(values, level["moves"][cursor]), cursor)
        plan = bfs((tuple(level["start"]), 0), lambda state: state[0] == tuple(level["target"]), expand) + [(6, {})]; assert len(plan) <= level["budget"], (level["name"], len(plan)); result.append(plan)
    return result


def plans_q032(module):
    result = []
    for level in module.LEVELS:
        n = len(level["pairs"])
        def expand(state):
            bits, cursor = state; yield (3, {}), (bits, (cursor - 1) % n); yield (4, {}), (bits, (cursor + 1) % n); a, b = level["pairs"][cursor]; yield (5, {}), (bits ^ (1 << a) ^ (1 << b), cursor)
        plan = bfs((level["start"], 0), lambda state: state[0] == level["target"], expand) + [(6, {})]; assert len(plan) <= level["budget"], (level["name"], len(plan)); result.append(plan)
    return result


def plans_q042(module):
    result = []
    for level in module.LEVELS:
        target = level["target"]; cursor = (0, 0); plan = [(6, {})]; dx, dy = target[0] - cursor[0], target[1] - cursor[1]
        plan.extend([((4 if dx > 0 else 3), {})] * abs(dx)); plan.extend([((2 if dy > 0 else 1), {})] * abs(dy))
        if level["probes"] > 1: plan.append((6, {}))
        plan.append((5, {})); assert len(plan) <= level["budget"], (level["name"], len(plan)); result.append(plan)
    return result


def plans_q052(module):
    result = []
    for level in module.LEVELS:
        n = len(level["start"]); fixed = set(level["fixed"])
        def expand(state):
            angles, cursor = state; yield (3, {}), (angles, (cursor - 1) % n); yield (4, {}), (angles, (cursor + 1) % n)
            if cursor not in fixed:
                for action, delta in ((1, -1), (2, 1)):
                    values = list(angles); values[cursor] = (values[cursor] + delta) % 4; yield (action, {}), (tuple(values), cursor)
        plan = bfs((tuple(level["start"]), 0), lambda state: module.exit_direction(state[0], level["coeff"]) == level["target"], expand) + [(5, {})]; assert len(plan) <= level["budget"], (level["name"], len(plan)); result.append(plan)
    return result


def adjacent_sort_plan(order, wanted):
    values = list(order); cursor = 0; plan = []
    for position, identity in enumerate(wanted):
        index = values.index(identity)
        while index > position:
            wanted_cursor = index - 1; plan.extend([((4 if wanted_cursor > cursor else 3), {})] * abs(wanted_cursor - cursor)); cursor = wanted_cursor; plan.append((5, {})); values[cursor], values[cursor + 1] = values[cursor + 1], values[cursor]; index -= 1
    return plan


def plans_q062(module):
    result = []
    for level in module.LEVELS:
        plan = adjacent_sort_plan(level["order"], module.target(len(level["order"]), level["light"])) + [(6, {})]; assert len(plan) <= level["budget"], (level["name"], len(plan)); result.append(plan)
    return result


def plans_q072(module): return [[(action, {}) for action in level["route"]] for level in module.LEVELS]


def plans_q082(module):
    result = []
    for level in module.LEVELS:
        plan = [(1, {})] * len(level["events"]) + adjacent_sort_plan(level["order"], list(range(len(level["order"])))) + [(6, {})]; assert len(plan) <= level["budget"], (level["name"], len(plan)); result.append(plan)
    return result


def plans_q092(module):
    result = []
    for level in module.LEVELS:
        values = list(level["start"]); plan = []
        for index, wanted in enumerate(level["target"]):
            plus = (wanted - values[index]) % 4; minus = (values[index] - wanted) % 4; action, count = (2, plus) if plus <= minus else (1, minus); plan.extend([(action, {})] * count); values[index] = wanted; plan.append((5, {}))
            if index < len(values) - 1: values[index + 1] = (values[index + 1] + level["influence"][index]) % 4
        assert len(plan) <= level["budget"], (level["name"], len(plan)); result.append(plan)
    return result


PLANNERS = {code: globals()[f"plans_{code}"] for code in CODES}
LOSS = {"q003": [(6, {})], "q012": [(6, {})], "q022": [(6, {})], "q032": [(6, {})], "q042": [(5, {})], "q052": [(5, {})], "q062": [(6, {})], "q072": [(1, {})], "q082": [(3, {})], "q092": [(5, {})]}


def validate_frame(result):
    grid = result.frame[-1]; assert grid.shape == (64, 64); assert np.issubdtype(grid.dtype, np.integer); assert int(grid.min()) >= 0; assert int(grid.max()) <= 15


def digest(result): return hashlib.sha256(np.asarray(result.frame[-1], dtype=np.uint8).tobytes()).hexdigest()


def execute(code, module, plans):
    game = getattr(module, code.upper())(); result = game.perform_action(ActionInput(id=GameAction.RESET), raw=True); records = []
    for index, plan in enumerate(plans):
        assert game.level_index == index; encoded = []
        for action, data in plan:
            result = game.perform_action(ActionInput(id=GameAction.from_id(action), data=data), raw=True); validate_frame(result); encoded.append([action, data["x"], data["y"]] if "x" in data else [action])
        records.append({"level": index + 1, "actions": encoded, "post_transition_frame_sha256": digest(result)})
    assert result.state == GameState.WIN, (code, result.state); return {"schema_version": 1, "game_id": f"{code}-v1", "expected_state": "WIN", "levels": records}


def execute_loss(code, module):
    game = getattr(module, code.upper())(); result = game.perform_action(ActionInput(id=GameAction.RESET), raw=True); encoded = []
    for action, data in LOSS[code]:
        result = game.perform_action(ActionInput(id=GameAction.from_id(action), data=data), raw=True); encoded.append([action]);
        if result.state == GameState.GAME_OVER: break
    assert result.state == GameState.GAME_OVER, (code, result.state); return {"schema_version": 1, "game_id": f"{code}-v1", "expected_state": result.state.value, "actions": encoded, "terminal_frame_sha256": digest(result)}


def qualify(write=False):
    for code in CODES:
        module = load(code); plans = PLANNERS[code](module); win = execute(code, module, plans); loss = execute_loss(code, module)
        if write:
            out = ROOT / "research" / "recordings"; out.mkdir(parents=True, exist_ok=True); (out / f"{code}-v1-win.json").write_text(json.dumps(win, indent=2) + "\n", encoding="utf-8"); (out / f"{code}-v1-loss.json").write_text(json.dumps(loss, indent=2) + "\n", encoding="utf-8")
        print(code, "levels", len(plans), "actions", sum(map(len, plans)), "qualified")


def test_batch03_known_plans_and_losses(): qualify(False)


def test_batch03_fuzz():
    rng = random.Random(8303)
    for code in CODES:
        module = load(code); game = getattr(module, code.upper())(); result = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
        for _ in range(500):
            if result.state in (GameState.GAME_OVER, GameState.WIN): result = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
            action = rng.choice(range(1, 7)); data = {"x": rng.randrange(64), "y": rng.randrange(64)} if action == 6 else {}; result = game.perform_action(ActionInput(id=GameAction.from_id(action), data=data), raw=True); validate_frame(result)


def test_batch03_artifacts():
    batch = json.loads((ROOT / "research" / "gpt-batch03-v1.json").read_text()); assert [game["game_id"] for game in batch["games"]] == CODES
    for code in CODES:
        module = load(code); meta = json.loads((ROOT / "research" / "games" / f"{code}-v1.json").read_text()); source = ROOT / meta["artifacts"]["source"]; assert hashlib.sha256(source.read_bytes()).hexdigest() == meta["artifacts"]["source_sha256"]
        win = json.loads((ROOT / meta["artifacts"]["win_recording"]).read_text()); game = getattr(module, code.upper())(); result = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
        for level in win["levels"]:
            for encoded in level["actions"]: result = game.perform_action(ActionInput(id=GameAction.from_id(encoded[0]), data={},), raw=True)
            assert digest(result) == level["post_transition_frame_sha256"]
        assert result.state == GameState.WIN


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--write-recordings", action="store_true"); args = parser.parse_args(); qualify(args.write_recordings)

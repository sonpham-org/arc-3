"""Deterministic qualification and recording generation for research Batch 02."""

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
CODES = ["q101", "q111", "q121", "q131", "q141", "q151", "q161", "q171", "q181", "q191"]


def load(code):
    path = ROOT / "docs" / "static" / "games" / "src" / f"{code}-v1" / f"{code}.py"
    spec = importlib.util.spec_from_file_location(f"{code}_batch02", path); module = importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(module)
    return module


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


def plans_q101(module):
    result = []
    for level in module.LEVELS:
        walls = set(level["walls"])
        def expand(state):
            pos, orientation = state
            for action, vector in module.DIRS.items():
                dx, dy = module.rotate(vector, orientation); nxt = (pos[0] + dx, pos[1] + dy)
                if not (0 <= nxt[0] < module.SIZE and 0 <= nxt[1] < module.SIZE) or nxt in walls: nxt = pos
                yield (action, {}), (nxt, (orientation + level["spin"]) % 4)
        plan = bfs((level["start"], level["orientation"]), lambda state: state[0] == level["goal"], expand); assert len(plan) <= level["budget"]; result.append(plan)
    return result


def plans_q111(module):
    return [[(module.transform(action, level["rotation"], level["mirror"]), {}) for action in level["demo"]] for level in module.LEVELS]


def plans_q121(module):
    result = []
    for level in module.LEVELS:
        walls = set(level["walls"])
        def expand(state):
            pos, history = state; forbidden = module.prediction(history)
            for action, (dx, dy) in module.DIRS.items():
                if action == forbidden: continue
                nxt = (pos[0] + dx, pos[1] + dy)
                if not (0 <= nxt[0] < module.SIZE and 0 <= nxt[1] < module.SIZE) or nxt in walls: nxt = pos
                yield (action, {}), (nxt, tuple((list(history) + [action])[-level["window"]:]))
        plan = bfs((level["start"], tuple(level["history"])), lambda state: state[0] == level["goal"], expand); assert len(plan) <= level["budget"], (level["name"], len(plan)); result.append(plan)
    return result


def plans_q131(module): return [[(pulse, {}) for pulse in level["expected"]] + [(5, {})] for level in module.LEVELS]


def plans_q141(module):
    result = []
    for level in module.LEVELS:
        correct = level["outcomes"].index(level["target"]); plan = []
        for i in range(correct + 1):
            plan.append((5, {}))
            if i < correct: plan.append((4, {}))
        plan.append((6, {})); assert correct + 1 <= level["probes"]; result.append(plan)
    return result


def plans_q151(module):
    return [[(6, {"x": level["road"][node][0], "y": level["road"][node][1]}) for node in level["path"][1:]] for level in module.LEVELS]


def plans_q161(module):
    result = []
    for level in module.LEVELS:
        survivors = (1 << level["n"]) - 1; plan = []
        for clue in level["clues"]:
            plan.append((5, {})); survivors &= clue
            if survivors.bit_count() == 1: break
        cursor = 0; answer = level["answer"]
        right = (answer - cursor) % level["n"]; left = (cursor - answer) % level["n"]
        plan.extend([(4 if right <= left else 3, {})] * min(right, left)); plan.append((6, {})); assert len(plan) <= level["budget"]; assert survivors == 1 << answer; result.append(plan)
    return result


def plans_q171(module):
    result = []
    for level in module.LEVELS:
        locked = set(level["locked"]); n = len(level["start"])
        def expand(state):
            values, cursor = state
            yield (3, {}), (values, (cursor - 1) % n); yield (4, {}), (values, (cursor + 1) % n)
            yield (1, {}), (module.adjust(values, cursor, -1, level["coupled"], locked), cursor)
            yield (2, {}), (module.adjust(values, cursor, 1, level["coupled"], locked), cursor)
        plan = bfs((tuple(level["start"]), 0), lambda state: state[0] == tuple(level["target"]), expand); assert len(plan) <= level["budget"], (level["name"], len(plan)); result.append(plan)
    return result


def plans_q181(module):
    result = []
    for level in module.LEVELS:
        debts = {key: set(map(tuple, cells)) for key, cells in level["debts"].items()}; first, future = level["first"], level["future"]
        def expand(state):
            phase, pos, debt_cells = state; grid = first if phase == 0 else future
            for action, (dx, dy) in module.DIRS.items():
                nxt = (pos[0] + dx, pos[1] + dy)
                if not (0 <= nxt[0] < module.W and 0 <= nxt[1] < module.H) or grid[nxt[1]][nxt[0]] == "#" or (phase == 1 and nxt in debt_cells): nxt = pos
                new_debt = set(debt_cells)
                if phase == 0 and grid[nxt[1]][nxt[0]] in debts: new_debt |= debts[grid[nxt[1]][nxt[0]]]
                new_phase = phase
                if nxt == module.locate(grid, "G"):
                    if phase == 0: new_phase, nxt = 1, module.locate(future, "S")
                    else: new_phase = 2
                yield (action, {}), (new_phase, nxt, frozenset(new_debt))
        start = (0, module.locate(first, "S"), frozenset()); plan = bfs(start, lambda state: state[0] == 2, expand); assert len(plan) <= level["budget"], (level["name"], len(plan)); result.append(plan)
    return result


def plans_q191(module):
    result = []
    for level in module.LEVELS:
        phase, direction, plan = 0, 1, []
        for index, event in enumerate(level["events"]):
            while phase != event:
                plan.append((5, {})); phase = (phase + direction) % level["period"]
            plan.append((6, {}))
            if index < len(level["events"]) - 1:
                if level["reverse"]: direction *= -1
                phase = (phase + direction) % level["period"]
        assert len(plan) <= level["budget"], (level["name"], len(plan)); result.append(plan)
    return result


PLANNERS = {code: globals()[f"plans_{code}"] for code in CODES}
LOSS = {
    "q101": [(1, {})] * 8,
    "q111": [(1, {})],
    "q121": [(3, {})],
    "q131": [(5, {})],
    "q141": [(6, {})],
    "q151": [(6, {"x": 8, "y": 47})],
    "q161": [(6, {})],
    "q171": [(1, {})] * 7,
    "q181": [(1, {})] * 24,
    "q191": [(6, {})],
}


def validate_frame(result):
    grid = result.frame[-1]; assert grid.shape == (64, 64); assert np.issubdtype(grid.dtype, np.integer); assert int(grid.min()) >= 0; assert int(grid.max()) <= 15


def frame_digest(result): return hashlib.sha256(np.asarray(result.frame[-1], dtype=np.uint8).tobytes()).hexdigest()


def execute(code, module, plans):
    game = getattr(module, code.upper())(); result = game.perform_action(ActionInput(id=GameAction.RESET), raw=True); validate_frame(result); records = []
    for level_index, plan in enumerate(plans):
        assert game.level_index == level_index
        encoded = []
        for action, data in plan:
            result = game.perform_action(ActionInput(id=GameAction.from_id(action), data=data), raw=True); validate_frame(result); encoded.append([action, data["x"], data["y"]] if "x" in data else [action])
        records.append({"level": level_index + 1, "actions": encoded, "post_transition_frame_sha256": frame_digest(result)})
    assert result.state == GameState.WIN, (code, result.state, game.level_index)
    return {"schema_version": 1, "game_id": f"{code}-v1", "expected_state": "WIN", "levels": records}


def execute_loss(code, module):
    game = getattr(module, code.upper())(); result = game.perform_action(ActionInput(id=GameAction.RESET), raw=True); encoded = []
    for action, data in LOSS[code]:
        result = game.perform_action(ActionInput(id=GameAction.from_id(action), data=data), raw=True); encoded.append([action, data["x"], data["y"]] if "x" in data else [action])
        if result.state == GameState.GAME_OVER: break
    assert result.state == GameState.GAME_OVER, (code, result.state)
    return {"schema_version": 1, "game_id": f"{code}-v1", "expected_state": result.state.value, "actions": encoded, "terminal_frame_sha256": frame_digest(result)}


def qualify(write=False):
    for code in CODES:
        module = load(code); plans = PLANNERS[code](module); win = execute(code, module, plans); loss = execute_loss(code, module)
        if write:
            out = ROOT / "research" / "recordings"; out.mkdir(parents=True, exist_ok=True)
            (out / f"{code}-v1-win.json").write_text(json.dumps(win, indent=2) + "\n", encoding="utf-8"); (out / f"{code}-v1-loss.json").write_text(json.dumps(loss, indent=2) + "\n", encoding="utf-8")
        print(code, "levels", len(plans), "actions", sum(map(len, plans)), "qualified")


def test_batch02_known_plans_and_losses(): qualify(write=False)


def test_batch02_seeded_action_fuzz():
    rng = random.Random(8202)
    for code in CODES:
        module = load(code); game = getattr(module, code.upper())(); result = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
        for _ in range(500):
            if result.state in (GameState.GAME_OVER, GameState.WIN): result = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
            action = rng.choice(range(1, 7)); data = {"x": rng.randrange(64), "y": rng.randrange(64)} if action == 6 else {}
            result = game.perform_action(ActionInput(id=GameAction.from_id(action), data=data), raw=True); validate_frame(result)


def test_batch02_backgrounds_are_unique_and_not_black_dominant():
    signatures = set()
    for code in CODES:
        module = load(code); game = getattr(module, code.upper())(); result = game.perform_action(ActionInput(id=GameAction.RESET), raw=True); grid = result.frame[-1]
        signature = tuple(int(grid[y, x]) for y, x in ((0, 0), (0, -1), (-1, 0), (-1, -1))); assert signature != (5, 5, 5, 5); assert float((grid == 5).sum()) / grid.size < 0.1; signatures.add(signature)
    assert len(signatures) == len(CODES)


def test_batch02_committed_recordings_and_hashes():
    batch = json.loads((ROOT / "research" / "gpt-batch02-v1.json").read_text(encoding="utf-8")); assert [item["game_id"] for item in batch["games"]] == CODES
    for code in CODES:
        module = load(code); metadata = json.loads((ROOT / "research" / "games" / f"{code}-v1.json").read_text(encoding="utf-8")); source = ROOT / metadata["artifacts"]["source"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == metadata["artifacts"]["source_sha256"]; assert len(metadata["progression"]) == 6
        win = json.loads((ROOT / metadata["artifacts"]["win_recording"]).read_text(encoding="utf-8")); game = getattr(module, code.upper())(); result = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
        for level in win["levels"]:
            for encoded in level["actions"]:
                data = {"x": encoded[1], "y": encoded[2]} if len(encoded) == 3 else {}; result = game.perform_action(ActionInput(id=GameAction.from_id(encoded[0]), data=data), raw=True)
            assert frame_digest(result) == level["post_transition_frame_sha256"]
        assert result.state == GameState.WIN
        loss = json.loads((ROOT / metadata["artifacts"]["loss_recording"]).read_text(encoding="utf-8")); game = getattr(module, code.upper())(); result = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
        for encoded in loss["actions"]:
            data = {"x": encoded[1], "y": encoded[2]} if len(encoded) == 3 else {}; result = game.perform_action(ActionInput(id=GameAction.from_id(encoded[0]), data=data), raw=True)
        assert result.state.value == loss["expected_state"]; assert frame_digest(result) == loss["terminal_frame_sha256"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--write-recordings", action="store_true"); args = parser.parse_args(); qualify(args.write_recordings)

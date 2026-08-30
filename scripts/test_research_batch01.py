"""Deterministic qualification and recording generation for research Batch 01."""

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
CODES = ["q002", "q011", "q021", "q031", "q041", "q051", "q061", "q071", "q081", "q091"]


def load(code):
    path = ROOT / "docs" / "static" / "games" / "src" / f"{code}-v1" / f"{code}.py"
    spec = importlib.util.spec_from_file_location(f"{code}_batch01", path)
    module = importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(module)
    return module


def click(cell, *, cell_size=6, ox=0, oy=0):
    return (6, {"x": ox + cell[0] * cell_size + cell_size // 2, "y": oy + cell[1] * cell_size + cell_size // 2})


def bfs(start, solved, expand):
    queue = deque([start]); parent = {start: None}; action = {}
    while queue:
        state = queue.popleft()
        if solved(state):
            out = []
            while parent[state] is not None: out.append(action[state]); state = parent[state]
            return list(reversed(out))
        for a, nxt in expand(state):
            if nxt not in parent: parent[nxt] = state; action[nxt] = a; queue.append(nxt)
    raise AssertionError("authored level is not solvable")


def plans_q002(m):
    def gate(level, i): return click(level["mills"][i]["cell"], cell_size=m.CELL, ox=m.OX, oy=m.OY)
    pulse = lambda n: [(5, {})] * n
    l = m.LEVELS
    plans = [
        [(4, {}), gate(l[0], 0)] + pulse(3),
        [(1, {}), gate(l[1], 0)] + pulse(3),
        [(1, {}), gate(l[2], 0)] + pulse(3) + [gate(l[2], 0), (4, {}), gate(l[2], 0)] + pulse(3),
        [gate(l[3], 1), (4, {}), gate(l[3], 0), gate(l[3], 1), (3, {}), gate(l[3], 1)] + pulse(3),
        [(1, {}), gate(l[4], 0)] + pulse(6),
    ]
    # Two straight programs stop on their sockets while a third consumes a turn plate.
    p = [gate(l[5], 0), gate(l[5], 1), gate(l[5], 2)] + pulse(3)
    p += [gate(l[5], 0), gate(l[5], 1)] + pulse(1)
    plans.append(p)
    for plan, level in zip(plans, l): assert len(plan) <= level["budget"], (level["name"], len(plan))
    return plans


def plans_q011(m):
    result = []
    for level in m.LEVELS:
        start = (tuple(level["order"]), 0); target = tuple(sorted(level["order"], key=lambda x: m.RANK[x], reverse=True)); n = len(target)
        def expand(s):
            order, cursor = s
            yield (3, {}), (order, (cursor - 1) % (n - 1)); yield (4, {}), (order, (cursor + 1) % (n - 1))
            changed = list(order); a, b = changed[cursor:cursor + 2]; swap = m.RANK[a] < m.RANK[b]
            if cursor in level["reverse"]: swap = not swap
            if swap: changed[cursor], changed[cursor + 1] = b, a
            yield (5, {}), (tuple(changed), cursor)
            if level["rotate"]: yield (6, {}), (order[1:] + order[:1], cursor)
        plan = bfs(start, lambda s: s[0] == target, expand); assert len(plan) <= level["budget"]; result.append(plan)
    return result


def plans_q021(m):
    result = []
    for level in m.LEVELS:
        n = len(level["masks"]); start = (level["initial"], 0, level["tests"])
        def expand(s):
            lamps, cur, tests = s
            yield (1, {}), (lamps, (cur - 1) % n, tests); yield (2, {}), (lamps, (cur + 1) % n, tests)
            if tests: yield (5, {}), (lamps ^ level["masks"][cur], cur, tests - 1)
        plan = bfs(start, lambda s: s[0] == level["target"], expand) + [(6, {})]; result.append(plan)
    return result


def plans_q031(m):
    result = []
    for level in m.LEVELS:
        n = len(level["ops"]); start = (tuple(level["start"]), 0, level["budget"])
        def expand(s):
            values, cur, left = s
            yield (3, {}), (values, (cur - 1) % n, left); yield (4, {}), (values, (cur + 1) % n, left)
            if left: yield (5, {}), (m.apply_op(values, level["ops"][cur]), cur, left - 1)
        plan = bfs(start, lambda s: s[0] == tuple(level["target"]), expand) + [(6, {})]; result.append(plan)
    return result


def plans_q041(m):
    result = []
    for level in m.LEVELS:
        grid = level["map"]; start = goal = None
        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch == "S": start = (x, y)
                elif ch == "G": goal = (x, y)
        def expand_route(s):
            pos, key, collapsed = s
            for aid, (dx, dy) in m.DIRS.items():
                p = (pos[0] + dx, pos[1] + dy)
                if not (0 <= p[0] < 8 and 0 <= p[1] < 8): continue
                ch = grid[p[1]][p[0]]
                if ch == "#" or p in collapsed or (ch == "d" and not key): continue
                gone = set(collapsed)
                if grid[pos[1]][pos[0]] == "!": gone.add(pos)
                yield (aid, {}), (p, key or ch == "k", frozenset(gone))
        move_plan = bfs((start, False, frozenset()), lambda s: s[0] == goal, expand_route)
        path = [start]; p = start
        for aid, _ in move_plan:
            dx, dy = m.DIRS[aid]; p = (p[0] + dx, p[1] + dy); path.append(p)
        initial = {(x, y) for y in range(max(0, start[1] - 1), min(8, start[1] + 2)) for x in range(max(0, start[0] - 1), min(8, start[0] + 2))}
        # Minimum set cover over only the route cells; masks keep this small and exact.
        need_cells = list(dict.fromkeys(path)); full = (1 << len(need_cells)) - 1
        initial_mask = sum(1 << i for i, c in enumerate(need_cells) if c in initial)
        centers = [(x, y) for y in range(8) for x in range(8)]
        masks = []
        for cx, cy in centers:
            mask = sum(1 << i for i, (x, y) in enumerate(need_cells) if abs(x - cx) <= 1 and abs(y - cy) <= 1)
            masks.append(mask)
        queue = deque([initial_mask]); parent = {initial_mask: None}; used = {}; terminal = None
        while queue:
            mask = queue.popleft()
            if mask == full: terminal = mask; break
            depth = 0; walk = mask
            while parent[walk] is not None: depth += 1; walk = parent[walk]
            if depth >= level["looks"]: continue
            for center, add in zip(centers, masks):
                nxt = mask | add
                if nxt not in parent: parent[nxt] = mask; used[nxt] = center; queue.append(nxt)
        assert terminal is not None
        chosen = []
        while parent[terminal] is not None: chosen.append(used[terminal]); terminal = parent[terminal]
        chosen.reverse()
        looks = [click(c, cell_size=m.CELL, ox=m.OX, oy=m.OY) for c in chosen]
        result.append(looks + move_plan)
    return result


def plans_q051(m):
    edge_sets = [[0, 1], [0, 1, 2, 3], [0, 1], [0, 1, 3, 4, 6, 7], [0, 1, 4, 5, 8, 9], [0, 1, 2, 5, 6, 7, 10, 11, 12, 15, 16, 17]]
    result = []
    for li, (level, indices) in enumerate(zip(m.LEVELS, edge_sets)):
        plan = []
        if li == 2: plan.append((4, {}))
        for idx in indices:
            a, b = level["edges"][idx]; ax, ay = level["nodes"][a]; bx, by = level["nodes"][b]
            plan.append((6, {"x": (ax + bx) // 2, "y": (ay + by) // 2}))
        plan.append((5, {})); result.append(plan)
    return result


def plans_q061(m):
    result = []
    for level in m.LEVELS:
        grids = (level["left"], level["right"]); starts = []; goals = []
        for grid in grids:
            st = go = None
            for y, row in enumerate(grid):
                for x, ch in enumerate(row):
                    if ch == "S": st = (x, y)
                    elif ch == "G": go = (x, y)
            starts.append(st); goals.append(go)
        start = (tuple(starts), 0, (False, False))
        def expand(s):
            positions, active, switches = s
            yield (5, {}), (positions, 1 - active, switches)
            grid = grids[active]
            for aid, (dx, dy) in m.DIRS.items():
                p = (positions[active][0] + dx, positions[active][1] + dy)
                if not (0 <= p[0] < 6 and 0 <= p[1] < 6): continue
                ch = grid[p[1]][p[0]]
                if ch in "#x" or (ch == "d" and not switches[1 - active]): continue
                ps = list(positions); ps[active] = p; sw = list(switches)
                if ch == "s": sw[active] = True
                yield (aid, {}), (tuple(ps), active, tuple(sw))
        plan = bfs(start, lambda s: s[0] == tuple(goals), expand); assert len(plan) <= level["budget"]; result.append(plan)
    return result


def plans_q071(m):
    result = []
    for level in m.LEVELS:
        grid = level["map"]; start = goal = None
        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch == "S": start = (x, y)
                elif ch == "G": goal = (x, y)
        initial = (start, 0, level["period"], False, frozenset(), level["budget"])
        def expand(s):
            pos, phase, until, rev, collapsed, budget = s
            if budget <= 1: return
            actions = [(5, {})] + [(aid, {}) for aid in m.DIRS]
            for aid, data in actions:
                p = pos; gone = set(collapsed); r = rev
                if aid in m.DIRS:
                    dx, dy = m.DIRS[aid]; q = (pos[0] + dx, pos[1] + dy)
                    if not (0 <= q[0] < 8 and 0 <= q[1] < 8): continue
                    ch = grid[q[1]][q[0]]
                    is_open = (ch == "a") == (phase == (1 if rev else 0))
                    if ch == "#" or q in gone or (ch in "ab" and not is_open): continue
                    p = q
                    if grid[pos[1]][pos[0]] == "!": gone.add(pos)
                    if ch == "M": r = not r
                if p == goal: yield (aid, data), (p, phase, until, r, frozenset(gone), budget - 1); continue
                u = until - 1; ph = phase
                if u <= 0: ph = 1 - ph; u = level["period"]
                yield (aid, data), (p, ph, u, r, frozenset(gone), budget - 1)
        plan = bfs(initial, lambda s: s[0] == goal, expand); result.append(plan)
    return result


def plans_q081(m):
    result = []
    for level in m.LEVELS:
        bodies = [{"identity": i, "appearance": i} for i in range(level["n"])]; plan = [(5, {}) for _ in level["events"]]
        for kind, a, b in level["events"]:
            if kind == "pos": bodies[a], bodies[b] = bodies[b], bodies[a]
            else: bodies[a]["appearance"], bodies[b]["appearance"] = bodies[b]["appearance"], bodies[a]["appearance"]
        target = level["target"]
        for i in range(len(bodies)):
            want = target[i]; j = next(j for j in range(i, len(bodies)) if bodies[j]["identity"] == want)
            while j > i and level["adjacent"]:
                plan += [(6, {"x": m.Display.xpos(j - 1, len(bodies)), "y": 30}), (6, {"x": m.Display.xpos(j, len(bodies)), "y": 30})]
                bodies[j - 1], bodies[j] = bodies[j], bodies[j - 1]; j -= 1
            if j != i:
                plan += [(6, {"x": m.Display.xpos(i, len(bodies)), "y": 30}), (6, {"x": m.Display.xpos(j, len(bodies)), "y": 30})]
                bodies[i], bodies[j] = bodies[j], bodies[i]
        assert len(plan) <= level["budget"]; result.append(plan)
    return result


def plans_q091(m):
    result = []
    for level in m.LEVELS:
        parts = list(level["parts"]); plan = []
        for a, b, out, tool in level["recipes"]:
            i, j = parts.index(a), parts.index(b)
            plan += [(6, {"x": m.Display.xpos(i), "y": 24 + (i // 6) * 16}), (6, {"x": m.Display.xpos(j), "y": 24 + (j // 6) * 16}), (5, {})]
            for idx in sorted((i, j), reverse=True): parts.pop(idx)
            parts.append(out)
        plan.append((5, {})); assert len(plan) <= level["budget"]; result.append(plan)
    return result


PLANNERS = {code: globals()[f"plans_{code}"] for code in CODES}
LOSS = {"q002": [(1, {})] * 20, "q011": [(1, {})] * 20, "q021": [(6, {})], "q031": [(6, {})], "q041": [(1, {})], "q051": [(5, {})], "q061": [(1, {})], "q071": [(5, {})] * 20, "q081": [(5, {})] * 20, "q091": [(5, {})] * 20}


def frame_digest(frame): return hashlib.sha256(np.asarray(frame.frame[-1]).tobytes()).hexdigest()


def validate_frame(frame):
    grid = np.asarray(frame.frame[-1]); assert grid.shape == (64, 64); assert np.issubdtype(grid.dtype, np.integer); assert 0 <= int(grid.min()) <= int(grid.max()) <= 15


def execute(code, module, plans):
    game = getattr(module, code.upper())(); frame = game.perform_action(ActionInput(id=GameAction.RESET), raw=True); validate_frame(frame); records = []
    for level_index, plan in enumerate(plans):
        assert game.level_index == level_index
        encoded = []
        for aid, data in plan:
            frame = game.perform_action(ActionInput(id=GameAction.from_id(aid), data=data), raw=True); validate_frame(frame)
            encoded.append([aid, data["x"], data["y"]] if "x" in data else [aid])
        records.append({"level": level_index + 1, "actions": encoded, "post_transition_frame_sha256": frame_digest(frame)})
    assert frame.state == GameState.WIN, (code, frame.state, game.level_index)
    return {"schema_version": 1, "game_id": f"{code}-v1", "expected_state": "WIN", "levels": records}


def execute_loss(code, module):
    game = getattr(module, code.upper())(); frame = game.perform_action(ActionInput(id=GameAction.RESET), raw=True); encoded = []
    for aid, data in LOSS[code]:
        frame = game.perform_action(ActionInput(id=GameAction.from_id(aid), data=data), raw=True); encoded.append([aid, data["x"], data["y"]] if "x" in data else [aid])
        if frame.state == GameState.GAME_OVER: break
    assert frame.state == GameState.GAME_OVER, (code, frame.state)
    return {"schema_version": 1, "game_id": f"{code}-v1", "expected_state": frame.state.value, "actions": encoded, "terminal_frame_sha256": frame_digest(frame)}


def qualify(write=False):
    for code in CODES:
        module = load(code); plans = PLANNERS[code](module); win = execute(code, module, plans); loss = execute_loss(code, module)
        if write:
            out = ROOT / "research" / "recordings"; out.mkdir(parents=True, exist_ok=True)
            (out / f"{code}-v1-win.json").write_text(json.dumps(win, indent=2) + "\n", encoding="utf-8")
            (out / f"{code}-v1-loss.json").write_text(json.dumps(loss, indent=2) + "\n", encoding="utf-8")
        print(code, "levels", len(plans), "actions", sum(map(len, plans)), "qualified")


def test_batch01_known_plans_and_losses(): qualify(write=False)


def test_batch01_seeded_action_fuzz():
    rng = random.Random(8101)
    for code in CODES:
        module = load(code); game = getattr(module, code.upper())(); frame = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
        for _ in range(500):
            if frame.state in (GameState.GAME_OVER, GameState.WIN): frame = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
            aid = rng.choice(list(range(1, 7))); data = {"x": rng.randrange(64), "y": rng.randrange(64)} if aid == 6 else {}
            frame = game.perform_action(ActionInput(id=GameAction.from_id(aid), data=data), raw=True); validate_frame(frame)


def test_batch01_committed_recordings_hashes_and_diversity():
    batch = json.loads((ROOT / "research" / "gpt-batch01-v1.json").read_text(encoding="utf-8"))
    assert [item["game_id"] for item in batch["games"]] == CODES
    assert len({item["axis"] for item in batch["games"]}) == len(CODES)
    palettes = set()
    for code in CODES:
        module = load(code)
        metadata = json.loads((ROOT / "research" / "games" / f"{code}-v1.json").read_text(encoding="utf-8"))
        source = ROOT / metadata["artifacts"]["source"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == metadata["artifacts"]["source_sha256"]
        assert len(metadata["progression"]) == 6
        palettes.add(tuple(metadata["visual_identity"]["dominant_palette"]))

        win = json.loads((ROOT / metadata["artifacts"]["win_recording"]).read_text(encoding="utf-8"))
        game = getattr(module, code.upper())(); frame = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
        for level in win["levels"]:
            for encoded in level["actions"]:
                data = {"x": encoded[1], "y": encoded[2]} if len(encoded) == 3 else {}
                frame = game.perform_action(ActionInput(id=GameAction.from_id(encoded[0]), data=data), raw=True)
            assert frame_digest(frame) == level["post_transition_frame_sha256"]
        assert frame.state == GameState.WIN

        loss = json.loads((ROOT / metadata["artifacts"]["loss_recording"]).read_text(encoding="utf-8"))
        game = getattr(module, code.upper())(); frame = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
        for encoded in loss["actions"]:
            data = {"x": encoded[1], "y": encoded[2]} if len(encoded) == 3 else {}
            frame = game.perform_action(ActionInput(id=GameAction.from_id(encoded[0]), data=data), raw=True)
        assert frame.state.value == loss["expected_state"]
        assert frame_digest(frame) == loss["terminal_frame_sha256"]
    assert len(palettes) == len(CODES)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--write-recordings", action="store_true"); args = parser.parse_args(); qualify(args.write_recordings)

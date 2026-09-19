#!/usr/bin/env python3
"""Vet a game source before it is published to the Games page.

Author: Claude Opus 5, 19-September-2026
Purpose: the publication API stores whatever bytes it is given, and the server never runs game
code (on purpose). This is the machine gate an uploader runs first: it plays the game in the
same engine the site uses (arcengine 0.9.3), from a fresh namespace, and checks that

  - it loads, renders valid 64x64 frames, and imports nothing it shouldn't;
  - a recorded winning trace clears every level, in order, and ends in WIN;
  - two replays, and a replay from a deep copy (how the site's Undo works), are identical;
  - RESET restarts the current level without losing completed ones, and the level can still
    be won from there;
  - level 1 is short (the recorded win is at most 10 actions) and ordinary random play cannot
    lose it; no level kills a random player within its first 10 actions more than 10% of
    the time ("not dying right away");
  - random play cannot clear levels 2 and later within a stated finite horizon;
  - no action plays more than 60 frames (15 is already a warning: moves should be short).

It writes a JSON report bound to the exact source bytes by sha256. publish_game_versions.py
refuses to upload a source whose report is missing, failing, or for other bytes. It cannot
judge fun, clarity, novelty, or whether the animation looks right: --strips renders the
trace's multi-frame actions as picture strips for the reviewer who does.

Usage:
  python scripts/vet_game.py --source game.py --trace game.trace.json --profile glowup \
      --out game.vet.json [--strips DIR] [--time-budget 300]
Exit status: 0 pass, 1 fail, 2 could not run.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

TOOL = "vet_game.py/1"
TRACE_FORMAT = "arc3-trace/1"
ALLOWED_IMPORTS = {
    "__future__", "abc", "arcengine", "bisect", "collections", "copy", "dataclasses", "enum", "fractions",
    "functools", "heapq", "itertools", "math", "numpy", "operator", "random", "string", "typing",
}
FORBIDDEN_CALLS = {"open", "eval", "exec", "compile", "__import__", "input", "breakpoint", "globals", "locals"}
PROFILES = {
    # A seed may be rough: 3+ levels, and a long level 1 or a random-clearable level is only a warning.
    "seed": {"min_levels": 3, "max_levels": 12, "strict_l1_length": False, "strict_resistance": False},
    # A glow-up or playability revision must meet the whole bar.
    "glowup": {"min_levels": 7, "max_levels": 12, "strict_l1_length": True, "strict_resistance": True},
}
L1_MAX_ACTIONS = 10
EARLY_WINDOW = 10
EARLY_DEATH_LIMIT = 0.10
FRAMES_WARN = 15
FRAMES_FAIL = 60
MAX_SOURCE_BYTES = 2 * 1024 * 1024
PALETTE = [
    (255, 255, 255), (204, 204, 204), (153, 153, 153), (102, 102, 102), (51, 51, 51), (0, 0, 0),
    (229, 58, 163), (255, 123, 204), (249, 60, 49), (30, 147, 255), (136, 216, 241), (255, 220, 0),
    (255, 133, 27), (146, 18, 49), (79, 204, 48), (163, 86, 214),
]


class VetError(Exception):
    """The game could not be exercised at all (as opposed to failing a check)."""


# ── Loading and acting ────────────────────────────────────────────────────────


def find_game_classes(tree: ast.AST) -> list[str]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", None)
                if name == "ARCBaseGame":
                    found.append(node.name)
    return found


def load_class(source: str, class_name: str):
    """Exec the source in a fresh namespace (stricter than the site, which pre-imports numpy and
    arcengine into the same globals), so a game must import everything it uses."""
    namespace: dict[str, Any] = {"__name__": "arc_game_module", "__file__": "/virtual/game.py"}
    exec(compile(source, "game.py", "exec"), namespace)
    if class_name not in namespace:
        raise VetError(f"class {class_name} not defined after exec")
    return namespace[class_name]


def engine():
    import arcengine
    from arcengine import ActionInput, GameAction, GameState

    return arcengine, ActionInput, GameAction, GameState


def decode_action(raw: Any) -> tuple[int, dict[str, int]]:
    if isinstance(raw, int) and raw in (1, 2, 3, 4, 5, 7):
        return raw, {}
    if isinstance(raw, list) and len(raw) == 3 and raw[0] == 6 and all(isinstance(v, int) for v in raw[1:]):
        if not (0 <= raw[1] <= 63 and 0 <= raw[2] <= 63):
            raise VetError(f"click outside the 64x64 screen: {raw}")
        return 6, {"x": raw[1], "y": raw[2]}
    raise VetError(f"bad trace action {raw!r}: use 1-5, 7, or [6, x, y]")


class Player:
    """One game instance plus the bookkeeping every check needs."""

    def __init__(self, game: Any):
        self.game = game
        _, self.ActionInput, self.GameAction, self.GameState = engine()
        self.max_frames = 0

    def reset(self):
        return self._do(self.ActionInput(id=self.GameAction.RESET))

    def act(self, action_id: int, data: dict[str, int] | None = None):
        return self._do(self.ActionInput(id=self.GameAction.from_id(action_id), data=data or {}))

    def _do(self, action_input):
        ended = self.game._state in (self.GameState.GAME_OVER, self.GameState.WIN)
        result = self.game.perform_action(action_input, raw=True)
        frames = result.frame
        if not frames:
            raise VetError(f"an action returned no frames{' (the game had already ended: ' + str(self.game._state) + ')' if ended else ''}")
        for frame in frames:
            shape = getattr(frame, "shape", None)
            if shape != (64, 64) or int(frame.min()) < 0 or int(frame.max()) > 15:
                raise VetError(f"invalid frame: shape {shape}, values must be 0..15")
        self.max_frames = max(self.max_frames, len(frames))
        return result

    @property
    def completed(self) -> int:
        return int(self.game._score)

    @property
    def state(self):
        return self.game._state


def frame_hash(frames) -> str:
    digest = hashlib.sha256()
    for frame in frames:
        digest.update(frame.astype("uint8").tobytes())
    return digest.hexdigest()[:16]


# ── Checks ────────────────────────────────────────────────────────────────────


def static_checks(source: str, tree: ast.AST) -> dict[str, dict[str, str]]:
    checks: dict[str, dict[str, str]] = {}
    size = len(source.encode("utf-8"))
    checks["size"] = (
        {"status": "fail", "detail": f"{size} bytes; the API takes at most {MAX_SOURCE_BYTES}"}
        if size > MAX_SOURCE_BYTES
        else {"status": "warn" if size > 200_000 else "pass", "detail": f"{size} bytes"}
    )
    bad_imports, bad_calls = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            bad_imports |= {a.name for a in node.names if a.name.split(".")[0] not in ALLOWED_IMPORTS}
        elif isinstance(node, ast.ImportFrom):
            if node.level or (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                bad_imports.add(node.module or ".")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            bad_calls.add(node.func.id)
    checks["imports"] = (
        {"status": "fail", "detail": f"not allowed: {sorted(bad_imports)} (allowed: {sorted(ALLOWED_IMPORTS)})"}
        if bad_imports
        else {"status": "pass", "detail": "standard library maths/containers, numpy, arcengine only"}
    )
    checks["calls"] = (
        {"status": "fail", "detail": f"forbidden calls: {sorted(bad_calls)}"}
        if bad_calls
        else {"status": "pass", "detail": "no file, eval or import-hook calls"}
    )
    return checks


def replay_trace(cls, levels: list[list[tuple[int, dict]]]) -> dict[str, Any]:
    """Play the whole trace once. Returns per-action hashes, per-level start snapshots, timings,
    and the first problem found (or None)."""
    player = Player(cls())
    start = player.reset()
    if player.state != player.GameState.NOT_FINISHED:
        return {"problem": f"RESET leaves the game in {player.state} (step() runs once for RESET too)", "won": False, "hashes": [],
                "snapshots": [], "level_start_frames": [], "multi_frame_actions": [], "seconds_per_action": 0.0, "max_frames": 0}
    hashes = [(frame_hash(start.frame), str(start.state), 0)]
    snapshots = [copy.deepcopy(player.game)]
    level_start_frames = [start.frame[-1].copy()]
    multi_frame_actions = []
    problem = None
    t0 = time.perf_counter()
    count = 0
    for index, actions in enumerate(levels):
        for position, (action_id, data) in enumerate(actions):
            result = player.act(action_id, data)
            count += 1
            hashes.append((frame_hash(result.frame), str(result.state), player.completed))
            if len(result.frame) > 1:
                multi_frame_actions.append((index, position, [f.copy() for f in result.frame]))
            if player.state == player.GameState.GAME_OVER:
                problem = f"level {index + 1}: GAME_OVER on trace action {position + 1}"
                break
            if player.completed > index and position < len(actions) - 1:
                problem = f"level {index + 1} was already cleared by action {position + 1} of {len(actions)}; trim the trace"
                break
        if problem:
            break
        if player.completed != index + 1:
            problem = f"level {index + 1} not cleared by its {len(actions)} trace actions (levels completed: {player.completed})"
            break
        if index < len(levels) - 1:
            snapshots.append(copy.deepcopy(player.game))
            level_start_frames.append(result.frame[-1].copy())
    won = problem is None and player.state == player.GameState.WIN
    if problem is None and not won:
        problem = f"all {len(levels)} trace levels cleared but the game is not in WIN (state {player.state})"
    return {
        "problem": problem,
        "won": won,
        "hashes": hashes,
        "snapshots": snapshots,
        "level_start_frames": level_start_frames,
        "multi_frame_actions": multi_frame_actions,
        "seconds_per_action": (time.perf_counter() - t0) / max(1, count),
        "max_frames": player.max_frames,
    }


def random_input(rng: random.Random, available: list[int], frame=None, targets=()) -> tuple[int, dict[str, int]]:
    """A random player that clicks on things, not only on empty space. A third of clicks land
    anywhere on the screen; a third pick a random non-background colour on screen and click a
    pixel of it (so each kind of object is equally likely, however small); a third click an
    engine-declared target (`sys_click` sprites) when the game has any. Clicking uniformly
    alone almost never hits a small button, which made click games look random-proof."""
    action_id = rng.choice(available)
    if action_id != 6:
        return action_id, {}
    roll = rng.random()
    if roll < 1 / 3 and targets:
        x, y = rng.choice(targets)
        return 6, {"x": x, "y": y}
    if roll < 2 / 3 and frame is not None:
        values, counts = np.unique(frame, return_counts=True)
        colours = [int(v) for v, c in zip(values, counts) if c != counts.max()]
        if colours:
            ys, xs = np.nonzero(frame == rng.choice(colours))
            k = rng.randrange(len(xs))
            return 6, {"x": int(xs[k]), "y": int(ys[k])}
    return 6, {"x": rng.randrange(64), "y": rng.randrange(64)}


def click_targets(game) -> list[tuple[int, int]]:
    try:
        return [(int(a.data["x"]), int(a.data["y"])) for a in game._get_valid_clickable_actions()]
    except Exception:  # a game with unusual sprites must not break the harness
        return []


def random_run(snapshot, rng: random.Random, budget: int, retry: bool) -> dict[str, Any]:
    """Uniform random play from a level-start snapshot. With retry, GAME_OVER is followed by RESET
    (a player retrying the current level), and that RESET must keep completed levels."""
    player = Player(copy.deepcopy(snapshot))
    base = player.completed
    available = [int(a) for a in player.game._available_actions if int(a) != 0]
    out: dict[str, Any] = {"actions": 0, "cleared_at": None, "game_over_at": None, "game_overs": 0, "silent": {}, "tried": {}}
    before = None
    screen = player.game.camera.render(player.game.current_level.get_sprites()) if 6 in available else None
    for step in range(budget):
        targets = click_targets(player.game) if 6 in available else []
        action_id, data = random_input(rng, available, before if before is not None else screen, targets)
        result = player.act(action_id, data)
        out["actions"] = step + 1
        final = result.frame[-1]
        out["tried"][action_id] = out["tried"].get(action_id, 0) + 1
        # Silent = no frame of the response differs from what was on screen: a refusal that
        # nudges and settles back is visible, a pixel-identical frame is not.
        if before is not None and all((frame == before).all() for frame in result.frame):
            out["silent"][action_id] = out["silent"].get(action_id, 0) + 1
        before = final
        if player.completed > base or player.state == player.GameState.WIN:
            out["cleared_at"] = step + 1
            break
        if player.state == player.GameState.GAME_OVER:
            out["game_overs"] += 1
            if out["game_over_at"] is None:
                out["game_over_at"] = step + 1
            if not retry:
                break
            again = player.reset()
            before = again.frame[-1]
            if player.state != player.GameState.NOT_FINISHED or player.completed != base:
                out["reset_lost_progress"] = True
                break
    out["max_frames"] = player.max_frames
    return out


class Clock:
    def __init__(self, budget: float):
        self.deadline = time.monotonic() + budget

    def left(self) -> float:
        return self.deadline - time.monotonic()


def vet(source_path: Path, trace_path: Path | None, profile_name: str, class_name: str | None, time_budget: float, seed: int, strips: Path | None) -> dict[str, Any]:
    profile = PROFILES[profile_name]
    raw = source_path.read_bytes().replace(b"\r\n", b"\n")  # hash what git stores and publish uploads
    source = raw.decode("utf-8")
    report: dict[str, Any] = {
        "tool": TOOL,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "source": source_path.name,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "profile": profile_name,
        "checks": {},
    }
    checks = report["checks"]
    try:
        import arcengine  # noqa: F401
        from importlib.metadata import version

        report["arcengine"] = version("arcengine")
    except Exception as exc:  # pragma: no cover - environment problem
        raise VetError(f"arcengine is not importable: {exc}") from exc
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        checks["parse"] = {"status": "fail", "detail": f"SyntaxError: {exc}"}
        return finish(report)
    checks.update(static_checks(source, tree))
    classes = find_game_classes(tree)
    if class_name is None:
        if len(classes) != 1:
            checks["class"] = {"status": "fail", "detail": f"expected one ARCBaseGame subclass, found {classes}; pass --class-name"}
            return finish(report)
        class_name = classes[0]
    report["class_name"] = class_name
    try:
        cls = load_class(source, class_name)
        probe = Player(cls())
        probe.reset()
        levels_total = len(probe.game._clean_levels)
    except Exception as exc:
        checks["load"] = {"status": "fail", "detail": f"{type(exc).__name__}: {exc}"[:400]}
        return finish(report)
    checks["load"] = {"status": "pass", "detail": f"{class_name}() loads and RESET renders a 64x64 frame"}
    report["levels"] = levels_total
    lo, hi = profile["min_levels"], profile["max_levels"]
    checks["level_count"] = {
        "status": "pass" if lo <= levels_total <= hi else "fail",
        "detail": f"{levels_total} levels ({profile_name} needs {lo}-{hi})",
    }
    if trace_path is None:
        checks["trace"] = {"status": "fail", "detail": "no --trace: a winning trace is required"}
        return finish(report)
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    report["trace_sha256"] = hashlib.sha256(trace_path.read_bytes()).hexdigest()
    try:
        levels = [[decode_action(a) for a in level["actions"]] for level in trace["levels"]]
    except (KeyError, TypeError, VetError) as exc:
        checks["trace"] = {"status": "fail", "detail": f"unreadable trace: {exc}"}
        return finish(report)
    if len(levels) != levels_total:
        checks["trace"] = {"status": "fail", "detail": f"trace covers {len(levels)} levels, the game has {levels_total}"}
        return finish(report)
    report["trace_actions_per_level"] = [len(level) for level in levels]

    # 1. The recorded win.
    first = replay_trace(cls, levels)
    if first["problem"]:
        checks["win_trace"] = {"status": "fail", "detail": first["problem"]}
        return finish(report)
    checks["win_trace"] = {"status": "pass", "detail": f"clears all {levels_total} levels in {sum(map(len, levels))} actions and ends in WIN"}

    # 2. Determinism: a second fresh replay, and each level replayed from a deep copy.
    second = replay_trace(cls, levels)
    same = second["hashes"] == first["hashes"]
    checks["determinism"] = {
        "status": "pass" if same else "fail",
        "detail": "two fresh replays produce identical frames" if same else "two fresh replays differ: hidden randomness, time, or shared module state",
    }
    copy_problem = None
    offset = 1
    for index, actions in enumerate(levels):
        player = Player(copy.deepcopy(first["snapshots"][index]))
        for position, (action_id, data) in enumerate(actions):
            result = player.act(action_id, data)
            if frame_hash(result.frame) != first["hashes"][offset + position][0]:
                copy_problem = f"level {index + 1}, action {position + 1}"
                break
        if copy_problem:
            break
        offset += len(actions)
    checks["deepcopy"] = {
        "status": "fail" if copy_problem else "pass",
        "detail": f"a deep copy diverges at {copy_problem} (the site's Undo deep-copies the game)" if copy_problem else "replays from deep copies match (Undo-safe)",
    }

    # 3. RESET restarts the current level, keeps completed ones, and the level stays winnable.
    reset_problems, reset_warnings = [], []
    for index, actions in enumerate(levels):
        player = Player(copy.deepcopy(first["snapshots"][index]))
        for action_id, data in actions[: max(1, min(3, len(actions) - 1))]:
            player.act(action_id, data)
        if player.completed > index:
            continue  # a one-action level: nothing to interrupt
        result = player.reset()
        if player.state != player.GameState.NOT_FINISHED or player.completed != index:
            reset_problems.append(f"level {index + 1}: RESET left state {player.state}, levels completed {player.completed}")
            continue
        if not (result.frame[-1] == first["level_start_frames"][index]).all():
            reset_warnings.append(f"level {index + 1}")
        for action_id, data in actions:
            player.act(action_id, data)
        if player.completed != index + 1:
            reset_problems.append(f"level {index + 1}: its trace no longer wins after a RESET")
    checks["reset"] = (
        {"status": "fail", "detail": "; ".join(reset_problems)}
        if reset_problems
        else {
            "status": "warn" if reset_warnings else "pass",
            "detail": (
                f"RESET keeps completed levels and each level is winnable after it; the post-RESET frame differs from the level's first frame on {', '.join(reset_warnings)}"
                if reset_warnings
                else "RESET restores each level exactly, keeps completed levels, and the level is winnable after it"
            ),
        }
    )

    # 4. Level 1 is short.
    l1 = len(levels[0])
    short_ok = l1 <= L1_MAX_ACTIONS
    checks["level1_short"] = {
        "status": "pass" if short_ok else ("fail" if profile["strict_l1_length"] else "warn"),
        "detail": f"the recorded level-1 win takes {l1} actions (limit {L1_MAX_ACTIONS})",
    }

    # 5-7. Random play: level-1 safety, early deaths on every level, resistance on levels 2+.
    clock = Clock(time_budget)
    rng = random.Random(seed)
    per_action = max(first["seconds_per_action"], 1e-4)
    silent: dict[int, int] = {}
    tried: dict[int, int] = {}
    fuzz_problem = None
    max_frames = max(first["max_frames"], second["max_frames"])
    random_report: dict[str, Any] = {"mode": "uniform over available actions; clicks split between anywhere, a random on-screen colour, and engine click targets", "seed": seed, "levels": []}

    def runs(snapshot, count, budget, retry, share):
        nonlocal fuzz_problem, max_frames
        results = []
        stop_at = time.monotonic() + max(1.0, clock.left() * share)
        for _ in range(count):
            if time.monotonic() > stop_at or clock.left() <= 0:
                break
            try:
                outcome = random_run(snapshot, rng, budget, retry)
            except Exception as exc:  # an exception under random input is a crash on the site
                fuzz_problem = f"{type(exc).__name__}: {exc}"[:300]
                break
            results.append(outcome)
            max_frames = max(max_frames, outcome["max_frames"])
            for key, value in outcome["silent"].items():
                silent[key] = silent.get(key, 0) + value
            for key, value in outcome["tried"].items():
                tried[key] = tried.get(key, 0) + value
        return results

    l1_runs = runs(first["snapshots"][0], 24, 150, retry=False, share=0.15)
    l1_deaths = sum(1 for r in l1_runs if r["game_over_at"] is not None)
    checks["level1_safe"] = {
        "status": "fail" if l1_deaths else ("warn" if len(l1_runs) < 12 else "pass"),
        "detail": f"{l1_deaths} of {len(l1_runs)} random runs of up to 150 actions reached GAME_OVER on level 1",
    }
    early_fail, early_detail = [], []
    resistance_clears, resistance_detail = [], []
    level_share = 0.85 / max(1, levels_total)
    for index in range(levels_total):
        snapshot = first["snapshots"][index]
        early = runs(snapshot, 24, EARLY_WINDOW, retry=False, share=level_share * 0.2)
        rate = sum(1 for r in early if r["game_over_at"] is not None) / max(1, len(early))
        entry = {"level": index + 1, "early_runs": len(early), "early_game_over_rate": round(rate, 3)}
        if rate > EARLY_DEATH_LIMIT:
            early_fail.append(index + 1)
        early_detail.append(f"L{index + 1} {rate:.0%}")
        if index >= 1:
            budget = 250
            count = int(min(40, max(8, (clock.left() * level_share) / (per_action * budget + 1e-9))))
            resist = runs(snapshot, count, budget, retry=True, share=level_share * 0.8)
            cleared = [r["cleared_at"] for r in resist if r["cleared_at"] is not None]
            lost = sum(1 for r in resist if r.get("reset_lost_progress"))
            entry.update({"resistance_runs": len(resist), "horizon": budget, "cleared": len(cleared), "fastest_clear": min(cleared) if cleared else None, "reset_lost_progress": lost})
            if cleared:
                resistance_clears.append(index + 1)
            resistance_detail.append(f"L{index + 1} {len(cleared)}/{len(resist)}")
            if lost:
                fuzz_problem = fuzz_problem or f"level {index + 1}: RESET after GAME_OVER lost completed levels"
        random_report["levels"].append(entry)
        if fuzz_problem:
            break
    report["random"] = random_report
    checks["early_death"] = {
        "status": "fail" if early_fail else "pass",
        "detail": f"share of random runs that reach GAME_OVER within {EARLY_WINDOW} actions: {', '.join(early_detail)} (limit {EARLY_DEATH_LIMIT:.0%})",
    }
    if levels_total > 1:
        status = "pass"
        if resistance_clears:
            status = "fail" if profile["strict_resistance"] else "warn"
        checks["random_resistance"] = {
            "status": status,
            "detail": f"random runs of 250 actions (retrying after GAME_OVER) that cleared the level: {', '.join(resistance_detail)}"
            + (f"; cleared: levels {resistance_clears}" if resistance_clears else ""),
        }
    checks["fuzz"] = (
        {"status": "fail", "detail": f"random input broke the game: {fuzz_problem}"}
        if fuzz_problem
        else {"status": "pass", "detail": f"{sum(tried.values())} random actions: no exception, every frame valid"}
    )
    checks["frames_per_action"] = {
        "status": "fail" if max_frames > FRAMES_FAIL else ("warn" if max_frames > FRAMES_WARN else "pass"),
        "detail": f"longest action plays {max_frames} frames (warn over {FRAMES_WARN}, fail over {FRAMES_FAIL}; the site plays ~30 per second)",
    }
    noisy = {k: round(silent.get(k, 0) / v, 2) for k, v in sorted(tried.items()) if v}
    quiet_keys = [k for k, share in noisy.items() if k != 6 and share > 0.5]
    checks["visible_response"] = {
        "status": "warn" if quiet_keys else "pass",
        "detail": f"share of random actions with no visible change, by action: {noisy}"
        + (f"; actions {quiet_keys} are silent most of the time: a refused move should look refused" if quiet_keys else ""),
    }
    if strips is not None:
        report["strips"] = write_strips(first["multi_frame_actions"], strips)
    return finish(report)


def finish(report: dict[str, Any]) -> dict[str, Any]:
    statuses = [c["status"] for c in report["checks"].values()]
    report["verdict"] = "fail" if "fail" in statuses or not report["checks"] else "pass"
    report["warnings"] = [name for name, c in report["checks"].items() if c["status"] == "warn"]
    return report


def write_strips(actions: list[tuple[int, int, list]], out_dir: Path, limit: int = 8) -> list[str]:
    """Save a few of the trace's multi-frame actions as left-to-right picture strips."""
    from PIL import Image

    out_dir.mkdir(parents=True, exist_ok=True)
    if not actions:
        return []
    step = max(1, len(actions) // limit)
    written = []
    for level, position, frames in actions[::step][:limit]:
        frames = frames[:16]
        scale, gap = 3, 4
        strip = Image.new("RGB", (len(frames) * (64 * scale + gap) - gap, 64 * scale), (40, 40, 40))
        for i, frame in enumerate(frames):
            tile = Image.new("RGB", (64, 64))
            tile.putdata([PALETTE[int(v)] for v in frame.flatten()])
            strip.paste(tile.resize((64 * scale, 64 * scale), Image.NEAREST), (i * (64 * scale + gap), 0))
        path = out_dir / f"L{level + 1}-a{position + 1}-{len(frames)}f.png"
        strip.save(path)
        written.append(path.name)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--trace", type=Path, help="winning trace JSON (format arc3-trace/1)")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="glowup")
    parser.add_argument("--class-name")
    parser.add_argument("--out", type=Path, help="write the JSON report here")
    parser.add_argument("--strips", type=Path, help="write animation strips of multi-frame trace actions here")
    parser.add_argument("--time-budget", type=float, default=300.0, help="seconds for the random-play checks")
    parser.add_argument("--seed", type=int, default=20260919)
    args = parser.parse_args(argv)
    try:
        report = vet(args.source, args.trace, args.profile, args.class_name, args.time_budget, args.seed, args.strips)
    except VetError as exc:
        print(f"vet_game: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(report, indent=1)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    width = max(len(name) for name in report["checks"]) if report["checks"] else 0
    for name, check in report["checks"].items():
        print(f"  {check['status'].upper():4}  {name:<{width}}  {check['detail']}")
    print(f"verdict: {report['verdict'].upper()}  ({report['source']} sha256 {report['source_sha256'][:12]}, profile {report['profile']})")
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())

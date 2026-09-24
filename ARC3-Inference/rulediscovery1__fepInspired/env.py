# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: A local, GPU-free environment that simulates an ARC-3 game exactly, asked by OpenMind in
#   #arc-3 (23-Sep-2026 22:34 ET: "look at locksmith traces and implement a environment which simulates
#   the game"). Instead of re-writing the game's rules by hand, it runs the game's own source
#   (docs/static/games/src/<game>-<build>/<game>.py) on the vendored ARC engine (vendor/arcengine-0.9.3),
#   so every mechanic is the real one. Locksmith (ls20, build 9607627b, the build the Kaggle traces were
#   played on) is the default. verify_env.py replays every recorded play through this class and checks
#   the board after every action.
#     - GameEnv(game, build): reset() -> Obs; step(Action) -> Obs. Obs holds the 64x64 grid (the last
#       frame of the action, as the harness sees it), levels completed, win levels, state, the valid
#       action names and every intermediate animation frame.
#     - Actions are this package's perception.Action (ACTION1..7, RESET; ACTION6 carries row/col and is
#       sent to the engine as x=col, y=row).
#     - RESET follows the harness pin ONLY_RESET_LEVELS=true (restart the current level, never the whole
#       game), which is what the recorded plays ran under.
#     - clone() deep-copies the game, so a planner can try actions without touching the real episode.
#   Needs Python 3.10+ (the engine uses match statements): run with ARC3-Inference/.venv/bin/python.
# SRP/DRY check: Pass -- no game logic here; the engine and the game source are loaded as they are.
#   The Action type is perception.Action, not restated. Only loading, stepping and the Obs shape are new.
"""GameEnv: run an ARC-3 game's own source locally (default: Locksmith, ls20)."""
from __future__ import annotations

import copy
import importlib.util
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .perception import CLICK, RESET, Action

REPO = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO / "vendor" / "arcengine-0.9.3"
GAMES_DIR = REPO / "docs" / "static" / "games" / "src"
DEFAULT_GAME, DEFAULT_BUILD = "ls20", "9607627b"      # Locksmith, the build the Kaggle plays used


def _engine():
    if sys.version_info < (3, 10):
        raise RuntimeError("the ARC engine needs Python 3.10+; run with ARC3-Inference/.venv/bin/python")
    os.environ["ONLY_RESET_LEVELS"] = "true"             # the harness pin: RESET restarts the level
    if str(ENGINE_DIR) not in sys.path:
        sys.path.insert(0, str(ENGINE_DIR))
    import arcengine
    return arcengine


def load_game_class(game: str = DEFAULT_GAME, build: str = DEFAULT_BUILD):
    """The ARCBaseGame subclass defined in the game's source file."""
    arc = _engine()
    path = GAMES_DIR / f"{game}-{build}" / f"{game}.py"
    if not path.exists():
        raise FileNotFoundError(f"no source for {game}-{build} at {path}")
    spec = importlib.util.spec_from_file_location(f"arc3_game_{game}_{build}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    classes = [v for v in vars(mod).values()
               if isinstance(v, type) and issubclass(v, arc.ARCBaseGame) and v is not arc.ARCBaseGame]
    if len(classes) != 1:
        raise RuntimeError(f"expected one game class in {path}, found {[c.__name__ for c in classes]}")
    return classes[0]


@dataclass
class Obs:
    grid: list                      # 64x64 board after the action (last rendered frame)
    levels_completed: int
    win_levels: int
    state: str                      # NOT_FINISHED / WIN / GAME_OVER
    valid_actions: list[str]
    frames: list = field(default_factory=list)   # every animation frame of this action
    level_completed: bool = False   # this action cleared a level
    changed: bool = True            # the board differs from the previous one

    @property
    def done(self) -> bool:
        return self.state in ("WIN", "GAME_OVER")


class GameEnv:
    def __init__(self, game: str = DEFAULT_GAME, build: str = DEFAULT_BUILD):
        self.game_name, self.build = game, build
        self._arc = _engine()
        self._cls = load_game_class(game, build)
        self.game = None
        self.last: Optional[Obs] = None
        self.n_actions = 0

    def _to_obs(self, fd, prev: Optional[Obs]) -> Obs:
        frames = [f.tolist() if hasattr(f, "tolist") else f for f in (fd.frame or [])]
        grid = frames[-1] if frames else (prev.grid if prev else None)   # a refused action draws nothing
        lv = int(fd.levels_completed)
        valid = [f"ACTION{int(getattr(a, 'value', a))}" for a in (fd.available_actions or [])]
        return Obs(grid=grid, levels_completed=lv, win_levels=int(fd.win_levels), state=fd.state.name,
                   valid_actions=valid, frames=frames,
                   level_completed=prev is not None and lv > prev.levels_completed,
                   changed=prev is None or grid != prev.grid)

    def reset(self) -> Obs:
        """A fresh game (full reset), as at the start of a play."""
        self.game = self._cls()
        self.n_actions = 0
        fd = self.game.perform_action(self._arc.ActionInput(id=self._arc.GameAction.RESET))
        self.last = self._to_obs(fd, None)
        return self.last

    def step(self, action: Action) -> Obs:
        if self.game is None:
            raise RuntimeError("call reset() first")
        data = {"x": int(action.col), "y": int(action.row)} if action.name == CLICK else {}
        fd = self.game.perform_action(self._arc.ActionInput(id=self._arc.GameAction[action.name], data=data))
        if action.name != RESET:
            self.n_actions += 1
        self.last = self._to_obs(fd, self.last)
        return self.last

    def clone(self) -> "GameEnv":
        """An independent copy of the current episode (for look-ahead)."""
        other = copy.copy(self)
        other.game = copy.deepcopy(self.game)
        other.last = copy.deepcopy(self.last)
        return other

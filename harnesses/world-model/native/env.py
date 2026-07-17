"""Native arcengine env driver for the world-model harness.

Drives an ARC-AGI-3 arcengine game directly -- the same engine our duck-harness
uses. This is engine PLUMBING, not the world-model method: the method
(synthesize an executable transition function, verify it by exact replay, plan by
simulating) is built natively in wm.py. The apply+settle loop and object
extraction follow arcengine's own contract (`_set_action`, then `step()` until
`is_action_complete()`; objects from `current_level._sprites`), so transitions
are faithful to the real game -- which is what makes exact-replay verification
meaningful.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ACTION_NAMES = {0: "RESET", 1: "ACTION1", 2: "ACTION2", 3: "ACTION3",
                4: "ACTION4", 5: "ACTION5", 6: "ACTION6", 7: "ACTION7"}


def load_game_class(name: str, env_root: str):
    root = Path(env_root) / name
    cands = sorted(root.rglob(f"{name}.py"))
    if not cands:
        raise FileNotFoundError(f"no {name}.py under {root}")
    py = cands[0]
    from arcengine import ARCBaseGame
    spec = importlib.util.spec_from_file_location(name, py)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if isinstance(obj, type) and obj is not ARCBaseGame and issubclass(obj, ARCBaseGame):
            return obj
    raise RuntimeError(f"no ARCBaseGame subclass in {py}")


class ArcEnv:
    """Thin, faithful wrapper: reset / step(action) -> (state, reward, done),
    where state is an object-centric list of records."""

    def __init__(self, name: str, env_root: str = "environment_files"):
        self.name = name
        self.game = load_game_class(name, env_root)()

    def reset(self):
        return self.extract_state()

    def available_actions(self) -> list[int]:
        declared = list(self.game._available_actions)
        out = [0] + declared
        if 7 not in declared:
            out.append(7)
        return out

    def level_index(self) -> int:
        return int(self.game.level_index)

    def is_won(self) -> bool:
        return str(getattr(self.game, "_state", "")) == "GameState.WIN"

    def is_over(self) -> bool:
        return str(getattr(self.game, "_state", "")) == "GameState.GAME_OVER"

    def extract_state(self) -> list[dict]:
        """Object-centric state: one record per sprite (skip full-screen bg)."""
        objs = []
        try:
            sprites = self.game.current_level._sprites
        except Exception:
            return objs
        for s in sprites:
            if getattr(s, "width", 0) >= 64 and getattr(s, "height", 0) >= 64:
                continue
            objs.append({
                "name": s.name,
                "tags": list(s.tags) if getattr(s, "tags", None) else [],
                "x": int(s.x), "y": int(s.y),
                "w": int(s.width), "h": int(s.height),
            })
        return objs

    def candidate_actions(self, state=None, max_clicks=48):
        """Generalized action set as dicts {'id','x','y'}. Directional actions as-is,
        plus salient CLICKS (action 6) at the center of each distinct object -- the
        interactive targets in point-and-click games (walls/full-bg excluded)."""
        state = state if state is not None else self.extract_state()
        acts = [{"id": a, "x": None, "y": None}
                for a in self.available_actions() if a in (1, 2, 3, 4, 5)]
        if 6 in self.available_actions():
            seen = set()
            for o in state:
                cx, cy = int(o["x"] + o["w"] // 2), int(o["y"] + o["h"] // 2)
                if (cx, cy) in seen:
                    continue
                seen.add((cx, cy))
                acts.append({"id": 6, "x": cx, "y": cy})
                if len(acts) >= max_clicks + 5:
                    break
        return acts

    def apply(self, action):
        """Step with a generalized action dict {'id','x','y'}."""
        if isinstance(action, dict):
            return self.step(action["id"], x=action.get("x"), y=action.get("y"))
        return self.step(action)

    def step(self, action_id: int, x=None, y=None):
        from arcengine import ActionInput, GameAction
        amap = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
                4: GameAction.ACTION4, 5: GameAction.ACTION5, 6: GameAction.ACTION6,
                7: GameAction.ACTION7}
        if action_id == 0:
            try:
                self.game.handle_reset()
            except Exception:
                pass
            return self.extract_state(), 0.0, False
        if self.is_over() or self.is_won():
            return self.extract_state(), 0.0, False
        level_before = self.level_index()
        if action_id == 6 and x is not None and y is not None:
            a = ActionInput(id=amap[6], data={"x": int(x), "y": int(y)})
        else:
            a = ActionInput(id=amap[action_id])
        try:
            from arcengine import base_game as _bg
            max_frames = int(getattr(_bg, "MAX_FRAME_PER_ACTION", 1000))
            self.game._set_action(a)
            safety = 0
            while not self.game.is_action_complete():
                if safety > max_frames:
                    break
                safety += 1
                if getattr(self.game, "_next_level", False):
                    self.game._really_set_next_level()
                else:
                    self.game.step()
        except Exception:
            try:
                self.game.perform_action(a)
            except Exception:
                pass
        level_after = self.level_index()
        won = self.is_won()
        reward = 1.0 if (level_after > level_before or won) else 0.0
        done = bool(level_after > level_before or won)
        return self.extract_state(), reward, done

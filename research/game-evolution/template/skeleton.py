"""Engine plumbing only -- NOT a design to copy.

Author: Claude Opus 5, 19-September-2026
Purpose: the smallest game that shows how an evolution-loop game meets the loop's technical
rules on arcengine 0.9.3: real sprites in the engine's object model, rule state kept apart
from presentation, a move that animates as one intact sprite over a few frames, a refused
move that is visible instead of silent, and a RESET that restores the level. It is the test
fixture for scripts/vet_game.py. Its mechanic (walk to the green cell) and its look are
deliberately bare; authors must not reuse either.
"""

from arcengine import ARCBaseGame, BlockingMode, Camera, GameAction, Level, Sprite

TILE = 6  # screen pixels per board cell (camera is 64x64 at scale 1)
WALL, FLOOR, GOAL, MOVER = 3, 0, 14, 9
STEPS_PER_MOVE = 3  # a one-cell move plays as 3 frames of 2 pixels each: short and rigid

MAPS = [
    ["#######", "#S...G#", "#######"],
    ["#######", "#S#...#", "#.#.#.#", "#...#G#", "#######"],
    ["#########", "#S..#...#", "##.##.#.#", "#...#.#G#", "#.#...#.#", "#########"],
]
MOVES = {GameAction.ACTION1: (0, -1), GameAction.ACTION2: (0, 1), GameAction.ACTION3: (-1, 0), GameAction.ACTION4: (1, 0)}


def _block(color: int, w: int = TILE, h: int = TILE) -> list[list[int]]:
    return [[color] * w for _ in range(h)]


def _level(rows: list[str], index: int) -> Level:
    ox = (64 - len(rows[0]) * TILE) // 2
    oy = (64 - len(rows) * TILE) // 2
    board = [[WALL if ch == "#" else FLOOR for ch in row for _ in range(TILE)] for row in rows for _ in range(TILE)]
    sprites = [Sprite(board, name="board", x=ox, y=oy, layer=0)]
    start = goal = None
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch == "S":
                start = (c, r)
            elif ch == "G":
                goal = (c, r)
    sprites.append(Sprite(_block(GOAL), name="goal", x=ox + goal[0] * TILE, y=oy + goal[1] * TILE, layer=1))
    body = _block(MOVER)
    body[0][0] = body[0][-1] = body[-1][0] = body[-1][-1] = FLOOR  # rounded corners: a silhouette, not a square
    sprites.append(
        Sprite(body, name="mover", x=ox + start[0] * TILE, y=oy + start[1] * TILE, layer=2, blocking=BlockingMode.NOT_BLOCKED)
    )
    return Level(sprites=sprites, name=f"level-{index + 1}", data={"rows": rows, "origin": (ox, oy), "start": start, "goal": goal})


class Skeleton(ARCBaseGame):
    def __init__(self) -> None:
        self.cell = (0, 0)
        self.frames: list[tuple[int, int]] = []  # pending presentation positions (pixels)
        self.finish = None  # what to do after the last presentation frame
        super().__init__(game_id="skeleton", levels=[_level(m, i) for i, m in enumerate(MAPS)], camera=Camera(background=5), available_actions=[1, 2, 3, 4])

    def on_set_level(self, level: Level) -> None:
        # Runs on start, level change, RESET: rule state comes from the clean level, never from the frame.
        self.cell = level.get_data("start")
        self.frames = []
        self.finish = None

    def _screen(self, cell: tuple[int, int]) -> tuple[int, int]:
        ox, oy = self.current_level.get_data("origin")
        return ox + cell[0] * TILE, oy + cell[1] * TILE

    def step(self) -> None:
        if self.action.id == GameAction.RESET:  # the engine calls step() once for RESET too
            self.complete_action()
            return
        mover = self.current_level.get_sprites_by_name("mover")[0]
        if not self.frames:  # a new action: decide the rule outcome once, then only present it
            dx, dy = MOVES.get(self.action.id, (0, 0))
            rows = self.current_level.get_data("rows")
            target = (self.cell[0] + dx, self.cell[1] + dy)
            x0, y0 = self._screen(self.cell)
            if (dx, dy) != (0, 0) and rows[target[1]][target[0]] != "#":
                self.cell = target
                x1, y1 = self._screen(target)
                self.frames = [(x0 + (x1 - x0) * k // STEPS_PER_MOVE, y0 + (y1 - y0) * k // STEPS_PER_MOVE) for k in range(1, STEPS_PER_MOVE + 1)]
                self.finish = "check-goal"
            else:
                # Refused: a visible 1-pixel nudge toward the wall and back. Nothing in the rules changes.
                self.frames = [(x0 + dx, y0 + dy), (x0, y0)]
                self.finish = None
        x, y = self.frames.pop(0)
        mover.set_position(x, y)  # the whole sprite moves: it can never split, smear or trail
        if not self.frames:
            if self.finish == "check-goal" and self.cell == self.current_level.get_data("goal"):
                self.next_level()
            self.complete_action()

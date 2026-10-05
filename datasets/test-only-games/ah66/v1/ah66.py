"""
HELD-OUT TEST COPY -- TEST ONLY, NEVER TRAIN. as66 is in our team's held-out set; this copycat
exists only to measure play on unseen surface variants of it. Do not feed it, its frames or its
solution replay into any training, fine-tuning, RL or prompt-example pipeline.

Author: Claude Opus 5.5 (Bubba sub-agent, 04-Oct-2026 copycat). Rule code is the as66
        recreation by Claude Fable 5.1 (16-Sep-2026) and Claude Opus 5 (17-Sep-2026), unchanged.
Date: 04-October-2026
PURPOSE: AH66 -- a "close copy cat" of AS66 "Always Sliding" for held-out evaluation only.

         KEPT (rule code copied verbatim from environment_files/as66/v1/as66.py): one-cell blocks
         slide until they hit something; the field wraps like a torus; 3x3 enemies with a core
         patrol and kill on contact (enemies step before the block slides); bars recolour a block
         that slides through them; every block must sit in a cup whose back-wall marker is the
         cup colour (any block) or the block's own colour; the ring side shows the last direction
         and pressing that side again is a free no-op; a per-level move budget fills a meter and
         the move that fills it loses; the winning move is not charged; four directions, nine
         levels, each mechanic introduced on the same level as the original (L1-2 one block and
         a plain cup, L3 first enemy, L4 two blocks and coloured markers, L5 first recolour bar
         with several enemies, L6-8 bar + enemy combinations, L9 two blocks, two bars, an enemy).

         CHANGED: every level map is new (searched by tools/gen_ah66.py and proven solvable,
         replays in dist/solutions/ah66.json); grid sizes differ; the colour of every role is moved
         by one fixed permutation (below); cell size per level differs from the original's;
         blocks are drawn as notched tiles and enemies as a hollow frame with a solid core; the
         ring corners are open; the move meter runs along the BOTTOM row and up the sides
         (originally top row and down the sides) and the level-progress bar is on the TOP row
         (originally bottom).

         Rendering, as in the original: the whole 64x64 frame is drawn into one canvas sprite from
         a cell model; collision uses the cell model, never sprites.
SRP/DRY check: Pass -- the original's model and rules are reused verbatim; only level data,
         palette constants and _draw differ.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from arcengine import ARCBaseGame, Camera, GameAction, Level, Sprite

# --------------------------------------------------------------------------------------
# Palette (ARC-3 indices). COPYCAT: every role keeps its original NAME so the rule code reads
# the same, but its colour is moved by one fixed permutation of the 16 colours:
#   0->5 1->2 2->1 3->0 4->13 5->3 6->14 7->7 8->9 9->6 10->8 11->15 12->4 13->12 14->11 15->10
# A permutation keeps "marker colour == block colour" exactly as the original had it.
# --------------------------------------------------------------------------------------
WHITE = 5  # cups (originally white)
LIGHT_GRAY = 2  # ring
DARK_GRAY = 0  # backdrop
WALL = 13
BLACK = 3  # progress-bar track
PINK = 14
RED = 9
BLUE = 6
LIGHT_BLUE = 8
YELLOW = 15
ORANGE = 4  # enemy body, meter track
DARK_RED = 12  # enemy core, meter fill
GREEN = 11  # ring side
PURPLE = 10  # field floor

BLOCK_COLORS = (RED, YELLOW, LIGHT_BLUE, PINK, BLUE)
BAR_COLORS = (BLUE, YELLOW, LIGHT_BLUE, PINK)
MARKER_COLORS = (WHITE, PINK, BLUE, LIGHT_BLUE, YELLOW)

HEX = "0123456789ABCDEF"

Cell = Tuple[int, int]
DIRS: Dict[str, Cell] = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
ACTION_TO_DIR = {GameAction.ACTION1: "UP", GameAction.ACTION2: "DOWN", GameAction.ACTION3: "LEFT", GameAction.ACTION4: "RIGHT"}
SIDE_OF_DIR = {"UP": "TOP", "DOWN": "BOTTOM", "LEFT": "LEFT", "RIGHT": "RIGHT"}

# --------------------------------------------------------------------------------------
# Level data -- COPYCAT maps written by tools/gen_ah66.py (field coordinates, one hex char per
# cell, in the permuted palette above: A floor, D wall, 5 cup, 4 enemy body, C enemy core,
# 9/F/8/E/6 block, marker or bar). Generated between the marker lines; edit the generator.
# --------------------------------------------------------------------------------------
# <<LEVEL_SPECS
LEVEL_SPECS: List[dict] = [
    dict(
        par=3, budget=15, cell=3, origin=(21, 5), green="RIGHT",
        grid=[
            "AAAAAAAAAADD",
            "DDAAAAAAAAAA",
            "ADDDDDDDDDAD",
            "AAADDAAAAAAD",
            "AAAAAAAADDDA",
            "AAAAAAAAADDA",
            "AAAADDDAADDD",
            "AAAAADAAAAAA",
            "AA55AAADDAAA",
            "AAA5AAAAAAAA",
            "AA55AAAAADAA",
            "AAAAAAAAAAAA",
            "AA9AAADAAAAA",
            "AAAAADDDAAAA",
        ],
    ),
    dict(
        par=4, budget=16, cell=3, origin=(11, 17), green="LEFT",
        grid=[
            "AAAAAAAAAAA",
            "ADAAAAAAA55",
            "AAAAAAAAAA5",
            "DAAAAAAAA55",
            "DDAAAADAAAA",
            "AAAAAADDDAA",
            "AAAAAADDAAA",
            "AFAAAAAAAAD",
            "AAAAAAAAADD",
            "AAAAAAAADDD",
            "AAAAAAAAAAA",
            "AAAAAAAAAAA",
        ],
    ),
    dict(
        par=8, budget=21, cell=3, origin=(18, 11), green="BOTTOM",
        grid=[
            "AA444AAAAAAA",
            "AA44CAAAAAAA",
            "AA444AAAAAAA",
            "AAAAAAAAADAA",
            "DAAAAAAADDAA",
            "AAA55ADDDAAA",
            "AAAA5ADAAAAA",
            "DAA55AAAAAAA",
            "ADAAAAAAAFAA",
            "ADDDAADAAAAA",
            "ADAAAADAAAAA",
        ],
    ),
    dict(
        par=4, budget=10, cell=3, origin=(8, 22), green="BOTTOM",
        grid=[
            "AADAAAADDAAAD",
            "AADDAAADAAADD",
            "AAADDDAADADDD",
            "ADAAAAAAAADAA",
            "DAA55AAAAAAAA",
            "AAAA8AAAAAA8A",
            "AAA55AADAAAAA",
            "AAAAAAADAEAAA",
            "AAAAAAADAAAAA",
            "AAA55AAADDADD",
            "AAAAEAAAAAAAA",
            "AAA55AAAAAADA",
        ],
    ),
    dict(
        par=15, budget=23, cell=2, origin=(23, 3), green="RIGHT",
        grid=[
            "AA444AAAAAADDAAAAA",
            "AA444AAA8AADAAAAAA",
            "DA4C4AAAAAAAAAADAA",
            "DAAAAADDAAA444ADDA",
            "DAAAADDADAA4C4ADAA",
            "AAAAAAAAAAA444AADD",
            "AAAAAAAAAAAAAAAADD",
            "AAAAA444AAAAAAAAAD",
            "ADDAA4C4AAADAAAAAA",
            "ADDAA444AAAAAA444A",
            "AAAAAAAAAAAAAA4C4A",
            "AAAAAAFA5A5AAA444A",
            "DAAAAAFA5F5AAAAAAA",
            "DAAADAFAAAAAAADADA",
            "AADADAAAAAAAADDADA",
            "ADDAAAAAAAAAADAADA",
            "DDDAAAAAAAAAADAAAA",
            "AAAAAAADDAAAADDAAA",
            "AAAAAAADDAAAADDAAA",
        ],
    ),
    dict(
        par=10, budget=20, cell=4, origin=(5, 5), green="RIGHT",
        grid=[
            "AAAAAAAAAAAAA",
            "AAAEADAAAAAAA",
            "ADAAADAAAAAAA",
            "AAAADAAADDAAA",
            "AAAADADDDDDAA",
            "AADAAADDAADAA",
            "6AAAAAADAADAA",
            "6AAAAAADAAAAA",
            "6A5A5ADAAAAAA",
            "AA565AAAAAAAA",
            "DAAAAA444AAAA",
            "ADADDA44CAADD",
            "ADADDA444AAAA",
        ],
    ),
    dict(
        par=7, budget=20, cell=3, origin=(11, 6), green="BOTTOM",
        grid=[
            "ADDDAAADAAAAAAA",
            "AADDDAADDAAAAAA",
            "DAADAAAAAAAAAAA",
            "AAADAAAAAAA666A",
            "AAAAAAAEAAAAAAA",
            "A55AAAAAAAADAAA",
            "A6AAAAAAAAAAAAD",
            "A55AAAAAAAAADDA",
            "AAAAADAAAAAAAAA",
            "AAAADAAAAAADDAA",
        ],
    ),
    dict(
        par=11, budget=34, cell=2, origin=(10, 16), green="RIGHT",
        grid=[
            "AAAAAAAAAADAAAA",
            "AAAAAAAAAADAAAA",
            "AAAFAA666ADAAAA",
            "AAAAAAAAAAAAAAA",
            "44CAADAAAAAAAAA",
            "444AADADAAAAAAA",
            "444AAADDDAAAAAA",
            "AAAADAAAAAAAAAA",
            "AAAADA565AAAAAA",
            "ADAAAA5A5ADA444",
            "ADDDAAAAAADA444",
            "ADAAAAAAAAAA44C",
            "ADAAAADAAAAAAAA",
            "AAAAAAAAADAAAAA",
            "AAAAAAAAADAAAAA",
        ],
    ),
    dict(
        par=12, budget=33, cell=3, origin=(4, 10), green="TOP",
        grid=[
            "AAAAAAAAAAAAAAADAD",
            "AAAAAAAAAAAAAAADDD",
            "AADDADA666AAAAADAA",
            "AAAAAAAAAAAAAADDAA",
            "AAAA444AAAAAAAAADD",
            "AAAA44CAAAAAAAAAAD",
            "AAAA444AAAAAAAAADD",
            "DADAAAAAAA8AAAAADA",
            "AADDAFADAAAAAAAAAA",
            "DDAAAFAADAAAAADDDA",
            "AAAAAFAADDDAAAAADA",
            "555AAAAAAAAA565AAA",
            "5A5AAAAAAADA5A5AAA",
            "AAAAAAAAAADAAAAAAD",
            "AAAAAAAAAADAAAADAD",
            "AAFAAAAAAAAAAAADAD",
        ],
    ),
]
# LEVEL_SPECS>>

WIN_LEVELS = len(LEVEL_SPECS)


# --------------------------------------------------------------------------------------
# Level model (unchanged from the original)
# --------------------------------------------------------------------------------------
@dataclass
class Cup:
    pocket: Cell
    opening: str
    marker_cell: Cell
    required: Optional[int]  # None = any color
    whites: List[Cell]


@dataclass
class Enemy:
    origin: Cell  # top-left of the 3x3 at level start
    pos: Cell
    dir0: Cell  # initial heading, (0,0) for static
    heading: Cell

    def cells(self, pos: Optional[Cell] = None) -> List[Cell]:
        x, y = pos or self.pos
        return [(x + dx, y + dy) for dy in range(3) for dx in range(3)]

    def core(self) -> Cell:
        return (self.pos[0] + 1 + self.heading[0], self.pos[1] + 1 + self.heading[1])


@dataclass
class Block:
    pos: Cell
    color: int
    start: Cell = (0, 0)
    moving: bool = False


@dataclass
class FieldModel:
    cols: int
    rows: int
    walls: Set[Cell] = field(default_factory=set)
    cups: List[Cup] = field(default_factory=list)
    bars: Dict[Cell, int] = field(default_factory=dict)
    enemies: List[Enemy] = field(default_factory=list)
    blocks: List[Block] = field(default_factory=list)

    # cells no block or enemy may ever enter
    def solid(self) -> Set[Cell]:
        s = set(self.walls)
        for c in self.cups:
            s.update(c.whites)
            s.add(c.marker_cell)
        return s


def _heading_from_core(dx: int, dy: int) -> Cell:
    return (dx, dy)


def parse_grid(grid: List[str]) -> FieldModel:
    rows, cols = len(grid), len(grid[0])
    g = [[HEX.index(ch) for ch in row] for row in grid]
    m = FieldModel(cols=cols, rows=rows)

    def at(x: int, y: int) -> Optional[int]:
        return g[y][x] if 0 <= x < cols and 0 <= y < rows else None

    for y in range(rows):
        for x in range(cols):
            if g[y][x] == WALL:
                m.walls.add((x, y))

    # enemies: 3x3 orange with one dark-red core
    for y in range(rows - 2):
        for x in range(cols - 2):
            blk = [g[y + dy][x + dx] for dy in range(3) for dx in range(3)]
            if sorted(blk) == sorted([ORANGE] * 8 + [DARK_RED]):
                k = blk.index(DARK_RED)
                d = (k % 3 - 1, k // 3 - 1)
                m.enemies.append(Enemy(origin=(x, y), pos=(x, y), dir0=d, heading=d))

    # cups: a 3-cell white back wall (center may be a colored marker), two white legs, a purple pocket
    for y in range(rows):
        for x in range(cols):
            mk = g[y][x]
            if mk not in MARKER_COLORS:
                continue
            for (ax, ay), (px, py), opening in (((1, 0), (0, -1), "UP"), ((1, 0), (0, 1), "DOWN"), ((0, 1), (-1, 0), "LEFT"), ((0, 1), (1, 0), "RIGHT")):
                b1 = (x - ax, y - ay)
                b2 = (x + ax, y + ay)
                l1 = (b1[0] + px, b1[1] + py)
                l2 = (b2[0] + px, b2[1] + py)
                pocket = (x + px, y + py)
                if all(at(*c) == WHITE for c in (b1, b2, l1, l2)) and at(*pocket) == PURPLE:
                    m.cups.append(Cup(pocket=pocket, opening=opening, marker_cell=(x, y), required=None if mk == WHITE else mk, whites=[b1, b2, l1, l2]))

    cup_cells = {c for cup in m.cups for c in cup.whites} | {cup.marker_cell for cup in m.cups}

    # bars (straight runs of >= 2 colored cells) and single blocks
    for color in BLOCK_COLORS:
        cs = {(x, y) for y in range(rows) for x in range(cols) if g[y][x] == color and (x, y) not in cup_cells}
        for (x, y) in sorted(cs):
            if (x - 1, y) in cs or (x, y - 1) in cs:
                continue
            run = [(x, y)]
            if (x + 1, y) in cs:
                while (run[-1][0] + 1, y) in cs:
                    run.append((run[-1][0] + 1, y))
            elif (x, y + 1) in cs:
                while (x, run[-1][1] + 1) in cs:
                    run.append((x, run[-1][1] + 1))
            if len(run) >= 2:
                for c in run:
                    m.bars[c] = color
            else:
                m.blocks.append(Block(pos=(x, y), color=color, start=(x, y)))
    return m


# --------------------------------------------------------------------------------------
# The game
# --------------------------------------------------------------------------------------
class Ah66(ARCBaseGame):
    """AH66 -- held-out copycat of Always Sliding (TEST ONLY, NEVER TRAIN)."""

    def __init__(self, seed: int = 0) -> None:
        levels = [Level(sprites=[Sprite(pixels=np.full((64, 64), DARK_GRAY, dtype=np.int8), name="canvas", layer=0, collidable=False)], data=dict(spec)) for spec in LEVEL_SPECS]
        super().__init__(
            game_id="ah66",
            levels=levels,
            camera=Camera(0, 0, 64, 64, background=DARK_GRAY, letter_box=DARK_GRAY),
            available_actions=[1, 2, 3, 4, 6],
            win_score=len(LEVEL_SPECS),
            seed=seed,
        )

    # ---------------------------------------------------------------- level lifecycle
    def on_set_level(self, level: Level) -> None:
        spec = {k: level.get_data(k) for k in ('par', 'budget', 'cell', 'origin', 'green', 'grid')}
        self._spec = spec
        self._model = parse_grid(spec["grid"])
        self._par: int = spec["par"]  # fewest counted moves that clear the level (found by the generator's search)
        self._budget: int = spec["budget"]  # the move on which the meter fills and the level is lost
        self._cell: int = spec["cell"]
        self._origin: Cell = tuple(spec["origin"])  # type: ignore[assignment]
        self._green: str = spec["green"]
        self._moves = 0
        self._meter_moves = 0  # the meter is redrawn on settle frames only, never on a death or winning frame
        self._sliding = False
        self._lapped = False
        self._before_move: Tuple[str, List[Tuple[Cell, Cell]], List[Tuple[Cell, int]]] = (self._green, [], [])
        self._canvas = level.get_sprites_by_name("canvas")[0]
        self._draw()

    # ---------------------------------------------------------------- input
    def step(self) -> None:
        action = self.action.id
        if self._sliding:
            self._slide_frame()
            return
        if action not in ACTION_TO_DIR:
            # RESET (already handled by the engine) and ACTION6 (accepted, inert, free)
            self._draw()
            self.complete_action()
            return
        direction = ACTION_TO_DIR[action]
        if SIDE_OF_DIR[direction] == self._green:
            # pressing the side the ring already shows: nothing happens, nothing is charged
            self.complete_action()
            return
        self._begin_move(direction)

    # ---------------------------------------------------------------- move resolution
    def _begin_move(self, direction: str) -> None:
        """Start a counted move: flip the ring, step the enemies, then slide (original rule)."""
        self._dir = DIRS[direction]
        self._moves += 1
        self._lapped = False
        self._before_move = (self._green, [(e.pos, e.heading) for e in self._model.enemies], [(b.pos, b.color) for b in self._model.blocks])
        for b in self._model.blocks:
            b.start = b.pos
            b.moving = True

        self._green = SIDE_OF_DIR[direction]
        self._step_enemies()
        if self._any_enemy_on_block():
            self._draw()
            self.lose()
            self.complete_action()
            return
        if not any(self._can_step(b) for b in self._model.blocks):
            # blocked in a new direction: enemies stepped and the meter fills, one frame
            for b in self._model.blocks:
                b.moving = False
            self._settle()
            return
        self._sliding = True
        self._slide_frame()

    def _can_step(self, b: Block) -> bool:
        solid = self._model.solid()
        occupied = {o.pos for o in self._model.blocks if o is not b}
        nxt = self._wrap((b.pos[0] + self._dir[0], b.pos[1] + self._dir[1]))
        return nxt not in solid and nxt not in occupied

    def _slide_frame(self) -> None:
        """Advance every moving block one cell (front-most first), render, and settle."""
        solid = self._model.solid()
        enemy_cells = {c for e in self._model.enemies for c in e.cells()}
        moving = [b for b in self._model.blocks if b.moving]
        if not moving:
            self._settle()
            return
        # front-most first along the direction of motion so trailing blocks stack behind
        moving.sort(key=lambda b: -(b.pos[0] * self._dir[0] + b.pos[1] * self._dir[1]))
        died = False
        arrived_home = False
        for b in moving:
            occupied = {o.pos for o in self._model.blocks if o is not b}
            nxt = self._wrap((b.pos[0] + self._dir[0], b.pos[1] + self._dir[1]))
            if nxt in solid or nxt in occupied:
                b.moving = False
                continue
            b.pos = nxt
            if nxt in self._model.bars:
                b.color = self._model.bars[nxt]
            if nxt in enemy_cells:
                died = True
            if nxt == b.start:
                # all the way round the torus and home: a block never passes its own start cell,
                # so no slide can run longer than one lap
                b.moving = False
                self._lapped = True
                arrived_home = True
            elif not self._can_step(b):
                b.moving = False  # stops now; the next frame is the settle frame
        if died:
            # the fatal frame is the last frame; the meter is not redrawn
            self._draw()
            self._sliding = False
            self.lose()
            self.complete_action()
            return
        if arrived_home and not any(b.moving for b in self._model.blocks):
            self._settle()
            return
        self._draw()

    def _settle(self) -> None:
        """End a counted move: win, take back a lap that changed nothing, charge the meter, check the budget."""
        self._sliding = False
        if self._all_cups_satisfied():
            # the winning move is not charged
            self._draw()
            self.next_level()  # win() is called by the engine on the last level
            self.complete_action()
            return
        green_before, enemies_before, blocks_before = self._before_move
        if self._lapped and [(b.pos, b.color) for b in self._model.blocks] == blocks_before:
            # A lap that left every block where it was, same color, is taken back: the ring side
            # and the enemies return to how they stood before the press. The move stays charged.
            self._green = green_before
            for e, (pos, heading) in zip(self._model.enemies, enemies_before):
                e.pos, e.heading = pos, heading
        self._meter_moves = self._moves
        self._draw()
        if self._moves >= self._budget:
            self.lose()
        self.complete_action()

    # ---------------------------------------------------------------- enemies
    def _step_enemies(self) -> None:
        solid = self._model.solid()
        for e in self._model.enemies:
            if e.dir0 == (0, 0):
                continue
            others = {c for o in self._model.enemies if o is not e for c in o.cells()}

            def blocked(h: Cell) -> bool:
                nxt = (e.pos[0] + h[0], e.pos[1] + h[1])
                for c in e.cells(nxt):
                    if not (0 <= c[0] < self._model.cols and 0 <= c[1] < self._model.rows):
                        return True
                    if c in solid or c in self._model.bars or c in others:
                        return True
                return False

            back = (-e.dir0[0], -e.dir0[1])
            if e.heading == back and e.pos == e.origin:
                e.heading = e.dir0  # the start cell is a hard end of the patrol
            if blocked(e.heading):
                e.heading = back if e.heading == e.dir0 else e.dir0
                if blocked(e.heading):
                    continue
            e.pos = (e.pos[0] + e.heading[0], e.pos[1] + e.heading[1])
            # after arriving, a further blocked step (or the origin) flips the shown core
            if e.heading == e.dir0 and blocked(e.dir0):
                e.heading = back
            elif e.heading == back and (e.pos == e.origin or blocked(back)):
                e.heading = e.dir0

    def _any_enemy_on_block(self) -> bool:
        cells = {c for e in self._model.enemies for c in e.cells()}
        return any(b.pos in cells for b in self._model.blocks)

    # ---------------------------------------------------------------- rules
    def _wrap(self, c: Cell) -> Cell:
        return (c[0] % self._model.cols, c[1] % self._model.rows)

    def _all_cups_satisfied(self) -> bool:
        by_pos = {b.pos: b for b in self._model.blocks}
        satisfied = 0
        for cup in self._model.cups:
            b = by_pos.get(cup.pocket)
            if b is not None and (cup.required is None or cup.required == b.color):
                satisfied += 1
        return satisfied == len(self._model.blocks) and all(b.pos in {c.pocket for c in self._model.cups} for b in self._model.blocks)

    # ---------------------------------------------------------------- rendering (COPYCAT shapes and HUD)
    def _draw(self) -> None:
        px = self._canvas.pixels
        px.fill(DARK_GRAY)
        m, cell, (ox, oy) = self._model, self._cell, self._origin
        fw, fh = m.cols * cell, m.rows * cell

        def fill(x0: int, y0: int, w: int, h: int, color: int) -> None:
            px[max(0, y0) : min(64, y0 + h), max(0, x0) : min(64, x0 + w)] = color

        # ring (one cell thick) with open corners (original: darker corners), then the lit side
        fill(ox - cell, oy - cell, fw + 2 * cell, fh + 2 * cell, LIGHT_GRAY)
        for cx, cy in ((ox - cell, oy - cell), (ox + fw, oy - cell), (ox - cell, oy + fh), (ox + fw, oy + fh)):
            fill(cx, cy, cell, cell, DARK_GRAY)
        if self._green == "TOP":
            fill(ox, oy - cell, fw, cell, GREEN)
        elif self._green == "BOTTOM":
            fill(ox, oy + fh, fw, cell, GREEN)
        elif self._green == "LEFT":
            fill(ox - cell, oy, cell, fh, GREEN)
        else:
            fill(ox + fw, oy, cell, fh, GREEN)

        # field
        fill(ox, oy, fw, fh, PURPLE)

        def cellfill(c: Cell, color: int) -> None:
            fill(ox + c[0] * cell, oy + c[1] * cell, cell, cell, color)

        def notch(c: Cell, color: int) -> None:
            # a block: the cell with its four corner pixels cut back to the floor (cell >= 3)
            cellfill(c, color)
            if cell >= 3:
                x0, y0 = ox + c[0] * cell, oy + c[1] * cell
                for dx, dy in ((0, 0), (cell - 1, 0), (0, cell - 1), (cell - 1, cell - 1)):
                    fill(x0 + dx, y0 + dy, 1, 1, PURPLE)

        for c in m.walls:
            cellfill(c, WALL)
        for cup in m.cups:
            for c in cup.whites:
                cellfill(c, WHITE)
            cellfill(cup.marker_cell, WHITE if cup.required is None else cup.required)
        for c, color in m.bars.items():
            cellfill(c, color)
        for e in m.enemies:
            # hollow frame: the eight body cells drawn, the centre left as floor, then the core
            for c in e.cells():
                if c != (e.pos[0] + 1, e.pos[1] + 1):
                    cellfill(c, ORANGE)
            cellfill(e.core(), DARK_RED)
        for b in m.blocks:
            notch(b.pos, b.color)

        # perimeter meter: one 188-px path that starts at the BOTTOM center and grows both ways,
        # along the bottom row and then UP each side column (rows 62..1); full on the losing move
        px[63, :] = ORANGE
        px[1:63, 0] = ORANGE
        px[1:63, 63] = ORANGE
        total = min(188, int(round(188 * self._meter_moves / self._budget)))
        left_len, right_len = (total + 1) // 2, total // 2
        for length, bottom_cols, col in ((left_len, range(31, -1, -1), 0), (right_len, range(32, 64), 63)):
            n_bottom = min(32, length)
            for c in list(bottom_cols)[:n_bottom]:
                px[63, c] = DARK_RED
            n_side = max(0, length - 32)
            if n_side:
                px[63 - n_side : 63, col] = DARK_RED

        # level progress bar on the TOP row
        px[0, :] = BLACK
        done = int(round(64 * self._score / len(LEVEL_SPECS)))
        px[0, :done] = WHITE

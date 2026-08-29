# Author: Claude Opus 5
# Date: 2026-08-26 23:10
# PURPOSE: hv01 "Hive" -- an ARC-AGI-3 environment. A swarm streams rightward from a
#   source; the player places influence nodes (attract / repel / teleport) that bend its
#   path, then presses RUN to play a deterministic simulation and herd the swarm into a
#   sink. Levels add exactly one new rule each. Core-knowledge priors only (objectness,
#   geometry, agentness): no text, digits or glyphs anywhere in the raster. Implements the
#   arcengine ARCBaseGame contract (step / on_set_level / complete_action); consumed by the
#   Pyodide browser player, the CLI agent, and the duck-harness bundle.
# SRP/DRY check: Pass -- self-contained environment module; no existing utility covers
#   swarm-field simulation. Rendering follows the RenderableUserDisplay house pattern used
#   by cr01/px02. No shared font/sprite module exists to reuse.
"""Hive -- steer a drifting swarm into the sink by placing influence nodes.

Everything is done by clicking: pick a node type from the palette, click the board to
place or remove one, then click RUN to play the simulation out. Adjust and run again.

Organisms always advance one cell to the right each tick; nodes decide whether they also
step up or down. That guarantees every run terminates and nothing can stall in place.

8 levels. Fully deterministic -- no RNG anywhere. Loss condition is the action budget.
"""

import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

CELL = 4
GRID_W = 15
GRID_H = 13
OX = 2                       # playfield origin x
OY = 10                      # playfield origin y (HUD occupies rows 0..9)

BAR_Y, BAR_X0, BAR_X1 = 0, 1, 63          # action-budget bar
SWATCH_Y, SWATCH_SIZE = 3, 5              # node palette
SWATCH_X = (2, 9, 16)
PIP_Y = 8                                 # remaining-stock pips
BANK_X, BANK_Y = 26, 3                    # banked-organism pips
VENT_HALF = 1                             # source vent extends this far above/below

# ---------------------------------------------------------------------------
# Colours (ARC-3 palette indices -- 12 is Orange, 8 is Red, 5 is Black)
# ---------------------------------------------------------------------------

C_WHITE, C_LGRAY, C_GRAY, C_DGRAY, C_VDGRAY, C_BLACK = 0, 1, 2, 3, 4, 5
C_MAGENTA, C_LMAGENTA, C_RED, C_BLUE, C_LBLUE = 6, 7, 8, 9, 10
C_YELLOW, C_ORANGE, C_MAROON, C_GREEN, C_PURPLE = 11, 12, 13, 14, 15

# ---------------------------------------------------------------------------
# Node and organism kinds
# ---------------------------------------------------------------------------

N_REPEL, N_ATTRACT, N_TELEPORT = "repel", "attract", "teleport"
NODE_COLOR = {N_REPEL: C_RED, N_ATTRACT: C_BLUE, N_TELEPORT: C_YELLOW}

O_NORMAL, O_INVERT = "normal", "invert"          # invert has reversed polarity
ORG_COLOR = {O_NORMAL: C_MAGENTA, O_INVERT: C_PURPLE}
SINK_COLOR = {O_NORMAL: C_LBLUE, O_INVERT: C_LMAGENTA}

NODE_K = 10.0                # node field strength (gives a useful reach of ~5 cells)
TURN_THRESHOLD = 0.30        # vertical force needed to bend the swarm one cell

# Placing a node is cheap; releasing the swarm to see what happens is expensive. Thinking
# about where the nodes go should be free, running the experiment should not be. Without
# this a blind policy simply releases every other action and brute-forces placements --
# measured at 1 in 12 on level 2 when a release cost the same as a click.
RELEASE_COST = 3

# ---------------------------------------------------------------------------
# Levels -- each introduces exactly one new rule and keeps every earlier one.
#   source / sinks / spawn / required / walls / hazards / stock as named.
# ---------------------------------------------------------------------------

LEVELS = [
    {
        "name": "First Pull",                       # NEW: attractors bend the swarm
        "source": (0, 6), "sinks": {O_NORMAL: (14, 2)},
        "spawn": [(O_NORMAL, 3)], "required": 3,
        "walls": set(), "hazards": set(),
        "stock": {N_ATTRACT: 2},
    },
    {
        # NEW: repulsors, the only tool here. The sink is kept off the bottom edge on
        # purpose: against the floor, overshoot is absorbed and any hard downward push
        # wins, which made random play twice as effective.
        "name": "Push Away",
        "source": (0, 6), "sinks": {O_NORMAL: (14, 10)},
        "spawn": [(O_NORMAL, 3)], "required": 3,
        "walls": set(), "hazards": set(),
        "stock": {N_REPEL: 2},
    },
    {
        # NEW: walls. The opening is three cells tall so the swarm can pass as a group --
        # a one-cell gap demands all three organisms converge exactly, which kills one
        # every time and is not a puzzle, just a tax.
        # The sink is deliberately NOT on the gap's row: an organism can settle onto a
        # single attractor's row and ride it to the edge, so one node must not be able to
        # both thread the gap and land the swarm.
        "name": "The Gap",
        "source": (0, 6), "sinks": {O_NORMAL: (14, 6)},
        "spawn": [(O_NORMAL, 3)], "required": 3,
        "walls": {(7, y) for y in range(GRID_H) if y not in (8, 9, 10)},
        "hazards": set(),
        "stock": {N_ATTRACT: 1, N_REPEL: 1},
    },
    {
        # NEW: two walls -- the turns must be sequenced. Gaps are spaced so the required
        # row change is reachable at one row per column, with a little slack.
        "name": "Two Gates",
        "source": (0, 6), "sinks": {O_NORMAL: (14, 4)},
        "spawn": [(O_NORMAL, 3)], "required": 3,
        "walls": ({(5, y) for y in range(GRID_H) if y not in (8, 9, 10)}
                  | {(11, y) for y in range(GRID_H) if y not in (3, 4, 5)}),
        "hazards": set(),
        "stock": {N_ATTRACT: 2, N_REPEL: 2},
    },
    {
        "name": "Scald",                            # NEW: hazards destroy organisms
        "source": (0, 6), "sinks": {O_NORMAL: (14, 6)},
        "spawn": [(O_NORMAL, 3)], "required": 3,
        "walls": set(),
        "hazards": {(x, 6) for x in range(6, 10)},
        "stock": {N_ATTRACT: 2, N_REPEL: 2},
    },
    {
        "name": "Sealed Room",                      # NEW: teleport pair -- the only way in
        "source": (0, 6), "sinks": {O_NORMAL: (12, 6)},
        "spawn": [(O_NORMAL, 3)], "required": 3,
        "walls": ({(10, y) for y in range(3, 10)} | {(14, y) for y in range(3, 10)}
                  | {(x, 3) for x in range(10, 15)} | {(x, 9) for x in range(10, 15)}),
        "hazards": set(),
        "stock": {N_ATTRACT: 1, N_TELEPORT: 2},
    },
    {
        "name": "Opposites",                        # NEW: a kind with reversed polarity
        "source": (0, 6),
        "sinks": {O_NORMAL: (14, 2), O_INVERT: (14, 10)},
        "spawn": [(O_NORMAL, 2), (O_INVERT, 2)], "required": 4,
        "walls": set(), "hazards": set(),
        "stock": {N_ATTRACT: 2},
    },
    {
        # Finale: walls (L3/L4) composed with reversed polarity (L7), and the sinks are
        # MIRRORED relative to level 7 so the previous level's answer cannot be replayed.
        "name": "Gauntlet",
        "source": (0, 6),
        "sinks": {O_NORMAL: (14, 10), O_INVERT: (14, 2)},
        "spawn": [(O_NORMAL, 2), (O_INVERT, 2)], "required": 4,
        "walls": {(6, y) for y in range(GRID_H) if y not in (5, 6, 7)},
        "hazards": set(),
        "stock": {N_ATTRACT: 2, N_REPEL: 2},
    },
]

# Action budgets, deliberately tight. A solver clears each level in 3-6 clicks, so these
# leave a human several full attempts while starving brute-force search: this is a
# place-and-test game, so a loose budget lets a random policy simply try placements until
# one sticks. The tutorial is generous because the mechanic is still unknown.
BUDGETS = (36, 20, 26, 26, 26, 34, 26, 32)
for _ldef, _budget in zip(LEVELS, BUDGETS):
    _ldef["budget"] = _budget

PALETTE_ORDER = (N_ATTRACT, N_REPEL, N_TELEPORT)
MAX_TICKS = GRID_W + 3       # every organism advances one column per tick, so this bounds a run


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

class Hv01Display(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    def _cell_px(self, gx, gy):
        return OX + gx * CELL, OY + gy * CELL

    def _fill_cell(self, frame, gx, gy, color):
        px, py = self._cell_px(gx, gy)
        if 0 <= px and 0 <= py and px + CELL <= 64 and py + CELL <= 64:
            frame[py:py + CELL, px:px + CELL] = color

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game
        frame[:, :] = C_BLACK

        # Floor: a dark field stippled at every cell corner, so the grid the swarm moves
        # on is legible without drawing lines that would read as objects.
        frame[OY:OY + GRID_H * CELL, OX:OX + GRID_W * CELL] = C_VDGRAY
        frame[OY:OY + GRID_H * CELL:CELL, OX:OX + GRID_W * CELL:CELL] = C_DGRAY

        # Walls: brick, lit from the top-left so they read as solid mass.
        for (gx, gy) in g.walls:
            px, py = self._cell_px(gx, gy)
            if px < 0 or py < 0 or px + CELL > 64 or py + CELL > 64:
                continue
            frame[py:py + CELL, px:px + CELL] = C_GRAY
            frame[py, px:px + CELL] = C_LGRAY                 # top highlight
            frame[py + CELL - 1, px:px + CELL] = C_DGRAY      # bottom shadow
            frame[py:py + CELL, px + CELL - 1] = C_DGRAY      # right shadow

        for (gx, gy) in g.hazards:
            px, py = self._cell_px(gx, gy)
            if 0 <= px and 0 <= py and px + CELL <= 64 and py + CELL <= 64:
                frame[py:py + CELL, px:px + CELL] = C_MAROON
                frame[py, px + 1] = C_ORANGE
                frame[py + 1, px + 3] = C_ORANGE
                frame[py + 2, px] = C_ORANGE
                frame[py + 3, px + 2] = C_ORANGE

        # Source: a vent as tall as the swarm that leaves it, so the opening matches what
        # actually comes out instead of three organisms overlapping a one-cell hole.
        for cell in sorted(g._vent_cells()):
            px, py = self._cell_px(*cell)
            if px < 0 or py < 0 or px + CELL > 64 or py + CELL > 64:
                continue
            frame[py:py + CELL, px:px + CELL] = C_GREEN
            frame[py + 1:py + 3, px + 2:px + CELL] = C_BLACK   # mouth, opening rightward
            frame[py:py + CELL, px] = C_LGRAY                  # rim on the closed side

        # Sinks recolour their centre once their own quota is met -- colour as affordance.
        for kind, (gx, gy) in g.sinks.items():
            self._fill_cell(frame, gx, gy, SINK_COLOR[kind])
            px, py = self._cell_px(gx, gy)
            if 0 <= px and 0 <= py and px + CELL <= 64 and py + CELL <= 64:
                done = g.banked_by_kind.get(kind, 0) >= g.need_by_kind.get(kind, 1)
                frame[py + 1:py + 3, px + 1:px + 3] = C_GREEN if done else C_WHITE

        # Nodes: hollow rings with a bright core, so they never read as an organism.
        for (gx, gy), kind in g.nodes.items():
            px, py = self._cell_px(gx, gy)
            if px < 0 or py < 0 or px + CELL > 64 or py + CELL > 64:
                continue
            frame[py:py + CELL, px:px + CELL] = NODE_COLOR[kind]
            frame[py + 1:py + 3, px + 1:px + 3] = C_BLACK
            frame[py + 1, px + 1] = C_WHITE if kind == N_ATTRACT else C_YELLOW

        # Teleport partners joined by a dotted line so the pairing is visible.
        tp = sorted(p for p, k in g.nodes.items() if k == N_TELEPORT)
        if len(tp) == 2:
            (ax, ay), (bx, by) = tp
            steps = max(abs(ax - bx), abs(ay - by), 1)
            for i in range(1, steps):
                cx, cy = ax + (bx - ax) * i // steps, ay + (by - ay) * i // steps
                ppx, ppy = self._cell_px(cx, cy)
                if (cx, cy) not in g.nodes and 0 <= ppx + 1 < 64 and 0 <= ppy + 1 < 64:
                    frame[ppy + 1, ppx + 1] = C_YELLOW

        # Organisms: a body with a lighter core, so a cluster still reads as individuals.
        for org in g.organisms:
            if not org["alive"]:
                continue
            px, py = self._cell_px(*org["pos"])
            if 0 <= px and 0 <= py and px + CELL <= 64 and py + CELL <= 64:
                frame[py + 1:py + 4, px + 1:px + 4] = ORG_COLOR[org["kind"]]
                frame[py + 2, px + 2] = (C_LMAGENTA if org["kind"] == O_NORMAL else C_MAGENTA)

        # ---- HUD ----------------------------------------------------------
        span = BAR_X1 - BAR_X0
        filled = 0 if g.budget_max <= 0 else int(span * g.budget_left / g.budget_max)
        frame[BAR_Y:BAR_Y + 2, BAR_X0:BAR_X1] = C_DGRAY
        if filled > 0:
            frame[BAR_Y:BAR_Y + 2, BAR_X0:BAR_X0 + filled] = (
                C_GREEN if g.budget_left * 4 > g.budget_max else C_ORANGE)

        for i, kind in enumerate(g.palette):
            x = SWATCH_X[i]
            frame[SWATCH_Y:SWATCH_Y + SWATCH_SIZE, x:x + SWATCH_SIZE] = NODE_COLOR[kind]
            frame[SWATCH_Y + 1:SWATCH_Y + 4, x + 1:x + 4] = C_BLACK
            if kind == g.selected:
                frame[SWATCH_Y - 1, x - 1:x + SWATCH_SIZE + 1] = C_WHITE
                frame[SWATCH_Y + SWATCH_SIZE, x - 1:x + SWATCH_SIZE + 1] = C_WHITE
                frame[SWATCH_Y - 1:SWATCH_Y + SWATCH_SIZE + 1, x - 1] = C_WHITE
                frame[SWATCH_Y - 1:SWATCH_Y + SWATCH_SIZE + 1, x + SWATCH_SIZE] = C_WHITE
            for p in range(g.stock_left.get(kind, 0)):
                if x + p * 2 < 64:
                    frame[PIP_Y, x + p * 2] = NODE_COLOR[kind]

        for i in range(g.required):
            hx = BANK_X + i * 3
            if hx + 2 > BAR_X1:
                break
            frame[BANK_Y:BANK_Y + 3, hx:hx + 2] = (
                C_GREEN if i < g.banked_total else C_DGRAY)

        return frame


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Hv01(ARCBaseGame):
    def __init__(self):
        self.display = Hv01Display(self)

        # on_set_level() runs inside super().__init__(), so every attribute must exist.
        self.source = (0, 0)
        self.sinks = {}
        self.spawn_plan = []
        self.required = 0
        self.walls = set()
        self.hazards = set()
        self.stock_left = {}
        self.palette = []
        self.selected = None
        self.nodes = {}
        self.organisms = []
        self._spawns = []
        self.banked_by_kind = {}
        self.need_by_kind = {}
        self.banked_total = 0
        self.budget_max = 0
        self.budget_left = 0
        self._running = False
        self._tick = 0

        levels = [Level(sprites=[], grid_size=(64, 64), data=ldef, name=ldef["name"])
                  for ldef in LEVELS]

        super().__init__(
            "hv",
            levels,
            Camera(0, 0, 64, 64, C_BLACK, C_BLACK, [self.display]),
            False,
            len(levels),
            [5, 6],              # 5 = release the swarm, 6 = click to place/remove/select
        )

    # -- level setup --------------------------------------------------------

    def on_set_level(self, level: Level) -> None:
        ldef = LEVELS[self.level_index]
        self.source = ldef["source"]
        self.sinks = dict(ldef["sinks"])
        self.spawn_plan = list(ldef["spawn"])
        self.required = ldef["required"]
        self.walls = set(ldef["walls"])
        self.hazards = set(ldef["hazards"])
        self.palette = [k for k in PALETTE_ORDER if k in ldef["stock"]]
        self.stock_left = dict(ldef["stock"])
        self.selected = self.palette[0] if self.palette else None
        self.nodes = {}
        self.budget_max = self.budget_left = ldef["budget"]

        self.need_by_kind = {}
        for kind, count in self.spawn_plan:
            self.need_by_kind[kind] = self.need_by_kind.get(kind, 0) + count
        self._spawns = self._compute_spawns()
        self._reset_run()

    def _compute_spawns(self):
        """Fixed spawn slots, stacked outward from the source row. The vent is drawn to
        exactly these cells so the opening always matches what comes out of it."""
        sx, sy = self.source
        slots = []
        for off in (0, -1, 1, -2, 2, -3, 3):
            gy = sy + off
            if 0 <= gy < GRID_H and (sx, gy) not in self.walls:
                slots.append((sx, gy))
        spawns, i = [], 0
        for kind, count in self.spawn_plan:
            for _ in range(count):
                if i < len(slots):
                    spawns.append((slots[i], kind))
                    i += 1
        return spawns

    def _vent_cells(self):
        return {cell for cell, _kind in self._spawns}

    def _reset_run(self):
        """Rewind the swarm to the source. Placed nodes are deliberately kept."""
        self.organisms = [{"pos": cell, "kind": kind, "alive": True}
                          for cell, kind in self._spawns]
        self.banked_by_kind = {k: 0 for k in self.sinks}
        self.banked_total = 0
        self._running = False
        self._tick = 0

    # -- simulation ---------------------------------------------------------

    def _blocked(self, gx, gy):
        return gx < 0 or gy < 0 or gx >= GRID_W or gy >= GRID_H or (gx, gy) in self.walls

    def _vertical_force(self, pos, kind):
        """Only the vertical component matters: forward motion is constant."""
        ox, oy = pos
        vy = 0.0
        for (nx, ny), ntype in self.nodes.items():
            if ntype == N_TELEPORT:
                continue
            dx, dy = ox - nx, oy - ny
            d2 = dx * dx + dy * dy
            if d2 == 0:
                continue
            dist = d2 ** 0.5
            sign = 1.0 if ntype == N_REPEL else -1.0
            if kind == O_INVERT:
                sign = -sign
            vy += sign * (dy / dist) * (NODE_K / d2)
        return vy

    def _teleport_partner(self, cell):
        tp = sorted(p for p, k in self.nodes.items() if k == N_TELEPORT)
        if len(tp) != 2 or cell not in tp:
            return None
        return tp[1] if tp[0] == cell else tp[0]

    def _sim_tick(self):
        """One tick: every organism advances exactly one column, bending up or down."""
        self._tick += 1
        for org in self.organisms:
            if not org["alive"]:
                continue
            gx, gy = org["pos"]
            vy = self._vertical_force((gx, gy), org["kind"])
            dy = 1 if vy > TURN_THRESHOLD else (-1 if vy < -TURN_THRESHOLD else 0)

            nx, ny = gx + 1, gy + dy
            if self._blocked(nx, ny):
                nx, ny = gx + 1, gy                      # try straight ahead instead
                if self._blocked(nx, ny):
                    org["alive"] = False                 # ran into a wall
                    continue
            if nx >= GRID_W:
                org["alive"] = False                     # left the board
                continue

            partner = self._teleport_partner((nx, ny))
            if partner is not None:
                nx, ny = partner

            org["pos"] = (nx, ny)
            if (nx, ny) in self.hazards:
                org["alive"] = False
                continue
            for kind, spos in self.sinks.items():
                if (nx, ny) == spos and org["kind"] == kind:
                    org["alive"] = False
                    self.banked_by_kind[kind] = self.banked_by_kind.get(kind, 0) + 1
                    self.banked_total += 1
                    break

    def _run_over(self):
        return (self.banked_total >= self.required
                or self._tick >= MAX_TICKS
                or not any(o["alive"] for o in self.organisms))

    def _finish_run(self):
        self._running = False
        if self.banked_total >= self.required:
            self.next_level()
            return
        tally = self.banked_total          # keep the tally readable on the failed frame
        self._reset_run()
        self.banked_total = tally
        if self.budget_left <= 0:
            self.budget_left = 0
            self.lose()

    # -- input --------------------------------------------------------------

    def _palette_hit(self, x, y):
        if not (SWATCH_Y <= y < SWATCH_Y + SWATCH_SIZE):
            return None
        for i, kind in enumerate(self.palette):
            if SWATCH_X[i] <= x < SWATCH_X[i] + SWATCH_SIZE:
                return kind
        return None

    def _board_cell(self, x, y):
        if not (OX <= x < OX + GRID_W * CELL and OY <= y < OY + GRID_H * CELL):
            return None
        return (x - OX) // CELL, (y - OY) // CELL

    def _handle_click(self, x, y):
        kind = self._palette_hit(x, y)
        if kind is not None:
            self.selected = kind
            return False

        cell = self._board_cell(x, y)
        if cell is None:
            return
        if cell in self.nodes:                        # click a node to take it back
            removed = self.nodes.pop(cell)
            self.stock_left[removed] = self.stock_left.get(removed, 0) + 1
            return
        if (cell in self.walls or cell in self.hazards
                or cell in self._vent_cells() or cell in self.sinks.values()):
            return
        if self.selected is None or self.stock_left.get(self.selected, 0) <= 0:
            return
        self.nodes[cell] = self.selected
        self.stock_left[self.selected] -= 1

    # -- engine entry point -------------------------------------------------

    def step(self) -> None:
        # A run in progress emits one frame per tick by withholding complete_action().
        if self._running:
            self._sim_tick()
            if self._run_over():
                self._finish_run()
                self.complete_action()
            return

        aid = self.action.id.value

        if aid == 6:
            self.budget_left -= 1
            self._handle_click(int(self.action.data.get("x", 0)),
                               int(self.action.data.get("y", 0)))
        elif aid == 5:                                 # release the swarm
            self.budget_left -= RELEASE_COST
            self._reset_run()
            self._running = True
            self._sim_tick()
            if self._run_over():
                self._finish_run()
            else:
                return                                 # animate: withhold completion

        if self.budget_left <= 0 and not self._running:
            self.budget_left = 0
            self.lose()

        self.complete_action()

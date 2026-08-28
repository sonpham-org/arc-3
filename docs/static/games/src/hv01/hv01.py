# Author: Claude Opus 5
# Date: 2026-08-26 20:40
# PURPOSE: hv01 "Hive" -- an ARC-AGI-3 environment. Organisms stream from a source and
#   drift across the board. The player places influence nodes (attract / repel / teleport)
#   that bend the stream, then runs a deterministic simulation to herd the organisms into
#   a sink. Levels add exactly one new rule each. Pure objectness/geometry/agentness
#   priors: no text, no digits, no glyphs anywhere in the raster. Integrates with the
#   arcengine ARCBaseGame contract (step/on_set_level/complete_action) and is consumed by
#   the Pyodide browser player, the CLI agent, and the duck-harness bundle.
# SRP/DRY check: Pass -- self-contained environment module; no existing utility covers
#   swarm-field simulation. Rendering follows the RenderableUserDisplay house pattern used
#   by cr01/px02; no shared font/sprite module exists to reuse.
"""Hive -- herd a drifting swarm into the sink by placing influence nodes.

Click a palette swatch to choose a node type, click the board to place or remove one,
then run the simulation and watch where the swarm goes. Adjust and run again.

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

BAR_Y = 0                    # action-budget bar rows 0..1
BAR_X0 = 1
BAR_X1 = 63
SWATCH_Y = 3                 # palette swatch rows 3..7
SWATCH_SIZE = 5
SWATCH_X = (2, 9, 16)        # up to three node types
PIP_Y = 8                    # remaining-node pips row

# ---------------------------------------------------------------------------
# Colours (ARC-3 palette indices -- see CLAUDE.md; 12 is Orange, 8 is Red)
# ---------------------------------------------------------------------------

C_WHITE = 0
C_LGRAY = 1
C_GRAY = 2
C_DGRAY = 3
C_VDGRAY = 4
C_BLACK = 5
C_MAGENTA = 6
C_LMAGENTA = 7
C_RED = 8
C_BLUE = 9
C_LBLUE = 10
C_YELLOW = 11
C_ORANGE = 12
C_MAROON = 13
C_GREEN = 14
C_PURPLE = 15

# ---------------------------------------------------------------------------
# Node and organism kinds
# ---------------------------------------------------------------------------

N_REPEL = "repel"
N_ATTRACT = "attract"
N_TELEPORT = "teleport"

NODE_COLOR = {N_REPEL: C_RED, N_ATTRACT: C_BLUE, N_TELEPORT: C_YELLOW}

O_NORMAL = "normal"          # attracted by attractors, pushed by repulsors
O_INVERT = "invert"          # polarity reversed

ORG_COLOR = {O_NORMAL: C_MAGENTA, O_INVERT: C_PURPLE}
SINK_COLOR = {O_NORMAL: C_LBLUE, O_INVERT: C_LMAGENTA}

DRIFT_W = 1.0                # weight of the level's ambient drift
NODE_K = 8.0                 # node field strength
MAX_TICKS = 60               # hard cap on one simulation run

# ---------------------------------------------------------------------------
# Levels
#
# Each level introduces exactly one new rule and keeps every earlier one.
#   source   : (gx, gy) cell the swarm streams out of
#   sinks    : {organism_kind: (gx, gy)}
#   drift    : ambient (dx, dy) every organism feels
#   spawn    : [(organism_kind, count), ...] emitted one per tick
#   required : how many organisms must bank to clear the level
#   walls    : blocking cells
#   hazards  : cells that destroy an organism
#   stock    : {node_kind: how many the player may place}
#   budget   : action budget for the level
# ---------------------------------------------------------------------------

LEVELS = [
    {
        "name": "First Pull",                       # NEW: attractors pull the swarm
        "source": (1, 6), "sinks": {O_NORMAL: (13, 2)},
        "drift": (1, 0), "spawn": [(O_NORMAL, 3)], "required": 3,
        "walls": set(), "hazards": set(),
        "stock": {N_ATTRACT: 2}, "budget": 40,
    },
    {
        # NEW: repulsors, and they are the only tool. The far wall has a single aperture
        # at the sink, so the swarm has to arrive on exactly the right row -- without it
        # any repulsor that produced some downward push won, and random play cleared the
        # level about 1 in 18.
        "name": "Push Away",
        "source": (1, 6), "sinks": {O_NORMAL: (13, 12)},
        "drift": (1, 0), "spawn": [(O_NORMAL, 3)], "required": 3,
        "walls": {(13, y) for y in range(GRID_H) if y != 12}, "hazards": set(),
        "stock": {N_REPEL: 2}, "budget": 44,
    },
    {
        "name": "The Gap",                          # NEW: walls -- funnel through one opening
        "source": (1, 6), "sinks": {O_NORMAL: (13, 10)},
        "drift": (1, 0), "spawn": [(O_NORMAL, 4)], "required": 4,
        "walls": {(7, y) for y in range(0, 10)} | {(7, y) for y in range(11, 13)},
        "hazards": set(),
        # One of each: exactly 7 placements in the whole space clear this level.
        "stock": {N_ATTRACT: 1, N_REPEL: 1}, "budget": 48,
    },
    {
        "name": "Two Only",                         # NEW: scarce stock -- selection, not placement
        "source": (1, 6), "sinks": {O_NORMAL: (13, 2)},
        "drift": (1, 0), "spawn": [(O_NORMAL, 4)], "required": 4,
        "walls": {(7, y) for y in range(0, 2)} | {(7, y) for y in range(3, 13)},
        "hazards": set(),
        "stock": {N_ATTRACT: 1, N_REPEL: 1}, "budget": 48,
    },
    {
        "name": "Scald",                            # NEW: hazards destroy organisms
        "source": (1, 6), "sinks": {O_NORMAL: (13, 2)},
        "drift": (1, 0), "spawn": [(O_NORMAL, 5)], "required": 4,
        "walls": set(),
        "hazards": {(x, y) for x in (8, 9, 10) for y in (2, 3, 4)},
        "stock": {N_ATTRACT: 2, N_REPEL: 2}, "budget": 52,
    },
    {
        "name": "Sealed Room",                      # NEW: teleport pair -- the only way in
        "source": (1, 6), "sinks": {O_NORMAL: (12, 6)},
        "drift": (1, 0), "spawn": [(O_NORMAL, 3)], "required": 3,
        "walls": ({(10, y) for y in range(3, 10)} | {(14, y) for y in range(3, 10)}
                  | {(x, 3) for x in range(10, 15)} | {(x, 9) for x in range(10, 15)}),
        "hazards": set(),
        "stock": {N_ATTRACT: 1, N_REPEL: 1, N_TELEPORT: 2}, "budget": 56,
    },
    {
        "name": "Opposites",                        # NEW: a second kind with reversed polarity
        "source": (1, 6),
        "sinks": {O_NORMAL: (13, 2), O_INVERT: (13, 10)},
        "drift": (1, 0), "spawn": [(O_NORMAL, 2), (O_INVERT, 2)], "required": 4,
        "walls": set(), "hazards": set(),
        "stock": {N_ATTRACT: 2, N_REPEL: 2}, "budget": 56,
    },
    {
        # Finale: walls (L3) composed with reversed polarity (L7), and the two sinks are
        # MIRRORED relative to level 7 -- verified that level 7's winning placement banks
        # 0 of 4 here, so the level cannot be cleared by replaying the previous answer.
        # No hazards: every position that gated anything also made the level unsolvable,
        # and a hazard placed somewhere harmless would be decoration, not difficulty.
        "name": "Gauntlet",
        "source": (1, 6),
        "sinks": {O_NORMAL: (13, 10), O_INVERT: (13, 2)},
        "drift": (1, 0), "spawn": [(O_NORMAL, 2), (O_INVERT, 2)], "required": 4,
        "walls": {(4, y) for y in range(0, 5)} | {(4, y) for y in range(8, 13)},
        "hazards": set(),
        "stock": {N_ATTRACT: 2, N_REPEL: 2}, "budget": 60,
    },
]

# Action budgets, tuned deliberately tight. A solver clears each level in 3-6 actions, so
# these leave a human three or four full attempts while starving brute-force search: this
# is a place-and-test game, so a loose budget lets a random policy simply try placements
# until one sticks. The tutorial gets a generous budget because the mechanic is unknown.
BUDGETS = (30, 11, 18, 18, 16, 18, 20, 22)
for _ldef, _budget in zip(LEVELS, BUDGETS):
    _ldef["budget"] = _budget

PALETTE_ORDER = (N_ATTRACT, N_REPEL, N_TELEPORT)


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

    def _draw_node(self, frame, gx, gy, kind, active):
        """Nodes read as rings so they never look like an organism."""
        px, py = self._cell_px(gx, gy)
        if px < 0 or py < 0 or px + CELL > 64 or py + CELL > 64:
            return
        col = NODE_COLOR[kind]
        frame[py:py + CELL, px:px + CELL] = col
        # Hollow centre; brightens to white while the node is influencing something.
        frame[py + 1:py + 3, px + 1:px + 3] = C_WHITE if active else C_BLACK

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game
        frame[:, :] = C_BLACK

        # ---- playfield backdrop -------------------------------------------
        frame[OY:OY + GRID_H * CELL, OX:OX + GRID_W * CELL] = C_VDGRAY

        for (gx, gy) in g.walls:
            self._fill_cell(frame, gx, gy, C_GRAY)
        for (gx, gy) in g.hazards:
            px, py = self._cell_px(gx, gy)
            if 0 <= px and 0 <= py and px + CELL <= 64 and py + CELL <= 64:
                frame[py:py + CELL, px:px + CELL] = C_MAROON
                frame[py + 1, px + 1] = C_ORANGE
                frame[py + 2, px + 2] = C_ORANGE

        # ---- source -------------------------------------------------------
        sx, sy = g.source
        self._fill_cell(frame, sx, sy, C_GREEN)
        px, py = self._cell_px(sx, sy)
        if 0 <= px and 0 <= py and px + CELL <= 64 and py + CELL <= 64:
            frame[py + 1:py + 3, px + 1:px + 3] = C_BLACK

        # ---- sinks: colour tracks whether their quota is already banked ----
        for kind, (gx, gy) in g.sinks.items():
            self._fill_cell(frame, gx, gy, SINK_COLOR[kind])
            px, py = self._cell_px(gx, gy)
            if 0 <= px and 0 <= py and px + CELL <= 64 and py + CELL <= 64:
                got = g.banked_by_kind.get(kind, 0)
                need = g.need_by_kind.get(kind, 0)
                frame[py + 1:py + 3, px + 1:px + 3] = C_GREEN if got >= need else C_WHITE

        # ---- nodes --------------------------------------------------------
        for (gx, gy), kind in g.nodes.items():
            self._draw_node(frame, gx, gy, kind, (gx, gy) in g.active_nodes)
        # teleport partners are joined by a faint dotted line so the pairing is visible
        tp = [p for p, k in g.nodes.items() if k == N_TELEPORT]
        if len(tp) == 2:
            (ax, ay), (bx, by) = tp
            steps = max(abs(ax - bx), abs(ay - by))
            for i in range(1, steps):
                cx = ax + (bx - ax) * i // max(1, steps)
                cy = ay + (by - ay) * i // max(1, steps)
                ppx, ppy = self._cell_px(cx, cy)
                if 0 <= ppx + 1 < 64 and 0 <= ppy + 1 < 64 and (cx, cy) not in g.nodes:
                    frame[ppy + 1, ppx + 1] = C_YELLOW

        # ---- organisms ----------------------------------------------------
        for org in g.organisms:
            if not org["alive"]:
                continue
            gx, gy = org["pos"]
            px, py = self._cell_px(gx, gy)
            if 0 <= px and 0 <= py and px + CELL <= 64 and py + CELL <= 64:
                frame[py + 1:py + 4, px + 1:px + 4] = ORG_COLOR[org["kind"]]

        # ---- HUD: action budget as a depleting bar (never a number) -------
        span = BAR_X1 - BAR_X0
        filled = 0 if g.budget_max <= 0 else int(span * g.budget_left / g.budget_max)
        frame[BAR_Y:BAR_Y + 2, BAR_X0:BAR_X1] = C_DGRAY
        if filled > 0:
            bar_col = C_GREEN if g.budget_left * 4 > g.budget_max else C_ORANGE
            frame[BAR_Y:BAR_Y + 2, BAR_X0:BAR_X0 + filled] = bar_col

        # ---- HUD: node palette; selected swatch gets a white frame --------
        for i, kind in enumerate(g.palette):
            x = SWATCH_X[i]
            frame[SWATCH_Y:SWATCH_Y + SWATCH_SIZE, x:x + SWATCH_SIZE] = NODE_COLOR[kind]
            frame[SWATCH_Y + 1:SWATCH_Y + 4, x + 1:x + 4] = C_BLACK
            if kind == g.selected:
                frame[SWATCH_Y - 1, x - 1:x + SWATCH_SIZE + 1] = C_WHITE
                frame[SWATCH_Y + SWATCH_SIZE, x - 1:x + SWATCH_SIZE + 1] = C_WHITE
                frame[SWATCH_Y - 1:SWATCH_Y + SWATCH_SIZE + 1, x - 1] = C_WHITE
                frame[SWATCH_Y - 1:SWATCH_Y + SWATCH_SIZE + 1, x + SWATCH_SIZE] = C_WHITE
            # remaining stock as pips, one per placeable node
            left = g.stock_left.get(kind, 0)
            for p in range(left):
                pxp = x + p * 2
                if pxp < 64:
                    frame[PIP_Y, pxp] = NODE_COLOR[kind]

        # ---- banked tally: one pip per organism already delivered ---------
        for i in range(g.required):
            hx = 40 + i * 3
            if hx + 2 > 64:
                break
            frame[SWATCH_Y + 1:SWATCH_Y + 3, hx:hx + 2] = (
                C_GREEN if i < g.banked_total else C_DGRAY
            )
        return frame


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Hv01(ARCBaseGame):
    def __init__(self):
        self.display = Hv01Display(self)

        # Per-level state. Really populated by on_set_level, which the engine calls
        # from inside super().__init__(), so every attribute must exist first.
        self.source = (0, 0)
        self.sinks = {}
        self.drift = (1, 0)
        self.spawn_plan = []
        self.required = 0
        self.walls = set()
        self.hazards = set()
        self.stock_left = {}
        self.palette = []
        self.selected = None
        self.nodes = {}
        self.active_nodes = set()
        self.organisms = []
        self.banked_by_kind = {}
        self.need_by_kind = {}
        self.banked_total = 0
        self.budget_max = 0
        self.budget_left = 0
        self._running = False
        self._tick = 0
        self._spawn_queue = []

        levels = [
            Level(sprites=[], grid_size=(64, 64), data=ldef, name=ldef["name"])
            for ldef in LEVELS
        ]

        super().__init__(
            "hv",
            levels,
            Camera(0, 0, 64, 64, C_BLACK, C_BLACK, [self.display]),
            False,
            len(levels),
            [1, 2, 6],          # 1 = run simulation, 2 = clear nodes, 6 = click
        )

    # -- level setup --------------------------------------------------------

    def on_set_level(self, level: Level) -> None:
        ldef = LEVELS[self.level_index]
        self.source = ldef["source"]
        self.sinks = dict(ldef["sinks"])
        self.drift = ldef["drift"]
        self.spawn_plan = list(ldef["spawn"])
        self.required = ldef["required"]
        self.walls = set(ldef["walls"])
        self.hazards = set(ldef["hazards"])
        self.palette = [k for k in PALETTE_ORDER if k in ldef["stock"]]
        self.stock_left = dict(ldef["stock"])
        self.selected = self.palette[0] if self.palette else None
        self.nodes = {}
        self.active_nodes = set()
        self.budget_max = ldef["budget"]
        self.budget_left = ldef["budget"]

        self.need_by_kind = {}
        for kind, count in self.spawn_plan:
            self.need_by_kind[kind] = self.need_by_kind.get(kind, 0) + count
        if len(self.sinks) == 1:
            only = next(iter(self.sinks))
            self.need_by_kind = {only: self.required}

        self._reset_run()

    def _reset_run(self):
        """Return the swarm to the source. Placed nodes are deliberately kept."""
        self.organisms = []
        self._spawn_queue = []
        for kind, count in self.spawn_plan:
            self._spawn_queue.extend([kind] * count)
        self.banked_by_kind = {k: 0 for k in self.sinks}
        self.banked_total = 0
        self.active_nodes = set()
        self._running = False
        self._tick = 0

    # -- simulation ---------------------------------------------------------

    def _blocked(self, gx, gy):
        if gx < 0 or gy < 0 or gx >= GRID_W or gy >= GRID_H:
            return True
        return (gx, gy) in self.walls

    def _field(self, pos, kind):
        """Ambient drift plus every node's contribution. Deterministic, no RNG."""
        ox, oy = pos
        vx = self.drift[0] * DRIFT_W
        vy = self.drift[1] * DRIFT_W
        for (nx, ny), ntype in self.nodes.items():
            if ntype == N_TELEPORT:
                continue
            dx, dy = ox - nx, oy - ny
            d2 = dx * dx + dy * dy
            if d2 == 0:
                d2 = 1
            dist = d2 ** 0.5
            strength = NODE_K / d2
            sign = 1.0 if ntype == N_REPEL else -1.0
            if kind == O_INVERT:
                sign = -sign
            vx += sign * (dx / dist) * strength
            vy += sign * (dy / dist) * strength
        return vx, vy

    def _teleport_partner(self, cell):
        tp = [p for p, k in self.nodes.items() if k == N_TELEPORT]
        if len(tp) != 2 or cell not in tp:
            return None
        return tp[1] if tp[0] == cell else tp[0]

    def _sim_tick(self):
        self._tick += 1
        self.active_nodes = set()

        # one organism leaves the source per tick
        if self._spawn_queue:
            kind = self._spawn_queue.pop(0)
            self.organisms.append({"pos": self.source, "kind": kind, "alive": True})

        for org in self.organisms:
            if not org["alive"]:
                continue
            gx, gy = org["pos"]
            vx, vy = self._field((gx, gy), org["kind"])

            # Quantise the field to one cardinal step; horizontal wins ties (deterministic).
            # There is deliberately NO fallback to the secondary axis: an organism whose
            # path is blocked stalls. Wall-sliding would let any weak pull from anywhere
            # navigate the whole board, which made single random node placements win.
            if abs(vx) >= abs(vy):
                step = (1 if vx > 0 else -1, 0) if vx != 0 else (0, 0)
            else:
                step = (0, 1 if vy > 0 else -1)

            nx, ny = gx, gy
            sx, sy = step
            if (sx or sy) and not self._blocked(gx + sx, gy + sy):
                nx, ny = gx + sx, gy + sy

            # mark whichever nodes are close enough to be visibly steering this organism
            for (px, py), ntype in self.nodes.items():
                if ntype == N_TELEPORT:
                    continue
                if abs(px - gx) + abs(py - gy) <= 3:
                    self.active_nodes.add((px, py))

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
        if self.banked_total >= self.required:
            return True
        if self._tick >= MAX_TICKS:
            return True
        return not self._spawn_queue and not any(o["alive"] for o in self.organisms)

    # -- input --------------------------------------------------------------

    def _palette_hit(self, x, y):
        if not (SWATCH_Y <= y < SWATCH_Y + SWATCH_SIZE):
            return None
        for i, kind in enumerate(self.palette):
            sx = SWATCH_X[i]
            if sx <= x < sx + SWATCH_SIZE:
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
            return

        cell = self._board_cell(x, y)
        if cell is None:
            return
        if cell in self.nodes:                       # click a node to take it back
            removed = self.nodes.pop(cell)
            self.stock_left[removed] = self.stock_left.get(removed, 0) + 1
            return
        if cell in self.walls or cell == self.source or cell in self.sinks.values():
            return
        if self.selected is None or self.stock_left.get(self.selected, 0) <= 0:
            return
        self.nodes[cell] = self.selected
        self.stock_left[self.selected] -= 1

    # -- engine entry point -------------------------------------------------

    def _finish_run(self) -> None:
        """Settle a completed simulation: advance, or rewind the swarm for another try."""
        self._running = False
        if self.banked_total >= self.required:
            self.next_level()
            return
        banked_view = self.banked_total          # keep the tally visible on the failed frame
        self._reset_run()
        self.banked_total = banked_view
        if self.budget_left <= 0:
            self.budget_left = 0
            self.lose()

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
            self._handle_click(int(self.action.data.get("x", 0)),
                               int(self.action.data.get("y", 0)))
            self.budget_left -= 1
        elif aid == 1:
            self.budget_left -= 1
            self._reset_run()
            self._running = True
            self._sim_tick()
            if self._run_over():
                self._finish_run()
            else:
                return                                # animate: withhold completion
        elif aid == 2:
            for cell, kind in list(self.nodes.items()):
                self.stock_left[kind] = self.stock_left.get(kind, 0) + 1
            self.nodes = {}
            self.budget_left -= 1

        if self.budget_left <= 0 and not self._running:
            self.budget_left = 0
            self.lose()

        self.complete_action()

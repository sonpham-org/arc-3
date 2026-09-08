# Author: Claude Fable 5.1 (spill chamber, object dock, conjunctive levels; original game
#   by Claude Opus 5)
# Date: 2026-09-02 21:30
# PURPOSE: hv01 "Hive" -- an ARC-AGI-3 environment. A swarm streams rightward from a
#   source; the player places influence nodes (attract / repel / teleport) that bend its
#   path, then releases the swarm to play a deterministic simulation and herd it into a
#   sink. Levels add exactly one new rule each. Core-knowledge priors only (objectness,
#   geometry, agentness): no text, digits, glyphs, bars or pips anywhere in the raster.
#   Everything around the field is an object -- nodes in hand sit on a shelf as themselves,
#   banked organisms are carried into a bank pocket, lost organisms fall into a spill
#   pocket -- and the level is lost only when the spill pocket is full. Implements the
#   arcengine ARCBaseGame contract (step / on_set_level / complete_action); consumed by
#   the Pyodide browser player, the CLI agent, and the duck-harness bundle.
# SRP/DRY check: Pass -- self-contained environment module; no existing utility covers
#   swarm-field simulation. Rendering follows the RenderableUserDisplay house pattern used
#   by cr01/px02. No shared font/sprite module exists to reuse.
"""Hive -- steer a drifting swarm into the sink by placing influence nodes.

Everything is done by clicking: pick a node from the shelf along the top edge, click the
board to place it or to take one back, then release the swarm to play the simulation out.
Adjust and release again.

Organisms always advance one cell to the right each tick; nodes decide whether they also
step up or down. That guarantees every run terminates and nothing can stall in place.

Nothing costs an action and nothing is counted for you. The nodes still in hand sit on
the shelf as themselves; organisms that reach a sink are carried into the bank pocket at
the top-right; every organism that falls off the board, hits a wall or a hazard lands in
the spill pocket along the bottom edge. When the spill pocket is full the level is lost.

8 levels. Fully deterministic -- no RNG anywhere.
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
OY = 6                       # playfield origin y: six rows of shelf above, six of pocket below

# There is no HUD: no bars, no pips, no counters. Everything around the field is a world
# object drawn at full size. Feedback from the ARC-3 team: all eight of our games lost by
# a budget counter and showed stock and progress as pip rows, so a set of eight tested
# one presentation eight times. Hive's pressure is a pile the player watches grow.
#  - DOCK: a shelf along the top edge holding one full-size node sprite per node still in
#    stock. A sprite leaves the shelf when its node is placed and comes back when the node
#    is taken back. Click a sprite to pick that kind; the picked kind is framed.
#  - BANK: a walled pocket at the top-right, exactly as many slots as the level's quota.
#    Every organism that reaches its sink is carried into it during the run.
#  - SPILL: a walled pocket along the bottom edge, exactly as many slots as the level's
#    capacity. Every organism that fails lands in it, in its own colour, and stays there
#    for the rest of the level. When it is full the level is lost.
# Both pockets are sized to what they hold, so "full" is visibly full and the remaining
# room is visibly remaining room. Walls are the board's brick greys (greys for structure).
DOCK_X0, DOCK_Y = 2, 1                    # first shelf slot's top-left; slots are CELL x CELL
DOCK_PITCH = CELL + 2                     # two clear pixels between shelf slots
BODY = 3                                  # body size in px: the sprite of a live organism
BODY_PITCH = BODY + 1                     # one-pixel gap between bodies in a pocket
POCKET_X1 = OX + GRID_W * CELL - 1        # both pockets are flush with the field's right edge
BANK_Y0 = 1                               # bank pocket top wall; its floor is the field's top rim
SPILL_Y0 = OY + GRID_H * CELL             # spill pocket top wall rests on the field's bottom rim

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

# Spill-pocket capacities: how many lost organisms a level tolerates before it fails.
# Every level's solution banks the whole swarm, so a clean run adds nothing to the pile and
# a fully failed release adds the whole swarm (3 or 4 bodies). Capacities are set so two
# total failures still leave a third attempt, while a blind policy that releases without
# thinking fills the pocket in three releases. The tutorial is generous because the
# mechanic is still unknown.
CAPACITIES = (12, 8, 8, 8, 8, 8, 10, 10)
for _ldef, _capacity in zip(LEVELS, CAPACITIES):
    _ldef["capacity"] = _capacity

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

    def _node_sprite(self, frame, px, py, kind):
        """A node: hollow ring with a bright core, so it never reads as an organism. The
        same sprite on the shelf and on the board -- the shelf holds the objects themselves."""
        frame[py:py + CELL, px:px + CELL] = NODE_COLOR[kind]
        frame[py + 1:py + 3, px + 1:px + 3] = C_BLACK
        frame[py + 1, px + 1] = C_WHITE if kind == N_ATTRACT else C_YELLOW

    def _pocket(self, frame, y0, slots, bodies):
        """A walled pocket flush with the field's right edge: light-grey top, grey left,
        dark-grey right and floor (lit from the top-left like the bricks), a black cavity
        exactly `slots` bodies wide, and one body per entry of `bodies` packed in from the
        left. A body is the exact sprite of a live organism in that organism's own colour."""
        x0 = POCKET_X1 - slots * BODY_PITCH
        y1 = y0 + BODY_PITCH
        frame[y0:y1 + 1, x0:POCKET_X1 + 1] = C_BLACK
        frame[y0, x0:POCKET_X1 + 1] = C_LGRAY
        frame[y0:y1 + 1, x0] = C_GRAY
        frame[y0:y1 + 1, POCKET_X1] = C_DGRAY
        frame[y1, x0:POCKET_X1 + 1] = C_DGRAY
        for i, kind in enumerate(bodies[:slots]):
            bx, by = x0 + 1 + i * BODY_PITCH, y0 + 1
            frame[by:by + BODY, bx:bx + BODY] = ORG_COLOR[kind]
            frame[by + 1, bx + 1] = C_LMAGENTA if kind == O_NORMAL else C_MAGENTA

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game
        # Palette: the corpus is 60.3% greyscale and this game was 95% grey -- worse than
        # the average it exists to differ from. Purple surround, maroon floor, orange
        # stipple: all three are near-absent from the catalogue (maroon is 0.0% of official
        # pixels), and the swarm/nodes keep their own hues so nothing loses meaning.
        frame[:, :] = C_PURPLE

        # Floor: a dark field stippled at every cell corner, so the grid the swarm moves
        # on is legible without drawing lines that would read as objects.
        frame[OY:OY + GRID_H * CELL, OX:OX + GRID_W * CELL] = C_MAROON
        frame[OY:OY + GRID_H * CELL:CELL, OX:OX + GRID_W * CELL:CELL] = C_ORANGE

        # Walls: brick, lit from the top-left so they read as solid mass.
        for (gx, gy) in g.walls:
            px, py = self._cell_px(gx, gy)
            if px < 0 or py < 0 or px + CELL > 64 or py + CELL > 64:
                continue
            frame[py:py + CELL, px:px + CELL] = C_GRAY
            frame[py, px:px + CELL] = C_LGRAY                 # top highlight
            frame[py + CELL - 1, px:px + CELL] = C_DGRAY      # bottom shadow
            frame[py:py + CELL, px + CELL - 1] = C_DGRAY      # right shadow

        # Hazards move maroon -> red with yellow flecks: maroon is now the floor, and a
        # hazard drawn in the floor's own colour is invisible.
        for (gx, gy) in g.hazards:
            px, py = self._cell_px(gx, gy)
            if 0 <= px and 0 <= py and px + CELL <= 64 and py + CELL <= 64:
                frame[py:py + CELL, px:px + CELL] = C_RED
                frame[py, px + 1] = C_YELLOW
                frame[py + 1, px + 3] = C_YELLOW
                frame[py + 2, px] = C_YELLOW
                frame[py + 3, px + 2] = C_YELLOW

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

        # Nodes on the board.
        for (gx, gy), kind in g.nodes.items():
            px, py = self._cell_px(gx, gy)
            if px < 0 or py < 0 or px + CELL > 64 or py + CELL > 64:
                continue
            self._node_sprite(frame, px, py, kind)

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

        # ---- the objects around the field ------------------------------------
        # Shelf: the nodes still in hand, as themselves. The picked kind is framed.
        for x, y, kind in g.dock_slots():
            self._node_sprite(frame, x, y, kind)
            if kind == g.selected:
                frame[y - 1, x - 1:x + CELL + 1] = C_WHITE
                frame[y + CELL, x - 1:x + CELL + 1] = C_WHITE
                frame[y - 1:y + CELL + 1, x - 1] = C_WHITE
                frame[y - 1:y + CELL + 1, x + CELL] = C_WHITE

        # Bank pocket (top-right, the quota) and spill pocket (bottom edge, the capacity).
        self._pocket(frame, BANK_Y0, g.required, g.bank)
        self._pocket(frame, SPILL_Y0, g.capacity, g.spill)

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
        self.dock_layout = []
        self.selected = None
        self.nodes = {}
        self.organisms = []
        self._spawns = []
        self.banked_by_kind = {}
        self.need_by_kind = {}
        self.banked_total = 0
        self.bank = []
        self.capacity = 1
        self.spill = []
        self._running = False
        self._tick = 0

        levels = [Level(sprites=[], grid_size=(64, 64), data=ldef, name=ldef["name"])
                  for ldef in LEVELS]

        super().__init__(
            "hv",
            levels,
            Camera(0, 0, 64, 64, C_PURPLE, C_PURPLE, [self.display]),
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
        self.capacity = ldef["capacity"]
        self.spill = []                    # kinds of every organism lost on this level

        # One fixed shelf slot per node in the level's stock, grouped by kind in palette
        # order. A slot empties when its node is placed and refills when it is taken back.
        self.dock_layout = []
        for kind in self.palette:
            for _ in range(ldef["stock"][kind]):
                self.dock_layout.append(
                    (DOCK_X0 + len(self.dock_layout) * DOCK_PITCH, DOCK_Y, kind))

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

    def dock_slots(self):
        """(x, y, kind) of every node sprite on the shelf right now: the first
        `stock_left[kind]` slots of each kind, so the rightmost of a kind leaves first."""
        shown, seen = [], {}
        for x, y, kind in self.dock_layout:
            seen[kind] = seen.get(kind, 0) + 1
            if seen[kind] <= self.stock_left.get(kind, 0):
                shown.append((x, y, kind))
        return shown

    def _reset_run(self):
        """Rewind the swarm to the source. Placed nodes and the spill pile are kept."""
        self.organisms = [{"pos": cell, "kind": kind, "alive": True}
                          for cell, kind in self._spawns]
        self.banked_by_kind = {k: 0 for k in self.sinks}
        self.banked_total = 0
        self.bank = []
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

    def _spill(self, org):
        """An organism that can never reach a sink dies, and its body joins the pile in
        the pocket on the same frame -- the player sees the cause and the cost together."""
        org["alive"] = False
        self.spill.append(org["kind"])

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
                    self._spill(org)                     # ran into a wall
                    continue
            if nx >= GRID_W:
                self._spill(org)                         # left the board
                continue

            partner = self._teleport_partner((nx, ny))
            if partner is not None:
                nx, ny = partner

            org["pos"] = (nx, ny)
            if (nx, ny) in self.hazards:
                self._spill(org)                         # scalded
                continue
            for kind, spos in self.sinks.items():
                if (nx, ny) == spos and org["kind"] == kind:
                    org["alive"] = False
                    self.banked_by_kind[kind] = self.banked_by_kind.get(kind, 0) + 1
                    self.banked_total += 1
                    self.bank.append(kind)               # carried into the bank pocket
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
        tally, bank = self.banked_total, self.bank   # keep the bank readable on the failed frame
        self._reset_run()
        self.banked_total, self.bank = tally, bank
        if len(self.spill) >= self.capacity:
            self.lose()                    # a full spill pocket is the only way to lose

    # -- input --------------------------------------------------------------

    def _dock_hit(self, x, y):
        """The kind of the shelf sprite under a click (one pixel of slack around it)."""
        for sx, sy, kind in self.dock_slots():
            if sx - 1 <= x <= sx + CELL and sy - 1 <= y <= sy + CELL:
                return kind
        return None

    def _board_cell(self, x, y):
        if not (OX <= x < OX + GRID_W * CELL and OY <= y < OY + GRID_H * CELL):
            return None
        return (x - OX) // CELL, (y - OY) // CELL

    def _handle_click(self, x, y):
        kind = self._dock_hit(x, y)
        if kind is not None:
            self.selected = kind
            return

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

        # Nothing costs an action: picking, placing and taking back nodes are free, and so
        # is releasing the swarm. A bad release is paid for in bodies, not in clicks.
        if aid == 6:
            self._handle_click(int(self.action.data.get("x", 0)),
                               int(self.action.data.get("y", 0)))
        elif aid == 5:                                 # release the swarm
            self._reset_run()
            self._running = True
            self._sim_tick()
            if self._run_over():
                self._finish_run()
            else:
                return                                 # animate: withhold completion

        self.complete_action()

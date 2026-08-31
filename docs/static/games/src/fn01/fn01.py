# Author: Claude Opus 5
# Date: 2026-08-27 09:10
# PURPOSE: fn01 "Feint" -- an ARC-AGI-3 environment built around an ADAPTIVE OPPONENT.
#   The player climbs a stack of walls; each wall has up to three doorways, one per route.
#   A guard stands in one doorway, chosen by a deterministic function of the player's own
#   route history. Some walls are chokes -- exactly one doorway exists -- so the player
#   cannot simply avoid the guard: the route history must be shaped several moves in
#   advance so the guard is standing somewhere else when the choke arrives. You win by
#   deliberately building a habit and then breaking it.
#   Searching all ~300 catalogued games for minimax/opponent/adversarial returns zero
#   files; every non-player mover in the corpus is a fixed script. "Agentness" is a
#   permitted ARC core prior, so a genuine adaptive opponent is legal and unoccupied.
# SRP/DRY check: Pass -- self-contained environment, no shared code to reuse.
"""Feint -- an opponent that learns your habits.

Click a doorway on the lit wall directly above you to step through it. A guard blocks one
doorway; its choice is a pure function of the routes you have been using, and it is always
shown BEFORE you commit, so the rule is learnable by playing. Walk into it and you lose a
life -- but a guard can never block the same doorway twice running, so nothing is ever
permanently sealed.

7 levels. Levels 1-5 each add exactly one rule to the guard and keep every earlier one;
6 and 7 add no rule and instead take away the slack. No RNG anywhere.
"""

import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

# ---------------------------------------------------------------------------
# Palette (ARC-3 indices). Deliberately built on the corpus' under-used colours:
# purple field, maroon/magenta walls, yellow/orange/green routes. Greys and black are
# used ONLY for inert structure (the HUD wash, the budget track, spent pips, walls
# already passed). Every semantic distinction is also carried by shape or position.
# ---------------------------------------------------------------------------

C_WHITE, C_LGRAY, C_GRAY, C_DGRAY, C_VDGRAY, C_BLACK = 0, 1, 2, 3, 4, 5
C_MAGENTA, C_LMAGENTA, C_RED, C_BLUE, C_LBLUE = 6, 7, 8, 9, 10
C_YELLOW, C_ORANGE, C_MAROON, C_GREEN, C_PURPLE = 11, 12, 13, 14, 15

C_FIELD = C_PURPLE            # the corridor the whole board is cut out of
C_WALL_AHEAD = C_MAROON       # a barrier you have not reached yet
C_WALL_LIVE = C_MAGENTA       # the barrier you may act on right now
C_WALL_PAST = C_VDGRAY        # inert -- already climbed
C_EXIT = C_LMAGENTA           # the band beyond the topmost wall
C_PLAYER = C_RED
C_HUD = C_VDGRAY              # background wash
C_TRACK = C_BLACK             # budget track / spent pips

ROUTE_COLOR = (C_YELLOW, C_ORANGE, C_GREEN)     # route 0 (left), 1 (middle), 2 (right)
GUARD_COLOR = (C_LBLUE, C_BLUE)                 # guard A solid, guard B punched

# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

K = 3                     # routes
CW = 21                   # width of a route band: 0-20, 21-41, 42-62
DOOR_INSET, DOOR_W = 4, 13
HUD_H = 9                 # rows 0..8 are the HUD wash
Y_TOP = HUD_H             # first playfield row
WALL0_Y0 = 55             # top row of the bottom-most wall

MOVE_COST = 2             # cost of attempting a doorway (hit or blocked)
BLOCK_COST = 2            # extra cost when the guard was standing there
MISS_COST = 1             # cost of a click that lands on solid wall / open field

MEMORY = 5                # how far back any guard clause may look -- its entire state
MEM_SHOW = 5              # history pips displayed (== MEMORY: the HUD shows all of it)


def geometry(n_walls):
    """Vertical layout for a level with n_walls walls. Chosen so the topmost wall never
    climbs into the HUD and the corridor gap always fits the 3px player token."""
    band = min(10, 43 // max(1, n_walls - 1)) if n_walls > 1 else 10
    wall_h = max(3, min(5, band - 3))
    return band, wall_h


# ---------------------------------------------------------------------------
# The guard's rule -- pure functions of the player's route history.
#
# Every clause is a pure function of H (the sequence of doorways the player has GONE FOR,
# successful or blocked), so the opponent is deterministic and its next block is always
# rendered before the player commits. Nothing here reads a random number.
# ---------------------------------------------------------------------------

def _mode_recent(hist, window):
    """Most-used route of the last `window` entries; ties go to the more recent."""
    win = hist[-window:]
    best, best_n, best_pos = win[-1], -1, -1
    for c in set(win):
        n = win.count(c)
        pos = max(i for i, v in enumerate(win) if v == c)
        if n > best_n or (n == best_n and pos > best_pos):
            best, best_n, best_pos = c, n, pos
    return best


def _last_other(hist, c):
    """Most recent entry different from `c`; falls back to the next route clockwise.

    Scans only MEMORY entries: the guard's whole state is the tail of the history that the
    HUD draws, so what the player can see is exactly what the guard knows."""
    for v in reversed(hist[-MEMORY:]):
        if v != c:
            return v
    return (c + 1) % K


def _is_alternating(hist):
    """The last four entries are a strict two-route alternation X Y X Y."""
    return (len(hist) >= 4 and hist[-1] != hist[-2]
            and hist[-1] == hist[-3] and hist[-2] == hist[-4])


def guard_pos(rule, extras, hist, just_blocked):
    """Which doorway this guard stands in, given the player's history.

    `extras` is the set of clauses this level has switched on; they are tested before the
    guard's base memory rule, so a level only ever ADDS behaviour to the level before it.
    `just_blocked` is the doorway this guard blocked on the immediately preceding attempt
    -- the one universal clause, present on every level: a guard never blocks the same
    doorway twice running, which is what makes it impossible to be sealed in.
    """
    if "ALT" in extras and _is_alternating(hist):
        pos = hist[-2]                       # counter-adapt: block the alternation itself
    elif "DOUBLE" in extras and len(hist) >= 2 and hist[-1] == hist[-2]:
        pos = _last_other(hist, hist[-1])    # a doubled move reads as a bait; pre-empt it
    elif rule == "FREQ3":
        pos = _mode_recent(hist, 3)
    else:                                    # "LAST"
        pos = hist[-1]
    if pos == just_blocked:                  # universal: never twice in a row
        pos = (pos + 1) % K
    return pos


# ---------------------------------------------------------------------------
# Levels.
#
# "walls" runs bottom (the one you face first) to top (the exit). Each wall is
#   (open_mask, guard_indices): open_mask is one character per route, "1" = there is a
#   doorway there, "0" = solid. A wall whose mask has a single "1" is a CHOKE -- the guard
#   cannot be side-stepped there, it has to have been led away several moves earlier.
# "guards" is (base_rule, extra_clauses) per guard.
# "seed" is the route history the level starts with; it is drawn in the HUD, so the
#   guard's whole input is on screen from the first frame.
# ---------------------------------------------------------------------------

_D = ("DOUBLE",)
_DA = ("DOUBLE", "ALT")

LEVELS = [
    {
        # NEW: there is a guard, and it stands in the doorway you used last. Alternating is
        # enough. Five lives and 4.6x the budget the level needs -- this one exists to show
        # what the guard does, not to be survived.
        "name": "First Door",
        "lives": 5, "budget": 46,
        "seed": (2, 1, 2, 1, 2),
        "guards": [("LAST", ())],
        "walls": [("111", (0,)), ("111", (0,)), ("101", (0,)),
                  ("111", (0,)), ("010", (0,))],
    },
    {
        # NEW: the guard remembers three moves and blocks your MOST-USED route, not your
        # last -- and choke walls appear, single doorways you cannot step around. The two
        # together are the whole game: the route you need is the route you have been using.
        "name": "Habit",
        "lives": 3, "budget": 22,
        "seed": (1, 0, 0, 1, 1),
        "guards": [("FREQ3", ())],
        "walls": [("011", (0,)), ("101", (0,)), ("111", (0,)), ("111", (0,)),
                  ("010", (0,)), ("011", (0,)), ("001", (0,)), ("001", (0,))],
    },
    {
        # NEW: a second guard, with a different memory length -- and walls are watched by
        # one of them, by both, or by neither, so which rule is about to be applied changes
        # as you climb. The marks on the ends of every wall say who is watching it.
        "name": "Two Watchers",
        "lives": 3, "budget": 22,
        "seed": (2, 0, 1, 2, 1),
        "guards": [("LAST", ()), ("FREQ3", ())],
        "walls": [("101", (0, 1)), ("011", ()), ("111", ()), ("110", (1,)),
                  ("100", (0,)), ("101", (1,)), ("001", (0,)), ("001", (1,))],
    },
    {
        # NEW: both guards now read a doubled move differently from an alternation. Repeat
        # a route and they take it as a bait and cover the route you would switch back to.
        "name": "Double Bind",
        "lives": 3, "budget": 22,
        "seed": (1, 2, 1, 1, 0),
        "guards": [("LAST", _D), ("FREQ3", _D)],
        "walls": [("011", ()), ("101", (0,)), ("101", ()), ("010", (0,)),
                  ("011", (1,)), ("011", (0,)), ("010", (0, 1)), ("001", (1,))],
    },
    {
        # NEW: counter-adaptation. Alternate cleanly four times and the guards stop
        # covering where you just were and start covering the alternation itself -- the
        # habit that was working becomes the thing being read.
        # The line that clears it opens 1,2,1,2 -- a clean alternation -- and then has to
        # break its own pattern, because by the fourth beat the guards are covering the
        # alternation rather than the last move.
        "name": "Mirror",
        "lives": 3, "budget": 22,
        "seed": (0, 0, 0, 1, 1),
        "guards": [("LAST", _DA), ("FREQ3", _DA)],
        "walls": [("011", (0, 1)), ("111", (0, 1)), ("111", (0,)), ("101", (0, 1)),
                  ("001", (1,)), ("001", (0,)), ("101", ()), ("100", (0,))],
    },
    {
        # Every rule now in force at once, with a life taken away and the choke walls
        # crowding together. Nothing new to learn here -- only nothing left to spare.
        "name": "Squeeze",
        "lives": 2, "budget": 22,
        "seed": (1, 0, 1, 0, 0),
        "guards": [("LAST", _DA), ("FREQ3", _DA)],
        "walls": [("101", (0,)), ("111", (0, 1)), ("011", (1,)), ("011", ()),
                  ("101", (0, 1)), ("100", (1,)), ("001", (0, 1)), ("100", (0, 1))],
    },
    {
        # The whole thing. The line that clears it is a habit built on one route and then
        # deliberately broken -- which is the only thing this game has ever been about.
        "name": "Feint",
        "lives": 2, "budget": 22,
        "seed": (1, 1, 1, 0, 2),
        "guards": [("LAST", _DA), ("FREQ3", _DA)],
        "walls": [("011", ()), ("011", (1,)), ("011", (1,)), ("001", (0, 1)),
                  ("011", (0, 1)), ("100", (0,)), ("100", ()), ("001", (0,))],
    },
]


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

class Fn01Display(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    @staticmethod
    def _rect(frame, x0, y0, x1, y1, color):
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(63, x1), min(63, y1)
        if x0 <= x1 and y0 <= y1:
            frame[y0:y1 + 1, x0:x1 + 1] = color

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game
        frame[:, :] = C_FIELD

        # -- HUD wash (grey is allowed here: it carries no meaning) ---------
        self._rect(frame, 0, 0, 63, HUD_H - 1, C_HUD)

        # budget: a bar, never a number. Length is the quantity; the colour restates it.
        self._rect(frame, 1, 0, 62, 1, C_TRACK)
        if g.budget_max > 0 and g.budget_left > 0:
            filled = max(1, int(61 * g.budget_left / g.budget_max))
            self._rect(frame, 1, 0, 1 + filled - 1, 1,
                       C_LMAGENTA if g.budget_left * 4 > g.budget_max else C_ORANGE)

        # lives: pips, left. Same red as the player token -- they are the player's lives.
        for i in range(g.lives_max):
            x = 1 + i * 4
            self._rect(frame, x, 3, x + 2, 5, C_PLAYER if i < g.lives else C_TRACK)

        # memory: the guard's entire input, on screen -- one pip per remembered move,
        # oldest on the left. Route is carried by the pip's vertical offset as well as by
        # its colour, so the strip stays readable without relying on hue alone.
        recent = g.history[-MEM_SHOW:]
        for i, c in enumerate(recent):
            x = 44 + i * 4
            self._rect(frame, x, 3 + c, x + 2, 5 + c, ROUTE_COLOR[c])

        # -- playfield ------------------------------------------------------
        n = g.n_walls
        band, wall_h = g.band, g.wall_h

        # route ribbons -- each route is one continuous line running the entire corridor,
        # so a doorway reads as "this route keeps going here" and a solid stretch of wall
        # reads as "it does not"
        for c in range(K):
            cx = c * CW + CW // 2
            self._rect(frame, cx - 1, Y_TOP, cx + 1, 63, ROUTE_COLOR[c])

        # the way out: the band across the top, past the last wall
        self._rect(frame, 0, Y_TOP, 63, Y_TOP + 2, C_EXIT)

        for i in range(n):
            y0 = WALL0_Y0 - i * band
            y1 = y0 + wall_h - 1
            if i < g.row:
                wc = C_WALL_PAST
            elif i == g.row:
                wc = C_WALL_LIVE
            else:
                wc = C_WALL_AHEAD
            self._rect(frame, 0, y0, 63, y1, wc)
            # Which guard patrols this wall, marked on BOTH ends of every wall, not just
            # the live one -- so which rule is coming is visible before you get there. A
            # wall with no mark is watched by nobody.
            gids = g.walls[i]["guards"]
            for j, gid in enumerate(gids):
                span = max(1, wall_h // len(gids))
                yy0 = y0 + j * span
                yy1 = y1 if j == len(gids) - 1 else min(y1, yy0 + span - 1)
                self._rect(frame, 0, yy0, 2, yy1, GUARD_COLOR[gid])
                self._rect(frame, 61, yy0, 63, yy1, GUARD_COLOR[gid])
            # doorways: carve the wall away so the route ribbon shows through
            for c in range(K):
                if not g.walls[i]["open"][c]:
                    continue
                dx0 = c * CW + DOOR_INSET
                dx1 = dx0 + DOOR_W - 1
                self._rect(frame, dx0, y0, dx1, y1, C_FIELD)
                cx = c * CW + CW // 2
                self._rect(frame, cx - 1, y0, cx + 1, y1, ROUTE_COLOR[c])
                if i == g.row:
                    # the doorways you may actually click: filled solid in route colour
                    self._rect(frame, dx0, y0, dx1, y1, ROUTE_COLOR[c])

        # -- guards: the telegraph, and the thing the whole game hangs on. Deliberately the
        # largest, highest-contrast objects on the board -- a cold blue block on a warm
        # field, standing taller than the wall it plugs, so the route about to close is the
        # first thing the eye lands on. Guard A is solid, guard B is punched through, so
        # the two are told apart by shape as well as by colour.
        if g.row < n:
            y0 = WALL0_Y0 - g.row * band
            y1 = y0 + wall_h - 1
            for gid in g.walls[g.row]["guards"]:
                c = g.gpos[gid]
                dx0 = c * CW + DOOR_INSET - 1
                dx1 = dx0 + DOOR_W + 1
                self._rect(frame, dx0, y0 - 2, dx1, y1, GUARD_COLOR[gid])
                if gid == 1:                      # guard B is punched through, guard A solid
                    mx = (dx0 + dx1) // 2
                    self._rect(frame, mx - 1, y0 - 1, mx + 1, y1 - 1, C_FIELD)

            # -- player: on the landing under the live wall, in the route band it last
            # used, so the newest history entry is also readable from the board itself.
            px = g.history[-1] * CW + (CW - 5) // 2
            self._rect(frame, px, y1 + 1, px + 4, y1 + 3, C_PLAYER)
        else:
            # past the last wall: standing in the way out
            px = g.history[-1] * CW + (CW - 5) // 2
            self._rect(frame, px, Y_TOP + 3, px + 4, Y_TOP + 5, C_PLAYER)
        return frame


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Fn01(ARCBaseGame):
    def __init__(self):
        self.display = Fn01Display(self)

        # on_set_level() runs inside super().__init__(), so all of these must exist first
        self.walls = []
        self.guards = []
        self.history = [0]
        self.gpos = []
        self.jb = []
        self.row = 0
        self.n_walls = 0
        self.band = 10
        self.wall_h = 5
        self.lives = 0
        self.lives_max = 0
        self.budget_max = 0
        self.budget_left = 0

        levels = [Level(sprites=[], grid_size=(64, 64), data=ldef, name=ldef["name"])
                  for ldef in LEVELS]

        super().__init__(
            "fn",
            levels,
            Camera(0, 0, 64, 64, C_FIELD, C_FIELD, [self.display]),
            False,
            len(levels),
            [6],                                  # click a doorway -- that is the whole verb
        )

    # -- level setup --------------------------------------------------------

    def on_set_level(self, level: Level) -> None:
        ldef = LEVELS[self.level_index]
        self.walls = [{"open": [ch == "1" for ch in mask], "guards": list(gids)}
                      for (mask, gids) in ldef["walls"]]
        self.guards = [(rule, set(extras)) for (rule, extras) in ldef["guards"]]
        self.history = list(ldef["seed"])
        self.jb = [None] * len(self.guards)
        self.row = 0
        self.n_walls = len(self.walls)
        self.band, self.wall_h = geometry(self.n_walls)
        self.lives = self.lives_max = ldef["lives"]
        self.budget_max = self.budget_left = ldef["budget"]
        self.gpos = [0] * len(self.guards)
        self._recompute_guards()

    def _recompute_guards(self):
        for i, (rule, extras) in enumerate(self.guards):
            self.gpos[i] = guard_pos(rule, extras, self.history, self.jb[i])

    # -- queries ------------------------------------------------------------

    def wall_rows(self, i):
        y0 = WALL0_Y0 - i * self.band
        return y0, y0 + self.wall_h - 1

    def door_at(self, x, y):
        """Which doorway of the LIVE wall a click landed in, or None."""
        if self.row >= self.n_walls:
            return None
        y0, y1 = self.wall_rows(self.row)
        if not (y0 <= y <= y1):
            return None
        for c in range(K):
            dx0 = c * CW + DOOR_INSET
            if dx0 <= x < dx0 + DOOR_W and self.walls[self.row]["open"][c]:
                return c
        return None

    def blockers_at(self, col):
        return [gid for gid in self.walls[self.row]["guards"] if self.gpos[gid] == col]

    # -- simulation ---------------------------------------------------------

    def attempt(self, col):
        """Go for doorway `col` of the live wall. Returns True if the player stepped through.

        The attempt enters the history whether or not it succeeded: the guard is watching
        what you go for, not what you get away with. That also means a blocked attempt is
        a legitimate (if expensive) way to move the guard.
        """
        blockers = self.blockers_at(col)
        self.history.append(col)
        for i in range(len(self.guards)):
            self.jb[i] = col if i in blockers else None
        if blockers:
            self.lives -= 1
        else:
            self.row += 1
        self._recompute_guards()
        return not blockers

    # -- engine entry point -------------------------------------------------

    def step(self) -> None:
        aid = self.action.id.value

        if aid == 6:
            data = self.action.data or {}
            x = int(data.get("x", 0))
            y = int(data.get("y", 0))
            col = self.door_at(x, y)
            if col is None:
                # A click on solid wall or open field is a wasted move, never a death:
                # the rule has to be discoverable by poking at the board.
                self.budget_left -= MISS_COST
            else:
                self.budget_left -= MOVE_COST
                if not self.attempt(col):
                    # Walking into the guard is a cost, never an ending: a life and a
                    # bite out of the budget, and the guard has to step aside next turn.
                    self.budget_left -= BLOCK_COST

        if self.row >= self.n_walls:
            self.next_level()
            self.complete_action()
            return

        if self.lives <= 0 or self.budget_left <= 0:
            self.lives = max(0, self.lives)
            self.budget_left = max(0, self.budget_left)
            self.lose()

        self.complete_action()

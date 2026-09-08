# Author: Claude Opus 5
# Date: 2026-08-27 09:10 (revised 2026-09-02 -- budget removed; lives are the only loss;
#   the guard's memory is drawn as footprints on the floor instead of a HUD strip)
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
#   Revision: the ARC-3 team found all our games lose by a budget counter. This one now
#   loses ONLY by lives -- being caught by a guard -- and the guard's whole input (the
#   last five route choices) is drawn in-world as a trail of fading footprints behind the
#   player instead of as a pip strip in the HUD.
# SRP/DRY check: Pass -- self-contained environment, no shared code to reuse.
"""Feint -- an opponent that learns your habits.

Click a doorway on the lit wall directly above you to step through it. A guard blocks one
doorway; its choice is a pure function of the routes you have been using, and it is always
shown BEFORE you commit, so the rule is learnable by playing. Walk into it and you lose a
life -- but a guard can never block the same doorway twice running, so nothing is ever
sealed while you still have a life to spend on bumping it.

Lives are the only way to lose, and they are not a counter: they are the doorways in the
exit wall at the top of the board. Every catch bricks one up, the exit visibly narrows,
and when the last doorway is walled the level is lost. There is no action budget: a click
on solid wall or open field does nothing at all. The guard reads your last five route
choices, and those five are on the floor behind you as footprints -- the pair you are
standing on is the newest and brightest, the print furthest behind is the oldest and
dimmest. Nothing has to be remembered: the guard, its rule's whole input, the doorways
ahead and the lives left are all on screen every frame.

7 levels. Levels 1-5 each add exactly one rule to the guard and keep every earlier one;
6 and 7 add no rule and instead take away the slack. Every layout is chosen so that a
player who dodges the guard it can see and looks at most two walls ahead is never caught
(verified exactly, see random_gate.py), while a blind door-masher and every fixed door
cycle fail. No RNG anywhere.
"""

import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

# ---------------------------------------------------------------------------
# Palette (ARC-3 indices). Deliberately built on the corpus' under-used colours:
# purple field, maroon/magenta walls, yellow/orange/green routes. The one grey is the
# inert colour of a wall already climbed; there is no HUD, no bar and no pip anywhere.
# Every semantic distinction is also carried by shape or position.
# ---------------------------------------------------------------------------

C_WHITE, C_LGRAY, C_GRAY, C_DGRAY, C_VDGRAY, C_BLACK = 0, 1, 2, 3, 4, 5
C_MAGENTA, C_LMAGENTA, C_RED, C_BLUE, C_LBLUE = 6, 7, 8, 9, 10
C_YELLOW, C_ORANGE, C_MAROON, C_GREEN, C_PURPLE = 11, 12, 13, 14, 15

C_FIELD = C_PURPLE            # the corridor the whole board is cut out of
C_WALL_AHEAD = C_MAROON       # a barrier you have not reached yet -- and the exit wall
C_WALL_LIVE = C_MAGENTA       # the barrier you may act on right now
C_WALL_PAST = C_VDGRAY        # inert -- already climbed
C_EXIT = C_LMAGENTA           # the beyond: the strip above the exit wall, seen through it
C_PLAYER = C_RED

ROUTE_COLOR = (C_YELLOW, C_ORANGE, C_GREEN)     # route 0 (left), 1 (middle), 2 (right)
GUARD_COLOR = (C_LBLUE, C_BLUE)                 # guard A solid, guard B punched

# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

K = 3                     # routes
CW = 21                   # width of a route band: 0-20, 21-41, 42-62
DOOR_INSET, DOOR_W = 4, 13
BEYOND_H = 3              # rows 0..2: the light-magenta beyond, past the exit wall
Y_TOP = BEYOND_H          # the exit wall: rows 3..5, one doorway per life
EXIT_DOOR_W = 8           # width of an exit doorway -- deliberately NOT a route doorway's 13
WALL0_Y1 = 52             # BOTTOM row of the bottom-most wall. The stack grows upward from
                          # it, so the top wall's top row lands on row 8 for every level and
                          # the floor under the first landing (rows 56-63) always has room
                          # for the whole footprint trail before a single wall is climbed.


def exit_doors(n):
    """x-spans of the n doorways in the exit wall, spread evenly and fixed for the level.

    There is no HUD. Lives are the doorways left open in the exit wall at the top: every
    catch bricks one up, the exit visibly narrows, and when the last one is walled the level
    is lost. The doorways are 8 wide, not the 13 of a route doorway, and sit off the route
    lanes, so they never read as something to click."""
    if n <= 0:
        return []
    pillar = (64 - EXIT_DOOR_W * n) // (n + 1)
    extra = 64 - EXIT_DOOR_W * n - pillar * (n + 1)
    x = pillar + extra // 2
    out = []
    for _ in range(n):
        out.append((x, x + EXIT_DOOR_W - 1))
        x += EXIT_DOOR_W + pillar
    return out

MEMORY = 5                # how far back any guard clause may look -- its entire state
TRAIL = MEMORY            # footprints drawn: the guard's whole input is on the floor
FOOT_PITCH = 2            # rows between successive prints

# The fade ramp for the trail, newest print first. Each print is a pair of 3x2 feet
# standing astride the route ribbon -- never on it, so a print is always drawn against the
# floor (purple field or dark-grey climbed wall) rather than against its own colour. Lit
# pixels per print: 12, 8, 6, 4, 2 -- a strictly falling brightness -- and age is carried
# by vertical order as well, so the trail reads without relying on the ramp alone.
FOOT_FADE = (
    (("###", "###"), ("###", "###")),
    (("#.#", ".#."), ("#.#", ".#.")),
    ((".#.", "#.#"), (".#.", "#.#")),
    (("#..", "..#"), ("..#", "#..")),
    (("#..", "..."), ("..#", "...")),
)
FOOT_W = 3


def geometry(n_walls):
    """Vertical layout for a level with n_walls walls. Chosen so the topmost wall never
    climbs into the exit band and the corridor gap always fits the 3px player token."""
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
    footprint trail draws, so what the player can see is exactly what the guard knows."""
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
# "seed" is the route history the level starts with; it is drawn as the footprint trail
#   under the first landing, so the guard's whole input is on screen from the first frame.
# "lives" is the only resource in the game, shown as the open doorways of the exit wall.
#
# Layouts (revised 2 Sep 2026). The first set was searched to admit essentially ONE
# guard-free line per level, which made a two-wall planner's clear odds 8-25% -- fine for
# an agent, hopeless for a person. The team's rule is now that a human must beat every
# level easily and no level may demand more than two steps of lookahead. So every layout
# below was re-searched (~30,000 candidates per level, exact evaluation, see
# random_gate.py) for these properties, all verified without sampling:
#   * a player who dodges the guard it can see and looks ONE wall ahead is never caught;
#   * a purely reactive player (no lookahead at all) is never caught on L2, and is caught
#     at most on some paths on L3-L7 -- where two lives absorb one mistake;
#   * no fixed door cycle of length <= 4 clears the level, even with free misses;
#   * a blind door-masher clears as rarely as those constraints allow (1/11 - 1/24).
# Two lives on every non-tutorial level: three lets a guard-dodger walk levels outright,
# one turns a single slip into a restart, which is not "easily".
# ---------------------------------------------------------------------------

_D = ("DOUBLE",)
_DA = ("DOUBLE", "ALT")

LEVELS = [
    {
        # NEW: there is a guard, and it stands in the doorway you used last. Alternating is
        # enough. Five lives on a five-wall climb -- this one exists to show what the guard
        # does, what a footprint trail is and what a bricked-up exit doorway means, not to
        # be survived.
        "name": "First Door",
        "lives": 5,
        "seed": (2, 1, 2, 1, 2),
        "guards": [("LAST", ())],
        "walls": [("111", (0,)), ("111", (0,)), ("101", (0,)),
                  ("111", (0,)), ("010", (0,))],
    },
    {
        # NEW: the guard remembers three moves and blocks your MOST-USED route, not your
        # last -- and choke walls appear, single doorways you cannot step around. The two
        # together are the whole game: the route you need is the route you have been using.
        # A player who simply avoids the guard it can see is never caught here; the chokes
        # (right, then middle) exist to show the rule, not to punish it.
        "name": "Habit",
        "lives": 2,
        "seed": (2, 1, 2, 1, 1),
        "guards": [("FREQ3", ())],
        "walls": [("011", (0,)), ("011", (0,)), ("101", (0,)), ("011", (0,)),
                  ("001", (0,)), ("010", (0,)), ("011", (0,)), ("101", (0,))],
    },
    {
        # NEW: a second guard, with a different memory length -- and walls are watched by
        # one of them, by both, or by neither, so which rule is about to be applied changes
        # as you climb. The marks on the ends of every wall say who is watching it. Three
        # chokes, one on each route; a reactive player is caught on half its paths, one
        # wall of lookahead is always enough.
        "name": "Two Watchers",
        "lives": 2,
        "seed": (2, 2, 2, 2, 0),
        "guards": [("LAST", ()), ("FREQ3", ())],
        "walls": [("111", (0, 1)), ("011", (0,)), ("101", ()), ("100", (0,)),
                  ("010", (0,)), ("110", (0, 1)), ("001", (0,)), ("101", (1,))],
    },
    {
        # NEW: both guards now read a doubled move differently from an alternation. Repeat
        # a route and they take it as a bait and cover the route you would switch back to.
        "name": "Double Bind",
        "lives": 2,
        "seed": (1, 2, 2, 2, 1),
        "guards": [("LAST", _D), ("FREQ3", _D)],
        "walls": [("111", (1,)), ("101", (0,)), ("101", (1,)), ("010", (0, 1)),
                  ("011", (0, 1)), ("001", ()), ("011", (0, 1)), ("011", (1,))],
    },
    {
        # NEW: counter-adaptation. Alternate cleanly four times and the guards stop
        # covering where you just were and start covering the alternation itself -- the
        # habit that was working becomes the thing being read.
        "name": "Mirror",
        "lives": 2,
        "seed": (1, 2, 0, 0, 2),
        "guards": [("LAST", _DA), ("FREQ3", _DA)],
        "walls": [("110", (0, 1)), ("111", (0,)), ("110", (0,)), ("100", (1,)),
                  ("001", (0,)), ("101", (0, 1)), ("101", (0,)), ("101", (0,))],
    },
    {
        # Every rule now in force at once and the choke walls crowding together: two
        # consecutive chokes on the left route, then one in the middle. Nothing new to
        # learn here -- but a purely reactive player is caught on half its paths, so this
        # is the level where looking one wall ahead stops being optional.
        "name": "Squeeze",
        "lives": 2,
        "seed": (2, 1, 1, 0, 0),
        "guards": [("LAST", _DA), ("FREQ3", _DA)],
        "walls": [("110", (0, 1)), ("110", (1,)), ("111", (0,)), ("100", (0, 1)),
                  ("100", (1,)), ("011", (0, 1)), ("110", (1,)), ("010", ())],
    },
    {
        # The whole thing: four chokes in the last five walls, alternating middle and left,
        # under guards that read an alternation as a habit. The line that clears it builds
        # a habit and then deliberately breaks it -- which is the only thing this game has
        # ever been about. One wall of lookahead still suffices, verified exactly.
        "name": "Feint",
        "lives": 2,
        "seed": (0, 1, 1, 2, 1),
        "guards": [("LAST", _DA), ("FREQ3", _DA)],
        "walls": [("011", (0,)), ("011", (0, 1)), ("011", (0, 1)), ("101", (1,)),
                  ("010", (0,)), ("100", (1,)), ("010", (1,)), ("100", ())],
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

    @staticmethod
    def _trail(frame, history, foot_y):
        """The guard's entire input, on the floor: the last TRAIL route choices as prints
        behind the player, newest at `foot_y` (the player's own feet) and one FOOT_PITCH
        further down for every step back in time. Each print is two 2x2 feet astride the
        route ribbon of the lane it was made in, so the lane is carried by position and the
        age by both vertical order and the fade ramp."""
        recent = history[-TRAIL:]
        for k, c in enumerate(reversed(recent)):        # k = 0 is the newest print
            y = foot_y + k * FOOT_PITCH
            if y > 63:
                break
            cx = c * CW + CW // 2
            left, right = FOOT_FADE[k]
            for fx, pat in ((cx - 2 - FOOT_W, left), (cx + 3, right)):
                for dy, row in enumerate(pat):
                    if y + dy > 63:
                        continue
                    for dx, ch in enumerate(row):
                        if ch == "#":
                            frame[y + dy, fx + dx] = ROUTE_COLOR[c]

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game
        frame[:, :] = C_FIELD

        n = g.n_walls

        # -- the way out, which is also the lives display. The beyond runs across the very
        # top; under it stands the exit wall with one doorway per life. A catch bricks the
        # leftmost open doorway up, so the exit narrows in full view, and when the last one
        # is walled there is no way out and the level is lost. There is no HUD.
        self._rect(frame, 0, 0, 63, BEYOND_H - 1, C_EXIT)
        self._rect(frame, 0, Y_TOP, 63, Y_TOP + 2, C_WALL_AHEAD)
        doors = exit_doors(g.lives_max)
        lost = g.lives_max - g.lives
        for i, (x0, x1) in enumerate(doors):
            if i >= lost:
                self._rect(frame, x0, Y_TOP, x1, Y_TOP + 2, C_EXIT)

        # route ribbons -- each route is one continuous line running the whole corridor
        # under the exit wall, so a doorway reads as "this route keeps going here" and a
        # solid stretch of wall reads as "it does not"
        for c in range(K):
            cx = c * CW + CW // 2
            self._rect(frame, cx - 1, Y_TOP + 3, cx + 1, 63, ROUTE_COLOR[c])

        for i in range(n):
            y0, y1 = g.wall_rows(i)
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
                span = max(1, g.wall_h // len(gids))
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
            y0, y1 = g.wall_rows(g.row)
            for gid in g.walls[g.row]["guards"]:
                c = g.gpos[gid]
                dx0 = c * CW + DOOR_INSET - 1
                dx1 = dx0 + DOOR_W + 1
                self._rect(frame, dx0, y0 - 2, dx1, y1, GUARD_COLOR[gid])
                if gid == 1:                      # guard B is punched through, guard A solid
                    mx = (dx0 + dx1) // 2
                    self._rect(frame, mx - 1, y0 - 1, mx + 1, y1 - 1, C_FIELD)

            # -- the trail, then the player standing on its newest print. The player is on
            # the landing under the live wall, in the route band it last went for, so the
            # newest history entry is the player's own position and every older one is a
            # print further down the corridor it has already walked.
            py = y1 + 1
            self._trail(frame, g.history, py + 1)
            px = g.history[-1] * CW + (CW - 5) // 2
            self._rect(frame, px, py, px + 4, py + 2, C_PLAYER)
        else:
            # past the last wall: standing in the first open exit doorway
            x0, x1 = doors[min(lost, len(doors) - 1)]
            px = (x0 + x1) // 2 - 2
            self._rect(frame, px, Y_TOP, px + 4, Y_TOP + 2, C_PLAYER)
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
        self.lives = self.lives_max = ldef["lives"]     # refilled on every level entry
        self.gpos = [0] * len(self.guards)
        self._recompute_guards()

    def _recompute_guards(self):
        for i, (rule, extras) in enumerate(self.guards):
            self.gpos[i] = guard_pos(rule, extras, self.history, self.jb[i])

    # -- queries ------------------------------------------------------------

    def wall_rows(self, i):
        """Top and bottom row of wall i. The stack is anchored to the bottom wall's bottom
        row and grows upward, so the top wall's top row is 8 on every level."""
        y0 = WALL0_Y1 - self.wall_h + 1 - i * self.band
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
            col = self.door_at(int(data.get("x", 0)), int(data.get("y", 0)))
            if col is not None:
                # Walking into the guard costs a life, never the level outright (except on
                # the one-life level, where it is still telegraphed before the commit), and
                # the guard has to step aside next turn. A click on solid wall or open field
                # does nothing at all: there is no budget for it to spend.
                self.attempt(col)

        if self.row >= self.n_walls:
            self.next_level()
            self.complete_action()
            return

        if self.lives <= 0:
            self.lives = 0
            self.lose()

        self.complete_action()

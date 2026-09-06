# Author: Claude (Fable 5.1)
# Date: 2026-09-02
# PURPOSE: pr01 "Press" -- an ARC-AGI-3 environment with no goal object at all. The room's
#   walls advance one cell on every action and halt on a drawn line; the player wins by
#   being inside that line when they halt and loses by being crushed. Nothing to reach,
#   collect or press. Each level adds one rule: interior pillars, a press from two sides
#   only, cracked pillars that give way as the wall arrives, a two-phase press that halts
#   and then resumes, and a sweeping piston. Core-knowledge priors only -- objectness,
#   geometry, basic physics, agentness. No text, glyphs, numbers, bars or pips: the
#   shrinking room is the only clock.
# SRP/DRY check: Pass -- self-contained. The rules live in one pure function,
#   `transition`, which the game, the smoke-test solver and the gate's exact counter share.
"""Press -- survive a room that closes in.

ACTION1/2/3/4 step up/down/left/right. Every action the walls advance one cell. They stop
on the drawn line. Be inside it. 7 levels, no RNG, d-pad only, no budget, no lives.
"""

from collections import namedtuple

import numpy as np
from arcengine import ARCBaseGame, Camera, GameState, Level, RenderableUserDisplay

# ---------------------------------------------------------------------------
# Palette (ARC-3 indices). Built on the under-used end: purple floor, maroon press,
# orange pillars, magenta piston, light-magenta halt line. Grey is texture only.
# ---------------------------------------------------------------------------

C_WHITE, C_VDGRAY = 0, 4
C_MAGENTA, C_LMAGENTA, C_YELLOW, C_ORANGE, C_MAROON, C_PURPLE = 6, 7, 11, 12, 13, 15

C_FLOOR = C_PURPLE      # the room
C_WALL = C_MAROON       # the press: a solid mass with a brick texture
C_FACE = C_YELLOW       # the pressing face -- of the wall, and of the piston's nose
C_PILLAR = C_ORANGE     # static, hollow-centred; cracked ones show a diagonal seam
C_HALT = C_LMAGENTA     # where the press stops. Solid = next halt, dashed = the one after
C_MOVER = C_MAGENTA     # the piston and the dots of its track
C_PLAYER = C_WHITE      # solid block alive; a single flat line when pressed
C_BRICK = C_VDGRAY

# ---------------------------------------------------------------------------
# Geometry -- 21x21 cells of 3px fill 63x63 of the 64x64 frame
# ---------------------------------------------------------------------------

W = 21
CELL = 3
OX, OY = 0, 0
CENTRE = (W // 2, W // 2)

DIR_OF_ACTION = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}

# ---------------------------------------------------------------------------
# Levels. Coordinates are (x, y). `sides` names the walls that move. `phases` lists how
# far the press has advanced when it halts; between phases it holds for `pause` actions.
# A cracked pillar gives way when the wall face is one cell from it. The piston shuttles
# along `track`, one cell per action, and presses whatever it moves onto.
# ---------------------------------------------------------------------------


def _block(skip=()):
    """The final 3x3 room, pillared except the cells in `skip`."""
    return [(x, y) for y in range(9, 12) for x in range(9, 12) if (x, y) not in skip]


LEVELS = [
    {
        # NEW: the walls advance on every action and halt on the line. Empty room, two
        # actions of slack -- move inward and you cannot fail.
        "name": "Room",
        "sides": "TBLR", "phases": [6], "pause": 0,
        "start": (10, 2), "pillars": [], "cracked": [], "mover": None,
    },
    {
        # NEW: pillars. The final room is pillared except one corner, and a fence runs
        # beside the lane so the sidestep into that corner has exactly one place to happen.
        # Walking to the centre ends against a pillar with the wall at your back.
        "name": "Pocket",
        "sides": "TBLR", "phases": [9], "pause": 0,
        "start": (10, 1),
        "pillars": _block(skip=[(9, 9)]) + [(9, r) for r in range(1, 8)],
        "cracked": [], "mover": None,
    },
    {
        # NEW: only two walls move. The safe region is a full-height band, so the centre
        # is not special -- and here it is a solid block. The corridor that points at it
        # is a dead end; the open lane below it is the way in.
        "name": "Vise",
        "sides": "LR", "phases": [9], "pause": 0,
        "start": (2, 10),
        "pillars": _block() + [(x, 9) for x in range(2, 9)] + [(x, 11) for x in range(3, 9)],
        "cracked": [], "mover": None,
    },
    {
        # NEW: a cracked pillar. The final room is fully pillared; one pillar is cracked
        # and gives way as the wall face arrives one cell from it. Push against it, it
        # holds, the wall reaches your back, it crumbles, step in.
        # The start is offset by one column from the crack ON PURPOSE: straight above it,
        # the whole level is cleared by pressing DOWN nine times, and a level a one-key
        # policy clears measures nothing. Offset, the lane ends against a solid pillar and
        # the sidestep onto the crack has to be chosen.
        "name": "Crack",
        "sides": "TBLR", "phases": [9], "pause": 0,
        "start": (10, 1),
        "pillars": _block(skip=[(9, 9)]), "cracked": [(9, 9)], "mover": None,
    },
    {
        # NEW: two phases. The press halts on the solid line, holds, then closes again to
        # the dashed one. The hold is when you walk round the block to its open corner.
        "name": "Twice",
        "sides": "TBLR", "phases": [6, 9], "pause": 5,
        "start": (10, 2),
        "pillars": _block(skip=[(11, 11)]) + [(c, r) for r in range(2, 6) for c in (9, 11)],
        "cracked": [], "mover": None,
    },
    {
        # NEW: a piston. It shuttles along the row in front of the final room and presses
        # whatever it moves onto; its yellow nose shows where it goes next. Straight down
        # walks into it. Sidestep through the gap on the side it is leaving.
        "name": "Sweep",
        "sides": "TBLR", "phases": [9], "pause": 0,
        "start": (10, 1),
        "pillars": _block(skip=[(10, 9), (11, 9)]) + [(c, r) for r in range(1, 7) for c in (9, 11)],
        "cracked": [],
        "mover": {"track": [(9, 8), (10, 8), (11, 8), (12, 8)], "at": 1, "dir": -1},
    },
    {
        # Everything at once: two phases, a piston sweeping the row you would wait on, and
        # a cracked corner that only opens on the final action. Wait beside it, off the
        # track, pushing against it.
        "name": "Gauntlet",
        "sides": "TBLR", "phases": [6, 9], "pause": 5,
        "start": (10, 1),
        "pillars": _block(skip=[(9, 9)]) + [(c, r) for r in range(1, 6) for c in (9, 11)],
        "cracked": [(9, 9)],
        "mover": {"track": [(8, 8), (9, 8), (10, 8), (11, 8)], "at": 0, "dir": 1},
    },
]


# ---------------------------------------------------------------------------
# Pure rules
# ---------------------------------------------------------------------------

State = namedtuple("State", "pos front phase hold midx mdir crumbled alive done")


class Lvl:
    """A level's constants, precomputed once."""

    def __init__(self, ldef):
        self.name = ldef["name"]
        self.sides = ldef["sides"]
        self.halts = list(ldef["phases"])
        self.pause = ldef["pause"]
        self.start = tuple(ldef["start"])
        self.pillars = frozenset(map(tuple, ldef["pillars"]))
        self.cracked = frozenset(map(tuple, ldef["cracked"]))
        m = ldef["mover"]
        self.track = [tuple(c) for c in m["track"]] if m else []
        self.m_at = m["at"] if m else 0
        self.m_dir = m["dir"] if m else 1
        ys, xs = np.mgrid[0:W, 0:W]
        parts = [np.full((W, W), W)]
        if "L" in self.sides:
            parts.append(xs)
        if "R" in self.sides:
            parts.append(W - 1 - xs)
        if "T" in self.sides:
            parts.append(ys)
        if "B" in self.sides:
            parts.append(W - 1 - ys)
        self.D = np.min(np.stack(parts), axis=0)
        self.dist = {(x, y): int(self.D[y, x]) for y in range(W) for x in range(W)}
        self.total = self.halts[-1] + self.pause * (len(self.halts) - 1)


def initial(lvl):
    return State(lvl.start, 0, 0, 0, lvl.m_at, lvl.m_dir, frozenset(), True, False)


def mover_next(lvl, st):
    """Index and direction of the piston after its next step (bounces at track ends)."""
    if not lvl.track:
        return st.midx, st.mdir
    ni, d = st.midx + st.mdir, st.mdir
    if not 0 <= ni < len(lvl.track):
        d = -d
        ni = st.midx + d
    return ni, d


def blocked(lvl, st, cell):
    x, y = cell
    if not (0 <= x < W and 0 <= y < W):
        return True
    if lvl.dist[cell] < st.front or cell in lvl.pillars:
        return True
    if cell in lvl.cracked and cell not in st.crumbled:
        return True
    return bool(lvl.track) and lvl.track[st.midx] == cell


def transition(lvl, st, aid):
    """One action. Order: the player steps, the piston steps, the press advances (or
    holds), cracked pillars one cell from the face give way, the halt is checked."""
    if st.done or not st.alive:
        return st
    pos = st.pos
    if aid in DIR_OF_ACTION:
        dx, dy = DIR_OF_ACTION[aid]
        nxt = (pos[0] + dx, pos[1] + dy)
        if not blocked(lvl, st, nxt):
            pos = nxt
    alive = True
    midx, mdir = st.midx, st.mdir
    if lvl.track:
        midx, mdir = mover_next(lvl, st)
        if lvl.track[midx] == pos:
            alive = False
    front, phase, hold, done = st.front, st.phase, st.hold, False
    if hold > 0:
        hold -= 1
    else:
        front += 1
        if front == lvl.halts[phase]:
            if phase == len(lvl.halts) - 1:
                done = True
            else:
                phase += 1
                hold = lvl.pause
    if lvl.dist[pos] < front:
        alive = False
    crumbled = st.crumbled | {c for c in lvl.cracked if lvl.dist[c] == front + 1}
    return State(pos, front, phase, hold, midx, mdir, crumbled, alive, done)


# ---------------------------------------------------------------------------
# Display -- everything is recomputed from the state every frame
# ---------------------------------------------------------------------------

class Pr01Display(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    @staticmethod
    def _px(cell):
        return OX + cell[0] * CELL, OY + cell[1] * CELL

    def _halt_line(self, frame, lvl, t, solid):
        left = t if "L" in lvl.sides else 0
        right = W - t if "R" in lvl.sides else W
        top = t if "T" in lvl.sides else 0
        bottom = W - t if "B" in lvl.sides else W
        x0, x1 = OX + left * CELL, OX + right * CELL - 1
        y0, y1 = OY + top * CELL, OY + bottom * CELL - 1
        step = 1 if solid else 2
        if "T" in lvl.sides:
            frame[y0, x0:x1 + 1:step] = C_HALT
        if "B" in lvl.sides:
            frame[y1, x0:x1 + 1:step] = C_HALT
        if "L" in lvl.sides:
            frame[y0:y1 + 1:step, x0] = C_HALT
        if "R" in lvl.sides:
            frame[y0:y1 + 1:step, x1] = C_HALT

    def _face(self, frame, lvl, f):
        if f <= 0:
            return
        span = slice(OX, OX + W * CELL)
        if "T" in lvl.sides:
            frame[OY + f * CELL - 1, span] = C_FACE
        if "B" in lvl.sides:
            frame[OY + (W - f) * CELL, span] = C_FACE
        if "L" in lvl.sides:
            frame[span, OX + f * CELL - 1] = C_FACE
        if "R" in lvl.sides:
            frame[span, OX + (W - f) * CELL] = C_FACE

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game
        lvl, st = g.lvl, g.st
        frame[:, :] = C_FLOOR

        wall = lvl.D < st.front
        cells = np.full((W, W), C_FLOOR, dtype=frame.dtype)
        cells[wall] = C_WALL
        body = frame[OY:OY + W * CELL, OX:OX + W * CELL]
        body[:, :] = np.repeat(np.repeat(cells, CELL, 0), CELL, 1)
        body[2::CELL, 2::CELL][wall] = C_BRICK          # brick texture: a mass, not a ring

        for cell in lvl.track:
            if not wall[cell[1], cell[0]]:
                px, py = self._px(cell)
                frame[py + 1, px + 1] = C_MOVER

        standing = [c for c in lvl.pillars | lvl.cracked
                    if not wall[c[1], c[0]] and c not in st.crumbled]
        for cell in standing:
            px, py = self._px(cell)
            frame[py:py + CELL, px:px + CELL] = C_PILLAR
            frame[py + 1, px + 1] = C_FLOOR                 # hollow centre

        # After the pillars, never before: on the levels whose final room IS the pillar block,
        # the halt line runs exactly along that block's outer edge, and drawing it first left
        # it completely hidden -- the player could not see where the press was going to stop.
        for k in range(st.phase, len(lvl.halts)):
            self._halt_line(frame, lvl, lvl.halts[k], solid=(k == st.phase))

        # ...and the seam goes on last of the three, because the halt line runs straight over
        # the corner it is cut into. A cracked pillar has to stay distinguishable from a solid
        # one at a glance; it is the only thing that will open.
        for cell in standing:
            if cell in lvl.cracked:
                px, py = self._px(cell)
                frame[py, px] = C_FLOOR                     # the seam runs corner to corner
                frame[py + 2, px + 2] = C_FLOOR

        if lvl.track:
            cell = lvl.track[st.midx]
            px, py = self._px(cell)
            frame[py:py + CELL, px:px + CELL] = C_MOVER
            ni, _ = mover_next(lvl, st)
            nx, ny = lvl.track[ni]
            if nx > cell[0]:
                frame[py:py + CELL, px + 2] = C_FACE
            elif nx < cell[0]:
                frame[py:py + CELL, px] = C_FACE
            elif ny > cell[1]:
                frame[py + 2, px:px + CELL] = C_FACE
            else:
                frame[py, px:px + CELL] = C_FACE

        self._face(frame, lvl, st.front)

        px, py = self._px(st.pos)
        if st.alive:
            frame[py:py + CELL, px:px + CELL] = C_PLAYER
        else:
            frame[py + 1, px:px + CELL] = C_PLAYER          # pressed flat
        return frame


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

LVLS = [Lvl(d) for d in LEVELS]


class Pr01(ARCBaseGame):
    def __init__(self):
        self.display = Pr01Display(self)
        # on_set_level() runs inside super().__init__(); these must exist first.
        self.lvl = LVLS[0]
        self.st = initial(self.lvl)
        levels = [Level(sprites=[], grid_size=(64, 64), data=d, name=d["name"])
                  for d in LEVELS]
        super().__init__(
            "pr",
            levels,
            Camera(0, 0, 64, 64, C_FLOOR, C_FLOOR, [self.display]),
            False,
            len(levels),
            [1, 2, 3, 4],
        )

    def on_set_level(self, level: Level) -> None:
        self.lvl = LVLS[self.level_index]
        self.st = initial(self.lvl)

    def handle_reset(self) -> None:
        """The base class promotes a RESET to a full restart whenever `_action_count == 0`,
        and `_action_count` is zeroed by every level load -- so a RESET taken as the first
        action of a level would throw the player back to level 1. Full restart only from
        NOT_PLAYED and WIN; anywhere else a RESET retries the level that is open."""
        if self._state in (GameState.NOT_PLAYED, GameState.WIN):
            self.full_reset()
        else:
            self.level_reset()

    def step(self) -> None:
        aid = self.action.id.value
        if aid == 0:
            # handle_reset() has already rebuilt the level; nothing to charge.
            self.complete_action()
            return
        # Any other action -- including the unadvertised 5/6/7 -- is a step that does not
        # move. The press advances regardless: standing still is never free.
        self.st = transition(self.lvl, self.st, aid)
        if not self.st.alive:
            self.lose()
        elif self.st.done:
            self.next_level()
        self.complete_action()

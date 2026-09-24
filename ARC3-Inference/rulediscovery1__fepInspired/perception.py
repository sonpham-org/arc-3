# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Perception layer of the rule discovery prototype (OpenMind, #arc-3, 23-Sep-2026 21:03 ET):
#   frame -> objects -> per-step events, plus the "imagination" operation the planner needs.
#     - Action: one engine action (ACTION1..7, RESET; ACTION6 carries row/col), and the trace-row dict
#       the distill/ code reads (action_name, action_display "row=r, col=c", level/game flags).
#     - Scene: one HUD-masked board as components (object_events.board_comps: 4-connected same-colour
#       components with colour, shape CRC, bbox, background flag), with object queries, a hashable
#       signature for search, an oe.Step "probe" for hypothetical actions (so agency / detector code
#       can score an action that was not taken), and apply(effects) -> the imagined next Scene.
#     - Effect / label_of / label_parts: structured predicted changes (move, recolour, vanish, appear,
#       resize, label-only tick) and their canonical outcome label in the exact object_events format
#       ("mv+1+0", "rc3>5", "grow|mv+1+0x2", ...), so predictions and observations share one alphabet.
#     - HudMasker: online HUD-line mask from the boards seen so far (efe_trace_analysis.hud_mask on a
#       bounded window, recomputed every few steps), or a fixed mask for offline replay.
#     - ObjectTracker: persistent object ids across frames (same greedy order as object_events).
#     - Transition + Perceiver: step -> event set. Labels come from object_events.match_events /
#       canonical, identical to the yardstick. The Perceiver ALWAYS advances pre = post after every
#       step (the stale-board bug of efe_trace_analysis.analyse, found in round four, is the reason
#       this is an invariant with its own test), and builds an oe.Step per transition so
#       agency_contexts / feature_detectors can be reused unchanged.
#   Integration: rules.py reads Scene/Effect; beliefs.py, agent.py and offline_eval.py consume
#   Transition; offline_eval builds Transitions from oe.Trace (object_events.load already advances the
#   board correctly). Not run yet: only py_compile was used.
# SRP/DRY check: Pass -- components, event matching, canonical labels, HUD masking and the Step record
#   are imported from distill/ (object_events, efe_trace_analysis) via _distill. New here: live-frame
#   path, cross-frame ids, and Scene.apply (nothing in distill/ imagines a board).
"""Frames -> objects -> events; imagined scenes for planning."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

import numpy as np

from ._distill import efe, oe

BUTTONS: tuple[str, ...] = ("ACTION1", "ACTION2", "ACTION3", "ACTION4", "ACTION5", "ACTION7")
CLICK = "ACTION6"
RESET = "RESET"
TERMINAL_LABELS = ("level_clear", "game_over")
NO_PART_LABELS = ("nothing", "reset", "level_clear", "game_over", oe.NOVEL)
_MULT_RE = re.compile(r"^(.*)x(2|3\+)$")


# ---------------------------------------------------------------- actions

@dataclass(frozen=True)
class Action:
    """One engine action. Clicks (ACTION6) carry the board cell as row/col (never legacy x/y)."""
    name: str
    row: Optional[int] = None
    col: Optional[int] = None

    @property
    def is_click(self) -> bool:
        return self.name == CLICK

    @property
    def is_button(self) -> bool:
        return self.name in BUTTONS

    def display(self) -> str:
        """The action_display text the distill/ code parses with efe.MOUSE_RE."""
        if self.is_click:
            return f"MOUSE row={self.row}, col={self.col}"
        return self.name

    def row_dict(self, level_completed: bool = False, game_over: bool = False) -> dict:
        """A trace-row-shaped dict (what object_events.Step.row holds)."""
        return {"action_name": self.name, "action_display": self.display(),
                "level_completed": bool(level_completed), "game_over": bool(game_over)}

    def key(self) -> tuple:
        return (self.name, self.row, self.col) if self.is_click else (self.name,)


# ---------------------------------------------------------------- effects and labels

@dataclass(frozen=True)
class Effect:
    """A predicted change. comp_id refers to a component of the Scene the prediction was made on.
    kind: move | recolour | vanish | appear | grow | shrink | reshape | tick (label only)."""
    kind: str
    comp_id: Optional[int] = None
    dx: int = 0
    dy: int = 0
    to_colour: Optional[int] = None
    from_colour: Optional[int] = None
    part: Optional[str] = None          # explicit label part (tick / appear / resize)

    def label_part(self) -> str:
        if self.kind == "move":
            return f"mv{oe._clip(self.dx):+d}{oe._clip(self.dy):+d}"
        if self.kind == "recolour":
            return f"rc{self.from_colour}>{self.to_colour}"
        if self.kind == "vanish":
            return "van"
        if self.kind == "appear":
            return "app"
        if self.kind in ("grow", "shrink", "reshape"):
            return self.kind
        return self.part or "tick"


def label_of(effects: Sequence[Effect]) -> str:
    """Canonical object-event label of a predicted effect list ("nothing" when empty)."""
    parts = [e.label_part() for e in effects]
    return oe.canonical(parts) if parts else "nothing"


def label_parts(label: Optional[str]) -> list[str]:
    """Inverse of object_events.canonical: 'grow|mv+1+0x2' -> ['grow', 'mv+1+0', 'mv+1+0'].
    Multiplicity '3+' expands to three. Labels without parts (nothing, clears, reset) -> []."""
    if not label or label in NO_PART_LABELS:
        return []
    out: list[str] = []
    for tok in label.split("|"):
        m = _MULT_RE.match(tok)
        if m:
            out += [m.group(1)] * (3 if m.group(2) == "3+" else 2)
        else:
            out.append(tok)
    return out


def parts_to_effects(parts: Iterable[str]) -> list[Effect]:
    """Label-only effects (used by rules that predict a label without a scene operation)."""
    return [Effect("tick", part=p) for p in parts]


# ---------------------------------------------------------------- scenes

class Scene:
    """One HUD-masked board as components. raw keeps the harness grid (lists of ints) for the
    distill/ functions that read it directly (efe.context_of, component_cells)."""

    def __init__(self, raw: list[list[int]], mask: Optional[np.ndarray], level: int = 0,
                 comps: Optional["oe.BoardComps"] = None):
        self.raw = raw
        self.mask = mask
        self.level = level
        self.comps = comps if comps is not None else oe.board_comps(raw, mask)
        self.track_ids: dict[int, int] = {}      # comp id -> persistent track id (ObjectTracker)

    @classmethod
    def from_grid(cls, grid, mask: Optional[np.ndarray], level: int = 0) -> "Scene":
        raw = [[int(v) for v in row] for row in grid]
        return cls(raw, mask, level)

    # -- queries
    @property
    def shape(self) -> tuple[int, int]:
        return self.comps.arr.shape

    @property
    def mode(self) -> int:
        return self.comps.mode

    def objects(self) -> list:
        """Non-background components that are not the dominant (floor) colour."""
        return [c for c in self.comps.comps if not c.bg and c.colour != self.comps.mode]

    def by_type(self) -> dict:
        return self.comps.by_type()

    def comp_at(self, row: int, col: int):
        h, w = self.shape
        if not (0 <= row < h and 0 <= col < w):
            return None
        cid = int(self.comps.lab[row, col])
        return self.comps.comps[cid - 1] if cid else None

    def cells(self, comp) -> tuple[np.ndarray, np.ndarray]:
        ys, xs = np.nonzero(self.comps.lab[comp.y0:comp.y1 + 1, comp.x0:comp.x1 + 1] == comp.id)
        return ys + comp.y0, xs + comp.x0

    def colour_cells(self, colour: int) -> int:
        return int((self.comps.arr == colour).sum())

    def colour_objects(self, colour: int) -> list:
        return [c for c in self.objects() if c.colour == colour]

    def colours(self) -> list[int]:
        return sorted({c.colour for c in self.objects()})

    def signature(self) -> tuple:
        """Hashable description for search (visited sets): every object's colour, shape, position."""
        return tuple(sorted((c.colour, c.shape, c.y0, c.x0) for c in self.objects()))

    def click_point(self, comp) -> tuple[int, int]:
        """A cell of comp nearest its bbox centre (a click that surely lands on the object)."""
        ys, xs = self.cells(comp)
        cy, cx = (comp.y0 + comp.y1) / 2.0, (comp.x0 + comp.x1) / 2.0
        i = int(np.argmin((ys - cy) ** 2 + (xs - cx) ** 2))
        return int(ys[i]), int(xs[i])

    def probe_step(self, action: Action) -> "oe.Step":
        """An object_events.Step for an action NOT (yet) taken on this board: lets agency_contexts /
        feature_detectors compute contexts for candidate actions exactly as for real ones."""
        return oe.Step(-1, action.row_dict(), self.raw, None, action.name == RESET, "", [], self.comps, None)

    # -- imagination
    def apply(self, effects: Sequence[Effect]) -> "Scene":
        """The imagined next scene. Moves are applied simultaneously (all movers are lifted first),
        recolours and vanishes in place; label-only effects (ticks, appear, resize) change nothing.
        HUD cells keep this scene's raw values."""
        arr = self.comps.arr.copy()
        floor = self.comps.mode
        lifted = []
        for e in effects:
            if e.comp_id is None:
                continue
            comp = self.comps.comps[e.comp_id - 1]
            ys, xs = self.cells(comp)
            if e.kind == "move":
                arr[ys, xs] = floor
                lifted.append((ys + e.dy, xs + e.dx, comp.colour))
            elif e.kind == "recolour" and e.to_colour is not None:
                arr[ys, xs] = e.to_colour
            elif e.kind == "vanish":
                arr[ys, xs] = floor
        h, w = arr.shape
        for ys, xs, colour in lifted:
            ok = (ys >= 0) & (ys < h) & (xs >= 0) & (xs < w)
            arr[ys[ok], xs[ok]] = colour
        raw_arr = np.asarray(self.raw, dtype=np.int16)
        keep = arr != oe.MASKED
        raw_arr[keep] = arr[keep]
        # board_comps skips MASKED cells, so the masked array itself is a valid input (no mask needed)
        return Scene(raw_arr.tolist(), self.mask, self.level, oe.board_comps(arr, None))


# ---------------------------------------------------------------- HUD mask

class HudMasker:
    """HUD lines from the boards seen so far (efe.hud_mask on the last `window` boards, recomputed
    every `every` observations). A fixed mask (offline replay) disables the online estimate."""

    def __init__(self, every: int = 8, window: int = 64, fixed: Optional[np.ndarray] = None):
        self.every, self.window = every, window
        self.fixed = fixed
        self.boards: list[list[list[int]]] = []
        self.mask: Optional[np.ndarray] = fixed
        self.version = 0
        self._since = 0

    def reset(self) -> None:
        if self.fixed is None:
            self.boards, self.mask, self._since = [], None, 0
            self.version += 1

    def observe(self, raw: list[list[int]]) -> Optional[np.ndarray]:
        if self.fixed is not None:
            return self.fixed
        self.boards.append(raw)
        if len(self.boards) > self.window:
            self.boards = self.boards[-self.window:]
        self._since += 1
        if self._since >= self.every and len(self.boards) >= 3:
            self._since = 0
            cells = efe.hud_mask(self.boards)
            new = mask_array(cells, len(raw), len(raw[0])) if cells else None
            if not _same_mask(new, self.mask):
                self.mask = new
                self.version += 1
        return self.mask


def mask_array(cells: set, h: int, w: int) -> np.ndarray:
    m = np.zeros((h, w), dtype=bool)
    for y, x in cells:
        m[y, x] = True
    return m


def _same_mask(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return a.shape == b.shape and bool((a == b).all())


# ---------------------------------------------------------------- object identity

class ObjectTracker:
    """Persistent ids across frames. Matching order follows object_events.match_events: unchanged
    (colour, shape, position) -> moved (same colour+shape, greedy nearest) -> recoloured in place
    (same shape+position) -> resized (same colour, overlapping boxes) -> new id."""

    def __init__(self):
        self.next_id = 1

    def reset(self) -> None:
        self.next_id = 1

    def _new(self) -> int:
        self.next_id += 1
        return self.next_id - 1

    def start(self, scene: Scene) -> None:
        scene.track_ids = {c.id: self._new() for c in scene.objects()}

    def track(self, pre: Scene, post: Scene) -> None:
        A = [c for c in pre.objects() if c.id in pre.track_ids]
        B = post.objects()
        used_a: set[int] = set()
        ids: dict[int, int] = {}

        def take(a, b):
            used_a.add(a.id)
            ids[b.id] = pre.track_ids[a.id]

        pos = {(a.colour, a.shape, a.y0, a.x0): a for a in A}
        for b in B:
            a = pos.get((b.colour, b.shape, b.y0, b.x0))
            if a is not None and a.id not in used_a:
                take(a, b)
        rest_b = [b for b in B if b.id not in ids]
        pairs = []
        for b in rest_b:
            for a in A:
                if a.id not in used_a and a.type_key == b.type_key:
                    pairs.append((abs(b.y0 - a.y0) + abs(b.x0 - a.x0), a.id, b.id, a, b))
        for _, _, _, a, b in sorted(pairs, key=lambda t: t[:3]):
            if a.id not in used_a and b.id not in ids:
                take(a, b)
        for b in [b for b in B if b.id not in ids]:
            for a in A:
                if a.id not in used_a and a.shape == b.shape and (a.y0, a.x0) == (b.y0, b.x0):
                    take(a, b)
                    break
        for b in [b for b in B if b.id not in ids]:
            for a in A:
                if a.id not in used_a and a.colour == b.colour and oe._overlap(a, b):
                    take(a, b)
                    break
        for b in B:
            if b.id not in ids:
                ids[b.id] = self._new()
        post.track_ids = ids


# ---------------------------------------------------------------- transitions

@dataclass
class Transition:
    """One observed step. label uses the object_events alphabet; step is the oe.Step for reuse."""
    index: int
    action: Action
    pre: Scene
    post: Optional[Scene]
    label: str
    events: Optional[list]
    moves: list
    level: int
    level_completed: bool
    game_over: bool
    reset: bool
    step: "oe.Step" = field(repr=False, default=None)

    @property
    def terminal(self) -> bool:
        return self.label in TERMINAL_LABELS

    @property
    def scored(self) -> bool:
        """Steps the rule sets are scored on: not a RESET, not a clear / game over."""
        return not self.reset and not self.terminal

    def parts(self) -> list[str]:
        return label_parts(self.label)


class Perceiver:
    """Stateful per play. begin(first grid) then observe(action, next grid, flags) per step.
    Invariant: after every observe, `current` is the board the NEXT action will be taken on."""

    def __init__(self, hud_every: int = 8, hud_window: int = 64, fixed_mask: Optional[np.ndarray] = None):
        self.hud = HudMasker(hud_every, hud_window, fixed_mask)
        self.tracker = ObjectTracker()
        self.current: Optional[Scene] = None
        self.level = 0
        self.index = 0
        self._mask_version = -1

    def begin(self, grid, level: int = 0) -> Scene:
        raw = [[int(v) for v in row] for row in grid]
        self.level = level
        self.index = 0
        self.hud.reset()
        mask = self.hud.observe(raw)
        self.current = Scene(raw, mask, level)
        self._mask_version = self.hud.version
        self.tracker.reset()
        self.tracker.start(self.current)
        return self.current

    def observe(self, action: Action, grid, level_completed: bool = False, game_over: bool = False,
                level: Optional[int] = None) -> Transition:
        if self.current is None:
            raise RuntimeError("Perceiver.begin() must be called with the first frame")
        raw = [[int(v) for v in row] for row in grid]
        mask = self.hud.observe(raw)
        pre = self.current
        if self.hud.version != self._mask_version:
            # the HUD estimate changed: re-describe the pre board under the same mask as the post
            # board (component ids shift, so object identity restarts here; rare, documented gap)
            pre = Scene(pre.raw, mask, pre.level)
            self.tracker.start(pre)
            self._mask_version = self.hud.version
        post = Scene(raw, mask, self.level)
        is_reset = action.name == RESET
        events, moves = None, []
        if is_reset:
            label = "reset"
        elif level_completed:
            label = "level_clear"
        elif game_over:
            label = "game_over"
        else:
            events, moves = oe.match_events(pre.comps, post.comps)
            label = "nothing" if events is None else oe.canonical(events)
        row = action.row_dict(level_completed, game_over)
        step = oe.Step(self.index, row, pre.raw, post.raw, is_reset, label, moves, pre.comps, events)
        tr = Transition(self.index, action, pre, post, label, events, moves, self.level,
                        bool(level_completed), bool(game_over), is_reset, step)
        if level_completed or is_reset:
            self.level = self.level + 1 if level_completed else self.level
            if level is not None:
                self.level = level
            post.level = self.level
            self.tracker.reset()
            self.tracker.start(post)
        else:
            if level is not None:
                self.level = level
            self.tracker.track(pre, post)
        self.index += 1
        self.current = post                      # ALWAYS advance: pre of the next step = this post
        return tr

    # -- offline replay
    @staticmethod
    def transitions_from_trace(trace: "oe.Trace") -> list[Transition]:
        """Transitions for a saved play. Labels, moves and pre components are object_events.load's
        own (identical to the yardstick; load advances the board after every step). The post Scene
        is rebuilt under the same trace-wide HUD mask load used."""
        boards = [s.pre for s in trace.steps[:1]] + [s.post for s in trace.steps]
        cells = efe.hud_mask(boards)
        first = next((b for b in boards if b), None)
        mask = mask_array(cells, len(first), len(first[0])) if (cells and first) else None
        out: list[Transition] = []
        level = 0
        for s in trace.steps:
            name = s.row.get("action_name") or ""
            action = _action_from_row(s.row, name)
            pre = Scene([list(r) for r in s.pre], mask, level, s.pa) if s.pre else None
            post = Scene([list(r) for r in s.post], mask, level) if s.post else None
            if pre is None:
                continue
            lc, go = s.label == "level_clear", s.label == "game_over"
            out.append(Transition(s.i, action, pre, post, s.label, s.events, s.moves, level, lc, go, s.reset, s))
            if lc:
                level += 1
                if post is not None:
                    post.level = level
        return out


def _action_from_row(row: dict, name: str) -> Action:
    if name == CLICK:
        m = efe.MOUSE_RE.search(row.get("action_display", ""))
        if m:
            return Action(CLICK, int(m.group(1)), int(m.group(2)))
        return Action(CLICK, -1, -1)
    return Action(name)


def label_counter(labels: Iterable[str]) -> Counter:
    """Part frequencies over labels (used by fitting and summaries)."""
    c: Counter = Counter()
    for lab in labels:
        c.update(label_parts(lab))
    return c

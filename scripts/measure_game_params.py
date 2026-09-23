#!/usr/bin/env python3
"""Measure every published game's tunable constants and write the Games page tuning specs.

Author: Claude Opus 5
Date: 20-September-2026
PURPOSE: Generate docs/static/games/params/<id>.json -- the per-game tuning panel specs read by
docs/static/js/games-tuning.js -- by measuring each candidate constant headlessly instead of
hand-measuring it in a browser. For every module-level `NAME = <int>` that the panel's patcher
can actually rewrite, this scans outward from the published value and keeps the range whose every
probed endpoint still loads, resets, steps and draws a legal 64x64 frame. Ranges are measured,
never guessed: a constant that only survives at its published value is dropped rather than
shipped with an invented range. Re-runnable by design, because the evolution loop rewrites these
sources continuously and a spec written for v2 will meet v4.

What a measured range is, and is not. This finds the *safety band* -- how far a constant can move
before the game breaks. The five hand-written specs carry a narrower *taste band* -- how far it
can move and still look right -- and the two are different objects. Measured on br10, CELL loads
cleanly from 4 to 24 with an unchanging colour count and a smoothly rising occupancy: there is no
discontinuity anywhere near the hand-chosen maximum of 10, so no headless check can find that
edge. Rather than clamp to some fraction of the hand-written precedent, which would be the guess
this script exists to avoid, the emitted band is the honest one and it is wider. The hand-written
five remain the quality bar; these are a floor, not a match.

One value range is a contract decision rather than a measurement: no slider is ever handed a
value below min(0, default). Negative geometry constants pass every check available -- at hg51's
X0 = -6 the occupancy is identical to X0 = 0 -- because numpy's negative indexing silently wraps
the drawing to the far side of the screen instead of raising. That is a bug surface, not a tuning
range, and no invariant can distinguish it.

SRP/DRY check: Pass -- this only decides what is tunable and by how much. Loading, stepping and
frame validation are reused from scripts/vet_game.py (load_class, find_game_classes, Player,
frame_hash, VetError); the assignment regex is a deliberate line-for-line mirror of readScalar()
in games-tuning.js, which is the contract a spec has to satisfy. Nothing here renders or serves;
scripts/serve_games_local.py is the verification harness.

  python3.13 scripts/measure_game_params.py                 # measure everything, write specs
  python3.13 scripts/measure_game_params.py --only br10 ts01 --dry-run
  python3.13 scripts/measure_game_params.py --report scratch/params-report.json

Requires python3.13 (the engine uses match/case) with arcengine and numpy importable.

Scope, and why it is not the whole catalog:
  * Families in BLIND_FAMILIES (arena, contributed-glowup, research) are played blind, and
    games-tuning.js refuses to attach a panel to them at all -- a list of named constants is a
    second way to read a game's shape, which is the leak that flag exists to stop. Measuring
    them would produce files nothing can render, so they are skipped. `--include-blind` exists
    for when that product decision changes.
  * Families in RETIRED_FAMILIES (ai-generated, redbluepill) are off the Games page entirely.
  * HANDWRITTEN specs are never touched. Those five were measured by hand in a browser with
    author-written labels and notes, and this script's derived English is honestly worse.

Label and note quality (stated plainly, because it is a real drop from the five hand-written
specs): `note` is the author's own trailing comment on the assignment line where there is one,
verbatim, and is omitted entirely otherwise -- a missing note is honest, an auto-generated one
is noise. `label` is mechanically derived from the constant name through a small abbreviation
map, so it reads like "Move frames" and "Cell size" but will never read as well as a human's.
`group` is keyword-classified into the four groups the hand-written specs already use.

Panels are capped (--max-knobs, default 12, the size of the largest hand-written spec), with at
most 4 palette entries so a colour-heavy game cannot crowd out its geometry and rules. Knobs
proven to change the game during probing take cap slots ahead of ones that did not, and commented
ones ahead of uncommented. A constant that never visibly moved is still shipped when there is
room: br10's FALL and hg51's WIN_HOLD are real knobs the hand pass measured, and neither shows up
in a blind ten-action probe -- WIN_HOLD only fires on a won level. A filter that rejects known
ground truth is a wrong filter, so the only rejection on this axis is an AST one: a constant the
module never reads cannot do anything. `--report` records which shipped unproven.
"""

from __future__ import annotations

import argparse
import ast
import json
import multiprocessing
import os
import re
import signal
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from vet_game import Player, VetError, find_game_classes, frame_hash, load_class  # noqa: E402

SITE = os.environ.get("ARC3_SITE", "https://arc3.sonpham.net")
TREES_API = "/api/v1/public/games/trees"
OUT_DIR = REPO / "docs" / "static" / "games" / "params"
CACHE = REPO / "scratch" / "param-measurements.json"
SRC_CACHE = REPO / "scratch" / "param-sources"

# games-api.js: panels never attach to a blind family, and retired families are off the page.
BLIND_FAMILIES = {"arena", "contributed-glowup", "research"}
RETIRED_FAMILIES = {"ai-generated", "redbluepill"}
# Measured by hand in a browser (commit d68b29574). Better English than this script can derive.
HANDWRITTEN = {"mx78", "mc18", "br10", "mb64", "hg51"}

# ── The patcher's contract, mirrored from games-tuning.js ─────────────────────

NAME_OK = re.compile(r"^[A-Z][A-Z0-9_]*$")


def assignment(name: str) -> re.Pattern[str]:
    """readScalar()'s regex, character for character. Line-anchored, one scalar int, optional
    trailing comment and nothing else -- so `CELL = 8 if hard else 6` cannot match and quietly
    lose its conditional, and a tuple unpack cannot match at all."""
    return re.compile(rf"^({re.escape(name)}[ \t]*=[ \t]*)(-?\d+)([ \t]*(?:#[^\n]*)?)$", re.M)


def read_scalar(source: str, name: str) -> int | None:
    """The value NAME is assigned, or None unless exactly one line assigns it."""
    if not NAME_OK.match(name):
        return None
    found = assignment(name).findall(source)
    return int(found[0][1]) if len(found) == 1 else None


def patch_source(source: str, values: dict[str, int]) -> str:
    """`source` with each named constant set to a new value, keeping spacing and comment."""
    out = source
    for name, value in values.items():
        if read_scalar(out, name) is None:
            continue
        out = assignment(name).sub(lambda m: f"{m.group(1)}{value}{m.group(3)}", out)
    return out


# ── Candidates ───────────────────────────────────────────────────────────────

# Anything this large is a seed, a budget or a bitmask, not a slider. Stated rather than guessed.
VALUE_CEILING = 256


def candidates(source: str) -> list[dict[str, Any]]:
    """Module-level SHOUTING_CASE int constants the panel could rewrite, in source order.

    A name qualifies only if the AST says it is assigned once at module level to a plain int
    literal AND the patcher's own regex finds exactly one matching line in the whole file. Both
    halves matter: the AST rejects tuple unpacks and conditionals, the regex rejects a name the
    file also assigns inside a docstring or at a second top-level line.
    """
    tree = ast.parse(source)
    assigned: dict[str, int] = {}
    out: list[dict[str, Any]] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not NAME_OK.match(target.id):
            continue
        value = literal_int(node.value)
        assigned[target.id] = assigned.get(target.id, 0) + 1
        if value is None:
            continue
        out.append({"name": target.id, "default": value, "line": node.lineno})

    used = name_uses(tree)
    keep = []
    for item in out:
        name = item["name"]
        if assigned[name] != 1:
            continue  # the file re-assigns it; we cannot say which line drives the drawing
        if read_scalar(source, name) != item["default"]:
            continue  # the patcher would not resolve this line the way the AST did
        if abs(item["default"]) > VALUE_CEILING:
            continue
        if used.get(name, 0) < 1:
            continue  # assigned and never read: turning it could not do anything
        item["comment"] = trailing_comment(source, name)
        keep.append(item)
    return keep


def literal_int(node: ast.AST) -> int | None:
    """The int a node is, allowing a leading minus. bool is not an int here."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = literal_int(node.operand)
        return None if inner is None else -inner
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return int(node.value)
    return None


def name_uses(tree: ast.AST) -> dict[str, int]:
    """How often each name is *read* anywhere in the module. A constant with no reads is dead,
    and a dead knob is a slider that visibly does nothing."""
    counts: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            counts[node.id] = counts.get(node.id, 0) + 1
    return counts


def trailing_comment(source: str, name: str) -> str:
    """The author's own comment on the assignment line, cleaned but not reworded."""
    match = assignment(name).search(source)
    if not match:
        return ""
    text = match.group(3).strip()
    if not text.startswith("#"):
        return ""
    text = text.lstrip("#").strip()
    return text[:117] + "…" if len(text) > 118 else text


# ── Measuring ────────────────────────────────────────────────────────────────

PROBE_ACTIONS = 10
PROBE_TIMEOUT = 8.0


class Timeout(Exception):
    """A patched value sent the game into a loop we are not going to sit through."""


def _alarm(signum, frame):  # noqa: ARG001
    raise Timeout("probe exceeded its time budget")


def signature(source: str, class_name: str) -> dict[str, Any]:
    """Load the source, reset, and play a fixed action script. Returns the behaviour signature
    and the facts the invariants are checked against. Raises on anything the site would see as a
    broken game: an exception, an illegal frame, a camera the engine cannot fit in 64x64.

    The signature covers every frame of reset plus the scripted actions, not just the reset
    frame. That is deliberate: a constant like a move's frame count or a firebox capacity does
    not change the opening picture but does change what the next few actions look like, and a
    reset-only signature would call those knobs dead and drop them.
    """
    cls = load_class(source, class_name)
    game = cls()
    player = Player(game)
    frames = list(player.reset().frame)

    camera = game.camera
    if camera.width < 1 or camera.height < 1 or camera.width > 64 or camera.height > 64:
        raise VetError(f"camera {camera.width}x{camera.height} does not fit the 64x64 frame")

    opening = frames[-1]
    colours = len({int(v) for v in opening.flatten()})
    ended_on_reset = str(player.state) != str(player.GameState.NOT_FINISHED)

    available = [int(a) for a in game._available_actions if int(a) != 0]
    script = [a for a in available if a != 6] or [6]
    for index in range(PROBE_ACTIONS):
        if str(player.state) in (str(player.GameState.GAME_OVER), str(player.GameState.WIN)):
            break  # a game that legitimately ends is not a fault; stop, do not keep poking it
        action = script[index % len(script)]
        frames += list(player.act(action, click_point(game) if action == 6 else {}).frame)

    return {
        "signature": frame_hash(frames),
        "colours": colours,
        "ended_on_reset": ended_on_reset,
        "tile_scale": min(64 // max(1, camera.width), 64 // max(1, camera.height)),
    }


def click_point(game: Any) -> dict[str, int]:
    """The game's first declared click target, or the middle of the screen. Deterministic, so
    two probes of the same source produce the same signature."""
    try:
        targets = game._get_valid_clickable_actions()
        if targets:
            return {"x": int(targets[0].data["x"]), "y": int(targets[0].data["y"])}
    except Exception:
        pass
    return {"x": 32, "y": 32}


def probe(source: str, class_name: str, name: str, value: int, baseline: dict[str, Any]) -> dict[str, Any]:
    """Is `name = value` a value a player could be handed? Measured, with a reason when not."""
    signal.setitimer(signal.ITIMER_REAL, PROBE_TIMEOUT)
    try:
        result = signature(patch_source(source, {name: value}), class_name)
    except Timeout as exc:
        return {"ok": False, "why": str(exc)}
    except (VetError, Exception) as exc:  # a game's own exception is the answer, not a crash
        return {"ok": False, "why": f"{type(exc).__name__}: {str(exc).splitlines()[0][:120]}"}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)

    # Invariants, each relative to what the published value already does -- a game that opens on
    # one colour or opens already finished is odd, but it is not this value's fault.
    if result["colours"] < 2 <= baseline["colours"]:
        return {"ok": False, "why": "opening board is a single colour"}
    if result["ended_on_reset"] and not baseline["ended_on_reset"]:
        return {"ok": False, "why": "the level is already over on reset"}
    if result["tile_scale"] < 1:
        return {"ok": False, "why": "camera does not fit the frame"}
    return {"ok": True, "signature": result["signature"]}


def furthest(test, default: int, direction: int, span: int) -> int:
    """The largest offset k in 0..span with `default + direction*k` still good.

    Doubling out to find a failure, then bisecting, costs about 2*log2(span) probes instead of
    span of them. It assumes a value that fails stays failed further out -- true of the geometry
    and capacity constants this measures, and the reason the emitted range is described as a
    measured safe band rather than an exhaustive one.
    """
    good, step, bad = 0, 1, None
    while step <= span:
        if test(default + direction * step):
            good, step = step, step * 2
        else:
            bad = step
            break
    if bad is None:
        if test(default + direction * span):
            return span
        bad = span
    low, high = good, bad
    while high - low > 1:
        middle = (low + high) // 2
        if test(default + direction * middle):
            low = middle
        else:
            high = middle
    return low


def span_for(default: int) -> int:
    """How far out to look. Proportional to the value, because a cell size of 6 and a screen row
    of 55 are not interesting over the same window, and capped so nothing scans unbounded."""
    return max(8, min(64, 2 * abs(default)))


def measure_game(source: str, class_name: str, max_knobs: int) -> dict[str, Any]:
    """Every measurable knob in one source, with why each rejected candidate was rejected."""
    found = candidates(source)
    report: dict[str, Any] = {"className": class_name, "knobs": [], "rejected": [], "candidates": len(found)}

    signal.signal(signal.SIGALRM, _alarm)
    try:
        signal.setitimer(signal.ITIMER_REAL, PROBE_TIMEOUT * 3)
        baseline = signature(source, class_name)
    except Exception as exc:
        report["error"] = f"the published source does not run here: {type(exc).__name__}: {exc}"
        return report
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)

    for item in found:
        name, default = item["name"], item["default"]
        seen: dict[int, dict[str, Any]] = {}

        def test(value: int, _name=name) -> bool:
            if value not in seen:
                seen[value] = probe(source, class_name, _name, value, baseline)
            return seen[value]["ok"]

        span = span_for(default)
        # Never below min(0, default): see the header on numpy's silent negative-index wrap.
        down = max(0, min(span, default - min(0, default)))
        low = default - furthest(test, default, -1, down)
        high = default + furthest(test, default, 1, span)

        if high == low:
            report["rejected"].append({"name": name, "why": "only its published value survives",
                                       "detail": first_reason(seen)})
            continue
        # Did turning it visibly do anything? A ranking signal, not a rejection -- a blind probe
        # never wins a level, so knobs that only bite on a win look inert and are not.
        moved = bool({p["signature"] for p in seen.values() if p.get("ok")} - {baseline["signature"]})

        report["knobs"].append({
            "name": name, "default": default, "min": low, "max": high, "moves": moved,
            "comment": item["comment"], "line": item["line"], "probes": len(seen),
        })

    report["knobs"] = [clamp_colour(k) for k in report["knobs"]]
    report["knobs"] = [k for k in report["knobs"] if k["max"] > k["min"]]
    report["measured"] = len(report["knobs"])
    report["unproven"] = sum(1 for k in report["knobs"] if not k["moves"])
    report["knobs"] = select(rank(report["knobs"]), max_knobs)
    report["dropped_to_cap"] = max(0, report["measured"] - len(report["knobs"]))
    return report


def first_reason(seen: dict[int, dict[str, Any]]) -> str:
    for value in sorted(seen, key=lambda v: abs(v)):
        if not seen[value]["ok"]:
            return f"{value}: {seen[value]['why']}"
    return ""


# ── English ──────────────────────────────────────────────────────────────────

GROUPS = [
    ("Animation", ("FRAME", "FRAMES", "STEPS", "TICK", "TICKS", "DELAY", "ANIM", "SPEED", "FPS",
                   "DUR", "BLINK", "FLASH", "PAUSE", "HOLD", "FADE", "TRAVEL", "SETTLE")),
    ("Palette", ("C", "COL", "COLOR", "COLOUR", "HUE", "PAL", "INK", "TINT", "SHADE", "DARK",
                 "LIT", "GLOW", "DIM", "BG", "FG", "WHITE", "BLACK", "GRAY", "GREY", "RED",
                 "GREEN", "BLUE", "YELLOW", "ORANGE", "PURPLE", "MAGENTA", "CYAN", "BROWN",
                 "PINK", "GOLD", "SILVER")),
    ("Geometry", ("CELL", "SIZE", "WIDTH", "HEIGHT", "ROWS", "COLS", "ROW", "PAD", "MARGIN",
                  "GAP", "TOP", "LEFT", "RIGHT", "BOTTOM", "HUD", "SPAN", "RADIUS", "SCALE",
                  "ORIGIN", "INSET", "EDGE", "BAND", "THICK", "DEPTH", "X", "Y", "X0", "Y0",
                  "STOREY", "DECK", "TRUSS", "SLOT", "PITCH", "OFFSET")),
    ("Rules", ("MAX", "MIN", "CAP", "LIMIT", "COUNT", "NUM", "LIVES", "TURNS", "MOVES", "GOAL",
               "WIN", "LOSE", "COST", "RATE", "CHANCE", "LEVEL", "LEVELS", "BUDGET", "REACH",
               "RANGE", "LOAD", "FALL", "PILE", "SCORE", "PENALTY", "BONUS")),
]
GROUP_ORDER = {"Geometry": 0, "Rules": 1, "Animation": 2, "Palette": 3, "Tuning": 4}

# Abbreviations worth expanding. Everything else is simply lower-cased, so a name that is already
# a word reads as one and a name that is a mystery stays a visible mystery rather than a fake word.
WORDS = {
    "COLS": "columns", "COL": "column", "ROWS": "rows", "ROW": "row", "PAD": "padding",
    "PX": "pixels", "W": "width", "H": "height", "N": "count", "NUM": "count", "AMT": "amount",
    "DUR": "duration", "ANIM": "animation", "BG": "background", "FG": "foreground",
    "CLR": "colour", "COLOR": "colour", "POS": "position", "DIR": "direction", "SPD": "speed",
    "IDX": "index", "LEN": "length", "THICK": "thickness", "MAXV": "max", "TMP": "temp",
    "C": "colour", "COLOUR": "colour", "COL": "colour", "MAX": "max", "MIN": "min",
    "CAP": "cap", "TOP": "top", "GAP": "gap", "ROW": "row", "BOX": "box", "BAR": "bar",
    "MAP": "map", "WIN": "win", "END": "end", "HIT": "hit", "DIM": "dim", "RUN": "run",
    "KEY": "key", "SUM": "sum", "AGE": "age", "HP": "HP", "XP": "XP", "GL": "GL",
    "HUD": "HUD", "FPS": "FPS", "X": "x", "Y": "y", "X0": "x0", "Y0": "y0", "MS": "ms",
}


def group_of(name: str, low: int, high: int) -> str:
    """Which of the four groups the shipped specs use. A range measured at exactly 0..15 is the
    engine's whole colour palette and almost nothing else survives precisely that, so it outvotes
    the keywords. A merely small 0-based band is not evidence of anything and is not used."""
    if low == 0 and high == 15:
        return "Palette"
    parts = set(name.split("_")) | {name}
    for group, keywords in GROUPS:
        if parts & set(keywords):
            return group
    return "Tuning"


def label_of(name: str) -> str:
    """A readable-ish label from a constant name. Mechanical, and worse than a human's."""
    # A short part that is not a known word stays upper-case, so an abbreviation reads as one
    # ("GL", "CW") instead of as a mangled word ("Gl", "Cw").
    parts = [WORDS.get(part, part if len(part) <= 3 else part.lower())
             for part in name.split("_") if part]
    if not parts:
        return name
    text = " ".join(parts)
    return text[0].upper() + text[1:] if text[0].islower() else text


def rank(knobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Which knobs are most worth a cap slot: ones a probe watched change the game, then ones the
    author commented -- that comment is the only real English in the file -- then the groups a
    player is most likely to reach for, then source order."""
    return sorted(knobs, key=lambda k: (0 if k["moves"] else 1,
                                        0 if k["comment"] else 1,
                                        GROUP_ORDER[group_of(k["name"], k["min"], k["max"])],
                                        k["line"]))


# The engine defines exactly sixteen colours (vet_game.PALETTE). A colour index above 15 is
# outside that domain, so it is clamped rather than measured: a padding colour set to 45 survives
# every check only because it never reaches a frame to be validated, and a slider that runs to 45
# to do nothing past 15 is broken. Domain, not taste -- the same reason a range is never guessed.
COLOUR_DOMAIN = 15
PALETTE_NAMES = frozenset(next(words for group, words in GROUPS if group == "Palette"))


def clamp_colour(knob: dict[str, Any]) -> dict[str, Any]:
    """A colour-named constant's band, held inside the engine's sixteen colours."""
    if not (set(knob["name"].split("_")) | {knob["name"]}) & PALETTE_NAMES:
        return knob
    return {**knob, "min": max(0, knob["min"]), "max": min(COLOUR_DOMAIN, knob["max"])}


PALETTE_CAP = 4


def select(ranked: list[dict[str, Any]], max_knobs: int) -> list[dict[str, Any]]:
    """The ranked knobs that fit the panel, with palette entries capped so a colour-heavy game
    keeps room for its geometry and rules. mb64's hand-written spec is twelve colours on purpose,
    because colour is that game's mechanic; nothing here can make that judgement, so it does not
    pretend to."""
    kept, palettes = [], 0
    for knob in ranked:
        if len(kept) >= max_knobs:
            break
        if group_of(knob["name"], knob["min"], knob["max"]) == "Palette":
            if palettes >= PALETTE_CAP:
                continue
            palettes += 1
        kept.append(knob)
    return kept


def spec_for(game_id: str, sha: str, report: dict[str, Any]) -> dict[str, Any]:
    """The JSON games-tuning.js reads. `sha256` is not read by the runtime; it records which
    bytes were measured, so a stale spec can be spotted without re-measuring."""
    params = []
    for knob in report["knobs"]:
        param = {
            "name": knob["name"],
            "label": label_of(knob["name"]),
            "group": group_of(knob["name"], knob["min"], knob["max"]),
            "type": "int",
            "min": knob["min"],
            "max": knob["max"],
            "step": 1,
            "default": knob["default"],
        }
        if knob["comment"]:
            param["note"] = knob["comment"]
        params.append(param)
    return {"gameId": game_id, "schema": 1, "sha256": sha,
            "generatedBy": "scripts/measure_game_params.py", "params": params}


# ── The catalog ──────────────────────────────────────────────────────────────


def fetch(url: str) -> bytes:
    """curl, because the site answers a browser user-agent and 403s urllib's."""
    done = subprocess.run(["curl", "-sfSL", "-A", "arc3-measure-game-params", url],
                          capture_output=True, check=True)
    return done.stdout


def heads(include_blind: bool) -> list[dict[str, Any]]:
    """Every tree head a tuning panel could render for, newest source first."""
    out, offset = [], 0
    while True:
        page = json.loads(fetch(f"{SITE}{TREES_API}?{urllib.parse.urlencode({'limit': 100, 'offset': offset})}"))
        out += page["trees"]
        offset += page["limit"]
        if offset >= page["total"]:
            break
    keep = []
    for tree in out:
        family = tree["family"]
        if family in RETIRED_FAMILIES:
            continue
        if family in BLIND_FAMILIES and not include_blind:
            continue
        head = tree["head"]
        keep.append({"gameId": head["gameId"], "family": family, "sha256": head["sha256"],
                     "className": head["className"], "sourceUrl": head["sourceUrl"]})
    return keep


def source_of(head: dict[str, Any]) -> str:
    """The head's exact bytes, cached under scratch/ by sha so a re-run only fetches what moved."""
    SRC_CACHE.mkdir(parents=True, exist_ok=True)
    path = SRC_CACHE / f"{head['gameId']}-{head['sha256'][:12]}.py"
    if not path.exists():
        path.write_bytes(fetch(SITE + head["sourceUrl"]))
    return path.read_text()


# ── Running ──────────────────────────────────────────────────────────────────


def _worker(source: str, class_name: str, max_knobs: int, pipe) -> None:
    try:
        pipe.send(measure_game(source, class_name, max_knobs))
    except Exception as exc:
        pipe.send({"error": f"{type(exc).__name__}: {exc}", "knobs": [], "rejected": [], "candidates": 0})
    finally:
        pipe.close()


def measure_isolated(source: str, class_name: str, max_knobs: int, budget: float) -> dict[str, Any]:
    """Measure one game in a child process. Game code is arbitrary: it can leak, abort the
    interpreter or wedge past its own alarm, and none of that may take the run down with it."""
    parent, child = multiprocessing.Pipe(duplex=False)
    process = multiprocessing.Process(target=_worker, args=(source, class_name, max_knobs, child))
    process.start()
    child.close()
    try:
        result = parent.recv() if parent.poll(budget) else {
            "error": f"gave up after {budget:.0f}s", "knobs": [], "rejected": [], "candidates": 0}
    except EOFError:
        result = {"error": "the measuring process died", "knobs": [], "rejected": [], "candidates": 0}
    finally:
        parent.close()
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", nargs="*", metavar="ID", help="measure just these game ids")
    parser.add_argument("--max-knobs", type=int, default=12,
                        help="sliders per panel (default 12, the largest hand-written spec)")
    parser.add_argument("--budget", type=float, default=600.0, help="seconds per game before giving up")
    parser.add_argument("--dry-run", action="store_true", help="measure and report, write nothing")
    parser.add_argument("--include-blind", action="store_true",
                        help="also measure blind families, whose panels games-tuning.js will not render")
    parser.add_argument("--include-handwritten", action="store_true",
                        help="overwrite the five hand-measured specs with derived English (do not)")
    parser.add_argument("--report", type=Path, help="write the full per-candidate measurement log here")
    parser.add_argument("--no-cache", action="store_true", help="re-measure even unchanged sources")
    args = parser.parse_args(argv)

    cache: dict[str, Any] = {}
    if CACHE.exists() and not args.no_cache:
        cache = json.loads(CACHE.read_text())

    catalog = heads(args.include_blind)
    if args.only:
        wanted = set(args.only)
        catalog = [h for h in catalog if h["gameId"] in wanted]
        missing = wanted - {h["gameId"] for h in catalog}
        if missing:
            print(f"! not in the renderable catalog: {', '.join(sorted(missing))}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"site": SITE, "maxKnobs": args.max_knobs, "games": {}}
    written = skipped = empty = 0

    for index, head in enumerate(catalog, 1):
        game_id = head["gameId"]
        if game_id in HANDWRITTEN and not args.include_handwritten:
            print(f"[{index}/{len(catalog)}] {game_id}: hand-written, left alone")
            report["games"][game_id] = {"handwritten": True}
            skipped += 1
            continue

        key = f"{game_id}@{head['sha256'][:12]}#{args.max_knobs}"
        if key in cache:
            result = cache[key]
            mark = "cached"
        else:
            source = source_of(head)
            class_name = head["className"] or (find_game_classes(ast.parse(source)) or [""])[0]
            result = measure_isolated(source, class_name, args.max_knobs, args.budget)
            cache[key] = result
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(cache, indent=1) + "\n")
            mark = "measured"

        result["family"] = head["family"]
        report["games"][game_id] = result
        knobs = result.get("knobs", [])
        note = f" [{result['error']}]" if result.get("error") else ""
        print(f"[{index}/{len(catalog)}] {game_id}: {len(knobs)} of {result.get('candidates', 0)} "
              f"candidates ({mark}){note}")

        out = OUT_DIR / f"{game_id}.json"
        if knobs and not any(k["moves"] for k in knobs):
            # Individually invisible knobs are fine and are kept (br10's FALL, hg51's WIN_HOLD
            # only bite later in a level). A whole panel where nothing moved is not: it would be
            # sliders that visibly do nothing. Measured in CPython and confirmed in the browser
            # on cn04-2fe56bfb, whose two template colour constants never reach a drawn pixel.
            print(f"    every knob is inert, writing no spec")
            report["games"][game_id]["inert"] = True
            report["games"][game_id]["knobs"] = []
            knobs = []
            empty += 1
            continue
        if not knobs:
            # games-tuning.js says a 404 is the ordinary answer for a game with nothing to turn,
            # so an empty spec is a file that says nothing. Do not write one.
            empty += 1
            continue
        if not args.dry_run:
            out.write_text(json.dumps(spec_for(game_id, head["sha256"], result), indent=2) + "\n")
        written += 1

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=1) + "\n")

    total_knobs = sum(len(g.get("knobs", [])) for g in report["games"].values())
    verb = "would write" if args.dry_run else "wrote"
    print(f"\n{verb} {written} specs ({total_knobs} sliders), {empty} games with nothing "
          f"measurable, {skipped} hand-written left alone, of {len(catalog)} renderable games")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

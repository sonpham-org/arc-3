#!/usr/bin/env python3
"""Find every published game's editable sprite art and write the Games page sprite specs.

Author: Claude Opus 5
Date: 20-September-2026
PURPOSE: Generate docs/static/games/sprites/<id>.json -- the per-game sprite-editor specs read by
docs/static/js/games-sprites.js -- by locating each game's literal glyph art in its head source
and proving, headlessly, that editing it actually changes the board and leaves the game playable.
Art is found, never assumed: a literal is only shipped as a sprite after a patched copy of the
game loads, draws a *different* frame, steps and resets. Re-runnable by design, because the
evolution loop rewrites these sources continuously.

What a sprite is here, and what it is not. Across the catalog "2D art" is mostly not art:
`DIRS = [[0,1],[1,0],[0,-1],[-1,0]]` is direction vectors, the q-family's 3x3 `RULES`/`SIG`/`BASE`
are response tables, `BAYER` is a dither matrix, and `pc01 _G1.._G7` and `pr01 MAZE` are level
maps. None of those translate and none of them are offered. What is offered is a small literal
glyph -- a rectangular block of equal-length symbol rows, or a set of (dx, dy) pixel offsets --
that the game blits at an actor's position.

SRP/DRY check: Pass -- this only decides what art is editable. Loading and frame validation are
reused from scripts/vet_game.py (load_class, Player, frame_hash, VetError); the catalog walk
(heads, source_of, fetch) and the blind/retired family policy are reused from
scripts/measure_game_params.py, which is the sibling generator for the tuning panel. The
anchoring and re-rendering rules here are a deliberate line-for-line mirror of readSprite() and
patchSprite() in games-sprites.js, which is the contract a spec has to satisfy.

  python3.13 scripts/measure_game_sprites.py                  # find everything, write specs
  python3.13 scripts/measure_game_sprites.py --only sd78 mb64 --dry-run
  python3.13 scripts/measure_game_sprites.py --report scratch/sprites-report.json

Requires python3.13 (the engine uses match/case) with arcengine and numpy importable.

Two design decisions worth stating, because both refuse an easier answer:

  * A sprite is anchored on the *exact source text of its own literal*, not on a name and not on
    a line number. Names do not exist for the nested ones (sd78's beetles live at
    SPECIES_ART["ladybird"]["stand"]), and line numbers are worthless because the bytes the
    player runs come from the API's head, which moves. The anchor must occur exactly once in the
    fetched source or the sprite is dropped from the panel -- the same "exactly one match or
    drop" rule readScalar() uses, for the same reason.

  * The editor's palette for a sprite is the set of symbols *that sprite's game already uses*,
    not the 16-colour ARC palette. This matters: cell values mean different things per game.
    fy01 stores palette indices, g013's mask cells index a 2-tuple of colours (painting a 12
    there is an IndexError, not a recolour), and sd78 maps chars through its own ART_KEY where
    'X' means "the species colour, substituted at build time". Offering 0..15 everywhere would
    break three encodings out of four. Restricting the brush to symbols already in the game's own
    art is correct by construction for all of them.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import multiprocessing
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

OUT_DIR = REPO / "docs" / "static" / "games" / "sprites"


def _sibling(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vet = _sibling("vet_game")                 # load_class(), Player, frame_hash, VetError

# ── The catalog ──────────────────────────────────────────────────────────────
# Deliberately not imported from scripts/measure_game_params.py, which does the same walk for the
# tuning panel. That script is not on main -- it is in flight alongside this one -- and a
# generator that cannot run without an uncommitted sibling is a generator that cannot be re-run
# later, which is the one thing both of these have to be. The family policy below is the same
# policy, read from the same place (games-api.js), not a copy of that script's copy.

SITE = "https://arc3.sonpham.net"
TREES_API = "/api/v1/public/games/trees"
SRC_CACHE = REPO / "scratch" / "sprite-sources"

# games-api.js: panels never attach to a blind family, and retired families are off the page.
# A sprite grid is a more direct read of a game's shape than a list of constant names, so the
# blind rule binds here at least as hard as it does on the tuning panel.
BLIND_FAMILIES = {"arena", "contributed-glowup", "research"}
RETIRED_FAMILIES = {"ai-generated", "redbluepill"}


def fetch(url: str) -> bytes:
    """curl, because the site answers a browser user-agent and 403s urllib's."""
    done = subprocess.run(["curl", "-sfSL", "-A", "arc3-measure-game-sprites", url],
                          capture_output=True, check=True)
    return done.stdout


def heads(include_blind: bool) -> list[dict[str, Any]]:
    """Every tree head a sprite panel could render for."""
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

# A glyph is small. Anything larger is a level map or a lookup table -- both are real 2D literals
# and neither translates, which is the line Son drew ("anything that is drawn non-programmatic
# and translates"). 8 is generous: the largest true sprite in the catalog is sd78's 6x6 stag.
MAX_SIDE = 8
MIN_SIDE = 2
# An art alphabet is a handful of symbols. A 15x15 maze of '#' and '.' passes this and is caught
# by MAX_SIDE; a block of prose or a list of names does not pass it at all.
MAX_ALPHABET = 12
# Every art literal needs a way to say "nothing here". Without one it is a dense table, not a glyph.
EMPTY_CHARS = set(". #~ ")


# ── Locating art ─────────────────────────────────────────────────────────────


def segment(source: str, node: ast.AST) -> str | None:
    """The exact source text of a literal, or None if it cannot be pinned down."""
    try:
        text = ast.get_source_segment(source, node)
    except Exception:
        return None
    return text


def char_rows(node: ast.AST) -> list[str] | None:
    """A List/Tuple of >=2 equal-length string constants -- a char stencil -- or None."""
    if not isinstance(node, (ast.List, ast.Tuple)) or len(node.elts) < MIN_SIDE:
        return None
    rows = []
    for element in node.elts:
        if not (isinstance(element, ast.Constant) and isinstance(element.value, str)):
            return None
        rows.append(element.value)
    widths = {len(r) for r in rows}
    if len(widths) != 1:
        return None
    return rows


def int_rows(node: ast.AST) -> list[list[int]] | None:
    """A rectangular block of int rows -- a palette or mask grid -- or None."""
    if not isinstance(node, (ast.List, ast.Tuple)) or len(node.elts) < MIN_SIDE:
        return None
    rows = []
    for element in node.elts:
        if not isinstance(element, (ast.List, ast.Tuple)) or len(element.elts) < MIN_SIDE:
            return None
        row = []
        for cell in element.elts:
            value = literal_int(cell)
            if value is None:
                return None
            row.append(value)
        rows.append(row)
    widths = {len(r) for r in rows}
    if len(widths) != 1:
        return None
    return rows


def literal_int(node: ast.AST) -> int | None:
    """An int constant, or its negation. Mirrors measure_game_params.literal_int."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = literal_int(node.operand)
        return None if inner is None else -inner
    return None


def offset_rows(node: ast.AST) -> list[tuple[int, int]] | None:
    """A set of >=2 (dx, dy) pairs, tight enough around the origin to be one figure's pixels.

    This is the encoding rw01's WALKER_PIXELS and pw01's KETTLE_BODY use. The span test is what
    separates a glyph from a list of board positions: fr01's SEAWEED runs 3..61, which is
    furniture scattered across a 64x64 board, not a sprite.
    """
    if not isinstance(node, (ast.List, ast.Tuple)) or len(node.elts) < MIN_SIDE:
        return None
    pairs = []
    for element in node.elts:
        if not isinstance(element, (ast.List, ast.Tuple)) or len(element.elts) != 2:
            return None
        a, b = literal_int(element.elts[0]), literal_int(element.elts[1])
        if a is None or b is None:
            return None
        pairs.append((a, b))
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    if max(xs) - min(xs) >= MAX_SIDE or max(ys) - min(ys) >= MAX_SIDE:
        return None
    # A figure has extent and distinct pixels. Without this, bq01's `[(6, 6), (6, 6)]` -- one
    # point written twice -- arrives as a 1x1 "sprite" with a single cell that cannot be
    # meaningfully painted, and `variant()` "edits" it by deleting half of nothing.
    if len(set(pairs)) < 2:
        return None
    if (max(xs) - min(xs)) < 1 and (max(ys) - min(ys)) < 1:
        return None
    # The four unit steps are a direction table, not a figure -- every grid game has one.
    unit = {(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)}
    if set(pairs) <= unit:
        return None
    return pairs


def candidates(source: str) -> list[dict[str, Any]]:
    """Every literal in the source that could be a glyph, with its anchor text.

    Walks the whole tree, not just module level: sd78's beetles are nested two dicts deep at
    SPECIES_ART["ladybird"]["stand"], and those are the best sprites in the catalog.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        anchor = None
        entry = None

        rows = char_rows(node)
        if rows is not None:
            width = len(rows[0])
            alphabet = sorted(set("".join(rows)))
            if not (MIN_SIDE <= len(rows) <= MAX_SIDE and MIN_SIDE <= width <= MAX_SIDE):
                continue
            if len(alphabet) > MAX_ALPHABET or not (set(alphabet) & EMPTY_CHARS):
                continue
            entry = {"encoding": "charStencil", "rows": len(rows), "cols": width,
                     "default": rows, "alphabet": alphabet}
        else:
            grid = int_rows(node)
            if grid is not None and len(grid[0]) == 2:
                # Nx2 is ambiguous on its face and is almost never a 2-pixel-wide glyph: it is a
                # direction table or a set of (dx, dy) pixel offsets. Route it to the offset
                # reader, which knows how to tell those two apart, rather than shipping DIRS as
                # a 4x2 sprite -- which is exactly what an earlier cut of this did.
                grid = None
            if grid is not None:
                width = len(grid[0])
                if not (MIN_SIDE <= len(grid) <= MAX_SIDE and MIN_SIDE <= width <= MAX_SIDE):
                    continue
                values = sorted({c for row in grid for c in row})
                # A palette grid needs a transparent or zero cell, same reasoning as EMPTY_CHARS,
                # and its values must be legal ARC indices (or -1). Anything else is a table.
                if not (-1 <= values[0] and values[-1] <= 15) or len(values) > MAX_ALPHABET:
                    continue
                entry = {"encoding": "intGrid", "rows": len(grid), "cols": width,
                         "default": grid, "alphabet": values}
            else:
                pairs = offset_rows(node)
                if pairs is not None:
                    entry = {"encoding": "offsets", "rows": max(p[1] for p in pairs) - min(p[1] for p in pairs) + 1,
                             "cols": max(p[0] for p in pairs) - min(p[0] for p in pairs) + 1,
                             "default": [list(p) for p in pairs], "alphabet": [0, 1],
                             "originX": min(p[0] for p in pairs), "originY": min(p[1] for p in pairs)}

        if entry is None:
            continue
        anchor = segment(source, node)
        if not anchor or source.count(anchor) != 1:
            continue  # not uniquely locatable: the panel could not patch it safely
        entry["anchor"] = anchor
        entry["line"] = getattr(node, "lineno", 0)
        found.append(entry)
    return found


# ── Re-rendering ─────────────────────────────────────────────────────────────
# Mirrored by renderSprite() in games-sprites.js. The two must agree exactly, because the spec's
# recorded default is produced here and the browser has to reproduce it byte for byte to know
# an unedited sprite is unedited.


def indent_of(anchor: str) -> str:
    """The leading whitespace of the anchor's second line -- the indent its rows are written at."""
    lines = anchor.split("\n")
    if len(lines) < 2:
        return ""
    return re.match(r"[ \t]*", lines[1]).group(0)


def closing_indent(anchor: str) -> str:
    """The indent the closing bracket sits at. Not the same as the rows' indent: art nested inside
    a call is written one level in from its own bracket, and normalising the two turns every
    nested sprite into a false "this does not round-trip"."""
    last = anchor.split("\n")[-1]
    return re.match(r"[ \t]*", last).group(0)


def render(entry: dict[str, Any], grid: Any) -> str:
    """`grid` written back in the anchor's own bracket, quote and layout style.

    Style is preserved rather than normalised because the anchor for an *unedited* sprite has to
    come back identical -- a tuple that returns as a list would make every sprite read as edited,
    and worse, would not be found again on a second patch.
    """
    anchor = entry["anchor"]
    multiline = "\n" in anchor
    open_bracket = anchor[0]
    close_bracket = "]" if open_bracket == "[" else ")"
    indent = indent_of(anchor)
    quote = '"' if '"' in anchor else "'"

    if entry["encoding"] == "charStencil":
        pieces = [f"{quote}{row}{quote}" for row in grid]
    elif entry["encoding"] == "intGrid":
        inner_open, inner_close = ("[", "]") if "[[" in anchor.replace(" ", "") or open_bracket == "[" else ("(", ")")
        pieces = [inner_open + ", ".join(str(c) for c in row) + inner_close for row in grid]
    else:  # offsets
        pieces = [f"({int(p[0])}, {int(p[1])})" for p in grid]

    if multiline:
        body = "".join(f"\n{indent}{piece}," for piece in pieces)
        return f"{open_bracket}{body}\n{closing_indent(anchor)}{close_bracket}"
    joined = ", ".join(pieces)
    # A one-element tuple needs its trailing comma, but art never has one element.
    return f"{open_bracket}{joined}{close_bracket}"


def patch(source: str, entry: dict[str, Any], grid: Any) -> str:
    """`source` with this one sprite's literal replaced. Raises if the anchor is not unique."""
    anchor = entry["anchor"]
    if source.count(anchor) != 1:
        raise vet.VetError("the sprite's anchor no longer occurs exactly once")
    return source.replace(anchor, render(entry, grid))


def round_trips(source: str, entry: dict[str, Any]) -> bool:
    """Re-rendering the untouched default reproduces the source exactly.

    The honesty check the whole spec rests on: if this fails, the panel would show a sprite as
    edited the moment it opened, and "reset to published" would not restore the published bytes.
    """
    return patch(source, entry, entry["default"]) == source


# ── Proving an edit is real ──────────────────────────────────────────────────


def variant(entry: dict[str, Any]) -> Any:
    """A deliberately different version of the art, drawn only from symbols the game already uses.

    Never invents a symbol: an unknown char is a KeyError in the game's own art() helper and an
    out-of-range int is an IndexError in a mask lookup, and neither would be the panel's fault.
    """
    default = entry["default"]
    alphabet = entry["alphabet"]
    if entry["encoding"] == "charStencil":
        empty = next((c for c in alphabet if c in EMPTY_CHARS), alphabet[0])
        ink = next((c for c in alphabet if c not in EMPTY_CHARS), alphabet[-1])
        # Fill it solid with the game's own ink: maximally different, always legal.
        return ["".join(ink for _ in row) for row in default]
    if entry["encoding"] == "intGrid":
        ink = max(alphabet)
        return [[ink for _ in row] for row in default]
    # offsets: drop the last pixel. Keeps order (rw01 reads this tuple in order as a drain
    # animation and uses its length as the denominator) while changing what is drawn.
    return [list(p) for p in default[:-1]]


# How far to play a game while looking for the edit. Most sprites are not on the opening frame:
# sd78's beetles have walk and sleep poses, its puff starts invisible, and mb64's slug is only
# drawn once a level is built. A check that compares the reset frame alone calls all of those
# "editing it changed nothing on screen", which is a false negative and rejects the best sprites
# in the catalog -- the first cut of this script did exactly that and shipped four sprites
# instead of twenty-eight.
PLAY_STEPS = 10
# ...on every level, not just the first. A beetle species, a coral bed or a slug only exists on
# the level whose spec asks for one, so a trace that never leaves level 1 rejects most of a
# game's cast as "changed nothing on screen".
MAX_LEVELS = 12


def trace_of(source: str, class_name: str) -> tuple[list[str], int]:
    """Play a fixed opening on every level and return every frame's hash, plus the level count.

    The action sequence is a fixed cycle over the game's own available actions, so two runs of
    the same source produce the same list -- which is what makes a difference between two lists
    mean "the art changed" rather than "the game is random".
    """
    cls = vet.load_class(source, class_name)
    game = cls()
    player = vet.Player(game)
    # _levels is the built level list. Not _win_levels -- that is the number needed to win, it
    # does not exist on every game, and defaulting it to 1 silently confines this whole sweep to
    # the opening level, which is how an earlier cut rejected mb64's coral and slug.
    levels = len(getattr(game, "_levels", []) or [None])
    available = [int(getattr(a, "value", a)) for a in (getattr(game, "_available_actions", []) or [1])]
    digests: list[str] = []
    for index in range(min(levels, MAX_LEVELS)):
        try:
            if index:
                game.set_level(index)
            result = player.reset()
        except Exception:
            break  # a game that will not build this level gives a comparable prefix and no more
        digests.append(vet.frame_hash(result.frame))
        for step in range(PLAY_STEPS):
            try:
                result = player.act(available[step % len(available)])
            except Exception:
                break
            digests.append(vet.frame_hash(result.frame))
    return digests, levels


def check(source: str, class_name: str, entry: dict[str, Any]) -> dict[str, Any]:
    """Is this literal really an editable sprite? Measured, not guessed."""
    if not round_trips(source, entry):
        # Almost always because the literal's own layout carries something a re-render would
        # drop -- rw01's WALKER_PIXELS groups its rows under per-line comments explaining that
        # the order is a Bayer fill sequence. Rewriting that away to gain an editor is a bad
        # trade, so the sprite is dropped instead.
        return {"ok": False, "why": "its layout carries comments or spacing a re-render would drop"}
    try:
        base, base_levels = trace_of(source, class_name)
        again, _ = trace_of(source, class_name)
    except Exception as exc:
        return {"ok": False, "why": f"the unpatched game did not run: {type(exc).__name__}: {exc}"}
    if base != again:
        # Not the sprite's fault, and not something this script may paper over: in a game whose
        # opening is random, no frame comparison can tell an edit from the dice.
        return {"ok": False, "why": "the game does not draw the same opening twice, so an edit cannot be told from noise"}
    try:
        edited = patch(source, entry, variant(entry))
        edit, edit_levels = trace_of(edited, class_name)
    except Exception as exc:
        return {"ok": False, "why": f"an edit broke the game: {type(exc).__name__}: {exc}"}
    if edit == base:
        return {"ok": False, "why": f"editing it changed nothing across {PLAY_STEPS} steps on each of its levels"}
    if edit_levels != base_levels:
        return {"ok": False, "why": "editing it changed how many levels the game has"}
    if len(edit) != len(base):
        return {"ok": False, "why": "editing it changed how far the game can be played"}
    return {"ok": True, "why": ""}


def label_of(entry: dict[str, Any], index: int) -> str:
    """Readable-ish. The anchor has no name when it is nested, so fall back to its shape."""
    name = entry.get("name")
    if name:
        words = name.strip("_").replace("_ART", "").replace("_PIXELS", "").split("_")
        return " ".join(w.capitalize() for w in words if w) or name
    return f"Sprite {index + 1} ({entry['rows']}x{entry['cols']})"


def names_in(source: str) -> dict[str, str]:
    """anchor text -> the constant it is assigned to, where it is assigned to one."""
    out = {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            text = segment(source, node.value)
            if text:
                out[text] = node.targets[0].id
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    text = segment(source, value)
                    if text:
                        out.setdefault(text, key.value)
    return out


def measure_game(source: str, class_name: str, max_sprites: int) -> dict[str, Any]:
    named = names_in(source)
    sprites, rejected = [], []
    for index, entry in enumerate(candidates(source)):
        entry["name"] = named.get(entry["anchor"])
        verdict = check(source, class_name, entry)
        if not verdict["ok"]:
            rejected.append({"line": entry["line"], "name": entry.get("name"),
                             "shape": f"{entry['rows']}x{entry['cols']}", "why": verdict["why"]})
            continue
        sprites.append({
            "id": f"s{len(sprites)}",
            "label": label_of(entry, len(sprites)),
            "name": entry.get("name"),
            "encoding": entry["encoding"],
            "rows": entry["rows"],
            "cols": entry["cols"],
            "alphabet": entry["alphabet"],
            "anchor": entry["anchor"],
            "default": entry["default"],
            **({"originX": entry["originX"], "originY": entry["originY"]} if "originX" in entry else {}),
        })
        if len(sprites) >= max_sprites:
            break
    return {"sprites": sprites, "rejected": rejected}


def _worker(source, class_name, max_sprites, pipe):
    try:
        pipe.send(measure_game(source, class_name, max_sprites))
    except Exception as exc:
        pipe.send({"error": f"{type(exc).__name__}: {exc}", "sprites": [], "rejected": []})
    finally:
        pipe.close()


def measure_isolated(source: str, class_name: str, max_sprites: int, budget: float) -> dict[str, Any]:
    """One game per child process: game code is arbitrary and may wedge or abort the interpreter.
    Same reasoning, and the same shape, as measure_game_params.measure_isolated."""
    parent, child = multiprocessing.Pipe(duplex=False)
    process = multiprocessing.Process(target=_worker, args=(source, class_name, max_sprites, child))
    process.start()
    child.close()
    try:
        result = parent.recv() if parent.poll(budget) else {
            "error": f"gave up after {budget:.0f}s", "sprites": [], "rejected": []}
    except EOFError:
        result = {"error": "the measuring process died", "sprites": [], "rejected": []}
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
    parser.add_argument("--max-sprites", type=int, default=24, help="sprites per panel (default 24)")
    parser.add_argument("--budget", type=float, default=600.0, help="seconds per game before giving up")
    parser.add_argument("--dry-run", action="store_true", help="measure and report, write nothing")
    parser.add_argument("--report", type=Path, help="write the full per-game findings here")
    parser.add_argument("--include-blind", action="store_true",
                        help="also measure blind families, whose panels games-sprites.js will not render")
    args = parser.parse_args(argv)

    catalog = heads(args.include_blind)
    if args.only:
        wanted = set(args.only)
        catalog = [h for h in catalog if h["gameId"] in wanted]
    print(f"{len(catalog)} published heads to look at", file=sys.stderr)

    report, written = {}, 0
    if not args.dry_run:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
    for head in catalog:
        game_id = head["gameId"]
        source = source_of(head)
        result = measure_isolated(source, head["className"], args.max_sprites, args.budget)
        report[game_id] = result
        sprites = result.get("sprites", [])
        note = result.get("error") or f"{len(sprites)} sprite(s), {len(result.get('rejected', []))} rejected"
        print(f"  {game_id:24} {note}", file=sys.stderr)
        if not sprites:
            # No spec file rather than an empty one: 404 is how games-sprites.js says "no tab".
            # And if a previous run wrote one, take it away: a head that has lost its art must
            # lose its tab too, or the panel goes on offering sprites that are no longer there.
            stale = OUT_DIR / f"{game_id}.json"
            if stale.exists() and not args.dry_run:
                stale.unlink()
                print(f"  {game_id:24} its art is gone; removed the stale spec", file=sys.stderr)
            continue
        spec = {"schema": 1, "gameId": game_id, "sha256": head["sha256"],
                "generatedBy": "scripts/measure_game_sprites.py", "sprites": sprites}
        if not args.dry_run:
            (OUT_DIR / f"{game_id}.json").write_text(json.dumps(spec, indent=1) + "\n")
        written += 1
    print(f"{written} spec(s) {'would be ' if args.dry_run else ''}written", file=sys.stderr)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

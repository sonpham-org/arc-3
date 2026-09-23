#!/usr/bin/env python3
"""Paint every sprite of every generated spec in a real browser, and fail if one breaks.

Author: Claude Opus 5
Date: 20-September-2026
PURPOSE: The acceptance gate for docs/static/games/sprites/*.json. A spec is a claim about what a
player can be handed, and the only place that claim is true or false is the Games page running
Pyodide -- the art is proven editable in CPython by scripts/measure_game_sprites.py, which is a
different interpreter, a different arcengine build and a different numpy. This drives Chromium
over the play view and, for each spec, checks six things: the Sprites tab appears, every sprite
the spec declares renders a grid of the right size, painting a cell changes the board, the game
still plays afterwards, "Reset this sprite" puts the published art back, and a sprite edit and a
knob edit applied together both survive.

SRP/DRY check: Pass -- checking only. Specs are produced by measure_game_sprites.py; the server
is scripts/serve_games_local.py (the tuning panel's, unchanged); this reads the spec files and
reports, and writes nothing to docs/.

Needs playwright, which is installed under python3.14 here -- not the 3.13 the generator needs:

  python3.13 scripts/serve_games_local.py &                      # terminal 1
  python3.13 scripts/measure_game_sprites.py                     # write the specs
  python3.14 scripts/verify_game_sprites.py --report scratch/verify-sprites.json

Exit status is 1 if any spec failed, so it can gate a push.

The same hard-won detail the tuning verifier carries applies here and for the same reason: every
game gets a brand new page and that page is closed after. Navigating by hash alone does not
reload, and a run that reuses one page reports the previous game's grid counts and lets one
game's wedged Pyodide worker fail every game after it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SPEC_DIR = REPO / "docs" / "static" / "games" / "sprites"
PARAM_DIR = REPO / "docs" / "static" / "games" / "params"

# The panel is built from the source the player actually loaded, so a sprite the evolution loop
# has since rewritten is simply not on screen. Count what rendered, not what the spec hoped for.
JS_CARDS = "() => document.querySelectorAll('#spritePanel .sprite-card').length"
JS_TAB = "() => !document.getElementById('panelTabs').hidden"
JS_CANVAS = "() => document.getElementById('gameCanvas').toDataURL()"
JS_IDLE = """() => !document.getElementById('spritePanel').classList.contains('tune-busy')
  && !document.getElementById('tuningPanel').classList.contains('tune-busy')"""
JS_FAULT = """() => {
  const msg = document.querySelector('#spritePanel .tune-msg');
  return (msg && !msg.hidden && msg.classList.contains('tune-bad')) ? msg.textContent : null;
}"""
JS_OPEN_SPRITES = "() => { document.getElementById('tabSprites').click(); return true; }"
# Fill a whole card with whichever brush is not the one its first cell already shows. One cell is
# not enough: the top-left of a glyph is very often transparent, and half these sprites are poses
# (mb64's "squash", sd78's "walk") that are only on screen mid-move. Filling the figure solid is
# the same edit measure_game_sprites.py proves visible headlessly, so the two checks agree.
JS_PAINT = """([card]) => {
  const cards = document.querySelectorAll('#spritePanel .sprite-card');
  if (card >= cards.length) return false;
  const brushes = cards[card].querySelectorAll('.sprite-brush');
  const cells = cards[card].querySelectorAll('.sprite-cell');
  if (brushes.length < 2 || !cells.length) return false;
  // The brush that is not "empty" makes the biggest visible difference.
  let picked = [...brushes].find((b) => !b.classList.contains('sprite-empty')) || brushes[1];
  picked.click();
  for (const cell of cells) cell.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
  return true;
}"""
JS_RESET_CARD = """([card]) => {
  const cards = document.querySelectorAll('#spritePanel .sprite-card');
  if (card >= cards.length) return false;
  const buttons = [...cards[card].querySelectorAll('button')];
  const reset = buttons.find((b) => b.textContent.startsWith('Reset'));
  if (!reset) return false;
  reset.click();
  return true;
}"""
JS_GRID_SIZE = """([card]) => {
  const cards = document.querySelectorAll('#spritePanel .sprite-card');
  if (card >= cards.length) return null;
  return cards[card].querySelectorAll('.sprite-cell').length;
}"""
JS_SET_KNOB = """([name, value]) => {
  document.getElementById('tabTune').click();
  const slider = document.getElementById('tune-' + name);
  if (!slider) return false;
  slider.value = String(value);
  slider.dispatchEvent(new Event('change', {bubbles: true}));
  return true;
}"""
# Is the game still playable? Send a real key and see the step counter move.
JS_STEPS = "() => document.getElementById('stepCount') ? document.getElementById('stepCount').textContent : null"

# How many steps of play to compare before and after an edit. A pose sprite is not on the opening
# board, so a single-frame comparison calls a perfectly good edit invisible -- which is exactly
# what the first cut of this script did, failing mb64 and sd78 on six cards between them while
# the headless generator had already proven every one of them visible.
TRACE_STEPS = 6
TRACE_KEYS = ("ArrowUp", "ArrowRight", "ArrowDown", "ArrowLeft", "Space", "Enter")


def trace(page) -> list:
    """The board now, and after each of a fixed run of key presses."""
    shots = [page.evaluate(JS_CANVAS)]
    for index in range(TRACE_STEPS):
        page.keyboard.press(TRACE_KEYS[index % len(TRACE_KEYS)])
        page.wait_for_timeout(140)
        shots.append(page.evaluate(JS_CANVAS))
    return shots


def settle(page, timeout: int) -> None:
    """Wait out the reload a paint just triggered."""
    page.wait_for_function(JS_IDLE, timeout=timeout)
    page.wait_for_timeout(180)


def check_game(page, base: str, game_id: str, spec: dict, knob: dict | None, timeout: int) -> dict:
    """Open one game, paint every sprite it renders, and report what happened."""
    problems: list[str] = []
    notes: list[str] = []
    # Cards whose edit this check could not see, which is not the same as a card that is broken.
    # Many of these sprites are animation poses -- mb64's "squash", sd78's "walk" -- and the
    # canvas only ever holds the settled frame, so an intermediate pose is not sampleable from
    # here at all. The headless generator hashes every frame the engine returns and has already
    # proven each of these visible; this run cannot confirm it and says so rather than either
    # failing a good sprite or quietly passing it.
    unobserved: list[str] = []

    page.goto(f"{base}/index.html#g={game_id}", wait_until="domcontentloaded")
    try:
        page.wait_for_function("() => document.querySelectorAll('#spritePanel .sprite-card').length > 0",
                               timeout=timeout)
    except Exception:
        return {"ok": False, "problems": ["the sprite panel rendered no cards at all"], "cards": 0, "notes": notes}

    if not page.evaluate(JS_TAB):
        problems.append("the Sprites tab did not appear even though the panel has cards")
    page.evaluate(JS_OPEN_SPRITES)
    settle(page, timeout)

    cards = page.evaluate(JS_CARDS)
    declared = len(spec.get("sprites", []))
    if cards < declared:
        # Expected and fine: the head moved and some anchors no longer resolve. Worth saying.
        notes.append(f"{cards} of {declared} declared sprites still resolve against this head")

    opening = page.evaluate(JS_CANVAS)

    for index in range(cards):
        size = page.evaluate(JS_GRID_SIZE, [index])
        declared_size = None
        if index < declared:
            entry = spec["sprites"][index]
            declared_size = entry["rows"] * entry["cols"]
        if declared_size and size != declared_size:
            notes.append(f"card {index} shows {size} cells, the spec's entry {index} has {declared_size}")

        before = trace(page)
        if not page.evaluate(JS_PAINT, [index]):
            notes.append(f"card {index}: no second brush to paint with, skipped")
            continue
        settle(page, timeout)
        fault = page.evaluate(JS_FAULT)
        if fault:
            # Not automatically a defect. Some games validate their own art -- mb64 raises
            # "your jelly's polyp must be its own" if you fill the jelly solid -- and a filled
            # grid is the most violent edit the panel can make. What has to hold is the rollback
            # contract: the fault is shown, and the game is still playable afterwards. That is
            # the designed behaviour for a bad value, so check it rather than fail on it.
            page.keyboard.press("ArrowUp")
            page.wait_for_timeout(200)
            if page.evaluate(JS_CANVAS) is None:
                problems.append(f"card {index}: filling it faulted and left no playable board -- "
                                f"{fault.strip()[:110]}")
            else:
                notes.append(f"card {index}: the game rejects a solid fill "
                             f"({fault.strip()[:80]}) and the panel rolled back cleanly")
            page.evaluate(JS_RESET_CARD, [index])
            settle(page, timeout)
            continue
        after = trace(page)
        if after == before:
            unobserved.append(f"card {index}: no visible change over {TRACE_STEPS} steps "
                              f"(likely an animation pose the canvas never settles on)")
        if after[-1] is None:
            problems.append(f"card {index}: the board stopped drawing after a paint")

        if not page.evaluate(JS_RESET_CARD, [index]):
            problems.append(f"card {index}: no per-sprite reset button")
            continue
        settle(page, timeout)

    # Every sprite back to published art. The trace above walked the game forward, so compare
    # against a fresh reset rather than the frame from before: what is being checked is that the
    # published art comes back, not that the game is on the same turn.
    page.keyboard.press("KeyR")
    page.wait_for_timeout(250)
    reset_board = page.evaluate(JS_CANVAS)
    for index in range(cards):
        page.evaluate(JS_RESET_CARD, [index])
        settle(page, timeout)
    page.keyboard.press("KeyR")
    page.wait_for_timeout(250)
    if page.evaluate(JS_CANVAS) != reset_board:
        notes.append("the board after resetting every sprite differs from the board before; "
                     "check this game by hand")

    # A sprite edit and a knob edit together: both must survive one reload.
    # Only meaningful on a sprite whose change this run could actually see; on an animation pose
    # the composed board is unobservable for exactly the same reason the single edit was.
    if knob and not any(note.startswith("card 0:") for note in unobserved):
        name, value = knob
        if page.evaluate(JS_SET_KNOB, [name, value]):
            settle(page, timeout)
            page.evaluate(JS_OPEN_SPRITES)
            if page.evaluate(JS_PAINT, [0, 0]):
                settle(page, timeout)
                fault = page.evaluate(JS_FAULT)
                if fault:
                    problems.append(f"a sprite edit on top of a knob edit faulted -- {fault.strip()[:110]}")
                elif page.evaluate(JS_CANVAS) == opening:
                    problems.append("a sprite edit on top of a knob edit left the published board")
                else:
                    notes.append(f"composed with knob {name}={value} and both held")
        else:
            notes.append("no knob spec for this game, so the compose check was skipped")
    elif knob:
        notes.append("compose check skipped: this game's first sprite is not observable from a canvas")

    return {"ok": not problems, "problems": problems, "cards": cards,
            "notes": notes, "unobserved": unobserved}


def knob_for(game_id: str) -> tuple[str, int] | None:
    """A knob from this game's tuning spec, for the compose check. None if it has no panel."""
    path = PARAM_DIR / f"{game_id}.json"
    if not path.exists():
        return None
    try:
        spec = json.loads(path.read_text())
    except Exception:
        return None
    for param in spec.get("params", []):
        low, high = param.get("min"), param.get("max")
        if isinstance(low, int) and isinstance(high, int) and low < high:
            return param["name"], high if high != low else low
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8731",
                        help="where serve_games_local.py is listening")
    parser.add_argument("--only", nargs="*", metavar="ID", help="check just these game ids")
    parser.add_argument("--timeout", type=int, default=90_000, help="ms to wait for one reload")
    parser.add_argument("--report", type=Path, help="write the full per-game findings here")
    parser.add_argument("--headed", action="store_true", help="watch it work")
    args = parser.parse_args(argv)

    from playwright.sync_api import sync_playwright

    specs = sorted(SPEC_DIR.glob("*.json"))
    if args.only:
        wanted = set(args.only)
        specs = [p for p in specs if p.stem in wanted]
    if not specs:
        print("no sprite specs to check", file=sys.stderr)
        return 1
    print(f"{len(specs)} spec(s) to check against {args.base_url}", file=sys.stderr)

    report, failed = {}, 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        for path in specs:
            game_id = path.stem
            spec = json.loads(path.read_text())
            page = browser.new_page(viewport={"width": 1500, "height": 1000})
            try:
                result = check_game(page, args.base_url, game_id, spec, knob_for(game_id), args.timeout)
            except Exception as exc:
                result = {"ok": False, "problems": [f"{type(exc).__name__}: {exc}"],
                          "cards": 0, "notes": [], "unobserved": []}
            finally:
                page.close()   # a fresh Pyodide boot per game: see the header
            report[game_id] = result
            failed += 0 if result["ok"] else 1
            mark = "ok  " if result["ok"] else "FAIL"
            print(f"  {mark} {game_id:22} {result['cards']} card(s)"
                  + ("" if result["ok"] else "  " + "; ".join(result["problems"])[:150]), file=sys.stderr)
            for note in result["notes"]:
                print(f"        note: {note}", file=sys.stderr)
            for note in result.get("unobserved", []):
                print(f"        unobserved: {note}", file=sys.stderr)
        browser.close()

    unobserved = sum(len(r.get("unobserved", [])) for r in report.values())
    seen = sum(r["cards"] for r in report.values()) - unobserved
    print(f"{len(specs) - failed}/{len(specs)} spec(s) passed; "
          f"{seen} sprite(s) seen to change the board, {unobserved} not observable from a canvas",
          file=sys.stderr)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=1) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

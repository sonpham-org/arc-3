#!/usr/bin/env python3
"""Turn every slider of every generated tuning spec in a real browser, and fail if one breaks.

Author: Claude Opus 5
Date: 20-September-2026
PURPOSE: The acceptance gate for docs/static/games/params/*.json. A spec is a claim about what a
player can be handed, and the only place that claim is true or false is the Games page running
Pyodide -- the ranges are measured in CPython by scripts/measure_game_params.py, which is a
different interpreter, a different arcengine build and a different numpy. This drives Chromium
over the play view and, for each spec, checks four things: every knob the spec declares actually
renders, every declared minimum and maximum loads without the panel reporting a fault, turning a
knob changes the board, and "Reset to defaults" puts the opening board back.

SRP/DRY check: Pass -- checking only. Specs are produced by measure_game_params.py and served by
serve_games_local.py; this reads the spec files and reports, and writes nothing to docs/.

Needs playwright, which is installed under python3.14 here -- not the 3.13 the generator needs
(arcengine and `match`). The two halves of the job genuinely run on two interpreters:

  python3.13 scripts/serve_games_local.py &                      # terminal 1
  python3.13 scripts/measure_game_params.py                      # write the specs
  python3.14 scripts/verify_game_params.py --report scratch/verify.json

Exit status is 1 if any spec failed, so it can gate a push.

One hard-won detail, in case this is ever made faster by reusing a page: every game gets a brand
new page and that page is closed after. Navigating by hash alone does not reload, and a run that
reused one page produced two false results at once -- slider counts belonging to the previous
game, and three games "failing" because an earlier game's unrecoverable rollback had wedged the
Pyodide worker for the rest of the session. A fresh Pyodide boot per game is the cost of a result
worth reading.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SPEC_DIR = REPO / "docs" / "static" / "games" / "params"

# Set a slider and tell the panel the drag is over, which is what makes it reload the game now
# rather than after its debounce.
JS_SET = """([name, value]) => {
  const slider = document.getElementById('tune-' + name);
  if (!slider) return false;
  slider.value = String(value);
  slider.dispatchEvent(new Event('change', {bubbles: true}));
  return true;
}"""
JS_CANVAS = "() => document.getElementById('gameCanvas').toDataURL()"
JS_FAULT = """() => {
  const msg = document.querySelector('#tuningPanel .tune-msg');
  return (msg && !msg.hidden && msg.classList.contains('tune-bad')) ? msg.textContent : null;
}"""
JS_IDLE = "() => !document.getElementById('tuningPanel').classList.contains('tune-busy')"


def settle(page, timeout: int) -> None:
    """Wait out the reload a knob just triggered."""
    page.wait_for_function(JS_IDLE, timeout=timeout)
    page.wait_for_timeout(150)


def set_knob(page, name: str, value: int, timeout: int) -> None:
    if not page.evaluate(JS_SET, [name, value]):
        raise AssertionError(f"{name}: the panel rendered no slider for it")
    settle(page, timeout)


def check(browser, base_url: str, game_id: str, spec: dict, timeout: int) -> dict:
    """One spec, on its own page. Returns the findings; raises nothing the caller must handle."""
    params = spec.get("params") or []
    result: dict = {"gameId": game_id, "declared": len(params), "faults": [], "ok": False}
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    try:
        page.goto(f"{base_url}/index.html#g={game_id}", wait_until="load")
        # A spec that declares nothing renders its note and no "Reset to defaults" button, so the
        # panel appearing is all there is to wait for. mc18 is that case on purpose: it keeps its
        # geometry in tuple-unpack form, which the patcher will not rewrite.
        page.wait_for_selector("#tuningPanel:not([hidden])" if not params
                               else "#tuningPanel .tune-reset", timeout=timeout)
        settle(page, timeout)

        if not params:
            result["rendered"] = page.locator("#tuningPanel input[type=range]").count()
            if result["rendered"]:
                result["faults"].append(f"spec declares no knobs but {result['rendered']} rendered")
            elif not page.locator("#tuningPanel .tune-note").count():
                result["faults"].append("no knobs and no note explaining why")
            result["ok"] = not result["faults"]
            return result

        rendered = page.locator("#tuningPanel input[type=range]").count()
        result["rendered"] = rendered
        if rendered != len(params):
            # The only check that the spec resolves against the source the browser really loaded.
            result["faults"].append(f"spec declares {len(params)} knobs, the panel rendered {rendered}")

        opening = page.evaluate(JS_CANVAS)
        result["board_is_blank"] = len(set(opening)) < 12
        if result["board_is_blank"]:
            result["faults"].append("the opening board is blank before anything is turned")

        moved = False
        for param in params:
            for edge in ("min", "max"):
                set_knob(page, param["name"], param[edge], timeout)
                fault = page.evaluate(JS_FAULT)
                if fault:
                    result["faults"].append(f"{param['name']} {edge}={param[edge]}: {fault.strip()[:140]}")
                if page.evaluate(JS_CANVAS) != opening:
                    moved = True
            # Back to the published value, so each knob is judged on its own.
            set_knob(page, param["name"], param["default"], timeout)
        result["a_knob_changed_the_board"] = moved
        if params and not moved:
            result["faults"].append("no knob changed the board at either end of its range")

        # Reset has to undo a moved knob, not merely repaint the sliders.
        set_knob(page, params[0]["name"], params[0]["max"], timeout)
        page.click("#tuningPanel .tune-reset")
        settle(page, timeout)
        result["reset_restores"] = page.evaluate(JS_CANVAS) == opening
        if not result["reset_restores"]:
            result["faults"].append("Reset to defaults did not bring the opening board back")
    except Exception as error:
        result["faults"].append(f"{type(error).__name__}: {str(error).splitlines()[0][:160]}")
    finally:
        page.close()
    result["ok"] = not result["faults"]
    return result


def rollback(browser, base_url: str, game_id: str, spec: dict, timeout: int) -> dict:
    """One value past a measured maximum -- the value CPython said breaks -- on its own page.

    This exercises games-tuning.js's rollback, not the spec, and it is the one step that can wedge
    a page badly enough to spoil whatever runs next, so it is kept apart and kept to a few games.
    """
    out: dict = {"gameId": game_id, "outcome": "no measured boundary broke in Pyodide"}
    page = browser.new_page()
    try:
        page.goto(f"{base_url}/index.html#g={game_id}", wait_until="load")
        page.wait_for_selector("#tuningPanel .tune-reset", timeout=timeout)
        settle(page, timeout)
        opening = page.evaluate(JS_CANVAS)
        for param in spec.get("params") or []:
            page.evaluate("""([name, value]) => {
              const slider = document.getElementById('tune-' + name);
              slider.max = String(value);
              slider.value = String(value);
              slider.dispatchEvent(new Event('change', {bubbles: true}));
            }""", [param["name"], param["max"] + 1])
            settle(page, timeout)
            fault = page.evaluate(JS_FAULT)
            if fault:
                restored = page.evaluate(JS_CANVAS) == opening
                out.update(at=f"{param['name']}={param['max'] + 1}", message=fault.strip()[:140],
                           outcome="rolled back" if restored else "reported, but the board was not restored")
                break
            set_knob(page, param["name"], param["default"], timeout)
    except Exception as error:
        out["outcome"] = f"{type(error).__name__}: {str(error).splitlines()[0][:140]}"
    finally:
        page.close()
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", nargs="*", metavar="ID", help="check just these game ids")
    parser.add_argument("--base", default="http://127.0.0.1:8731",
                        help="where serve_games_local.py is listening")
    parser.add_argument("--timeout", type=int, default=240_000, help="ms to allow one reload")
    parser.add_argument("--rollback", nargs="*", default=None, metavar="ID",
                        help="also check the panel's rollback on these games (a few is plenty)")
    parser.add_argument("--report", type=Path, help="write the full findings here")
    parser.add_argument("--headed", action="store_true", help="watch it work")
    args = parser.parse_args(argv)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not importable by this interpreter. Here it lives under "
              "python3.14: /opt/homebrew/opt/python@3.14/bin/python3.14", file=sys.stderr)
        return 2

    specs = {}
    for path in sorted(SPEC_DIR.glob("*.json")):
        spec = json.loads(path.read_text())
        if args.only and path.stem not in args.only:
            continue
        specs[path.stem] = spec
    if not specs:
        print("no specs to check", file=sys.stderr)
        return 2

    base = args.base.rstrip("/")
    findings: dict = {"base": base, "games": [], "rollback": []}
    failed = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed)
        for index, (game_id, spec) in enumerate(specs.items(), 1):
            started = time.time()
            result = check(browser, base, game_id, spec, args.timeout)
            result["seconds"] = round(time.time() - started, 1)
            findings["games"].append(result)
            if not result["ok"]:
                failed.append(game_id)
            mark = "ok  " if result["ok"] else "FAIL"
            print(f"[{index}/{len(specs)}] {mark} {game_id}: {result.get('rendered')} sliders, "
                  f"{result['seconds']}s", flush=True)
            for fault in result["faults"]:
                print(f"        {fault}", flush=True)

        for game_id in args.rollback or []:
            if game_id in specs and specs[game_id].get("params"):
                out = rollback(browser, base, game_id, specs[game_id], args.timeout)
                findings["rollback"].append(out)
                print(f"rollback {game_id}: {out['outcome']}"
                      f"{' at ' + out['at'] if out.get('at') else ''}", flush=True)
        browser.close()

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(findings, indent=1) + "\n")

    print(f"\n{len(specs) - len(failed)}/{len(specs)} specs pass in the browser")
    if failed:
        print(f"failed: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

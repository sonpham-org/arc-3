#!/usr/bin/env python3.13
"""
Author: Claude Opus 5 (Bubba)
Date: 17-September-2026
PURPOSE: Pull the account owner's ARC-3 scorecards from arcprize.org (cookie auth), fetch
per-card detail (which carries open_at/last_update — the REAL play timestamps, unlike the list
view's published_at batch-publish time), and emit a flat run list plus a per-game coverage
report. Exists because published_at lies: 117 zero-action opens were batch-published in one
second on 14-Sep-2026, so any date filter built on published_at silently promotes legacy
Jan/Feb plays into "September". Integration points: the runs JSON it writes is the input to
`tools/replay_scrape.py bulk --runs-file`, which turns those guids into recordings under
datasets/decision-steps/v0/recordings/.
SRP/DRY check: Pass — this is the only tool here that touches the AUTHENTICATED scorecard
surface (/api/user/scorecards). replay_scrape.py covers the public recordings/sessions
endpoints and never authenticates; the two do not overlap.

Auth
----
Reads a raw Cookie header from $ARC3_COOKIE_FILE, defaulting to
~/bubba-workspace/secrets/arcprize-boss-cookie.txt. The cookie is deliberately NOT stored in
this repo and must not be: nothing here is gitignored for secrets beyond `.env`, so a cookie
committed by a stray `git add -A` would be published to a repo with other collaborators.

Window limit
------------
/api/user/scorecards caps at 50 cards. `at` is a page SIZE, not a cursor — `at=50` re-serves
the same 50 — so this walks until it stops seeing new card_ids, which is one page. Cards that
fall off the bottom are the oldest. Check the open_at range this prints before concluding a
game was never played.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://arcprize.org"
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COOKIE = Path("~/bubba-workspace/secrets/arcprize-boss-cookie.txt").expanduser()
DEFAULT_OUT = REPO_ROOT / "datasets" / "decision-steps" / "scorecards"


def read_cookie(path: Path) -> str:
    if not path.exists():
        raise SystemExit(
            f"cookie file not found: {path}\n"
            "Set $ARC3_COOKIE_FILE or pass --cookie-file. The cookie is a raw Cookie header."
        )
    return path.read_text().strip().replace("\n", "")


def get(path: str, cookie: str, tries: int = 3) -> dict:
    request = urllib.request.Request(BASE + path, headers={
        "Cookie": cookie,
        "User-Agent": "arc-3-scorecard-inventory/0.1 (pull_boss_scorecards.py)",
        "Accept": "application/json",
    })
    last: Exception | None = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (401, 403):
                raise SystemExit(f"{path}: HTTP {exc.code} — the cookie is expired or wrong")
            time.sleep(2 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001 - retry anything transient
            last = exc
            time.sleep(2 * (attempt + 1))
    raise SystemExit(f"{path}: giving up after {tries} attempts ({last})")


def fetch_cards(cookie: str) -> list[dict]:
    cards: list[dict] = []
    seen: set[str] = set()
    at = 0
    while True:
        page = get(f"/api/user/scorecards?limit=50&at={at}", cookie)
        items = page.get("items") or []
        new = [card for card in items if card["card_id"] not in seen]
        seen.update(card["card_id"] for card in new)
        cards.extend(new)
        print(f"page at={at}: {len(items)} items, {len(new)} new, total {len(cards)}",
              file=sys.stderr)
        if not items or not new or len(items) < 50:
            break
        at += 50
        if at > 1000:
            break
    return cards


def fetch_runs(cards: list[dict], cookie: str) -> tuple[list[dict], list[dict]]:
    """Expand each card into one row per run, carrying the card's REAL timestamps."""
    runs: list[dict] = []
    failures: list[dict] = []
    for index, card in enumerate(cards, 1):
        card_id = card["card_id"]
        try:
            detail = get(f"/api/user/scorecards/{card_id}", cookie)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            failures.append({"card_id": card_id, "error": repr(exc)})
            continue
        for environment in detail.get("environments") or []:
            for run in environment.get("runs") or []:
                game_id = run.get("id") or environment.get("id") or ""
                runs.append({
                    "card": card_id,
                    "game_id": game_id,
                    "game": game_id[:4],
                    "guid": run.get("guid"),
                    "state": run.get("state"),
                    "levels": run.get("levels_completed"),
                    "actions": run.get("actions"),
                    "resets": run.get("resets"),
                    "score": run.get("score"),
                    "tags": detail.get("tags") or [],
                    "published_at": detail.get("published_at"),
                    "open_at": detail.get("open_at"),
                    "last_update": detail.get("last_update"),
                })
        if index % 10 == 0:
            print(f"  detail {index}/{len(cards)}", file=sys.stderr)
    return runs, failures


def is_real(run: dict) -> bool:
    """A run counts only if it took an action AND cleared a level.

    Both bars are load-bearing. `actions > 0` rejects the zero-action scorecard opens that the
    site creates just by loading a game. `levels > 0` rejects a poke that cleared nothing —
    without it, a 24-action 0-level open reads as "played" and a game silently leaves the
    needs-a-playthrough list.
    """
    return (run.get("actions") or 0) > 0 and (run.get("levels") or 0) > 0


def coverage(runs: list[dict], month: str | None) -> dict:
    """Per-game coverage: which games have a WIN, which were played and lost, which neither."""
    window = [r for r in runs if not month or (r.get("open_at") or "").startswith(month)]
    real = [r for r in window if is_real(r)]
    won: dict[str, list[dict]] = {}
    played: dict[str, list[dict]] = {}
    for run in real:
        played.setdefault(run["game"], []).append(run)
        if run.get("state") == "WIN":
            won.setdefault(run["game"], []).append(run)
    opens = [r["open_at"] for r in runs if r.get("open_at")]
    return {
        "month": month,
        "open_at_range": [min(opens), max(opens)] if opens else None,
        "runs_in_window": len(window),
        "real_runs": len(real),
        "won": sorted(won),
        "played_never_won": sorted(set(played) - set(won)),
        "detail": {game: sorted(rs, key=lambda r: -(r.get("levels") or 0))[:1]
                   for game, rs in played.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pull the account owner's ARC-3 scorecards and report per-game coverage.")
    parser.add_argument("--cookie-file", type=Path,
                        default=Path(os.environ.get("ARC3_COOKIE_FILE", DEFAULT_COOKIE)),
                        help="raw Cookie header file (default: $ARC3_COOKIE_FILE or %(default)s)")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT,
                        help="where to write cards/runs JSON (default: %(default)s)")
    parser.add_argument("--month", default=None,
                        help="restrict the coverage report to an open_at prefix, e.g. 2026-09")
    args = parser.parse_args()

    cookie = read_cookie(args.cookie_file.expanduser())
    cards = fetch_cards(cookie)
    runs, failures = fetch_runs(cards, cookie)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    cards_file = args.out_dir / f"cards-{stamp}.json"
    runs_file = args.out_dir / f"runs-{stamp}.json"
    cards_file.write_text(json.dumps(cards, indent=1))
    runs_file.write_text(json.dumps(runs, indent=1))

    print(json.dumps({
        "cards": len(cards), "runs": len(runs), "failures": failures,
        "cards_file": str(cards_file), "runs_file": str(runs_file),
        "coverage": coverage(runs, args.month),
    }, indent=1))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3.13
"""
Author: Claude Opus 5
Date: 18-September-2026
PURPOSE: Pull the human-curated write-ups of the 25 public ARC-AGI-3 games from arc-explainer
into datasets/explainer-games/games.json. Stdlib only (urllib), Python 3.13.

arc-explainer (shared/arc3Games/) is the ONLY place those write-ups are edited: the rules of
every level with the game-code lines they were checked against, the level pictures, Boss's
notes from play (saw / did / expected / happened), and Boss's scorecard runs with their replay
guids, which are the join key into datasets/decision-steps/v0/recordings/. This repo never
holds an edited copy; it fetches, and the fetched file is gitignored. Re-run to pick up
corrections.

Record shape (schema "arc-explainer/arc3-game/v1"): one document per game, with `levels[]`.
Each level has `images`, `newRules` (the rules that start on that level; the rules in force on
level N are the newRules of levels 1..N), `observations`, `arcBaselineActions` and `runs`
(Boss's runs that reached it). as66 is never in it: test-only here, never trained on.

The endpoint is private until Boss releases the dataset. It takes the arc3 admin token as
X-ARC3-Admin-Token, read from $ARC3_COMMUNITY_ADMIN_TOKEN, or on the Mac Mini from the login
keychain (service `arc3-community-admin-token`). The gx10 boxes need the env var set, or
fetch on the Mac Mini and let the file travel with the rest of the data.

Usage:
  python3.13 tools/fetch_explainer_games.py            # all 25 games
  python3.13 tools/fetch_explainer_games.py --game dc22 --out /tmp/dc22.json
SRP/DRY check: Pass -- fetch and write only. The data is built and owned by arc-explainer
(server/services/arc3/arc3GameDataset.ts); nothing here reshapes it.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "https://arc.markbarney.net/api/arc3/dataset"
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "datasets" / "explainer-games" / "games.json"
KEYCHAIN_SERVICE = "arc3-community-admin-token"


def read_token() -> str:
    token = os.environ.get("ARC3_COMMUNITY_ADMIN_TOKEN", "").strip()
    if token:
        return token
    if sys.platform == "darwin":
        result = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    sys.exit(
        "No token: set ARC3_COMMUNITY_ADMIN_TOKEN, or on the Mac Mini keep it in the login "
        f"keychain under service '{KEYCHAIN_SERVICE}'."
    )


def fetch(url: str, token: str) -> dict:
    request = urllib.request.Request(
        url, headers={"X-ARC3-Admin-Token": token, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.load(response)
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:300]
        sys.exit(f"{url} -> HTTP {err.code}: {detail}")
    except urllib.error.URLError as err:
        sys.exit(f"{url} -> {err.reason}")
    if not body.get("success"):
        sys.exit(f"{url} -> not a success envelope: {json.dumps(body)[:300]}")
    return body["data"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--game", help="one game id (e.g. dc22) instead of all 25")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    url = f"{args.base_url.rstrip('/')}/{args.game}" if args.game else args.base_url
    data = fetch(url, read_token())

    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(args.out.suffix + ".part")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(args.out)

    games = data.get("games", [data])
    rules = sum(len(level["newRules"]) for g in games for level in g["levels"])
    notes = sum(
        len(level["observations"]) for g in games for level in g["levels"]
    ) + sum(len(g["observationsAnyLevel"]) for g in games)
    print(f"{len(games)} games, {rules} rules, {notes} play notes -> {args.out}")


if __name__ == "__main__":
    main()

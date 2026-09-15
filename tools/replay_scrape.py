#!/usr/bin/env python3.13
"""
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Pull published ARC-3 human replay recordings off the live API into
datasets/decision-steps/v0/recordings/<game_id>/<guid>.ndjson, one raw API row per line,
byte-for-byte as the API served them. Step 3 of
docs/trace-findings/2026-09-14-decision-step-corpus-v0-plan.md. Also resolves a bare replay
guid to its game_id via /api/sessions/<guid>, which is the only way to build a recordings URL
for a guid harvested off the public replay pages. Stdlib only (urllib), Python 3.13.
Consumed by nothing yet: step 4 reads the NDJSON it writes, via
datasets/decision-steps/validate.py's frame_ref resolver.
SRP/DRY check: Pass — nothing in this repo fetched a replay before (plan §4(c): "No scrape
tooling exists in-repo"; the endpoint path forms existed only as prose in two trace-finding
docs). This file does not parse, reshape or validate record content — SCHEMA.md owns the
record contract and validate.py enforces it.

Rows are written VERBATIM
-------------------------
No normalising, no reshaping, no re-serialising at scrape time. The on-disk NDJSON is the
source of truth, so a downstream resolver bug never costs a 138 MB re-pull, and the row-count
acceptance criterion only means something if the rows are the API's own bytes. Consumers that
want "the frame" walk the dotted path data.frame and take the last grid — see
datasets/decision-steps/SCHEMA.md#frame-references.

This is NOT resumable
---------------------
The API ignores `Range` and serves the whole file regardless (observed 15-Sep-2026: a
`Range: bytes=0-1023` GET for the g50t recording returned status 200 and all 73,579,940
bytes — no 206, no Content-Range, no Accept-Ranges).
So there is no mid-file resume; an interrupted pull restarts from zero. What protects you is
that the download lands on `<guid>.ndjson.part` **in the destination directory** and is only
os.replace()d into place after it parses and its line count is known. A truncated file is
therefore never left behind looking complete. Re-running skips a target that already exists
and parses; --force re-pulls.
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

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RECORDINGS = REPO_ROOT / "datasets" / "decision-steps" / "v0" / "recordings"

# Verified by observation 15-Sep-2026, not inferred from the public replay URL:
#   GET https://three.arcprize.org/api/recordings/bp35-0a0ad940/c935ca1b-...  -> 138 MB, 1030 lines
#   GET https://three.arcprize.org/api/sessions/c935ca1b-...                  -> 200, run metadata
API_HOST = "https://three.arcprize.org"
USER_AGENT = "arc-3-decision-step-corpus/0.1 (replay_scrape.py)"

# The two known-good human wins, from plan §5. Row counts are what the docs recorded; the
# scraper REPORTS what it observed and never reconciles the two.
KNOWN_REPLAYS = [
    ("bp35-0a0ad940", "c935ca1b-dfee-4be1-9574-bf4cc80c5b89", 1030),
    ("g50t-5849a774", "4f0689d0-7d06-4be7-91ac-31cb9a800b85", 534),
]


class ScrapeError(RuntimeError):
    """A pull that failed in a way the caller should see, not a bug."""


def _request(url: str, timeout: int) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": USER_AGENT})


def _sleep_for_rate_limit(headers, attempt: int) -> float:
    """Seconds to wait before retrying, honouring the API's own rate-limit headers.

    The API sends x-ratelimit-limit / x-ratelimit-remaining / x-ratelimit-reset (unix
    seconds). Observed 120/hour-ish on 15-Sep-2026. Falls back to exponential backoff.
    """
    reset = headers.get("x-ratelimit-reset") if headers else None
    if reset:
        try:
            wait = float(reset) - time.time()
            if 0 < wait <= 900:
                return wait + 1
        except ValueError:
            pass
    return min(60.0, 2.0**attempt)


def fetch_bytes(url: str, timeout: int = 900, attempts: int = 4) -> bytes:
    """GET a URL, retrying on 429 and 5xx with rate-limit-aware backoff."""
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(_request(url, timeout), timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code == 429 or 500 <= exc.code < 600:
                if attempt + 1 == attempts:
                    break
                wait = _sleep_for_rate_limit(exc.headers, attempt)
                print(f"  {url}: HTTP {exc.code}, retrying in {wait:.0f}s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise ScrapeError(f"{url}: HTTP {exc.code} {exc.reason}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            if attempt + 1 == attempts:
                break
            time.sleep(min(60.0, 2.0**attempt))
    raise ScrapeError(f"{url}: giving up after {attempts} attempts ({last})")


def fetch_session(guid: str, timeout: int = 60) -> dict:
    """GET /api/sessions/<guid>.

    Verified live 15-Sep-2026 — this endpoint DOES exist on the recordings host and returns
    run metadata (game_id, state, levels_completed, actions, resets, score, published_at).
    It is the only published way to turn a bare replay guid into the game_id that the
    recordings path needs.
    """
    raw = fetch_bytes(f"{API_HOST}/api/sessions/{guid}", timeout=timeout)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ScrapeError(f"/api/sessions/{guid}: response is not JSON: {exc}") from exc


def game_ids_for_guid(session: dict, guid: str) -> list[str]:
    """Pull the game_id(s) this guid was played on out of a session document."""
    found: list[str] = []
    for environment in session.get("environments") or []:
        for run in environment.get("runs") or []:
            if run.get("guid") == guid and isinstance(run.get("id"), str):
                found.append(run["id"])
        if not found and isinstance(environment.get("id"), str):
            found.append(environment["id"])
    return sorted(set(found))


def count_rows(path: Path) -> int:
    """Line count, after proving every line is a JSON object and the file ends in a newline.

    This is the truncation guard. A 138 MB body cut short mid-line still looks like a file;
    it does not still parse.
    """
    data = path.read_bytes()
    if not data:
        raise ScrapeError(f"{path}: empty")
    if not data.endswith(b"\n"):
        raise ScrapeError(f"{path}: does not end in a newline — truncated download")
    rows = 0
    for index, line in enumerate(data.splitlines()):
        if not line.strip():
            raise ScrapeError(f"{path}: line {index} is blank; NDJSON rows must be one per line")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ScrapeError(f"{path}: line {index} is not valid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ScrapeError(f"{path}: line {index} is not a JSON object")
        rows += 1
    return rows


def scrape_recording(
    game_id: str,
    guid: str,
    recordings_dir: Path,
    *,
    expected_rows: int | None = None,
    force: bool = False,
    timeout: int = 900,
) -> tuple[Path, int, bool]:
    """Pull one recording. Returns (path, observed row count, whether it was downloaded)."""
    target = recordings_dir / game_id / f"{guid}.ndjson"
    if target.exists() and not force:
        rows = count_rows(target)
        print(f"  {target.name}: already on disk, {rows} rows — skipping (use --force to re-pull)")
        return target, rows, False

    target.parent.mkdir(parents=True, exist_ok=True)
    url = f"{API_HOST}/api/recordings/{game_id}/{guid}"
    print(f"  GET {url}")
    body = fetch_bytes(url, timeout=timeout)

    # .part lives in the destination directory so the replace is a same-filesystem rename,
    # which is the only kind that is atomic.
    part = target.with_name(target.name + ".part")
    part.write_bytes(body)
    try:
        rows = count_rows(part)
    except ScrapeError:
        part.unlink(missing_ok=True)
        raise
    os.replace(part, target)

    size_mb = len(body) / (1024 * 1024)
    note = ""
    if expected_rows is not None:
        note = " (matches expected)" if rows == expected_rows else f" — EXPECTED {expected_rows}"
    print(f"  wrote {target} — {size_mb:.1f} MB, {rows} rows{note}")
    return target, rows, True


def cmd_known(args: argparse.Namespace) -> int:
    """Re-pull the two known-good human replays named in plan §5."""
    failures = 0
    for game_id, guid, expected in KNOWN_REPLAYS:
        print(f"{game_id} / {guid}")
        try:
            _, rows, _ = scrape_recording(
                game_id, guid, args.recordings_dir, expected_rows=expected,
                force=args.force, timeout=args.timeout,
            )
        except ScrapeError as exc:
            print(f"  FAILED: {exc}", file=sys.stderr)
            failures += 1
            continue
        # Report, never reconcile. A mismatch is a finding about the doc or the API, and it
        # is not this tool's job to decide which.
        if rows != expected:
            print(
                f"  MISMATCH: observed {rows} rows, docs recorded {expected}. "
                f"Reported as observed; not reconciled.",
                file=sys.stderr,
            )
            failures += 1
    return 1 if failures else 0


def cmd_guid(args: argparse.Namespace) -> int:
    """Resolve each guid to its game_id via /api/sessions, then pull the recording."""
    failures = 0
    for guid in args.guids:
        print(f"{guid}")
        try:
            session = fetch_session(guid, timeout=args.timeout)
        except ScrapeError as exc:
            print(f"  FAILED: {exc}", file=sys.stderr)
            failures += 1
            continue
        game_ids = game_ids_for_guid(session, guid)
        if not game_ids:
            print(f"  FAILED: /api/sessions/{guid} named no game_id", file=sys.stderr)
            failures += 1
            continue
        print(f"  tags={session.get('tags')} published_at={session.get('published_at')}")
        for game_id in game_ids:
            try:
                scrape_recording(
                    game_id, guid, args.recordings_dir,
                    force=args.force, timeout=args.timeout,
                )
            except ScrapeError as exc:
                print(f"  FAILED: {exc}", file=sys.stderr)
                failures += 1
    return 1 if failures else 0


def cmd_session(args: argparse.Namespace) -> int:
    """Print the /api/sessions document for a guid. Downloads nothing."""
    failures = 0
    for guid in args.guids:
        try:
            print(json.dumps(fetch_session(guid, timeout=args.timeout), indent=2))
        except ScrapeError as exc:
            print(f"{guid}: FAILED: {exc}", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pull ARC-3 published replay recordings into the decision-step corpus.",
        epilog="Recordings are 70-140 MB apiece and gitignored. Never git add -f one.",
    )
    parser.add_argument(
        "--recordings-dir", type=Path, default=DEFAULT_RECORDINGS,
        help="destination root (default: %(default)s)",
    )
    parser.add_argument("--force", action="store_true", help="re-pull even if the file exists")
    parser.add_argument("--timeout", type=int, default=900, help="per-request timeout, seconds")
    sub = parser.add_subparsers(dest="command", required=True)

    known = sub.add_parser("known", help="re-pull the two known-good human replays (plan §5)")
    known.set_defaults(func=cmd_known)

    guid = sub.add_parser("guid", help="resolve guid(s) via /api/sessions, then pull")
    guid.add_argument("guids", nargs="+")
    guid.set_defaults(func=cmd_guid)

    session = sub.add_parser("session", help="print /api/sessions/<guid>; downloads nothing")
    session.add_argument("guids", nargs="+")
    session.set_defaults(func=cmd_session)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

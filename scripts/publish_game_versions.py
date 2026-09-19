#!/usr/bin/env python3
"""Publish game versions to the Games page's evolution trees, and read back player feedback.

Like scripts/publish_railway_data.py for traces: this talks to the Railway API with
ARC3_PUBLISH_TOKEN, never changes Git, and never needs a site deploy. A version is one exact
game source, stored immutably as "<game_id>@<first 12 hex of its sha256>".

  sync      Upload every game in docs/static/games/manifest.json with its history, rebuilt
            from this repo's git log: each commit that changed a game's source becomes a
            version, its subject becomes the reason, and a Co-Authored-By trailer or the
            file's "Author:" header says whether GPT or Claude made it. Idempotent: versions
            the API already holds are skipped, so re-run it after any change to
            docs/static/games/src/.

  publish   Upload ONE new version. This is the call to make every time GPT, Claude or a
            person evolves a game, with the main reason for the change:

              python scripts/publish_game_versions.py publish --game g009 \\
                  --source path/to/g009.py --author claude --model "Claude Opus 5" \\
                  --reason "Walls now show which side is sticky"

            A known game id becomes a revision of its latest version. A new id with --parent
            becomes a branch (a new game grown from that version), or --kind revision for the
            same game under a new id (q041-v1 -> q041-v2). A new id with no parent is a seed.

  feedback  Download reviews as JSON lines (team reviews first within each version), for the
            next evolution pass: python scripts/publish_game_versions.py feedback --game g009

Thumbnails are the game's reset frame, rendered locally with `arcengine` + Pillow (as
scripts/build_games_manifest.py does); without them a version still publishes, thumbnail-less.
"""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import http.client
import io
import json
import multiprocessing
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

try:
    from .publish_railway_data import ApiError, api_connection, decode_response, resolve_publish_token
except ImportError:  # Direct script execution adds scripts/ to sys.path.
    from publish_railway_data import ApiError, api_connection, decode_response, resolve_publish_token


REPO = Path(__file__).resolve().parents[1]
DEFAULT_API_URL = "https://arc3.sonpham.net"
SRC_ROOT = "docs/static/games/src"
GAME_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
BLIND_FAMILIES = {"arena", "contributed-glowup"}
# Categories kept in manifest.json (arc-explainer mirrors them) but not published to the Games
# page's trees. "ai-generated" is the 571 unreviewed generator games ("Fresh off the pipeline"
# on arc.markbarney.net), taken off the page on 19-Sep-2026. docs/static/js/games-api.js
# drops the same list from its static fallback.
RETIRED_FAMILIES = {"ai-generated"}


def family_of(row: dict[str, Any]) -> str:
    return row.get("category") or ("official" if row.get("official") else "custom")


def select_games(manifest: list[dict[str, Any]], games: str | None, families: str | None) -> list[dict[str, Any]]:
    """The manifest rows `sync` publishes: named ids or named categories if given (a retired
    category is published only when asked for by name), otherwise everything not retired."""

    rows = manifest
    if games:
        wanted = set(games.split(","))
        rows = [row for row in rows if row["id"] in wanted]
    if families:
        wanted_families = set(families.split(","))
        rows = [row for row in rows if family_of(row) in wanted_families]
    elif not games:
        rows = [row for row in rows if family_of(row) not in RETIRED_FAMILIES]
    return rows
# Same palette as build_games_manifest.py / games-play.js, so thumbnails match play.
PALETTE = [
    (255, 255, 255), (204, 204, 204), (153, 153, 153), (102, 102, 102),
    (51, 51, 51), (0, 0, 0), (229, 58, 163), (255, 123, 204),
    (249, 60, 49), (30, 147, 255), (136, 216, 241), (255, 220, 0),
    (255, 133, 27), (146, 18, 49), (79, 204, 48), (163, 86, 214),
]


# ── Who made a version ───────────────────────────────────────────────────────

TRAILER_RE = re.compile(r"^co-authored-by:\s*(?P<name>[^<\n]+?)\s*<(?P<email>[^>\n]*)>\s*$", re.I | re.M)
HEADER_AUTHOR_RE = re.compile(r"^\s*#?\s*Author:\s*(?P<who>.+?)\s*$", re.M)


def classify_model(text: str) -> str | None:
    lowered = text.lower()
    if "claude" in lowered or "anthropic" in lowered:
        return "claude"
    if re.search(r"\b(gpt|codex|openai)", lowered):
        return "gpt"
    return None


def model_name(text: str) -> str:
    # "Claude Fable 5.1 (spill chamber ...; original game by Claude Opus 5)" -> "Claude Fable 5.1"
    head = text.split("(", 1)[0].strip().rstrip(",;")
    if not head and "(" in text:  # "(Codex GPT-6)" style: keep what is inside
        head = text.strip("() ")
    if head.lower() == "codex":  # "Codex (GPT-6)": the model is in the brackets
        inner = re.search(r"\(([^)]+)\)", text)
        head = f"Codex ({inner.group(1).strip()})" if inner else "Codex"
    return head[:120]


def trailer_author(body: str) -> dict[str, Any] | None:
    for match in TRAILER_RE.finditer(body or ""):
        kind = classify_model(f"{match.group('name')} {match.group('email')}")
        if kind:
            return {"kind": kind, "model": model_name(match.group("name"))}
    return None


def header_author(source_head: str) -> dict[str, Any] | None:
    header = HEADER_AUTHOR_RE.search(source_head or "")
    if header:
        kind = classify_model(header.group("who"))
        if kind:
            return {"kind": kind, "model": model_name(header.group("who"))}
    return None


# Games we did not make. Their first version is credited to where they came from, not to
# whoever (or whichever co-author) committed the import.
IMPORTED_FAMILIES = {
    "official": ({"kind": "human", "model": None}, "ARC Prize Foundation", "Official ARC-AGI-3 public game"),
    "redbluepill": (
        {"kind": "other", "model": None},
        "theredbluepill/arc-interactive",
        "Imported from the Red Blue Pill community catalog",
    ),
}


def infer_author(
    body: str,
    source_head: str,
    *,
    seed: bool,
    focused: bool,
    metadata: dict | None = None,
) -> dict[str, Any]:
    """GPT, Claude, or unknown, from the best evidence for this exact version.

    A revision: the commit's Co-Authored-By trailer, then the file's "Author:" header.
    A seed: the research metadata's authorship block, then the header, then the trailer, but
    the trailer only when the commit was about this game (`focused`), since a bulk import's
    co-author is whoever ran the import, not whoever made the game."""

    if seed:
        candidates = [metadata, header_author(source_head), trailer_author(body) if focused else None]
    else:
        candidates = [trailer_author(body), header_author(source_head)]
    for candidate in candidates:
        if candidate and candidate.get("kind"):
            return candidate
    return {"kind": "unknown", "model": None}


def split_commit_message(message: str) -> tuple[str, str | None]:
    """(subject, details) with trailers dropped; the subject is the version's reason."""

    lines = (message or "").strip().splitlines()
    subject = (lines[0] if lines else "").strip()
    subject = re.sub(r"^Games tab:\s*", "", subject) or "Published"
    body = [
        line
        for line in lines[1:]
        if not re.match(r"^\s*(co-authored-by|signed-off-by|generated with)\b", line, re.I)
        and "Claude Code" not in line
    ]
    details = "\n".join(body).strip() or None
    return subject[:500], (details[:20000] if details else None)


# ── Sources: class, file name, thumbnail ─────────────────────────────────────


def find_game_class(source: str) -> str | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", None)
                if name == "ARCBaseGame":
                    return node.name
    return None


def render_reset_frame(job: tuple[str, str]) -> tuple[bytes | None, int | None, str | None]:
    """Worker: exec one game source, press RESET, return (png, tile_scale, error)."""

    source, class_name = job
    try:
        from arcengine import ActionInput, GameAction
        from PIL import Image

        namespace = {"__name__": "arc_game_module", "__file__": f"{class_name}.py"}
        exec(compile(source, f"{class_name}.py", "exec"), namespace)
        game = namespace[class_name]()
        frame = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
        camera = game.camera
        tile_scale = min(64 // max(1, camera.width), 64 // max(1, camera.height))
        grid = frame.frame[-1]
        rows, cols = grid.shape
        image = Image.new("RGB", (cols, rows))
        image.putdata([PALETTE[max(0, min(15, int(value)))] for row in grid for value in row])
        out = io.BytesIO()
        image.save(out, format="PNG", optimize=True)
        return out.getvalue(), max(1, tile_scale), None
    except BaseException as exc:  # a broken historical build must not stop the sync
        return None, None, f"{type(exc).__name__}: {exc}"[:300]


class Renderer:
    """Renders thumbnails in worker processes, so a game that hangs on RESET is killed after
    `timeout` seconds instead of stalling the whole sync."""

    def __init__(self, enabled: bool, workers: int = 4, timeout: float = 60):
        self.enabled = enabled
        self.workers = workers
        self.timeout = timeout
        self.pool = None
        if enabled:
            try:
                import arcengine  # noqa: F401
                import PIL  # noqa: F401
            except ImportError as exc:
                print(f"thumbnails disabled ({exc}); install arcengine + Pillow to render them", file=sys.stderr)
                self.enabled = False

    def render_many(self, jobs: list[tuple[str, str]]) -> list[tuple[bytes | None, int | None, str | None]]:
        if not self.enabled:
            return [(None, None, "thumbnails disabled")] * len(jobs)
        results: list[Any] = [None] * len(jobs)
        todo = list(range(len(jobs)))
        while todo:
            pool = multiprocessing.get_context("spawn").Pool(self.workers)
            pending = {index: pool.apply_async(render_reset_frame, (jobs[index],)) for index in todo}
            todo = []
            hung = False
            for index, future in pending.items():
                if hung:
                    todo.append(index)
                    continue
                try:
                    results[index] = future.get(timeout=self.timeout)
                except multiprocessing.TimeoutError:
                    results[index] = (None, None, f"timed out after {self.timeout:.0f}s")
                    hung = True  # kill the pool (and the stuck game), retry the rest
            pool.terminate()
            pool.join()
        return results


# ── Git history of this repo's published sources ────────────────────────────


@dataclass
class Version:
    game_id: str
    blob: str
    source: bytes
    commit: str
    date: datetime
    author_name: str
    message: str
    path: str
    sha256: str = ""
    version_id: str = ""
    reason: str = ""
    details: str | None = None
    author: dict[str, Any] = field(default_factory=dict)


def git(*args: str, input_bytes: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        input=input_bytes,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def read_blobs(blobs: list[str]) -> dict[str, bytes]:
    """Blob contents exactly as committed (LF endings, never a CRLF checkout), in one call."""

    if not blobs:
        return {}
    output = git("cat-file", "--batch", input_bytes=("\n".join(blobs) + "\n").encode())
    contents: dict[str, bytes] = {}
    offset = 0
    for blob in blobs:
        header_end = output.index(b"\n", offset)
        _sha, _kind, size = output[offset:header_end].decode().split()
        start = header_end + 1
        contents[blob] = output[start : start + int(size)]
        offset = start + int(size) + 1
    return contents


def history(manifest: list[dict[str, Any]]) -> dict[str, list[Version]]:
    """Every distinct committed source of every manifest game, oldest first."""

    wanted = {f"{SRC_ROOT}/{entry['id']}/{entry['src_file']}": entry["id"] for entry in manifest}
    log = git(
        "log", "--reverse", "--no-renames", "--raw", "--no-abbrev",
        "--format=%x1e%H%x1f%cI%x1f%an%x1f%B%x1d", "--", SRC_ROOT,
    ).decode("utf-8", errors="replace")
    found: dict[str, list[Version]] = {}
    for chunk in log.split("\x1e")[1:]:
        header, _, raw = chunk.partition("\x1d")
        commit, date, author_name, message = header.split("\x1f", 3)
        for line in raw.splitlines():
            match = re.match(r"^:\d+ \d+ [0-9a-f]+ ([0-9a-f]{40}) ([AM])\t(.+)$", line.strip())
            if not match or match.group(3) not in wanted:
                continue
            game_id = wanted[match.group(3)]
            found.setdefault(game_id, []).append(
                Version(
                    game_id=game_id,
                    blob=match.group(1),
                    source=b"",
                    commit=commit,
                    date=datetime.fromisoformat(date),
                    author_name=author_name,
                    message=message,
                    path=match.group(3),
                )
            )
    contents = read_blobs(sorted({version.blob for versions in found.values() for version in versions}))
    for versions in found.values():
        for version in versions:
            version.source = contents[version.blob]
            version.sha256 = hashlib.sha256(version.source).hexdigest()
            version.version_id = f"{version.game_id}@{version.sha256[:12]}"
    return found


def research_authorship(game_id: str) -> dict[str, Any] | None:
    path = REPO / "research" / "games" / f"{game_id}.json"
    if not path.is_file():
        return None
    try:
        authorship = json.loads(path.read_text(encoding="utf-8")).get("authorship") or {}
    except (OSError, json.JSONDecodeError):
        return None
    family = authorship.get("model_family") or ""
    kind = classify_model(family)
    return {"kind": kind, "model": family[:120] or None} if kind else None


# ── API ──────────────────────────────────────────────────────────────────────


def request(args: argparse.Namespace, method: str, path: str, token: str, body: dict | None = None) -> dict | str:
    """One API call, retried on connection errors and 502/503/504 like the trace publisher."""

    payload = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "arc3-game-publisher/1", "Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(payload))
    for attempt in range(1, args.attempts + 1):
        connection, prefix = api_connection(args.api_url, args.timeout)
        try:
            connection.request(method, f"{prefix}{path}", body=payload, headers=headers)
            response = connection.getresponse()
            data = decode_response(response)
        except (OSError, http.client.HTTPException):
            if attempt == args.attempts:
                raise
        else:
            if response.status < 400:
                return data
            if response.status not in (502, 503, 504) or attempt == args.attempts:
                raise ApiError(response.status, data)
        finally:
            connection.close()
        time.sleep(min(2 ** (attempt - 1), 8))
    raise AssertionError("unreachable")


def game_entry(manifest_row: dict[str, Any]) -> dict[str, Any]:
    family = family_of(manifest_row)
    entry = {"game_id": manifest_row["id"], "family": family, "default_fps": manifest_row.get("default_fps")}
    if family not in BLIND_FAMILIES:
        entry.update(
            {
                "title": manifest_row.get("title"),
                "description": manifest_row.get("description"),
                "tags": manifest_row.get("tags") or [],
            }
        )
    return entry


# ── Commands ─────────────────────────────────────────────────────────────────


def cmd_sync(args: argparse.Namespace) -> int:
    manifest = json.loads((REPO / "docs" / "static" / "games" / "manifest.json").read_text(encoding="utf-8"))
    manifest = select_games(manifest, args.games, args.families)
    by_id = {row["id"]: row for row in manifest}
    found = history(manifest)
    missing = sorted(set(by_id) - set(found))
    if missing:
        print(f"no committed source for {len(missing)} game(s): {', '.join(missing[:10])}", file=sys.stderr)

    token = "" if args.dry_run else resolve_publish_token(args)
    known: dict[str, set[str]] = {}
    if not args.dry_run and not args.update_notes:
        listing = request(args, "GET", "/api/v1/games/publication", token)
        known = {gid: set(shas) for gid, shas in (listing.get("games") or {}).items()} if isinstance(listing, dict) else {}

    games_per_commit: dict[str, int] = {}
    for versions in found.values():
        for version in versions:
            games_per_commit[version.commit] = games_per_commit.get(version.commit, 0) + 1

    plan: list[tuple[dict[str, Any], dict[str, Any], Version]] = []
    for game_id in sorted(found, key=lambda gid: found[gid][0].date):
        versions = found[game_id]
        entry = game_entry(by_id[game_id])
        imported = IMPORTED_FAMILIES.get(entry["family"])
        previous_id = None
        previous_date = None
        seen: set[str] = set()
        for version in versions:
            if version.sha256 in seen:
                # A revert back to an earlier source: that version already exists, so later
                # versions simply descend from it, which is what happened.
                previous_id = version.version_id
                continue
            seen.add(version.sha256)
            seed = previous_id is None
            head_text = version.source[:4000].decode("utf-8", errors="replace")
            version.reason, version.details = split_commit_message(version.message)
            author_name = version.author_name
            if seed and imported:
                version.author, author_name, version.reason = imported
            else:
                version.author = infer_author(
                    version.message,
                    head_text,
                    seed=seed,
                    focused=games_per_commit[version.commit] <= 3,
                    metadata=research_authorship(game_id) if seed else None,
                )
            created = version.date.astimezone(timezone.utc)
            if previous_date and created <= previous_date:
                created = previous_date + timedelta(seconds=1)  # rebased history: keep order
            previous_date = created
            payload = {
                "sha256": version.sha256,
                "src_file": by_id[game_id]["src_file"],
                "class_name": find_game_class(version.source.decode("utf-8", errors="replace"))
                or by_id[game_id]["class_name"],
                "parent_version_id": previous_id,
                "kind": "seed" if seed else "revision",
                "created_at": created.isoformat().replace("+00:00", "Z"),
                "author": {**version.author, "name": author_name},
                "reason": version.reason,
                "details": version.details,
                "origin": "git-sync",
                "provenance": {"repo": "sonpham-org/arc-3", "commit": version.commit, "path": version.path},
            }
            previous_id = version.version_id
            if version.sha256 in known.get(game_id, set()):
                continue
            plan.append((entry, payload, version))

    print(
        json.dumps(
            {
                "games": len(found),
                "versions": sum(len(v) for v in found.values()),
                "toUpload": len(plan),
                "withHistory": sum(1 for v in found.values() if len({x.sha256 for x in v}) > 1),
                "dryRun": args.dry_run,
            }
        )
    )
    if args.limit:
        plan = plan[: args.limit]
    if args.dry_run:
        for entry, payload, _version in plan[: args.show]:
            print(
                f"  {payload['created_at'][:10]}  {entry['game_id']:<14} {payload['kind']:<8} "
                f"{payload['author']['kind']:<7} {payload['reason'][:70]}"
            )
        return 0

    renderer = Renderer(not args.no_thumbnails, workers=args.workers)
    published = unchanged = failed = 0
    for start in range(0, len(plan), args.batch):
        batch = plan[start : start + args.batch]
        thumbs = renderer.render_many(
            [(v.source.decode("utf-8", errors="replace"), p["class_name"]) for _e, p, v in batch]
        )
        for (entry, payload, version), (png, tile_scale, error) in zip(batch, thumbs):
            body = dict(payload)
            body["source_b64"] = base64.b64encode(version.source).decode("ascii")
            if png:
                body["thumb_png_b64"] = base64.b64encode(png).decode("ascii")
                body["tile_scale"] = tile_scale
            elif error and args.verbose:
                print(f"  thumbnail {version.version_id}: {error}", file=sys.stderr)
            try:
                result = request(
                    args, "PUT", "/api/v1/games/publication", token,
                    {"game": entry, "version": body, "update_notes": args.update_notes},
                )
            except ApiError as exc:
                failed += 1
                print(f"  FAILED {version.version_id}: {exc}", file=sys.stderr)
                continue
            status = result.get("status") if isinstance(result, dict) else "?"
            published += status == "published"
            unchanged += status in ("unchanged", "updated")
        print(f"  {min(start + args.batch, len(plan))}/{len(plan)} uploaded", flush=True)
    print(json.dumps({"published": published, "unchanged": unchanged, "failed": failed}))
    return 1 if failed else 0


def cmd_publish(args: argparse.Namespace) -> int:
    if not GAME_ID_RE.fullmatch(args.game):
        raise SystemExit("--game must be letters, digits, dot, underscore or dash")
    source = Path(args.source).read_bytes()
    if not args.keep_crlf:
        source = source.replace(b"\r\n", b"\n")  # hash what git would store
    text = source.decode("utf-8")
    class_name = args.class_name or find_game_class(text)
    if not class_name:
        raise SystemExit(f"{args.source}: no ARCBaseGame subclass found; pass --class-name")
    src_file = args.src_file or f"{args.game.split('-')[0]}.py"
    entry: dict[str, Any] = {"game_id": args.game}
    for key, value in (
        ("family", args.family),
        ("title", args.title),
        ("description", args.description),
        ("default_fps", args.fps),
    ):
        if value is not None:
            entry[key] = value
    if args.tags is not None:
        entry["tags"] = [tag.strip() for tag in args.tags.split(",") if tag.strip()]
    version: dict[str, Any] = {
        "sha256": hashlib.sha256(source).hexdigest(),
        "src_file": src_file,
        "class_name": class_name,
        "author": {"kind": args.author, "model": args.model, "name": args.name},
        "reason": args.reason,
        "details": args.details,
        "origin": "publish-cli",
        "provenance": {"source": Path(args.source).name, **({"commit": args.commit} if args.commit else {})},
    }
    if args.parent:
        version["parent_version_id"] = args.parent
    if args.kind:
        version["kind"] = args.kind
    if args.created_at:
        version["created_at"] = args.created_at
    png = tile_scale = None
    if not args.no_thumbnail:
        png, tile_scale, error = Renderer(True, workers=1).render_many([(text, class_name)])[0]
        if error:
            print(f"thumbnail not rendered: {error}", file=sys.stderr)
    if png:
        version["thumb_png_b64"] = base64.b64encode(png).decode("ascii")
        version["tile_scale"] = tile_scale
    summary = {k: v for k, v in version.items() if k not in ("thumb_png_b64",)}
    print(json.dumps({"game": entry, "version": summary, "thumbnail": bool(png)}, indent=1))
    if args.dry_run:
        return 0
    version["source_b64"] = base64.b64encode(source).decode("ascii")
    token = resolve_publish_token(args)
    result = request(args, "PUT", "/api/v1/games/publication", token, {"game": entry, "version": version})
    print(json.dumps(result, indent=1))
    return 0


def cmd_feedback(args: argparse.Namespace) -> int:
    query = {
        key: value
        for key, value in (("since", args.since), ("game_id", args.game), ("tree_id", args.tree))
        if value
    }
    token = resolve_publish_token(args)
    connection, prefix = api_connection(args.api_url, args.timeout)
    path = f"{prefix}/api/v1/games/feedback-export" + (f"?{urlencode(query)}" if query else "")
    try:
        connection.request("GET", path, headers={"Authorization": f"Bearer {token}", "User-Agent": "arc3-game-publisher/1"})
        response = connection.getresponse()
        body = response.read()
    finally:
        connection.close()
    if response.status != 200:
        raise ApiError(response.status, body.decode("utf-8", errors="replace"))
    if args.out:
        Path(args.out).write_bytes(body)
        reviews = body.count(b"\n")
        print(f"{reviews} review(s) -> {args.out}")
    else:
        sys.stdout.write(body.decode("utf-8"))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api-url", default=os.environ.get("ARC3_API_URL", DEFAULT_API_URL))
    parser.add_argument("--railway-cwd", type=Path, default=REPO)
    parser.add_argument("--railway-bin", default=os.environ.get("RAILWAY_BIN", "railway"))
    parser.add_argument("--service", default="arc3-viewer")
    parser.add_argument("--environment", default="production")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--attempts", type=int, default=3)
    commands = parser.add_subparsers(dest="command", required=True)

    sync = commands.add_parser("sync", help="upload the catalog's games with their git history")
    sync.add_argument("--games", help="comma-separated game ids (default: the whole manifest)")
    sync.add_argument(
        "--families",
        help="comma-separated categories, e.g. arena,custom (default: all but the retired ai-generated set)",
    )
    sync.add_argument("--limit", type=int, default=0, help="upload at most this many versions")
    sync.add_argument("--batch", type=int, default=40)
    sync.add_argument("--workers", type=int, default=4, help="thumbnail render processes")
    sync.add_argument("--no-thumbnails", action="store_true")
    sync.add_argument("--update-notes", action="store_true", help="re-send reasons/authors of existing versions")
    sync.add_argument("--dry-run", action="store_true")
    sync.add_argument("--show", type=int, default=60, help="plan rows to print with --dry-run")
    sync.add_argument("--verbose", action="store_true")

    publish = commands.add_parser("publish", help="upload one new version of a game")
    publish.add_argument("--game", required=True)
    publish.add_argument("--source", required=True, help="the game's single-file .py source")
    publish.add_argument("--reason", required=True, help="the main reason for this change, one line")
    publish.add_argument("--author", required=True, choices=("gpt", "claude", "human", "other"))
    publish.add_argument("--model", help='e.g. "Claude Opus 5", "GPT-6 (Codex)"')
    publish.add_argument("--name", help="who ran it (person or bot)")
    publish.add_argument("--details", help="longer notes")
    publish.add_argument("--parent", help="version id to descend from: <game_id>@<12 hex>")
    publish.add_argument("--kind", choices=("revision", "branch"))
    publish.add_argument("--family", help="category for a brand-new game (arena, custom, ai-generated, ...)")
    publish.add_argument("--title")
    publish.add_argument("--description")
    publish.add_argument("--tags", help="comma-separated")
    publish.add_argument("--fps", type=int)
    publish.add_argument("--src-file", help="served file name (default <code>.py)")
    publish.add_argument("--class-name")
    publish.add_argument("--created-at", help="ISO-8601 with timezone (default: now)")
    publish.add_argument("--commit", help="git commit the source came from, for provenance")
    publish.add_argument("--keep-crlf", action="store_true")
    publish.add_argument("--no-thumbnail", action="store_true")
    publish.add_argument("--dry-run", action="store_true")

    feedback = commands.add_parser("feedback", help="download reviews as JSON lines")
    feedback.add_argument("--since", help="ISO-8601; only reviews after this time")
    feedback.add_argument("--game")
    feedback.add_argument("--tree")
    feedback.add_argument("--out")

    args = parser.parse_args(argv)
    args.railway_cwd = args.railway_cwd.resolve()
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return {"sync": cmd_sync, "publish": cmd_publish, "feedback": cmd_feedback}[args.command](args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ApiError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

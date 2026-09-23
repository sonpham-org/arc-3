"""Game evolution trees and human feedback for the Games page.

The route prefix decides who is calling, and every handler below trusts nothing else:

  /api/v1/public/games/...         anyone. oauth2-proxy skips auth here, so identity headers
                                   are never read, and change notes / feedback text are never
                                   returned. Public feedback is accepted, rate limited, and
                                   stored as reviewer_class = 'public'.
  /api/v1/games/...                the signed-in team. oauth2-proxy authenticates the request
                                   and injects X-Forwarded-Email, which becomes the reviewer.
                                   Team feedback is always ranked ahead of public feedback.
  /api/v1/games/publication        machines holding ARC3_PUBLISH_TOKEN: upload one game
                                   version (source + thumbnail + reason). No site deploy.
  /api/v1/games/feedback-export    machines holding ARC3_PUBLISH_TOKEN: feedback as JSON
                                   lines, for whatever GPT/Claude loop writes the next version.
  /api/v1/games/ideas/publication  machines holding ARC3_PUBLISH_TOKEN: add or refresh game
                                   ideas for the ideas board, in bulk.

A version is immutable and content-addressed: version_id = "<game_id>@<sha12>", where sha12
is the first 12 hex of sha256(source bytes). That is the same stamp arc-explainer records as
`source_version`, so a review on either site names the same build. Sources and thumbnails
are written to the Railway volume under <data_root>/_games/<game_id>/<sha12>/, which Caddy
serves at /data/_games/ (a run id cannot start with "_", so the two never collide).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import parse_qs, unquote, urlparse


GAME_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
VERSION_ID_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]{0,99})@([0-9a-f]{12})$")
FAMILY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
SRC_FILE_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}\.py$")
CLASS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,99}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
VISITOR_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")
EMAIL_RE = re.compile(r"^[^\s@]{1,200}@[^\s@]{1,200}$")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# Who primarily drove a version (19-Sep-2026 definitions): "gpt" = GPT was the primary
# driver, "claude" = Claude was, "human" = a person actively tuned it. "other" is for imports
# made elsewhere (the community catalog), "unknown" when nobody recorded it.
AUTHOR_KINDS = ("gpt", "claude", "human", "other", "unknown")
VERSION_KINDS = ("seed", "revision", "branch")
# Families whose games are played blind: the UI shows the id and nothing that names the
# mechanic (the same rule scripts/build_arena_catalog.py applies to the static manifest).
BLIND_FAMILIES = frozenset({"arena", "contributed-glowup", "research"})
MAX_EXTRA_PARENTS = 8

IDEA_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$")
IDEA_SOURCE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,59}$")
IDEA_STATUSES = ("unexplored", "exploring", "explored", "dropped")
MAX_IDEAS_PER_UPLOAD = 2000
MAX_IDEAS_BODY = 8 * 1024 * 1024
# "synthetic" = everything we generate or build; the official 25 and the imported community
# catalog are not ours to evolve, so the feedback queue skips them unless asked.
NOT_SYNTHETIC = ("official", "redbluepill")

# The first six are arc-explainer's flag names, kept identical so both sites' data joins.
FEEDBACK_FLAGS = (
    "solved_it",
    "never_understood",
    "inputs_did_nothing",
    "felt_broken",
    "felt_impossible",
    "enjoyed_it",
    "too_easy",
    "looks_like_others",
    "boring",
    "visual_clutter",
    "has_text",
)
RATING_FIELDS = ("fun", "clarity", "difficulty", "novelty")
TEXT_LIMITS = {"comment": 4000, "goal_guess": 2000, "liked": 2000, "disliked": 2000, "suggestion": 2000, "bugs": 2000}
COUNT_FIELDS = ("levels_completed", "levels_total", "actions", "resets", "undos", "seconds")
OUTCOMES = ("won", "lost", "gave_up", "in_progress")
VERDICTS = ("keep", "revise", "branch", "retire")

MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_THUMB_BYTES = 512 * 1024
MAX_PUBLICATION_BODY = 4 * 1024 * 1024
MAX_FEEDBACK_BODY = 64 * 1024
MAX_REASON = 500
MAX_DETAILS = 20_000
MAX_PROVENANCE = 16 * 1024
PUBLICATION_LOCK = 0x61726333  # "arc3": serializes version uploads so parents resolve in order

# The version order within a game: oldest first. created_at is the authoring time the
# publisher reports (a commit date, for backfilled history); ties fall back to upload order.
VERSION_ORDER = "ORDER BY v.created_at, v.published_at, v.version_id"


class GamesProblem(Exception):
    """An expected failure that is safe to show the client."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


@dataclass
class Response:
    status: int
    body: bytes
    content_type: str = "application/json; charset=utf-8"
    public_read: bool = False


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def sha12(sha256: str) -> str:
    return sha256[:12]


def source_url(game_id: str, sha256: str, src_file: str) -> str:
    return f"/data/_games/{game_id}/{sha12(sha256)}/{src_file}"


def thumb_url(game_id: str, sha256: str) -> str:
    return f"/data/_games/{game_id}/{sha12(sha256)}/thumb.png"


def blind(family: str) -> bool:
    return family in BLIND_FAMILIES


# ── Validation ───────────────────────────────────────────────────────────────


def _text(value: Any, field: str, limit: int, *, required: bool = False) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise GamesProblem(400, f"missing_{field}", f"{field} is required")
        return None
    if not isinstance(value, str):
        raise GamesProblem(400, f"invalid_{field}", f"{field} must be a string")
    # Drop control characters other than newline and tab; they only ever arrive by accident
    # or by abuse, and they make exported JSON lines awkward for the evolvers to read.
    cleaned = "".join(ch for ch in value if ch in "\n\t" or ord(ch) >= 32).strip()
    if len(cleaned) > limit:
        raise GamesProblem(400, f"{field}_too_long", f"{field} is limited to {limit} characters")
    return cleaned or None


def _game_id(value: Any, field: str = "game_id") -> str:
    if not isinstance(value, str) or not GAME_ID_RE.fullmatch(value):
        raise GamesProblem(400, f"invalid_{field}", f"{field} must match {GAME_ID_RE.pattern}")
    return value


def _version_id(value: Any, field: str = "version_id") -> str:
    if not isinstance(value, str) or not VERSION_ID_RE.fullmatch(value):
        raise GamesProblem(400, f"invalid_{field}", f"{field} must look like <game_id>@<12 hex>")
    return value


def _b64(value: Any, field: str, max_bytes: int, *, required: bool) -> bytes | None:
    if value in (None, ""):
        if required:
            raise GamesProblem(400, f"missing_{field}", f"{field} is required")
        return None
    if not isinstance(value, str):
        raise GamesProblem(400, f"invalid_{field}", f"{field} must be base64 text")
    try:
        payload = base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise GamesProblem(400, f"invalid_{field}", f"{field} is not valid base64") from exc
    if not payload or len(payload) > max_bytes:
        raise GamesProblem(400, f"invalid_{field}", f"{field} must be 1..{max_bytes} bytes")
    return payload


def _timestamp(value: Any, field: str) -> datetime | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise GamesProblem(400, f"invalid_{field}", f"{field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GamesProblem(400, f"invalid_{field}", f"{field} is not ISO-8601") from exc
    if parsed.tzinfo is None:
        raise GamesProblem(400, f"invalid_{field}", f"{field} needs a timezone")
    if parsed > utc_now() + timedelta(days=1):
        raise GamesProblem(400, f"invalid_{field}", f"{field} is in the future")
    return parsed


def clean_publication(payload: Any) -> dict[str, Any]:
    """Validate one version upload. Pure: no database, no disk."""

    if not isinstance(payload, dict):
        raise GamesProblem(400, "invalid_body", "expected a JSON object")
    game = payload.get("game")
    version = payload.get("version")
    if not isinstance(game, dict) or not isinstance(version, dict):
        raise GamesProblem(400, "invalid_body", "expected {game: {...}, version: {...}}")

    game_id = _game_id(game.get("game_id"))
    family = game.get("family")
    if family is not None and (not isinstance(family, str) or not FAMILY_RE.fullmatch(family)):
        raise GamesProblem(400, "invalid_family", f"family must match {FAMILY_RE.pattern}")
    tags = game.get("tags")
    if tags is not None:
        if not isinstance(tags, list) or len(tags) > 32 or not all(
            isinstance(tag, str) and 0 < len(tag) <= 120 for tag in tags
        ):
            raise GamesProblem(400, "invalid_tags", "tags must be up to 32 short strings")
    default_fps = game.get("default_fps")
    if default_fps is not None and (
        not isinstance(default_fps, int) or isinstance(default_fps, bool) or not 1 <= default_fps <= 60
    ):
        raise GamesProblem(400, "invalid_default_fps", "default_fps must be an integer 1..60")

    source = _b64(version.get("source_b64"), "source", MAX_SOURCE_BYTES, required=True)
    assert source is not None
    digest = hashlib.sha256(source).hexdigest()
    claimed = version.get("sha256")
    if claimed is not None and claimed != digest:
        raise GamesProblem(400, "sha256_mismatch", "sha256 does not match the uploaded source")
    thumbnail = _b64(version.get("thumb_png_b64"), "thumbnail", MAX_THUMB_BYTES, required=False)
    if thumbnail is not None and not thumbnail.startswith(PNG_MAGIC):
        raise GamesProblem(400, "invalid_thumbnail", "thumbnail must be a PNG")

    src_file = version.get("src_file")
    if not isinstance(src_file, str) or not SRC_FILE_RE.fullmatch(src_file):
        raise GamesProblem(400, "invalid_src_file", f"src_file must match {SRC_FILE_RE.pattern}")
    class_name = version.get("class_name")
    if not isinstance(class_name, str) or not CLASS_RE.fullmatch(class_name):
        raise GamesProblem(400, "invalid_class_name", "class_name must be a Python identifier")
    tile_scale = version.get("tile_scale")
    if tile_scale is not None and (
        not isinstance(tile_scale, int) or isinstance(tile_scale, bool) or not 1 <= tile_scale <= 64
    ):
        raise GamesProblem(400, "invalid_tile_scale", "tile_scale must be an integer 1..64")

    author = version.get("author") or {}
    if not isinstance(author, dict):
        raise GamesProblem(400, "invalid_author", "author must be an object")
    author_kind = author.get("kind") or "unknown"
    if author_kind not in AUTHOR_KINDS:
        raise GamesProblem(400, "invalid_author_kind", f"author.kind must be one of {AUTHOR_KINDS}")

    # Parents: `parent_version_ids` (a list, first = the primary parent that places the version
    # in its tree; the rest are secondary, e.g. the other half of a crossover), or the older
    # single `parent_version_id`. Both may be sent if they agree on the primary.
    parent = version.get("parent_version_id")
    if parent is not None:
        parent = _version_id(parent, "parent_version_id")
    parents = version.get("parent_version_ids")
    extra_parents: list[str] = []
    if parents is not None:
        if not isinstance(parents, list) or not parents or len(parents) > 1 + MAX_EXTRA_PARENTS:
            raise GamesProblem(
                400, "invalid_parent_version_ids", f"parent_version_ids must list 1..{1 + MAX_EXTRA_PARENTS} versions"
            )
        parents = [_version_id(p, "parent_version_ids") for p in parents]
        if len(set(parents)) != len(parents):
            raise GamesProblem(400, "invalid_parent_version_ids", "parent_version_ids repeats a version")
        if parent is not None and parent != parents[0]:
            raise GamesProblem(400, "invalid_parent_version_ids", "parent_version_id disagrees with parent_version_ids[0]")
        parent, extra_parents = parents[0], parents[1:]
    idea_ids = version.get("idea_ids") or []
    if not isinstance(idea_ids, list) or len(idea_ids) > 16 or not all(
        isinstance(i, str) and IDEA_ID_RE.fullmatch(i) for i in idea_ids
    ):
        raise GamesProblem(400, "invalid_idea_ids", "idea_ids must be up to 16 idea ids")
    kind = version.get("kind")
    if kind is not None and kind not in VERSION_KINDS:
        raise GamesProblem(400, "invalid_kind", f"kind must be one of {VERSION_KINDS}")
    if kind == "seed" and parent:
        raise GamesProblem(400, "invalid_kind", "a seed has no parent")

    provenance = version.get("provenance") or {}
    if not isinstance(provenance, dict) or len(json.dumps(provenance)) > MAX_PROVENANCE:
        raise GamesProblem(400, "invalid_provenance", "provenance must be a small JSON object")
    origin = _text(version.get("origin"), "origin", 64) or "api"

    return {
        "game_id": game_id,
        "family": family,
        "title": _text(game.get("title"), "title", 120),
        "description": _text(game.get("description"), "description", 4000),
        "tags": tags,
        "default_fps": default_fps,
        "source": source,
        "sha256": digest,
        "version_id": f"{game_id}@{sha12(digest)}",
        "thumbnail": thumbnail,
        "src_file": src_file,
        "class_name": class_name,
        "tile_scale": tile_scale,
        "parent_version_id": parent,
        "extra_parent_version_ids": extra_parents,
        "idea_ids": list(dict.fromkeys(idea_ids)),
        "kind": kind,
        "created_at": _timestamp(version.get("created_at"), "created_at"),
        "author_kind": author_kind,
        "author_model": _text(author.get("model"), "author_model", 120),
        "author_name": _text(author.get("name"), "author_name", 120),
        "reason": _text(version.get("reason"), "reason", MAX_REASON, required=True),
        "details": _text(version.get("details"), "details", MAX_DETAILS),
        "origin": origin,
        "provenance": provenance,
        "update_notes": bool(payload.get("update_notes")),
    }


def clean_feedback(payload: Any) -> dict[str, Any]:
    """Validate one review. Pure: the caller decides team vs public and resolves the version."""

    if not isinstance(payload, dict):
        raise GamesProblem(400, "invalid_body", "expected a JSON object")
    if payload.get("website"):
        # Honeypot: a hidden field no person fills in.
        raise GamesProblem(400, "rejected", "feedback rejected")

    game_id = _game_id(payload.get("game_id"))
    version_id = payload.get("version_id")
    if version_id is None:
        digest = payload.get("source_sha256")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise GamesProblem(400, "missing_version", "version_id or source_sha256 is required")
        version_id = f"{game_id}@{sha12(digest)}"
    version_id = _version_id(version_id)
    if VERSION_ID_RE.fullmatch(version_id).group(1) != game_id:
        raise GamesProblem(400, "version_game_mismatch", "version_id belongs to another game")

    cleaned: dict[str, Any] = {"game_id": game_id, "version_id": version_id}
    for field in RATING_FIELDS:
        value = payload.get(field)
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 5
        ):
            raise GamesProblem(400, f"invalid_{field}", f"{field} must be an integer 1..5")
        cleaned[field] = value
    for field in COUNT_FIELDS:
        value = payload.get(field)
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 10_000_000
        ):
            raise GamesProblem(400, f"invalid_{field}", f"{field} must be a non-negative integer")
        cleaned[field] = value
    flags = payload.get("flags") or []
    if not isinstance(flags, list) or not all(flag in FEEDBACK_FLAGS for flag in flags):
        raise GamesProblem(400, "invalid_flags", f"flags must be drawn from {FEEDBACK_FLAGS}")
    cleaned["flags"] = sorted(set(flags), key=FEEDBACK_FLAGS.index)
    for field, limit in TEXT_LIMITS.items():
        cleaned[field] = _text(payload.get(field), field, limit)
    outcome = payload.get("outcome")
    if outcome is not None and outcome not in OUTCOMES:
        raise GamesProblem(400, "invalid_outcome", f"outcome must be one of {OUTCOMES}")
    cleaned["outcome"] = outcome
    verdict = payload.get("verdict")
    if verdict is not None and verdict not in VERDICTS:
        raise GamesProblem(400, "invalid_verdict", f"verdict must be one of {VERDICTS}")
    cleaned["verdict"] = verdict
    cleaned["nickname"] = _text(payload.get("nickname"), "nickname", 40)
    visitor = payload.get("visitor_id")
    if visitor is not None and (not isinstance(visitor, str) or not VISITOR_RE.fullmatch(visitor)):
        raise GamesProblem(400, "invalid_visitor_id", "visitor_id must be 8..64 letters, digits or dashes")
    cleaned["visitor_id"] = visitor
    client = payload.get("client") or {}
    if not isinstance(client, dict) or len(json.dumps(client)) > 2048:
        raise GamesProblem(400, "invalid_client", "client must be a small JSON object")
    cleaned["client"] = client

    said_something = (
        any(cleaned[field] is not None for field in RATING_FIELDS)
        or cleaned["flags"]
        or any(cleaned[field] for field in TEXT_LIMITS)
        or cleaned["verdict"]
    )
    if not said_something:
        raise GamesProblem(400, "empty_feedback", "rate, flag, or write something before sending")
    return cleaned


# ── Rate limiting (public writes only) ──────────────────────────────────────


class SlidingWindowLimiter:
    """In-memory sliding window per key. One process serves the API, so this is enough to
    blunt a spam burst; it resets on deploy, which is fine for that purpose."""

    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window = window_seconds
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and now - events[0] > self.window:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            if len(self._events) > 50_000:  # forget idle keys rather than grow forever
                for stale in [k for k, v in self._events.items() if not v][:25_000]:
                    self._events.pop(stale, None)
            return True


# ── Publication (machine uploads) ───────────────────────────────────────────


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp.write_bytes(payload)
    os.replace(temp, path)


def _link_extras(cursor: Any, version_id: str, game_id: str, item: dict[str, Any]) -> None:
    """Secondary parents and the ideas a version was built from. Additive and idempotent, so
    a re-upload with update_notes can add links but never silently drops one."""

    extras = item["extra_parent_version_ids"]
    if version_id in extras or item["parent_version_id"] in extras:
        raise GamesProblem(400, "invalid_parent_version_ids", "a secondary parent repeats the version or its primary parent")
    if extras:
        cursor.execute("SELECT version_id FROM arc3_game_versions WHERE version_id = ANY(%s)", (extras,))
        missing = sorted(set(extras) - {row[0] for row in cursor.fetchall()})
        if missing:
            raise GamesProblem(404, "parent_not_found", f"not published: {', '.join(missing)}")
        cursor.execute("SELECT coalesce(max(position), 0) FROM arc3_game_version_parents WHERE version_id = %s", (version_id,))
        position = cursor.fetchone()[0]
        for parent in extras:
            position += 1
            cursor.execute(
                """
                INSERT INTO arc3_game_version_parents (version_id, parent_version_id, position)
                VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
                """,
                (version_id, parent, position),
            )
    if item["idea_ids"]:
        cursor.execute("SELECT idea_id FROM arc3_game_ideas WHERE idea_id = ANY(%s)", (item["idea_ids"],))
        missing = sorted(set(item["idea_ids"]) - {row[0] for row in cursor.fetchall()})
        if missing:
            raise GamesProblem(404, "idea_not_found", f"no such idea: {', '.join(missing)}")
        for idea_id in item["idea_ids"]:
            cursor.execute(
                "INSERT INTO arc3_game_idea_games (idea_id, game_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (idea_id, game_id),
            )
        # A game built from an idea is what "explored" means; a status the team chose by hand
        # (dropped, or already explored) stands.
        cursor.execute(
            """
            UPDATE arc3_game_ideas SET status = 'explored', updated_at = now()
            WHERE idea_id = ANY(%s) AND status IN ('unexplored', 'exploring')
            """,
            (item["idea_ids"],),
        )


def publish_version(connect: Callable[[], Any], data_root: Path, payload: Any) -> dict[str, Any]:
    """Store one uploaded version: files on the volume, rows in Postgres, in one transaction.

    Parent rules:
      - a new game_id with no parent starts a new tree: a seed;
      - a new game_id with a parent joins that parent's tree, as a branch (a new game) unless
        the upload says kind="revision" (the same game under a new id, e.g. q041-v2);
      - a known game_id is always a revision; its parent defaults to that game's latest
        version, and may name an older version of the same game to fork within it.
    """

    item = clean_publication(payload)
    version_id = item["version_id"]
    game_id = item["game_id"]
    version_dir = data_root / "_games" / game_id / sha12(item["sha256"])
    created_dir = False
    connection = connect()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", (PUBLICATION_LOCK,))
                cursor.execute(
                    "SELECT version_id, sha256 FROM arc3_game_versions WHERE version_id = %s",
                    (version_id,),
                )
                existing = cursor.fetchone()
                if existing and existing[1] != item["sha256"]:
                    raise GamesProblem(409, "version_id_collision", "another source already owns this version id")
                if existing:
                    if not item["update_notes"]:
                        return {"status": "unchanged", "versionId": version_id}
                    _link_extras(cursor, version_id, game_id, item)
                    cursor.execute(
                        """
                        UPDATE arc3_game_versions
                        SET reason = %s, details = %s, author_kind = %s, author_model = %s,
                            author_name = %s, provenance = %s
                        WHERE version_id = %s
                        """,
                        (
                            item["reason"],
                            item["details"],
                            item["author_kind"],
                            item["author_model"],
                            item["author_name"],
                            json.dumps(item["provenance"]),
                            version_id,
                        ),
                    )
                    return {"status": "updated", "versionId": version_id}

                cursor.execute(
                    "SELECT tree_id, family FROM arc3_games WHERE game_id = %s", (game_id,)
                )
                game_row = cursor.fetchone()
                parent = None
                if item["parent_version_id"]:
                    cursor.execute(
                        """
                        SELECT version_id, game_id, tree_id, created_at
                        FROM arc3_game_versions WHERE version_id = %s
                        """,
                        (item["parent_version_id"],),
                    )
                    parent = cursor.fetchone()
                    if not parent:
                        raise GamesProblem(404, "parent_not_found", "parent_version_id is not published")
                    if game_row and parent[1] != game_id:
                        raise GamesProblem(
                            409,
                            "parent_in_other_game",
                            "an existing game's versions must descend from that game; "
                            "publish a branch or a renamed revision under a new game_id instead",
                        )
                elif game_row:
                    cursor.execute(
                        """
                        SELECT v.version_id, v.game_id, v.tree_id, v.created_at
                        FROM arc3_game_versions AS v WHERE v.game_id = %s
                        ORDER BY v.created_at DESC, v.published_at DESC, v.version_id DESC
                        LIMIT 1
                        """,
                        (game_id,),
                    )
                    parent = cursor.fetchone()

                if parent is None:
                    if item["kind"] not in (None, "seed"):
                        raise GamesProblem(400, "missing_parent", f"a {item['kind']} needs parent_version_id")
                    kind = "seed"
                elif game_row:
                    if item["kind"] == "seed":
                        raise GamesProblem(
                            409, "already_seeded", "this game already has versions; only a new game_id can be a seed"
                        )
                    if item["kind"] == "branch":
                        raise GamesProblem(
                            409, "branch_needs_new_game", "a branch is a new game: give it a new game_id"
                        )
                    kind = "revision"
                else:
                    kind = item["kind"] or "branch"

                created_at = item["created_at"] or utc_now()
                if parent and created_at < parent[3]:
                    raise GamesProblem(
                        409,
                        "created_before_parent",
                        "created_at is earlier than the parent version; name the parent explicitly",
                    )

                if game_row:
                    tree_id, family = game_row
                    cursor.execute(
                        """
                        UPDATE arc3_games
                        SET title = COALESCE(%s, title),
                            description = COALESCE(%s, description),
                            tags = COALESCE(%s, tags),
                            default_fps = COALESCE(%s, default_fps),
                            updated_at = now()
                        WHERE game_id = %s
                        """,
                        (
                            game_id if blind(family) else item["title"],
                            None if blind(family) else item["description"],
                            None if blind(family) or item["tags"] is None else json.dumps(item["tags"]),
                            item["default_fps"],
                            game_id,
                        ),
                    )
                else:
                    if parent:
                        tree_id = parent[2]
                        cursor.execute("SELECT family FROM arc3_games WHERE game_id = %s", (parent[1],))
                        family = item["family"] or cursor.fetchone()[0]
                    else:
                        tree_id = game_id
                        family = item["family"] or "custom"
                        cursor.execute(
                            """
                            INSERT INTO arc3_game_trees (tree_id, root_game_id, family, created_at)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (tree_id, game_id, family, created_at),
                        )
                    cursor.execute(
                        """
                        INSERT INTO arc3_games (
                            game_id, tree_id, family, title, description, tags,
                            default_fps, derived_from, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            game_id,
                            tree_id,
                            family,
                            game_id if blind(family) else (item["title"] or game_id),
                            None if blind(family) else item["description"],
                            json.dumps([] if blind(family) else (item["tags"] or [])),
                            item["default_fps"] or 6,
                            parent[0] if parent else None,
                            created_at,
                        ),
                    )

                cursor.execute(
                    """
                    INSERT INTO arc3_game_versions (
                        version_id, game_id, tree_id, sha256, parent_version_id, kind,
                        created_at, author_kind, author_model, author_name, reason, details,
                        src_file, class_name, tile_scale, byte_count, has_thumbnail,
                        origin, provenance
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        version_id,
                        game_id,
                        tree_id,
                        item["sha256"],
                        parent[0] if parent else None,
                        kind,
                        created_at,
                        item["author_kind"],
                        item["author_model"],
                        item["author_name"],
                        item["reason"],
                        item["details"],
                        item["src_file"],
                        item["class_name"],
                        item["tile_scale"],
                        len(item["source"]),
                        item["thumbnail"] is not None,
                        item["origin"],
                        json.dumps(item["provenance"]),
                    ),
                )
                _link_extras(cursor, version_id, game_id, item)
                cursor.execute(
                    "UPDATE arc3_game_trees SET updated_at = now() WHERE tree_id = %s", (tree_id,)
                )

                # Files last, before commit: if they fail, the rows roll back; if the commit
                # fails, the except below removes what this request wrote.
                created_dir = not version_dir.exists()
                _write_atomic(version_dir / item["src_file"], item["source"])
                if item["thumbnail"] is not None:
                    _write_atomic(version_dir / "thumb.png", item["thumbnail"])
        return {
            "status": "published",
            "versionId": version_id,
            "treeId": tree_id,
            "gameId": game_id,
            "kind": kind,
            "parentVersionId": parent[0] if parent else None,
            "sourceUrl": source_url(game_id, item["sha256"], item["src_file"]),
        }
    except Exception:
        if created_dir:
            shutil.rmtree(version_dir, ignore_errors=True)
        raise
    finally:
        connection.close()


def known_versions(cursor: Any, game_id: str | None) -> dict[str, Any]:
    if game_id:
        cursor.execute(
            f"SELECT v.game_id, v.sha256 FROM arc3_game_versions AS v WHERE v.game_id = %s {VERSION_ORDER}",
            (game_id,),
        )
    else:
        cursor.execute(f"SELECT v.game_id, v.sha256 FROM arc3_game_versions AS v {VERSION_ORDER}")
    known: dict[str, list[str]] = {}
    for gid, digest in cursor.fetchall():
        known.setdefault(gid, []).append(digest)
    return {"apiVersion": 1, "games": known}


# ── Reads ────────────────────────────────────────────────────────────────────

# Lines. A seed or a branch starts a line; each revision continues its parent's line.
# `number` is the version's position in its line (v1, v2, ...), and a line's latest version
# is its head: the current, best version of that game.
LINE_CTES = """
    lines AS (
        SELECT v.version_id, v.version_id AS line_id, 1 AS number
        FROM arc3_game_versions AS v
        WHERE v.parent_version_id IS NULL OR v.kind <> 'revision'
      UNION ALL
        SELECT c.version_id, l.line_id, l.number + 1
        FROM arc3_game_versions AS c
        JOIN lines AS l ON c.parent_version_id = l.version_id
        WHERE c.kind = 'revision'
    ),
    line_heads AS (
        SELECT DISTINCT ON (l.line_id) l.line_id, l.version_id, l.number
        FROM lines AS l
        JOIN arc3_game_versions AS v ON v.version_id = l.version_id
        ORDER BY l.line_id, v.created_at DESC, v.published_at DESC, v.version_id DESC
    ),
    tree_heads AS (
        SELECT r.tree_id, lh.version_id, lh.number
        FROM line_heads AS lh
        JOIN arc3_game_versions AS r ON r.version_id = lh.line_id
        WHERE r.parent_version_id IS NULL
    )
"""

VERSION_COLUMNS = """
    v.version_id, v.game_id, v.tree_id, v.parent_version_id, v.kind, v.created_at,
    v.author_kind, v.author_model, v.sha256, v.src_file, v.class_name, v.tile_scale,
    v.has_thumbnail
"""

SORTS = {
    "recent": "s.last_changed_at DESC, t.tree_id",
    "versions": "s.version_count DESC, s.last_changed_at DESC, t.tree_id",
    "feedback": "COALESCE(fb.team_count, 0), COALESCE(fb.public_count, 0), s.last_changed_at DESC, t.tree_id",
    "id": "t.tree_id",
}


def _game_public(family: str, game_id: str, title: str | None, description: str | None, tags: Any) -> dict[str, Any]:
    if blind(family):
        return {"title": game_id, "description": None, "tags": []}
    return {"title": title or game_id, "description": description, "tags": tags or []}


def _version_public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "versionId": row["version_id"],
        "gameId": row["game_id"],
        "parentVersionId": row.get("parent_version_id"),
        "kind": row.get("kind"),
        "number": row.get("number"),
        "createdAt": iso(row["created_at"]),
        "author": {"kind": row["author_kind"], "model": row.get("author_model")},
        "sha256": row["sha256"],
        "srcFile": row["src_file"],
        "className": row["class_name"],
        "tileScale": row.get("tile_scale"),
        "sourceUrl": source_url(row["game_id"], row["sha256"], row["src_file"]),
        "thumbUrl": thumb_url(row["game_id"], row["sha256"]) if row["has_thumbnail"] else None,
    }


def _rows(cursor: Any) -> list[dict[str, Any]]:
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _one(cursor: Any) -> dict[str, Any] | None:
    """One row as a dict, whatever cursor factory the caller is using."""
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(row) if isinstance(row, dict) else dict(zip([column[0] for column in cursor.description], row))


def _pool_filter(pool: str | None) -> tuple[str, list[Any]]:
    if not pool or pool == "synthetic":
        return "g.family <> ALL(%s)", [list(NOT_SYNTHETIC)]
    if pool == "all":
        return "TRUE", []
    if not FAMILY_RE.fullmatch(pool):
        raise GamesProblem(400, "invalid_pool", "pool must be synthetic, all, or a family name")
    return "g.family = %s", [pool]


def assign_lines(rows: list[dict[str, Any]]) -> dict[str, tuple[str, int]]:
    """version_id -> (line_id, number), for one tree's versions in oldest-first order.

    The Python twin of LINE_CTES, used where the whole tree is already in memory. A revision
    whose parent is not in `rows` (its game is hidden) starts a line of its own rather than
    vanishing."""

    placed: dict[str, tuple[str, int]] = {}
    pending = list(rows)
    while pending:
        waiting = []
        for row in pending:
            parent = row.get("parent_version_id")
            if parent is None or row.get("kind") != "revision":
                placed[row["version_id"]] = (row["version_id"], 1)
            elif parent in placed:
                line_id, number = placed[parent]
                placed[row["version_id"]] = (line_id, number + 1)
            else:
                waiting.append(row)
        if len(waiting) == len(pending):
            for row in waiting:
                placed[row["version_id"]] = (row["version_id"], 1)
            break
        pending = waiting
    return placed


def list_trees(cursor: Any, query: dict[str, list[str]]) -> dict[str, Any]:
    family = (query.get("family") or [""])[0]
    search = (query.get("q") or [""])[0].strip()
    evolved = (query.get("evolved") or [""])[0] in ("1", "true")
    sort = (query.get("sort") or ["recent"])[0]
    if sort not in SORTS:
        raise GamesProblem(400, "invalid_sort", f"sort must be one of {sorted(SORTS)}")
    try:
        limit = max(1, min(100, int((query.get("limit") or ["20"])[0])))
        offset = max(0, int((query.get("offset") or ["0"])[0]))
    except ValueError as exc:
        raise GamesProblem(400, "invalid_page", "limit and offset must be integers") from exc

    where = ["TRUE"]
    params: list[Any] = []
    if family:
        if family == "synthetic":
            where.append("t.family <> ALL(%s)")
            params.append(list(NOT_SYNTHETIC))
        elif FAMILY_RE.fullmatch(family):
            where.append("t.family = %s")
            params.append(family)
        else:
            raise GamesProblem(400, "invalid_family", "unknown family filter")
    if search:
        if len(search) > 80:
            raise GamesProblem(400, "invalid_q", "search is limited to 80 characters")
        like = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where.append(
            "(t.tree_id ILIKE %s OR EXISTS (SELECT 1 FROM arc3_games AS sg WHERE sg.tree_id = t.tree_id "
            "AND NOT sg.hidden AND (sg.game_id ILIKE %s OR sg.title ILIKE %s OR sg.tags::text ILIKE %s)))"
        )
        params.extend([like, like, like, like])
    if evolved:
        where.append("s.version_count > 1")

    cursor.execute(
        f"""
        WITH RECURSIVE {LINE_CTES},
        stats AS (
            SELECT tree_id,
                   count(*) AS version_count,
                   count(DISTINCT game_id) AS game_count,
                   count(*) FILTER (WHERE kind = 'branch') AS branch_count,
                   max(created_at) AS last_changed_at,
                   count(*) FILTER (WHERE author_kind = 'gpt') AS by_gpt,
                   count(*) FILTER (WHERE author_kind = 'claude') AS by_claude,
                   count(*) FILTER (WHERE author_kind = 'human') AS by_human,
                   count(*) FILTER (WHERE author_kind = 'other') AS by_other,
                   count(*) FILTER (WHERE author_kind = 'unknown') AS by_unknown
            FROM arc3_game_versions
            GROUP BY tree_id
        ),
        fb AS (
            SELECT g.tree_id,
                   count(*) FILTER (WHERE f.reviewer_class = 'team') AS team_count,
                   count(*) FILTER (WHERE f.reviewer_class = 'public') AS public_count
            FROM arc3_game_feedback AS f
            JOIN arc3_games AS g ON g.game_id = f.game_id
            WHERE NOT f.hidden
            GROUP BY g.tree_id
        )
        SELECT t.tree_id, t.family AS tree_family, t.root_game_id,
               g.family, g.title, g.description, g.tags, g.default_fps,
               {VERSION_COLUMNS}, th.number,
               s.version_count, s.game_count, s.branch_count, s.last_changed_at,
               s.by_gpt, s.by_claude, s.by_human, s.by_other, s.by_unknown,
               COALESCE(fb.team_count, 0) AS team_count,
               COALESCE(fb.public_count, 0) AS public_count,
               count(*) OVER () AS total
        FROM arc3_game_trees AS t
        JOIN tree_heads AS th ON th.tree_id = t.tree_id
        JOIN arc3_game_versions AS v ON v.version_id = th.version_id
        JOIN arc3_games AS g ON g.game_id = v.game_id AND NOT g.hidden
        JOIN stats AS s ON s.tree_id = t.tree_id
        LEFT JOIN fb ON fb.tree_id = t.tree_id
        WHERE {" AND ".join(where)}
        ORDER BY {SORTS[sort]}
        LIMIT %s OFFSET %s
        """,
        (*params, limit, offset),
    )
    rows = _rows(cursor)
    trees = []
    for row in rows:
        trees.append(
            {
                "treeId": row["tree_id"],
                "family": row["tree_family"],
                "rootGameId": row["root_game_id"],
                "defaultFps": row["default_fps"],
                **_game_public(row["family"], row["game_id"], row["title"], row["description"], row["tags"]),
                "head": {**_version_public(row), "isTreeHead": True, "isLineHead": True},
                "versionCount": row["version_count"],
                "gameCount": row["game_count"],
                "branchCount": row["branch_count"],
                "lastChangedAt": iso(row["last_changed_at"]),
                "authors": {
                    "gpt": row["by_gpt"],
                    "claude": row["by_claude"],
                    "human": row["by_human"],
                    "other": row["by_other"],
                    "unknown": row["by_unknown"],
                },
                "feedback": {"team": row["team_count"], "public": row["public_count"]},
            }
        )
    cursor.execute("SELECT family, count(*) FROM arc3_game_trees GROUP BY family ORDER BY family")
    families = {name: count for name, count in cursor.fetchall()}
    return {
        "apiVersion": 1,
        "total": rows[0]["total"] if rows else 0,
        "offset": offset,
        "limit": limit,
        "families": families,
        "trees": trees,
    }


def _feedback_stats(cursor: Any, tree_id: str) -> dict[str, dict[str, Any]]:
    cursor.execute(
        """
        SELECT f.version_id, f.reviewer_class, count(*) AS n,
               avg(f.fun) AS fun, avg(f.clarity) AS clarity,
               avg(f.difficulty) AS difficulty, avg(f.novelty) AS novelty,
               count(*) FILTER (WHERE f.outcome = 'won') AS won
        FROM arc3_game_feedback AS f
        JOIN arc3_games AS g ON g.game_id = f.game_id
        WHERE g.tree_id = %s AND NOT f.hidden
        GROUP BY f.version_id, f.reviewer_class
        """,
        (tree_id,),
    )
    stats: dict[str, dict[str, Any]] = {}
    for row in _rows(cursor):
        bucket = stats.setdefault(row["version_id"], {"team": None, "public": None})
        bucket[row["reviewer_class"]] = {
            "count": row["n"],
            "won": row["won"],
            **{
                field: (round(float(row[field]), 2) if row[field] is not None else None)
                for field in RATING_FIELDS
            },
        }
    return stats


def tree_detail(cursor: Any, tree_id: str) -> dict[str, Any]:
    tree_id = _game_id(tree_id, "tree_id")
    cursor.execute(
        "SELECT tree_id, family, root_game_id, created_at, updated_at FROM arc3_game_trees WHERE tree_id = %s",
        (tree_id,),
    )
    tree = cursor.fetchone()
    if not tree:
        raise GamesProblem(404, "tree_not_found", "no such game tree")
    cursor.execute(
        """
        SELECT game_id, family, title, description, tags, default_fps, derived_from, created_at
        FROM arc3_games WHERE tree_id = %s AND NOT hidden ORDER BY created_at, game_id
        """,
        (tree_id,),
    )
    games = [
        {
            "gameId": row["game_id"],
            "family": row["family"],
            "defaultFps": row["default_fps"],
            "derivedFrom": row["derived_from"],
            "createdAt": iso(row["created_at"]),
            **_game_public(row["family"], row["game_id"], row["title"], row["description"], row["tags"]),
        }
        for row in _rows(cursor)
    ]
    visible = {game["gameId"] for game in games}
    stats = _feedback_stats(cursor, tree_id)
    cursor.execute(
        f"""
        SELECT {VERSION_COLUMNS} FROM arc3_game_versions AS v
        WHERE v.tree_id = %s
        ORDER BY v.created_at, v.published_at, v.version_id
        """,
        (tree_id,),
    )
    rows = [row for row in _rows(cursor) if row["game_id"] in visible]
    cursor.execute(
        """
        SELECT p.version_id, p.parent_version_id
        FROM arc3_game_version_parents AS p
        JOIN arc3_game_versions AS v ON v.version_id = p.version_id
        WHERE v.tree_id = %s
        ORDER BY p.version_id, p.position
        """,
        (tree_id,),
    )
    extra_parents: dict[str, list[str]] = {}
    for child, extra in cursor.fetchall():
        extra_parents.setdefault(child, []).append(extra)
    lines = assign_lines(rows)
    line_heads: dict[str, str] = {}
    for row in rows:  # oldest first, so the last one seen per line is its head
        line_heads[lines[row["version_id"]][0]] = row["version_id"]
    root_line = next((row["version_id"] for row in rows if row["parent_version_id"] is None), None)
    tree_head = line_heads.get(root_line) if root_line else (rows[-1]["version_id"] if rows else None)
    versions = []
    for row in rows:
        line_id, number = lines[row["version_id"]]
        row["number"] = number
        version = _version_public(row)
        version.update(
            {
                "lineId": line_id,
                "isLineHead": line_heads[line_id] == row["version_id"],
                "isTreeHead": tree_head == row["version_id"],
                "feedback": stats.get(row["version_id"], {"team": None, "public": None}),
                "extraParentVersionIds": extra_parents.get(row["version_id"], []),
            }
        )
        versions.append(version)
    return {
        "apiVersion": 1,
        "treeId": tree[0],
        "family": tree[1],
        "rootGameId": tree[2],
        "createdAt": iso(tree[3]),
        "updatedAt": iso(tree[4]),
        "headVersionId": tree_head,
        "games": games,
        "versions": versions,
    }


def tree_notes(cursor: Any, tree_id: str) -> dict[str, Any]:
    """Change notes and every review for one tree. Team-only: never route this publicly."""

    tree_id = _game_id(tree_id, "tree_id")
    cursor.execute(
        """
        SELECT version_id, reason, details, author_kind, author_model, author_name,
               origin, provenance, published_at, train_ok, train_ok_by, train_ok_at
        FROM arc3_game_versions WHERE tree_id = %s
        """,
        (tree_id,),
    )
    notes = {
        row["version_id"]: {
            "reason": row["reason"],
            "details": row["details"],
            "author": {
                "kind": row["author_kind"],
                "model": row["author_model"],
                "name": row["author_name"],
            },
            "origin": row["origin"],
            "provenance": row["provenance"],
            "publishedAt": iso(row["published_at"]),
            "trainOk": row["train_ok"],
            "trainOkBy": row["train_ok_by"],
            "trainOkAt": iso(row["train_ok_at"]),
        }
        for row in _rows(cursor)
    }
    cursor.execute(
        "SELECT game_id, title, description, tags FROM arc3_games WHERE tree_id = %s", (tree_id,)
    )
    game_notes = {
        row["game_id"]: {"title": row["title"], "description": row["description"], "tags": row["tags"]}
        for row in _rows(cursor)
    }
    cursor.execute(
        """
        SELECT f.* FROM arc3_game_feedback AS f
        JOIN arc3_games AS g ON g.game_id = f.game_id
        WHERE g.tree_id = %s
        ORDER BY (f.reviewer_class = 'team') DESC, f.created_at DESC
        LIMIT 2000
        """,
        (tree_id,),
    )
    feedback = [feedback_record(row) for row in _rows(cursor)]
    cursor.execute(
        """
        SELECT ig.game_id, i.idea_id, i.title, i.axis, i.status, i.source
        FROM arc3_game_idea_games AS ig
        JOIN arc3_game_ideas AS i ON i.idea_id = ig.idea_id
        WHERE ig.game_id IN (SELECT game_id FROM arc3_games WHERE tree_id = %s)
        ORDER BY ig.game_id, i.idea_id
        """,
        (tree_id,),
    )
    ideas: dict[str, list[dict[str, Any]]] = {}
    for row in _rows(cursor):
        ideas.setdefault(row["game_id"], []).append(
            {"ideaId": row["idea_id"], "title": row["title"], "axis": row["axis"], "status": row["status"], "source": row["source"]}
        )
    return {
        "apiVersion": 1,
        "treeId": tree_id,
        "notes": notes,
        "games": game_notes,
        "feedback": feedback,
        "ideas": ideas,
    }


# ── The training tick ────────────────────────────────────────────────────────


def set_train_ok(cursor: Any, version_id: str, good: bool, *, email: str) -> dict[str, Any]:
    """Tick one exact version as fit to train on. Per version, not per game: the pipeline
    trains on exact bytes, and the next version of the same game may not be fit at all."""

    version_id = _version_id(version_id, "version_id")
    cursor.execute(
        """
        UPDATE arc3_game_versions
           SET train_ok = %s, train_ok_by = %s, train_ok_at = now()
         WHERE version_id = %s
        RETURNING version_id, game_id, tree_id, train_ok, train_ok_by, train_ok_at
        """,
        (good, email if good else None, version_id),
    )
    row = _one(cursor)
    if not row:
        raise GamesProblem(404, "version_not_found", f"not published: {version_id}")
    print(f"games: train_ok={good} on {version_id} by {email}", flush=True)
    return {
        "apiVersion": 1,
        "versionId": row["version_id"],
        "gameId": row["game_id"],
        "treeId": row["tree_id"],
        "trainOk": row["train_ok"],
        "trainOkBy": row["train_ok_by"],
        "trainOkAt": iso(row["train_ok_at"]),
    }


def training_set(cursor: Any) -> dict[str, Any]:
    """Every version a person ticked as good to train, for the training pipeline to pull."""

    cursor.execute(
        """
        SELECT v.version_id, v.game_id, v.tree_id, v.sha256, v.src_file, v.kind,
               v.author_kind, v.author_model, v.train_ok_by, v.train_ok_at, g.family
        FROM arc3_game_versions AS v JOIN arc3_games AS g ON g.game_id = v.game_id
        WHERE v.train_ok ORDER BY v.tree_id, v.published_at
        """
    )
    versions = [
        {
            "versionId": row["version_id"],
            "gameId": row["game_id"],
            "treeId": row["tree_id"],
            "family": row["family"],
            "kind": row["kind"],
            "sha256": row["sha256"],
            "sourceUrl": f"/data/_games/{row['game_id']}/{row['sha256'][:12]}/{row['src_file']}",
            "author": {"kind": row["author_kind"], "model": row["author_model"]},
            "markedBy": row["train_ok_by"],
            "markedAt": iso(row["train_ok_at"]),
        }
        for row in _rows(cursor)
    ]
    return {"apiVersion": 1, "count": len(versions), "versions": versions}


def feedback_record(row: dict[str, Any], *, include_ip: bool = False) -> dict[str, Any]:
    record = {
        "feedbackId": row["feedback_id"],
        "gameId": row["game_id"],
        "versionId": row["version_id"],
        "reviewerClass": row["reviewer_class"],
        "reviewer": row["reviewer"],
        "createdAt": iso(row["created_at"]),
        "outcome": row["outcome"],
        "flags": list(row["flags"] or []),
        "verdict": row["verdict"],
        "hidden": row["hidden"],
    }
    for field in COUNT_FIELDS + RATING_FIELDS + tuple(TEXT_LIMITS):
        record[_camel(field)] = row[field]
    if include_ip:
        record["ipHint"] = row.get("ip_hint")
    return record


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.title() for part in rest)


def next_version(
    cursor: Any,
    query: dict[str, list[str]],
    *,
    reviewer: str | None,
) -> dict[str, Any]:
    """The current version that most needs a review: every line's head is a candidate.

    Team reviewers are steered to versions no team member has reviewed yet, and never to one
    they reviewed themselves; public players to the least-reviewed version overall. Newer
    versions win ties, so a fresh revision is played before an old one."""

    pool_sql, pool_params = _pool_filter((query.get("pool") or ["synthetic"])[0])
    exclude = [
        item
        for item in (query.get("exclude") or [""])[0].split(",")
        if VERSION_ID_RE.fullmatch(item)
    ][:500]
    if reviewer:
        count_sql = "COALESCE(fb.team_n, 0)"
        mine_sql = (
            "AND NOT EXISTS (SELECT 1 FROM arc3_game_feedback AS mine WHERE mine.version_id = v.version_id "
            "AND mine.reviewer_class = 'team' AND mine.reviewer = %s)"
        )
        mine_params: list[Any] = [reviewer]
        tiebreak_seed = reviewer
    else:
        count_sql = "COALESCE(fb.all_n, 0)"
        mine_sql = ""
        mine_params = []
        tiebreak_seed = (query.get("visitor") or [""])[0][:64] or uuid.uuid4().hex
    cursor.execute(
        f"""
        WITH RECURSIVE {LINE_CTES},
        fb AS (
            SELECT version_id,
                   count(*) FILTER (WHERE reviewer_class = 'team') AS team_n,
                   count(*) AS all_n
            FROM arc3_game_feedback WHERE NOT hidden GROUP BY version_id
        )
        SELECT {VERSION_COLUMNS}, lh.number,
               g.family, g.title, g.description, g.tags, g.default_fps,
               {count_sql} AS reviews, count(*) OVER () AS remaining
        FROM line_heads AS lh
        JOIN arc3_game_versions AS v ON v.version_id = lh.version_id
        JOIN arc3_games AS g ON g.game_id = v.game_id AND NOT g.hidden
        LEFT JOIN fb ON fb.version_id = v.version_id
        WHERE {pool_sql}
          AND NOT (v.version_id = ANY(%s))
          {mine_sql}
        ORDER BY {count_sql}, v.created_at DESC, md5(v.version_id || %s)
        LIMIT 1
        """,
        (*pool_params, exclude, *mine_params, tiebreak_seed),
    )
    rows = _rows(cursor)
    if not rows:
        return {"apiVersion": 1, "version": None, "remaining": 0}
    row = rows[0]
    version = _version_public(row)
    version.update(
        {
            "isLineHead": True,
            "treeId": row["tree_id"],
            "family": row["family"],
            "defaultFps": row["default_fps"],
            "reviews": row["reviews"],
            **_game_public(row["family"], row["game_id"], row["title"], row["description"], row["tags"]),
        }
    )
    return {"apiVersion": 1, "version": version, "remaining": row["remaining"]}


def public_manifest(cursor: Any) -> list[dict[str, Any]]:
    """Each game id's latest version, in the static manifest.json shape plus source/thumbnail
    URLs, so a mirror (arc-explainer) can follow uploads without a site deploy."""

    cursor.execute(
        f"""
        SELECT DISTINCT ON (v.game_id) {VERSION_COLUMNS},
               g.family, g.title, g.description, g.tags, g.default_fps
        FROM arc3_game_versions AS v
        JOIN arc3_games AS g ON g.game_id = v.game_id AND NOT g.hidden
        ORDER BY v.game_id, v.created_at DESC, v.published_at DESC, v.version_id DESC
        """
    )
    manifest = []
    for row in _rows(cursor):
        public = _game_public(row["family"], row["game_id"], row["title"], row["description"], row["tags"])
        entry = {
            "id": row["game_id"],
            "title": public["title"],
            "class_name": row["class_name"],
            "src_file": row["src_file"],
            "default_fps": row["default_fps"],
            "category": row["family"],
            "official": row["family"] == "official",
            "version_id": row["version_id"],
            "tree_id": row["tree_id"],
            "src_url": source_url(row["game_id"], row["sha256"], row["src_file"]),
            "thumb_url": thumb_url(row["game_id"], row["sha256"]) if row["has_thumbnail"] else None,
        }
        if public["tags"]:
            entry["tags"] = public["tags"]
        if public["description"]:
            entry["description"] = public["description"]
        if row["tile_scale"]:
            entry["tile_scale"] = row["tile_scale"]
        manifest.append(entry)
    return manifest


# ── Feedback writes ──────────────────────────────────────────────────────────


def insert_feedback(
    cursor: Any,
    item: dict[str, Any],
    *,
    reviewer_class: str,
    reviewer: str | None,
    ip_hint: str | None,
    static_game_ids: frozenset[str],
) -> dict[str, Any]:
    cursor.execute("SELECT game_id FROM arc3_game_versions WHERE version_id = %s", (item["version_id"],))
    row = cursor.fetchone()
    if not row and item["game_id"] not in static_game_ids:
        # Unpublished versions are only accepted for games the site itself ships, so the
        # table cannot fill up with reviews of ids nobody can play.
        raise GamesProblem(404, "unknown_game", "no such game version")
    cursor.execute(
        """
        INSERT INTO arc3_game_feedback (
            game_id, version_id, reviewer_class, reviewer, visitor_id, outcome,
            levels_completed, levels_total, actions, resets, undos, seconds,
            fun, clarity, difficulty, novelty, flags,
            comment, goal_guess, liked, disliked, suggestion, bugs, verdict, client, ip_hint
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        RETURNING feedback_id, created_at
        """,
        (
            item["game_id"],
            item["version_id"],
            reviewer_class,
            reviewer,
            item["visitor_id"],
            item["outcome"],
            *(item[field] for field in COUNT_FIELDS),
            *(item[field] for field in RATING_FIELDS),
            item["flags"],
            *(item[field] for field in TEXT_LIMITS),
            item["verdict"],
            json.dumps(item["client"]),
            ip_hint,
        ),
    )
    feedback_id, created_at = cursor.fetchone()
    return {
        "apiVersion": 1,
        "feedbackId": feedback_id,
        "reviewerClass": reviewer_class,
        "versionId": item["version_id"],
        "createdAt": iso(created_at),
        "registered": bool(row),
    }


def export_feedback(cursor: Any, query: dict[str, list[str]], *, include_ip: bool) -> Iterable[dict[str, Any]]:
    """Reviews as records for the evolvers: team first within each version, newest last, with
    the version's own change note attached so a reader sees what the reviewer played."""

    where = ["TRUE"]
    params: list[Any] = []
    since = _timestamp((query.get("since") or [None])[0], "since")
    if since:
        where.append("f.created_at > %s")
        params.append(since)
    for key, column in (("game_id", "f.game_id"), ("version_id", "f.version_id")):
        value = (query.get(key) or [None])[0]
        if value:
            (_version_id if key == "version_id" else _game_id)(value)
            where.append(f"{column} = %s")
            params.append(value)
    tree = (query.get("tree_id") or [None])[0]
    if tree:
        where.append("g.tree_id = %s")
        params.append(_game_id(tree, "tree_id"))
    if (query.get("include_hidden") or ["0"])[0] not in ("1", "true"):
        where.append("NOT f.hidden")
    cursor.execute(
        f"""
        SELECT f.*, g.tree_id, v.reason AS version_reason, v.created_at AS version_created_at,
               v.author_kind AS version_author_kind, v.author_model AS version_author_model
        FROM arc3_game_feedback AS f
        LEFT JOIN arc3_games AS g ON g.game_id = f.game_id
        LEFT JOIN arc3_game_versions AS v ON v.version_id = f.version_id
        WHERE {" AND ".join(where)}
        ORDER BY f.version_id, (f.reviewer_class = 'team') DESC, f.created_at
        LIMIT 20000
        """,
        params,
    )
    for row in _rows(cursor):
        record = feedback_record(row, include_ip=include_ip)
        record["treeId"] = row["tree_id"]
        record["version"] = {
            "reason": row["version_reason"],
            "createdAt": iso(row["version_created_at"]),
            "author": {"kind": row["version_author_kind"], "model": row["version_author_model"]},
        }
        yield record


# ── Ideas board ──────────────────────────────────────────────────────────────


def clean_idea(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise GamesProblem(400, "invalid_idea", "each idea must be an object")
    idea_id = raw.get("idea_id")
    if not isinstance(idea_id, str) or not IDEA_ID_RE.fullmatch(idea_id):
        raise GamesProblem(400, "invalid_idea_id", f"idea_id must match {IDEA_ID_RE.pattern}")
    source = raw.get("source")
    if not isinstance(source, str) or not IDEA_SOURCE_RE.fullmatch(source):
        raise GamesProblem(400, "invalid_idea_source", f"source must match {IDEA_SOURCE_RE.pattern}")
    status = raw.get("status") or "unexplored"
    if status not in IDEA_STATUSES:
        raise GamesProblem(400, "invalid_idea_status", f"status must be one of {IDEA_STATUSES}")
    details = raw.get("details") or {}
    if not isinstance(details, dict) or len(json.dumps(details)) > 16 * 1024:
        raise GamesProblem(400, "invalid_idea_details", "details must be a small JSON object")
    games = raw.get("game_ids") or []
    if not isinstance(games, list) or len(games) > 32:
        raise GamesProblem(400, "invalid_idea_games", "game_ids must list up to 32 games")
    return {
        "idea_id": idea_id,
        "source": source,
        "title": _text(raw.get("title"), "title", 200, required=True),
        "axis": _text(raw.get("axis"), "axis", 120),
        "pitch": _text(raw.get("pitch"), "pitch", 4000, required=True),
        "details": details,
        "status": status,
        "game_ids": [_game_id(g, "game_ids") for g in games],
    }


def upsert_ideas(cursor: Any, payload: Any) -> dict[str, Any]:
    """Add or refresh ideas in bulk (machines only). Text and details are replaced. Status only
    moves forward from `unexplored`: re-seeding a ledger never undoes a card the team moved.
    Game links are added, never removed, and a linked game makes its idea explored."""

    ideas = payload.get("ideas") if isinstance(payload, dict) else None
    if not isinstance(ideas, list) or not 1 <= len(ideas) <= MAX_IDEAS_PER_UPLOAD:
        raise GamesProblem(400, "invalid_body", f"send {{\"ideas\": [...]}} with 1..{MAX_IDEAS_PER_UPLOAD} ideas")
    items = [clean_idea(raw) for raw in ideas]
    inserted = updated = linked = 0
    for item in items:
        status = "explored" if item["game_ids"] and item["status"] == "unexplored" else item["status"]
        cursor.execute(
            """
            INSERT INTO arc3_game_ideas (idea_id, source, title, axis, pitch, details, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (idea_id) DO UPDATE SET
                source = EXCLUDED.source,
                title = EXCLUDED.title,
                axis = EXCLUDED.axis,
                pitch = EXCLUDED.pitch,
                details = EXCLUDED.details,
                status = CASE WHEN arc3_game_ideas.status = 'unexplored' THEN EXCLUDED.status
                              ELSE arc3_game_ideas.status END,
                updated_at = now()
            RETURNING (xmax = 0)
            """,
            (item["idea_id"], item["source"], item["title"], item["axis"], item["pitch"],
             json.dumps(item["details"]), status),
        )
        if cursor.fetchone()[0]:
            inserted += 1
        else:
            updated += 1
        for game_id in item["game_ids"]:
            cursor.execute(
                "INSERT INTO arc3_game_idea_games (idea_id, game_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (item["idea_id"], game_id),
            )
            linked += cursor.rowcount
    return {"apiVersion": 1, "inserted": inserted, "updated": updated, "linked": linked}


def list_ideas(cursor: Any, query: dict[str, list[str]]) -> dict[str, Any]:
    """One page of one board column, plus the counts every column and source filter needs."""

    status = (query.get("status") or [""])[0]
    if status and status not in IDEA_STATUSES:
        raise GamesProblem(400, "invalid_status", f"status must be one of {IDEA_STATUSES}")
    source = (query.get("source") or [""])[0]
    if source and not IDEA_SOURCE_RE.fullmatch(source):
        raise GamesProblem(400, "invalid_source", "unknown source")
    search = (query.get("q") or [""])[0].strip()
    if len(search) > 80:
        raise GamesProblem(400, "invalid_q", "search is limited to 80 characters")
    try:
        limit = max(1, min(200, int((query.get("limit") or ["40"])[0])))
        offset = max(0, int((query.get("offset") or ["0"])[0]))
    except ValueError as exc:
        raise GamesProblem(400, "invalid_page", "limit and offset must be integers") from exc

    where, params = ["TRUE"], []
    if source:
        where.append("i.source = %s")
        params.append(source)
    if search:
        like = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where.append(
            "(i.idea_id ILIKE %s OR i.title ILIKE %s OR i.axis ILIKE %s OR i.pitch ILIKE %s "
            "OR EXISTS (SELECT 1 FROM arc3_game_idea_games AS sg WHERE sg.idea_id = i.idea_id AND sg.game_id ILIKE %s))"
        )
        params.extend([like] * 5)
    filters = " AND ".join(where)
    cursor.execute(f"SELECT i.status, count(*) FROM arc3_game_ideas AS i WHERE {filters} GROUP BY i.status", params)
    counts = {name: 0 for name in IDEA_STATUSES}
    counts.update({name: n for name, n in cursor.fetchall()})
    cursor.execute("SELECT source, count(*) FROM arc3_game_ideas GROUP BY source ORDER BY source")
    sources = {name: n for name, n in cursor.fetchall()}

    page_where = filters + (" AND i.status = %s" if status else "")
    page_params = [*params, *([status] if status else [])]
    cursor.execute(
        f"""
        SELECT i.idea_id, i.source, i.title, i.axis, i.pitch, i.status, i.note, i.updated_at, i.updated_by,
               COALESCE(array_agg(g.game_id ORDER BY g.game_id) FILTER (WHERE g.game_id IS NOT NULL), '{{}}') AS games
        FROM arc3_game_ideas AS i
        LEFT JOIN arc3_game_idea_games AS g ON g.idea_id = i.idea_id
        WHERE {page_where}
        GROUP BY i.idea_id
        ORDER BY i.updated_at DESC, i.source, i.idea_id
        LIMIT %s OFFSET %s
        """,
        (*page_params, limit, offset),
    )
    ideas = [
        {
            "ideaId": row["idea_id"],
            "source": row["source"],
            "title": row["title"],
            "axis": row["axis"],
            "pitch": row["pitch"],
            "status": row["status"],
            "note": row["note"],
            "games": list(row["games"] or []),
            "updatedAt": iso(row["updated_at"]),
            "updatedBy": row["updated_by"],
        }
        for row in _rows(cursor)
    ]
    return {"apiVersion": 1, "counts": counts, "sources": sources, "offset": offset, "limit": limit, "ideas": ideas}


def update_idea(cursor: Any, idea_id: str, payload: Any, *, email: str) -> dict[str, Any]:
    """Move a card, or annotate it (team only)."""

    if not IDEA_ID_RE.fullmatch(idea_id):
        raise GamesProblem(400, "invalid_idea_id", "invalid idea id")
    if not isinstance(payload, dict):
        raise GamesProblem(400, "invalid_body", "expected a JSON object")
    status = payload.get("status")
    if status is not None and status not in IDEA_STATUSES:
        raise GamesProblem(400, "invalid_status", f"status must be one of {IDEA_STATUSES}")
    note_given = "note" in payload
    note = _text(payload.get("note"), "note", 2000)
    if status is None and not note_given:
        raise GamesProblem(400, "empty_update", "send a status, a note, or both")
    cursor.execute(
        """
        UPDATE arc3_game_ideas
        SET status = COALESCE(%s, status),
            note = CASE WHEN %s THEN %s ELSE note END,
            updated_at = now(),
            updated_by = %s
        WHERE idea_id = %s
        RETURNING idea_id, status, note, updated_at
        """,
        (status, note_given, note, email, idea_id),
    )
    row = cursor.fetchone()
    if not row:
        raise GamesProblem(404, "idea_not_found", "no such idea")
    return {"apiVersion": 1, "ideaId": row[0], "status": row[1], "note": row[2], "updatedAt": iso(row[3])}


# ── HTTP dispatch ────────────────────────────────────────────────────────────


def _json(status: int, payload: Any, *, public_read: bool = False) -> Response:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
    return Response(status, body, public_read=public_read)


def load_static_game_ids(manifest_path: Path | None) -> frozenset[str]:
    if not manifest_path or not manifest_path.is_file():
        return frozenset()
    try:
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return frozenset()
    return frozenset(entry["id"] for entry in entries if isinstance(entry, dict) and "id" in entry)


class GamesApi:
    PUBLIC_PREFIX = "/api/v1/public/games"
    TEAM_PREFIX = "/api/v1/games"

    def __init__(
        self,
        connect: Callable[[], Any],
        data_root: Path,
        publish_token: str,
        static_manifest: Path | None = None,
    ):
        self.connect = connect
        self.data_root = data_root
        self.publish_token = publish_token
        self.static_game_ids = load_static_game_ids(static_manifest)
        self.public_visitor_limit = SlidingWindowLimiter(12, 600)
        self.public_global_limit = SlidingWindowLimiter(300, 600)

    @classmethod
    def owns(cls, path: str) -> bool:
        return path.startswith(cls.PUBLIC_PREFIX + "/") or path == cls.PUBLIC_PREFIX or path.startswith(
            cls.TEAM_PREFIX + "/"
        )

    # Identity. Only ever called on team routes, which oauth2-proxy has authenticated; the
    # public prefix is skip-auth, so a header there could be forged and is never read.
    @staticmethod
    def team_email(headers: Any) -> str:
        email = (headers.get("X-Forwarded-Email") or "").strip().lower()
        if not EMAIL_RE.fullmatch(email):
            raise GamesProblem(401, "sign_in_required", "sign in to use this endpoint")
        return email

    def require_token(self, headers: Any) -> None:
        if not self.publish_token:
            raise GamesProblem(503, "publisher_disabled", "publication API is not configured")
        authorization = headers.get("Authorization", "")
        supplied = authorization[len("Bearer ") :] if authorization.startswith("Bearer ") else ""
        if not supplied or not secrets.compare_digest(supplied, self.publish_token):
            raise GamesProblem(401, "unauthorized", "invalid publication token")

    @staticmethod
    def ip_hint(headers: Any) -> str | None:
        forwarded = headers.get("X-Real-IP") or (headers.get("X-Forwarded-For") or "").split(",")[0]
        forwarded = forwarded.strip()
        return forwarded[:64] or None

    def _read(self, read_body: Callable[[int], bytes], headers: Any, limit: int) -> Any:
        try:
            length = int(headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise GamesProblem(400, "invalid_content_length", "invalid Content-Length") from exc
        if length <= 0 or length > limit:
            raise GamesProblem(413 if length > limit else 400, "invalid_body", f"body must be 1..{limit} bytes")
        try:
            return json.loads(read_body(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GamesProblem(400, "invalid_json", "body is not JSON") from exc

    def handle(self, method: str, raw_path: str, headers: Any, read_body: Callable[[int], bytes]) -> Response:
        parsed = urlparse(raw_path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            return self._route(method, path, query, headers, read_body)
        except GamesProblem as exc:
            return _json(exc.status, {"error": exc.code, "message": exc.message})

    def _route(self, method: str, path: str, query: dict[str, list[str]], headers: Any, read_body: Callable[[int], bytes]) -> Response:
        public = self.PUBLIC_PREFIX
        team = self.TEAM_PREFIX

        # Machines (bearer token). oauth2-proxy lets these two paths through unauthenticated.
        if path == f"{team}/publication":
            self.require_token(headers)
            if method == "PUT":
                payload = self._read(read_body, headers, MAX_PUBLICATION_BODY)
                result = publish_version(self.connect, self.data_root, payload)
                return _json(201 if result["status"] == "published" else 200, {"apiVersion": 1, **result})
            if method == "GET":
                with self._cursor() as cursor:
                    return _json(200, known_versions(cursor, (query.get("game_id") or [None])[0]))
            raise GamesProblem(405, "method_not_allowed", "use GET or PUT")
        if path == f"{team}/ideas/publication":
            self.require_token(headers)
            if method != "PUT":
                raise GamesProblem(405, "method_not_allowed", "use PUT")
            payload = self._read(read_body, headers, MAX_IDEAS_BODY)
            with self._cursor(commit=True) as cursor:
                return _json(200, upsert_ideas(cursor, payload))
        if path == f"{team}/training-set":
            self.require_token(headers)
            if method != "GET":
                raise GamesProblem(405, "method_not_allowed", "use GET")
            with self._cursor() as cursor:
                return _json(200, training_set(cursor))
        if path == f"{team}/feedback-export":
            self.require_token(headers)
            if method != "GET":
                raise GamesProblem(405, "method_not_allowed", "use GET")
            return self._jsonl(query, include_ip=False)

        # Anyone.
        if path.startswith(public + "/") or path == public:
            if method == "GET":
                if path == f"{public}/trees":
                    with self._cursor() as cursor:
                        return _json(200, list_trees(cursor, query), public_read=True)
                match = re.fullmatch(rf"{re.escape(public)}/trees/([^/]+)", path)
                if match:
                    with self._cursor() as cursor:
                        return _json(200, tree_detail(cursor, unquote(match.group(1))), public_read=True)
                if path == f"{public}/next":
                    with self._cursor() as cursor:
                        return _json(200, next_version(cursor, query, reviewer=None), public_read=True)
                if path == f"{public}/manifest.json":
                    with self._cursor() as cursor:
                        return _json(200, public_manifest(cursor), public_read=True)
            if method == "POST" and path == f"{public}/feedback":
                item = clean_feedback(self._read(read_body, headers, MAX_FEEDBACK_BODY))
                visitor = item["visitor_id"] or "no-visitor-id"
                if not self.public_global_limit.allow("all") or not self.public_visitor_limit.allow(visitor):
                    raise GamesProblem(429, "slow_down", "too much feedback too fast; try again in a few minutes")
                with self._cursor(commit=True) as cursor:
                    result = insert_feedback(
                        cursor,
                        item,
                        reviewer_class="public",
                        reviewer=item["nickname"],
                        ip_hint=self.ip_hint(headers),
                        static_game_ids=self.static_game_ids,
                    )
                return _json(201, result)
            raise GamesProblem(404, "not_found", "not found")

        # The signed-in team (oauth2-proxy has authenticated every request that gets here).
        email = self.team_email(headers)
        if method == "GET":
            if path == f"{team}/me":
                return _json(200, {"apiVersion": 1, "email": email, "reviewerClass": "team"})
            if path == f"{team}/ideas":
                with self._cursor() as cursor:
                    return _json(200, list_ideas(cursor, query))
            match = re.fullmatch(rf"{re.escape(team)}/trees/([^/]+)/notes", path)
            if match:
                with self._cursor() as cursor:
                    return _json(200, tree_notes(cursor, unquote(match.group(1))))
            if path == f"{team}/next":
                with self._cursor() as cursor:
                    return _json(200, next_version(cursor, query, reviewer=email))
            if path == f"{team}/feedback":
                return self._jsonl(query, include_ip=True)
            if path == f"{team}/training-set":
                with self._cursor() as cursor:
                    return _json(200, training_set(cursor))
        if method == "POST":
            match = re.fullmatch(rf"{re.escape(team)}/ideas/([^/]+)", path)
            if match:
                body = self._read(read_body, headers, 8 * 1024)
                with self._cursor(commit=True) as cursor:
                    return _json(200, update_idea(cursor, unquote(match.group(1)), body, email=email))
            if path == f"{team}/feedback":
                item = clean_feedback(self._read(read_body, headers, MAX_FEEDBACK_BODY))
                with self._cursor(commit=True) as cursor:
                    result = insert_feedback(
                        cursor,
                        item,
                        reviewer_class="team",
                        reviewer=email,
                        ip_hint=None,
                        static_game_ids=self.static_game_ids,
                    )
                return _json(201, result)
            match = re.fullmatch(rf"{re.escape(team)}/versions/([^/]+)/train", path)
            if match:
                body = self._read(read_body, headers, 1024)
                good = body.get("good") if isinstance(body, dict) else None
                if not isinstance(good, bool):
                    raise GamesProblem(400, "invalid_good", "send {\"good\": true|false}")
                with self._cursor(commit=True) as cursor:
                    return _json(200, set_train_ok(cursor, unquote(match.group(1)), good, email=email))
            match = re.fullmatch(rf"{re.escape(team)}/feedback/(\d+)/hidden", path)
            if match:
                body = self._read(read_body, headers, 1024)
                hidden = body.get("hidden") if isinstance(body, dict) else None
                if not isinstance(hidden, bool):
                    raise GamesProblem(400, "invalid_hidden", "send {\"hidden\": true|false}")
                with self._cursor(commit=True) as cursor:
                    cursor.execute(
                        "UPDATE arc3_game_feedback SET hidden = %s WHERE feedback_id = %s RETURNING feedback_id",
                        (hidden, int(match.group(1))),
                    )
                    if not cursor.fetchone():
                        raise GamesProblem(404, "feedback_not_found", "no such feedback")
                print(f"games: feedback {match.group(1)} hidden={hidden} by {email}", flush=True)
                return _json(200, {"apiVersion": 1, "feedbackId": int(match.group(1)), "hidden": hidden})
        raise GamesProblem(404, "not_found", "not found")

    def _jsonl(self, query: dict[str, list[str]], *, include_ip: bool) -> Response:
        with self._cursor() as cursor:
            lines = [
                json.dumps(record, ensure_ascii=False, separators=(",", ":"), default=str)
                for record in export_feedback(cursor, query, include_ip=include_ip)
            ]
        body = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
        return Response(200, body, "application/x-ndjson; charset=utf-8")

    class _Cursor:
        def __init__(self, connect: Callable[[], Any], commit: bool):
            self.connection = connect()
            self.commit = commit
            self.cursor = None

        def __enter__(self):
            self.cursor = self.connection.cursor()
            return self.cursor

        def __exit__(self, exc_type, exc, tb):
            try:
                if exc_type is None and self.commit:
                    self.connection.commit()
                else:
                    self.connection.rollback()
            finally:
                self.cursor.close()
                self.connection.close()
            return False

    def _cursor(self, commit: bool = False) -> "GamesApi._Cursor":
        return GamesApi._Cursor(self.connect, commit)

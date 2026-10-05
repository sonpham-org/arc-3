"""Evidence-backed trace review. Diagnostics and decisions are never automatic rewards.

Only the exact publication/export endpoints accept a machine token. All browsing and
human decisions require the OAuth team's forwarded identity. No public invite routes.
"""
from __future__ import annotations

import json
import os
import re
import secrets
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

try:
    from .triage_contract import validate_item
except ImportError:
    from triage_contract import validate_item

MAX_PUBLICATION = 16 * 1024 * 1024
MAX_ITEMS = 1000
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
EMAIL_RE = re.compile(r"^[^\s@]{1,200}@[^\s@]{1,200}$")
VERDICTS = {"confirmed", "reasonable", "insufficient", "dismissed"}


@dataclass
class Response:
    status: int
    body: bytes
    content_type: str = "application/json; charset=utf-8"


class TriageProblem(ValueError):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _json(status: int, payload: Any) -> Response:
    return Response(status, json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode())


def canonical(item: Any) -> str:
    return json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _id(value: Any) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise TriageProblem(400, "invalid_id", "id must be a SHA-256 digest")
    return value


def clean_decision(value: Any) -> dict:
    if not isinstance(value, dict):
        raise TriageProblem(400, "invalid_decision", "send a JSON object")
    verdict, seconds, note = value.get("verdict"), value.get("seconds", 0), value.get("note", "")
    if not isinstance(verdict, str) or verdict not in VERDICTS:
        raise TriageProblem(400, "invalid_verdict", "choose confirmed, reasonable, insufficient or dismissed")
    if type(seconds) is not int or not 0 <= seconds <= 86400:
        raise TriageProblem(400, "invalid_seconds", "seconds must be an integer in 0..86400")
    if not isinstance(note, str) or len(note) > 4000 or "\0" in note:
        raise TriageProblem(400, "invalid_note", "note must be text of at most 4000 characters")
    try:
        note.encode("utf-8")
    except UnicodeError as exc:
        raise TriageProblem(400, "invalid_note", "note must be valid Unicode") from exc
    return {"id": _id(value.get("id")), "verdict": verdict, "note": note.strip(), "seconds": seconds}


def clean_publication(body: Any) -> list[dict]:
    if not isinstance(body, dict) or not isinstance(body.get("items"), list):
        raise TriageProblem(400, "invalid_publication", "send an object containing items")
    if not 1 <= len(body["items"]) <= MAX_ITEMS:
        raise TriageProblem(400, "invalid_publication", f"publish 1..{MAX_ITEMS} items at a time")
    items = {}
    for raw in body["items"]:
        try:
            item = validate_item(raw)
            encoded = canonical(item)
            encoded.encode("utf-8")
            if "\\u0000" in encoded:
                raise ValueError("NUL characters are not supported")
        except (ValueError, TypeError, KeyError, UnicodeError) as exc:
            raise TriageProblem(400, "invalid_item", str(exc)) from exc
        if item["route"] not in ("human", "assistant") or item["assessment"]["status"] == "no_issue":
            raise TriageProblem(400, "invalid_item", "publish only actionable diagnostics")
        if item["id"] in items and canonical(items[item["id"]]) != encoded:
            raise TriageProblem(409, "immutable_item", "an id names different content in this publication")
        items[item["id"]] = item
    return list(items.values())


def _lock_cluster(cursor: Any, cluster: str) -> None:
    # Same lock is used by publishers and reviewers, including the first occurrence.
    cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 7319))", (cluster,))


def publish(cursor: Any, items: list[dict]) -> dict:
    for item_id in sorted(item["id"] for item in items):
        _lock_cluster(cursor, "item:" + item_id)
    for cluster in sorted({item["cluster_key"] for item in items}):
        _lock_cluster(cursor, cluster)
    inserted = 0
    for item in items:
        cursor.execute("SELECT payload FROM trace_triage_items WHERE id = %s", (item["id"],))
        old = cursor.fetchone()
        if old:
            # Cache eviction may re-create the same judgment at a later time. Keep the
            # first timestamp; meaningful evidence/assessment changes still conflict.
            if canonical({k: v for k, v in old[0].items() if k != "created_at"}) != canonical(
                    {k: v for k, v in item.items() if k != "created_at"}):
                raise TriageProblem(409, "immutable_item", "published content cannot change under the same id")
            continue
        cursor.execute("SELECT status, route FROM trace_triage_items WHERE cluster_key = %s "
                       "ORDER BY updated_at DESC, id LIMIT 1", (item["cluster_key"],))
        resolved = cursor.fetchone()
        status = resolved[0] if resolved else "open"
        route = resolved[1] if resolved else item["route"]
        cursor.execute("INSERT INTO trace_triage_items "
                       "(id, cluster_key, game, route, priority, status, payload) "
                       "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)",
                       (item["id"], item["cluster_key"], item["game"], route, item["priority"],
                        status, canonical(item)))
        inserted += 1
    return {"status": "published", "items": len(items), "inserted": inserted, "training_approved": False}


def queue(cursor: Any, route: str, limit: int, exclude=()) -> dict:
    cursor.execute("""
        WITH ranked AS (
            SELECT payload, status, priority, length(payload::text) AS reading_size,
                   count(*) OVER (PARTITION BY cluster_key) AS occurrences,
                   row_number() OVER (PARTITION BY cluster_key ORDER BY priority DESC,
                       length(payload::text), id) AS position
            FROM trace_triage_items candidate WHERE status = 'open' AND route = %s
                AND NOT EXISTS (
                    SELECT 1 FROM trace_triage_items skipped
                    WHERE skipped.id = ANY(%s::text[]) AND skipped.cluster_key = candidate.cluster_key
                )
        )
        SELECT payload, status, occurrences FROM ranked WHERE position = 1
        ORDER BY priority DESC, occurrences DESC, reading_size, payload->>'id' LIMIT %s
    """, (route, list(exclude), limit))
    items = [{**payload, "route": route, "status": status, "occurrences": occurrences}
             for payload, status, occurrences in cursor.fetchall()]
    for item in items:
        item["decisions"] = decisions(cursor, item["cluster_key"])
    cursor.execute("""SELECT count(DISTINCT cluster_key) FILTER (WHERE status = 'open' AND route = 'human'),
                      count(DISTINCT cluster_key) FILTER (WHERE status = 'open' AND route = 'assistant'),
                      count(DISTINCT cluster_key) FILTER (WHERE status <> 'open') FROM trace_triage_items""")
    counts = dict(zip(("human", "assistant", "resolved"), cursor.fetchone()))
    return {"items": items, "counts": counts}


def decisions(cursor: Any, cluster: str) -> list[dict]:
    cursor.execute("SELECT item_id, reviewer, verdict, note, seconds, created_at "
                   "FROM trace_triage_decisions WHERE cluster_key = %s ORDER BY created_at, decision_id", (cluster,))
    keys = ("id", "reviewer", "verdict", "note", "seconds", "created_at")
    return [dict(zip(keys, row)) for row in cursor.fetchall()]


def read_item(cursor: Any, item_id: str) -> dict:
    cursor.execute("SELECT payload, status, cluster_key, route FROM trace_triage_items WHERE id = %s", (item_id,))
    row = cursor.fetchone()
    if not row:
        raise TriageProblem(404, "unknown_item", "this diagnostic does not exist")
    payload, status, cluster, route = row
    cursor.execute("SELECT count(*) FROM trace_triage_items WHERE cluster_key = %s", (cluster,))
    return {**payload, "route": route, "status": status, "occurrences": cursor.fetchone()[0],
            "decisions": decisions(cursor, cluster), "training_approved": False}


def decide(cursor: Any, item: dict, reviewer: str) -> dict:
    cursor.execute("SELECT cluster_key FROM trace_triage_items WHERE id = %s", (item["id"],))
    row = cursor.fetchone()
    if not row:
        raise TriageProblem(404, "unknown_item", "this diagnostic does not exist")
    cluster = row[0]
    _lock_cluster(cursor, cluster)
    cursor.execute("SELECT status FROM trace_triage_items WHERE id = %s", (item["id"],))
    status = cursor.fetchone()[0]
    # A retry is successful even if client elapsed time changed after a timeout.
    previous = decisions(cursor, cluster)
    if any(d["reviewer"] == reviewer and all(d[k] == item[k] for k in ("id", "verdict", "note"))
           for d in previous):
        return {"status": "saved", "id": item["id"], "training_approved": False}
    if status != "open":
        raise TriageProblem(409, "already_reviewed", "this issue was already reviewed; refresh the queue")
    cursor.execute("INSERT INTO trace_triage_decisions (item_id, cluster_key, reviewer, verdict, note, seconds) "
                   "VALUES (%s, %s, %s, %s, %s, %s)",
                   (item["id"], cluster, reviewer, item["verdict"], item["note"], item["seconds"]))
    if item["verdict"] == "insufficient":
        cursor.execute("UPDATE trace_triage_items SET status = 'open', route = 'assistant', updated_at = now() "
                       "WHERE cluster_key = %s", (cluster,))
    else:
        status = "dismissed" if item["verdict"] == "dismissed" else "resolved"
        cursor.execute("UPDATE trace_triage_items SET status = %s, updated_at = now() WHERE cluster_key = %s",
                       (status, cluster))
    return {"status": "saved", "id": item["id"], "training_approved": False}


def review_hold(payload: dict, status: str, history: list[dict]) -> dict:
    """Describe a diagnostic hold for an external record picker; never claim enforcement.

    A consumer must exclude records containing a held step of this exact source. Match
    the source digest as well as path/step: a reused run name must not target new bytes.
    Multiple diagnostics on a record combine with OR; clearing one is not global approval.
    The deployed Plan C picker is outside this checkout and does not consume this yet.
    """
    latest = history[-1]["verdict"] if history else None
    held = status == "open" or latest not in ("reasonable", "dismissed")
    scope = {key: payload[key] for key in ("path_id", "trace_sha256", "game", "build", "level", "step")}
    # Only expose a separate run/play identity when it exactly matches our indexer's
    # format. Opaque third-party path IDs remain valid but must be matched as supplied.
    match = re.fullmatch(r"(?P<run>.+):(?P<game>[a-z0-9]{4})_p(?P<pass>\d+):L(?P<level>\d+)", payload["path_id"])
    if match and match["game"] == payload["game"] and int(match["level"]) == payload["level"]:
        scope.update(run=match["run"], play=f"{match['game']}_p{match['pass']}", pass_index=int(match["pass"]))
    return {"review_hold": held, "review_hold_scope": scope, "training_approved": False}


def export(cursor: Any, after: str, limit: int) -> dict:
    cursor.execute("SELECT payload, status, cluster_key, route FROM trace_triage_items WHERE id > %s ORDER BY id LIMIT %s",
                   (after, limit + 1))
    rows = cursor.fetchall()
    result = []
    cache = {}
    for payload, status, cluster, route in rows[:limit]:
        if cluster not in cache:
            cache[cluster] = decisions(cursor, cluster)
        result.append({**payload, "route": route, "status": status, "decisions": cache[cluster],
                       **review_hold(payload, status, cache[cluster])})
    return {"items": result, "next_cursor": result[-1]["id"] if len(rows) > limit else None,
            "training_approved": False, "training_enforcement": "external_consumer_required"}


class TraceTriageApi:
    PREFIX = "/api/v1/review/triage"

    def __init__(self, connect: Callable[[], Any], publish_token: str):
        self.connect, self.publish_token = connect, publish_token

    @classmethod
    def owns(cls, path: str) -> bool:
        return path == cls.PREFIX or path.startswith(cls.PREFIX + "/")

    @contextmanager
    def _cursor(self, write=False):
        conn = self.connect()
        try:
            with conn.cursor() as cursor:
                yield cursor
            if write:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _token(self, headers: Any):
        if not self.publish_token:
            raise TriageProblem(503, "publisher_disabled", "publication token is not configured")
        expected = "Bearer " + self.publish_token
        actual = headers.get("Authorization", "")
        if not secrets.compare_digest(actual.encode("utf-8"), expected.encode("utf-8")):
            raise TriageProblem(401, "unauthorized", "invalid publication token")

    @staticmethod
    def _team(headers: Any) -> str:
        email = headers.get("X-Forwarded-Email", "").strip().casefold()
        if not EMAIL_RE.fullmatch(email):
            raise TriageProblem(401, "sign_in_required", "sign in to use this endpoint")
        allowed = {e.casefold() for e in re.split(r"[,\s]+", os.environ.get("ALLOWED_EMAILS", "")) if e}
        if email not in allowed:
            raise TriageProblem(403, "not_on_team", "this account is not on the team list")
        return email

    @staticmethod
    def _body(headers: Any, read_body: Callable, limit: int) -> Any:
        try:
            length = int(headers.get("Content-Length", "0"))
        except (TypeError, ValueError) as exc:
            raise TriageProblem(400, "invalid_length", "Content-Length is required") from exc
        if not 0 < length <= limit:
            raise TriageProblem(413 if length > limit else 400, "invalid_length", f"body must be 1..{limit} bytes")
        if headers.get("Content-Encoding", "identity") != "identity":
            raise TriageProblem(415, "invalid_encoding", "send uncompressed JSON")
        raw = read_body(length)
        if len(raw) != length:
            raise TriageProblem(400, "incomplete_body", "body was truncated")
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise TriageProblem(400, "invalid_json", "send valid JSON") from exc

    def handle(self, method: str, raw_path: str, headers: Any, read_body: Callable) -> Response:
        parsed = urlparse(raw_path)
        query = parse_qs(parsed.query)
        path = parsed.path
        try:
            machine = path in (self.PREFIX + "/publication", self.PREFIX + "/export")
            reviewer = None
            if machine:
                self._token(headers)
            else:
                reviewer = self._team(headers)
            action = path.removeprefix(self.PREFIX + "/")
            methods = {"publication": "PUT", "export": "GET", "queue": "GET", "item": "GET", "decision": "POST"}
            if action not in methods:
                raise TriageProblem(404, "not_found", "not found")
            if method != methods[action]:
                raise TriageProblem(405, "method_not_allowed", "use " + methods[action])
            if action == "publication":
                items = clean_publication(self._body(headers, read_body, MAX_PUBLICATION))
                with self._cursor(write=True) as cursor:
                    return _json(200, publish(cursor, items))
            if action == "decision":
                item = clean_decision(self._body(headers, read_body, 32768))
                with self._cursor(write=True) as cursor:
                    return _json(200, decide(cursor, item, reviewer))
            if action == "item":
                item_id = _id(query.get("id", [None])[0])
                with self._cursor() as cursor:
                    return _json(200, read_item(cursor, item_id))
            default, maximum = (5, 20) if action == "queue" else (1000, 5000)
            try:
                limit = int(query.get("limit", [str(default)])[0])
            except ValueError as exc:
                raise TriageProblem(400, "invalid_limit", "limit must be an integer") from exc
            if not 1 <= limit <= maximum:
                raise TriageProblem(400, "invalid_limit", f"limit must be 1..{maximum}")
            if action == "queue":
                route = query.get("route", ["human"])[0]
                if route not in ("human", "assistant"):
                    raise TriageProblem(400, "invalid_route", "route must be human or assistant")
                values = query.get("exclude", [])
                excluded = [item for value in values for item in value.split(",")]
                if len(excluded) > 100:
                    raise TriageProblem(400, "invalid_exclude", "exclude at most 100 item ids")
                excluded = list(dict.fromkeys(_id(item) for item in excluded))
                with self._cursor() as cursor:
                    return _json(200, queue(cursor, route, limit, excluded))
            after = query.get("after", [""])[0]
            if after:
                _id(after)
            with self._cursor() as cursor:
                return _json(200, export(cursor, after, limit))
        except TriageProblem as exc:
            return _json(exc.status, {"error": exc.code, "message": exc.message})

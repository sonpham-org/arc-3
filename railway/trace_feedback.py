"""Thumbs up / thumbs down on the model's own output in a run, with the reason.

A reviewer reading a turn in the run inspector marks one section of what the model produced
(THINKING, ASSISTANT, a TOOL CALL) as right or wrong and says why. Those marks are labels for
supervised fine-tuning and RL, so each one is stored with the exact text it judged:

  * the position (run, game, step, section) says where the reviewer was looking;
  * content_sha256 + content say what they were looking at.

A run can be re-exported in place (publish --replace). If the text at a position changes, the
old mark stays attached to the old text and simply stops showing at that position; it is never
silently re-aimed at different words. One reviewer has one mark per (position, text); voting
again replaces it, and sending vote = null removes it.

The route prefix decides who is calling, exactly as in games_store:

  /api/v1/traces/feedback          the signed-in team. oauth2-proxy authenticates the request
                                   and injects X-Forwarded-Email, which becomes the reviewer.
                                   GET lists the marks on one game (or one step) of a run,
                                   POST sets, changes or clears the caller's mark.
                                   GET ?format=jsonl is the export below, for a signed-in person.
  /api/v1/traces/feedback-export   machines holding ARC3_PUBLISH_TOKEN: every mark as JSON
                                   lines, text included, for whatever builds the training set.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from urllib.parse import parse_qs, urlparse


# Kept identical to games_store's, on purpose: this module imports nothing from its siblings so
# it loads the same way in the image (flat files) and under test (the railway package).
EMAIL_RE = re.compile(r"^[^\s@]{1,200}@[^\s@]{1,200}$")
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
VOTES = ("up", "down")
# The label a trainer wants: +1 keep this reasoning, -1 this reasoning was wrong.
VOTE_VALUE = {"up": 1, "down": -1}

MAX_BODY = 2 * 1024 * 1024
MAX_CONTENT_CHARS = 500_000
MAX_REASON = 4000
MAX_LABEL = 120
MAX_GAME_ID = 100
MAX_INDEX = 1_000_000
MAX_EXPORT_ROWS = 50_000

_LONE_SURROGATE = re.compile(r"[\ud800-\udfff]")


@dataclass
class Response:
    status: int
    body: bytes
    content_type: str = "application/json; charset=utf-8"


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class TraceFeedbackProblem(Exception):
    """An expected failure that is safe to show the client."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def canonical_text(value: str) -> str:
    """The text as it is stored and hashed.

    Postgres text cannot hold NUL or a lone surrogate, and the browser's TextEncoder turns a
    lone surrogate into U+FFFD, so both sides drop NULs and replace lone surrogates the same
    way. docs/static/js/trace-votes.js applies the identical rule before it hashes.
    """

    return _LONE_SURROGATE.sub("�", value.replace("\x00", ""))


def content_sha256(value: str) -> str:
    return hashlib.sha256(canonical_text(value).encode("utf-8")).hexdigest()


def _int(value: Any, field: str, *, required: bool = True) -> int | None:
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_INDEX:
        raise TraceFeedbackProblem(400, f"invalid_{field}", f"{field} must be an integer in 0..{MAX_INDEX}")
    return value


def _run_id(value: Any) -> str:
    if not isinstance(value, str) or not RUN_ID_RE.fullmatch(value):
        raise TraceFeedbackProblem(400, "invalid_run", "run must be a run id")
    return value


def _short_text(value: Any, field: str, limit: int, *, required: bool = False) -> str | None:
    if value is None or value == "":
        if required:
            raise TraceFeedbackProblem(400, f"invalid_{field}", f"{field} is required")
        return None
    if not isinstance(value, str):
        raise TraceFeedbackProblem(400, f"invalid_{field}", f"{field} must be text")
    text = canonical_text(value).strip()
    if len(text) > limit:
        raise TraceFeedbackProblem(400, f"invalid_{field}", f"{field} is longer than {limit} characters")
    if not text and required:
        raise TraceFeedbackProblem(400, f"invalid_{field}", f"{field} is required")
    return text or None


def clean_vote(payload: Any) -> dict[str, Any]:
    """Validate one POST body. Returns snake_case fields ready for SQL."""

    if not isinstance(payload, dict):
        raise TraceFeedbackProblem(400, "invalid_body", "send a JSON object")
    vote = payload.get("vote")
    if vote is not None and vote not in VOTES:
        raise TraceFeedbackProblem(400, "invalid_vote", 'vote must be "up", "down" or null')
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise TraceFeedbackProblem(400, "invalid_content", "content must be the section's text")
    if len(content) > MAX_CONTENT_CHARS:
        raise TraceFeedbackProblem(413, "invalid_content", f"content is longer than {MAX_CONTENT_CHARS} characters")
    content = canonical_text(content)
    return {
        "run_id": _run_id(payload.get("run")),
        "game_index": _int(payload.get("gameIndex"), "gameIndex"),
        "game_id": _short_text(payload.get("gameId"), "gameId", MAX_GAME_ID),
        "step_index": _int(payload.get("stepIndex"), "stepIndex"),
        "turn": _int(payload.get("turn"), "turn", required=False),
        "section_index": _int(payload.get("sectionIndex"), "sectionIndex"),
        "section_label": _short_text(payload.get("sectionLabel"), "sectionLabel", MAX_LABEL, required=True),
        "content": content,
        "content_sha256": content_sha256(content),
        "vote": vote,
        "reason": _short_text(payload.get("reason"), "reason", MAX_REASON),
    }


_COLUMNS = (
    "feedback_id, run_id, game_index, game_id, step_index, turn, section_index, section_label, "
    "content_sha256, vote, reason, reviewer, created_at, updated_at"
)


def _rows(cursor: Any) -> list[dict[str, Any]]:
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def vote_record(row: dict[str, Any], *, viewer: str | None = None) -> dict[str, Any]:
    """One mark as the viewer and the export see it. `content` appears only if it was selected."""

    record = {
        "feedbackId": row["feedback_id"],
        "run": row["run_id"],
        "gameIndex": row["game_index"],
        "gameId": row["game_id"],
        "stepIndex": row["step_index"],
        "turn": row["turn"],
        "sectionIndex": row["section_index"],
        "sectionLabel": row["section_label"],
        "contentSha256": row["content_sha256"],
        "vote": row["vote"],
        "value": VOTE_VALUE[row["vote"]],
        "reason": row["reason"],
        "reviewer": row["reviewer"],
        "createdAt": iso(row["created_at"]),
        "updatedAt": iso(row["updated_at"]),
    }
    if viewer is not None:
        record["mine"] = row["reviewer"] == viewer
    if "content" in row:
        record["content"] = row["content"]
    return record


def set_vote(cursor: Any, item: dict[str, Any], *, reviewer: str) -> dict[str, Any]:
    """Set, change or (vote = None) clear this reviewer's mark on one section's exact text."""

    key = (
        item["run_id"],
        item["game_index"],
        item["step_index"],
        item["section_index"],
        item["content_sha256"],
        reviewer,
    )
    if item["vote"] is None:
        cursor.execute(
            """
            DELETE FROM arc3_trace_feedback
            WHERE run_id = %s AND game_index = %s AND step_index = %s AND section_index = %s
              AND content_sha256 = %s AND reviewer = %s
            """,
            key,
        )
        return {"apiVersion": 1, "status": "cleared", "contentSha256": item["content_sha256"], "vote": None}
    cursor.execute(
        f"""
        INSERT INTO arc3_trace_feedback (
            run_id, game_index, game_id, step_index, turn, section_index, section_label,
            content_sha256, content, vote, reason, reviewer
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (run_id, game_index, step_index, section_index, content_sha256, reviewer)
        DO UPDATE SET
            vote = EXCLUDED.vote,
            reason = EXCLUDED.reason,
            game_id = COALESCE(EXCLUDED.game_id, arc3_trace_feedback.game_id),
            turn = COALESCE(EXCLUDED.turn, arc3_trace_feedback.turn),
            section_label = EXCLUDED.section_label,
            updated_at = now()
        RETURNING {_COLUMNS}
        """,
        (
            item["run_id"],
            item["game_index"],
            item["game_id"],
            item["step_index"],
            item["turn"],
            item["section_index"],
            item["section_label"],
            item["content_sha256"],
            item["content"],
            item["vote"],
            item["reason"],
            reviewer,
        ),
    )
    row = _rows(cursor)[0]
    return {"apiVersion": 1, "status": "saved", **vote_record(row, viewer=reviewer)}


def _query_int(query: dict[str, list[str]], name: str) -> int | None:
    raw = (query.get(name) or [None])[0]
    if raw is None or raw == "":
        return None
    if not raw.isdigit() or int(raw) > MAX_INDEX:
        raise TraceFeedbackProblem(400, f"invalid_{name}", f"{name} must be an integer in 0..{MAX_INDEX}")
    return int(raw)


def list_scope(query: dict[str, list[str]]) -> tuple[str, int, int | None]:
    """(run, game, step or None) from a list query. Raises before any database work."""

    run_id = _run_id((query.get("run") or [None])[0])
    game_index = _query_int(query, "game")
    if game_index is None:
        raise TraceFeedbackProblem(400, "invalid_game", "game is required")
    return run_id, game_index, _query_int(query, "step")


def list_votes(cursor: Any, query: dict[str, list[str]], *, viewer: str) -> dict[str, Any]:
    """Every reviewer's marks on one game of a run, or on one step of it. No section text."""

    run_id, game_index, step_index = list_scope(query)
    where = "run_id = %s AND game_index = %s"
    params: list[Any] = [run_id, game_index]
    if step_index is not None:
        where += " AND step_index = %s"
        params.append(step_index)
    cursor.execute(
        f"SELECT {_COLUMNS} FROM arc3_trace_feedback WHERE {where} "
        "ORDER BY step_index, section_index, updated_at, feedback_id",
        params,
    )
    return {
        "apiVersion": 1,
        "me": viewer,
        "run": run_id,
        "gameIndex": game_index,
        "votes": [vote_record(row, viewer=viewer) for row in _rows(cursor)],
    }


def _since(query: dict[str, list[str]]) -> datetime | None:
    raw = (query.get("since") or [None])[0]
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TraceFeedbackProblem(400, "invalid_since", "since must be an ISO-8601 timestamp") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def export_filter(query: dict[str, list[str]]) -> tuple[list[str], list[Any]]:
    """SQL conditions and their parameters for an export query. Raises before any database work."""

    where: list[str] = []
    params: list[Any] = []
    run = (query.get("run") or [None])[0]
    if run:
        where.append("run_id = %s")
        params.append(_run_id(run))
    vote = (query.get("vote") or [None])[0]
    if vote:
        if vote not in VOTES:
            raise TraceFeedbackProblem(400, "invalid_vote", 'vote must be "up" or "down"')
        where.append("vote = %s")
        params.append(vote)
    reviewer = (query.get("reviewer") or [None])[0]
    if reviewer:
        where.append("reviewer = %s")
        params.append(reviewer.strip().lower())
    since = _since(query)
    if since is not None:
        where.append("updated_at >= %s")
        params.append(since)
    return where, params


def export_votes(cursor: Any, query: dict[str, list[str]]) -> Iterable[dict[str, Any]]:
    """Marks as training records, oldest first. Filters: run, vote, reviewer, since, content=0."""

    where, params = export_filter(query)
    columns = _COLUMNS if query.get("content") == ["0"] else f"{_COLUMNS}, content"
    cursor.execute(
        f"SELECT {columns} FROM arc3_trace_feedback "
        + (f"WHERE {' AND '.join(where)} " if where else "")
        + f"ORDER BY updated_at, feedback_id LIMIT {MAX_EXPORT_ROWS}",
        params,
    )
    return [vote_record(row) for row in _rows(cursor)]


def _json(status: int, payload: Any) -> Response:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
    return Response(status, body)


class TraceFeedbackApi:
    PREFIX = "/api/v1/traces"

    def __init__(self, connect: Callable[[], Any], publish_token: str):
        self.connect = connect
        self.publish_token = publish_token

    @classmethod
    def owns(cls, path: str) -> bool:
        return path.startswith(cls.PREFIX + "/")

    # Identity. Only ever read on the signed-in routes, which oauth2-proxy has authenticated;
    # the export path is skip-auth, so a header there could be forged and is never read.
    @staticmethod
    def team_email(headers: Any) -> str:
        email = (headers.get("X-Forwarded-Email") or "").strip().lower()
        if not EMAIL_RE.fullmatch(email):
            raise TraceFeedbackProblem(401, "sign_in_required", "sign in to use this endpoint")
        return email

    def require_token(self, headers: Any) -> None:
        if not self.publish_token:
            raise TraceFeedbackProblem(503, "publisher_disabled", "publication API is not configured")
        authorization = headers.get("Authorization", "")
        supplied = authorization[len("Bearer ") :] if authorization.startswith("Bearer ") else ""
        if not supplied or not secrets.compare_digest(supplied, self.publish_token):
            raise TraceFeedbackProblem(401, "unauthorized", "invalid publication token")

    @staticmethod
    def _read(read_body: Callable[[int], bytes], headers: Any) -> Any:
        try:
            length = int(headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise TraceFeedbackProblem(400, "invalid_content_length", "invalid Content-Length") from exc
        if length <= 0 or length > MAX_BODY:
            raise TraceFeedbackProblem(
                413 if length > MAX_BODY else 400, "invalid_body", f"body must be 1..{MAX_BODY} bytes"
            )
        try:
            return json.loads(read_body(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TraceFeedbackProblem(400, "invalid_json", "body is not JSON") from exc

    def handle(self, method: str, raw_path: str, headers: Any, read_body: Callable[[int], bytes]) -> Response:
        parsed = urlparse(raw_path)
        try:
            return self._route(method, parsed.path, parse_qs(parsed.query), headers, read_body)
        except TraceFeedbackProblem as exc:
            return _json(exc.status, {"error": exc.code, "message": exc.message})

    def _route(
        self,
        method: str,
        path: str,
        query: dict[str, list[str]],
        headers: Any,
        read_body: Callable[[int], bytes],
    ) -> Response:
        # Machines (bearer token). oauth2-proxy lets this one path through unauthenticated.
        if path == f"{self.PREFIX}/feedback-export":
            self.require_token(headers)
            if method != "GET":
                raise TraceFeedbackProblem(405, "method_not_allowed", "use GET")
            return self._jsonl(query)

        if path != f"{self.PREFIX}/feedback":
            raise TraceFeedbackProblem(404, "not_found", "not found")

        # The signed-in team (oauth2-proxy has authenticated every request that gets here).
        email = self.team_email(headers)
        if method == "GET":
            if query.get("format") == ["jsonl"]:
                return self._jsonl(query)
            list_scope(query)
            with self._cursor() as cursor:
                return _json(200, list_votes(cursor, query, viewer=email))
        if method == "POST":
            item = clean_vote(self._read(read_body, headers))
            with self._cursor(commit=True) as cursor:
                result = set_vote(cursor, item, reviewer=email)
            print(
                f"traces: {result['status']} {item['vote'] or 'none'} run={item['run_id']} "
                f"game={item['game_index']} step={item['step_index']} section={item['section_index']} by {email}",
                flush=True,
            )
            return _json(200, result)
        raise TraceFeedbackProblem(405, "method_not_allowed", "use GET or POST")

    def _jsonl(self, query: dict[str, list[str]]) -> Response:
        export_filter(query)
        with self._cursor() as cursor:
            lines = [
                json.dumps(record, ensure_ascii=False, separators=(",", ":"), default=str)
                for record in export_votes(cursor, query)
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

    def _cursor(self, commit: bool = False) -> "TraceFeedbackApi._Cursor":
        return TraceFeedbackApi._Cursor(self.connect, commit)

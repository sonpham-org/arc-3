"""
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: Shared, versioned Mode explorer modes (Son's ask, #arc-3 6-Oct 08:42 ET: "Mark needs a way to edit and add
  new modes, is it there? And when will the mode be recorded?"). Every signed-in user sees the same current modes and
  can add a mode or edit any mode, built-in ones included. Storage is append-only (arc3_mode_versions): each save is
  a new version with who and when, the current mode is its highest version, restore copies an old version forward,
  delete is a version with hidden = true, so nothing is ever lost. Version 1 of each built-in mode is seeded from
  docs/static/data/modes.json (the image's /srv/static/data/modes.json) for ids that have no rows yet, so a later
  repo edit never overwrites a version saved on the site.
    GET  /api/v1/modes                        current version of every mode (hidden ones flagged), and who is asking
    GET  /api/v1/modes/<id>/versions          every version of one mode, newest first
    GET  /api/v1/modes/runs?game=<code>       what each Play recorded for that game (see record_play)
    POST /api/v1/modes/save                   {id?, from_version?, mode, note?} -> a new version (or a new mode)
    POST /api/v1/modes/<id>/restore           {version, from_version} -> copies that version forward
    POST /api/v1/modes/<id>/hide | unhide     {from_version} -> current version with hidden switched
  record_play is called by the Spark runner relay (spark_runner.py) after the runner accepts a Play: it stores the
  exact slots sent (full prompt text, Stock template, settings) with the mode version each came from and whether
  that text still matched the stored version, keyed by the runner's job id (arc3_spark_runner_job_modes).
SRP/DRY check: Pass - same handler shape as spark_runner.py (identity from oauth2-proxy's X-Forwarded-Email, narrow
  route list, same-site Origin on POST, size caps). Prompt application stays in tools/spark_runner/modes.py; this
  module only stores and checks text.
"""
from __future__ import annotations

import json
import os
import re
import secrets
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from psycopg2 import errors as pg_errors
from psycopg2.extras import Json

PREFIX = "/api/v1/modes"
MODE_ID = r"[a-z0-9][a-z0-9_-]{0,63}"
ID_RE = re.compile(MODE_ID)
VERSIONS_ROUTE = re.compile(rf"/({MODE_ID})/versions")
ACTION_ROUTE = re.compile(rf"/({MODE_ID})/(restore|hide|unhide)")
JOB_ID_RE = re.compile(r"[a-z0-9-]{8,40}")
GAME_RE = re.compile(r"[a-z0-9]{4}")
EMAIL_RE = re.compile(r"^[^\s@]{1,64}@[^\s@]{1,255}$")
COLOR_RE = re.compile(r"#[0-9a-fA-F]{6}")
SITE_ORIGIN = os.environ.get("ARC3_SITE_ORIGIN", "https://arc3.sonpham.net")
MAX_BODY = 256 * 1024
BASES = ("turn", "game_over", "level_start")
VARIANTS = ("son", "daniel")
EFFORTS = ("default", "low", "medium", "high")
SEED_EDITOR = "modes.json (built in)"


class ModeError(ValueError):
    pass


def _text(value, limit: int, *, required: bool = False, what: str = "text") -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ModeError(f"{what} must be text")
    if len(value) > limit:
        raise ModeError(f"{what} is longer than {limit} characters")
    if required and not value.strip():
        raise ModeError(f"{what} is required")
    return value


def _num(value, lo, hi, what: str, *, integer: bool):
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ModeError(f"{what} must be a number")
    if integer:
        value = int(round(value))
    if not lo <= value <= hi:
        raise ModeError(f"{what} must be between {lo} and {hi}")
    return value


def clean_settings(s) -> dict:
    """The six per-turn settings, in the ranges the Spark runner accepts (tools/spark_runner/server.py Settings)."""
    s = s if isinstance(s, dict) else {}
    budget = _num(s.get("thinking_budget"), 0, 32768, "thinking budget", integer=True)
    tools = _num(s.get("tool_calls"), 0, 50, "tool calls", integer=True)
    actions = _num(s.get("actions"), 0, 500, "action budget", integer=True)
    effort = s.get("effort") or "default"
    if effort not in EFFORTS:
        raise ModeError("effort must be default, low, medium or high")
    temp = _num(s.get("temperature"), 0, 2, "temperature", integer=False)
    return {
        "temperature": 0.6 if temp is None else temp,
        "thinking": bool(s.get("thinking", True)),
        "effort": effort,
        "thinking_budget": budget if budget and budget >= 256 else None,
        "tool_calls": tools if tools else None,
        "actions": actions if actions else None,
    }


def clean_mode(m) -> dict:
    """Validate a mode body from the page; keeps only known fields."""
    if not isinstance(m, dict):
        raise ModeError("mode must be an object")
    name = _text(m.get("name"), 32, required=True, what="name").strip()
    color = m.get("color") or "#0e7490"
    if not isinstance(color, str) or not COLOR_RE.fullmatch(color):
        raise ModeError("colour must look like #12ab34")
    base = m.get("base") or "turn"
    if base not in BASES:
        raise ModeError("base must be turn, game_over or level_start")
    raw = m.get("variants")
    if not isinstance(raw, dict):
        raise ModeError("variants must be an object")
    variants = {}
    for k in VARIANTS:
        v = raw.get(k)
        if v is None:
            continue
        if not isinstance(v, dict):
            raise ModeError(f"variant {k} must be an object")
        variants[k] = {
            "purpose": _text(v.get("purpose"), 500, what="purpose"),
            "trigger": _text(v.get("trigger"), 500, what="when to use"),
            "budget": _text(v.get("budget"), 200, what="budget text"),
            "prompt": _text(v.get("prompt"), 20000, required=True, what=f"{k} prompt"),
        }
    if not variants:
        raise ModeError("a mode needs at least one prompt")
    out = {"name": name, "color": color.lower(), "base": base, "variants": variants,
           "settings": clean_settings(m.get("settings")),
           "settings_why": _text(m.get("settings_why"), 1000, what="why these settings")}
    rl2 = m.get("rl2")
    if isinstance(rl2, str) and re.fullmatch(r"[a-z0-9_-]{1,32}", rl2):
        out["rl2"] = rl2
    if m.get("builtin") is True:
        out["builtin"] = True
    return out


def _row(r) -> dict:
    mode_id, version, body, hidden, note, by, at = r
    return {"id": mode_id, "version": version, **body, "hidden": hidden, "note": note,
            "created_by": by, "created_at": at.isoformat()}


class ModeLibrary:
    def __init__(self, connect, seed_path: Path | None = None):
        self.connect = connect
        self.seed_path = seed_path
        self.seed_order: dict[str, int] = {}   # built-ins keep modes.json's order in the bar (they share one seed time)

    @staticmethod
    def owns(path: str) -> bool:
        return path == PREFIX or path.startswith(PREFIX + "/")

    # ------------------------------------------------------------ storage

    def seed(self) -> int:
        """Insert modes.json's modes as version 1 of every built-in id that has no rows. Returns how many."""
        if not self.seed_path or not self.seed_path.is_file():
            print(f"modes: no seed file at {self.seed_path}; built-in modes not seeded", flush=True)
            return 0
        data = json.loads(self.seed_path.read_text(encoding="utf-8"))
        self.seed_order = {m.get("id"): i for i, m in enumerate(data.get("modes", [])) if isinstance(m, dict)}
        added = 0
        connection = self.connect()
        try:
            with connection.cursor() as cursor:
                for m in data.get("modes", []):
                    if not isinstance(m, dict) or not ID_RE.fullmatch(str(m.get("id", ""))):
                        continue
                    body = clean_mode({**m, "builtin": True})
                    cursor.execute(
                        """
                        INSERT INTO arc3_mode_versions (mode_id, version, body, note, created_by)
                        SELECT %s, 1, %s, %s, %s
                        WHERE NOT EXISTS (SELECT 1 FROM arc3_mode_versions WHERE mode_id = %s)
                        """,
                        (m["id"], Json(body), "draft from modes.json", SEED_EDITOR, m["id"]),
                    )
                    added += cursor.rowcount
            connection.commit()
        finally:
            connection.close()
        return added

    def current(self, cursor) -> list[dict]:
        cursor.execute(
            """
            SELECT DISTINCT ON (mode_id) mode_id, version, body, hidden, note, created_by, created_at
            FROM arc3_mode_versions ORDER BY mode_id, version DESC
            """
        )
        rows = [_row(r) for r in cursor.fetchall()]
        cursor.execute("SELECT mode_id, min(created_at), count(*) FROM arc3_mode_versions GROUP BY mode_id")
        first = {mid: (at, n) for mid, at, n in cursor.fetchall()}
        for r in rows:
            at, n = first.get(r["id"], (None, 1))
            r["versions"] = n
            r["first_at"] = at.isoformat() if at else None
        rows.sort(key=lambda r: (r["first_at"] or "", self.seed_order.get(r["id"], len(self.seed_order)), r["id"]))
        return rows

    def _latest(self, cursor, mode_id: str):
        cursor.execute(
            """
            SELECT mode_id, version, body, hidden, note, created_by, created_at FROM arc3_mode_versions
            WHERE mode_id = %s ORDER BY version DESC LIMIT 1 FOR UPDATE
            """,
            (mode_id,),
        )
        r = cursor.fetchone()
        return _row(r) if r else None

    def _insert(self, cursor, mode_id: str, version: int, body: dict, hidden: bool, note: str, who: str) -> dict:
        cursor.execute(
            """
            INSERT INTO arc3_mode_versions (mode_id, version, body, hidden, note, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING mode_id, version, body, hidden, note, created_by, created_at
            """,
            (mode_id, version, Json(body), hidden, note[:500], who),
        )
        return _row(cursor.fetchone())

    def _name_taken(self, cursor, name: str, mode_id: str | None) -> bool:
        return any(r["name"].casefold() == name.casefold() and r["id"] != mode_id and not r["hidden"] for r in self.current(cursor))

    # ------------------------------------------------------------ Play records

    def record_play(self, job_id: str, payload: dict, who: str) -> None:
        """Keep the exact mode text and settings a Play sent, with the version each slot came from."""
        if not JOB_ID_RE.fullmatch(job_id or ""):
            return
        variant = payload.get("variant") if payload.get("variant") in VARIANTS else "son"
        connection = self.connect()
        try:
            with connection.cursor() as cursor:
                def slot(s: dict) -> dict:
                    s = s if isinstance(s, dict) else {}
                    v = s.get("version") if isinstance(s.get("version"), dict) else {}
                    mode_id, number = v.get("mode_id"), v.get("version")
                    check, stored = "unknown", None
                    if isinstance(mode_id, str) and ID_RE.fullmatch(mode_id) and isinstance(number, int):
                        cursor.execute("SELECT body, created_by, created_at FROM arc3_mode_versions WHERE mode_id = %s AND version = %s",
                                       (mode_id, number))
                        stored = cursor.fetchone()
                    if stored:
                        body = stored[0]
                        text = (body["variants"].get(v.get("variant") or variant) or {}).get("prompt")
                        check = "matches" if text == s.get("prompt") else "differs"
                    return {
                        "mode": s.get("mode"), "name": s.get("name"), "base": s.get("base"),
                        "prompt": s.get("prompt"), "stock_template": s.get("stock_template"), "settings": s.get("settings"),
                        "mode_id": mode_id, "version": number, "prompt_variant": v.get("variant") or variant,
                        "edited_by": stored[1] if stored else v.get("created_by"),
                        "edited_at": stored[2].isoformat() if stored else v.get("created_at"),
                        "version_check": check,
                    }
                record = {"variant": variant, "stuck_level": payload.get("stuck_level"),
                          "scheme": [slot(s) for s in payload.get("scheme") or []], "stock": slot(payload.get("stock")),
                          "caps": {k: payload.get(k) for k in ("samples", "max_turns", "max_actions", "max_minutes")}}
                cursor.execute(
                    """
                    INSERT INTO arc3_spark_runner_job_modes (job_id, game, record, created_by) VALUES (%s, %s, %s, %s)
                    ON CONFLICT (job_id) DO NOTHING
                    """,
                    (job_id, str(payload.get("game") or "")[:8], Json(record), who),
                )
            connection.commit()
        finally:
            connection.close()

    # ------------------------------------------------------------ HTTP

    def handle(self, handler, method: str) -> bool:
        parsed = urlsplit(handler.path)
        if not self.owns(parsed.path):
            return False
        who = (handler.headers.get("X-Forwarded-Email") or "").strip().casefold()
        if not EMAIL_RE.fullmatch(who):
            handler.send_json(401, {"error": "sign_in_required", "message": "sign in to see and edit the shared modes"})
            return True
        sub = parsed.path[len(PREFIX):]
        if method == "GET":
            return self._get(handler, sub, parsed.query, who)
        if method != "POST":
            handler.send_json(405, {"error": "method_not_allowed"})
            return True
        if handler.headers.get("Origin") != SITE_ORIGIN:
            handler.send_json(403, {"error": "bad_origin", "message": "invalid request origin"})
            return True
        try:
            length = int(handler.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY or handler.headers.get("Transfer-Encoding"):
            handler.send_json(413, {"error": "invalid_body", "message": "invalid or oversized request"})
            return True
        try:
            body = json.loads(handler.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError
        except (UnicodeDecodeError, ValueError):
            handler.send_json(400, {"error": "invalid_json", "message": "body must be a JSON object"})
            return True
        try:
            return self._post(handler, sub, body, who)
        except ModeError as exc:
            handler.send_json(400, {"error": "invalid_mode", "message": str(exc)})
            return True

    def _get(self, handler, sub: str, query: str, who: str) -> bool:
        connection = self.connect()
        try:
            with connection.cursor() as cursor:
                if sub in ("", "/"):
                    handler.send_json(200, {"modes": self.current(cursor), "me": who})
                    return True
                m = VERSIONS_ROUTE.fullmatch(sub)
                if m:
                    cursor.execute(
                        """
                        SELECT mode_id, version, body, hidden, note, created_by, created_at FROM arc3_mode_versions
                        WHERE mode_id = %s ORDER BY version DESC
                        """,
                        (m.group(1),),
                    )
                    rows = [_row(r) for r in cursor.fetchall()]
                    if not rows:
                        handler.send_json(404, {"error": "not_found", "message": "no such mode"})
                    else:
                        handler.send_json(200, {"id": m.group(1), "versions": rows})
                    return True
                if sub == "/runs":
                    game = (parse_qs(query).get("game") or [""])[0]
                    if not GAME_RE.fullmatch(game):
                        handler.send_json(400, {"error": "bad_game", "message": "game must be a four-character code"})
                        return True
                    cursor.execute(
                        """
                        SELECT job_id, record, created_by, created_at FROM arc3_spark_runner_job_modes
                        WHERE game = %s ORDER BY job_id DESC LIMIT 200
                        """,
                        (game,),
                    )
                    runs = {jid: {**rec, "by": by, "at": at.isoformat()} for jid, rec, by, at in cursor.fetchall()}
                    handler.send_json(200, {"runs": runs})
                    return True
        finally:
            connection.close()
        handler.send_json(404, {"error": "not_found", "message": "unknown modes route"})
        return True

    def _post(self, handler, sub: str, body: dict, who: str) -> bool:
        note = _text(body.get("note"), 500, what="note").strip()
        from_version = body.get("from_version")
        connection = self.connect()
        try:
            with connection.cursor() as cursor:
                if sub == "/save":
                    mode = clean_mode(body.get("mode"))
                    mode_id = body.get("id")
                    if mode_id is None:
                        base = re.sub(r"[^a-z0-9]+", "-", mode["name"].lower()).strip("-")[:40] or "mode"
                        mode_id = f"{base}-{secrets.token_hex(3)}"
                        if not ID_RE.fullmatch(mode_id):
                            mode_id = f"mode-{secrets.token_hex(4)}"
                        latest = None
                    else:
                        if not isinstance(mode_id, str) or not ID_RE.fullmatch(mode_id):
                            raise ModeError("bad mode id")
                        latest = self._latest(cursor, mode_id)
                    if latest is not None and from_version != latest["version"]:
                        connection.rollback()
                        handler.send_json(409, {"error": "edited_meanwhile", "current": latest,
                                                "message": f"{latest['created_by']} saved version {latest['version']} of {latest['name']} "
                                                           "while you were editing; reopen it to see their change"})
                        return True
                    if latest is None and body.get("id") is not None and from_version not in (None, 0):
                        raise ModeError("that mode does not exist")
                    if self._name_taken(cursor, mode["name"], mode_id):
                        raise ModeError(f"a mode called {mode['name']} already exists")
                    mode.pop("builtin", None)        # built-in is a fact about the mode's origin, not something a save sets
                    if latest and latest.get("builtin"):
                        mode["builtin"] = True
                    row = self._insert(cursor, mode_id, (latest["version"] if latest else 0) + 1, mode, False,
                                       note or ("new mode" if latest is None else ""), who)
                    connection.commit()
                    handler.send_json(200, {"mode": row})
                    return True
                m = ACTION_ROUTE.fullmatch(sub)
                if m:
                    mode_id, action = m.groups()
                    latest = self._latest(cursor, mode_id)
                    if latest is None:
                        handler.send_json(404, {"error": "not_found", "message": "no such mode"})
                        return True
                    if from_version != latest["version"]:
                        connection.rollback()
                        handler.send_json(409, {"error": "edited_meanwhile", "current": latest,
                                                "message": f"{latest['created_by']} saved version {latest['version']} meanwhile; reload and try again"})
                        return True
                    if action == "restore":
                        number = body.get("version")
                        cursor.execute("SELECT body FROM arc3_mode_versions WHERE mode_id = %s AND version = %s", (mode_id, number))
                        old = cursor.fetchone()
                        if not old:
                            handler.send_json(404, {"error": "not_found", "message": "no such version"})
                            return True
                        restored = clean_mode(old[0])
                        if self._name_taken(cursor, restored["name"], mode_id):
                            raise ModeError(f"another mode is now called {restored['name']}; rename that one first")
                        row = self._insert(cursor, mode_id, latest["version"] + 1, restored, False,
                                           note or f"restored version {number}", who)
                    else:
                        hide = action == "hide"
                        if not hide and self._name_taken(cursor, latest["name"], mode_id):
                            raise ModeError(f"another mode is now called {latest['name']}; rename that one first")
                        keep = {k: latest[k] for k in ("name", "color", "base", "variants", "settings", "settings_why", "rl2", "builtin") if k in latest}
                        row = self._insert(cursor, mode_id, latest["version"] + 1, clean_mode(keep), hide,
                                           note or ("deleted (hidden; history kept)" if hide else "brought back"), who)
                    connection.commit()
                    handler.send_json(200, {"mode": row})
                    return True
        except pg_errors.UniqueViolation:
            connection.rollback()
            handler.send_json(409, {"error": "edited_meanwhile", "message": "someone saved this mode at the same moment; reload and try again"})
            return True
        finally:
            connection.close()
        handler.send_json(404, {"error": "not_found", "message": "unknown modes route"})
        return True

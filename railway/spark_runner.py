"""
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: The site's side of the Mode explorer's Play button. Signed-in pages call /api/v1/spark-runner/*; this
  relays the call over the ARC tailnet (the container's Tailscale HTTP proxy, the same one the debugger relay uses)
  to the Spark runner on Jethro (tools/spark_runner/server.py, published tailnet-only by `tailscale serve`), and
  keeps every job view it sees in Postgres (arc3_spark_runner_jobs) so the results table still loads when the
  Sparks are off or busy.
    GET  /api/v1/spark-runner/health | stuck-points | exact-starts | jobs[?game=] | jobs/<id> | jobs/<id>/samples/<k>/turns
    POST /api/v1/spark-runner/play | jobs/<id>/cancel
  The runner's own key (typed once into the page, kept in that browser) travels in the Authorization header and is
  checked by the runner, not here; Play and Cancel also need a same-site Origin. The signed-in Google account is
  sent along as the job's "by". When the runner cannot be reached, job reads are answered from storage and say so.
  After the runner accepts a Play, on_play (modes_store.ModeLibrary.record_play) keeps the exact mode versions sent.
  Exact level starts (6-Oct): the small per-level index of the runner's exact checkpoints (game, level, variant,
  the chosen one's actions from RESET, tokens, source job; never the checkpoints themselves) is kept in
  arc3_spark_runner_exact_starts whenever stuck-points or exact-starts is relayed, and exact-starts is answered from
  there when the runner is off. Only Play job views are stored; harvest views pass through (the page's level
  buttons count them) but are not kept.
SRP/DRY check: Pass - relay shape follows harness_relay.py and debugger_relay.py (identity from oauth2-proxy,
  narrow route list, size caps, no redirects); storage is one upsert table in catalog_schema.sql. No game logic.
"""
from __future__ import annotations

import json
import os
import re
import socket
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlsplit

from psycopg2.extras import Json

PREFIX = "/api/v1/spark-runner"
GET_ROUTES = re.compile(r"/(?:health|stuck-points|exact-starts|jobs|jobs/[a-z0-9-]{8,40}|jobs/[a-z0-9-]{8,40}/samples/\d{1,2}/turns)")
POST_ROUTES = re.compile(r"/(?:play|jobs/[a-z0-9-]{8,40}/cancel)")
JOB_ROUTE = re.compile(r"/jobs/([a-z0-9-]{8,40})")
EMAIL_RE = re.compile(r"^[^\s@]{1,64}@[^\s@]{1,255}$")
SITE_ORIGIN = "https://arc3.sonpham.net"
MAX_BODY = 512 * 1024
MAX_RESPONSE = 16 * 1024 * 1024
DEFAULT_UPSTREAM = "https://gx10-a424.tail1528b6.ts.net"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class SparkRunnerRelay:
    def __init__(self, connect, *, upstream: str | None = None, proxy_url: str | None = None, timeout: float = 60.0,
                 on_play=None):
        self.connect = connect
        self.on_play = on_play   # (job_id, payload, identity): keeps the exact mode versions a Play sent (modes_store.py)
        self.upstream = (upstream or os.environ.get("ARC3_SPARK_RUNNER_UPSTREAM") or DEFAULT_UPSTREAM).rstrip("/")
        proxy = proxy_url if proxy_url is not None else os.environ.get("ARC3_DEBUGGER_PROXY", "http://127.0.0.1:1055")
        handlers: list = [_NoRedirect()]
        if proxy:
            handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        self.opener = urllib.request.build_opener(*handlers)
        self.timeout = timeout

    @staticmethod
    def owns(path: str) -> bool:
        return path == PREFIX or path.startswith(PREFIX + "/")

    # ------------------------------------------------------------ storage

    def _store(self, views: list[dict]) -> None:
        # Play jobs only: the page also lists harvest runs (idle-time Stock runs for exact starts) for its level tally,
        # but stored ones would come back as Play jobs when the Sparks are off.
        rows = [v for v in views if isinstance(v, dict) and isinstance(v.get("id"), str) and JOB_ROUTE.fullmatch("/jobs/" + v["id"])
                and v.get("kind", "play") == "play"]
        if not rows:
            return
        try:
            connection = self.connect()
            try:
                with connection.cursor() as cursor:
                    for v in rows:
                        cursor.execute(
                            """
                            INSERT INTO arc3_spark_runner_jobs (job_id, game, status, view, updated_at)
                            VALUES (%s, %s, %s, %s, now())
                            ON CONFLICT (job_id) DO UPDATE SET
                                game = EXCLUDED.game, status = EXCLUDED.status, view = EXCLUDED.view, updated_at = now()
                            """,
                            (v["id"], str(v.get("game") or "")[:8], str(v.get("status") or "")[:16], Json(v)),
                        )
                connection.commit()
            finally:
                connection.close()
        except Exception as exc:  # storage must never break a live relay
            print(f"spark-runner: storing {len(rows)} job view(s) failed: {exc}", flush=True)

    def _store_exact(self, rows: list[dict]) -> None:
        rows = [r for r in rows if isinstance(r, dict) and re.fullmatch(r"[a-z0-9]{4}", str(r.get("game") or ""))
                and isinstance(r.get("level"), int) and r.get("variant") in ("son", "daniel")]
        if not rows:
            return
        try:
            connection = self.connect()
            try:
                with connection.cursor() as cursor:
                    for r in rows:
                        cursor.execute(
                            """
                            INSERT INTO arc3_spark_runner_exact_starts (game, level, variant, count, chosen, updated_at)
                            VALUES (%s, %s, %s, %s, %s, now())
                            ON CONFLICT (game, level, variant) DO UPDATE SET
                                count = EXCLUDED.count, chosen = EXCLUDED.chosen, updated_at = now()
                            """,
                            (r["game"], r["level"], r["variant"], int(r.get("count") or 0), Json(r.get("chosen"))),
                        )
                connection.commit()
            finally:
                connection.close()
        except Exception as exc:  # storage must never break a live relay
            print(f"spark-runner: storing {len(rows)} exact start(s) failed: {exc}", flush=True)

    def _stored_exact(self) -> list[dict]:
        connection = self.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT game, level, variant, count, chosen FROM arc3_spark_runner_exact_starts "
                               "ORDER BY game, level, variant")
                return [{"game": g, "level": lv, "variant": v, "count": c, "chosen": ch} for g, lv, v, c, ch in cursor.fetchall()]
        finally:
            connection.close()

    def _stored(self, job_id: str | None, game: str | None) -> list[dict]:
        connection = self.connect()
        try:
            with connection.cursor() as cursor:
                if job_id:
                    cursor.execute("SELECT view FROM arc3_spark_runner_jobs WHERE job_id = %s", (job_id,))
                elif game:
                    cursor.execute("SELECT view FROM arc3_spark_runner_jobs WHERE game = %s ORDER BY job_id DESC LIMIT 200", (game,))
                else:
                    cursor.execute("SELECT view FROM arc3_spark_runner_jobs ORDER BY job_id DESC LIMIT 200")
                return [row[0] for row in cursor.fetchall()]
        finally:
            connection.close()

    # ------------------------------------------------------------ relay

    def handle(self, handler, method: str) -> bool:
        parsed = urlsplit(handler.path)
        if not self.owns(parsed.path):
            return False
        identity = (handler.headers.get("X-Forwarded-Email") or "").strip().casefold()
        if not EMAIL_RE.fullmatch(identity):
            handler.send_json(401, {"error": "sign_in_required", "message": "sign in to use the Spark runner"})
            return True
        sub = parsed.path[len(PREFIX):]
        routes = GET_ROUTES if method == "GET" else POST_ROUTES if method == "POST" else None
        if routes is None or not routes.fullmatch(sub):
            handler.send_json(404, {"error": "not_found", "message": "unknown Spark runner route"})
            return True
        body = None
        payload = None
        if method == "POST":
            if handler.headers.get("Origin") != SITE_ORIGIN:
                handler.send_json(403, {"error": "bad_origin", "message": "invalid request origin"})
                return True
            try:
                length = int(handler.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if not 0 <= length <= MAX_BODY or handler.headers.get("Transfer-Encoding"):
                handler.send_json(413, {"error": "invalid_body", "message": "invalid or oversized request"})
                return True
            raw = handler.rfile.read(length) if length else b"{}"
            if sub == "/play":
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    handler.send_json(400, {"error": "invalid_json", "message": "body is not JSON"})
                    return True
                if not isinstance(payload, dict):
                    handler.send_json(400, {"error": "invalid_json", "message": "body must be an object"})
                    return True
                payload["by"] = identity
                raw = json.dumps(payload).encode("utf-8")
            body = raw
        headers = {"Accept": "application/json", "X-ARC3-User": identity}
        auth = handler.headers.get("Authorization") or ""
        if auth.startswith("Bearer ") and len(auth) < 300:
            headers["Authorization"] = auth
        if body is not None:
            headers["Content-Type"] = "application/json"
        url = f"{self.upstream}/api{sub}" + (f"?{parsed.query}" if parsed.query else "")
        request = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            try:
                response = self.opener.open(request, timeout=self.timeout)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                content = response.read(MAX_RESPONSE + 1)
                status = response.code
            if len(content) > MAX_RESPONSE:
                raise ValueError("oversized response")
            json.loads(content.decode("utf-8"))   # the runner only speaks JSON; anything else is a fault upstream
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError, ValueError) as exc:
            print(f"spark-runner relay {method} {sub} failed: {exc}", flush=True)
            self._unreachable(handler, method, sub, parsed.query)
            return True
        if sub == "/play" and status == 200 and self.on_play is not None:
            try:
                job_id = json.loads(content.decode("utf-8")).get("job")
                if isinstance(job_id, str):
                    self.on_play(job_id, payload, identity)
            except Exception as exc:  # recording must never fail a Play the runner already accepted
                print(f"spark-runner: recording the modes of a play failed: {exc}", flush=True)
        if method == "GET" and status == 200 and (sub == "/jobs" or JOB_ROUTE.fullmatch(sub)):
            data = json.loads(content.decode("utf-8"))
            self._store(data.get("jobs", []) if sub == "/jobs" else [data])
        elif method == "GET" and status == 200 and sub == "/exact-starts":
            self._store_exact(json.loads(content.decode("utf-8")).get("levels", []))
        elif method == "GET" and status == 200 and sub == "/stuck-points":
            points = json.loads(content.decode("utf-8")).get("stuck_points", [])
            self._store_exact([{**x, "game": p.get("game")} for p in points if isinstance(p, dict)
                               for x in (p.get("exact_levels") or []) if isinstance(x, dict)])
        handler.send_relay_response(status, "application/json; charset=utf-8", content)
        return True

    def _unreachable(self, handler, method: str, sub: str, query: str) -> None:
        message = "The Spark runner cannot be reached from the site right now (Sparks off, busy restarting, or the tailnet is down)."
        if method == "GET" and sub == "/health":
            handler.send_json(200, {"ok": False, "runner_reachable": False, "message": message})
            return
        if method == "GET" and sub == "/exact-starts":
            try:
                rows = self._stored_exact()
            except Exception as exc:
                print(f"spark-runner: stored exact starts read failed: {exc}", flush=True)
                rows = []
            handler.send_json(200, {"levels": rows, "from_storage": True, "runner_reachable": False, "message": message})
            return
        m = JOB_ROUTE.fullmatch(sub)
        if method == "GET" and (sub == "/jobs" or m):
            try:
                game = (parse_qs(query).get("game") or [None])[0]
                rows = self._stored(m.group(1) if m else None, game if game and re.fullmatch(r"[a-z0-9]{4}", game) else None)
            except Exception as exc:
                print(f"spark-runner: stored read failed: {exc}", flush=True)
                rows = []
            if m:
                if rows:
                    handler.send_json(200, {**rows[0], "from_storage": True, "runner_reachable": False})
                else:
                    handler.send_json(503, {"error": "runner_unreachable", "message": message})
            else:
                handler.send_json(200, {"jobs": rows, "from_storage": True, "runner_reachable": False, "message": message})
            return
        handler.send_json(503, {"error": "runner_unreachable", "message": message})

"""Authenticated ARC context-fork service for a local OpenAI-compatible model.

The service binds to loopback. Tailscale Serve supplies TLS and the
``Tailscale-User-Login`` identity header; an optional bearer token is supported
for non-browser automation. Model calls run asynchronously so the HTTP handler
stays responsive while a long Qwen reasoning turn is in flight.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from debugger.flags import build_resume_request, flag_manifest


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _display_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return json.dumps(content, ensure_ascii=False, indent=2) if content not in (None, "") else ""
    blocks: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            blocks.append(str(part))
            continue
        part_type = str(part.get("type") or "")
        if part_type in {"text", "input_text"}:
            blocks.append(str(part.get("text") or ""))
        elif part_type in {"image_url", "input_image"}:
            blocks.append("[CURRENT GRID IMAGE ATTACHED]")
        else:
            blocks.append(json.dumps(part, ensure_ascii=False, indent=2))
    return "\n".join(block for block in blocks if block)


def render_context(payload: dict[str, Any]) -> str:
    """Render the final outbound request without leaking embedded image bytes."""
    messages = payload.get("messages") if isinstance(payload.get("messages"), list) else []
    blocks: list[str] = []
    total = len(messages)
    for index, message in enumerate(messages, start=1):
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "unknown").upper()
        tool_call_id = str(message.get("tool_call_id") or "").strip()
        suffix = f" · tool_call_id={tool_call_id}" if tool_call_id else ""
        parts = [f"[MESSAGE {index}/{total} · {role}{suffix}]"]
        reasoning = _display_content(message.get("reasoning") or message.get("reasoning_content"))
        if reasoning:
            parts.extend(("[REASONING]", reasoning))
        content = _display_content(message.get("content"))
        if content:
            parts.append(content)
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            parts.extend(("[TOOL CALLS]", json.dumps(tool_calls, ensure_ascii=False, indent=2)))
        blocks.append("\n".join(parts))

    tools = payload.get("tools")
    if isinstance(tools, list) and tools:
        blocks.append(f"[AVAILABLE TOOLS]\n{json.dumps(tools, ensure_ascii=False, indent=2)}")
    settings = {
        key: payload.get(key)
        for key in ("model", "max_tokens", "temperature", "top_p", "top_k", "tool_choice", "chat_template_kwargs")
        if payload.get(key) is not None
    }
    blocks.append(f"[REQUEST SETTINGS]\n{json.dumps(settings, ensure_ascii=False, indent=2)}")
    return "\n\n".join(blocks)


class QwenClient:
    def __init__(self, base_url: str, *, timeout: float = 3600.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def models(self) -> dict[str, Any]:
        request = urllib.request.Request(f"{self.base_url}/models")
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read())

    def model_info(self) -> dict[str, Any]:
        payload = self.models()
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or not rows:
            raise RuntimeError("Qwen server returned no models")
        row = rows[0]
        if not isinstance(row, dict):
            raise RuntimeError("Qwen server returned invalid model metadata")
        return row

    def model_id(self) -> str:
        return str(self.model_info().get("id") or "").strip()

    def tokenize(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = {
            key: payload[key]
            for key in ("model", "messages", "tools", "chat_template_kwargs")
            if payload.get(key) is not None
        }
        body["add_generation_prompt"] = True
        root = self.base_url[:-3] if self.base_url.endswith("/v1") else self.base_url
        request = urllib.request.Request(
            f"{root}/tokenize",
            data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=min(self.timeout, 120.0)) as response:
                result = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read(4096).decode("utf-8", errors="replace")
            raise RuntimeError(f"Qwen tokenizer HTTP {exc.code}: {detail}") from exc
        if not isinstance(result, dict) or not isinstance(result.get("count"), int):
            raise RuntimeError("Qwen tokenizer returned no token count")
        return result

    def complete(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read(4096).decode("utf-8", errors="replace")
            raise RuntimeError(f"Qwen HTTP {exc.code}: {detail}") from exc


class Authorizer:
    def __init__(self, *, allowed_users: set[str], bearer_token: str) -> None:
        self.allowed_users = {value.casefold() for value in allowed_users if value}
        self.bearer_token = bearer_token

    def identity(self, headers: Any) -> str | None:
        authorization = str(headers.get("Authorization") or "")
        supplied = authorization[7:] if authorization.startswith("Bearer ") else ""
        if self.bearer_token and supplied and secrets.compare_digest(supplied, self.bearer_token):
            relayed_user = str(headers.get("X-ARC3-User") or "").strip().casefold()
            if relayed_user and len(relayed_user) <= 320 and not any(ord(char) < 32 for char in relayed_user):
                return f"railway:{relayed_user}"
            return "bearer-token"
        login = str(headers.get("Tailscale-User-Login") or "").strip().casefold()
        if login and login in self.allowed_users:
            return login
        return None

    @property
    def configured(self) -> bool:
        return bool(self.allowed_users or self.bearer_token)


class SessionService:
    def __init__(
        self,
        client: QwenClient,
        *,
        state_root: Path,
        cluster_nodes: list[str],
        workers: int = 2,
    ) -> None:
        self.client = client
        self.state_root = state_root
        self.cluster_nodes = cluster_nodes
        self.executor = ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="arc-debugger")
        self.lock = threading.RLock()
        self.sessions: dict[str, dict[str, Any]] = {}
        self.requests: dict[str, dict[str, Any]] = {}
        self._model_info: dict[str, Any] | None = None
        state_root.mkdir(parents=True, exist_ok=True)

    def capabilities(self) -> dict[str, Any]:
        self._model_info = self._model_info or self.client.model_info()
        return {
            "ok": True,
            "apiVersion": 1,
            "service": "arc-debugger",
            "model": str(self._model_info.get("id") or "").strip(),
            "maxModelLen": int(self._model_info.get("max_model_len") or 0),
            "clusterNodes": self.cluster_nodes,
            "flags": flag_manifest(),
        }

    def _build_payload(self, body: dict[str, Any]) -> tuple[dict[str, Any], dict[str, bool]]:
        context = body.get("context")
        if not isinstance(context, dict):
            raise ValueError("context must be an object")
        capabilities = self.capabilities()
        return build_resume_request(
            model=capabilities["model"],
            context=context,
            raw_flags=body.get("flags"),
            settings=body.get("settings"),
        )

    def _inspect_context_window(self, payload: dict[str, Any]) -> dict[str, Any]:
        tokenized = self.client.tokenize(payload)
        prompt_tokens = int(tokenized.get("count") or 0)
        max_model_len = int(tokenized.get("max_model_len") or self.capabilities().get("maxModelLen") or 0)
        requested_output = int(payload.get("max_tokens") or 0)
        available_output = max(0, max_model_len - prompt_tokens)
        return {
            "messageCount": len(payload.get("messages") or []),
            "promptTokens": prompt_tokens,
            "maxModelLen": max_model_len,
            "requestedOutputTokens": requested_output,
            "availableOutputTokens": available_output,
            "fits": prompt_tokens + requested_output <= max_model_len,
        }

    def preview(self, body: dict[str, Any]) -> dict[str, Any]:
        payload, flags = self._build_payload(body)
        window = self._inspect_context_window(payload)
        context = body.get("context") if isinstance(body.get("context"), dict) else {}
        return {
            "ok": True,
            "source": str(context.get("source") or "reconstructed"),
            "flags": flags,
            "contextText": render_context(payload),
            **window,
        }

    def public_session(self, session_id: str, *, owner: str | None = None) -> dict[str, Any]:
        with self.lock:
            session = self.sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)
            if owner is not None and session["owner"] != owner:
                raise PermissionError("session belongs to another user")
            return json.loads(json.dumps(session))

    def create(self, body: dict[str, Any], *, owner: str) -> dict[str, Any]:
        capabilities = self.capabilities()
        payload, flags = self._build_payload(body)
        context_window = self._inspect_context_window(payload)
        if not context_window["fits"]:
            raise ValueError(
                f"Context uses {context_window['promptTokens']} of {context_window['maxModelLen']} tokens, "
                f"leaving {context_window['availableOutputTokens']} for output; reduce Max output tokens."
            )
        session_id = secrets.token_urlsafe(18)
        now = utc_now()
        session = {
            "id": session_id,
            "status": "queued",
            "owner": owner,
            "createdAt": now,
            "updatedAt": now,
            "origin": body.get("origin") if isinstance(body.get("origin"), dict) else {},
            "flags": flags,
            "model": capabilities["model"],
            "contextWindow": context_window,
            "turns": [],
        }
        with self.lock:
            self.sessions[session_id] = session
            self.requests[session_id] = payload
            self._persist(session_id)
        self.executor.submit(self._run, session_id)
        return self.public_session(session_id)

    def follow_up(self, session_id: str, text: str, *, owner: str) -> dict[str, Any]:
        text = text.strip()
        if not text:
            raise ValueError("message must not be empty")
        with self.lock:
            session = self.sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)
            if session["owner"] != owner:
                raise PermissionError("session belongs to another user")
            if session["status"] not in {"complete", "error"}:
                raise RuntimeError("session is still running")
            payload = self.requests[session_id]
            previous = session.get("response") or {}
            prior_text = "\n\n".join(
                part
                for part in (
                    str(previous.get("reasoning") or "").strip(),
                    str(previous.get("content") or "").strip(),
                    json.dumps(previous.get("toolCalls"), ensure_ascii=False)
                    if previous.get("toolCalls") else "",
                )
                if part
            )
            if prior_text:
                payload["messages"].append({"role": "assistant", "content": prior_text})
            payload["messages"].append({"role": "user", "content": text})
            session["status"] = "queued"
            session["updatedAt"] = utc_now()
            session.pop("error", None)
            session.pop("response", None)
            self._persist(session_id)
        self.executor.submit(self._run, session_id)
        return self.public_session(session_id)

    def _run(self, session_id: str) -> None:
        with self.lock:
            session = self.sessions[session_id]
            session["status"] = "running"
            session["updatedAt"] = utc_now()
            payload = json.loads(json.dumps(self.requests[session_id]))
            self._persist(session_id)
        started = time.monotonic()
        try:
            raw = self.client.complete(payload)
            choices = raw.get("choices") if isinstance(raw, dict) else None
            choice = choices[0] if isinstance(choices, list) and choices else {}
            message = choice.get("message") if isinstance(choice, dict) else {}
            message = message if isinstance(message, dict) else {}
            response = {
                "content": message.get("content"),
                "reasoning": message.get("reasoning_content") or message.get("reasoning"),
                "toolCalls": message.get("tool_calls") or [],
                "finishReason": choice.get("finish_reason") if isinstance(choice, dict) else None,
                "usage": raw.get("usage") if isinstance(raw, dict) else None,
                "elapsedSeconds": round(time.monotonic() - started, 3),
            }
            with self.lock:
                session = self.sessions[session_id]
                session["status"] = "complete"
                session["response"] = response
                session["turns"].append({"at": utc_now(), **response})
                session["updatedAt"] = utc_now()
                self._persist(session_id)
        except Exception as exc:
            with self.lock:
                session = self.sessions[session_id]
                session["status"] = "error"
                session["error"] = str(exc)[:4096]
                session["updatedAt"] = utc_now()
                self._persist(session_id)

    def _persist(self, session_id: str) -> None:
        target = self.state_root / f"{session_id}.json"
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(self.sessions[session_id], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)


class DebuggerHandler(BaseHTTPRequestHandler):
    server_version = "ARCDebugger/1"
    service: SessionService
    authorizer: Authorizer
    allowed_origins: set[str]
    max_body_bytes = 16 * 1024 * 1024

    def _origin(self) -> str:
        origin = str(self.headers.get("Origin") or "").rstrip("/")
        return origin if origin in self.allowed_origins else ""

    def send_json(self, status: HTTPStatus | int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        origin = self._origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def identity(self) -> str | None:
        return self.authorizer.identity(self.headers)

    def read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if length <= 0 or length > self.max_body_bytes:
            raise ValueError("request body is empty or too large")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        origin = self._origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Vary", "Origin")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        identity = self.identity()
        if identity is None:
            status = HTTPStatus.UNAUTHORIZED if self.authorizer.configured else HTTPStatus.SERVICE_UNAVAILABLE
            self.send_json(status, {"error": "unauthorized" if self.authorizer.configured else "auth_not_configured"})
            return
        path = urlparse(self.path).path.rstrip("/")
        try:
            if path in {"/healthz", "/v1/capabilities"}:
                self.send_json(HTTPStatus.OK, self.service.capabilities())
                return
            prefix = "/v1/sessions/"
            if path.startswith(prefix):
                self.send_json(
                    HTTPStatus.OK,
                    self.service.public_session(path[len(prefix) :], owner=identity),
                )
                return
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        except KeyError:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "session_not_found"})
        except PermissionError as exc:
            self.send_json(HTTPStatus.FORBIDDEN, {"error": "forbidden", "message": str(exc)})
        except Exception as exc:
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "upstream_unavailable", "message": str(exc)})

    def do_POST(self) -> None:  # noqa: N802
        identity = self.identity()
        if identity is None:
            self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        path = urlparse(self.path).path.rstrip("/")
        try:
            body = self.read_json()
            if path == "/v1/sessions":
                self.send_json(HTTPStatus.ACCEPTED, self.service.create(body, owner=identity))
                return
            if path == "/v1/preview":
                self.send_json(HTTPStatus.OK, self.service.preview(body))
                return
            prefix = "/v1/sessions/"
            if path.startswith(prefix) and path.endswith("/messages"):
                session_id = path[len(prefix) : -len("/messages")].rstrip("/")
                self.send_json(
                    HTTPStatus.ACCEPTED,
                    self.service.follow_up(session_id, str(body.get("message") or ""), owner=identity),
                )
                return
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        except KeyError:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "session_not_found"})
        except PermissionError as exc:
            self.send_json(HTTPStatus.FORBIDDEN, {"error": "forbidden", "message": str(exc)})
        except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request", "message": str(exc)})
        except Exception as exc:
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "request_failed", "message": str(exc)})

    def log_message(self, format_string: str, *args: Any) -> None:
        print(f"arc-debugger: {format_string % args}", flush=True)


def parse_csv(value: str) -> set[str]:
    return {part.strip() for part in value.replace(" ", ",").split(",") if part.strip()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("ARC3_DEBUGGER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=8033)
    parser.add_argument("--model-base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--state-root", type=Path, default=Path("~/.local/state/arc-debugger").expanduser())
    parser.add_argument("--workers", type=int, default=2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    allowed_users = parse_csv(os.environ.get("ARC3_DEBUGGER_ALLOWED_USERS", ""))
    bearer_token = os.environ.get("ARC3_DEBUGGER_TOKEN", "").strip()
    origins = parse_csv(
        os.environ.get(
            "ARC3_DEBUGGER_ALLOWED_ORIGINS",
            "https://arc3.sonpham.net,http://127.0.0.1:8021,http://localhost:8021",
        )
    )
    nodes = sorted(parse_csv(os.environ.get("ARC3_DEBUGGER_CLUSTER_NODES", "a108,a424")))
    DebuggerHandler.service = SessionService(
        QwenClient(args.model_base_url),
        state_root=args.state_root,
        cluster_nodes=nodes,
        workers=args.workers,
    )
    DebuggerHandler.authorizer = Authorizer(allowed_users=allowed_users, bearer_token=bearer_token)
    DebuggerHandler.allowed_origins = {origin.rstrip("/") for origin in origins}
    if not DebuggerHandler.authorizer.configured:
        raise SystemExit("Configure ARC3_DEBUGGER_ALLOWED_USERS and/or ARC3_DEBUGGER_TOKEN")
    print(
        f"arc-debugger listening on {args.host}:{args.port}; users={len(allowed_users)} "
        f"token={'yes' if bearer_token else 'no'} upstream={args.model_base_url}",
        flush=True,
    )
    ThreadingHTTPServer((args.host, args.port), DebuggerHandler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

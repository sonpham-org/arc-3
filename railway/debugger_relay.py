"""Narrow authenticated relay from the Railway site to the ARC debugger gateway."""

from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.message import Message
from typing import Mapping
from urllib.parse import urlsplit


PUBLIC_PREFIX = "/api/v1/debugger"
UPSTREAM_PATH_RE = re.compile(
    r"/v1/(?:capabilities|preview|sessions(?:/[A-Za-z0-9_-]{1,200}(?:/messages)?)?)"
)
EMAIL_RE = re.compile(r"^[^\s@]{1,64}@[^\s@]{1,255}$")


@dataclass(frozen=True)
class RelayResponse:
    status: int
    content_type: str
    body: bytes


class RelayProblem(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class DebuggerRelay:
    """Forward only the debugger API through Tailscale's local HTTP proxy."""

    max_response_bytes = 32 * 1024 * 1024

    def __init__(
        self,
        *,
        upstream: str,
        bearer_token: str,
        proxy_url: str,
        timeout: float = 180.0,
    ) -> None:
        self.upstream = upstream.rstrip("/")
        self.bearer_token = bearer_token.strip()
        self.proxy_url = proxy_url.strip()
        self.timeout = timeout
        proxies = (
            {"http": self.proxy_url, "https": self.proxy_url}
            if self.proxy_url
            else {}
        )
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
        self._validate_configuration()

    @property
    def configured(self) -> bool:
        return bool(self.upstream and self.bearer_token)

    def _validate_configuration(self) -> None:
        if not self.upstream:
            return
        parsed = urlsplit(self.upstream)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("ARC3_DEBUGGER_UPSTREAM must be an HTTP(S) origin")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("ARC3_DEBUGGER_UPSTREAM must not contain credentials or a query")
        if self.proxy_url:
            proxy = urlsplit(self.proxy_url)
            if proxy.scheme != "http" or not proxy.hostname:
                raise ValueError("ARC3_DEBUGGER_PROXY must be an HTTP proxy URL")

    @staticmethod
    def _identity(headers: Mapping[str, str]) -> str:
        # oauth2-proxy strips incoming identity headers and supplies this one after
        # successful Google authentication. Never accept a browser-provided token.
        identity = str(headers.get("X-Forwarded-Email") or "").strip().casefold()
        if not EMAIL_RE.fullmatch(identity):
            raise RelayProblem(401, "missing_authenticated_user", "Google identity is unavailable")
        return identity

    @staticmethod
    def _upstream_path(public_path: str) -> str:
        if not public_path.startswith(PUBLIC_PREFIX):
            raise RelayProblem(404, "not_found", "debugger route not found")
        upstream_path = public_path[len(PUBLIC_PREFIX) :] or "/"
        if not UPSTREAM_PATH_RE.fullmatch(upstream_path):
            raise RelayProblem(404, "not_found", "debugger route not found")
        return upstream_path

    @staticmethod
    def _content_type(headers: Message) -> str:
        value = headers.get("Content-Type", "application/json; charset=utf-8")
        return value if value.startswith("application/json") else "application/json; charset=utf-8"

    def forward(
        self,
        *,
        method: str,
        public_path: str,
        headers: Mapping[str, str],
        body: bytes | None = None,
    ) -> RelayResponse:
        if not self.configured:
            raise RelayProblem(503, "debugger_relay_disabled", "Spark relay is not configured")
        if method not in {"GET", "POST"}:
            raise RelayProblem(405, "method_not_allowed", "debugger method not allowed")
        identity = self._identity(headers)
        upstream_path = self._upstream_path(public_path)
        request_headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.bearer_token}",
            "X-ARC3-User": identity,
        }
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.upstream}{upstream_path}",
            data=body,
            headers=request_headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                payload = response.read(self.max_response_bytes + 1)
                if len(payload) > self.max_response_bytes:
                    raise RelayProblem(502, "debugger_response_too_large", "Spark response is too large")
                return RelayResponse(response.status, self._content_type(response.headers), payload)
        except urllib.error.HTTPError as exc:
            payload = exc.read(self.max_response_bytes + 1)
            if len(payload) > self.max_response_bytes:
                payload = json.dumps({"error": "debugger_response_too_large"}).encode()
            return RelayResponse(exc.code, self._content_type(exc.headers), payload)
        except RelayProblem:
            raise
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise RelayProblem(
                503,
                "debugger_relay_unavailable",
                "Railway cannot reach the Spark gateway over the ARC tailnet",
            ) from exc

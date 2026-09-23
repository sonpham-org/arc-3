#!/usr/bin/env python3
"""Serve docs/ locally with the live site's API and game sources proxied in.

Author: Claude Opus 5
Date: 20-September-2026
PURPOSE: The verification harness for the Games page tuning panels. A tuning spec can only be
checked by loading the real play view in a real browser and turning the sliders against real
Pyodide, and that needs three things at once: the spec files as they are in the working tree, the
catalog from the live API, and each game's head source from the live site. A plain static server
gives only the first -- docs/static/games/manifest.json is a stale fallback that predates the
evolution trees, so browsing it locally cannot reach a game the API knows about. This serves
docs/ from disk and forwards /api/ and /data/ upstream, so an uncommitted spec is exercised
against the catalog it will actually meet.

SRP/DRY check: Pass -- serving only. Specs are produced by scripts/measure_game_params.py; this
does not read, write or know about them. No existing script in scripts/ serves docs/.

  python3.13 scripts/serve_games_local.py                       # http://127.0.0.1:8731
  python3.13 scripts/serve_games_local.py --port 9000 --upstream https://arc3.sonpham.net

Then open http://127.0.0.1:<port>/index.html#g=<gameId> to play one game directly.

Local only, and deliberately: it binds 127.0.0.1, serves GET and HEAD alone, and forwards
nothing but /api/ and /data/. Team-only API routes answer 401 through the proxy because no
signed-in session is carried, which is correct -- the panel is a public-surface feature and this
checks the public surface.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PROXIED = ("/api/", "/data/")


class Handler(http.server.SimpleHTTPRequestHandler):
    """Static files from docs/, with the live site standing in for the parts only it has."""

    upstream = "https://arc3.sonpham.net"
    quiet = True

    def do_GET(self) -> None:
        if self.path.startswith(PROXIED):
            self.forward()
        else:
            super().do_GET()

    def do_HEAD(self) -> None:
        if self.path.startswith(PROXIED):
            self.forward(body=False)
        else:
            super().do_HEAD()

    def forward(self, body: bool = True) -> None:
        # The site 403s urllib's default user-agent, the same reason measure_game_params.py shells
        # out to curl for sources.
        request = urllib.request.Request(self.upstream + self.path,
                                        headers={"User-Agent": "arc3-serve-games-local",
                                                 "Accept": "*/*"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
                self.reply(response.status, response.headers.get("Content-Type"), payload, body)
        except urllib.error.HTTPError as error:
            # An upstream 404 or 401 is an answer the page knows how to handle; pass it through
            # rather than turning it into a proxy error the page cannot read.
            self.reply(error.code, error.headers.get("Content-Type"), error.read(), body)
        except Exception as error:
            self.send_error(502, f"upstream: {error}")

    def reply(self, status: int, content_type: str | None, payload: bytes, body: bool) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(payload)

    def log_message(self, *args) -> None:  # noqa: ANN002
        if not self.quiet:
            super().log_message(*args)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8731)
    parser.add_argument("--upstream", default="https://arc3.sonpham.net")
    parser.add_argument("--root", type=Path, default=REPO / "docs")
    parser.add_argument("--verbose", action="store_true", help="log every request")
    args = parser.parse_args()

    Handler.upstream = args.upstream.rstrip("/")
    Handler.quiet = not args.verbose
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    handler = functools.partial(Handler, directory=str(args.root))
    with socketserver.ThreadingTCPServer(("127.0.0.1", args.port), handler) as server:
        print(f"{args.root} on http://127.0.0.1:{args.port}/  "
              f"({', '.join(PROXIED)} -> {Handler.upstream})")
        print(f"one game: http://127.0.0.1:{args.port}/index.html#g=<gameId>   ctrl-c to stop")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

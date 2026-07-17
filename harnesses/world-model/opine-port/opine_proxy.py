#!/usr/bin/env python3
"""Tiny stdlib reverse proxy: codex -> (this :1235) -> vLLM :1234.

codex 0.142's Responses API request uses the `developer` message role, which
vLLM 0.19's /v1/responses rejects ("Unexpected message role"). This proxy
recursively rewrites role "developer" -> "system" in any JSON request body and
streams everything else through untouched (SSE responses included). It logs each
upstream status + any error body so further dialect gaps are visible in the log.
"""
import http.server, socketserver, urllib.request, urllib.error, json, sys, os

UPSTREAM = os.environ.get("PROXY_UPSTREAM", "http://127.0.0.1:1234")
PORT = int(os.environ.get("PROXY_PORT", "1235"))

def _text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for c in content:
            if isinstance(c, dict):
                t = c.get("text")
                if isinstance(t, str):
                    out.append(t)
            elif isinstance(c, str):
                out.append(c)
        return "\n".join(out)
    return ""


def normalize(data):
    """vLLM 0.19 /v1/responses is strict: it rejects the `developer` role AND
    requires a single system message at the very beginning. codex sends developer/
    system messages inside `input`. Fold all of them out of `input` into the single
    top-level `instructions` string (which vLLM places first), leaving `input` with
    only user/assistant/tool/function items in order."""
    if not isinstance(data, dict):
        return data
    inp = data.get("input")
    if not isinstance(inp, list):
        return data  # string input: nothing to reorder
    sys_parts = []
    instr = data.get("instructions")
    if isinstance(instr, str) and instr.strip():
        sys_parts.append(instr)
    kept = []
    for it in inp:
        if isinstance(it, dict) and it.get("role") in ("system", "developer"):
            txt = _text_of(it.get("content"))
            if txt:
                sys_parts.append(txt)
        else:
            kept.append(it)
    if sys_parts:
        data["instructions"] = "\n\n".join(sys_parts)
    data["input"] = kept
    return data


class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _proxy(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(n) if n else b""
        if body and "responses" in self.path:
            try:
                data = normalize(json.loads(body))
                body = json.dumps(data).encode()
                roles = [i.get("role") for i in data.get("input", []) if isinstance(i, dict)]
                sys.stderr.write(
                    f"[proxy] normalized: instr_len={len(data.get('instructions','') or '')} "
                    f"input_roles={roles}\n")
                sys.stderr.flush()
            except Exception as e:
                sys.stderr.write(f"[proxy] normalize err: {e}\n"); sys.stderr.flush()
        req = urllib.request.Request(
            UPSTREAM + self.path,
            data=body if self.command == "POST" else None,
            method=self.command,
        )
        for k, v in self.headers.items():
            if k.lower() not in ("host", "content-length", "connection"):
                req.add_header(k, v)
        if body:
            req.add_header("Content-Length", str(len(body)))
        try:
            resp = urllib.request.urlopen(req, timeout=900)
            status = resp.status
        except urllib.error.HTTPError as e:
            resp = e
            status = e.code
            try:
                err = e.read()
                sys.stderr.write(f"[proxy] {self.command} {self.path} -> {status}: {err[:300]!r}\n")
                sys.stderr.flush()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(err)
                return
            except Exception:
                pass
        except Exception as e:
            sys.stderr.write(f"[proxy] upstream error: {e}\n"); sys.stderr.flush()
            self.send_response(502); self.send_header("Connection", "close"); self.end_headers()
            return
        self.send_response(status)
        for k, v in resp.headers.items():
            if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                self.send_header(k, v)
        self.send_header("Connection", "close")
        self.end_headers()
        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            try:
                self.wfile.write(chunk)
                self.wfile.flush()
            except Exception:
                break

    do_POST = _proxy
    do_GET = _proxy

    def log_message(self, *a):
        pass


class TS(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    sys.stderr.write(f"[proxy] listening :{PORT} -> {UPSTREAM} (developer->system)\n")
    sys.stderr.flush()
    TS(("127.0.0.1", PORT), H).serve_forever()

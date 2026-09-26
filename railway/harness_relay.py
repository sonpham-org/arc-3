"""Approved-user relay to the dedicated cellensml Harness Lab API."""
import json
import os
import re
import urllib.error
import urllib.request
from urllib.parse import urlsplit

PREFIX = '/api/v1/harness'
ROUTES = re.compile(r'/(?:preset|games(?:/[A-Za-z0-9_-]+/preview)?|runner|trees(?:/[A-Za-z0-9_-]+/(?:nodes(?:/[A-Za-z0-9_-]+)?|children|actions|runs))?|runs/[A-Za-z0-9_-]+(?:/(?:nodes|log|cancel))?)')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def relay(handler, method):
    parsed = urlsplit(handler.path)
    if not (parsed.path == PREFIX or parsed.path.startswith(PREFIX + '/')):
        return False
    def reply(status, message):
        handler.send_json(status, {'detail': message})
    identity = handler.headers.get('X-Forwarded-Email', '').strip().casefold()
    allowed = {email.casefold() for email in re.split(r'[,\s]+', os.getenv('ALLOWED_EMAILS', '')) if email}
    # oauth2-proxy replaces identity headers. The catalog listener is loopback only.
    if not identity or identity not in allowed:
        reply(403, 'This Google account is not approved for Harness Lab')
        return True
    path = parsed.path[len(PREFIX):]
    if not ROUTES.fullmatch(path):
        reply(404, 'Unknown Harness Lab route')
        return True
    upstream = os.getenv('ARC3_HARNESS_UPSTREAM', '').rstrip('/')
    secret = os.getenv('ARC3_HARNESS_TOKEN', '')
    if upstream != 'https://harness-lab-api-293261284498.us-east4.run.app' or not secret:
        reply(503, 'Harness Lab connection is not configured')
        return True
    body = None
    if method == 'POST':
        if handler.headers.get('Origin') != 'https://arc3.sonpham.net':
            reply(403, 'Invalid request origin')
            return True
        try:
            length = int(handler.headers.get('Content-Length', '0'))
        except ValueError:
            length = 0
        if not 0 < length <= 262144 or handler.headers.get('Transfer-Encoding'):
            reply(413, 'Invalid or oversized request')
            return True
        body = handler.rfile.read(length)
    request = urllib.request.Request(upstream + '/api' + path + ('?' + parsed.query if parsed.query else ''),
        data=body, method=method, headers={'X-Harness-Key': secret,
        'X-Harness-User': 'google:' + identity, 'Content-Type': 'application/json'})
    try:
        opener = urllib.request.build_opener(NoRedirect())
        try:
            response = opener.open(request, timeout=120)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            content = response.read(32 * 1024 * 1024 + 1)
            if len(content) > 32 * 1024 * 1024:
                raise ValueError('Oversized response')
            if 'application/json' not in response.headers.get('Content-Type', ''):
                raise ValueError('Unexpected response')
            handler.send_relay_response(response.code, 'application/json; charset=utf-8', content)
    except Exception:
        reply(503, 'Harness Lab backend is temporarily unavailable')
    return True

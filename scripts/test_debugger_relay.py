import json
import sys
import unittest
import urllib.error
from email.message import Message
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "railway"))

from debugger_relay import DebuggerRelay, RelayProblem  # noqa: E402


class FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = "application/json"
        self.payload = json.dumps(payload or {"ok": True}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit):
        return self.payload


class FakeOpener:
    def __init__(self):
        self.request = None

    def open(self, request, timeout):
        self.request = request
        self.timeout = timeout
        return FakeResponse()


class DebuggerRelayTests(unittest.TestCase):
    def setUp(self):
        self.relay = DebuggerRelay(
            upstream="http://100.118.4.20:8033",
            bearer_token="server-secret",
            proxy_url="http://127.0.0.1:1055",
        )
        self.opener = FakeOpener()
        self.relay.opener = self.opener

    def test_relay_injects_server_credentials_and_authenticated_user(self):
        response = self.relay.forward(
            method="POST",
            public_path="/api/v1/debugger/v1/sessions",
            headers={"X-Forwarded-Email": "Person@Example.com"},
            body=b"{}",
        )
        self.assertEqual(200, response.status)
        self.assertEqual("http://100.118.4.20:8033/v1/sessions", self.opener.request.full_url)
        self.assertEqual("Bearer server-secret", self.opener.request.get_header("Authorization"))
        self.assertEqual("person@example.com", self.opener.request.get_header("X-arc3-user"))

    def test_relay_rejects_missing_identity(self):
        with self.assertRaisesRegex(RelayProblem, "Google identity"):
            self.relay.forward(
                method="GET",
                public_path="/api/v1/debugger/v1/capabilities",
                headers={},
            )

    def test_relay_allows_authenticated_context_preview(self):
        response = self.relay.forward(
            method="POST",
            public_path="/api/v1/debugger/v1/preview",
            headers={"X-Forwarded-Email": "person@example.com"},
            body=b"{}",
        )
        self.assertEqual(200, response.status)
        self.assertEqual("http://100.118.4.20:8033/v1/preview", self.opener.request.full_url)

    def test_relay_is_not_an_open_proxy(self):
        with self.assertRaisesRegex(RelayProblem, "not found"):
            self.relay.forward(
                method="GET",
                public_path="/api/v1/debugger/http://example.com",
                headers={"X-Forwarded-Email": "person@example.com"},
            )


if __name__ == "__main__":
    unittest.main()

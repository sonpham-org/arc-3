"""POST a JSON request with the short-lived GCP token already in the environment."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: gcp_json_post.py URL", file=sys.stderr)
        return 2
    token = os.environ.get("CLOUDSDK_AUTH_ACCESS_TOKEN", "").strip()
    if not token:
        print("CLOUDSDK_AUTH_ACCESS_TOKEN is missing", file=sys.stderr)
        return 2
    body = sys.stdin.buffer.read()
    try:
        json.loads(body)
    except (TypeError, ValueError) as exc:
        print(f"request body is not valid JSON: {exc}", file=sys.stderr)
        return 2
    request = urllib.request.Request(
        sys.argv[1],
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            sys.stdout.buffer.write(response.read())
    except urllib.error.HTTPError as exc:
        sys.stderr.buffer.write(exc.read())
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

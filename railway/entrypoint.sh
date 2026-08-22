#!/bin/sh
set -eu

: "${ALLOWED_EMAILS:?set ALLOWED_EMAILS (comma-separated Google accounts)}"
: "${OAUTH2_PROXY_CLIENT_ID:?set OAUTH2_PROXY_CLIENT_ID}"
: "${OAUTH2_PROXY_CLIENT_SECRET:?set OAUTH2_PROXY_CLIENT_SECRET}"
: "${OAUTH2_PROXY_COOKIE_SECRET:?set OAUTH2_PROXY_COOKIE_SECRET (32-byte)}"
: "${DATABASE_URL:?set DATABASE_URL to the Railway Postgres private URL}"

printf '%s\n' "$ALLOWED_EMAILS" \
  | tr ', ' '\n\n' \
  | sed '/^[[:space:]]*$/d' \
  > /tmp/emails.txt

echo "oauth2-proxy: allowlisting $(wc -l < /tmp/emails.txt) email(s)"
python3 /catalog_server.py --bootstrap-root /srv/data &
catalog_pid=$!
catalog_ready=0
for _attempt in $(seq 1 30); do
  if wget -q -O /dev/null http://127.0.0.1:8082/api/healthz; then
    catalog_ready=1
    break
  fi
  if ! kill -0 "$catalog_pid" 2>/dev/null; then
    echo "catalog server exited during startup" >&2
    exit 1
  fi
  sleep 1
done
if [ "$catalog_ready" != "1" ]; then
  echo "catalog server did not become ready" >&2
  exit 1
fi
caddy start --config /etc/caddy/Caddyfile --adapter caddyfile

exec oauth2-proxy \
  --provider=google \
  --http-address="0.0.0.0:${PORT:-8080}" \
  --upstream="http://127.0.0.1:8081" \
  --redirect-url="${OAUTH2_PROXY_REDIRECT_URL:-https://arc3.sonpham.net/oauth2/callback}" \
  --authenticated-emails-file=/tmp/emails.txt \
  --email-domain="*" \
  --cookie-secure=true \
  --cookie-expire=168h \
  --reverse-proxy=true \
  --skip-provider-button=false \
  --skip-auth-route="^/$" \
  --skip-auth-route="^/static/" \
  --whitelist-domain="arc3.sonpham.net"

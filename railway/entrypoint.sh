#!/bin/sh
set -eu

: "${ALLOWED_EMAILS:?set ALLOWED_EMAILS (comma-separated Google accounts)}"
: "${OAUTH2_PROXY_CLIENT_ID:?set OAUTH2_PROXY_CLIENT_ID}"
: "${OAUTH2_PROXY_CLIENT_SECRET:?set OAUTH2_PROXY_CLIENT_SECRET}"
: "${OAUTH2_PROXY_COOKIE_SECRET:?set OAUTH2_PROXY_COOKIE_SECRET (32-byte)}"
: "${DATABASE_URL:?set DATABASE_URL to the Railway Postgres private URL}"
: "${ARC3_PUBLISH_TOKEN:?set ARC3_PUBLISH_TOKEN for the trace publication API}"

TAILSCALE_SOCKET="${TAILSCALE_SOCKET:-/tmp/tailscaled.sock}"
TAILSCALE_STATE_DIR="${TAILSCALE_STATE_DIR:-/srv/data/.tailscale}"
TAILSCALE_PROXY_ADDR="${TAILSCALE_PROXY_ADDR:-127.0.0.1:1055}"
mkdir -p "$TAILSCALE_STATE_DIR" /var/run/tailscale

tailscaled \
  --tun=userspace-networking \
  --socket="$TAILSCALE_SOCKET" \
  --state="$TAILSCALE_STATE_DIR/tailscaled.state" \
  --socks5-server="$TAILSCALE_PROXY_ADDR" \
  --outbound-http-proxy-listen="$TAILSCALE_PROXY_ADDR" &
tailscaled_pid=$!

tailscale_ready=0
for _attempt in $(seq 1 30); do
  if [ -S "$TAILSCALE_SOCKET" ]; then
    tailscale_ready=1
    break
  fi
  if ! kill -0 "$tailscaled_pid" 2>/dev/null; then
    echo "tailscaled exited during startup" >&2
    break
  fi
  sleep 1
done
if [ "$tailscale_ready" = "1" ]; then
  if [ -n "${TS_AUTHKEY:-}" ]; then
    tailscale --socket="$TAILSCALE_SOCKET" up \
      --auth-key="$TS_AUTHKEY" \
      --hostname="${TS_HOSTNAME:-arc3-railway}" \
      --accept-dns=false &
  else
    # First boot prints a one-time login URL. State lives on the Railway volume,
    # so the site only needs to be enrolled in the tailnet once.
    tailscale --socket="$TAILSCALE_SOCKET" up \
      --hostname="${TS_HOSTNAME:-arc3-railway}" \
      --accept-dns=false &
  fi
else
  echo "warning: Tailscale proxy is not ready; debugger relay will return 503" >&2
fi

export ARC3_DEBUGGER_PROXY="${ARC3_DEBUGGER_PROXY:-http://$TAILSCALE_PROXY_ADDR}"

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
  --custom-templates-dir=/etc/oauth2-proxy/templates \
  --email-domain="*" \
  --cookie-secure=true \
  --cookie-expire=168h \
  --reverse-proxy=true \
  --skip-provider-button=false \
  --skip-auth-route="^/$" \
  --skip-auth-route="^/static/" \
  --skip-auth-route="^/api/v1/runs/[A-Za-z0-9._-]+/publication$" \
  --whitelist-domain="arc3.sonpham.net"

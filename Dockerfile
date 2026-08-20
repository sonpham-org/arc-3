FROM caddy:2.11.4-alpine

ARG TARGETARCH
ARG OAUTH2_PROXY_VERSION=7.7.1

RUN set -eux; \
    case "$TARGETARCH" in \
      amd64|arm64) oauth_arch="$TARGETARCH" ;; \
      *) echo "unsupported TARGETARCH: $TARGETARCH" >&2; exit 1 ;; \
    esac; \
    wget -q -O /tmp/oauth2-proxy.tgz \
      "https://github.com/oauth2-proxy/oauth2-proxy/releases/download/v${OAUTH2_PROXY_VERSION}/oauth2-proxy-v${OAUTH2_PROXY_VERSION}.linux-${oauth_arch}.tar.gz"; \
    tar -xzf /tmp/oauth2-proxy.tgz -C /tmp; \
    install -m 0755 \
      "/tmp/oauth2-proxy-v${OAUTH2_PROXY_VERSION}.linux-${oauth_arch}/oauth2-proxy" \
      /usr/local/bin/oauth2-proxy; \
    rm -rf /tmp/oauth2-proxy.tgz "/tmp/oauth2-proxy-v${OAUTH2_PROXY_VERSION}.linux-${oauth_arch}"

COPY railway/Caddyfile /etc/caddy/Caddyfile
COPY railway/entrypoint.sh /entrypoint.sh
COPY docs/*.html /srv/
COPY docs/static/ /srv/static/

RUN chmod 0755 /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

FROM caddy:2.11.4-alpine

ARG TARGETARCH
ARG OAUTH2_PROXY_VERSION=7.7.1

RUN apk add --no-cache postgresql-client python3 py3-psycopg2

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
COPY railway/catalog_server.py /catalog_server.py
COPY railway/catalog_schema.sql /catalog_schema.sql
COPY railway/publication_store.py /publication_store.py
COPY scripts/run_catalog.py /run_catalog.py
COPY templates/ /etc/oauth2-proxy/templates/
COPY docs/*.html /srv/
COPY docs/static/ /srv/static/

RUN test -s /etc/oauth2-proxy/templates/sign_in.html \
    && test -s /etc/oauth2-proxy/templates/error.html \
    && grep -q "Internal runs are private" /etc/oauth2-proxy/templates/sign_in.html \
    && grep -q "ARC-3" /etc/oauth2-proxy/templates/error.html \
    && grep -q -- "--custom-templates-dir=/etc/oauth2-proxy/templates" /entrypoint.sh \
    && grep -q "ARC3_PUBLISH_TOKEN" /entrypoint.sh \
    && grep -q "publication_store" /catalog_server.py \
    && chmod 0755 /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

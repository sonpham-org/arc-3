#!/bin/bash
# Rebuild data.json every 5 minutes and publish it twice: the arc3-rl-live web.app page (firebase deploy) and the
# RL page on arc3.sonpham.net (PUT /api/v1/rl/dashboard-publication with the site's publish token, read once from
# Railway; never printed).
#   bash refresh.sh            (runs until stopped; each pass logs one line)
cd "$(dirname "$0")"
RAILWAY_DIR=${RAILWAY_DIR:-/d/codex-work/arc3-game-evolution-20260918}   # a checkout linked to the ARC3 project
if [ -z "${ARC3_PUBLISH_TOKEN:-}" ]; then
  ARC3_PUBLISH_TOKEN=$(cd "$RAILWAY_DIR" && railway.cmd variable list --service arc3-viewer --environment production --json 2>/dev/null \
    | C:/Python312/python.exe -c "import sys, json; print(json.load(sys.stdin).get('ARC3_PUBLISH_TOKEN', ''))" | tr -d '\r')
fi
export ARC3_PUBLISH_TOKEN
while true; do
  if C:/Python312/python.exe build_site.py > .build.log 2>&1; then
    C:/Python312/python.exe sync_site_page.py > /dev/null 2>&1   # web.app page = the site's rl.html (bright)
    web=$(firebase.cmd deploy --only hosting:rl --project cellensml -m "data $(date -u +%H:%M)" > .deploy.log 2>&1 && echo ok || echo FAILED)
    site=$(C:/Python312/python.exe -c "
import gzip, os, urllib.request
body = gzip.compress(open('public/data.json', 'rb').read())
req = urllib.request.Request('https://arc3.sonpham.net/api/v1/rl/dashboard-publication', data=body, method='PUT',
    headers={'Authorization': 'Bearer ' + os.environ['ARC3_PUBLISH_TOKEN'], 'Content-Type': 'application/gzip', 'User-Agent': 'arc3-rl-dashboard/1'})
try:
    print(urllib.request.urlopen(req, timeout=60).status)
except Exception as exc:
    print('FAILED', getattr(exc, 'code', exc))
" 2>&1)
    echo "$(date -u +%H:%M) web.app $web, site $site; $(tail -n 1 .build.log | cut -c1-150)"
  else
    echo "$(date -u +%H:%M) FAILED: $(tail -n 2 .build.log | tr '\n' ' ' | cut -c1-300)"
  fi
  sleep 300
done

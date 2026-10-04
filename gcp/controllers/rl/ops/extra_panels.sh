#!/bin/bash
# Extra copies of a round's train and hard panels (Son 4-Oct: 10 attempts a game instead of 5 / 6: with 5 plays not even
# 5/5 shows a level is mastered, and the panel totals stay noisy). Once the round's own panels are listed on the RL page
# (launch_panels.sh from the round script), the same notebooks are launched on the same staged input copy as letter x
# (EXTRA=1: listed FIRST in the round's runs, so runs[-1] stays the panel run the round scripts follow), watched to the
# end, and a copy lost to Spot is dropped from the list and relaunched once as letter y.
#   bash ops/extra_panels.sh <round>        e.g. n0 (run it in the background next to the round script)
# Env: WAIT_H (8): give up if the round's panels are not listed by then.
set -uo pipefail
export CLOUDSDK_PYTHON='C:\python312\python.exe'
OPS=$(cd "$(dirname "$0")" && pwd)
SITE=$(cd "$OPS/../site" && pwd)
RUNS=gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs
ROUND=${1:?round, e.g. n0}
declare -A NB_OF=(["p5train"]="noborder-panel-train5x5-v1" ["p4hard"]="noborder-panel-hard4x6-v1")
say() { echo "$(date -u +%H:%M) extra panels $ROUND: $*"; }
g() { timeout 120 gcloud "$@"; }

listed() {   # the round's own train and hard panel runs (not x / y copies), space separated, or nothing
  C:/Python312/python.exe - "$SITE/site_config.json" "$ROUND" <<'PY' | tr -d '\r'
import json, re, sys
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
own = {p["key"]: [r for r in (p["runs"].get(sys.argv[2]) or []) if r and not re.search(r"-[xy]-\d{4}$", r)]
       for p in cfg["panels"]}
if own.get("train") and own.get("hard"):
    print(own["train"][-1], own["hard"][-1])
PY
}
t0=$SECONDS
until [ -n "$(listed)" ]; do
  [ $((SECONDS - t0)) -gt $(( ${WAIT_H:-8} * 3600 )) ] && { say "the round's panels were not listed in ${WAIT_H:-8} h"; exit 1; }
  sleep 120
done
say "round panels listed ($(listed)); launching copies x"
EXTRA=1 PANELS="p5train:${NB_OF[p5train]} p4hard:${NB_OF[p4hard]}" bash "$OPS/launch_panels.sh" "$ROUND" x

# a copy lost to Spot: off the list (its partial passes would count as failures), relaunched once as y
LOST=""
for key in p5train p4hard; do
  run=$(C:/Python312/python.exe - "$SITE/site_config.json" "$ROUND" "$key" <<'PY' | tr -d '\r'
import json, re, sys
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
panel = {"p5train": "train", "p4hard": "hard"}[sys.argv[3]]
runs = next(p for p in cfg["panels"] if p["key"] == panel)["runs"].get(sys.argv[2]) or []
print(next((r for r in runs if re.search(r"-x-\d{4}$", r)), ""))
PY
)
  [ -z "$run" ] && continue
  last=$(g storage cat "$RUNS/$run/phases.tsv" 2>/dev/null | tail -n 1 | cut -f3 | tr -d '\r')
  if [[ "$last" != *finish*notebook_rc_0* ]]; then
    say "$run ended unfinished (${last:-no phases}): off the list, relaunching as y"
    C:/Python312/python.exe - "$SITE/site_config.json" "$ROUND" "$run" <<'PY'
import json, sys
path, rnd, run = sys.argv[1:]
cfg = json.load(open(path, encoding="utf-8"))
for p in cfg["panels"]:
    if run in (p["runs"].get(rnd) or []):
        p["runs"][rnd] = [r for r in p["runs"][rnd] if r != run]
open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(cfg, indent=1, ensure_ascii=False) + "\n")
PY
    LOST="$LOST $key:${NB_OF[$key]}"
  fi
done
[ -n "$LOST" ] && EXTRA=1 PANELS="${LOST# }" bash "$OPS/launch_panels.sh" "$ROUND" y
say "done"

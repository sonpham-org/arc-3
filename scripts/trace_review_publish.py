"""Publish a run's paths to Trace review on arc3.sonpham.net (railway/rl_review.py), and keep the pool growing.

Author: Claude Opus 5.5 (2-Oct-2026). For each run: download its plays' event logs from GCS (held-out games skipped),
cut them into level-start nodes and paths (scripts/trace_review_index.py), and PUT them to
/api/v1/review/publication one game at a time. The server stores the content and pairs every new path with the
paths already at the same point (base against LoRA first), so publishing each new run is all the sampling needs.

  python scripts/trace_review_publish.py --run daniel-p5train-base-a-1002 --model base
  python scripts/trace_review_publish.py --run daniel-noborder-c-1001 --model base --dry-run
  python scripts/trace_review_publish.py --watch runs.txt     # lines "<run id> <model>"; re-publishes every 15 min

Runs are read from gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs/<run>/working/artifacts/ with the local
gcloud login. ARC3_PUBLISH_TOKEN comes from the environment or from `railway variable list` (as in
scripts/publish_railway_data.py).
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trace_review_index import FENCED, index_run  # noqa: E402

RUNS = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"
FINAL_STATUS = {"won", "gave_up", "lost", "game_over", "timeout", "finished", "error", "cancelled", "failed"}
API = "https://storage.googleapis.com/storage/v1"
GCLOUD_PY = Path(r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py")


def gcs_token() -> str:
    cmd = [sys.executable, str(GCLOUD_PY)] if GCLOUD_PY.exists() else ["gcloud"]
    return subprocess.run(cmd + ["auth", "print-access-token"], capture_output=True, text=True, check=True).stdout.strip()


def gcs_get(url: str, token: str) -> bytes:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def download_run(run: str, dest: Path, games: set[str] | None) -> list[str]:
    """The run's per-play event logs and viewer files (non-held-out games) into dest/artifacts/. Re-downloads only
    changed files."""
    token = gcs_token()
    bucket, prefix = RUNS[len("gs://"):].split("/", 1)
    pre = f"{prefix}/{run}/working/artifacts/"
    names, page = [], ""
    while True:
        body = json.loads(gcs_get(f"{API}/b/{bucket}/o?prefix={quote(pre)}&fields=items(name,size,md5Hash),nextPageToken"
                                  + (f"&pageToken={quote(page)}" if page else ""), token))
        names += [i for i in body.get("items", []) if i["name"].endswith(("_events.jsonl", "_viewer_data.json"))]
        page = body.get("nextPageToken")
        if not page:
            break
    (dest / "artifacts").mkdir(parents=True, exist_ok=True)
    got = []
    for item in names:
        name = item["name"].rsplit("/", 1)[-1]
        game = name[:4]
        if game in FENCED or (games and game not in games):
            continue
        target = dest / "artifacts" / name
        stamp = target.with_suffix(".md5")
        if target.exists() and stamp.exists() and stamp.read_text() == item["md5Hash"]:
            got.append(name)
            continue
        target.write_bytes(gcs_get(f"{API}/b/{bucket}/o/{quote(item['name'], safe='')}?alt=media", token))
        stamp.write_text(item["md5Hash"])
        got.append(name)
    return got


def railway_token(args) -> str:
    token = os.environ.get("ARC3_PUBLISH_TOKEN")
    if token:
        return token
    exe = shutil.which("railway.cmd") or shutil.which("railway") or "railway"
    out = subprocess.run([exe, "variable", "list", "--service", args.service, "--environment", args.environment,
                          "--json"], cwd=args.railway_cwd, check=True, capture_output=True, text=True).stdout
    token = json.loads(out).get("ARC3_PUBLISH_TOKEN")
    if not token:
        raise RuntimeError("ARC3_PUBLISH_TOKEN is not set on the Railway service")
    return token


def put(site: str, token: str, bundle: dict) -> dict:
    body = gzip.compress(json.dumps(bundle, separators=(",", ":")).encode("utf-8"), compresslevel=6)
    req = urllib.request.Request(f"{site}/api/v1/review/publication", data=body, method="PUT",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/gzip",
                                          "Content-Length": str(len(body))})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"publication refused: {exc.code} {exc.read()[:300]!r}") from exc


def publish_run(args, run: str, model: str, token: str | None) -> None:
    cache = Path(args.cache) / run
    games = set(args.games.split(",")) if args.games else None
    files = [f for f in download_run(run, cache, games) if f.endswith("_events.jsonl")]
    finished = {}
    for v in (cache / "artifacts").glob("*_viewer_data.json"):
        m = re.match(r"([a-z0-9]{4})-[0-9a-f]+_p(\d+)_viewer_data\.json$", v.name)
        if m:
            status = str(json.loads(v.read_text(encoding="utf-8")).get("status") or "").lower()
            finished[f"{m.group(1)}_p{m.group(2)}"] = status in FINAL_STATUS
    nodes, paths, contents = index_run(cache, run, model, include_fenced=False, finished=finished)
    by_game: dict[str, dict] = {}
    for n in nodes.values():
        by_game.setdefault(n["game"], {"nodes": [], "paths": []})["nodes"].append(
            {"id": n["id"], "kind": n["kind"], "game": n["game"], "level": n["level"], "meta": n.get("meta", {})})
    for p in paths:
        game = p["play"][:4]
        by_game[game]["paths"].append({**p, "content": contents[p["id"]]})
    print(f"{run} ({model}): {len(files)} plays, {len(paths)} paths at {len(nodes)} points, {len(by_game)} games")
    for game, bundle in sorted(by_game.items()):
        bundle["source"] = f"trace_review_publish {run}"
        if args.dry_run:
            size = len(gzip.compress(json.dumps(bundle).encode()))
            print(f"  {game}: {len(bundle['paths'])} paths, {size // 1024} KB gz (dry run)")
            continue
        result = put(args.site, token, bundle)
        print(f"  {game}: {result['paths']} paths, {result['contentWritten']} new files, {result['splitsMade']} new pairs")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", help="Daniel-runner run id")
    ap.add_argument("--model", help="model label: base, r0, r1, ...")
    ap.add_argument("--watch", help="file of '<run id> <model>' lines; publish all, then again every --every minutes")
    ap.add_argument("--every", type=int, default=15)
    ap.add_argument("--games", help="comma-separated game ids to limit to")
    ap.add_argument("--site", default="https://arc3.sonpham.net")
    ap.add_argument("--cache", default=r"D:\codex-work\trace-review-cache")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--service", default="arc3-viewer")
    ap.add_argument("--environment", default="production")
    ap.add_argument("--railway-cwd", default=str(Path(__file__).resolve().parents[1]))
    args = ap.parse_args()
    token = None if args.dry_run else railway_token(args)
    if args.watch:
        while True:
            for line in Path(args.watch).read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) == 2 and not line.startswith("#"):
                    try:
                        publish_run(args, parts[0], parts[1], token)
                    except Exception as exc:  # keep watching the other runs
                        print(f"{parts[0]}: {exc}", flush=True)
            time.sleep(60 * args.every)
    if not (args.run and args.model):
        ap.error("--run and --model (or --watch)")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}", args.run):
        ap.error("--run is not a run id")
    publish_run(args, args.run, args.model, token)
    return 0


if __name__ == "__main__":
    sys.exit(main())

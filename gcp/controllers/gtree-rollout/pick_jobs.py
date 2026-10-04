"""Job picker (stub): universal-tree frontier -> mid-tree rollout jobs for rollout_driver.py.

Author: Claude Opus 5.5 (3-Oct-2026, Son: restart nodes per (state, action) capped at N).

  python pick_jobs.py --game sb26 [--mode backward|uncertain] [--tree 5] [--N 4] [--limit 20] [--tries 4]
                      [--coach policy] [--campaign c1] --out jobs/   [--frontier-json saved.json]

1. GET /api/v1/gtree/frontier?game=&tree=&N=&mode=&limit= : nodes where some action has fewer than N samples, best
   first (the site documents the score; modes backward / uncertain re-rank it).
2. per node, GET /api/v1/gtree/node/<id>: its outgoing steps. One step is the restart point: prefer a resumable one
   (ctx_before set: the source play logged its requests, so replay_exact rebuilds the exact context), else any step
   with an event log (replay_actions). Fenced games are never picked.
3. one job per node: tries = the most samples any action there still needs (capped by --tries); the job names the
   source play's logs by GCS URI (the VM runner stages them and rewrites the paths, runner/stage_jobs.py).
Stub: the tree API needs a team key (env ARC3_TREE_KEY, sent as X-Review-Key) and has no source-log index yet, so the
URIs follow the duck layout gs://cellens-ai-artifacts/arc3-duck/<run>/{artifacts,working}/ (open question).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

SITE = os.environ.get("ARC3_SITE", "https://arc3.sonpham.net")
DUCK = "gs://cellens-ai-artifacts/arc3-duck"
FENCED = {"lf52", "tn36", "re86", "dc22", "su15", "as66"}
PLAY_RE = re.compile(r"^(?P<run>.+):(?P<game>[a-z0-9]{4})_p(?P<ps>\d+)(?:-(?P<gh>[0-9a-f]+))?$")


def get(path: str, params: dict | None = None) -> dict:
    url = f"{SITE}{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    headers = {"User-Agent": "arc3-gtree-rollout-picker/1"}
    if os.environ.get("ARC3_TREE_KEY"):
        headers["X-Review-Key"] = os.environ["ARC3_TREE_KEY"]
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
        return json.loads(r.read())


def source_of(step: dict, game_ids: dict[str, str]) -> dict | None:
    """The source play's logs for a step (duck layout); None when the rollout id does not parse."""
    m = PLAY_RE.match(step["rollout_id"])
    if not m:
        return None
    run, game, ps = m.group("run"), m.group("game"), int(m.group("ps"))
    gid = game_ids.get(game) or (f"{game}-{m.group('gh')}" if m.group("gh") else None)
    if not gid:
        return None
    base = f"{DUCK}/{run}"
    return {"run": run, "rollout_id": step["rollout_id"], "game_id": gid, "pass": ps,
            "events": f"{base}/artifacts/{gid}_p{ps}_events.jsonl",
            "requests": f"{base}/working/{gid}_p{ps}_requests.jsonl" if step.get("ctx_before") else None,
            "coach_log": f"{base}/working/coach-decisions.jsonl" if (step.get("detail") or {}).get("source") == "coach"
            else None}


def pick(frontier: dict, nodes: dict[str, dict], *, tries: int, coach: str, campaign: str, stop: dict,
         game_ids: dict[str, str]) -> list[dict]:
    jobs = []
    for row in frontier.get("nodes", []):
        node = nodes.get(row["id"])
        if not node:
            continue
        steps = [s for s in node.get("steps", []) if s.get("game") not in FENCED]
        steps.sort(key=lambda s: (not s.get("resumable"), s.get("rollout_id"), s.get("seq")))
        for s in steps:
            src = source_of(s, game_ids)
            if src is None:
                continue
            need = max((row.get("open") or {}).values() or [1])
            jobs.append({
                "job_id": f"{campaign}-{row['id'].split(':')[-1][:10]}-{s['seq']}",
                "campaign": campaign, "game_id": src.pop("game_id"), "pass": src.pop("pass"),
                "mode": "replay_exact" if src.get("requests") else "replay_actions",
                "source": src,
                "origin": {"seq": s["seq"], "turn": (s.get("detail") or {}).get("turn"), "t1": s["n1"],
                           "node": row["id"], "screen_hash": s["screen_hash"], "level": s["level"]},
                "tries": max(1, min(tries, int(need))), "stop": stop, "coach": {"spec": coach, "cap": None},
                "frontier": {"score": row.get("score"), "parts": row.get("parts"), "open": row.get("open")}})
            break
    return jobs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--mode", default="backward", choices=("backward", "uncertain", "coverage"))
    ap.add_argument("--tree", type=int, default=5)
    ap.add_argument("--N", type=int, default=4)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--tries", type=int, default=4)
    ap.add_argument("--coach", default="policy")
    ap.add_argument("--campaign", default="dev")
    ap.add_argument("--turn-cap", type=int, default=40)
    ap.add_argument("--frontier-json", help="use a saved frontier response instead of the API (offline)")
    ap.add_argument("--nodes-json", help="saved {node id: /node response} (offline)")
    ap.add_argument("--game-ids", default="{}", help='JSON {"sb26": "sb26-7fbdac44"} when rollout ids lack it')
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.game in FENCED:
        raise SystemExit(f"{a.game} is a held-out game: never sampled")
    if a.frontier_json:
        frontier = json.loads(Path(a.frontier_json).read_text(encoding="utf-8"))
    else:
        frontier = get("/api/v1/gtree/frontier", {"game": a.game, "tree": a.tree, "N": a.N, "mode": a.mode,
                                                  "limit": a.limit})
    if a.nodes_json:
        nodes = json.loads(Path(a.nodes_json).read_text(encoding="utf-8"))
    else:
        nodes = {row["id"]: get(f"/api/v1/gtree/node/{urllib.parse.quote(row['id'], safe=':')}")
                 for row in frontier.get("nodes", [])}
    jobs = pick(frontier, nodes, tries=a.tries, coach=a.coach, campaign=a.campaign,
                stop={"turn_cap": a.turn_cap, "stop_on_game_over": True}, game_ids=json.loads(a.game_ids))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for j in jobs:
        (out / f"{j['job_id']}.json").write_text(json.dumps(j, indent=1), encoding="utf-8")
    print(f"{len(jobs)} jobs from {len(frontier.get('nodes', []))} frontier nodes -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

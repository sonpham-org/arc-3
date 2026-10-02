"""Trace lake backfill (design: docs/plans/2026-10-01-arc3-trace-lake.md §7, steps A and B). Runs on a GCP VM.

index    step B: one lake_episodes doc per game of every finished run under gs://cellens-ai-artifacts/arc3-duck/
         (from the per-game *_p0_viewer_data.json) and one lake_levels doc per level; arm names from Firestore arc3_runs.
         No prompts needed, so every historical run gets a per-level index. These docs point at the raw run folder
         (`raw_uri`); `uri` stays empty until the run gets a canonical episode.
episodes step A: canonical episodes (lake.episode_lines) for runs that have request logs (Daniel's notebook runs),
         blobs deduped, pushed to gs://cellens-ai-artifacts/arc3-lake/v1/, index docs with real episode URIs.

Usage (VM):
  python lake_backfill.py index [--limit-runs N] [--dry-run]
  python lake_backfill.py episodes --runs daniel-base-a-1001,... --root gs://.../arc3-duck/daniel-base/runs \
      --harness-label daniel-nb-v1 --policy-json '{"base": "intel-w4a16-autoround", ...}' --stage /opt/rl/lake
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, urlencode

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lake  # noqa: E402
import rl_reward as rr  # noqa: E402
import rl_tree as rt  # noqa: E402
import seed_moments as sm  # noqa: E402

BUCKET = "cellens-ai-artifacts"
TOP = "arc3-duck/"


class Gcs:
    def __init__(self, store: rt.FirestoreStore):
        self.store = store

    def _get(self, url: str) -> bytes:
        from urllib.request import Request, urlopen
        with urlopen(Request(url, headers={"Authorization": "Bearer " + self.store._token()}), timeout=120) as r:
            return r.read()

    def list(self, prefix: str, delimiter: str | None = None) -> tuple[list[dict], list[str]]:
        items, prefixes, cursor = [], [], None
        while True:
            params = {"prefix": prefix, "fields": "items(name,generation,size,updated),prefixes,nextPageToken",
                      "maxResults": 1000}
            if delimiter:
                params["delimiter"] = delimiter
            if cursor:
                params["pageToken"] = cursor
            page = json.loads(self._get(f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o?" + urlencode(params)))
            items += page.get("items", [])
            prefixes += page.get("prefixes", [])
            cursor = page.get("nextPageToken")
            if not cursor:
                return items, prefixes

    def cat(self, name: str) -> bytes:
        return self._get(f"https://storage.googleapis.com/download/storage/v1/b/{BUCKET}/o/{quote(name, safe='')}?alt=media")


def run_of(name: str) -> str:
    """Run id of a viewer file path: arc3-duck/<run>/... or arc3-duck/daniel-base/runs/<run>/..."""
    parts = name.split("/")
    if len(parts) > 3 and parts[1] == "daniel-base" and parts[2] == "runs":
        return parts[3]
    return parts[1]


def index_docs(run: str, arm: str | None, name: str, viewer: dict, base_actions: dict) -> tuple[dict, list[dict]]:
    gid = str(viewer.get("game_id") or "")
    human = list(base_actions.get(gid) or [])
    done = int(viewer.get("levels_completed") or 0)
    apl = [int(x) for x in viewer.get("actions_per_level") or []]
    eid = lake.episode_id("scored_run", run, gid)
    fenced = gid[:4].lower() in lake.FENCED
    levels = []
    for k in range(1, max(len(human), done + (1 if done < len(apl) else 0)) + 1):
        cleared = k <= done
        used = apl[k - 1] if k - 1 < len(apl) else None
        if not cleared and not used:
            continue
        h = human[k - 1] if k - 1 < len(human) else None
        levels.append({"id": f"{eid}.L{k}", "episode_id": eid, "run_id": run, "arm": arm, "game": gid[:4],
                       "game_id": gid, "level": k, "cleared": cleared, "actions": used, "human": h,
                       "score": rr.level_score(h, used) if (cleared and h and used) else 0.0,
                       "source": "scored_run", "teacher": "none", "fenced": fenced, "harness_id": None,
                       "policy_id": None})
    acts = [apl[k - 1] for k in range(1, done + 1) if k - 1 < len(apl)]
    ep = {"id": eid, "schema": lake.SCHEMA, "uri": None, "raw_uri": f"gs://{BUCKET}/{name.rsplit('/', 1)[0]}/",
          "source": {"kind": "scored_run", "run_id": run, "arm": arm}, "run_id": run, "arm": arm,
          "game": gid[:4], "game_id": gid, "game_version": None, "harness_id": None, "policy_id": None,
          "parent": None, "teacher": "none", "fenced": fenced, "levels_cleared": done, "n_levels": len(human) or None,
          "actions": sum(apl), "status": viewer.get("status"),
          "game_score": rr.game_score(done, acts, human) if human else None, "created_at": time.time()}
    return ep, levels


def cmd_index(args) -> int:
    store = rt.FirestoreStore()
    gcs = Gcs(store)
    obs = sm._observer()
    arms = {}
    for d in store.query("arc3_runs"):
        if d.get("run_id"):
            arms[d["run_id"]] = d.get("arm")
    _, tops = gcs.list(TOP, delimiter="/")
    tops = [p for p in tops if not any(p.startswith(TOP + x) for x in ("models/", "code/", "injection/", "lobotomy/"))]
    print(f"{len(tops)} top-level folders; {len(arms)} runs with arm names", flush=True)

    def viewers(prefix: str) -> list[dict]:
        items, _ = gcs.list(prefix)
        return [i for i in items if i["name"].endswith("_p0_viewer_data.json")]

    with ThreadPoolExecutor(max_workers=32) as pool:
        files = [f for fs in pool.map(viewers, tops[:args.limit_runs or None]) for f in fs]
    print(f"{len(files)} viewer files", flush=True)

    # A folder can hold several runs' (or passes') files for the same game: those get the folder path's hash on the id.
    from collections import Counter
    import hashlib
    gid_of = lambda n: n.rsplit("/", 1)[1].replace("_p0_viewer_data.json", "")  # noqa: E731
    seen = Counter((run_of(i["name"]), gid_of(i["name"])) for i in files)

    def one(item):
        try:
            v = json.loads(gcs.cat(item["name"]))
        except Exception as e:  # noqa: BLE001
            return None, [], f"{item['name']}: {e}"
        run = run_of(item["name"])
        ep, lv = index_docs(run, arms.get(run), item["name"], v, obs.BASE_ACTIONS)
        if seen[(run, gid_of(item["name"]))] > 1:
            tag = hashlib.sha1(item["name"].rsplit("/", 1)[0].encode()).hexdigest()[:8]
            old = ep["id"]
            ep["id"] = f"{old}-{tag}"
            for d in lv:
                d["id"] = d["id"].replace(old, ep["id"], 1)
                d["episode_id"] = ep["id"]
        return ep, lv, None

    eps, lvs, errs = [], [], []
    with ThreadPoolExecutor(max_workers=32) as pool:
        for ep, lv, err in pool.map(one, files):
            if err:
                errs.append(err)
            elif ep:
                eps.append(ep)
                lvs += lv
    print(f"{len(eps)} episodes, {len(lvs)} levels, {len(errs)} read errors", flush=True)
    Path(args.out).mkdir(parents=True, exist_ok=True)
    for name, rows in (("lake_episodes", eps), ("lake_levels", lvs)):
        with open(Path(args.out) / f"{name}.jsonl", "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    if not args.dry_run:
        f = store.fs
        n1 = lake.firestore_batch_write("lake_episodes", eps, f._call, f.API, store._token, f._value)
        n2 = lake.firestore_batch_write("lake_levels", lvs, f._call, f.API, store._token, f._value)
        print(f"Firestore: {n1} lake_episodes, {n2} lake_levels", flush=True)
    return 0


def cmd_episodes(args) -> int:
    store = rt.FirestoreStore()
    gcs = Gcs(store)
    obs = sm._observer()
    stage = Path(args.stage)
    blobs = lake.LocalBlobs(stage)
    policy = json.loads(args.policy_json)
    harness = {"label": args.harness_label, "bundle": args.harness_label, "knobs": None,
               "render_profile": args.render_profile}
    harness["id"] = lake.harness_id(harness)
    policy["id"] = lake.policy_id(policy)
    eps, lvs = [], []
    for run in [r for r in args.runs.split(",") if r]:
        work = f"{args.root.rstrip('/')}/{run}/working/".replace(f"gs://{BUCKET}/", "")
        items, _ = gcs.list(work)
        for item in items:
            name = item["name"]
            if not name.endswith("_p0_requests.jsonl"):
                continue
            gid = name.rsplit("/", 1)[1].replace("_p0_requests.jsonl", "")
            rows = [json.loads(l) for l in gcs.cat(name).decode("utf-8").splitlines() if l.strip()]
            try:
                events = [json.loads(l) for l in gcs.cat(f"{work}artifacts/{gid}_p0_events.jsonl").decode("utf-8").splitlines() if l.strip()]
            except Exception:  # noqa: BLE001
                events = []
            eid = lake.episode_id("scored_run", run, gid)
            header = {"episode_id": eid, "source": {"kind": "scored_run", "run_id": run, "raw": f"gs://{BUCKET}/{work}"},
                      "game": {"id": gid, "version": None}, "harness": harness, "policy": policy, "parent": None,
                      "teacher": "none", "fenced": gid[:4].lower() in lake.FENCED}
            lines = lake.episode_lines(header, rows, blobs, events=events, human=list(obs.BASE_ACTIONS.get(gid) or []))
            uri = lake.episode_uri(eid, "scored_run")
            lake.write_episode(stage, uri, lines)
            ep = lake.episode_doc(lines, uri)
            ep.update(run_id=run, arm=args.harness_label, raw_uri=f"gs://{BUCKET}/{work}")
            eps.append(ep)
            lvs += [dict(d, run_id=run, arm=args.harness_label) for d in lake.level_docs(lines)]
            print(f"{run} {gid}: {sum(1 for l in lines if l['kind'] == 'call')} calls -> {uri}", flush=True)
    lake.rsync_stage(stage)
    f = store.fs
    print("Firestore:", lake.firestore_batch_write("lake_episodes", eps, f._call, f.API, store._token, f._value),
          lake.firestore_batch_write("lake_levels", lvs, f._call, f.API, store._token, f._value), flush=True)
    for col, doc in (("lake_harnesses", {**harness, "id": harness["id"], "created_at": time.time()}),
                     ("lake_policies", {**policy, "id": policy["id"], "created_at": time.time()})):
        store.put(col, doc)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("index")
    a.add_argument("--limit-runs", type=int, default=0)
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--out", default="/opt/rl/lake-index")
    b = sub.add_parser("episodes")
    b.add_argument("--runs", required=True)
    b.add_argument("--root", required=True)
    b.add_argument("--harness-label", required=True)
    b.add_argument("--render-profile", default="sglang-0.5.19")
    b.add_argument("--policy-json", required=True)
    b.add_argument("--stage", default="/opt/rl/lake")
    args = ap.parse_args()
    return cmd_index(args) if args.cmd == "index" else cmd_episodes(args)


if __name__ == "__main__":
    raise SystemExit(main())

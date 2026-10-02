"""Data for the RL live page (https://arc3-rl-live.web.app): the round being trained, the test panels and the
loop's timing. Plan: docs/plans/2026-10-01-rl-on-burst-games.md section 9g.

  C:/Python312/python.exe build_site.py        -> public/data.json
  bash refresh.sh                              -> rebuild and deploy every 5 minutes

Reads with the local gcloud login (GCS JSON API, one token per build): the trainer's train_log.jsonl / job.log /
status.json and their .mtime.json sidecars (joblog_mirror.sh on the trainer VM copies them every minute), each test
run's phases.tsv and per-game viewer files, the G0 extraction summaries (cached in site-cache/), and Daniel's four
all-25 runs from the local Firestore dump. The page gets game ids only (never titles) and no bucket, VM or path.
"""
import concurrent.futures
import json
import math
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))   # gcp/
import arc3_firestore_scores as fs  # noqa: E402

API = "https://storage.googleapis.com/storage/v1"
CFG = json.loads((HERE / "site_config.json").read_text(encoding="utf-8"))
CACHE = HERE / "site-cache"
BASE = {gid.split("-")[0]: base for gid, base in fs.observer.BASE_ACTIONS.items()}   # per-level baseline actions
LEVELS = {g: len(b) for g, b in BASE.items()}
FINAL = {"won", "gave_up", "lost", "game_over", "timeout", "finished", "error", "cancelled", "failed"}
SAVE_MIN = 3                                         # adapter save + upload after the last record
IO = concurrent.futures.ThreadPoolExecutor(16)       # leaf reads only (never waits on another task)
_TOKEN = {}


# ------------------------------------------------------------------------------------------------ GCS reads
def _get(url):
    if "v" not in _TOKEN:
        _TOKEN["v"] = fs._local_token()
    with urlopen(Request(url, headers={"Authorization": f"Bearer {_TOKEN['v']}"}), timeout=90) as r:
        return r.read()


def _split(uri):
    bucket, _, name = uri[len("gs://"):].partition("/")
    return bucket, name


def gcat(uri):
    """Text of one object, or None when it is missing or unreadable."""
    bucket, name = _split(uri)
    try:
        return _get(f"{API}/b/{bucket}/o/{quote(name, safe='')}?alt=media").decode("utf-8", "replace")
    except (HTTPError, URLError, TimeoutError):
        return None


def gfiles(prefix, suffix):
    """{name: text} for every object under a gs:// prefix whose name ends with `suffix`."""
    bucket, pre = _split(prefix)
    names, page = [], ""
    while True:
        try:
            body = json.loads(_get(f"{API}/b/{bucket}/o?prefix={quote(pre)}&fields=items(name),nextPageToken"
                                   + (f"&pageToken={quote(page)}" if page else "")))
        except (HTTPError, URLError, TimeoutError):
            return {}
        names += [i["name"] for i in body.get("items", []) if i["name"].endswith(suffix)]
        page = body.get("nextPageToken")
        if not page:
            break
    texts = IO.map(lambda n: gcat(f"gs://{bucket}/{n}"), names)
    return {n.rsplit("/", 1)[-1]: t for n, t in zip(names, texts) if t is not None}


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ts else None


def parse_iso(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()


def jload(text):
    try:
        return json.loads(text) if text else None
    except json.JSONDecodeError:
        return None


# ------------------------------------------------------------------------------------------------ training
def training():
    t, job, mj = CFG["trainer"], CFG["train_job"], CFG["merge_job"]
    keys = {"log": f"{t}/out/{job}/job.log", "rows": f"{t}/out/{job}/train_log.jsonl",
            "mt": f"{t}/out/{job}/train_log.jsonl.mtime.json", "status": f"{t}/status.json",
            "exit": f"{t}/out/{job}/EXIT", "adapter": f"{t}/out/{job}/ADAPTER.json",
            "mexit": f"{t}/out/{mj}/EXIT", "mreport": f"{t}/out/{mj}/merged/MERGE_REPORT.json"}
    got = dict(zip(keys, IO.map(gcat, keys.values())))
    rows = [jload(line) for line in (got["rows"] or "").splitlines() if line.strip()]
    recs = [r for r in rows if r and "loss" in r]
    skips = [r for r in rows if r and "skip" in r]
    m = re.search(r"^(\d+) records$", got["log"] or "", re.M)
    total = int(m.group(1)) if m else CFG["records_total"]
    last_end = (jload(got["mt"]) or {}).get("mtime")
    # each record's end time, counted back from the log's last change by the records' own durations
    ends, at = [], last_end
    for r in reversed(recs):
        ends.append(at)
        at = at - r["sec"] if at else None
    ends.reverse()
    started = parse_iso(CFG["train_started"])
    load_min = max(0.0, (ends[0] - recs[0]["sec"] - started) / 60) if recs and ends[0] else None
    status = jload(got["status"]) or {}
    exit_code = (got["exit"] or "").strip()
    state = ("done" if exit_code == "0" else "failed" if exit_code else
             "running" if status.get("job") == job or recs else "waiting")
    recent = [r["sec"] for r in recs[-12:]]
    mean_sec = sum(recent) / len(recent) if recent else 300.0
    left = max(0, total - len(recs) - len(skips))
    eta = (last_end + left * mean_sec + SAVE_MIN * 60) if (state == "running" and last_end) else None
    adapter = jload(got["adapter"])
    mexit = (got["mexit"] or "").strip()
    report = jload(got["mreport"]) or {}
    merge_state = "done" if mexit == "0" else "failed" if mexit else "running" if status.get("job") == mj else "waiting"
    return {
        "job_state": state, "total": total, "done": len(recs), "skipped": len(skips),
        "records": [{"game": r["game"].split("-")[0], "loss": round(r["loss"], 4), "tokens": r["tokens"],
                     "trained": r["n_loss"], "sec": r["sec"], "step": r["step"], "mem": r.get("mem_gib"),
                     "end": iso(e)} for r, e in zip(recs, ends)],
        "skips": [{"game": (s.get("skip") or "").split("-")[0], "tokens": s.get("tokens"),
                   "why": "out of memory" if s.get("oom") else "no trainable turns" if not s.get("n_loss")
                   else "too long"} for s in skips],
        "started": CFG["train_started"], "last_record_end": iso(last_end), "eta": iso(eta),
        "mean_sec": round(mean_sec), "load_min": None if load_min is None else round(load_min, 1),
        "adapter": adapter and {"sha": adapter.get("sha"), "steps": adapter.get("steps")},
        "minutes_est": round((load_min or 2) + total * mean_sec / 60 + SAVE_MIN),
        "merge": {"state": merge_state, "kept_share": report.get("kept_share_mean"),
                  "changed_files": len(report.get("changed_shards") or [])},
    }


# ------------------------------------------------------------------------------------------------ test runs
def run_state(run_id):
    prefix = f"{CFG['runs_prefix']}/{run_id}"
    phases = gcat(f"{prefix}/phases.tsv") or ""
    lines = [ln.split("\t") for ln in phases.splitlines() if ln.strip()]
    plays = []
    for text in gfiles(f"{prefix}/working/artifacts/", "_viewer_data.json").values():
        v = jload(text)
        if not v or not v.get("game_id"):
            continue
        g = v["game_id"].split("-")[0]
        if g not in BASE:
            continue
        levels = int(v.get("levels_completed") or 0)
        actions = [int(x) for x in v.get("actions_per_level") or []]
        status = str(v.get("status") or "").lower()
        plays.append({"game": g, "pass": v.get("pass_index"), "levels": levels, "actions": sum(actions),
                      "score": round(fs.observer.game_score(levels, actions, BASE[g]), 1),
                      "playing": status not in FINAL, "won": status == "won"})
    first, last = (lines[0], lines[-1]) if lines else (None, None)
    phase = last[2] if last and len(last) > 2 else "launching"
    ready = next((ln[0] for ln in lines if len(ln) > 2 and ln[2].startswith("server_ready")), None)
    state = "done" if phase.startswith("finish") else "playing" if ready else "setting up" if lines else "launching"
    return {"state": state, "phase": phase, "started": first[0] if first else None, "ready": ready,
            "finished": last[0] if phase.startswith("finish") else None, "plays": plays}


def summarize(games, plays):
    """Per game: repeats and mean levels. Panel total = sum of per-game means; its standard error =
    sqrt(sum of variance / repeats), only once every game has 2+ repeats."""
    out, total, var, complete = {}, 0.0, 0.0, True
    for g in games:
        lv = [p["levels"] for p in plays if p["game"] == g]
        n = len(lv)
        mean = sum(lv) / n if n else None
        out[g] = {"n": n, "mean": None if mean is None else round(mean, 2)}
        if n > 1:
            total += mean
            var += sum((x - mean) ** 2 for x in lv) / (n - 1) / n
        else:
            total += mean or 0.0
            complete = False
    return out, round(total, 2), (round(math.sqrt(var), 2) if complete else None)


def panels():
    run_ids = sorted({r for p in CFG["panels"] for arm in ("base", "lora") for r in p[arm]})
    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        states = dict(zip(run_ids, pool.map(run_state, run_ids)))
    out = []
    for p in CFG["panels"]:
        arms = {}
        for arm in ("base", "lora"):
            runs = [states[r] for r in p[arm]]
            plays = [dict(x, run=i) for i, r in enumerate(runs) for x in r["plays"] if x["game"] in p["games"]]
            per_game, total, se = summarize(p["games"], plays)
            arms[arm] = {"runs": [{k: r[k] for k in ("state", "phase", "started", "ready", "finished")} for r in runs],
                         "plays": plays, "per_game": per_game, "total": total, "se": se,
                         "playing": sum(x["playing"] for x in plays)}
        out.append({"key": p["key"], "label": p["label"], "note": p["note"], "games": p["games"],
                    "passes": p["passes"], "levels": {g: LEVELS[g] for g in p["games"]}, "arms": arms})
    return out


# ------------------------------------------------------------------------------------------------ static parts
def g0_data():
    CACHE.mkdir(exist_ok=True)
    out = {}
    for run, uri in CFG["g0"].items():
        f = CACHE / f"g0-{run}.json"
        if not f.exists():
            text = gcat(uri)
            if text:
                f.write_text(text, encoding="utf-8")
        s = jload(f.read_text(encoding="utf-8")) if f.exists() else None
        for g, d in ((s or {}).get("games") or {}).items():
            out.setdefault(g, {})[run] = {"cleared": d.get("cleared") or [], "replies": d.get("trained_replies", 0),
                                          "records": d.get("records", 0), "turns": d.get("turns", 0)}
    return out


def noise():
    rows = json.loads(Path(CFG["noise_dump"]).read_text(encoding="utf-8"))
    by_id = {r["run_id"]: r for r in rows}
    runs = [(rid, label) for rid, label in CFG["noise_runs"] if rid in by_id]
    games = sorted(LEVELS)
    return {"runs": [label for _, label in runs], "games": games,
            "levels": {g: [(by_id[rid]["per_game"].get(g) or {}).get("levels") for rid, _ in runs] for g in games}}


def main():
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(2) as outer:
        f_train, f_panels = outer.submit(training), outer.submit(panels)
        data = {"updated": iso(time.time()), "round": CFG["round"], "round_note": CFG["round_note"],
                "split": CFG["split"], "levels": LEVELS, "g0": g0_data(), "noise": noise(),
                "train": f_train.result(), "panels": f_panels.result()}
    data["stages"] = [dict(s, minutes=data["train"]["minutes_est"]) if s["key"] == "train" else s
                      for s in CFG["stages"]]
    data["build_sec"] = round(time.time() - t0, 1)
    (HERE / "public" / "data.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    tr = data["train"]
    runs = [(p["key"], r["state"], len(p["arms"][a]["plays"])) for p in data["panels"] for a in ("base", "lora")
            for r in p["arms"][a]["runs"]]
    print(f"data.json: train {tr['done']}/{tr['total']} {tr['job_state']} eta {tr['eta']} load {tr['load_min']} min; "
          f"runs {runs}; {data['build_sec']} s")
    IO.shutdown(wait=False)


if __name__ == "__main__":
    main()

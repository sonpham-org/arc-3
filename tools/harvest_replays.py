#!/usr/bin/env python3.13
"""
Author: Claude Opus 5 (sub-agent for Bubba)
Date: 17-September-2026
PURPOSE: Harvest public ARC Prize vendor-agent replays (unauthenticated, GET only) and
         stream-strip them into compact per-session JSONL suitable for coherence analysis.
         Fetches /api/sessions/<guid> for metadata, then /api/recordings/<game_id>/<guid>
         for each run, parsing the recording line-by-line and DROPPING the raw frame grids
         (which dominate the 10-90MB payloads) in favour of a frame fingerprint. Records
         the parsed action_input.reasoning object (output / reasoning summary / usage /
         cost / adapter state) which is the actual deliverable.
         Disk-guarded, resumable, atomic writes. Never POSTs, never starts/resets a game.
SRP/DRY check: Pass - tools/replay_scrape.py fetches the SAME endpoint but keeps every byte
         the API served, because the decision-step corpus is defined as the raw record. This
         file exists for the opposite need: frames dropped, reasoning kept, ~50x smaller, so
         a coherence sweep over hundreds of sessions fits on disk. Merging them would force
         one of the two corpora to store what it does not want.
"""
import json, os, sys, time, hashlib, shutil, urllib.request, urllib.error

BASE = "https://arcprize.org"
ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "datasets", "vendor-coherence")
REPLAYS = os.path.join(ROOT, "replays")
GUIDS = os.path.join(ROOT, "guids")
MIN_FREE_GB = 60
UA = "bubba-arc3-research/1.0 (read-only replay analysis)"


def free_gb(path=ROOT):
    st = shutil.disk_usage(path)
    return st.free / (1024 ** 3)


def get(url, timeout=300, retries=3):
    """GET only. Returns bytes. Raises on persistent failure."""
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA}, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(2 * (a + 1))
    raise last


def geti(v, default=0):
    try:
        return int(str(v))
    except Exception:
        return default


def getb(v):
    return str(v).lower() == "true"


def frame_fp(frame):
    """Cheap fingerprint of the frame grid; lets us tell if an action changed anything."""
    if frame is None:
        return None, None
    blob = json.dumps(frame, separators=(",", ":"), sort_keys=True)
    dims = None
    try:
        f = frame
        d = []
        while isinstance(f, list) and f:
            d.append(len(f))
            f = f[0]
        dims = "x".join(str(n) for n in d)
    except Exception:
        pass
    return hashlib.sha1(blob.encode()).hexdigest()[:16], dims


def compact_line(idx, rec, prev_hash, stats):
    data = rec.get("data", rec)
    ai = data.get("action_input") or {}
    raw = ai.get("reasoning")
    fh, fdims = frame_fp(data.get("frame"))

    out = {
        "i": idx,
        "ts": rec.get("timestamp"),
        "state": data.get("state"),
        "levels_completed": geti(data.get("levels_completed")),
        "win_levels": geti(data.get("win_levels")),
        "available_actions": [geti(a) for a in (data.get("available_actions") or [])],
        "full_reset": getb(data.get("full_reset")),
        "act_id": ai.get("id"),
        "fhash": fh,
        "fdims": fdims,
        "fchanged": (None if fh is None or prev_hash is None else fh != prev_hash),
    }
    ad = ai.get("data") or {}
    if "x" in ad:
        out["x"] = geti(ad.get("x"), None)
    if "y" in ad:
        out["y"] = geti(ad.get("y"), None)

    if raw in (None, "None", ""):
        out["reasoning_present"] = False
        stats["no_reasoning"] += 1
    else:
        out["reasoning_present"] = True
        try:
            ro = json.loads(raw)
        except Exception:
            stats["unparseable"] += 1
            out["reasoning_unparseable"] = True
            out["reasoning_raw_head"] = str(raw)[:400]
            return out, fh
        stats["parsed"] += 1
        stats["keysets"][",".join(sorted(ro.keys()))] = (
            stats["keysets"].get(",".join(sorted(ro.keys())), 0) + 1
        )
        out["out"] = ro.get("output")
        summ = ro.get("reasoning")
        # Some adapters may name it differently; capture whichever is present.
        if summ in (None, "", [], {}):
            for alt in ("summary", "reasoning_summary", "thinking", "thought"):
                if ro.get(alt):
                    summ = ro[alt]
                    stats["alt_summary_key"][alt] = stats["alt_summary_key"].get(alt, 0) + 1
                    break
        out["summary"] = summ if summ not in ("", [], {}) else None
        if out["summary"]:
            stats["summary_nonnull"] += 1

        u = ro.get("usage") or {}
        if u:
            out["usage"] = {
                "in": u.get("input_tokens"),
                "out": u.get("output_tokens"),
                "total": u.get("total_tokens"),
                "cached": (u.get("input_tokens_details") or {}).get("cached_tokens"),
                "rtok": (u.get("output_tokens_details") or {}).get("reasoning_tokens"),
            }
            if (out["usage"]["rtok"] or 0) > 0:
                stats["reasoning_tokens_pos"] += 1
        c = ro.get("cost") or {}
        if c:
            out["cost_total"] = c.get("total_cost")
        st = ro.get("state") or {}
        if st:
            out["hist"] = {
                "sent": st.get("input_items_sent"),
                "compacted": st.get("compaction_items_returned"),
                "before_prune": st.get("history_items_before_prune"),
                "after_prune": st.get("history_items_after_prune"),
            }
    return out, fh


def new_stats():
    return {
        "parsed": 0, "unparseable": 0, "no_reasoning": 0,
        "summary_nonnull": 0, "reasoning_tokens_pos": 0,
        "keysets": {}, "alt_summary_key": {},
    }


def harvest_session(group, guid, keep_raw_to=None, log=print):
    gdir = os.path.join(REPLAYS, group)
    os.makedirs(gdir, exist_ok=True)
    meta_path = os.path.join(gdir, f"{guid}.meta.json")

    if os.path.exists(meta_path):
        try:
            meta = json.load(open(meta_path))
            if meta.get("_complete"):
                return "skip"
        except Exception:
            pass

    sess = json.loads(get(f"{BASE}/api/sessions/{guid}", timeout=60))
    meta = {
        "guid": guid, "group": group,
        "model": sess.get("model"), "runner": sess.get("runner"),
        "config": sess.get("config"), "tags": sess.get("tags"),
        "score": sess.get("score"), "ai_agent": sess.get("ai_agent"),
        "published_at": sess.get("published_at"), "open_at": sess.get("open_at"),
        "last_update": sess.get("last_update"),
        "total_actions": sess.get("total_actions"),
        "total_levels_completed": sess.get("total_levels_completed"),
        "total_environments": sess.get("total_environments"),
        "total_environments_completed": sess.get("total_environments_completed"),
        "environments": sess.get("environments"),
        "runs": [],
    }

    for env in sess.get("environments") or []:
        for run in env.get("runs") or []:
            gid = run.get("id")
            if not gid:
                continue
            if free_gb() < MIN_FREE_GB:
                raise RuntimeError(f"DISK GUARD: free {free_gb():.1f}GB < {MIN_FREE_GB}GB")
            stem = f"{guid}__{gid}"
            final = os.path.join(gdir, f"{stem}.jsonl")
            tmp = final + ".tmp"

            raw = get(f"{BASE}/api/recordings/{gid}/{guid}")
            if keep_raw_to:
                os.makedirs(keep_raw_to, exist_ok=True)
                with open(os.path.join(keep_raw_to, f"{stem}.raw.jsonl"), "wb") as fh:
                    fh.write(raw)

            stats = new_stats()
            prev = None
            n = 0
            bad = 0
            with open(tmp, "w") as outf:
                for line in raw.decode("utf-8", "replace").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        bad += 1
                        continue
                    c, prev = compact_line(n, rec, prev, stats)
                    outf.write(json.dumps(c, separators=(",", ":")) + "\n")
                    n += 1
            os.replace(tmp, final)

            expected = geti(run.get("actions"), None)
            integrity = "ok" if (expected is not None and n == expected + 1) else "MISMATCH"
            rmeta = {
                "game_id": gid, "guid": guid,
                "run_score": run.get("score"), "run_state": run.get("state"),
                "run_actions": expected, "run_resets": run.get("resets"),
                "levels_completed": run.get("levels_completed"),
                "level_scores": run.get("level_scores"),
                "level_actions": run.get("level_actions"),
                "level_baseline_actions": run.get("level_baseline_actions"),
                "raw_bytes": len(raw),
                "compact_bytes": os.path.getsize(final),
                "lines": n, "bad_lines": bad,
                "integrity": integrity,
                "expected_lines": (expected + 1) if expected is not None else None,
                "stats": stats,
            }
            meta["runs"].append(rmeta)
            log(f"  {group} {guid[:8]} {gid} lines={n} exp={rmeta['expected_lines']} "
                f"{integrity} parsed={stats['parsed']} summary={stats['summary_nonnull']} "
                f"rtok+={stats['reasoning_tokens_pos']} raw={len(raw)/1e6:.1f}MB "
                f"compact={rmeta['compact_bytes']/1e3:.0f}KB")

    meta["_complete"] = True
    mtmp = meta_path + ".tmp"
    with open(mtmp, "w") as f:
        json.dump(meta, f)
    os.replace(mtmp, meta_path)
    return "ok"


def main():
    groups = sys.argv[1:]
    if not groups:
        print("usage: harvest_replays.py <group> [group...]")
        sys.exit(2)
    # A handful of raw recordings retained for fidelity checking.
    sample_dir = os.path.join(ROOT, "samples")
    sample_budget = int(os.environ.get("RAW_SAMPLES", "0"))

    out_group = os.environ.get("OUT_GROUP")
    shard = os.environ.get("SHARD")  # "k/n" -> take every nth guid starting at k
    for group in groups:
        gf = os.path.join(GUIDS, f"{group}.txt")
        guids = [l.strip() for l in open(gf) if l.strip()]
        if shard:
            k, n = (int(x) for x in shard.split("/"))
            guids = guids[k::n]
        group = out_group or group
        print(f"=== {group}: {len(guids)} sessions, free={free_gb():.1f}GB", flush=True)
        ok = skip = err = 0
        for i, guid in enumerate(guids, 1):
            keep = sample_dir if sample_budget > 0 else None
            try:
                r = harvest_session(group, guid, keep_raw_to=keep,
                                    log=lambda m: print(m, flush=True))
                if r == "skip":
                    skip += 1
                else:
                    ok += 1
                    if keep:
                        sample_budget -= 1
            except RuntimeError as e:
                print(f"FATAL {e}", flush=True)
                sys.exit(1)
            except Exception as e:
                err += 1
                print(f"  ERR {guid}: {type(e).__name__}: {e}", flush=True)
            if i % 25 == 0:
                print(f"--- {group} {i}/{len(guids)} ok={ok} skip={skip} err={err} "
                      f"free={free_gb():.1f}GB", flush=True)
        print(f"=== {group} DONE ok={ok} skip={skip} err={err}", flush=True)


if __name__ == "__main__":
    main()

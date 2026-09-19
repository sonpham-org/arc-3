#!/usr/bin/env python3
"""Bookkeeping for the game evolution loop (research/game-evolution/README.md).

Author: Claude Opus 5, 19-September-2026
Purpose: the parts of the loop that should be arithmetic, not judgement. It reads the pool
from the Games page's public trees API and the private mechanic descriptors, then:

  status   pool size, how much of it is improved, and whether step 1 (grow) is due
  nearest  the existing games closest to a game's metadata.json (novelty check)
  anchor   new-seed mode: sample the anchor for a new seed from its 5 nearest games
  pair     normal mode: least-improved first game, partner from the farthest 20%
  draw     step 3: three mechanic-family candidates for a game, weighted 1/(1+adopted+drawn)
  publish  vet with the step's profile, upload through publish_game_versions.py, log it
  log      append one event to the public ledger (ids only)

Distance follows Codex's v3 sampler (weighted overlap of mechanic phrases, primary x3 and
secondary x2), plus the structural fields (verb, subject, control, topology, timing,
information, objective), which v3 left to reviewers:
    distance = 0.6 * mechanic_distance + 0.4 * structure_distance      (0 = same, 1 = unrelated)

The descriptors of pool games live outside this public repo (most pool games are shown
blind): point --descriptors at the run directory's pool/descriptors.json.
"""

from __future__ import annotations

import argparse
import http.client
import json
import math
import random
import re
import secrets
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "research" / "game-evolution" / "ledger.jsonl"
REGISTRY = ROOT / "research" / "game-evolution" / "recovered" / "codex" / "glowup-mechanics-registry-v1.json"
GROWTH_THRESHOLD = 0.80
GENERATION_SIZE = 10
STRUCTURE_FIELDS = ("core_verb", "controlled_subject", "control", "topology", "temporal", "information", "objective")
STOP = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of", "on", "or", "the", "to", "with", "its", "their"}


# ── Pool ─────────────────────────────────────────────────────────────────────


def fetch_pool(api_url: str) -> list[dict]:
    """Every tree on the Games page, through the anonymous public API."""
    parts = urlsplit(api_url)
    trees, offset = [], 0
    while True:
        conn_cls = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
        conn = conn_cls(parts.netloc, timeout=60)
        conn.request("GET", f"{parts.path.rstrip('/')}/api/v1/public/games/trees?limit=100&offset={offset}")
        response = conn.getresponse()
        if response.status != 200:
            raise SystemExit(f"trees API answered {response.status}")
        page = json.loads(response.read())
        trees += page["trees"]
        offset += len(page["trees"])
        if not page["trees"] or offset >= page["total"]:
            return trees


def pool_of(trees: list[dict]) -> list[dict]:
    """The loop's pool: family is not official and not retired. Note that a tree's family is
    its root's: the contributed glow-ups hang under ai-generated seeds, so trees rooted in a
    retired family stay in the pool when a later version belongs to another family."""
    return [t for t in trees if t["family"] not in {"official", "redbluepill"}]


def improved(tree: dict) -> bool:
    return int(tree.get("versionCount") or 1) > 1


# ── Distance ─────────────────────────────────────────────────────────────────


def mechanic_vector(meta: dict) -> Counter:
    vector: Counter = Counter()
    phrases = [(meta.get("primary") or "", 3)] + [(p, 2) for p in meta.get("secondary") or []]
    for phrase, weight in phrases:
        for token in set(re.findall(r"[a-z0-9]+", str(phrase).lower())) - STOP:
            vector[token] += weight
    return vector


def mechanic_distance(a: dict, b: dict) -> float:
    va, vb = mechanic_vector(a), mechanic_vector(b)
    keys = set(va) | set(vb)
    shared = sum(min(va[k], vb[k]) for k in keys)
    return 1.0 - shared / max(1, sum(max(va[k], vb[k]) for k in keys))


def structure_distance(a: dict, b: dict) -> float:
    def norm(value) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", str(value or "").lower())) - STOP

    diffs = []
    for field in STRUCTURE_FIELDS:
        x, y = norm(a.get(field)), norm(b.get(field))
        diffs.append(1.0 if not x or not y else 1.0 - len(x & y) / len(x | y))
    return sum(diffs) / len(diffs)


def distance(a: dict, b: dict) -> dict:
    m, s = mechanic_distance(a, b), structure_distance(a, b)
    return {"distance": round(0.6 * m + 0.4 * s, 4), "mechanic": round(m, 4), "structure": round(s, 4)}


def load_descriptors(path: Path) -> dict[str, dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {row["tree_id"]: row for row in rows}


def rank(meta: dict, descriptors: dict[str, dict], exclude: set[str] = frozenset()) -> list[dict]:
    ranked = [{"tree_id": tid, "version_id": row.get("version_id"), **distance(meta, row)} for tid, row in descriptors.items() if tid not in exclude]
    return sorted(ranked, key=lambda r: (r["distance"], r["tree_id"]))


# ── Ledger ───────────────────────────────────────────────────────────────────


def log_event(event: dict) -> dict:
    record = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **event}
    with LEDGER.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")
    return record


def recent_samples(limit: int = 10) -> list[str]:
    if not LEDGER.exists():
        return []
    ids = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("event") in ("pair", "anchor"):
            ids += row.get("tree_ids", [])
    return ids[-limit:]


# ── Commands ─────────────────────────────────────────────────────────────────


def cmd_status(args) -> int:
    pool = pool_of(fetch_pool(args.api_url))
    done = sum(improved(t) for t in pool)
    share = done / max(1, len(pool))
    by_family = Counter(t["family"] for t in pool)
    growth = min(GENERATION_SIZE, math.ceil(0.20 * len(pool)))
    print(json.dumps({
        "pool": len(pool),
        "improved": done,
        "improved_share": round(share, 3),
        "families": dict(by_family),
        "growth_due": share >= GROWTH_THRESHOLD,
        "growth_rule": f"grow when >= {GROWTH_THRESHOLD:.0%} of the pool is improved (or on request); a generation is {growth} seeds",
        "least_improved_tier": sorted(t["treeId"] for t in pool if not improved(t))[:40],
    }, indent=1))
    return 0


def cmd_nearest(args) -> int:
    meta = json.loads(Path(args.metadata).read_text(encoding="utf-8"))
    ranked = rank(meta, load_descriptors(args.descriptors))
    print(json.dumps(ranked[: args.k], indent=1))
    return 0


def cmd_anchor(args) -> int:
    meta = json.loads(Path(args.metadata).read_text(encoding="utf-8"))
    ranked = rank(meta, load_descriptors(args.descriptors))
    nearest = ranked[: args.k]
    rng = random.Random(args.seed) if args.seed is not None else secrets.SystemRandom()
    anchor = rng.choice(nearest)
    result = {
        "event": "anchor",
        "mode": "new-seed",
        "game_id": args.game,
        "seed_version_id": args.version,
        "anchor_tree_id": anchor["tree_id"],
        "anchor_version_id": anchor["version_id"],
        "tree_ids": [args.game, anchor["tree_id"]],
        "rule": f"uniform over the {len(nearest)} nearest pool games; only the new game moves",
        "nearest": nearest,
    }
    print(json.dumps(result, indent=1))
    if args.record:
        log_event(result)
    return 0


def cmd_pair(args) -> int:
    descriptors = load_descriptors(args.descriptors)
    pool = [t for t in pool_of(fetch_pool(args.api_url)) if t["treeId"] in descriptors]
    counts = {t["treeId"]: int(t.get("versionCount") or 1) for t in pool}
    low = min(counts.values())
    tier = [tid for tid, c in counts.items() if c == low]
    recent = set(recent_samples())
    rng = random.Random(args.seed) if args.seed is not None else secrets.SystemRandom()
    first = rng.choice([t for t in tier if t not in recent] or tier)
    partners = [t for t in tier if t != first]
    if not partners:
        higher = sorted({c for tid, c in counts.items() if c > low})
        partners = [tid for tid, c in counts.items() if higher and c == higher[0]]
    ranked = sorted(
        ({"tree_id": t, **distance(descriptors[first], descriptors[t])} for t in (p for p in partners if p not in recent) or partners),
        key=lambda r: (-r["distance"], r["tree_id"]),
    )
    far = ranked[: max(1, math.ceil(len(ranked) * 0.20))]
    second = rng.choice(far)
    result = {"event": "pair", "mode": "normal", "tree_ids": [first, second["tree_id"]], "tier_version_count": low,
              "tier_size": len(tier), "farthest_20_percent": far}
    print(json.dumps(result, indent=1))
    if args.record:
        log_event(result)
    return 0


def cmd_draw(args) -> int:
    """Codex's v3 draw: three candidates without replacement, weight 1/(1 + adoptions + draws),
    counting the registry's history plus every v4 draw and adoption in the ledger."""
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    drawn, adopted = Counter(), Counter()
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("event") == "mechanic-draw":
                drawn.update(row.get("candidates", []))
            elif row.get("event") == "mechanic-decision" and row.get("adopted"):
                adopted[row["adopted"]] += 1
    pool = {m["id"]: 1.0 / (1 + m.get("adoption_count", 0) + adopted[m["id"]] + m.get("draw_count", 0) + drawn[m["id"]]) for m in registry["mechanics"]}
    rng = random.Random(args.seed) if args.seed is not None else secrets.SystemRandom()
    picks = []
    for _ in range(min(args.k, len(pool))):
        ids, weights = zip(*sorted(pool.items()))
        choice = rng.choices(ids, weights=weights)[0]
        picks.append(choice)
        pool.pop(choice)
    by_id = {m["id"]: m for m in registry["mechanics"]}
    result = {"event": "mechanic-draw", "game_id": args.game, "candidates": picks,
              "families": [by_id[i]["family"] for i in picks], "rule": "adopt at most one; record why each is rejected"}
    print(json.dumps({**result, "definitions": {i: {"definition": by_id[i]["definition"], "portable_form": by_id[i]["portable_form"]} for i in picks}}, indent=1))
    if args.record:
        log_event(result)
    return 0


STEP_PROFILES = {"seed": "seed", "glowup": "glowup", "playability": "glowup"}
# Publishing names its target explicitly: the publish CLI falls back to production's token.
TARGETS = {"local": "http://127.0.0.1:8090", "production": "https://arc3.sonpham.net"}
STEP_PREFIX = {"seed": "Seed:", "glowup": "Glow-up:", "playability": "Playability:"}


def cmd_publish(args) -> int:
    """One loop step, published: the vetting profile is the step's, the reason names the
    step, and the ledger records the version id. Seeds get the loop's family; later steps
    are revisions of their parent."""
    folder = Path(args.dir)
    source, trace = folder / f"{args.game}.py", folder / f"{args.game}.trace.json"
    profile = STEP_PROFILES[args.step]
    if not args.reason.startswith(STEP_PREFIX[args.step]):
        raise SystemExit(f"a {args.step} reason starts with '{STEP_PREFIX[args.step]}'")
    if args.step != "seed" and not args.parent:
        raise SystemExit(f"a {args.step} version needs --parent (the version it improves)")
    report_path = folder / f"vet.{args.step}.json"
    vet = subprocess.run([sys.executable, str(ROOT / "scripts" / "vet_game.py"), "--source", str(source), "--trace", str(trace),
                          "--profile", profile, "--out", str(report_path), "--strips", str(folder / "strips"),
                          "--time-budget", str(args.time_budget)], capture_output=True, text=True)
    print(vet.stdout.strip().splitlines()[-1] if vet.stdout.strip() else vet.stderr.strip())
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    if vet.returncode != 0 or report.get("verdict") != "pass":
        log_event({"event": "vet", "step": args.step, "game_id": args.game, "verdict": "fail",
                   "failed": sorted(k for k, c in report.get("checks", {}).items() if c["status"] == "fail")})
        raise SystemExit(f"{args.game}: vet failed; nothing published")
    api_url = TARGETS[args.target]
    command = [sys.executable, str(ROOT / "scripts" / "publish_game_versions.py"), "--api-url", api_url, "publish",
               "--game", args.game, "--source", str(source), "--driver", args.driver, "--model", args.model,
               "--reason", args.reason, "--vet-report", str(report_path)]
    if args.step == "seed":
        command += ["--family", args.family]
    else:
        command += ["--kind", "revision", "--parent", args.parent]
    for idea in args.idea or []:
        command += ["--idea", idea]
    if args.details_file:
        command += ["--details", Path(args.details_file).read_text(encoding="utf-8")[:20000]]
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit(f"publish failed: {done.stderr.strip()[-600:] or done.stdout.strip()[-600:]}")
    text = done.stdout
    result = json.loads(text[text.rindex("{", 0, text.rindex('"status"')):])
    record = log_event({"event": "publish", "step": args.step, "game_id": args.game, "version_id": result["versionId"],
                        "parent": args.parent, "ideas": args.idea or [], "target": args.target,
                        "status": result.get("status"), "vet_warnings": report.get("warnings", [])})
    print(json.dumps(record))
    return 0


def cmd_log(args) -> int:
    event = json.loads(args.json)
    if "event" not in event:
        raise SystemExit("the JSON needs an 'event' field")
    print(json.dumps(log_event(event)))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--api-url", default="https://arc3.sonpham.net")
    parser.add_argument("--descriptors", type=Path, help="pool descriptors JSON (private run directory)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    near = sub.add_parser("nearest")
    near.add_argument("--metadata", required=True)
    near.add_argument("-k", type=int, default=8)
    anchor = sub.add_parser("anchor")
    anchor.add_argument("--game", required=True)
    anchor.add_argument("--version", help="the published seed version id")
    anchor.add_argument("--metadata", required=True)
    anchor.add_argument("-k", type=int, default=5)
    anchor.add_argument("--seed", type=int)
    anchor.add_argument("--record", action="store_true")
    pair = sub.add_parser("pair")
    pair.add_argument("--seed", type=int)
    pair.add_argument("--record", action="store_true")
    draw = sub.add_parser("draw")
    draw.add_argument("--game", required=True)
    draw.add_argument("-k", type=int, default=3)
    draw.add_argument("--seed", type=int)
    draw.add_argument("--record", action="store_true")
    pub = sub.add_parser("publish")
    pub.add_argument("--game", required=True)
    pub.add_argument("--step", required=True, choices=sorted(STEP_PROFILES))
    pub.add_argument("--target", required=True, choices=sorted(TARGETS), help="local dev stack or production; no default on purpose")
    pub.add_argument("--dir", required=True, help="folder holding <game>.py and <game>.trace.json")
    pub.add_argument("--reason", required=True)
    pub.add_argument("--parent")
    pub.add_argument("--idea", action="append")
    pub.add_argument("--details-file")
    pub.add_argument("--family", default="evolution")
    pub.add_argument("--driver", default="claude", choices=("gpt", "claude", "human", "other"))
    pub.add_argument("--model", default="Claude Opus 5")
    pub.add_argument("--time-budget", type=float, default=180.0)
    log = sub.add_parser("log")
    log.add_argument("json")
    args = parser.parse_args(argv)
    if args.command in ("nearest", "anchor", "pair") and not args.descriptors:
        raise SystemExit("--descriptors is required (the private pool descriptors file)")
    commands = {"status": cmd_status, "nearest": cmd_nearest, "anchor": cmd_anchor, "pair": cmd_pair, "draw": cmd_draw,
                "publish": cmd_publish, "log": cmd_log}
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())

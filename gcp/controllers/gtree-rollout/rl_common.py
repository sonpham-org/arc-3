"""RL rollout server: what the picker and the learner share (master files, node stats, the coach's modes).

Author: Claude Opus 5.5 (3-Oct-2026, Son: "take advantage of the high throughput in the 10 lanes to do sampled
rollouts off policy").

Master files (gtree-ingest's format, one per play or per rollout try):
  <store>/rollouts/<run>/<game>_p<pass>.jsonl.gz                  seed plays (ingest.py)
  <store>/rollouts/gtr-<campaign>/<game>_p<pass>.<job>.k<k>.jsonl.gz   rollout tries (runner/rl_host_sync.py)
typed rows: kind = rollout | step | trace | screen | node (| report, ignored). Only rollout + step rows are read here.
<store> is gs://cellens-ai-artifacts/arc3-gtree/v1 or a local directory with the same layout (tests). GCS objects are
cached under a local directory and downloaded once (name + size), so a loop on this PC's slow network only fetches
what is new.
"""
from __future__ import annotations

import gzip
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
INGEST = HERE.parent / "gtree-ingest"
COACH_DIR = Path(os.environ.get("ARC3_COACH_DIR", r"D:\codex-work\daniel-base-20261001\variants\coach"))
for _p in (INGEST, COACH_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import arc3_coach as coach  # noqa: E402
from gtree_store import Store, gcs_download, gcs_list  # noqa: E402

MODES = list(coach.MODES)
FENCED = frozenset({"lf52", "tn36", "re86", "dc22", "su15", "as66"})
STORE = "gs://cellens-ai-artifacts/arc3-gtree/v1"
SEED_RUNS = ("daniel-hicache-sbt06-b-1003", "daniel-hicache-sbt06-c-1003", "daniel-hicache-sbt06-d-1003",
             "daniel-hicache-sbt06-e-1003")
SEED_SOURCES = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"   # <run>/working/{artifacts/,}<gid>_p<ps>_*
BAD_STOPS = frozenset({"deadline", "diverged", "aborted", "no_origin", "forked_parent"})


def campaign_run(campaign: str) -> str:
    return f"gtr-{campaign}"


# ------------------------------------------------------------------------------------------------ master files
def sync_masters(store_root: str, runs: Iterable[str], cache: Path) -> list[Path]:
    """Every master file of these runs, as local paths (GCS objects downloaded once into cache/<run>/)."""
    out: list[Path] = []
    for run in runs:
        if not store_root.startswith("gs://"):
            out += sorted((Path(store_root) / "rollouts" / run).glob("*.jsonl.gz"))
            continue
        items, _ = gcs_list(f"{store_root.rstrip('/')}/rollouts/{run}/")
        bucket = store_root[5:].split("/", 1)[0]
        for it in items:
            if not it["name"].endswith(".jsonl.gz"):
                continue
            dest = cache / run / it["name"].rsplit("/", 1)[-1]
            if not dest.exists() or dest.stat().st_size != int(it["size"]):
                gcs_download(f"gs://{bucket}/{it['name']}", dest)
            out.append(dest)
    return out


def load_state_index(store_root: str, cache: Path) -> dict[tuple[str, int], dict]:
    """(rollout id, step seq) -> the state snapshot that restores that step: state/index/<run>/<file>.jsonl lines
    written by runner/rl_host_sync.py from each try's state_refs.jsonl (the origin snapshot of a replayed seed node
    is listed under the seed play's own id and seq, so the next restore of that node needs no replay)."""
    out: dict[tuple[str, int], dict] = {}
    files: list[Path] = []
    if not store_root.startswith("gs://"):
        files = sorted((Path(store_root) / "state" / "index").rglob("*.jsonl"))
    else:
        items, _ = gcs_list(f"{store_root.rstrip('/')}/state/index/")
        bucket = store_root[5:].split("/", 1)[0]
        prefix = store_root[5:].split("/", 1)[1].rstrip("/") + "/state/index/"
        for it in items:
            dest = cache / "state-index" / it["name"][len(prefix):]
            if not dest.exists() or dest.stat().st_size != int(it["size"]):
                gcs_download(f"gs://{bucket}/{it['name']}", dest)
            files.append(dest)
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                x = json.loads(line)
                out.setdefault((x["rollout_id"], int(x["seq"])), x)
    return out


def read_master(path: Path) -> dict:
    """{rollout, steps} of one master file (traces, screens, nodes skipped)."""
    p = {"rollout": None, "steps": [], "path": str(path)}
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if '"kind":"step"' not in line[:20] and '"kind":"rollout"' not in line[:20] \
                    and '"kind": "step"' not in line[:20] and '"kind": "rollout"' not in line[:20]:
                continue
            d = json.loads(line)
            kind = d.pop("kind")
            if kind == "rollout":
                p["rollout"] = d
            elif kind == "step":
                p["steps"].append(d)
    return p


def load_plays(paths: Iterable[Path], *, drop_bad_stops: bool = True) -> list[dict]:
    """Plays from master files; fenced games never; rollout tries that ended without a fair outcome (deadline,
    divergence, abort) dropped: their 'not cleared' is censoring, not a result."""
    plays = []
    for p in paths:
        play = read_master(Path(p))
        r = play["rollout"]
        if not r or r.get("game") in FENCED:
            continue
        stop = (r.get("result") or {}).get("stop_reason")
        if drop_bad_stops and r.get("origin_kind") not in (None, "start") and stop in BAD_STOPS:
            continue
        plays.append(play)
    return plays


def is_rollout(play: dict) -> bool:
    return (play["rollout"] or {}).get("origin_kind") not in (None, "start")


# ------------------------------------------------------------------------------------------------ node stats
def level_moves(s: dict) -> int | None:
    """Moves the level took in the step's play: moves already spent + moves from the step to the clear."""
    o = s.get("outcome") or {}
    if not (o.get("cleared_level") and o.get("moves_to_clear") is not None):
        return None
    return int(s.get("moves") or 0) + int(o["moves_to_clear"])


class NodeStats:
    """Per t1 node: visits, per-action samples, clears and moves to clear (every play: seed and rollouts)."""

    def __init__(self, plays: list[dict]):
        self.n = defaultdict(Counter)                 # n1 -> action -> samples
        self.clears = defaultdict(Counter)            # n1 -> action -> cleared
        self.mtc = defaultdict(lambda: defaultdict(list))   # n1 -> action -> [moves_to_clear]
        self.t5 = defaultdict(Counter)                # n5 -> action -> samples (the restart grid)
        self.best_level: dict[tuple[str, int], int] = {}     # (game, level) -> fewest moves any play took
        for play in plays:
            for s in play["steps"]:
                a = s.get("action") or "stock"
                self.n[s["n1"]][a] += 1
                self.t5[s.get("n5")][a] += 1
                o = s.get("outcome") or {}
                if o.get("cleared_level") and o.get("moves_to_clear") is not None:
                    self.clears[s["n1"]][a] += 1
                    self.mtc[s["n1"]][a].append(int(o["moves_to_clear"]))
                lm = level_moves(s)
                if lm is not None:
                    key = (s["game"], int(s["level"]))
                    self.best_level[key] = min(self.best_level.get(key, lm), lm)

    def visits(self, n1: str) -> int:
        return sum(self.n[n1].values())

    def clear_rate(self, n1: str) -> float:
        """Clear rate with a uniform prior: (clears + 1) / (visits + 2)."""
        return (sum(self.clears[n1].values()) + 1) / (self.visits(n1) + 2)

    def best_from(self, n1: str) -> int | None:
        vals = [m for v in self.mtc[n1].values() for m in v]
        return min(vals) if vals else None

    def uncertainty(self, n1: str) -> float:
        p = self.clear_rate(n1)
        return 1.0 - abs(2 * p - 1) + 1.0 / math.sqrt(self.visits(n1) + 1)

    def table(self, n1: str) -> dict[str, dict]:
        """Per action at a node: samples, clear rate, mean moves to clear."""
        out = {}
        for a, k in sorted(self.n[n1].items(), key=lambda x: -x[1]):
            m = self.mtc[n1][a]
            out[a] = {"n": k, "clear": round(self.clears[n1][a] / k, 2) if k else None,
                      "moves": round(sum(m) / len(m), 1) if m else None}
        return out


def policy_doc(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path[1:] if path.startswith("@") else path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def mode_dist(pol: dict, feats: dict) -> dict[str, float]:
    """The policy's mode distribution at a step's features ({} without a policy)."""
    return coach.policy_mode_dist(pol, feats or {})


def write_json(store: Store, name: str, obj, once: bool = False) -> None:
    store.put(name, json.dumps(obj, indent=1).encode("utf-8"), once=once, content_type="application/json")

"""Data files for the fork review page (plan §6: people pick the best continuation from one moment).

For every moment of a try campaign that has finished tries, one JSON file with:
- the path to the fork: every frame of the source run from the game start to the fork (64x64 boards,
  delta-encoded), action names, level per action, and a short excerpt of the model's thinking per turn;
- the candidates from the fork: each valid try's frames, actions, outcome (cleared / actions / reward) and thinking
  excerpts, plus the source run's own continuation (what the model did the first time, kind "source").
Fenced games (the test five and as66) are never exported: their labels must not reach training.

Frame strings: "F<w>,<h>:<hex digit per cell>" (full) or "D<pos 3 hex><color 1 hex>..." (cells changed since the
previous frame of the same list; a candidate's first frame is a delta from the fork frame).

Writes <out>/data/index.json and <out>/data/<moment>.json.
Usage:
  python review_export.py --campaign rl-1002a --out review/          # tries campaign on GCS
  python review_export.py --sample-events run_events.jsonl --fork-action 40 --game ab12 --out review/   # layout check
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rl_tree as rt  # noqa: E402

HEX = "0123456789abcdef"
THINK_CHARS = 700
SOURCE_MAX_ACTIONS = 80
TRIES_ROOT = "gs://cellens-ai-artifacts/arc3-rl/tries"
PALETTE = ["#FFFFFF", "#CCCCCC", "#999999", "#666666", "#333333", "#000000", "#E53AA3", "#FF7BCC",
           "#F93C31", "#1E93FF", "#88D8F1", "#FFDC00", "#FF851B", "#921231", "#4FCC30", "#A356D6"]
_SECTION = re.compile(r"^\[([A-Z][A-Z _]+)(?::[^\]\n]*)?\]\s*$", re.M)     # [THINKING], [TOOL CALL: python], ...


# ------------------------------------------------------------------------------------------------ io
def _gcloud(*args: str, binary: bool = False):
    p = subprocess.run(["gcloud", "storage", *args], capture_output=True, text=not binary)
    return p.stdout if p.returncode == 0 else None


def read_bytes(uri: str) -> bytes | None:
    if uri.startswith("gs://"):
        return _gcloud("cat", uri, binary=True)
    p = Path(uri)
    return p.read_bytes() if p.exists() else None


def read_jsonl(uri: str) -> list[dict]:
    raw = read_bytes(uri)
    if raw is None:
        return []
    if uri.endswith(".gz"):
        raw = gzip.decompress(raw)
    return [json.loads(l) for l in raw.decode("utf-8").splitlines() if l.strip()]


def list_names(prefix: str) -> list[str]:
    if prefix.startswith("gs://"):
        out = _gcloud("ls", prefix.rstrip("/") + "/") or ""
        return sorted(Path(l.strip()).name for l in out.splitlines() if l.strip() and not l.strip().endswith("/"))
    d = Path(prefix)
    return sorted(p.name for p in d.iterdir()) if d.is_dir() else []


def source_events_uri(transcript_uri: str) -> str:
    """runs/transcripts/<stem>.txt -> runs/artifacts/<stem>_events.jsonl (our harness layout)."""
    head, _, name = transcript_uri.rpartition("/transcripts/")
    return f"{head}/artifacts/{Path(name).stem}_events.jsonl"


# ------------------------------------------------------------------------------------------------ encoding
def _flat(board: list[list[int]]) -> list[int]:
    return [int(c) & 15 for row in board for c in row]


def encode_frames(boards: list, prev_board: list | None = None) -> list[str]:
    out = []
    prev = _flat(prev_board) if prev_board is not None else None
    prev_dims = (len(prev_board[0]), len(prev_board)) if prev_board else None
    for b in boards:
        flat = _flat(b)
        dims = (len(b[0]), len(b))
        if prev is None or dims != prev_dims or len(flat) > 4096:
            out.append(f"F{dims[0]},{dims[1]}:" + "".join(HEX[c] for c in flat))
        else:
            diff = [(i, c) for i, (p, c) in enumerate(zip(prev, flat)) if p != c]
            if len(diff) * 4 >= len(flat):
                out.append(f"F{dims[0]},{dims[1]}:" + "".join(HEX[c] for c in flat))
            else:
                out.append("D" + "".join(f"{i:03x}{HEX[c]}" for i, c in diff))
        prev, prev_dims = flat, dims
    return out


def decode_frames(frames: list[str], prev_board: list | None = None) -> list[list[list[int]]]:
    """Inverse of encode_frames (tests)."""
    out = []
    cur = _flat(prev_board) if prev_board is not None else None
    w = len(prev_board[0]) if prev_board else 0
    for f in frames:
        if f[0] == "F":
            dims, cells = f[1:].split(":", 1)
            w, _h = (int(x) for x in dims.split(","))
            cur = [int(ch, 16) for ch in cells]
        else:
            cur = list(cur)
            body = f[1:]
            for k in range(0, len(body), 4):
                cur[int(body[k:k + 3], 16)] = int(body[k + 3], 16)
        out.append([cur[r * w:(r + 1) * w] for r in range(len(cur) // w)])
    return out


# ------------------------------------------------------------------------------------------------ turns
def thinking(transcript: str) -> list[str]:
    """The [THINKING] sections of one turn's transcript, in order."""
    marks = list(_SECTION.finditer(transcript or ""))
    out = []
    for i, m in enumerate(marks):
        if m.group(1).strip() == "THINKING":
            end = marks[i + 1].start() if i + 1 < len(marks) else len(transcript)
            text = transcript[m.end():end].strip()
            if text:
                out.append(text)
    return out


def _cut(text: str, n: int = THINK_CHARS) -> str:
    text = re.sub(r"\s+\n", "\n", text).strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def turn_notes(events: list[dict]) -> dict[int, dict]:
    """analysis_step -> {"first": first thinking excerpt, "last": last one (if different)}."""
    notes = {}
    for ev in events:
        if ev.get("type") != "analysis" or ev.get("analysis_step") is None:
            continue
        th = thinking(ev.get("transcript") or "")
        if not th:
            continue
        note = {"first": _cut(th[0])}
        if len(th) > 1:
            note["last"] = _cut(th[-1], 400)
        notes[int(ev["analysis_step"])] = note
    return notes


def path_part(events: list[dict], lo: int, hi: int, prev_board=None, stop_at_level_clear: bool = False) -> dict:
    """Actions lo..hi (inclusive) of an events log: encoded frames, names, levels, turns, and level clears."""
    acts = [e for e in events if e.get("type") == "action" and lo <= int(e.get("action_num") or 0) <= hi]
    if stop_at_level_clear:
        cut = next((i for i, e in enumerate(acts) if e.get("level_completed")), None)
        if cut is not None:
            acts = acts[: cut + 1]
    notes = turn_notes(events)
    steps = [int(e.get("analysis_step") or 0) for e in acts]
    turns = []
    for i, st in enumerate(steps):
        if i == 0 or st != steps[i - 1]:
            turns.append({"at": i, "step": st, **notes.get(st, {})})
    return {
        "frames": encode_frames([e["board"] for e in acts], prev_board),
        "names": [str(e.get("action_display") or e.get("action_name") or "") for e in acts],
        "levels": [int(e.get("level") or 0) for e in acts],
        "clears": [i for i, e in enumerate(acts) if e.get("level_completed")],
        "game_over": any(bool(e.get("game_over")) for e in acts),
        "turns": turns,
        "first_action": int(acts[0]["action_num"]) if acts else None,
        "last_board": acts[-1]["board"] if acts else prev_board,
    }


# ------------------------------------------------------------------------------------------------ moments
def build_moment(job: dict, source_events: list[dict], tries: list[tuple[dict, list[dict]]],
                 min_candidates: int = 2) -> dict | None:
    """job = the campaign's moment job; tries = [(result record, that try's events)]."""
    game = job["game_id"]
    if rt.is_fenced(game):
        return None
    mom = job.get("moment") or {}
    fork = int(job.get("action_at_start") or mom.get("action_at_start") or 0)
    level = int(job.get("level") or mom.get("level") or 1)
    init = next((e for e in source_events if e.get("type") == "initial"), None)
    if init is None or fork < 1:
        return None
    prefix = path_part(source_events, 1, fork - 1, prev_board=None)
    first = encode_frames([init["board"]])
    fork_board = prefix.pop("last_board") or init["board"]
    prefix["frames"] = first + prefix["frames"]
    prefix["names"] = ["START"] + prefix["names"]
    prefix["levels"] = [1] + prefix["levels"]
    prefix["clears"] = [i + 1 for i in prefix["clears"]]
    prefix["turns"] = [dict(t, at=t["at"] + 1) for t in prefix["turns"]]
    level_start = max([0] + prefix["clears"])     # the frame after a clearing action already shows the next level
    human = job.get("human") or []
    cands = []
    src = path_part(source_events, fork, fork + SOURCE_MAX_ACTIONS - 1, prev_board=fork_board, stop_at_level_clear=True)
    src.pop("last_board", None)
    if src["frames"]:
        cands.append({"id": "source", "kind": "source", "cleared": bool(src["clears"]), "actions": len(src["names"]),
                      **src})
    for res, evs in tries:
        if not (res.get("outcome") or {}).get("valid"):
            continue
        sw = int((res.get("switch") or {}).get("action_count") or 0)
        part = path_part(evs, sw + 1, sw + 10_000, prev_board=fork_board, stop_at_level_clear=True)
        part.pop("last_board", None)
        doc = res.get("try_doc") or {}
        cands.append({"id": res["try_id"], "kind": "try", "cleared": bool(res.get("cleared")),
                      "actions": len(part["names"]), "reward": doc.get("reward"), "stop": res.get("stop_reason"),
                      **part})
    if len(cands) < min_candidates:
        return None
    mid = job["moment_id"]
    return {"id": safe_id(mid), "moment_id": mid, "game": game, "level": level, "fork_action": fork,
            "human": human[level - 1] if len(human) >= level else None, "palette": PALETTE,
            "prefix": prefix, "level_start": level_start, "candidates": cands}


def safe_id(mid: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", mid)[:120]


def index_row(m: dict) -> dict:
    tries = [c for c in m["candidates"] if c["kind"] == "try"]
    cleared = [c["actions"] for c in tries if c["cleared"]]
    return {"id": m["id"], "game": m["game"], "level": m["level"], "fork_action": m["fork_action"],
            "human": m["human"], "tries": len(tries), "cleared": len(cleared),
            "best": min(cleared) if cleared else None, "source_cleared": any(
                c["cleared"] for c in m["candidates"] if c["kind"] == "source")}


def write(out: Path, moments: list[dict]) -> None:
    d = out / "data"
    d.mkdir(parents=True, exist_ok=True)
    rows = []
    for m in moments:
        (d / f"{m['id']}.json").write_text(json.dumps(m, separators=(",", ":")), encoding="utf-8")
        rows.append(index_row(m))
    (d / "index.json").write_text(json.dumps({"moments": rows}, separators=(",", ":")), encoding="utf-8")
    size = sum(p.stat().st_size for p in d.glob("*.json"))
    print(f"{len(rows)} moments -> {d} ({size / 1e6:.2f} MB)")


# ------------------------------------------------------------------------------------------------ main
def from_campaign(campaign: str, root: str = "") -> list[dict]:
    root = (root or f"{TRIES_ROOT}/{campaign}").rstrip("/")
    jobs = {}
    for name in list_names(f"{root}/jobs"):
        raw = read_bytes(f"{root}/jobs/{name}")
        if raw:
            j = json.loads(raw)
            jobs[j["moment_id"]] = j
    by_moment: dict[str, list[dict]] = {}
    for name in list_names(f"{root}/results"):
        if name.endswith("._error.json") or not name.endswith(".json"):
            continue
        r = json.loads(read_bytes(f"{root}/results/{name}") or b"{}")
        if r.get("moment_id"):
            by_moment.setdefault(r["moment_id"], []).append(r)
    moments = []
    for mid, results in sorted(by_moment.items()):
        job = jobs.get(mid)
        if job is None or rt.is_fenced(job["game_id"]):
            continue
        src = read_jsonl(source_events_uri(job["transcript_uri"]))
        tries = [(r, read_jsonl(f"{root}/events/{r['try_id']}.jsonl.gz")) for r in sorted(results, key=lambda r: r["try_id"])]
        m = build_moment(job, src, tries)
        if m:
            moments.append(m)
            print(f"{mid}: {len(m['candidates'])} candidates, prefix {len(m['prefix']['names'])} frames")
    return moments


def sample(events_path: str, fork_action: int, game: str) -> list[dict]:
    """Layout check before any try exists: one moment from a finished run, whose only candidate is the run's own
    continuation (local preview only; reviewers get campaign moments)."""
    events = read_jsonl(events_path)
    acts = [e for e in events if e.get("type") == "action"]
    level = next((int(e["level"]) for e in acts if int(e["action_num"]) == fork_action), 1)
    job = {"moment_id": f"sample:{game}:{fork_action}", "game_id": game, "action_at_start": fork_action,
           "level": level, "moment": {}, "human": []}
    m = build_moment(job, events, [], min_candidates=1)
    return [m] if m else []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign", default="")
    ap.add_argument("--root", default="", help="a local or gs:// campaign root instead of the default")
    ap.add_argument("--sample-events", default="")
    ap.add_argument("--fork-action", type=int, default=0)
    ap.add_argument("--game", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.sample_events:
        moments = sample(a.sample_events, a.fork_action, a.game)
    else:
        moments = from_campaign(a.campaign, a.root)
    write(Path(a.out), moments)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

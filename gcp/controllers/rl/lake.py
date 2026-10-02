"""ARC-3 trace lake: canonical episodes, content-addressed blobs, Firestore index docs
(design: docs/plans/2026-10-01-arc3-trace-lake.md).

An EPISODE is one game played (a scored run's game, an RL try, a replay, a human or teacher path), stored as gzipped
JSONL under gs://cellens-ai-artifacts/arc3-lake/v1/episodes/<source>/<yyyymmdd>/<episode_id>.jsonl.gz:
  header  provenance: source, game + version, harness, policy, parent (forks), teacher, fenced
  call    one per model call: turn, request index, action number, `msgs` = the messages appended since the previous
          call (or the full list where the context was rebuilt: reset=true), the reply when the next call does not
          carry it, usage, finish
  action  one per game action (from the events log): turn, action, level, frame blob, level/game-over flags
  footer  per level: cleared, actions, human baseline, level score; game score
Images inside messages and frames are stored once as blobs (sha256 of their exact bytes), so the level-start frame
shared by every run and the prefix shared by every fork cost nothing extra. `call_messages` rebuilds the exact
message list of every call (tested byte-for-byte on a real request log).

Writers stage files under a local directory mirroring the lake layout and push it with one `gcloud storage rsync`.
Index docs (lake_episodes, lake_levels) are small dicts for Firestore (`firestore_batch_write`).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

import rl_reward as rr

SCHEMA = "lake-1"
LAKE_ROOT = "gs://cellens-ai-artifacts/arc3-lake/v1"
SOURCES = ("scored_run", "rl_try", "replay", "human", "teacher")
FENCED = frozenset({"lf52", "tn36", "re86", "dc22", "su15", "as66"})


# ------------------------------------------------------------------------------------------------ ids
def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def policy_id(desc: dict) -> str:
    """Model build identity: base checkpoint, expert cut, repair net, draft, adapter, sampling."""
    keys = ("base", "prune", "corrector", "draft", "adapter", "temperature", "top_p", "top_k")
    return "pol-" + _sha(_canon({k: desc.get(k) for k in keys}))[:16]


def harness_id(desc: dict) -> str:
    """Harness identity: bundle, knob set, render profile (what reproduces the exact prompts)."""
    keys = ("bundle", "knobs", "render_profile")
    return "har-" + _sha(_canon({k: desc.get(k) for k in keys}))[:16]


def episode_id(source: str, *parts: str) -> str:
    if source not in SOURCES:
        raise ValueError(f"source {source!r}")
    clean = [str(p).replace("/", "_").replace(".", "-") for p in parts]
    return ".".join([source] + clean)


def episode_uri(eid: str, source: str, when: float | None = None) -> str:
    day = time.strftime("%Y%m%d", time.gmtime(when or time.time()))
    return f"episodes/{source}/{day}/{eid}.jsonl.gz"


# ------------------------------------------------------------------------------------------------ blobs
class LocalBlobs:
    """Content-addressed blobs under <root>/blobs/<sha[:2]>/<sha>; the bytes are stored exactly as given."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def put(self, data: bytes) -> str:
        sha = _sha(data)
        p = self.root / "blobs" / sha[:2] / sha
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        return sha

    def get(self, sha: str) -> bytes:
        return (self.root / "blobs" / sha[:2] / sha).read_bytes()


def _deflate_msgs(msgs: list[dict], blobs: LocalBlobs) -> list[dict]:
    """Messages with every image data URL replaced by {"blob": sha} (the exact URL string is the blob)."""
    out = []
    for m in msgs:
        c = m.get("content")
        if isinstance(c, list):
            parts = []
            for p in c:
                if isinstance(p, dict) and p.get("type") == "image_url" and isinstance(p.get("image_url"), dict) \
                        and isinstance(p["image_url"].get("url"), str):
                    sha = blobs.put(p["image_url"]["url"].encode("utf-8"))
                    parts.append({**p, "image_url": {**{k: v for k, v in p["image_url"].items() if k != "url"},
                                                     "blob": sha}})
                else:
                    parts.append(p)
            m = {**m, "content": parts}
        out.append(m)
    return out


def _inflate_msgs(msgs: list[dict], get: Callable[[str], bytes]) -> list[dict]:
    out = []
    for m in msgs:
        c = m.get("content")
        if isinstance(c, list):
            parts = []
            for p in c:
                if isinstance(p, dict) and p.get("type") == "image_url" and isinstance(p.get("image_url"), dict) \
                        and "blob" in p["image_url"]:
                    iu = {k: v for k, v in p["image_url"].items() if k != "blob"}
                    iu = {"url": get(p["image_url"]["blob"]).decode("utf-8"), **iu}
                    parts.append({**p, "image_url": iu})
                else:
                    parts.append(p)
            m = {**m, "content": parts}
        out.append(m)
    return out


# ------------------------------------------------------------------------------------------------ write
def _extends(cur: list[dict], prev: list[dict]) -> bool:
    return len(cur) > len(prev) and [_canon(m) for m in cur[:len(prev)]] == [_canon(m) for m in prev]


def episode_lines(header: dict, rows: list[dict], blobs: LocalBlobs, *, events: Iterable[dict] | None = None,
                  human: list[int] | None = None, first_level: int = 1) -> list[dict]:
    """Canonical episode lines from a harness request log (rows with event request/response, in order; our harness
    also logs response_message) and optionally the events log (actions, levels, boards). A try's episode starts
    mid-game: its events are the live part only and first_level is the level it starts on."""
    reqs = []
    for i, r in enumerate(rows):
        if r.get("event") != "request":
            continue
        resp = next((n for n in rows[i + 1:i + 3] if n.get("event") == "response"
                     and n.get("analysis_step") == r.get("analysis_step")
                     and n.get("request_index_within_turn") == r.get("request_index_within_turn")), None)
        reqs.append((r, resp))
    lines: list[dict] = [dict(header, kind="header", schema=SCHEMA)]
    prev: list[dict] | None = None
    for idx, (r, resp) in enumerate(reqs):
        msgs = r.get("messages") or []
        reset = prev is None or not _extends(msgs, prev)
        delta = msgs if reset else msgs[len(prev):]
        nxt = reqs[idx + 1][0].get("messages") if idx + 1 < len(reqs) else None
        reply_in_next = bool(nxt is not None and _extends(nxt, msgs) and nxt[len(msgs)].get("role") == "assistant")
        reply = None
        if not reply_in_next and resp is not None and isinstance(resp.get("response_message"), dict):
            reply = resp["response_message"]
        lines.append({
            "kind": "call", "i": idx, "turn": r.get("analysis_step"), "req": r.get("request_index_within_turn"),
            "action": r.get("action"), "reset": reset, "msgs": _deflate_msgs(delta, blobs),
            "tools": r.get("tools") if reset else None, "chat_template_kwargs": r.get("chat_template_kwargs"),
            "reply_in_next": reply_in_next, "reply": reply,
            "usage": (resp or {}).get("usage"), "finish": (resp or {}).get("finish_reason"),
        })
        prev = msgs
    level = int(first_level)
    cleared: dict[int, int] = {}
    evs = [ev for ev in events or [] if ev.get("type") == "action"]
    starts = {level: int(evs[0]["action_num"]) if evs and level > 1 else 1}
    for ev in evs:
        if ev.get("type") != "action":
            continue
        board = ev.get("board")
        frame = blobs.put(_canon(board)) if board is not None else None
        lines.append({"kind": "action", "n": ev.get("action_num"), "turn": ev.get("analysis_step"),
                      "name": ev.get("action_name") or ev.get("action_display"), "level": level, "frame": frame,
                      "changed": ev.get("board_changed"), "level_done": bool(ev.get("level_completed")),
                      "game_over": bool(ev.get("game_over"))})
        if ev.get("level_completed"):
            cleared[level] = int(ev["action_num"])
            level += 1
            starts[level] = int(ev["action_num"]) + 1
    lines.append({"kind": "footer", "levels": level_rows(cleared, starts, human or []), "human": list(human or []),
                  "calls": len(reqs), "actions": sum(1 for l in lines if l["kind"] == "action")})
    return lines


def level_rows(cleared: dict[int, int], starts: dict[int, int], human: list[int]) -> list[dict]:
    out = []
    for k in range(1, len(human) + 1):
        if k in cleared:
            used = cleared[k] - starts[k] + 1
            out.append({"level": k, "cleared": True, "actions": used, "human": human[k - 1],
                        "score": rr.level_score(human[k - 1], used)})
        elif k in starts:
            out.append({"level": k, "cleared": False, "actions": None, "human": human[k - 1], "score": 0.0})
    return out


def write_episode(stage: str | Path, uri: str, lines: list[dict]) -> Path:
    p = Path(stage) / uri
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        for l in lines:
            fh.write(json.dumps(l, ensure_ascii=False) + "\n")
    return p


def read_episode(path: str | Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


# ------------------------------------------------------------------------------------------------ read
def call_messages(lines: list[dict], get: Callable[[str], bytes]) -> Iterator[tuple[dict, list[dict], dict | None]]:
    """(call line, its exact message list, its reply message or None) for every call, rebuilt from deltas."""
    calls = [l for l in lines if l.get("kind") == "call"]
    cur: list[dict] = []
    for i, c in enumerate(calls):
        delta = _inflate_msgs(c["msgs"], get)
        cur = delta if c["reset"] else cur + delta
        if c.get("reply_in_next") and i + 1 < len(calls):
            nd = calls[i + 1]["msgs"]
            reply = _inflate_msgs(nd[:1], get)[0] if nd else None
        else:
            reply = c.get("reply")
        yield c, list(cur), reply


# ------------------------------------------------------------------------------------------------ index docs
def episode_doc(lines: list[dict], uri: str) -> dict:
    h = lines[0]
    f = lines[-1] if lines[-1].get("kind") == "footer" else {}
    lv = f.get("levels") or []
    # the game score needs EVERY level's baseline (weights 1..N), not only the levels this episode reached
    human = list(f.get("human") or [r["human"] for r in lv])
    cleared = sum(r["cleared"] for r in lv)
    acts = [r["actions"] or 0 for r in lv if r["cleared"]]
    gid = (h.get("game") or {}).get("id", "")
    return {
        "id": h["episode_id"], "schema": SCHEMA, "uri": f"{LAKE_ROOT}/{uri}", "source": h.get("source"),
        "game": gid[:4], "game_id": gid, "game_version": (h.get("game") or {}).get("version"),
        "harness_id": (h.get("harness") or {}).get("id"), "policy_id": (h.get("policy") or {}).get("id"),
        "parent": h.get("parent"), "teacher": h.get("teacher", "none"), "fenced": gid[:4].lower() in FENCED,
        "levels_cleared": cleared, "n_levels": len(human), "calls": f.get("calls"), "actions": f.get("actions"),
        "game_score": rr.game_score(cleared, acts, human) if human else None, "created_at": time.time(),
    }


def level_docs(lines: list[dict]) -> list[dict]:
    h = lines[0]
    f = lines[-1] if lines[-1].get("kind") == "footer" else {}
    gid = (h.get("game") or {}).get("id", "")
    return [{"id": f"{h['episode_id']}.L{r['level']}", "episode_id": h["episode_id"], "game": gid[:4],
             "game_id": gid, "level": r["level"], "cleared": r["cleared"], "actions": r["actions"],
             "human": r["human"], "score": r["score"], "harness_id": (h.get("harness") or {}).get("id"),
             "policy_id": (h.get("policy") or {}).get("id"), "source": (h.get("source") or {}).get("kind"),
             "teacher": h.get("teacher", "none"), "fenced": gid[:4].lower() in FENCED}
            for r in f.get("levels") or []]


# ------------------------------------------------------------------------------------------------ push
def rsync_stage(stage: str | Path, dest: str = LAKE_ROOT) -> None:
    subprocess.run(["gcloud", "storage", "rsync", "-r", str(stage), dest], check=True)


def firestore_batch_write(collection: str, docs: list[dict], call: Callable, api: str, token: Callable[[], str],
                          value: Callable[[Any], dict]) -> int:
    """Write docs (each with an "id") in batches of 500 via documents:batchWrite. `call`, `value` and `api` are
    arc3_firestore_scores' REST helpers (_call, _value, API)."""
    from urllib.error import HTTPError
    uniq = list({d["id"]: d for d in docs}.values())       # one write per document per request (Firestore rule)
    if len(uniq) != len(docs):
        print(f"firestore_batch_write: {len(docs) - len(uniq)} duplicate ids in {collection}, last kept", flush=True)
    n = 0
    for i in range(0, len(uniq), 500):
        writes = [{"update": {"name": f"{api.split('/v1/')[1]}/{collection}/{d['id']}",
                              "fields": {k: value(v) for k, v in d.items()}}} for d in uniq[i:i + 500]]
        try:
            call(f"{api}:batchWrite", token(), {"writes": writes}, method="POST")
        except HTTPError as e:
            raise RuntimeError(f"batchWrite {collection} [{i}:{i + len(writes)}]: HTTP {e.code} "
                               f"{e.read().decode(errors='replace')[:800]}") from e
        n += len(writes)
    return n

#!/usr/bin/env python3
"""
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: Exact level-start checkpoints for the Spark runner (Son, #arc-3, 6-Oct 08:33 ET: restart from a point "with
  the context as if it played the game and completed the level up to that point"; if a level was completed several
  times, pick one).
  A checkpoint is written by sample.py the first time a sample starts a turn after a level was completed (or, when
  the sample stops right after a clear, by a dry build of that turn's request). It holds everything the harness reads
  to play the next turn, taken from the live process, not rebuilt:
    request.json.gz   the full chat request body the harness sent (or would send) for that turn, byte for byte as
                      posted: system prompt, every message, board images (base64), tool calls and tool results,
                      sampling settings and chat-template kwargs
    state.pkl.gz      the harness agent's own attributes (conversation history, retained functions = the whole REPL
                      state, since the Python tool runs a fresh subprocess per call seeded only with them, world
                      model, death ledger, pending images, token counters, effort rung ...) and the game session's
                      (history entries = the runtime state the harness reloads every turn, animation record,
                      analysis step)
    actions.json      every engine action from the first RESET, with the harness's automatic flag, so the game is
                      replayed exactly and checked against the saved board hash
    meta.json         game, level, variant, actions to reach, tokens, model id, notebook flags, board hash, source job,
                      lineage (exact only if the sample itself started from RESET or from an exact checkpoint)
  Layout: <home>/checkpoints/<game>/<level>/<variant>-<id>/ and <home>/checkpoints/index.json (rebuilt from the
  meta files; per game, level and variant: every checkpoint plus the chosen one). Choice: exact lineage only, then
  fewest total actions from RESET, then fewest tokens, then oldest. At most KEEP_PER_LEVEL are kept per game, level and
  variant (the best by the same order); the rest are deleted so the folder cannot grow without bound.
SRP/DRY check: Pass - storage, choice and index only; capture and restore hooks live in sample.py, the scheduler in
  server.py. No harness logic here.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import pickle
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

HOME = Path(os.environ.get("ARC3_RUNNER_HOME", Path.home() / "arc3-runner"))
ROOT = Path(os.environ.get("ARC3_RUNNER_CHECKPOINTS", HOME / "checkpoints"))
KEEP_PER_LEVEL = int(os.environ.get("ARC3_RUNNER_CHECKPOINTS_PER_LEVEL", "8"))

# Agent attributes that are this process's wiring or the job's settings, not game memory: never saved or restored.
AGENT_SKIP = {
    "_model", "_timeout", "_api_key", "_tool_steps", "_python_timeout", "_yield_seconds", "_yield_tokens",
    "_max_output_tokens", "_save_request_logs", "_session_runtime_dir", "_step_env_callback",
    "_http_initial_grace_used", "_diag_name", "analyze", "_build_user_prompt", "_harness_template_kwargs",
    # the prompt profile's (prompt_profiles.py): a job sets its own system prompt after restoring, so a checkpoint
    # captured under one profile cannot hand its system prompt to a job running another
    "_system_prompt", "_dedup_turn", "_append_context_message", "_retained_function_context", "_tools",
}
SESSION_KEYS = ("history_entries", "animation_record", "last_engine_action", "analysis_step")
# The Stock settings checkpoints are taken under: what the page sends for Stock (modes.json stock.settings, the 28.94
# and 31.63 notebooks' per-turn values) and what harvest runs play with.
STOCK_SETTINGS = {"temperature": 0.6, "thinking": True, "effort": "default", "thinking_budget": None,
                  "tool_calls": None, "actions": None}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, payload) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str))
    tmp.replace(path)


def _read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return default


def board_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def request_hash(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def capture_state(agent, session) -> tuple[bytes, list[str]]:
    """Pickle the agent's and session's game memory. Returns (bytes, skipped attribute names)."""
    agent_state, skipped = {}, []
    for k, v in vars(agent).items():
        if k in AGENT_SKIP or callable(v) and not isinstance(v, (dict, list)):
            continue
        try:
            agent_state[k] = pickle.dumps(v)
        except Exception:  # noqa: BLE001 - a lock or handle: recorded, never silently lost
            skipped.append(k)
    session_state = {k: pickle.dumps(getattr(session, k)) for k in SESSION_KEYS}
    return pickle.dumps({"agent": agent_state, "session": session_state}), skipped


def restore_state(blob: bytes, agent, session) -> list[str]:
    state = pickle.loads(blob)
    restored = []
    for k, raw in state["agent"].items():
        if k in AGENT_SKIP:
            continue
        setattr(agent, k, pickle.loads(raw))
        restored.append(k)
    for k, raw in state["session"].items():
        setattr(session, k, pickle.loads(raw))
    return restored


def save(*, game: str, game_id: str, level: int, variant: str, request_body: dict, state_blob: bytes,
         skipped: list[str], actions: list[dict], meta: dict) -> Path:
    cid = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    d = ROOT / game / str(level) / f"{variant}-{cid}"
    tmp = d.with_name(d.name + ".partial")
    tmp.mkdir(parents=True)
    with gzip.open(tmp / "request.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(request_body, fh)
    with gzip.open(tmp / "state.pkl.gz", "wb") as fh:
        fh.write(state_blob)
    _write_json(tmp / "actions.json", actions)
    meta = {**meta, "id": f"{variant}-{cid}", "game": game, "game_id": game_id, "level": level, "variant": variant,
            "created": now(), "actions_to_reach": len(actions), "request_sha256": request_hash(request_body),
            "request_messages": len(request_body.get("messages") or []),
            "request_images": sum(1 for m in request_body.get("messages") or [] if isinstance(m.get("content"), list)
                                  for p in m["content"] if isinstance(p, dict) and p.get("type") == "image_url"),
            "skipped_attributes": skipped}
    _write_json(tmp / "meta.json", meta)
    tmp.rename(d)
    prune(game, level, variant)
    rebuild_index()
    return d


def rank(meta: dict) -> tuple:
    return (0 if meta.get("exact_lineage") else 1, int(meta.get("actions_to_reach") or 0),
            int(meta.get("tokens_to_reach") or 0), meta.get("created") or "")


def metas(game: str | None = None) -> list[dict]:
    out = []
    games = [ROOT / game] if game else [p for p in ROOT.iterdir() if p.is_dir()] if ROOT.exists() else []
    for g in games:
        for m in g.glob("*/*/meta.json"):
            meta = _read_json(m)
            if meta:
                meta["path"] = str(m.parent)
                out.append(meta)
    return out


def prune(game: str, level: int, variant: str) -> None:
    rows = sorted((m for m in metas(game) if m["level"] == level and m["variant"] == variant), key=rank)
    for m in rows[KEEP_PER_LEVEL:]:
        shutil.rmtree(m["path"], ignore_errors=True)


def rebuild_index() -> dict:
    groups: dict[tuple, list[dict]] = {}
    for m in metas():
        groups.setdefault((m["game"], m["level"], m["variant"]), []).append(m)
    rows = []
    for (game, level, variant), ms in sorted(groups.items()):
        ms.sort(key=rank)
        best = ms[0]
        exact = [m for m in ms if m.get("exact_lineage")]
        rows.append({
            "game": game, "level": level, "variant": variant, "count": len(ms), "exact_count": len(exact),
            "chosen": ({k: best.get(k) for k in ("id", "actions_to_reach", "tokens_to_reach", "source_job",
                                                    "source_kind", "created", "actions_into_level")}
                       if best.get("exact_lineage") else None),
            "others": [{k: m.get(k) for k in ("id", "actions_to_reach", "tokens_to_reach", "source_job", "exact_lineage")}
                       for m in ms[1:]],
        })
    index = {"kind": "arc3-spark-exact-starts", "built": now(), "rule": "exact lineage, fewest actions from RESET, "
             "then fewest tokens", "levels": rows}
    ROOT.mkdir(parents=True, exist_ok=True)
    _write_json(ROOT / "index.json", index)
    return index


def index() -> dict:
    """The index, rebuilt when any checkpoint is newer than it: two samples saving at the same moment each rebuild
    it and the last rename wins, so a row can go missing until the next save; checking on read closes that gap."""
    path = ROOT / "index.json"
    idx = _read_json(path)
    if idx:
        built = path.stat().st_mtime
        if not any(m.stat().st_mtime > built for m in ROOT.glob("*/*/*/meta.json")):
            return idx
    return rebuild_index()


def chosen(game: str, level: int, variant: str) -> dict | None:
    for row in index().get("levels", []):
        if row["game"] == game and row["level"] == level and row["variant"] == variant and row.get("chosen"):
            d = ROOT / game / str(level) / row["chosen"]["id"]
            meta = _read_json(d / "meta.json")
            if meta:
                meta["path"] = str(d)
                return meta
    return None


def load(path: str | Path) -> dict:
    d = Path(path)
    with gzip.open(d / "request.json.gz", "rt", encoding="utf-8") as fh:
        body = json.load(fh)
    with gzip.open(d / "state.pkl.gz", "rb") as fh:
        blob = fh.read()
    return {"meta": _read_json(d / "meta.json"), "request": body, "state": blob,
            "actions": _read_json(d / "actions.json", [])}


def diff_requests(saved: dict, sent: dict) -> dict:
    """How the request a restored sample sent differs from the saved one. Equal means byte-equal JSON."""
    if request_hash(saved) == request_hash(sent):
        return {"equal": True}
    keys = sorted(k for k in set(saved) | set(sent) if saved.get(k) != sent.get(k))
    sm, tm = saved.get("messages") or [], sent.get("messages") or []
    first = next((i for i in range(min(len(sm), len(tm))) if sm[i] != tm[i]), None)
    context_equal = sm[:-1] == tm[:-1] and len(sm) == len(tm)
    return {"equal": False, "keys_differ": keys, "messages_saved": len(sm), "messages_sent": len(tm),
            "first_message_differs": first, "context_equal_except_last_message": context_equal,
            "t": time.time()}

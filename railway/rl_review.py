"""Trace review for RL: raters compare paths forward from the same point in a game. Plus the RL page's data.

A rater sees the board and the moves up to a point, then two or more ways the model went on from there (a split:
LEFT / RIGHT / ...), each with its thinking, the code it ran, its actions and the boards after them. They say which
is better and why, and can mark single turns up or down with a note. Nothing here trains anything; the export is
for later.

  node    a game state several plays reach. level_start: every repeat of a game starts level L on the same board,
          so the repeats of a panel run are already paths forward from one point. fork: one logged turn, K sampled
          next turns (a fork sampler; same shapes).
  path    one play's turns from a node. Its content is a JSON file on the volume,
          <data root>/_review/paths/<sha256>.json, written by the publication below; rows here index it.
  split   2-4 paths of one node shown side by side. The server makes them whenever new paths reach a node: every
          pair not made yet, pairs from different models and pairs that ended differently first, so the pool keeps
          growing as runs are published.
  rating  one rater's verdict on one split: choice (a path id, 'tie' or 'neither'), confidence 1-3, a 1-5 score
          per path, marks on single turns [{path, step, verdict up|down, note}], a comment, seconds spent.

Who is calling, by route:

  /api/v1/review/...                  the signed-in team. oauth2-proxy authenticated the request and set
                                      X-Forwarded-Email; it must also be in ALLOWED_EMAILS (checked here, as the
                                      Harness Lab relay does). next, split, path, rating, me, stats, raters.
  /api/v1/public/review/...           outside raters. /api/v1/public/ is skip-auth; the X-Review-Key header (from
                                      an invite link, review.html#k=...) is the identity. next, split, path,
                                      rating, me. Rate-limited.
  /api/v1/review/publication          PUT, machines with ARC3_PUBLISH_TOKEN: nodes, paths (with content), splits.
  /api/v1/review/export               GET, machines with ARC3_PUBLISH_TOKEN: every rating as JSON lines.
  /api/v1/rl/dashboard                GET, the signed-in team: the RL page's data (one JSON document).
  /api/v1/rl/dashboard-publication    PUT, machines with ARC3_PUBLISH_TOKEN: replaces that document.

Held-out games (ARC3_REVIEW_FENCED; default the five test games and as66) are refused at publication: a rating
on them could leak into training. Game ids only, never titles.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import re
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

# This module imports nothing from its siblings, so it loads the same way in the image (flat files) and under
# test (the railway package).
EMAIL_RE = re.compile(r"^[^\s@]{1,200}@[^\s@]{1,200}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._~-]{0,199}$")
SPLIT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._~-]{0,254}$")
GAME_RE = re.compile(r"^[a-z0-9]{4}$")
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")
KEY_RE = re.compile(r"^[A-Za-z0-9_-]{20,100}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
RL2_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,120}$")
DEFAULT_FENCED = "lf52,tn36,re86,dc22,su15,as66"
CHOICE_EXTRA = ("tie", "neither")
VERDICTS = ("up", "down")

MAX_BODY = 1024 * 1024                       # one rating
MAX_PUBLICATION = 64 * 1024 * 1024           # one publication, as sent (gzip or plain)
MAX_UNPACKED = 512 * 1024 * 1024
MAX_DASHBOARD = 16 * 1024 * 1024
MAX_COMMENT = 4000
MAX_NOTE = 2000
MAX_MARKS = 200
MAX_NAME = 80
MAX_SPLITS_PER_NODE = 24
MAX_EXPORT_ROWS = 50_000
PUBLIC_POSTS = (40, 600.0)                   # ratings per rater per 10 minutes
PUBLIC_GETS = (900, 600.0)                   # reads per rater per 10 minutes


@dataclass
class Response:
    status: int
    body: bytes
    content_type: str = "application/json; charset=utf-8"


class ReviewProblem(Exception):
    """An expected failure that is safe to show the client."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fenced_games() -> set[str]:
    return {g.strip().lower() for g in os.environ.get("ARC3_REVIEW_FENCED", DEFAULT_FENCED).split(",") if g.strip()}


def allowed_emails() -> set[str]:
    return {e.casefold() for e in re.split(r"[,\s]+", os.environ.get("ALLOWED_EMAILS", "")) if e}


def key_sha256(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def content_bytes(content: Any) -> bytes:
    return json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _json(status: int, payload: Any) -> Response:
    return Response(status, json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8"))


def _rows(cursor: Any) -> list[dict[str, Any]]:
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _text(value: Any, field: str, limit: int) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ReviewProblem(400, f"invalid_{field}", f"{field} must be text")
    text = value.replace("\x00", "").strip()
    if len(text) > limit:
        raise ReviewProblem(400, f"invalid_{field}", f"{field} is longer than {limit} characters")
    return text or None


def _id(value: Any, field: str, pattern: re.Pattern = ID_RE) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ReviewProblem(400, f"invalid_{field}", f"{field} is not a valid id")
    return value


# ------------------------------------------------------------------------------------------------ ratings
def clean_rating(payload: Any, path_ids: list[str]) -> dict[str, Any]:
    """Validate one rating against the split it is for. Returns fields ready for SQL."""

    if not isinstance(payload, dict):
        raise ReviewProblem(400, "invalid_body", "send a JSON object")
    choice = payload.get("choice")
    if choice not in path_ids and choice not in CHOICE_EXTRA:
        raise ReviewProblem(400, "invalid_choice", "choice must be one of the split's paths, 'tie' or 'neither'")
    confidence = payload.get("confidence")
    if confidence is not None and (isinstance(confidence, bool) or confidence not in (1, 2, 3)):
        raise ReviewProblem(400, "invalid_confidence", "confidence must be 1, 2 or 3")
    scores = payload.get("scores") or {}
    if not isinstance(scores, dict) or any(k not in path_ids for k in scores) or any(
            isinstance(v, bool) or v not in (1, 2, 3, 4, 5) for v in scores.values()):
        raise ReviewProblem(400, "invalid_scores", "scores maps the split's paths to 1..5")
    marks = payload.get("marks") or []
    if not isinstance(marks, list) or len(marks) > MAX_MARKS:
        raise ReviewProblem(400, "invalid_marks", f"marks must be a list of at most {MAX_MARKS}")
    clean_marks = []
    for mark in marks:
        if not isinstance(mark, dict) or mark.get("path") not in path_ids:
            raise ReviewProblem(400, "invalid_marks", "each mark names one of the split's paths")
        step = mark.get("step")
        if isinstance(step, bool) or not isinstance(step, int) or not 0 <= step <= 1_000_000:
            raise ReviewProblem(400, "invalid_marks", "each mark has a turn number (step)")
        verdict = mark.get("verdict")
        if verdict is not None and verdict not in VERDICTS:
            raise ReviewProblem(400, "invalid_marks", "a mark's verdict is 'up', 'down' or null")
        note = _text(mark.get("note"), "note", MAX_NOTE)
        if verdict is None and note is None:
            continue
        clean_marks.append({"path": mark["path"], "step": step, "verdict": verdict, "note": note})
    seconds = payload.get("seconds")
    if seconds is not None and (isinstance(seconds, bool) or not isinstance(seconds, int) or not 0 <= seconds <= 86_400):
        raise ReviewProblem(400, "invalid_seconds", "seconds must be an integer in 0..86400")
    return {"choice": choice, "confidence": confidence, "scores": scores, "marks": clean_marks,
            "comment": _text(payload.get("comment"), "comment", MAX_COMMENT), "seconds": seconds}


def split_row(cursor: Any, split_id: str) -> dict[str, Any]:
    cursor.execute("SELECT split_id, node_id, path_ids, priority, source, active, created_at FROM rl_review_splits "
                   "WHERE split_id = %s", (split_id,))
    rows = _rows(cursor)
    if not rows:
        raise ReviewProblem(404, "unknown_split", "no such split")
    return rows[0]


def save_rating(cursor: Any, split_id: str, rater_id: str, payload: Any) -> dict[str, Any]:
    split = split_row(cursor, split_id)
    item = clean_rating(payload, list(split["path_ids"]))
    cursor.execute(
        """
        INSERT INTO rl_review_ratings (split_id, rater_id, choice, confidence, scores, marks, comment, seconds)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
        ON CONFLICT (split_id, rater_id) DO UPDATE SET
            choice = EXCLUDED.choice, confidence = EXCLUDED.confidence, scores = EXCLUDED.scores,
            marks = EXCLUDED.marks, comment = EXCLUDED.comment, seconds = EXCLUDED.seconds, updated_at = now()
        RETURNING rating_id, created_at, updated_at
        """,
        (split_id, rater_id, item["choice"], item["confidence"], json.dumps(item["scores"]),
         json.dumps(item["marks"]), item["comment"], item["seconds"]),
    )
    row = _rows(cursor)[0]
    return {"apiVersion": 1, "status": "saved", "ratingId": row["rating_id"], "split": split_id,
            "choice": item["choice"], "createdAt": iso(row["created_at"]), "updatedAt": iso(row["updated_at"])}


# ------------------------------------------------------------------------------------------------ reading
def _order(path_ids: list[str], rater_id: str, split_id: str) -> list[str]:
    """LEFT / RIGHT order, shuffled per rater (fixed for that rater): position must not stand for anything."""

    return sorted(path_ids, key=lambda p: hashlib.sha256(f"{rater_id}|{split_id}|{p}".encode()).hexdigest())


def split_view(cursor: Any, split_id: str, rater_id: str) -> dict[str, Any]:
    split = split_row(cursor, split_id)
    cursor.execute("SELECT node_id, kind, game_id, level, meta FROM rl_review_nodes WHERE node_id = %s",
                   (split["node_id"],))
    node = _rows(cursor)[0]
    cursor.execute("SELECT path_id, run_id, play, model, level, cleared, turns, actions, content_sha256, meta "
                   "FROM rl_review_paths WHERE path_id = ANY(%s)", (list(split["path_ids"]),))
    paths = {row["path_id"]: row for row in _rows(cursor)}
    cursor.execute("SELECT choice, confidence, scores, marks, comment, seconds, updated_at FROM rl_review_ratings "
                   "WHERE split_id = %s AND rater_id = %s", (split_id, rater_id))
    mine = _rows(cursor)
    cursor.execute("SELECT count(*) FROM rl_review_ratings WHERE split_id = %s", (split_id,))
    count = cursor.fetchone()[0]
    return {
        "apiVersion": 1,
        "split": {"id": split_id, "source": split["source"], "ratings": count},
        "node": {"id": node["node_id"], "kind": node["kind"], "game": node["game_id"], "level": node["level"],
                 "meta": node["meta"]},
        "paths": [{"id": p, "run": paths[p]["run_id"], "play": paths[p]["play"], "model": paths[p]["model"],
                   "level": paths[p]["level"], "cleared": paths[p]["cleared"], "turns": paths[p]["turns"],
                   "actions": paths[p]["actions"], "meta": paths[p]["meta"]}
                  for p in _order(list(split["path_ids"]), rater_id, split_id) if p in paths],
        "mine": ({**{k: mine[0][k] for k in ("choice", "confidence", "scores", "marks", "comment", "seconds")},
                  "updatedAt": iso(mine[0]["updated_at"])} if mine else None),
    }


def next_split(cursor: Any, rater_id: str, skip: list[str]) -> str | None:
    """The split this rater should see next: unrated by them, fewest ratings overall, highest priority first.
    Ties break on a per-rater hash, so two raters do not walk the pool in the same order."""

    cursor.execute(
        f"""
        SELECT s.split_id
        FROM rl_review_splits s
        JOIN rl_review_nodes n ON n.node_id = s.node_id
        LEFT JOIN (SELECT split_id, count(*) AS n FROM rl_review_ratings GROUP BY split_id) c
               ON c.split_id = s.split_id
        WHERE s.active AND {SHARED_CONTEXT_SQL}
          AND NOT EXISTS (SELECT 1 FROM rl_review_ratings r WHERE r.split_id = s.split_id AND r.rater_id = %s)
          AND NOT (s.split_id = ANY(%s))
        ORDER BY COALESCE(c.n, 0) ASC, n.kind = 'fork' DESC, s.priority DESC, md5(s.split_id || %s)
        LIMIT 1
        """,
        (rater_id, skip, rater_id),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def path_meta(cursor: Any, path_id: str) -> dict[str, Any]:
    cursor.execute("SELECT path_id, content_sha256 FROM rl_review_paths WHERE path_id = %s", (path_id,))
    rows = _rows(cursor)
    if not rows:
        raise ReviewProblem(404, "unknown_path", "no such path")
    return rows[0]


def rater_summary(cursor: Any, rater_id: str) -> dict[str, Any]:
    cursor.execute("SELECT count(*), max(updated_at) FROM rl_review_ratings WHERE rater_id = %s", (rater_id,))
    count, last = cursor.fetchone()
    cursor.execute(f"SELECT count(*) FROM rl_review_splits s JOIN rl_review_nodes n ON n.node_id = s.node_id "
                   f"WHERE s.active AND {SHARED_CONTEXT_SQL}")
    total = cursor.fetchone()[0]
    return {"rated": count, "last": iso(last), "splits": total}


def tree(cursor: Any, game: str) -> dict[str, Any]:
    """One game as a tree for the explorer: its nodes (level starts; forks later), every path out of each node and
    where it led (the next level's node when it cleared), and how each path fared with raters (pairwise wins,
    losses, ties, 'both bad', and turn marks)."""

    cursor.execute("SELECT node_id, kind, level, meta FROM rl_review_nodes WHERE game_id = %s ORDER BY level, node_id",
                   (game,))
    nodes = _rows(cursor)
    if not nodes:
        raise ReviewProblem(404, "unknown_game", "nothing published for this game")
    ids = [n["node_id"] for n in nodes]
    cursor.execute("SELECT path_id, node_id, run_id, play, model, level, cleared, turns, actions FROM rl_review_paths "
                   "WHERE node_id = ANY(%s) ORDER BY level, path_id", (ids,))
    paths = _rows(cursor)
    record = {p["path_id"]: {"wins": 0, "losses": 0, "ties": 0, "neither": 0} for p in paths}
    marks: dict[str, dict[str, int]] = {}
    cursor.execute("SELECT s.path_ids, r.choice, r.marks FROM rl_review_splits s "
                   "JOIN rl_review_ratings r ON r.split_id = s.split_id WHERE s.node_id = ANY(%s)", (ids,))
    for path_ids, choice, rating_marks in cursor.fetchall():
        for pid in path_ids:
            if pid in record:
                key = "ties" if choice == "tie" else "neither" if choice == "neither" else (
                    "wins" if choice == pid else "losses")
                record[pid][key] += 1
        for m in rating_marks or []:
            d = marks.setdefault(m.get("path"), {"up": 0, "down": 0, "notes": 0})
            if m.get("verdict") in VERDICTS:
                d[m["verdict"]] += 1
            if m.get("note"):
                d["notes"] += 1
    cursor.execute("SELECT node_id, split_id FROM rl_review_splits WHERE node_id = ANY(%s) AND active "
                   "ORDER BY priority DESC, split_id", (ids,))
    split_ids: dict[str, list[str]] = {}
    for node_id, split_id in cursor.fetchall():
        split_ids.setdefault(node_id, []).append(split_id)
    splits_at = {k: len(v) for k, v in split_ids.items()}
    cursor.execute("SELECT s.node_id, count(*) FROM rl_review_ratings r JOIN rl_review_splits s ON s.split_id = r.split_id "
                   "WHERE s.node_id = ANY(%s) GROUP BY s.node_id", (ids,))
    ratings_at = dict(cursor.fetchall())
    same_play = {(p["run_id"], p["play"], p["level"]): p["node_id"] for p in paths}
    first_at_level: dict[int, str] = {}
    for n in nodes:
        first_at_level.setdefault(n["level"], n["node_id"])
    out_paths = []
    for p in paths:
        nxt = None
        if p["cleared"]:   # the same play's next level, else the level's node any other play reached
            nxt = same_play.get((p["run_id"], p["play"], p["level"] + 1)) or first_at_level.get(p["level"] + 1)
        out_paths.append({"id": p["path_id"], "node": p["node_id"], "next": nxt, "run": p["run_id"], "play": p["play"],
                          "model": p["model"], "level": p["level"], "cleared": p["cleared"], "turns": p["turns"],
                          "actions": p["actions"], **record[p["path_id"]],
                          "marks": marks.get(p["path_id"], {"up": 0, "down": 0, "notes": 0})})
    return {"apiVersion": 1, "game": game,
            "nodes": [{"id": n["node_id"], "kind": n["kind"], "level": n["level"], "start": (n["meta"] or {}).get("start"),
                       "paths": sum(p["node_id"] == n["node_id"] for p in paths), "splits": splits_at.get(n["node_id"], 0),
                       "splitIds": split_ids.get(n["node_id"], [])[:24], "ratings": ratings_at.get(n["node_id"], 0)}
                      for n in nodes],
            "paths": out_paths}


def stats(cursor: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"apiVersion": 1}
    for name, table in (("nodes", "rl_review_nodes"), ("paths", "rl_review_paths"),
                        ("splits", "rl_review_splits"), ("ratings", "rl_review_ratings")):
        cursor.execute(f"SELECT count(*) FROM {table}")
        out[name] = cursor.fetchone()[0]
    # the pool: only pairs that share a context (shared_context), still switched on
    cursor.execute(f"SELECT count(*) FROM rl_review_splits s JOIN rl_review_nodes n ON n.node_id = s.node_id "
                   f"WHERE s.active AND {SHARED_CONTEXT_SQL}")
    out["splits"] = cursor.fetchone()[0]
    cursor.execute(
        f"""
        SELECT n.game_id AS game, count(DISTINCT n.node_id) AS nodes, count(DISTINCT p.path_id) AS paths,
               count(DISTINCT s.split_id) AS splits, count(DISTINCT r.rating_id) AS ratings
        FROM rl_review_nodes n
        LEFT JOIN rl_review_paths p ON p.node_id = n.node_id
        LEFT JOIN rl_review_splits s ON s.node_id = n.node_id AND s.active AND {SHARED_CONTEXT_SQL}
        LEFT JOIN rl_review_ratings r ON r.split_id = s.split_id
        GROUP BY n.game_id ORDER BY n.game_id
        """
    )
    out["games"] = _rows(cursor)
    cursor.execute("SELECT model, count(*) AS paths, sum(CASE WHEN cleared THEN 1 ELSE 0 END) AS cleared "
                   "FROM rl_review_paths GROUP BY model ORDER BY model")
    out["models"] = _rows(cursor)
    cursor.execute(
        """
        SELECT r.rater_id, COALESCE(x.name, r.rater_id) AS name, count(*) AS ratings, max(r.updated_at) AS last
        FROM rl_review_ratings r LEFT JOIN rl_review_raters x ON x.rater_id = r.rater_id
        GROUP BY r.rater_id, x.name ORDER BY count(*) DESC
        """
    )
    out["raters"] = [{**row, "last": iso(row["last"])} for row in _rows(cursor)]
    # Agreement: splits with 2+ ratings, share whose raters all picked the same answer.
    cursor.execute(
        """
        SELECT count(*) AS multi, sum(CASE WHEN distinct_choices = 1 THEN 1 ELSE 0 END) AS agreed
        FROM (SELECT split_id, count(DISTINCT choice) AS distinct_choices FROM rl_review_ratings
              GROUP BY split_id HAVING count(*) >= 2) t
        """
    )
    multi, agreed = cursor.fetchone()
    out["agreement"] = {"splits": multi or 0, "agreed": agreed or 0}
    cursor.execute(
        """
        SELECT r.split_id, r.rater_id, COALESCE(x.name, r.rater_id) AS name, r.choice, r.confidence, r.comment,
               r.updated_at, s.node_id
        FROM rl_review_ratings r JOIN rl_review_splits s ON s.split_id = r.split_id
        LEFT JOIN rl_review_raters x ON x.rater_id = r.rater_id
        ORDER BY r.updated_at DESC LIMIT 25
        """
    )
    out["recent"] = [{**row, "updated_at": iso(row["updated_at"])} for row in _rows(cursor)]
    return out


# ------------------------------------------------------------------------------------------------ raters
def create_rater(cursor: Any, name: Any, created_by: str) -> dict[str, Any]:
    clean = _text(name, "name", MAX_NAME)
    if not clean:
        raise ReviewProblem(400, "invalid_name", "give the rater a name")
    key = secrets.token_urlsafe(24)
    rater_id = "r_" + secrets.token_hex(6)
    cursor.execute("INSERT INTO rl_review_raters (rater_id, name, key_sha256, created_by) VALUES (%s, %s, %s, %s)",
                   (rater_id, clean, key_sha256(key), created_by))
    return {"apiVersion": 1, "raterId": rater_id, "name": clean, "key": key,
            "note": "the key is shown once; the link is review.html#k=<key>"}


def list_raters(cursor: Any) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT x.rater_id, x.name, x.created_by, x.active, x.created_at, count(r.rating_id) AS ratings,
               max(r.updated_at) AS last
        FROM rl_review_raters x LEFT JOIN rl_review_ratings r ON r.rater_id = x.rater_id
        GROUP BY x.rater_id ORDER BY x.created_at DESC
        """
    )
    return [{**row, "created_at": iso(row["created_at"]), "last": iso(row["last"])} for row in _rows(cursor)]


def set_rater_active(cursor: Any, rater_id: Any, active: bool) -> dict[str, Any]:
    rid = _id(rater_id, "raterId", re.compile(r"^r_[0-9a-f]{12}$"))
    cursor.execute("UPDATE rl_review_raters SET active = %s WHERE rater_id = %s", (active, rid))
    if cursor.rowcount == 0:
        raise ReviewProblem(404, "unknown_rater", "no such rater")
    return {"apiVersion": 1, "raterId": rid, "active": active}


def rater_by_key(cursor: Any, key: str) -> tuple[str, str]:
    if not KEY_RE.fullmatch(key or ""):
        raise ReviewProblem(401, "invalid_key", "open your invite link again")
    cursor.execute("SELECT rater_id, name FROM rl_review_raters WHERE key_sha256 = %s AND active",
                   (key_sha256(key),))
    row = cursor.fetchone()
    if not row:
        raise ReviewProblem(401, "invalid_key", "this invite link is not active")
    return row[0], row[1]


# ------------------------------------------------------------------------------------------------ publication
def pair_priority(a: dict[str, Any], b: dict[str, Any]) -> float:
    """Which pairs a rater learns most from: different models first (that is the before/after question), then
    pairs that ended differently (one cleared the level, one did not), then very different lengths."""

    return round(3.0 * (a["model"] != b["model"]) + 2.0 * (a["cleared"] != b["cleared"])
                 + abs(a["actions"] - b["actions"]) / max(a["actions"], b["actions"], 1), 3)


SHARED_CONTEXT_SQL = "(n.kind = 'fork' OR (n.kind = 'level_start' AND n.level = 1))"


def shared_context(node: dict[str, Any]) -> bool:
    """Only paths that went on from the same context are a branch (Son 2-Oct: "the context is not the same").
    A fork shares the forked play's exact history; the start of level 1 is the one point independent plays share
    (same prompt, same first board, no history). A later level start is the same board reached with different
    histories: comparing those paths compares different pasts, so no pairs are made there."""

    return node["kind"] == "fork" or (node["kind"] == "level_start" and node["level"] == 1)


def make_splits(cursor: Any, node_ids: list[str], source: str) -> int:
    """Every pair of paths at these nodes that is not a split yet, best pairs first, at most MAX_SPLITS_PER_NODE
    splits per node, only where the paths share a context (shared_context); pairs made earlier at other nodes
    are switched off."""

    made = 0
    for node_id in node_ids:
        cursor.execute("SELECT kind, level FROM rl_review_nodes WHERE node_id = %s", (node_id,))
        kind, level = cursor.fetchone()
        if not shared_context({"kind": kind, "level": level}):
            cursor.execute("UPDATE rl_review_splits SET active = false WHERE node_id = %s AND active", (node_id,))
            continue
        cursor.execute("SELECT path_id, model, cleared, actions FROM rl_review_paths WHERE node_id = %s ORDER BY path_id",
                       (node_id,))
        paths = _rows(cursor)
        cursor.execute("SELECT path_ids FROM rl_review_splits WHERE node_id = %s", (node_id,))
        have = {tuple(sorted(row[0])) for row in cursor.fetchall()}
        room = MAX_SPLITS_PER_NODE - len(have)
        pairs = sorted(((pair_priority(a, b), a["path_id"], b["path_id"]) for a, b in combinations(paths, 2)
                        if (a["path_id"], b["path_id"]) not in have), reverse=True)
        for priority, a, b in pairs[:max(0, room)]:
            digest = hashlib.sha256(f"{a}|{b}".encode()).hexdigest()[:12]
            cursor.execute(
                "INSERT INTO rl_review_splits (split_id, node_id, path_ids, priority, source) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (split_id) DO NOTHING",
                (f"{node_id}~{digest}", node_id, [a, b], priority, source),
            )
            made += cursor.rowcount
    return made


def publish(cursor: Any, data_root: Path, bundle: Any) -> dict[str, Any]:
    """Store nodes, paths (content to the volume) and make the splits they open up. Idempotent: publishing the same
    bundle again changes nothing; a path whose content changed gets the new content."""

    if not isinstance(bundle, dict):
        raise ReviewProblem(400, "invalid_body", "send a JSON object")
    source = _text(bundle.get("source"), "source", 120) or "publication"
    nodes, paths = bundle.get("nodes") or [], bundle.get("paths") or []
    if not isinstance(nodes, list) or not isinstance(paths, list):
        raise ReviewProblem(400, "invalid_body", "nodes and paths must be lists")
    fenced = fenced_games()
    node_ids = set()
    for node in nodes:
        if not isinstance(node, dict):
            raise ReviewProblem(400, "invalid_node", "each node is an object")
        nid = _id(node.get("id"), "node")
        game = _id(node.get("game"), "game", GAME_RE)
        if game in fenced:
            raise ReviewProblem(422, "fenced_game", f"{game} is held out: it is never rated")
        kind = node.get("kind")
        if kind not in ("level_start", "fork"):
            raise ReviewProblem(400, "invalid_kind", "kind must be level_start or fork")
        level = node.get("level")
        if isinstance(level, bool) or not isinstance(level, int) or level < 1:
            raise ReviewProblem(400, "invalid_level", "level must be a positive integer")
        meta = node.get("meta") or {}
        if not isinstance(meta, dict):
            raise ReviewProblem(400, "invalid_meta", "meta must be an object")
        cursor.execute(
            "INSERT INTO rl_review_nodes (node_id, kind, game_id, level, meta) VALUES (%s, %s, %s, %s, %s::jsonb) "
            "ON CONFLICT (node_id) DO UPDATE SET meta = rl_review_nodes.meta || EXCLUDED.meta",
            (nid, kind, game, level, json.dumps(meta)),
        )
        node_ids.add(nid)
    store = data_root / "_review" / "paths"
    store.mkdir(parents=True, exist_ok=True)
    touched, written = set(), 0
    for path in paths:
        if not isinstance(path, dict):
            raise ReviewProblem(400, "invalid_path", "each path is an object")
        pid = _id(path.get("id"), "path")
        nid = _id(path.get("node"), "node")
        cursor.execute("SELECT game_id FROM rl_review_nodes WHERE node_id = %s", (nid,))
        row = cursor.fetchone()
        if not row:
            raise ReviewProblem(400, "unknown_node", f"path {pid} names node {nid}, which is not published")
        if row[0] in fenced:
            raise ReviewProblem(422, "fenced_game", f"{row[0]} is held out: it is never rated")
        model = _id(path.get("model"), "model", MODEL_RE)
        content = path.get("content")
        if not isinstance(content, dict) or not isinstance(content.get("turns"), list):
            raise ReviewProblem(400, "invalid_content", f"path {pid} has no turns")
        raw = content_bytes(content)
        sha = hashlib.sha256(raw).hexdigest()
        target = store / f"{sha}.json"
        if not target.exists():
            tmp = store / f".{sha}.{secrets.token_hex(4)}.tmp"
            tmp.write_bytes(raw)
            os.replace(tmp, target)
            written += 1
        ints = {}
        for field in ("level", "turns", "actions"):
            value = path.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ReviewProblem(400, f"invalid_{field}", f"path {pid}: {field} must be a non-negative integer")
            ints[field] = value
        meta = path.get("meta") or {}
        if not isinstance(meta, dict):
            raise ReviewProblem(400, "invalid_meta", "meta must be an object")
        for field in ("first_action", "last_action"):
            if isinstance(path.get(field), int):
                meta[field] = path[field]
        cursor.execute(
            """
            INSERT INTO rl_review_paths (path_id, node_id, run_id, play, model, level, cleared, turns, actions,
                                         content_sha256, meta)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (path_id) DO UPDATE SET
                cleared = EXCLUDED.cleared, turns = EXCLUDED.turns, actions = EXCLUDED.actions,
                content_sha256 = EXCLUDED.content_sha256, meta = EXCLUDED.meta
            """,
            (pid, nid, _id(path.get("run"), "run"), _id(path.get("play"), "play"), model, ints["level"],
             bool(path.get("cleared")), ints["turns"], ints["actions"], sha, json.dumps(meta)),
        )
        touched.add(nid)
    made = make_splits(cursor, sorted(touched), source)
    return {"apiVersion": 1, "status": "published", "nodes": len(node_ids), "paths": len(paths),
            "contentWritten": written, "splitsMade": made}


# ------------------------------------------------------------------------------------------------ export
def export_ratings(cursor: Any, query: dict[str, list[str]]) -> list[dict[str, Any]]:
    where, params = [], []
    since = (query.get("since") or [None])[0]
    if since:
        try:
            parsed = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ReviewProblem(400, "invalid_since", "since must be an ISO-8601 timestamp") from exc
        where.append("r.updated_at >= %s")
        params.append(parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc))
    cursor.execute(
        f"""
        SELECT r.rating_id, r.split_id, r.rater_id, r.choice, r.confidence, r.scores, r.marks, r.comment, r.seconds,
               r.created_at, r.updated_at, s.node_id, s.path_ids, n.kind, n.game_id, n.level
        FROM rl_review_ratings r JOIN rl_review_splits s ON s.split_id = r.split_id
        JOIN rl_review_nodes n ON n.node_id = s.node_id
        {('WHERE ' + ' AND '.join(where)) if where else ''}
        ORDER BY r.updated_at, r.rating_id LIMIT {MAX_EXPORT_ROWS}
        """,
        params,
    )
    rows = _rows(cursor)
    ids = sorted({p for row in rows for p in row["path_ids"]})
    paths = {}
    if ids:
        cursor.execute("SELECT path_id, run_id, play, model, level, cleared, turns, actions, content_sha256 "
                       "FROM rl_review_paths WHERE path_id = ANY(%s)", (ids,))
        paths = {row["path_id"]: row for row in _rows(cursor)}
    out = []
    for row in rows:
        out.append({
            "ratingId": row["rating_id"], "split": row["split_id"], "node": row["node_id"], "kind": row["kind"],
            "game": row["game_id"], "level": row["level"], "rater": row["rater_id"],
            "raterKind": "team" if row["rater_id"].startswith("team:") else "outside",
            "choice": row["choice"], "confidence": row["confidence"], "scores": row["scores"], "marks": row["marks"],
            "comment": row["comment"], "seconds": row["seconds"],
            "createdAt": iso(row["created_at"]), "updatedAt": iso(row["updated_at"]),
            "paths": [{"id": p, "run": paths[p]["run_id"], "play": paths[p]["play"], "model": paths[p]["model"],
                       "cleared": paths[p]["cleared"], "turns": paths[p]["turns"], "actions": paths[p]["actions"],
                       "contentSha256": paths[p]["content_sha256"]} for p in row["path_ids"] if p in paths],
        })
    return out


# ------------------------------------------------------------------------------------------------ the API
class _Limiter:
    """Per-key sliding window, in memory (one server process)."""

    def __init__(self, limit: int, window: float):
        self.limit, self.window = limit, window
        self.hits: dict[str, deque] = {}
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self.lock:
            q = self.hits.setdefault(key, deque())
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True


class RlReviewApi:
    REVIEW = "/api/v1/review"
    PUBLIC = "/api/v1/public/review"
    RL = "/api/v1/rl"
    RL2 = "/api/v1/rl2"

    def __init__(self, connect: Callable[[], Any], data_root: Path, publish_token: str):
        self.connect = connect
        self.data_root = Path(data_root)
        self.publish_token = publish_token
        self.posts = _Limiter(*PUBLIC_POSTS)
        self.gets = _Limiter(*PUBLIC_GETS)

    @classmethod
    def owns(cls, path: str) -> bool:
        return any(path == p or path.startswith(p + "/") for p in (cls.REVIEW, cls.PUBLIC, cls.RL, cls.RL2))

    # Identity. The team routes are behind oauth2-proxy; the allowlist is re-checked here because the proxy's
    # domain setting may let other Google accounts sign in. The public prefix is skip-auth, so X-Forwarded-Email
    # is never read there: the review key is the identity.
    @staticmethod
    def team_email(headers: Any) -> str:
        email = (headers.get("X-Forwarded-Email") or "").strip().lower()
        if not EMAIL_RE.fullmatch(email):
            raise ReviewProblem(401, "sign_in_required", "sign in to use this endpoint")
        if email.casefold() not in allowed_emails():
            raise ReviewProblem(403, "not_on_team", "this Google account is not on the team list; use an invite link")
        return email

    def require_token(self, headers: Any) -> None:
        if not self.publish_token:
            raise ReviewProblem(503, "publisher_disabled", "publication API is not configured")
        authorization = headers.get("Authorization", "")
        supplied = authorization[len("Bearer "):] if authorization.startswith("Bearer ") else ""
        if not supplied or not secrets.compare_digest(supplied, self.publish_token):
            raise ReviewProblem(401, "unauthorized", "invalid publication token")

    @staticmethod
    def _length(headers: Any, limit: int) -> int:
        try:
            length = int(headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ReviewProblem(400, "invalid_content_length", "invalid Content-Length") from exc
        if length <= 0 or length > limit:
            raise ReviewProblem(413 if length > limit else 400, "invalid_body", f"body must be 1..{limit} bytes")
        return length

    def _read_json(self, read_body: Callable[[int], bytes], headers: Any, limit: int) -> Any:
        raw = read_body(self._length(headers, limit))
        if raw[:2] == b"\x1f\x8b":
            try:
                with gzip.GzipFile(fileobj=io.BytesIO(raw)) as fh:
                    raw = fh.read(MAX_UNPACKED + 1)
            except OSError as exc:
                raise ReviewProblem(400, "invalid_gzip", "body is not valid gzip") from exc
            if len(raw) > MAX_UNPACKED:
                raise ReviewProblem(413, "invalid_body", "unpacked body is too large")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReviewProblem(400, "invalid_json", "body is not JSON") from exc

    def handle(self, method: str, raw_path: str, headers: Any, read_body: Callable[[int], bytes]) -> Response:
        parsed = urlparse(raw_path)
        try:
            return self._route(method, parsed.path, parse_qs(parsed.query), headers, read_body)
        except ReviewProblem as exc:
            return _json(exc.status, {"error": exc.code, "message": exc.message})

    def _route(self, method: str, path: str, query: dict[str, list[str]], headers: Any,
               read_body: Callable[[int], bytes]) -> Response:
        # Machines (bearer token); oauth2-proxy lets exactly these paths through unauthenticated.
        if path == f"{self.REVIEW}/publication":
            self.require_token(headers)
            if method != "PUT":
                raise ReviewProblem(405, "method_not_allowed", "use PUT")
            bundle = self._read_json(read_body, headers, MAX_PUBLICATION)
            with self._cursor(commit=True) as cursor:
                result = publish(cursor, self.data_root, bundle)
            print(f"review: published {result['paths']} paths, {result['splitsMade']} new splits", flush=True)
            return _json(200, result)
        if path == f"{self.REVIEW}/export":
            self.require_token(headers)
            if method != "GET":
                raise ReviewProblem(405, "method_not_allowed", "use GET")
            with self._cursor() as cursor:
                lines = [json.dumps(r, ensure_ascii=False, separators=(",", ":"), default=str)
                         for r in export_ratings(cursor, query)]
            return Response(200, ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8"),
                            "application/x-ndjson; charset=utf-8")
        if path == f"{self.RL}/dashboard-publication":
            self.require_token(headers)
            if method != "PUT":
                raise ReviewProblem(405, "method_not_allowed", "use PUT")
            document = self._read_json(read_body, headers, MAX_DASHBOARD)
            if not isinstance(document, dict):
                raise ReviewProblem(400, "invalid_body", "send a JSON object")
            target = self.data_root / "_rl" / "dashboard.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(f".dashboard.{secrets.token_hex(4)}.tmp")
            tmp.write_bytes(json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            os.replace(tmp, target)
            return _json(200, {"apiVersion": 1, "status": "published"})
        if path == f"{self.RL}/dashboard":
            self.team_email(headers)
            if method != "GET":
                raise ReviewProblem(405, "method_not_allowed", "use GET")
            target = self.data_root / "_rl" / "dashboard.json"
            if not target.exists():
                raise ReviewProblem(404, "no_dashboard", "nothing published yet")
            return Response(200, target.read_bytes())
        # RL2 (turn coach): named documents, published by machines and read by the team.
        if path.startswith(f"{self.RL2}/publication/"):
            name = self._rl2_name(path[len(f"{self.RL2}/publication/"):])
            self.require_token(headers)
            if method != "PUT":
                raise ReviewProblem(405, "method_not_allowed", "use PUT")
            document = self._read_json(read_body, headers, MAX_DASHBOARD)
            if not isinstance(document, dict):
                raise ReviewProblem(400, "invalid_body", "send a JSON object")
            target = self.data_root / "_rl2" / f"{name}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(f".{name}.{secrets.token_hex(4)}.tmp")
            tmp.write_bytes(json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            os.replace(tmp, target)
            return _json(200, {"apiVersion": 1, "status": "published", "name": name})
        if path.startswith(f"{self.RL2}/doc/"):
            name = self._rl2_name(path[len(f"{self.RL2}/doc/"):])
            self.team_email(headers)
            if method != "GET":
                raise ReviewProblem(405, "method_not_allowed", "use GET")
            target = self.data_root / "_rl2" / f"{name}.json"
            if not target.exists():
                raise ReviewProblem(404, "no_document", "nothing published under this name yet")
            return Response(200, target.read_bytes())

        # Raters.
        if path.startswith(self.PUBLIC + "/"):
            key = headers.get("X-Review-Key", "")
            if not KEY_RE.fullmatch(key or ""):          # before any database work
                raise ReviewProblem(401, "invalid_key", "open your invite link again")
            sub = path[len(self.PUBLIC):]
            with self._cursor() as cursor:
                rater_id, name = rater_by_key(cursor, key)
            limiter = self.posts if method == "POST" else self.gets
            if not limiter.allow(rater_id):
                raise ReviewProblem(429, "slow_down", "too many requests; take a short break")
            return self._rater_route(method, sub, query, headers, read_body, rater_id, name, team=False)
        if path.startswith(self.REVIEW + "/"):
            email = self.team_email(headers)
            sub = path[len(self.REVIEW):]
            return self._rater_route(method, sub, query, headers, read_body, f"team:{email}", email, team=True)
        raise ReviewProblem(404, "not_found", "not found")

    @staticmethod
    def _rl2_name(name: str) -> str:
        if not RL2_NAME_RE.fullmatch(name or ""):
            raise ReviewProblem(400, "invalid_name", "document names are lowercase letters, digits, '.', '_' and '-'")
        return name

    def _rater_route(self, method: str, sub: str, query: dict[str, list[str]], headers: Any,
                     read_body: Callable[[int], bytes], rater_id: str, name: str, team: bool) -> Response:
        arg = lambda key: (query.get(key) or [None])[0]  # noqa: E731
        if sub == "/me" and method == "GET":
            with self._cursor() as cursor:
                return _json(200, {"apiVersion": 1, "rater": rater_id, "name": name, "team": team,
                                   **rater_summary(cursor, rater_id)})
        if sub == "/next" and method == "GET":
            skip = [s for s in (arg("skip") or "").split(",") if s and SPLIT_RE.fullmatch(s)][:200]
            with self._cursor() as cursor:
                split_id = next_split(cursor, rater_id, skip)
                if split_id is None:
                    return _json(200, {"apiVersion": 1, "done": True, **rater_summary(cursor, rater_id)})
                return _json(200, split_view(cursor, split_id, rater_id))
        if sub == "/split" and method == "GET":
            split_id = _id(arg("id"), "id", SPLIT_RE)
            with self._cursor() as cursor:
                return _json(200, split_view(cursor, split_id, rater_id))
        if sub == "/path" and method == "GET":
            path_id = _id(arg("id"), "id")
            with self._cursor() as cursor:
                meta = path_meta(cursor, path_id)
            target = self.data_root / "_review" / "paths" / f"{meta['content_sha256']}.json"
            if not SHA_RE.fullmatch(meta["content_sha256"]) or not target.exists():
                raise ReviewProblem(404, "missing_content", "this path's content is not on the server")
            return Response(200, target.read_bytes())
        if sub == "/rating" and method == "POST":
            payload = self._read_json(read_body, headers, MAX_BODY)
            split_id = _id((payload or {}).get("split") if isinstance(payload, dict) else None, "split", SPLIT_RE)
            with self._cursor(commit=True) as cursor:
                result = save_rating(cursor, split_id, rater_id, payload)
            print(f"review: {rater_id} rated {split_id} -> {result['choice']}", flush=True)
            return _json(200, result)
        if team and sub == "/stats" and method == "GET":
            with self._cursor() as cursor:
                return _json(200, stats(cursor))
        if team and sub == "/tree" and method == "GET":
            game = _id(arg("game"), "game", GAME_RE)
            with self._cursor() as cursor:
                return _json(200, tree(cursor, game))
        if team and sub == "/raters":
            with self._cursor(commit=method == "POST") as cursor:
                if method == "GET":
                    return _json(200, {"apiVersion": 1, "raters": list_raters(cursor)})
                if method == "POST":
                    body = self._read_json(read_body, headers, MAX_BODY)
                    return _json(200, create_rater(cursor, (body or {}).get("name") if isinstance(body, dict) else None,
                                                   name))
        if team and sub in ("/raters/revoke", "/raters/restore") and method == "POST":
            body = self._read_json(read_body, headers, MAX_BODY)
            with self._cursor(commit=True) as cursor:
                return _json(200, set_rater_active(cursor, (body or {}).get("raterId") if isinstance(body, dict) else None,
                                                   sub.endswith("restore")))
        raise ReviewProblem(404, "not_found", "not found")

    class _Cursor:
        def __init__(self, connect: Callable[[], Any], commit: bool):
            self.connection = connect()
            self.commit = commit
            self.cursor = None

        def __enter__(self):
            self.cursor = self.connection.cursor()
            return self.cursor

        def __exit__(self, exc_type, exc, tb):
            try:
                if exc_type is None and self.commit:
                    self.connection.commit()
                else:
                    self.connection.rollback()
            finally:
                self.cursor.close()
                self.connection.close()
            return False

    def _cursor(self, commit: bool = False) -> "RlReviewApi._Cursor":
        return RlReviewApi._Cursor(self.connect, commit)

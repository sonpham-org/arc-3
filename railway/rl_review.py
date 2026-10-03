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
  /api/v1/rl2/publication/<name>      PUT, machines: an RL2 (turn coach) named document. GET .../rl2/doc/<name>, team.
  /api/v1/rl2/tree/publication        PUT, machines: one run's part of the RL2 decision tree (nodes, branches,
                                      traces). GET .../rl2/tree/games, /node/<id>, /trace/<sha>: the team.
                                      (Kept for now; the RL2 page reads the universal tree below.)
  /api/v1/gtree/publication           PUT, machines: rollouts, screens, nodes, steps, traces into the universal game
                                      tree (one step table read as four trees; rollouts from the game start or
                                      restarted mid-tree). GET .../gtree/games, /stats, /node/<id>, /rollout/<id>,
                                      /trace/<sha>, /frontier?game=&tree=&N=: the team.

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
from urllib.parse import parse_qs, unquote, urlparse

# This module imports nothing from its siblings, so it loads the same way in the image (flat files) and under
# test (the railway package).
EMAIL_RE = re.compile(r"^[^\s@]{1,200}@[^\s@]{1,200}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._~-]{0,199}$")
# RL2 build ids are paths in the build tree ("animft/coach-random50")
BUILD_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._~/-]{0,199}$")
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


# ------------------------------------------------------------------------------------------------ RL2 decision tree
# The turn coach's decisions as a tree that merges: a node is the game state where the coach decided
# ('<game>:L<level>:<board_hash>'), a branch is one decision taken there (mode, cap, probability, what the coach saw,
# what followed, the turn's trace) and points at the node of that play's next decision. Every run starts level L
# from the same board, so a level's start node collects branches from every run, mode and build. Tables
# rl2_tree_nodes / rl2_tree_branches (catalog_schema.sql); traces on the volume, <data root>/_rl2/traces/<sha>.json,
# named by the sha256 of their canonical JSON (rl2_trace_bytes).
RL2_NODE_RE = re.compile(r"^([a-z0-9]{4}):L([0-9]{1,4}):([0-9a-f]{12})$")
RL2_MODE_RE = re.compile(r"^[a-z_]{1,20}$")
HEX_ROW_RE = re.compile(r"^[0-9a-fA-F]{1,64}$")
MAX_TREE_NODES = 100_000
MAX_TREE_BRANCHES = 200_000
MAX_TREE_TRACES = 200_000
MAX_TREE_JSON = 8 * 1024                    # one branch's features or outcome, as JSON
MAX_NODE_BRANCHES = 20_000                  # branches returned for one node


def rl2_trace_bytes(content: Any) -> bytes:
    """A trace's canonical bytes; its name is their sha256 (the publisher computes the same)."""

    return json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _int(value: Any, field: str, low: int = 0, null: bool = False) -> int | None:
    if value is None and null:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < low:
        raise ReviewProblem(400, f"invalid_{field}", f"{field} must be an integer >= {low}")
    return value


def _small_object(value: Any, field: str, where: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict) or len(json.dumps(value)) > MAX_TREE_JSON:
        raise ReviewProblem(400, f"invalid_{field}", f"{where}: {field} must be an object under {MAX_TREE_JSON} bytes")
    return value


def clean_tree_bundle(bundle: Any) -> dict[str, Any]:
    """Validate one run's tree publication (no database, no disk). Returns {run, build, policy, nodes, branches,
    traces} ready for SQL: nodes {id, game, level, board_hash, board}, branches with every column, traces
    {sha: canonical bytes}. Node references outside the bundle are checked against the database by publish_tree."""

    if not isinstance(bundle, dict):
        raise ReviewProblem(400, "invalid_body", "send a JSON object")
    run = _id(bundle.get("run"), "run")
    build = _id(bundle.get("build"), "build", BUILD_RE)
    policy = None if bundle.get("policy") in (None, "") else _id(bundle.get("policy"), "policy")
    nodes, branches, traces = bundle.get("nodes") or [], bundle.get("branches") or [], bundle.get("traces") or {}
    if not isinstance(nodes, list) or not isinstance(branches, list) or not isinstance(traces, dict):
        raise ReviewProblem(400, "invalid_body", "nodes and branches are lists, traces an object")
    if len(nodes) > MAX_TREE_NODES or len(branches) > MAX_TREE_BRANCHES or len(traces) > MAX_TREE_TRACES:
        raise ReviewProblem(413, "too_many", f"at most {MAX_TREE_NODES} nodes, {MAX_TREE_BRANCHES} branches, "
                                             f"{MAX_TREE_TRACES} traces per publication")
    clean_traces: dict[str, bytes] = {}
    for sha, content in traces.items():
        _id(sha, "trace_sha", SHA_RE)
        if not isinstance(content, dict) or not isinstance(content.get("turns"), list):
            raise ReviewProblem(400, "invalid_trace", f"trace {sha[:12]} has no turns")
        raw = rl2_trace_bytes(content)
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ReviewProblem(400, "trace_sha_mismatch", f"trace {sha[:12]} does not match the sha256 of its "
                                                           "canonical JSON (sort_keys, no spaces)")
        clean_traces[sha] = raw
    clean_nodes: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise ReviewProblem(400, "invalid_node", "each node is an object")
        nid = node.get("id")
        match = RL2_NODE_RE.fullmatch(nid) if isinstance(nid, str) else None
        if not match:
            raise ReviewProblem(400, "invalid_node", "a node id is '<game>:L<level>:<12 hex board hash>'")
        game, level, board_hash = match.group(1), int(match.group(2)), match.group(3)
        if (node.get("game"), node.get("level"), node.get("board_hash")) != (game, level, board_hash):
            raise ReviewProblem(400, "invalid_node", f"node {nid}: game, level and board_hash must match its id")
        board = node.get("board")
        if board is not None and (not isinstance(board, list) or not 1 <= len(board) <= 64 or any(
                not isinstance(row, str) or not HEX_ROW_RE.fullmatch(row) for row in board)):
            raise ReviewProblem(400, "invalid_board", f"node {nid}: board is up to 64 rows of hex digits, or null")
        if nid in clean_nodes and clean_nodes[nid]["board"] is not None:
            continue
        clean_nodes[nid] = {"id": nid, "game": game, "level": level, "board_hash": board_hash, "board": board}
    clean_branches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for branch in branches:
        if not isinstance(branch, dict):
            raise ReviewProblem(400, "invalid_branch", "each branch is an object")
        bid = _id(branch.get("id"), "branch")
        if not bid.startswith(run + ":"):
            raise ReviewProblem(400, "invalid_branch", f"branch {bid} must start with its run id '{run}:'")
        if bid in seen:
            raise ReviewProblem(400, "duplicate_branch", f"branch {bid} appears twice")
        seen.add(bid)
        if branch.get("run", run) != run:
            raise ReviewProblem(400, "invalid_run", f"branch {bid} belongs to another run")
        node_id, child = branch.get("node"), branch.get("child")
        if not isinstance(node_id, str) or not RL2_NODE_RE.fullmatch(node_id):
            raise ReviewProblem(400, "invalid_node", f"branch {bid}: node is not a node id")
        if child is not None and (not isinstance(child, str) or not RL2_NODE_RE.fullmatch(child)):
            raise ReviewProblem(400, "invalid_child", f"branch {bid}: child is a node id or null")
        mode = branch.get("mode")
        if not isinstance(mode, str) or not RL2_MODE_RE.fullmatch(mode):
            raise ReviewProblem(400, "invalid_mode", f"branch {bid}: mode is 1-20 lowercase letters or '_'")
        prob = branch.get("prob")
        if prob is not None and (isinstance(prob, bool) or not isinstance(prob, (int, float)) or not 0 <= prob <= 1):
            raise ReviewProblem(400, "invalid_prob", f"branch {bid}: prob is a number in 0..1 or null")
        trace_sha = branch.get("trace_sha")
        if trace_sha is not None:
            _id(trace_sha, "trace_sha", SHA_RE)
        b_policy = branch.get("policy", policy)
        clean_branches.append({
            "id": bid, "node": node_id, "child": child, "run": run, "play": _id(branch.get("play"), "play"),
            "build": _id(branch.get("build") or build, "build", BUILD_RE),
            "policy": None if b_policy in (None, "") else _id(b_policy, "policy"),
            "decision": _int(branch.get("decision"), "decision"), "mode": mode,
            "cap": _int(branch.get("cap"), "cap", null=True), "prob": None if prob is None else float(prob),
            "features": _small_object(branch.get("features"), "features", bid),
            "outcome": _small_object(branch.get("outcome"), "outcome", bid), "trace_sha": trace_sha,
        })
    return {"run": run, "build": build, "policy": policy, "nodes": list(clean_nodes.values()),
            "branches": clean_branches, "traces": clean_traces}


def publish_tree(cursor: Any, data_root: Path, bundle: Any) -> dict[str, Any]:
    """Store one run's part of the tree. Idempotent per run: nodes are upserted (the first board is kept), the run's
    branches are deleted and the new ones inserted, traces are written once by sha."""

    item = clean_tree_bundle(bundle)
    store = data_root / "_rl2" / "traces"
    in_bundle = {n["id"] for n in item["nodes"]}
    outside = sorted({b["node"] for b in item["branches"]} - in_bundle)
    if outside:
        cursor.execute("SELECT id FROM rl2_tree_nodes WHERE id = ANY(%s)", (outside,))
        missing = set(outside) - {row[0] for row in cursor.fetchall()}
        if missing:
            raise ReviewProblem(400, "unknown_node", f"branches name nodes that are not published: "
                                                     f"{', '.join(sorted(missing)[:5])}")
    for sha in sorted({b["trace_sha"] for b in item["branches"] if b["trace_sha"]} - set(item["traces"])):
        if not (store / f"{sha}.json").exists():
            raise ReviewProblem(400, "unknown_trace", f"trace {sha[:12]} is neither in this publication nor stored")
    if item["nodes"]:
        cursor.executemany(
            "INSERT INTO rl2_tree_nodes (id, game, level, board_hash, board, first_run) "
            "VALUES (%s, %s, %s, %s, %s::jsonb, %s) "
            "ON CONFLICT (id) DO UPDATE SET board = COALESCE(rl2_tree_nodes.board, EXCLUDED.board)",
            [(n["id"], n["game"], n["level"], n["board_hash"], None if n["board"] is None else json.dumps(n["board"]),
              item["run"]) for n in item["nodes"]])
    cursor.execute("DELETE FROM rl2_tree_branches WHERE run = %s", (item["run"],))
    replaced = cursor.rowcount
    if item["branches"]:
        cursor.executemany(
            "INSERT INTO rl2_tree_branches (id, node_id, child_id, run, play, build, policy, decision, mode, cap, prob, "
            "features, outcome, trace_sha) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)",
            [(b["id"], b["node"], b["child"], b["run"], b["play"], b["build"], b["policy"], b["decision"], b["mode"],
              b["cap"], b["prob"], json.dumps(b["features"]), json.dumps(b["outcome"]), b["trace_sha"])
             for b in item["branches"]])
    written = 0
    if item["traces"]:
        store.mkdir(parents=True, exist_ok=True)
        for sha, raw in item["traces"].items():
            target = store / f"{sha}.json"
            if target.exists():
                continue
            tmp = store / f".{sha}.{secrets.token_hex(4)}.tmp"
            tmp.write_bytes(raw)
            os.replace(tmp, target)
            written += 1
    return {"apiVersion": 1, "status": "published", "run": item["run"], "nodes": len(item["nodes"]),
            "branches": len(item["branches"]), "branchesReplaced": replaced, "traces": len(item["traces"]),
            "tracesWritten": written}


def tree_games(cursor: Any) -> list[dict[str, Any]]:
    """Every game and level in the tree, with its start nodes: nodes where some branch was decided with 0 actions
    into the level, most-visited first; a level with none falls back to its most-visited node."""

    cursor.execute(
        """
        SELECT n.game, n.level, n.id, count(b.id) AS branches,
               COALESCE(bool_or(b.features -> 'actions_in_level' = '0'::jsonb), false) AS start
        FROM rl2_tree_nodes n LEFT JOIN rl2_tree_branches b ON b.node_id = n.id
        GROUP BY n.game, n.level, n.id
        ORDER BY n.game, n.level, count(b.id) DESC, n.id
        """
    )
    games: dict[str, dict[int, dict[str, Any]]] = {}
    for game, level, nid, count, start in cursor.fetchall():
        slot = games.setdefault(game, {}).setdefault(level, {"level": level, "nodes": 0, "branches": 0,
                                                             "start_nodes": [], "_top": nid})
        slot["nodes"] += 1
        slot["branches"] += count
        if start and len(slot["start_nodes"]) < 20:
            slot["start_nodes"].append(nid)
    out = []
    for game in sorted(games):
        levels = []
        for level in sorted(games[game]):
            slot = games[game][level]
            top = slot.pop("_top")
            if not slot["start_nodes"]:
                slot["start_nodes"] = [top]
            levels.append(slot)
        out.append({"game": game, "levels": levels})
    return out


def _mean(values: list[Any]) -> float | None:
    nums = [float(v) for v in values if isinstance(v, (int, float)) and not (isinstance(v, float) and v != v)]
    return round(sum(nums) / len(nums), 4) if nums else None


def tree_node(cursor: Any, node_id: str) -> dict[str, Any]:
    """One node: its branches (no trace content), a summary per mode, the nodes that lead here and, per child, how
    many plays reached it (a child more than one play reached is a merge)."""

    if not RL2_NODE_RE.fullmatch(node_id or ""):
        raise ReviewProblem(400, "invalid_node", "a node id is '<game>:L<level>:<12 hex board hash>'")
    cursor.execute("SELECT id, game, level, board_hash, board, first_run, created_at FROM rl2_tree_nodes WHERE id = %s",
                   (node_id,))
    rows = _rows(cursor)
    if not rows:
        raise ReviewProblem(404, "unknown_node", "no such node")
    node = {**rows[0], "created_at": iso(rows[0]["created_at"])}
    cursor.execute(
        f"""
        SELECT id, node_id AS node, child_id AS child, run, play, build, policy, decision, mode, cap, prob, features,
               outcome, trace_sha, published_at
        FROM rl2_tree_branches WHERE node_id = %s ORDER BY run, play, decision LIMIT {MAX_NODE_BRANCHES + 1}
        """,
        (node_id,))
    branches = [{**b, "published_at": iso(b["published_at"])} for b in _rows(cursor)]
    truncated = len(branches) > MAX_NODE_BRANCHES
    branches = branches[:MAX_NODE_BRANCHES]
    cursor.execute("SELECT count(*) FROM rl2_tree_branches WHERE child_id = %s", (node_id,))
    arrivals = cursor.fetchone()[0]
    cursor.execute("SELECT node_id, count(*) FROM rl2_tree_branches WHERE child_id = %s GROUP BY node_id "
                   "ORDER BY count(*) DESC, node_id LIMIT 200", (node_id,))
    parents = [row[0] for row in cursor.fetchall()]
    children = sorted({b["child"] for b in branches if b["child"]})
    child_info: dict[str, dict[str, Any]] = {}
    if children:
        cursor.execute(
            """
            SELECT c.id, (SELECT count(*) FROM rl2_tree_branches x WHERE x.node_id = c.id) AS branches,
                   (SELECT count(*) FROM rl2_tree_branches y WHERE y.child_id = c.id) AS arrivals,
                   EXISTS (SELECT 1 FROM rl2_tree_nodes z WHERE z.id = c.id) AS published
            FROM unnest(%s::text[]) AS c(id)
            """,
            (children,))
        child_info = {r["id"]: {"branches": r["branches"], "arrivals": r["arrivals"], "published": r["published"]}
                      for r in _rows(cursor)}
    for b in branches:
        b["child_info"] = child_info.get(b["child"]) if b["child"] else None
    by_mode: dict[str, dict[str, Any]] = {}
    for mode in sorted({b["mode"] for b in branches}):
        outs = [b["outcome"] or {} for b in branches if b["mode"] == mode]
        by_mode[mode] = {"n": len(outs), "lvl30": _mean([o.get("lvl30") for o in outs]),
                         "cleared": _mean([o.get("cleared_level") for o in outs]),
                         "acts": _mean([o.get("acts") for o in outs]), "go": _mean([o.get("go_turn") for o in outs])}
    return {"apiVersion": 1, "node": {**node, "branches": len(branches), "arrivals": arrivals},
            "branches": branches, "truncated": truncated, "by_mode": by_mode, "parents": parents}


# ------------------------------------------------------------------------------------------------ the universal game tree
# Any rollout's data, stored once and read as four trees (tables gt_screens / gt_nodes / gt_rollouts / gt_steps,
# catalog_schema.sql), separate from RL v1 (Firestore) and from the RL2 tables above.
#
#   step     one action of one rollout: the mode chosen ('stock' for an uncoached turn), the screen before it, what
#            the coach saw (features), what followed (outcome), its trace, and its node in each tree (n1..n4) plus the
#            node it led to (c1..c4; null at a rollout's end).
#   tree     t1 path (context-aware: the actions taken since the game start), t2 screen + moves, t3 level + screen,
#            t4 screen only. Every step is in all four, so each tree is a GROUP BY over the same rows. The root of a
#            tree is the game start, '<game>:t<k>:root' (screen null). The PUBLISHER computes every node id; the
#            server only checks their shape and that a step's nodes exist.
#   rollout  one play: from the game start (origin_state null, origin_kind 'start') or restarted from a t1 node in
#            the middle of the tree (Go-Explore style: origin_state the node, origin_kind replay_exact /
#            replay_actions / restore, origin_edge the step it branched after, if any).
# Traces are on the volume, <data root>/_gtree/traces/<sha>.json, named like the RL2 traces (rl2_trace_bytes).
GT_TREES = (1, 2, 3, 4)
GT_TREE_NAMES = {1: "path (context-aware)", 2: "screen + moves", 3: "level + screen", 4: "screen only"}
GT_ORIGINS = ("start", "replay_exact", "replay_actions", "restore")
GT_NODE_RE = re.compile(r"^([a-z0-9]{4}):t([1-4]):([0-9a-f]{16}|root)$")
GT_SCREEN_RE = re.compile(r"^[0-9a-f]{12}$")
GT_STEP_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._~-]{0,254}$")
GT_ACTION_RE = re.compile(r"^[A-Za-z0-9_.:+-]{1,40}$")
GT_STATUS_RE = re.compile(r"^[A-Za-z0-9_.-]{1,40}$")
MAX_GT_ROLLOUTS = 20_000
MAX_GT_RESULT = 32 * 1024                   # one rollout's result, as JSON
MAX_HIDDEN_REF = 500
MAX_FRONTIER = 500
MAX_FRONTIER_N = 1000
GT_OUTCOME_KEYS = (("lvl30", "lvl30"), ("cleared", "cleared_level"), ("acts", "acts"), ("go", "go_turn"),
                   ("level_score", "level_score"))


def _small(value: Any, field: str, where: str, limit: int = MAX_TREE_JSON) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict) or len(json.dumps(value)) > limit:
        raise ReviewProblem(400, f"invalid_{field}", f"{where}: {field} must be an object under {limit} bytes")
    return value


def _node_id(value: Any, field: str, where: str, game: str | None = None, tree: int | None = None,
             null: bool = False) -> str | None:
    """A node id '<game>:t<tree>:<16 hex>' or '<game>:t<tree>:root', of this game and tree when given."""

    if value is None and null:
        return None
    match = GT_NODE_RE.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise ReviewProblem(400, f"invalid_{field}", f"{where}: {field} is a node id '<game>:t<1-4>:<16 hex>' or "
                                                     f"'<game>:t<1-4>:root'" + (" or null" if null else ""))
    if game is not None and match.group(1) != game:
        raise ReviewProblem(400, f"invalid_{field}", f"{where}: {field} is a node of another game")
    if tree is not None and int(match.group(2)) != tree:
        raise ReviewProblem(400, f"invalid_{field}", f"{where}: {field} must be a node of tree t{tree}")
    return value


def _screen(value: Any, field: str, where: str, null: bool = False) -> str | None:
    if value is None and null:
        return None
    if not isinstance(value, str) or not GT_SCREEN_RE.fullmatch(value):
        raise ReviewProblem(400, f"invalid_{field}", f"{where}: {field} is 12 lowercase hex digits"
                                                     + (" or null" if null else ""))
    return value


def _board(value: Any, where: str) -> list[str] | None:
    if value is not None and (not isinstance(value, list) or not 1 <= len(value) <= 64 or any(
            not isinstance(row, str) or not HEX_ROW_RE.fullmatch(row) for row in value)):
        raise ReviewProblem(400, "invalid_board", f"{where}: board is up to 64 rows of hex digits, or null")
    return value


def clean_gtree_bundle(bundle: Any) -> dict[str, Any]:
    """Validate one publication to the universal tree (no database, no disk). Returns {rollouts, screens, nodes,
    steps, traces} ready for SQL; traces as {sha: canonical bytes}. References to nodes and traces outside the body
    are checked against the database and the volume by publish_gtree."""

    if not isinstance(bundle, dict):
        raise ReviewProblem(400, "invalid_body", "send a JSON object")
    lists = {k: bundle.get(k) or [] for k in ("rollouts", "screens", "nodes", "steps")}
    traces = bundle.get("traces") or {}
    if not all(isinstance(x, list) for x in lists.values()) or not isinstance(traces, dict):
        raise ReviewProblem(400, "invalid_body", "rollouts, screens, nodes and steps are lists, traces an object")
    if not lists["rollouts"]:
        raise ReviewProblem(400, "invalid_body", "send at least one rollout")
    if (len(lists["rollouts"]) > MAX_GT_ROLLOUTS or len(lists["screens"]) > MAX_TREE_NODES
            or len(lists["nodes"]) > 4 * MAX_TREE_NODES or len(lists["steps"]) > MAX_TREE_BRANCHES
            or len(traces) > MAX_TREE_TRACES):
        raise ReviewProblem(413, "too_many", f"at most {MAX_GT_ROLLOUTS} rollouts, {MAX_TREE_NODES} screens, "
                                             f"{4 * MAX_TREE_NODES} nodes, {MAX_TREE_BRANCHES} steps, "
                                             f"{MAX_TREE_TRACES} traces per publication")
    clean_traces: dict[str, bytes] = {}
    for sha, content in traces.items():
        _id(sha, "trace_sha", SHA_RE)
        if not isinstance(content, dict) or not isinstance(content.get("turns"), list):
            raise ReviewProblem(400, "invalid_trace", f"trace {sha[:12]} has no turns")
        raw = rl2_trace_bytes(content)
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ReviewProblem(400, "trace_sha_mismatch", f"trace {sha[:12]} does not match the sha256 of its "
                                                           "canonical JSON (sort_keys, no spaces)")
        clean_traces[sha] = raw
    screens: dict[str, dict[str, Any]] = {}
    for sc in lists["screens"]:
        if not isinstance(sc, dict):
            raise ReviewProblem(400, "invalid_screen", "each screen is an object")
        h = _screen(sc.get("screen_hash"), "screen_hash", "a screen")
        board = _board(sc.get("board"), f"screen {h}")
        if h not in screens or screens[h]["board"] is None:
            screens[h] = {"screen_hash": h, "board": board}
    nodes: dict[str, dict[str, Any]] = {}
    for nd in lists["nodes"]:
        if not isinstance(nd, dict):
            raise ReviewProblem(400, "invalid_node", "each node is an object")
        nid = _node_id(nd.get("id"), "node", "a node")
        match = GT_NODE_RE.fullmatch(nid)
        game, tree, root = match.group(1), int(match.group(2)), match.group(3) == "root"
        if nd.get("game", game) != game or nd.get("tree", tree) != tree:
            raise ReviewProblem(400, "invalid_node", f"node {nid}: game and tree must match its id")
        where = f"node {nid}"
        item = {"id": nid, "tree": tree, "game": game, "level": _int(nd.get("level"), "level", null=True),
                "moves": _int(nd.get("moves"), "moves", null=True),
                "screen_hash": _screen(nd.get("screen_hash"), "screen_hash", where, null=True),
                "parent": _node_id(nd.get("parent"), "parent", where, game, 1, null=True),
                "depth": _int(nd.get("depth"), "depth", null=True)}
        if tree != 1 and (item["parent"] is not None or item["depth"] is not None):
            raise ReviewProblem(400, "invalid_node", f"{where}: parent and depth are for tree t1 only")
        if root and (item["screen_hash"] is not None or item["parent"] is not None):
            raise ReviewProblem(400, "invalid_node", f"{where}: a root (the game start) has no screen and no parent")
        if nid in nodes:                                 # the same node twice: the first value of each field wins
            item = {k: nodes[nid][k] if nodes[nid][k] is not None else v for k, v in item.items()}
        nodes[nid] = item
    rollouts: dict[str, dict[str, Any]] = {}
    for ro in lists["rollouts"]:
        if not isinstance(ro, dict):
            raise ReviewProblem(400, "invalid_rollout", "each rollout is an object")
        rid = _id(ro.get("id"), "rollout")
        if rid in rollouts:
            raise ReviewProblem(400, "duplicate_rollout", f"rollout {rid} appears twice")
        game = _id(ro.get("game"), "game", GAME_RE)
        if game in fenced_games():
            # held-out / test-only games never enter the tree: its rollouts are training data
            raise ReviewProblem(400, "fenced_game", f"{game} is a held-out game and is not stored")
        where = f"rollout {rid}"
        origin_kind = ro.get("origin_kind") or "start"
        if origin_kind not in GT_ORIGINS:
            raise ReviewProblem(400, "invalid_origin_kind", f"{where}: origin_kind is one of {', '.join(GT_ORIGINS)}")
        origin_state = ro.get("origin_state")
        if (origin_state is None) != (origin_kind == "start"):
            raise ReviewProblem(400, "invalid_origin", f"{where}: a rollout from the game start has no origin_state; "
                                                       "one started mid-tree names its t1 node and how (origin_kind)")
        if origin_state is not None:
            match = GT_NODE_RE.fullmatch(origin_state) if isinstance(origin_state, str) else None
            if not match:
                raise ReviewProblem(400, "invalid_origin_state", f"{where}: origin_state is a t1 node id")
            if match.group(1) != game or match.group(2) != "1":
                raise ReviewProblem(400, "invalid_origin", f"{where}: origin_state is a t1 node of the same game")
        origin_edge = ro.get("origin_edge")
        if origin_edge is not None:
            if origin_state is None:
                raise ReviewProblem(400, "invalid_origin", f"{where}: origin_edge needs an origin_state")
            _id(origin_edge, "origin_edge", GT_STEP_RE)
        status = ro.get("status") or "finished"
        if not isinstance(status, str) or not GT_STATUS_RE.fullmatch(status):
            raise ReviewProblem(400, "invalid_status", f"{where}: status is 1-40 letters, digits, '_', '.', '-'")
        policy = ro.get("policy")
        rollouts[rid] = {
            "id": rid, "game": game, "run": _id(ro.get("run"), "run"), "build": _id(ro.get("build"), "build", BUILD_RE),
            "model": _id(ro.get("model"), "model"), "harness": _id(ro.get("harness"), "harness"),
            "policy": None if policy in (None, "") else _id(policy, "policy"), "origin_state": origin_state,
            "origin_edge": origin_edge, "origin_kind": origin_kind, "status": status,
            "result": _small(ro.get("result"), "result", where, MAX_GT_RESULT),
        }
    steps: list[dict[str, Any]] = []
    seen: set[str] = set()
    for st in lists["steps"]:
        if not isinstance(st, dict):
            raise ReviewProblem(400, "invalid_step", "each step is an object")
        rid = st.get("rollout_id")
        if not isinstance(rid, str) or rid not in rollouts:
            raise ReviewProblem(400, "unknown_rollout", "each step names a rollout sent in the same publication "
                                                        "(a rollout's steps are replaced whole)")
        seq = _int(st.get("seq"), "seq")
        sid = f"{rid}:{seq}"
        if st.get("id") not in (None, sid):
            raise ReviewProblem(400, "invalid_step", f"a step id is '<rollout id>:<seq>' ({sid})")
        if not GT_STEP_RE.fullmatch(sid):
            raise ReviewProblem(400, "invalid_step", f"step id {sid[:60]} is too long")
        if sid in seen:
            raise ReviewProblem(400, "duplicate_step", f"step {sid} appears twice")
        seen.add(sid)
        game = rollouts[rid]["game"]
        if st.get("game", game) != game:
            raise ReviewProblem(400, "invalid_step", f"step {sid}: game must be its rollout's")
        action = st.get("action")
        if not isinstance(action, str) or not GT_ACTION_RE.fullmatch(action):
            raise ReviewProblem(400, "invalid_action", f"step {sid}: action is 1-40 of A-Z a-z 0-9 _ . : + -")
        trace_sha = st.get("trace_sha")
        if trace_sha is not None:
            _id(trace_sha, "trace_sha", SHA_RE)
        hidden_ref = st.get("hidden_ref")
        if hidden_ref is not None and (not isinstance(hidden_ref, str) or not 1 <= len(hidden_ref) <= MAX_HIDDEN_REF
                                       or any(ord(c) < 32 for c in hidden_ref)):
            raise ReviewProblem(400, "invalid_hidden_ref", f"step {sid}: hidden_ref is one line of text, "
                                                           f"at most {MAX_HIDDEN_REF} characters")
        where = f"step {sid}"
        item = {
            "id": sid, "rollout_id": rid, "seq": seq, "game": game, "level": _int(st.get("level"), "level"),
            "moves": _int(st.get("moves"), "moves"), "screen_hash": _screen(st.get("screen_hash"), "screen_hash", where),
            "next_screen_hash": _screen(st.get("next_screen_hash"), "next_screen_hash", where, null=True),
            "next_level": _int(st.get("next_level"), "next_level", null=True),
            "next_moves": _int(st.get("next_moves"), "next_moves", null=True), "action": action,
            "detail": _small(st.get("detail"), "detail", where), "features": _small(st.get("features"), "features", where),
            "outcome": _small(st.get("outcome"), "outcome", where), "trace_sha": trace_sha, "hidden_ref": hidden_ref,
        }
        for k in GT_TREES:
            item[f"n{k}"] = _node_id(st.get(f"n{k}"), f"n{k}", where, game, k)
            item[f"c{k}"] = _node_id(st.get(f"c{k}"), f"c{k}", where, game, k, null=True)
        if len({item[f"c{k}"] is None for k in GT_TREES}) > 1:
            raise ReviewProblem(400, "invalid_step", f"{where}: c1..c4 are all set or all null (the rollout's end)")
        steps.append(item)
    return {"rollouts": list(rollouts.values()), "screens": list(screens.values()), "nodes": list(nodes.values()),
            "steps": steps, "traces": clean_traces}


def _insert_many(cursor: Any, sql: str, template: str, rows: list[tuple]) -> None:
    """Batched INSERT (psycopg2's execute_values when it is there; plain executemany otherwise)."""

    if not rows:
        return
    try:
        from psycopg2.extras import execute_values
    except ImportError:                                  # pragma: no cover - other drivers
        cursor.executemany(sql.replace("VALUES %s", "VALUES " + template), rows)
        return
    execute_values(cursor, sql, rows, template=template, page_size=1000)


def publish_gtree(cursor: Any, data_root: Path, bundle: Any) -> dict[str, Any]:
    """Store one publication. Idempotent per rollout: screens and nodes are upserted (the first value of each field is
    kept), each rollout row is upserted, its steps are deleted and the new ones inserted; traces are written once by
    sha. Everything is checked before the first write, and the caller's transaction rolls back on any refusal."""

    item = clean_gtree_bundle(bundle)
    store = data_root / "_gtree" / "traces"
    in_body = {n["id"] for n in item["nodes"]}
    named = ({s[f"n{k}"] for s in item["steps"] for k in GT_TREES} | {n["parent"] for n in item["nodes"] if n["parent"]}
             | {r["origin_state"] for r in item["rollouts"] if r["origin_state"]})
    outside = sorted(named - in_body)
    if outside:
        cursor.execute("SELECT id FROM gt_nodes WHERE id = ANY(%s)", (outside,))
        missing = set(outside) - {row[0] for row in cursor.fetchall()}
        if missing:
            raise ReviewProblem(400, "unknown_node", f"steps, nodes or rollouts name nodes that are neither in this "
                                                     f"publication nor stored: {', '.join(sorted(missing)[:5])}")
    for sha in sorted({s["trace_sha"] for s in item["steps"] if s["trace_sha"]} - set(item["traces"])):
        if not (store / f"{sha}.json").exists():
            raise ReviewProblem(400, "unknown_trace", f"trace {sha[:12]} is neither in this publication nor stored")
    _insert_many(
        cursor,
        "INSERT INTO gt_screens (screen_hash, board) VALUES %s "
        "ON CONFLICT (screen_hash) DO UPDATE SET board = COALESCE(gt_screens.board, EXCLUDED.board)",
        "(%s, %s::jsonb)",
        [(s["screen_hash"], None if s["board"] is None else json.dumps(s["board"])) for s in item["screens"]])
    _insert_many(
        cursor,
        "INSERT INTO gt_nodes (id, tree, game, level, moves, screen_hash, parent, depth) VALUES %s "
        "ON CONFLICT (id) DO UPDATE SET level = COALESCE(gt_nodes.level, EXCLUDED.level), "
        "moves = COALESCE(gt_nodes.moves, EXCLUDED.moves), screen_hash = COALESCE(gt_nodes.screen_hash, "
        "EXCLUDED.screen_hash), parent = COALESCE(gt_nodes.parent, EXCLUDED.parent), "
        "depth = COALESCE(gt_nodes.depth, EXCLUDED.depth)",
        "(%s, %s, %s, %s, %s, %s, %s, %s)",
        [(n["id"], n["tree"], n["game"], n["level"], n["moves"], n["screen_hash"], n["parent"], n["depth"])
         for n in item["nodes"]])
    _insert_many(
        cursor,
        "INSERT INTO gt_rollouts (id, game, run, build, model, harness, policy, origin_state, origin_edge, "
        "origin_kind, status, result) VALUES %s ON CONFLICT (id) DO UPDATE SET game = EXCLUDED.game, "
        "run = EXCLUDED.run, build = EXCLUDED.build, model = EXCLUDED.model, harness = EXCLUDED.harness, "
        "policy = EXCLUDED.policy, origin_state = EXCLUDED.origin_state, origin_edge = EXCLUDED.origin_edge, "
        "origin_kind = EXCLUDED.origin_kind, status = EXCLUDED.status, result = EXCLUDED.result, published_at = now()",
        "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
        [(r["id"], r["game"], r["run"], r["build"], r["model"], r["harness"], r["policy"], r["origin_state"],
          r["origin_edge"], r["origin_kind"], r["status"], json.dumps(r["result"])) for r in item["rollouts"]])
    cursor.execute("DELETE FROM gt_steps WHERE rollout_id = ANY(%s)", ([r["id"] for r in item["rollouts"]],))
    replaced = cursor.rowcount
    _insert_many(
        cursor,
        "INSERT INTO gt_steps (id, rollout_id, seq, game, level, moves, screen_hash, next_screen_hash, next_level, "
        "next_moves, action, detail, features, outcome, trace_sha, hidden_ref, n1, n2, n3, n4, c1, c2, c3, c4) "
        "VALUES %s",
        "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, "
        "%s, %s)",
        [(s["id"], s["rollout_id"], s["seq"], s["game"], s["level"], s["moves"], s["screen_hash"],
          s["next_screen_hash"], s["next_level"], s["next_moves"], s["action"], json.dumps(s["detail"]),
          json.dumps(s["features"]), json.dumps(s["outcome"]), s["trace_sha"], s["hidden_ref"],
          s["n1"], s["n2"], s["n3"], s["n4"], s["c1"], s["c2"], s["c3"], s["c4"]) for s in item["steps"]])
    written = 0
    if item["traces"]:
        store.mkdir(parents=True, exist_ok=True)
        for sha, raw in item["traces"].items():
            target = store / f"{sha}.json"
            if target.exists():
                continue
            tmp = store / f".{sha}.{secrets.token_hex(4)}.tmp"
            tmp.write_bytes(raw)
            os.replace(tmp, target)
            written += 1
    return {"apiVersion": 1, "status": "published", "rollouts": len(item["rollouts"]),
            "screens": len(item["screens"]), "nodes": len(item["nodes"]), "steps": len(item["steps"]),
            "stepsReplaced": replaced, "traces": len(item["traces"]), "tracesWritten": written}


def _gt_tree(query: dict[str, list[str]]) -> int:
    raw = (query.get("tree") or ["1"])[0]
    if raw not in ("1", "2", "3", "4"):
        raise ReviewProblem(400, "invalid_tree", "tree is 1, 2, 3 or 4")
    return int(raw)


def gtree_games(cursor: Any) -> list[dict[str, Any]]:
    """Every game: rollouts (and how many started mid-tree), steps, and per tree its node count, deepest level and
    start node: the root '<game>:t<k>:root' when published, else the node with the most steps out at the lowest
    level."""

    cursor.execute("SELECT game, tree, count(*), max(level) FROM gt_nodes GROUP BY game, tree")
    trees: dict[str, dict[int, dict[str, Any]]] = {}
    for game, tree, count, deepest in cursor.fetchall():
        trees.setdefault(game, {})[tree] = {"nodes": count, "deepest": deepest, "root": None}
    cursor.execute("SELECT game, tree, id FROM gt_nodes WHERE id ~ ':root$'")
    for game, tree, nid in cursor.fetchall():
        trees[game][tree]["root"] = nid
    cursor.execute("SELECT game, count(*) FROM gt_steps GROUP BY game")
    steps = dict(cursor.fetchall())
    cursor.execute("SELECT game, count(*), count(*) FILTER (WHERE origin_kind <> 'start') FROM gt_rollouts GROUP BY game")
    rollouts = {game: (n, mid) for game, n, mid in cursor.fetchall()}
    for game, by_tree in trees.items():
        for k, slot in by_tree.items():
            slot["start"] = slot["root"]
            if slot["root"] is None:
                cursor.execute(f"SELECT n{k} FROM gt_steps WHERE game = %s GROUP BY n{k} "
                               f"ORDER BY min(level), count(*) DESC, n{k} LIMIT 1", (game,))
                row = cursor.fetchone()
                slot["start"] = row[0] if row else None
    out = []
    for game in sorted(set(trees) | set(rollouts)):
        n, mid = rollouts.get(game, (0, 0))
        out.append({"game": game, "rollouts": n, "mid_rollouts": mid, "steps": steps.get(game, 0),
                    "trees": {str(k): {**trees.get(game, {}).get(k, {"nodes": 0, "deepest": None, "root": None,
                                                                         "start": None}), "name": GT_TREE_NAMES[k]}
                              for k in GT_TREES}})
    return out


def _mean_stats(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    return {"n": len(outcomes), **{name: _mean([o.get(key) for o in outcomes]) for name, key in GT_OUTCOME_KEYS}}


ROLLOUT_COLUMNS = ("id, game, run, build, model, harness, policy, origin_state, origin_edge, origin_kind, status, "
                   "result, published_at")
STEP_COLUMNS = ("s.id, s.rollout_id, s.seq, s.game, s.level, s.moves, s.screen_hash, s.next_screen_hash, s.next_level, "
                "s.next_moves, s.action, s.detail, s.features, s.outcome, s.trace_sha, s.hidden_ref, "
                "s.n1, s.n2, s.n3, s.n4, s.c1, s.c2, s.c3, s.c4")


def gtree_node(cursor: Any, node_id: str) -> dict[str, Any]:
    """One node of one tree: the node, its screen (a root shows the screen its steps start from), its outgoing steps
    (no trace content) with their rollout's run, build, policy and origin, a summary per action (n, means of lvl30,
    cleared_level, acts, go_turn and level_score with nulls ignored, and the distinct children with counts), the
    nodes that lead here, the rollouts restarted here and, per child, steps out and arrivals."""

    match = GT_NODE_RE.fullmatch(node_id or "")
    if not match:
        raise ReviewProblem(400, "invalid_node", "a node id is '<game>:t<1-4>:<16 hex>' or '<game>:t<1-4>:root'")
    k = int(match.group(2))
    cursor.execute("SELECT id, tree, game, level, moves, screen_hash, parent, depth, first_seen FROM gt_nodes "
                   "WHERE id = %s", (node_id,))
    rows = _rows(cursor)
    if not rows:
        raise ReviewProblem(404, "unknown_node", "no such node")
    node = {**rows[0], "first_seen": iso(rows[0]["first_seen"])}
    cursor.execute(
        f"""
        SELECT {STEP_COLUMNS}, s.c{k} AS child, r.run, r.build, r.model, r.harness, r.policy, r.origin_kind,
               r.origin_state
        FROM gt_steps s JOIN gt_rollouts r ON r.id = s.rollout_id
        WHERE s.n{k} = %s ORDER BY r.run, s.rollout_id, s.seq LIMIT {MAX_NODE_BRANCHES + 1}
        """,
        (node_id,))
    steps = _rows(cursor)
    truncated = len(steps) > MAX_NODE_BRANCHES
    steps = steps[:MAX_NODE_BRANCHES]
    screen = node["screen_hash"]
    if screen is None and steps:                         # a root: the screen its steps start from, most common first
        counts: dict[str, int] = {}
        for s in steps:
            counts[s["screen_hash"]] = counts.get(s["screen_hash"], 0) + 1
        screen = min(counts, key=lambda h: (-counts[h], h))
    board = None
    if screen:
        cursor.execute("SELECT board FROM gt_screens WHERE screen_hash = %s", (screen,))
        row = cursor.fetchone()
        board = row[0] if row else None
    cursor.execute(f"SELECT count(*), count(DISTINCT rollout_id) FROM gt_steps WHERE c{k} = %s", (node_id,))
    arrivals, arrival_rollouts = cursor.fetchone()
    cursor.execute(f"SELECT n{k}, count(*) FROM gt_steps WHERE c{k} = %s GROUP BY n{k} "
                   f"ORDER BY count(*) DESC, n{k} LIMIT 200", (node_id,))
    parents = [{"id": nid, "n": n} for nid, n in cursor.fetchall()]
    cursor.execute(f"SELECT {ROLLOUT_COLUMNS} FROM gt_rollouts WHERE origin_state = %s "
                   "ORDER BY published_at DESC, id LIMIT 200", (node_id,))
    started_here = [{**r, "published_at": iso(r["published_at"])} for r in _rows(cursor)]
    children = sorted({s["child"] for s in steps if s["child"]})
    child_info: dict[str, dict[str, Any]] = {}
    if children:
        cursor.execute(
            f"""
            SELECT c.id, (SELECT count(*) FROM gt_steps x WHERE x.n{k} = c.id) AS steps,
                   (SELECT count(*) FROM gt_steps y WHERE y.c{k} = c.id) AS arrivals,
                   z.id IS NOT NULL AS published, z.level, z.moves, z.screen_hash
            FROM unnest(%s::text[]) AS c(id) LEFT JOIN gt_nodes z ON z.id = c.id
            """,
            (children,))
        child_info = {r["id"]: {key: r[key] for key in ("steps", "arrivals", "published", "level", "moves",
                                                        "screen_hash")} for r in _rows(cursor)}
    for s in steps:
        s["child_info"] = child_info.get(s["child"]) if s["child"] else None
    by_action: dict[str, dict[str, Any]] = {}
    for action in sorted({s["action"] for s in steps}):
        mine = [s for s in steps if s["action"] == action]
        kids: dict[str, int] = {}
        for s in mine:
            if s["child"]:
                kids[s["child"]] = kids.get(s["child"], 0) + 1
        by_action[action] = {**_mean_stats([s["outcome"] or {} for s in mine]),
                             "children": [{"id": c, "n": n} for c, n in sorted(kids.items(), key=lambda x: (-x[1], x[0]))],
                             "ended": sum(1 for s in mine if not s["child"])}
    return {"apiVersion": 1, "tree": k, "tree_name": GT_TREE_NAMES[k],
            "node": {**node, "screen_shown": screen, "board": board, "steps": len(steps), "arrivals": arrivals,
                     "arrival_rollouts": arrival_rollouts},
            "steps": steps, "truncated": truncated, "by_action": by_action, "parents": parents,
            "started_here": started_here}


def gtree_rollout(cursor: Any, rollout_id: str) -> dict[str, Any]:
    cursor.execute(f"SELECT {ROLLOUT_COLUMNS} FROM gt_rollouts WHERE id = %s", (rollout_id,))
    rows = _rows(cursor)
    if not rows:
        raise ReviewProblem(404, "unknown_rollout", "no such rollout")
    cursor.execute(f"SELECT {STEP_COLUMNS} FROM gt_steps s WHERE s.rollout_id = %s ORDER BY s.seq "
                   f"LIMIT {MAX_NODE_BRANCHES + 1}", (rollout_id,))
    steps = _rows(cursor)
    return {"apiVersion": 1, "rollout": {**rows[0], "published_at": iso(rows[0]["published_at"])},
            "steps": steps[:MAX_NODE_BRANCHES], "truncated": len(steps) > MAX_NODE_BRANCHES}


def gtree_stats(cursor: Any) -> dict[str, Any]:
    """Totals: rollouts, steps, games; per tree its nodes and games (every step is in all four trees)."""

    cursor.execute("SELECT count(*), count(DISTINCT game), count(*) FILTER (WHERE origin_kind <> 'start') "
                   "FROM gt_rollouts")
    rollouts, games, mid = cursor.fetchone()
    cursor.execute("SELECT count(*) FROM gt_steps")
    steps = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM gt_screens")
    screens = cursor.fetchone()[0]
    cursor.execute("SELECT tree, count(*), count(DISTINCT game) FROM gt_nodes GROUP BY tree")
    per = {tree: (n, g) for tree, n, g in cursor.fetchall()}
    return {"apiVersion": 1, "rollouts": rollouts, "mid_rollouts": mid, "games": games, "steps": steps,
            "screens": screens,
            "trees": {str(k): {"name": GT_TREE_NAMES[k], "nodes": per.get(k, (0, 0))[0], "games": per.get(k, (0, 0))[1],
                               "steps": steps, "rollouts": rollouts} for k in GT_TREES}}


# Cleared rate of one step, as SQL: outcome.cleared_level as a number (true = 1, false = 0); null when absent.
_CLEARED_SQL = ("CASE jsonb_typeof(s.outcome -> 'cleared_level') "
                "WHEN 'number' THEN (s.outcome ->> 'cleared_level')::double precision "
                "WHEN 'boolean' THEN CASE WHEN (s.outcome ->> 'cleared_level')::boolean THEN 1.0 ELSE 0.0 END END")


def gtree_frontier(cursor: Any, game: str, tree: int = 1, n: int = 4, limit: int = 50,
                   actions: list[str] | None = None) -> dict[str, Any]:
    """Nodes to sample next: the nodes of one tree where some action has fewer than N samples (Go-Explore style
    restarts, up to N per (node, action)). The actions are the ones given, else every action seen in this game. Best
    first by a score of four parts, each returned so the order can be checked:

      few     1 if at most 3 steps leave the node (little explored), else 0
      depth   the node's level / the deepest level of this tree's nodes in the game (a root counts as level 0)
      spread  the gap between the best and the worst action's mean cleared_level there (a choice that matters);
              0 with fewer than two actions that have an outcome
      merge   0.5 if steps from more than one rollout arrive (several plays meet here), else 0

    score = few + depth + spread + merge; ties go to the higher level, then more arrivals, then the id. 'open' lists
    the actions still short of N and how many samples each needs."""

    cursor.execute("SELECT id, level FROM gt_nodes WHERE game = %s AND tree = %s", (game, tree))
    levels = {nid: lvl or 0 for nid, lvl in cursor.fetchall()}
    if not levels:
        raise ReviewProblem(404, "unknown_game", "nothing stored for this game in this tree")
    deepest = max(levels.values()) or 1
    cursor.execute(f"SELECT s.n{tree}, s.action, count(*), avg({_CLEARED_SQL}) FROM gt_steps s WHERE s.game = %s "
                   f"GROUP BY s.n{tree}, s.action", (game,))
    per: dict[str, dict[str, tuple[int, float | None]]] = {}
    for nid, action, count, rate in cursor.fetchall():
        per.setdefault(nid, {})[action] = (count, None if rate is None else float(rate))
    if not actions:
        actions = sorted({a for d in per.values() for a in d})
    cursor.execute(f"SELECT c{tree}, count(*), count(DISTINCT rollout_id) FROM gt_steps "
                   f"WHERE game = %s AND c{tree} IS NOT NULL GROUP BY c{tree}", (game,))
    arrivals = {nid: (count, ro) for nid, count, ro in cursor.fetchall()}
    cursor.execute("SELECT origin_state, count(*) FROM gt_rollouts WHERE game = %s AND origin_state IS NOT NULL "
                   "GROUP BY origin_state", (game,))
    started = dict(cursor.fetchall())
    rows = []
    for nid, level in levels.items():
        here = per.get(nid, {})
        open_ = {a: n - here.get(a, (0, None))[0] for a in actions if here.get(a, (0, None))[0] < n}
        if not open_:
            continue
        n_out = sum(c for c, _ in here.values())
        rates = [r for _, r in here.values() if r is not None]
        arr, arr_ro = arrivals.get(nid, (0, 0))
        parts = {"few": 1.0 if n_out <= 3 else 0.0, "depth": round(level / deepest, 4),
                 "spread": round(max(rates) - min(rates), 4) if len(rates) >= 2 else 0.0,
                 "merge": 0.5 if arr_ro > 1 else 0.0}
        rows.append({"id": nid, "level": level, "out": n_out, "samples": {a: c for a, (c, _) in sorted(here.items())},
                     "open": open_, "missing": sum(open_.values()), "arrivals": arr, "arrival_rollouts": arr_ro,
                     "started_here": started.get(nid, 0), "parts": parts, "score": round(sum(parts.values()), 4)})
    rows.sort(key=lambda x: (-x["score"], -x["level"], -x["arrivals"], x["id"]))
    return {"apiVersion": 1, "game": game, "tree": tree, "tree_name": GT_TREE_NAMES[tree], "N": n,
            "actions": actions, "candidates": len(rows), "deepest": deepest,
            "score": "few (<=3 steps out) + depth (level / deepest) + spread (best - worst action's mean cleared) "
                     "+ merge (0.5 if more than one rollout arrives); only nodes where some action has < N samples",
            "nodes": rows[:limit]}


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
    GTREE = "/api/v1/gtree"

    def __init__(self, connect: Callable[[], Any], data_root: Path, publish_token: str):
        self.connect = connect
        self.data_root = Path(data_root)
        self.publish_token = publish_token
        self.posts = _Limiter(*PUBLIC_POSTS)
        self.gets = _Limiter(*PUBLIC_GETS)

    @classmethod
    def owns(cls, path: str) -> bool:
        return any(path == p or path.startswith(p + "/") for p in (cls.REVIEW, cls.PUBLIC, cls.RL, cls.RL2, cls.GTREE))

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
        # RL2 decision tree: one run's nodes, branches and traces (machines); games, nodes and traces (team).
        if path == f"{self.RL2}/tree/publication":
            self.require_token(headers)
            if method != "PUT":
                raise ReviewProblem(405, "method_not_allowed", "use PUT")
            bundle = self._read_json(read_body, headers, MAX_PUBLICATION)
            clean_tree_bundle(bundle)                      # refuse a bad body before opening a connection
            with self._cursor(commit=True) as cursor:
                result = publish_tree(cursor, self.data_root, bundle)
            print(f"rl2 tree: {result['run']} published {result['branches']} branches at {result['nodes']} nodes",
                  flush=True)
            return _json(200, result)
        if path.startswith(f"{self.RL2}/tree/"):
            self.team_email(headers)
            if method != "GET":
                raise ReviewProblem(405, "method_not_allowed", "use GET")
            sub = path[len(f"{self.RL2}/tree/"):]
            if sub == "games":
                with self._cursor() as cursor:
                    return _json(200, {"apiVersion": 1, "games": tree_games(cursor)})
            if sub.startswith("node/"):
                node_id = sub[len("node/"):]
                if not RL2_NODE_RE.fullmatch(node_id):
                    raise ReviewProblem(400, "invalid_node", "a node id is '<game>:L<level>:<12 hex board hash>'")
                with self._cursor() as cursor:
                    return _json(200, tree_node(cursor, node_id))
            if sub.startswith("trace/"):
                sha = _id(sub[len("trace/"):], "trace_sha", SHA_RE)
                target = self.data_root / "_rl2" / "traces" / f"{sha}.json"
                if not target.exists():
                    raise ReviewProblem(404, "missing_trace", "this trace is not on the server")
                return Response(200, target.read_bytes())
            raise ReviewProblem(404, "not_found", "not found")
        # The universal game tree: publications (machines); games, nodes, rollouts, traces, frontier, stats (team).
        if path == f"{self.GTREE}/publication":
            self.require_token(headers)
            if method != "PUT":
                raise ReviewProblem(405, "method_not_allowed", "use PUT")
            bundle = self._read_json(read_body, headers, MAX_PUBLICATION)
            clean_gtree_bundle(bundle)                     # refuse a bad body before opening a connection
            with self._cursor(commit=True) as cursor:
                result = publish_gtree(cursor, self.data_root, bundle)
            print(f"gtree: published {result['rollouts']} rollouts, {result['steps']} steps, {result['nodes']} nodes",
                  flush=True)
            return _json(200, result)
        if path == self.GTREE or path.startswith(f"{self.GTREE}/"):
            self.team_email(headers)
            if method != "GET":
                raise ReviewProblem(405, "method_not_allowed", "use GET")
            # ids hold ':'; a browser may send it as %3A (each id is checked by its pattern after unquoting)
            sub = unquote(path[len(f"{self.GTREE}/"):]) if path != self.GTREE else ""
            arg = lambda key, default=None: (query.get(key) or [default])[0]  # noqa: E731
            if sub == "games":
                with self._cursor() as cursor:
                    return _json(200, {"apiVersion": 1, "trees": {str(k): v for k, v in GT_TREE_NAMES.items()},
                                       "games": gtree_games(cursor)})
            if sub == "stats":
                with self._cursor() as cursor:
                    return _json(200, gtree_stats(cursor))
            if sub.startswith("node/"):
                node_id = sub[len("node/"):]
                if not GT_NODE_RE.fullmatch(node_id):
                    raise ReviewProblem(400, "invalid_node", "a node id is '<game>:t<1-4>:<16 hex>' or "
                                                             "'<game>:t<1-4>:root'")
                with self._cursor() as cursor:
                    return _json(200, gtree_node(cursor, node_id))
            if sub.startswith("rollout/"):
                rollout_id = _id(sub[len("rollout/"):], "rollout")
                with self._cursor() as cursor:
                    return _json(200, gtree_rollout(cursor, rollout_id))
            if sub.startswith("trace/"):
                sha = _id(sub[len("trace/"):], "trace_sha", SHA_RE)
                target = self.data_root / "_gtree" / "traces" / f"{sha}.json"
                if not target.exists():
                    raise ReviewProblem(404, "missing_trace", "this trace is not on the server")
                return Response(200, target.read_bytes())
            if sub == "frontier":
                game = _id(arg("game"), "game", GAME_RE)
                tree = _gt_tree(query)
                raw_n, raw_limit = arg("N", "4"), arg("limit", "50")
                if not raw_n.isdigit() or not 1 <= int(raw_n) <= MAX_FRONTIER_N:
                    raise ReviewProblem(400, "invalid_N", f"N is 1..{MAX_FRONTIER_N}")
                if not raw_limit.isdigit() or not 1 <= int(raw_limit) <= MAX_FRONTIER:
                    raise ReviewProblem(400, "invalid_limit", f"limit is 1..{MAX_FRONTIER}")
                actions = [a for a in (arg("actions") or "").split(",") if a]
                if len(actions) > 50 or not all(GT_ACTION_RE.fullmatch(a) for a in actions):
                    raise ReviewProblem(400, "invalid_actions", "actions is a comma list of at most 50 action names")
                with self._cursor() as cursor:
                    return _json(200, gtree_frontier(cursor, game, tree, int(raw_n), int(raw_limit), actions or None))
            raise ReviewProblem(404, "not_found", "not found")
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

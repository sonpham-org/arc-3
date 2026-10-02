"""The RL tree: forkable moments, tries, groups and rounds (plan: docs/plans/2026-10-01-rl-on-burst-games.md §6).

Two identities:
- a GAME STATE is a game plus the list of actions from its start. The engine is deterministic under replay, so
  that list rebuilds the board exactly. `state_key` hashes it; values are pooled per state across trajectories.
- a MOMENT is a point in one trajectory: game state PLUS the model's context (its past thinking and notes).
  Tries fork from moments. A moment comes from a scored run (source kind "run") or from inside an earlier try
  (source kind "try"), so the tree grows as tries are played.

Storage: Firestore (database ai-namespace, project cellensml) holds small index documents in four collections;
GCS holds the payloads (exact requests and replies per try) under gs://cellens-ai-artifacts/arc3-rl/<campaign>/.
Each try writes only its own document, so concurrent VMs never fight over a counter; the controller recomputes
group and moment aggregates from the tries (`refresh_moment`).

Two stores, one interface: MemoryStore (tests, dry runs) and FirestoreStore (REST, token from gcloud here or
from the VM metadata server).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence
from urllib.parse import quote

import rl_reward as rr

COLLECTIONS = ("rl_moments", "rl_tries", "rl_groups", "rl_rounds")
GCS_ROOT = "gs://cellens-ai-artifacts/arc3-rl"
TRY_KINDS = ("plain", "hint")
MOMENT_STATUSES = ("open", "saturated", "dead", "closed")

# Never trained, forked or played by RL (plan §1): the fenced test five and the test-only game.
FENCED_GAMES = frozenset({"lf52", "tn36", "re86", "dc22", "su15", "as66"})


def game4(game_id: str) -> str:
    return str(game_id)[:4].lower()


def is_fenced(game_id: str) -> bool:
    return game4(game_id) in FENCED_GAMES


# ------------------------------------------------------------------------------------------------ IDs
def _h(text: str, n: int = 12) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:n]


def state_key(game_id: str, actions: Sequence[str]) -> str:
    """Game state identity: the game plus every action from the start (deterministic replay)."""
    return f"{game4(game_id)}-{_h(str(game_id) + '|' + ','.join(map(str, actions)), 16)}"


def moment_id(source: str, game_id: str, turn: int) -> str:
    """A forkable moment: one trajectory (`source` = run id or try id) at the start of solver turn `turn`."""
    return f"{game4(game_id)}-{_h(source + '|' + str(game_id))}-t{int(turn):04d}"


def group_id(moment: str, policy: str, kind: str, hint_id: str = "") -> str:
    return f"{moment}.{_h(policy, 8)}.{kind}" + (f".{hint_id}" if hint_id else "")


def try_id(group: str, index: int) -> str:
    return f"{group}.{int(index):02d}"


def payload_uri(campaign: str, try_doc_id: str) -> str:
    return f"{GCS_ROOT}/{campaign}/tries/{try_doc_id}.jsonl.gz"


# ------------------------------------------------------------------------------------------------ documents
def new_moment(*, source_kind: str, source: str, game_id: str, level: int, turn: int, action_num: int,
               level_actions_before: int, human_actions: int, n_levels: int, harness: str, policy: str,
               state: str = "", ref_remaining_actions: int | None = None, ref_remaining_tokens: int | None = None,
               ref_cleared: bool | None = None, campaign: str = "", source_uri: str = "",
               parent_moment: str = "") -> dict[str, Any]:
    """A moment document. turn = the solver turn (analysis_step) whose FIRST request is the fork point;
    action_num = the action number at that point (1-based, as the harness counts)."""
    if source_kind not in ("run", "try"):
        raise ValueError(f"source_kind {source_kind!r}")
    if is_fenced(game_id):
        raise ValueError(f"{game_id} is fenced (never forked)")
    doc = {
        "id": moment_id(source, game_id, turn), "campaign": campaign, "game_id": game_id, "game": game4(game_id),
        "level": int(level), "n_levels": int(n_levels), "turn": int(turn), "action_num": int(action_num),
        "level_actions_before": int(level_actions_before), "human_actions": int(human_actions),
        "level_weight": rr.level_weight(int(level), int(n_levels)),
        "state_key": state, "source_kind": source_kind, "source": source, "source_uri": source_uri,
        "parent_moment": parent_moment, "harness": harness, "policy": policy,
        "ref_remaining_actions": ref_remaining_actions, "ref_remaining_tokens": ref_remaining_tokens,
        "ref_cleared": ref_cleared,
        "tries": 0, "clears": 0, "value": None, "best_reward": 0.0, "status": "open",
        "created_at": time.time(), "updated_at": time.time(),
    }
    return doc


def new_try(*, moment: dict, policy: str, kind: str, index: int, vm: str = "", hint_id: str = "",
            campaign: str = "") -> dict[str, Any]:
    if kind not in TRY_KINDS:
        raise ValueError(f"kind {kind!r}")
    g = group_id(moment["id"], policy, kind, hint_id)
    tid = try_id(g, index)
    return {
        "id": tid, "group_id": g, "moment_id": moment["id"], "game": moment["game"], "level": moment["level"],
        "policy": policy, "kind": kind, "hint_id": hint_id, "index": int(index), "vm": vm,
        "campaign": campaign or moment.get("campaign", ""), "status": "running",
        "started_at": time.time(), "finished_at": None,
        "cleared": None, "try_actions": None, "turns": None, "tokens": None, "over_token_cap": None,
        "reward": None, "finish": "", "payload_uri": payload_uri(campaign or moment.get("campaign", "x"), tid),
        "train_use": "", "excluded": False,
    }


def finish_try(doc: dict, *, moment: dict, cleared: bool, try_actions: int, turns: int, tokens: int,
               over_token_cap: bool, finish: str) -> dict:
    """Fill a try's outcome and reward (the scorer's level formula, rl_reward.try_reward)."""
    doc = dict(doc)
    doc.update(status="done", finished_at=time.time(), cleared=bool(cleared), try_actions=int(try_actions),
               turns=int(turns), tokens=int(tokens), over_token_cap=bool(over_token_cap), finish=finish)
    doc["reward"] = rr.try_reward(cleared=cleared, human_actions=moment["human_actions"],
                                  prefix_level_actions=moment["level_actions_before"], try_actions=try_actions,
                                  over_token_cap=over_token_cap)
    return doc


# ------------------------------------------------------------------------------------------------ stores
class MemoryStore:
    def __init__(self):
        self.docs: dict[str, dict[str, dict]] = {c: {} for c in COLLECTIONS}

    def put(self, collection: str, doc: dict) -> None:
        self.docs[collection][doc["id"]] = json.loads(json.dumps(doc))

    def get(self, collection: str, doc_id: str) -> dict | None:
        d = self.docs[collection].get(doc_id)
        return json.loads(json.dumps(d)) if d is not None else None

    def query(self, collection: str, **equals) -> list[dict]:
        return [json.loads(json.dumps(d)) for d in self.docs[collection].values()
                if all(d.get(k) == v for k, v in equals.items())]


class FirestoreStore:
    """REST client on the same database as the run scores (gcp/arc3_firestore_scores.py helpers)."""

    def __init__(self, token_fn: Callable[[], str] | None = None):
        here = Path(__file__).resolve()
        src = next((p / "arc3_firestore_scores.py" for p in (here.parent, *here.parents)
                    if (p / "arc3_firestore_scores.py").exists()), None)
        if src is None:
            raise FileNotFoundError("arc3_firestore_scores.py (ship it next to rl_tree.py on a VM)")
        spec = importlib.util.spec_from_file_location("_arc3_fs_rl", src)
        fs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fs)
        self.fs = fs
        self._token_fn = token_fn or (fs._vm_token if fs._meta("instance/id") else fs._local_token)
        self._tok = ("", 0.0)

    def _token(self) -> str:
        tok, at = self._tok
        if not tok or time.time() - at > 1200:
            self._tok = (self._token_fn(), time.time())
        return self._tok[0]

    def put(self, collection: str, doc: dict) -> None:
        url = f"{self.fs.API}/{collection}/{quote(doc['id'], safe='')}"
        self.fs._call(url, self._token(), {"fields": {k: self.fs._value(v) for k, v in doc.items()}}, method="PATCH")

    def get(self, collection: str, doc_id: str) -> dict | None:
        from urllib.error import HTTPError
        try:
            body = self.fs._call(f"{self.fs.API}/{collection}/{quote(doc_id, safe='')}", self._token())
        except HTTPError as e:
            if e.code == 404:
                return None
            raise
        return {k: self.fs._plain(v) for k, v in (body.get("fields") or {}).items()}

    def query(self, collection: str, **equals) -> list[dict]:
        filters = [{"fieldFilter": {"field": {"fieldPath": k}, "op": "EQUAL", "value": self.fs._value(v)}}
                   for k, v in equals.items()]
        where = ({"compositeFilter": {"op": "AND", "filters": filters}} if len(filters) > 1
                 else filters[0] if filters else None)
        sq = {"from": [{"collectionId": collection}]}
        if where:
            sq["where"] = where
        rows = self.fs._call(f"{self.fs.API}:runQuery", self._token(), {"structuredQuery": sq}, method="POST")
        return [{k: self.fs._plain(v) for k, v in r["document"].get("fields", {}).items()}
                for r in rows if "document" in r]


# ------------------------------------------------------------------------------------------------ aggregates
def refresh_moment(store, moment_id_: str, *, policy: str | None = None, saturate_at: int = 16) -> dict:
    """Recompute a moment's tries / clears / value / best reward and each group's stats from its tries.
    policy=None pools every policy (value of the moment in general); with a policy, only that policy's tries."""
    m = store.get("rl_moments", moment_id_)
    if m is None:
        raise KeyError(moment_id_)
    tries = [t for t in store.query("rl_tries", moment_id=moment_id_) if t.get("status") == "done"]
    if policy is not None:
        tries = [t for t in tries if t.get("policy") == policy]
    groups: dict[str, list[dict]] = {}
    for t in tries:
        groups.setdefault(t["group_id"], []).append(t)
    for gid, ts in groups.items():
        ts.sort(key=lambda t: t["index"])
        st = rr.group_stats([t["reward"] for t in ts])
        store.put("rl_groups", {"id": gid, "moment_id": moment_id_, "game": m["game"], "level": m["level"],
                                "policy": ts[0]["policy"], "kind": ts[0]["kind"], "hint_id": ts[0].get("hint_id", ""),
                                "rewards": [t["reward"] for t in ts], "tries": [t["id"] for t in ts],
                                "updated_at": time.time(), **st})
    plain = [t for t in tries if t["kind"] == "plain"]
    m["tries"] = len(plain)
    m["clears"] = sum(bool(t["cleared"]) and not t.get("over_token_cap") for t in plain)
    m["value"] = (m["clears"] / m["tries"]) if plain else None
    m["best_reward"] = max([t["reward"] for t in tries] or [0.0])
    if m["status"] == "open" and m["tries"] >= saturate_at:
        m["status"] = "saturated"
    if m["tries"] >= 8 and m["clears"] == 0:
        m["status"] = "dead"          # a dead end: candidate for a hint group (plan §4)
    m["updated_at"] = time.time()
    store.put("rl_moments", m)
    return m


# ------------------------------------------------------------------------------------------------ selection
def prior_clear_rate(m: dict, level_clear_given_reached: float | None) -> float:
    """Before any try: the level's measured clear rate given it was reached (frontier.json), raised toward 1
    for moments late in the reference's level (a late moment is closer to the clear)."""
    p = 0.3 if level_clear_given_reached is None else max(0.02, min(0.98, level_clear_given_reached))
    rem, before = m.get("ref_remaining_actions"), m.get("level_actions_before") or 0
    if m.get("ref_cleared") and rem is not None and (rem + before) > 0:
        progress = before / (rem + before)              # 0 = level start, 1 = at the clear
        p = p + (1 - p) * progress ** 2
    return p


def priority(m: dict, prior: float, *, floor: float = 0.02) -> float:
    """Expected learning signal of one more group at this moment: p(1-p) (soft weighting, no hard band: plan §0c
    item 1), times the level's weight in the game score; p Laplace-smoothed with the prior. Moments measured at
    (almost) always-win or always-lose fall below `floor` and are skipped."""
    n, c = m.get("tries") or 0, m.get("clears") or 0
    p = (c + 2 * prior) / (n + 2)
    w = p * (1 - p)
    if n >= 8 and w < floor:
        return 0.0
    return w * (0.5 + m.get("level_weight", 0.1)) / (1 + 0.1 * n)


def select_moments(moments: Iterable[dict], n: int, *, priors: dict[tuple[str, int], float] | None = None,
                   max_game_share: float = 0.15) -> list[dict]:
    """Pick n open moments with the highest priority, at most max_game_share of the pick from any one game
    (variety beats depth here: the hidden games are new games)."""
    priors = priors or {}
    scored = []
    for m in moments:
        if m.get("status") != "open" or is_fenced(m.get("game_id", m.get("game", ""))):
            continue
        pr = prior_clear_rate(m, priors.get((m["game"], m["level"])))
        s = priority(m, pr)
        if s > 0:
            scored.append((s, m))
    scored.sort(key=lambda x: -x[0])
    cap = max(1, int(round(max_game_share * n)))
    per_game: dict[str, int] = {}
    out = []
    for s, m in scored:
        if per_game.get(m["game"], 0) >= cap:
            continue
        per_game[m["game"]] = per_game.get(m["game"], 0) + 1
        out.append(dict(m, priority=s))
        if len(out) >= n:
            break
    return out


def priors_from_frontier(frontier: dict) -> dict[tuple[str, int], float]:
    """P(clear level k | reached k) = reach(k) / reach(k-1), from frontier.json (D:\\codex-work\\rl-20261001)."""
    out = {}
    for g, info in frontier.get("games", {}).items():
        reach = [1.0] + list(info.get("reach") or [])
        for k in range(1, len(reach)):
            if reach[k - 1] > 0:
                out[(g, k)] = reach[k] / reach[k - 1]
    return out


def value_cliffs(moments: Sequence[dict], *, drop: float = 0.4, min_tries: int = 4) -> list[tuple[dict, dict]]:
    """Consecutive measured moments of ONE trajectory and level whose clear rate falls by >= drop: the turn
    between them is where the trajectory went wrong (a teacher-free juncture; plan §6)."""
    by_traj: dict[tuple[str, int], list[dict]] = {}
    for m in moments:
        if (m.get("tries") or 0) >= min_tries and m.get("value") is not None:
            by_traj.setdefault((m["source"], m["level"]), []).append(m)
    cliffs = []
    for ms in by_traj.values():
        ms.sort(key=lambda m: m["turn"])
        for a, b in zip(ms, ms[1:]):
            if a["value"] - b["value"] >= drop:
                cliffs.append((a, b))
    return cliffs

"""Mid-tree rollouts for Daniel's notebook harness: the pure part (no harness imports, no cloud).

Author: Claude Opus 5.5 (3-Oct-2026, Son: "sampling from the middle of the tree and then roll out"; restart nodes per
(state, action) capped at N; "store history so a live RL agent can quickly prefill the context up to that point").

A JOB restarts one logged play at the start of one of its steps (a universal-tree node) and plays it on live, K times:

  {"job_id": "j-0001", "campaign": "dev",
   "game_id": "sb26-7fbdac44", "pass": 0,                        # the engine env id and the source play's pass
   "source": {"run": "<run>", "rollout_id": "<run>:sb26_p0",     # the universal-tree rollout restarted from
              "requests": "<path of the play's _requests.jsonl>", # replay_exact: the exact model calls (fork_replay)
              "events": "<path of the play's _events.jsonl>",     # replay_actions (and origin facts): the moves
              "coach_log": "<path of the run's coach-decisions.jsonl>" | null},   # a coached source: its decisions
   "origin": {"seq": 12, "turn": 14,                             # tree step seq and its analysis_step (either; seq
                                                                 #   needs the events to find the turn)
              "t1": "<game>:t1:<16 hex>", "screen_hash": "<12 hex>", "level": 2, "actions_before": 57},
   "mode": "replay_exact" | "replay_actions",
   "tries": 4,
   "stop": {"move_budget": null, "budget_x": 2.0, "budget_default": 200, "turn_cap": 40, "token_cap": null,
            "stop_on_game_over": true},
   "coach": {"spec": "policy" | "off" | "rules" | "force:<mode>" | "random:<p>", "cap": null | "4" | "none"}}

replay_exact   the harness is re-run turn by turn up to the origin with a fake model that returns each logged reply
               with its logged usage (fork_replay.load_sequence), so every bit of harness state is rebuilt; every
               rebuilt request is compared with the logged one (clock readings masked) and the first divergence
               stops the try. The origin's first request is sent with the logged messages (fork_replay's rule).
replay_actions only the game moves are replayed through the engine, then the model starts from a fresh context.

Everything here is pure Python and runs anywhere; rollout_driver.py uses it inside the notebook, tests use it on
logged plays. The step records come from gtree-ingest (gtree_build.build_play) on the try's own event log, so a
rollout's steps have exactly the ingest's format and node ids (t1 ids of the replayed prefix equal the source's).
"""
from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def _ingest_dir() -> Path:
    for d in (os.environ.get("GTREE_INGEST_DIR"), HERE / "ingest", HERE.parent / "gtree-ingest"):
        if d and (Path(d) / "gtree_build.py").exists():
            return Path(d)
    raise FileNotFoundError("gtree-ingest not found (GTREE_INGEST_DIR, ./ingest or ../gtree-ingest)")


_ING = _ingest_dir()
if str(_ING) not in sys.path:
    sys.path.insert(0, str(_ING))
import deps  # noqa: E402  (gtree-ingest: trace_review_index, fork_replay, rl_reward, observer)
import gtree_build as gb  # noqa: E402
import gtree_ctx as gc  # noqa: E402
from gtree_store import Store  # noqa: E402

fr = deps.fork_replay
tri = deps.tri

MODES = ("replay_exact", "replay_actions", "snapshot")
DEFAULT_STOP = {"move_budget": None, "budget_x": 2.0, "budget_default": 200, "turn_cap": 40, "token_cap": None,
                "stop_on_game_over": True}
FENCED = frozenset(gb.FENCED)
# the turn coach's line, appended to the fresh turn opener's text (variants/coach/arc3_coach.py _HEAD + one line)
COACH_TAIL = re.compile(r"\n\nFocus for this turn: [^\n]*")
GRID_CAPTION = "Current grid image"     # "...:" or, after a game over, "... (the board AFTER the automatic reset ...):"
MOUSE_RE = re.compile(r"^MOUSE\(row=(\d+), col=(\d+)\)$")
# coach log fields copied into a rollout step's detail (arc3_coach.Coach.decide rows; RL rollout server)
DECISION_FIELDS = ("policy", "policy_seq", "policy_prob", "policy_dist", "assigned", "design_prob", "cap_choice",
                   "cap_prob", "assign_job", "assign_try", "assign_anchor", "assign_picker_policy_prob")


# ------------------------------------------------------------------------------------------------ jobs
def normalize_job(job: dict) -> dict:
    """A job with defaults filled in; ValueError on anything malformed."""
    j = copy.deepcopy(job)
    for key in ("job_id", "game_id"):
        if not isinstance(j.get(key), str) or not j[key]:
            raise ValueError(f"job needs {key}")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._~-]{0,80}", j["job_id"]):
        raise ValueError("job_id: 1-81 of A-Z a-z 0-9 . _ ~ -")
    j["game"] = j["game_id"].split("-")[0]
    j["pass"] = int(j.get("pass") or 0)
    j["mode"] = j.get("mode") or "replay_exact"
    if j["mode"] not in MODES:
        raise ValueError(f"mode is one of {MODES}")
    j["tries"] = max(1, int(j.get("tries") or 1))
    j["campaign"] = str(j.get("campaign") or "dev")
    src = j.setdefault("source", {})
    src.setdefault("run", "unknown")
    src.setdefault("rollout_id", None)
    if j["mode"] == "replay_exact" and not src.get("requests"):
        raise ValueError("replay_exact needs source.requests (the play's request log)")
    if j["mode"] == "replay_actions" and not src.get("events"):
        raise ValueError("replay_actions needs source.events (the play's event log)")
    if j["mode"] == "snapshot" and not src.get("state"):
        raise ValueError("snapshot needs source.state (a local arc3_state snapshot file)")
    o = j.setdefault("origin", {})
    if o.get("turn") is None and o.get("seq") is None:
        raise ValueError("origin needs turn (analysis_step) or seq (tree step)")
    if j.get("assignments"):            # sibling job (pick_nodes.py): one assignment per try, try k = assignments[k]
        if [a.get("k") for a in j["assignments"]] != list(range(len(j["assignments"]))):
            raise ValueError("assignments must be listed in try order with k = 0..K-1")
        j["tries"] = len(j["assignments"])
    j["stop"] = {**DEFAULT_STOP, **(j.get("stop") or {})}
    j["replay_tolerate_near"] = bool(j.get("replay_tolerate_near", False))   # default: any text difference stops
    c = j.get("coach") or {}
    j["coach"] = {"spec": str(c.get("spec") or "off"), "cap": c.get("cap")}
    return j


def coach_spec(job: dict) -> str:
    """The coach spec the live phase plays ('' = stock harness), as arc3_coach.policy_spec reads it."""
    raw = str(job["coach"]["spec"]).strip().lower()
    return "" if raw in ("", "0", "off", "none") else raw


def read_lines(path: str | Path | None) -> list[str]:
    if not path:
        return []
    return Path(path).read_text(encoding="utf-8").splitlines()


# ------------------------------------------------------------------------------------------------ the source play
def board_hash(grid: Any) -> str:
    """trace_review_index.board_hash over the viewer event's board ([list(row) for row in frame.grid])."""
    return tri.board_hash([list(map(int, row)) for row in grid])


def play_steps(events: list[str]) -> tuple[dict | None, list[dict], list[dict], list[tuple]]:
    """(initial, acts, steps, states) of one logged play, segmented exactly as the ingest does."""
    initial, acts, _turns = tri.read_play(events)
    if initial is None:
        return None, [], [], []
    steps = gb.segment(acts)
    steps = gb.split_at_clears(steps, [None] * len(steps), acts)[0]     # a turn that clears a level mid-batch
    return initial, acts, steps, gb.replay_states(initial, acts)


def t1_ids(game: str, steps: list[dict], states: list[tuple]) -> list[str]:
    """The t1 node of every step (gtree_build.build_play's chain: root, then [parent t1, level, screen, moves])."""
    ids: list[str] = []
    for j, st in enumerate(steps):
        if j == 0:
            ids.append(gb.node_id(game, 1, None))
            continue
        board, level, moves = states[st["s"]]
        ids.append(gb.node_id(game, 1, gb.tree_keys(ids[-1], level, tri.board_hash(board), moves)[1]))
    return ids


def origin_facts(job: dict, events: list[str]) -> dict:
    """From the source's event log: the origin step's turn, t1 node, screen, level, moves before it (action count),
    and the action prefix that reaches it (each {name, display, data, automatic, turn})."""
    initial, acts, steps, states = play_steps(events)
    if initial is None:
        raise ValueError("source event log has no initial event")
    o = job["origin"]
    if o.get("seq") is not None:
        j = int(o["seq"]) - 1
    else:
        j = next((i for i, st in enumerate(steps) if st["turn"] == int(o["turn"])), None)
        if j is None:
            raise ValueError(f"turn {o['turn']} starts no step of the source play")
    if not 0 <= j < len(steps):
        raise ValueError(f"origin seq {j + 1} outside the play's {len(steps)} steps")
    st = steps[j]
    board, level, _moves = states[st["s"]]
    t1 = t1_ids(job["game"], steps, states)[j]
    prefix = []
    for i, a in enumerate(acts[:st["s"]]):
        prefix.append({"name": str(a.get("action_name") or "").upper(), "display": a.get("action_display"),
                       "data": action_data(a), "automatic": gb.automatic(acts, i),
                       "turn": int(a.get("analysis_step") or 0), "game_over": gb._true(a.get("game_over"))})
    part = int(st.get("part") or 1)
    if part > 1 and job["mode"] == "replay_exact":
        raise ValueError(f"step {j + 1} starts mid-turn (part {part} of turn {st['turn']}, after a level clear): no "
                         "logged context there, use replay_actions")
    return {"seq": j + 1, "turn": int(st["turn"]), "part": part,
            # the live play's first turn number: a mid-turn origin's turn already carries the prefix's moves
            "live_turn": int(st["turn"]) + (1 if part > 1 else 0),
            "t1": t1, "screen_hash": tri.board_hash(board),
            "level": int(level), "actions_before": int(st["s"]), "prefix": prefix,
            "lead_resets": sum(1 for p in prefix if p["automatic"] and p["turn"] == 0)}


def action_data(event: dict) -> dict:
    """Engine data of a logged action (the event keeps only the display for a click: MOUSE(row=r, col=c))."""
    name = str(event.get("action_name") or "").upper()
    if name != "ACTION6":
        return {}
    m = MOUSE_RE.match(str(event.get("action_display") or ""))
    if not m:
        raise ValueError(f"click without coordinates: {event.get('action_display')!r}")
    return {"x": int(m.group(2)), "y": int(m.group(1))}


def lead_resets_from_requests(seq: list[dict]) -> int:
    """Automatic RESETs before the first model turn (the notebook's warmup RESET): the first request's displayed
    action number is action_count + 1."""
    return max(0, int(seq[0].get("action") or 1) - 1) if seq else 0


# ------------------------------------------------------------------------------------------------ replay plan
class ReplayPlan:
    """The logged model calls of one play up to the origin turn (fork_replay.load_sequence rows)."""

    def __init__(self, seq: list[dict], origin_turn: int):
        self.seq = seq
        self.origin_turn = int(origin_turn)
        self.origin_index = next((i for i, r in enumerate(seq) if r["step"] >= self.origin_turn), None)
        if self.origin_index is None:
            raise ValueError(f"the request log ends before turn {origin_turn}")
        first = seq[self.origin_index]
        if first["step"] != self.origin_turn or first["idx"] != 1:
            raise ValueError(f"turn {origin_turn} has no first request in the log (next is step {first['step']} "
                             f"idx {first['idx']})")
        bad = [(r["step"], r["idx"]) for r in seq[:self.origin_index] if r["reply"] is None and not r["failed"]]
        if bad:
            raise ValueError(f"logged calls before the origin without a reply: {bad[:5]}")

    def failure_kind(self, i: int) -> str:
        """How a logged call with no response failed: context_overflow (the harness trimmed and retried inside the
        turn), timeout_yield (read timeout, the turn's exchanges kept), or request_error (the turn rolled back)."""
        r, nxt = self.seq[i], self.seq[i + 1] if i + 1 < len(self.seq) else None
        if nxt is None:
            return "request_error"
        if nxt["step"] == r["step"] and nxt["idx"] == r["idx"] + 1:
            return "context_overflow"
        if nxt["step"] == r["step"] and nxt["idx"] == 1 and len(nxt["messages"]) > len(r["messages"]) \
                and fr.compare(nxt["messages"][:len(r["messages"])], r["messages"])["verdict"] in ("exact", "clock"):
            return "timeout_yield"
        return "request_error"

    def yields_after(self, i: int) -> bool:
        """The analyze call ended after call i without a move (the next call resumes the same turn)."""
        nxt = self.seq[i + 1] if i + 1 < len(self.seq) else None
        return nxt is not None and nxt["step"] == self.seq[i]["step"] and nxt["idx"] == 1


def load_plan(requests_path: str | Path, origin_turn: int) -> ReplayPlan:
    return ReplayPlan(fr.load_sequence(requests_path), origin_turn)


# ------------------------------------------------------------------------------------------------ comparing contexts
def roundtrip(messages: list[dict]) -> list[dict]:
    """The request log's copy of a message list (analyze logs json.loads(json.dumps(messages)))."""
    return json.loads(json.dumps(messages))


_PIXELS: dict[str, str] = {}
# verdicts that mean "the model saw the same thing" (clock readings masked, images compared by pixels)
SAME = ("exact", "clock", "pixels", "pixels+clock")


def _pixel_key(url: str) -> str:
    """An image data URL as what the model sees: size + mode + sha256 of the decoded pixels. Two PNG encoders
    (Pillow versions: this PC's vs Kaggle's image) write different bytes for the same pixels."""
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()
    if h not in _PIXELS:
        try:
            from PIL import Image  # noqa: PLC0415
            img = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
            img.load()
            _PIXELS[h] = f"pixels:{img.size[0]}x{img.size[1]}:{img.mode}:" + hashlib.sha256(img.tobytes()).hexdigest()
        except Exception:                        # noqa: BLE001 - not an image we can read: compare the bytes
            _PIXELS[h] = "bytes:" + h
    return _PIXELS[h]


def pixel_normal(messages: list[dict]) -> list[dict]:
    out = []
    for m in messages:
        c = m.get("content")
        if isinstance(c, list):
            parts = []
            for p in c:
                iu = p.get("image_url") if isinstance(p, dict) and p.get("type") == "image_url" else None
                if isinstance(iu, dict) and str(iu.get("url", "")).startswith("data:image"):
                    p = {**p, "image_url": {**iu, "url": _pixel_key(iu["url"])}}
                parts.append(p)
            m = {**m, "content": parts}
        out.append(m)
    return out


def compare(sent: list[dict], logged: list[dict]) -> dict:
    """fork_replay.compare, then once more with images compared by their pixels: 'pixels' = the same text and the
    same pixels, the images only encoded differently ('pixels+clock' when clock readings differ too)."""
    v = fr.compare(sent, logged)
    if v["verdict"] in ("exact", "clock"):
        return v
    w = fr.compare(pixel_normal(sent), pixel_normal(logged))
    if w["verdict"] == "exact":
        return {"verdict": "pixels"}
    if w["verdict"] == "clock":
        return {"verdict": "pixels+clock"}
    return w


def split_tail(messages: list[dict]) -> tuple[list[dict], str]:
    """The message list without the coach's focus line in the last user message, and that line ('' if none)."""
    msgs = copy.deepcopy(messages)
    if not msgs or msgs[-1].get("role") != "user":
        return msgs, ""
    last = msgs[-1]
    c = last.get("content")
    if isinstance(c, str):
        m = COACH_TAIL.search(c)
        if m:
            last["content"] = c[:m.start()] + c[m.end():]
            return msgs, m.group(0)
        return msgs, ""
    if isinstance(c, list):
        for part in c:
            if isinstance(part, dict) and part.get("type") == "text":
                m = COACH_TAIL.search(part.get("text") or "")
                if m:
                    part["text"] = part["text"][:m.start()] + part["text"][m.end():]
                    return msgs, m.group(0)
    return msgs, ""


def _insert_tail(messages: list[dict], tail: str) -> list[dict]:
    """Put a coach line where the harness puts it: the end of the user prompt, i.e. before the grid caption."""
    if not tail:
        return messages
    msgs = copy.deepcopy(messages)
    last = msgs[-1]
    c = last.get("content")
    if isinstance(c, str):
        k = c.rfind("\n\n" + GRID_CAPTION)
        last["content"] = c[:k] + tail + c[k:] if k >= 0 else c + tail
        return msgs
    for part in c:
        if isinstance(part, dict) and part.get("type") == "text":
            t = part.get("text") or ""
            k = t.rfind("\n\n" + GRID_CAPTION)
            part["text"] = t[:k] + tail + t[k:] if k >= 0 else t + tail
            return msgs
    return msgs


def origin_request(built: list[dict], logged: list[dict]) -> tuple[dict, list[dict], dict]:
    """The origin's first request: (verdict of built vs logged with coach lines removed, the messages to send, info).
    Sent = the logged messages (so clock readings are the source's) with the live coach line in place of the
    source's; the harness keeps its own list for the requests after it."""
    b, new_tail = split_tail(roundtrip(built))
    lg, old_tail = split_tail(logged)
    verdict = compare(b, lg)
    send = _insert_tail(lg, new_tail)
    return verdict, send, {"tail_live": new_tail.strip(), "tail_source": old_tail.strip()}


def digest(messages: list[dict]) -> str:
    """sha256 of a message list with clock readings masked and the coach line removed: equal digests = the same
    restored context."""
    return hashlib.sha256(fr.masked(pixel_normal(split_tail(roundtrip(messages))[0])).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------------ boards in requests
def opener_image_url(messages: list[dict]) -> str | None:
    """The 'Current grid image' data URL of a turn opener (the board the turn starts from)."""
    if not messages or messages[-1].get("role") != "user" or not isinstance(messages[-1].get("content"), list):
        return None
    parts = messages[-1]["content"]
    for a, b in zip(parts, parts[1:]):
        last = (a.get("text") or "").rstrip().rsplit("\n", 1)[-1] if a.get("type") == "text" else ""
        if last.startswith(GRID_CAPTION) and last.endswith(":") and b.get("type") == "image_url":
            return (b.get("image_url") or {}).get("url")
    return None


def decode_board(url: str, palette: dict[int, tuple[int, int, int]], size: int = 64) -> list[list[int]]:
    """A board from the harness's grid image (flat exact-palette blocks, MULTIMODAL_UPSCALE per cell)."""
    from PIL import Image  # noqa: PLC0415 (the harness ships Pillow)
    raw = base64.b64decode(url.split(",", 1)[1])
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = img.size
    s = w // size
    if s < 1 or h // s != size:
        raise ValueError(f"grid image {w}x{h} is not a {size}x{size} board")
    inverse: dict[tuple, int] = {}
    for k, rgb in sorted(palette.items()):
        inverse.setdefault(tuple(rgb), int(k))
    px = img.load()
    out = []
    for r in range(size):
        row = []
        for c in range(size):
            rgb = tuple(px[c * s + s // 2, r * s + s // 2])
            if rgb not in inverse:
                raise ValueError(f"off-palette pixel {rgb} at cell ({r}, {c})")
            row.append(inverse[rgb])
        out.append(row)
    return out


def logged_screen_hash(messages: list[dict], palette: dict) -> str | None:
    url = opener_image_url(messages)
    return board_hash(decode_board(url, palette)) if url else None


# ------------------------------------------------------------------------------------------------ stop rule
def move_budget(stop: dict, baselines: list[int] | None, level: int) -> int:
    """Moves a try may make from the origin: stop.move_budget, else budget_x x the level's human baseline, else
    budget_default."""
    if stop.get("move_budget"):
        return int(stop["move_budget"])
    if baselines and 0 < level <= len(baselines) and baselines[level - 1]:
        return max(1, int(round(float(stop.get("budget_x") or 2.0) * int(baselines[level - 1]))))
    return int(stop.get("budget_default") or 200)


# ------------------------------------------------------------------------------------------------ records
def _find_one(root: Path, pattern: str) -> Path | None:
    hits = sorted(root.glob(pattern))
    return hits[0] if hits else None


def coach_rows(path: str | Path | None, key: str) -> list[dict]:
    """A coach log's decisions for one game session (rows whose 'game' is that session's state path)."""
    rows = []
    for line in read_lines(path) if path and Path(path).exists() else []:
        if not line.strip():
            continue
        r = json.loads(line)
        if str(r.get("game")) == key:
            rows.append(r)
    rows.sort(key=lambda r: r.get("decision") or 0)
    return rows


def rollout_records(job: dict, try_dir: str | Path, k: int, result: dict, *, store_root: str | None = None,
                    build: str = "gtree-rollout", model: str = "flash-next-w4a16", harness: str = "daniel-notebook",
                    allow_fenced: bool = False) -> dict:
    """One try as universal-tree records: {rollout, steps, traces, screens, nodes, report} in the ingest's format.

    The try's own event log (it starts at the game start: the replayed prefix is in it) goes through
    gtree_build.build_play; the steps from the origin on are kept and renumbered from 1. Their node ids are the
    tree's (the prefix replays the source's states, so the origin step's t1 id is the source's: report.t1_match).
    Contexts (ctx_before / ctx_after) are written to store_root (default <try_dir>/gtree-store) from the try's
    request log. allow_fenced: tests on a held-out game only (records stay local; publishing refuses them)."""
    try_dir = Path(try_dir)
    gid, ps = job["game_id"], job["pass"]
    ev = _find_one(try_dir / "artifacts", f"{gid}_p{ps}_events.jsonl")
    if ev is None:
        raise FileNotFoundError(f"no event log in {try_dir / 'artifacts'}")
    events = ev.read_text(encoding="utf-8").splitlines()
    req = try_dir / "requests.jsonl"
    if not req.exists():
        req = _find_one(try_dir, f"{gid}_p{ps}_requests.jsonl") or req
    contexts_fn, tokens, final_turn, ctx_rep = None, None, None, {}
    store = Store(store_root or str(try_dir / "gtree-store"))
    if req.exists():
        first, tokens, final_turn = gc.read_requests(req)
        blobs = gc.Blobs(store)

        def contexts_fn(turns, _first=first):
            shas, rep = gc.write_chain([_first.get(t) if t is not None else None for t in turns], store, blobs)
            ctx_rep.update(rep)
            return shas
    run = f"gtr-{job['campaign']}"
    rid = f"{run}:{job['game']}_p{ps}.{job['job_id']}.k{k}"
    decisions = coach_rows(result.get("coach_log"), result.get("state_path") or "") or None
    old = gb.FENCED
    if allow_fenced:
        gb.FENCED = frozenset()
    try:
        play = gb.build_play(run=run, game_id=gid, ps=ps, events=events, decisions=decisions, rollout_id=rid,
                             build=build, model=model, harness=harness,
                             policy=(coach_spec(job) + (f"@{result['policy_version']}" if result.get("policy_version")
                                                        else "")) or None,
                             final_turn=final_turn, contexts=contexts_fn, tokens=tokens)
    finally:
        gb.FENCED = old
    if not play["rollout"]:
        raise ValueError("the try's event log is empty")
    turn = int(result["origin"]["turn"])
    at = int(result["origin"]["actions_before"])      # the origin step = the step that starts after `at` moves
    at -= int(result["origin"].get("lead_in_origin") or 0)   # a warmup RESET is segmented into the play's first step
    j0, done = None, 0
    for j, s in enumerate(play["steps"]):
        if done == at:
            j0 = j
            break
        done += int(s["moves_step"])
    if j0 is None:
        raise ValueError(f"no step of the try starts after {at} moves (the origin)")
    kept = []
    by_decision = {int(d["decision"]): d for d in decisions or [] if d.get("decision") is not None}
    snaps: dict[int, str] = {}                 # turn -> state snapshot sha (arc3_state: origin capture, turn hook)
    sidx = try_dir / "state" / "index.jsonl"
    for line in read_lines(sidx) if sidx.exists() else []:
        if line.strip():
            x = json.loads(line)
            snaps[int(x["analysis_step"])] = x["sha"]
    if job["mode"] == "snapshot" and job["source"].get("state_ref"):
        snaps.setdefault(turn, job["source"]["state_ref"])
    for n, s in enumerate(play["steps"][j0:], start=1):
        s = dict(s, seq=n, id=f"{rid}:{n}")
        d = by_decision.get(int((s.get("detail") or {}).get("decision") or -1)) \
            if (s.get("detail") or {}).get("source") == "coach" else None
        if d is not None:      # the RL fields of the decision: policy version + probabilities, the assignment
            s["detail"] = {**s["detail"], **{x: d[x] for x in DECISION_FIELDS if x in d}}
        dt = s.get("detail") or {}
        if int(dt.get("part") or 1) == 1 and dt.get("turn") is not None and int(dt["turn"]) in snaps:
            s["state_ref"] = snaps[int(dt["turn"])]
        kept.append(s)
    used = {s["trace_sha"] for s in kept if s["trace_sha"]}
    screens = {h: b for h, b in play["screens"].items()
               if h in {s["screen_hash"] for s in kept} | {s["next_screen_hash"] for s in kept}}
    o = job["origin"]
    origin_t1 = o.get("t1") or kept[0]["n1"]
    origin_seq = o.get("seq") or result["origin"].get("seq")
    src_rid = job["source"].get("rollout_id")
    rollout = dict(play["rollout"])
    rollout.update(origin_state=origin_t1, origin_kind=job["mode"],
                   origin_edge=f"{src_rid}:{int(origin_seq) - 1}" if src_rid and origin_seq and int(origin_seq) > 1
                   else None,
                   status=result.get("stop_reason") or "finished",
                   result={**rollout["result"], **{x: result.get(x) for x in ("cleared", "moves_to_clear", "turns",
                                                                                "tokens", "moves", "stop_reason")},
                           "job": job["job_id"], "try": k, "source_rollout": src_rid, "origin_seq": origin_seq,
                           "origin_turn": turn, "origin_actions_before": at, "round": job.get("round"),
                           "assignment": result.get("assignment"), "policy_version": result.get("policy_version"),
                           "first_live": result.get("first_live"), "restore_s": result.get("restore_s"),
                           "fork": result.get("fork")})
    report = {"t1_match": kept[0]["n1"] == origin_t1, "origin_n1": kept[0]["n1"], "origin_t1": origin_t1,
              "steps_total": len(play["steps"]), "steps_kept": len(kept), "ctx": ctx_rep, **play["report"]}
    # where each snapshot of this try restores: the kept step it starts (the origin's also under the source play)
    state_refs = [{"sha": s["state_ref"], "rollout_id": rid, "seq": s["seq"], "t1": s["n1"], "turn": s["detail"]["turn"],
                   "game_id": gid, "pass": ps, "screen_hash": s["screen_hash"], "level": s["level"],
                   "ctx_before": s.get("ctx_before")} for s in kept if s.get("state_ref")]
    if kept and kept[0].get("state_ref") and src_rid and origin_seq:
        state_refs.append({**state_refs[0], "rollout_id": src_rid, "seq": int(origin_seq), "t1": origin_t1})
    return {"rollout": rollout, "steps": kept, "traces": {k2: v for k2, v in play["traces"].items() if k2 in used},
            "screens": screens, "nodes": play["nodes"], "report": report, "state_refs": state_refs}


def write_records(rec: dict, path: str | Path) -> None:
    """The master-copy shape of the ingest (one rollout line, its steps, traces, screens, nodes), uncompressed."""
    lines = [{"kind": "rollout", **rec["rollout"]}]
    lines += [{"kind": "step", **s} for s in rec["steps"]]
    lines += [{"kind": "trace", "sha": k, "content": v} for k, v in rec["traces"].items()]
    lines += [{"kind": "screen", "screen_hash": h, "board": b} for h, b in rec["screens"].items()]
    lines += [{"kind": "node", **n} for n in rec["nodes"].values()]
    lines += [{"kind": "report", **rec["report"]}]
    Path(path).write_text("\n".join(json.dumps(x, separators=(",", ":")) for x in lines) + "\n", encoding="utf-8")


def publishable(rec: dict) -> bool:
    """Held-out games never leave the machine."""
    return rec["rollout"]["game"] not in FENCED


def master_name(rec: dict) -> str:
    """The try's master file under rollouts/<run>/ (ingest naming: the rollout id without '<run>:')."""
    rid, run = rec["rollout"]["id"], rec["rollout"]["run"]
    return f"rollouts/{run}/{rid[len(run) + 1:]}.jsonl.gz"


def write_master(rec: dict, path: str | Path) -> None:
    """The ingest's master copy (gzip; rollout, steps, traces, screens, nodes: ingest.master_lines' order)."""
    import gzip
    lines = [{"kind": "rollout", **rec["rollout"]}]
    lines += [{"kind": "step", **s} for s in rec["steps"]]
    lines += [{"kind": "trace", "sha": k, "content": v} for k, v in rec["traces"].items()]
    lines += [{"kind": "screen", "screen_hash": h, "board": b} for h, b in rec["screens"].items()]
    lines += [{"kind": "node", **n} for n in rec["nodes"].values()]
    raw = "\n".join(json.dumps(x, separators=(",", ":")) for x in lines).encode("utf-8")
    Path(path).write_bytes(gzip.compress(raw, 6))

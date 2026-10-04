"""RL v1 training records from rollout-server tries (4-Oct-2026, Son: "you don't just play the games better from the
beginning, you also try to play the game better from everywhere").

A rollout-server job is one node (a saved game moment) and K sibling tries from it, all with the same context up to the
moment. Each try plays on until its level clears, its move budget runs out, or the run's deadline cuts it. Here:

  reward     the scorer's level score of the try: min(1.15, (human / actions)^2), actions = the level's actions before
             the moment plus the try's own until the clear (rl_reward.try_reward); 0 when the level did not clear.
             (The master record's outcome.level_score leaves out the actions before the moment; within one job the
             order is the same, but this one is the Kaggle number, as in g0_data's level advantages.)
  advantage  reward minus the mean reward of the job's finished tries (Dr. GRPO, no division by the spread). A job
             whose finished tries all scored the same teaches nothing and gives no records.
  records    build_records.segments / record_from_segment over the try's own request log, training only the replies
             the try produced (analysis_step >= the moment's turn), each weighted by the try's advantage. The harness
             logs requests but not replies; rollout_driver (4-Oct) writes replies.jsonl, which puts each stretch's
             last reply (the clearing turn, when it cleared) back into its record. Older tries lose that last reply.

Tries cut by the deadline, diverged or aborted ones, and (with --modes) tries with any turn outside the given modes
are left out before the means. Output: one .jsonl.gz of candidate records, for select_records.py.

  python try_records.py --tries /opt/m/work/tries/v1r1 --out /opt/m/work/tries/v1r1-cand.jsonl.gz --modes stock
  python select_records.py --in /opt/m/work/tries/v1r1-cand.jsonl.gz --out /opt/m/work/records/110 --budget 64
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_records as br  # noqa: E402
import rl_reward as rr  # noqa: E402

GAME_RE = re.compile(r"([a-z0-9]{4}-[0-9a-f]{8})")


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    op = gzip.open if path.suffix == ".gz" else open
    out = []
    with op(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:            # a cut last line (copied while the try was writing)
                    pass
    return out


def load_try(d: Path) -> dict | None:
    """One try dir -> {result, steps, coach, requests, replies}; None without result.json."""
    rf = d / "result.json"
    if not rf.exists():
        return None
    res = json.loads(rf.read_text(encoding="utf-8"))
    master = _jsonl(d / "master.jsonl.gz")
    return {"dir": d, "result": res,
            "rollout": next((x for x in master if x.get("kind") == "rollout"), None),
            "steps": sorted((x for x in master if x.get("kind") == "step"), key=lambda s: s.get("seq") or 0),
            "coach": _jsonl(d / "coach-decisions.jsonl")}


def game_id(t: dict) -> str | None:
    res = t["result"]
    for s in (res.get("state_path"), res.get("coach_log"), ((t["rollout"] or {}).get("result") or {}).get("game_id")):
        m = GAME_RE.search(str(s or ""))
        if m:
            return m.group(1)
    return None


def turn_modes(t: dict) -> list[str]:
    """The mode of every live turn: the master steps' actions, else the try's coach decisions, else its assignment."""
    if t["steps"]:
        return [str(s.get("action")) for s in t["steps"]]
    origin = int((t["result"].get("origin") or {}).get("turn") or 0)
    rows = [c for c in t["coach"] if int((c.get("features") or {}).get("step") or 0) >= origin]
    if rows:
        return [str(c.get("mode")) for c in rows]
    return [str((t["result"].get("assignment") or {}).get("mode") or "stock")]


def finished(t: dict) -> str | None:
    """None when the try counts; else why not."""
    res = t["result"]
    if res.get("diverged") or res.get("aborted"):
        return "diverged/aborted"
    if res.get("status") != "done":
        return f"status {res.get('status')}"
    if not res.get("turns_done") and not res.get("turns"):
        return "no live turn"
    return None


def reward(t: dict, human: dict[str, list[int]] | None = None) -> tuple[float, dict]:
    """(reward, detail). Human actions and the level's actions before the moment come from the master steps."""
    res = t["result"]
    origin = res.get("origin") or {}
    level = int(origin.get("level") or 0)
    if not res.get("cleared"):
        return 0.0, {"level": level, "cleared": False}
    first = t["steps"][0] if t["steps"] else {}
    out = first.get("outcome") or {}
    h = out.get("human_moves")
    if h is None and human is not None:
        g = game_id(t)
        h = (human.get(g) or [None] * level)[level - 1] if g and level else None
    prefix = (first.get("features") or {}).get("actions_in_level")
    used = int(res.get("moves_to_clear") or res.get("moves") or 0)
    if h is None or prefix is None:
        return float("nan"), {"level": level, "cleared": True, "why": "no human moves / level actions"}
    r = rr.try_reward(cleared=True, human_actions=int(h), prefix_level_actions=int(prefix), try_actions=used)
    return r, {"level": level, "cleared": True, "human": int(h), "prefix": int(prefix), "moves": used,
               "master_level_score": out.get("level_score")}


def replies_by_key(d: Path) -> dict[tuple[int, int], dict]:
    out = {}
    for r in _jsonl(d / "replies.jsonl"):
        if isinstance(r.get("message"), dict):
            out[(int(r.get("analysis_step") or 0), int(r.get("request_index_within_turn") or 0))] = r["message"]
    return out


def _same_reply(a: dict, b: dict) -> bool:
    keys = ("content", "reasoning_content", "tool_calls")
    norm = lambda m: json.dumps({k: (m.get(k) or None) for k in keys}, sort_keys=True)  # noqa: E731
    return norm(a) == norm(b)


def _tokens(req: dict) -> int:
    """Prompt + reply tokens of one request as the server counted them (0 when the usage was not logged)."""
    u = req.get("_usage") or {}
    return int(u.get("prompt_tokens") or 0) + (int(u.get("completion_tokens") or 0) if req.get("_reply") else 0)


def try_records(t: dict, advantage: float, meta: dict, stats: Counter, max_tokens: int = 119000) -> list[dict]:
    d = t["dir"]
    origin_turn = int((t["result"].get("origin") or {}).get("turn") or 0)
    rows = _jsonl(d / "requests.jsonl") or _jsonl(d / "requests.jsonl.gz")   # .gz: the host sync's per-try copy
    if not rows:
        stats["no request log"] += 1
        return []
    reps = replies_by_key(d)
    for r in rows:
        if r.get("event") == "response":
            key = (int(r.get("analysis_step") or 0), int(r.get("request_index_within_turn") or 0))
            if key in reps:
                r["response_message"] = reps[key]
    rows = br.attach_usage(rows)
    reqs = [r for r in rows if r.get("event") == "request"]
    # every logged reply that the harness also put into a later request must be that same message (checks the format
    # of the appended last replies)
    for i, r in enumerate(reqs[:-1]):
        rep = r.get("_reply")
        nxt = reqs[i + 1]["messages"]
        j = len(r["messages"])
        if isinstance(rep, dict) and j < len(nxt) and nxt[j].get("role") == "assistant":
            stats["reply check same" if _same_reply(rep, nxt[j]) else "reply check DIFFERENT"] += 1
    keep = lambda req: int(req.get("analysis_step") or -1) >= origin_turn  # noqa: E731
    out = []
    for seg in br.segments(rows):
        # the trainer skips a record longer than its --max-tokens: end the stretch at the last request that fits
        # (prompt + its reply, as the server counted them), so the try's earlier replies still train
        n0 = len(seg)
        while seg and _tokens(seg[-1]) > max_tokens:
            seg = seg[:-1]
        if len(seg) < n0:
            stats["stretches cut to fit" if seg else "stretches too long"] += 1
        if not seg:
            continue
        rec = br.record_from_segment(seg, keep, dict(meta, weighting="try_advantage"), lambda req: advantage)
        if rec is not None:
            stats["last reply appended" if rec["meta"]["reply_appended"] else "last reply missing"] += 1
            out.append(rec)
    return out


def build(dirs: Iterable[Path], *, modes: set[str] | None, group_by: str, min_tries: int,
          campaign: str, human: dict[str, list[int]] | None = None,
          max_tokens: int = 119000) -> tuple[list[dict], dict]:
    stats: Counter = Counter()
    groups: dict[str, list[dict]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for d in dirs:
        t = load_try(d)
        if t is None:
            continue
        tid = (str(t["result"].get("job")), str(t["result"].get("try")))
        if tid in seen:                                # the host sync's copy and the final rsync's copy of one try
            stats["duplicate copies"] += 1
            continue
        seen.add(tid)
        stats["tries"] += 1
        why = finished(t)
        if why:
            stats[f"skip: {why}"] += 1
            continue
        tm = turn_modes(t)
        if modes and any(m not in modes for m in tm):
            stats["skip: turn outside modes"] += 1
            continue
        r, det = reward(t, human)
        if r != r:                                     # nan
            stats["skip: no reward"] += 1
            continue
        t["reward"], t["reward_detail"] = r, det
        key = str(t["result"].get("job")) if group_by == "job" else \
            f"{game_id(t)}:{(t['result'].get('origin') or {}).get('screen_hash')}"
        groups[key].append(t)
    recs: list[dict] = []
    summary = []
    for key, ts in sorted(groups.items()):
        rewards = [t["reward"] for t in ts]
        mean = sum(rewards) / len(rewards)
        row = {"group": key, "tries": len(ts), "cleared": sum(1 for t in ts if t["reward_detail"]["cleared"]),
               "rewards": [round(x, 3) for x in rewards], "records": 0}
        summary.append(row)
        if len(ts) < min_tries:
            stats["groups: too few tries"] += 1
            continue
        if max(rewards) - min(rewards) < 1e-9:
            stats["groups: all equal"] += 1
            continue
        stats["groups: used"] += 1
        for t in ts:
            adv = t["reward"] - mean
            if abs(adv) < 1e-9:
                continue
            res = t["result"]
            meta = {"run": campaign, "game": game_id(t), "pass": f"{res.get('job')}.k{res.get('try')}",
                    "job": res.get("job"), "try": res.get("try"), "group": key, "reward": round(t["reward"], 4),
                    "advantage": round(adv, 4), "group_mean": round(mean, 4), "group_tries": len(ts),
                    "origin_turn": (res.get("origin") or {}).get("turn"), "level": t["reward_detail"]["level"],
                    "cleared": t["reward_detail"]["cleared"], "moves": res.get("moves"),
                    "stop_reason": res.get("stop_reason"), "policy_version": res.get("policy_version")}
            got = try_records(t, adv, meta, stats, max_tokens)
            row["records"] += len(got)
            recs += got
    return recs, {"stats": dict(stats), "groups": summary}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tries", required=True, action="append",
                    help="root(s) holding <job>/k<k>/result.json (a run's gtree-rollout dir or a campaign's runs dir)")
    ap.add_argument("--out", required=True, help="candidate records (.jsonl.gz)")
    ap.add_argument("--modes", default="", help="comma list: keep only tries whose every turn used one of these")
    ap.add_argument("--group-by", choices=("job", "node"), default="job",
                    help="job = siblings sharing one context (default); node = every try from the same screen")
    ap.add_argument("--min-tries", type=int, default=2)
    ap.add_argument("--max-tokens", type=int, default=119000,
                    help="cut stretches to this many tokens (the trainer runs --max-tokens 121000 and skips longer records)")
    ap.add_argument("--campaign", default="")
    ap.add_argument("--report", default="", help="write the stats + per-group rewards here (json)")
    args = ap.parse_args()
    dirs = sorted({p.parent for root in args.tries for p in Path(root).rglob("result.json")
                   if re.fullmatch(r"k\d+", p.parent.name)})
    recs, rep = build(dirs, modes={m for m in args.modes.split(",") if m} or None, group_by=args.group_by,
                      min_tries=args.min_tries, campaign=args.campaign or Path(args.tries[0]).name,
                      max_tokens=args.max_tokens)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out, "wt", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    pos = sum(1 for r in recs if r["meta"]["advantage"] > 0)
    rep["stats"].update(records=len(recs), positive=pos, negative=len(recs) - pos,
                        trained_replies=sum(r["meta"]["n_trained"] for r in recs))
    if args.report:
        Path(args.report).write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps(rep["stats"]), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Training records from the harness's request logs (plan: docs/plans/2026-10-01-rl-on-burst-games.md §2, B4).

A request log (<game>_p0_requests.jsonl, written when save_request_logs is on) has one "request" row per model
call with the exact messages sent (system prompt, user turns with their grid images, the model's earlier replies
with their thinking, tool results) and one "response" row with the usage. The reply itself is not in the
response row: it shows up as the assistant message appended to the NEXT request (checked on re86, 1-Oct).

Within a stretch where every request extends the previous one (no compaction / half-swap), the last request
holds the whole conversation, so one sequence trains every reply in it: each assistant message produced inside
the stretch gets loss when its turn is kept; everything else (system, user turns, images, tool output, replies
from before the stretch) is context only. The stretch's own final reply is not in the log and is dropped.

Record = {"tools", "chat_template_kwargs", "messages", "train": [bool per message], "meta"}. The trainer renders
it with the model's chat template (render.py); g0_data.py compares the rendered prompt with the logged usage to catch
re-tokenization drift (plan §11).

Usage:
  python build_records.py --requests <..._requests.jsonl or gs://...> --events <..._events.jsonl> --game re86-8af5384d \
      --run daniel-base-a-1001 --levels cleared --min-level-score 0.25 --out records.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Iterable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rl_reward as rr  # noqa: E402
import seed_moments as sm  # noqa: E402


def _canon(messages: list[dict]) -> list[str]:
    return [json.dumps(m, sort_keys=True, ensure_ascii=False) for m in messages]


def attach_usage(rows: list[dict]) -> list[dict]:
    """Copy each response row's usage / finish_reason onto the request row it answers (the next row with the
    same turn and request index). The usage is what the server counted for that exact prompt."""
    for i, r in enumerate(rows):
        if r.get("event") != "request":
            continue
        for nxt in rows[i + 1:i + 3]:
            if (nxt.get("event") == "response" and nxt.get("analysis_step") == r.get("analysis_step")
                    and nxt.get("request_index_within_turn") == r.get("request_index_within_turn")):
                r["_usage"] = nxt.get("usage") or {}
                r["_finish"] = nxt.get("finish_reason")
                if isinstance(nxt.get("response_message"), dict):     # our harness logs the reply; Daniel's does not
                    r["_reply"] = nxt["response_message"]
                break
    return rows


def segments(requests: Iterable[dict]) -> list[list[dict]]:
    """Split request rows (event == 'request') into append-only stretches."""
    segs: list[list[dict]] = []
    prev: list[str] | None = None
    for r in requests:
        if r.get("event") != "request":
            continue
        cur = _canon(r.get("messages") or [])
        if prev is not None and len(cur) > len(prev) and cur[:len(prev)] == prev:
            segs[-1].append(r)
        else:
            segs.append([r])
        prev = cur
    return segs


def record_from_segment(seg: list[dict], keep: Callable[[dict], bool], meta: dict | None = None,
                        weight: Callable[[dict], float] | None = None) -> dict | None:
    """One training record from one stretch; None when no kept reply is inside it. When the log carries the
    stretch's final reply (response_message), it is appended so that reply can be trained too.
    `weight(req)` gives each trained reply its loss weight (default 1); `weights` runs parallel to `messages`."""
    last = seg[-1]
    messages = list(last["messages"])
    reply = last.get("_reply")
    appended = isinstance(reply, dict) and reply.get("role", "assistant") == "assistant"
    if appended:
        messages.append(dict(reply, role="assistant"))
    train = [False] * len(messages)
    weights = [0.0] * len(messages)
    turns = []
    for req in seg:
        j = len(req["messages"])                      # where this request's reply sits in the next request
        if j < len(messages) and messages[j].get("role") == "assistant" and keep(req):
            train[j] = True
            weights[j] = float(weight(req)) if weight else 1.0
            turns.append(int(req.get("analysis_step") or 0))
    if not any(train):
        return None
    usage = last.get("_usage") or {}
    return {
        "tools": last.get("tools") or [],
        "chat_template_kwargs": last.get("chat_template_kwargs") or {},
        "messages": messages,
        "train": train,
        "weights": weights,
        "meta": dict(meta or {}, turns=sorted(set(turns)), n_trained=sum(train), n_messages=len(messages),
                     first_step=int(seg[0].get("analysis_step") or 0), last_step=int(last.get("analysis_step") or 0),
                     reply_appended=appended, logged_prompt_tokens=usage.get("prompt_tokens"),
                     logged_image_tokens=(usage.get("prompt_tokens_details") or {}).get("image_tokens")),
    }


def kept_levels(spans: dict, human: list[int], *, mode: str, min_level_score: float,
                frontier: list[int] | None = None) -> set[int]:
    """Which cleared levels' turns become training data.
    mode 'cleared': every cleared level whose level score >= min_level_score (efficient wins), plus every cleared
    frontier level whatever its efficiency (rare wins are the point)."""
    if mode != "cleared":
        raise ValueError(mode)
    out = set()
    for k, last in spans["clear"].items():
        used = last - spans["start"][k] + 1
        if k <= len(human) and (rr.level_score(human[k - 1], used) >= min_level_score or k in (frontier or [])):
            out.add(k)
    return out


def best_clears(spans_by_pass: dict[int, dict], human: list[int], *, min_level_score: float,
                frontier: list[int] | None = None, n_best: int = 1) -> dict[int, set[int]]:
    """Which pass trains which level, when a run played each game several times (Son, 3-Oct: g0_data read only
    pass 0, so 4 of every 5 attempts never reached training). Per level, of the clears that qualify under
    kept_levels, the n_best with the fewest actions win (ties: lower pass). Returns {pass: levels}.
    Fewest actions is also the guard against lucky clears: the 3-Oct sc25 audit's level-1 record took 48 of a
    50-action budget on a wrong story, while another pass of the same run cleared it in 17."""
    cands: dict[int, list[tuple[int, int]]] = {}
    for p, spans in spans_by_pass.items():
        for k in kept_levels(spans, human, mode="cleared", min_level_score=min_level_score, frontier=frontier):
            cands.setdefault(k, []).append((spans["clear"][k] - spans["start"][k] + 1, p))
    out: dict[int, set[int]] = {}
    for k, lst in cands.items():
        for _, p in sorted(lst)[:n_best]:
            out.setdefault(p, set()).add(k)
    return out


def level_advantages(spans_by_pass: dict[int, dict], human: list[int], *,
                     min_abs: float = 0.0) -> dict[int, dict[int, float]]:
    """Relative credit (Son, 4-Oct: "if a trace is better than average then it is positive"): every attempt (pass)
    of a game is scored per level, reward = the scorer's level score min(1.15, (human / actions)^2) when cleared, 0
    when not (whether it got stuck there or never reached it). A level's advantage for an attempt is its reward minus
    the mean reward of all attempts at that level, so a rare clear is strongly positive, a clear everyone makes in the
    same moves is ~0, and getting stuck where others cleared is negative. Not divided by the spread: with 5-6
    attempts it is too noisy (Dr. GRPO).
    Only levels an attempt PLAYED get a value (it has turns there): every cleared level, plus the level it was
    stuck on at the end. Returns {pass: {level: advantage}}, dropping |advantage| < min_abs."""
    if not spans_by_pass:
        return {}
    levels = sorted({k for sp in spans_by_pass.values() for k in sp["start"] if k <= len(human)})
    reward = {p: {k: (rr.level_score(human[k - 1], sp["clear"][k] - sp["start"][k] + 1) if k in sp["clear"] else 0.0)
                  for k in levels} for p, sp in spans_by_pass.items()}
    mean = {k: sum(reward[p][k] for p in reward) / len(reward) for k in levels}
    out: dict[int, dict[int, float]] = {}
    for p, sp in spans_by_pass.items():
        played = [k for k in levels if k in sp["clear"] or k == max(sp["start"])]
        adv = {k: reward[p][k] - mean[k] for k in played}
        adv = {k: a for k, a in adv.items() if abs(a) >= min_abs and a != 0.0}
        if adv:
            out[p] = adv
    return out


def level_scores(spans: dict, human: list[int]) -> dict[int, float]:
    """Scorer's level score of every cleared level: min(1.15, (human / used)^2)."""
    return {k: rr.level_score(human[k - 1], last - spans["start"][k] + 1)
            for k, last in spans["clear"].items() if k <= len(human)}


def records_for_game(requests: list[dict], spans: dict, levels: set[int], meta: dict,
                     human: list[int] | None = None, level_weight: dict[int, float] | None = None) -> list[dict]:
    """Records whose trained replies are exactly the turns that START inside one of `levels`.

    With `human` (the level baselines), each reply is weighted by its level's score (Son, 1-Oct: winning turns are not
    all equal; the score rewards fewer moves): a level won in the human's moves weighs ~1, in 3x the moves ~0.11.
    `level_weight` ({level: weight}, e.g. advantages, may be negative) overrides that. Without either every kept
    reply weighs 1."""
    step_level = {s: lvl for s, (_, lvl) in spans["turn_start"].items()}
    keep_steps = {s for s, lvl in step_level.items() if lvl in levels}
    keep = lambda req: int(req.get("analysis_step") or -1) in keep_steps  # noqa: E731
    weight, weighting = None, "uniform"
    if level_weight is not None:
        weight = lambda req: level_weight.get(step_level.get(int(req.get("analysis_step") or -1)), 0.0)  # noqa: E731
        weighting = "advantage"
    elif human:
        scores = level_scores(spans, human)
        weight = lambda req: scores.get(step_level.get(int(req.get("analysis_step") or -1)), 0.0)  # noqa: E731
        weighting = "level_score"
    out = []
    for seg in segments(attach_usage(requests)):
        rec = record_from_segment(seg, keep, dict(meta, weighting=weighting), weight)
        if rec is not None:
            out.append(rec)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--requests", required=True)
    ap.add_argument("--events", required=True)
    ap.add_argument("--game", required=True, help="full game id, e.g. re86-8af5384d")
    ap.add_argument("--run", required=True)
    ap.add_argument("--human", default="", help="comma list of human actions per level (default: observer table)")
    ap.add_argument("--frontier", default="")
    ap.add_argument("--levels", default="cleared")
    ap.add_argument("--min-level-score", type=float, default=0.25)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    human = [int(x) for x in args.human.split(",")] if args.human else list(sm._observer().BASE_ACTIONS[args.game])
    frontier = []
    if args.frontier:
        frontier = json.loads(Path(args.frontier).read_text())["games"].get(args.game[:4], {}).get("frontier", [])
    spans = sm.level_spans(sm.iter_jsonl(args.events))
    requests = list(sm.iter_jsonl(args.requests))
    levels = kept_levels(spans, human, mode=args.levels, min_level_score=args.min_level_score, frontier=frontier)
    recs = records_for_game(requests, spans, levels, {"run": args.run, "game": args.game, "levels": sorted(levels)},
                            human=human)
    with open(args.out, "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    n = sum(r["meta"]["n_trained"] for r in recs)
    print(f"{args.game}: levels kept {sorted(levels)} -> {len(recs)} records, {n} trained replies -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

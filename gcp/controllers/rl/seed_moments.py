"""Seed forkable moments from finished runs (plan: docs/plans/2026-10-01-rl-on-burst-games.md §2, B3).

For each game of a run, read the harness's own logs:
- <game>_p0_events.jsonl (artifacts/): one row per action (action_num, analysis_step, action_name, level_completed)
  and per solver turn ("analysis" rows) -> level boundaries and the action list (state keys);
- <game>_p0_requests.jsonl (working/, written when save_request_logs is on; Daniel's notebook has it on):
  per request the solver turn, the action number at that point and the reply's token usage -> the
  reference's remaining tokens from each moment.

A moment = the start of a solver turn inside a frontier level (frontier.json from frontier.py). Up to
`per_level` moments per level, spread from the level's first turn to its last, so the tree has easy (late) and
hard (early) starting points for the reverse curriculum. Levels the run cleared are seeded by default; with
--uncleared, the level the run died in is seeded too (ref_cleared False).

Usage (here, Python 3.12):
  python seed_moments.py --run daniel-base-a-1001 --gcs gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs/daniel-base-a-1001/working \
      --frontier D:/codex-work/rl-20261001/frontier.json --harness daniel-nb-v1 --campaign rl-1001a \
      --out D:/codex-work/rl-20261001/moments/daniel-base-a-1001.jsonl [--write-firestore]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Iterator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rl_tree as rt  # noqa: E402

GCLOUD_PY = Path(r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py")


def _observer():
    for p in (HERE, *HERE.parents):
        f = p / "arc3_minute_score_observer.py"
        if f.exists():
            spec = importlib.util.spec_from_file_location("_obs_seed", f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise FileNotFoundError("arc3_minute_score_observer.py")


# ------------------------------------------------------------------------------------------------ reading
def _gcloud(*args: str) -> list[str]:
    if GCLOUD_PY.exists():
        os.environ.setdefault("CLOUDSDK_PYTHON", sys.executable)
        return [sys.executable, str(GCLOUD_PY), *args]
    return ["gcloud", *args]


def iter_jsonl(src: str | Path) -> Iterator[dict]:
    """Rows of a local or gs:// JSONL file, streamed (request logs are 20-50 MB per game)."""
    src = str(src)
    if src.startswith("gs://"):
        proc = subprocess.Popen(_gcloud("storage", "cat", src), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        assert proc.stdout is not None
        for line in proc.stdout:
            if line.strip():
                yield json.loads(line)
        proc.wait()
        return
    with open(src, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def exists(src: str) -> bool:
    if src.startswith("gs://"):
        return subprocess.run(_gcloud("storage", "ls", src), capture_output=True).returncode == 0
    return Path(src).exists()


# ------------------------------------------------------------------------------------------------ pure logic
def action_token(ev: dict) -> str:
    """One action as text for the state key: name plus click coordinates when the event carries them."""
    name = str(ev.get("action_name") or ev.get("action_display") or "?")
    for kx, ky in (("x", "y"), ("click_x", "click_y")):
        if ev.get(kx) is not None and ev.get(ky) is not None:
            return f"{name}@{ev[kx]},{ev[ky]}"
    data = ev.get("action_data") or ev.get("data")
    if isinstance(data, dict) and data.get("x") is not None:
        return f"{name}@{data.get('x')},{data.get('y')}"
    return name


def level_spans(events: Iterable[dict]) -> dict[str, Any]:
    """From the events log: actions in order, per level its first and clearing action, and per solver turn the
    action number and level it STARTS at.

    Returns {"actions": [(action_num, token)], "start": {level: first action_num}, "clear": {level: action_num},
             "turn_start": {analysis_step: (action_num at turn start, level at turn start)}}.

    Careful (checked on re86, 1-Oct): an "analysis" row is written AFTER its turn's actions, so its action_num is
    the turn's LAST action and its level the level after it. The start of turn s is therefore 1 + the last action
    of every earlier turn; its level is 1 + the levels cleared by actions before that start. The request log's
    `action` field (first request of a turn) is the same number; `check_turn_starts` compares the two.
    """
    actions: list[tuple[int, str]] = []
    step_of: dict[int, int] = {}
    cleared_at: list[int] = []
    steps: set[int] = set()
    for ev in events:
        if ev.get("analysis_step") is not None:
            steps.add(int(ev["analysis_step"]))
        if ev.get("type") == "action":
            n = int(ev["action_num"])
            actions.append((n, action_token(ev)))
            if ev.get("analysis_step") is not None:
                step_of[n] = int(ev["analysis_step"])
            if ev.get("level_completed"):
                cleared_at.append(n)
    actions.sort()
    cleared_at.sort()
    clear = {i + 1: n for i, n in enumerate(cleared_at)}
    start = {1: 1, **{i + 2: n + 1 for i, n in enumerate(cleared_at)}}
    turn_start: dict[int, tuple[int, int]] = {}
    last_action = 0
    for s in sorted(steps):
        a = last_action + 1
        turn_start[s] = (a, 1 + sum(c < a for c in cleared_at))
        mine = [n for n, st in step_of.items() if st == s]
        if mine:
            last_action = max(last_action, max(mine))
    return {"actions": actions, "start": start, "clear": clear, "turn_start": turn_start}


def check_turn_starts(spans: dict, tokens: dict[int, dict[str, int]]) -> list[int]:
    """Turns whose start action from the events log differs from the request log's (should be none)."""
    return [s for s, t in tokens.items() if s in spans["turn_start"] and t["action"] != spans["turn_start"][s][0]]


def turn_tokens(requests: Iterable[dict]) -> dict[int, dict[str, int]]:
    """Per solver turn: the first request's action number and the replies' completion tokens."""
    out: dict[int, dict[str, int]] = {}
    for r in requests:
        step = r.get("analysis_step")
        if step is None:
            continue
        t = out.setdefault(int(step), {"action": int(r.get("action") or 0), "tokens": 0, "requests": 0})
        if r.get("event") == "response":
            t["tokens"] += int((r.get("usage") or {}).get("completion_tokens") or 0)
            t["requests"] += 1
    return out


CHARS_PER_TOKEN = 3.5      # Qwen tokenizer on English reasoning + python (rough; only sizes the try token cap)
_SECTION = re.compile(r"^\[([A-Z][A-Z _]+)(?::[^\]\n]*)?\]\s*$", re.M)     # [THINKING], [TOOL CALL: python], ...


def _sections(transcript: str, name: str) -> list[str]:
    marks = list(_SECTION.finditer(transcript or ""))
    return [transcript[m.end():(marks[i + 1].start() if i + 1 < len(marks) else len(transcript))]
            for i, m in enumerate(marks) if m.group(1).strip() == name]


def turn_tokens_from_events(events: Iterable[dict]) -> dict[int, int]:
    """Per solver turn, the reply tokens ESTIMATED from the turn transcripts (reasoning + content + tool-call
    arguments, in characters / CHARS_PER_TOKEN). Our harness's request logs carry no usage (checked 1-Oct on the
    Combo A seeds), so this is the only per-turn size we have for them."""
    out: dict[int, int] = {}
    for ev in events:
        if ev.get("type") != "analysis" or ev.get("analysis_step") is None:
            continue
        chars = 0
        for meta in _sections(ev.get("transcript") or "", "MODEL RESPONSE META"):
            for key in ("reasoning_chars", "content_chars"):
                m = re.search(rf"^{key}: (\d+)", meta, re.M)
                chars += int(m.group(1)) if m else 0
            if "raw_tool_calls:" in meta:          # the calls' JSON (arguments + ~150 chars of wrapper per call)
                chars += len(meta.split("raw_tool_calls:", 1)[1].strip())
        out[int(ev["analysis_step"])] = int(chars / CHARS_PER_TOKEN)
    return out


def spread(items: list, k: int) -> list:
    """Up to k items spread from first to last (always keeps the first and the last)."""
    if len(items) <= k:
        return list(items)
    if k <= 1:
        return [items[0]]
    idx = sorted({round(i * (len(items) - 1) / (k - 1)) for i in range(k)})
    return [items[i] for i in idx]


def moments_for_game(*, run_id: str, game_id: str, spans: dict, tokens: dict[int, dict[str, int]],
                     levels: list[int], human: list[int], harness: str, policy: str, campaign: str,
                     per_level: int = 6, include_uncleared: bool = False, source_uri: str = "") -> list[dict]:
    """Moment documents for the given levels of one game of one run."""
    n_levels = len(human)
    acts = spans["actions"]
    out = []
    for k in levels:
        cleared = k in spans["clear"]
        if k not in spans["start"] or (not cleared and not include_uncleared):
            continue
        first = spans["start"][k]
        last = spans["clear"].get(k)
        # turns that START inside level k (their first action number lies in the level)
        cand = sorted(step for step, (a, lvl) in spans["turn_start"].items()
                      if lvl == k and a >= first and (last is None or a <= last))
        for step in spread(cand, per_level):
            a, _ = spans["turn_start"][step]
            later = [s for s in tokens if s >= step and (last is None or tokens[s]["action"] <= last)]
            rem_tokens = sum(tokens[s]["tokens"] for s in later) if tokens else None
            prefix = [tok for n, tok in acts if n < a]
            out.append(rt.new_moment(
                source_kind="run", source=run_id, game_id=game_id, level=k, turn=step, action_num=a,
                level_actions_before=a - first, human_actions=human[k - 1], n_levels=n_levels, harness=harness,
                policy=policy, state=rt.state_key(game_id, prefix),
                ref_remaining_actions=(last - a + 1) if cleared else None, ref_remaining_tokens=rem_tokens,
                ref_cleared=cleared, campaign=campaign, source_uri=source_uri))
    return out


# ------------------------------------------------------------------------------------------------ CLI
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="run id (the trajectory source of every moment)")
    ap.add_argument("--gcs", default="", help="the run's working dir (gs://.../working) with artifacts/")
    ap.add_argument("--local", default="", help="same layout on disk instead of --gcs")
    ap.add_argument("--frontier", required=True)
    ap.add_argument("--harness", required=True)
    ap.add_argument("--policy", default="base")
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--games", default="", help="comma list of 4-letter ids (default: every non-fenced game)")
    ap.add_argument("--per-level", type=int, default=6)
    ap.add_argument("--uncleared", action="store_true")
    ap.add_argument("--no-tokens", action="store_true", help="skip the request logs (no remaining-token refs)")
    ap.add_argument("--tokens-from-events", action="store_true",
                    help="size turns from the transcripts in the events log, skip the request logs (our harness)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--write-firestore", action="store_true")
    args = ap.parse_args()

    obs = _observer()
    frontier = json.loads(Path(args.frontier).read_text())["games"]
    root = (args.gcs or args.local).rstrip("/")
    wanted = {g.strip() for g in args.games.split(",") if g.strip()}
    store = rt.FirestoreStore() if args.write_firestore else None
    all_moments = []
    for game_id, human in obs.BASE_ACTIONS.items():
        g = rt.game4(game_id)
        if rt.is_fenced(game_id) or (wanted and g not in wanted) or g not in frontier:
            continue
        levels = list(frontier[g]["frontier"])
        if not levels:
            continue
        ev_src = f"{root}/artifacts/{game_id}_p0_events.jsonl"
        rq_src = f"{root}/{game_id}_p0_requests.jsonl"
        if not exists(ev_src):
            print(f"{g}: no events log, skipped")
            continue
        events = list(iter_jsonl(ev_src))
        spans = level_spans(events)
        if args.tokens_from_events:     # our harness: the request logs (20-50 MB) carry no usage, skip them
            est = turn_tokens_from_events(events)
            tokens = {st: {"action": a0, "tokens": est.get(st, 0), "requests": 0}
                      for st, (a0, _lvl) in spans["turn_start"].items()}
        else:
            tokens = {} if args.no_tokens or not exists(rq_src) else turn_tokens(iter_jsonl(rq_src))
        estimated = args.tokens_from_events or (bool(tokens) and not any(t["tokens"] for t in tokens.values()))
        if estimated and not args.tokens_from_events:   # request log without usage: size turns from transcripts
            est = turn_tokens_from_events(events)
            for st, t in tokens.items():
                t["tokens"] = est.get(st, 0)
        bad = check_turn_starts(spans, tokens)
        if bad:
            print(f"{g}: turn starts disagree between events and requests at turns {bad[:8]} -> skipped")
            continue
        ms = moments_for_game(run_id=args.run, game_id=game_id, spans=spans, tokens=tokens, levels=levels,
                              human=list(human), harness=args.harness, policy=args.policy, campaign=args.campaign,
                              per_level=args.per_level, include_uncleared=args.uncleared, source_uri=root)
        for m in ms:
            m["ref_tokens_estimated"] = estimated
        print(f"{g}: cleared {sorted(spans['clear'])}, frontier {levels} -> {len(ms)} moments"
              + (" (turn tokens estimated from transcripts)" if estimated else ""))
        all_moments += ms
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for m in all_moments:
            fh.write(json.dumps(m) + "\n")
    if store is not None:
        for m in all_moments:
            store.put("rl_moments", m)
    print(f"{len(all_moments)} moments -> {out}" + (" (+ Firestore rl_moments)" if store else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

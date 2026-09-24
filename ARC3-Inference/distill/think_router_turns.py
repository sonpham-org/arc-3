#!/usr/bin/env python3
# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Turn table for the "think hard vs think light" router study (Son's ask, relayed in #arc-3,
#   23-Sep-2026). Offline only: reads the recorded Flash-Next plays (ebul_perception.trace_paths(301))
#   and writes one row per agent TURN with
#     - thinking spent: the harness writes one "[MODEL RESPONSE META]" block per model request inside
#       each analysis row's transcript, with `reasoning_chars` (length of the reasoning text) and
#       `content_chars`; there are no token counts per request. A turn = one analysis_step id: the
#       model is called repeatedly (python tool calls) until one action(...) call executes; a turn
#       that hits the per-turn time budget is written as several analysis rows with the SAME
#       analysis_step ("Yielded control to solver: turn_time_budget"), so thinking is summed over all
#       rows of the id. Rows with no META are request time-outs (kept, flagged). Action rows carry the
#       analysis_step of the turn that issued them and are written BEFORE their analysis row, so actions
#       are assigned by id, never by file position. Also: first request's reasoning_chars (the only
#       thinking that precedes every tool result of the turn), request count, time-outs, yields, the
#       runtime budget line (game seconds left; written only in the Kaggle plays) and the wall clock of
#       the turn header (seconds since the play's first turn, seconds until the next turn), which is
#       the budget proxy available in every play.
#     - cheap router features known BEFORE the turn (no LLM call): the round-seven chain back-off model
#       (round7.Model, chain=True, keys handcolour context -> + previous outcome, open vocabulary,
#       fresh per play, no training) gives the surprisal of the last step's outcome, the previous
#       turn's max / mean surprisal, and the predictive entropy and unseen-outcome mass for every
#       candidate action context (valid buttons; for clicks, every click context already tried in the
#       play plus one "fresh click" context, a cost cap: enumerating every object type per turn would
#       cost more than the router saves); untried buttons and untried clickable object types (colour
#       + shape) on the board; first turn / level start / just cleared / after RESET; stall length
#       (actions and turns since the last new outcome label or level clear); level index, actions into
#       the level, turn index, last turn's batch size; game type from the valid-action list.
#     - outcomes of the turn: actions issued, any outcome label never seen before in the play (new),
#       level clear in the turn, level clear within the next 5 / 10 actions from the turn's start,
#       game over, realised surprisal (sum / max) of the turn's outcomes.
#   Also a chars-to-tokens calibration per job: summed reasoning + content + tool-call argument chars
#   of every request in the job's artifacts against the vLLM generation_tokens_total of that job.
#   Output: results/think_router/turns.jsonl, calibration.json, extract_log.txt.
#   Reads trace files only; no harness, prompt, Kaggle or Jethro change; no existing file edited.
# SRP/DRY check: Pass -- events and labels from object_events.load_all, handcolour context and
#   previous-outcome values from feature_detectors.run_trace, the chain back-off from round7.Model,
#   the play list from ebul_perception.trace_paths; this file only parses thinking metadata and builds
#   the per-turn table. The analysis lives in think_router.py.
"""Extract the per-turn table (thinking, pre-turn features, outcomes) for the think-router study."""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ebul_perception as ep  # noqa: E402
import efe_trace_analysis as efe  # noqa: E402
import feature_detectors as fd  # noqa: E402
import object_events as oe  # noqa: E402
import round7 as r7  # noqa: E402

OUT = Path(__file__).parent / "results/think_router"
N_PLAYS = 301
META_RE = re.compile(r"\[MODEL RESPONSE META\]\n(.*?)(?=\n\[THINKING\]|\n\[TOOL CALL|\n\[RUNTIME BUDGET\]|\n\[ANALYZER STATUS\]|\Z)",
                     re.S)
RC_RE = re.compile(r"reasoning_chars: (\d+)")
CC_RE = re.compile(r"content_chars: (\d+)")
BUDGET_RE = re.compile(r"\[Runtime budget\] time left (\d+)s \(game (\d+)s, suite (\d+)s\)")
HEADER_RE = re.compile(r"--- analysis_step=\d+ \| action=\d+ \| (\d\d):(\d\d):(\d\d) \|")
THINK_RE = re.compile(r"\[THINKING\]\n(.*?)(?=\n\[TOOL CALL|\n\[RUNTIME BUDGET\]|\n\[ANALYZER STATUS\]|\n\[TOOL RESULT|\Z)", re.S)
K_CLEAR = (5, 10)
FRESH_CLICK = ("M", "__fresh__")


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- thinking metadata

def tool_arg_chars(meta: str) -> int:
    """Summed length of the tool-call argument strings in one META block (0 if unparsable)."""
    i = meta.find("raw_tool_calls:")
    if i < 0:
        return 0
    try:
        calls = json.loads(meta[i + len("raw_tool_calls:"):].strip())
    except json.JSONDecodeError:
        return 0
    return sum(len(c.get("function", {}).get("arguments", "") or "") for c in calls if isinstance(c, dict))


def parse_request_blocks(transcript: str) -> list:
    """[(reasoning_chars, content_chars, tool_arg_chars)] per model request in one analysis row."""
    out = []
    for m in META_RE.finditer(transcript or ""):
        meta = m.group(1)
        rc, cc = RC_RE.search(meta), CC_RE.search(meta)
        if rc is None:
            continue
        out.append((int(rc.group(1)), int(cc.group(1)) if cc else 0, tool_arg_chars(meta)))
    return out


def turn_meta(path: str) -> dict:
    """analysis_step (int) -> thinking metadata of that turn, summed over all its analysis rows."""
    turns = {}
    with open(path) as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("type") != "analysis":
                continue
            try:
                k = int(r.get("analysis_step"))
            except (TypeError, ValueError):
                continue
            t = r.get("transcript") or ""
            reqs = parse_request_blocks(t)
            d = turns.setdefault(k, {"rows": 0, "requests": [], "timeouts": 0, "yields": 0, "game_left": None,
                                     "suite_left": None, "think_text_chars": 0, "clock": None})
            hm = HEADER_RE.search(t)
            if hm and d["clock"] is None:
                d["clock"] = int(hm.group(1)) * 3600 + int(hm.group(2)) * 60 + int(hm.group(3))
            d["rows"] += 1
            d["requests"] += reqs
            d["timeouts"] += int("request_error:" in t)
            d["yields"] += int("Yielded control to solver" in t)
            d["think_text_chars"] += sum(len(x) for x in THINK_RE.findall(t))
            if d["game_left"] is None:
                b = BUDGET_RE.search(t)
                if b:
                    d["suite_left"], d["game_left"] = int(b.group(1)), int(b.group(2))
    return turns


# ---------------------------------------------------------------- chain back-off helpers

def chain_key(ctx, last_label):
    return ((ctx,), (ctx, last_label))


def predictive(m: r7.Model, key) -> tuple:
    """(entropy in nats, unseen-outcome mass) of the chain model's predictive for one context."""
    ps = [m.p(key, o) for o in m.vocab]
    novel = max(0.0, 1.0 - sum(ps))
    h = -sum(p * math.log(p) for p in ps if p > 0)
    if novel > 0:
        h -= novel * math.log(novel)
    return h, novel


def click_type_at(step):
    """(colour, shape) of the component under the click of a click step, or None."""
    if step.pa is None or step.row.get("action_name") != "ACTION6":
        return None
    m = efe.MOUSE_RE.search(step.row.get("action_display", ""))
    if not m:
        return None
    r, c = int(m.group(1)), int(m.group(2))
    if not (0 <= r < step.pa.lab.shape[0] and 0 <= c < step.pa.lab.shape[1]):
        return None
    cid = int(step.pa.lab[r, c])
    if not cid:
        return None
    comp = step.pa.comps[cid - 1]
    return None if comp.bg else comp.type_key


# ---------------------------------------------------------------- one play

def play_turns(trace) -> tuple:
    """(rows, notes) for one play: one row per turn, in turn order."""
    meta = turn_meta(trace.path)
    det = fd.run_trace(trace, names=["last_label"])
    buttons = [a for a in trace.valid if a not in ("ACTION6", "RESET")]
    clicking = "ACTION6" in trace.valid
    by_turn = defaultdict(list)
    order_viol = 0
    last_k = -1
    for s in trace.steps:
        k = int(s.row.get("analysis_step"))
        order_viol += int(k < last_k)
        last_k = max(last_k, k)
        by_turn[k].append(s)
    # per-step prequential pass first (surprisal, new-label flag), aligned with det rows
    m = r7.Model(efe.BASE_OUTCOMES, chain=True)
    seen = set()
    j = 0
    step_info = {}                  # step index -> (surprisal, is_new, label)
    snapshots = {}                  # step index of a turn's first step -> model features before it
    turn_first = {min(s.i for s in ss): k for k, ss in by_turn.items()}
    tried_click_ctx = set()
    clicked_types = set()
    last_label_state = "start"
    for s in trace.steps:
        if s.i in turn_first:
            snapshots[s.i] = pre_turn_model_features(m, buttons, clicking, tried_click_ctx, clicked_types,
                                                     s, trace, last_label_state)
        if s.reset:
            last_label_state = "reset"
            continue
        ctx, lab, vals = det[j]
        j += 1
        assert vals["last_label"] == last_label_state, (trace.path, s.i, vals["last_label"], last_label_state)
        key = chain_key(ctx, vals["last_label"])
        p = m.p(key, lab)
        step_info[s.i] = (-math.log(p), lab not in seen, lab)
        seen.add(lab)
        m.update(key, lab)
        if ctx and ctx[0] == "M":
            tried_click_ctx.add(ctx)
        ct = click_type_at(s)
        if ct is not None:
            clicked_types.add(ct)
        last_label_state = lab
    assert j == len(det)
    end_snapshot = pre_turn_model_features(m, buttons, clicking, tried_click_ctx, clicked_types, None, trace,
                                           last_label_state)

    # turn walk
    nonreset = [s for s in trace.steps if not s.reset]
    pos_in_nonreset = {s.i: n for n, s in enumerate(nonreset)}
    labels_nr = [s.label for s in nonreset]
    rows = []
    prev = None
    stall_actions = stall_turns = 0
    actions_in_level = 0
    last_surp = None
    turn_idx = 0
    last_step_kind = "start"      # start / reset / game_over / normal
    level_seen = None
    snap = None
    all_ids = sorted(set(meta) | set(by_turn))
    for k in all_ids:
        ss = by_turn.get(k, [])
        md = meta.get(k, {"rows": 0, "requests": [], "timeouts": 0, "yields": 0, "game_left": None,
                          "suite_left": None, "think_text_chars": 0, "clock": None})
        if ss:
            snap = snapshots[ss[0].i]
        else:
            snap = snap_for_gap(snapshots, end_snapshot, trace, by_turn, k)
        nr = [s for s in ss if not s.reset]
        info = [step_info[s.i] for s in nr]
        surps = [x[0] for x in info]
        new = any(x[1] for x in info)
        clear = any(x[2] == "level_clear" for x in info)
        gover = any(x[2] == "game_over" for x in info)
        first_nr = nr[0] if nr else None
        clear_k = {}
        for kk in K_CLEAR:
            if first_nr is None:
                clear_k[kk] = int(clear)
            else:
                p0 = pos_in_nonreset[first_nr.i]
                clear_k[kk] = int(any(lb == "level_clear" for lb in labels_nr[p0:p0 + kk]))
        reqs = md["requests"]
        level_now = None
        if ss:
            try:
                level_now = int(ss[0].row.get("level"))
            except (TypeError, ValueError):
                level_now = None
        row = {
            "path": trace.path, "run": trace.run, "game": trace.game, "nick": trace.nick, "gtype": trace.gtype,
            "pass": trace.pass_no, "turn_id": k, "turn_idx": turn_idx,
            # thinking
            "think_total": sum(r[0] for r in reqs), "think_first": reqs[0][0] if reqs else 0,
            "n_requests": len(reqs), "content_chars": sum(r[1] for r in reqs), "tool_arg_chars": sum(r[2] for r in reqs),
            "think_text_chars": md["think_text_chars"], "analysis_rows": md["rows"], "timeouts": md["timeouts"],
            "yields": md["yields"], "game_left": md["game_left"], "suite_left": md["suite_left"],
            "clock": md["clock"],
            # pre-turn features
            "first_turn": int(turn_idx == 0),
            "just_cleared": int(prev is not None and prev["clear"] == 1),
            "after_reset": int(last_step_kind in ("reset", "game_over")),
            "level_start": int(turn_idx == 0 or (prev is not None and prev["clear"] == 1) or last_step_kind in ("reset", "game_over")),
            "last_surp": last_surp, "prev_max_surp": prev["max_surp"] if prev else None,
            "prev_mean_surp": prev["mean_surp"] if prev else None,
            "stall_actions": stall_actions, "stall_turns": stall_turns, "actions_in_level": actions_in_level,
            "last_batch": prev["n_actions"] if prev else 0, "level": level_now if level_now is not None else level_seen,
            **snap,
            # outcomes
            "n_actions": len(nr), "n_resets": len(ss) - len(nr), "new": int(new), "clear": int(clear),
            "game_over": int(gover), "info": int(new or clear),
            "clear5": clear_k[5], "clear10": clear_k[10],
            "sum_surp": sum(surps), "max_surp": max(surps) if surps else None,
            "mean_surp": sum(surps) / len(surps) if surps else None,
        }
        rows.append(row)
        # state after the turn
        prev = row
        turn_idx += 1
        if level_now is not None:
            level_seen = level_now
        for s in ss:
            if s.reset:
                last_step_kind = "reset"
                actions_in_level = 0
                continue
            sp, is_new, lab = step_info[s.i]
            last_surp = sp
            last_step_kind = "game_over" if lab == "game_over" else "normal"
            actions_in_level = 0 if lab == "level_clear" else actions_in_level + 1
            stall_actions = 0 if (is_new or lab == "level_clear") else stall_actions + 1
        if ss:
            stall_turns = 0 if row["info"] else stall_turns + 1
        else:
            stall_turns += 1
        if row["clear"] and level_now is not None:
            level_seen = level_now + 1
    # wall clock: seconds since the play's first turn header, and seconds to the next turn header
    # (the header time is when the turn's transcript row was opened; midnight wrap handled)
    t0, prev_c, day = None, None, 0
    for r in rows:
        c = r.pop("clock")
        if c is None:
            r["elapsed_s"] = None
            continue
        if prev_c is not None and c + day < prev_c - 43200:
            day += 86400
        c += day
        prev_c = c
        t0 = c if t0 is None else t0
        r["elapsed_s"] = c - t0
    for a, b in zip(rows, rows[1:]):
        a["turn_wall_s"] = (b["elapsed_s"] - a["elapsed_s"]) if a["elapsed_s"] is not None and b["elapsed_s"] is not None else None
    if rows:
        rows[-1]["turn_wall_s"] = None
    notes = {"order_violations": order_viol, "turns": len(rows), "turns_without_actions": sum(1 for r in rows if not r["n_actions"])}
    return rows, notes


def snap_for_gap(snapshots, end_snapshot, trace, by_turn, k):
    """Model features for a turn that issued no action: the snapshot of the next turn that did (the
    model state is the same, since nothing happened in between), else the end-of-play state."""
    later = [kk for kk in by_turn if kk > k]
    if later:
        return snapshots[by_turn[min(later)][0].i]
    return end_snapshot


def pre_turn_model_features(m, buttons, clicking, tried_click_ctx, clicked_types, step, trace, last_label):
    cands = [(b,) for b in buttons]
    if clicking:
        cands += sorted(tried_click_ctx, key=repr) + [FRESH_CLICK]
    hs, nv = [], []
    for c in cands:
        h, n = predictive(m, chain_key(c, last_label))
        hs.append(h)
        nv.append(n)
    untried_btn = sum(1 for b in buttons if m.n[((b,),)] == 0) if buttons else 0
    # untried clickable object types on the board the model is looking at
    ut_click = None
    n_types = None
    if clicking and step is not None:
        pa = step.pa
        if pa is None and not step.reset:
            pa = None
        if pa is not None:
            types = set(pa.by_type())
            n_types = len(types)
            ut_click = len(types - clicked_types)
    return {
        "n_cands": len(cands), "ent_mean": sum(hs) / len(hs) if hs else None, "ent_min": min(hs) if hs else None,
        "ent_max": max(hs) if hs else None, "pnovel_mean": sum(nv) / len(nv) if nv else None,
        "pnovel_max": max(nv) if nv else None, "untried_btn": untried_btn,
        "untried_btn_share": untried_btn / len(buttons) if buttons else None,
        "untried_click_types": ut_click, "board_types": n_types, "vocab": len(m.vocab), "model_steps": m.N,
    }


# ---------------------------------------------------------------- calibration

def job_dir_of(path: str) -> Path:
    p = Path(path).parent            # .../artifacts
    return p.parent if p.parent.name != "output" else p.parent.parent


def calibration(paths) -> dict:
    """Per job with a vLLM metrics file: generated tokens vs chars written by the model."""
    out = {}
    for jd in sorted({job_dir_of(p) for p in paths}):
        prom = jd / "vllm-metrics-final.prom"
        if not prom.exists():
            continue
        gen = req = None
        req = 0.0
        for line in prom.read_text().splitlines():
            if line.startswith("vllm:generation_tokens_total"):
                gen = float(line.split()[-1])
            if line.startswith("vllm:request_success_total"):
                req += float(line.split()[-1])
        rc = cc = ta = nreq = 0
        art = jd / "artifacts"
        for f in sorted(art.glob("*_events.jsonl")):
            with open(f) as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if r.get("type") != "analysis":
                        continue
                    for a, b, c in parse_request_blocks(r.get("transcript") or ""):
                        rc += a
                        cc += b
                        ta += c
                        nreq += 1
        out[jd.name] = {"generation_tokens": gen, "vllm_requests": req, "logged_requests": nreq,
                        "reasoning_chars": rc, "content_chars": cc, "tool_arg_chars": ta,
                        "chars_per_token_all": (rc + cc + ta) / gen if gen else None,
                        "reasoning_share_of_chars": rc / (rc + cc + ta) if rc + cc + ta else None}
    return out


# ---------------------------------------------------------------- driver

def _one(i):
    t = G["traces"][i]
    t0 = time.time()
    rows, notes = play_turns(t)
    return i, rows, notes, time.time() - t0


G = {}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=N_PLAYS)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    T = {}
    t0 = time.time()
    paths = ep.trace_paths(args.n)
    traces, cpu = oe.load_all(paths, workers=min(args.workers, 10))
    T["load_and_event_code_s"] = round(time.time() - t0, 1)
    log(f"{len(traces)} plays, {len({t.nick for t in traces})} games, loaded in {T['load_and_event_code_s']} s")
    G["traces"] = traces
    t1 = time.time()
    res = [None] * len(traces)
    notes = []
    with mp.get_context("fork").Pool(min(args.workers, 10)) as pool:
        for i, rows, nt, _ in pool.imap_unordered(_one, range(len(traces))):
            res[i] = rows
            notes.append(nt)
    T["turn_table_s"] = round(time.time() - t1, 1)
    with open(out / "turns.jsonl", "w") as fh:
        for rows in res:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    t2 = time.time()
    cal = calibration(paths)
    T["calibration_s"] = round(time.time() - t2, 1)
    (out / "calibration.json").write_text(json.dumps(cal, indent=1))
    agg = Counter()
    for nt in notes:
        agg.update(nt)
    n_turns = sum(len(r) for r in res)
    msg = [f"plays {len(traces)}; turns {n_turns}; turns without actions {agg['turns_without_actions']}; "
           f"turn-order violations {agg['order_violations']}", f"timings {json.dumps(T)}"]
    for k, v in cal.items():
        msg.append(f"calibration {k}: {json.dumps(v)}")
    (out / "extract_log.txt").write_text("\n".join(msg) + "\n")
    log("\n".join(msg))


if __name__ == "__main__":
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    main()

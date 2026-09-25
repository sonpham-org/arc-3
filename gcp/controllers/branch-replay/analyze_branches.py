"""Aggregate branch-replay results: action efficiency (live actions vs the original's remaining actions),
token efficiency (live completion tokens vs the original's remaining generation, calibrated through the
xhigh control), per effort, per level and per position in the level; plus the 'oracle switch' value.

usage: python analyze_branches.py <pack_dir> <results.jsonl ...> [--md out.md]
"""
from __future__ import annotations

import argparse, json, statistics as st
from collections import defaultdict
from pathlib import Path

BASELINES = {  # environment_files/<game>/<hash>/metadata.json baseline_actions (human), hard seven
    "bp35-0a0ad940": [21, 48, 44, 38, 33, 87, 86, 131, 163], "g50t-5849a774": [78, 175, 179, 230, 96, 54, 67],
    "lf52-271a04aa": [32, 81, 60, 71, 205, 148, 244, 109, 164, 225], "ls20-9607627b": [22, 123, 73, 84, 96, 192, 186],
    "sk48-d8078629": [61, 177, 101, 103, 230, 181, 125, 92], "tn36-ef4dde99": [32, 72, 26, 40, 30, 55, 62],
    "wa30-ee6fef47": [71, 119, 183, 98, 368, 68, 79, 442, 415]}
EFFORTS = ["xhigh", "high", "medium", "low"]


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(st.median(xs), 2) if xs else None


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 2) if xs else None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("pack"); ap.add_argument("results", nargs="+"); ap.add_argument("--md")
    a = ap.parse_args()
    plan = {j["job_id"]: j for j in json.loads((Path(a.pack) / "plan.json").read_text(encoding="utf-8"))}
    rows = []
    for f in a.results:
        for line in Path(f).read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            r = json.loads(line)
            if r.get("status") != "done" or r["job_id"] not in plan: continue
            rows.append(r)
    out = []
    P = out.append
    P(f"# Branch-replay results: {len(rows)} finished branches, {len({r['group'] for r in rows})} checkpoints, "
      f"{len({(r['game_id'], r['level']) for r in rows})} levels")
    bad = [r for r in rows if not r.get("prefix_ok")]
    P(f"replay fidelity: {len(rows) - len(bad)}/{len(rows)} branches reproduced the recorded action prefix exactly"
      + (f"; mismatches: {[(r['job_id'], r.get('prefix_mismatch_at')) for r in bad][:8]}" if bad else ""))
    rows = [r for r in rows if r.get("prefix_ok")]
    # ---- token calibration: tokens per generated char on the live xhigh control (same effort as the recording)
    ctl = [r for r in rows if r["effort"] == "xhigh" and r["live_completion_tokens"] and (r["live_reasoning_chars"] + r["live_content_chars"] + r.get("live_tool_arg_chars", 0))]
    tpc = (sum(r["live_completion_tokens"] for r in ctl) / sum(r["live_reasoning_chars"] + r["live_content_chars"] + r.get("live_tool_arg_chars", 0) for r in ctl)) if ctl else 0.30
    P(f"token calibration from {len(ctl)} xhigh control branches: {tpc:.3f} completion tokens per generated char "
      f"(applied to the recording's remaining reasoning+content+code chars to estimate its remaining tokens)")
    for r in rows:
        r["orig_tokens_est"] = r["orig_remaining_chars"] * tpc
        r["action_ratio"] = (r["live_actions"] / r["orig_remaining_actions"]) if r["orig_remaining_actions"] else None
        r["token_ratio"] = (r["live_completion_tokens"] / r["orig_tokens_est"]) if r["orig_tokens_est"] else None
        r["turn_ratio"] = (r["live_turns"] / r["orig_remaining_turns"]) if r["orig_remaining_turns"] else None
        base = BASELINES[r["game_id"]][r["level"] - 1]
        r["rhae_level"] = base / (r["expected_action_count"] - r["level_action_lo"] + 1 + r["live_actions"]) if r["solved"] else 0.0
        r["rhae_orig"] = base / (r["level_action_hi"] - r["level_action_lo"] + 1)

    def table(title, key):
        P(f"\n## {title}\n")
        P("| effort | n | solved | action ratio (med) | token ratio (med) | turn ratio (med) | tokens/branch (mean) | RHAE level (mean, unsolved=0) | RHAE original |")
        P("|---|---|---|---|---|---|---|---|---|")
        for e in EFFORTS:
            rs = [r for r in rows if r["effort"] == e and key(r)]
            if not rs: continue
            solved = [r for r in rs if r["solved"]]
            P(f"| {e} | {len(rs)} | {len(solved)}/{len(rs)} ({100*len(solved)/len(rs):.0f}%) | {med([r['action_ratio'] for r in solved])} | "
              f"{med([r['token_ratio'] for r in solved])} | {med([r['turn_ratio'] for r in solved])} | {mean([r['live_completion_tokens'] for r in rs])} | "
              f"{mean([r['rhae_level'] for r in rs])} | {mean([r['rhae_orig'] for r in rs])} |")
        P("\nratios are branch / original for the remainder of the level, solved branches only; <1 = the branch was more efficient than the recording.")

    table("All checkpoints", lambda r: True)
    for lo, hi, name in ((0, 0.34, "early (first third of the level's turns)"), (0.34, 0.67, "middle third"), (0.67, 1.01, "last third")):
        table(f"Checkpoints in the {name}", lambda r, lo=lo, hi=hi: lo <= r["frac"] < hi)
    # ---- per level
    P("\n## Per level (solve rate by effort; median action ratio in parentheses)\n")
    P("| game | level | turns | orig actions | human | " + " | ".join(EFFORTS) + " |")
    P("|---|---|---|---|---|" + "---|" * len(EFFORTS))
    for (g, L) in sorted({(r["game_id"], r["level"]) for r in rows}):
        rs = [r for r in rows if r["game_id"] == g and r["level"] == L]
        cells = []
        for e in EFFORTS:
            es = [r for r in rs if r["effort"] == e]
            sv = [r for r in es if r["solved"]]
            cells.append(f"{len(sv)}/{len(es)} ({med([r['action_ratio'] for r in sv])})" if es else "-")
        P(f"| {g[:4]} | {L} | {rs[0]['n_turns']} | {rs[0]['level_action_hi'] - rs[0]['level_action_lo'] + 1} | {BASELINES[g][L-1]} | " + " | ".join(cells) + " |")
    # ---- oracle switch value per checkpoint: cheapest effort that still solves within the original's remaining actions
    P("\n## Oracle switch value\n")
    groups = defaultdict(list)
    for r in rows: groups[r["group"]].append(r)
    saved, total, n_switch, n_groups = 0.0, 0.0, 0, 0
    per_effort_pick = defaultdict(int)
    for g, rs in groups.items():
        ctl_r = [r for r in rs if r["effort"] == "xhigh"]
        ref_tokens = mean([r["live_completion_tokens"] for r in ctl_r]) if ctl_r else rs[0]["orig_tokens_est"]
        ok = [r for r in rs if r["solved"] and r["action_ratio"] is not None and r["action_ratio"] <= 1.0 and r["effort"] != "xhigh"]
        n_groups += 1; total += ref_tokens
        if ok:
            best = min(ok, key=lambda r: r["live_completion_tokens"])
            if best["live_completion_tokens"] < ref_tokens:
                saved += ref_tokens - best["live_completion_tokens"]; n_switch += 1; per_effort_pick[best["effort"]] += 1
    P(f"checkpoints: {n_groups}; a cheaper effort solved the level with no more actions than the recording at {n_switch} of them "
      f"(picked: {dict(per_effort_pick)}); if a router made exactly those switches the remaining-level tokens would drop by "
      f"{100*saved/total:.0f}% ({saved:,.0f} of {total:,.0f} reference tokens, reference = xhigh control where available).")
    text = "\n".join(out)
    print(text)
    if a.md: Path(a.md).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

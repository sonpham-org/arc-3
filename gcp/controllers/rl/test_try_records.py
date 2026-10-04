"""CPU test of try_records.py (4-Oct-2026) on a fake rollout-server job: three finished sibling tries from one moment
(turn 5, level 2, 3 actions into the level) plus one cut by the deadline and one with a coached turn.

  python test_try_records.py
"""
from __future__ import annotations

import gzip
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import try_records as tr  # noqa: E402

RESULTS: list[tuple[bool, str]] = []
GAME = "ab12-0123abcd"


def check(ok: bool, name: str, detail: object = "") -> None:
    RESULTS.append((bool(ok), name))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail != "" else ""), flush=True)


def msg(role: str, text: str) -> dict:
    if role == "assistant":
        return {"role": "assistant", "content": None, "reasoning_content": text,
                "tool_calls": [{"id": f"c-{text}", "type": "function", "function": {"name": "python", "arguments": "{}"}}]}
    return {"role": role, "content": text}


def write_try(job: Path, k: int, *, cleared: bool, moves: int, status: str = "done", modes=("stock", "stock"),
              last_reply: bool = True, bad_mid_reply: bool = False) -> None:
    d = job / f"k{k}"
    d.mkdir(parents=True)
    res = {"job": job.name, "try": k, "status": status, "cleared": cleared, "moves_to_clear": moves if cleared else None,
           "moves": moves, "turns": 2, "turns_done": 2, "stop_reason": "cleared" if cleared else "move_budget",
           "origin": {"turn": 5, "level": 2, "actions_before": 9},
           "state_path": f"/kaggle/working/x/{job.name}/k{k}/artifacts/{GAME}_p0_tool_runtime_state.json"}
    (d / "result.json").write_text(json.dumps(res))
    steps = [{"kind": "step", "seq": i + 1, "action": m, "features": {"actions_in_level": 3 + i, "step": 5 + i},
              "outcome": {"human_moves": 6, "level_score": 99.0}} for i, m in enumerate(modes)]
    with gzip.open(d / "master.jsonl.gz", "wt", encoding="utf-8") as fh:
        for row in [{"kind": "rollout", "result": {"game_id": GAME}}] + steps:
            fh.write(json.dumps(row) + "\n")
    sys_m, u4, a4, u5 = msg("system", "rules"), msg("user", "turn 4"), msg("assistant", f"a4"), msg("user", "turn 5")
    a5, u6, a6 = msg("assistant", f"a5-k{k}"), msg("user", "turn 6"), msg("assistant", f"a6-k{k}")
    rows = [{"event": "request", "analysis_step": 5, "request_index_within_turn": 1, "messages": [sys_m, u4, a4, u5]},
            {"event": "response", "analysis_step": 5, "request_index_within_turn": 1, "usage": {"prompt_tokens": 100}},
            {"event": "request", "analysis_step": 6, "request_index_within_turn": 1,
             "messages": [sys_m, u4, a4, u5, a5, u6]},
            {"event": "response", "analysis_step": 6, "request_index_within_turn": 1, "usage": {"prompt_tokens": 140}}]
    (d / "requests.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    reps = [{"analysis_step": 5, "request_index_within_turn": 1,
             "message": msg("assistant", "something else") if bad_mid_reply else a5}]
    if last_reply:
        reps.append({"analysis_step": 6, "request_index_within_turn": 1, "message": a6})
    (d / "replies.jsonl").write_text("".join(json.dumps(r) + "\n" for r in reps))


def main() -> int:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        job = Path(tmp) / "v1r1-r001-ab12-node"
        write_try(job, 0, cleared=True, moves=3)                       # (6 / (3 + 3))^2 = 1.0
        write_try(job, 1, cleared=True, moves=9)                       # (6 / 12)^2 = 0.25
        write_try(job, 2, cleared=False, moves=40, bad_mid_reply=True, last_reply=False)   # 0
        write_try(job, 3, cleared=True, moves=1, status="deadline")    # cut: left out
        write_try(job, 4, cleared=True, moves=2, modes=("probe", "stock"))   # coached turn: left out with --modes stock
        dirs = sorted(p.parent for p in Path(tmp).rglob("result.json"))
        recs, rep = tr.build(dirs, modes={"stock"}, group_by="job", min_tries=2, campaign="t")
        st = rep["stats"]
        check(st.get("skip: status deadline") == 1 and st.get("skip: turn outside modes") == 1,
              "the deadline-cut try and the coached try are left out", st)
        g = rep["groups"][0]
        check(g["tries"] == 3 and g["rewards"] == [1.0, 0.25, 0.0],
              "rewards = the scorer's level score with the level's earlier actions counted (0 when not cleared)", g)
        by = {r["meta"]["try"]: r for r in recs}
        mean = (1.0 + 0.25) / 3
        check(set(by) == {0, 1, 2} and abs(by[0]["meta"]["advantage"] - (1.0 - mean)) < 1e-3
              and abs(by[2]["meta"]["advantage"] + mean) < 1e-3 and by[1]["meta"]["advantage"] < 0,
              "advantage = reward minus the siblings' mean (one record per try here)",
              {k: r["meta"]["advantage"] for k, r in by.items()})
        r0 = by[0]
        check(r0["train"] == [False, False, False, False, True, False, True] and r0["meta"]["reply_appended"],
              "trained: the try's own replies (turns 5 and 6, the last from replies.jsonl); turn 4's reply is context",
              r0["train"])
        check(r0["messages"][6]["reasoning_content"] == "a6-k0" and r0["weights"][4] == r0["weights"][6]
              and abs(r0["weights"][6] - r0["meta"]["advantage"]) < 1e-3,
              "the appended last reply is the try's own; each trained reply carries the try's advantage",
              r0["weights"])
        check(not by[2]["meta"]["reply_appended"] and by[2]["train"] == [False, False, False, False, True, False],
              "without a logged last reply the record ends at the last request (that reply is lost)", by[2]["train"])
        check(st.get("reply check same") == 2 and st.get("reply check DIFFERENT") == 1,
              "logged mid replies are compared with the next request's copy (a changed one is counted)", st)
        check(by[0]["meta"]["game"] == GAME and by[0]["meta"]["pass"] == f"{job.name}.k0",
              "meta names the game and the try (select_records caps records per try)", by[0]["meta"])
        st3: dict = tr.Counter()
        cut = tr.try_records(tr.load_try(job / "k0"), 0.5, {"run": "t"}, st3, max_tokens=120)
        check(len(cut) == 1 and cut[0]["train"] == [False, False, False, False, True] and cut[0]["meta"]["reply_appended"]
              and st3["stretches cut to fit"] == 1,
              "a stretch longer than --max-tokens ends at the last request that fits (its logged reply appended)",
              [c["train"] for c in cut])
        recs2, rep2 = tr.build(dirs, modes=None, group_by="job", min_tries=2, campaign="t")
        check(rep2["groups"][0]["tries"] == 4, "without --modes the coached try counts too", rep2["groups"][0])
    bad = [n for ok, n in RESULTS if not ok]
    print(f"{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed" + (f"; FAILED {bad}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

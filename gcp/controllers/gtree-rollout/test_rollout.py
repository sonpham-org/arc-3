"""Local tests for the mid-tree rollout driver: Daniel's real harness on Windows, a stub model, no GPU.

Author: Claude Opus 5.5 (3-Oct-2026).

  D:/codex-work/_branch/venv/Scripts/python.exe test_rollout.py [--quick] [--work DIR]

Source play: D:/codex-work/rl-20261001/fork-dev/dc22-fdcac232_p0_requests.jsonl (a daniel-base run with request logs).
dc22 is a FENCED game: test data only. Its records stay under the work dir and are marked not publishable.

1. replay_exact to several origins (early, mid, the turn after a game over, late): every rebuilt request equals the
   log (clock readings masked), the board at the origin equals the logged opener's grid image, and the first live
   request (sent to the stub) is the logged origin request itself.
   Mutation: one logged tool result before the origin is altered -> the try must stop as diverged at that call.
2. replay_actions to the mid origin from the moves of test 1's event log: the engine board after the prefix equals
   the logged board (decoded from the logged origin opener), and the t1 node equals the one the event log gives.
3. live: K=3 tries from one origin with the turn coach on (rules), 3 lanes at once: each try restores the identical
   state (same board, same context digest, byte-identical first live request carrying the coach line) and writes a
   rollout record with origin_state / origin_kind / origin_edge from the job.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import local_env as le  # noqa: E402

SRC_REQ = Path(r"D:\codex-work\rl-20261001\fork-dev\dc22-fdcac232_p0_requests.jsonl")
GAME_ID = "dc22-fdcac232"
STUB_CODE = ("a = valid_actions[0] if valid_actions else 'UP'\n"
             "r = action([{'action': a}])\n"
             "print('stub moved', a)")
RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> bool:
    RESULTS.append((bool(ok), name, detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)
    return bool(ok)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="fewer origins (early + after the first game over)")
    ap.add_argument("--work", default=r"D:\codex-work\gtree-rollout-test")
    a = ap.parse_args()
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    stub = le.StubModel(STUB_CODE)
    os.environ.update(le.notebook_env(stub.url))
    os.environ.update({"ARC3_ROLLOUT": "1", "ARC3_COACH": "policy",          # bind() sets the coach master switch
                       "ARC3_COACH_LOG": str(work / "coach-decisions.jsonl")})
    (work / "coach-decisions.jsonl").unlink(missing_ok=True)
    bundle = le.prepare_bundle(work / "bundle")
    le.put_on_path(bundle)
    le.windows()
    import rollout_core as core
    import rollout_driver as rd
    from inference.agent import tool_agent as ta
    solver = le.solver_template(bundle)
    spec = le.arcade_spec()
    out = work / "tries"
    seq = core.fr.load_sequence(SRC_REQ)
    first_of = {}
    for i, r in enumerate(seq):
        first_of.setdefault(r["step"], i)

    def logged_hash(turn: int) -> str:
        return core.logged_screen_hash(seq[first_of[turn]]["messages"], rd.PALETTE)

    def after_game_over(turn: int) -> bool:          # the opener says so (the harness's own words)
        return "GAME OVER occurred during the previous sequence" in json.dumps(seq[first_of[turn]]["messages"][-1])

    turns = sorted(first_of)
    go_turn = next(t for t in turns if t > 2 and after_game_over(t))
    origins = {"early": 3, "after_game_over": go_turn} if a.quick else \
        {"early": 3, "mid": 30, "after_game_over": go_turn, "late": 70}
    print(f"source: {len(seq)} calls, turns {turns[0]}..{turns[-1]}; origins {origins}", flush=True)

    def job(job_id, mode, turn, **kw):
        j = {"job_id": job_id, "campaign": "localtest", "game_id": GAME_ID, "pass": 0, "mode": mode, "tries": 1,
             "source": {"run": "fork-dev", "rollout_id": "fork-dev:dc22_p0", "requests": str(SRC_REQ)},
             "origin": {"turn": turn, "screen_hash": logged_hash(turn)},
             "stop": {"turn_cap": 1}, "coach": {"spec": "off"}}
        for k2, v in kw.items():
            j[k2] = {**j[k2], **v} if isinstance(v, dict) and isinstance(j.get(k2), dict) else v
        return j

    def first_live_of(n_before: int) -> dict | None:
        return stub.requests[n_before] if len(stub.requests) > n_before else None

    # ---- 1. replay_exact ---------------------------------------------------------------------------------------
    exact_results = {}
    for name, turn in origins.items():
        n0 = len(stub.requests)
        t0 = time.time()
        r = rd.run_try(job(f"exact-{name}-t{turn}", "replay_exact", turn), 0, solver, spec, out, allow_fenced=True)
        exact_results[name] = r
        v = r["replay"]["verdicts"]
        check(r["status"] == "done", f"replay_exact {name} (turn {turn}): restored and played",
              f"status {r['status']} {r.get('diverged') or r.get('aborted') or ''}"[:400])
        check(set(v) <= set(core.SAME) and r["replay"]["calls"] == first_of[turn],
              f"replay_exact {name}: all {first_of[turn]} rebuilt requests equal the log (clock masked, images by pixels)",
              f"verdicts {v} first_issue {json.dumps(r['replay']['first_issue'])[:300]}")
        o = r.get("origin") or {}
        check(o.get("mismatch") == {} and o.get("screen_hash") == logged_hash(turn)
              and o.get("logged_image_screen_hash") == o.get("screen_hash"),
              f"replay_exact {name}: board at the origin = the logged opener's grid image",
              f"screen {o.get('screen_hash')} logged {logged_hash(turn)} level {o.get('level')} "
              f"actions {o.get('actions_before')}")
        check(o.get("request_verdict") in core.SAME,
              f"replay_exact {name}: origin request rebuilt = logged", str(o.get("request_verdict")))
        fl = first_live_of(n0)
        want = ta._strip_control_keys(copy.deepcopy(seq[first_of[turn]]["messages"]))   # as _chat_completion sends
        check(fl is not None and fl["messages"] == want,
              f"replay_exact {name}: first live request = the logged origin request, byte for byte",
              f"{len(fl['messages']) if fl else None} msgs")
        rec = r.get("records") or {}
        check(rec.get("steps", 0) >= 1 and rec.get("publishable") is False,
              f"replay_exact {name}: rollout record written (fenced: not publishable)", json.dumps(rec)[:300])
        print(f"   wall {time.time() - t0:.0f}s", flush=True)

    # mutation: alter one logged tool result before the origin -> must diverge there
    mut_turn = 3
    k = next(i for i in range(first_of[mut_turn]) if any(m.get("role") == "tool" for m in seq[i]["messages"]))
    mut_path = work / "mutated_requests.jsonl"
    with open(SRC_REQ, encoding="utf-8") as fh, open(mut_path, "w", encoding="utf-8") as w:
        req_n = -1
        for line in fh:
            row = json.loads(line)
            if row.get("event") == "request":
                req_n += 1
                if req_n == k:
                    tm = [m for m in row["messages"] if m.get("role") == "tool"][-1]
                    tm["content"] = tm["content"].replace('"level"', '"levl"', 1) if '"level"' in tm["content"] \
                        else "MUTATED " + tm["content"]
            w.write(json.dumps(row) + "\n")
    r = rd.run_try(job("mutation", "replay_exact", mut_turn, source={"requests": str(mut_path)}), 0, solver, spec,
                   out, allow_fenced=True)
    check(r["status"] == "diverged" and (r.get("diverged") or {}).get("call") == k,
          "mutation: an altered logged tool result stops the replay at that call",
          f"status {r['status']} diverged {json.dumps(r.get('diverged'))[:300]}")

    # ---- 2. replay_actions -------------------------------------------------------------------------------------
    src_name = "mid" if "mid" in exact_results else "after_game_over"
    t_act = origins[src_name]
    ev_src = out / f"exact-{src_name}-t{t_act}" / "k0" / "artifacts" / f"{GAME_ID}_p0_events.jsonl"
    if not check(ev_src.exists(), f"replay_actions: source event log from the {src_name} try exists", str(ev_src)):
        return finish(stub, work)
    j = job(f"actions-t{t_act}", "replay_actions", t_act, source={"events": str(ev_src)})
    j["source"].pop("requests")
    facts = core.origin_facts(core.normalize_job(j), core.read_lines(ev_src))
    j["origin"]["t1"] = facts["t1"]          # the tree node from the source event log: the try's must equal it
    r = rd.run_try(j, 0, solver, spec, out, allow_fenced=True)
    o = r.get("origin") or {}
    check(r["status"] == "done" and o.get("mismatch") == {},
          f"replay_actions (turn {t_act}): prefix of {facts['actions_before']} moves replayed, origin checks pass",
          f"status {r['status']} {r.get('aborted') or ''} origin {json.dumps(o)[:300]}")
    logged_board = core.decode_board(core.opener_image_url(seq[first_of[t_act]]["messages"]), rd.PALETTE)
    ev = (out / j["job_id"] / "k0" / "artifacts" / f"{GAME_ID}_p0_events.jsonl").read_text(encoding="utf-8")
    _ini, acts, steps, states = core.play_steps(ev.splitlines())
    st = next(s for s in steps if s["turn"] == t_act)
    engine_board = states[st["s"]][0]
    check(engine_board == logged_board and o.get("screen_hash") == logged_hash(t_act),
          "replay_actions: engine board after the prefix = the logged board (decoded from the logged opener)",
          f"{sum(a != b for x, y in zip(engine_board, logged_board) for a, b in zip(x, y))} cells differ")
    rec = r.get("records") or {}
    check(rec.get("t1_match") is True and o.get("actions_before") == facts["actions_before"],
          "replay_actions: the try's origin t1 node = the source event log's", json.dumps(rec)[:300])
    check(r["turns"] >= 1, "replay_actions: live from a fresh context",
          f"turns {r['turns']} moves {r['moves']} stop {r['stop_reason']}")

    # ---- 3. live: K tries, coach on, concurrent ----------------------------------------------------------------
    n0 = len(stub.requests)
    live_turn = 3
    jl = job("live-k3", "replay_exact", live_turn, tries=3, stop={"turn_cap": 2},
             coach={"spec": "rules"}, origin={"seq": 3, "t1": None})
    jl["origin"].pop("t1")
    res = rd.run_job(jl, solver, spec, out, lanes=3, allow_fenced=True)
    check(len(res) == 3 and all(x["status"] == "done" for x in res), "live: 3 tries done",
          str([(x["status"], x["stop_reason"], x["turns"], x["moves"]) for x in res]))
    os_ = [x["origin"] for x in res]
    check(len({(o["screen_hash"], o["level"], o["actions_before"], o["context_digest"]) for o in os_}) == 1,
          "live: every try starts from the identical restored state (board, level, moves, context digest)",
          str({(o["screen_hash"], o["level"], o["actions_before"], o["context_digest"][:12]) for o in os_}))
    firsts = [b for b in stub.requests[n0:] if "call_stub_" not in json.dumps(b["messages"])]
    tail = os_[0].get("tails", {}).get("tail_live", "")
    check(len(firsts) == 3 and all(json.dumps(b["messages"]) == json.dumps(firsts[0]["messages"]) for b in firsts)
          and tail.startswith("Focus for this turn:") and tail in json.dumps(firsts[0]["messages"]),
          "live: the 3 first live requests are byte-identical and carry the coach's line",
          f"{len(firsts)} first requests, tail {tail[:60]!r}, temperatures {[b.get('temperature') for b in firsts]}")
    logged_sans_tail = ta._strip_control_keys(core.split_tail(seq[first_of[live_turn]]["messages"])[0])
    check(bool(firsts) and core.split_tail(firsts[0]["messages"])[0] == logged_sans_tail,
          "live: first live request = the logged origin request + the coach line")
    recs = []
    for k in range(3):
        p = out / "live-k3" / f"k{k}" / "rollout.jsonl"
        lines = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []
        recs.append(lines)
    ro = [next((x for x in L if x["kind"] == "rollout"), None) for L in recs]
    st1 = [next((x for x in L if x["kind"] == "step"), None) for L in recs]
    check(all(ro) and len({r_["id"] for r_ in ro}) == 3
          and all(r_["origin_kind"] == "replay_exact" and r_["origin_edge"] == "fork-dev:dc22_p0:2" for r_ in ro)
          and all(r_["origin_state"] == s["n1"] and s["seq"] == 1 and s["detail"]["turn"] == live_turn
                  for r_, s in zip(ro, st1))
          and len({r_["origin_state"] for r_ in ro}) == 1,
          "live: 3 rollout records with origin_state (t1) / origin_kind / origin_edge from the job",
          str([(r_["id"], r_["origin_state"], r_["origin_edge"], r_["result"].get("stop_reason")) for r_ in ro if r_]))
    acts_ = [[x["action"] for x in L if x["kind"] == "step"] for L in recs]
    check(all(s and s[0] == "probe" for s in acts_), "live: the coach's live decisions label the steps",
          str(acts_))
    ctx_ok = all(x["ctx_before"] and x["resumable"] for L in recs for x in L if x["kind"] == "step")
    check(ctx_ok, "live: every live step has its context node (ctx_before, resumable)")
    return finish(stub, work)


def finish(stub, work: Path) -> int:
    stub.close()
    bad = [n for ok, n, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed" + (f"; FAILED: {bad}" if bad else ""))
    (work / "test_results.json").write_text(json.dumps([{"ok": o, "name": n, "detail": d} for o, n, d in RESULTS],
                                                       indent=1), encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

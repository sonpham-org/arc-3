"""Local tests for state snapshots (arc3_state.py): Daniel's real harness on Windows, a stub model, no GPU.

Author: Claude Opus 5.5 (3-Oct-2026, Son: "make restores confident and fast with STATE SNAPSHOTS").

  D:/codex-work/_branch/venv/Scripts/python.exe test_state.py [--work DIR] [--turn 30]

1. process A: replay_exact to the origin turn (the restore cache captures a snapshot there), one live turn.
2. process B (a fresh python, a fresh bundle): mode 'snapshot' from that file, no replay: the engine board, level and
   action count equal the origin's; the rebuilt origin request equals the logged one (clock masked, images by
   pixels) and the first live request is the logged request byte for byte; the board equals the logged opener's
   grid image. Mutations: a snapshot whose action prefix lost its last move, and one whose system prompt differs,
   are refused (the try aborts with the reason; no request is sent).
3. per-turn hook (ARC3_STATE_SNAPSHOTS=1) on a live try: one snapshot per fresh live turn (not the replayed ones, not
   the origin twice), its cost in ms and its size, and the try's step records carry state_ref.
Source play: the fork-dev dc22 request log (FENCED: test data only).
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import os
import pickle
import subprocess
import sys
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


def setup(work: Path, bundle_name: str, extra_env: dict | None = None):
    stub = le.StubModel(STUB_CODE)
    os.environ.update(le.notebook_env(stub.url))
    os.environ.update({"ARC3_ROLLOUT": "1", "ARC3_COACH": "policy", "ARC3_COACH_LOG": str(work / "coach.jsonl"),
                       "ARC3_MAX_ACTIVE_STREAMS": "0", **(extra_env or {})})
    bundle = le.prepare_bundle(work / bundle_name)
    le.put_on_path(bundle)
    le.windows()
    import rollout_core as core
    import rollout_driver as rd
    return stub, core, rd, le.solver_template(bundle), le.arcade_spec()


def job(job_id, mode, turn, **kw):
    j = {"job_id": job_id, "campaign": "statetest", "game_id": GAME_ID, "pass": 0, "mode": mode, "tries": 1,
         "source": {"run": "fork-dev", "rollout_id": "fork-dev:dc22_p0", "requests": str(SRC_REQ)},
         "origin": {"turn": turn}, "stop": {"turn_cap": 1}, "coach": {"spec": "off"}}
    for k, v in kw.items():
        j[k] = {**j[k], **v} if isinstance(v, dict) and isinstance(j.get(k), dict) else v
    return j


def phase_restore(a) -> int:
    """Process B: restore from the snapshot (and two mutated copies) in a fresh process; print one JSON line."""
    work = Path(a.work)
    stub, core, rd, solver, spec = setup(work, "bundle-b")
    from inference.agent import tool_agent as ta
    seq = core.fr.load_sequence(SRC_REQ)
    first = next(i for i, r in enumerate(seq) if r["step"] == a.turn)
    logged = seq[first]["messages"]
    msgs_path = work / "origin_messages.json"
    msgs_path.write_text(json.dumps(logged), encoding="utf-8")
    origin = json.loads(Path(a.origin).read_text(encoding="utf-8"))
    out = {}
    for name, snap in (("good", a.snap), ("bad_prefix", a.snap_bad_prefix), ("bad_prompt", a.snap_bad_prompt)):
        n0 = len(stub.requests)
        j = job(f"snap-{name}", "snapshot", a.turn,
                source={"state": snap, "state_ref": Path(snap).name.split(".")[0], "origin_messages": str(msgs_path),
                        "requests": None},
                origin={"seq": origin.get("seq"), "screen_hash": origin["screen_hash"], "level": origin["level"],
                        "actions_before": origin["actions_before"]})
        r = rd.run_try(j, 0, solver, spec, work / "tries-b", allow_fenced=True)
        fl = stub.requests[n0] if len(stub.requests) > n0 else None
        out[name] = {"status": r["status"], "aborted": r.get("aborted"), "origin": r.get("origin"),
                     "state": r.get("state"), "wall_s": r.get("wall_s"), "restore_s": r.get("restore_s"),
                     "requests_sent": len(stub.requests) - n0,
                     "first_live_equals_logged": bool(fl) and fl["messages"] == ta._strip_control_keys(
                         copy.deepcopy(logged)),
                     "records": r.get("records")}
    stub.close()
    print("PHASE_B " + json.dumps(out, default=str), flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default=r"D:\codex-work\gtree-rollout-test\state")
    ap.add_argument("--turn", type=int, default=30)
    ap.add_argument("--phase", default="a")
    ap.add_argument("--snap")
    ap.add_argument("--snap-bad-prefix")
    ap.add_argument("--snap-bad-prompt")
    ap.add_argument("--origin")
    a = ap.parse_args()
    if a.phase == "b":
        return phase_restore(a)
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    stub, core, rd, solver, spec = setup(work, "bundle-a")
    out = work / "tries-a"

    # ---- 1. replay to the origin; the restore cache snapshots it ----------------------------------------------------
    r = rd.run_try(job("replay", "replay_exact", a.turn), 0, solver, spec, out, allow_fenced=True)
    cap = (r.get("state") or {}).get("captured") or {}
    check(r["status"] == "done" and cap.get("sha"), f"1: replay_exact to turn {a.turn} done; origin snapshot captured",
          f"status {r['status']} restore {r.get('restore_s')}s snapshot {json.dumps(cap)}")
    snap = out / "replay" / "k0" / "state" / f"{cap.get('sha')}.pkl.gz"
    origin = r.get("origin") or {}
    (work / "origin.json").write_text(json.dumps(origin), encoding="utf-8")
    doc = pickle.loads(gzip.decompress(snap.read_bytes()))
    sizes = {k: len(pickle.dumps(v)) for k, v in doc.items()}
    big = sorted(((k, len(pickle.dumps(v))) for k, v in doc["agent"].items()), key=lambda x: -x[1])[:4]
    print(f"   snapshot {snap.stat().st_size / 1e6:.2f} MB gz; parts (pickled bytes) {sizes}; biggest agent fields {big}")
    bad = copy.deepcopy(doc)
    bad["prefix"] = bad["prefix"][:-1]
    p_bad1 = work / "bad_prefix.pkl.gz"
    p_bad1.write_bytes(gzip.compress(pickle.dumps(bad), 6, mtime=0))
    bad = copy.deepcopy(doc)
    bad["meta"]["system_prompt_sha"] = "0" * 64
    p_bad2 = work / "bad_prompt.pkl.gz"
    p_bad2.write_bytes(gzip.compress(pickle.dumps(bad), 6, mtime=0))

    # ---- 2. a fresh process restores it -----------------------------------------------------------------------------
    cmd = [sys.executable, str(Path(__file__).resolve()), "--phase", "b", "--work", str(work), "--turn", str(a.turn),
           "--snap", str(snap), "--snap-bad-prefix", str(p_bad1), "--snap-bad-prompt", str(p_bad2),
           "--origin", str(work / "origin.json")]
    pb = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    line = next((x for x in pb.stdout.splitlines() if x.startswith("PHASE_B ")), None)
    if not check(line is not None, "2: the fresh process ran", (pb.stderr or pb.stdout)[-800:] if line is None else ""):
        return finish(stub, work)
    b = json.loads(line[len("PHASE_B "):])
    g = b["good"]
    o = g.get("origin") or {}
    st = g.get("state") or {}
    check(g["status"] == "done" and (st.get("restored") or {}).get("moves") == origin.get("actions_before"),
          "2: restored from the snapshot in a fresh process, no turn replayed (engine: the action prefix)",
          f"status {g['status']} {g.get('aborted') or ''} restore {json.dumps(st.get('restored'))}")
    check(o.get("mismatch") == {} and o.get("screen_hash") == origin.get("screen_hash")
          and o.get("level") == origin.get("level") and o.get("actions_before") == origin.get("actions_before"),
          "2: board, level and action count equal the replayed origin's",
          f"{o.get('screen_hash')} L{o.get('level')} {o.get('actions_before')} vs {origin.get('screen_hash')} "
          f"L{origin.get('level')} {origin.get('actions_before')}")
    check(o.get("logged_image_screen_hash") == o.get("screen_hash"),
          "2: the board equals the logged opener's grid image", str(o.get("logged_image_screen_hash")))
    check(o.get("request_verdict") in core.SAME and o.get("context_digest") == origin.get("context_digest"),
          "2: the restored agent rebuilds the logged origin request (clock masked, images by pixels), same digest "
          "as the replay's", f"{o.get('request_verdict')} {str(o.get('context_digest'))[:12]}")
    check(g["first_live_equals_logged"], "2: the first live request is the logged origin request, byte for byte")
    check((g.get("records") or {}).get("t1_match") is True or (g.get("records") or {}).get("steps"),
          "2: the restored try writes its records", json.dumps(g.get("records"))[:200])
    for name, why in (("bad_prefix", "engine after the prefix"), ("bad_prompt", "system prompt differs")):
        x = b[name]
        check(x["status"] == "aborted" and why in str(x.get("aborted")) and x["requests_sent"] == 0,
              f"2: mutation {name}: refused before any request ({why})", str(x.get("aborted"))[:200])
    speed = (r.get("restore_s") or 0, (st.get("restored") or {}).get("restore_ms"), g.get("restore_s"))
    print(f"   restore: replay {speed[0]} s vs snapshot {speed[1]} ms (whole try setup to origin {speed[2]} s)")

    # ---- 3. the per-turn hook on a live try -------------------------------------------------------------------------
    os.environ["ARC3_STATE_SNAPSHOTS"] = "1"
    r3 = rd.run_try(job("hook", "replay_exact", 3, stop={"turn_cap": 3}), 0, solver, spec, out, allow_fenced=True)
    os.environ.pop("ARC3_STATE_SNAPSHOTS")
    idx = out / "hook" / "k0" / "state" / "index.jsonl"
    rows = [json.loads(x) for x in idx.read_text(encoding="utf-8").splitlines()] if idx.exists() else []
    turns = [x["analysis_step"] for x in rows]
    live = [x for x in rows if x.get("kind") != "origin"]
    check(r3["status"] == "done" and turns and turns[0] == 3 and sorted(set(turns)) == turns and len(live) >= 1
          and all(t > 3 for t in (x["analysis_step"] for x in live)),
          "3: one snapshot per fresh turn: the origin (restore cache) + each later live turn, none while replaying",
          f"turns {turns} ({r3['turns']} live turns)")
    ms = [x["ms"] for x in live]
    mb = [x["bytes"] / 1e6 for x in live]
    check(bool(ms), "3: hook cost measured", f"ms per turn {ms}, MB per snapshot {[round(v, 2) for v in mb]}")
    lines = (out / "hook" / "k0" / "rollout.jsonl").read_text(encoding="utf-8").splitlines()
    steps = [json.loads(x) for x in lines if '"kind": "step"' in x[:20] or '"kind":"step"' in x[:20]]
    refs = (out / "hook" / "k0" / "state_refs.jsonl").read_text(encoding="utf-8").splitlines()
    check(steps and all(s.get("state_ref") for s in steps[:len(turns)]) and len(refs) >= len(turns),
          "3: the try's step records carry state_ref, and state_refs.jsonl maps each snapshot to its step",
          f"{[(s['seq'], (s.get('state_ref') or '')[:8]) for s in steps]} refs {len(refs)}")
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

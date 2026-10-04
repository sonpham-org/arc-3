"""Test of the VM host sync with local directories in place of GCS (no network).

Author: Claude Opus 5.5 (3-Oct-2026).   C:/Python312/python.exe runner/test_host_sync.py

Staging: a replay_exact job (logs copied, paths rewritten to /kaggle/rollout/src/...), a snapshot job (state file
staged, the logged origin request rebuilt from a ctx chain in the store, the fallback request log NOT staged), a
fenced job refused. Policy: copied when it changes, not again when it does not. STOP: mirrored. Upload: a finished
try's master, contexts, snapshot and state index land in the store's layout; a fenced try and an unfinished one do
not; a diverged try's result.json does (its diff readable later); jobs another VM's server played, has in flight or
dropped are not staged; a second pass uploads nothing again.
"""
from __future__ import annotations

import gzip
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "gtree-ingest"))
import gtree_ctx as gc  # noqa: E402
import rl_host_sync as hs  # noqa: E402
from gtree_store import Store  # noqa: E402

RESULTS = []


def check(ok, name, detail=""):
    RESULTS.append((bool(ok), name))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="hostsync-"))
    store_dir, root, results = tmp / "store", tmp / "kroot" / "rollout", tmp / "kroot" / "working" / "gtree-rollout"
    store = Store(str(store_dir))
    rl = Store(str(store_dir / "rl" / "c1"))
    src = tmp / "duck"
    (src / "w").mkdir(parents=True)
    (src / "w" / "sb26-x_p0_requests.jsonl").write_text("{}\n")
    (src / "w" / "sb26-x_p0_events.jsonl").write_text("{}\n")
    (src / "snap.pkl.gz").write_bytes(b"snapshot")
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": [{"type": "text", "text": "hi"}]}]
    shas, _ = gc.write_chain([{"messages": msgs}], store, gc.Blobs(store))
    base = {"campaign": "c1", "round": 1, "pass": 0, "origin": {"turn": 3}, "assignments": []}
    rl.put("jobs/round-0001/0001-00000-a.json", json.dumps({**base, "job_id": "a", "game_id": "sb26-x",
           "mode": "replay_exact", "source": {"requests": str(src / "w" / "sb26-x_p0_requests.jsonl"),
                                              "events": str(src / "w" / "sb26-x_p0_events.jsonl")}}).encode())
    rl.put("jobs/round-0001/0001-00001-b.json", json.dumps({**base, "job_id": "b", "game_id": "sb26-x",
           "mode": "snapshot", "source": {"state": str(src / "snap.pkl.gz"), "ctx_before": shas[0],
                                          "requests": str(src / "w" / "sb26-x_p0_requests.jsonl")}}).encode())
    rl.put("jobs/round-0001/0001-00002-c.json", json.dumps({**base, "job_id": "c", "game_id": "dc22-y",
           "mode": "replay_exact", "source": {"requests": "x"}}).encode())
    for i, j in ((5, "e"), (6, "f"), (7, "g")):   # played / in flight / dropped by another VM's server
        rl.put(f"jobs/round-0001/0001-0000{i}-{j}.json", json.dumps({**base, "job_id": j, "game_id": "sb26-x",
               "mode": "replay_exact", "source": {"requests": str(src / "w" / "sb26-x_p0_requests.jsonl")}}).encode())
    rl.put("results/vm0/summary.json", json.dumps({"results": [{"job": "e", "try": 0, "status": "done"}],
                                                   "running": {"nodes": 1, "tries": 5, "jobs": ["f"]},
                                                   "skipped_old_round": ["0001-00007-g.json"]}).encode())
    rl.put("policy/current.json", json.dumps({"version": "c1-v0", "seq": 0}).encode())
    # finished tries
    def try_dir(job, k, game, publishable=True, status="done"):
        d = results / job / f"k{k}"
        (d / "gtree-store" / "ctx").mkdir(parents=True)
        (d / "gtree-store" / "ctx" / "abc.json.gz").write_bytes(gzip.compress(b"{}"))
        (d / "state").mkdir()
        (d / "state" / ("f" * 64 + ".pkl.gz")).write_bytes(b"state")
        (d / "state_refs.jsonl").write_text(json.dumps({"sha": "f" * 64, "rollout_id": "r", "seq": 1}) + "\n")
        (d / "master.jsonl.gz").write_bytes(gzip.compress(b'{"kind":"rollout"}\n'))
        (d / "requests.jsonl").write_bytes(b'{"event": "request"}\n')
        (d / "replies.jsonl").write_text('{"analysis_step": 1}\n')
        name = f"rollouts/gtr-c1/{game}_p0.{job}.k{k}.jsonl.gz"
        res = {"job": job, "try": k, "status": status, "records": {"master_name": name, "publishable": publishable}}
        if status == "diverged":
            res = {"job": job, "try": k, "status": status, "stop_reason": "diverged",
                   "diverged": {"kind": "origin_messages", "call": 0, "first": {"message": 1, "sent": "a", "logged": "b"}}}
        (d / "result.json").write_text(json.dumps(res))
    try_dir("c1-r001-sb26-a", 0, "sb26")
    try_dir("c1-r001-dc22-c", 0, "dc22", publishable=False)
    try_dir("c1-r001-sb26-d", 1, "sb26", status="diverged")
    (results / "summary.json").write_text("{}")
    args = hs.argparse.Namespace(campaign="c1", store=str(store_dir), root=str(root), results=str(results), vm="vm1",
                                 every=1, stage_fallback=False, cmd="once")
    s = hs.Sync(args)
    out = s.once()
    ja = json.loads((root / "jobs" / "round-0001" / "0001-00000-a.json").read_text())
    jb = json.loads((root / "jobs" / "round-0001" / "0001-00001-b.json").read_text())
    check(out["jobs"] == 2 and not (root / "jobs" / "round-0001" / "0001-00002-c.json").exists(),
          "staging: 2 jobs staged, the fenced one refused", json.dumps(out))
    ok_a = ja["source"]["requests"].startswith("/kaggle/rollout/src/") and \
        (root / "src" / ja["source"]["requests"][len("/kaggle/rollout/src/"):]).exists()
    check(ok_a, "replay_exact job: logs copied under src/ and paths rewritten for the container", ja["source"]["requests"])
    om = root / "src" / jb["source"]["origin_messages"][len("/kaggle/rollout/src/"):]
    check(jb["source"]["state"].startswith("/kaggle/rollout/src/") and om.exists() and json.loads(om.read_text()) ==
          msgs and "requests" not in jb["source"],
          "snapshot job: state staged, origin request rebuilt from ctx_before, fallback log not staged")
    check(json.loads((root / "policy" / "current.json").read_text())["version"] == "c1-v0" and out["policy"] is True,
          "policy staged")
    up = store_dir / "rollouts" / "gtr-c1" / "sb26_p0.c1-r001-sb26-a.k0.jsonl.gz"
    check(out["uploaded"] == 1 and up.exists() and (store_dir / "ctx" / "abc.json.gz").exists()
          and (store_dir / "state" / ("f" * 64 + ".pkl.gz")).exists()
          and (store_dir / "state" / "index" / "gtr-c1" / "sb26_p0.c1-r001-sb26-a.k0.jsonl").exists()
          and (store_dir / "rl" / "c1" / "results" / "vm1" / "summary.json").exists(),
          "upload: master, contexts, snapshot, state index and results in the store layout")
    check(not (store_dir / "rollouts" / "gtr-c1" / "dc22_p0.c1-r001-dc22-c.k0.jsonl.gz").exists()
          and not list((store_dir / "rollouts" / "gtr-c1").glob("*sb26-d*")),
          "upload: the fenced try and the unfinished try are not uploaded")
    tl = store_dir / "rl" / "c1" / "tries" / "vm1" / "c1-r001-sb26-a" / "k0"
    check(gzip.decompress((tl / "requests.jsonl.gz").read_bytes()) == b'{"event": "request"}\n'
          and (tl / "replies.jsonl").exists() and (tl / "result.json").exists() and (tl / "master.jsonl.gz").exists()
          and not (store_dir / "rl" / "c1" / "tries" / "vm1" / "c1-r001-dc22-c").exists()
          and not (store_dir / "rl" / "c1" / "tries" / "vm1" / "c1-r001-sb26-d").exists(),
          "upload: a finished try's request log (gzipped), replies, result and master go to rl/<C>/tries/<vm>/ "
          "(RL v1 data survives a preemption); fenced / unfinished tries do not")
    dv = rl.get("results/vm1/c1-r001-sb26-d/k1/result.json")
    check(dv is not None and json.loads(dv)["diverged"]["kind"] == "origin_messages",
          "upload: a diverged try's result.json goes up (the divergence diff stays readable), no master")
    check(not any(list((root / "jobs" / "round-0001").glob(f"*-{j}.json")) for j in "efg"),
          "staging: jobs another VM's server played, has in flight or dropped are not staged again",
          str(sorted(p.name for p in (root / "jobs" / "round-0001").glob("*.json"))))
    rl.put("STOP", b"1")
    out2 = hs.Sync(args).once()
    check(out2["jobs"] == 0 and out2["uploaded"] == 0 and out2["policy"] is False and (root / "STOP").exists(),
          "second pass: nothing staged or uploaded twice, policy unchanged, STOP mirrored", json.dumps(out2))
    # claims: two VMs on one campaign split a round (3-Oct rl2: 8 VMs played the same jobs), buffer 2 each
    import os
    os.environ["ARC3_RL_STAGE_BUFFER"] = "2"
    cdir = tmp / "claims"
    cstore, crl = Store(str(cdir / "store")), Store(str(cdir / "store" / "rl" / "c2"))
    for r in (1, 2, 3):
        for i in range(4):
            crl.put(f"jobs/round-000{r}/000{r}-0000{i}-r{r}j{i}.json", json.dumps({**base, "campaign": "c2", "round": r,
                    "job_id": f"r{r}j{i}", "game_id": "sb26-x", "mode": "replay_exact", "source": {}}).encode())

    def vm(name):
        a = hs.argparse.Namespace(campaign="c2", store=str(cdir / "store"), root=str(cdir / name / "rollout"),
                                  results=str(cdir / name / "results"), vm=name, every=1, stage_fallback=False, cmd="once")
        return hs.Sync(a)

    va, vb = vm("vmA"), vm("vmB")
    va.once()
    vb.once()
    staged = {v: sorted(p.name for p in (cdir / v / "rollout" / "jobs").rglob("*.json")) for v in ("vmA", "vmB")}
    check(len(staged["vmA"]) == 2 and len(staged["vmB"]) == 2 and not set(staged["vmA"]) & set(staged["vmB"])
          and all(n.startswith(("0002-", "0003-")) for v in staged for n in staged[v]),
          "claims: two VMs stage disjoint jobs, at most the buffer each, newest 2 rounds only", json.dumps(staged))
    # a VM that staged everything before claims existed: unclaimed extras and another VM's jobs are removed
    vc = vm("vmC")
    for r in (2, 3):
        for i in range(4):
            dest = cdir / "vmC" / "rollout" / "jobs" / f"round-000{r}" / f"000{r}-0000{i}-r{r}j{i}.json"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("{}")
    vc.once()
    left = sorted(p.name for p in (cdir / "vmC" / "rollout" / "jobs").rglob("*.json"))
    owners = {n: json.loads(crl.get(f"claims/{hs.job_id_of(n)}"))["vm"] for n in left}
    check(len(left) == 2 and set(owners.values()) == {"vmC"} and not set(left) & (set(staged["vmA"]) | set(staged["vmB"])),
          "claims: a pre-staged VM keeps only its own claims (buffer) and drops jobs other VMs claimed", json.dumps(owners))
    del os.environ["ARC3_RL_STAGE_BUFFER"]
    shutil.rmtree(tmp, ignore_errors=True)
    bad = [n for ok, n in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed" + (f"; FAILED: {bad}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

"""RL rollout server, VM host side: feed the notebook (no network inside) and carry its results out.

Author: Claude Opus 5.5 (3-Oct-2026). Runs on the GPU VM host next to the notebook container (rl-vm-startup.sh),
with gtree_store.py and gtree_ctx.py beside it (copied from gs://cellens-ai-artifacts/arc3-gtree/rollout-code/).

  python3 rl_host_sync.py loop --campaign C --root /kaggle-root/rollout --results /kaggle-root/working/gtree-rollout
                               --vm NAME [--store gs://cellens-ai-artifacts/arc3-gtree/v1] [--every 120]
  python3 rl_host_sync.py once ...        (one pass: what the loop does every --every seconds; the final flush)

Every pass:
  jobs     new files under <store>/rl/<C>/jobs/round-*/ -> <root>/jobs/round-NNNN/ (atomic rename; the container's
           server scans that dir). Sources are fetched once each and the paths rewritten to /kaggle/rollout/src/...:
           replay_exact: the play's request + event logs; snapshot: the state file and the logged origin request
           (rebuilt from the ctx store: ctx_before). A snapshot job's request log (its fallback) is only staged with
           --stage-fallback (it is 20-150 MB). Fenced games are refused.
  policy   <store>/rl/<C>/policy/current.json -> <root>/policy/current.json when it changed (the coach re-reads it
           between nodes: ARC3_COACH_POLICY=@/kaggle/rollout/policy/current.json)
  stop     <store>/rl/<C>/STOP exists -> <root>/STOP (the server finishes its nodes and ends)
  upload   every finished try (result.json status done, a master.jsonl.gz, publishable) once:
             master.jsonl.gz            -> <store>/rollouts/gtr-<C>/<game>_p<pass>.<job>.k<k>.jsonl.gz
             gtree-store/ctx, blobs     -> <store>/ctx/, <store>/blobs/ (write-once)
             state/*.pkl.gz             -> <store>/state/<sha>.pkl.gz (write-once)
             state_refs.jsonl           -> <store>/state/index/gtr-<C>/<game>_p<pass>.<job>.k<k>.jsonl
           and result.json + the server's summary.json -> <store>/rl/<C>/results/<vm>/ (request logs stay on the VM
           disk and go up with the final rsync of the results dir). A try that ended without a master (diverged,
           aborted, deadline) uploads its result.json too: the divergence diff / abort reason stays readable.
  Jobs some server of the campaign already played, has in flight or dropped (any VM's summary.json) are not staged:
  a new VM in a running campaign does not replay them.
Publishing to the site stays an operator step (ingest.py republish --runs gtr-<C>).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _d in (HERE, HERE.parent, HERE.parent.parent / "gtree-ingest"):
    if (_d / "gtree_store.py").exists() and str(_d) not in sys.path:
        sys.path.insert(0, str(_d))
from gtree_store import Store, gcs_download, gcs_list  # noqa: E402

FENCED = {"lf52", "tn36", "re86", "dc22", "su15", "as66"}
MOUNT = "/kaggle/rollout"
STAGE_BUFFER = 4          # claimed, unstarted jobs staged ahead of the server (2 nodes in flight + 2 waiting)
CLAIM_STALE_S = 45 * 60   # another VM's claim this old, on a job no server reports played or running: taken over


def log(msg: str) -> None:
    print(f"[rl-host {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def job_id_of(name: str) -> str:
    """jobs/round-NNNN/RRRR-PPPPP-<job id>.json (or a bare file name) -> the job id (rl_loop.job_id_of)."""
    base = name.rsplit("/", 1)[-1]
    base = base[:-5] if base.endswith(".json") else base
    parts = base.split("-", 2)
    return parts[2] if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit() else base


def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


class Sync:
    def __init__(self, a: argparse.Namespace):
        self.a = a
        self.store = Store(a.store)
        self.rl = Store(f"{a.store.rstrip('/')}/rl/{a.campaign}")
        self.root = Path(a.root)
        self.results = Path(a.results)
        self.state_file = self.root.parent / f"rl-host-state-{a.campaign}.json"
        st = json.loads(self.state_file.read_text()) if self.state_file.exists() else {}
        self.staged: set[str] = set(st.get("staged", []))
        self.uploaded: set[str] = set(st.get("uploaded", []))
        self.fetched: dict[str, str] = st.get("fetched", {})
        self.policy_stamp = st.get("policy_stamp")

    def save(self) -> None:
        _atomic(self.state_file, json.dumps({"staged": sorted(self.staged), "uploaded": sorted(self.uploaded),
                                             "fetched": self.fetched, "policy_stamp": self.policy_stamp}).encode())

    # ---- sources ---------------------------------------------------------------------------------------------------
    def fetch(self, uri: str) -> str:
        """A gs:// object staged once under <root>/src/; returns its container path."""
        if uri in self.fetched:
            return self.fetched[uri]
        rel = uri.split("://", 1)[-1].replace(":", "").lstrip("/\\")
        dest = self.root / "src" / rel
        if not dest.exists():
            if uri.startswith("gs://"):
                gcs_download(uri, dest)
            else:                                    # a local file (tests)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(uri, dest)
        self.fetched[uri] = f"{getattr(self.a, 'mount', MOUNT)}/src/{rel}"
        return self.fetched[uri]

    def origin_messages(self, ctx_sha: str) -> str:
        """The logged origin request of a snapshot job, rebuilt from the ctx store (gtree_ctx.restore_context)."""
        key = f"ctx:{ctx_sha}"
        if key in self.fetched:
            return self.fetched[key]
        import gtree_ctx  # noqa: PLC0415
        msgs = gtree_ctx.restore_context(ctx_sha, self.store)
        rel = f"origin/{ctx_sha}.json"
        _atomic(self.root / "src" / rel, json.dumps(msgs).encode("utf-8"))
        self.fetched[key] = f"{getattr(self.a, 'mount', MOUNT)}/src/{rel}"
        return self.fetched[key]

    def consumed(self) -> set[str]:
        """Job ids some server of the campaign (any VM) already played, has in flight, or dropped: a new VM in a
        running campaign must not play them again (results/<vm>/summary.json; rl_loop.queue_state uses the same rule
        to decide when the queue is low)."""
        out: set[str] = set()
        for n in self.rl.list("results/"):
            if n.count("/") != 2 or not n.endswith("/summary.json"):
                continue
            try:
                s = json.loads(self.rl.get(n) or b"{}")
            except ValueError:
                continue
            out |= {str(r.get("job")) for r in s.get("results") or []}
            out |= {str(e.get("job")) for e in s.get("errors") or []}
            out |= {str(j) for j in (s.get("running") or {}).get("jobs") or []}
            out |= {job_id_of(x) for x in list(s.get("skipped_old_round") or []) + list(s.get("skipped_fenced") or [])}
        return out

    # ---- claims: one VM per job (3-Oct rl2: 8 VMs staged every job of a round and played the same ones) ------------
    def claim_owner(self, jid: str) -> dict | None:
        raw = self.rl.get(f"claims/{jid}")
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            return {"vm": raw.decode(errors="replace").strip(), "t": 0}

    def claim(self, jid: str, done: set[str]) -> bool:
        """First writer wins (write-once <rl>/claims/<job id>); our own claim counts; another VM's claim older than
        CLAIM_STALE_S on a job no server reports played or running (that VM died first) is taken over."""
        doc = json.dumps({"vm": self.a.vm, "t": time.time()}).encode()
        if self.rl.put(f"claims/{jid}", doc, once=True, content_type="application/json"):
            return True
        cur = self.claim_owner(jid) or {}
        if cur.get("vm") == self.a.vm:
            return True
        if jid not in done and time.time() - float(cur.get("t") or 0) > CLAIM_STALE_S:
            self.rl.put(f"claims/{jid}", doc, once=False, content_type="application/json")
            log(f"took over stale claim {jid} from {cur.get('vm')}")
            return True
        return False

    def local_started(self) -> set[str]:
        """Job ids this VM's server started, finished or dropped (its summary.json, its per-job result dirs)."""
        out: set[str] = set()
        summ = self.results / "summary.json"
        if summ.exists():
            try:
                s = json.loads(summ.read_text(encoding="utf-8"))
            except ValueError:
                s = {}
            out |= {str(r.get("job")) for r in s.get("results") or []}
            out |= {str(e.get("job")) for e in s.get("errors") or []}
            out |= {str(j) for j in (s.get("running") or {}).get("jobs") or []}
            out |= {job_id_of(x) for x in list(s.get("skipped_old_round") or []) + list(s.get("skipped_fenced") or [])}
        if self.results.exists():
            out |= {p.name for p in self.results.iterdir() if p.is_dir()}
        return out

    # ---- one pass ----------------------------------------------------------------------------------------------------
    def stage_jobs(self) -> int:
        """Stage only jobs this VM claimed, at most ARC3_RL_STAGE_BUFFER waiting, from the newest keep-rounds rounds
        (the server's own rule); staged-but-unstarted jobs another VM claimed (or nobody, with no room left) are
        removed again, before the server starts them (it rescans the dir before every node)."""
        buffer = int(os.environ.get("ARC3_RL_STAGE_BUFFER", "") or STAGE_BUFFER)
        keep = int(os.environ.get("ARC3_ROLLOUT_KEEP_ROUNDS", "2") or 0)
        names_all = [x for x in sorted(self.rl.list("jobs/")) if x.endswith(".json")]
        rounds = sorted({x.split("/")[1] for x in names_all if x.count("/") >= 2})
        kept = set(rounds[-keep:]) if keep else set(rounds)
        started, done = self.local_started(), self.consumed()
        waiting = 0
        jobs_dir = self.root / "jobs"
        for p in sorted(jobs_dir.rglob("*.json")) if jobs_dir.exists() else []:
            if p.name.startswith("."):
                continue
            jid = job_id_of(p.name)
            if jid in started:
                continue
            rel = p.relative_to(self.root).as_posix()
            owner = (self.claim_owner(jid) or {}).get("vm")
            ours = owner == self.a.vm
            if not ours and owner is None and rel.split("/")[1] in kept and jid not in done and waiting < buffer:
                ours = self.claim(jid, done)
            if ours:
                waiting += 1
                continue
            p.unlink(missing_ok=True)
            self.staged.discard(rel)
            log(f"unstaged {rel}: claimed by {owner or 'nobody'}")
        n = 0
        for name in names_all:
            if waiting >= buffer:
                break
            if name in self.staged or name.split("/")[1] not in kept:
                continue
            jid = job_id_of(name)
            if jid in done or jid in started:
                log(f"skip {name}: already played, running or dropped by a server of this campaign")
                self.staged.add(name)
                continue
            if not self.claim(jid, done):
                continue                              # another VM's: looked at again next pass (stale takeover)
            try:
                job = json.loads(self.rl.get(name))
                if str(job["game_id"]).split("-")[0] in FENCED:
                    log(f"refused fenced job {name}")
                    self.staged.add(name)
                    continue
                src = job["source"]
                if job.get("mode") == "snapshot":
                    src["state"] = self.fetch(src["state"])
                    if src.get("ctx_before"):
                        src["origin_messages"] = self.origin_messages(src["ctx_before"])
                    keys = ("requests", "events") if self.a.stage_fallback else ()
                    for k in ("requests", "events"):
                        if k not in keys:
                            src.pop(k, None)
                else:
                    keys = ("requests", "events", "coach_log")
                for k in keys:
                    if src.get(k):
                        src[k] = self.fetch(src[k])
                _atomic(self.root / name, json.dumps(job, indent=1).encode("utf-8"))   # <root>/jobs/round-NNNN/...
                self.staged.add(name)
                n += 1
                waiting += 1
            except Exception as exc:                 # noqa: BLE001 - one bad job must not stop the feed
                log(f"stage {name}: {type(exc).__name__}: {exc}")
        return n

    def sync_policy(self) -> bool:
        raw = self.rl.get("policy/current.json")
        if raw is None:
            return False
        stamp = hashlib.sha256(raw).hexdigest()
        if stamp == self.policy_stamp:
            return False
        doc = json.loads(raw)
        _atomic(self.root / "policy" / "current.json", raw)
        self.policy_stamp = stamp
        log(f"policy -> {doc.get('version')} (seq {doc.get('seq')})")
        return True

    def check_stop(self) -> None:
        if self.rl.get("STOP") is not None and not (self.root / "STOP").exists():
            _atomic(self.root / "STOP", b"stop\n")
            log("STOP")

    def put_try_logs(self, key: str, try_dir: Path) -> None:
        """What RL v1 trains on (try_records.py), per finished try as it ends (4-Oct): until then request logs went
        up only with the final rsync, which a Spot preemption skips. -> <store>/rl/<C>/tries/<vm>/<job>/k<k>/:
        result.json, master.jsonl.gz, requests.jsonl.gz (the exact prompts, ~5 MB raw), replies.jsonl (the replies
        the harness does not log), coach-decisions.jsonl."""
        base = f"tries/{self.a.vm}/{key.replace(os.sep, '/')}"
        for name, gz in (("result.json", False), ("master.jsonl.gz", False), ("requests.jsonl", True),
                         ("replies.jsonl", False), ("coach-decisions.jsonl", False)):
            p = try_dir / name
            if not p.exists():
                continue
            data = p.read_bytes()
            if gz:
                data = gzip.compress(data, compresslevel=3)
            self.rl.put(f"{base}/{name}{'.gz' if gz else ''}", data, once=False,
                        content_type="application/gzip" if gz or name.endswith(".gz") else "application/json")

    def upload(self) -> int:
        run = f"gtr-{self.a.campaign}"
        n = 0
        for res_path in sorted(self.results.glob("*/k*/result.json")):
            try_dir = res_path.parent
            key = str(try_dir.relative_to(self.results))
            if key in self.uploaded:
                continue
            try:
                res = json.loads(res_path.read_text(encoding="utf-8"))
            except ValueError:
                continue                              # being written
            rec = res.get("records") or {}
            if res.get("status") != "done" or not rec.get("master_name"):
                if res.get("status") not in (None, "done"):
                    # final without a master (diverged, aborted, deadline): its result.json still goes up, so why it
                    # failed (the 'diverged' diff, the abort reason, the origin check) can be read later (3-Oct: ar25)
                    self.rl.put(f"results/{self.a.vm}/{key.replace(os.sep, '/')}/result.json", res_path.read_bytes(),
                                once=False, content_type="application/json")
                    self.uploaded.add(key)
                continue
            if not rec.get("publishable") or rec["master_name"].rsplit("/", 1)[-1].split("_p")[0] in FENCED:
                self.uploaded.add(key)
                continue
            mname = rec["master_name"]
            if not mname.startswith(f"rollouts/{run}/"):
                log(f"{key}: master {mname} is not in {run}; skipped")
                self.uploaded.add(key)
                continue
            gstore = try_dir / "gtree-store"
            for sub in ("blobs", "ctx"):                # contexts before the master that names them
                for p in sorted((gstore / sub).rglob("*")) if (gstore / sub).exists() else []:
                    if p.is_file():
                        self.store.put(p.relative_to(gstore).as_posix(), p.read_bytes(), once=True)
            for p in sorted((try_dir / "state").glob("*.pkl.gz")) if (try_dir / "state").exists() else []:
                self.store.put(f"state/{p.name}", p.read_bytes(), once=True, content_type="application/gzip")
            base = mname.rsplit("/", 1)[-1][:-len(".jsonl.gz")]
            refs = try_dir / "state_refs.jsonl"
            if refs.exists() and refs.stat().st_size:
                self.store.put(f"state/index/{run}/{base}.jsonl", refs.read_bytes(), once=False,
                               content_type="application/x-ndjson")
            self.store.put(mname, (try_dir / "master.jsonl.gz").read_bytes(), once=False,
                           content_type="application/gzip")
            self.put_try_logs(key, try_dir)
            self.rl.put(f"results/{self.a.vm}/{key.replace(os.sep, '/')}/result.json", res_path.read_bytes(),
                        once=False, content_type="application/json")
            self.uploaded.add(key)
            n += 1
        summ = self.results / "summary.json"
        if summ.exists():
            self.rl.put(f"results/{self.a.vm}/summary.json", summ.read_bytes(), once=False,
                        content_type="application/json")
        return n

    def once(self) -> dict:
        out = {}
        for name, fn in (("jobs", self.stage_jobs), ("policy", self.sync_policy), ("stop", self.check_stop),
                         ("uploaded", self.upload)):
            try:
                out[name] = fn()
            except Exception as exc:                 # noqa: BLE001 - e.g. a GCS hiccup: next pass
                out[name] = f"error {type(exc).__name__}: {exc}"[:300]
                log(traceback.format_exc()[-800:])
        self.save()
        return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("loop", "once"))
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--store", default="gs://cellens-ai-artifacts/arc3-gtree/v1")
    ap.add_argument("--root", required=True, help="host dir mounted read-only at /kaggle/rollout")
    ap.add_argument("--mount", default=MOUNT, help="where --root appears in the container (4-Oct RL box sessions: "
                    "/kaggle/rollout/sess/<campaign>; staged sources are rewritten to <mount>/src/...)")
    ap.add_argument("--results", required=True, help="host path of /kaggle/working/gtree-rollout")
    ap.add_argument("--vm", default=os.uname().nodename if hasattr(os, "uname") else "local")
    ap.add_argument("--every", type=float, default=120.0)
    ap.add_argument("--stage-fallback", action="store_true")
    a = ap.parse_args(argv)
    s = Sync(a)
    while True:
        log(json.dumps(s.once()))
        if a.cmd == "once":
            return 0
        time.sleep(a.every)


if __name__ == "__main__":
    raise SystemExit(main())

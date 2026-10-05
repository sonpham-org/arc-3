"""RL v1 plan C on the RL box (4-Oct-2026, Son: "go with C and (a)"; rl/box/README.md): play and training never wait for
each other.
  cards 0-2  persistent rollout servers (box_pslot.sh): every new model is swapped in (hotswap.py, ~5 s) and gets its
             own campaign: its test slice first (pick_nodes.test_jobs: 2 tries at each game's frontier level + 1 below,
             the same restart points for every model), then training tries (the usual picker), refilled until the next
             model lands; the old campaign gets STOP and its running tries finish
  card 3     the held-out full test (box_panel.sh, on the box itself), newest model after newest model
  cards 4-7  back-to-back training jobs (trainer service): cut_records.py takes every ready, unused training try of the
             campaigns so far, trains from the last adapter + optimizer, then merges in the background (CPU) and writes
             the hot-swap delta; the next training starts at once
This driver (on this PC) only decides: it polls GCS every minute, starts campaigns, writes session requests, queues
training jobs. State: <work>/c_state.json (resumable). Stop: create <work>/STOP_C (the box keeps its servers).
  C:/Python312/python.exe ops/run_c.py --box arc3-rl-box1 --zone us-central1-b --sha <code> [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GT = HERE.parent.parent / "gtree-rollout"
PY = r"C:\Python312\python.exe"
GCLOUD = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
B = "gs://cellens-ai-artifacts/arc3-rl/trainer/train4-1002"
STORE = "gs://cellens-ai-artifacts/arc3-gtree/v1"
GAMES = "bp35,cn04,g50t,ka59,ls20,m0r0,r11l,s5i5,sc25,sk48,sp80,tu93,vc33,wa30"     # site_config.json split.train
MIX = "level_start=0.35,backward=0.25,unresumed=0.15,uncertain=0.25"
ENV = dict(os.environ, CLOUDSDK_PYTHON=r"C:\python312\python.exe")


def say(msg: str) -> None:
    print(f"{time.strftime('%H:%M', time.gmtime())} {msg}", flush=True)


def g(*args: str, data: str | None = None, timeout: int = 180) -> tuple[int, str]:
    try:
        p = subprocess.run(GCLOUD + list(args), input=data, capture_output=True, text=True, timeout=timeout, env=ENV)
        return p.returncode, p.stdout.replace("\r", "")
    except subprocess.TimeoutExpired:
        return 124, ""


def gcat(uri: str) -> str | None:
    rc, out = g("storage", "cat", uri)
    return out if rc == 0 else None


def gput(uri: str, text: str) -> bool:
    return g("storage", "cp", "-", uri, data=text)[0] == 0


class Driver:
    def __init__(self, a: argparse.Namespace):
        self.a = a
        self.work = Path(a.work)
        self.state_f = self.work / "c_state.json"
        self.st = json.loads(self.state_f.read_text(encoding="utf-8")) if self.state_f.exists() else {
            "models": [{"merge": a.first_merge, "train": a.first_train, "idx": 0}], "playing": None, "campaigns": [],
            "cut_extra": [c for c in a.cut_extra.split(",") if c], "k": 1, "attempt": 0, "inflight": None,
            "pending_merges": [], "last_train": a.first_train, "next_train_at": 0}
        self.refill: subprocess.Popen | None = None
        self.boxq = f"gs://cellens-ai-artifacts/arc3-rl/box/{a.box}"

    def save(self) -> None:
        tmp = self.state_f.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.st, indent=1), encoding="utf-8")
        os.replace(tmp, self.state_f)

    # ------------------------------------------------------------------ play side
    def pick_args(self) -> list[str]:
        base_runs = subprocess.run([PY, "-c", "import pick_nodes; print(','.join(pick_nodes.BASE_RUNS))"], cwd=GT,
                                   capture_output=True, text=True).stdout.strip()
        hist = ["rl1", "rl2", "speed1", "speed2"] + self.st["cut_extra"] + [c["campaign"] for c in self.st["campaigns"]]
        return ["--modes", "stock", "--K", "8", "--N", "8", "--limit", str(self.a.limit), "--stage-k", "4",
                "--frontier", "0.8", "--frontier-runs", base_runs, "--mix", MIX, "--history-campaigns", ",".join(hist)]

    def start_campaign(self, model: dict) -> None:
        camp = f"{self.a.prefix}{model['idx']}-{time.strftime('%m%d', time.gmtime())}"
        lbl = "".join(ch for ch in camp.lower() if ch.isalnum())
        say(f"model {model['merge']} -> campaign {camp} (test slice + training tries)")
        if self.a.dry_run:
            return
        p = subprocess.run([PY, "rl_loop.py", "init", "--campaign", camp, *self.pick_args(), "--games", GAMES,
                            "--lanes", "16", "--test-games", "all", "--test-tries", self.a.test_tries],
                           cwd=GT, capture_output=True, text=True)
        if p.returncode:
            say(f"campaign init failed: {(p.stdout + p.stderr)[-600:]}")
            raise SystemExit(1)
        say(p.stdout.strip().splitlines()[-1])
        old = self.st["playing_campaign"] if self.st.get("playing_campaign") else None
        if old:
            gput(f"{STORE}/rl/{old}/STOP", "stop")
            say(f"STOP {old}: its servers finish their running tries, then take {camp}")
        if self.refill and self.refill.poll() is None:
            self.refill.terminate()
        labels = [f"{lbl}{chr(97 + i)}" for i in range(self.a.slots)]
        for lab in labels:
            env = f"RUN_ID=rl-{camp}-{lab}\nCAMPAIGN={camp}\nLABEL={lab}\nMERGE={model['merge']}\n"
            gput(f"{self.boxq}/requests/{lab}.env", env) or say(f"request {lab} not written")
        self.start_refill(camp)
        with open(self.work / "tries-campaigns.txt", "a", encoding="utf-8") as fh:
            fh.write(camp + "\n")
        self.st["campaigns"].append({"campaign": camp, "merge": model["merge"], "labels": labels, "started": time.time()})
        self.st["playing"], self.st["playing_campaign"] = model["merge"], camp
        self.save()

    def start_refill(self, camp: str) -> None:
        """rl_loop.py run: refills the campaign's queue with the same picker rules (training tries only)."""
        if self.refill and self.refill.poll() is None:
            self.refill.terminate()
        log = open(self.work / f"learner-{camp}.log", "a", encoding="utf-8")
        self.refill = subprocess.Popen([PY, "rl_loop.py", "run", "--campaign", camp, "--every", "10", "--no-publish",
                                        "--min-steps", "99999999", "--lanes", "16", *self.pick_args()],
                                       cwd=GT, stdout=log, stderr=subprocess.STDOUT)

    # ------------------------------------------------------------------ training side
    def train_cmd(self, jid: str, jm: str, prev: str, camps: list[str]) -> str:
        sha, w = self.a.sha, "/opt/m/work"
        env = "ARC3_OFFLOAD_MIN_ELEMS=1239040000 ARC3_MOE_TOKEN_CHUNK=32768 ARC3_NVFP4_CHUNK=128"
        merge = (f"cd /opt/rl && /opt/rl/venv/bin/python merge_lora.py --adapter {w}/out/{jid} --checkpoint /opt/m/daniel "
                 f"--out {w}/out/{jm}/merged --only-changed && /opt/rl/venv/bin/python extract_delta.py --merged "
                 f"{w}/out/{jm}/merged --out /kaggle-delta/{jm}/delta.safetensors && chmod -R a+rX /kaggle-delta/{jm}; "
                 f"rc=$?; echo $rc > {w}/out/{jm}/EXIT; gcloud storage cp {w}/out/{jm}/bg.log "
                 f"{w}/out/{jm}/merged/MERGE_REPORT.json {B}/out/{jm}/; gcloud storage cp {w}/out/{jm}/EXIT {B}/out/{jm}/EXIT; "
                 f"ls -1dt {w}/out/c*-merge/merged | tail -n +4 | xargs -r rm -rf")
        cmd = (f"set -e; cd /opt/rl && gcloud storage cp 'gs://cellens-ai-artifacts/arc3-rl/code/{sha}/*' /opt/rl/ && "
               f"set +e; /opt/rl/venv/bin/python cut_records.py --campaigns {','.join(camps)} --state {w}/c "
               f"--name {jid} --out {w}/records/{jid} --games {GAMES} --budget {self.a.budget} --min {self.a.min_records}; "
               f"rc=$?; [ $rc -eq 0 ] || exit $rc; set -e; "
               f"test -f {w}/out/{prev}/ADAPTER.json && test -f {w}/out/{prev}/optim.pt && "
               "{ test -f /opt/m/daniel-stacked/index.json || /opt/rl/venv/bin/python nvfp4_experts.py stack "
               "--ckpt /opt/m/daniel --out /opt/m/daniel-stacked; } && "
               f"mkdir -p {w}/out/{jid} && {env} /opt/rl/venv/bin/python lora_train.py train --model /opt/m/bf16 "
               f"--hf /opt/m/bf16 --gpus 4 --dp 4 --gpu-gib 86 --nvfp4 /opt/m/daniel --experts-source mmap "
               f"--experts-stacked /opt/m/daniel-stacked --ple-cache {w}/ple/{jid} --records '{w}/records/{jid}/*.jsonl.gz' "
               f"--out {w}/out/{jid} --init-adapter {w}/out/{prev} --init-optim {w}/out/{prev}/optim.pt --clip 0.2 "
               f"--kl 0.05 --epochs 1 --accum 4 --lr 5e-5 --warmup 2 --rank 32 --alpha 64 --max-tokens 121000 "
               f"--ckpt-every 1 && mkdir -p {w}/out/{jm} && "
               # braces: only the merge goes to the background (4-Oct: a bare trailing & sent the whole && chain there,
               # so the job ended at once with exit 0 while its training ran on unseen)
               f"{{ setsid nohup bash -c '{merge}' > {w}/out/{jm}/bg.log 2>&1 < /dev/null & }}")
        assert "'" not in merge and "/opt/m/work/" in cmd and "Program Files" not in cmd
        return cmd

    def queue_train(self) -> None:
        k, att = self.st["k"], self.st["attempt"]
        if k > self.a.last_model:                  # the run's size (Son 5-Oct: "code to define how many rounds")
            return
        jid, jm, prev = f"c{k:03d}-train-{att}", f"c{k:03d}-merge", self.st["last_train"]
        camps = self.st["cut_extra"] + [c["campaign"] for c in self.st["campaigns"]]
        if not camps:
            return
        if self.st["campaigns"] and not self.a.no_loop_gate:          # the model now playing must not copy-paste
            lc = subprocess.run([PY, str(HERE / "loop_check_tries.py"), self.st["campaigns"][-1]["campaign"]],
                                capture_output=True, text=True).stdout.strip().splitlines()
            last = lc[-1] if lc else ""
            if last.startswith("LOOPING"):
                say(f"loop check: {last}: no more training (the servers keep the current model)")
                self.st["halted"] = last
                self.save()
                return
        cmd = self.train_cmd(jid, jm, prev, camps)
        if self.a.dry_run:
            print(json.dumps({"cmd": "shell", "args": {"command": cmd}}, indent=1))
            return
        if not gput(f"{B}/jobs/{jid}.json", json.dumps({"cmd": "shell", "args": {"command": cmd}})):
            say(f"could not queue {jid}")
            return
        self.st["inflight"] = {"job": jid, "merge": jm, "queued": time.time(), "prev": prev}
        self.save()
        say(f"queued {jid}: from {prev}, tries of {','.join(camps)}")

    def poll_train(self) -> None:
        inf = self.st["inflight"]
        if not inf:
            return
        ex = gcat(f"{B}/out/{inf['job']}/EXIT")
        if ex is None:
            return
        ex = ex.strip()
        if ex == "0":
            adapter = gcat(f"{B}/out/{inf['job']}/ADAPTER.json") or "{}"
            try:
                recs = json.loads(adapter).get("records")
            except ValueError:
                recs = "?"
            say(f"{inf['job']} trained on {recs} records in {round((time.time() - inf['queued']) / 60)} min; "
                f"{inf['merge']} merging in the background")
            self.st["pending_merges"].append({"merge": inf["merge"], "train": inf["job"], "idx": self.st["k"]})
            self.st.update(last_train=inf["job"], k=self.st["k"] + 1, attempt=0, inflight=None)
        elif ex == "75":
            say(f"{inf['job']}: not enough ready tries yet; again in {self.a.retry_min} min")
            self.st.update(attempt=self.st["attempt"] + 1, inflight=None,
                           next_train_at=time.time() + 60 * self.a.retry_min)
        else:
            log = gcat(f"{B}/out/{inf['job']}/job.log") or ""
            say(f"{inf['job']} FAILED (exit {ex}); last lines:\n" + "\n".join(log.splitlines()[-20:]))
            self.st["halted"] = f"{inf['job']} exit {ex}"
            self.st["inflight"] = None
        self.save()

    def poll_merges(self) -> None:
        for pm in list(self.st["pending_merges"]):
            ex = gcat(f"{B}/out/{pm['merge']}/EXIT")
            if ex is None:
                continue
            self.st["pending_merges"].remove(pm)
            if ex.strip() == "0":
                self.st["models"].append(pm)
                say(f"{pm['merge']} merged: model {pm['idx']} goes to the servers")
            else:
                say(f"{pm['merge']} merge FAILED (exit {ex.strip()}): see {B}/out/{pm['merge']}/bg.log")
            self.save()

    def check_sessions(self) -> None:
        """Each server of the current campaign: its last phase line; a failing session is reported once (5-Oct: every
        job of v1c0 failed at once and nothing said so for 7 h)."""
        cur = self.st["campaigns"][-1] if self.st["campaigns"] else None
        if not cur:
            return
        seen = self.st.setdefault("reported", [])
        for lab in cur["labels"]:
            ph = gcat(f"{STORE}/rl/{cur['campaign']}/runs/rl-{cur['campaign']}-{lab}/phases.tsv") or ""
            # the stall clock starts when a server actually takes the session (5-Oct: after the switch the servers
            # finish the old model's running tries first, 20+ minutes, which the clock must not count)
            if "server_ready session" in ph and not cur.get("session_at"):
                cur["session_at"] = time.time()
            for line in ph.splitlines():
                if ("jobs_failing" in line or "finish (" in line and "session_done" not in line) and line not in seen:
                    seen.append(line)
                    say(f"server {lab} FAILING: {line.split(chr(9))[-1][:220]}")
                    if "jobs_failing" in line:
                        self.halt_all(f"server {lab}: its session's jobs fail and no try finishes")
                        return
        # no finished try at all half an hour into a campaign: nothing is being learned; stop paying for it
        t0 = cur.get("session_at") or (cur["started"] + 60 * self.a.stall_min)   # no session yet: allow 2x the window
        if time.time() - t0 > 60 * self.a.stall_min and not cur.get("alive"):
            rc, out = g("storage", "ls", f"{STORE}/rl/{cur['campaign']}/tries/**/result.json", timeout=300)
            if rc == 0 and out.strip():
                cur["alive"] = True
                say(f"{cur['campaign']}: tries are finishing ({len(out.split())} so far)")
            else:
                self.halt_all(f"{cur['campaign']}: no finished try {self.a.stall_min} min after it started")
                return
        self.save()

    def stop_box(self) -> None:
        rc, _ = g("compute", "instances", "stop", self.a.box, "--zone", self.a.zone, timeout=900)
        say(f"box stop: {'ok' if rc == 0 else 'FAILED (rc %d)' % rc}")

    def halt_all(self, why: str) -> None:
        say(f"HALT: {why}; stopping the box")
        self.st["halted"] = why
        self.save()
        if self.refill and self.refill.poll() is None:
            self.refill.terminate()
        self.stop_box()
        (self.work / "STOP_C").write_text(why, encoding="utf-8")

    def hold_panel(self) -> None:
        """One held-out test during the training (the first new model of this run), the next on a 1-card box at the
        end: box_panel.sh starts no new test while <box>/panel-hold exists."""
        if self.st.get("panel_hold"):
            return
        rc, out = g("storage", "ls", "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs/")
        first = self.st.setdefault("first_new_idx", self.st["models"][-1]["idx"] + 1)
        tags = [f"daniel-p5held-c{i:03d}-boxnp-" for i in range(first, self.a.last_model + 1)]
        if any(t in out for t in tags):
            gput(f"{self.boxq}/panel-hold", "hold")
            self.st["panel_hold"] = True
            self.save()
            say("held-out test of this run's first new model started; the test card holds until the last model")

    def final_heldout(self) -> int:
        """The last model: no more play or training; the box becomes ONE card (g4-standard-48) that runs the last
        model's held-out test, then stops."""
        last = self.st["models"][-1]
        camp = self.st.get("playing_campaign")
        if camp:
            gput(f"{STORE}/rl/{camp}/STOP", "stop")
        if self.refill and self.refill.poll() is None:
            self.refill.terminate()
        say(f"model {last['idx']} ({last['merge']}) is the last: the box goes to 1 card for its held-out test")
        self.stop_box()
        g("compute", "instances", "set-machine-type", self.a.box, "--zone", self.a.zone, "--machine-type",
          "g4-standard-48", timeout=300)
        g("compute", "instances", "add-metadata", self.a.box, "--zone", self.a.zone, "--metadata",
          f"^;^slot-gpus=none;panel-gpu=0;trainer-gpus=none;panel-first={last['merge']}")
        g("storage", "rm", f"{self.boxq}/panel-hold")
        rc, _ = g("compute", "instances", "start", self.a.box, "--zone", self.a.zone, timeout=900)
        say(f"1-card box start: {'ok' if rc == 0 else 'FAILED'}")
        tag = last["merge"].removesuffix("-merge")
        t0 = time.time()
        while time.time() - t0 < 4 * 3600:
            time.sleep(120)
            rc, out = g("storage", "ls", "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs/")
            runs = [u.rstrip("/").split("/")[-1] for u in out.split() if f"daniel-p5held-{tag}-boxnp-" in u]
            ph = gcat(f"gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs/{runs[-1]}/phases.tsv") if runs else None
            if ph and "finish" in ph.strip().splitlines()[-1]:
                say(f"held-out test {runs[-1]}: {ph.strip().splitlines()[-1].split(chr(9))[-1]}")
                break
            if time.time() > self.deadline:
                say("deadline during the last held-out test")
                break
        self.stop_box()
        say("run complete: box stopped")
        return 0

    def box_alive(self) -> None:
        rc, out = g("compute", "instances", "describe", self.a.box, "--zone", self.a.zone, "--format", "value(status)")
        st = out.strip()
        if st in ("TERMINATED", "STOPPED", "SUSPENDED"):
            rc, _ = g("compute", "instances", "start", self.a.box, "--zone", self.a.zone, timeout=600)
            say(f"box was {st}: start {'ok' if rc == 0 else 'refused'} (servers restart cold; sessions are re-requested)")
            if rc == 0 and self.st.get("playing_campaign"):
                self.st["playing"] = None                 # a new campaign for the current model: fresh requests
                self.save()

    def run(self) -> int:
        say(f"plan C driver: box {self.a.box}, code {self.a.sha}, state {self.state_f}")
        if not self.a.dry_run:
            g("storage", "cp", str(GT / "runner" / "rl_host_sync.py"), str(GT.parent / "gtree-ingest" / "gtree_store.py"),
              str(GT.parent / "gtree-ingest" / "gtree_ctx.py"), "gs://cellens-ai-artifacts/arc3-gtree/rollout-code/")
        if self.st.get("playing_campaign") and not self.a.dry_run:     # a restarted driver: the refills again
            self.start_refill(self.st["playing_campaign"])
        n = 0
        self.deadline = time.time() + 3600 * self.a.deadline_h
        say(f"run size: models up to {self.a.last_model}; hard stop at "
            f"{time.strftime('%H:%M UTC', time.gmtime(self.deadline))}")
        while not (self.work / "STOP_C").exists():
            if time.time() > self.deadline:
                self.halt_all(f"deadline ({self.a.deadline_h} h) reached")
                break
            self.poll_merges()
            newest = self.st["models"][-1]
            if newest["idx"] >= self.a.last_model and not self.st["pending_merges"] and not self.st["inflight"]:
                return self.final_heldout() if not self.a.no_final_heldout else 0
            if self.st["playing"] != newest["merge"]:
                self.start_campaign(newest)
            self.poll_train()
            blocked = self.st.get("block_until_merge") in [m["merge"] for m in self.st["pending_merges"]]
            if (not self.a.no_train and not self.st["inflight"] and not self.st.get("halted") and not blocked
                    and time.time() >= self.st["next_train_at"]):
                self.queue_train()
            if self.a.dry_run:
                return 0
            if n % 5 == 0:
                self.box_alive()
                self.check_sessions()
                self.hold_panel()
            n += 1
            time.sleep(60)
        say("STOP_C found: driver ends (the box keeps playing the current model)")
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--box", required=True)
    ap.add_argument("--zone", required=True)
    ap.add_argument("--sha", required=True, help="rl code snapshot (ops/push_code.sh) with cut_records.py")
    ap.add_argument("--work", default=r"D:\codex-work\rl-20261001")
    ap.add_argument("--first-merge", default="105k-n0-merge")
    ap.add_argument("--first-train", default="104k-n0-train")
    ap.add_argument("--cut-extra", default="v1r1-1004,boxtest-1004", help="earlier campaigns of the first model")
    ap.add_argument("--prefix", default="v1c")
    ap.add_argument("--slots", type=int, default=3)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--test-tries", default="2,1")
    ap.add_argument("--budget", type=int, default=48)
    ap.add_argument("--min-records", type=int, default=16)
    ap.add_argument("--retry-min", type=int, default=5)
    ap.add_argument("--no-loop-gate", action="store_true")
    ap.add_argument("--no-train", action="store_true", help="play only (a test of the servers and sessions)")
    ap.add_argument("--last-model", type=int, default=7, help="train models up to this index (c<NNN>), then the "
                    "last held-out test on a 1-card box and stop (Son 5-Oct: 6 more rounds = models 2-7)")
    ap.add_argument("--deadline-h", type=float, default=7.5, help="hard stop: the box is stopped this many hours "
                    "after the driver starts, whatever is running")
    ap.add_argument("--stall-min", type=int, default=30, help="stop the box when a campaign has no finished try "
                    "this many minutes after it started")
    ap.add_argument("--no-final-heldout", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    return Driver(ap.parse_args()).run()


if __name__ == "__main__":
    raise SystemExit(main())

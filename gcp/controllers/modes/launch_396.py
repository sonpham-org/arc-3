"""Launch the 396-minute compaction-v5-clean-return ceiling run.

One g4-standard-48 (1x RTX PRO 6000, the golden Flash-Next runtime image, so no model download),
Spot: on-demand was refused (GPUS_PER_GPU_FAMILY limit 0 -- this GPU family is preemptible-only
on this project). Four of five 264-minute Spot runs were preempted, so treat a finished run as the
good case and the partial score curve as the fallback.

Usage: python launch_396.py [--dry-run] [--zones ...]
"""
import argparse, hashlib, json, os, secrets, subprocess, time, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARM = HERE / "arms" / os.environ.get("ARC3_ARM_NAME", "compaction_v5_clean_return_" + os.environ.get("ARC3_SUITE_MINUTES", "396"))
PROJECT = "cellensml"
BUCKET = "gs://cellens-ai-artifacts/arc3-duck"
MACHINE = "g4-standard-48"
GCLOUD = os.environ.get("GCLOUD", "gcloud")
ENV = dict(os.environ, CLOUDSDK_PYTHON=os.environ.get("CLOUDSDK_PYTHON", r"C:\python312\python.exe"))

def gcloud(*args, check=True):
    r = subprocess.run([GCLOUD, *args], env=ENV, capture_output=True, text=True, shell=(os.name == "nt"))
    if check and r.returncode:
        raise SystemExit(f"gcloud {' '.join(args)} failed:\n{r.stderr}")
    return r.stdout.strip()

def sha(p: Path): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--zones", default="europe-west1-b,europe-west1-c,us-central1-b,us-central1-c,us-east4-b")
    ap.add_argument("--suffix", default=secrets.token_hex(5))
    args = ap.parse_args()

    cfgp = ARM / "CONFIG_FLAGS.json"
    cfg = json.loads(cfgp.read_text()); cfg_sha = sha(cfgp)
    armcfg = json.loads((ARM / "ARM.json").read_text())
    startup = (ARM / "startup.sh").read_text(encoding="utf-8")
    delete_request_id = (ARM / "DELETE_REQUEST_ID").read_text().strip()
    assert delete_request_id in startup
    assert armcfg["config_object"].split("/code/")[1] in startup and f"/{cfg_sha}/CONFIG_FLAGS.json" in startup
    assert cfg_sha == armcfg["config_sha256"] and cfg["config_id"] == armcfg["config_id"]
    for local, key in (("selftest.tgz", "selftest_sha256"), ("release.json", "release_sha256")):
        assert sha(ARM / local) == armcfg[key], local
        assert armcfg[key] in startup, f"{local} hash is not pinned in startup.sh"
    assert sha(ARM / "ADAPTER.json") == armcfg["adapter_sha256"] and armcfg["adapter_sha256"] in startup

    if not args.dry_run:
        uploads = [("config_object", "CONFIG_FLAGS.json"), ("runner_object", "runner.py"), ("probe_object", "runtime_probe.py"),
                   ("selftest_object", "selftest.tgz"), ("adapter_object", "ADAPTER.json"), ("release_object", "release.json")]
        for key, local in (("prompt_probe_object", "prompt_probe.py"), ("expected_prompts_object", "EXPECTED_PROMPTS.json"),
                           ("candidate_object", "candidate.tgz")):
            if key in armcfg and (key != "candidate_object" or armcfg.get("candidate_changed")):
                uploads.append((key, local))
        for key, local in uploads:
            obj = armcfg[key]
            assert sha(ARM / local) == armcfg[key.replace("_object", "_sha256")], local
            if subprocess.run([GCLOUD, "storage", "ls", obj], capture_output=True, env=ENV,
                              shell=(os.name == "nt")).returncode:
                gcloud("storage", "cp", str(ARM / local), obj); print("uploaded", obj)
            else:
                print("present  ", obj)

    body = json.loads((ARM / "instance-body.json").read_text())
    run_id = f"{armcfg['run_id_prefix']}-{time.strftime('%Y%m%d')}-{args.suffix}"
    name = f"{armcfg['instance_prefix']}-{args.suffix}"
    body["name"] = name
    body["labels"].update({"arc3-matrix": f"{armcfg.get('tag', 'cv5cr')}{armcfg['suite_minutes']}", "arc3-profile": armcfg['arm'].replace('_', '-'),
                           "config-id": cfg["config_id"][:20], "owner-task": "claude-ceiling-run"})
    # Spot. On-demand was tried first and refused: GPUS_PER_GPU_FAMILY has a limit of 0 in every
    # region checked, so this GPU family is preemptible-only on this project. A preemption kills the
    # run (the startup refuses any boot after the first, to avoid duplicate gameplay), but runs/ is
    # rsynced to GCS every 120 s and the minute-score observer writes continuously, so a run that
    # dies at minute N still yields the score curve up to N -- which is most of what a ceiling
    # question needs.
    body["scheduling"] = {"automaticRestart": False, "onHostMaintenance": "TERMINATE",
                          "preemptible": True, "provisioningModel": "SPOT",
                          "instanceTerminationAction": "DELETE",
                          "maxRunDuration": {"seconds": str(armcfg["vm_lifetime_seconds"])}}
    meta = {i["key"]: i["value"] for i in body["metadata"]["items"]}
    meta.update({
        "arc3-mig": name, "arc3-run-id": run_id, "arc3-config-id": cfg["config_id"],
        "arc3-delete-request-id": delete_request_id,
        "arc3-feature-arm": armcfg["arm"],
        "arc3-runner-object": armcfg["runner_object"], "arc3-runner-sha256": armcfg["runner_sha256"],
        "arc3-max-runtime-s-per-game": str(armcfg["game_seconds"]),
        "arc3-max-run-runtime-minutes": str(armcfg["suite_minutes"]),
        "arc3-duration-class-minutes": str(armcfg["suite_minutes"]),
        "arc3-hard-lifetime-seconds": str(armcfg["vm_lifetime_seconds"]),
        "arc3-selftest-object": armcfg["selftest_object"], "arc3-selftest-sha256": armcfg["selftest_sha256"],
        "arc3-release-manifest-object": armcfg["release_object"],
        "arc3-parent-run-id": armcfg.get("parent_run_id", "g4run-compaction-v5-clean-return-a132-w7-20260919-693e7fd43c"),
        **({"arc3-bundle-object": armcfg["candidate_object"], "arc3-bundle-sha256": armcfg["candidate_sha256"]} if armcfg.get("candidate_changed") else {}),
        **({"arc3-feature-arm": armcfg["feature_arm"], "arc3-harness-arm": armcfg["harness_arm"],
            "arc3-execution-mode": str(int("execution" in armcfg["features"])),
            "arc3-symbolic-search": str(int("symbolic" in armcfg["features"])),
            "arc3-programmatic-workspace": str(int("workspace" in armcfg["features"])),
            "arc3-prompt-ablation": "+".join(armcfg["ablations"]),
            "arc3-game-subset": armcfg.get("subset", "")} if "harness_arm" in armcfg else {}),
        "arc3-repeat-of-run": "",
        "startup-script": startup,
    })
    body["metadata"]["items"] = [{"key": k, "value": v} for k, v in sorted(meta.items())]

    import urllib.request, urllib.error
    token = None if args.dry_run else gcloud("auth", "print-access-token")
    last = None
    for zone in args.zones.split(","):
        b = json.loads(json.dumps(body))
        b["machineType"] = f"zones/{zone}/machineTypes/{MACHINE}"
        b["disks"][0]["initializeParams"]["diskType"] = f"zones/{zone}/diskTypes/hyperdisk-balanced"
        (ARM / "instance-body.json").write_text(json.dumps(b, indent=2))
        print(f"== {zone}: {name} run={run_id} {MACHINE} SPOT "
              f"{armcfg['suite_minutes']}min/{armcfg['game_seconds']}s-per-game maxRun={armcfg['vm_lifetime_seconds']}s")
        if args.dry_run:
            print("dry run: body at", ARM / "instance-body.json"); return
        req = urllib.request.Request(
            f"https://compute.googleapis.com/compute/v1/projects/{PROJECT}/zones/{zone}/instances?requestId={uuid.uuid4()}",
            data=json.dumps(b).encode(), method="POST",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                op = json.load(r)
        except urllib.error.HTTPError as e:
            last = e.read().decode(); print("insert refused:", last[:400]); continue
        for _ in range(60):
            time.sleep(5)
            st = json.loads(gcloud("compute", "operations", "describe", op["name"], "--zone", zone, "--format=json"))
            if st.get("status") == "DONE":
                if st.get("error"):
                    last = json.dumps(st["error"]); print("operation error:", last[:400]); break
                print("CREATED", name, "in", zone)
                (ARM / "STATUS.json").write_text(json.dumps({
                    "run_id": run_id, "instance": name, "zone": zone,
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "config_id": cfg["config_id"], "provisioning": "SPOT",
                    "suite_minutes": armcfg["suite_minutes"], "game_seconds": armcfg["game_seconds"],
                    "bucket_prefix": f"{BUCKET}/{run_id}/"}, indent=2) + "\n")
                return
        if last and any(k in last for k in ("ZONE_RESOURCE_POOL_EXHAUSTED", "QUOTA_EXCEEDED", "does not exist")):
            continue
        break
    raise SystemExit(f"no zone accepted the instance; last error: {last}")

if __name__ == "__main__":
    main()

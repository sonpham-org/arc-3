"""Launch an LA-CR serving variant on one Spot g4-standard-48 from the LA-CR arm's own instance body.

The body (golden Flash-Next runtime image, every arc3-* metadata key, Spot + maxRunDuration 14400 + DELETE) is the
LA-CR arm's verbatim; only the keys the base controller refreshes per launch change: startup-script, run id, instance
name, config id, parent run, feature arm, delete request id, and (batched16k) arc3-serving-max-num-batched-tokens.
Usage: python launch.py --variant effort_medium [--zones a,b] [--dry-run]   |   python launch.py --variant X status
"""
import argparse, hashlib, json, secrets, sys, time, uuid
from pathlib import Path
import requests

HERE = Path(__file__).resolve().parent
SRC_ARM = Path(r"D:\codex-work\la-clean-return132-20260921\arms\la_clean_return_a")
sys.path.insert(0, r"C:\Users\celle\Documents\Codex\2026-09-06\okay-bro-let-s-do-the\work\nex-mini")
from stage_control import cloud  # noqa: E402

PROJECT = "cellensml"
BASE = f"https://compute.googleapis.com/compute/v1/projects/{PROJECT}"
BUCKET = "gs://cellens-ai-artifacts/arc3-duck"
PARENT_RUN = "g4run-la-clean-return-a132-w7-20260921-b4119c3bbb"


def sha(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def gcs_put(c, name, raw):
    r = requests.post("https://storage.googleapis.com/upload/storage/v1/b/cellens-ai-artifacts/o",
                      params={"uploadType": "media", "name": name}, data=raw,
                      headers={**c.headers, "Content-Type": "application/octet-stream"}, timeout=120)
    r.raise_for_status()


def gcs_exists(c, name):
    return requests.get("https://storage.googleapis.com/storage/v1/b/cellens-ai-artifacts/o/" + requests.utils.quote(name, safe=""),
                        headers=c.headers, timeout=60).status_code == 200


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", nargs="?", default="launch", choices=["launch", "status"])
    ap.add_argument("--variant", required=True)
    ap.add_argument("--arm-suffix", default="a")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--zones", default="europe-west4-b,europe-west4-a,europe-west4-c,europe-west1-b,us-central1-b")
    ap.add_argument("--suffix", default=secrets.token_hex(5))
    args = ap.parse_args()
    arm = HERE / "arms" / f"lacr_{args.variant}_{args.arm_suffix}"
    c = cloud()
    if args.command == "status":
        st = json.loads((arm / "STATUS.json").read_text())
        vm = c.get_json(BASE + f"/zones/{st['zone']}/instances/{st['instance']}", allow_missing=True)
        out = {"run_id": st["run_id"], "vm_status": vm.get("status")}
        for p in ("FAILED", "DONE", "HARD_TIMEOUT", "server-mode", "runs/score-observer/score-latest.json"):
            name = f"arc3-duck/{st['run_id']}/{p}"
            if gcs_exists(c, name):
                r = requests.get("https://storage.googleapis.com/storage/v1/b/cellens-ai-artifacts/o/" + requests.utils.quote(name, safe=""),
                                 params={"alt": "media"}, headers=c.headers, timeout=60)
                out[p] = r.json() if p.endswith(".json") else r.text.strip()[:200]
        print(json.dumps(out, indent=1)); return

    cfg = json.loads((arm / "CONFIG_FLAGS.json").read_text())
    cfg_sha = sha(arm / "CONFIG_FLAGS.json")
    startup = (arm / "startup.sh").read_text(encoding="utf-8")
    assert f"cap-compact132/{cfg_sha}/CONFIG_FLAGS.json" in startup
    delete_request_id = (arm / "DELETE_REQUEST_ID").read_text().strip()
    assert delete_request_id in startup
    body = json.loads((SRC_ARM / "instance-body.json").read_text())
    meta = {i["key"]: i["value"] for i in body["metadata"]["items"]}
    missing = sorted(k for k in json.loads((arm / "META_KEYS.json").read_text()) if k not in meta)
    assert not missing, ("startup reads metadata the body does not carry", missing)
    run_id = f"g4run-lacr-{args.variant.replace('_', '-')}-{args.arm_suffix}132-w7-{time.strftime('%Y%m%d')}-{args.suffix}"
    name = f"arc3-g4-lacr-{args.variant.replace('_', '-')}-{args.arm_suffix}-{args.suffix}"
    meta.update({"startup-script": startup, "arc3-run-id": run_id, "arc3-mig": name, "arc3-config-id": cfg["config_id"],
                 "arc3-parent-run-id": PARENT_RUN, "arc3-feature-arm": f"lacr_{args.variant}_{args.arm_suffix}",
                 "arc3-delete-request-id": delete_request_id, "arc3-repeat-of-run": ""})
    if args.variant == "batched16k":
        assert meta.get("arc3-serving-max-num-batched-tokens") == "6144", meta.get("arc3-serving-max-num-batched-tokens")
        meta["arc3-serving-max-num-batched-tokens"] = "16384"
    body["metadata"]["items"] = [{"key": k, "value": v} for k, v in sorted(meta.items())]
    body["name"] = name
    body["labels"].update({"arc3-matrix": "lacr-serving", "arc3-profile": f"lacr-{args.variant.replace('_', '-')}",
                           "config-id": cfg["config_id"][:20], "owner-task": "claude-lacr-serving"})
    assert body["scheduling"]["provisioningModel"] == "SPOT" and body["scheduling"]["instanceTerminationAction"] == "DELETE"
    assert body["scheduling"]["maxRunDuration"]["seconds"] == "14400"
    cfg_obj = f"arc3-duck/code/cap-compact132/{cfg_sha}/CONFIG_FLAGS.json"
    if not args.dry_run and not gcs_exists(c, cfg_obj):
        gcs_put(c, cfg_obj, (arm / "CONFIG_FLAGS.json").read_bytes()); print("uploaded", cfg_obj)
    last_err = None
    for zone in args.zones.split(","):
        b = json.loads(json.dumps(body))
        b["machineType"] = f"zones/{zone}/machineTypes/g4-standard-48"
        b["disks"][0]["initializeParams"]["diskType"] = f"zones/{zone}/diskTypes/hyperdisk-balanced"
        (arm / "instance-body.json").write_text(json.dumps(b, indent=2))
        print(f"== {zone}: {name} run_id={run_id} golden image spot maxRun=14400s")
        if args.dry_run:
            print("dry run: body written"); return
        r = requests.post(BASE + f"/zones/{zone}/instances", params={"requestId": str(uuid.uuid4())}, headers=c.headers, json=b, timeout=60)
        if r.status_code >= 400:
            last_err = r.text; print("insert refused:", last_err[:400]); continue
        op = r.json()
        for _ in range(60):
            time.sleep(5)
            st = c.get_json(op["selfLink"])
            if st.get("status") == "DONE":
                if st.get("error"):
                    last_err = json.dumps(st["error"]); print("operation error:", last_err[:400]); break
                print("CREATED", name, "in", zone)
                (arm / "STATUS.json").write_text(json.dumps({"run_id": run_id, "instance": name, "zone": zone,
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "config_id": cfg["config_id"],
                    "config_flags_sha256": cfg_sha, "bucket_prefix": f"{BUCKET}/{run_id}/", "delete_request_id": delete_request_id}, indent=2))
                return
        if last_err and any(k in last_err for k in ("ZONE_RESOURCE_POOL_EXHAUSTED", "QUOTA_EXCEEDED", "OPERATION_CANCELED_BY_USER", "preempted", "notFound")):
            continue
        break
    raise SystemExit(f"no zone accepted the instance; last error: {last_err}")


if __name__ == "__main__":
    main()

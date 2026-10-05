"""Daniel-notebook variant: host tier (his fork's HiCache) + over-admission + tuned drafter (2-Oct-2026, daniel-draft).

Son: over-park Daniel's server (11/12/13 games over his 10 server slots). Without a host tier that failed (oa12: prompt
cache hit 93% -> 81%, 2.5x recomputed prompt tokens, score 48 -> 35): his GPU holds ~1M tokens of KV + 60 Mamba states,
sized for 10 running games, so parked games lose their cached prompts. His fork already has a complete host tier for
this model (pool_host/: KV incl. the MTP draft's layer, Mamba states, QSA compressed index keys, target and draft); his
launcher just never enables it. This build:
  1. port cell after his setup cell: border off, DRAFT_MODEL_DIR -> the tuned drafter, ARC3_MAX_ACTIVE_STREAMS=<oa>,
     ARC3_HICACHE_GB=<gb>;
  2. his launcher cell: when ARC3_HICACHE_GB > 0, adds --enable-hierarchical-cache --hicache-size <gb>
     --hicache-write-policy write_through --hicache-io-backend kernel --hicache-mem-layout page_first (our stack's flags);
  3. a check cell right after the launcher (server up, no game started): teacher-forced logprobs of a 512-token suffix
     after a 60k-token prefix, fresh vs device-cached vs reloaded from host after filler prompts push the prefix off the
     GPU (lobotomy/kv4fix/qsa_hicache_test.py, sized for his pools) -> /kaggle/working/hicache_test.json. Never raises.
Host RAM: Kaggle and our G4 have 176.9 GB; his runs use ~121 GB (offloaded PLE), min ~51 GB free -> 32 GB tier.

  python make_hicache_notebook.py --oa 12 [--gb 32] --out nb-hic-oa12   (builds, uploads, prints the GCS object)
  python make_hicache_notebook.py --oa 12 --base-early <variant early.py> --frspec-map-env --out ...
      (on top of another build's port cell, e.g. the Reverse-flow thread's submission build variants/subbuild/ctl:
       its cell + ARC3_MAX_ACTIVE_STREAMS / ARC3_HICACHE_GB appended; same launcher edit and check cell)
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILDER = Path(r"D:\codex-work\daniel-base-20261001\build_daniel_notebook.py")
SOURCE = Path(r"D:\codex-work\daniel-base-20261001\nb-latest\arc-agi-3-milestone-2-solution.ipynb")
GCLOUD = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
BUCKET = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/notebooks"

PORT = r'''# --- daniel-draft port cell: host tier + over-admission + tuned drafter (2-Oct-2026; make_hicache_notebook.py) ---
# Border off (the deploy A/B control) + DRAFT_MODEL_DIR -> the retrained drafter + his gate admits __OA__ games over his
# 10 server slots + a __GB__ GB host tier (his fork's HiCache; the flags are added in his launcher cell).
import os as _os, sys as _sys

NOBORDER = {
    'ARC3_NOOP_GUARD_BORDER': '0', 'ARC3_BATCH_NOOP_BLOCK': '0', 'ARC3_STALE_STATE_BLOCK': '0',
    'ARC3_EXPLAIN_GAMEPLAY_CHANGED': '0', 'ARC3_REPORT_GAMEPLAY_CHANGED': '0', 'ARC3_NEW_CHANGED_PROMPTS': '0',
}
_os.environ.update(NOBORDER)
assert not any(m.startswith(('inference', 'taaf')) for m in _sys.modules), 'harness imported before the port cell'
_TUNED = '/kaggle/input/models/cellens/daniel-drafter-tuned/transformers/default/1'
assert _os.path.isfile(_os.path.join(_TUNED, 'TUNED.json')) and _os.path.isfile(_os.path.join(_TUNED, 'config.json')), _TUNED
_draft_before, DRAFT_MODEL_DIR = DRAFT_MODEL_DIR, _TUNED
_oa_before = _os.environ.get('ARC3_MAX_ACTIVE_STREAMS')
_os.environ['ARC3_MAX_ACTIVE_STREAMS'] = '__OA__'
_os.environ['ARC3_HICACHE_GB'] = '__GB__'
print('daniel-draft hicache port: border off | DRAFT_MODEL_DIR', _draft_before, '->', DRAFT_MODEL_DIR,
      '| ARC3_MAX_ACTIVE_STREAMS', _oa_before, '-> __OA__ (server max-running stays 10) | host tier __GB__ GB')
'''

PORT_ADD = r'''
# --- port: host tier + over-admission (Slice and dice, 2-Oct-2026; make_hicache_notebook.py --base-early) ---
# His gate admits __OA__ games over his 10 server slots; a __GB__ GB host tier (his fork's HiCache, flags added in his
# launcher cell) keeps parked games' cached prompts. Host reloads checked exact on 6 GCP runs (logprob ratio 0.9-1.3).
_oa_before = os.environ.get('ARC3_MAX_ACTIVE_STREAMS')
os.environ['ARC3_MAX_ACTIVE_STREAMS'] = '__OA__'
os.environ['ARC3_HICACHE_GB'] = '__GB__'
print('daniel-draft port hicache: ARC3_MAX_ACTIVE_STREAMS', _oa_before, '-> __OA__ (server max-running stays 10) | host tier __GB__ GB')
'''

LAUNCH_ANCHOR = "\n# ---- launch detached and wait for health ----\n"
LAUNCH_ADD = '''
if int(os.environ.get("ARC3_HICACHE_GB", "0")) > 0:  # daniel-draft: his fork's host tier (KV + draft KV, Mamba, QSA keys)
    args += ["--enable-hierarchical-cache", "--hicache-size", os.environ["ARC3_HICACHE_GB"],
             "--hicache-write-policy", "write_through", "--hicache-io-backend", "kernel", "--hicache-mem-layout", "page_first"]
'''

CHECK = r'''# --- daniel-draft: host-tier reload check (2-Oct-2026; make_hicache_notebook.py) ---
# Server up, no game started. Teacher-forced logprobs of a 512-token suffix after a 60k-token prefix, three ways: fresh
# (cache flushed), device (prefix just cached on the GPU), host (prefix pushed off the GPU by ~1.4M tokens of filler
# prompts, more than his ~1.0M-token GPU pool, less than the host tier, then reloaded). If host >> max(noise, device),
# host reloads change the model's outputs and this run's score is void. -> /kaggle/working/hicache_test.json. Never raises.
import os
from pathlib import Path

def _hct_run():
    import glob, json, sys as _s, time, urllib.error, urllib.request
    server = f"http://127.0.0.1:{SERVED_MODEL_PORT}"
    def post(path, body, timeout=3600):
        req = urllib.request.Request(server + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
        try:
            return json.loads(raw)
        except ValueError:
            return {"raw": raw.decode(errors="replace")[:200]}
    def flush():
        for _ in range(300):
            try:
                post("/flush_cache", {}); time.sleep(2); return
            except urllib.error.HTTPError:
                time.sleep(2)
        raise RuntimeError("flush_cache never succeeded")
    def host_hits():  # sglang:cached_tokens_total{...,cache_source="host"} (his metrics_collector)
        tot = 0.0
        for line in urllib.request.urlopen(server + "/metrics", timeout=30).read().decode().splitlines():
            if not line.startswith("#") and "cached_tokens_total" in line and 'cache_source="host"' in line:
                try:
                    tot += float(line.rsplit(" ", 1)[1])
                except ValueError:
                    pass
        return tot
    def score(ids, start):
        out = post("/generate", {"input_ids": ids, "sampling_params": {"temperature": 0, "max_new_tokens": 1},
                                 "return_logprob": True, "logprob_start_len": start})
        meta = out["meta_info"]
        return [x[0] for x in meta["input_token_logprobs"] if x[0] is not None], meta.get("cached_tokens", 0)
    def mad(a, b):
        n = min(len(a), len(b))
        return sum(abs(x - y) for x, y in zip(a[:n], b[:n])) / max(1, n)
    t0 = time.time()
    try:
        from tokenizers import Tokenizer
        enc = Tokenizer.from_file(str(Path(MODEL_DIR) / "tokenizer.json"))
        encode = lambda t: enc.encode(t, add_special_tokens=False).ids
    except Exception:
        from transformers import AutoTokenizer
        _t = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True)
        encode = lambda t: _t(t, add_special_tokens=False)["input_ids"]
    pool = []
    for f in sorted(glob.glob(_s.base_prefix + "/lib/python3*/**/*.py", recursive=True)):
        try:
            pool.extend(encode(open(f, encoding="utf-8", errors="replace").read()))
        except Exception:
            continue
        if len(pool) > 3_400_000:
            break
    plen, slen, flen, fill = 60000, 512, 90000, 1_400_000
    need = plen + 4 * slen + fill + flen
    out = {"prefix": plen, "suffix": slen, "fill_tokens": fill, "filler_len": flen, "pool_tokens": len(pool), "runs": []}
    for k in range(2):  # two prefixes, each with its own disjoint region (fillers never share prefixes)
        base = k * need
        assert base + need <= len(pool), (len(pool), need)
        P = pool[base: base + plen]
        S1, S2 = pool[base + plen: base + plen + slen], pool[base + plen + slen: base + plen + 2 * slen]
        res, fresh = {}, []
        for _ in range(3):
            flush(); lp, _c = score(P + S2, plen); fresh.append(lp)
        res["noise_fresh_vs_fresh"] = (mad(fresh[0], fresh[1]) + mad(fresh[0], fresh[2]) + mad(fresh[1], fresh[2])) / 3
        flush(); f1, _c = score(P + S1, plen)
        flush(); score(P, plen - 1); time.sleep(3)
        d1, c = score(P + S1, plen)
        res["device_cached"], res["device_vs_fresh"] = c, mad(d1, f1)
        host0 = host_hits()
        a = base + plen + 4 * slen
        while a + flen <= base + need:
            post("/generate", {"input_ids": pool[a: a + flen], "sampling_params": {"temperature": 0, "max_new_tokens": 1}})
            a += flen
        time.sleep(5)
        h2, c = score(P + S2, plen)
        res["host_cached"] = c
        res["host_tokens_loaded"] = host_hits() - host0
        res["host_vs_fresh"] = sum(mad(h2, f) for f in fresh) / 3
        print("daniel-draft hicache_run", json.dumps(res), flush=True)
        out["runs"].append(res)
    ok = [r for r in out["runs"] if r["host_tokens_loaded"] > 0.5 * plen]
    if not ok:
        out["verdict"] = "INCONCLUSIVE: host path not exercised"
    else:
        worst = max(r["host_vs_fresh"] / max(r["noise_fresh_vs_fresh"], r["device_vs_fresh"], 1e-3) for r in ok)
        out["verdict"] = ("BUG: host-loaded prefixes score differently (ratio %.1f)" % worst) if worst > 3 else ("OK: no clear difference (ratio %.1f)" % worst)
    out["seconds"] = round(time.time() - t0)
    flush()
    Path("/kaggle/working/hicache_test.json").write_text(json.dumps(out, indent=1))
    print("daniel-draft hicache_test", json.dumps({k: v for k, v in out.items() if k != "runs"}), flush=True)

if int(os.environ.get("ARC3_HICACHE_GB", "0")) > 0:
    try:
        _hct_run()
    except Exception as _e:
        print("daniel-draft hicache_test could not run:", repr(_e)[:800], flush=True)
'''


def src(c):
    return "".join(c["source"]) if isinstance(c["source"], list) else c["source"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oa", type=int, required=True, help="games admitted by his gate (server slots stay 10)")
    ap.add_argument("--gb", type=int, default=32, help="host tier size")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--base-early", type=Path, help="another build's port cell; ours is appended to it")
    ap.add_argument("--frspec-map-env", action="store_true", help="pass through to build_daniel_notebook.py")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    port = a.out / "port_cell.py"
    if a.base_early:
        text = a.base_early.read_text(encoding="utf-8").rstrip("\n") + "\n" + PORT_ADD
    else:
        text = PORT
    port.write_text(text.replace("__OA__", str(a.oa)).replace("__GB__", str(a.gb)), encoding="utf-8", newline="\n")
    base = a.out / "base"
    cmd = [sys.executable, str(BUILDER), "--source", str(SOURCE), "--early", str(port), "--compile-threads", "1",
           "--out", str(base)] + (["--frspec-map-env"] if a.frspec_map_env else [])
    subprocess.run(cmd, check=True, capture_output=True)
    nb = json.loads((base / "notebook.ipynb").read_text(encoding="utf-8"))
    hits = [i for i, c in enumerate(nb["cells"]) if c["cell_type"] == "code" and LAUNCH_ANCHOR in src(c)]
    assert len(hits) == 1, hits
    li = hits[0]
    s = src(nb["cells"][li])
    assert s.count(LAUNCH_ANCHOR) == 1 and "--speculative-draft-kv-cache-dtype" in s
    nb["cells"][li]["source"] = s.replace(LAUNCH_ANCHOR, LAUNCH_ADD + LAUNCH_ANCHOR)
    check = {"cell_type": "code", "execution_count": None, "id": "daniel-draft-hicache-check", "metadata": {},
             "outputs": [], "source": CHECK}
    nb["cells"].insert(li + 1, check)
    for c in nb["cells"]:  # compile every code cell we touched (magics excluded)
        if c is check or c is nb["cells"][li]:
            compile(src(c), "cell", "exec")
    data = (json.dumps(nb, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    (a.out / "notebook.ipynb").write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    obj = f"{BUCKET}/{sha[:12]}/notebook.ipynb"
    (a.out / "BUILD.json").write_text(json.dumps({"oa": a.oa, "hicache_gb": a.gb, "base_early": str(a.base_early or ""),
                                                  "frspec_map_env": a.frspec_map_env, "launcher_cell": li, "check_cell": li + 1,
                                                  "notebook_sha256": sha, "gcs_object": obj}, indent=1))
    subprocess.run(GCLOUD + ["storage", "cp", "-q", str(a.out / "notebook.ipynb"), obj], check=True)
    print(obj)


if __name__ == "__main__":
    main()

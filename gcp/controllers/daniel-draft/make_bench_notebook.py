"""Throughput-scaling bench of Daniel Franzen's server (3-Oct-2026, daniel-draft; Son's go via the Reverse-flow thread).

His real notebook is the bench (live harness: images, 58k drains, middle truncation, branching), on the submission build
(--base-early: border off + ARC hot map + tuned drafter), with a 60-minute gameplay budget (not a scored run), and:
  server   (his launcher CFG reads env)  slots S (--max-running-requests and CUDA-graph max bs), context, Mamba cache,
           target KV dtype, draft KV dtype (his launcher passed one KV dtype to both; the draft has no nvfp4 choice),
           mem fraction, optional --mamba-max-states-per-path, optional 32 GB host tier;
  harness  gate = S + 1 games (ARC3_MAX_ACTIVE_STREAMS), context window and drain scaled by 10/S
           (his: LOCAL_ANALYZER_CONTEXT_WINDOW 128k, ARC3_CONTEXT_DRAIN_TOKENS 58k; server CTX = window + 8k);
  cells    after his launcher: host-reload check (with a host tier), KL probe (teacher-forced logprobs of recorded
           responses, images stripped, from kl_set.json in the input mirror -> working/kl_probe.json), and a /metrics
           scraper thread (every 60 s -> working/metrics.jsonl: cached tokens by device/host, prompt/generation totals,
           running/queued, token usage, spec accept).

  python make_bench_notebook.py --base-early <early.py> --slots 12 [--gate 13] [--kv nvfp4] [--hicache-gb 32]
                                [--path-cap 2] [--mamba N] [--memfrac 0.96] [--minutes 60] [--kl]
                                [--profile-at 12,30 --profile-steps 30] [--routing 10]
                                [--qsa-ring 12 --spec-steps 7 --qsa-check 10] [--ba-k0 6] [--kv4] [--window N]
                                --out DIR
  --kv4:        4-bit KV for the QSA layers (qsakv4/: our 0007 NVFP4 patch ported to his fork, on top of qsaring)
                --kv-cache-dtype nvfp4_qsa, draft KV fp8, no host tier; a check cell runs
                qsakv4/test_qsa_nvfp4_daniel.py --skip-speed in his venv -> working/kv4_test.json
  --window:     harness context window (default 131k x 10/slots); server CTX = window + 8k
  --ba-k0:      batch-aware expert routing (barouting/: his topk.py patched): each token keeps its top k0 experts,
                its other slots refill from experts the batch already loads (decode/verify batches only)
  --qsa-ring:   QSA pending ring of R slots per request (qsaring/: five patched files of his fork; allows target
                verifies of up to R - 3 tokens; 0 = his wheel untouched)
  --spec-steps: MTP draft steps (his 3; verify width = steps + 1)
  --qsa-check:  before any game, N kl_set prompts: greedy generation, then probe logprobs cached vs fresh
                -> working/qsa_check.json
  --profile-at: torch-profiler traces of N forward steps at those minutes (once >= slots-1 requests run)
                -> working/profile/m<minute>/ (Son 3-Oct: faster MoE; parse with live/profile_report.py)
  --routing:    before any game, N concurrent kl_set prompts generate with return_routed_experts (server flag
                --enable-return-routed-experts) -> working/routing/req<i>.json (batch-aware routing study)
"""
import argparse
import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_hicache_notebook as H  # noqa: E402
QSA = {}
exec((HERE / "qsaring" / "bench_qsa_src.py").read_text(encoding="utf-8"), QSA)  # QSA_FILES, QSA_PORT, QSA_CHECK
import make_variant_notebook as V  # noqa: E402  (RS_FILES, RS_LAUNCH_ADD, RS_CHECK, RS_TEST: rejection sampling, 0008 v2)

WINDOW, DRAIN, MARGIN = 128 * 1024, 58 * 1024, 8 * 1024   # his harness window / drain, server CTX = window + 8k

OVERRIDE = """\
# --- daniel-draft bench override (make_bench_notebook.py; 3-Oct-2026) ---
# Throughput bench, NOT a scored run: same 25 public games, every game admitted at once (pooled clock), but a
# __MIN__-minute gameplay budget.
demo_excluded_games = []
bm.solver.concurrency = 25
bm.solver.max_runtime_s_per_game = __SEC__
print('daniel-draft bench override: concurrency', bm.solver.concurrency, '| max_runtime_s_per_game',
      bm.solver.max_runtime_s_per_game, '| priority', USE_PRIORITY_SCHEDULING)
"""

PORT_ADD = r'''
# --- port: throughput-scaling bench (Slice and dice, 3-Oct-2026; make_bench_notebook.py) ---
_bench = __BENCH__
os.environ.update({k: str(v) for k, v in _bench.items()})
print('daniel-draft bench port:', _bench)
'''

CFG_EDITS = [  # his launcher CFG -> env-driven (defaults = his values)
    ('    CTX=(116+12+8)*1024,\n', '    CTX=int(os.environ.get("ARC3_SRV_CTX", (116+12+8)*1024)),\n'),
    ('    MEMFRAC=0.96,\n', '    MEMFRAC=float(os.environ.get("ARC3_SRV_MEMFRAC", 0.96)),\n'),
    ('    MAXREQ=10,\n', '    MAXREQ=int(os.environ.get("ARC3_SRV_MAXREQ", 10)),\n'),
    ('    CUDAGRAPH_MAXBS=10,\n', '    CUDAGRAPH_MAXBS=int(os.environ.get("ARC3_SRV_MAXREQ", 10)),\n'),
    ('    MAMBA_CACHE=60,\n', '    MAMBA_CACHE=int(os.environ.get("ARC3_SRV_MAMBA", 60)),\n'),
    ('    SPEC_STEPS=3,\n', '    SPEC_STEPS=int(os.environ.get("ARC3_SRV_SPEC_STEPS", 3)),\n'),
    ('"SGLANG_SM120_ONLINE_MXFP8": "0",',
     '"SGLANG_SM120_ONLINE_MXFP8": os.environ.get("SGLANG_SM120_ONLINE_MXFP8", "0"),'),
    ('    KVDTYPE="fp8_e4m3",\n', '    KVDTYPE=os.environ.get("ARC3_SRV_KVDTYPE", "fp8_e4m3"),\n'),
    ('"--speculative-draft-kv-cache-dtype", CFG["KVDTYPE"],',
     '"--speculative-draft-kv-cache-dtype", os.environ.get("ARC3_SRV_DRAFT_KVDTYPE", "fp8_e4m3"),'),
]
LAUNCH_ADD = '''
if int(os.environ.get("ARC3_SRV_PATH_CAP", "0")) > 0:  # daniel-draft bench: cap Mamba states per radix path
    args += ["--mamba-max-states-per-path", os.environ["ARC3_SRV_PATH_CAP"]]
if os.environ.get("ARC3_SRV_ATTN"):  # daniel-draft bench: attention backend (his fork's nvfp4 KV refuses flashinfer)
    args += ["--attention-backend", os.environ["ARC3_SRV_ATTN"]]
if os.environ.get("ARC3_SRV_ROUTED") == "1":  # daniel-draft bench: per-token expert routing in responses
    args += ["--enable-return-routed-experts"]
'''
SPEC_OFF = '''
# daniel-draft make_bench_notebook.py --spec-off (4-Oct-2026): plain decode, one token per step (draft width 1). Drops
# every --speculative-* flag and its values from his launch list; the drafter's weights and draft KV are not loaded.
_kept, _i = [], 0
while _i < len(args):
    if str(args[_i]).startswith("--speculative-"):
        _i += 1
        while _i < len(args) and not str(args[_i]).startswith("--"):
            _i += 1
        continue
    _kept.append(args[_i])
    _i += 1
args = _kept
print("daniel-draft bench: speculative decoding OFF")
'''

METRICS = r'''# --- daniel-draft bench: /metrics scraper (3-Oct-2026) --- every 60 s -> /kaggle/working/metrics.jsonl
import json as _mj, threading as _mt, time as _mtm, urllib.request as _mu
_KEYS = ("cached_tokens_total", "prompt_tokens_total", "generation_tokens_total", "num_running_reqs", "num_queue_reqs",
         "token_usage", "spec_accept", "num_requests_total", "cache_hit_rate", "mamba")
def _scrape():
    while True:
        try:
            txt = _mu.urlopen(f"http://127.0.0.1:{SERVED_MODEL_PORT}/metrics", timeout=20).read().decode()
            row = {"t": round(_mtm.time(), 1)}
            for line in txt.splitlines():
                if line.startswith("#") or not any(k in line for k in _KEYS) or "_created" in line:
                    continue
                name, _, val = line.rpartition(" ")
                try:
                    row[name] = float(val)
                except ValueError:
                    pass
            with open("/kaggle/working/metrics.jsonl", "a") as f:
                f.write(_mj.dumps(row) + "\n")
        except Exception as e:
            with open("/kaggle/working/metrics.jsonl", "a") as f:
                f.write(_mj.dumps({"t": round(_mtm.time(), 1), "error": repr(e)[:200]}) + "\n")
        _mtm.sleep(60)
_mt.Thread(target=_scrape, daemon=True, name="daniel-draft-metrics").start()
print("daniel-draft bench: metrics scraper started")
'''

KL = r'''# --- daniel-draft bench: KL probe (3-Oct-2026) --- before any game: teacher-forced logprobs of RECORDED responses
# (kl_set.json: requests from daniel-sb-ctl-a-1002 with their recorded responses, images stripped) on this server's KV
# setting -> /kaggle/working/kl_probe.json (per request: response token ids, their logprobs, top-1 ids). Compared
# offline across KV settings. Never raises.
def _kl_probe():
    import json, time, urllib.request
    from pathlib import Path
    from transformers import AutoTokenizer
    src = Path("/kaggle/input/datasets/cellens/daniel-bench/kl_set.json")
    if not src.exists():
        print("daniel-draft kl probe: no kl_set.json"); return
    items = json.loads(src.read_text())
    tok = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True)
    tmpl = Path(MODEL_DIR, "chat_template.jinja")
    if tmpl.is_file():
        tok.chat_template = tmpl.read_text()
    out, t0 = [], time.time()
    for it in items:
        # render TEXT, then tokenize: some transformers versions return a dict from apply_chat_template(tokenize=True)
        kw = dict(tools=it.get("tools"), tokenize=False, preserve_thinking=True)
        pt = tok.apply_chat_template(it["messages"], add_generation_prompt=True, **kw)
        ft = tok.apply_chat_template(it["messages"] + [it["response"]], add_generation_prompt=False, **kw)
        p = list(tok(pt, add_special_tokens=False)["input_ids"])
        full = list(tok(ft, add_special_tokens=False)["input_ids"])
        L = 0  # common token prefix (the newline after the think tag may merge with the reasoning's first token)
        while L < min(len(p), len(full)) and p[L] == full[L]:
            L += 1
        if not ft.startswith(pt) or L < len(p) - 2 or len(full) <= L:
            out.append({"id": it["id"], "error": f"template prefix mismatch (prompt {len(p)}, full {len(full)}, common {L})"}); continue
        p = full[:L]
        full = full[:L + 256]  # cap: logprobs over ~2k tokens x 248k vocab (fp32) OOM the server
        body = {"input_ids": full, "sampling_params": {"temperature": 0, "max_new_tokens": 1}, "return_logprob": True,
                "logprob_start_len": len(p) - 1, "top_logprobs_num": 1}
        req = urllib.request.Request(f"http://127.0.0.1:{SERVED_MODEL_PORT}/generate", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        meta = json.loads(urllib.request.urlopen(req, timeout=1800).read())["meta_info"]
        lps = [x[0] for x in meta["input_token_logprobs"]][1:]
        tops = [x[0][1] if x else None for x in meta["input_top_logprobs"]][1:]
        out.append({"id": it["id"], "prompt_len": len(p), "tokens": full[len(p):], "logprobs": lps, "top1": tops})
    Path("/kaggle/working/kl_probe.json").write_text(json.dumps({"kv": os.environ.get("ARC3_SRV_KVDTYPE", "fp8_e4m3"),
                                                                 "seconds": round(time.time() - t0), "items": out}))
    print("daniel-draft kl probe:", len(out), "requests,", sum(len(o.get("tokens", [])) for o in out), "tokens,",
          round(time.time() - t0), "s", flush=True)
try:
    _kl_probe()
except Exception as _e:
    print("daniel-draft kl probe could not run:", repr(_e)[:800], flush=True)
'''

PROFILE = r'''# --- daniel-draft bench: decode profile (3-Oct-2026; Son: faster MoE) --- background thread: at each minute mark
# (counted from this cell), once >= __MINRUN__ requests run, POST /start_profile for __STEPS__ forward steps (torch
# profiler, CPU+GPU) -> /kaggle/working/profile/m<minute>/ ; log in /kaggle/working/profile/log.txt. Never raises.
import json as _pj, os as _po, threading as _pt, time as _ptm, urllib.request as _pu
def _prof():
    t0 = _ptm.time()
    _po.makedirs("/kaggle/working/profile", exist_ok=True)
    def log(msg):
        with open("/kaggle/working/profile/log.txt", "a") as f:
            f.write(_ptm.strftime("%H:%M:%S") + " " + msg + "\n")
    for m in __MARKS__:
        try:
            while _ptm.time() < t0 + m * 60:
                _ptm.sleep(10)
            run, deadline = -1.0, _ptm.time() + 900
            while _ptm.time() < deadline:
                try:
                    txt = _pu.urlopen(f"http://127.0.0.1:{SERVED_MODEL_PORT}/metrics", timeout=20).read().decode()
                    run = max([float(l.rpartition(" ")[2]) for l in txt.splitlines()
                               if l.startswith("sglang:num_running_reqs")] or [0.0])
                except Exception:
                    run = -1.0
                if run >= __MINRUN__:
                    break
                _ptm.sleep(5)
            body = {"output_dir": f"/kaggle/working/profile/m{m}", "num_steps": __STEPS__, "activities": ["CPU", "GPU"],
                    "profile_prefix": f"m{m}"}
            req = _pu.Request(f"http://127.0.0.1:{SERVED_MODEL_PORT}/start_profile", data=_pj.dumps(body).encode(),
                              headers={"Content-Type": "application/json"})
            r = _pu.urlopen(req, timeout=900).read().decode()[:300]
            log(f"m{m}: running {run}: start_profile -> {r}")
        except Exception as e:
            log(f"m{m}: failed {e!r}"[:500])
_pt.Thread(target=_prof, daemon=True, name="daniel-draft-profile").start()
print("daniel-draft bench: profile thread started, marks", __MARKS__, "steps", __STEPS__)
'''

ROUTING = r'''# --- daniel-draft bench: routing dump (3-Oct-2026; batch-aware routing study) --- before any game: the __N__
# shortest kl_set prompts (chat-rendered) generate together at T0.7/top-k 20/top-p 0.95 for __NEW__ tokens with
# return_routed_experts from the prompt end -> /kaggle/working/routing/req<i>.json. Never raises.
def _routing_dump():
    import json, time, urllib.request
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    from transformers import AutoTokenizer
    src = Path("/kaggle/input/datasets/cellens/daniel-bench/kl_set.json")
    if not src.exists():
        print("daniel-draft routing: no kl_set.json"); return
    items = json.loads(src.read_text())
    tok = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True)
    tmpl = Path(MODEL_DIR, "chat_template.jinja")
    if tmpl.is_file():
        tok.chat_template = tmpl.read_text()
    reqs = []
    for it in items:
        pt = tok.apply_chat_template(it["messages"], add_generation_prompt=True, tools=it.get("tools"),
                                     tokenize=False, preserve_thinking=True)
        reqs.append((it["id"], list(tok(pt, add_special_tokens=False)["input_ids"])))
    reqs = sorted(reqs, key=lambda r: len(r[1]))[:__N__]
    out = Path("/kaggle/working/routing")
    out.mkdir(parents=True, exist_ok=True)
    def one(kr):
        k, (rid, ids) = kr
        body = {"input_ids": ids, "return_routed_experts": True, "routed_experts_start_len": len(ids),
                "sampling_params": {"temperature": 0.7, "top_k": 20, "top_p": 0.95, "max_new_tokens": __NEW__}}
        req = urllib.request.Request(f"http://127.0.0.1:{SERVED_MODEL_PORT}/generate", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        t = time.time()
        r = json.loads(urllib.request.urlopen(req, timeout=3600).read())
        meta = r.get("meta_info", {}) or {}
        rexp = meta.pop("routed_experts", None) or r.get("routed_experts")
        keep = {kk: vv for kk, vv in meta.items() if isinstance(vv, (int, float, str)) or kk.startswith("spec")}
        (out / f"req{k}.json").write_text(json.dumps({"id": rid, "prompt_len": len(ids),
                                                      "seconds": round(time.time() - t, 1),
                                                      "output_ids": r.get("output_ids"), "routed_experts": rexp,
                                                      "meta": keep}))
        return k, len(rexp or "")
    t0 = time.time()
    with ThreadPoolExecutor(len(reqs)) as ex:
        done = list(ex.map(one, enumerate(reqs)))
    print("daniel-draft routing:", done, "in", round(time.time() - t0), "s", flush=True)
try:
    _routing_dump()
except Exception as _e:
    print("daniel-draft routing dump could not run:", repr(_e)[:800], flush=True)
'''


KV4_FILES = [
    "sglang/srt/layers/attention/flashinfer_backend.py",
    "sglang/srt/layers/attention/qsa/sparse_attn.py",
    "sglang/srt/layers/attention/qwen_sparse_attn_backend.py",
    "sglang/srt/layers/quantization/fp4_kv_cache_quant_method.py",
    "sglang/srt/mem_cache/kv_cache_configurator.py",
    "sglang/srt/mem_cache/kv_cache_dtype.py",
    "sglang/srt/mem_cache/memory_pool.py",
    "sglang/srt/server_args.py",
]

KV4H_FILES = [
    "sglang/srt/mem_cache/pool_host/mha.py",
    "sglang/srt/mem_cache/hybrid_cache/hybrid_pool_assembler.py",
    "sglang/srt/mem_cache/kv_cache_configurator.py",
    "sglang/srt/server_args.py",
]


KV4_CHECK = r'''# --- daniel-draft: NVFP4 QSA KV check (3-Oct-2026) --- qsakv4/test_qsa_nvfp4_daniel.py --skip-speed in his venv
# (the patched install, next to the live server): gather kernels vs a torch reference and FlashInfer's dequantizer,
# the write path, backend decode / chunked prefill vs an unquantized pool, CUDA-graph replay.
# -> /kaggle/working/kv4_test.json (+ .log). Never raises.
import os, subprocess
from pathlib import Path
try:
    _t = Path('/kaggle/working/test_qsa_nvfp4_daniel.py')
    _t.write_bytes(__import__('base64').b64decode(__TEST__))
    _r = subprocess.run([PYTHON, str(_t), '--skip-speed'], capture_output=True, text=True, timeout=1800,
                        env=dict(globals().get('env') or os.environ))
    Path('/kaggle/working/kv4_test.log').write_text(_r.stdout + '\n' + _r.stderr[-6000:])
    _last = [l for l in _r.stdout.splitlines() if l.startswith('{')]
    Path('/kaggle/working/kv4_test.json').write_text('\n'.join(_last) + '\n')
    print('daniel-draft kv4_test rc', _r.returncode, '|', (_last[-1][:600] if _last else _r.stderr[-1200:]), flush=True)
except Exception as _e:
    print('daniel-draft kv4_test could not run:', repr(_e)[:800], flush=True)
'''


BA_CHECK = r'''# --- daniel-draft: batch-aware routing unit test (3-Oct-2026) --- barouting/test_ba.py in his venv (the patched
# install): core experts kept, distinct experts never grow, weight sums kept, padded rows untouched, CUDA-graph
# replay. -> /kaggle/working/ba_test.json (+ .log). Never raises.
import os, subprocess
from pathlib import Path
try:
    _t = Path('/kaggle/working/test_ba.py')
    _t.write_bytes(__import__('base64').b64decode(__TEST__))
    _r = subprocess.run([PYTHON, str(_t)], capture_output=True, text=True, timeout=900,
                        env=dict(globals().get('env') or os.environ))
    Path('/kaggle/working/ba_test.log').write_text(_r.stdout + '\n' + _r.stderr[-4000:])
    _last = [l for l in _r.stdout.splitlines() if l.startswith('{')]
    Path('/kaggle/working/ba_test.json').write_text('\n'.join(_last) + '\n')
    print('daniel-draft ba_test rc', _r.returncode, '|', (_last[-1][:600] if _last else _r.stderr[-800:]), flush=True)
except Exception as _e:
    print('daniel-draft ba_test could not run:', repr(_e)[:800], flush=True)
'''


# --pre-script: inserted in the launcher cell right before the server launch (PYTHON and the patched install exist,
# the GPU is still free). Kernel micro-benchmarks and GPU tests that need the whole card (3-Oct-2026).
PRE = r'''
# ---- daniel-draft: pre-server scripts (3-Oct-2026; make_bench_notebook.py --pre-script): his venv, patched install,
# free GPU. -> /kaggle/working/pre_<stem>.json (stdout lines starting with "{") + pre_<stem>.log. Never raises.
import base64 as _pb64, subprocess as _psp
from pathlib import Path as _PP
for _pn, _pc in __FILES__:
    _PP('/kaggle/working', _pn).write_bytes(_pb64.b64decode(_pc))
for _pn, _pc in __SCRIPTS__:
    _pt = _PP('/kaggle/working', _pn)
    try:
        _pt.write_bytes(_pb64.b64decode(_pc))
        _pr = _psp.run([PYTHON, str(_pt)], capture_output=True, text=True, timeout=__TIMEOUT__, cwd='/kaggle/working',
                       env=dict(globals().get('env') or os.environ))
        _PP(f'/kaggle/working/pre_{_pt.stem}.log').write_text(_pr.stdout + '\n--- stderr ---\n' + _pr.stderr[-20000:])
        _pl = [l for l in _pr.stdout.splitlines() if l.startswith('{')]
        _PP(f'/kaggle/working/pre_{_pt.stem}.json').write_text('\n'.join(_pl) + '\n')
        print('daniel-draft pre', _pn, 'rc', _pr.returncode, '|', (_pl[-1][:600] if _pl else _pr.stderr[-1200:]), flush=True)
    except Exception as _pe:
        print('daniel-draft pre', _pn, 'could not run:', repr(_pe)[:800], flush=True)
'''
PRE_STOP = '''raise RuntimeError("daniel-draft --pre-only: stopped before the server; results in /kaggle/working/pre_*")
'''


def src(c):
    return "".join(c["source"]) if isinstance(c["source"], list) else c["source"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-early", type=Path, required=True)
    ap.add_argument("--slots", type=int, required=True)
    ap.add_argument("--gate", type=int, help="games admitted (default slots + 1)")
    ap.add_argument("--kv", default="fp8_e4m3")
    ap.add_argument("--hicache-gb", type=int, default=0)
    ap.add_argument("--path-cap", type=int, default=0)
    ap.add_argument("--mamba", type=int, help="Mamba cache states (default 4 per slot + 20 parked, min 60)")
    ap.add_argument("--memfrac", type=float, default=0.96)
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--kl", action="store_true")
    ap.add_argument("--attn", default="", help="--attention-backend override")
    ap.add_argument("--profile-at", default="", help="comma list of minutes for profiler traces")
    ap.add_argument("--profile-steps", type=int, default=30)
    ap.add_argument("--routing", type=int, default=0, help="routing dump: number of concurrent requests")
    ap.add_argument("--routing-new", type=int, default=3072)
    ap.add_argument("--qsa-ring", type=int, default=0)
    ap.add_argument("--spec-steps", type=int, default=0)
    ap.add_argument("--qsa-check", type=int, default=0)
    ap.add_argument("--qsa-check-new", type=int, default=1024)
    ap.add_argument("--ba-k0", type=int, default=0)
    ap.add_argument("--kv4", action="store_true")
    ap.add_argument("--kv4-host", action="store_true", help="--kv4 plus his host tier (qsakv4h/); needs --hicache-gb")
    ap.add_argument("--kv-hadamard", action="store_true", help="Hadamard-rotated K/V in the QSA layers (qsahad/)")
    ap.add_argument("--window", type=int, default=0)
    ap.add_argument("--rs", action="store_true", help="rejection sampling over the hot draft vocab (make_variant_notebook.py's "
                    "patch 0008 v2; Son 3-Oct: fold 4-bit KV into the toolfast + rejection-sampling candidate), "
                    "merged into the same shadow wheel; its exactness check cell runs after the launcher")
    ap.add_argument("--env", action="append", default=[], help="KEY=VALUE for the server (repeatable)")
    ap.add_argument("--patch-set", action="append", default=[], type=Path,
                    help="extra patch set DIR with orig/ + patched/ trees (paths inside the wheel, sglang/srt/...); "
                         "every patched/**/*.py goes into the shadow wheel (repeatable)")
    ap.add_argument("--pre-script", action="append", default=[], type=Path,
                    help="python script run in his venv on the free GPU just before the server starts (after the "
                         "patched install); stdout lines starting with '{' -> /kaggle/working/pre_<stem>.json, "
                         "full output -> pre_<stem>.log (repeatable, in order)")
    ap.add_argument("--pre-file", action="append", default=[], type=Path,
                    help="extra file copied into /kaggle/working before the pre-scripts run (helper modules, data)")
    ap.add_argument("--pre-timeout", type=int, default=3600, help="seconds per pre-script")
    ap.add_argument("--server-args", default="",
                    help='extra sglang server CLI args, one shell-quoted string appended last (later flags win), '
                         'e.g. --server-args="--speculative-eagle-topk 2 --speculative-num-draft-tokens 6"')
    ap.add_argument("--pre-only", action="store_true",
                    help="stop after the pre-scripts: no server, no games, no later cells (the run ends notebook_rc_1)")
    ap.add_argument("--spec-off", action="store_true",
                    help="speculative decoding off (draft width 1): strips his --speculative-* launch flags")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    assert not a.pre_only or a.pre_script, "--pre-only needs --pre-script"
    assert not (a.spec_off and (a.rs or a.spec_steps or a.qsa_ring)), "--spec-off: no --rs / --spec-steps / --qsa-ring"
    S = a.slots
    window, drain = WINDOW * 10 // S, DRAIN * 10 // S
    if a.window:  # explicit window: drain keeps his 58k/128k proportion
        window, drain = a.window, a.window * DRAIN // WINDOW
    if a.kv4_host:
        assert a.hicache_gb, '--kv4-host needs --hicache-gb'
        a.kv4 = True
    elif a.kv4:
        assert not a.hicache_gb, '--kv4: nvfp4_qsa refuses the host tier unless --kv4-host (qsakv4h port)'
    if a.kv4:
        a.kv = 'nvfp4_qsa'
    bench = {"ARC3_SRV_MAXREQ": S, "ARC3_SRV_CTX": window + MARGIN, "ARC3_SRV_MAMBA": a.mamba or max(60, 4 * S + 20),
             "ARC3_SRV_KVDTYPE": a.kv, "ARC3_SRV_DRAFT_KVDTYPE": "fp8_e4m3", "ARC3_SRV_MEMFRAC": a.memfrac,
             "ARC3_SRV_PATH_CAP": a.path_cap, "ARC3_MAX_ACTIVE_STREAMS": a.gate or S + 1,
             "LOCAL_ANALYZER_CONTEXT_WINDOW": window, "ARC3_CONTEXT_DRAIN_TOKENS": drain}
    if a.attn:
        bench["ARC3_SRV_ATTN"] = a.attn
    if a.hicache_gb:
        bench["ARC3_HICACHE_GB"] = a.hicache_gb
    if a.routing:
        bench["ARC3_SRV_ROUTED"] = 1
    if a.spec_steps:
        bench["ARC3_SRV_SPEC_STEPS"] = a.spec_steps
    for kv in a.env:  # extra server env, e.g. SGLANG_SM120_ONLINE_MXFP8=1
        k, _, v = kv.partition("=")
        assert k and v, kv
        bench[k] = v
    if a.spec_steps and a.spec_steps + 1 > 4:
        assert a.qsa_ring >= a.spec_steps + 1 + 3, "verify width needs --qsa-ring >= steps + 4"
    a.out.mkdir(parents=True, exist_ok=True)
    port = a.base_early.read_text(encoding="utf-8").rstrip("\n") + "\n" + PORT_ADD.replace("__BENCH__", repr(bench))
    files = {}  # patch sets merged into one shadow wheel: published path -> (his sha256, patched bytes b64)

    def add_set(dirname, names, override=False):
        for n in names:
            orig = (HERE / dirname / "orig" / n).read_bytes()
            new = (HERE / dirname / "patched" / n).read_bytes()
            compile(new, n, "exec")
            if n in files:  # only --patch-set may supersede (its patched file must carry the earlier set's changes)
                assert override, ("two patch sets change", n)
                assert files[n][0] == hashlib.sha256(orig).hexdigest(), ("superseding set's orig differs", n)
                print(f"patch-set {Path(dirname).name} supersedes {n}", file=sys.stderr)
            files[n] = (hashlib.sha256(orig).hexdigest(), base64.b64encode(new).decode())
    if a.kv4:  # qsakv4 carries its own backend (built on qsaring's); the other four qsaring files are needed
        add_set("qsaring", [n for n in QSA["QSA_FILES"] if not n.endswith("qwen_sparse_attn_backend.py")])
        if a.kv4_host:  # qsakv4h supersedes qsakv4's configurator + server_args and adds the host pool files
            add_set("qsakv4", [n for n in KV4_FILES if n not in KV4H_FILES])
            add_set("qsakv4h", KV4H_FILES)
        else:
            add_set("qsakv4", KV4_FILES)
    elif a.qsa_ring:
        add_set("qsaring", QSA["QSA_FILES"])
    if a.ba_k0:
        add_set("barouting", ["sglang/srt/layers/moe/topk.py"])
    if a.kv_hadamard:
        add_set("qsahad", ["sglang/srt/models/qwen4_exp.py"])
    if a.rs:  # his three speculative files; no other set touches them (add_set asserts it)
        add_set("rs", V.RS_FILES)
    for d in a.patch_set:  # generic extra sets (absolute dirs; HERE / abs = abs), applied last, may supersede
        add_set(d.resolve(), sorted(p.relative_to(d.resolve() / "patched").as_posix()
                                    for p in (d.resolve() / "patched").rglob("*.py")), override=True)
    if files:
        port += QSA["QSA_PORT"].replace("__QSA_FILES__", repr(files)).replace("__RING__", str(a.qsa_ring))
    if a.ba_k0:
        port += f"\nos.environ['SGLANG_BA_K0'] = '{a.ba_k0}'  # daniel-draft: batch-aware routing\n"
    if a.kv_hadamard:
        port += "\nos.environ['SGLANG_QSA_KV_HADAMARD'] = '1'  # daniel-draft: Hadamard-rotated QSA K/V\n"
    if a.rs:
        port += ("\nos.environ['ARC3_SPEC_RS'] = '1'  # daniel-draft: rejection sampling over the hot draft vocab (0008 v2)\n"
                 "print('daniel-draft port rs: 0008 v2 files in the shadow wheel | ARC3_SPEC_RS=1')\n")
    (a.out / "port_cell.py").write_text(port, encoding="utf-8", newline="\n")
    ov = OVERRIDE.replace("__MIN__", str(a.minutes)).replace("__SEC__", str(a.minutes * 60))
    (a.out / "override.py").write_text(ov, encoding="utf-8", newline="\n")
    base = a.out / "base"
    subprocess.run([sys.executable, str(H.BUILDER), "--source", str(H.SOURCE), "--early", str(a.out / "port_cell.py"),
                    "--override", str(a.out / "override.py"), "--compile-threads", "1", "--frspec-map-env",
                    "--out", str(base)], check=True, capture_output=True)
    nb = json.loads((base / "notebook.ipynb").read_text(encoding="utf-8"))
    hits = [i for i, c in enumerate(nb["cells"]) if c["cell_type"] == "code" and H.LAUNCH_ANCHOR in src(c)]
    assert len(hits) == 1, hits
    li = hits[0]
    s = src(nb["cells"][li])
    for old, new in CFG_EDITS:
        assert s.count(old) == 1, ("launcher edit anchor", old)
        s = s.replace(old, new)
    pre = ""
    if a.pre_script:
        b64 = lambda p: base64.b64encode(p.read_bytes()).decode()  # noqa: E731
        pre = (PRE.replace("__FILES__", repr([(p.name, b64(p)) for p in a.pre_file]))
               .replace("__SCRIPTS__", repr([(p.name, b64(p)) for p in a.pre_script]))
               .replace("__TIMEOUT__", str(a.pre_timeout)))
        if a.pre_only:
            pre += PRE_STOP
    if a.server_args:
        import shlex
        pre = f"\nargs += {shlex.split(a.server_args)!r}  # daniel-draft make_bench_notebook.py --server-args\n" + pre
        bench_note = {"server_args": a.server_args}
    else:
        bench_note = {}
    if a.spec_off:
        pre += SPEC_OFF
        bench_note["spec_off"] = True
    s = s.replace(H.LAUNCH_ANCHOR, H.LAUNCH_ADD + LAUNCH_ADD + (V.RS_LAUNCH_ADD if a.rs else "") + pre + H.LAUNCH_ANCHOR)
    compile(s, "launcher", "exec")
    nb["cells"][li]["source"] = s
    if a.pre_only:  # nothing after the launcher would run anyway
        del nb["cells"][li + 1:]
    cells = []
    if a.hicache_gb:
        cells.append(("daniel-draft-hicache-check", H.CHECK))
    if a.kl:
        cells.append(("daniel-draft-kl-probe", KL))
    if a.kv4:
        kb64 = base64.b64encode((HERE / "qsakv4" / "test_qsa_nvfp4_daniel.py").read_bytes()).decode()
        cells.append(("daniel-draft-kv4-check", KV4_CHECK.replace("__TEST__", repr(kb64))))
    if a.rs:  # same check cell as make_variant_notebook.py --rs
        rb64 = base64.b64encode(V.RS_TEST.read_text(encoding="utf-8").replace(
            'load_token_map("/sgl/hot_tokens_64k.pt")',
            'load_token_map(__import__("os").environ.get("RS_TEST_MAP") or "/sgl/hot_tokens_64k.pt")').encode()).decode()
        cells.append(("daniel-draft-rs-check", V.RS_CHECK.replace("__RS_TEST__", repr(rb64))))
    if a.kv4_host:
        hb64 = base64.b64encode((HERE / "qsakv4h" / "test_hicache_nvfp4.py").read_bytes()).decode()
        cells.append(("daniel-draft-kv4h-check", KV4_CHECK.replace("__TEST__", repr(hb64))
                      .replace("test_qsa_nvfp4_daniel.py", "test_hicache_nvfp4.py")
                      .replace("kv4_test", "kv4h_test").replace("'--skip-speed'", "")))
    if a.ba_k0:
        tb64 = base64.b64encode((HERE / "barouting" / "test_ba.py").read_bytes()).decode()
        cells.append(("daniel-draft-ba-check", BA_CHECK.replace("__TEST__", repr(tb64))))
    if a.qsa_check:
        cells.append(("daniel-draft-qsa-check", QSA["QSA_CHECK"].replace("__N__", str(a.qsa_check))
                      .replace("__NEW__", str(a.qsa_check_new))))
    if a.routing:
        cells.append(("daniel-draft-routing", ROUTING.replace("__N__", str(a.routing))
                      .replace("__NEW__", str(a.routing_new))))
    cells.append(("daniel-draft-metrics", METRICS))
    if a.profile_at:
        marks = [int(x) for x in a.profile_at.split(",") if x.strip()]
        cells.append(("daniel-draft-profile", PROFILE.replace("__MARKS__", repr(marks))
                      .replace("__STEPS__", str(a.profile_steps)).replace("__MINRUN__", str(max(1, S - 1)))))
    if a.pre_only:  # no server: no check, metrics or profile cells
        cells = []
    for k, (cid, code) in enumerate(cells):
        compile(code, cid, "exec")
        nb["cells"].insert(li + 1 + k, {"cell_type": "code", "execution_count": None, "id": cid, "metadata": {},
                                        "outputs": [], "source": code})
    data = (json.dumps(nb, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    (a.out / "notebook.ipynb").write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    obj = f"{H.BUCKET}/{sha[:12]}/notebook.ipynb"
    (a.out / "BUILD.json").write_text(json.dumps({"bench": bench, "minutes": a.minutes, "kl": a.kl, "profile_at": a.profile_at,
                                                  "profile_steps": a.profile_steps, "routing": a.routing,
                                                  "routing_new": a.routing_new, "qsa_ring": a.qsa_ring,
                                                  "spec_steps": a.spec_steps, "qsa_check": a.qsa_check,
                                                  "ba_k0": a.ba_k0, "kv4": a.kv4, "kv4_host": a.kv4_host, "kv_hadamard": a.kv_hadamard, "rs": a.rs, "window": window,
                                                  "launcher_cell": li, "cells": [c for c, _ in cells],
                                                  **({"patch_sets": [str(d) for d in a.patch_set]} if a.patch_set else {}),
                                                  **bench_note,
                                                  **({"pre_scripts": [p.name for p in a.pre_script],
                                                      "pre_files": [p.name for p in a.pre_file],
                                                      "pre_only": a.pre_only} if a.pre_script else {}),
                                                  "notebook_sha256": sha, "gcs_object": obj}, indent=1))
    subprocess.run(H.GCLOUD + ["storage", "cp", "-q", str(a.out / "notebook.ipynb"), obj], check=True)
    print(obj)


if __name__ == "__main__":
    main()

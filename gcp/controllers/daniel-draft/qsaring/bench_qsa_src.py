QSA_FILES = ("sglang/srt/mem_cache/qsa_kv_pool.py", "sglang/srt/layers/attention/qsa/metadata.py",
             "sglang/srt/layers/attention/qsa/graph_metadata.py", "sglang/srt/layers/attention/qsa/qsa_indexer.py",
             "sglang/srt/layers/attention/qwen_sparse_attn_backend.py")

QSA_PORT = r'''
# --- port: QSA ring widening (daniel-draft qsaring/, 3-Oct-2026; Son: "go lift the 4-token cap") ---
# His fork's per-request QSA pending ring has `compress_ratio` (4) slots and refuses target verifies wider than 4.
# Five patched files (sha-checked against his wheel) replace his in a /tmp copy of his wheelhouse; the ring gets
# SGLANG_QSA_RING_SIZE slots per request, which allows verifies of up to ring - 3 tokens and keeps a verify's own keys
# off the slots of the older members of the first group it completes.
import base64 as _qb64, hashlib as _qhl, zipfile as _qzf
from pathlib import Path as _QP
_QSA = __QSA_FILES__
_q_src = _QP(WHEELHOUSE_DIR)
_q_wheels = sorted((_q_src / 'wheels').glob('sglang-*.whl'))
assert len(_q_wheels) == 1, _q_wheels
_q_shadow = _QP('/tmp/arc3-wheelhouse-qsaring')
(_q_shadow / 'wheels').mkdir(parents=True, exist_ok=True)
for _p in _q_src.iterdir():
    if _p.name != 'wheels' and not (_q_shadow / _p.name).exists():
        (_q_shadow / _p.name).symlink_to(_p)
for _p in (_q_src / 'wheels').iterdir():
    if _p != _q_wheels[0] and not (_q_shadow / 'wheels' / _p.name).exists():
        (_q_shadow / 'wheels' / _p.name).symlink_to(_p)
_q_out = _q_shadow / 'wheels' / _q_wheels[0].name
_q_new = {n: _qb64.b64decode(b) for n, (sha, b) in _QSA.items()}
with _qzf.ZipFile(_q_wheels[0]) as _zin, _qzf.ZipFile(_q_out, 'w') as _zout:
    for _n, (_sha, _b) in _QSA.items():
        assert _qhl.sha256(_zin.read(_n)).hexdigest() == _sha, ('his wheel changed under qsaring', _n)
    _n_record = 0
    for _info in _zin.infolist():
        _data = _zin.read(_info.filename)
        if _info.filename in _q_new:
            _data = _q_new[_info.filename]
        elif _info.filename.endswith('.dist-info/RECORD'):
            _lines = _data.decode('utf-8').splitlines()
            for _n, _b in _q_new.items():
                _hits = [i for i, l in enumerate(_lines) if l.startswith(_n + ',')]
                assert len(_hits) == 1, (_n, _hits)
                _dig = _qb64.urlsafe_b64encode(_qhl.sha256(_b).digest()).rstrip(b'=').decode()
                _lines[_hits[0]] = f'{_n},sha256={_dig},{len(_b)}'
            _n_record += 1
            _data = ('\n'.join(_lines) + '\n').encode('utf-8')
        _zout.writestr(_info, _data)
    assert _n_record == 1
WHEELHOUSE_DIR = str(_q_shadow)
os.environ['SGLANG_QSA_RING_SIZE'] = '__RING__'
print('daniel-draft port qsaring: patched', len(_q_new), 'files into', _q_out, '| ring', os.environ['SGLANG_QSA_RING_SIZE'])
'''

QSA_CHECK = r'''# --- daniel-draft: QSA ring check (3-Oct-2026) --- cached vs fresh. For the __N__ shortest kl_set prompts: generate
# __NEW__ tokens greedy, all in flight together (spec decode: the generated region's QSA compressed keys come from
# verify forwards), then score a fixed probe (the item's recorded response, first 512 tokens) teacher-forced after
# prompt + generation (a) at once (radix hit reuses the generated region's KV + compressed keys) and (b) after
# /flush_cache (a fresh prefill rebuilds them). A corrupted ring widens the a-vs-b gap. Also per-request accept length.
# -> /kaggle/working/qsa_check.json. Never raises.
def _qsa_check():
    import json, time, urllib.request
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    from transformers import AutoTokenizer
    src = Path("/kaggle/input/datasets/cellens/daniel-bench/kl_set.json")
    if not src.exists():
        print("daniel-draft qsa check: no kl_set.json"); return
    items = json.loads(src.read_text())
    tok = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True)
    tmpl = Path(MODEL_DIR, "chat_template.jinja")
    if tmpl.is_file():
        tok.chat_template = tmpl.read_text()
    base = f"http://127.0.0.1:{SERVED_MODEL_PORT}"
    def post(path, body=None, timeout=3600):
        data = json.dumps(body).encode() if body is not None else b""
        req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
        raw = urllib.request.urlopen(req, timeout=timeout).read()
        try:
            return json.loads(raw)
        except Exception:
            return {"text": raw.decode("utf-8", "replace")[:200]}
    cases = []
    for it in items:
        kw = dict(tools=it.get("tools"), tokenize=False, preserve_thinking=True)
        pt = tok.apply_chat_template(it["messages"], add_generation_prompt=True, **kw)
        ft = tok.apply_chat_template(it["messages"] + [it["response"]], add_generation_prompt=False, **kw)
        p = list(tok(pt, add_special_tokens=False)["input_ids"])
        full = list(tok(ft, add_special_tokens=False)["input_ids"])
        L = 0
        while L < min(len(p), len(full)) and p[L] == full[L]:
            L += 1
        if L < len(p) - 2 or len(full) <= L:
            continue
        cases.append({"id": it["id"], "prompt": full[:L], "probe": full[L:L + 512]})
    cases = sorted(cases, key=lambda c: len(c["prompt"]))[:__N__]
    t0 = time.time()
    def gen(c):
        r = post("/generate", {"input_ids": c["prompt"], "sampling_params": {"temperature": 0, "max_new_tokens": __NEW__}})
        m = r.get("meta_info", {}) or {}
        c["gen"] = r.get("output_ids") or []
        c["gen_meta"] = {k: m.get(k) for k in ("completion_tokens", "spec_verify_ct", "spec_accept_length",
                                                "spec_accept_token_num", "e2e_latency", "cached_tokens")}
        return len(c["gen"])
    with ThreadPoolExecutor(len(cases)) as ex:
        lens = list(ex.map(gen, cases))
    t_gen = time.time() - t0
    def score(c):
        ids = c["prompt"] + c["gen"] + c["probe"]
        body = {"input_ids": ids, "sampling_params": {"temperature": 0, "max_new_tokens": 1}, "return_logprob": True,
                "logprob_start_len": len(c["prompt"]) + len(c["gen"]) - 1, "top_logprobs_num": 1}
        m = post("/generate", body)["meta_info"]
        lps = [x[0] for x in m["input_token_logprobs"]][1:]
        tops = [x[0][1] if x else None for x in m["input_top_logprobs"]][1:]
        return {"cached": m.get("cached_tokens"), "lp": lps, "top1": tops}
    for c in cases:
        c["a"] = score(c)
    flushed = post("/flush_cache")
    for c in cases:
        c["b"] = score(c)
    out = []
    for c in cases:
        a, b = c["a"], c["b"]
        n = min(len(a["lp"]), len(b["lp"]))
        d = [abs(x - y) for x, y in zip(a["lp"][:n], b["lp"][:n])]
        agree = sum(1 for x, y in zip(a["top1"][:n], b["top1"][:n]) if x == y)
        gm = c["gen_meta"]
        acc = (gm.get("completion_tokens") or 0) / gm["spec_verify_ct"] if gm.get("spec_verify_ct") else None
        out.append({"id": c["id"], "prompt_len": len(c["prompt"]), "gen_len": len(c["gen"]), "probe_len": n,
                    "cached_a": a["cached"], "cached_b": b["cached"], "mean_abs_dlp": sum(d) / max(n, 1),
                    "max_abs_dlp": max(d) if d else None, "top1_agree": agree / max(n, 1), "accept_len": acc,
                    "gen_meta": gm})
    summ = {"ring": os.environ.get("SGLANG_QSA_RING_SIZE", "orig"), "spec_steps": os.environ.get("ARC3_SRV_SPEC_STEPS", "3"),
            "gen_seconds": round(t_gen, 1), "flush": flushed, "n": len(out),
            "mean_abs_dlp": sum(o["mean_abs_dlp"] for o in out) / max(len(out), 1),
            "top1_agree": sum(o["top1_agree"] for o in out) / max(len(out), 1),
            "accept_len": [o["accept_len"] for o in out], "items": out}
    Path("/kaggle/working/qsa_check.json").write_text(json.dumps(summ))
    print("daniel-draft qsa check:", {k: summ[k] for k in ("ring", "spec_steps", "gen_seconds", "n", "mean_abs_dlp",
                                                           "top1_agree")}, "| cached a/b",
          [(o["cached_a"], o["cached_b"]) for o in out][:4], "| accept", summ["accept_len"], flush=True)
try:
    _qsa_check()
except Exception as _e:
    print("daniel-draft qsa check could not run:", repr(_e)[:800], flush=True)
'''

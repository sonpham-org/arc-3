"""Insert a greedy-decode losslessness check into a built bench notebook (3-Oct-2026, daniel-draft kernels).

make_bench_notebook.py's --kl probe is teacher-forced PREFILL (large M), so it never runs the decode-width GEMM path a
kernel patch changes. This adds one cell right after the launcher (server up, before any game): the N shortest kl_set
prompts generate NEW tokens greedy, all in flight together (verify batches of N x 4 rows), with decode-time logprobs of
every output token; the same pass runs twice (pass 2 = the server's own nondeterminism floor: Marlin's atomic adds).
-> /kaggle/working/greedy_check.json. Never raises. Re-uploads the notebook under its new sha; prints the GCS path.
  python add_greedy_cell.py NB_DIR [--n 13] [--new 384]
(Does not modify make_bench_notebook.py; post-processes its output dir: notebook.ipynb + BUILD.json.)
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

GCLOUD = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
BUCKET = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/notebooks"

CELL = r'''# --- daniel-draft kernels: greedy decode check (3-Oct-2026; add_greedy_cell.py) --- before any game: the __N__
# shortest kl_set prompts generate __NEW__ tokens greedy, all in flight together (decode verify batches of __N__ x 4
# rows), with decode-time logprobs; two passes (pass 2 = this server's own nondeterminism floor).
# -> /kaggle/working/greedy_check.json. Never raises.
def _greedy_check():
    import json, time, urllib.request
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    from transformers import AutoTokenizer
    src = Path("/kaggle/input/datasets/cellens/daniel-bench/kl_set.json")
    if not src.exists():
        print("daniel-draft greedy check: no kl_set.json"); return
    items = json.loads(src.read_text())
    tok = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True)
    tmpl = Path(MODEL_DIR, "chat_template.jinja")
    if tmpl.is_file():
        tok.chat_template = tmpl.read_text()
    prompts = []
    for it in items:
        pt = tok.apply_chat_template(it["messages"], add_generation_prompt=True, tools=it.get("tools"),
                                     tokenize=False, preserve_thinking=True)
        prompts.append((it["id"], list(tok(pt, add_special_tokens=False)["input_ids"])))
    prompts = sorted(prompts, key=lambda p: len(p[1]))[:__N__]
    url = f"http://127.0.0.1:{SERVED_MODEL_PORT}/generate"
    def gen(p, with_lp):
        body = {"input_ids": p[1], "sampling_params": {"temperature": 0, "max_new_tokens": __NEW__}}
        if with_lp:
            body["return_logprob"] = True
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        r = json.loads(urllib.request.urlopen(req, timeout=3600).read())
        m = r.get("meta_info", {}) or {}
        lps = [x[0] for x in (m.get("output_token_logprobs") or [])]
        return {"id": p[0], "prompt_len": len(p[1]), "ids": r.get("output_ids") or [], "lp": lps,
                "meta": {k: m.get(k) for k in ("completion_tokens", "spec_verify_ct", "cached_tokens", "e2e_latency")}}
    out = {"n": len(prompts), "new": __NEW__, "passes": []}
    with_lp = True
    for k in range(2):
        t0 = time.time()
        try:
            with ThreadPoolExecutor(len(prompts)) as ex:
                res = list(ex.map(lambda p: gen(p, with_lp), prompts))
        except Exception as e:
            if not with_lp:
                raise
            out["logprob_error"] = repr(e)[:300]; with_lp = False
            with ThreadPoolExecutor(len(prompts)) as ex:
                res = list(ex.map(lambda p: gen(p, with_lp), prompts))
        out["passes"].append({"seconds": round(time.time() - t0, 1), "items": res})
    Path("/kaggle/working/greedy_check.json").write_text(json.dumps(out))
    a, b = out["passes"][0]["items"], out["passes"][1]["items"]
    same = sum(1 for x, y in zip(a, b) if x["ids"] == y["ids"])
    print("daniel-draft greedy check:", len(a), "prompts x", __NEW__, "tokens; pass1 == pass2 for", same,
          "| seconds", [p["seconds"] for p in out["passes"]], "| logprobs", with_lp, flush=True)
try:
    _greedy_check()
except Exception as _e:
    print("daniel-draft greedy check could not run:", repr(_e)[:800], flush=True)
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("nb_dir", type=Path)
    ap.add_argument("--n", type=int, default=13)
    ap.add_argument("--new", type=int, default=384)
    a = ap.parse_args()
    nbp, bp = a.nb_dir / "notebook.ipynb", a.nb_dir / "BUILD.json"
    nb = json.loads(nbp.read_text(encoding="utf-8"))
    build = json.loads(bp.read_text(encoding="utf-8"))
    li = build["launcher_cell"]
    assert not any(c.get("id") == "kernels-greedy-check" for c in nb["cells"]), "already inserted"
    code = CELL.replace("__N__", str(a.n)).replace("__NEW__", str(a.new))
    compile(code, "greedy", "exec")
    nb["cells"].insert(li + 1, {"cell_type": "code", "execution_count": None, "id": "kernels-greedy-check",
                                "metadata": {}, "outputs": [], "source": code})
    data = (json.dumps(nb, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    nbp.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    obj = f"{BUCKET}/{sha[:12]}/notebook.ipynb"
    build.update(cells=["kernels-greedy-check"] + build.get("cells", []), greedy_check={"n": a.n, "new": a.new},
                 notebook_sha256=sha, gcs_object=obj)
    bp.write_text(json.dumps(build, indent=1))
    subprocess.run(GCLOUD + ["storage", "cp", "-q", str(nbp), obj], check=True)
    print(obj)


if __name__ == "__main__":
    main()

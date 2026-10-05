"""Daniel-notebook variants stacked on another build's port cell (2-Oct-2026, daniel-draft).

  python make_variant_notebook.py --base-early <early.py> [--frspec-map-env] [--oa N --hicache-gb G] [--rs] --out DIR

--base-early   a port cell to start from (e.g. the Reverse-flow thread's variants/subbuild/ctl/early.py: border off +
               ARC hot map + tuned drafter), used verbatim
--oa / --hicache-gb   over-admission + his fork's host tier (make_hicache_notebook.py's launcher edit and pre-game
               reload check); host reloads checked exact on 6 GCP runs
--rs           rejection sampling over the 64k hot draft vocab = our patch 0008 v2 (kv4/0008-rs-hot-vocab.patch) on his
               fork: his eagle_worker_v2 refuses rejection sampling with a hot vocab (the same FIXME guard ours had) and
               his draft q gets the temperature only. The patch applies to his three files cleanly (12 hunks); the
               patched files (rs/patched/, built from his wheel's exact bytes) replace his in a /tmp copy of his
               wheelhouse (RECORD updated), and his launcher gets --speculative-use-rejection-sampling. A check cell
               after the launcher runs kv4/test_rs_hot.py in his venv (chain kernel 400k rows: committed tokens follow
               the target p with q on a hot subset; top-k/top-p truncation eager and in a CUDA graph) ->
               /kaggle/working/rs_test.json. Offline (tuned drafter, his sampling, fp8 draft KV, 4 held-out games):
               2.932 -> 3.058 tokens per verify step (+4.3%).
Uploads the notebook to gs://.../daniel-base/notebooks/<sha12>/notebook.ipynb and prints the object.
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
import make_hicache_notebook as H  # noqa: E402  (BUILDER, SOURCE, LAUNCH_ANCHOR, LAUNCH_ADD, CHECK, PORT_ADD, GCLOUD, BUCKET)

RS_FILES = ("sglang/srt/speculative/eagle_worker_v2.py", "sglang/srt/speculative/spec_utils.py",
            "sglang/srt/speculative/eagle_draft_cuda_graph_runner.py")
RS_TEST = Path(r"D:\codex-work\arc3-sglang-parking\gcp\controllers\sglang-scored\kv4\test_rs_hot.py")

RS_PORT = r'''
# --- port: rejection sampling over the 64k hot draft vocab (patch 0008 v2; Slice and dice, 2-Oct-2026) ---
# His fork refuses --speculative-use-rejection-sampling with a hot (FR-Spec) draft vocab and gives the draft q the
# temperature only. 0008 v2 scatters q into the full vocab (q = 0 off the hot ids: lossless, the residual keeps every
# token reachable) and truncates q with each request's top-k / top-p like the verify's p. Three patched files replace
# his in a /tmp copy of his wheel (originals checked by sha256); his launcher adds the flag (ARC3_SPEC_RS=1).
import base64 as _rb64, hashlib as _rhl, zipfile as _rzf
from pathlib import Path as _RP
_RS = __RS_FILES__
_rs_src = _RP(WHEELHOUSE_DIR)
_rs_wheels = sorted((_rs_src / 'wheels').glob('sglang-*.whl'))
assert len(_rs_wheels) == 1, _rs_wheels
_rs_shadow = _RP('/tmp/arc3-wheelhouse-rs')
(_rs_shadow / 'wheels').mkdir(parents=True, exist_ok=True)
for _p in _rs_src.iterdir():
    if _p.name != 'wheels' and not (_rs_shadow / _p.name).exists():
        (_rs_shadow / _p.name).symlink_to(_p)
for _p in (_rs_src / 'wheels').iterdir():
    if _p != _rs_wheels[0] and not (_rs_shadow / 'wheels' / _p.name).exists():
        (_rs_shadow / 'wheels' / _p.name).symlink_to(_p)
_rs_out = _rs_shadow / 'wheels' / _rs_wheels[0].name
_rs_new = {n: _rb64.b64decode(b) for n, (sha, b) in _RS.items()}
with _rzf.ZipFile(_rs_wheels[0]) as _zin, _rzf.ZipFile(_rs_out, 'w') as _zout:
    for _n, (_sha, _b) in _RS.items():
        assert _rhl.sha256(_zin.read(_n)).hexdigest() == _sha, ('his wheel changed under 0008', _n)
    _n_record = 0
    for _info in _zin.infolist():
        _data = _zin.read(_info.filename)
        if _info.filename in _rs_new:
            _data = _rs_new[_info.filename]
        elif _info.filename.endswith('.dist-info/RECORD'):
            _lines = _data.decode('utf-8').splitlines()
            for _n, _b in _rs_new.items():
                _hits = [i for i, l in enumerate(_lines) if l.startswith(_n + ',')]
                assert len(_hits) == 1, (_n, _hits)
                _dig = _rb64.urlsafe_b64encode(_rhl.sha256(_b).digest()).rstrip(b'=').decode()
                _lines[_hits[0]] = f'{_n},sha256={_dig},{len(_b)}'
            _n_record += 1
            _data = ('\n'.join(_lines) + '\n').encode('utf-8')
        _zout.writestr(_info, _data)
    assert _n_record == 1
WHEELHOUSE_DIR = str(_rs_shadow)
os.environ['ARC3_SPEC_RS'] = '1'
print('daniel-draft port rs: patched', len(_rs_new), 'files into', _rs_out, '| WHEELHOUSE_DIR ->', WHEELHOUSE_DIR)
'''

RS_LAUNCH_ADD = '''
if os.environ.get("ARC3_SPEC_RS") == "1":  # daniel-draft: rejection sampling over the hot draft vocab (patch 0008 v2)
    args += ["--speculative-use-rejection-sampling"]
'''

RS_CHECK = r'''# --- daniel-draft: rejection-sampling exactness check (patch 0008 v2; 2-Oct-2026) ---
# Runs kv4/test_rs_hot.py in his SGLang venv (the patched install): the chain kernel on 400k rows with the draft q on a
# hot subset must commit tokens distributed as the target p; truncate_draft_probs eager and in a CUDA graph.
# -> /kaggle/working/rs_test.json (+ .log). Never raises.
import os, subprocess
from pathlib import Path
if os.environ.get("ARC3_SPEC_RS") == "1":
    try:
        _t = Path("/kaggle/working/test_rs_hot.py")
        _t.write_bytes(__import__("base64").b64decode(__RS_TEST__))
        _env = dict(globals().get("env") or os.environ, RS_TEST_MAP=os.environ.get("ARC3_FRSPEC_MAP", ""))  # his server's env
        _r = subprocess.run([PYTHON, str(_t)], capture_output=True, text=True, timeout=1200, env=_env)
        Path("/kaggle/working/rs_test.log").write_text(_r.stdout + "\n" + _r.stderr[-4000:])
        _last = [l for l in _r.stdout.splitlines() if l.startswith("{")]
        Path("/kaggle/working/rs_test.json").write_text("\n".join(_last) + "\n")
        print("daniel-draft rs_test rc", _r.returncode, "|", _last[-1] if _last else _r.stderr[-800:], flush=True)
    except Exception as _e:
        print("daniel-draft rs_test could not run:", repr(_e)[:800], flush=True)
'''


def src(c):
    return "".join(c["source"]) if isinstance(c["source"], list) else c["source"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-early", type=Path, required=True)
    ap.add_argument("--frspec-map-env", action="store_true")
    ap.add_argument("--oa", type=int)
    ap.add_argument("--hicache-gb", type=int)
    ap.add_argument("--rs", action="store_true")
    ap.add_argument("--patch-set", action="append", default=[], type=Path,
                    help="extra patch set DIR (orig/ + patched/ trees, paths inside the wheel), merged into the --rs "
                         "shadow wheel (4-Oct-2026: 8-bit kernel upgrade, kernels/kfast + kernels/kfuse8); repeatable")
    ap.add_argument("--env", action="append", default=[],
                    help="KEY=VALUE set in the port cell before the server starts (e.g. SGLANG_BA_K0=4); repeatable")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    assert (a.oa is None) == (a.hicache_gb is None), "--oa and --hicache-gb go together"
    assert a.rs or not a.patch_set, "--patch-set rides the --rs shadow wheel: use it with --rs"
    a.out.mkdir(parents=True, exist_ok=True)
    port = a.base_early.read_text(encoding="utf-8").rstrip("\n") + "\n"
    if a.oa is not None:
        port += H.PORT_ADD.replace("__OA__", str(a.oa)).replace("__GB__", str(a.hicache_gb))
    if a.rs:
        files = {}
        for n in RS_FILES:
            orig = (HERE / "rs" / "orig" / n).read_bytes()
            new = (HERE / "rs" / "patched" / n).read_bytes()
            compile(new, n, "exec")
            files[n] = (hashlib.sha256(orig).hexdigest(), base64.b64encode(new).decode())
        for d in a.patch_set:  # same shadow wheel; the port cell sha-checks each original against his wheel
            d = d.resolve()
            for p in sorted((d / "patched").rglob("*.py")):
                n = p.relative_to(d / "patched").as_posix()
                orig_sha = hashlib.sha256((d / "orig" / n).read_bytes()).hexdigest()
                if n in files:  # a later set may supersede an earlier one (e.g. kdsamp = rs's spec_utils.py + more),
                    assert files[n][0] == orig_sha, ("two patch sets change", n)  # only from the same original file
                    print(f"note: {d.name} supersedes the earlier copy of {n}")
                new = p.read_bytes()
                compile(new, n, "exec")
                files[n] = (orig_sha, base64.b64encode(new).decode())
        port += RS_PORT.replace("__RS_FILES__", repr(files))
    for kv in a.env:  # e.g. SGLANG_BA_K0=4 for the barouting patch set (read at import by the server)
        k, _, v = kv.partition("=")
        assert k and v, kv
        port += f"\nos.environ[{k!r}] = {v!r}  # daniel-draft make_variant_notebook.py --env\n"
    (a.out / "port_cell.py").write_text(port, encoding="utf-8", newline="\n")
    base = a.out / "base"
    cmd = [sys.executable, str(H.BUILDER), "--source", str(H.SOURCE), "--early", str(a.out / "port_cell.py"),
           "--compile-threads", "1", "--out", str(base)] + (["--frspec-map-env"] if a.frspec_map_env else [])
    subprocess.run(cmd, check=True, capture_output=True)
    nb = json.loads((base / "notebook.ipynb").read_text(encoding="utf-8"))
    hits = [i for i, c in enumerate(nb["cells"]) if c["cell_type"] == "code" and H.LAUNCH_ANCHOR in src(c)]
    assert len(hits) == 1, hits
    li = hits[0]
    s = src(nb["cells"][li])
    add = (H.LAUNCH_ADD if a.oa is not None else "") + (RS_LAUNCH_ADD if a.rs else "")
    nb["cells"][li]["source"] = s.replace(H.LAUNCH_ANCHOR, add + H.LAUNCH_ANCHOR)
    checks = []
    if a.oa is not None:
        checks.append(("daniel-draft-hicache-check", H.CHECK))
    if a.rs:
        test_b64 = base64.b64encode(RS_TEST.read_text(encoding="utf-8").replace(
            'load_token_map("/sgl/hot_tokens_64k.pt")',
            'load_token_map(__import__("os").environ.get("RS_TEST_MAP") or "/sgl/hot_tokens_64k.pt")').encode()).decode()
        checks.append(("daniel-draft-rs-check", RS_CHECK.replace("__RS_TEST__", repr(test_b64))))
    for k, (cid, code) in enumerate(checks):
        compile(code, cid, "exec")
        nb["cells"].insert(li + 1 + k, {"cell_type": "code", "execution_count": None, "id": cid, "metadata": {},
                                        "outputs": [], "source": code})
    compile(src(nb["cells"][li]), "launcher", "exec") if not src(nb["cells"][li]).lstrip().startswith("%") else None
    data = (json.dumps(nb, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    (a.out / "notebook.ipynb").write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    obj = f"{H.BUCKET}/{sha[:12]}/notebook.ipynb"
    (a.out / "BUILD.json").write_text(json.dumps({"base_early": str(a.base_early), "frspec_map_env": a.frspec_map_env,
                                                  "oa": a.oa, "hicache_gb": a.hicache_gb, "rs": a.rs, "launcher_cell": li,
                                                  "check_cells": [c for c, _ in checks],
                                                  **({"patch_sets": [str(d) for d in a.patch_set]} if a.patch_set else {}),
                                                  **({"env": a.env} if a.env else {}),
                                                  "notebook_sha256": sha,
                                                  "gcs_object": obj}, indent=1))
    subprocess.run(H.GCLOUD + ["storage", "cp", "-q", str(a.out / "notebook.ipynb"), obj], check=True)
    print(obj)


if __name__ == "__main__":
    main()

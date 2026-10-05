"""ZipServ speed test driver (4-Oct-2026, Kernel optimizations thread; Son: "do the ZipServ speed test too").

make_bench_notebook.py --pre-script (with --pre-file zipserv_src.tgz --pre-file zs_bench.cu, --pre-only): his venv, free
GPU, no network. Steps:
  1. find nvcc (sm_120-capable), CUDA / cuBLAS headers and libs in the container or his venv; report them
  2. build zs_bench (ZipServ csrc/L_API.cu + our harness) for sm_120
  3. write REAL Flash-Next weights (the decode-step shapes of kernels/bench/bench_dense.py) as raw BF16 files
  4. run zs_bench per shape (one process each): ZipServ (split-K sweep) vs cuBLAS, CUDA graphs over cold weight copies,
     at 40 / 48 / 10 tokens; outputs compared with cuBLAS
Stdout lines starting with "{" are kept by the pre-script cell (-> pre_zs_run.json).
"""
import glob
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import time

import numpy as np

T0 = time.time()
W = "/kaggle/working"
ZS = os.path.join(W, "zs")
MODEL_GLOB = "/kaggle/input/models/dfranzen/intel-qwen3.8-flash-next-w4a16-autoround/**/model.safetensors.index.json"
TOKENS = os.environ.get("ZS_TOKENS", "40,48,10")
BUDGET_S = float(os.environ.get("ZS_BUDGET_S", 2400))


def emit(**kw):
    kw["t"] = round(time.time() - T0, 1)
    print(json.dumps(kw), flush=True)


# ------------------------------------------------------------------ 1. toolchain
def find_toolchain():
    roots = ["/usr/local/cuda", *sorted(glob.glob("/usr/local/cuda-*")), sys.prefix, "/opt/conda", "/usr"]
    cands = []
    w = shutil.which("nvcc")
    if w:
        cands.append(w)
    for r in roots:
        cands += glob.glob(os.path.join(r, "bin", "nvcc")) + glob.glob(os.path.join(r, "**", "bin", "nvcc"), recursive=True)
    seen, nvcc, info = set(), None, []
    for c in cands:
        c = os.path.realpath(c)
        if c in seen or not os.access(c, os.X_OK):
            continue
        seen.add(c)
        try:
            v = subprocess.run([c, "--version"], capture_output=True, text=True, timeout=60).stdout
            a = subprocess.run([c, "--list-gpu-arch"], capture_output=True, text=True, timeout=60).stdout
        except Exception as e:
            info.append((c, repr(e)[:100]))
            continue
        ver = re.findall(r"release ([\d.]+)", v)
        ok = "compute_120" in a
        info.append((c, ver[0] if ver else "?", ok))
        if ok and nvcc is None:
            nvcc = c
    emit(stage="nvcc", chosen=nvcc, candidates=info)

    def find(fname, extra=()):
        hits = []
        for r in roots + list(extra):
            hits += glob.glob(os.path.join(r, "**", fname), recursive=True)
        return sorted(set(os.path.dirname(os.path.realpath(h)) for h in hits))

    nv_root = os.path.dirname(os.path.dirname(nvcc)) if nvcc else None
    extra = [nv_root] if nv_root else []
    inc = []
    for h in ("cuda_runtime.h", "cuda_bf16.h", "cublas_v2.h"):
        d = find(h, extra)
        emit(stage="header", file=h, dirs=d[:6])
        if d:
            pref = [x for x in d if nv_root and x.startswith(nv_root)] or d
            inc.append(pref[0])
    libs = find("libcublas.so*", extra)
    libdir = None
    libfile = None
    for d in libs:
        so = sorted(glob.glob(os.path.join(d, "libcublas.so*")))
        if so:
            libdir, libfile = d, (os.path.join(d, "libcublas.so") if os.path.exists(os.path.join(d, "libcublas.so")) else so[-1])
            break
    emit(stage="cublas_lib", dirs=libs[:6], chosen=libfile)
    return nvcc, sorted(set(inc)), libdir, libfile


# ------------------------------------------------------------------ 2. build
def build(nvcc, inc, libdir, libfile):
    os.makedirs(ZS, exist_ok=True)
    with tarfile.open(os.path.join(W, "zipserv_src.tgz")) as t:
        t.extractall(ZS)
    src = os.path.join(ZS, "ZipServ_ASPLOS26")
    cmd = [nvcc, "-O3", "-std=c++17", "-gencode", "arch=compute_120,code=sm_120", "--use_fast_math",
           "-maxrregcount=255", "-I", os.path.join(src, "csrc"), "-I", os.path.join(src, "build"),
           "-I", os.path.join(src, "kernel_benchmark")]
    for d in inc:
        cmd += ["-I", d]
    cmd += [os.path.join(W, "zs_bench.cu"), os.path.join(src, "csrc", "L_API.cu"), "-o", os.path.join(ZS, "zs_bench")]
    cmd += ["-L", libdir, "-lcublas"] if libfile and libfile.endswith("libcublas.so") else [libfile]
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
    emit(stage="build", rc=r.returncode, seconds=round(time.time() - t, 1), cmd=" ".join(cmd)[-600:],
         stderr_tail=r.stderr[-2500:] if r.returncode else "")
    return r.returncode == 0


# ------------------------------------------------------------------ 3. real weights
def header(path):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        return 8 + n, json.loads(f.read(n))


def tensor(d, wm, name):
    path = os.path.join(d, wm[name])
    base, h = header(path)
    m = h[name]
    assert m["dtype"] == "BF16", (name, m["dtype"])
    o0, o1 = m["data_offsets"]
    return np.memmap(path, dtype=np.uint16, mode="r", offset=base + o0, shape=tuple(m["shape"]))


def write_shapes():
    idx = sorted(glob.glob(MODEL_GLOB, recursive=True))[0]
    d = os.path.dirname(idx)
    wm = json.load(open(idx))["weight_map"]
    L = "model.language_model.layers."
    attn = min(int(n.split(".")[3]) for n in wm if n.startswith(L) and ".self_attn.q_proj." in n)
    lin = min(int(n.split(".")[3]) for n in wm if n.startswith(L) and ".linear_attn.out_proj." in n)
    t = lambda s: tensor(d, wm, s)  # noqa: E731
    la = f"{L}{lin}.linear_attn."
    sa = f"{L}{attn}.self_attn."
    mlp = f"{L}{lin}.mlp."
    hc = f"{L}{lin}.attn_hyper_connection."

    def pad64(a):
        r = (-a.shape[0]) % 64
        return a if r == 0 else np.concatenate([a, a[:r]])   # pad rows with real rows (keeps the exponent mix)

    shapes = [  # name, array [out, in], calls per target verify step (bench_dense.py SHAPES)
        ("gdn_in_proj_qkvzba", pad64(np.concatenate([t(la + "in_proj_qkv.weight"), t(la + "in_proj_z.weight"),
                                                     t(la + "in_proj_b.weight"), t(la + "in_proj_a.weight")])), 36),
        ("gdn_out_proj", t(la + "out_proj.weight"), 36),
        ("qsa_qkv_gate", np.concatenate([t(sa + "q_proj.weight"), t(sa + "k_proj.weight"), t(sa + "v_proj.weight")]), 12),
        ("qsa_o_proj", t(sa + "o_proj.weight"), 12),
        ("shared_gate_up", np.concatenate([t(mlp + "shared_expert.gate_proj.weight"),
                                           t(mlp + "shared_expert.up_proj.weight")]), 48),
        ("shared_down", t(mlp + "shared_expert.down_proj.weight"), 48),
        ("router_gate", t(mlp + "gate.weight"), 48),
        ("hc_mix_down", t(hc + "input_mix_weight_down.weight"), 96),
        ("hc_mix_up", t(hc + "input_mix_weight_up.weight"), 96),
        ("draft_lm_head_hot64k", t("lm_head.weight")[:65536], 3),
        ("lm_head", t("lm_head.weight"), 1),
    ]
    out = []
    for name, a, calls in shapes:
        p = os.path.join(ZS, f"w_{name}.bin")
        np.ascontiguousarray(a).tofile(p)
        out.append((name, a.shape[0], a.shape[1], calls, p))
        emit(stage="weight", name=name, shape=list(a.shape), MB=round(a.size * 2 / 1e6, 1), calls=calls,
             layer=(attn if name.startswith("qsa") else lin))
    return out


def splits_for(M):
    if M >= 65536:
        return "1,2"
    if M >= 10240:
        return "1,2,3,4"
    return "1,2,3,4,5,6,8,10,12,16"


# ------------------------------------------------------------------ main
def main():
    nvcc, inc, libdir, libfile = find_toolchain()
    if not nvcc or not libfile:
        emit(stage="fatal", why="no sm_120 nvcc or no libcublas")
        return
    if not build(nvcc, inc, libdir, libfile):
        return
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = ":".join(x for x in (libdir, env.get("LD_LIBRARY_PATH", "")) if x)
    for name, M, K, calls, p in write_shapes():
        if time.time() - T0 > BUDGET_S:
            emit(stage="skip", name=name, why="budget")
            continue
        try:
            r = subprocess.run([os.path.join(ZS, "zs_bench"), p, str(M), str(K), TOKENS, splits_for(M), name],
                               capture_output=True, text=True, timeout=900, env=env)
            for ln in r.stdout.splitlines():
                if ln.startswith("{"):
                    d = json.loads(ln)
                    d["calls"] = calls
                    print(json.dumps(d), flush=True)
            if r.returncode:
                emit(stage="bench_rc", name=name, rc=r.returncode, stderr_tail=r.stderr[-1500:])
        except subprocess.TimeoutExpired:
            emit(stage="bench_timeout", name=name)
        try:
            os.remove(p)
        except OSError:
            pass
    emit(stage="done")


if __name__ == "__main__":
    main()

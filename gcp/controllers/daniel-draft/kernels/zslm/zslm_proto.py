"""zslm prototype: ZipServ for the target lm_head through ctypes (5-Oct-2026, Kernel optimizations thread).
Pre-server script, free GPU, his venv. Needs --pre-file zslm.cu --pre-file ../zipserv/zipserv_src.tgz
--pre-file ../zipserv/zs_run.py (toolchain discovery). Steps, one JSON line each:
1. build libzslm.so (ZipServ csrc/L_API.cu + zslm.cu) for sm_120; seconds
2. load the served lm_head weight (or embed_tokens when tied), compress on the host: seconds, bytes, ratio
3. bitwise: zslm vs torch.matmul(hidden, W.T) (logits_processor's call) at 1..64 rows, real-scale random hidden
4. CUDA graph capture of the zslm call, replay with fresh hidden == eager torch.matmul
5. timing in CUDA graphs: torch.matmul vs zslm at 10 / 40 / 48 / 64 rows (the 1.27 GB weight is > L2: cold)
Last line {"verdict": ...}.
"""
import ctypes
import glob
import json
import os
import struct
import subprocess
import sys
import tarfile
import time

import numpy as np
import torch

T0 = time.time()
W = "/kaggle/working"
ZS = os.path.join(W, "zs")
MODEL_GLOB = "/kaggle/input/models/dfranzen/intel-qwen3.8-flash-next-w4a16-autoround/**/model.safetensors.index.json"
DEV = torch.device("cuda")
FAIL = []


def emit(**kw):
    kw["t"] = round(time.time() - T0, 1)
    print(json.dumps(kw), flush=True)


def build():
    sys.path.insert(0, W)
    import zs_run
    nvcc, inc, libdir, libfile = zs_run.find_toolchain()
    os.makedirs(ZS, exist_ok=True)
    with tarfile.open(os.path.join(W, "zipserv_src.tgz")) as t:
        t.extractall(ZS)
    src = os.path.join(ZS, "ZipServ_ASPLOS26")
    so = os.path.join(ZS, "libzslm.so")
    cmd = [nvcc, "-O3", "-std=c++17", "-shared", "-Xcompiler", "-fPIC", "-gencode", "arch=compute_120,code=sm_120",
           "--use_fast_math", "-maxrregcount=255", "-I", os.path.join(src, "csrc"), "-I", os.path.join(src, "build"),
           "-I", os.path.join(src, "kernel_benchmark")]
    for d in inc:
        cmd += ["-I", d]
    cmd += [os.path.join(W, "zslm.cu"), os.path.join(src, "csrc", "L_API.cu"), "-o", so]
    if libfile:
        cmd += ["-L", libdir, "-lcublas"] if libfile.endswith("libcublas.so") else [libfile]
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
    emit(kind="build", rc=r.returncode, seconds=round(time.time() - t, 1), stderr_tail=r.stderr[-2000:] if r.returncode else "")
    if r.returncode:
        return None
    if libdir:
        try:
            ctypes.CDLL(os.path.join(libdir, os.path.basename(libfile)), mode=ctypes.RTLD_GLOBAL)
        except OSError:
            pass
    lib = ctypes.CDLL(so)
    lib.zslm_create.restype = ctypes.c_void_p
    lib.zslm_create.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_double)]
    lib.zslm_gemm.restype = ctypes.c_int
    lib.zslm_gemm.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    lib.zslm_destroy.argtypes = [ctypes.c_void_p]
    return lib


def lm_head_host():
    idx = sorted(glob.glob(MODEL_GLOB, recursive=True))[0]
    d = os.path.dirname(idx)
    wm = json.load(open(idx))["weight_map"]
    cfg = json.load(open(os.path.join(d, "config.json")))
    tc = cfg.get("text_config", cfg)
    tied = bool(cfg.get("tie_word_embeddings", tc.get("tie_word_embeddings", False)))
    names = [n for n in wm if n.endswith("lm_head.weight")] if not tied else []
    if not names:
        names = [n for n in wm if n.endswith("embed_tokens.weight")]
    name = sorted(names, key=len)[0]
    path = os.path.join(d, wm[name])
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        h = json.loads(f.read(n))
    m = h[name]
    o0, o1 = m["data_offsets"]
    a = np.fromfile(path, dtype=np.uint16, count=(o1 - o0) // 2, offset=8 + n + o0).reshape(m["shape"])
    emit(kind="weight", name=name, tied=tied, shape=list(a.shape), dtype=m["dtype"], all_names=names[:4])
    return np.ascontiguousarray(a)


def graph_us(fn, reps=20):
    s = torch.cuda.Stream()
    s.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(s):
        fn()
    torch.cuda.current_stream().wait_stream(s)
    torch.cuda.synchronize()
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g):
        fn()
    g.replay()
    torch.cuda.synchronize()
    e0, e1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    e0.record()
    for _ in range(reps):
        g.replay()
    e1.record()
    torch.cuda.synchronize()
    del g
    return e0.elapsed_time(e1) * 1e3 / reps


def main():
    lib = build()
    if lib is None:
        emit(verdict="FAIL", why="build")
        return
    a = lm_head_host()
    V, K = a.shape
    stats = (ctypes.c_double * 6)()
    t = time.time()
    h = lib.zslm_create(a.ctypes.data, V, K, stats)
    emit(kind="compress", ok=bool(h), wall_s=round(time.time() - t, 1), host_compress_s=round(stats[0], 1),
         upload_s=round(stats[1], 2), comp_MB=round(stats[2] / 1e6, 1), dense_MB=round(V * K * 2 / 1e6, 1),
         high_freq_frac=round(stats[3], 5), start_exp=int(stats[4]))
    if not h:
        emit(verdict="FAIL", why="compress")
        return
    Wt = torch.from_numpy(a.view(np.int16)).view(torch.bfloat16).to(DEV)
    del a
    gen = torch.Generator(device=DEV).manual_seed(3)

    def zs(x, y):
        rc = lib.zslm_gemm(h, x.data_ptr(), y.data_ptr(), x.shape[0], torch.cuda.current_stream().cuda_stream)
        if rc:
            raise RuntimeError(f"zslm_gemm rc {rc}")
        return y

    for T in (1, 2, 3, 4, 7, 8, 10, 16, 20, 30, 32, 40, 44, 48, 56, 64):
        x = (torch.randn(T, K, generator=gen, device=DEV) * 1.5).to(torch.bfloat16)
        ref = torch.matmul(x, Wt.T)
        y = zs(x, torch.empty(T, V, dtype=torch.bfloat16, device=DEV))
        torch.cuda.synchronize()
        eq = bool(torch.equal(ref, y))
        share = (ref == y).float().mean().item()
        emit(kind="bitwise", T=T, equal=eq, share_equal=round(share, 6),
             max_abs_diff=float((ref.float() - y.float()).abs().max()))
        if not eq:
            FAIL.append(("bitwise", T))
    # graph capture + replay
    T = 40
    x = (torch.randn(T, K, generator=gen, device=DEV) * 1.5).to(torch.bfloat16)
    y = torch.empty(T, V, dtype=torch.bfloat16, device=DEV)
    s = torch.cuda.Stream()
    s.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(s):
        zs(x, y)
    torch.cuda.current_stream().wait_stream(s)
    torch.cuda.synchronize()
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g):
        zs(x, y)
    ok = True
    for _ in range(3):
        x.copy_((torch.randn(T, K, generator=gen, device=DEV) * 1.5).to(torch.bfloat16))
        g.replay()
        torch.cuda.synchronize()
        ok &= bool(torch.equal(y, torch.matmul(x, Wt.T)))
    emit(kind="graph_replay", ok=ok)
    if not ok:
        FAIL.append(("graph",))
    del g
    for T in (10, 40, 48, 64):
        x = (torch.randn(T, K, generator=gen, device=DEV) * 1.5).to(torch.bfloat16)
        y = torch.empty(T, V, dtype=torch.bfloat16, device=DEV)
        t_ref = graph_us(lambda: torch.matmul(x, Wt.T))
        t_zs = graph_us(lambda: zs(x, y))
        emit(kind="timing", T=T, torch_matmul_us=round(t_ref, 1), zslm_us=round(t_zs, 1),
             saving_us=round(t_ref - t_zs, 1))
    lib.zslm_destroy(h)
    emit(verdict="PASS" if not FAIL else "FAIL", fails=FAIL)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        emit(kind="error", err=repr(e)[:400], tb=traceback.format_exc()[-2000:])
        emit(verdict="FAIL")

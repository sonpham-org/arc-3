"""klmh check in the PATCHED install (5-Oct-2026, Kernel optimizations thread). Pre-server script, free GPU.
Drives logits_processor._klmh_try with the served lm_head weight: build from the embedded sources, compress,
self-check; then bitwise vs torch.matmul at 1..64 rows (1 row must fall back: None), CUDA-graph replay with fresh
hidden states, timing (graphs). Last line {"verdict": ...}.
"""
import glob
import json
import os
import struct
import time

import numpy as np
import torch

T0 = time.time()
DEV = torch.device("cuda")
MODEL_GLOB = "/kaggle/input/models/dfranzen/intel-qwen3.8-flash-next-w4a16-autoround/**/model.safetensors.index.json"
FAIL = []


def emit(**kw):
    kw["t"] = round(time.time() - T0, 1)
    print(json.dumps(kw), flush=True)


def lm_head():
    idx = sorted(glob.glob(MODEL_GLOB, recursive=True))[0]
    d = os.path.dirname(idx)
    wm = json.load(open(idx))["weight_map"]
    name = "lm_head.weight"
    path = os.path.join(d, wm[name])
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        h = json.loads(f.read(n))
    m = h[name]
    o0, o1 = m["data_offsets"]
    a = np.fromfile(path, dtype=np.uint16, count=(o1 - o0) // 2, offset=8 + n + o0).reshape(m["shape"])
    return torch.from_numpy(a.view(np.int16)).view(torch.bfloat16).to(DEV)


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
    import sglang.srt.layers.logits_processor as LP
    W = lm_head()
    V, K = W.shape
    gen = torch.Generator(device=DEV).manual_seed(5)
    t = time.time()
    x = (torch.randn(4, K, generator=gen, device=DEV) * 1.5).to(torch.bfloat16)
    y = LP._klmh_try(x, W)
    st = LP._klmh["state"]
    emit(kind="prepare", seconds=round(time.time() - t, 1), on=isinstance(st, dict), first_call_used=y is not None)
    if not isinstance(st, dict):
        emit(verdict="FAIL", why="klmh off")
        return
    for rows in (1, 2, 3, 4, 8, 10, 12, 16, 20, 28, 36, 40, 44, 48, 52, 64, 65):
        x = (torch.randn(rows, K, generator=gen, device=DEV) * 1.5).to(torch.bfloat16)
        ref = torch.matmul(x, W.T)
        y = LP._klmh_try(x, W)
        torch.cuda.synchronize()
        if rows < 2 or rows > 64:
            ok = y is None
            emit(kind="fallback", rows=rows, falls_back=ok)
        else:
            ok = y is not None and bool(torch.equal(ref, y))
            emit(kind="bitwise", rows=rows, equal=ok)
        if not ok:
            FAIL.append(("rows", rows))
    # graph replay
    rows = 40
    x = (torch.randn(rows, K, generator=gen, device=DEV) * 1.5).to(torch.bfloat16)
    out = {}
    s = torch.cuda.Stream()
    s.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(s):
        LP._klmh_try(x, W)
    torch.cuda.current_stream().wait_stream(s)
    torch.cuda.synchronize()
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g):
        out["y"] = LP._klmh_try(x, W)
    ok = True
    for _ in range(3):
        x.copy_((torch.randn(rows, K, generator=gen, device=DEV) * 1.5).to(torch.bfloat16))
        g.replay()
        torch.cuda.synchronize()
        ok &= bool(torch.equal(out["y"], torch.matmul(x, W.T)))
    emit(kind="graph_replay", ok=ok)
    if not ok:
        FAIL.append(("graph",))
    del g
    for rows in (10, 40):
        x = (torch.randn(rows, K, generator=gen, device=DEV) * 1.5).to(torch.bfloat16)
        t_ref = graph_us(lambda: torch.matmul(x, W.T))
        t_new = graph_us(lambda: LP._klmh_try(x, W))
        emit(kind="timing", rows=rows, matmul_us=round(t_ref, 1), klmh_us=round(t_new, 1), saving_us=round(t_ref - t_new, 1))
    emit(verdict="PASS" if not FAIL else "FAIL", fails=FAIL)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        emit(kind="error", err=repr(e)[:400], tb=traceback.format_exc()[-2000:])
        emit(verdict="FAIL")

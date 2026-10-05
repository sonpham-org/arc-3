"""Smoke test for make_bench_notebook.py --pre-script (3-Oct-2026): his venv + free GPU; versions and one BF16 GEMM."""
import json, time
import torch
r = {"torch": torch.__version__, "cuda": torch.version.cuda, "gpu": torch.cuda.get_device_name(0),
     "free_gb": round(torch.cuda.mem_get_info()[0] / 2**30, 1)}
for mod in ("sglang", "flashinfer", "triton", "sgl_kernel", "vllm"):
    try:
        m = __import__(mod); r[mod] = getattr(m, "__version__", "?")
    except Exception as e:
        r[mod] = "missing: " + repr(e)[:80]
a = torch.randn(52, 2560, device="cuda", dtype=torch.bfloat16); w = torch.randn(2560, 8192, device="cuda", dtype=torch.bfloat16)
for _ in range(10): a @ w
torch.cuda.synchronize(); t = time.perf_counter()
for _ in range(200): a @ w
torch.cuda.synchronize(); dt = (time.perf_counter() - t) / 200
r["gemm_52x2560x8192_us"] = round(dt * 1e6, 1); r["gemm_GBps"] = round(2560 * 8192 * 2 / dt / 1e9, 0)
print(json.dumps(r))

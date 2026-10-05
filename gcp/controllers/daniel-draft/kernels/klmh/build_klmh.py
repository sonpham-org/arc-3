"""Build klmh's patched logits_processor.py (5-Oct-2026, Kernel optimizations thread). python build_klmh.py

klmh: the target lm_head (vocab 248,320 x 2,560 bf16 = 1.27 GB, ~890 us per decode step at 92% of DRAM speed) runs
through ZipServ's ZipGEMM (TCA-TBE lossless BF16 compression, Apache-2.0, github.com/HPMLL/ZipServ_ASPLOS26) on a
compressed copy (0.90 GB): 720 us at 40 rows. Measured (daniel-bench-zslm-1005, served weights): output BIT-IDENTICAL
to torch.matmul(hidden, W.T) at 2..64 rows; at 1 row cuBLAS switches to a GEMV kernel (0.12% of logits differ by 1
bf16 step), so 1-row calls (a lone prefill's last token) stay on torch.matmul. The dense weight is kept (fallback,
any other reader): +0.90 GB GPU memory, taken at the first eligible eager call (before CUDA-graph capture), only when
enough memory stays free. A startup self-check compares 2 / 8 / 40 rows bitwise and disables klmh on any mismatch.
The ZipServ sources + our C shim (zslm.cu) ride inside the file as a base64 tgz; compiled once with sglang's nvcc into
$SGLANG_KLMH_DIR (default the temp dir), ~10 s; host compression ~10 s.
SGLANG_KLMH=0 disables. SGLANG_KLMH_MIN_FREE_GB (default 2.0) = free GPU memory required after the allocation.
"""
import base64
import io
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
WHEEL = ROOT / "wheel" / "full"
ZSRC = HERE.parent / "zipserv" / "src" / "ZipServ_ASPLOS26"
REL = "sglang/srt/layers/logits_processor.py"

FILES = {
    "zslm.cu": HERE.parent / "zslm" / "zslm.cu",
    "LICENSE": ZSRC / "LICENSE",
    "build/L_API.cuh": ZSRC / "build" / "L_API.cuh",
    "kernel_benchmark/utils.h": ZSRC / "kernel_benchmark" / "utils.h",
}
for p in sorted((ZSRC / "csrc").iterdir()):
    FILES[f"csrc/{p.name}"] = p

buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.USTAR_FORMAT) as t:
    for name, p in sorted(FILES.items()):
        data = p.read_bytes()
        ti = tarfile.TarInfo(name)
        ti.size = len(data)
        ti.mtime = 0
        t.addfile(ti, io.BytesIO(data))
b64 = base64.b64encode(buf.getvalue()).decode()
lines = [b64[i:i + 116] for i in range(0, len(b64), 116)]
blob = "(\n" + "\n".join(f'    "{ln}"' for ln in lines) + "\n)"

TAIL = r'''


# --- klmh (Kernel optimizations thread, 5-Oct-2026): target lm_head through ZipServ's ZipGEMM on a losslessly
# compressed copy (TCA-TBE; Apache-2.0, github.com/HPMLL/ZipServ_ASPLOS26). Bit-identical to torch.matmul at 2..64
# rows (measured on the served weights); 1-row calls and everything else stay on torch.matmul. See the kernels/klmh
# README in daniel-draft. SGLANG_KLMH=0 disables.
import os as _klmh_os

_KLMH = _klmh_os.environ.get("SGLANG_KLMH", "1") != "0"
_KLMH_MIN_VOCAB = 131072
_KLMH_MIN_ROWS = 2
_KLMH_MAX_ROWS = 64
_KLMH_MIN_FREE_GB = float(_klmh_os.environ.get("SGLANG_KLMH_MIN_FREE_GB", "2.0"))
_klmh = {"state": None}   # None: not tried yet; "off": disabled; dict: ready
_KLMH_SRC = __BLOB__


def _klmh_build():
    import base64
    import ctypes
    import glob
    import hashlib
    import subprocess
    import sys
    import tarfile
    import tempfile
    from pathlib import Path

    from sglang.kernels.jit.utils.compile import toolchain

    sha = hashlib.sha256(_KLMH_SRC.encode()).hexdigest()[:12]
    major, minor = torch.cuda.get_device_capability()
    d = Path(_klmh_os.environ.get("SGLANG_KLMH_DIR", tempfile.gettempdir())) / f"klmh_{sha}_sm{major}{minor}"
    so = d / "libzslm.so"
    home = toolchain.cuda_home()
    roots = [home, sys.prefix, "/usr/local/cuda"]
    cublas = []
    for r in roots:
        for pat in ("lib64/libcublas.so*", "lib/libcublas.so*", "lib/python3*/site-packages/nvidia/*/lib/libcublas.so*",
                    "**/nvidia/cublas/lib/libcublas.so*"):
            cublas += glob.glob(_klmh_os.path.join(r, pat), recursive="**" in pat)
    cublas = sorted(set(c for c in cublas if _klmh_os.path.basename(c).startswith("libcublas.so")))
    if not so.exists():
        d.mkdir(parents=True, exist_ok=True)
        import io

        with tarfile.open(fileobj=io.BytesIO(base64.b64decode(_KLMH_SRC))) as t:
            t.extractall(d)
        incs = [_klmh_os.path.join(home, "include")]
        for r in roots:
            incs += [_klmh_os.path.dirname(h) for h in glob.glob(_klmh_os.path.join(r, "**", "cublas_v2.h"),
                                                                recursive=True)[:4]]
        cmd = [toolchain.device_compiler_path(), "-O3", "-std=c++17", "-shared", "-Xcompiler", "-fPIC", "-gencode",
               f"arch=compute_{major}{minor},code=sm_{major}{minor}", "--use_fast_math", "-maxrregcount=255",
               "-I", str(d / "csrc"), "-I", str(d / "build"), "-I", str(d / "kernel_benchmark")]
        for i in dict.fromkeys(incs):
            cmd += ["-I", i]
        tmp = d / f"libzslm.{_klmh_os.getpid()}.so"
        cmd += [str(d / "zslm.cu"), str(d / "csrc" / "L_API.cu"), "-o", str(tmp)]
        if cublas:
            cmd += [cublas[0]]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
        if r.returncode:
            raise RuntimeError("klmh build failed: " + r.stderr[-1500:])
        _klmh_os.replace(tmp, so)
    for c in cublas[:1]:
        try:
            ctypes.CDLL(c, mode=ctypes.RTLD_GLOBAL)
        except OSError:
            pass
    lib = ctypes.CDLL(str(so))
    lib.zslm_create.restype = ctypes.c_void_p
    lib.zslm_create.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_double)]
    lib.zslm_gemm.restype = ctypes.c_int
    lib.zslm_gemm.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    lib.zslm_destroy.argtypes = [ctypes.c_void_p]
    return lib


def _klmh_prepare(weight):
    import ctypes
    import time

    t0 = time.time()
    V, K = weight.shape
    need = V * K * 2 * 0.75 + _KLMH_MIN_FREE_GB * 2**30   # compressed copy (~0.71 of dense) + headroom
    free, _ = torch.cuda.mem_get_info(weight.device)
    if free < need:
        logger.warning(f"klmh: off, {free / 2**30:.2f} GB free < {need / 2**30:.2f} GB needed")
        return "off"
    lib = _klmh_build()
    torch.cuda.synchronize()
    host = weight.detach().to("cpu").contiguous().view(torch.int16).numpy()
    stats = (ctypes.c_double * 6)()
    h = lib.zslm_create(host.ctypes.data, V, K, stats)
    del host
    if not h or stats[5] != 1.0:
        logger.warning("klmh: off, compression / upload failed")
        return "off"
    st = {"lib": lib, "h": h, "V": V, "K": K, "ptr": weight.data_ptr()}
    gen = torch.Generator(device=weight.device).manual_seed(7)
    for rows in (2, 8, 40):
        x = (torch.randn(rows, K, generator=gen, device=weight.device) * 1.5).to(torch.bfloat16)
        ref = torch.matmul(x, weight.T)
        y = _klmh_gemm(st, x)
        torch.cuda.synchronize()
        if not torch.equal(ref, y):
            logger.warning(f"klmh: off, self-check mismatch at {rows} rows")
            lib.zslm_destroy(h)
            return "off"
    logger.info(f"klmh: on, lm_head {V}x{K} compressed to {stats[2] / 2**30:.2f} GB (host {stats[0]:.1f} s), "
                f"self-check bitwise at 2/8/40 rows, {time.time() - t0:.1f} s total")
    return st


def _klmh_gemm(st, x):
    y = torch.empty((x.shape[0], st["V"]), dtype=torch.bfloat16, device=x.device)
    rc = st["lib"].zslm_gemm(st["h"], x.data_ptr(), y.data_ptr(), x.shape[0], torch.cuda.current_stream().cuda_stream)
    if rc:
        raise RuntimeError(f"klmh: zslm_gemm returned CUDA error {rc}")
    return y


def _klmh_try(hidden_states, weight):
    """logits = hidden_states @ weight.T through the compressed copy, or None (caller uses torch.matmul)."""
    if not _KLMH:
        return None
    if (
        hidden_states.dim() != 2
        or weight.dim() != 2
        or weight.shape[0] < _KLMH_MIN_VOCAB
        or not (_KLMH_MIN_ROWS <= hidden_states.shape[0] <= _KLMH_MAX_ROWS)
        or hidden_states.dtype != torch.bfloat16
        or weight.dtype != torch.bfloat16
        or not hidden_states.is_cuda
        or hidden_states.shape[1] != weight.shape[1]
    ):
        return None
    st = _klmh["state"]
    if st is None:
        if torch.cuda.is_current_stream_capturing():
            return None
        try:
            st = _klmh_prepare(weight)
        except Exception as e:  # never take the server down for a speed-up
            logger.warning(f"klmh: off ({e!r})"[:600])
            st = "off"
        _klmh["state"] = st
    if st == "off" or st["ptr"] != weight.data_ptr() or st["V"] != weight.shape[0]:
        return None   # one compressed matrix per process (ZipServ sizes shared memory from its first call)
    x = hidden_states if hidden_states.is_contiguous() else hidden_states.contiguous()
    return _klmh_gemm(st, x)
'''.replace("__BLOB__", blob)

OLD = """            else:
                logits = torch.matmul(
                    hidden_states.to(lm_head.weight.dtype), lm_head.weight.T
                )"""
NEW = """            else:
                logits = _klmh_try(hidden_states, lm_head.weight)   # klmh: None -> unchanged path
                if logits is None:
                    logits = torch.matmul(
                        hidden_states.to(lm_head.weight.dtype), lm_head.weight.T
                    )"""

s = (WHEEL / REL).read_text(encoding="utf-8")
assert s.count(OLD) == 1, s.count(OLD)
s = s.replace(OLD, NEW)
assert "\nlogger = " in s
s = s.rstrip("\n") + "\n" + TAIL
out = HERE / "patched" / REL
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(s, encoding="utf-8")
orig = HERE / "orig" / REL
orig.parent.mkdir(parents=True, exist_ok=True)
orig.write_bytes((WHEEL / REL).read_bytes())
compile(s, str(out), "exec")
print("wrote", out, f"({len(s) // 1024} KB, blob {len(b64) // 1024} KB, {len(FILES)} files)")

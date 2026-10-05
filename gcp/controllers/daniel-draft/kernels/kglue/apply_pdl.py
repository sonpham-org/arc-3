"""kglue PDL (programmatic dependent launch) for our Triton kernels (5-Oct-2026, Kernel optimizations thread).
Idempotent: rebuilds from kfast's patched file. python apply_pdl.py

His JIT CUDA kernels (norms, combine, top-k sum, ...) already launch with PDL on sm_90+; the kfast skinny GEMM (about
255 launches per decode step) did not, so every transition into it paid the full graph launch gap (~0.5 us idle).
With launch_pdl=True the skinny kernel's CTAs are launched while the previous kernel drains and wait at
griddepcontrol.wait (first statement, before ANY global memory access, so ordering and visibility are unchanged);
no explicit early trigger (the dependent launch happens at our grid's completion as before). Math unchanged.
SGLANG_KGLUE_PDL=0 disables.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
WHEEL = HERE.parent.parent / "wheel" / "full"


def build(rel, base, subs, out_dir):
    s = base.read_text(encoding="utf-8")
    for sub in subs:
        old, new, n = (*sub, 1) if len(sub) == 2 else sub
        assert s.count(old) == n, (rel, old[:70], s.count(old))
        s = s.replace(old, new)
    out = out_dir / "patched" / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(s, encoding="utf-8")
    orig = out_dir / "orig" / rel
    orig.parent.mkdir(parents=True, exist_ok=True)
    orig.write_bytes((WHEEL / rel).read_bytes())
    compile(s, str(out), "exec")
    print("wrote", out)


G = "sglang/kernels/ops/gemm/sm120_lowm_bf16_gemm.py"
# Separate sets so a stack can pair PDL with either GEMM table: kpdl = kfast + PDL (<= 64 rows, W4),
# kpdl128 = kfast128 + PDL (<= 128 rows, W8). Each supersedes its base's file.
SUBS = [
    ("""_SKINNY_ON = _os.environ.get("SGLANG_KFAST_SKINNY", "1") == "1"
""", """_SKINNY_ON = _os.environ.get("SGLANG_KFAST_SKINNY", "1") == "1"
# kglue (5-Oct-2026): launch the skinny kernel with PDL (see kernel). SGLANG_KGLUE_PDL=0 disables.
_KGLUE_PDL = _os.environ.get("SGLANG_KGLUE_PDL", "1") != "0"
_kglue_pdl_ok = None


def _kglue_use_pdl() -> bool:
    global _kglue_pdl_ok
    if _kglue_pdl_ok is None:
        try:
            from sglang.kernels.jit.utils import is_arch_support_pdl

            _kglue_pdl_ok = bool(_KGLUE_PDL and is_arch_support_pdl())
        except Exception:
            _kglue_pdl_ok = False
    return _kglue_pdl_ok
"""),
    ("""    EVEN_N: tl.constexpr,
    NTHREADS: tl.constexpr,
):
    pid_n = tl.program_id(0)""", """    EVEN_N: tl.constexpr,
    NTHREADS: tl.constexpr,
    USE_PDL: tl.constexpr = False,
):
    if USE_PDL:
        # kglue: launched early under PDL; wait for the previous grid before touching any memory
        tl.extra.cuda.gdc_wait()
    pid_n = tl.program_id(0)"""),
    ("""        EVEN_N=(n % block_n == 0),
        NTHREADS=32 * num_warps,
        num_warps=num_warps,
    )
    return out""", """        EVEN_N=(n % block_n == 0),
        NTHREADS=32 * num_warps,
        USE_PDL=_kglue_use_pdl(),
        num_warps=num_warps,
        **({"launch_pdl": True} if _kglue_use_pdl() else {}),
    )
    return out"""),
]
build(G, HERE.parent / "kfast" / "patched" / G, SUBS, HERE.parent / "kpdl")
build(G, HERE.parent / "kfast128" / "patched" / G, SUBS, HERE.parent / "kpdl128")

"""kglue: the khc fused HC mix made bit-exact (5-Oct-2026, Kernel optimizations thread). Substitutions applied by
apply_hc.py to khc's hyperconnection.py.

daniel-bench-kglue2-1005 / kmix-1005 (real layer-0 weights): the 0.05% of differing elements all came from the down
projection's split-K order. cuBLAS (CUTLASS split-K) cuts K = 10,240 into slices of round_up(ceil(K / splits), 8)
and sums the slice partials in order; at 33..64 rows it uses 20 slices with fp32 partials (kernel
s16816gemm_bf16_64x64_32x6 grid z = 20), at 80 rows (width-8 verify) 27 slices of 384 (last 256) with BF16 partials
(bf16_s16816gemm_relu_bf16_64x128_64x3 grid z = 27, splitKreduce<.., bf16, bf16, float>). Our down kernel takes the
same slices and partial dtype, so the down projection is BIT-IDENTICAL to F.linear and the whole mix to the compiled
chain (silu and the sigmoid-mul-mean tail already were). cuBLAS's choice depends on the row count, so the recipe is
picked per (K, N, hc, rows) at the first eager call of that shape (graph warm-up runs before capture): each candidate
must reproduce F.linear's down projection AND the compiled chain's output on 6 random inputs; a shape with no match
keeps the compiled chain (17..32 rows today). Under capture an unchecked shape keeps the compiled chain.
SGLANG_KGLUE_MIX_EXACT=0 goes back to the fixed 10-slice split (not exact); SGLANG_KHC_MIX_MAX_ROWS=0 turns the fused
mix off. The kernels launch with PDL (wait first, before any memory access); SGLANG_KGLUE_PDL=0 disables.
"""

SUBS = [
    # on by default up to 128 rows (exact mode decides per shape)
    ('_KHC_MIX_MAX_ROWS = int(_khc_os.environ.get("SGLANG_KHC_MIX_MAX_ROWS", "0"))',
     '_KHC_MIX_MAX_ROWS = int(_khc_os.environ.get("SGLANG_KHC_MIX_MAX_ROWS", "128"))  # kglue: on, exact mode below\n'
     '_KGLUE_MIX_EXACT = _khc_os.environ.get("SGLANG_KGLUE_MIX_EXACT", "1") != "0"\n'
     '# cuBLAS\'s own split-K recipes for this projection (slices, partial dtype); anything else only matches by luck\n'
     '_KGLUE_MIX_CANDIDATES = (dict(S=20, PART_BF16=False), dict(S=27, PART_BF16=True))\n'
     '_KGLUE_MIX_TRIALS = 6\n'
     '# sweep at the exact split (daniel-bench-kmix-1005, 40 rows, cold weights; all 72 tactics bitwise): 16.6 us vs\n'
     '# the compiled chain 20.1 us. BLOCK_K 64 divides every slice length used (512, 384, 256).\n'
     '_KGLUE_MIX_TACTIC = dict(BLOCK_N=64, BLOCK_K=64, down_warps=8, down_stages=4)\n'
     '_kglue_mix_split = {}   # (K, N, hc, rows) -> recipe proven bitwise vs the compiled chain, or None\n'
     '_KGLUE_MIX_PDL = _khc_os.environ.get("SGLANG_KGLUE_PDL", "1") != "0"\n'
     '_kglue_mix_pdl_ok = None\n'),
    # khc's split combine (bit-identical to his one-CTA-per-row kernel by construction) up to 128 rows: width-8
    # verify has 80 rows; the combine + norm fusion rides on it
    ('_KHC_SPLIT_MAX_ROWS = int(_khc_os.environ.get("SGLANG_KHC_SPLIT_MAX_ROWS", "64"))',
     '_KHC_SPLIT_MAX_ROWS = int(_khc_os.environ.get("SGLANG_KHC_SPLIT_MAX_ROWS", "128"))  # kglue: width-8 (80 rows)'),
    # down kernel: PDL, variable slice length (last slice shorter), partial stored in the scratch's dtype
    ("""def _khc_mix_down_kernel(x_ptr, w_ptr, part_ptr, M, K, N,
                         K_PER_S: tl.constexpr, ROWS: tl.constexpr,
                         BLOCK_N: tl.constexpr, BLOCK_K: tl.constexpr):
    pid_n = tl.program_id(0)""",
     """def _khc_mix_down_kernel(x_ptr, w_ptr, part_ptr, M, K, N,
                         K_PER_S: tl.constexpr, ROWS: tl.constexpr,
                         BLOCK_N: tl.constexpr, BLOCK_K: tl.constexpr, USE_PDL: tl.constexpr = False):
    if USE_PDL:
        tl.extra.cuda.gdc_wait()
    pid_n = tl.program_id(0)"""),
    ("""    k0 = pid_s * K_PER_S
    for kk in range(0, K_PER_S, BLOCK_K):""", """    k0 = pid_s * K_PER_S
    k_end = tl.minimum(K - k0, K_PER_S)   # kglue: cuBLAS's last split-K slice is shorter
    for kk in range(0, k_end, BLOCK_K):"""),
    ("""    tl.store(p, acc, mask=mask_n[None, :])""",
     """    tl.store(p, acc.to(part_ptr.dtype.element_ty), mask=mask_n[None, :])   # kglue: fp32 or bf16 partials"""),
    # reduce kernel: PDL; partials may be bf16
    ("""def _khc_mix_reduce_kernel(part_ptr, t_ptr, M, N, SLICE_STRIDE, hc_f, S: tl.constexpr,
                           BLOCK: tl.constexpr):
""", """def _khc_mix_reduce_kernel(part_ptr, t_ptr, M, N, SLICE_STRIDE, hc_f, S: tl.constexpr,
                           BLOCK: tl.constexpr, USE_PDL: tl.constexpr = False):
    if USE_PDL:
        tl.extra.cuda.gdc_wait()
"""),
    ("""        tot += tl.load(part_ptr + s * SLICE_STRIDE + idx, mask=mask, other=0.0)""",
     """        tot += tl.load(part_ptr + s * SLICE_STRIDE + idx, mask=mask, other=0.0).to(tl.float32)"""),
    # up kernels: PDL
    ("""                       HC: tl.constexpr, ROWS: tl.constexpr, BLOCK_J: tl.constexpr,
                       BLOCK_R: tl.constexpr, N_PAD: tl.constexpr):
    pid = tl.program_id(0)""", """                       HC: tl.constexpr, ROWS: tl.constexpr, BLOCK_J: tl.constexpr,
                       BLOCK_R: tl.constexpr, N_PAD: tl.constexpr, USE_PDL: tl.constexpr = False):
    if USE_PDL:
        tl.extra.cuda.gdc_wait()
    pid = tl.program_id(0)"""),
    ("""                        ROWS: tl.constexpr, BLOCK_J: tl.constexpr, BLOCK_R: tl.constexpr, N_PAD: tl.constexpr):
""", """                        ROWS: tl.constexpr, BLOCK_J: tl.constexpr, BLOCK_R: tl.constexpr, N_PAD: tl.constexpr,
                        USE_PDL: tl.constexpr = False):
    if USE_PDL:
        tl.extra.cuda.gdc_wait()
"""),
    # launcher: slice length (cuBLAS: round_up(ceil(K / S), 8)), partial dtype, PDL
    ("""    rows_pad = 32 if rows <= 32 else (64 if rows <= 64 else 128)
    key = (x.device, k, n, rows_pad, S)
    scratch = _khc_mix_scratch.get(key)
    if scratch is None:   # persistent per shape: CUDA graphs keep these pointers
        scratch = (torch.empty((S, rows_pad, n), dtype=torch.float32, device=x.device),""",
     """    rows_pad = 32 if rows <= 32 else (64 if rows <= 64 else 128)
    k_slice = -(-(-(-k // S)) // 8) * 8   # kglue: CUTLASS split-K slice = round_up(ceil(K / S), 8)
    S = -(-k // k_slice)
    part_dt = torch.bfloat16 if t_.get("PART_BF16", False) else torch.float32
    key = (x.device, k, n, rows_pad, S, part_dt)
    scratch = _khc_mix_scratch.get(key)
    if scratch is None:   # persistent per shape: CUDA graphs keep these pointers
        scratch = (torch.empty((S, rows_pad, n), dtype=part_dt, device=x.device),"""),
    ("""    stage = t_.get("stage", "all")   # tuning only: "down" / "reduce" / "up" run one kernel
""", """    stage = t_.get("stage", "all")   # tuning only: "down" / "reduce" / "up" run one kernel
    pdl = _kglue_mix_use_pdl()
    pk = {"launch_pdl": True} if pdl else {}
"""),
    ("""            x, w_down, part, rows, k, n, K_PER_S=k // S, ROWS=rows_pad, BLOCK_N=bn, BLOCK_K=bk,
            num_warps=t_.get("down_warps", 4), num_stages=t_.get("down_stages", 3))""",
     """            x, w_down, part, rows, k, n, K_PER_S=k_slice, ROWS=rows_pad, BLOCK_N=bn, BLOCK_K=bk,
            USE_PDL=pdl, num_warps=t_.get("down_warps", 4), num_stages=t_.get("down_stages", 3), **pk)"""),
    ("""            part, t, rows, n, rows_pad * n, float(hc), S=S, BLOCK=256, num_warps=4)""",
     """            part, t, rows, n, rows_pad * n, float(hc), S=S, BLOCK=256, USE_PDL=pdl, num_warps=4, **pk)"""),
    ("""            N_PAD=triton.cdiv(n, br) * br, num_warps=t_.get("up_warps", 4), num_stages=t_.get("up_stages", 3))""",
     """            N_PAD=triton.cdiv(n, br) * br, USE_PDL=pdl, num_warps=t_.get("up_warps", 4),
            num_stages=t_.get("up_stages", 3), **pk)""", 2),
    # helpers before HyperConnectionConfig
    ("""

class HyperConnectionConfig(msgspec.Struct, frozen=True):""", '''

def _kglue_mix_use_pdl() -> bool:
    global _kglue_mix_pdl_ok
    if _kglue_mix_pdl_ok is None:
        try:
            from sglang.kernels.jit.utils import is_arch_support_pdl

            _kglue_mix_pdl_ok = bool(_KGLUE_MIX_PDL and is_arch_support_pdl())
        except Exception:
            _kglue_mix_pdl_ok = False
    return _kglue_mix_pdl_ok


def _kglue_mix_pick(mod, x, w_down, w_up, hc, hs):
    """kglue: the split-K recipe for which the fused mix is bit-identical to mod._mix_compute at this shape, else
    None (the compiled chain)."""
    key = (x.shape[1], w_down.shape[0], hc, x.shape[0])
    if key in _kglue_mix_split:
        return _kglue_mix_split[key]
    if torch.cuda.is_current_stream_capturing():
        return None   # unchecked shape inside a capture: the compiled chain
    m, k = x.shape
    n = w_down.shape[0]
    rows_pad = 32 if m <= 32 else (64 if m <= 64 else 128)
    gen = torch.Generator(device=x.device).manual_seed(4242 + m)
    xs = [(torch.randn(m, k, generator=gen, device=x.device) * (0.25 * (1 + i))).to(torch.bfloat16)
          for i in range(_KGLUE_MIX_TRIALS)]
    pick = None
    with torch.no_grad():
        refs = [(F.linear(xx, w_down), mod._mix_compute(xx, w_down, w_up, hc, hs).to(torch.bfloat16)) for xx in xs]
        for cand in _KGLUE_MIX_CANDIDATES:
            tac = dict(_KGLUE_MIX_TACTIC, **cand)
            k_slice = -(-(-(-k // cand["S"])) // 8) * 8
            if k_slice % tac["BLOCK_K"] or (k % k_slice) % tac["BLOCK_K"]:
                continue
            S = -(-k // k_slice)
            part_dt = torch.bfloat16 if cand.get("PART_BF16") else torch.float32
            ok = True
            for xx, (d_ref, o_ref) in zip(xs, refs):
                _khc_fused_mix(xx, w_down, w_up, hc, hs, dict(tac, stage="down"))
                part = _khc_mix_scratch[(xx.device, k, n, rows_pad, S, part_dt)][0]
                tot = part[0, :m].float()
                for s in range(1, S):
                    tot = tot + part[s, :m].float()
                out = _khc_fused_mix(xx, w_down, w_up, hc, hs, tac)
                ok = ok and torch.equal(tot.to(torch.bfloat16), d_ref) and torch.equal(out, o_ref)
                if not ok:
                    break
            if ok:
                pick = tac
                break
    _kglue_mix_split[key] = pick
    return pick


class HyperConnectionConfig(msgspec.Struct, frozen=True):'''),
    # dispatch
    ("""        elif self.hc_count == 4 and _khc_mix_ok(   # the up4 kernel; hc 5 (MTP) keeps the compiled chain
            hyper_input_normed,
            self.input_mix_weight_down.weight,
            self.input_mix_weight_up.weight,
        ):
            mixed_input = _khc_fused_mix(
                hyper_input_normed,
                self.input_mix_weight_down.weight,
                self.input_mix_weight_up.weight,
                self.hc_count,
                self.hidden_size,
            ).to(self.params_dtype)""",
     """        elif self.hc_count == 4 and _khc_mix_ok(   # the up4 kernel; hc 5 (MTP) keeps the compiled chain
            hyper_input_normed,
            self.input_mix_weight_down.weight,
            self.input_mix_weight_up.weight,
        ) and (
            not _KGLUE_MIX_EXACT
            or _kglue_mix_pick(self, hyper_input_normed, self.input_mix_weight_down.weight,
                               self.input_mix_weight_up.weight, self.hc_count, self.hidden_size) is not None
        ):
            recipe = (_kglue_mix_split.get((hyper_input_normed.shape[1], self.input_mix_weight_down.weight.shape[0],
                                            self.hc_count, hyper_input_normed.shape[0]))
                      if _KGLUE_MIX_EXACT else None)
            mixed_input = _khc_fused_mix(
                hyper_input_normed,
                self.input_mix_weight_down.weight,
                self.input_mix_weight_up.weight,
                self.hc_count,
                self.hidden_size,
                recipe,
            ).to(self.params_dtype)"""),
]

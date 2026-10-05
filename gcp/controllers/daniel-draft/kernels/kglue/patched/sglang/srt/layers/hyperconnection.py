import os as _khc_os
import weakref as _kglue_weakref
from typing import Optional

import msgspec
import torch
import torch.nn as nn
import torch.nn.functional as F

from sglang.srt.layers.hc_mix_triton import fused_hc_mix, fused_hc_mix_supported

# --- khc (Kernel optimizations thread, 4-Oct-2026): the split HC combine (hc_combine_gate + hc_combine_apply, one CTA
# per warp of the reference kernel, bit-identical by construction) is used up to this many rows; his cap was 32, so a
# 10-lane x 4-token verify (40 rows) fell back to the one-CTA-per-row kernel (40 CTAs on 188 SMs, 6.8 us per call).
# SGLANG_KHC_SPLIT_MAX_ROWS=32 restores his behaviour.
_KHC_SPLIT_MAX_ROWS = int(_khc_os.environ.get("SGLANG_KHC_SPLIT_MAX_ROWS", "64"))

# --- khc fused HC mix (4-Oct-2026): for 17.._KHC_MIX_MAX_ROWS rows (his persistent kernel covers <= 16, the
# torch.compile chain everything above) the low-rank mix runs as 3 deterministic kernels instead of the 6-kernel
# chain (cuBLAS down GEMM + splitK reduce, div_silu, cuBLAS up GEMM, sigmoid-mul-mean):
#   down : grid (N tiles, S K-slices); partial x @ W_down^T per slice -> fp32 scratch (plain stores)
#   red  : fixed-order sum over slices -> bf16 (as cuBLAS writes it) -> / hc -> silu -> bf16 t
#   up   : per column strip, all hc groups: t @ W_up^T -> bf16 (as cuBLAS) -> sigmoid * normed -> sum over groups
#          in order g = 0..hc-1 -> / hc -> bf16
# Rounding points follow the compiled chain; only fp32 accumulation order differs (as kfast). No atomics.
# SGLANG_KHC_MIX_MAX_ROWS=0 disables it.
# Default OFF: NOT bitwise (99.95% of elements equal the compiled chain; split-K sum order), -0.34 ms/step in-server
# (daniel-bench-khcmixs-1004), greedy inside cross-server noise. SGLANG_KHC_MIX_MAX_ROWS=64 turns it on.
_KHC_MIX_MAX_ROWS = int(_khc_os.environ.get("SGLANG_KHC_MIX_MAX_ROWS", "64"))  # kglue: on, exact mode below
_KGLUE_MIX_EXACT = _khc_os.environ.get("SGLANG_KGLUE_MIX_EXACT", "1") != "0"
_KGLUE_MIX_CANDIDATES = (20,)   # cuBLAS's own split at 33..64 rows; other splits only match by luck
_KGLUE_MIX_TRIALS = 6
_KGLUE_MIX_FUSE_REDUCE = _khc_os.environ.get("SGLANG_KGLUE_MIX_FUSE_REDUCE", "0") == "1"   # slower: 23.8 us
# sweep at the exact split (daniel-bench-kmix-1005, 40 rows, cold weights; all 72 tactics bitwise): 16.6 us vs
# the compiled chain 20.1 us
_KGLUE_MIX_TACTIC_S20 = dict(BLOCK_N=64, BLOCK_K=64, down_warps=8, down_stages=4)
_kglue_mix_cnt = {}   # (device, N, BLOCK_N, rows_pad, S) -> int32 arrival counters, zero at rest
_kglue_mix_split = {}   # (K, N, hc, rows) -> split proven bitwise vs the compiled chain, or None
_KGLUE_MIX_PDL = _khc_os.environ.get("SGLANG_KGLUE_PDL", "1") != "0"
_kglue_mix_pdl_ok = None

# Tactic from the sweep (daniel-bench-khctune2-1004, 40 rows, cold weights): down 7.4 + reduce 1.2 + up4 8.3 =
# 16.1 us vs 19.5 us for the compiled chain; bitwise 99.9% equal (the rest 1 bf16 step: split-K sum order).
_KHC_MIX_S = 10          # K slices of the down projection (K = hc * hs = 10240 -> 1024 per slice)
_KHC_MIX_BLOCK_K = 128
_KHC_MIX_BLOCK_N = 32
_KHC_MIX_BLOCK_J = 16
_KHC_MIX_BLOCK_R = 64
_KHC_MIX_TACTIC = dict(down_warps=8, down_stages=4, up_warps=4, up_stages=4)
_khc_mix_scratch = {}

import triton  # noqa: E402  (khc)
import triton.language as tl  # noqa: E402  (khc)


@triton.jit
def _khc_mix_down_kernel(x_ptr, w_ptr, part_ptr, M, K, N,
                         K_PER_S: tl.constexpr, ROWS: tl.constexpr,
                         BLOCK_N: tl.constexpr, BLOCK_K: tl.constexpr, USE_PDL: tl.constexpr = False):
    if USE_PDL:
        tl.extra.cuda.gdc_wait()
    pid_n = tl.program_id(0)
    pid_s = tl.program_id(1)
    offs_m = tl.arange(0, ROWS)
    offs_n = pid_n * BLOCK_N + tl.arange(0, BLOCK_N)
    mask_m = offs_m < M
    mask_n = offs_n < N
    acc = tl.zeros((ROWS, BLOCK_N), dtype=tl.float32)
    k0 = pid_s * K_PER_S
    for kk in range(0, K_PER_S, BLOCK_K):
        k = k0 + kk + tl.arange(0, BLOCK_K)
        xt = tl.load(x_ptr + offs_m[:, None] * K + k[None, :], mask=mask_m[:, None], other=0.0)
        w = tl.load(w_ptr + offs_n[:, None] * K + k[None, :], mask=mask_n[:, None], other=0.0)
        acc = tl.dot(xt, tl.trans(w), acc)
    p = part_ptr + (pid_s * ROWS + offs_m[:, None]) * N + offs_n[None, :]
    tl.store(p, acc, mask=mask_n[None, :])


@triton.jit
def _khc_mix_reduce_kernel(part_ptr, t_ptr, M, N, SLICE_STRIDE, hc_f, S: tl.constexpr,
                           BLOCK: tl.constexpr, USE_PDL: tl.constexpr = False):
    if USE_PDL:
        tl.extra.cuda.gdc_wait()
    idx = tl.program_id(0) * BLOCK + tl.arange(0, BLOCK)   # = m * N + n over the M real rows
    mask = idx < M * N
    tot = tl.zeros((BLOCK,), dtype=tl.float32)
    for s in range(0, S):   # fixed order: deterministic
        tot += tl.load(part_ptr + s * SLICE_STRIDE + idx, mask=mask, other=0.0)
    y = tot.to(tl.bfloat16).to(tl.float32) / hc_f
    t = y * tl.sigmoid(y)
    tl.store(t_ptr + idx, t.to(tl.bfloat16), mask=mask)


@triton.jit
def _khc_mix_up_kernel(t_ptr, w_ptr, x_ptr, out_ptr, M, N, HS, hc_f,
                       HC: tl.constexpr, ROWS: tl.constexpr, BLOCK_J: tl.constexpr,
                       BLOCK_R: tl.constexpr, N_PAD: tl.constexpr, USE_PDL: tl.constexpr = False):
    if USE_PDL:
        tl.extra.cuda.gdc_wait()
    pid = tl.program_id(0)
    offs_m = tl.arange(0, ROWS)
    mask_m = offs_m < M
    j = pid * BLOCK_J + tl.arange(0, BLOCK_J)
    mask_j = j < HS
    out = tl.zeros((ROWS, BLOCK_J), dtype=tl.float32)
    for g in tl.static_range(HC):
        acc = tl.zeros((ROWS, BLOCK_J), dtype=tl.float32)
        for r0 in range(0, N_PAD, BLOCK_R):
            r = r0 + tl.arange(0, BLOCK_R)
            mask_r = r < N
            a = tl.load(t_ptr + offs_m[:, None] * N + r[None, :], mask=mask_m[:, None] & mask_r[None, :], other=0.0)
            w = tl.load(w_ptr + (g * HS + j)[:, None] * N + r[None, :], mask=mask_j[:, None] & mask_r[None, :],
                        other=0.0)
            acc = tl.dot(a, tl.trans(w), acc)
        gate = tl.sigmoid(acc.to(tl.bfloat16).to(tl.float32))
        xg = tl.load(x_ptr + offs_m[:, None] * (HC * HS) + g * HS + j[None, :],
                     mask=mask_m[:, None] & mask_j[None, :], other=0.0).to(tl.float32)
        out += gate * xg
    out = out / hc_f
    tl.store(out_ptr + offs_m[:, None] * HS + j[None, :], out.to(tl.bfloat16), mask=mask_m[:, None] & mask_j[None, :])


@triton.jit
def _khc_mix_up4_kernel(t_ptr, w_ptr, x_ptr, out_ptr, M, N, HS, hc_f,
                        ROWS: tl.constexpr, BLOCK_J: tl.constexpr, BLOCK_R: tl.constexpr, N_PAD: tl.constexpr,
                        USE_PDL: tl.constexpr = False):
    if USE_PDL:
        tl.extra.cuda.gdc_wait()
    # hc == 4: each t chunk is loaded ONCE and feeds the four group dots (the generic kernel reloads t per group);
    # groups are summed in order g = 0..3 like the compiled chain, so the result stays bitwise the same.
    pid = tl.program_id(0)
    offs_m = tl.arange(0, ROWS)
    mask_m = offs_m < M
    j = pid * BLOCK_J + tl.arange(0, BLOCK_J)
    mask_j = j < HS
    acc0 = tl.zeros((ROWS, BLOCK_J), dtype=tl.float32)
    acc1 = tl.zeros((ROWS, BLOCK_J), dtype=tl.float32)
    acc2 = tl.zeros((ROWS, BLOCK_J), dtype=tl.float32)
    acc3 = tl.zeros((ROWS, BLOCK_J), dtype=tl.float32)
    for r0 in range(0, N_PAD, BLOCK_R):
        r = r0 + tl.arange(0, BLOCK_R)
        mask_r = r < N
        a = tl.load(t_ptr + offs_m[:, None] * N + r[None, :], mask=mask_m[:, None] & mask_r[None, :], other=0.0)
        wm = mask_j[:, None] & mask_r[None, :]
        w0 = tl.load(w_ptr + (0 * HS + j)[:, None] * N + r[None, :], mask=wm, other=0.0)
        w1 = tl.load(w_ptr + (1 * HS + j)[:, None] * N + r[None, :], mask=wm, other=0.0)
        w2 = tl.load(w_ptr + (2 * HS + j)[:, None] * N + r[None, :], mask=wm, other=0.0)
        w3 = tl.load(w_ptr + (3 * HS + j)[:, None] * N + r[None, :], mask=wm, other=0.0)
        acc0 = tl.dot(a, tl.trans(w0), acc0)
        acc1 = tl.dot(a, tl.trans(w1), acc1)
        acc2 = tl.dot(a, tl.trans(w2), acc2)
        acc3 = tl.dot(a, tl.trans(w3), acc3)
    xm = mask_m[:, None] & mask_j[None, :]
    xb = x_ptr + offs_m[:, None] * (4 * HS) + j[None, :]
    out = tl.sigmoid(acc0.to(tl.bfloat16).to(tl.float32)) * tl.load(xb, mask=xm, other=0.0).to(tl.float32)
    out += tl.sigmoid(acc1.to(tl.bfloat16).to(tl.float32)) * tl.load(xb + HS, mask=xm, other=0.0).to(tl.float32)
    out += tl.sigmoid(acc2.to(tl.bfloat16).to(tl.float32)) * tl.load(xb + 2 * HS, mask=xm, other=0.0).to(tl.float32)
    out += tl.sigmoid(acc3.to(tl.bfloat16).to(tl.float32)) * tl.load(xb + 3 * HS, mask=xm, other=0.0).to(tl.float32)
    out = out / hc_f
    tl.store(out_ptr + offs_m[:, None] * HS + j[None, :], out.to(tl.bfloat16), mask=xm)


def _khc_mix_ok(x: torch.Tensor, w_down: torch.Tensor, w_up: torch.Tensor) -> bool:
    if _KHC_MIX_MAX_ROWS <= 16 or x.dim() != 2:
        return False
    rows, k = x.shape
    n = w_down.shape[0]
    return (
        17 <= rows <= _KHC_MIX_MAX_ROWS
        and x.is_cuda
        and x.dtype == torch.bfloat16
        and w_down.dtype == torch.bfloat16
        and w_up.dtype == torch.bfloat16
        and x.is_contiguous()
        and w_down.is_contiguous()
        and w_up.is_contiguous()
        and w_down.shape[1] == k
        and w_up.shape[0] == k
        and w_up.shape[1] == n
        and k % (_KHC_MIX_S * _KHC_MIX_BLOCK_K) == 0
        and n % _KHC_MIX_BLOCK_N == 0
    )


def _khc_fused_mix(x: torch.Tensor, w_down: torch.Tensor, w_up: torch.Tensor, hc: int, hs: int,
                   tactic: Optional[dict] = None) -> torch.Tensor:
    t_ = dict(_KHC_MIX_TACTIC, **(tactic or {}))
    S = t_.get("S", _KHC_MIX_S)
    bn = t_.get("BLOCK_N", _KHC_MIX_BLOCK_N)
    bk = t_.get("BLOCK_K", _KHC_MIX_BLOCK_K)
    bj = t_.get("BLOCK_J", _KHC_MIX_BLOCK_J)
    br = t_.get("BLOCK_R", _KHC_MIX_BLOCK_R)
    rows, k = x.shape
    n = w_down.shape[0]
    rows_pad = 32 if rows <= 32 else (64 if rows <= 64 else 128)
    key = (x.device, k, n, rows_pad, S)
    scratch = _khc_mix_scratch.get(key)
    if scratch is None:   # persistent per shape: CUDA graphs keep these pointers
        scratch = (torch.empty((S, rows_pad, n), dtype=torch.float32, device=x.device),
                   torch.empty((rows_pad, n), dtype=torch.bfloat16, device=x.device))
        _khc_mix_scratch[key] = scratch
    part, t = scratch
    out = torch.empty((rows, hs), dtype=x.dtype, device=x.device)
    stage = t_.get("stage", "all")   # tuning only: "down" / "reduce" / "up" run one kernel
    pdl = _kglue_mix_use_pdl()
    pk = {"launch_pdl": True} if pdl else {}
    fuse = stage == "all" and t_.get("fuse_reduce", _KGLUE_MIX_FUSE_REDUCE)
    if fuse:   # kglue: down + reduce in one launch (last CTA per N tile reduces in slice order)
        ckey = (x.device, n, bn, rows_pad, S)
        cnt = _kglue_mix_cnt.get(ckey)
        if cnt is None:   # first use is eager (the split check runs before capture): outside graph pools
            cnt = torch.zeros(n // bn, dtype=torch.int32, device=x.device)
            _kglue_mix_cnt[ckey] = cnt
        dw = t_.get("down_warps", 4)
        _kglue_mix_down_reduce_kernel[(n // bn, S)](
            x, w_down, part, cnt, t, rows, k, n, float(hc), K_PER_S=k // S, ROWS=rows_pad, BLOCK_N=bn,
            BLOCK_K=bk, NTHREADS=32 * dw, USE_PDL=pdl, num_warps=dw, num_stages=t_.get("down_stages", 3), **pk)
    if stage in ("all", "down") and not fuse:
        _khc_mix_down_kernel[(n // bn, S)](
            x, w_down, part, rows, k, n, K_PER_S=k // S, ROWS=rows_pad, BLOCK_N=bn, BLOCK_K=bk,
            USE_PDL=pdl, num_warps=t_.get("down_warps", 4), num_stages=t_.get("down_stages", 3), **pk)
    if stage in ("all", "reduce") and not fuse:
        _khc_mix_reduce_kernel[(triton.cdiv(rows * n, 256),)](
            part, t, rows, n, rows_pad * n, float(hc), S=S, BLOCK=256, USE_PDL=pdl, num_warps=4, **pk)
    if stage in ("all", "up") and hc == 4 and t_.get("up4", True):
        _khc_mix_up4_kernel[(triton.cdiv(hs, bj),)](
            t, w_up, x, out, rows, n, hs, float(hc), ROWS=rows_pad, BLOCK_J=bj, BLOCK_R=br,
            N_PAD=triton.cdiv(n, br) * br, USE_PDL=pdl, num_warps=t_.get("up_warps", 4),
            num_stages=t_.get("up_stages", 3), **pk)
    elif stage in ("all", "up"):
        _khc_mix_up_kernel[(triton.cdiv(hs, bj),)](
            t, w_up, x, out, rows, n, hs, float(hc), HC=hc, ROWS=rows_pad, BLOCK_J=bj, BLOCK_R=br,
            N_PAD=triton.cdiv(n, br) * br, USE_PDL=pdl, num_warps=t_.get("up_warps", 4),
            num_stages=t_.get("up_stages", 3), **pk)
    return out


# --- kglue (Kernel optimizations thread, 5-Oct-2026): HC combine apply + the NEXT mix's per-branch norm in one kernel.
# In decode every split combine (hc_combine_gate -> hc_combine_apply) is followed by the next HyperConnection's
# hc_norm (grouped_gemma_rmsnorm, one CTA per (row, branch)) on the residual it just wrote. kglue_hc_apply_norm_kernel
# runs one CTA per (row, branch) with the norm kernel's exact thread layout: each thread computes the combine for the
# 16 elements the norm kernel would load (same expression as hc_combine_apply_kernel), stores them, and then runs the
# norm kernel's own code on those bf16 values, so both outputs are bit-identical to the two kernels. One launch and
# one gap less per boundary. The combine learns its successor at runtime: a mix whose input IS the last combine's
# output links the two (eager warm-up runs before graph capture); the combine then hands the normed tensor to it.
# SGLANG_KGLUE_HCNORM=0 disables it.
_KGLUE_HCNORM = _khc_os.environ.get("SGLANG_KGLUE_HCNORM", "1") != "0"
_kglue_last_combine = None   # (weakref to the last split-combine output, its module)

_KGLUE_HCNORM_SRC = r"""
#include "__HC_COMBINE_CUH__"

namespace sglang {

struct KglueApplyNormParams {
  const void* block_output;
  const void* residual;
  const float* partials;
  const void* __restrict__ weight;
  void* output;
  void* normed;
  float eps;
};

template <int64_t kHcCount, int64_t kHiddenSize, bool kUsePDL, typename Float>
__global__ __launch_bounds__(kHiddenSize / 16) void kglue_hc_apply_norm_kernel(
    const KglueApplyNormParams __grid_constant__ params) {
  using namespace device;
  using Float2 = packed_t<Float>;
  // grouped_gemma_rmsnorm_kernel's layout, verbatim
#if SGL_ARCH_BLACKWELL_OR_GREATER
  using Storage = AlignedVector<Float2, 8>;
  constexpr uint32_t kNumLoads = 1;
#else
  using Storage = AlignedVector<Float2, 4>;
  constexpr uint32_t kNumLoads = 2;
#endif
  constexpr uint32_t kVecLen = kNumLoads == 1 ? 8 : 4;
  constexpr int64_t kGroupSize = kHiddenSize;
  constexpr auto kNumThreads = kGroupSize / 16;
  constexpr auto kNumWarps = kNumThreads / kWarpThreads;
  constexpr uint32_t kSplit = hc_combine_split_detail::kSplit;

  const uint32_t m = blockIdx.x;
  const uint32_t branch = blockIdx.y;
  const int64_t chunk = static_cast<int64_t>(m) * kHcCount + branch;  // the norm kernel's bid
  const auto gmem = tile::Memory<Storage>::cta(kNumThreads);
  __shared__ float smem[kWarpThreads];

  PDLWaitPrimary<kUsePDL>();

  // hc_combine_apply_kernel's gate, verbatim
  float total = 0.0f;
#pragma unroll
  for (uint32_t s = 0; s < kSplit; ++s) {
    total += params.partials[(static_cast<int64_t>(m) * kSplit + s) * kHcCount + branch];
  }
  const float a = 2.0f / (1.0f + math::exp(-total / kHcCount));

  const auto r_ptr = pointer::offset<Float>(params.residual, chunk * kGroupSize);
  const auto y_ptr = pointer::offset<Float>(params.block_output, static_cast<int64_t>(m) * kHiddenSize);
  const auto input_ptr = pointer::offset<Float>(params.output, chunk * kGroupSize);
  const auto output_ptr = pointer::offset<Float>(params.normed, chunk * kGroupSize);
  const auto weight_ptr = pointer::offset<Float>(params.weight, static_cast<int64_t>(branch) * kGroupSize);

  Storage input_vec[kNumLoads];
  Storage weight_vec[kNumLoads];
#pragma unroll
  for (uint32_t j = 0; j < kNumLoads; ++j) {
    const Storage r_vec = gmem.load(r_ptr, j);
    const Storage y_vec = gmem.load(y_ptr, j);
#pragma unroll
    for (uint32_t i = 0; i < kVecLen; ++i) {
      const auto [rx, ry] = cast<fp32x2_t>(r_vec[i]);
      const auto [yx, yy] = cast<fp32x2_t>(y_vec[i]);
      input_vec[j][i] = cast<Float2>(fp32x2_t{rx + a * yx, ry + a * yy});
    }
    gmem.store(input_ptr, input_vec[j], j);
    weight_vec[j] = gmem.load(weight_ptr, j);
  }

  // grouped_gemma_rmsnorm_kernel from here on, verbatim
  float sum_of_squares = 0.0f;
#pragma unroll
  for (uint32_t j = 0; j < kNumLoads; ++j) {
#pragma unroll
    for (uint32_t i = 0; i < kVecLen; ++i) {
      const auto [x, y] = cast<fp32x2_t>(input_vec[j][i]);
      sum_of_squares += x * x + y * y;
    }
  }

  sum_of_squares = warp::reduce_sum(sum_of_squares);
  float norm_factor;
  if constexpr (kNumWarps == 1) {
    norm_factor = math::rsqrt(sum_of_squares / kGroupSize + params.eps);
  } else {
    const auto warp_id = threadIdx.x / kWarpThreads;
    smem[warp_id] = sum_of_squares;
    __syncthreads();
    if (warp_id == 0) {
      const auto tx = threadIdx.x;
      const auto local_sum = tx < kNumWarps ? smem[tx] : 0.0f;
      sum_of_squares = warp::reduce_sum(local_sum);
      smem[tx] = math::rsqrt(sum_of_squares / kGroupSize + params.eps);
    }
    __syncthreads();
    norm_factor = smem[warp_id];
  }

#pragma unroll
  for (uint32_t j = 0; j < kNumLoads; ++j) {
    Storage output_vec;
#pragma unroll
    for (uint32_t i = 0; i < kVecLen; ++i) {
      const auto [ix, iy] = cast<fp32x2_t>(input_vec[j][i]);
      const auto [wx, wy] = cast<fp32x2_t>(weight_vec[j][i]);
      output_vec[i] = cast<Float2>(fp32x2_t{ix * norm_factor * (1.0f + wx), iy * norm_factor * (1.0f + wy)});
    }
    gmem.store(output_ptr, output_vec, j);
  }

  PDLTriggerSecondary<kUsePDL>();
}

template <int64_t kHcCount, int64_t kHiddenSize, bool kUsePDL, typename DType>
struct KglueHcCombineNormKernel {
  static_assert(sizeof(DType) == 2, "2-byte dtypes only");
  static_assert(kHiddenSize % 512 == 0, "norm group must be a multiple of 512");
  static constexpr auto gate_kernel = hc_combine_gate_kernel<kHcCount, kHiddenSize, kUsePDL, DType>;
  static constexpr auto apply_norm_kernel = kglue_hc_apply_norm_kernel<kHcCount, kHiddenSize, kUsePDL, DType>;

  static void
  run(const tvm::ffi::TensorView block_output,
      const tvm::ffi::TensorView residual,
      const tvm::ffi::TensorView normed_residual,
      const tvm::ffi::TensorView inject_weight,
      const tvm::ffi::TensorView norm_weight,
      const tvm::ffi::TensorView output,
      const tvm::ffi::TensorView normed,
      const tvm::ffi::TensorView partials,
      float eps) {
    using namespace host;
    using namespace hc_combine_split_detail;
    auto M = SymbolicSize{"num_tokens"};
    auto device = SymbolicDevice{};
    device.set_options<kDLCUDA>();
    TensorMatcher({M, kHiddenSize}).with_dtype<DType>().with_device(device).verify(block_output);
    TensorMatcher({M, kHcCount * kHiddenSize})
        .with_dtype<DType>()
        .with_device(device)
        .verify(residual)
        .verify(normed_residual)
        .verify(output)
        .verify(normed);
    TensorMatcher({kHcCount, kHcCount * kHiddenSize}).with_dtype<DType>().with_device(device).verify(inject_weight);
    TensorMatcher({kHcCount * kHiddenSize}).with_dtype<DType>().with_device(device).verify(norm_weight);
    auto part_rows = SymbolicSize{"partial_rows"};
    TensorMatcher({part_rows, kSplit, kHcCount}).with_dtype<fp32_t>().with_device(device).verify(partials);

    const auto gp = HcCombineSplitParams{
        .block_output = block_output.data_ptr(),
        .residual = residual.data_ptr(),
        .normed_residual = normed_residual.data_ptr(),
        .inject_weight = inject_weight.data_ptr(),
        .output = output.data_ptr(),
        .partials = static_cast<float*>(partials.data_ptr()),
    };
    const auto np = KglueApplyNormParams{
        .block_output = block_output.data_ptr(),
        .residual = residual.data_ptr(),
        .partials = static_cast<const float*>(partials.data_ptr()),
        .weight = norm_weight.data_ptr(),
        .output = output.data_ptr(),
        .normed = normed.data_ptr(),
        .eps = eps,
    };
    const auto num_tokens = static_cast<uint32_t>(M.unwrap());
    LaunchKernel(dim3(num_tokens, kSplit * kHcCount, 1), kGateThreads, device.unwrap())
        .enable_pdl(kUsePDL)(gate_kernel, gp);
    LaunchKernel(dim3(num_tokens, kHcCount, 1), static_cast<uint32_t>(kHiddenSize / 16), device.unwrap())
        .enable_pdl(kUsePDL)(apply_norm_kernel, np);
  }
};

}  // namespace sglang
"""
_kglue_hcnorm_modules = {}


def _kglue_hcnorm_module(hc: int, hs: int, dtype: torch.dtype):
    key = (hc, hs, dtype)
    mod = _kglue_hcnorm_modules.get(key)
    if mod is None:
        import hashlib
        import tempfile
        from pathlib import Path

        import sglang.kernels.jit.utils as _jit_utils
        from sglang.kernels.jit.utils import is_arch_support_pdl, load_jit, make_cpp_args

        inc = Path(_jit_utils.__file__).resolve().parent.parent / "csrc" / "elementwise" / "hc_combine.cuh"
        src = _KGLUE_HCNORM_SRC.replace("__HC_COMBINE_CUH__", inc.as_posix())
        d = Path(tempfile.gettempdir()) / "kglue_jit"
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"hc_apply_norm_{hashlib.sha256(src.encode()).hexdigest()[:12]}.cuh"
        if not f.exists():
            tmp = f.with_suffix(f".{_khc_os.getpid()}.tmp")
            tmp.write_text(src, encoding="utf-8")
            _khc_os.replace(tmp, f)
        args = make_cpp_args(hc, hs, is_arch_support_pdl(), dtype)
        mod = load_jit("kglue_hc_apply_norm", *args, cuda_files=[str(f)],
                       cuda_wrappers=[("run", f"KglueHcCombineNormKernel<{args}>::run")])
        _kglue_hcnorm_modules[key] = mod
    return mod


def kglue_hc_combine_norm(block_output, residual, normed_residual, inject_weight, norm_weight, eps, hc, hs):
    """hc_combine_split + grouped_gemma_rmsnorm(out, norm_weight, hs, eps): two launches (gate, apply + norm)."""
    from sglang.kernels.ops.elementwise import hc_combine as _hc_mod

    y = block_output.reshape(-1, hs)
    r = residual.reshape(-1, hc * hs)
    n = normed_residual.reshape(-1, hc * hs)
    out = torch.empty_like(r)
    normed = torch.empty_like(r)
    rows = r.shape[0]
    if _hc_mod._MAX_ROWS < _KHC_SPLIT_MAX_ROWS:
        _hc_mod._MAX_ROWS = _KHC_SPLIT_MAX_ROWS
    partials = _hc_mod._get_partials(hc, r.device, rows)[:rows]
    _kglue_hcnorm_module(hc, hs, r.dtype).run(y, r, n, inject_weight, norm_weight, out, normed, partials, float(eps))
    return out.reshape(residual.shape), normed.reshape(residual.shape)



@triton.jit
def _kglue_mix_down_reduce_kernel(x_ptr, w_ptr, part_ptr, cnt_ptr, t_ptr, M, K, N, hc_f,
                                  K_PER_S: tl.constexpr, ROWS: tl.constexpr, BLOCK_N: tl.constexpr,
                                  BLOCK_K: tl.constexpr, NTHREADS: tl.constexpr, USE_PDL: tl.constexpr = False):
    # kglue (5-Oct-2026): _khc_mix_down_kernel + _khc_mix_reduce_kernel in one launch. Every CTA stores its slice's
    # fp32 partial exactly as the down kernel; the LAST CTA to arrive on an N tile (arrival counter, kfast's fence
    # pattern) sums the S partials in slice order 0..S-1 from zero and applies the reduce kernel's expressions, so
    # every byte of t equals the two-kernel path. The counter is reset by that CTA (CUDA-graph safe).
    if USE_PDL:
        tl.extra.cuda.gdc_wait()
    pid_n = tl.program_id(0)
    pid_s = tl.program_id(1)
    n_split = tl.num_programs(1)
    offs_m = tl.arange(0, ROWS)
    offs_n = pid_n * BLOCK_N + tl.arange(0, BLOCK_N)
    mask_m = offs_m < M
    mask_n = offs_n < N
    acc = tl.zeros((ROWS, BLOCK_N), dtype=tl.float32)
    k0 = pid_s * K_PER_S
    for kk in range(0, K_PER_S, BLOCK_K):
        k = k0 + kk + tl.arange(0, BLOCK_K)
        xt = tl.load(x_ptr + offs_m[:, None] * K + k[None, :], mask=mask_m[:, None], other=0.0)
        w = tl.load(w_ptr + offs_n[:, None] * K + k[None, :], mask=mask_n[:, None], other=0.0)
        acc = tl.dot(xt, tl.trans(w), acc)
    p = part_ptr + (pid_s * ROWS + offs_m[:, None]) * N + offs_n[None, :]
    tl.store(p, acc, mask=mask_n[None, :], cache_modifier=".cg")
    _f = tl.inline_asm_elementwise("fence.acq_rel.gpu;\n\tmov.u32 $0, $1;", "=r,r", [tl.arange(0, NTHREADS)],
                                   dtype=tl.int32, is_pure=False, pack=1)
    tl.debug_barrier()
    arrived = tl.atomic_add(cnt_ptr + pid_n, 1, sem="acq_rel", scope="gpu")
    if arrived == n_split - 1:
        _g = tl.inline_asm_elementwise("fence.acq_rel.gpu;\n\tmov.u32 $0, $1;", "=r,r", [tl.arange(0, NTHREADS)],
                                       dtype=tl.int32, is_pure=False, pack=1)
        tot = tl.zeros((ROWS, BLOCK_N), dtype=tl.float32)
        for s in range(0, n_split):
            tot += tl.load(part_ptr + (s * ROWS + offs_m[:, None]) * N + offs_n[None, :], mask=mask_n[None, :],
                           other=0.0, cache_modifier=".cg")
        y = tot.to(tl.bfloat16).to(tl.float32) / hc_f
        t = y * tl.sigmoid(y)
        tl.store(t_ptr + offs_m[:, None] * N + offs_n[None, :], t.to(tl.bfloat16),
                 mask=mask_m[:, None] & mask_n[None, :])
        tl.atomic_xchg(cnt_ptr + pid_n, 0, sem="relaxed", scope="gpu")


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
    """kglue: the split for which the fused mix is bit-identical to mod._mix_compute at this shape, else None."""
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
    with torch.no_grad():
        refs = [(F.linear(xx, w_down), mod._mix_compute(xx, w_down, w_up, hc, hs).to(torch.bfloat16)) for xx in xs]
        pick = None
        for S in _KGLUE_MIX_CANDIDATES:
            if k % S or (k // S) % _KHC_MIX_BLOCK_K:
                continue
            ok = True
            for xx, (d_ref, o_ref) in zip(xs, refs):
                _khc_fused_mix(xx, w_down, w_up, hc, hs, dict(S=S, stage="down"))
                part = _khc_mix_scratch[(xx.device, k, n, rows_pad, S)][0]
                tot = part[0, :m].clone()
                for s in range(1, S):
                    tot += part[s, :m]
                out = _khc_fused_mix(xx, w_down, w_up, hc, hs, dict(_KGLUE_MIX_TACTIC_S20, S=S))
                ok = ok and torch.equal(tot.to(torch.bfloat16), d_ref) and torch.equal(out, o_ref)
                if not ok:
                    break
            if ok:
                pick = S
                break
    _kglue_mix_split[key] = pick
    return pick


class HyperConnectionConfig(msgspec.Struct, frozen=True):
    hc_count: int = 4
    hidden_size: int = 64
    params_dtype: torch.dtype = torch.bfloat16
    mtp_hc: bool = False
    hc_lowrank: int = 16
    rms_norm_eps: float = 1e-6
    hc_per_branch_norm: bool = False


class GroupedGemmaRMSNorm(nn.Module):
    def __init__(
        self, hidden_size: int, eps: float = 1e-6, group_size: Optional[int] = None
    ):
        super().__init__()
        if group_size is not None and hidden_size % group_size != 0:
            raise ValueError(
                f"hidden_size ({hidden_size}) must be divisible by group_size ({group_size})"
            )
        self.weight = nn.Parameter(torch.zeros(hidden_size))
        self.variance_epsilon = eps
        self.group_size = group_size
        self.weight.weight_loader = self._weight_loader
        # The JIT kernel requires group_size to be a multiple of 512; this is
        # init-static, so resolve it once here (device/dtype stay per-call).
        effective_group_size = group_size if group_size is not None else hidden_size
        self._jit_group_size = (
            effective_group_size if effective_group_size % 512 == 0 else None
        )

    def _weight_loader(self, param: torch.Tensor, loaded_weight: torch.Tensor) -> None:
        assert param.size() == loaded_weight.size()
        param.data.copy_(loaded_weight)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if (
            self._jit_group_size is not None
            and x.is_cuda
            and x.dtype in (torch.bfloat16, torch.float16)
        ):
            from sglang.kernels.ops.layernorm.grouped_gemma_rmsnorm import (
                grouped_gemma_rmsnorm,
            )

            return grouped_gemma_rmsnorm(
                x, self.weight, self._jit_group_size, self.variance_epsilon
            )
        input_dtype = x.dtype
        x_float = x.float()
        if self.group_size is None:
            variance = x_float.pow(2).mean(dim=-1, keepdim=True)
            x_norm = x_float * torch.rsqrt(variance + self.variance_epsilon)
        else:
            x_grouped = x_float.reshape(
                *x_float.shape[:-1],
                x_float.shape[-1] // self.group_size,
                self.group_size,
            )
            variance = x_grouped.pow(2).mean(dim=-1, keepdim=True)
            x_norm = (
                x_grouped * torch.rsqrt(variance + self.variance_epsilon)
            ).flatten(-2)
        return (x_norm * (1.0 + self.weight.float())).to(input_dtype)


class HyperConnectionBase(nn.Module):
    def __init__(
        self,
        config: HyperConnectionConfig,
        use_mix: bool = True,
        use_combine: bool = True,
        role: Optional[str] = None,
    ):
        super().__init__()

        self.config = config
        self.hc_count = config.hc_count
        if config.mtp_hc and role is not None and "mtp" in role:
            self.hc_count = self.hc_count + 1
        self.hidden_size = config.hidden_size
        self.params_dtype = config.params_dtype

    def mix(self, hyper_input: torch.Tensor):
        assert hyper_input.shape[-1] == self.hc_count * self.hidden_size
        mixed_input = hyper_input.view(
            *hyper_input.shape[:-1], self.hc_count, self.hidden_size
        ).mean(dim=-2)
        return mixed_input, hyper_input

    def combine(
        self, block_output: torch.Tensor, residual: torch.Tensor
    ) -> torch.Tensor:
        assert residual.shape[-1] == self.hc_count * self.hidden_size
        assert block_output.shape[-1] == self.hidden_size
        residual_reshaped = residual.view(
            *residual.shape[:-1], self.hc_count, self.hidden_size
        )
        combined_output = residual_reshaped + block_output.unsqueeze(-2)
        combined_output = combined_output.view(
            *residual.shape[:-1], self.hc_count * self.hidden_size
        )
        return combined_output


class GatedResidual(HyperConnectionBase):
    def __init__(
        self,
        config: HyperConnectionConfig,
        use_mix: bool = True,
        use_combine: bool = True,
        role: Optional[str] = None,
        online_fp8: bool = False,
    ):
        super().__init__(config, use_mix, use_combine, role)

        norm_dim = (
            self.config.hidden_size * self.hc_count
            if self.config.hc_per_branch_norm
            else self.config.hidden_size
        )
        norm_group_size = (
            self.config.hidden_size if self.config.hc_per_branch_norm else None
        )
        self.hc_norm = GroupedGemmaRMSNorm(
            norm_dim, eps=self.config.rms_norm_eps, group_size=norm_group_size
        )

        # kglue: successor link (learned at runtime) and the hand-off slot it fills
        self._kglue_next = None
        self._kglue_prenormed = None

        if use_mix:
            from sglang.kernels.ops.gemm.sm120_online_fp8 import (
                attach_rowwise_ingest,
                online_fp8_enabled,
            )

            rowwise_mix = online_fp8 and online_fp8_enabled()
            self._online_fp8_mix = rowwise_mix
            self.input_mix_weight_down = nn.Linear(
                self.hidden_size * self.hc_count,
                self.config.hc_lowrank,
                bias=False,
                device="meta" if rowwise_mix else torch.cuda.current_device(),
                dtype=config.params_dtype,
            )
            self.input_mix_weight_up = nn.Linear(
                self.config.hc_lowrank,
                self.hc_count * self.hidden_size,
                bias=False,
                device="meta" if rowwise_mix else torch.cuda.current_device(),
                dtype=config.params_dtype,
            )
            if rowwise_mix:
                # Quantize checkpoint shards before they enter device memory;
                # the resident Parameter remains paired with its row scales.
                attach_rowwise_ingest(
                    [self.input_mix_weight_down, self.input_mix_weight_up]
                )
            from sglang.srt.environ import envs

            lowrank = self.config.hc_lowrank
            self._jit_mix_ok = (
                envs.SGLANG_HC_MIX_CUDA.get()
                and torch.cuda.is_available()
                # The CuTe split-K pair is tcgen05 (sm_100 family) only; the
                # default-on env must not route Hopper/Ada to it.
                and torch.cuda.get_device_capability()[0] == 10
                and (self.hc_count * self.hidden_size) % 2048 == 0
                and self.hidden_size % 8 == 0
                and lowrank > 0
                and lowrank % 8 == 0
            )
            self._mix_up_weight_padded = None

        if use_combine:
            self.block_inject_weight = nn.Linear(
                self.hidden_size * self.hc_count,
                self.hc_count,
                bias=False,
                device=torch.cuda.current_device(),
                dtype=config.params_dtype,
            )
            # The JIT combine kernel requires hidden_size % 8 == 0 and
            # hc_count * hidden_size % 2048 == 0; this is init-static, so
            # resolve it once here (device/dtype stay per-call).
            self._jit_combine_ok = (
                self.hidden_size % 8 == 0
                and (self.hc_count * self.hidden_size) % 2048 == 0
            )
            from sglang.srt.environ import envs

            vecs = self.hc_count * self.hidden_size // 8
            self._split_combine_ok = (
                envs.SGLANG_HC_COMBINE_SPLIT.get()
                and self._jit_combine_ok
                and vecs % (8 * 160) == 0
                and (self.hidden_size // 8) % (vecs // 8) == 0
            )

        def _mix_compute(
            hyper_input_normed: torch.Tensor,
            input_mix_weight_down: torch.Tensor,
            input_mix_weight_up: torch.Tensor,
            hc: int,
            hs: int,
        ) -> torch.Tensor:
            input_mix_weight = F.silu(
                F.linear(hyper_input_normed, input_mix_weight_down) / hc
            )
            input_mix_weight = F.linear(input_mix_weight, input_mix_weight_up)
            input_mix_weight = torch.sigmoid(input_mix_weight)
            input_mix_weight = input_mix_weight.unflatten(-1, (hc, hs))
            output = (
                input_mix_weight * hyper_input_normed.unflatten(-1, (hc, hs))
            ).mean(dim=-2)
            return output

        def _combine_compute(
            block_output: torch.Tensor,
            residual: torch.Tensor,
            normed_residual: torch.Tensor,
            block_inject_weight: torch.Tensor,
            hc: int,
            hs: int,
        ) -> torch.Tensor:
            R = residual.unflatten(-1, (hc, hs))
            block_inject_weight_out = 2 * torch.sigmoid(
                F.linear(normed_residual, block_inject_weight) / hc
            )
            injection = block_output.unsqueeze(-2) * block_inject_weight_out.unsqueeze(
                -1
            )
            return (R + injection).flatten(-2)

        self._mix_compute = torch.compile(_mix_compute)
        self._combine_compute = torch.compile(_combine_compute)

    def _kglue_can_prenorm(self, prev) -> bool:
        """kglue: may `prev`'s split combine also produce this module's hc_norm output? (per-branch JIT norm only)"""
        w = self.hc_norm.weight
        return (
            _KGLUE_HCNORM
            and self.config.hc_per_branch_norm
            and isinstance(self.hc_norm, GroupedGemmaRMSNorm)
            and self.hc_norm._jit_group_size == self.hidden_size
            and self.hc_norm.group_size == self.hidden_size
            and self.hidden_size % 512 == 0
            and prev.hc_count == self.hc_count
            and prev.hidden_size == self.hidden_size
            and w.is_cuda
            and w.dtype == prev.block_inject_weight.weight.dtype
            and w.dtype in (torch.bfloat16, torch.float16)
            and w.numel() == self.hc_count * self.hidden_size
            and w.is_contiguous()
        )

    def mix(self, hyper_input: torch.Tensor):
        assert hyper_input.shape[-1] == self.hc_count * self.hidden_size
        if hyper_input.shape[0] == 0:
            mixed_input = hyper_input.new_empty(
                (*hyper_input.shape[:-1], self.hidden_size), dtype=self.params_dtype
            )
            return mixed_input, (hyper_input, hyper_input)

        global _kglue_last_combine
        pre, self._kglue_prenormed = self._kglue_prenormed, None
        last, _kglue_last_combine = _kglue_last_combine, None
        if pre is not None and pre[0]() is hyper_input:
            hyper_input_normed = pre[1]   # kglue: normed by the previous combine's kernel (bit-identical)
        elif self.config.hc_per_branch_norm:
            if (last is not None and last[1]._kglue_next is None and last[0]() is hyper_input
                    and self._kglue_can_prenorm(last[1])):
                last[1]._kglue_next = self   # kglue: learn the successor; fused from the next forward on
            hyper_input_normed = self.hc_norm(hyper_input)
        else:
            hyper_input_normed = self.hc_norm(
                hyper_input.unflatten(-1, (self.hc_count, self.hidden_size))
            ).flatten(-2)
        if (
            self._jit_mix_ok
            and hyper_input_normed.is_cuda
            and hyper_input_normed.dtype in (torch.bfloat16, torch.float16)
            and hyper_input_normed.shape[0] <= 24
        ):
            from sglang.kernels.ops.elementwise.hc_mix import (
                hc_mix,
                permute_pad_up_weight,
            )

            if self._mix_up_weight_padded is None:
                self._mix_up_weight_padded = permute_pad_up_weight(
                    self.input_mix_weight_up.weight, self.hc_count
                )
            mixed_input = hc_mix(
                hyper_input_normed,
                self.input_mix_weight_down.weight.data,
                self._mix_up_weight_padded,
                self.hc_count,
                self.hidden_size,
            ).to(self.params_dtype)
        elif fused_hc_mix_supported(
            hyper_input_normed,
            self.input_mix_weight_down.weight,
            self.input_mix_weight_up.weight,
        ):
            mixed_input = fused_hc_mix(
                hyper_input_normed,
                self.input_mix_weight_down.weight,
                self.input_mix_weight_up.weight,
                self.hc_count,
                self.hidden_size,
            ).to(self.params_dtype)
        elif self.hc_count == 4 and _khc_mix_ok(   # the up4 kernel; hc 5 (MTP) keeps the compiled chain
            hyper_input_normed,
            self.input_mix_weight_down.weight,
            self.input_mix_weight_up.weight,
        ) and (
            not _KGLUE_MIX_EXACT
            or _kglue_mix_pick(self, hyper_input_normed, self.input_mix_weight_down.weight,
                               self.input_mix_weight_up.weight, self.hc_count, self.hidden_size) is not None
        ):
            split = (_kglue_mix_split.get((hyper_input_normed.shape[1], self.input_mix_weight_down.weight.shape[0],
                                           self.hc_count, hyper_input_normed.shape[0]))
                     if _KGLUE_MIX_EXACT else None)
            mixed_input = _khc_fused_mix(
                hyper_input_normed,
                self.input_mix_weight_down.weight,
                self.input_mix_weight_up.weight,
                self.hc_count,
                self.hidden_size,
                dict(_KGLUE_MIX_TACTIC_S20, S=split) if split else None,
            ).to(self.params_dtype)
        else:
            down_weight = self.input_mix_weight_down.weight
            up_weight = self.input_mix_weight_up.weight
            if (
                down_weight.dtype == torch.float8_e4m3fn
                or up_weight.dtype == torch.float8_e4m3fn
            ):
                from sglang.kernels.ops.gemm.sm120_online_fp8 import (
                    dequantize_rowwise_weight,
                )

                # Prefill/deterministic execution uses the compiled BF16 path.
                # Materialize only transient BF16 operands from resident FP8.
                down_weight = dequantize_rowwise_weight(
                    down_weight, hyper_input_normed.dtype
                )
                up_weight = dequantize_rowwise_weight(
                    up_weight, hyper_input_normed.dtype
                )
            mixed_input = self._mix_compute(
                hyper_input_normed,
                down_weight,
                up_weight,
                self.hc_count,
                self.hidden_size,
            ).to(self.params_dtype)
        return mixed_input, (hyper_input, hyper_input_normed)

    def combine(self, block_output: torch.Tensor, residuals) -> torch.Tensor:
        hyper_input, hyper_input_normed = residuals
        assert hyper_input.shape[-1] == self.hc_count * self.hidden_size
        assert block_output.shape[-1] == self.hidden_size
        if block_output.shape[0] == 0:
            return hyper_input.to(self.params_dtype)

        if (
            self._jit_combine_ok
            and block_output.is_cuda
            and block_output.dtype in (torch.bfloat16, torch.float16)
            and hyper_input.dtype == block_output.dtype
            and hyper_input_normed.dtype == block_output.dtype
            and self.block_inject_weight.weight.dtype == block_output.dtype
        ):
            if self._split_combine_ok and block_output.shape[0] <= _KHC_SPLIT_MAX_ROWS:
                from sglang.kernels.ops.elementwise import hc_combine as _khc_hc_mod
                from sglang.kernels.ops.elementwise.hc_combine import (
                    hc_combine_split,
                )

                # khc: size the shared fp32 partials buffer for the full cap on first use. It is reallocated only
                # when too small, and a CUDA graph captured against an older (smaller) buffer would keep its stale
                # pointer; his 32-row default covered every call while the cap was 32.
                if _khc_hc_mod._MAX_ROWS < _KHC_SPLIT_MAX_ROWS:
                    _khc_hc_mod._MAX_ROWS = _KHC_SPLIT_MAX_ROWS

                global _kglue_last_combine
                nxt = self._kglue_next
                if nxt is not None and _KGLUE_HCNORM:
                    out, normed = kglue_hc_combine_norm(
                        block_output,
                        hyper_input,
                        hyper_input_normed,
                        self.block_inject_weight.weight.data,
                        nxt.hc_norm.weight.data,
                        nxt.hc_norm.variance_epsilon,
                        self.hc_count,
                        self.hidden_size,
                    )
                    nxt._kglue_prenormed = (_kglue_weakref.ref(out), normed)
                else:
                    out = hc_combine_split(
                        block_output,
                        hyper_input,
                        hyper_input_normed,
                        self.block_inject_weight.weight.data,
                        self.hc_count,
                        self.hidden_size,
                    )
                if _KGLUE_HCNORM:
                    _kglue_last_combine = (_kglue_weakref.ref(out), self)
                return out
            from sglang.kernels.ops.elementwise.hc_combine import hc_combine

            return hc_combine(
                block_output,
                hyper_input,
                hyper_input_normed,
                self.block_inject_weight.weight,
                self.hc_count,
                self.hidden_size,
            )

        updated_residuals = self._combine_compute(
            block_output,
            hyper_input,
            hyper_input_normed,
            self.block_inject_weight.weight,
            self.hc_count,
            self.hidden_size,
        ).to(self.params_dtype)
        return updated_residuals


HYPERCONNECTION_CLASS_DICT = {
    "hyperconnection_average": HyperConnectionBase,
    "gated_residual_simple": GatedResidual,
}

"""Source text of the kglue additions to hyperconnection.py (5-Oct-2026, Kernel optimizations thread).
apply_hc.py inserts BLOCK into the khc patched file; kept separate so the edit is reproducible."""

BLOCK = r'''

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

'''

INIT_ADD = '''
        # kglue: successor link (learned at runtime) and the hand-off slot it fills
        self._kglue_next = None
        self._kglue_prenormed = None
'''

MIX_OLD = '''        if self.config.hc_per_branch_norm:
            hyper_input_normed = self.hc_norm(hyper_input)
        else:'''

MIX_NEW = '''        global _kglue_last_combine
        pre, self._kglue_prenormed = self._kglue_prenormed, None
        last, _kglue_last_combine = _kglue_last_combine, None
        if pre is not None and pre[0]() is hyper_input:
            hyper_input_normed = pre[1]   # kglue: normed by the previous combine's kernel (bit-identical)
        elif self.config.hc_per_branch_norm:
            if (last is not None and last[1]._kglue_next is None and last[0]() is hyper_input
                    and self._kglue_can_prenorm(last[1])):
                last[1]._kglue_next = self   # kglue: learn the successor; fused from the next forward on
            hyper_input_normed = self.hc_norm(hyper_input)
        else:'''

COMBINE_OLD = '''                return hc_combine_split(
                    block_output,
                    hyper_input,
                    hyper_input_normed,
                    self.block_inject_weight.weight.data,
                    self.hc_count,
                    self.hidden_size,
                )'''

COMBINE_NEW = '''                global _kglue_last_combine
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
                return out'''

CAN_PRENORM = '''
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
        if hyper_input.shape[0] == 0:'''

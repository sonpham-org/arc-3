import os as _khc_os
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
# Default OFF (4-Oct, daniel-bench-khcmix3-1004): bit-identical to the compiled chain but not faster at the first
# tactic (20.0 vs 19.4 us cold at 40 rows); SGLANG_KHC_MIX_MAX_ROWS=64 turns it on for tests.
_KHC_MIX_MAX_ROWS = int(_khc_os.environ.get("SGLANG_KHC_MIX_MAX_ROWS", "0"))
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
                         BLOCK_N: tl.constexpr, BLOCK_K: tl.constexpr):
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
                           BLOCK: tl.constexpr):
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
                       BLOCK_R: tl.constexpr, N_PAD: tl.constexpr):
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
                        ROWS: tl.constexpr, BLOCK_J: tl.constexpr, BLOCK_R: tl.constexpr, N_PAD: tl.constexpr):
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
    if stage in ("all", "down"):
        _khc_mix_down_kernel[(n // bn, S)](
            x, w_down, part, rows, k, n, K_PER_S=k // S, ROWS=rows_pad, BLOCK_N=bn, BLOCK_K=bk,
            num_warps=t_.get("down_warps", 4), num_stages=t_.get("down_stages", 3))
    if stage in ("all", "reduce"):
        _khc_mix_reduce_kernel[(triton.cdiv(rows * n, 256),)](
            part, t, rows, n, rows_pad * n, float(hc), S=S, BLOCK=256, num_warps=4)
    if stage in ("all", "up") and hc == 4 and t_.get("up4", True):
        _khc_mix_up4_kernel[(triton.cdiv(hs, bj),)](
            t, w_up, x, out, rows, n, hs, float(hc), ROWS=rows_pad, BLOCK_J=bj, BLOCK_R=br,
            N_PAD=triton.cdiv(n, br) * br, num_warps=t_.get("up_warps", 4), num_stages=t_.get("up_stages", 3))
    elif stage in ("all", "up"):
        _khc_mix_up_kernel[(triton.cdiv(hs, bj),)](
            t, w_up, x, out, rows, n, hs, float(hc), HC=hc, ROWS=rows_pad, BLOCK_J=bj, BLOCK_R=br,
            N_PAD=triton.cdiv(n, br) * br, num_warps=t_.get("up_warps", 4), num_stages=t_.get("up_stages", 3))
    return out


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

    def mix(self, hyper_input: torch.Tensor):
        assert hyper_input.shape[-1] == self.hc_count * self.hidden_size
        if hyper_input.shape[0] == 0:
            mixed_input = hyper_input.new_empty(
                (*hyper_input.shape[:-1], self.hidden_size), dtype=self.params_dtype
            )
            return mixed_input, (hyper_input, hyper_input)

        if self.config.hc_per_branch_norm:
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
        ):
            mixed_input = _khc_fused_mix(
                hyper_input_normed,
                self.input_mix_weight_down.weight,
                self.input_mix_weight_up.weight,
                self.hc_count,
                self.hidden_size,
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

                return hc_combine_split(
                    block_output,
                    hyper_input,
                    hyper_input_normed,
                    self.block_inject_weight.weight.data,
                    self.hc_count,
                    self.hidden_size,
                )
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

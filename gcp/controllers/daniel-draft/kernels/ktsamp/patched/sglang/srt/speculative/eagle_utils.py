from __future__ import annotations

import logging
import math
from enum import IntEnum
from typing import TYPE_CHECKING, List, Optional, Tuple

import torch

from sglang.kernels.ops.speculative.spec_tree import (
    sgl_build_tree_kernel_efficient_triton,
    verify_tree_greedy_kernel_triton,
)
from sglang.srt.hardware_backend.npu.dsv4.dsv4_common_hooks import (
    maybe_build_dsv4_verify_bundle,
)
from sglang.srt.mem_cache.allocation import alloc_for_spec_decode
from sglang.srt.mem_cache.allocation_sizing import (
    get_alloc_reserve_per_decode,
    page_aligned_decode_alloc_lens,
)
from sglang.srt.model_executor.runner_utils.pool import borrow_graph_pool
from sglang.srt.runtime_context import get_parallel, get_spec
from sglang.srt.utils import (
    is_cpu,
    is_cuda,
    is_hip,
    is_musa,
    is_npu,
    is_xpu,
)
from sglang.srt.utils.async_probe import maybe_detect_oob

if TYPE_CHECKING:
    from sglang.srt.constrained.base_grammar_backend import GrammarMask
    from sglang.srt.layers.logits_processor import LogitsProcessorOutput
    from sglang.srt.managers.schedule_batch import ScheduleBatch
    from sglang.srt.managers.tp_worker import TpModelWorker
    from sglang.srt.mem_cache.memory_pool import ReqToTokenPool
    from sglang.srt.model_executor.model_runner import ModelRunner
    from sglang.srt.sampling.sampling_batch_info import SamplingBatchInfo
    from sglang.srt.speculative.eagle_info import EagleVerifyInput

_is_cuda = is_cuda()
_is_hip = is_hip()
_is_npu = is_npu()
_is_musa = is_musa()
_is_xpu = is_xpu()
_is_cpu = is_cpu()

logger = logging.getLogger(__name__)

if _is_cuda or _is_hip or _is_musa:
    from sgl_kernel import (
        build_tree_kernel_efficient as sgl_build_tree_kernel_efficient,
    )
elif _is_cpu:
    from sgl_kernel import (
        build_tree_kernel_efficient_cpu as sgl_build_tree_kernel_efficient_cpu,
    )
    from sgl_kernel import verify_tree_greedy_cpu as sgl_verify_tree_greedy_cpu


def per_step_draft_out_cache_loc(
    out_cache_loc: torch.Tensor,
    batch_size: int,
    topk: int,
    num_steps: int,
) -> torch.Tensor:
    """Per-step slice of the multi-step EAGLE draft out_cache_loc buffer.

    Single source of truth for the layout shared by EagleWorkerV2.draft_forward
    (per-step write target) and DeepseekV4AttnBackend (per-step compression
    write target baked into metadata).
    """
    expected = batch_size * topk * num_steps
    assert out_cache_loc.shape[0] == expected, (
        f"out_cache_loc.shape[0]={out_cache_loc.shape[0]} != "
        f"batch_size * topk * num_steps = {batch_size}*{topk}*{num_steps}={expected}"
    )
    return (
        out_cache_loc.view(batch_size, topk, num_steps)
        .permute(2, 0, 1)
        .reshape(num_steps, -1)
    )


def _eagle_prefill_tail_tokens(
    batch: ScheduleBatch, next_token_ids: torch.Tensor
) -> torch.Tensor:
    """Per-seq tail token for EAGLE prefill rotation; uses next prompt token for
    non-final chunks (chunked-prefill chain consistency, see PR #26329)."""
    tail_tokens = next_token_ids.to(batch.input_ids.dtype)
    next_prompt_token = batch.chunked_req_next_prompt_token
    if next_prompt_token is not None:
        for i, r in enumerate(batch.reqs):
            if r is batch.chunked_req:
                tail_tokens = tail_tokens.clone()
                # Keep the scalar as a kernel argument. Assigning a Python scalar
                # through scalar indexing issues a pageable H2D copy and
                # synchronizes the current CUDA stream before draft extend.
                tail_tokens[i : i + 1].fill_(next_prompt_token)
                break
    return tail_tokens


def organize_draft_results(
    score_list: List[torch.Tensor],
    token_list: List[torch.Tensor],
    parents_list: List[torch.Tensor],
    num_draft_token: int,
):
    # b, n, topk; n = 1 + (num_steps-1) * topk
    score_list = torch.cat(score_list, dim=1).flatten(1)
    # b, (topk + (num_steps-1) * topk)
    ss_token_list = torch.cat(token_list, dim=1)
    top_scores = torch.topk(score_list, num_draft_token - 1, dim=-1)
    top_scores_index = top_scores.indices
    top_scores_index = torch.sort(top_scores_index).values
    maybe_detect_oob(
        top_scores_index,
        0,
        ss_token_list.shape[1],
        "organize_draft_results: top_scores_index OOB for gather on ss_token_list",
    )
    draft_tokens = torch.gather(ss_token_list, index=top_scores_index, dim=1)

    if len(parents_list) > 1:
        parent_list = torch.cat(parents_list[:-1], dim=1)
    else:
        batch_size = parents_list[0].shape[0]
        parent_list = torch.empty(
            batch_size, 0, dtype=torch.long, device=parents_list[0].device
        )

    return parent_list, top_scores_index, draft_tokens


class TreeMaskMode(IntEnum):
    FULL_MASK = 0
    QLEN_ONLY = 1
    QLEN_ONLY_BITPACKING = 2


def default_tree_mask_mode() -> TreeMaskMode:
    # The CPU verify attention kernel (intel_amx) consumes the qlen x qlen
    # QLEN_ONLY tree mask directly; FULL_MASK is for the GPU kernels.
    return TreeMaskMode.QLEN_ONLY if _is_cpu else TreeMaskMode.FULL_MASK


def build_tree_kernel_efficient(
    bonus_tokens: torch.Tensor,
    parent_list: List[torch.Tensor],
    top_scores_index: torch.Tensor,
    draft_tokens: torch.Tensor,
    seq_lens: torch.Tensor,
    seq_lens_sum: int,
    topk: int,
    spec_steps: int,
    num_verify_tokens: int,
    tree_mask_mode: TreeMaskMode = TreeMaskMode.FULL_MASK,
    tree_mask_buf: Optional[torch.Tensor] = None,
    fill_prefix_mask: bool = True,
):
    draft_tokens = torch.cat((bonus_tokens.unsqueeze(1), draft_tokens), dim=1).flatten()

    # seq_lens_sum == sum(seq_lens); seq_lens: sequence length without draft tokens
    bs = seq_lens.numel()
    device = seq_lens.device
    # e.g. for bs=1, tree_mask: num_draft_token, seq_lens_sum + num_draft_token (flattened)
    # where each row indicates the attending pattern of each draft token
    # if use_partial_packed_tree_mask is True, tree_mask: num_draft_token (flattened, packed)
    if tree_mask_buf is not None:
        tree_mask = tree_mask_buf
        if tree_mask_mode == TreeMaskMode.QLEN_ONLY:
            tree_mask.fill_(True)
        elif tree_mask_mode == TreeMaskMode.QLEN_ONLY_BITPACKING:
            tree_mask.fill_(0)
        elif tree_mask_mode == TreeMaskMode.FULL_MASK:
            # Only the [0, seq_len) prefix columns depend on this fill; the
            # kernel below writes every tree cell itself. Skip the (up to
            # 100s of MB) per-step memset when nothing reads the mask.
            if fill_prefix_mask:
                tree_mask.fill_(True)
        else:
            raise NotImplementedError(f"Invalid tree mask: {tree_mask_mode=}")
    elif tree_mask_mode == TreeMaskMode.QLEN_ONLY:
        tree_mask = torch.full(
            (num_verify_tokens * bs * num_verify_tokens,),
            True,
            dtype=torch.bool,
            device=device,
        )
    elif tree_mask_mode == TreeMaskMode.QLEN_ONLY_BITPACKING:
        packed_dtypes = [torch.uint8, torch.uint16, torch.uint32]
        packed_dtype_idx = int(math.ceil(math.log2((num_verify_tokens + 7) // 8)))
        tree_mask = torch.zeros(
            (num_verify_tokens * bs,),
            dtype=packed_dtypes[packed_dtype_idx],
            device=device,
        )
    elif tree_mask_mode == TreeMaskMode.FULL_MASK:
        mask_shape = (
            seq_lens_sum * num_verify_tokens
            + num_verify_tokens * num_verify_tokens * bs,
        )
        # Same reasoning as the preallocated branch above.
        tree_mask = (
            torch.full(mask_shape, True, dtype=torch.bool, device=device)
            if fill_prefix_mask
            else torch.empty(mask_shape, dtype=torch.bool, device=device)
        )
    else:
        raise NotImplementedError(f"Invalid tree mask: {tree_mask_mode=}")

    # TODO: make them torch.empty and fuse them into `sgl_build_tree_kernel`
    retrieve_buf = torch.full(
        (3, bs, num_verify_tokens), -1, device=device, dtype=torch.long
    )
    retrieve_index, retrieve_next_token, retrieve_next_sibling = retrieve_buf
    # position: where each token belongs to
    # e.g. if depth of each draft token is [0, 1, 1, 2] and the prompt length is 7
    # then, positions = [7, 8, 8, 9]
    positions = torch.empty((bs * num_verify_tokens,), device=device, dtype=torch.long)

    if _is_npu:
        torch.ops.npu.build_tree_kernel_efficient(
            parent_list.to(dtype=torch.int64),
            top_scores_index,
            seq_lens,
            tree_mask,
            positions,
            retrieve_index,
            retrieve_next_token,
            retrieve_next_sibling,
            topk,
            spec_steps,
            num_verify_tokens,
            tree_mask_mode,
        )
    elif _is_xpu:
        sgl_build_tree_kernel_triton(
            parent_list,
            top_scores_index,
            seq_lens,
            tree_mask,
            positions,
            retrieve_index,
            retrieve_next_token,
            retrieve_next_sibling,
            topk,
            spec_steps,
            num_verify_tokens,
            tree_mask_mode,
        )
    elif _is_cpu:
        sgl_build_tree_kernel_efficient_cpu(
            parent_list,
            top_scores_index,
            seq_lens,
            tree_mask,
            positions,
            retrieve_index,
            retrieve_next_token,
            retrieve_next_sibling,
            topk,
            spec_steps,
            num_verify_tokens,
            tree_mask_mode,
        )
    else:
        sgl_build_tree_kernel_efficient(
            parent_list,
            top_scores_index,
            seq_lens,
            tree_mask,
            positions,
            retrieve_index,
            retrieve_next_token,
            retrieve_next_sibling,
            topk,
            spec_steps,
            num_verify_tokens,
            tree_mask_mode,
        )
    return (
        tree_mask,
        positions,
        retrieve_index,
        retrieve_next_token,
        retrieve_next_sibling,
        draft_tokens,
    )


def sgl_build_tree_kernel_triton(
    parent_list: torch.Tensor,
    selected_index: torch.Tensor,
    verified_seq_len: torch.Tensor,
    tree_mask: torch.Tensor,
    positions: torch.Tensor,
    retrieve_index: torch.Tensor,
    retrieve_next_token: torch.Tensor,
    retrieve_next_sibling: torch.Tensor,
    topk: int,
    depth: int,
    draft_token_num: int,
    tree_mask_mode: TreeMaskMode = TreeMaskMode.FULL_MASK,
):
    """Triton-based implementation."""
    # TODO: Add support for QLEN_ONLY_BITPACKING mode
    if tree_mask_mode == TreeMaskMode.QLEN_ONLY_BITPACKING:
        raise NotImplementedError(
            "QLEN_ONLY_BITPACKING is not supported in Triton implementation"
        )

    batch_size = verified_seq_len.shape[0]
    seq_len_prefix_sum = torch.cumsum(verified_seq_len, dim=0) - verified_seq_len

    # Launch kernel with one program per batch item
    grid = (batch_size,)

    sgl_build_tree_kernel_efficient_triton[grid](
        parent_list,
        selected_index,
        verified_seq_len,
        seq_len_prefix_sum,
        tree_mask,
        positions,
        retrieve_index,
        retrieve_next_token,
        retrieve_next_sibling,
        topk=topk,
        depth=depth,
        draft_token_num=draft_token_num,
        tree_mask_mode=int(tree_mask_mode),
        batch_size=batch_size,
        parent_list_stride=(
            parent_list.stride(0) if parent_list.dim() > 1 else parent_list.shape[0]
        ),
        selected_index_stride=selected_index.stride(0),
    )


def verify_tree_greedy_triton(
    predicts: torch.Tensor,
    accept_index: torch.Tensor,
    accept_token_num: torch.Tensor,
    candidates: torch.Tensor,
    retrieve_index: torch.Tensor,
    retrieve_next_token: torch.Tensor,
    retrieve_next_sibling: torch.Tensor,
    target_predict: torch.Tensor,
):
    """Triton-based implementation."""
    batch_size = candidates.shape[0]
    num_speculative_tokens = accept_index.shape[1]
    num_draft_tokens = candidates.shape[1]

    # Launch kernel with one program per batch item
    grid = (batch_size,)

    verify_tree_greedy_kernel_triton[grid](
        predicts,
        accept_index,
        accept_token_num,
        candidates,
        retrieve_index,
        retrieve_next_token,
        retrieve_next_sibling,
        target_predict,
        batch_size=batch_size,
        num_speculative_tokens=num_speculative_tokens,
        num_draft_tokens=num_draft_tokens,
    )


def verify_tree_greedy_func(
    predicts: torch.Tensor,
    accept_index: torch.Tensor,
    accept_token_num: torch.Tensor,
    candidates: torch.Tensor,
    retrieve_index: torch.Tensor,
    retrieve_next_token: torch.Tensor,
    retrieve_next_sibling: torch.Tensor,
    target_predict: torch.Tensor,
    topk: int = -1,
):
    if _is_cuda or _is_hip or _is_musa:
        from sgl_kernel import verify_tree_greedy

        verify_tree_greedy(
            predicts=predicts,  # mutable
            accept_index=accept_index,  # mutable
            accept_token_num=accept_token_num,  # mutable
            candidates=candidates,
            # kwarg LHS retained as `retrive_*` to match sgl_kernel op schema.
            retrive_index=retrieve_index,
            retrive_next_token=retrieve_next_token,
            retrive_next_sibling=retrieve_next_sibling,
            target_predict=target_predict,
        )

    elif _is_cpu:
        sgl_verify_tree_greedy_cpu(
            predicts=predicts,  # mutable
            accept_index=accept_index,  # mutable
            accept_token_num=accept_token_num,  # mutable
            candidates=candidates,
            # kwarg LHS retained as `retrive_*` to match the CUDA op schema, so
            # the CPU/CUDA call sites stay grep-symmetric.
            retrive_index=retrieve_index,
            retrive_next_token=retrieve_next_token,
            retrive_next_sibling=retrieve_next_sibling,
            target_predict=target_predict,
        )

    elif _is_npu:
        from sgl_kernel_npu.sample.verify_tree_greedy import verify_tree_greedy

        verify_tree_greedy(
            predicts=predicts,
            accept_index=accept_index,
            accept_token_num=accept_token_num,
            candidates=candidates,
            # kwarg LHS retained as `retrive_*` to match sgl_kernel op schema.
            retrive_index=retrieve_index,
            retrive_next_token=retrieve_next_token,
            retrive_next_sibling=retrieve_next_sibling,
            target_predict=target_predict,
        )
    elif _is_xpu:
        verify_tree_greedy_triton(
            predicts=predicts,
            accept_index=accept_index,
            accept_token_num=accept_token_num,
            candidates=candidates,
            retrieve_index=retrieve_index,
            retrieve_next_token=retrieve_next_token,
            retrieve_next_sibling=retrieve_next_sibling,
            target_predict=target_predict,
        )
    return predicts, accept_index, accept_token_num


def get_draft_input_from_target_hidden_dim(model_runner: ModelRunner) -> int:
    """Width of the target hidden states fed into the draft model.

    This is the single source of truth and is derived entirely from config: for
    EAGLE3 aux mode the draft consumes `num_aux` concatenated target layers
    (each `target_hidden_size` wide); every other arch consumes the per-layer
    `spec_hidden_size`.

    Do NOT read this off a draft projection's `in_features` (e.g. an `fc`
    layer): that width is arch-specific.

    Note: read entirely from the *draft* `model_runner`'s config. The non-aux
    branch assumes the draft's `spec_hidden_size` equals the target hidden width
    fed to the draft (true for standard EAGLE, where the draft mirrors the
    target hidden size); aux mode reads the explicit `target_hidden_size`.
    """
    model_config = model_runner.model_config
    hf_config = model_config.hf_config
    eagle_config = getattr(hf_config, "eagle_config", None) or {}
    get_eagle_config = (
        eagle_config.get
        if isinstance(eagle_config, dict)
        else lambda key, default=None: getattr(eagle_config, key, default)
    )
    use_aux = get_eagle_config("use_aux_hidden_state", True)
    spec_algorithm = model_runner.spec_algorithm

    if not (spec_algorithm is not None and spec_algorithm.is_eagle3() and use_aux):
        return model_config.spec_hidden_size

    target_hidden = getattr(hf_config, "target_hidden_size", None)
    if target_hidden is None:
        target_hidden = model_config.hidden_size
    num_aux = getattr(hf_config, "num_aux_hidden_states", None)
    if num_aux is None:
        layer_ids = get_eagle_config("eagle_aux_hidden_state_layer_ids", None)
        if layer_ids is None:
            layer_ids = getattr(hf_config, "eagle_aux_hidden_state_layer_ids", None)
        num_aux = len(layer_ids) if layer_ids else 3
    return target_hidden * num_aux


def get_draft_recurrent_hidden_state_spec(
    model_runner: ModelRunner,
) -> tuple[Optional[int], Optional[torch.dtype]]:
    """Return hidden_states width/dtype carried between draft decode steps."""
    if model_runner.spec_algorithm.is_standalone():
        return None, None
    return model_runner.model_config.spec_hidden_size, model_runner.model_config.dtype


def eagle_prepare_for_verify(
    verify_input: EagleVerifyInput,
    req_to_token_pool: ReqToTokenPool,
    batch: ScheduleBatch,
    target_worker: TpModelWorker,
):
    from sglang.kernels.ops.speculative.cache_locs import (
        assign_extend_cache_locs_uniform_func,
    )
    from sglang.srt.model_executor.forward_batch_info import (
        CaptureHiddenMode,
        ForwardBatch,
        ForwardMode,
    )
    from sglang.srt.speculative.spec_utils import prepare_mamba_track_for_verify

    if not batch.forward_mode.is_idle():
        # Assign cache locations
        bs = len(batch.req_pool_indices)
        batch.input_ids = verify_input.draft_token
        maybe_detect_oob(
            batch.input_ids,
            0,
            batch.model_config.vocab_size,
            "v2 prepare_for_verify input_ids",
        )
        device = batch.device
        # Uniform variant: end offsets (= start + draft_token_num) are computed
        # inside the kernel, keeping the eager `seq_lens + N` add off the host
        # critical path (bs=1 MTP inter-phase seam).
        batch.out_cache_loc = assign_extend_cache_locs_uniform_func(
            req_pool_indices=batch.req_pool_indices,
            req_to_token=req_to_token_pool.req_to_token,
            start_offset=batch.seq_lens,
            batch_size=bs,
            draft_token_num=verify_input.draft_token_num,
            device=device,
        )

        batch.out_cache_loc_dsv4 = maybe_build_dsv4_verify_bundle(
            batch, verify_input.draft_token_num
        )

        prepare_mamba_track_for_verify(batch)

        # TBO's split_spec_info reads these; no-verify-sync leaves both None.
        verify_input.seq_lens_cpu = batch.seq_lens_cpu
        verify_input.seq_lens_sum = (
            int(batch.seq_lens_cpu.sum()) if batch.seq_lens_cpu is not None else None
        )

    # Get a forward batch
    batch.forward_mode = (
        ForwardMode.IDLE if batch.forward_mode.is_idle() else ForwardMode.TARGET_VERIFY
    )
    capture_mode = (
        CaptureHiddenMode.NULL
        if target_worker.model_runner.spec_algorithm.is_standalone()
        else CaptureHiddenMode.FULL
    )
    verify_forward_batch = ForwardBatch.init_new(
        batch,
        target_worker.model_runner,
        capture_hidden_mode=capture_mode,
        return_hidden_states_before_norm=False,
    )

    # Run attention backend plan and cuda graph preparation
    can_run_cuda_graph = bool(
        target_worker.model_runner.decode_cuda_graph_runner
        and target_worker.model_runner.decode_cuda_graph_runner.can_run_graph(
            verify_forward_batch
        )
    )
    if can_run_cuda_graph:
        target_worker.model_runner.decode_cuda_graph_runner.load_batch(
            verify_forward_batch
        )
        verify_forward_batch.mark_forward_metadata_ready()
    # Non-cuda-graph: defer init to forward_extend, which runs after
    # `_forward_raw -> prepare_mlp_sync_batch` pads the batch. Initing
    # here would use pre-pad shapes and trip DSv4 indexer shape match.

    return verify_forward_batch, can_run_cuda_graph


def _seeded_verify_coins(
    *,
    sampling_seed: torch.Tensor,
    seq_lens: torch.Tensor,
    draft_token_num: int,
    device,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Derive deterministic verify-side coins from per-request sampling seeds.

    Mirrors the main seeded-sampling path: murmur_hash32(seed, seq_lens,
    column) mapped to [0, 1). Columns [0, draft_token_num) drive the
    per-draft rejection coins; column draft_token_num drives the final
    fallback-sampling coin.

    Scope: this seeds only the verify-side RNG. With rejection sampling the
    draft workers still pick candidates via unseeded multinomial
    (fast_sample in eagle_worker_v2), so that mode stays non-deterministic
    until the draft RNG is seeded in a follow-up; top-k/greedy draft
    selection is already deterministic.
    """
    from sglang.kernels.ops.sampling.murmur_hash import murmur_hash32

    cols = torch.arange(draft_token_num + 1, device=device, dtype=torch.int64)
    hashed = murmur_hash32(
        sampling_seed.to(torch.uint64), seq_lens.to(torch.uint64), cols
    )
    uniforms = hashed.to(torch.float64) / torch.iinfo(torch.uint32).max
    # The float32 cast rounds the top 129 uint32 hashes to exactly 1.0, but
    # the sampling kernels expect half-open [0, 1) coins: a 1.0 coin walks
    # past the last CDF bucket and can return a zero-probability token.
    # Clamp to the largest float32 below one; every other coin value is
    # untouched, so previously verified bitwise baselines stay intact.
    max_coin = 1.0 - 2**-24
    coins = (
        uniforms[:, :draft_token_num].to(torch.float32).clamp_(max=max_coin)
    ).contiguous()
    coins_for_final_sampling = (
        uniforms[:, draft_token_num].to(torch.float32).clamp_(max=max_coin)
    ).contiguous()
    return coins, coins_for_final_sampling


def _verify_coins(
    *,
    sampling_info: SamplingBatchInfo,
    seq_lens: torch.Tensor,
    draft_token_num: int,
    candidates: torch.Tensor,
    device,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Rejection and final-sampling coins for verify: deterministic seeded
    coins when sampling_seed is set (see _seeded_verify_coins), torch.rand
    otherwise.
    """
    if sampling_info.sampling_seed is not None:
        return _seeded_verify_coins(
            sampling_seed=sampling_info.sampling_seed,
            seq_lens=seq_lens,
            draft_token_num=draft_token_num,
            device=device,
        )
    # coins for rejection sampling
    coins = torch.rand_like(candidates, dtype=torch.float32, device=device)
    # coins for final sampling
    coins_for_final_sampling = torch.rand(
        (candidates.shape[0],), dtype=torch.float32, device=device
    )
    return coins, coins_for_final_sampling


# --- ktsamp (daniel-draft kernels, 4-Oct-2026): the verify's target p, top-k first ---------------------------------
# Rejection-sampling verify builds p = top-p(top-k(softmax(logits / T))) densely over the 248k vocab for every
# verify row (bs x W): a division pass, softmax (one CTA per row), flashinfer RadixTopK renorm and AirTopP renorm:
# ~0.67 ms per verify at W8, growing with W. When every request's top-k is <= 32 (host flag kts_max_top_k from
# SamplingBatchInfo) this computes the same p from the top of each row: (1) per-chunk logit max; (2) every logit >= the
# 32nd largest chunk max is a candidate (the top 32 and every value tied with them always are) and the dense output
# row is zeroed in the same pass; (3) one program per row sorts its candidates, x = logit / T as before, keeps every
# token >= the k-th value (flashinfer keeps all ties, probed in run daniel-bench-kchk3-1004), renormalizes, then keeps
# every token >= the value at which the cumulative mass first reaches top-p (again all ties), renormalizes, and writes
# the kept values. Same p as the dense chain up to fp32 rounding (~1e-7). Otherwise his dense chain. Off:
# SGLANG_KTSAMP=0.
import os as _kts_os  # noqa: E402

import triton  # noqa: E402
import triton.language as tl  # noqa: E402

_KTS_ON = _kts_os.environ.get("SGLANG_KTSAMP", "1") == "1"
_KTS_CH = int(_kts_os.environ.get("SGLANG_KTSAMP_CH", "1024"))
_KTS_CAP = int(_kts_os.environ.get("SGLANG_KTSAMP_CAP", "1024"))
_KTS_KSEL = 32


@triton.jit
def _kts_chunk_max_kernel(logits_ptr, stride_l, cmax_ptr, cnt_ptr, V, NCHP: tl.constexpr, CH: tl.constexpr):
    r = tl.program_id(0)
    c = tl.program_id(1)
    offs = c * CH + tl.arange(0, CH)
    x = tl.load(logits_ptr + r.to(tl.int64) * stride_l + offs, mask=offs < V, other=float("-inf")).to(tl.float32)
    tl.store(cmax_ptr + r * NCHP + c, tl.max(x, 0))
    if c == 0:
        tl.store(cnt_ptr + r, 0)


@triton.jit
def _kts_collect_kernel(logits_ptr, stride_l, cmax_ptr, cnt_ptr, cand_ptr, out_ptr, V, NCH,
                        NCHP: tl.constexpr, CH: tl.constexpr, KSEL: tl.constexpr, CAP: tl.constexpr):
    r = tl.program_id(0)
    c = tl.program_id(1)
    j = tl.arange(0, NCHP)
    cm = tl.load(cmax_ptr + r * NCHP + j, mask=j < NCH, other=float("-inf"))
    cms = tl.sort(cm, descending=True)
    tau = tl.max(tl.where(j == KSEL - 1, cms, float("-inf")), 0)
    offs = c * CH + tl.arange(0, CH)
    inb = offs < V
    row = r.to(tl.int64)
    x = tl.load(logits_ptr + row * stride_l + offs, mask=inb, other=float("-inf")).to(tl.float32)
    tl.store(out_ptr + row * V + offs, tl.zeros([CH], dtype=tl.float32), mask=inb)
    sel = (x >= tau) & inb
    seli = sel.to(tl.int32)
    n = tl.sum(seli, 0)
    base = tl.atomic_add(cnt_ptr + r, n)
    pos = base + tl.cumsum(seli, 0) - 1
    bits = x.to(tl.int32, bitcast=True)
    key = tl.where(bits >= 0, bits, bits ^ 0x7FFFFFFF)
    packed = (key.to(tl.int64) << 32) | (2147483647 - offs).to(tl.int64)
    tl.store(cand_ptr + row * CAP + pos, packed, mask=sel & (pos < CAP))


@triton.jit
def _kts_finish_kernel(cand_ptr, cnt_ptr, temp_ptr, stride_t, topk_ptr, topp_ptr, out_ptr, ovf_ptr, V, W,
                       CAP: tl.constexpr, KSEL: tl.constexpr, NEED_TOP_P: tl.constexpr):
    r = tl.program_id(0)
    req = r // W
    row = r.to(tl.int64)
    j = tl.arange(0, CAP)
    cnt = tl.load(cnt_ptr + r)
    tl.atomic_add(ovf_ptr, (cnt > CAP).to(tl.int32))
    n = tl.minimum(cnt, CAP)
    packed = tl.load(cand_ptr + row * CAP + j, mask=j < n, other=-9223372036854775807)
    packed = tl.sort(packed, descending=True)
    key = (packed >> 32).to(tl.int32)
    bits = tl.where(key >= 0, key, key ^ 0x7FFFFFFF)
    lg = bits.to(tl.float32, bitcast=True)
    idx = (2147483647 - (packed & 2147483647)).to(tl.int32)
    t = tl.load(temp_ptr + req * stride_t).to(tl.float32)
    x = lg / t
    valid = j < n
    k = tl.minimum(tl.maximum(tl.load(topk_ptr + req).to(tl.int32), 1), KSEL)
    k = tl.minimum(k, n)
    xmax = tl.max(tl.where(valid, x, float("-inf")), 0)
    piv_k = tl.max(tl.where(j == k - 1, x, float("-inf")), 0)
    keep = valid & (x >= piv_k)
    e = tl.where(keep, tl.exp(x - xmax), 0.0)
    p = e / tl.sum(e, 0)
    if NEED_TOP_P:
        tp = tl.load(topp_ptr + req).to(tl.float32)
        cum = tl.cumsum(p, 0)
        first = tl.min(tl.where(keep & (cum >= tp), j, CAP), 0)
        piv_p = tl.max(tl.where(j == first, x, float("-inf")), 0)
        keep = keep & (x >= piv_p)
        e = tl.where(keep, e, 0.0)
        p = e / tl.sum(e, 0)
    tl.store(out_ptr + row * V + idx, p, mask=keep)


def _kts_target_probs(logits, temperatures, top_ks, top_ps, draft_token_num, need_top_p):
    R, V = logits.shape
    dev = logits.device
    ch = _KTS_CH
    nch = triton.cdiv(V, ch)
    nchp = triton.next_power_of_2(nch)
    cmax = torch.empty((R, nchp), dtype=torch.float32, device=dev)
    cnt = torch.empty((R,), dtype=torch.int32, device=dev)
    cand = torch.empty((R, _KTS_CAP), dtype=torch.int64, device=dev)
    out = torch.empty((R, V), dtype=torch.float32, device=dev)
    ovf = _kts_overflow(dev)
    _kts_chunk_max_kernel[(R, nch)](logits, logits.stride(0), cmax, cnt, V, NCHP=nchp, CH=ch, num_warps=4)
    _kts_collect_kernel[(R, nch)](logits, logits.stride(0), cmax, cnt, cand, out, V, nch, NCHP=nchp, CH=ch,
                                  KSEL=_KTS_KSEL, CAP=_KTS_CAP, num_warps=4)
    _kts_finish_kernel[(R,)](cand, cnt, temperatures, temperatures.stride(0), top_ks, top_ps, out, ovf, V,
                             draft_token_num, CAP=_KTS_CAP, KSEL=_KTS_KSEL, NEED_TOP_P=bool(need_top_p),
                             num_warps=8)
    return out


_KTS_OVF = {}


def _kts_overflow(dev):
    """Rows whose candidate count exceeded the cap (never seen; read by the check script)."""
    t = _KTS_OVF.get(dev)
    if t is None:
        t = torch.zeros(1, dtype=torch.int32, device=dev)
        _KTS_OVF[dev] = t
    return t


def _kts_usable(sampling_info, next_token_logits, bs, draft_token_num):
    return (
        _KTS_ON
        and sampling_info.need_top_k_sampling
        and getattr(sampling_info, "kts_max_top_k", 1 << 30) <= _KTS_KSEL
        and next_token_logits.dim() == 2
        and next_token_logits.is_cuda
        and next_token_logits.shape[0] == bs * draft_token_num
        and next_token_logits.stride(-1) == 1
        and sampling_info.temperatures.shape[0] == bs
        and sampling_info.temperatures.numel() == bs
        and sampling_info.top_ks.shape[0] == bs
        and sampling_info.top_ps.shape[0] == bs
    )


def eagle_sample(
    verify_input: EagleVerifyInput,
    batch: ScheduleBatch,
    logits_output: LogitsProcessorOutput,
    grammar_mask: Optional[GrammarMask] = None,
):
    """
    Verify and find accepted tokens based on logits output and batch
    (which contains spec decoding information).
    """
    import torch.nn.functional as F

    from sglang.srt.distributed import get_tp_group
    from sglang.srt.layers.dp_attention import (
        is_dp_attention_enabled,
    )
    from sglang.srt.sampling.penaltylib.repetition_penalty import (
        apply_scaling_penalties,
    )
    from sglang.srt.speculative.spec_utils import (
        SIMULATE_ACC_LEN,
        SIMULATE_ACC_TOKEN_MODE,
        generate_simulated_accept_index,
    )
    from sglang.srt.utils.async_probe import maybe_detect_nan, sanitize_nan_logits

    device = batch.device
    if batch.forward_mode.is_idle():
        predict = torch.empty(0, dtype=torch.int32, device=device)
        num_correct_drafts = torch.empty(0, dtype=torch.int32, device=device)
        accept_index = torch.empty(0, dtype=torch.int32, device=device)
        return predict, num_correct_drafts, accept_index

    bs = len(batch.seq_lens)
    sampling_info = batch.sampling_info
    next_token_logits = logits_output.next_token_logits

    sanitize_nan_logits(next_token_logits, "verify: target model logits")

    # Apply penalty
    # This is a relaxed version of penalties for speculative decoding.
    if sampling_info.acc_additive_penalties is not None:
        next_token_logits.add_(
            torch.repeat_interleave(
                sampling_info.acc_additive_penalties,
                verify_input.draft_token_num,
                dim=0,
            )
        )
    if sampling_info.acc_scaling_penalties is not None:
        apply_scaling_penalties(
            next_token_logits,
            torch.repeat_interleave(
                sampling_info.acc_scaling_penalties, verify_input.draft_token_num, dim=0
            ),
        )
    if sampling_info.logit_bias is not None:
        next_token_logits.add_(
            torch.repeat_interleave(
                sampling_info.logit_bias, verify_input.draft_token_num, dim=0
            )
        )

    # Apply grammar mask if provided
    if grammar_mask is not None:
        grammar_mask.apply(next_token_logits)

    candidates = verify_input.draft_token.reshape(bs, verify_input.draft_token_num)
    predict_shape = list(next_token_logits.shape)[:-1]
    predict = torch.zeros(predict_shape, dtype=torch.int32, device=device).flatten()
    accept_index = torch.full(
        (bs, verify_input.max_tree_depth), -1, dtype=torch.int32, device=device
    )
    num_correct_drafts = torch.empty((bs,), dtype=torch.int32, device=device)

    # Sample tokens
    target_predict = None
    if sampling_info.is_all_greedy or _is_cpu or _is_npu or _is_hip or _is_xpu:
        target_predict = torch.argmax(next_token_logits, dim=-1)
        target_predict = target_predict.reshape(bs, verify_input.draft_token_num)
        predict, accept_index, num_correct_drafts = verify_tree_greedy_func(
            predicts=predict,  # mutable
            accept_index=accept_index,  # mutable
            accept_token_num=num_correct_drafts,  # mutable
            candidates=candidates,
            retrieve_index=verify_input.retrieve_index,
            retrieve_next_token=verify_input.retrieve_next_token,
            retrieve_next_sibling=verify_input.retrieve_next_sibling,
            target_predict=target_predict,
            topk=verify_input.tree_topk,
        )

        if _is_hip:
            # On ROCm, the per-rank draft tokens can differ, so ranks accept a
            # different number of drafts, desynchronize the committed seq_lens, and
            # deadlock the next TP collective. Broadcast from rank 0 to ensure
            # consistency, the same way the sampling branch below does.
            tp_group = (
                get_parallel().attn_tp_group
                if is_dp_attention_enabled()
                else get_tp_group()
            )
            if tp_group.world_size > 1:
                tp_group.broadcast(predict, src=0)
                tp_group.broadcast(accept_index, src=0)
                tp_group.broadcast(num_correct_drafts, src=0)
    else:
        from sgl_kernel import (
            top_k_renorm_prob,
            top_p_renorm_prob,
            tree_speculative_sampling_target_only,
        )

        from sglang.kernels.ops.speculative.reject_sampling import (
            chain_speculative_sampling_triton,
        )

        use_rejection_sampling = get_spec().speculative_use_rejection_sampling

        sampling_fn = (
            chain_speculative_sampling_triton
            if use_rejection_sampling
            else tree_speculative_sampling_target_only
        )

        # These full-vocabulary matrices are consumed by the sampling kernel
        # within this step. Returned tensors were allocated before the scope,
        # so the next CUDA graph replay may safely reclaim these borrowed bytes.
        with borrow_graph_pool(user="EAGLE probability borrow"):
            _kts = _kts_usable(
                sampling_info, next_token_logits, bs, verify_input.draft_token_num
            )
            if _kts:  # ktsamp: p already top-k / top-p truncated and renormalized
                expanded_temperature = None
                target_probs = _kts_target_probs(
                    next_token_logits,
                    sampling_info.temperatures,
                    sampling_info.top_ks,
                    sampling_info.top_ps,
                    verify_input.draft_token_num,
                    sampling_info.need_top_p_sampling,
                )
                maybe_detect_nan(target_probs, "v2 verify: ktsamp target_probs")
            else:
                expanded_temperature = torch.repeat_interleave(
                    sampling_info.temperatures, verify_input.draft_token_num, dim=0
                )  # (bs * num_draft_tokens, 1)

                target_probs = F.softmax(
                    next_token_logits / expanded_temperature, dim=-1
                )  # (bs * num_draft_tokens, vocab_size)
                maybe_detect_nan(target_probs, "v2 verify: target_probs after softmax")
            if sampling_info.need_top_k_sampling and not _kts:
                target_probs = top_k_renorm_prob(
                    target_probs,
                    torch.repeat_interleave(
                        sampling_info.top_ks, verify_input.draft_token_num, dim=0
                    ),
                )  # (bs * num_draft_tokens, vocab_size)
                maybe_detect_nan(
                    target_probs, "v2 verify: target_probs after top_k_renorm"
                )
            if sampling_info.need_top_p_sampling and not _kts:
                target_probs = top_p_renorm_prob(
                    target_probs,
                    torch.repeat_interleave(
                        sampling_info.top_ps, verify_input.draft_token_num, dim=0
                    ),
                )
                maybe_detect_nan(
                    target_probs, "v2 verify: target_probs after top_p_renorm"
                )
            target_probs = target_probs.reshape(bs, verify_input.draft_token_num, -1)
            draft_probs = (
                verify_input.draft_probs
                if use_rejection_sampling
                else torch.zeros_like(target_probs)
            )
            # Defense-in-depth behind the spec_hook startup allowlist: validate
            # the actual kernel inputs before the Triton kernel.
            if use_rejection_sampling and (
                draft_probs is None or draft_probs.shape[-1] != target_probs.shape[-1]
            ):
                raise ValueError(
                    "Rejection sampling requires a target-vocab draft proposal "
                    "distribution; the current speculative algorithm/draft worker "
                    "does not produce one (draft_probs missing or vocab-mismatched)."
                )

            coins, coins_for_final_sampling = _verify_coins(
                sampling_info=sampling_info,
                seq_lens=batch.seq_lens,
                draft_token_num=verify_input.draft_token_num,
                candidates=candidates,
                device=device,
            )
            sampling_fn(
                predicts=predict,  # mutable
                accept_index=accept_index,  # mutable
                accept_token_num=num_correct_drafts,  # mutable
                candidates=candidates,
                # kwarg LHS retained as `retrive_*` to match sgl_kernel op schema.
                retrive_index=verify_input.retrieve_index,
                retrive_next_token=verify_input.retrieve_next_token,
                retrive_next_sibling=verify_input.retrieve_next_sibling,
                uniform_samples=coins,
                uniform_samples_for_final_sampling=coins_for_final_sampling,
                target_probs=target_probs,
                draft_probs=draft_probs,
                threshold_single=get_spec().speculative_accept_threshold_single,
                threshold_acc=get_spec().speculative_accept_threshold_acc,
                deterministic=True,
            )
            del (
                expanded_temperature,
                target_probs,
                draft_probs,
                coins,
                coins_for_final_sampling,
            )

        # Sync sampling results across TP ranks: different GPUs may
        # produce slightly different target_probs due to floating-point
        # non-determinism in softmax/top_k/top_p, causing different
        # sampled tokens. Broadcast from rank 0 to ensure consistency.
        tp_group = (
            get_parallel().attn_tp_group
            if is_dp_attention_enabled()
            else get_tp_group()
        )
        if tp_group.world_size > 1:
            tp_group.broadcast(predict, src=0)
            tp_group.broadcast(accept_index, src=0)
            tp_group.broadcast(num_correct_drafts, src=0)

    if SIMULATE_ACC_LEN > 0:
        # Do simulation. The helper builds (and returns) a replacement
        # accept_index of width spec_steps + 1, so pass max_tree_depth - 1
        # to keep the simulated width identical to the real one.
        if SIMULATE_ACC_TOKEN_MODE not in ("fixed", "real-draft-token"):
            raise ValueError(
                "Invalid SGLANG_SIMULATE_ACC_TOKEN_MODE "
                f"{SIMULATE_ACC_TOKEN_MODE!r}; expected 'fixed' or "
                "'real-draft-token'."
            )

        if SIMULATE_ACC_TOKEN_MODE == "real-draft-token":
            if verify_input.tree_topk != 1:
                raise ValueError(
                    "SGLANG_SIMULATE_ACC_LEN with real draft tokens currently "
                    "requires speculative_eagle_topk=1."
                )

            # Use target argmax as the synthetic bonus for non-greedy requests.
            if target_predict is None:
                target_predict = torch.argmax(next_token_logits, dim=-1).reshape(
                    bs, verify_input.draft_token_num
                )
        accept_index = generate_simulated_accept_index(
            accept_index=accept_index,
            predict=predict,  # mutable
            num_correct_drafts=num_correct_drafts,  # mutable
            candidates=candidates,
            target_predict=target_predict,
            simulate_acc_len=SIMULATE_ACC_LEN,
            simulate_acc_token_mode=SIMULATE_ACC_TOKEN_MODE,
            bs=bs,
            spec_steps=verify_input.max_tree_depth - 1,
        )

    # `num_correct_drafts` stays drafts-only inside this function; the returned
    # tensor includes the trailing/bonus token via out-of-place +1 so the
    # name no longer flips semantics mid-function (naming doc C2).
    return predict, num_correct_drafts + 1, accept_index


def eagle_prepare_for_decode(batch: ScheduleBatch):
    batch.maybe_evict_swa()

    bs = batch.batch_size()

    # Accumulate penalty
    # This is a relaxed version of penalties for speculative decoding.
    if batch.sampling_info.penalizer_orchestrator.is_required:
        batch.cumulate_penalty_output_tokens()

    page_size = batch.token_to_kv_pool_allocator.page_size
    double_alloc = get_alloc_reserve_per_decode()

    cur_kv_lens, nxt_kv_lens, num_needed_tokens = page_aligned_decode_alloc_lens(
        batch.reqs,
        reserve=double_alloc,
        page_size=page_size,
    )
    for r in batch.reqs:
        r.decode_batch_idx += 1

    cur_kv_lens_cpu = torch.tensor(cur_kv_lens, dtype=torch.int32, device="cpu")
    nxt_kv_lens_cpu = torch.tensor(nxt_kv_lens, dtype=torch.int32, device="cpu")

    # Fail fast if the page>1 + topk>1 draft over-allocation
    # (get_alloc_reserve_per_decode) outgrows the req_to_token row: the write below
    # would OOB and free would leak KV. The row is widened to hold it in _init_pools
    # (PR #26972); fail here with a clear error, not on a later cryptic CUDA assert.

    if page_size > 1 and (get_spec().speculative_eagle_topk or 1) > 1:
        max_alloc_len = int(nxt_kv_lens_cpu.max())
        row_width = batch.req_to_token_pool.req_to_token.shape[1]
        assert max_alloc_len <= row_width, (
            f"spec v2 page>1 topk>1 draft over-allocation ({max_alloc_len}) exceeds "
            f"req_to_token row width ({row_width}); page_size={page_size}. Widen the "
            f"row to hold committed + get_alloc_reserve_per_decode (PR #26972)."
        )

    # non_blocking H2D: a blocking .to() syncs the schedule stream, which the WAR
    # barrier has chained to the prev forward -> host stalls a full forward.
    cur_kv_lens_device = cur_kv_lens_cpu.to(device=batch.device, non_blocking=True)
    nxt_kv_lens_device = nxt_kv_lens_cpu.to(device=batch.device, non_blocking=True)
    tree_cache = batch.tree_cache
    req_to_token_pool = batch.req_to_token_pool
    req_pool_indices = batch.req_pool_indices
    reqs = batch.reqs
    cur_kv_lens = cur_kv_lens_device
    nxt_kv_lens = nxt_kv_lens_device
    alloc_for_spec_decode(
        tree_cache,
        req_to_token_pool,
        reqs=reqs,
        req_pool_indices=req_pool_indices,
        cur_kv_lens=cur_kv_lens,
        cur_kv_lens_cpu=cur_kv_lens_cpu,
        nxt_kv_lens=nxt_kv_lens,
        nxt_kv_lens_cpu=nxt_kv_lens_cpu,
        num_needed_tokens=num_needed_tokens,
        batch=batch,
    )

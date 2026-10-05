# Copyright 2023-2024 SGLang Team
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Logits processing."""

import dataclasses
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple, Union

import torch
from torch import nn

from sglang.kernels.ops.activation.softcap import (
    softcap_inplace_logits as fused_softcap,
)
from sglang.srt.distributed import get_tp_group
from sglang.srt.distributed.device_communicators import triton_symm_mem_ag
from sglang.srt.layers.aux_hidden_states import (
    AuxHiddenStates,
    pack_aux_hidden_states,
)
from sglang.srt.layers.dp_attention import (
    DpPaddingMode,
    attn_tp_all_gather,
    attn_tp_all_gather_into_tensor,
    dp_gather_replicate,
    dp_scatter,
    get_dp_device,
    get_dp_dtype,
    get_dp_hidden_size,
)
from sglang.srt.layers.logprob_processor import (
    InputLogprobProcessor,
    LogprobStage,
    get_token_ids_logprobs_raw,
    get_top_logprobs_raw,
)
from sglang.srt.layers.vocab_parallel_embedding import VocabParallelEmbedding
from sglang.srt.model_executor.forward_batch_info import (
    CaptureHiddenMode,
    ForwardBatch,
    ForwardMode,
)
from sglang.srt.runtime_context import get_exec, get_parallel
from sglang.srt.sampling.sampling_observer import DeviceAuxiliaryOutput
from sglang.srt.utils.common import (
    is_cpu,
    is_npu,
    is_pin_memory_available,
    use_intel_amx_backend,
)

logger = logging.getLogger(__name__)

_is_npu = is_npu()
_is_cpu = is_cpu()

_UNQUANTIZED_LM_HEAD_METHODS = {
    "UnquantizedEmbeddingMethod",
    "UnquantizedLinearMethod",
    "PackWeightMethod",
}

# None outside a FlashInfer autotune pass; inside one, whether that pass runs the
# LM head. Not-None means the forward's output is discarded -- attention backends
# read that via get_in_autotune_dummy_run() to skip a cross-node exchange.
# Skipping the LM head skips its [batch * dp_size, vocab] all-gather, which OOMs
# under DP attention with a tight mem_fraction_static.
_autotune_run_lm_head: Optional[bool] = None


def get_in_autotune_dummy_run() -> bool:
    return _autotune_run_lm_head is not None


@contextmanager
def autotune_dummy_run_mode(*, run_lm_head: bool):
    global _autotune_run_lm_head
    _autotune_run_lm_head = run_lm_head
    try:
        yield
    finally:
        _autotune_run_lm_head = None


@dataclasses.dataclass
class LogitsProcessorOutput:
    ## Part 1: This part will be assigned in python/sglang/srt/layers/logits_processor.py::LogitsProcessor
    # The logits of the next tokens.       shape: [#seq, vocab_size]
    # Can be None for certain prefill-only requests (e.g., multi-item scoring) that don't need next token generation
    next_token_logits: Optional[torch.Tensor]
    # Used by speculative decoding (EAGLE)
    # The last hidden layers
    hidden_states: Optional[torch.Tensor] = None

    ## Part 2: This part will be assigned in python/sglang/srt/layers/sampler.py::Sampler
    # he log probs of output tokens, if SGLANG_RETURN_ORIGINAL_LOGPROB = True, will get the log probs before applying temperature. If False, will get the log probs before applying temperature.
    next_token_logprobs: Optional[torch.Tensor] = None
    # The logprobs and ids of the top-k tokens in output positions. shape: [#seq, k]
    next_token_top_logprobs_val: Optional[List] = None
    next_token_top_logprobs_idx: Optional[List] = None
    # The logprobs and ids of the requested token ids in output positions. shape: [#seq, n] (n is the number of requested token ids)
    # Can contain either lists or GPU tensors (for delayed copy optimization in prefill-only requests)
    next_token_token_ids_logprobs_val: Optional[
        List[Union[List[float], torch.Tensor]]
    ] = None
    next_token_token_ids_logprobs_idx: Optional[List] = None
    # Sparse top-k/top-p/min-p support ids and selected-token logprob after
    # truncation/renormalization. Only populated when requested.
    next_token_sampling_mask_idx: Optional[List[Optional[List[int]]]] = None
    next_token_sampling_logprobs: Optional[List[Optional[float]]] = None

    ## Part 3: Prefill-only. This part will be assigned in python/sglang/srt/layers/logits_processor.py::LogitsProcessor
    # The logprobs of input tokens.        shape: [#token]
    input_token_logprobs: Optional[torch.Tensor] = None
    # The logprobs and ids of the top-k tokens in input positions.  shape: [#seq, #token, k]
    input_top_logprobs_val: Optional[List] = None
    input_top_logprobs_idx: Optional[List] = None
    # The logprobs and ids of the requested token ids in input positions. shape: [#seq, n] (n is the number of requested token ids)
    # Can contain either lists or GPU tensors (for delayed GPU-to-CPU transfer optimization)
    input_token_ids_logprobs_val: Optional[List[Union[List[float], torch.Tensor]]] = (
        None
    )
    input_token_ids_logprobs_idx: Optional[List] = None

    ## Part 4: Diffusion LLM only.
    full_logits: Optional[torch.Tensor] = None

    ## Part 5: Customized Info
    customized_info: Optional[Dict[str, List[Any]]] = None

    ## Part 6: Temporary variables
    # FIXME: These fields are not logits-related but are passed through here as a
    # workaround since ForwardBatch is local to forward_batch_generation().
    # They should be moved to GenerationBatchResult to keep this class clean.
    mm_input_embeds: Optional[torch.Tensor] = None

    # Scheduler-local output copied alongside the ordinary generation result.
    auxiliary_device_output: Optional[DeviceAuxiliaryOutput] = None


@dataclasses.dataclass
class LogitsMetadata:
    forward_mode: ForwardMode
    capture_hidden_mode: CaptureHiddenMode = CaptureHiddenMode.NULL
    next_token_logits_buffer: Optional[torch.Tensor] = None

    extend_return_logprob: bool = False
    extend_return_top_logprob: bool = False
    extend_token_ids_logprob: bool = False
    extend_seq_lens: Optional[torch.Tensor] = None
    extend_seq_lens_cpu: Optional[List[int]] = None
    extend_logprob_start_lens_cpu: Optional[List[int]] = None
    extend_logprob_pruned_lens_cpu: Optional[List[int]] = None
    top_logprobs_nums: Optional[List[int]] = None
    extend_input_logprob_token_ids_gpu: Optional[torch.Tensor] = None
    token_ids_logprobs: Optional[List[List[int]]] = None

    # logits and logprobs post processing
    temperature: torch.Tensor = None
    top_p: torch.Tensor = None

    # DP attention metadata. Not needed when DP attention is not used.
    # Number of tokens in the request.
    global_num_tokens_gpu: Optional[torch.Tensor] = None
    # The start position of local hidden states.
    dp_local_start_pos: Optional[torch.Tensor] = None
    dp_local_num_tokens: Optional[torch.Tensor] = None
    global_dp_buffer_len: Optional[int] = None
    # Number of tokens to sample per DP rank
    global_num_tokens_for_logprob_cpu: Optional[torch.Tensor] = None
    global_num_tokens_for_logprob_gpu: Optional[torch.Tensor] = None
    # The gather mode for DP attention
    dp_padding_mode: Optional[DpPaddingMode] = None

    # Whether this batch is prefill-only (no token generation needed)
    is_prefill_only: bool = False

    mm_input_embeds: Optional[torch.Tensor] = None

    # DRAFT_EXTEND_V2: when set, lm_head runs only on these rows (see
    # EagleDraftExtendInput.select_index).
    draft_extend_select_index: Optional[torch.Tensor] = None

    @classmethod
    def from_forward_batch(cls, forward_batch: ForwardBatch):
        if (
            forward_batch.forward_mode.is_extend()
            and forward_batch.return_logprob
            and not forward_batch.forward_mode.is_target_verify()
        ):
            extend_return_top_logprob = any(
                x > 0 for x in forward_batch.top_logprobs_nums
            )
            extend_token_ids_logprob = any(
                x is not None for x in forward_batch.token_ids_logprobs
            )
            extend_return_logprob = False
            extend_logprob_pruned_lens_cpu = []
            for extend_len, start_len in zip(
                forward_batch.extend_seq_lens_cpu,
                forward_batch.extend_logprob_start_lens_cpu,
            ):
                if extend_len - start_len > 0:
                    extend_return_logprob = True
                extend_logprob_pruned_lens_cpu.append(extend_len - start_len)
        else:
            extend_return_logprob = extend_return_top_logprob = (
                extend_token_ids_logprob
            ) = extend_logprob_pruned_lens_cpu = False

        if forward_batch.forward_mode.is_draft_extend_v2():
            draft_extend_select_index = forward_batch.spec_info.select_index
        else:
            draft_extend_select_index = None

        return cls(
            forward_mode=forward_batch.forward_mode,
            capture_hidden_mode=forward_batch.capture_hidden_mode,
            next_token_logits_buffer=forward_batch.next_token_logits_buffer,
            extend_return_logprob=extend_return_logprob,
            extend_return_top_logprob=extend_return_top_logprob,
            extend_token_ids_logprob=extend_token_ids_logprob,
            extend_seq_lens=forward_batch.extend_seq_lens,
            extend_seq_lens_cpu=forward_batch.extend_seq_lens_cpu,
            extend_logprob_start_lens_cpu=forward_batch.extend_logprob_start_lens_cpu,
            extend_logprob_pruned_lens_cpu=extend_logprob_pruned_lens_cpu,
            top_logprobs_nums=forward_batch.top_logprobs_nums,
            token_ids_logprobs=forward_batch.token_ids_logprobs,
            extend_input_logprob_token_ids_gpu=forward_batch.extend_input_logprob_token_ids_gpu,
            is_prefill_only=forward_batch.is_prefill_only,
            global_num_tokens_gpu=forward_batch.global_num_tokens_gpu,
            dp_local_start_pos=forward_batch.dp_local_start_pos,
            dp_local_num_tokens=forward_batch.dp_local_num_tokens,
            global_dp_buffer_len=forward_batch.global_dp_buffer_len,
            global_num_tokens_for_logprob_cpu=forward_batch.global_num_tokens_for_logprob_cpu,
            global_num_tokens_for_logprob_gpu=forward_batch.global_num_tokens_for_logprob_gpu,
            dp_padding_mode=DpPaddingMode.SUM_LEN,
            mm_input_embeds=forward_batch.mm_input_embeds,
            draft_extend_select_index=draft_extend_select_index,
        )

    def compute_dp_attention_metadata(self):
        cumtokens = torch.cumsum(self.global_num_tokens_for_logprob_gpu, dim=0)
        dp_rank = get_parallel().attn_dp_rank
        if dp_rank == 0:
            dp_local_start_pos = torch.zeros_like(
                self.global_num_tokens_for_logprob_gpu[0]
            )
        else:
            dp_local_start_pos = cumtokens[dp_rank - 1]

        self.dp_local_start_pos = dp_local_start_pos
        self.dp_local_num_tokens = self.global_num_tokens_for_logprob_gpu[dp_rank]

        hidden_size = get_dp_hidden_size()
        dtype = get_dp_dtype()
        device = get_dp_device()

        if self.global_num_tokens_for_logprob_cpu is not None:
            # create a smaller buffer to reduce peak memory usage
            self.global_dp_buffer_len = sum(self.global_num_tokens_for_logprob_cpu)
        else:
            self.global_dp_buffer_len = self.global_dp_buffer_len

        self.gathered_buffer = torch.empty(
            (
                self.global_dp_buffer_len,
                hidden_size,
            ),
            dtype=dtype,
            device=device,
        )


class LogitsProcessor(nn.Module):
    def __init__(
        self,
        config,
        skip_all_gather: bool = False,
        logit_scale: Optional[float] = None,
        return_full_logits: bool = False,
    ):
        super().__init__()
        self.config = config
        self.vocab_size = config.vocab_size
        self.logit_scale = logit_scale
        self.use_attn_tp_group = get_parallel().config.enable_dp_lm_head
        self.use_tp_lm_head_all_to_all = (
            get_parallel().config.enable_tp_lm_head_all_to_all
        )
        self.use_fp32_lm_head = get_exec().features.enable_fp32_lm_head
        if self.use_attn_tp_group:
            self.attn_tp_size = get_parallel().attn_tp_size
            self.do_tensor_parallel_all_gather = (
                not skip_all_gather and self.attn_tp_size > 1
            )
            self.do_tensor_parallel_all_gather_dp_attn = False
        else:
            self.do_tensor_parallel_all_gather = (
                not skip_all_gather and get_parallel().tp_size > 1
            )
            self.do_tensor_parallel_all_gather_dp_attn = (
                self.do_tensor_parallel_all_gather and get_parallel().attn_dp_size != 1
            )
        self.final_logit_softcapping = getattr(
            self.config, "final_logit_softcapping", None
        )
        if (
            self.final_logit_softcapping is not None
            and self.final_logit_softcapping < 0
        ):
            self.final_logit_softcapping = None

        self.return_full_logits = return_full_logits
        self.enable_mis = get_exec().features.enable_mis
        self.rl_on_policy_target = get_exec().deterministic.rl_on_policy_target

        self._logits_gatherer = triton_symm_mem_ag.MultimemAllGatherer(
            max_tokens=triton_symm_mem_ag.recommended_max_tokens(
                include_prefill=False, floor=128
            ),
            enabled=self.do_tensor_parallel_all_gather and not self.use_attn_tp_group,
            skip_entry_sync=True,
        )

        self.input_logprob_processor = InputLogprobProcessor()

    def forward(
        self,
        input_ids,
        hidden_states,
        lm_head: VocabParallelEmbedding,
        logits_metadata: Union[LogitsMetadata, ForwardBatch],
        aux_hidden_states: Optional[AuxHiddenStates] = None,
        hidden_states_before_norm: Optional[torch.Tensor] = None,
    ) -> LogitsProcessorOutput:
        # Extract MIS indices before ForwardBatch → LogitsMetadata conversion
        multi_item_delimiter_indices = None
        if isinstance(logits_metadata, ForwardBatch):
            multi_item_delimiter_indices = logits_metadata.multi_item_delimiter_indices
            logits_metadata = LogitsMetadata.from_forward_batch(logits_metadata)

        # Autotune dummy run discards this output. `is False` not `not`: None
        # means no autotune pass, which must not skip. Placed before the MIS /
        # DLLM / common dispatch so all three LM-head paths are skipped.
        if _autotune_run_lm_head is False:
            return LogitsProcessorOutput(next_token_logits=None)

        # Multi-item scoring only for prefill-only requests with pre-computed indices.
        if multi_item_delimiter_indices is not None and logits_metadata.is_prefill_only:
            return self.compute_logprobs_for_multi_item_scoring(
                input_ids,
                hidden_states,
                lm_head,
                logits_metadata,
                multi_item_delimiter_indices,
            )

        # Diffusion LLM only.
        if logits_metadata.forward_mode.is_dllm_extend():
            return self._get_dllm_logits(hidden_states, lm_head, logits_metadata)

        # Get the last hidden states and last logits for the next token prediction
        (
            pruned_states,
            pruned_states_before_norm,
            aux_pruned_states,
            sample_indices,
            input_logprob_indices,
            token_to_seq_idx,
        ) = self._get_pruned_states(
            hidden_states,
            hidden_states_before_norm,
            aux_hidden_states,
            logits_metadata,
        )

        hidden_states_to_store = self._get_hidden_states_to_store(
            hidden_states,
            hidden_states_before_norm,
            aux_hidden_states,
            pruned_states,
            pruned_states_before_norm,
            aux_pruned_states,
            sample_indices,
            logits_metadata,
        )
        del hidden_states

        if not logits_metadata.extend_return_logprob:
            # Compute logits for both input and sampled tokens.
            logits = self._get_logits(pruned_states, lm_head, logits_metadata)
            sampled_logits = (
                logits[sample_indices] if sample_indices is not None else logits
            )

            # Decode mode or extend mode without return_logprob.
            return LogitsProcessorOutput(
                next_token_logits=sampled_logits,
                hidden_states=hidden_states_to_store,
                mm_input_embeds=logits_metadata.mm_input_embeds,
            )

        logprobs_result, sampled_logits = self.input_logprob_processor.forward(
            pruned_states=pruned_states,
            sample_indices=sample_indices,
            input_logprob_indices=input_logprob_indices,
            token_to_seq_idx=token_to_seq_idx,
            lm_head=lm_head,
            get_logits_fn=self._get_logits,
            logits_metadata=logits_metadata,
            skip_chunking_for_dp_attn=self.do_tensor_parallel_all_gather_dp_attn,
        )

        logits_output = LogitsProcessorOutput(
            next_token_logits=sampled_logits,
            hidden_states=hidden_states_to_store,
            mm_input_embeds=logits_metadata.mm_input_embeds,
        )
        logprobs_result.write_input_to(logits_output)
        return logits_output

    def _get_pruned_states(
        self,
        hidden_states: torch.Tensor,
        hidden_states_before_norm: Optional[torch.Tensor],
        aux_hidden_states: Optional[AuxHiddenStates],
        logits_metadata: LogitsMetadata,
    ):
        pruned_states_before_norm: Optional[torch.Tensor] = None
        aux_pruned_states = None
        token_to_seq_idx = []

        if (
            logits_metadata.forward_mode.is_decode_or_idle()
            or logits_metadata.forward_mode.is_target_verify()
            or logits_metadata.forward_mode.is_draft_extend_v2()
        ):
            if logits_metadata.draft_extend_select_index is not None:
                # Only next_token_logits narrows to [bs, vocab]; the
                # FULL-capture hidden stays unpruned.
                pruned_states = hidden_states[logits_metadata.draft_extend_select_index]
            else:
                pruned_states = hidden_states
            pruned_states_before_norm = hidden_states_before_norm
            if aux_hidden_states is not None:
                aux_pruned_states = (
                    aux_hidden_states
                    if isinstance(aux_hidden_states, torch.Tensor)
                    else [hidden for hidden in aux_hidden_states]
                )
            sample_indices = None
            input_logprob_indices = None

        elif (
            logits_metadata.forward_mode.is_extend()
            and not logits_metadata.extend_return_logprob
        ):
            # Prefill without input logprobs.
            last_index = torch.cumsum(logits_metadata.extend_seq_lens, dim=0) - 1
            pruned_states = hidden_states[last_index]
            if hidden_states_before_norm is not None:
                pruned_states_before_norm = hidden_states_before_norm[last_index]
            if aux_hidden_states is not None:
                aux_pruned_states = (
                    aux_hidden_states[last_index]
                    if isinstance(aux_hidden_states, torch.Tensor)
                    else [hidden[last_index] for hidden in aux_hidden_states]
                )
            sample_indices = None
            input_logprob_indices = None
        else:
            # Prefill with input logprobs.
            # Find 4 different indices.
            # 1. pruned_states: hidden states that we want logprobs from.
            # 2. sample_indices: Indices that have sampled tokens.
            # 3. input_logprob_indices: Indices that have input logprob tokens.
            # 4. token_to_seq_idx: map each token to its sequence index
            #
            # Example
            # -------
            # Suppose a batch (flattened by sequence):
            # [t00, t01, t02, t03, t10, t11, t12, t13, t14, t20, t21, t22, t23, t24, t25]
            # extend_seq_lens_cpu           = [4, 5, 6]
            # extend_logprob_start_lens_cpu = [0, 5, 3]
            #
            # Then, the indices are:
            # pruned_states         -> [t00, t01, t02, t03, t14, t23, t24, t25]
            # sample_indices        -> [3, 4, 7]
            # input_logprob_indices -> [0, 1, 2, 3, 5, 6, 7]
            # token_to_seq_idx      -> [0, 0, 0, 0, 1, 2, 2, 2]
            #
            # If chunk is enabled and chunk_size = 3, the chunks will be computed in a chunked manner:
            # [t00, t01, t02], [t03, t14, t23], [t24, t25]

            sample_index_pt = -1
            sample_indices = []
            input_logprob_indices_pt = 0
            input_logprob_indices = []
            pt, pruned_states_list, pruned_states_before_norm_list = 0, [], []
            is_packed_aux_hidden_states = isinstance(aux_hidden_states, torch.Tensor)
            aux_pruned_states_lists = None
            if aux_hidden_states is not None:
                aux_pruned_states_lists = (
                    []
                    if is_packed_aux_hidden_states
                    else [[] for _ in aux_hidden_states]
                )

            for idx, (extend_logprob_start_len, extend_len) in enumerate(
                zip(
                    logits_metadata.extend_logprob_start_lens_cpu,
                    logits_metadata.extend_seq_lens_cpu,
                )
            ):
                # It can happen in chunked prefill. We still need to sample 1 token,
                # But we don't want to include it in input logprob.
                if extend_len == extend_logprob_start_len:
                    start_len = extend_logprob_start_len - 1
                else:
                    start_len = extend_logprob_start_len

                # We always need at least 1 token to sample because that's required
                # by a caller.
                assert extend_len > start_len
                pruned_states_list.append(
                    hidden_states[pt + start_len : pt + extend_len]
                )
                if hidden_states_before_norm is not None:
                    pruned_states_before_norm_list.append(
                        hidden_states_before_norm[pt + start_len : pt + extend_len]
                    )
                if aux_pruned_states_lists is not None:
                    if is_packed_aux_hidden_states:
                        aux_pruned_states_lists.append(
                            aux_hidden_states[pt + start_len : pt + extend_len]
                        )
                    else:
                        for j, hidden in enumerate(aux_hidden_states):
                            aux_pruned_states_lists[j].append(
                                hidden[pt + start_len : pt + extend_len]
                            )
                # Map each token to its sequence index, for chunked computation
                # of input logprobs
                token_to_seq_idx.extend([idx] * (extend_len - start_len))
                pt += extend_len
                sample_index_pt += extend_len - start_len
                sample_indices.append(sample_index_pt)
                input_logprob_indices.extend(
                    [
                        input_logprob_indices_pt + i
                        for i in range(extend_len - extend_logprob_start_len)
                    ]
                )
                input_logprob_indices_pt += extend_len - start_len

            pruned_states = torch.cat(pruned_states_list)
            if hidden_states_before_norm is not None:
                pruned_states_before_norm = torch.cat(pruned_states_before_norm_list)
            if aux_pruned_states_lists is not None:
                aux_pruned_states = (
                    torch.cat(aux_pruned_states_lists)
                    if is_packed_aux_hidden_states
                    else [torch.cat(lst) for lst in aux_pruned_states_lists]
                )

            # Build the index tensors via pinned host memory + non-blocking H2D
            # so the small copy doesn't drain the stream.
            sample_indices = torch.tensor(
                sample_indices,
                dtype=torch.int64,
                pin_memory=is_pin_memory_available(),
            ).to(pruned_states.device, non_blocking=True)
            input_logprob_indices = torch.tensor(
                input_logprob_indices,
                dtype=torch.int64,
                pin_memory=is_pin_memory_available(),
            ).to(pruned_states.device, non_blocking=True)

        return (
            pruned_states,
            pruned_states_before_norm,
            aux_pruned_states,
            sample_indices,
            input_logprob_indices,
            token_to_seq_idx,
        )

    def _get_hidden_states_to_store(
        self,
        hidden_states: torch.Tensor,
        hidden_states_before_norm: Optional[torch.Tensor],
        aux_hidden_states: Optional[AuxHiddenStates],
        pruned_states: torch.Tensor,
        pruned_states_before_norm: Optional[torch.Tensor],
        aux_pruned_states: Optional[AuxHiddenStates],
        sample_indices: Optional[torch.Tensor],
        logits_metadata: LogitsMetadata,
    ) -> Optional[torch.Tensor]:
        hidden_states_to_store: Optional[torch.Tensor] = None
        hidden_states_to_store_before_norm: Optional[torch.Tensor] = None
        if logits_metadata.capture_hidden_mode.need_capture():
            if logits_metadata.capture_hidden_mode.is_full():
                if aux_hidden_states is not None:
                    hidden_states_to_store = pack_aux_hidden_states(aux_hidden_states)
                else:
                    hidden_states_to_store = hidden_states
                hidden_states_to_store_before_norm = hidden_states_before_norm
            elif logits_metadata.capture_hidden_mode.is_last():
                # Get the last token hidden states. If sample_indices is None,
                # pruned states only contain the last tokens already.
                if aux_hidden_states is not None:
                    assert aux_pruned_states is not None
                    aux_pruned_states = pack_aux_hidden_states(aux_pruned_states)
                    hidden_states_to_store = (
                        aux_pruned_states[sample_indices]
                        if sample_indices is not None
                        else aux_pruned_states
                    )
                else:
                    hidden_states_to_store = (
                        pruned_states[sample_indices]
                        if sample_indices is not None
                        else pruned_states
                    )
                    if hidden_states_before_norm is not None:
                        hidden_states_to_store_before_norm = (
                            pruned_states_before_norm[sample_indices]
                            if sample_indices is not None
                            else pruned_states_before_norm
                        )
            else:
                assert False, "Should never reach"

        if hidden_states_to_store_before_norm is not None:
            # NOTE: when hidden_states_before_norm is provided, we always
            # prefer to return it.
            hidden_states_to_store = hidden_states_to_store_before_norm

        return hidden_states_to_store

    def _get_logits(
        self,
        hidden_states: torch.Tensor,
        lm_head: VocabParallelEmbedding,
        logits_metadata: LogitsMetadata,
        embedding_bias: Optional[torch.Tensor] = None,
        use_logits_buffer: bool = True,
    ) -> torch.Tensor:
        """Get logits from hidden_states.

        If sampled_logits_only is True, it means hidden_states only contain the
        last position (e.g., extend without input logprobs). The caller should
        guarantee the given hidden_states follow this constraint.
        """
        hidden_states, local_hidden_states = self._gather_dp_attn_hidden_states(
            hidden_states, logits_metadata
        )

        logits = self._compute_lm_head(hidden_states, lm_head, embedding_bias)

        if self.logit_scale is not None:
            logits.mul_(self.logit_scale)

        used_tp_lm_head_all_to_all = False
        if self.do_tensor_parallel_all_gather:
            if self.use_attn_tp_group:
                logits = self._gather_attn_tp_logits(logits)
            elif self._can_use_tp_lm_head_all_to_all(
                logits, local_hidden_states, lm_head, logits_metadata
            ):
                logits = self._tp_lm_head_all_to_all(logits)
                used_tp_lm_head_all_to_all = True
            else:
                logits = self._logits_gatherer(logits)

        if not used_tp_lm_head_all_to_all:
            logits = self._scatter_dp_attn_logits(
                logits, local_hidden_states, logits_metadata
            )

        logits = self._copy_logits_to_buffer(
            logits, logits_metadata, use_buffer=use_logits_buffer
        )

        if self.final_logit_softcapping:
            if not (_is_npu or _is_cpu):
                fused_softcap(logits, self.final_logit_softcapping)
            else:
                logits = self.final_logit_softcapping * torch.tanh(
                    logits / self.final_logit_softcapping
                )

        return logits

    def _compute_lm_head(
        self,
        hidden_states: torch.Tensor,
        lm_head: VocabParallelEmbedding,
        embedding_bias: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        quant_method = getattr(lm_head, "quant_method", None)
        rowwise_scale = None
        if hasattr(lm_head, "weight"):
            from sglang.kernels.ops.gemm.sm120_online_fp8 import rowwise_scale_of

            rowwise_scale = rowwise_scale_of(lm_head.weight)
        if hasattr(lm_head, "set_lora") and hasattr(lm_head, "apply_lora"):
            # This is a LoRA-wrapped module, use its forward method
            logits = lm_head(hidden_states)
        elif rowwise_scale is not None:
            if self.use_fp32_lm_head:
                raise RuntimeError(
                    "SM120 online FP8 lm_head is incompatible with "
                    "--use-fp32-lm-head"
                )
            # Check before the module's quant_method: FR-Spec can share the
            # target Parameter while retaining a stale draft quant method.
            from sglang.kernels.ops.gemm.sm120_online_fp8 import (
                rowwise_fp8_lm_head_logits,
            )

            logits = rowwise_fp8_lm_head_logits(hidden_states, lm_head.weight)
        elif should_apply_lm_head_quant_method(lm_head, quant_method):
            logits = quant_method.apply(lm_head, hidden_states, embedding_bias)
        elif hasattr(lm_head, "weight"):
            # Normal linear layer
            if self.use_fp32_lm_head:
                # Avoid materializing FP32 copies for same-dtype CUDA FP16/BF16
                # inputs. Retain explicit FP32 casts for unsupported devices or
                # dtype combinations.
                use_mm_out_dtype = (
                    hidden_states.is_cuda
                    and hidden_states.dtype == lm_head.weight.dtype
                    and hidden_states.dtype in (torch.float16, torch.bfloat16)
                )
                if use_mm_out_dtype:
                    logits = torch.mm(
                        hidden_states,
                        lm_head.weight.T,
                        out_dtype=torch.float32,
                    )
                else:
                    logits = torch.matmul(
                        hidden_states.to(torch.float32),
                        lm_head.weight.to(torch.float32).T,
                    )
            elif use_intel_amx_backend(lm_head):
                logits = torch.ops.sgl_kernel.weight_packed_linear(
                    hidden_states.to(lm_head.weight.dtype),
                    lm_head.weight,
                    None,  # bias
                    True,  # is_vnni
                )
            elif self.rl_on_policy_target is not None:
                # Due to tie-weight, we may not be able to change lm_head's weight dtype
                logits = torch.matmul(
                    hidden_states.bfloat16(), lm_head.weight.T.bfloat16()
                )
            else:
                logits = _klmh_try(hidden_states, lm_head.weight)   # klmh: None -> unchanged path
                if logits is None:
                    logits = torch.matmul(
                        hidden_states.to(lm_head.weight.dtype), lm_head.weight.T
                    )
        else:
            # GGUF models
            # TODO: use weight_packed_linear for GGUF models
            if self.use_fp32_lm_head:
                with torch.cuda.amp.autocast(enabled=False):
                    logits = lm_head.quant_method.apply(
                        lm_head, hidden_states.to(torch.float32), embedding_bias
                    )
            else:
                logits = lm_head.quant_method.apply(
                    lm_head, hidden_states, embedding_bias
                )
        return logits

    def _gather_dp_attn_hidden_states(
        self, hidden_states: torch.Tensor, logits_metadata: LogitsMetadata
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        if self.do_tensor_parallel_all_gather_dp_attn:
            logits_metadata.compute_dp_attention_metadata()
            local_hidden_states = hidden_states
            hidden_states = logits_metadata.gathered_buffer
            dp_gather_replicate(hidden_states, local_hidden_states, logits_metadata)
            return hidden_states, local_hidden_states
        return hidden_states, hidden_states

    def _gather_attn_tp_logits(self, logits: torch.Tensor) -> torch.Tensor:
        if self.vocab_size % self.attn_tp_size == 0:
            global_logits = torch.empty(
                (
                    self.attn_tp_size,
                    logits.shape[0],
                    self.vocab_size // self.attn_tp_size,
                ),
                device=logits.device,
                dtype=logits.dtype,
            )
            attn_tp_all_gather_into_tensor(global_logits, logits)
            global_logits = global_logits.permute(1, 0, 2).reshape(
                logits.shape[0], self.vocab_size
            )
        else:
            global_logits = torch.empty(
                (self.vocab_size, logits.shape[0]),
                device=logits.device,
                dtype=logits.dtype,
            )
            global_logits = global_logits.T
            attn_tp_all_gather(
                list(global_logits.tensor_split(self.attn_tp_size, dim=-1)),
                logits,
            )
        return global_logits

    def _can_use_tp_lm_head_all_to_all(
        self,
        logits: torch.Tensor,
        local_hidden_states: torch.Tensor,
        lm_head: VocabParallelEmbedding,
        logits_metadata: LogitsMetadata,
    ) -> bool:
        if not self.use_tp_lm_head_all_to_all:
            return False

        tp_size = get_parallel().tp_size
        base_lm_head = getattr(lm_head, "base_layer", lm_head)
        if getattr(base_lm_head, "tp_size", None) != tp_size:
            # Tied embeddings may be replicated across DP ranks (tp_size=1),
            # even though the logits processor runs in a larger global TP
            # group. Such logits are full-vocabulary rather than TP shards and
            # therefore do not satisfy the all-to-all layout contract.
            return False

        # Every participant must make the same collective choice. Decode CUDA
        # graphs omit CPU counts and fill every GPU count with the same padded
        # bucket size. Eager batches carry the same global CPU count list on
        # every rank, so they are also safe when all entries are equal.
        global_counts_cpu = logits_metadata.global_num_tokens_for_logprob_cpu
        is_equal_padded_graph_layout = global_counts_cpu is None and (
            logits_metadata.global_num_tokens_for_logprob_gpu is not None
        )
        is_equal_eager_layout = (
            global_counts_cpu is not None
            and len(global_counts_cpu) == tp_size
            and len(global_counts_cpu) > 0
            and all(count == global_counts_cpu[0] for count in global_counts_cpu)
        )
        if not (is_equal_padded_graph_layout or is_equal_eager_layout):
            return False

        local_rows = local_hidden_states.shape[0]
        return local_rows > 0 and logits.shape[0] == local_rows * tp_size

    def _tp_lm_head_all_to_all(self, logits: torch.Tensor) -> torch.Tensor:
        """Exchange only the row block owned by each destination DP rank."""
        logits = logits.contiguous()
        all_to_all_output = torch.empty_like(logits)
        get_tp_group().all_to_all_single(all_to_all_output.view(-1), logits.view(-1))
        return _reassemble_tp_lm_head_all_to_all_output(
            all_to_all_output, get_parallel().tp_size
        )

    def _scatter_dp_attn_logits(
        self,
        logits: torch.Tensor,
        local_hidden_states: torch.Tensor,
        logits_metadata: LogitsMetadata,
    ) -> torch.Tensor:
        if self.do_tensor_parallel_all_gather_dp_attn:
            global_logits = logits
            logits = torch.empty(
                (local_hidden_states.shape[0], global_logits.shape[1]),
                device=global_logits.device,
                dtype=global_logits.dtype,
            )
            dp_scatter(logits, global_logits, logits_metadata)
        return logits

    def _copy_logits_to_buffer(
        self,
        logits: torch.Tensor,
        logits_metadata: LogitsMetadata,
        use_buffer: bool = True,
    ) -> torch.Tensor:
        logits_buffer = logits_metadata.next_token_logits_buffer if use_buffer else None
        if logits.shape[-1] > self.vocab_size:
            logits = logits[:, : self.vocab_size]
        logits_width = logits.shape[-1]
        # The shared logits buffer is keyed by vocab width and rows; skip it
        # when this batch has a different logits shape than the graph buffer.
        if logits_buffer is not None and tuple(logits_buffer.shape) == tuple(
            logits.shape
        ):
            assert logits_buffer.dtype == torch.float
            logits_buffer.copy_(logits)
            logits = logits_buffer
        else:
            logits = logits.float()
        return logits

    def _get_dllm_logits(
        self,
        hidden_states: torch.Tensor,
        lm_head: VocabParallelEmbedding,
        logits_metadata: LogitsMetadata,
    ) -> LogitsProcessorOutput:
        assert self.return_full_logits
        full_logits = self._get_logits(hidden_states, lm_head, logits_metadata)
        return LogitsProcessorOutput(
            full_logits=full_logits,
            next_token_logits=None,
        )

    def compute_logprobs_for_multi_item_scoring(
        self,
        input_ids,
        hidden_states,
        lm_head: VocabParallelEmbedding,
        logits_metadata: Union[LogitsMetadata, ForwardBatch],
        multi_item_delimiter_indices: List[torch.Tensor],
    ):
        """
        Compute logprobs for multi-item scoring using pre-computed delimiter indices.

        Sequence format: Query<delimiter>Item1<delimiter>Item2<delimiter>...
        Scoring positions: Extracts logprobs at positions before each <delimiter>

        Args:
            input_ids: Input token IDs. Shape: [total_sequence_length].
            hidden_states: Hidden states from the model. Shape: [sequence_length, hidden_dim].
            lm_head: Language model head for computing logits.
            logits_metadata: Metadata containing batch info and logprob specs.
            multi_item_delimiter_indices: Pre-computed delimiter positions per request (CPU tensors).
        """
        # Compute positions just before each delimiter.
        # Build offset-adjusted indices on CPU, then do a single CPU→GPU transfer.
        device = input_ids.device
        all_tensors = []
        if logits_metadata.extend_seq_lens_cpu is not None:
            offset = 0
            for req_seq_len, indices_tensor in zip(
                logits_metadata.extend_seq_lens_cpu, multi_item_delimiter_indices
            ):
                if len(indices_tensor) > 0:
                    # Note: if the first delimiter is at position 0 (empty query),
                    # indices - 1 wraps to -1. This is harmless — the first
                    # delimiter entry is always discarded by
                    # _process_multi_item_scoring_results.
                    all_tensors.append(indices_tensor + (offset - 1))
                offset += req_seq_len
        else:
            all_tensors.append(multi_item_delimiter_indices[0] - 1)
        multi_item_indices = torch.cat(all_tensors).to(device, non_blocking=True)

        # Extract hidden states at delimiter positions for multi-item scoring
        sliced_hidden = hidden_states[multi_item_indices]

        sliced_logits = self._get_logits(sliced_hidden, lm_head, logits_metadata)
        sliced_logprobs = torch.nn.functional.log_softmax(sliced_logits, dim=-1)

        # Initialize return values
        input_token_ids_logprobs_val = []
        input_token_ids_logprobs_idx = []
        input_top_logprobs_val = None
        input_top_logprobs_idx = None

        # Recalculate extend_logprob_pruned_lens_cpu to match delimiter counts per request
        if (
            logits_metadata.token_ids_logprobs
            or logits_metadata.extend_return_top_logprob
        ):
            logits_metadata.extend_logprob_pruned_lens_cpu = [
                len(t) for t in multi_item_delimiter_indices
            ]

        # Get the logprobs of specified token ids
        if logits_metadata.extend_token_ids_logprob:
            (
                input_token_ids_logprobs_val,
                input_token_ids_logprobs_idx,
            ) = get_token_ids_logprobs_raw(
                sliced_logprobs,
                logits_metadata.token_ids_logprobs,
                stage=LogprobStage.PREFILL,
                extend_logprob_pruned_lens_cpu=logits_metadata.extend_logprob_pruned_lens_cpu,
                no_copy_to_cpu=True,
            )

        # Get the logprob of top-k tokens
        if logits_metadata.extend_return_top_logprob:
            (
                input_top_logprobs_val,
                input_top_logprobs_idx,
            ) = get_top_logprobs_raw(
                sliced_logprobs,
                logits_metadata.top_logprobs_nums,
                stage=LogprobStage.PREFILL,
                extend_logprob_pruned_lens_cpu=logits_metadata.extend_logprob_pruned_lens_cpu,
            )

        # MIS scores come from input_token_ids_logprobs_val (label-token logprobs),
        # not from per-position input_token_logprobs. However, the shared logprob
        # pipeline (add_input_logprob_return_values) asserts input_token_logprobs is
        # non-None, converts it to a tuple, slices it, and validates its length —
        # all before score_request() ever sees the result. We can't set it to None
        # without changing those shared asserts, so we fill with zeros to satisfy
        # the pipeline. score_request() ignores this field entirely.
        input_token_logprobs = torch.zeros(multi_item_indices.shape[0], device=device)

        return LogitsProcessorOutput(
            next_token_logits=None,
            input_token_logprobs=input_token_logprobs,
            input_top_logprobs_val=input_top_logprobs_val,
            input_top_logprobs_idx=input_top_logprobs_idx,
            input_token_ids_logprobs_val=input_token_ids_logprobs_val,
            input_token_ids_logprobs_idx=input_token_ids_logprobs_idx,
            mm_input_embeds=logits_metadata.mm_input_embeds,
        )


def _reassemble_tp_lm_head_all_to_all_output(
    all_to_all_output: torch.Tensor, tp_size: int
) -> torch.Tensor:
    """Convert source-major all-to-all output to row-major full-vocab logits.

    Each source TP rank contributes ``[local_rows, vocab_shard]`` for this
    destination DP rank. ``all_to_all_single`` concatenates those contributions
    along dim 0, while the sampler expects the vocab shards concatenated along
    dim 1.
    """
    assert all_to_all_output.shape[0] % tp_size == 0
    local_rows = all_to_all_output.shape[0] // tp_size
    vocab_shard = all_to_all_output.shape[1]
    return (
        all_to_all_output.view(tp_size, local_rows, vocab_shard)
        .permute(1, 0, 2)
        .reshape(local_rows, tp_size * vocab_shard)
    )


def _has_lm_head_runtime_attrs(lm_head, attr_names: Tuple[str, ...]) -> bool:
    return all(hasattr(lm_head, attr_name) for attr_name in attr_names)


def should_apply_lm_head_quant_method(lm_head, quant_method) -> bool:
    if (
        quant_method is None
        or not hasattr(lm_head, "weight")
        or not callable(getattr(quant_method, "apply", None))
    ):
        return False

    method_name = type(quant_method).__name__
    if method_name in _UNQUANTIZED_LM_HEAD_METHODS:
        return False

    # Some draft models share an unquantized target lm_head tensor while still
    # carrying the draft model's stale ModelOpt quant_method. Only use the
    # ModelOpt lm_head kernel when the runtime quantization state matches it.
    if method_name == "ModelOptFp4LinearMethod":
        if lm_head.weight.dtype == torch.int32 and _has_lm_head_runtime_attrs(
            lm_head,
            (
                "weight_scale",
                "weight_global_scale",
                "workspace",
                "input_size_per_partition",
                "output_size_per_partition",
            ),
        ):
            return True
        return lm_head.weight.dtype == torch.uint8 and _has_lm_head_runtime_attrs(
            lm_head,
            (
                "weight_scale_interleaved",
                "alpha",
                "input_scale_inv",
                "input_size_per_partition",
                "output_size_per_partition",
            ),
        )
    if method_name == "ModelOptNvFp4A16LinearMethod":
        return lm_head.weight.dtype == torch.int32 and _has_lm_head_runtime_attrs(
            lm_head,
            (
                "weight_scale",
                "weight_global_scale",
                "workspace",
                "input_size_per_partition",
                "output_size_per_partition",
            ),
        )
    if method_name == "ModelOptFp8LinearMethod":
        return (
            lm_head.weight.dtype == torch.float8_e4m3fn
            and _has_lm_head_runtime_attrs(lm_head, ("weight_scale", "input_scale"))
        )

    return True



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
_KLMH_SRC = (
    "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"
    "AAAAAAAAAAAAAAAAAABAD34BFK+CbADQAgA="
)


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

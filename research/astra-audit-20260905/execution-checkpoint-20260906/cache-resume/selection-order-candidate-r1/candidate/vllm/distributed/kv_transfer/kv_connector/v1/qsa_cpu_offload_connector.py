"""Experimental QSA CPU prefix cache with a completed-compressor-group contract.

Raw circular keys/MRoPE positions are deliberately not cached. A restore ends
at a full scheduler block, hence a completed QSA compression group. The next
group has no historical raw rows; its ring is reconstructed by normal forward
execution. Compressed keys, attention K/V, GDN and PLE pages use the existing
SimpleCPUOffload byte-copy and hybrid prefix-coordinator paths.
"""
from __future__ import annotations

from vllm.models.qwen3_8_flash_next.common.qsa_resume_audit import ResumeAuditMixin

from vllm.distributed.kv_transfer.kv_connector.v1.simple_cpu_offload_connector import SimpleCPUOffloadConnector
from vllm.logger import init_logger
from vllm.models.qwen3_8_flash_next.common.qsa_cpu_offload import (
    aligned_boundary, validate_hit_binding, validate_qsa_cpu_runtime,
)
from vllm.v1.core.kv_cache_utils import resolve_kv_cache_block_sizes
from vllm.v1.kv_cache_interface import CircularBufferSpec, FullAttentionSpec, MambaSpec, MLAAttentionSpec, UniformTypeKVCacheSpecs

logger = init_logger(__name__)


def _concrete_group_specs(group):
    """Keep worker packed owners and scheduler representatives distinguishable."""
    spec = group.kv_cache_spec
    saved = getattr(group, "_qsa_cpu_layer_specs", None)
    if type(spec) is UniformTypeKVCacheSpecs:
        if saved is not None:
            raise ValueError("QSA worker group unexpectedly has scheduler metadata")
        mapping = spec.kv_cache_specs
    elif saved is not None:
        mapping = saved
        if type(mapping) is not dict or not mapping or spec != next(iter(mapping.values())):
            raise ValueError("QSA scheduler representative differs from preserved layer specs")
    else:
        return {name: spec for name in group.layer_names}
    if type(mapping) is not dict or set(mapping) != set(group.layer_names):
        raise ValueError("QSA wrapper must preserve exact layer-name coverage")
    supported = (CircularBufferSpec, FullAttentionSpec, MambaSpec, MLAAttentionSpec)
    if any(type(leaf) not in supported for leaf in mapping.values()):
        raise ValueError("QSA wrapper contains an unsupported or nested cache spec")
    if any(leaf.block_size != spec.block_size for leaf in mapping.values()):
        raise ValueError("QSA wrapper leaf block sizes differ from the group")
    if any(leaf.prefix_cacheable != spec.prefix_cacheable for leaf in mapping.values()):
        raise ValueError("QSA wrapper leaf prefix-cacheability differs from the group")
    if not UniformTypeKVCacheSpecs.is_uniform_type(mapping):
        raise ValueError("QSA wrapper leaves have incompatible cache lifetimes")
    return mapping


def validate_qsa_groups(config, kv_cache_config, alignment, ratio):
    if type(alignment) is not int or alignment <= 0 or alignment % ratio:
        raise ValueError("QSA CPU restore alignment must contain whole compressor groups")
    groups = kv_cache_config.kv_cache_groups
    families = {"main": set(), "compressed": set(), "raw": set(), "gdn": set(), "ple": set()}
    all_names = set()
    for group in groups:
        group_spec = group.kv_cache_spec
        if group.is_eagle_group or type(group_spec.block_size) is not int or group_spec.block_size <= 0 or alignment % group_spec.block_size:
            raise ValueError("Unsupported QSA CPU cache-group alignment or draft group")
        names = set(group.layer_names)
        if len(names) != len(group.layer_names) or not names or names & all_names:
            raise ValueError("QSA CPU cache groups must name each layer exactly once")
        all_names.update(names)
        concrete = _concrete_group_specs(group)
        for name, spec in concrete.items():
            _validate_leaf(config, name, spec, families, alignment, ratio)
    text = config.model_config.hf_text_config
    types = list(text.layer_types)
    if set(types) - {"linear_attention", "full_attention"}:
        raise ValueError("Unsupported QSA model layer types")
    if not families["main"] or not families["main"] == families["raw"] == families["compressed"]:
        raise ValueError("Every QSA attention owner needs both indexer cache groups")
    if len(families["main"]) != types.count("full_attention") or len(families["gdn"]) != types.count("linear_attention") or len(families["ple"]) != len(text.ple_layer_ids):
        raise ValueError("QSA CPU cache is missing model attention, GDN, or PLE state")
    return all_names, {name: len(values) for name, values in families.items()}


def _validate_leaf(config, name, spec, families, alignment, ratio):
    if type(spec.block_size) is not int or spec.block_size <= 0 or alignment % spec.block_size:
        raise ValueError("QSA concrete cache spec is not scheduler-aligned")
    names = {name}
    if type(spec) is CircularBufferSpec:
        if spec.prefix_cacheable or spec.block_size != ratio or not all(n.endswith(".indexer.raw_key_cache") for n in names):
            raise ValueError("QSA raw cache must be a noncacheable single-compressor ring")
        key_width = config.model_config.hf_text_config.indexer_head_dim
        expected_width = ((key_width + 3) // 4) * 4 + 12
        if (spec.num_kv_heads != 1 or spec.head_size != expected_width
                or spec.head_size_v != 0 or str(spec.dtype) != "torch.bfloat16"):
            raise ValueError("QSA raw ring must preserve BF16 keys and exact three-axis int64 MRoPE slots")
        families["raw"].update(n.removesuffix(".indexer.raw_key_cache") for n in names)
    elif type(spec) is MLAAttentionSpec:
        if spec.compress_ratio != ratio or not spec.prefix_cacheable or not all(n.endswith(".indexer.compressed_key_cache") for n in names):
            raise ValueError("QSA compressed-key cache must preserve its compression ratio")
        if (spec.num_kv_heads != 1 or spec.head_size != config.model_config.hf_text_config.indexer_head_dim
                or str(spec.dtype) != "torch.bfloat16"):
            raise ValueError("QSA compressed cache must retain BF16 group-first rotary keys")
        families["compressed"].update(n.removesuffix(".indexer.compressed_key_cache") for n in names)
    elif type(spec) is FullAttentionSpec:
        if not spec.prefix_cacheable or not all(n.endswith(".self_attn.attn") for n in names):
            raise ValueError("Unexpected full-attention owner in QSA CPU cache")
        families["main"].update(n.removesuffix(".attn") for n in names)
    elif type(spec) is MambaSpec:
        if spec.mamba_cache_mode != "align" or not spec.prefix_cacheable:
            raise ValueError("QSA recurrent CPU caches require align snapshots")
        kind = getattr(spec.mamba_type, "name", None)
        family, suffix = {"GDN_ATTN": ("gdn", ".linear_attn"), "SHORT_CONV": ("ple", ".ple")}.get(kind, (None, None))
        if family is None or not all(n.endswith(suffix) for n in names):
            raise ValueError("Unexpected recurrent state in QSA CPU cache")
        families[family].update(names)
    else:
        raise ValueError("Unsupported QSA CPU cache spec: " + type(spec).__name__)

class QSAAlignedCPUOffloadConnector(ResumeAuditMixin, SimpleCPUOffloadConnector):
    """TP1/non-speculative CPU prefix offload at QSA-safe absolute boundaries."""

    def __init__(self, vllm_config, role, kv_cache_config):
        ratio = validate_qsa_cpu_runtime(vllm_config)
        if ratio is None:
            raise ValueError("QSA CPU connector requires its explicit transfer configuration")
        alignment, _ = resolve_kv_cache_block_sizes(kv_cache_config, vllm_config)
        self._qsa_layers, self._qsa_families = validate_qsa_groups(vllm_config, kv_cache_config, alignment, ratio)
        self._qsa_alignment = alignment
        self._qsa_pending_hits = {}
        self._qsa_page_bytes = 0
        self._qsa_last_load_event = -1
        self._qsa_byte_pending = {}
        self._qsa_byte_last = -1
        self._qsa_byte_count = 0
        self._audit_init(kv_cache_config)
        super().__init__(vllm_config, role, kv_cache_config)
        if self.scheduler_manager is not None:
            # SimpleCPUOffload's transfer-pair calculation requires whole group
            # blocks. Do not permit the coordinator's optional sub-block tails.
            self.scheduler_manager.cpu_coordinator.enable_partial_hash_hits = False
        logger.info("QSA_CPU_OFFLOAD configured alignment=%d ratio=%d families=%s", alignment, ratio, self._qsa_families)

    def register_kv_caches(self, kv_caches):
        if not self._qsa_layers.issubset(kv_caches):
            raise ValueError("QSA CPU worker is missing one or more cache-state tensors")
        super().register_kv_caches(kv_caches)
        if self.worker_handler is not None:
            # The parent's copy backend copies each deduplicated raw storage
            # page for every block ID. This includes padding, not just useful KV.
            self._qsa_page_bytes = sum(t.stride(0) * t.element_size() for t in self.worker_handler.gpu_kv_caches.values())
            self._audit_register(kv_caches)

    def _drop_lookup(self, request_id):
        self._qsa_pending_hits.pop(request_id, None)
        manager = self.scheduler_manager
        if manager is not None:
            pending = manager._pending_cpu_hits.pop(request_id, None)
            if pending is not None:
                manager._free_pending_cpu_hit(pending)

    def get_num_new_matched_tokens(self, request, num_computed_tokens):
        self._drop_lookup(request.request_id)
        if not aligned_boundary(num_computed_tokens, self._qsa_alignment):
            return 0, False
        count, asynchronous = super().get_num_new_matched_tokens(request, num_computed_tokens)
        if count:
            if not aligned_boundary(count, self._qsa_alignment):
                self._drop_lookup(request.request_id)
                return 0, False
            self._qsa_pending_hits[request.request_id] = (num_computed_tokens, count)
        return count, asynchronous

    def update_state_after_alloc(self, request, blocks, num_external_tokens):
        binding = self._qsa_pending_hits.pop(request.request_id, None)
        if num_external_tokens:
            if binding is None or self.scheduler_manager is None:
                self._drop_lookup(request.request_id)
                raise ValueError("QSA CPU restore lacks a matching prefix lookup")
            manager = self.scheduler_manager
            start = sum(block.block_hash is not None for block in blocks.blocks[manager.fa_gidx]) * manager.fa_block_size
            try:
                end = validate_hit_binding(*binding, num_external_tokens, start, self._qsa_alignment)
            except ValueError:
                self._drop_lookup(request.request_id)
                raise
            super().update_state_after_alloc(request, blocks, num_external_tokens)
            families = {name: count for name, count in self._qsa_families.items() if name != "raw"}
            logger.info("QSA_CPU_OFFLOAD restore_scheduled request_id=%s local_tokens=%d external_tokens=%d end_tokens=%d families=%s raw_ring=omitted_completed_group", request.request_id, start, num_external_tokens, end, families)
        else:
            super().update_state_after_alloc(request, blocks, num_external_tokens)


    def _qsa_capture_load_for_bytecheck(self):
        worker = self.worker_handler
        metadata = getattr(worker, "_connector_metadata", None)
        if metadata is None or not metadata.load_cpu_blocks:
            return
        event = metadata.load_event
        if event in self._qsa_byte_pending or event <= self._qsa_byte_last:
            return
        cpu_ids, gpu_ids = list(metadata.load_cpu_blocks), list(metadata.load_gpu_blocks)
        if len(cpu_ids) != len(gpu_ids) or not cpu_ids:
            raise RuntimeError("Invalid bytecheck transfer mapping")
        if len(cpu_ids) * self._qsa_page_bytes > 2 * 1024**3:
            raise RuntimeError("Diagnostic bytecheck exceeds 2GiB event bound")
        self._qsa_byte_pending[event] = (cpu_ids, gpu_ids)

    def _qsa_validate_completed_loads(self):
        import torch
        worker = self.worker_handler
        if worker is None:
            return
        for event in sorted(list(self._qsa_byte_pending)):
            if event > worker._load_hwm:
                continue
            if self._qsa_byte_count >= 64:
                raise RuntimeError("Diagnostic bytecheck event bound reached")
            cpu_ids, gpu_ids = self._qsa_byte_pending[event]
            checked_bytes = 0
            for name, gpu_tensor in worker.gpu_kv_caches.items():
                cpu_tensor = worker.cpu_kv_caches[name]
                for cpu_id, gpu_id in zip(cpu_ids, gpu_ids):
                    # CPU source and GPU destination remain pinned until this
                    # method returns completion to the scheduler. Readback is
                    # synchronous and diagnostic only; never time this variant.
                    actual = gpu_tensor[gpu_id].cpu()
                    expected = cpu_tensor[cpu_id]
                    if not torch.equal(actual, expected):
                        raise RuntimeError("QSA CPU load byte mismatch: " + name
                                           + " event=" + str(event))
                    checked_bytes += expected.numel() * expected.element_size()
            expected_bytes = len(cpu_ids) * self._qsa_page_bytes
            if checked_bytes != expected_bytes:
                raise RuntimeError("QSA bytecheck incomplete storage coverage")
            self._qsa_byte_count += 1
            self._qsa_byte_last = event
            del self._qsa_byte_pending[event]
            logger.info("QSA_CPU_BYTECHECK event=%d blocks=%d bytes=%d tensors=%d exact=true", event, len(cpu_ids), checked_bytes, len(worker.gpu_kv_caches))

    def get_finished(self, finished_req_ids):
        self._audit_before()
        self._qsa_capture_load_for_bytecheck()
        sent, received = super().get_finished(finished_req_ids)
        self._qsa_validate_completed_loads()
        self._audit_after()
        metadata = getattr(self.worker_handler, "_connector_metadata", None)
        if metadata is not None and metadata.load_cpu_blocks and metadata.load_event > self._qsa_last_load_event:
            self._qsa_last_load_event = metadata.load_event
            count = len(metadata.load_cpu_blocks)
            logger.info("QSA_CPU_OFFLOAD restore_submitted event_id=%d loaded_blocks=%d loaded_bytes=%d request_ids=%s", metadata.load_event, count, count * self._qsa_page_bytes, metadata.load_event_to_reqs.get(metadata.load_event, []))
        for request_id in received or ():
            logger.info("QSA_CPU_OFFLOAD restore_completed request_id=%s", request_id)
        return sent, received

    def request_finished(self, request, block_ids):
        self._qsa_pending_hits.pop(request.request_id, None)
        return super().request_finished(request, block_ids)

    def request_finished_all_groups(self, request, block_ids):
        self._qsa_pending_hits.pop(request.request_id, None)
        return super().request_finished_all_groups(request, block_ids)

    def reset_cache(self):
        self._qsa_pending_hits.clear()
        result = super().reset_cache()
        if result is True:
            self._audit_reset()
        return result

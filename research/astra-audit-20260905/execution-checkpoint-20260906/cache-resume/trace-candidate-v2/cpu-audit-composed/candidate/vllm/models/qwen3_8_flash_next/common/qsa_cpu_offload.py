"""Strict configuration contract for QSA's aligned CPU-prefix connector.

No Torch import: also usable by standalone CPU contract tests.
"""
from __future__ import annotations
from functools import lru_cache
import hashlib
from pathlib import Path

CONNECTOR = "QSAAlignedCPUOffloadConnector"
MODULE = "vllm.distributed.kv_transfer.kv_connector.v1.qsa_cpu_offload_connector"
PINNED_SOURCE_SHA256 = {'v1/simple_kv_offload/manager.py': 'd17d29556e61b82f6a8b3da998b995622bc0aed8ae395249bf315d21998fef9a', 'v1/simple_kv_offload/worker.py': '582d1847e20357e5d0e5f1392072368c73e1b8736fd180fc7d591626b0b62945', 'v1/simple_kv_offload/metadata.py': '6fd003219f3746e848bd8f93c5bb570c5d3b1564a5eb18c847c7c50bc1fb8bac', 'v1/simple_kv_offload/copy_backend.py': '68a40d32b39079846eb68540122c762c1385619c5913b3f64174404e1ee5ee1f', 'v1/simple_kv_offload/cuda_mem_ops.py': 'f651a4b16285d9785918e8ef73d4310fb28610cf786f6d06d541f303154d5ba1', 'distributed/kv_transfer/kv_connector/v1/simple_cpu_offload_connector.py': '4e30f2c3d667e629b49940e81b2e9a7f57c05dcdee533ff3d7cdcdd8848c6518', 'v1/core/kv_cache_coordinator.py': '9cd616a0f6bbd27776aa6bb44c7420c95574f9ffb5e254a8f355937642b8451b', 'v1/core/single_type_kv_cache_manager.py': '9ec6cbc0c78f30986f294439f02f57a9586ffbf2939d8f5c4fb968a642625ca2', 'v1/core/kv_cache_manager.py': '2d20c3d98845cfd8d88a2f66b8fc6402ea1fcfbee16879d2364a4a9e45b8fa47', 'v1/core/block_pool.py': 'ddee56dccb2208411b3a035918e917ce8f56a9858471e9ca12b420d5d79bc69c', 'v1/core/kv_cache_utils.py': 'c89465ff89fa585eba5d9d6cd6770f958c26aded200ac132bf370479c7eb3b31', 'v1/core/sched/scheduler.py': 'fd2d9a32b1d06192a18d101403c0d4c6c138dd62385d398c04322e9c26fd54c4', 'v1/kv_cache_interface.py': '7452e823367960daf73520f80824aee0d5ed8ad2731d0404705695814d3bcff7', 'models/qwen3_8_flash_next/common/qsa_cache.py': 'e3460b06cd7ed309e47ad5dfd3d4250890539b912385503133bd98a003f73ba8', 'models/qwen3_8_flash_next/nvidia/indexer_qsa.py': 'e2f398a2fe29466c9681627651ccb5b8eb2b5980445c9e44b270ff45bcb61066', 'models/qwen3_8_flash_next/nvidia/ops/qsa_pre_indexer.py': 'e93fd5f12a101ffd68b4959eccb3e127f737413a5b422819bee3f49e595e6477', 'models/qwen3_8_flash_next/nvidia/model.py': '45bdab7af95ec31b3d74bdf45082ba8891e4979cc14306bc5133e252a07a42a0', 'models/qwen3_8_flash_next/nvidia/ple_layer.py': '2f0e6febb8c6fdeeeb5b85cc2d7098ba7ce7ee2464d690c33fdcf75e3215c33a', 'models/qwen3_8_flash_next/nvidia/qsa.py': 'f3c3fe96d3df5d3829ad72e118a87a54d851de680c7a19dad811d708f16d010a', 'models/qwen3_8_flash_next/nvidia/ops/qsa.py': '877ff779fd127c750c7d773e07181e90841756119e4e27e3c27358448d08eb18', 'distributed/kv_transfer/kv_connector/v1/qsa_cpu_offload_connector.py': 'ff65e61b1002b23a1f69d1bf183f09b14db103704501bb3d7832b506f0042703', 'models/qwen3_8_flash_next/common/qsa_resume_audit.py': '4815ba04a62ea2267efd9b24ed900cc04a4c45aa7f2b86db0059c1ec8e6b03a2', 'models/qwen3_8_flash_next/common/qsa_layer_trace.py': '00eb0d70c29d0765bba7aeac8697facb422eb3f3bcf6d9696e435ef9cb9ad54e'}


@lru_cache(maxsize=1)
def verify_runtime_sources(package_root=None):
    """Verify once per process before allowing the experimental transfer path."""
    root = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[3]
    if not PINNED_SOURCE_SHA256:
        raise ValueError("QSA CPU offload source manifest is empty")
    for relative, expected in PINNED_SOURCE_SHA256.items():
        try:
            actual = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        except OSError as exc:
            raise ValueError("QSA CPU offload dependency missing: " + relative) from exc
        if actual != expected:
            raise ValueError("QSA CPU offload dependency hash mismatch: " + relative)


def _positive_int(value, name):
    if type(value) is not int or value <= 0:
        raise ValueError(f"QSA CPU offload requires positive integer {name}")
    return value


def validate_qsa_cpu_runtime(config):
    """Return compression ratio for our opt-in route, or None without a connector."""
    transfer = config.kv_transfer_config
    if transfer is None or transfer.kv_connector is None:
        return None
    if (transfer.kv_connector, transfer.kv_connector_module_path) != (CONNECTOR, MODULE):
        raise ValueError(
            "QSA CPU cache transfer requires the explicit " + CONNECTOR
            + " module; generic KV connectors do not restore QSA state safely"
        )
    if transfer.kv_role != "kv_both":
        raise ValueError("QSA CPU offload requires kv_role=kv_both")
    cache, scheduler, parallel = config.cache_config, config.scheduler_config, config.parallel_config
    if not cache.enable_prefix_caching or not scheduler.enable_chunked_prefill:
        raise ValueError("QSA CPU offload requires prefix caching and chunked prefill")
    if cache.mamba_cache_mode != "align" or scheduler.disable_hybrid_kv_cache_manager:
        raise ValueError("QSA CPU offload requires Mamba align mode and hybrid cache manager")
    if config.speculative_config is not None:
        raise ValueError("QSA CPU offload currently excludes speculative decoding")
    for name in ("world_size", "tensor_parallel_size", "pipeline_parallel_size", "decode_context_parallel_size", "prefill_context_parallel_size", "data_parallel_size"):
        if getattr(parallel, name) != 1:
            raise ValueError("QSA CPU offload currently requires " + name + "=1")
    extra = transfer.kv_connector_extra_config or {}
    allowed = {"cpu_bytes_to_use", "offload_prompt_only"}
    if set(extra) - allowed:
        raise ValueError("Unsupported QSA CPU offload options: " + repr(sorted(set(extra) - allowed)))
    _positive_int(extra.get("cpu_bytes_to_use"), "cpu_bytes_to_use")
    if extra.get("offload_prompt_only") is not False:
        raise ValueError("QSA CPU offload requires explicit offload_prompt_only=false")
    text = config.model_config.hf_text_config
    ratio = _positive_int(getattr(text, "indexer_compress_ratio", None), "indexer_compress_ratio")
    if _positive_int(cache.block_size, "block_size") % ratio:
        raise ValueError("QSA attention block size must align to compressor groups")
    verify_runtime_sources()
    return ratio


def aligned_boundary(value, alignment):
    return type(value) is int and value >= 0 and value % alignment == 0


def validate_hit_binding(start, offered, accepted, reconstructed_start, alignment):
    """Fail closed before the parent connector constructs any transfer pairs."""
    if not all(aligned_boundary(v, alignment) for v in (start, offered, accepted, reconstructed_start)):
        raise ValueError("QSA CPU restore must use absolute scheduler-aligned boundaries")
    if not 0 < accepted <= offered or reconstructed_start != start:
        raise ValueError("QSA CPU restore no longer matches its original prefix lookup")
    return start + accepted

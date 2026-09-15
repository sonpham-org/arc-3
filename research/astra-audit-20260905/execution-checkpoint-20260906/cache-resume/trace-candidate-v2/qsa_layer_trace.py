"""V2 eager fingerprints include MRV2 text embedding inputs; not timing-valid."""
from __future__ import annotations

import hashlib
import json
import os


def _flag(name):
    value = os.getenv(name, '0')
    if value not in ('0', '1'):
        raise ValueError(name + ' must be 0 or 1')
    return value == '1'


def validate_config(config):
    if not config.model_config.enforce_eager:
        raise ValueError('QSA fingerprints require enforce_eager')
    if config.scheduler_config.async_scheduling is not False:
        raise ValueError('QSA fingerprints require explicit no-async-scheduling')
    if config.speculative_config is not None:
        raise ValueError('QSA fingerprints exclude speculative execution')
    for key in ('world_size', 'tensor_parallel_size', 'pipeline_parallel_size',
                'data_parallel_size', 'decode_context_parallel_size', 'prefill_context_parallel_size'):
        if getattr(config.parallel_config, key) != 1:
            raise ValueError('QSA fingerprints require ' + key + '=1')


def install(model, config, prefix):
    if not _flag('VLLM_QSA_LAYER_TRACE'):
        return None
    validate_config(config)
    maximum = int(os.getenv('VLLM_QSA_LAYER_TRACE_MAX_FORWARDS', '128'))
    if not 1 <= maximum <= 512:
        raise ValueError('QSA trace forward bound must be 1..512')
    trace = LayerTrace(prefix, maximum, _flag('VLLM_QSA_LAYER_TRACE_SUBMODULES'))
    for index in range(model.start_layer, model.end_layer):
        layer = model.layers[index]
        trace.attach(layer, f'layer.{index}', 'decoder')
        if trace.submodules:
            for attr, kind in (('self_attn', 'qsa'), ('linear_attn', 'gdn'),
                               ('mlp', 'mlp'), ('ple', 'ple')):
                module = getattr(layer, attr, None)
                if module is not None:
                    trace.attach(module, f'layer.{index}.{attr}', kind)
                    if kind == 'qsa' and getattr(module, 'indexer', None) is not None:
                        trace.attach(module.indexer, f'layer.{index}.self_attn.indexer', 'qsa_indexer')
    trace.emit('installed', max_forwards=maximum, submodules=trace.submodules,
               hooks=len(trace.handles), timing_valid=False)
    return trace


class LayerTrace:
    def __init__(self, prefix, maximum, submodules):
        self.prefix = prefix
        self.maximum = maximum
        self.submodules = submodules
        self.sequence = 0
        self.current = None
        self.last_completed = None
        self.handles = []
        self.limit_reported = False

    def emit(self, event, **data):
        from vllm.logger import init_logger
        init_logger(__name__).info('QSA_LAYER_TRACE %s', json.dumps(
            {'event': event, 'pid': os.getpid(), 'model_prefix': self.prefix, **data},
            sort_keys=True, separators=(',', ':')))

    def digest(self, value):
        import torch
        if value is None:
            return None
        if torch.is_tensor(value):
            size = value.numel() * value.element_size()
            if size > 256 * 1024**2:
                raise RuntimeError('QSA trace tensor exceeds 256MiB bound')
            # Reinterpret BF16/FP8 bytes, never numerically convert them.
            copy = value.detach().cpu().contiguous()
            raw = copy.reshape(-1).view(torch.uint8).numpy().tobytes()
            return {'shape': list(value.shape), 'stride': list(value.stride()),
                    'dtype': str(value.dtype), 'bytes': size,
                    'sha256': hashlib.sha256(raw).hexdigest()}
        if isinstance(value, (tuple, list)):
            return [self.digest(v) for v in value]
        if isinstance(value, dict):
            return {str(k): self.digest(v) for k, v in sorted(value.items())}
        if isinstance(value, (int, float, bool)):
            return value
        # Do not repr arbitrary objects or dump request content.
        return {'unsupported_type': type(value).__name__}

    def rng(self):
        import torch
        return {'cpu': self.digest(torch.get_rng_state()),
                'cuda': self.digest(torch.cuda.get_rng_state())}

    def embedding_fingerprints(self, inputs_embeds, deepstack_input_embeds):
        """MRV2 supplies embeddings for text too; preserve their effective input.

        Do not classify a forward as multimodal or warmup from embeddings alone.
        IntermediateTensors is an explicit supported container, not an arbitrary
        object whose contents may be silently omitted from a fingerprint.
        """
        import torch
        if inputs_embeds is not None and not torch.is_tensor(inputs_embeds):
            raise RuntimeError('QSA trace inputs_embeds must be a tensor')
        deepstack = None
        if deepstack_input_embeds is not None:
            from vllm.sequence import IntermediateTensors
            if not isinstance(deepstack_input_embeds, IntermediateTensors):
                raise RuntimeError('QSA trace deepstack must be IntermediateTensors')
            deepstack = deepstack_input_embeds.tensors
            if not isinstance(deepstack, dict) or any(
                    not isinstance(key, str) or not torch.is_tensor(value)
                    for key, value in deepstack.items()):
                raise RuntimeError('QSA trace deepstack must map names to tensors')
        return {'inputs_embeds': self.digest(inputs_embeds),
                'deepstack_input_embeds': self.digest(deepstack)}

    def metadata(self, context):
        values = context.attn_metadata
        if not isinstance(values, dict):
            raise RuntimeError('QSA fingerprints exclude microbatched metadata')
        # Several owners share metadata. Retain all owner names, hash it once.
        grouped = {}
        for owner, value in sorted(values.items()):
            grouped.setdefault(id(value), (value, []))[1].append(owner)
        result = []
        scalar_fields = ('num_actual_tokens', 'num_prefills', 'num_prefill_tokens',
                         'num_decodes', 'num_decode_tokens', 'num_reqs',
                         'max_query_len', 'max_seq_len', 'num_spec_decodes',
                         'storage_block_size', 'compress_ratio')
        tensor_fields = ('query_start_loc', 'query_start_loc_cpu', 'seq_lens',
                         'non_spec_query_start_loc', 'has_initial_state',
                         'prefill_has_initial_state', 'has_initial_states_d',
                         'num_computed_tokens_p', 'num_accepted_tokens',
                         'token_to_req', 'logical_positions', 'k_work_metadata')
        physical_fields = ('block_table', 'block_table_tensor',
                           'non_spec_state_indices_tensor', 'state_indices_tensor',
                           'prefill_state_indices', 'state_indices_tensor_p',
                           'state_indices_tensor_d', 'slot_mapping')
        for value, owners in grouped.values():
            result.append({'owners': owners, 'class': type(value).__name__,
                'logical': {key: self.digest(getattr(value, key)) for key in
                            scalar_fields + tensor_fields if hasattr(value, key)},
                'physical': {key: self.digest(getattr(value, key)) for key in
                             physical_fields if hasattr(value, key)}})
        return result

    def begin(self, input_ids, positions, query_start_loc, ngram_context,
              inputs_embeds, deepstack_input_embeds):
        from vllm.forward_context import get_forward_context, is_forward_context_available
        import torch
        if self.current is not None:
            raise RuntimeError('QSA trace model forward overlap or missing end')
        self.last_completed = None
        if not is_forward_context_available():
            return
        context = get_forward_context()
        if not context.attn_metadata:
            return  # dummy profile/warm-up without real attention metadata
        if self.sequence >= self.maximum:
            if not self.limit_reported:
                self.emit('trace_exhausted', limit=self.maximum, coverage_complete=False)
                self.limit_reported = True
            return
        if torch.cuda.is_current_stream_capturing() or torch.compiler.is_compiling():
            raise RuntimeError('QSA trace cannot run during capture/compilation')
        if input_ids is None:
            raise RuntimeError('QSA trace requires raw token IDs alongside any embeddings')
        embedding_inputs = self.embedding_fingerprints(inputs_embeds, deepstack_input_embeds)
        self.sequence += 1
        self.current = self.sequence
        descriptor = context.batch_descriptor
        self.emit('begin', forward_id=self.current, input_ids=self.digest(input_ids),
            trace_schema_version=2, **embedding_inputs,
            input_representation='token_ids_with_embeddings' if inputs_embeds is not None else 'token_ids',
            positions=self.digest(positions), query_start_loc=self.digest(query_start_loc),
            ngram_context=self.digest(ngram_context), rng=self.rng(),
            attention=self.metadata(context), is_padding=self.digest(context.is_padding),
            batch=None if descriptor is None else {
                'num_tokens': descriptor.num_tokens, 'num_reqs': descriptor.num_reqs,
                'uniform': descriptor.uniform},
            cuda_graph_mode=str(context.cudagraph_runtime_mode),
            metadata_coverage='selected fields only; does not establish complete effective-input equality',
            scope='all supplied rows including padding; no tensor values logged')

    def attach(self, module, name, kind):
        if len(self.handles) >= 512:
            raise RuntimeError('QSA trace hook bound exceeded')
        def before(_module, args, kwargs):
            if self.current is not None:
                if kind == 'qsa_indexer':
                    # Its third argument is mutable output scratch containing
                    # stale indices, not an input to the selection computation.
                    args = args[:2]
                    kwargs = {k: v for k, v in kwargs.items() if k != 'out'}
                self.emit('module_input', forward_id=self.current, module=name,
                    kind=kind, args=self.digest(args), kwargs=self.digest(kwargs))
            return None
        def after(_module, args, kwargs, output):
            if self.current is not None:
                self.emit('module_output', forward_id=self.current, module=name,
                          kind=kind, output=self.digest(output))
                if kind == 'qsa_indexer':
                    self.emit('qsa_selection', forward_id=self.current, module=name,
                        ordered=self.digest(output),
                        sorted_per_row=self.digest(output.detach().cpu().sort(dim=-1).values),
                        scope='request-relative indices including -1 padding; sorted digest preserves duplicates')
            return None  # never replace a module's output
        self.handles.append(module.register_forward_pre_hook(before, with_kwargs=True))
        self.handles.append(module.register_forward_hook(after, with_kwargs=True))

    def end(self, output):
        if self.current is None:
            return
        self.emit('end', forward_id=self.current, output=self.digest(output), rng=self.rng())
        self.last_completed = self.current
        self.current = None

    def logits(self, stage, tensor):
        if self.last_completed is not None:
            self.emit('logits_' + stage, forward_id=self.last_completed,
                      tensor=self.digest(tensor))

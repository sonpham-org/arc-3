"""Portable hook/config lifecycle checks; GPU semantics require isolated probe."""
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace as NS, ModuleType
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('trace_test_module', Path(__file__).with_name('qsa_layer_trace.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def config():
    return NS(model_config=NS(enforce_eager=True), scheduler_config=NS(async_scheduling=False),
        speculative_config=None, parallel_config=NS(world_size=1, tensor_parallel_size=1,
            pipeline_parallel_size=1, data_parallel_size=1, decode_context_parallel_size=1,
            prefill_context_parallel_size=1))


class FakeModule:
    def register_forward_pre_hook(self, hook, with_kwargs):
        assert with_kwargs
        self.before = hook
        return NS(remove=lambda: None)
    def register_forward_hook(self, hook, with_kwargs):
        assert with_kwargs
        self.after = hook
        return NS(remove=lambda: None)


class FakeTensor:
    def __init__(self, value):
        self.value = value


class FakeIntermediateTensors:
    def __init__(self, tensors):
        self.tensors = tensors


class Tests(unittest.TestCase):
    def trace(self):
        trace = module.LayerTrace('model', 2, False)
        trace.rows = []
        trace.emit = lambda event, **kw: trace.rows.append({'event': event, **kw})
        trace.digest = lambda value: value
        trace.rng = lambda: {'rng': 'unchanged'}
        return trace

    def context(self, real=True):
        context = NS(attn_metadata={'layer': NS(num_actual_tokens=1)} if real else {},
            batch_descriptor=NS(num_tokens=1, num_reqs=1, uniform=True),
            is_padding=None, cudagraph_runtime_mode='NONE')
        forward = ModuleType('vllm.forward_context')
        forward.get_forward_context = lambda: context
        forward.is_forward_context_available = lambda: True
        torch = ModuleType('torch')
        torch.is_tensor = lambda value: isinstance(value, FakeTensor)
        torch.cuda = NS(is_current_stream_capturing=lambda: False)
        torch.compiler = NS(is_compiling=lambda: False)
        sequence = ModuleType('vllm.sequence')
        sequence.IntermediateTensors = FakeIntermediateTensors
        return patch.dict(sys.modules, {'torch': torch, 'vllm.forward_context': forward,
                                       'vllm.sequence': sequence})

    def test_disabled_does_not_require_runtime_dependencies(self):
        with patch.dict(os.environ, {'VLLM_QSA_LAYER_TRACE': '0'}):
            self.assertIsNone(module.install(None, None, 'unused'))

    def test_guards_eager_no_async_and_single_rank(self):
        module.validate_config(config())
        for field, value in [('enforce_eager', False), ('async_scheduling', True),
                             ('async_scheduling', None), ('world_size', 2)]:
            candidate = config()
            obj = candidate.model_config if field == 'enforce_eager' else candidate.scheduler_config if field == 'async_scheduling' else candidate.parallel_config
            setattr(obj, field, value)
            with self.assertRaises(ValueError):
                module.validate_config(candidate)

    def test_hook_preserves_outputs_and_full_delayed_tuple(self):
        trace = self.trace()
        target = FakeModule()
        trace.attach(target, 'layer.0', 'decoder')
        trace.current = 1
        kwargs = {'hidden_states': 'hidden', 'prev_block_output': 'block', 'prev_injection': 'injection'}
        self.assertIsNone(target.before(target, (), kwargs))
        output = ('hidden-out', 'block-out', 'injection-out')
        self.assertIsNone(target.after(target, (), kwargs, output))
        self.assertEqual(trace.rows[0]['kwargs'], kwargs)
        self.assertEqual(trace.rows[1]['output'], output)

    def test_idle_hook_does_not_hash(self):
        trace = self.trace()
        target = FakeModule()
        trace.attach(target, 'layer.0', 'decoder')
        target.before(target, (), {'unexpected': object()})
        target.after(target, (), {}, object())
        self.assertFalse(trace.rows)

    def test_skip_dummy_forward_and_end(self):
        trace = self.trace()
        with self.context(False):
            trace.begin(None, None, None, None, None, None)
            trace.end('dummy')
        self.assertFalse(trace.rows)
        self.assertEqual(trace.sequence, 0)

    def test_model_logit_sequence_and_bound_marker(self):
        trace = self.trace()
        with self.context():
            for n in (1, 2):
                trace.begin([99], [7], [0, 1], None, None, None)
                trace.end('model-output')
                trace.logits('output', 'logits')
                self.assertEqual(trace.rows[-1]['forward_id'], n)
            trace.begin([99], [7], [0, 1], None, None, None)
            trace.end('untraced')
            trace.logits('output', 'untraced')
        self.assertEqual(trace.rows[-1]['event'], 'trace_exhausted')
        self.assertIsNone(trace.last_completed)

    def test_overlap_or_missing_end_fails_explicitly(self):
        trace = self.trace()
        with self.context():
            trace.begin([99], [7], None, None, None, None)
            with self.assertRaisesRegex(RuntimeError, 'overlap'):
                trace.begin([99], [7], None, None, None, None)

    def test_raw_ids_remain_required_with_or_without_embeddings(self):
        for embedding in (None, FakeTensor('embedded')):
            trace = self.trace()
            with self.context(), self.assertRaisesRegex(RuntimeError, 'raw token IDs'):
                trace.begin(None, [7], None, None, embedding, None)
            self.assertIsNone(trace.current)
            self.assertEqual(trace.sequence, 0)

    def test_mrv2_metadata_warmup_and_real_embedded_request_are_both_traced(self):
        trace = self.trace()
        # Warmup and text requests both have metadata, IDs and embedding tensors.
        # The helper must not guess which one is warmup from that representation.
        with self.context():
            for ids in ([0, 1], [99]):
                embedded = FakeTensor(('embedding', ids))
                deep = FakeTensor(('deepstack', ids))
                container = FakeIntermediateTensors({'deepstack_input_embeds_0': deep})
                trace.begin(ids, [7], None, None, embedded, container)
                event = trace.rows[-1]
                self.assertEqual(event['event'], 'begin')
                self.assertEqual(event['trace_schema_version'], 2)
                self.assertEqual(event['input_representation'], 'token_ids_with_embeddings')
                self.assertIs(event['inputs_embeds'], embedded)
                self.assertIs(event['deepstack_input_embeds']['deepstack_input_embeds_0'], deep)
                self.assertNotIn('unsupported_type', event['deepstack_input_embeds'])
                trace.end('out')
        self.assertEqual(trace.sequence, 2)

    def test_malformed_embedding_inputs_rejected_before_begin(self):
        for embedding, deep, expected in (
                (object(), None, 'inputs_embeds'),
                (None, object(), 'IntermediateTensors'),
                (None, FakeIntermediateTensors({'k': object()}), 'map names to tensors'),
                (None, FakeIntermediateTensors({1: FakeTensor('badkey')}), 'map names to tensors')):
            trace = self.trace()
            with self.context(), self.assertRaisesRegex(RuntimeError, expected):
                trace.begin([99], [7], None, None, embedding, deep)
            self.assertIsNone(trace.current)
            self.assertEqual(trace.sequence, 0)

    def test_embedding_payloads_are_fingerprinted_not_only_type_named(self):
        trace = self.trace()
        trace.digest = lambda value: value.value if isinstance(value, FakeTensor) else {
            key: tensor.value for key, tensor in value.items()} if isinstance(value, dict) else value
        with self.context():
            first = trace.embedding_fingerprints(FakeTensor('embed-a'),
                FakeIntermediateTensors({'deepstack_input_embeds_0': FakeTensor('deep-a')}))
            changed_embedding = trace.embedding_fingerprints(FakeTensor('embed-b'),
                FakeIntermediateTensors({'deepstack_input_embeds_0': FakeTensor('deep-a')}))
            changed_deep = trace.embedding_fingerprints(FakeTensor('embed-a'),
                FakeIntermediateTensors({'deepstack_input_embeds_0': FakeTensor('deep-b')}))
        self.assertNotEqual(first['inputs_embeds'], changed_embedding['inputs_embeds'])
        self.assertNotEqual(first['deepstack_input_embeds'], changed_deep['deepstack_input_embeds'])

    def test_no_metadata_profile_skips_even_supplied_dummy_embeddings(self):
        trace = self.trace()
        with self.context(False):
            trace.begin([99], [7], None, None, object(), None)
            trace.end('dummy')
        self.assertEqual(trace.rows, [])
        self.assertEqual(trace.sequence, 0)

    def test_tensor_limit_before_readback(self):
        trace = module.LayerTrace('model', 2, False)
        tensor = NS(numel=lambda: 256 * 1024**2 + 1, element_size=lambda: 1)
        fake_torch = ModuleType('torch')
        fake_torch.is_tensor = lambda value: value is tensor
        with patch.dict(sys.modules, {'torch': fake_torch}), self.assertRaisesRegex(RuntimeError, '256MiB'):
            trace.digest(tensor)

    def test_optional_submodules_installed(self):
        decoder = FakeModule()
        decoder.self_attn, decoder.mlp, decoder.ple = FakeModule(), FakeModule(), FakeModule()
        model = NS(start_layer=0, end_layer=1, layers=[decoder])
        with patch.dict(os.environ, {'VLLM_QSA_LAYER_TRACE': '1', 'VLLM_QSA_LAYER_TRACE_SUBMODULES': '1'}), patch.object(module.LayerTrace, 'emit'):
            trace = module.install(model, config(), 'model')
        self.assertEqual(len(trace.handles), 8)

    def test_indexer_pre_hook_omits_mutable_output_scratch(self):
        trace = self.trace()
        target = FakeModule()
        trace.attach(target, 'layer.3.self_attn.indexer', 'qsa_indexer')
        trace.current = 1
        target.before(target, ('hidden', 'positions', 'stale-indices'), {'out': 'stale-indices'})
        self.assertEqual(trace.rows[0]['args'], ('hidden', 'positions'))
        self.assertEqual(trace.rows[0]['kwargs'], {})

    def test_qsa_metadata_logical_and_physical_fields_are_separate(self):
        trace = self.trace()
        value = NS(token_to_req='requests', logical_positions='positions',
            k_work_metadata='compression-work', compress_ratio=4,
            slot_mapping='physical-slots', block_table='physical-table')
        result = trace.metadata(NS(attn_metadata={'raw': value, 'compressed': value}))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['logical']['k_work_metadata'], 'compression-work')
        self.assertEqual(result[0]['logical']['logical_positions'], 'positions')
        self.assertEqual(result[0]['physical']['slot_mapping'], 'physical-slots')
        self.assertNotIn('slot_mapping', result[0]['logical'])


if __name__ == '__main__':
    unittest.main()

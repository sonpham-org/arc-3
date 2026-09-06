"""Portable transfer/provenance state-machine tests; no Torch/GPU imports."""
from dataclasses import dataclass, field
import ast
import importlib.util
from pathlib import Path
import pickle
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest

META_NAME = 'vllm.v1.simple_kv_offload.metadata'
stub = ModuleType(META_NAME)


@dataclass
class BaseMetadata:
    load_event: int = -1
    load_gpu_blocks: list = field(default_factory=list)
    load_cpu_blocks: list = field(default_factory=list)
    load_event_to_reqs: dict = field(default_factory=dict)
    store_event: int = -1
    store_gpu_blocks: list = field(default_factory=list)
    store_cpu_blocks: list = field(default_factory=list)
    need_flush: bool = False


stub.SimpleCPUOffloadMetadata = BaseMetadata
sys.modules[META_NAME] = stub
spec = importlib.util.spec_from_file_location('audit_under_test',
    Path(__file__).with_name('qsa_resume_audit.py'))
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


class FakeParent:
    def build_connector_meta(self, output):
        return self.base


class Fake(audit.ResumeAuditMixin, FakeParent):
    def __init__(self):
        self._audit_init(NS(kv_cache_groups=[NS(layer_names=['layer.ple'],
            kv_cache_spec=NS(block_size=1600, prefix_cacheable=True))]))
        self._qsa_page_bytes = 8
        self.worker_handler = NS(_store_hwm=-1, _load_hwm=-1)
        self.raw = {'gpu': {3: {'storage': 'initial'}}, 'cpu': {5: {'storage': 'empty'}}}
        self.semantic = {3: {'ple': 'state-original'}}
        self.logs = []
        self.reads = 0

    def _audit_emit(self, event, **data):
        self.logs.append({'event': event, **data})

    def _audit_raw(self, side, block_id):
        self.reads += 1
        return dict(self.raw[side][block_id])

    def _audit_semantic(self, desc):
        self.reads += 1
        return dict(self.semantic[desc['gpu']])

    def bind(self, kind='store', event=0, desc=None, watches=None, step=1):
        desc = desc or {'cpu': 5, 'gpu': 3, 'key': 'a000000000', 'group': 0,
            'request_ids': ['producer'], 'boundaries': [['producer', 1600]]}
        fields = {kind + '_event': event, kind + '_cpu_blocks': [desc['cpu']],
                  kind + '_gpu_blocks': [desc['gpu']]}
        self.worker_handler._connector_metadata = audit.QSAResumeAuditMetadata(
            **fields, qsa_audit={'epoch': 0, 'step': step,
                'stores': [desc] if kind == 'store' else [],
                'loads': [desc] if kind == 'load' else [],
                'watches': watches or [], 'rebound_skipped': 0,
                'new_request_ids': [], 'finished_request_ids': []})
        return desc

    def complete_store(self):
        desc = self.bind()
        self._audit_before()
        self.raw['cpu'][5] = dict(self.raw['gpu'][3])
        self.worker_handler._store_hwm = 0
        self._audit_after()
        return desc


class Tests(unittest.TestCase):
    def test_metadata_serialization_preserves_explicit_payload(self):
        fake = Fake()
        fake.bind()
        meta = fake.worker_handler._connector_metadata
        copy = pickle.loads(pickle.dumps(meta))
        self.assertEqual(copy, meta)
        self.assertIsInstance(copy, BaseMetadata)

    def test_wait_for_completion_and_original_snapshot_not_alias(self):
        f = Fake()
        f.bind()
        f._audit_before()
        f._audit_after()
        self.assertFalse(f._audit_ledger)
        f.raw['cpu'][5] = dict(f.raw['gpu'][3])
        f.raw['gpu'][3]['storage'] = 'later-active-values'
        f.worker_handler._store_hwm = 0
        f._audit_after()
        self.assertEqual(f._audit_ledger[(5, 'a000000000')]['raw'], {'storage': 'initial'})

    def test_store_mismatch_fails_before_completion_return(self):
        f = Fake()
        f.bind()
        f._audit_before()
        f.worker_handler._store_hwm = 0
        with self.assertRaisesRegex(RuntimeError, 'store source/destination'):
            f._audit_after()

    def test_load_origin_is_original_producer(self):
        f = Fake()
        desc = f.complete_store()
        restore = {**desc, 'gpu': 7, 'request_ids': ['restore']}
        f.raw['gpu'][7] = dict(f.raw['cpu'][5])
        f.semantic[7] = dict(f.semantic[3])
        f.bind('load', desc=restore, step=2)
        f._audit_before()
        f.worker_handler._load_hwm = 0
        f._audit_after()
        report = [x for x in f.logs if x['event'] == 'load_origin'][0]
        self.assertTrue(report['cpu_unchanged_since_store'])
        self.assertTrue(report['semantic_exact'])
        self.assertEqual(report['origin_descriptor']['request_ids'], ['producer'])

    def test_equal_load_bytes_can_expose_different_semantic_origin(self):
        f = Fake()
        desc = f.complete_store()
        f.semantic[3]['ple'] = 'changed-recurrent-state'
        f.bind('load', desc=desc, step=2)
        f._audit_before()
        f.worker_handler._load_hwm = 0
        f._audit_after()
        self.assertFalse([x for x in f.logs if x['event'] == 'load_origin'][0]['semantic_exact'])

    def test_missing_origin_is_coverage_failure_not_exact(self):
        f = Fake()
        f.raw['gpu'][3] = dict(f.raw['cpu'][5])
        f.bind('load')
        f._audit_before()
        f.worker_handler._load_hwm = 0
        f._audit_after()
        report = [x for x in f.logs if x['event'] == 'load_origin'][0]
        self.assertIsNone(report['semantic_exact'])
        self.assertEqual(report['coverage'], 'missing_store_provenance')

    def test_watch_semantic_change_and_padding_separate(self):
        f = Fake()
        desc = f.complete_store()
        f.raw['gpu'][3]['storage'] = 'padding-only-change'
        f.bind(event=0, watches=[desc], step=2)
        f._audit_before()
        self.assertTrue([x for x in f.logs if x['event'] == 'resident_checkpoint_watch'][-1]['exact'])
        f.semantic[3]['ple'] = 'state-mutated'
        f.bind(event=0, watches=[desc], step=3)
        f._audit_before()
        self.assertFalse([x for x in f.logs if x['event'] == 'resident_checkpoint_watch'][-1]['exact'])

    def test_transfer_pair_mismatch_before_any_read(self):
        f = Fake()
        f.bind()
        f.worker_handler._connector_metadata.store_cpu_blocks = [6]
        with self.assertRaisesRegex(RuntimeError, 'mapping differs'):
            f._audit_before()
        self.assertEqual(f.reads, 0)

    def test_size_limit_before_any_read(self):
        f = Fake()
        f._qsa_page_bytes = 2 * 1024**3 + 1
        f.bind()
        with self.assertRaisesRegex(RuntimeError, '2GiB'):
            f._audit_before()
        self.assertEqual(f.reads, 0)

    def test_external_reset_refuses_pending_provenance(self):
        f = Fake()
        f.bind()
        f._audit_before()
        f.worker_handler._connector_metadata.qsa_audit['epoch'] = 1
        with self.assertRaisesRegex(RuntimeError, 'reset with pending'):
            f._audit_before()

    def test_idle_reset_clears_provenance(self):
        f = Fake()
        f.complete_store()
        f.bind(step=2)
        f.worker_handler._connector_metadata.qsa_audit['epoch'] = 1
        f._audit_before()
        self.assertFalse(f._audit_ledger)

    def test_scheduler_key_boundary_and_rebound_skip(self):
        f = Fake()
        key = b'prefix-hash' + (0).to_bytes(4, 'big')
        f.base = BaseMetadata(store_event=0, store_cpu_blocks=[5], store_gpu_blocks=[3])
        request = NS(block_hashes=[b'prefix-hash'])
        f.scheduler_manager = NS(_reqs_to_store={'producer': NS(request=request)},
            _reqs_to_load={}, hash_block_size=1600, _store_event_to_reqs={0: ['producer']},
            cpu_block_pool=NS(blocks={5: NS(block_hash=key)}),
            _gpu_block_pool=NS(blocks={3: NS(block_hash=key)}))
        out = NS(scheduled_new_reqs=[NS(req_id='producer')], finished_req_ids=set())
        result = f.build_connector_meta(out)
        self.assertEqual(result.qsa_audit['stores'][0]['boundaries'], [['producer', 1600]])
        self.assertEqual(result.qsa_audit['stores'][0]['families'], ['ple'])
        f.base = BaseMetadata()
        f.scheduler_manager._gpu_block_pool.blocks[3].block_hash = b'reused' + b'\0' * 4
        result = f.build_connector_meta(out)
        self.assertEqual(result.qsa_audit['rebound_skipped'], 1)
        self.assertFalse(result.qsa_audit['watches'])

    def test_composed_reset_false_then_true(self):
        source = Path(__file__).parent / 'candidate/vllm/distributed/kv_transfer/kv_connector/v1/qsa_cpu_offload_connector.py'
        tree = ast.parse(source.read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                   and n.name == 'QSAAlignedCPUOffloadConnector')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == 'reset_cache')
        # Compile the actual generated method to retain its __class__/super cell.
        wrapper = ast.ClassDef(name='Composed', bases=[ast.Name(id='Parent', ctx=ast.Load())],
            keywords=[], body=[method], decorator_list=[])
        module = ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[]))
        class Parent:
            result = False
            def reset_cache(self):
                return self.result
        ns = {'Parent': Parent}
        exec(compile(module, '<actual-composed-reset>', 'exec'), ns)
        instance = ns['Composed']()
        instance._qsa_pending_hits = {'pending': True}
        calls = []
        instance._audit_reset = lambda: calls.append('committed')
        self.assertFalse(instance.reset_cache())
        self.assertFalse(calls)
        instance.result = True
        self.assertTrue(instance.reset_cache())
        self.assertEqual(calls, ['committed'])

    def test_watch_prefers_token_boundary_over_slot_insertion_order(self):
        f = Fake()
        f.base = BaseMetadata()
        keys = {5: b'higher' + b'\0' * 4, 6: b'lower' + b'\0' * 4}
        f._audit_known = {
            5: {'cpu': 5, 'gpu': 3, 'key': keys[5].hex(), 'group': 0,
                'boundaries': [['producer', 3200]]},
            6: {'cpu': 6, 'gpu': 4, 'key': keys[6].hex(), 'group': 0,
                'boundaries': [['producer', 1600]]},
        }
        f.scheduler_manager = NS(_reqs_to_store={}, _reqs_to_load={},
            cpu_block_pool=NS(blocks={c: NS(block_hash=k) for c, k in keys.items()}),
            _gpu_block_pool=NS(blocks={3: NS(block_hash=keys[5]), 4: NS(block_hash=keys[6])}))
        result = f.build_connector_meta(NS(scheduled_new_reqs=[NS(req_id='resident')],
                                          finished_req_ids=set()))
        self.assertEqual([d['cpu'] for d in result.qsa_audit['watches']], [5])


if __name__ == '__main__':
    unittest.main()

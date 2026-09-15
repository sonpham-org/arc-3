"""Portable positive and incomplete-evidence tests; no Torch, GPU, or cloud."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import compare_trace as c


def tensor(values, shape=None, dtype='torch.int64'):
    return {'shape': shape or [len(values)], 'stride': [1], 'dtype': dtype,
            'bytes': len(values) * (8 if dtype == 'torch.int64' else 4),
            'sha256': c.int_hash(values, dtype)}


def fixture(root, mutation=None):
    root = Path(root)
    frozen = list(range(17))
    data = bytearray()
    identity = {'pid': 7, 'model_prefix': 'language_model.model'}

    def emit(event, **values):
        data.extend(b'(Worker pid=7) INFO 09-06 17:00:00 [qsa_layer_trace.py:1] QSA_LAYER_TRACE ')
        data.extend(json.dumps({**identity, 'event': event, **values}).encode() + b'\n')

    emit('installed', hooks=2, submodules=False, max_forwards=128)

    def forward(number, count=1, change=False):
        begin = {'input_ids': tensor(frozen[-count:]),
                 'positions': tensor(list(range(len(frozen) - count, len(frozen))) * 3, [3, count]),
                 'inputs_embeds': tensor([0] * count), 'deepstack_input_embeds': {},
                 'input_representation': 'token_ids_with_embeddings',
                 'query_start_loc': tensor([0, count]), 'ngram_context': None,
                 'is_padding': None, 'batch': {'num_tokens': count, 'num_reqs': 1},
                 'rng': {'cpu': 'same', 'cuda': 'same'}, 'attention': [],
                 'trace_schema_version': 2}
        if mutation == 'wrong_input' and number == 3:
            begin['input_ids'] = tensor([99])
        if mutation == 'wrong_position' and number == 3:
            begin['positions'] = tensor([12] * 3, [3, 1])
        if mutation == 'embedding_changed' and number == 3:
            begin['inputs_embeds'] = tensor([123])
        if mutation == 'missing_embeddings':
            del begin['inputs_embeds']
            del begin['deepstack_input_embeds']
        emit('begin', forward_id=number, **begin)
        emit('module_input', forward_id=number, module='layer.0', kind='decoder',
             args=[], kwargs={'hidden_states': tensor([8] * count)})
        if mutation != 'missing_module_output' or number != 3:
            emit('module_output', forward_id=number, module='layer.0', kind='decoder',
                 output=[tensor([9 if not change else 10] * count), None, None])
        emit('end', forward_id=number, output=tensor([9] * count), rng=begin['rng'])
        emit('logits_input', forward_id=number, tensor=tensor([4]))
        if mutation != 'missing_logits' or number != 3:
            emit('logits_output', forward_id=number, tensor=tensor([5 if not change else 6], [1, 1]))

    rows = []
    producer = {'request_id': 'producer', 'token_ids': frozen[-9:] + [99] * 23,
                'prompt_tokens': len(frozen) - 9,
                'prompt_sha256': hashlib.sha256(json.dumps(frozen[:-9], sort_keys=True).encode()).hexdigest()}
    # Unmatched warmup/producer early steps must not acquire a request binding.
    forward(1)
    categories = ['producer', 'resident', 'resident']
    if mutation == 'complete_cpu':
        categories += ['cpu-restored', 'cpu-restored']
    categories += ['cold', 'cold']
    counters = {}
    for index, category in enumerate(categories):
        category_index = counters.get(category, 0)
        counters[category] = category_index + 1
        start = len(data)
        count = len(frozen) if category == 'cold' else 1
        forward(index + 2, count, change=mutation == 'drift' and index == 1)
        if mutation == 'ambiguous' and index == 1:
            forward(99, count)
        end = len(data)
        row = producer if category == 'producer' else {
            'category': category, 'index': category_index,
            'request_id': 'req-' + str(index), 'prompt_tokens': len(frozen),
            'prompt_sha256': hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest(),
            'token_ids': [17]}
        row.update(trace_log={'start_offset': start, 'end_offset': end},
                   server_log_same_file_and_nonshrinking=True,
                   request_started_utc='2026-09-06T17:00:00+00:00',
                   request_finished_utc='2026-09-06T17:00:01+00:00')
        if category != 'producer':
            rows.append(row)
    if mutation == 'buffered_end':
        rows[0]['trace_log']['end_offset'] -= 100
    if mutation == 'log_rotated':
        rows[0]['server_log_same_file_and_nonshrinking'] = False
    if mutation == 'duplicated_binding':
        rows[1]['trace_log'] = dict(rows[0]['trace_log'])
    report = {'mode': 'cpu' if mutation == 'complete_cpu' else 'gpu', 'status': 'completed',
              'identity': {'runtime_attestation': {'server_arguments_match': True}},
              'cases': [{'target': 32, 'status': 'completed', 'boundary': len(frozen) - 1, 'producer': producer,
                         'frozen_input_ids': frozen, 'frozen_input_sha256':
                         hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest(), 'rows': rows}]}
    log = root / 'vllm.log'
    path = root / 'report.json'
    log.write_bytes(data)
    path.write_text(json.dumps(report))
    return log, path


class Tests(unittest.TestCase):
    def run_case(self, mutation=None):
        with tempfile.TemporaryDirectory() as directory:
            log, report = fixture(directory, mutation)
            return c.analyze(log, report)

    def test_complete_same_input_repeats_bind_and_compare(self):
        result = self.run_case()
        self.assertTrue(result['analysis_complete'], result)
        self.assertEqual(len(result['cases'][0]['bindings']), 5)
        first = result['cases'][0]['comparisons'][0]
        self.assertTrue(first['full_layer_comparison_eligible'])
        self.assertIsNone(first['first_observed_difference'])

    def test_first_observed_module_drift_reported_not_passed_as_equal(self):
        result = self.run_case('drift')
        self.assertTrue(result['analysis_complete'])
        first = result['cases'][0]['comparisons'][0]
        self.assertEqual(first['first_observed_difference']['module'], 'layer.0')
        self.assertEqual(first['first_observed_difference']['event'], 'module_output')
        self.assertFalse(first['logits_output_equal'])

    def test_complete_cpu_probe_requires_and_compares_restore_repeats(self):
        result = self.run_case('complete_cpu')
        self.assertTrue(result['analysis_complete'], result)
        case = result['cases'][0]
        self.assertEqual(len(case['bindings']), 7)
        names = {pair['comparison'] for pair in case['comparisons']}
        self.assertIn('resident:0 -> cpu-restored:0', names)
        self.assertIn('cpu-restored:0 -> cpu-restored:1', names)

    def test_cold_vs_resident_layers_are_not_directly_comparable(self):
        result = self.run_case()
        pair = next(p for p in result['cases'][0]['comparisons'] if 'resident:0 -> cold:0' == p['comparison'])
        self.assertFalse(pair['full_layer_comparison_eligible'])
        self.assertTrue(pair['logits_input_equal'])

    def test_embedding_difference_disables_layer_causal_claim(self):
        result = self.run_case('embedding_changed')
        pair = result['cases'][0]['comparisons'][0]
        self.assertFalse(pair['selected_logical_inputs_equal'])
        self.assertFalse(pair['full_layer_comparison_eligible'])
        self.assertIn('inputs_embeds', pair['different_input_fields'])

    def test_missing_or_wrong_evidence_never_complete(self):
        for mode in ('wrong_input', 'wrong_position', 'missing_module_output',
                     'missing_logits', 'ambiguous', 'buffered_end', 'log_rotated', 'duplicated_binding'):
            with self.subTest(mode=mode):
                result = self.run_case(mode)
                self.assertFalse(result['analysis_complete'])
                self.assertTrue(result['errors'] or any(b['errors'] for b in result['cases'][0]['bindings']))

    def test_mrope_and_int32_fingerprint(self):
        frozen = [1, 2, 3]
        begin = {'input_ids': tensor([3], dtype='torch.int32'),
                 'positions': tensor([2, 2, 2], [3, 1], 'torch.int32')}
        self.assertTrue(c.terminal_input(begin, frozen, 'resident'))
        self.assertFalse(c.terminal_input(begin, [1, 2, 4], 'resident'))

    def test_trace_startup_failure_has_no_false_forward_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            log, report = fixture(directory)
            first = log.read_bytes().splitlines(keepends=True)[0]
            log.write_bytes(first + b'RuntimeError: trace embedding guard\n')
            result = c.analyze(log, report)
        self.assertFalse(result['analysis_complete'])
        self.assertIn('no_traced_forward_records', result['errors'])

    def test_duplicate_json_key_is_rejected(self):
        with self.assertRaises(c.EvidenceError):
            c.decode('{"a":1,"a":2}')

    def test_nonfinite_json_is_rejected(self):
        with self.assertRaises(c.EvidenceError):
            c.decode('{"a":NaN}')

    def test_invalid_report_type_is_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            log, report = fixture(directory)
            report.write_text('[]')
            result = c.analyze(log, report)
        self.assertFalse(result['analysis_complete'])
        self.assertIn('probe_report_must_be_an_object', result['errors'])

    def test_missing_final_fingerprint_is_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            log, report = fixture(directory)
            lines = log.read_bytes().splitlines(keepends=True)
            values = []
            for line in lines:
                prefix, raw = line.split(c.MARKER, 1)
                event = json.loads(raw)
                if event['event'] == 'logits_output':
                    event['tensor'] = None
                values.append(prefix + c.MARKER + json.dumps(event).encode() + b'\n')
            log.write_bytes(b''.join(values))
            forwards, _, _ = c.parse_trace(log)
        self.assertTrue(all('missing_or_malformed_final_tensor_fingerprint' in f['errors'] for f in forwards))

    def test_missing_embedding_fields_cannot_compare_as_equal(self):
        result = self.run_case('missing_embeddings')
        self.assertFalse(result['analysis_complete'])
        self.assertEqual(result['cases'][0]['comparisons'], [])
        self.assertTrue(all('missing_embedding_input_coverage' in b['errors'][0]
                            for b in result['cases'][0]['bindings']))

    def test_malformed_embedding_schema_is_incomplete(self):
        valid = {'trace_schema_version': 2, 'inputs_embeds': tensor([1]),
                 'deepstack_input_embeds': {}, 'input_representation': 'token_ids_with_embeddings'}
        mutations = (
            {'trace_schema_version': 1},
            {'inputs_embeds': {'unsupported_type': 'TensorLike'}},
            {'deepstack_input_embeds': {'unsupported_type': 'IntermediateTensors'}},
            {'deepstack_input_embeds': {'0': None}},
            {'deepstack_input_embeds': []},
            {'input_representation': 'token_ids'},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertTrue(c.embedding_input_errors({**valid, **mutation}))
        self.assertEqual(c.embedding_input_errors(valid), [])
        self.assertEqual(c.embedding_input_errors({**valid, 'inputs_embeds': None,
            'deepstack_input_embeds': None, 'input_representation': 'token_ids'}), [])

    def test_incomplete_probe_families_status_or_repeats_rejected(self):
        for mutation in ('report_status', 'case_status', 'cpu_without_restores', 'missing_cold_repeat', 'duplicate_index'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                log, report_path = fixture(directory)
                report = json.loads(report_path.read_text())
                case = report['cases'][0]
                if mutation == 'report_status':
                    report['status'] = 'stopped-after-error'
                elif mutation == 'case_status':
                    case['status'] = 'running'
                elif mutation == 'cpu_without_restores':
                    report['mode'] = 'cpu'
                elif mutation == 'missing_cold_repeat':
                    case['rows'].pop()
                elif mutation == 'duplicate_index':
                    case['rows'][-1]['index'] = 0
                report_path.write_text(json.dumps(report))
                result = c.analyze(log, report_path)
                self.assertFalse(result['analysis_complete'])
                self.assertTrue(result['errors'])

    def test_selection_order_and_membership_are_reported_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            log, _ = fixture(directory)
            forwards, _, _ = c.parse_trace(log)
        left, right = copy.deepcopy(forwards[1]), copy.deepcopy(forwards[2])
        base = {'event': 'qsa_selection', 'module': 'layer.3.self_attn.indexer',
                'ordered': tensor([2, 1, -1], [1, 3]),
                'sorted_per_row': tensor([-1, 1, 2], [1, 3]), '_line': 999}
        other = copy.deepcopy(base)
        other['ordered'] = tensor([1, 2, -1], [1, 3])
        left['events'].insert(-3, base)
        right['events'].insert(-3, other)
        pair = c.compare(left, right, 'selection-order')
        self.assertEqual(pair['selection_differences'][0], {
            'module': 'layer.3.self_attn.indexer', 'ordered_equal': False,
            'sorted_multiset_equal': True})
        other['sorted_per_row'] = tensor([-1, 1, 3], [1, 3])
        pair = c.compare(left, right, 'selection-membership')
        self.assertFalse(pair['selection_differences'][0]['sorted_multiset_equal'])

    def test_indexer_without_selection_has_incomplete_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            log, _ = fixture(directory)
            data = log.read_bytes().replace(b'"kind": "decoder"', b'"kind": "qsa_indexer"')
            log.write_bytes(data)
            forwards, _, _ = c.parse_trace(log)
        self.assertTrue(all('missing_or_duplicate_indexer_selection:layer.0' in f['errors'] for f in forwards))

    def test_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            log, report = fixture(directory)
            output = Path(directory) / 'existing.json'
            output.write_text('preserve')
            process = subprocess.run([sys.executable, '-B', str(Path(c.__file__)),
                '--logfile', str(log), '--probe-report', str(report), '--output', str(output)],
                capture_output=True)
            self.assertNotEqual(process.returncode, 0)
            self.assertEqual(output.read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main()

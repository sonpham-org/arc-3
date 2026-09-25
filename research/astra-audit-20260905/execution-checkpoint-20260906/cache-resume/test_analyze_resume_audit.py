"""Portable synthetic log tests; no cloud, model, or runtime imports."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import analyze_resume_audit as analyzer

PRODUCER = '1' * 32
RESTORE = '2' * 32
P = 'cmpl-' + PRODUCER + '-0'
R = 'cmpl-' + RESTORE + '-0'
OWNERS = ['layer.self_attn.attn', 'layer.indexer.compressed_key_cache',
          'layer.linear_attn', 'layer.ple', 'layer.indexer.raw_key_cache']


def digest(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def event(name, **data):
    return {'event': name, 'epoch': 1, **data}


def fixture():
    groups = {str(i): {'owners': [owner], 'block_size': 1600 if i < 4 else 4,
                       'cacheable': i < 4} for i, owner in enumerate(OWNERS)}
    sources, loads = [], []
    for group in range(4):
        for boundary in ([1600, 3200] if group < 2 else [3200]):
            slot = len(sources)
            key = digest(boundary) + group.to_bytes(4, 'big').hex()
            source = {'cpu': slot, 'gpu': slot + 100, 'group': group,
                'key': key, 'families': [analyzer.family(OWNERS[group])],
                'group_block_size': 1600, 'request_ids': [P], 'boundaries': [[P, boundary]]}
            sources.append(source)
            loads.append({**source, 'gpu': slot + 200, 'request_ids': [R], 'boundaries': [[R, boundary]]})
    def semantic(desc):
        owner = OWNERS[desc['group']]
        return {owner + ':0': {'family': analyzer.family(owner), 'shape': [3, 4],
                               'dtype': 'torch.bfloat16', 'sha256': digest(('semantic', desc['key']))}}
    def raw(desc):
        return {'storage-a': digest(('raw-a', desc['key'])), 'storage-b': digest(('raw-b', desc['key']))}
    rows = [event('registered', epoch=0, groups=groups, raw_storages=2, timing_valid=False),
            event('external_reset'), event('store_captured', transfer_event=0, descriptors=sources,
                phase='after_forward_before_submit')]
    rows += [event('store_raw_copy', transfer_event=0, descriptor=desc, exact=True,
                scope=analyzer.RAW_SCOPE, source_raw_sha256=raw(desc),
                destination_raw_sha256=raw(desc), source_semantic=semantic(desc)) for desc in sources]
    rows += ['QSA_CPU_OFFLOAD restore_scheduled request_id=' + R +
             " local_tokens=0 external_tokens=3200 end_tokens=3200 families={'main':1}"]
    rows.append(event('load_captured', transfer_event=0, descriptors=loads,
                      phase='after_forward_before_submit'))
    for source, load in zip(sources, loads):
        rows.append(event('load_raw_copy', transfer_event=0, descriptor=load, exact=True,
            scope=analyzer.RAW_SCOPE, source_raw_sha256=raw(load),
            destination_raw_sha256=raw(load), source_semantic=None))
        rows.append(event('load_origin', transfer_event=0, descriptor=load, origin_store_event=0,
            origin_descriptor=source, cpu_unchanged_since_store=True,
            semantic_exact=True, semantic=semantic(load), coverage='semantic_owners'))
    rows += ["QSA_CPU_OFFLOAD restore_submitted event_id=0 loaded_blocks=6 loaded_bytes=48 request_ids=['" + R + "']",
             'QSA_CPU_OFFLOAD restore_completed request_id=' + R]
    return rows


def run(rows, targets=None):
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'vllm.log'
        path.write_text('\n'.join(('(Worker_TP0 pid=42) INFO QSA_RESUME_AUDIT ' + json.dumps(row))
                                   if isinstance(row, dict) else row for row in rows) + '\n')
        return analyzer.analyze_resume_audit(path, targets if targets is not None else
            [{'request_id': RESTORE, 'producer_request_id': PRODUCER, 'boundary': 3200}])


class AnalyzerTests(unittest.TestCase):
    def assertFailed(self, rows, reason=None, targets=None):
        result = run(rows, targets)
        self.assertFalse(result['pass'])
        self.assertFalse(any(r['pass'] for r in result['results']))
        if reason:
            self.assertIn(reason, json.dumps(result))
        return result

    def test_complete_chain_covers_prior_attention_pages_and_terminal_recurrent_states(self):
        result = run(fixture())
        self.assertTrue(result['pass'], result)
        row = result['results'][0]
        self.assertEqual(row['verified_pair_count'], 6)
        self.assertEqual(row['registered_cacheable_groups'], [0, 1, 2, 3])
        self.assertEqual({c['boundary'] for c in row['chains']}, {1600, 3200})
        self.assertTrue(all(c['source_gpu'] != c['restored_gpu'] for c in row['chains']))

    def test_empty_or_missing_or_non_audit_log_never_passes(self):
        self.assertFailed([], 'missing_audit_events')
        self.assertFailed(['ordinary server output'], 'missing_audit_events')
        self.assertFalse(analyzer.analyze_resume_audit('missing-never-created-log',
            [{'request_id': RESTORE, 'producer_request_id': PRODUCER, 'boundary': 3200}])['pass'])

    def test_empty_duplicate_or_bare_targets_never_pass(self):
        self.assertFailed(fixture(), 'expected_nonempty', targets=[])
        self.assertFailed(fixture(), 'duplicate_target', targets=[RESTORE, RESTORE])
        self.assertFailed(fixture(), 'expected_producer_identity', targets=[RESTORE])

    def test_aggregate_requires_every_requested_target(self):
        result = run(fixture(), [{'request_id': RESTORE, 'producer_request_id': PRODUCER, 'boundary': 3200},
            {'request_id': '3' * 32, 'producer_request_id': PRODUCER, 'boundary': 3200}])
        self.assertFalse(result['pass'])
        self.assertTrue(result['results'][0]['pass'])
        self.assertFalse(result['results'][1]['pass'])

    def test_bounded_log_read_fails_closed(self):
        with patch.object(analyzer, 'MAX_LOG_BYTES', 10):
            self.assertFailed(fixture(), 'log_size_limit')

    def test_unrelated_request_cannot_establish_target_provenance(self):
        self.assertFailed(fixture(), 'missing_or_ambiguous_restore_schedule', targets=[
            {'request_id': '3' * 32, 'producer_request_id': PRODUCER, 'boundary': 3200}])
        self.assertFalse(analyzer.request_matches('cmpl-x' + RESTORE + '-0', RESTORE))

    def test_scheduler_log_stream_may_arrive_after_worker_records(self):
        rows = fixture()
        scheduled = rows.pop(next(i for i, r in enumerate(rows)
                                  if isinstance(r, str) and 'restore_scheduled' in r))
        result = run([*rows, scheduled])
        self.assertTrue(result['pass'], result)

    def test_registration_missing_or_duplicate_rejected(self):
        rows = fixture()
        self.assertFailed(rows[1:], 'registration_missing')
        self.assertFailed([rows[0], *rows], 'registration_missing')

    def test_truncated_and_duplicate_key_json_rejected(self):
        self.assertFailed([*fixture(), 'INFO QSA_RESUME_AUDIT {"event":'])
        self.assertFailed([*fixture(), 'QSA_RESUME_AUDIT {"event":"external_reset","epoch":2,"epoch":3}'], 'duplicate_json_key')

    def test_missing_capture_submission_completion_or_origin_rejected(self):
        for category in ('store_captured', 'store_raw_copy', 'load_captured', 'load_raw_copy', 'load_origin'):
            rows = fixture()
            index = next(i for i, r in enumerate(rows) if isinstance(r, dict) and r['event'] == category)
            rows.pop(index)
            self.assertFailed(rows)
        for marker in ('restore_submitted', 'restore_completed', 'restore_scheduled'):
            self.assertFailed([r for r in fixture() if not isinstance(r, str) or marker not in r])

    def test_omitted_entire_page_detected_by_submission_count(self):
        rows = fixture()
        for row in rows:
            if isinstance(row, dict) and row['event'] == 'load_captured':
                row['descriptors'] = [d for d in row['descriptors'] if d['cpu'] != 0]
        rows = [r for r in rows if not isinstance(r, dict) or r.get('event') not in ('load_raw_copy', 'load_origin') or r['descriptor']['cpu'] != 0]
        self.assertFailed(rows, 'submitted_pair_count')

    def test_missing_group_and_missing_terminal_boundary_rejected(self):
        rows = fixture()
        for r in rows:
            if isinstance(r, dict) and r['event'] == 'load_captured':
                r['descriptors'] = [d for d in r['descriptors'] if d['group'] != 3]
        rows = [r for r in rows if not isinstance(r, dict) or r['event'] not in ('load_raw_copy', 'load_origin') or r['descriptor']['group'] != 3]
        rows = [r.replace('loaded_blocks=6 loaded_bytes=48', 'loaded_blocks=5 loaded_bytes=40') if isinstance(r, str) else r for r in rows]
        self.assertFailed(rows, 'missing_registered_cacheable_load_groups')
        self.assertFailed(fixture(), 'restore_did_not_load_exact', targets=[
            {'request_id': RESTORE, 'producer_request_id': PRODUCER, 'boundary': 4800}])

    def test_raw_truth_flag_does_not_override_disagreeing_digests(self):
        for kind in ('store_raw_copy', 'load_raw_copy'):
            rows = fixture()
            row = next(r for r in rows if isinstance(r, dict) and r['event'] == kind)
            row['destination_raw_sha256']['storage-a'] = digest('bad')
            self.assertFailed(rows, 'raw_')

    def test_cpu_contents_can_not_change_between_valid_store_and_load(self):
        rows = fixture()
        row = next(r for r in rows if isinstance(r, dict) and r['event'] == 'load_raw_copy')
        row['source_raw_sha256']['storage-a'] = row['destination_raw_sha256']['storage-a'] = digest('changed-cpu')
        self.assertFailed(rows, 'store_to_cpu_to_load_raw_chain_differs')

    def test_missing_false_or_null_origin_flags_fail(self):
        for field in ('cpu_unchanged_since_store', 'semantic_exact', 'origin_store_event'):
            for value in (None, False):
                rows = fixture()
                row = next(r for r in rows if isinstance(r, dict) and r['event'] == 'load_origin')
                row[field] = value
                self.assertFailed(rows)

    def test_semantic_true_flag_cannot_override_changed_or_missing_owners(self):
        for mode in ('changed', 'empty', 'part'):
            rows = fixture()
            row = next(r for r in rows if isinstance(r, dict) and r['event'] == 'load_origin')
            if mode == 'changed': next(iter(row['semantic'].values()))['sha256'] = digest('wrong')
            elif mode == 'empty': row['semantic'] = {}
            else:
                key = next(iter(row['semantic']))
                row['semantic'][key[:-1] + '1'] = row['semantic'].pop(key)
            self.assertFailed(rows)

    def test_wrong_intended_producer_and_multi_request_origin_fail(self):
        self.assertFailed(fixture(), 'wrong_request_binding', targets=[
            {'request_id': RESTORE, 'producer_request_id': '4' * 32, 'boundary': 3200}])
        rows = fixture()
        row = next(r for r in rows if isinstance(r, dict) and r['event'] == 'load_origin')
        row['origin_descriptor']['request_ids'].append('another-producer')
        self.assertFailed(rows, 'wrong_request_binding')

    def test_group_key_and_cpu_origin_mismatch_rejected(self):
        for field, value in (('cpu', 99), ('key', digest('different') + '00000000'), ('group', 4)):
            rows = fixture()
            row = next(r for r in rows if isinstance(r, dict) and r['event'] == 'load_origin')
            row['origin_descriptor'] = {**row['origin_descriptor'], field: value}
            self.assertFailed(rows)

    def test_cross_epoch_origin_is_rejected(self):
        rows = fixture()
        index = next(i for i, r in enumerate(rows) if isinstance(r, dict) and r['event'] == 'load_captured')
        rows.insert(index, event('external_reset', epoch=2))
        for r in rows[index + 1:]:
            if isinstance(r, dict): r['epoch'] = 2
        self.assertFailed(rows, 'origin_store_capture_missing')

    def test_origin_store_must_finish_before_load_capture(self):
        rows = fixture()
        row = rows.pop(next(i for i, r in enumerate(rows) if isinstance(r, dict) and r['event'] == 'store_raw_copy'))
        at = next(i for i, r in enumerate(rows) if isinstance(r, dict) and r['event'] == 'load_captured')
        rows.insert(at + 1, row)
        self.assertFailed(rows, 'not_completed_before_load')

    def test_duplicate_pair_and_duplicate_completion_rejected(self):
        rows = fixture()
        row = next(r for r in rows if isinstance(r, dict) and r['event'] == 'load_origin')
        rows.insert(-2, copy.deepcopy(row))
        self.assertFailed(rows, 'incomplete_or_extra_load_origin_pairs')
        self.assertFailed([*fixture(), fixture()[-1]], 'ambiguous_restore_completion')

    def test_raw_storage_count_and_family_coverage_rejected(self):
        rows = fixture(); rows[0]['raw_storages'] = 3
        self.assertFailed(rows, 'missing_raw_storage_coverage')
        rows = fixture(); rows[0]['groups'].pop('3')
        self.assertFailed(rows, 'missing_expected_qsa_families')

    def test_cpu_slot_reuse_invalidates_old_origin_even_when_bytes_match(self):
        rows = fixture()
        old = next(r for r in rows if isinstance(r, dict) and r['event'] == 'store_raw_copy')
        reused = copy.deepcopy(old); reused['transfer_event'] = 9
        reused['descriptor']['key'] = digest('rebound') + '00000000'
        at = next(i for i, r in enumerate(rows) if isinstance(r, dict) and r['event'] == 'load_captured')
        rows.insert(at, reused)
        self.assertFailed(rows, 'cpu_slot_rebound')

    def test_sampled_mutation_is_separate_from_exact_restoration(self):
        rows = fixture()
        source = copy.deepcopy(next(r for r in rows if isinstance(r, dict) and r['event'] == 'store_raw_copy')['descriptor'])
        rows.insert(-1, event('resident_checkpoint_watch', descriptor=source, origin_store_event=0,
            exact=False, coverage='semantic_owners', new_request_ids=['resident'], finished_request_ids=[]))
        result = run(rows)
        self.assertTrue(result['pass'])
        self.assertTrue(result['results'][0]['sampled_resident_mutation_observed'])

    def test_probe_target_extraction_checks_conditioning_and_transfer_proof(self):
        ids = [1] * 3201
        sha = hashlib.sha256(json.dumps(ids, sort_keys=True).encode()).hexdigest()
        report = {'mode': 'cpu', 'cases': [{'boundary': 3200, 'frozen_input_ids': ids,
            'frozen_input_sha256': sha, 'producer': {'request_id': PRODUCER,
                'token_ids': [1] * 32, 'prompt_tokens': 3192,
                'prompt_sha256': hashlib.sha256(json.dumps(ids[:-9], sort_keys=True).encode()).hexdigest()}, 'rows': [
                {'category': 'cpu-restored', 'request_id': RESTORE, 'prompt_sha256': sha,
                 'prompt_tokens': len(ids), 'restore_proof': {'confirmed': True}}]}]}
        targets = analyzer.targets_from_probe(report)
        self.assertTrue(run(fixture(), targets)['pass'])
        report['cases'][0]['rows'][0]['restore_proof']['confirmed'] = False
        self.assertFailed(fixture(), 'probe_restore_proof_failed', targets=analyzer.targets_from_probe(report))
        report['cases'][0]['frozen_input_sha256'] = 'wrong'
        with self.assertRaises(analyzer.EvidenceError): analyzer.targets_from_probe(report)

    def test_cli_preserves_existing_output_and_failure_exit(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            logfile = directory / 'vllm.log'
            logfile.write_text('unrelated server output\n')
            ids = [1] * 3201
            sha = hashlib.sha256(json.dumps(ids, sort_keys=True).encode()).hexdigest()
            report = {'mode': 'cpu', 'cases': [{'boundary': 3200, 'frozen_input_ids': ids,
                'frozen_input_sha256': sha, 'producer': {'request_id': PRODUCER,
                    'token_ids': [1] * 32, 'prompt_tokens': 3192,
                    'prompt_sha256': hashlib.sha256(json.dumps(ids[:-9], sort_keys=True).encode()).hexdigest()},
                'rows': [{'category': 'cpu-restored', 'request_id': RESTORE, 'prompt_sha256': sha,
                          'prompt_tokens': len(ids), 'restore_proof': {'confirmed': True}}]}]}
            probe = directory / 'probe.json'; probe.write_text(json.dumps(report))
            output = directory / 'result.json'
            command = [sys.executable, '-B', str(Path(analyzer.__file__)), '--logfile', str(logfile),
                       '--probe-report', str(probe), '--output', str(output)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            saved = output.read_bytes()
            self.assertFalse(json.loads(saved)['pass'])
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), saved)


if __name__ == '__main__':
    unittest.main()

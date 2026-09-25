"""Read-only, fail-closed analysis of the isolated QSA restoration diagnostic.

``analyze_resume_audit(logfile, targets)`` returns a result per restore request.
Targets are dictionaries with request_id, producer_request_id, and boundary.
``targets_from_probe(report)`` extracts them from probe_first_token.py output.
Bare request IDs are accepted for diagnosis but cannot establish producer origin.
No vLLM, Torch, credentials, or cloud access is required.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re

MAX_LOG_BYTES = 128 * 1024**2
MAX_PROBE_BYTES = 16 * 1024**2
MAX_LINE_BYTES = 8 * 1024**2
MAX_EVENTS = 50000
MAX_TARGETS = 32
MARKER = 'QSA_RESUME_AUDIT '
RAW_SCOPE = 'deduplicated_full_storage_including_padding_and_aliases'
EVENTS = {'registered', 'external_reset', 'store_captured', 'load_captured',
          'store_raw_copy', 'load_raw_copy', 'load_origin',
          'resident_checkpoint_watch', 'watch_binding_reused'}
SHA = re.compile(r'[0-9a-f]{64}')
REQUEST = re.compile(r'[A-Za-z0-9_-]{1,256}')


class EvidenceError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise EvidenceError(reason)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate_json_key:' + key)
        result[key] = value
    return result


def decode_json(raw):
    def reject(value):
        raise EvidenceError('nonfinite_json:' + value)
    return json.loads(raw, object_pairs_hook=unique_json, parse_constant=reject)


def request_matches(actual, wanted):
    return (isinstance(actual, str) and isinstance(wanted, str)
            and bool(REQUEST.fullmatch(actual)) and bool(REQUEST.fullmatch(wanted))
            and re.search(r'(?:^|[-_])' + re.escape(wanted) + r'(?:$|[-_])', actual) is not None)


def family(owner):
    for suffix, name in (('.indexer.compressed_key_cache', 'compressed'),
                         ('.indexer.raw_key_cache', 'raw'), ('.linear_attn', 'gdn'),
                         ('.ple', 'ple'), ('.self_attn.attn', 'main')):
        if owner.endswith(suffix):
            return name
    raise EvidenceError('unknown_semantic_owner:' + str(owner))


def parse_log(logfile):
    path = Path(logfile)
    require(path.is_file(), 'missing_log')
    require(path.stat().st_size <= MAX_LOG_BYTES, 'log_size_limit')
    with path.open('rb') as handle:
        raw = handle.read(MAX_LOG_BYTES + 1)
    require(len(raw) <= MAX_LOG_BYTES, 'log_size_limit')
    require(bool(raw), 'empty_log')
    # Decode strictly: a torn or corrupted audit record must not disappear.
    text = raw.decode('utf-8')
    audit, connector = [], []
    for number, line in enumerate(text.splitlines(), 1):
        if MARKER not in line and 'QSA_CPU_OFFLOAD restore_' not in line:
            continue
        require(len(line.encode()) <= MAX_LINE_BYTES, 'audit_line_size_limit')
        if MARKER in line:
            require(line.count(MARKER) == 1, 'multiple_markers_on_line')
            value = decode_json(line.split(MARKER, 1)[1])
            require(isinstance(value, dict) and value.get('event') in EVENTS, 'unknown_audit_event')
            require(integer(value.get('epoch')), 'missing_or_invalid_epoch')
            audit.append({**value, '_line': number})
        else:
            submitted = re.search(r'QSA_CPU_OFFLOAD restore_submitted event_id=(\d+) loaded_blocks=(\d+) loaded_bytes=(\d+) request_ids=(.+)$', line)
            scheduled = re.search(r'QSA_CPU_OFFLOAD restore_scheduled request_id=(\S+) local_tokens=(\d+) external_tokens=(\d+) end_tokens=(\d+) families=([^\r\n]+)$', line)
            completed = re.search(r'QSA_CPU_OFFLOAD restore_completed request_id=(\S+)\s*$', line)
            if submitted:
                ids = ast.literal_eval(submitted[4])
                require(isinstance(ids, list) and ids and all(isinstance(v, str) and REQUEST.fullmatch(v) for v in ids), 'invalid_submitted_requests')
                connector.append({'event': 'submitted', 'transfer_event': int(submitted[1]),
                    'loaded_blocks': int(submitted[2]), 'loaded_bytes': int(submitted[3]),
                    'request_ids': ids, '_line': number})
            elif scheduled:
                connector.append({'event': 'scheduled', 'request_id': scheduled[1],
                    'local_tokens': int(scheduled[2]), 'external_tokens': int(scheduled[3]),
                    'end_tokens': int(scheduled[4]), '_line': number})
            elif completed:
                connector.append({'event': 'completed', 'request_id': completed[1], '_line': number})
            else:
                raise EvidenceError('malformed_restore_marker_at_line:' + str(number))
        require(len(audit) + len(connector) <= MAX_EVENTS, 'event_count_limit')
    require(audit, 'missing_audit_events')
    registered = [r for r in audit if r['event'] == 'registered']
    require(len(registered) == 1 and audit[0] is registered[0], 'registration_missing_ambiguous_or_not_first')
    epoch = registered[0]['epoch']
    for event in audit[1:]:
        if event['event'] == 'external_reset':
            require(event['epoch'] > epoch, 'reset_epoch_not_increasing')
            epoch = event['epoch']
        else:
            require(event['epoch'] == epoch, 'event_epoch_without_committed_reset')
    return audit, connector, {'path': str(path.resolve()), 'sha256': hashlib.sha256(raw).hexdigest(),
                             'bytes': len(raw), 'audit_events': len(audit)}


def registry(event):
    groups = event.get('groups')
    require(isinstance(groups, dict) and groups and len(groups) <= 128, 'invalid_registered_groups')
    require(integer(event.get('raw_storages'), 1) and event['raw_storages'] <= 2048, 'invalid_raw_storage_count')
    result = {}
    owners_seen = set()
    for key, group in groups.items():
        require(isinstance(key, str) and key.isdigit() and str(int(key)) == key, 'invalid_group_id')
        require(isinstance(group, dict) and type(group.get('cacheable')) is bool, 'missing_group_cacheability')
        require(integer(group.get('block_size'), 1), 'invalid_group_block_size')
        owners = group.get('owners')
        require(isinstance(owners, list) and owners and all(isinstance(v, str) for v in owners), 'invalid_group_owners')
        require(len(set(owners)) == len(owners) and not owners_seen.intersection(owners), 'duplicate_group_owners')
        owners_seen.update(owners)
        families = sorted({family(v) for v in owners})
        require(('raw' not in families) if group['cacheable'] else families == ['raw'], 'unexpected_cacheability_family')
        result[int(key)] = {**group, 'families': families}
    cached = {g: v for g, v in result.items() if v['cacheable']}
    require({f for g in cached.values() for f in g['families']} == {'main', 'compressed', 'gdn', 'ple'}, 'missing_expected_qsa_families')
    return result, event['raw_storages']


def descriptor(value, groups):
    require(isinstance(value, dict), 'missing_descriptor')
    for key in ('cpu', 'gpu', 'group'):
        require(integer(value.get(key)), 'invalid_descriptor_' + key)
    group = groups.get(value['group'])
    require(group is not None and group['cacheable'], 'unregistered_or_noncacheable_transfer_group')
    key = value.get('key')
    require(isinstance(key, str) and len(key) > 8 and len(key) <= 264 and len(key) % 2 == 0
            and re.fullmatch('[0-9a-f]+', key), 'invalid_checkpoint_key')
    require(int(key[-8:], 16) == value['group'], 'checkpoint_key_group_mismatch')
    require(value.get('group_block_size') == group['block_size'], 'descriptor_block_size_mismatch')
    require(value.get('families') == group['families'], 'descriptor_family_mismatch')
    ids = value.get('request_ids')
    require(isinstance(ids, list) and ids and len(set(ids)) == len(ids)
            and all(isinstance(v, str) and REQUEST.fullmatch(v) for v in ids), 'invalid_descriptor_requests')
    bounds = value.get('boundaries')
    require(isinstance(bounds, list) and bounds, 'missing_descriptor_boundaries')
    seen = set()
    for pair in bounds:
        require(isinstance(pair, list) and len(pair) == 2 and pair[0] in ids
                and integer(pair[1], 1) and pair[1] % group['block_size'] == 0, 'invalid_descriptor_boundary')
        require(tuple(pair) not in seen, 'duplicate_descriptor_boundary')
        seen.add(tuple(pair))
    return value


def pair_key(desc):
    return desc['cpu'], desc['gpu'], desc['key'], desc['group']


def bound_to(desc, request_id):
    # The fixture is serial. Event-wide request membership alone is insufficient.
    require(len(desc['request_ids']) == 1 and request_matches(desc['request_ids'][0], request_id), 'ambiguous_or_wrong_request_binding')
    rows = [(rid, n) for rid, n in desc['boundaries'] if request_matches(rid, request_id)]
    require(len(rows) == len(desc['boundaries']) == 1, 'ambiguous_or_missing_hash_boundary_binding')
    return rows[0][1]


def raw_hashes(value, count):
    require(isinstance(value, dict) and len(value) == count, 'missing_raw_storage_coverage')
    require(all(isinstance(k, str) and k and isinstance(v, str) and SHA.fullmatch(v)
                for k, v in value.items()), 'invalid_raw_digest')
    return value


def semantic_hashes(value, group):
    require(isinstance(value, dict) and value, 'missing_semantic_owner_coverage')
    parts = {owner: [] for owner in group['owners']}
    for key, detail in value.items():
        require(isinstance(key, str) and ':' in key, 'invalid_semantic_owner_key')
        owner, part = key.rsplit(':', 1)
        require(owner in parts and part.isdigit() and str(int(part)) == part and int(part) < 8, 'unexpected_semantic_owner_or_part')
        require(isinstance(detail, dict) and detail.get('family') == family(owner), 'semantic_family_mismatch')
        require(isinstance(detail.get('dtype'), str) and detail['dtype'].startswith('torch.'), 'missing_semantic_dtype')
        require(isinstance(detail.get('shape'), list) and all(integer(n, 1) for n in detail['shape']), 'invalid_semantic_shape')
        require(isinstance(detail.get('sha256'), str) and SHA.fullmatch(detail['sha256']), 'invalid_semantic_digest')
        parts[owner].append(int(part))
    require(all(sorted(v) == list(range(len(v))) and v for v in parts.values()), 'incomplete_semantic_owner_parts')
    return value


def one(values, reason):
    require(len(values) == 1, reason)
    return values[0]


def targets_from_probe(report):
    require(isinstance(report, dict) and report.get('mode') == 'cpu', 'cpu_probe_report_required')
    require(isinstance(report.get('cases'), list) and report['cases'], 'missing_probe_cases')
    targets = []
    for case in report['cases']:
        require(isinstance(case, dict), 'invalid_probe_case')
        producer = case.get('producer') or {}
        require(integer(case.get('boundary'), 1), 'missing_probe_boundary')
        ids = case.get('frozen_input_ids')
        require(isinstance(ids, list) and len(ids) == case['boundary'] + 1
                and all(integer(v) for v in ids), 'probe_conditioning_length_mismatch')
        digest = hashlib.sha256(json.dumps(ids, sort_keys=True).encode()).hexdigest()
        require(case.get('frozen_input_sha256') == digest, 'probe_conditioning_hash_mismatch')
        produced_ids = producer.get('token_ids')
        require(isinstance(produced_ids, list) and len(produced_ids) >= 9
                and all(integer(v) for v in produced_ids)
                and produced_ids[:9] == ids[-9:]
                and producer.get('prompt_tokens') == len(ids) - 9
                and producer.get('prompt_sha256') == hashlib.sha256(
                    json.dumps(ids[:-9], sort_keys=True).encode()).hexdigest(),
                'probe_input_not_exact_producer_prefix_and_first_nine_tokens')
        rows = case.get('rows')
        require(isinstance(rows, list) and all(isinstance(r, dict) for r in rows), 'invalid_probe_rows')
        restored = [r for r in rows if r.get('category') == 'cpu-restored']
        require(restored, 'missing_probe_restore_requests')
        for row in restored:
            targets.append({'request_id': row.get('request_id'),
                'producer_request_id': producer.get('request_id'), 'boundary': case['boundary'],
                'probe_transfer_confirmed': (row.get('restore_proof') or {}).get('confirmed') is True,
                'probe_conditioning_confirmed': row.get('prompt_sha256') == digest
                    and row.get('prompt_tokens') == len(ids)})
    return targets


def analyze_target(target, audit, connector, groups, storage_count):
    request_id = target['request_id']
    producer = target.get('producer_request_id')
    require(isinstance(producer, str) and REQUEST.fullmatch(producer), 'expected_producer_identity_required')
    require(producer != request_id, 'producer_equals_restore_request')
    expected = target.get('boundary')
    require(integer(expected, 1), 'expected_boundary_required')
    require(target.get('probe_transfer_confirmed', True) is True, 'probe_restore_proof_failed')
    require(target.get('probe_conditioning_confirmed', True) is True, 'probe_conditioning_failed')
    schedules = [v for v in connector if v['event'] == 'scheduled' and request_matches(v['request_id'], request_id)]
    scheduled = one(schedules, 'missing_or_ambiguous_restore_schedule')
    require(scheduled['local_tokens'] == 0 and scheduled['external_tokens'] == scheduled['end_tokens'] == expected,
            'restore_did_not_load_exact_expected_boundary_from_cpu')
    completed = one([v for v in connector if v['event'] == 'completed' and request_matches(v['request_id'], request_id)],
                    'missing_or_ambiguous_restore_completion')
    actual_id = scheduled['request_id']
    require(completed['request_id'] == actual_id, 'restore_request_wrapper_mismatch')
    captured = []
    for event in audit:
        if event['event'] != 'load_captured':
            continue
        values = event.get('descriptors')
        require(isinstance(values, list), 'load_capture_without_descriptor_list')
        if any(isinstance(d, dict) and any(request_matches(r, request_id) for r in d.get('request_ids', [])) for d in values):
            captured.append(event)
    capture = one(captured, 'missing_or_ambiguous_target_load_capture')
    event_id, epoch = capture.get('transfer_event'), capture['epoch']
    require(integer(event_id) and capture.get('phase') == 'after_forward_before_submit', 'invalid_load_capture_phase_or_event')
    # EngineCore emits restore_scheduled; workers emit the other events. Docker
    # may interleave those streams, so require ordering only within the worker.
    require(capture['_line'] < completed['_line'], 'restore_event_order_invalid')
    descs = [descriptor(d, groups) for d in capture['descriptors']]
    require(descs and len({pair_key(d) for d in descs}) == len(descs), 'empty_or_duplicate_load_pairs')
    require(len({d['cpu'] for d in descs}) == len(descs) and len({d['gpu'] for d in descs}) == len(descs), 'duplicate_physical_load_slot')
    submit = one([v for v in connector if v['event'] == 'submitted' and v['transfer_event'] == event_id],
                 'missing_or_ambiguous_transfer_submission')
    require(submit['request_ids'] == [actual_id] and submit['loaded_blocks'] == len(descs)
            and submit['loaded_bytes'] > 0 and submit['loaded_bytes'] % len(descs) == 0, 'submitted_pair_count_or_request_mismatch')
    require(capture['_line'] < submit['_line'] < completed['_line'], 'submission_order_invalid')
    events = [v for v in audit if v['epoch'] == epoch and v.get('transfer_event') == event_id]
    raw_loads = [v for v in events if v['event'] == 'load_raw_copy']
    origins = [v for v in events if v['event'] == 'load_origin']
    keys = {pair_key(d) for d in descs}
    for values, kind in ((raw_loads, 'load_raw_copy'), (origins, 'load_origin')):
        actual_keys = [pair_key(descriptor(v.get('descriptor'), groups)) for v in values]
        require(len(actual_keys) == len(keys) and set(actual_keys) == keys, 'incomplete_or_extra_' + kind + '_pairs')
    covered = {}
    chains = []
    for desc in descs:
        boundary = bound_to(desc, request_id)
        require(desc['request_ids'] == [actual_id] and boundary <= expected, 'load_boundary_or_wrapper_mismatch')
        covered.setdefault(desc['group'], []).append(boundary)
        raw = one([v for v in raw_loads if v['descriptor'] == desc], 'load_descriptor_changed_after_capture')
        origin = one([v for v in origins if v['descriptor'] == desc], 'origin_descriptor_changed_after_capture')
        require(capture['_line'] < raw['_line'] < origin['_line'] < completed['_line'], 'load_completion_order_invalid')
        require(raw.get('exact') is True and raw.get('scope') == RAW_SCOPE, 'load_raw_copy_not_exact')
        cpu_raw = raw_hashes(raw.get('source_raw_sha256'), storage_count)
        gpu_raw = raw_hashes(raw.get('destination_raw_sha256'), storage_count)
        require(cpu_raw == gpu_raw, 'load_raw_digests_differ')
        require(origin.get('coverage') == 'semantic_owners'
                and origin.get('cpu_unchanged_since_store') is True
                and origin.get('semantic_exact') is True, 'origin_missing_or_chain_not_exact')
        store_id = origin.get('origin_store_event')
        require(integer(store_id), 'missing_origin_store_event')
        source = descriptor(origin.get('origin_descriptor'), groups)
        for field in ('cpu', 'key', 'group', 'group_block_size', 'families'):
            require(source[field] == desc[field], 'origin_' + field + '_mismatch')
        require(bound_to(source, producer) == boundary, 'producer_hash_boundary_mismatch')
        store_cap = one([v for v in audit if v['epoch'] == epoch and v['event'] == 'store_captured'
                         and v.get('transfer_event') == store_id], 'origin_store_capture_missing_or_ambiguous')
        require(store_cap.get('phase') == 'after_forward_before_submit'
                and isinstance(store_cap.get('descriptors'), list)
                and store_cap['descriptors'].count(source) == 1, 'source_pair_not_in_store_capture')
        store_raw = one([v for v in audit if v['epoch'] == epoch and v['event'] == 'store_raw_copy'
                         and v.get('transfer_event') == store_id and v.get('descriptor') == source],
                        'origin_store_raw_copy_missing_or_ambiguous')
        require(store_cap['_line'] < store_raw['_line'] < capture['_line'], 'origin_store_not_completed_before_load_capture')
        require(store_raw.get('exact') is True and store_raw.get('scope') == RAW_SCOPE, 'origin_store_raw_copy_not_exact')
        source_raw = raw_hashes(store_raw.get('source_raw_sha256'), storage_count)
        stored_raw = raw_hashes(store_raw.get('destination_raw_sha256'), storage_count)
        require(source_raw == stored_raw == cpu_raw, 'store_to_cpu_to_load_raw_chain_differs')
        source_semantic = semantic_hashes(store_raw.get('source_semantic'), groups[desc['group']])
        loaded_semantic = semantic_hashes(origin.get('semantic'), groups[desc['group']])
        require(source_semantic == loaded_semantic, 'origin_semantic_digests_differ')
        slot_stores = [v for v in audit if v['epoch'] == epoch and v['event'] == 'store_raw_copy'
                       and isinstance(v.get('descriptor'), dict) and v['descriptor'].get('cpu') == desc['cpu']
                       and v['_line'] < capture['_line']]
        require(max(slot_stores, key=lambda v: v['_line']) is store_raw, 'cpu_slot_rebound_since_claimed_origin')
        chains.append({'cpu': desc['cpu'], 'source_gpu': source['gpu'], 'restored_gpu': desc['gpu'],
            'key': desc['key'], 'group': desc['group'], 'boundary': boundary,
            'origin_store_event': store_id, 'producer_request_id': source['request_ids'][0],
            'store_line': store_raw['_line'], 'load_line': raw['_line'], 'origin_line': origin['_line'],
            'raw_chain_exact': True, 'semantic_origin_exact': True})
    expected_groups = {g for g, v in groups.items() if v['cacheable']}
    require(set(covered) == expected_groups, 'missing_registered_cacheable_load_groups')
    require(all(max(bounds) == expected for bounds in covered.values()), 'terminal_boundary_missing_in_group')
    watches = []
    chain_keys = {(v['cpu'], v['key'], v['origin_store_event']) for v in chains}
    for event in audit:
        desc = event.get('descriptor')
        if event['event'] != 'resident_checkpoint_watch' or event['epoch'] != epoch or not isinstance(desc, dict):
            continue
        key = (desc.get('cpu'), desc.get('key'), event.get('origin_store_event'))
        if key in chain_keys and event['_line'] < completed['_line']:
            watches.append({'line': event['_line'], 'group': desc.get('group'),
                'exact': event.get('exact'), 'coverage': event.get('coverage'),
                'new_request_ids': event.get('new_request_ids'), 'finished_request_ids': event.get('finished_request_ids')})
    return {'pass': True, 'epoch': epoch, 'transfer_event': event_id,
        'actual_request_id': actual_id, 'expected_boundary': expected,
        'expected_pair_count': submit['loaded_blocks'], 'verified_pair_count': len(chains),
        'registered_cacheable_groups': sorted(expected_groups), 'chains': chains,
        'sampled_resident_watches': watches,
        'sampled_resident_mutation_observed': any(v['exact'] is False for v in watches)}


def analyze_resume_audit(logfile, report_request_ids):
    """Return strict per-request provenance. Bare IDs lack an origin and fail.

    A full probe report may be supplied directly, or a list of target specs.
    Errors are returned as evidence failures; no empty aggregate can pass.
    """
    output = {'schema_version': 1, 'pass': False, 'results': [], 'errors': [],
        'analyzer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope': 'serial text fixture; exact GPU-source to CPU-store to GPU-load provenance',
        'limitations': ['Raw hashes include padding and aliased storage; semantic hashes select registered group owners.',
            'A provenance pass does not establish numerical output equivalence or correctness of the original checkpoint.',
            'Resident watches sample selected bound checkpoints and are not exhaustive immutability proof.',
            'Synchronous readbacks can mask ordering races; no throughput or asynchronous-safety claim.',
            'All per-owner state parts are enumerated by the attested runtime; registration names alone do not specify part counts.',
            'Log source/runtime identity must be attested independently; this analyzer performs no cloud or runtime inspection.']}
    targets = []
    try:
        source = targets_from_probe(report_request_ids) if isinstance(report_request_ids, dict) else report_request_ids
        require(isinstance(source, list) and 1 <= len(source) <= MAX_TARGETS, 'expected_nonempty_bounded_target_list')
        targets = [{'request_id': item} if isinstance(item, str) else item for item in source]
        require(all(isinstance(t, dict) and isinstance(t.get('request_id'), str)
                    and REQUEST.fullmatch(t['request_id']) for t in targets), 'invalid_target_request_id')
        require(len({t['request_id'] for t in targets}) == len(targets), 'duplicate_target_request_id')
        audit, connector, evidence = parse_log(logfile)
        groups, storages = registry(audit[0])
        output['log'] = evidence
        for target in targets:
            row = {'request_id': target['request_id'], 'producer_request_id': target.get('producer_request_id'),
                   'expected_boundary': target.get('boundary'), 'pass': False, 'errors': []}
            try:
                row.update(analyze_target(target, audit, connector, groups, storages))
            except (EvidenceError, ValueError, TypeError, KeyError, IndexError) as error:
                row['errors'].append(str(error))
            output['results'].append(row)
        output['pass'] = bool(output['results']) and all(r['pass'] for r in output['results'])
    except (EvidenceError, OSError, UnicodeError, ValueError, TypeError, KeyError, IndexError, SyntaxError) as error:
        output['errors'].append(str(error))
        output['results'] = [{'request_id': t.get('request_id'), 'pass': False,
                              'errors': ['log_or_target_input_invalid']} for t in targets if isinstance(t, dict)]
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--logfile', type=Path, required=True)
    parser.add_argument('--probe-report', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    with args.probe_report.open('rb') as handle:
        probe_bytes = handle.read(MAX_PROBE_BYTES + 1)
    require(len(probe_bytes) <= MAX_PROBE_BYTES, 'probe_report_size_limit')
    report = decode_json(probe_bytes)
    result = analyze_resume_audit(args.logfile, report)
    result['probe_report'] = {'path': str(args.probe_report.resolve()),
                              'sha256': hashlib.sha256(probe_bytes).hexdigest()}
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        with args.output.open('x', encoding='utf-8') as handle:
            handle.write(text)
    else:
        print(text, end='')
    raise SystemExit(0 if result['pass'] else 1)


if __name__ == '__main__':
    main()

"""Bounded read-only trace comparison. Missing or ambiguous binding is not a pass."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import itertools
import json
from pathlib import Path
import re
import struct

MAX_BYTES = 256 * 1024**2
MAX_LINE = 4 * 1024**2
MAX_EVENTS = 300000
MARKER = b'QSA_LAYER_TRACE '
EVENTS = {'installed', 'begin', 'module_input', 'module_output', 'qsa_selection',
          'end', 'logits_input', 'logits_output', 'trace_exhausted'}


class EvidenceError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise EvidenceError(reason)


def unique_pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'duplicate_json_key:' + key)
        result[key] = value
    return result


def decode(raw):
    def reject(value):
        raise EvidenceError('nonfinite_json:' + value)
    return json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=reject)


def file_bytes(path):
    path = Path(path)
    require(path.is_file() and path.stat().st_size <= MAX_BYTES, 'missing_or_oversized_file')
    raw = path.read_bytes()
    require(len(raw) <= MAX_BYTES, 'file_grew_past_bound')
    return raw


def int_hash(values, dtype):
    fmt = {'torch.int64': '<q', 'torch.int32': '<i'}.get(dtype)
    require(fmt is not None, 'unsupported_token_or_position_dtype')
    digest = hashlib.sha256()
    for value in values:
        require(type(value) is int, 'noninteger_token_or_position')
        digest.update(struct.pack(fmt, value))
    return digest.hexdigest()


def fingerprint_match(desc, values, shape):
    if not isinstance(desc, dict) or desc.get('shape') != shape:
        return False
    width = {'torch.int64': 8, 'torch.int32': 4}.get(desc.get('dtype'))
    return width is not None and desc.get('bytes') == width * len(values) and desc.get('sha256') == int_hash(values, desc['dtype'])


def terminal_input(begin, frozen, category):
    desc = begin.get('input_ids')
    if not isinstance(desc, dict) or not isinstance(desc.get('shape'), list) or len(desc['shape']) != 1:
        return False
    count = desc['shape'][0]
    if type(count) is not int or not 1 <= count <= len(frozen):
        return False
    if category != 'cold' and count != 1:
        return False
    if not fingerprint_match(desc, frozen[-count:], [count]):
        return False
    position_desc = begin.get('positions')
    positions = list(range(len(frozen) - count, len(frozen)))
    shape = position_desc.get('shape') if isinstance(position_desc, dict) else None
    if shape == [count]:
        return fingerprint_match(position_desc, positions, shape)
    if shape == [3, count]:
        return fingerprint_match(position_desc, positions * 3, shape)
    return False


def tensor_desc(value):
    return (isinstance(value, dict) and isinstance(value.get('shape'), list)
            and all(type(n) is int and n >= 0 for n in value['shape'])
            and isinstance(value.get('dtype'), str) and value['dtype'].startswith('torch.')
            and type(value.get('bytes')) is int and value['bytes'] >= 0
            and isinstance(value.get('sha256'), str)
            and re.fullmatch('[0-9a-f]{64}', value['sha256']) is not None)


def embedding_input_errors(begin):
    """V2 must explicitly attest embeddings even when they are absent."""
    errors = []
    if begin.get('trace_schema_version') != 2:
        errors.append('unsupported_or_missing_trace_schema_version')
    if not all(key in begin for key in ('inputs_embeds', 'deepstack_input_embeds', 'input_representation')):
        return errors + ['missing_embedding_input_coverage']
    embeddings, deepstack = begin['inputs_embeds'], begin['deepstack_input_embeds']
    if embeddings is not None and not tensor_desc(embeddings):
        errors.append('malformed_embedding_fingerprint')
    if deepstack is not None and not (
            isinstance(deepstack, dict)
            and all(isinstance(key, str) and tensor_desc(value) for key, value in deepstack.items())):
        errors.append('malformed_deepstack_fingerprints')
    expected = 'token_ids' if embeddings is None else 'token_ids_with_embeddings'
    if begin['input_representation'] != expected:
        errors.append('embedding_representation_mismatch')
    return errors


def parse_trace(logfile):
    raw = file_bytes(logfile)
    forwards, installed, other, count = {}, {}, [], 0
    offset = 0
    # Keep exact physical byte spans. CR progress lines are not trace records.
    for line_number, line in enumerate(raw.splitlines(keepends=True), 1):
        start, offset = offset, offset + len(line)
        if MARKER not in line:
            continue
        require(line.count(MARKER) == 1 and len(line) <= MAX_LINE, 'malformed_or_oversized_trace_line')
        value = decode(line.split(MARKER, 1)[1])
        require(isinstance(value, dict) and value.get('event') in EVENTS, 'unknown_trace_event')
        require(type(value.get('pid')) is int and isinstance(value.get('model_prefix'), str), 'missing_trace_identity')
        prefix = line.split(MARKER, 1)[0].decode('utf-8', errors='strict')
        timestamp = re.search(r'\b(\d\d-\d\d \d\d:\d\d:\d\d)\b', prefix)
        event = {**value, '_start': start, '_end': offset, '_line': line_number,
                 '_log_timestamp': timestamp[1] if timestamp else None}
        owner = (value['pid'], value['model_prefix'])
        count += 1
        require(count <= MAX_EVENTS, 'trace_event_limit')
        if value['event'] == 'installed':
            require(owner not in installed, 'duplicate_trace_installation')
            installed[owner] = event
        elif value['event'] == 'trace_exhausted':
            other.append(event)
        else:
            number = value.get('forward_id')
            require(type(number) is int and 1 <= number <= 512, 'invalid_forward_id')
            forwards.setdefault((*owner, number), []).append(event)
    require(installed, 'missing_trace_installation')
    require(forwards, 'no_traced_forward_records')
    result = []
    for key, events in forwards.items():
        require(key[:2] in installed, 'forward_without_installation')
        by_type = {}
        for event in events:
            by_type.setdefault(event['event'], []).append(event)
        errors = []
        for kind in ('begin', 'end', 'logits_input', 'logits_output'):
            if len(by_type.get(kind, [])) != 1:
                errors.append('missing_or_duplicate_' + kind)
        if not errors:
            begin, end = by_type['begin'][0], by_type['end'][0]
            li, lo = by_type['logits_input'][0], by_type['logits_output'][0]
            errors.extend(embedding_input_errors(begin))
            if not begin['_start'] < end['_start'] < li['_start'] < lo['_start']:
                errors.append('invalid_model_logit_event_order')
            if not tensor_desc(end.get('output')) or not tensor_desc(li.get('tensor')) or not tensor_desc(lo.get('tensor')):
                errors.append('missing_or_malformed_final_tensor_fingerprint')
            modules = {}
            for event in events:
                if event['event'] not in ('module_input', 'module_output'):
                    continue
                module = event.get('module')
                if not isinstance(module, str) or not begin['_start'] < event['_start'] < end['_start']:
                    errors.append('invalid_module_identity_or_order')
                    continue
                modules.setdefault(module, {}).setdefault(event['event'], []).append(event)
                if event['event'] == 'module_input' and (not isinstance(event.get('args'), list) or not isinstance(event.get('kwargs'), dict)):
                    errors.append('missing_module_input_fingerprints:' + module)
                if event['event'] == 'module_output' and 'output' not in event:
                    errors.append('missing_module_output_fingerprint:' + module)
            for module, pair in modules.items():
                if len(pair.get('module_input', [])) != 1 or len(pair.get('module_output', [])) != 1:
                    errors.append('incomplete_or_duplicate_module:' + module)
                elif pair['module_input'][0]['_start'] >= pair['module_output'][0]['_start']:
                    errors.append('module_output_precedes_input:' + module)
                if pair.get('module_input', [{}])[0].get('kind') == 'qsa_indexer':
                    selections = [e for e in events if e['event'] == 'qsa_selection' and e.get('module') == module]
                    if len(selections) != 1:
                        errors.append('missing_or_duplicate_indexer_selection:' + module)
                    elif not tensor_desc(selections[0].get('ordered')) or not tensor_desc(selections[0].get('sorted_per_row')):
                        errors.append('missing_selection_fingerprints:' + module)
            # One input+output per installed module, including optional indexer.
            if 2 * len(modules) != installed[key[:2]].get('hooks'):
                errors.append('module_coverage_differs_from_registered_hooks')
        result.append({'key': key, 'events': events, 'types': by_type, 'errors': errors,
                       'start': events[0]['_start'], 'end': events[-1]['_end']})
    return sorted(result, key=lambda f: f['start']), other, {
        'path': str(Path(logfile).resolve()), 'sha256': hashlib.sha256(raw).hexdigest(),
        'bytes': len(raw), 'events': count, 'forward_count': len(result)}


def row_interval(row):
    require(row.get('server_log_same_file_and_nonshrinking') is True, 'unattested_or_rotated_log_interval')
    span = row.get('trace_log') or {}
    start, end = span.get('start_offset'), span.get('end_offset')
    require(type(start) is int and type(end) is int and 0 <= start <= end, 'invalid_log_byte_span')
    begin_time = datetime.fromisoformat(row['request_started_utc'])
    end_time = datetime.fromisoformat(row['request_finished_utc'])
    require(begin_time.tzinfo is not None and end_time.tzinfo is not None and begin_time <= end_time,
            'invalid_request_utc_interval')
    return start, end


def bind(row, frozen, category, forwards, log_bytes):
    start, end = row_interval(row)
    require(end <= log_bytes, 'log_copy_ends_before_request_observation')
    candidates = [f for f in forwards if len(f['types'].get('begin', [])) == 1
                  and terminal_input(f['types']['begin'][0], frozen, category)]
    within = [f for f in candidates if start <= f['start'] and f['end'] <= end]
    require(len(within) == 1, 'missing_or_ambiguous_terminal_forward_in_exact_observed_span')
    chosen = within[0]
    require(not chosen['errors'], 'incomplete_terminal_forward:' + ','.join(chosen['errors']))
    require(chosen['types']['logits_input'][0]['tensor']['shape'][0] == 1,
            'nonserial_sampled_logits_batch')
    return chosen


def clean(value):
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if not k.startswith('_')
                and k not in ('pid', 'model_prefix', 'forward_id')}
    return value


def signature(event):
    return event['event'], event.get('module')


def logical_inputs(begin):
    return {key: begin.get(key) for key in ('input_ids', 'positions', 'query_start_loc',
        'ngram_context', 'inputs_embeds', 'deepstack_input_embeds', 'input_representation',
        'is_padding', 'batch')} | {'attention': [
            {'owners': row['owners'], 'class': row['class'], 'logical': row['logical']}
            for row in begin.get('attention', [])]}


def compare(left, right, label):
    a, b = left['types']['begin'][0], right['types']['begin'][0]
    inputs_equal = logical_inputs(a) == logical_inputs(b)
    left_inputs, right_inputs = logical_inputs(a), logical_inputs(b)
    events_a = [e for e in left['events'] if e['event'] in ('module_input', 'module_output', 'qsa_selection')]
    events_b = [e for e in right['events'] if e['event'] in ('module_input', 'module_output', 'qsa_selection')]
    same_order = [signature(e) for e in events_a] == [signature(e) for e in events_b]
    out = {'comparison': label, 'left_forward': list(left['key']), 'right_forward': list(right['key']),
           'selected_logical_inputs_equal': inputs_equal,
           'different_input_fields': [key for key in left_inputs if left_inputs[key] != right_inputs[key]],
           'physical_metadata_equal': [r.get('physical') for r in a.get('attention', [])] ==
                                      [r.get('physical') for r in b.get('attention', [])],
           'rng_before_equal': a.get('rng') == b.get('rng'),
           'rng_after_equal': left['types']['end'][0].get('rng') == right['types']['end'][0].get('rng'),
           'module_event_order_equal': same_order,
           'full_layer_comparison_eligible': inputs_equal and same_order,
           'first_observed_difference': None, 'selection_differences': []}
    for kind in ('logits_input', 'logits_output'):
        out[kind + '_equal'] = left['types'][kind][0].get('tensor') == right['types'][kind][0].get('tensor')
    if inputs_equal and same_order:
        for ea, eb in zip(events_a, events_b):
            if clean(ea) != clean(eb) and out['first_observed_difference'] is None:
                out['first_observed_difference'] = {'event': ea['event'], 'module': ea.get('module'),
                    'kind': ea.get('kind'), 'left_line': ea['_line'], 'right_line': eb['_line']}
            if ea['event'] == 'qsa_selection' and (ea.get('ordered') != eb.get('ordered') or ea.get('sorted_per_row') != eb.get('sorted_per_row')):
                out['selection_differences'].append({'module': ea['module'],
                    'ordered_equal': ea.get('ordered') == eb.get('ordered'),
                    'sorted_multiset_equal': ea.get('sorted_per_row') == eb.get('sorted_per_row')})
        if out['first_observed_difference'] is None:
            if left['types']['end'][0].get('output') != right['types']['end'][0].get('output'):
                out['first_observed_difference'] = {'event': 'model_end', 'module': None}
            elif not out['logits_input_equal']:
                out['first_observed_difference'] = {'event': 'logits_input', 'module': None}
            elif not out['logits_output_equal']:
                out['first_observed_difference'] = {'event': 'logits_output', 'module': None}
    out['interpretation'] = ('First differing observation, not proof of defective computation; cached state/omitted metadata may differ.'
        if out['full_layer_comparison_eligible'] else
        'Layer hashes are not directly comparable because logical inputs, shapes, or module coverage differ; compare selected logits only.')
    return out


def analyze(logfile, report_path):
    result = {'analysis_complete': False, 'errors': [], 'cases': [],
        'scope': 'Serial exact observed-log-span binding plus token/position fingerprint validation',
        'limitations': ['Follower offsets are observations, not flush fences. Unbound requests remain incomplete; no timestamp guessing.',
            'Selected logical metadata is partial effective-input coverage; cached state is checked separately by the CPU provenance audit.',
            'Cold full-prefill and resident one-token layer shapes differ; only selected logits are directly comparable across those paths.',
            'Synchronous tracing can hide races and has no valid throughput interpretation.',
            'Hashes report exact byte differences, not magnitude, tolerance, or model accuracy.']}
    try:
        report_raw = file_bytes(report_path)
        report = decode(report_raw)
        require(isinstance(report, dict), 'probe_report_must_be_an_object')
        result['probe_report'] = {'path': str(Path(report_path).resolve()), 'sha256': hashlib.sha256(report_raw).hexdigest()}
        require(report.get('status') == 'completed', 'probe_not_completed')
        require(report.get('mode') in ('cpu', 'gpu'), 'invalid_probe_mode')
        require(isinstance(report.get('cases'), list) and 1 <= len(report['cases']) <= 3, 'invalid_probe_cases')
        forwards, exhausted, evidence = parse_trace(logfile)
        result['log'] = evidence
        result['trace_exhausted'] = [clean(e) for e in exhausted]
        require(report.get('identity', {}).get('runtime_attestation', {}).get('server_arguments_match') is True,
                'missing_probe_runtime_attestation')
        used, all_intervals = set(), []
        for case in report['cases']:
            require(isinstance(case, dict), 'probe_case_must_be_an_object')
            require(case.get('status') == 'completed', 'probe_case_not_completed')
            frozen = case.get('frozen_input_ids')
            require(isinstance(frozen, list) and len(frozen) == case.get('boundary', -1) + 1
                    and all(type(v) is int and v >= 0 for v in frozen), 'invalid_frozen_input')
            frozen_hash = hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest()
            require(frozen_hash == case.get('frozen_input_sha256'), 'frozen_input_hash_mismatch')
            producer = case.get('producer') or {}
            require(producer.get('token_ids', [])[:9] == frozen[-9:] and producer.get('prompt_tokens') == len(frozen) - 9,
                    'producer_continuation_mismatch')
            require(producer.get('prompt_sha256') == hashlib.sha256(json.dumps(frozen[:-9], sort_keys=True).encode()).hexdigest(),
                    'producer_prompt_hash_mismatch')
            require(isinstance(case.get('rows'), list) and all(isinstance(r, dict) for r in case['rows']), 'invalid_probe_rows')
            families = {}
            for row in case['rows']:
                families.setdefault(row.get('category'), []).append(row.get('index'))
            required_families = {'resident', 'cold'} | ({'cpu-restored'} if report['mode'] == 'cpu' else set())
            require(set(families) == required_families, 'missing_or_unexpected_probe_families')
            repeats = len(families['resident'])
            require(2 <= repeats <= 5 and all(
                len(indices) == repeats and all(type(i) is int for i in indices)
                and indices == list(range(repeats)) for indices in families.values()),
                'missing_or_inconsistent_repeat_indices')
            rows = [(producer, 'producer')] + [(r, r.get('category')) for r in case['rows']]
            require(3 <= len(rows) <= 16 and all(c in ('producer', 'resident', 'cold', 'cpu-restored') for _, c in rows),
                    'invalid_or_unbounded_probe_rows')
            output = {'target': case.get('target'), 'boundary': case['boundary'], 'bindings': [], 'comparisons': []}
            result['cases'].append(output)
            bound = []
            for row, category in rows:
                entry = {'request_id': row.get('request_id'), 'category': category, 'index': row.get('index'),
                         'bound': False, 'errors': []}
                output['bindings'].append(entry)
                try:
                    require(isinstance(row.get('request_id'), str) and re.fullmatch(r'[A-Za-z0-9_-]{1,256}', row['request_id']), 'invalid_request_id')
                    if category != 'producer':
                        require(row.get('prompt_sha256') == frozen_hash and row.get('prompt_tokens') == len(frozen), 'row_conditioning_mismatch')
                    interval = row_interval(row)
                    all_intervals.append((interval, row['request_id']))
                    forward = bind(row, frozen, category, forwards, evidence['bytes'])
                    require(forward['key'] not in used, 'same_forward_bound_to_multiple_requests')
                    used.add(forward['key'])
                    entry.update(bound=True, forward=list(forward['key']), start_byte=forward['start'], end_byte=forward['end'],
                                 begin_line=forward['types']['begin'][0]['_line'],
                                 request_started_utc=row['request_started_utc'], request_finished_utc=row['request_finished_utc'])
                    bound.append((entry, forward))
                except (EvidenceError, KeyError, TypeError, ValueError) as error:
                    entry['errors'].append(str(error))
            for (a, fa), (b, fb) in itertools.combinations(bound, 2):
                # Bounded fixture: include first resident as common reference,
                # same-category repeats, and producer against first resident.
                if (a['category'] == b['category'] or a['category'] == 'resident' and a['index'] == 0
                    or a['category'] == 'producer' and b['category'] == 'resident' and b['index'] == 0):
                    name = f"{a['category']}:{a['index']} -> {b['category']}:{b['index']}"
                    output['comparisons'].append(compare(fa, fb, name))
            output['all_requests_bound'] = bool(output['bindings']) and all(b['bound'] for b in output['bindings'])
        ordered = sorted(all_intervals)
        require(len({rid for _, rid in ordered}) == len(ordered), 'duplicate_request_id')
        require(all(a[0][1] <= b[0][0] for a, b in zip(ordered, ordered[1:])), 'overlapping_observed_request_spans')
        result['analysis_complete'] = all(c['all_requests_bound'] for c in result['cases'])
    except (EvidenceError, OSError, ValueError, TypeError, KeyError, IndexError, OverflowError) as error:
        result['errors'].append(str(error))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--logfile', type=Path, required=True)
    parser.add_argument('--probe-report', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = analyze(args.logfile, args.probe_report)
    rendered = json.dumps(result, indent=2) + '\n'
    if args.output:
        with args.output.open('x', encoding='utf-8') as handle:
            handle.write(rendered)
    else:
        print(rendered, end='')
    raise SystemExit(0 if result['analysis_complete'] else 1)


if __name__ == '__main__':
    main()

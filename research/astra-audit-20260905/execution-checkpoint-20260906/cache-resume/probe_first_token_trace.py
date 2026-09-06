"""Repeated one-token cache checks with identical conditioning, no gameplay.

All phases use the same token IDs. Resident repeats must hit exactly the
declared aligned boundary. CPU phases require request-specific transfer proof.
Cold recomputation is a separate control, never a substitute for CPU restore.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import subprocess
import time
import urllib.parse
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

HELPER_SHA256 = '2ccc8c1a3e16a37484757544443f12f42590bd3e51037664d0803d0a70e676a3'
PLE_SHA256 = '2f0e6febb8c6fdeeeb5b85cc2d7098ba7ce7ee2464d690c33fdcf75e3215c33a'


def log_position(path):
    """Read the follower's current byte position; never block inference on logs."""
    try:
        value = Path(path).stat()
        return {'byte_offset': value.st_size, 'device': value.st_dev, 'inode': value.st_ino}
    except OSError as error:
        return {'byte_offset': None, 'error': type(error).__name__}


@contextmanager
def capture_completion_http(helper, server_log, interval_sink=None):
    """Observe the exact existing HTTP call; preserve payload, reply and errors.

    The helper is used serially by this probe. Its HTTP callable is restored on
    every exit. Log offsets are follower observations, not a flushed trace fence.
    """
    original = helper.http
    intervals = []

    def observed(base, path, payload=None, timeout=60):
        if path != '/v1/completions':
            return original(base, path, payload, timeout)
        before = log_position(server_log)
        interval = {'request_id': payload.get('request_id') if isinstance(payload, dict) else None,
                    'request_started_utc': datetime.now(timezone.utc).isoformat(),
                    'trace_log': {'start_offset': before['byte_offset'], 'end_offset': None},
                    'server_log_byte_offset_before': before['byte_offset'],
                    'server_log_position_before': before}
        intervals.append(interval)
        if interval_sink is not None:
            interval_sink.append(interval)
        try:
            return original(base, path, payload, timeout)
        except BaseException as error:
            interval['request_error_type'] = type(error).__name__
            raise
        finally:
            interval['request_finished_utc'] = datetime.now(timezone.utc).isoformat()
            after = log_position(server_log)
            interval['server_log_byte_offset_after'] = after['byte_offset']
            interval['trace_log']['end_offset'] = after['byte_offset']
            interval['server_log_position_after'] = after
            interval['server_log_same_file_and_nonshrinking'] = (
                before['byte_offset'] is not None and after['byte_offset'] is not None
                and before['byte_offset'] <= after['byte_offset']
                and (before['device'], before['inode']) == (after['device'], after['inode']))

    helper.http = observed
    try:
        yield intervals
    finally:
        helper.http = original


def producer_completion(helper, args, prompt, salt, interval_sink):
    with capture_completion_http(helper, args.server_log, interval_sink) as intervals:
        producer = helper.completion(args.base_url, args.model, prompt,
                                     args.producer_tokens, salt, 'producer', args.timeout)
    if len(intervals) == 1:
        producer.update(intervals[0])
    return producer


def load_helpers(path):
    spec = importlib.util.spec_from_file_location('original_restore_probe', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compare_next(left, right, tolerance=1e-4):
    if left['prompt_sha256'] != right['prompt_sha256']:
        raise ValueError('Cannot compare differently conditioned predictions')
    if len(left['token_ids']) != 1 or len(right['token_ids']) != 1:
        raise ValueError('This comparison accepts exactly one output token')
    token_equal = left['token_ids'] == right['token_ids']
    # Selected logprobs are comparable only when they refer to the same token.
    selected_error = (abs(left['token_logprobs'][0] - right['token_logprobs'][0])
                      if token_equal else None)
    common = sorted(set(left.get('top_logprobs', {})) & set(right.get('top_logprobs', {})))
    common_errors = {key: abs(left['top_logprobs'][key] - right['top_logprobs'][key]) for key in common}
    top_equal = bool(common) and set(left.get('top_logprobs', {})) == set(right.get('top_logprobs', {}))
    top_pass = top_equal and max(common_errors.values(), default=math.inf) <= tolerance
    selected_pass = token_equal and selected_error is not None and selected_error <= tolerance
    return {'same_conditioning': True, 'exact_next_token_equal': token_equal,
            'selected_token_logprob_error': selected_error,
            'common_top_token_count': len(common),
            'common_top_logprob_error_max': max(common_errors.values(), default=None),
            'selected_token_gate_pass': selected_pass, 'top_tokens_equal': top_equal,
            'top_distribution_gate_pass': top_pass, 'pass': selected_pass and top_pass}


def summarize(rows, tolerance):
    families = {}
    for row in rows:
        families.setdefault(row['category'], []).append(row)
    output = {}
    for category, values in families.items():
        pairs = [compare_next(a, b, tolerance) for a, b in itertools.combinations(values, 2)]
        output[category + '_repeatability'] = {
            'pairs': pairs, 'pass': bool(pairs) and all(p['pass'] for p in pairs)}
    if 'resident' in families and 'cpu-restored' in families:
        pairs = [compare_next(a, b, tolerance) for a in families['resident'] for b in families['cpu-restored']]
        output['resident_vs_cpu'] = {'pairs': pairs, 'pass': all(p['pass'] for p in pairs)}
    if 'resident' in families and 'cold' in families:
        output['resident_vs_cold_diagnostic'] = [compare_next(a, b, tolerance)
                                                for a in families['resident'] for b in families['cold']]
    return output


def next_token(helper, args, prompt, salt, category, index, interval_sink=None):
    helper.wait_idle(args.base_url)
    request_id = uuid.uuid4().hex
    payload = {'model': args.model, 'prompt': prompt, 'max_tokens': 1, 'min_tokens': 1,
               'temperature': 0, 'seed': 0, 'ignore_eos': True, 'stream': False,
               'return_token_ids': True, 'return_tokens_as_token_ids': True,
               'logprobs': 5, 'request_id': request_id, 'cache_salt': salt}
    start = time.perf_counter()
    with capture_completion_http(helper, args.server_log, interval_sink) as intervals:
        reply = helper.http(args.base_url, '/v1/completions', payload, args.timeout)
    choice = reply['choices'][0]
    assert choice.get('prompt_token_ids') == prompt, 'Prompt IDs changed'
    assert reply.get('usage', {}).get('prompt_tokens') == len(prompt)
    ids = choice.get('token_ids')
    assert isinstance(ids, list) and len(ids) == 1 and type(ids[0]) is int
    logs = choice.get('logprobs') or {}
    probabilities = logs.get('token_logprobs')
    assert isinstance(probabilities, list) and len(probabilities) == 1
    assert isinstance(probabilities[0], (int, float)) and math.isfinite(probabilities[0])
    top = (logs.get('top_logprobs') or [{}])[0]
    assert isinstance(top, dict) and all(isinstance(v, (int, float)) and math.isfinite(v) for v in top.values())
    return {'category': category, 'index': index, 'request_id': request_id,
            'prompt_sha256': helper.sha(prompt), 'prompt_tokens': len(prompt),
            'request_sha256': helper.sha(payload), 'token_ids': ids,
            'token_logprobs': probabilities, 'top_logprobs': top,
            'usage': reply['usage'], 'elapsed_seconds': time.perf_counter() - start,
            **(intervals[0] if len(intervals) == 1 else {})}


def attest(args):
    identity = json.loads(args.identity.read_text())
    current = json.loads(args.current_identity.read_text())
    if identity['container_id'] != current['container_id']:
        raise ValueError('Diagnostic profile is not the current container')
    state = subprocess.check_output(['docker', 'inspect', '--format', '{{.State.Running}}',
                                     identity['container_id']], text=True).strip()
    if state != 'true':
        raise ValueError('Diagnostic container is not running')
    inspected = json.loads(subprocess.check_output(['docker', 'inspect', identity['container_id']], text=True))[0]
    assert inspected['Config']['Image'] == identity['image'], 'Live image reference differs'
    argv = identity['command_argv']
    assert inspected['Config']['Cmd'] == argv[argv.index(identity['image']) + 1:], 'Live server arguments differ'
    mounts = {item['Destination']: item for item in inspected.get('Mounts', [])}
    files = dict(identity['patches'])
    files['vllm/models/qwen3_8_flash_next/nvidia/ple_layer.py'] = PLE_SHA256
    verified = {}
    for name, expected in files.items():
        mount = mounts['/usr/local/lib/python3.12/dist-packages/' + name]
        assert mount['RW'] is False, 'Diagnostic overlays must be read-only'
        actual = hashlib.sha256(Path(mount['Source']).read_bytes()).hexdigest()
        assert actual == expected, 'Live mounted source differs: ' + name
        verified[name] = actual
    assert hashlib.sha256(args.helper.read_bytes()).hexdigest() == HELPER_SHA256, 'Probe helper source differs'
    identity = dict(identity, runtime_attestation={'image_reference': inspected['Config']['Image'],
                                                 'server_arguments_match': True, 'mounted_source_hashes': verified,
                                                 'helper_sha256': HELPER_SHA256})
    assert identity['main_gpu_memory_utilization'] == .965
    assert identity['context'] >= max(args.lengths)
    assert identity['served_model_name'] == args.model
    if args.mode == 'cpu':
        assert identity['arm'].startswith('qsa-cpu-')
    else:
        assert not identity['arm'].startswith('qsa-cpu-')
    return identity


def execute_case(helper, args, report, target):
    boundary = ((target - 128) // args.alignment) * args.alignment
    base_length = boundary - 8
    if base_length < 512:
        raise ValueError('Boundary too small')
    salt = 'resume-first-token-' + uuid.uuid4().hex
    head = helper.tokenize(args.base_url, args.model, f'Isolated numeric cache validation at {target}.\n', args.timeout)
    filler = helper.tokenize(args.base_url, args.model, ' record blue square green circle red triangle.\n', args.timeout)
    tail = helper.tokenize(args.base_url, args.model, '\nContinue a numbered list of short color and shape records:\n1.', args.timeout)
    prompt = helper.exact_prompt(head, filler, tail, base_length)
    case = {'target': target, 'boundary': boundary, 'producer_prompt_tokens': base_length,
            'rows': [], 'resets': [], 'status': 'running', 'request_intervals': []}
    report['cases'].append(case)
    case['resets'].append(helper.reset_gpu(args.base_url, external=True))
    producer = producer_completion(helper, args, prompt, salt, case['request_intervals'])
    case['producer'] = producer
    continuation = prompt + producer['token_ids'][:9]
    case['producer_output_tokens'] = args.producer_tokens
    case['continuation_uses_first_generated_tokens'] = 9
    case['frozen_input_ids'] = continuation
    case['frozen_input_sha256'] = helper.sha(continuation)
    # No more than one prediction per request: all cached lookups end at N and
    # every evaluated prediction conditions on the identical N+1 input tokens.
    for index in range(args.repeats):
        row = next_token(helper, args, continuation, salt, 'resident', index, case['request_intervals'])
        row['boundary_confirmed'] = helper.cached(row) == boundary
        case['rows'].append(row)
        helper.save(args.output, report)
    if args.mode == 'cpu':
        for index in range(args.repeats):
            case['resets'].append(helper.reset_gpu(args.base_url, external=False))
            before = helper.metrics(args.base_url)
            _, offset, _ = helper.read_log(args.server_log)
            row = next_token(helper, args, continuation, salt, 'cpu-restored', index, case['request_intervals'])
            row['restore_proof'] = helper.collect_restore_proof(
                args, row['request_id'], before, base_length, len(continuation), args.alignment, offset)
            case['rows'].append(row)
            helper.save(args.output, report)
    for index in range(args.repeats):
        case['resets'].append(helper.reset_gpu(args.base_url, external=True))
        before = helper.metrics(args.base_url)
        row = next_token(helper, args, continuation, salt, 'cold', index, case['request_intervals'])
        after = helper.metrics(args.base_url)
        row['metrics_before'] = before
        row['metrics_after'] = after
        external = helper.metric_delta(before, after, 'vllm:external_prefix_cache_hits_total')
        row['cold_confirmed'] = helper.cached(row) == 0 and external == 0
        case['rows'].append(row)
        helper.save(args.output, report)
    case['comparisons'] = summarize(case['rows'], args.tolerance)
    provenance = all(
        row.get('boundary_confirmed') is True if row['category'] == 'resident' else
        row.get('cold_confirmed') is True if row['category'] == 'cold' else
        row.get('restore_proof', {}).get('confirmed') is True if row['category'] == 'cpu-restored' else False
        for row in case['rows'])
    case['provenance_pass'] = provenance
    case['resident_repeatability_pass'] = case['comparisons']['resident_repeatability']['pass']
    case['cold_repeatability_pass'] = case['comparisons']['cold_repeatability']['pass']
    case['cpu_restore_pass'] = (provenance and case['resident_repeatability_pass']
                                and case['comparisons'].get('cpu-restored_repeatability', {}).get('pass', False)
                                and case['comparisons'].get('resident_vs_cpu', {}).get('pass', False)) if args.mode == 'cpu' else None
    case['status'] = 'completed'
    helper.save(args.output, report)
    print(json.dumps({key: case[key] for key in ('target', 'provenance_pass', 'resident_repeatability_pass',
                                                 'cold_repeatability_pass', 'cpu_restore_pass')}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helper', type=Path, required=True)
    parser.add_argument('--mode', choices=('gpu', 'cpu'), required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:1234')
    parser.add_argument('--model', default='RadixArk/Qwen3.8-Flash-Next-NVFP4')
    parser.add_argument('--identity', type=Path, required=True)
    parser.add_argument('--current-identity', type=Path, default=Path('/opt/arc3/astra-probe/serving-current.json'))
    parser.add_argument('--server-log', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--alignment', type=int, required=True)
    parser.add_argument('--lengths', type=int, nargs='+', default=[4096])
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--producer-tokens', type=int, choices=(9, 32), default=32)
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--telemetry-wait', type=float, default=20)
    parser.add_argument('--tolerance', type=float, default=1e-4)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    parsed = urllib.parse.urlparse(args.base_url)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.username or parsed.password or parsed.query or parsed.fragment:
        parser.error('Only a credential-free isolated loopback HTTP server is allowed')
    if args.output.exists():
        parser.error('Preserve existing output; choose a new path')
    if not 2 <= args.repeats <= 5 or not 1 <= args.timeout <= 600 or not 1 <= args.telemetry_wait <= 60:
        parser.error('Probe repetition/time bounds invalid')
    if not args.lengths or any(n not in (4096, 65536, 131072) for n in args.lengths) or len(set(args.lengths)) != len(args.lengths):
        parser.error('Use distinct supported context lengths')
    if args.alignment not in (800, 1600) or args.tolerance != 1e-4:
        parser.error('Only reviewed alignment and original unchanged tolerance are supported')
    if not args.run:
        print(json.dumps({'status': 'plan', 'mode': args.mode, 'lengths': args.lengths, 'repeats': args.repeats}))
        return
    identity = attest(args)
    helper = load_helpers(args.helper)
    if args.mode == 'cpu':
        log, _, _ = helper.read_log(args.server_log)
        assert helper.parse_configuration(log)['alignment'] == args.alignment
    report = {'schema_version': 1, 'mode': args.mode, 'identity': identity, 'status': 'running',
              'started_utc': datetime.now(timezone.utc).isoformat(), 'cases': [],
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'helper_sha256': hashlib.sha256(args.helper.read_bytes()).hexdigest(),
              'tolerance': args.tolerance, 'scope': 'serial fixed-next-token text diagnostic',
              'limitations': ['This probe does not establish multi-turn or multimodal correctness.',
                              'Request UTC intervals bracket HTTP calls; log byte offsets observe a buffered follower and may lag trace emission.',
                              'Selected logprobs are compared only for the same token and same conditioning.',
                              'Cold-versus-resident differences remain separate from restoration parity.',
                              'Latency includes diagnostic overhead and is not a serving benchmark.']}
    helper.save(args.output, report)
    try:
        for target in args.lengths:
            execute_case(helper, args, report, target)
        report['status'] = 'completed'
        report['diagnostic_gates_pass'] = all(
            case['provenance_pass'] and case['resident_repeatability_pass'] and case['cold_repeatability_pass']
            and (args.mode == 'gpu' or case['cpu_restore_pass']) for case in report['cases'])
    except Exception as error:
        report['status'] = 'stopped-after-error'
        report['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        helper.save(args.output, report)
    if not report.get('diagnostic_gates_pass'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()

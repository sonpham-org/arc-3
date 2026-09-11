"""Test an already running isolated QSA CPU-offload server. Defaults to plan only.

Uses the pinned native GPU-prefix reset endpoint, never starts or configures a
server. Exact completion token IDs preserve generated-prefix identity. This is
a text-only restoration check; it does not establish multimodal or ARC quality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def http(base, path, payload=None, timeout=60):
    request = urllib.request.Request(
        base.rstrip('/') + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(4_000_001)
    if len(data) > 4_000_000:
        raise ValueError('HTTP response exceeded 4 MB')
    return data.decode('utf-8') if path == '/metrics' else json.loads(data)


def parse_metrics(raw):
    names = ('vllm:external_prefix_cache_hits_total',
             'vllm:prefix_cache_hits_total', 'vllm:num_requests_running',
             'vllm:num_requests_waiting', 'vllm:num_preemptions_total')
    result = {}
    for line in raw.splitlines():
        if not line or line.startswith('#'):
            continue
        name = line.split('{', 1)[0].split(' ', 1)[0]
        if name not in names:
            continue
        value = float(line.split()[-1])
        if not math.isfinite(value) or value < 0:
            raise ValueError('Non-finite or negative metric')
        result[name] = result.get(name, 0.0) + value
    return result


def metric_delta(before, after, name):
    if name not in before or name not in after or after[name] < before[name]:
        return None
    return after[name] - before[name]


def metrics(base):
    return parse_metrics(http(base, '/metrics', timeout=10))


def wait_idle(base, seconds=20):
    deadline = time.monotonic() + seconds
    while True:
        current = metrics(base)
        running = current.get('vllm:num_requests_running')
        waiting = current.get('vllm:num_requests_waiting')
        if running == 0 and waiting == 0:
            return current
        if time.monotonic() >= deadline:
            raise RuntimeError('Could not confirm isolated server idle from metrics')
        time.sleep(.5)


def reset_gpu(base, external=False, seconds=20):
    wait_idle(base, seconds)
    path = '/reset_prefix_cache?reset_running_requests=false&reset_external=' + str(external).lower()
    attempts = []
    deadline = time.monotonic() + seconds
    while True:
        result = http(base, path, {}, timeout=10)
        attempts.append(result)
        if result.get('success') is True:
            return {'endpoint': path, 'success': True, 'attempts': attempts}
        if result.get('success') is not False:
            raise RuntimeError('Reset endpoint did not return an explicit boolean success')
        if time.monotonic() >= deadline:
            raise RuntimeError('Prefix reset remained busy; do not infer cache eviction')
        time.sleep(.5)


def read_log(path, offset=0):
    size = path.stat().st_size
    if size < offset:
        raise RuntimeError('Server log rotated during probe')
    with path.open('rb') as handle:
        handle.seek(max(offset, size - 2_000_000))
        raw = handle.read(2_000_001)
    return raw.decode('utf-8', errors='replace'), size, size - offset > 2_000_000


def parse_configuration(log):
    matches = re.findall(r'QSA_CPU_OFFLOAD configured alignment=(\d+) ratio=(\d+) families=([^\r\n]+)', log)
    if not matches:
        raise ValueError('Missing QSA connector runtime configuration marker')
    alignment, ratio, families = matches[-1]
    alignment, ratio = int(alignment), int(ratio)
    if ratio != 4 or alignment < 4 or alignment % ratio:
        raise ValueError('Runtime alignment must be a positive multiple of QSA ratio 4')
    return {'alignment': alignment, 'ratio': ratio, 'families': families.strip()}


def restore_events(log, request_id):
    scheduled, completed = [], []
    # Completion serving may wrap the user request ID with cmpl- / -0 suffixes.
    # An independently generated 128-bit ID is matched only as an entire segment.
    identity = re.compile(r'(?:^|[-_])' + re.escape(request_id) + r'(?:$|[-_])')
    for line in log.splitlines():
        match = re.search(r'QSA_CPU_OFFLOAD restore_scheduled request_id=(\S+) local_tokens=(\d+) external_tokens=(\d+) end_tokens=(\d+) families=([^\r\n]+)', line)
        if match and identity.search(match[1]):
            scheduled.append({'request_id': match[1], 'local_tokens': int(match[2]),
                              'external_tokens': int(match[3]), 'end_tokens': int(match[4]),
                              'families': match[5].strip()})
        match = re.search(r'QSA_CPU_OFFLOAD restore_completed request_id=(\S+)', line)
        if match and identity.search(match[1]):
            completed.append(match[1])
    return {'scheduled': scheduled, 'completed': completed}


def verify_restore(events, before, after, *, base_prompt_length, prompt_length, alignment, allow_concurrent_local_hits=False):
    external = metric_delta(before, after, 'vllm:external_prefix_cache_hits_total')
    local = metric_delta(before, after, 'vllm:prefix_cache_hits_total')
    valid = []
    for event in events['scheduled']:
        valid.append(
            event['request_id'] in events['completed']
            and event['local_tokens'] == 0
            and event['external_tokens'] == event['end_tokens']
            and base_prompt_length < event['end_tokens'] < prompt_length
            and event['end_tokens'] % alignment == 0
        )
    return {'external_hit_tokens_delta': external, 'local_hit_tokens_delta': local,
            'completed_aligned_decode_restore': any(valid),
            'allow_concurrent_local_hits': allow_concurrent_local_hits,
            'confirmed': external is not None and external > base_prompt_length
            and (local is not None and local >= 0 if allow_concurrent_local_hits else local == 0)
            and any(valid)}


def tokenize(base, model, text, timeout):
    result = http(base, '/tokenize', {'model': model, 'prompt': text, 'add_special_tokens': False}, timeout)
    values = result.get('tokens')
    if not isinstance(values, list) or not values or any(type(v) is not int or v < 0 for v in values):
        raise ValueError('Tokenizer did not return valid token IDs')
    return values


def exact_prompt(head, filler, tail, length):
    remaining = length - len(head) - len(tail)
    if remaining < 0 or not filler:
        raise ValueError('Prompt length too small')
    return head + (filler * ((remaining + len(filler) - 1) // len(filler)))[:remaining] + tail


def completion(base, model, prompt, count, salt, label, timeout):
    request_id = uuid.uuid4().hex
    payload = {'model': model, 'prompt': prompt, 'max_tokens': count, 'min_tokens': count,
               'temperature': 0, 'seed': 0, 'ignore_eos': True, 'stream': False,
               'return_token_ids': True, 'return_tokens_as_token_ids': True,
               'logprobs': 1, 'request_id': request_id, 'cache_salt': salt}
    start = time.perf_counter()
    reply = http(base, '/v1/completions', payload, timeout)
    choice = reply['choices'][0]
    tokens = choice.get('token_ids')
    if not isinstance(tokens, list) or len(tokens) != count or any(type(v) is not int for v in tokens):
        raise ValueError('Completion failed exact generated-token-count validation')
    if choice.get('prompt_token_ids') != prompt:
        raise ValueError('Server did not echo the exact supplied prompt IDs')
    if reply.get('usage', {}).get('prompt_tokens') != len(prompt):
        raise ValueError('Server prompt usage does not match exact token-ID input')
    logprobs = (choice.get('logprobs') or {}).get('token_logprobs')
    if not isinstance(logprobs, list) or len(logprobs) != count or any(
        not isinstance(v, (int, float)) or not math.isfinite(v) for v in logprobs
    ):
        raise ValueError('Missing finite per-token output logprobs')
    return {'label': label, 'request_id': request_id, 'prompt_sha256': sha(prompt),
            'request_sha256': sha(payload), 'prompt_tokens': len(prompt),
            'elapsed_seconds': time.perf_counter() - start, 'text': choice.get('text'),
            'token_ids': tokens, 'token_logprobs': logprobs, 'usage': reply.get('usage'),
            'finish_reason': choice.get('finish_reason')}


def compare(left, right, tolerance):
    ids_equal = left['token_ids'] == right['token_ids']
    values = [abs(a - b) for a, b in zip(left['token_logprobs'], right['token_logprobs'])]
    error = max(values) if values else None
    return {'exact_token_ids_equal': ids_equal, 'max_logprob_absolute_error': error,
            'logprob_tolerance': tolerance, 'pass': ids_equal and error is not None and error <= tolerance}


def cached(row):
    return (row.get('usage') or {}).get('prompt_tokens_details', {}).get('cached_tokens')


def collect_restore_proof(args, request_id, before, base_length, prompt_length, alignment, offset, allow_concurrent_local_hits=False):
    deadline = time.monotonic() + args.telemetry_wait
    while True:
        after = metrics(args.base_url)
        log, _, truncated = read_log(args.server_log, offset)
        events = restore_events(log, request_id)
        proof = verify_restore(events, before, after, base_prompt_length=base_length,
                               prompt_length=prompt_length, alignment=alignment,
                               allow_concurrent_local_hits=allow_concurrent_local_hits)
        if proof['confirmed'] or time.monotonic() >= deadline:
            return {'metrics_before': before, 'metrics_after': after, 'events': events,
                    'log_window_truncated': truncated, **proof}
        time.sleep(.5)


def execute_case(args, report, target, configuration):
    alignment = configuration['alignment']
    # Nine generated tokens give eight confirmed decode positions. The next
    # request has exactly boundary+1 input tokens: both GPU and CPU lookup must
    # stop at boundary because the final input token is always recomputed. This
    # prevents fine-grained GPU hits from giving the resident arm a longer prefix.
    boundary = ((target - 128) // alignment) * alignment
    base_length = boundary - 8
    if boundary < 512 or base_length + 9 + 32 > target:
        raise ValueError('Unsupported scheduler alignment for requested context')
    case = {'target_context': target, 'alignment': alignment,
            'base_prompt_tokens': base_length, 'first_decode_boundary': boundary,
            'phases': [], 'resets': [], 'status': 'running'}
    report['cases'].append(case)
    salt = 'isolated-qsa-restore-' + uuid.uuid4().hex
    head = tokenize(args.base_url, args.model, f'Isolated numeric cache validation at {target}.\n', args.timeout)
    filler = tokenize(args.base_url, args.model, ' record blue square green circle red triangle.\n', args.timeout)
    tail = tokenize(args.base_url, args.model, '\nContinue a numbered list of short color and shape records:\n1.', args.timeout)
    prompt = exact_prompt(head, filler, tail, base_length)
    case['resets'].append(reset_gpu(args.base_url, external=True))
    producer = completion(args.base_url, args.model, prompt, 9, salt, 'producer', args.timeout)
    case['phases'].append(producer)
    continuation = prompt + producer['token_ids']
    resident = completion(args.base_url, args.model, continuation, 32, salt, 'resident', args.timeout)
    case['phases'].append(resident)
    case['resident_cached_tokens'] = cached(resident)
    case['resident_prefix_confirmed'] = isinstance(cached(resident), int) and cached(resident) >= boundary
    save(args.output, report)

    # Reset hashes only: CPU backing pages and confirmed generated prefixes stay.
    case['resets'].append(reset_gpu(args.base_url, external=False))
    before = metrics(args.base_url)
    _, offset, _ = read_log(args.server_log)
    restored = completion(args.base_url, args.model, continuation, 32, salt, 'cpu-restored', args.timeout)
    case['phases'].append(restored)
    proof = collect_restore_proof(args, restored['request_id'], before, base_length,
                                  len(continuation), alignment, offset)
    case['restore_proof'] = proof
    case['resident_vs_restored'] = compare(resident, restored, args.logprob_tolerance)
    save(args.output, report)

    # Clear both stores for an independent fresh computation of the identical
    # token prefix. This diagnoses prefill-vs-decode differences separately from
    # CPU-copy parity; cold recomputation is not the sole restoration baseline.
    case['resets'].append(reset_gpu(args.base_url, external=True))
    cold = completion(args.base_url, args.model, continuation, 32, salt, 'cold-recompute', args.timeout)
    case['phases'].append(cold)
    case['cold_cached_tokens'] = cached(cold)
    case['cold_vs_restored'] = compare(cold, restored, args.logprob_tolerance)
    case['cold_vs_resident'] = compare(cold, resident, args.logprob_tolerance)
    case['status'] = 'completed'
    case['pass'] = (case['resident_prefix_confirmed'] and proof['confirmed']
                    and case['resident_vs_restored']['pass']
                    and case['cold_vs_restored']['pass'] and cached(cold) == 0)
    if getattr(args, 'overlap', False) and case['pass']:
        from overlap_probe import run_overlap
        case['overlap'] = run_overlap(args, continuation, salt, base_length, alignment)
    save(args.output, report)
    print(json.dumps({'target_context': target, 'pass': case['pass'],
                      'cpu_restore_confirmed': proof['confirmed'],
                      'parity': case['resident_vs_restored']}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:1234')
    parser.add_argument('--model', default='RadixArk/Qwen3.8-Flash-Next-NVFP4')
    parser.add_argument('--lengths', type=int, nargs='+', default=[65536, 131072])
    parser.add_argument('--identity', type=Path)
    parser.add_argument('--server-log', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=600)
    parser.add_argument('--telemetry-wait', type=float, default=20)
    parser.add_argument('--logprob-tolerance', type=float, default=1e-4)
    parser.add_argument('--overlap', action='store_true', help='Optional paired 256-token active stream during target CPU restoration; defaults off')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--ack-isolated-test-server', action='store_true')
    args = parser.parse_args()
    parsed = urllib.parse.urlparse(args.base_url)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1') or parsed.username or parsed.password or parsed.query or parsed.fragment:
        parser.error('Only a loopback HTTP endpoint without credentials is accepted')
    if not args.model.strip() or len(args.model) > 256:
        parser.error('Model alias must be nonempty and <=256 characters')
    if not args.lengths or len(set(args.lengths)) != len(args.lengths) or any(n not in (4096, 65536, 131072) for n in args.lengths):
        parser.error('Use distinct targets from 4096, 65536, 131072')
    if not 1 <= args.timeout <= 1200 or not 1 <= args.telemetry_wait <= 60 or not 0 <= args.logprob_tolerance <= .1:
        parser.error('Invalid bounded timeout, telemetry wait, or tolerance')
    plan = {'lengths': args.lengths, 'requests_per_length': 4, 'generated_tokens_by_phase': [9, 32, 32, 32],
            'offload_prompt_only': False, 'cpu_backend': 'QSAAlignedCPUOffloadConnector',
            'cache_reset': 'native API, idle requests only; preserve CPU for restore phase',
            'required_server_env': 'VLLM_SERVER_DEV_MODE=1', 'scope': 'text-only',
            'optional_overlap': args.overlap,
            'gpu_allocation_or_server_configuration_changes': False}
    if not args.run:
        print(json.dumps({'status': 'plan-only', **plan}))
        return
    if not args.ack_isolated_test_server or args.identity is None or args.server_log is None:
        parser.error('--run requires --ack-isolated-test-server, --identity, and --server-log')
    if args.output.exists():
        parser.error('Output exists; preserve previous results and choose a new filename')
    identity = json.loads(args.identity.read_text(encoding='utf-8'))
    log, _, truncated = read_log(args.server_log)
    if truncated and 'QSA_CPU_OFFLOAD configured' not in log:
        parser.error('Configuration marker fell outside bounded log tail; provide a dedicated current server log')
    configuration = parse_configuration(log)
    report = {'schema_version': 1, 'plan': plan, 'configuration': configuration,
              'identity_as_supplied': identity, 'identity_sha256': hashlib.sha256(args.identity.read_bytes()).hexdigest(),
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'overlap_script_sha256': hashlib.sha256(Path(__file__).with_name('overlap_probe.py').read_bytes()).hexdigest() if args.overlap else None,
              'started_utc': datetime.now(timezone.utc).isoformat(), 'cases': [], 'status': 'running',
              'limitations': ['Native GPU hash invalidation forces logical GPU prefix eviction; it does not zero physical memory.',
                              'Connector/source identity must be independently attested by the caller.',
                              'Text-only synthetic parity does not establish ARC quality, multimodal MRoPE restore, or multi-stream pressure robustness.',
                              'Logprob differences are reported; greedy tokens must match exactly. No tolerance is adapted after observing a result.']}
    save(args.output, report)
    try:
        for target in args.lengths:
            execute_case(args, report, target, configuration)
        report['status'] = 'completed'
        report['all_text_restore_gates_pass'] = all(case['pass'] for case in report['cases'])
    except Exception as error:
        report['status'] = 'stopped-after-error'
        report['error'] = f'{type(error).__name__}: {error}'
        report['all_text_restore_gates_pass'] = False
    finally:
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save(args.output, report)
    print(json.dumps({'status': report['status'], 'all_text_restore_gates_pass': report['all_text_restore_gates_pass']}))
    if not report['all_text_restore_gates_pass']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

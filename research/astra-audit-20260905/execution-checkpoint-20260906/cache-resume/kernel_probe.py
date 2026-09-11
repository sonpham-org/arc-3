"""Bounded synthetic FlashNext-shape CUTLASS probe; host controller, no model load.

Run on the already-owned, idle Linux GPU host, not inside an existing container:
  python3 kernel_probe.py --output /absolute/new/path [--include-large]
No serving container is stopped or modified. The pinned image must exist locally.
The private worker mode is only entered by this controller in its fresh container.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
import uuid

IMAGE = 'vllm/vllm-openai@sha256:fc120ece0a388cc0aa1caad4a9f1cd92113484ab7ec2fd0efadd62585be05bf8'
GIB = 1024 ** 3
LIMIT = 8 * GIB
IDLE_MIB = 512
E, K, N, TOPK = 512, 2560, 640, 10
MAX_EXPERT_TOKENS = 163840  # Preserve the pinned runtime's default scale allocation.
SOURCES = {
    '_custom_ops.py': '9f11980f43c44857acd88e6f5c96cbd2d767b657b05207e26f064566200dae11',
    'model_executor/layers/fused_moe/experts/cutlass_moe.py': 'e23321bc003cb19311e6c29c3cb90c53c603627f72c97844d5b9bef51bce363e',
    'model_executor/layers/quantization/utils/nvfp4_utils.py': 'ed665537e42580e82ae71bb4f2ce8a699c0ffe8a042947c4eb600107c0b924ba',
    'model_executor/layers/fused_moe/activation.py': '907f35cd47dc6642a52e2f289ec64d8c50925664a277337835c8f18b927d7764',
    'envs.py': 'fb701e932ff263612d520c1447dfdbd882da3286c889c4e01735c8456c3db508',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    temporary = Path(str(path) + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def command(argv, timeout=10):
    result = subprocess.run(argv, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'Command failed: {argv!r}: {result.stderr[-2000:]}')
    return result.stdout.strip()


def gpu_snapshot():
    lines = command(['nvidia-smi', '--query-gpu=uuid,memory.total,memory.used',
                     '--format=csv,noheader,nounits']).splitlines()
    if len(lines) != 1:
        raise RuntimeError('Requires exactly one visible physical GPU')
    fields = [part.strip() for part in lines[0].split(',')]
    if len(fields) != 3 or not re.fullmatch(r'GPU-[a-fA-F0-9-]+', fields[0]):
        raise RuntimeError('Unrecognized GPU inventory')
    return {'uuid': fields[0], 'total_mib': int(fields[1]), 'used_mib': int(fields[2])}


def require_idle(expected_uuid=None):
    snapshot = gpu_snapshot()
    if expected_uuid and snapshot['uuid'] != expected_uuid:
        raise RuntimeError('GPU identity changed')
    processes = command(['nvidia-smi', '--query-compute-apps=pid,used_gpu_memory',
                         '--format=csv,noheader,nounits'])
    if processes or snapshot['used_mib'] > IDLE_MIB:
        raise RuntimeError('GPU has an existing compute process or allocation above 512 MiB')
    if snapshot['total_mib'] - snapshot['used_mib'] < (LIMIT // 1048576) + 512:
        raise RuntimeError('Less than the guarded GPU budget plus slack is available')
    return snapshot


def estimate_bytes(m):
    """Conservative concurrent tensor allowance plus 2 GiB native/context reserve.

    Includes both packed weight sets, three copies of weight scale storage during
    swizzling, both expert-quant scale buffers at their unchanged default sizes,
    original/input/output/workspaces, shuffles and reduction temporaries. CUDA
    native allocation is additionally policed by the host's GPU-memory watchdog.
    """
    if m not in (1, 22, 64, 6144):
        raise ValueError('Unreviewed token count')
    expanded = m * TOPK
    weights = E * ((2 * N * K // 2) + (K * N // 2))
    scales = E * ((2 * N * K // 16) + (K * N // 16))
    quant_scales = MAX_EXPERT_TOKENS * TOPK * ((K // 16) + (N // 16))
    scratch = expanded * (12 * K + 8 * N) + m * K * 6 + expanded * 32
    return weights + 3 * scales + quant_scales + scratch + 2 * GIB


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--include-large', action='store_true')
    p.add_argument('--deadline-seconds', type=int, default=300)
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    return p


def stop_owned(name, nonce):
    info = json.loads(command(['docker', 'inspect', name]))[0]
    if info.get('Config', {}).get('Labels', {}).get('arc3.kernel-probe') != nonce:
        raise RuntimeError('Refusing cleanup: diagnostic-container identity changed')
    command(['docker', 'kill', name])


def controller(a):
    if sys.platform != 'linux' or Path('/.dockerenv').exists():
        raise RuntimeError('Controller must run directly on the isolated Linux GPU host')
    if not a.output.is_absolute() or a.output.exists():
        raise RuntimeError('Output must be an absolute fresh directory')
    if command(['docker', 'ps', '-q']):
        raise RuntimeError('Refusing to run while any Docker container is active')
    initial = require_idle()
    image_info = json.loads(command(['docker', 'image', 'inspect', IMAGE]))[0]
    if IMAGE not in image_info.get('RepoDigests', []):
        raise RuntimeError('Pinned image digest is not present locally')
    peak_estimate = estimate_bytes(6144 if a.include_large else 64)
    if peak_estimate > LIMIT:
        raise RuntimeError('Conservative GPU-memory estimate exceeds 8 GiB')
    a.output.mkdir(parents=True, exist_ok=False)
    nonce = uuid.uuid4().hex
    name = 'arc3-kernel-probe-' + nonce[:16]
    source = Path(__file__).resolve()
    proof = {'schema': 1, 'nonce': nonce, 'created_unix': time.time(),
             'gpu': initial, 'image': IMAGE, 'image_id': image_info['Id'],
             'script_sha256': sha(source), 'deadline_seconds': a.deadline_seconds,
             'include_large': a.include_large, 'estimate_bytes': peak_estimate,
             'limit_bytes': LIMIT, 'no_running_containers': True}
    write_json(a.output / 'host-proof.json', proof)
    argv = ['docker', 'run', '--rm', '--pull', 'never', '--name', name,
            '--label', 'arc3.kernel-probe=' + nonce, '--network', 'none',
            '--gpus', 'device=' + initial['uuid'], '--memory', '16g',
            '--cpus', '8', '--pids-limit', '256', '--ipc', 'private',
            '--shm-size', '1g', '-e', 'CUDA_LAUNCH_BLOCKING=1',
            '-e', 'VLLM_MAX_TOKENS_PER_EXPERT_FP4_MOE=' + str(MAX_EXPERT_TOKENS),
            '-e', 'ARC3_KERNEL_PROBE_NONCE=' + nonce,
            '-e', 'PYTHONUNBUFFERED=1',
            '-v', str(source) + ':/probe/kernel_probe.py:ro',
            '-v', str(a.output) + ':/out', '--entrypoint', 'python3',
            IMAGE, '/probe/kernel_probe.py', '--worker', '--output', '/out',
            '--deadline-seconds', str(a.deadline_seconds)]
    if a.include_large:
        argv.append('--include-large')
    write_json(a.output / 'controller.json', {'status': 'prepared', 'argv': argv,
                                             'proof_sha256': sha(a.output / 'host-proof.json')})
    # Recheck immediately before the only container start. No allocation retry.
    if command(['docker', 'ps', '-q']):
        raise RuntimeError('A container became active during preparation')
    require_idle(initial['uuid'])
    started, maximum = time.monotonic(), initial['used_mib']
    with (a.output / 'worker.log').open('x') as log:
        process = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT)
        try:
            while process.poll() is None:
                if time.monotonic() - started > a.deadline_seconds:
                    raise TimeoutError('Hard host deadline exceeded')
                active = command(['docker', 'ps', '--format', '{{.Names}}']).splitlines()
                if any(other != name for other in active):
                    raise RuntimeError('Another container became active; aborting only this probe')
                snapshot = gpu_snapshot()
                maximum = max(maximum, snapshot['used_mib'])
                if snapshot['uuid'] != initial['uuid']:
                    raise RuntimeError('GPU identity changed during probe')
                if snapshot['used_mib'] - initial['used_mib'] > LIMIT // 1048576:
                    raise RuntimeError('Host watchdog observed more than 8 GiB additional GPU memory')
                time.sleep(0.5)
            result = {'status': 'finished', 'returncode': process.returncode,
                      'elapsed_seconds': time.monotonic() - started,
                      'peak_observed_gpu_mib': maximum, 'argv': argv}
        except BaseException as error:
            result = {'status': 'controller_aborted', 'error': repr(error), 'argv': argv,
                      'peak_observed_gpu_mib': maximum}
            try:
                stop_owned(name, nonce)
                process.wait(timeout=10)
                result['cleanup'] = 'owned diagnostic container killed'
            except Exception as cleanup_error:
                result['cleanup'] = 'uncertain: ' + repr(cleanup_error)
            write_json(a.output / 'controller.json', result)
            raise
    write_json(a.output / 'controller.json', result)
    return process.returncode


def worker(a):
    # Deliberately precede all Torch/vLLM imports and CUDA context creation.
    os.environ['CUDA_LAUNCH_BLOCKING'] = '1'
    if 'torch' in sys.modules or not Path('/.dockerenv').exists() or a.output != Path('/out'):
        raise RuntimeError('Private worker requires the fresh diagnostic container')
    proof = json.loads((a.output / 'host-proof.json').read_text())
    if (proof.get('nonce') != os.environ.get('ARC3_KERNEL_PROBE_NONCE')
            or not re.fullmatch('[0-9a-f]{32}', proof.get('nonce', ''))
            or proof.get('script_sha256') != sha(__file__)
            or proof.get('image') != IMAGE or not proof.get('no_running_containers')
            or proof.get('deadline_seconds') != a.deadline_seconds
            or proof.get('include_large') != a.include_large
            or not 0 <= time.time() - proof['created_unix'] <= 60):
        raise RuntimeError('Missing, stale or mismatched host quiescence proof')
    require_idle(proof['gpu']['uuid'])
    spec = importlib.util.find_spec('vllm')
    if spec is None or spec.origin is None:
        raise RuntimeError('Pinned vLLM package not installed')
    package = Path(spec.origin).parent
    actual_sources = {relative: sha(package / relative) for relative in SOURCES}
    if actual_sources != SOURCES:
        raise RuntimeError('Pinned Python source identity mismatch: ' + repr(actual_sources))
    if os.environ.get('VLLM_MAX_TOKENS_PER_EXPERT_FP4_MOE') != str(MAX_EXPERT_TOKENS):
        raise RuntimeError('Expert scale allocation differs from pinned control')
    import torch
    from vllm import _custom_ops as ops
    from vllm.model_executor.layers.fused_moe.experts.cutlass_moe import run_cutlass_moe_fp4
    from vllm.model_executor.layers.fused_moe.activation import MoEActivation
    from vllm.model_executor.layers.quantization.utils.nvfp4_utils import swizzle_blockscale
    if torch.cuda.device_count() != 1 or torch.cuda.get_device_capability() != (12, 0):
        raise RuntimeError('Only the isolated SM120 GPU is supported')
    torch.cuda.set_per_process_memory_fraction(LIMIT / torch.cuda.get_device_properties(0).total_memory)
    started = time.monotonic()
    events = (a.output / 'stages.jsonl').open('x', buffering=1)
    summary = {'schema': 1, 'status': 'running', 'synthetic': True,
               'dims': {'experts': E, 'hidden': K, 'intermediate': N, 'topk': TOPK},
               'sources': actual_sources, 'torch': torch.__version__,
               'cuda': torch.version.cuda, 'image': IMAGE, 'cases': [],
               'scope': 'kernel smoke and repeated synthetic output; not model accuracy or resume parity'}
    current = {'case': 'setup', 'stage': 'imports'}

    def emit(kind, **details):
        events.write(json.dumps({'event': kind, **current, **details,
                                'elapsed_seconds': time.monotonic() - started}) + '\n')
        events.flush()

    def bound():
        if time.monotonic() - started > a.deadline_seconds - 10:
            raise TimeoutError('Worker deadline reached')
        if torch.cuda.memory_reserved() > LIMIT:
            raise RuntimeError('Torch reserved allocation exceeds 8 GiB')

    def describe(tensor, finite=False):
        cpu = tensor.detach().cpu().contiguous()
        raw = cpu.view(torch.uint8).numpy().tobytes()
        result = {'shape': list(tensor.shape), 'dtype': str(tensor.dtype),
                  'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
        if finite:
            values = cpu.float()
            result.update(finite=bool(torch.isfinite(values).all()),
                          nonzero=int(torch.count_nonzero(values)),
                          min=float(values.min()), max=float(values.max()))
            if not result['finite']:
                raise RuntimeError('Nonfinite logical output at ' + current['stage'])
        return result

    originals = {}
    counters = {}

    def instrument(name):
        original = getattr(ops, name)
        originals[name] = original

        def wrapped(*args, **kwargs):
            counters[name] = counters.get(name, 0) + 1
            current['stage'] = f'{name}:{counters[name]}'
            bound()
            emit('begin')
            torch.cuda.synchronize()
            result = original(*args, **kwargs)
            torch.cuda.synchronize()
            details = {}
            if name == 'get_cutlass_moe_mm_data':
                # Validate native maps before a bad index can reach the shuffle.
                offsets, amap, cmap = args[1].cpu(), args[4].cpu(), args[5].cpu()
                rows = args[0].numel()
                if (int(offsets[0]) != 0 or int(offsets[-1]) != rows
                        or bool((offsets[1:] < offsets[:-1]).any())
                        or int(amap.min()) < 0 or int(amap.max()) >= args[0].shape[0]
                        or int(cmap.min()) < 0 or int(cmap.max()) >= rows):
                    raise RuntimeError('Native routing map is out of bounds')
                details['maps'] = [describe(args[i]) for i in (1, 2, 3, 4, 5, 9)]
            elif name == 'shuffle_rows':
                details['output'] = describe(result, finite=True)
            elif name in ('scaled_fp4_experts_quant', 'silu_and_mul_scaled_fp4_experts_quant'):
                details['packed'] = describe(result[0])
                details['scale_shape'] = list(result[1].shape)
                # Padding is uninitialized by this native API. Do not hash or
                # compare its full capacity as though it were semantic state.
                details['scale_note'] = 'uninitialized padded capacity excluded from hashes'
            elif name == 'cutlass_fp4_moe_mm':
                details['output'] = describe(args[0], finite=True)
            emit('end', allocated_bytes=torch.cuda.memory_allocated(), **details)
            bound()
            return result

        setattr(ops, name, wrapped)

    try:
        torch.manual_seed(20260906)
        for name in ('get_cutlass_moe_mm_data', 'shuffle_rows', 'scaled_fp4_experts_quant',
                     'silu_and_mul_scaled_fp4_experts_quant', 'cutlass_fp4_moe_mm'):
            instrument(name)
        device = torch.device('cuda:0')
        # Every E2M1 nibble is finite. Uniform, exactly representable FP8 scales
        # are explicitly swizzled with the same pinned conversion as loading.
        current['stage'] = 'synthetic_weights'
        emit('begin', estimate_bytes=estimate_bytes(6144 if a.include_large else 64))
        w1 = torch.randint(0, 256, (E, 2 * N, K // 2), dtype=torch.uint8, device=device)
        w2 = torch.randint(0, 256, (E, K, N // 2), dtype=torch.uint8, device=device)
        s1 = swizzle_blockscale(torch.full((E, 2 * N, K // 16), 1 / 64,
                                          dtype=torch.float8_e4m3fn, device=device))
        s2 = swizzle_blockscale(torch.full((E, K, N // 16), 1 / 64,
                                          dtype=torch.float8_e4m3fn, device=device))
        ones = torch.ones(E, dtype=torch.float32, device=device)
        torch.cuda.synchronize()
        emit('end', allocated_bytes=torch.cuda.memory_allocated())
        sizes = [1, 22, 64] + ([6144] if a.include_large else [])
        for m in sizes:
            if estimate_bytes(m) > LIMIT:
                raise RuntimeError('Case exceeds conservative GPU budget')
            # Reaching 6144 implies every small case and repeat already passed.
            for routing in ('concentrated', 'distributed'):
                current['case'] = f'm{m}-{routing}'
                input_cpu = (torch.arange(m * K, dtype=torch.float32).reshape(m, K) % 127 - 63) / 256
                a_input = input_cpu.to(device=device, dtype=torch.bfloat16)
                row = torch.arange(m, dtype=torch.int64).reshape(m, 1)
                expert = torch.arange(TOPK, dtype=torch.int64).reshape(1, TOPK)
                ids_cpu = (expert.expand(m, TOPK) if routing == 'concentrated'
                           else (row * TOPK + expert) % E).contiguous()
                ids = ids_cpu.to(device=device, dtype=torch.int32)
                probabilities = torch.full((m, TOPK), 1 / TOPK, device=device, dtype=torch.float32)
                workspace13 = torch.empty((m * TOPK, max(2 * N, K)), device=device, dtype=torch.bfloat16)
                workspace2 = torch.empty((m * TOPK, N), device=device, dtype=torch.bfloat16)
                output = torch.empty((m, K), device=device, dtype=torch.bfloat16)
                case = {'name': current['case'], 'tokens': m, 'routing': routing,
                        'estimate_bytes': estimate_bytes(m), 'repeats': []}
                for repeat in range(3):
                    counters.clear()
                    current['repeat'] = repeat
                    # Different sentinels expose unwritten logical output.
                    sentinel = (float('nan'), -12345.0, 12345.0)[repeat]
                    workspace13.fill_(sentinel)
                    workspace2.fill_(sentinel)
                    output.fill_(sentinel)
                    run_cutlass_moe_fp4(
                        output, a_input, ones, w1, s1, ones, ones, w2, s2, ones,
                        probabilities, ids, MoEActivation.SILU, workspace13, workspace2,
                        m, N, K, E, device, apply_router_weight_on_input=False)
                    torch.cuda.synchronize()
                    current['stage'] = 'final_output'
                    observed = describe(output, finite=True)
                    if observed['nonzero'] == 0:
                        raise RuntimeError('Degenerate all-zero synthetic output')
                    case['repeats'].append(observed)
                    emit('output', **observed)
                    if observed['sha256'] != case['repeats'][0]['sha256']:
                        raise RuntimeError('Repeated identical synthetic input changed output bytes')
                    bound()
                case['passed'] = True
                summary['cases'].append(case)
                write_json(a.output / 'result.json', summary)
                del a_input, ids, probabilities, workspace13, workspace2, output
        summary['status'] = 'passed'
        summary['peak_torch_allocated_bytes'] = torch.cuda.max_memory_allocated()
        summary['peak_torch_reserved_bytes'] = torch.cuda.max_memory_reserved()
        returncode = 0
    except BaseException as error:
        summary.update(status='failed', error=repr(error), location=dict(current),
                       traceback=traceback.format_exc())
        emit('error', error=repr(error))
        returncode = 1
    finally:
        for name, original in originals.items():
            setattr(ops, name, original)
        summary['elapsed_seconds'] = time.monotonic() - started
        write_json(a.output / 'result.json', summary)
        events.close()
    return returncode


def main():
    args = parser().parse_args()
    if not 60 <= args.deadline_seconds <= 600:
        raise ValueError('Deadline must be 60–600 seconds')
    return worker(args) if args.worker else controller(args)


if __name__ == '__main__':
    raise SystemExit(main())

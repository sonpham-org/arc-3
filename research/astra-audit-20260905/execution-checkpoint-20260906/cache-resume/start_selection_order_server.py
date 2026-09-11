"""Start isolated QSA selection-order control; never alters an existing server."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

IMAGE = 'vllm/vllm-openai@sha256:fc120ece0a388cc0aa1caad4a9f1cd92113484ab7ec2fd0efadd62585be05bf8'
PROBE = Path('/opt/arc3/astra-probe')
SITE = '/usr/local/lib/python3.12/dist-packages/'
MODEL = '/opt/arc3/flashnext-model'
SERVED = 'RadixArk/Qwen3.8-Flash-Next-NVFP4'
PLE = 'vllm/models/qwen3_8_flash_next/nvidia/ple_layer.py'
PLE_SHA = '2f0e6febb8c6fdeeeb5b85cc2d7098ba7ce7ee2464d690c33fdcf75e3215c33a'
SCHEDULER = 'vllm/v1/core/sched/scheduler.py'
SCHEDULER_SHA = 'fd2d9a32b1d06192a18d101403c0d4c6c138dd62385d398c04322e9c26fd54c4'
SCHEDULER_BASE_SHA = 'c710f49e41e974e5b7b8f1cd2f5fb9722523f4da0165252e16351199ebd03124'
QSA_PATHS = {'vllm/models/qwen3_8_flash_next/nvidia/qsa.py',
             'vllm/models/qwen3_8_flash_next/nvidia/ops/qsa.py'}
CPU_PATHS = QSA_PATHS | {
    'vllm/models/qwen3_8_flash_next/common/qsa_cpu_offload.py',
    'vllm/distributed/kv_transfer/kv_connector/v1/qsa_cpu_offload_connector.py',
    'vllm/v1/core/kv_cache_utils.py'}
AUDIT_PATH = 'vllm/models/qwen3_8_flash_next/common/qsa_resume_audit.py'
TRACE_MODEL_PATH = 'vllm/models/qwen3_8_flash_next/nvidia/model.py'
TRACE_MODEL_BASE_SHA = 'd900cd6fcacba18f460e00b3f018fbf36fbe6ecc310692b6adb1451f7f53cc17'
TRACE_MODEL_SHA = '45bdab7af95ec31b3d74bdf45082ba8891e4979cc14306bc5133e252a07a42a0'
TRACE_HELPER_PATH = 'vllm/models/qwen3_8_flash_next/common/qsa_layer_trace.py'
TRACE_HELPER_SHA = '00eb0d70c29d0765bba7aeac8697facb422eb3f3bcf6d9696e435ef9cb9ad54e'
TRACE_MANIFEST_SHA = '9581fb0105abaf3c1850cb6ec0c668199098dbb2004e45cbe8e2e2fc3300de34'
TRACE_PARENT_SHA = '966b7a9d01f5994d0580468104f3147fa9fd3acdc4af8a20e5a7e42890afd56f'
TRACE_RELATIVE = 'qsa-resume-correctness-r1/selection-order-candidate-r1'
ORDER_OPS_PATH = 'vllm/models/qwen3_8_flash_next/nvidia/ops/qsa.py'
ORDER_OPS_BASE_SHA = 'c4ffe3674cafa0ce2dabc39a39f0ddbb4b594bc358ad210ffce9d04383350c7f'
ORDER_OPS_PARENT_SHA = '877ff779fd127c750c7d773e07181e90841756119e4e27e3c27358448d08eb18'
ORDER_OPS_SHA = '1bb70e3410908e334de9df490f876473ad6b83ca5c3af9c25632b685d69d924d'
TRACE_ENV = {'VLLM_QSA_LAYER_TRACE': '1', 'VLLM_QSA_LAYER_TRACE_SUBMODULES': '1',
             'VLLM_QSA_LAYER_TRACE_MAX_FORWARDS': '128'}
ARMS = ('qsa-cpu-fp8-bytecheck',)


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read_json(path): return json.loads(Path(path).read_bytes())


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--arm', required=True, choices=ARMS)
    p.add_argument('--context', type=int, choices=[131072], default=131072)
    p.add_argument('--sequences', type=int, choices=[22], default=22)
    p.add_argument('--attempt', required=True)
    p.add_argument('--numeric-report', default='gpu-numeric-r3.json')
    p.add_argument('--cpu-cache-gib', type=int, choices=[16], default=16)
    p.add_argument('--dev-cache-reset', action='store_true')
    p.add_argument('--scheduler-alignment-fix', action='store_true')
    p.add_argument('--synchronous-eager', action='store_true')
    p.add_argument('--moe-backend', choices=['auto'], default='auto')
    p.add_argument('--batch-invariant', action='store_true')
    p.add_argument('--resume-diagnostics', type=Path)
    p.add_argument('--resume-manifest-sha256')
    p.add_argument('--layer-trace', action='store_true')
    return p


def validate_args(a):
    if a.arm not in ARMS or a.context != 131072 or a.sequences != 22:
        raise ValueError('Only owned FlashNext 131072/22 diagnostic profiles are supported')
    if not re.fullmatch('[A-Za-z0-9]{1,48}', a.attempt): raise ValueError('Invalid fresh attempt label')
    if a.moe_backend != 'auto' or a.batch_invariant or a.cpu_cache_gib != 16:
        raise ValueError('Ordering control preserves auto backend, batch invariance off and 16GiB CPU cache')
    if Path(a.numeric_report).name != a.numeric_report or '\\' in a.numeric_report:
        raise ValueError('Numeric report must be a probe-local filename')
    if not a.layer_trace or not a.synchronous_eager:
        raise ValueError('This launcher requires --layer-trace and --synchronous-eager')
    if a.arm != 'qsa-cpu-fp8-bytecheck' or not a.scheduler_alignment_fix:
        raise ValueError('Layer tracing requires the aligned CPU-bytecheck profile')
    expected = (PROBE / TRACE_RELATIVE).resolve()
    if a.resume_diagnostics is None or a.resume_diagnostics.resolve() != expected:
        raise ValueError('Only the frozen selection-order candidate directory is allowed')
    if a.resume_manifest_sha256 != TRACE_MANIFEST_SHA:
        raise ValueError('Explicit frozen selection-order manifest SHA is required')


def verified_sources(a, image_hash):
    """Validate every mounted source; image_hash is supplied by the remote CLI."""
    validate_args(a)
    mounts, patches, evidence = [], {}, {}
    def mount(source, target, expected):
        if not target.startswith('vllm/') or '..' in target.split('/') or target in patches:
            raise ValueError('Unexpected or duplicate runtime mount')
        actual = digest(source)
        if actual != expected: raise RuntimeError('Audited source changed: ' + target)
        mounts.append((str(source), SITE + target))
        patches[target] = actual
    if a.scheduler_alignment_fix:
        root = PROBE / 'scheduler-alignment-r1'
        manifest = read_json(root / 'manifest.json')
        if (manifest['path'], manifest['base_sha256'], manifest['candidate_sha256']) != (
                SCHEDULER, SCHEDULER_BASE_SHA, SCHEDULER_SHA):
            raise RuntimeError('Scheduler alignment manifest changed')
        if image_hash(SCHEDULER) != SCHEDULER_BASE_SHA: raise RuntimeError('Scheduler alignment image base drift')
        mount(root / 'candidate' / SCHEDULER, SCHEDULER, SCHEDULER_SHA)
        evidence['scheduler_alignment_manifest_sha256'] = digest(root / 'manifest.json')
    mount(Path('/opt/arc3/ple_layer_native_fp8.py'), PLE, PLE_SHA)
    fp8_root = PROBE / 'fp8'
    fp8_manifest = read_json(fp8_root / 'patch-manifest.json')
    cpu = a.arm == 'qsa-cpu-fp8-bytecheck'
    if cpu:
        root = a.resume_diagnostics or PROBE / ('qsa-cpu-aligned-bytecheck-r1' if a.scheduler_alignment_fix else 'qsa-cpu-bytecheck-r1')
        manifest_path = root / 'manifest.json'
        if a.resume_diagnostics and digest(manifest_path) != a.resume_manifest_sha256:
            raise RuntimeError('Resume manifest differs from the explicitly reviewed version')
        manifest = read_json(manifest_path)
        if manifest.get('connector') != 'QSAAlignedCPUOffloadConnector': raise RuntimeError('Unexpected CPU connector')
        rows = manifest['files']
        expected_paths = CPU_PATHS | {AUDIT_PATH, TRACE_MODEL_PATH, TRACE_HELPER_PATH}
        if len(rows) != len(expected_paths) or {row['path'] for row in rows} != expected_paths:
            raise RuntimeError('Unexpected CPU diagnostic patch layout')
        if manifest.get('parent_manifest_sha256') != TRACE_PARENT_SHA:
            raise RuntimeError('Selection-order bundle has a different frozen v2 parent')
        model_row = next(row for row in rows if row['path'] == TRACE_MODEL_PATH)
        if model_row.get('exact_sha256') != TRACE_MODEL_BASE_SHA:
            raise RuntimeError('Trace manifest model base changed')
        if model_row.get('candidate_sha256') != TRACE_MODEL_SHA:
            raise RuntimeError('Trace model payload identity changed')
        helper_row = next(row for row in rows if row['path'] == TRACE_HELPER_PATH)
        if helper_row.get('candidate_sha256') != TRACE_HELPER_SHA:
            raise RuntimeError('Trace helper payload identity changed')
        if image_hash(TRACE_MODEL_PATH) != TRACE_MODEL_BASE_SHA:
            raise RuntimeError('Trace model image base drift')
        ops_row = next(row for row in rows if row['path'] == ORDER_OPS_PATH)
        if (ops_row.get('exact_sha256'), ops_row.get('ordering_parent_sha256'), ops_row.get('candidate_sha256')) != (
                ORDER_OPS_BASE_SHA, ORDER_OPS_PARENT_SHA, ORDER_OPS_SHA):
            raise RuntimeError('Selection-order ops base, parent or payload identity changed')
        if image_hash(ORDER_OPS_PATH) != ORDER_OPS_BASE_SHA:
            raise RuntimeError('Selection-order ops image base drift')
        for row in rows: mount(root / 'candidate' / row['path'], row['path'], row['candidate_sha256'])
        evidence['qsa_cpu_manifest_sha256'] = digest(manifest_path)
        evidence['bytecheck_diagnostics'] = True
        if a.resume_diagnostics:
            evidence['resume_diagnostics'] = str(root)
            evidence['resume_manifest_sha256'] = digest(manifest_path)
            expected_dependencies = manifest['runtime_dependency_hashes']
            for target, actual in patches.items():
                dependency = target.removeprefix('vllm/')
                if dependency in expected_dependencies and expected_dependencies[dependency] != actual:
                    raise RuntimeError('Resume policy conflicts with composed mount: ' + target)
    else:
        for target in sorted(QSA_PATHS):
            mount(fp8_root / 'corrected-patched' / target, target, fp8_manifest['files'][target]['corrected_sha256'])
    report_path = fp8_root / a.numeric_report
    report = read_json(report_path)
    if report.get('status') != 'completed' or not report.get('all_gates_passed'):
        raise RuntimeError('FP8 numerical gates have not passed')
    if report.get('script_sha256') != 'abc09adedb35e1cb2976f6f71d4c40566cd4c8d2498424e019b91a51dc6512aa' or len(report.get('cases', [])) != 16:
        raise RuntimeError('Numerical report is not the complete frozen R3 probe')
    if report['patch_manifest_sha256'] != digest(fp8_root / 'patch-manifest.json'):
        raise RuntimeError('Numeric report used another patch manifest')
    evidence['gpu_numeric_report_sha256'] = digest(report_path)
    return {'mounts': mounts, 'patches': patches, 'evidence': evidence}


def build_command(a, verified, source_sha256):
    """Pure argv/identity builder: no process, disk, or network operations."""
    validate_args(a)
    out = PROBE / 'serving' / f'selection-order-r1-{a.arm}-{a.context}-{a.sequences}-{a.attempt}'
    cache = PROBE / 'compile-cache' / a.arm
    cmd = ['docker', 'run', '-d', '--name', 'astra-serve', '--hostname', 'arc3-vllm', '--gpus', 'all',
        '--ipc=host', '--network=host', '--ulimit', 'memlock=-1', '--cap-add=SYS_PTRACE',
        '-e', 'TORCH_CUDA_ARCH_LIST=12.0f', '-e', 'PYTORCH_ALLOC_CONF=expandable_segments:True',
        '-e', 'HF_HUB_OFFLINE=1', '-e', 'OMP_NUM_THREADS=1', '-e', 'VLLM_NO_USAGE_STATS=1',
        '-v', MODEL + ':/model:ro', '-v', str(cache) + ':/root/.cache',
        '-e', 'VLLM_PLE_CPU_OFFLOAD=1', '-e', 'VLLM_PLE_OFFLOAD_READY_TIMEOUT=1800']
    identity = {'arm': a.arm, 'context': a.context, 'sequences': a.sequences, 'kv_requested': 'fp8_e4m3',
        'image': IMAGE, 'main_gpu_memory_utilization': .965, 'model_directory': MODEL,
        'served_model_name': SERVED, 'source_script_sha256': source_sha256, 'patches': dict(verified['patches']),
        'diagnostic_scope': 'qsa-resume-correctness-r1; no gameplay', 'moe_backend_requested': a.moe_backend,
        'batch_invariant': a.batch_invariant, 'synchronous_eager_diagnostic': a.synchronous_eager,
        'layer_trace': a.layer_trace, 'layer_trace_environment': dict(TRACE_ENV),
        'trace_schema_version': 2,
        'selection_order_control': 'post-expansion ascending integer sort',
        'selection_order_ops_sha256': ORDER_OPS_SHA,
        'selection_order_parent_manifest_sha256': TRACE_PARENT_SHA,
        'trace_timing_valid': False,
        'resume_diagnostics_enabled': a.resume_diagnostics is not None, **verified['evidence']}
    for source, target in verified['mounts']: cmd += ['-v', source + ':' + target + ':ro']
    if a.arm == 'qsa-cpu-fp8-bytecheck' or a.dev_cache_reset: cmd += ['-e', 'VLLM_SERVER_DEV_MODE=1']
    if a.batch_invariant: cmd += ['-e', 'VLLM_BATCH_INVARIANT=1']
    for key, value in TRACE_ENV.items(): cmd += ['-e', key + '=' + value]
    cmd += [IMAGE, '--model', '/model', '--served-model-name', SERVED, '--host', '127.0.0.1', '--port', '1234',
        '--tensor-parallel-size', '1', '--distributed-executor-backend', 'mp', '--gpu-memory-utilization', '0.965',
        '--max-model-len', '131072', '--max-num-seqs', '22', '--max-num-batched-tokens', '6144',
        '--kv-cache-dtype', 'fp8_e4m3', '--scheduling-policy', 'fcfs', '--watermark', '0.000',
        '--enable-chunked-prefill', '--enable-prefix-caching', '--enable-prompt-tokens-details',
        '--no-enable-flashinfer-autotune', '--enable-auto-tool-choice', '--tool-call-parser', 'qwen3_xml',
        '--generation-config', 'vllm', '--default-chat-template-kwargs', '{"preserve_thinking": true}',
        '--reasoning-parser', 'qwen3', '--cudagraph-capture-sizes', '1', '2', '4', '8', '12', '14', '15',
        '16', '17', '18', '19', '20', '21', '22', '24', '32', '40']
    if a.synchronous_eager: cmd += ['--enforce-eager', '--no-async-scheduling']
    if a.moe_backend != 'auto': cmd += ['--moe-backend', a.moe_backend]
    if a.arm == 'qsa-cpu-fp8-bytecheck':
        transfer = {'kv_connector': 'QSAAlignedCPUOffloadConnector',
            'kv_connector_module_path': 'vllm.distributed.kv_transfer.kv_connector.v1.qsa_cpu_offload_connector',
            'kv_role': 'kv_both', 'kv_connector_extra_config': {
                'cpu_bytes_to_use': a.cpu_cache_gib * 1024**3, 'offload_prompt_only': False}}
        cmd += ['--mamba-cache-mode', 'align', '--kv-transfer-config', json.dumps(transfer, separators=(',', ':'))]
        identity['cpu_cache_gib'] = a.cpu_cache_gib
    identity['command_argv'] = list(cmd)
    return cmd, identity, out, cache


def main():
    a = parser().parse_args()
    validate_args(a)
    if not (PROBE / 'READY').is_file(): raise RuntimeError('Owned probe bootstrap has not completed')
    # Deliberately never stops or replaces a live diagnostic or gameplay server.
    existing = subprocess.run(['docker', 'container', 'inspect', 'astra-serve'], capture_output=True, text=True)
    if existing.returncode == 0: raise RuntimeError('astra-serve exists; reconcile and stop it separately before starting a fresh diagnostic')
    if 'No such' not in existing.stderr: raise RuntimeError('Could not prove diagnostic container name is free')
    subprocess.run(['docker', 'image', 'inspect', IMAGE], check=True, stdout=subprocess.DEVNULL)
    def image_hash(target):
        return subprocess.check_output(['docker', 'run', '--rm', '--entrypoint', 'sha256sum', IMAGE,
                                        SITE + target], text=True).split()[0]
    verified = verified_sources(a, image_hash)
    cmd, identity, out, cache = build_command(a, verified, digest(__file__))
    if out.exists(): raise RuntimeError('Attempt directory already exists; inspect it rather than retrying')
    cache.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True)
    identity.update(started_epoch=time.time(), status='start_requested')
    identity_path = out / 'identity.json'
    identity_path.write_text(json.dumps(identity, indent=2) + '\n')
    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    except Exception as error:
        identity.update(status='start_failed_or_uncertain', error_type=type(error).__name__)
        identity_path.write_text(json.dumps(identity, indent=2) + '\n')
        raise
    identity.update(container_id=result.stdout.strip(), status='container_started')
    identity_path.write_text(json.dumps(identity, indent=2) + '\n')
    with (out / 'vllm.log').open('wb') as log:
        follower = subprocess.Popen(['docker', 'logs', '-f', 'astra-serve'], stdout=log,
                                    stderr=subprocess.STDOUT, start_new_session=True)
    (PROBE / 'serving-current.json').write_text(json.dumps({'directory': str(out),
        'container_id': identity['container_id'], 'follower_pid': follower.pid}) + '\n')
    print(json.dumps({'status': 'container_started', 'directory': str(out), 'container_id': identity['container_id']}))


if __name__ == '__main__': main()

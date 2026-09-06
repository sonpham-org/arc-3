"""Reproducible local-only diagnostic composition from the frozen aligned bundle."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'qsa-cpu-aligned-bytecheck-r1'
CONNECTOR = 'vllm/distributed/kv_transfer/kv_connector/v1/qsa_cpu_offload_connector.py'
POLICY = 'vllm/models/qwen3_8_flash_next/common/qsa_cpu_offload.py'
HELPER = 'vllm/models/qwen3_8_flash_next/common/qsa_resume_audit.py'
PARENT_SHA = 'c9a2781c864e4f51dfcabf805c5b5728adeef2cfd7d023b1f934e7f26372d3e8'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Source anchor mismatch: ' + before)
    return source.replace(before, after)


def main():
    parent_bytes = (SOURCE / 'manifest.json').read_bytes()
    assert sha(parent_bytes) == PARENT_SHA
    manifest = json.loads(parent_bytes)
    original, payload = {}, {}
    for row in manifest['files']:
        raw = (SOURCE / 'candidate' / row['path']).read_bytes()
        assert sha(raw) == row['candidate_sha256'], row['path']
        original[row['path']] = payload[row['path']] = raw
    source = payload[CONNECTOR].decode().replace('\r\n', '\n')
    source = replace_once(source, 'from __future__ import annotations\n',
        'from __future__ import annotations\n\nfrom vllm.models.qwen3_8_flash_next.common.qsa_resume_audit import ResumeAuditMixin\n')
    source = replace_once(source,
        'class QSAAlignedCPUOffloadConnector(SimpleCPUOffloadConnector):',
        'class QSAAlignedCPUOffloadConnector(ResumeAuditMixin, SimpleCPUOffloadConnector):')
    source = replace_once(source, '        self._qsa_byte_count = 0\n',
        '        self._qsa_byte_count = 0\n        self._audit_init(kv_cache_config)\n')
    anchor = '            self._qsa_page_bytes = sum(t.stride(0) * t.element_size() for t in self.worker_handler.gpu_kv_caches.values())\n'
    source = replace_once(source, anchor, anchor + '            self._audit_register(kv_caches)\n')
    source = replace_once(source, '    def get_finished(self, finished_req_ids):\n        self._qsa_capture_load_for_bytecheck()\n',
        '    def get_finished(self, finished_req_ids):\n        self._audit_before()\n        self._qsa_capture_load_for_bytecheck()\n')
    source = replace_once(source, '        self._qsa_validate_completed_loads()\n',
        '        self._qsa_validate_completed_loads()\n        self._audit_after()\n')
    source = replace_once(source, '    def reset_cache(self):\n        self._qsa_pending_hits.clear()\n        return super().reset_cache()\n',
        '    def reset_cache(self):\n        self._qsa_pending_hits.clear()\n        result = super().reset_cache()\n        if result is True:\n            self._audit_reset()\n        return result\n')
    payload[CONNECTOR] = source.encode()
    payload[HELPER] = (HERE / 'qsa_resume_audit.py').read_bytes()
    policy = payload[POLICY].decode().replace('\r\n', '\n')
    tree = ast.parse(policy)
    assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == 'PINNED_SOURCE_SHA256' for t in n.targets))
    pins = ast.literal_eval(assignment.value)
    assert pins['v1/core/sched/scheduler.py'] == manifest['scheduler_alignment_sha256']
    assert pins[CONNECTOR.removeprefix('vllm/')] == sha(original[CONNECTOR])
    pins[CONNECTOR.removeprefix('vllm/')] = sha(payload[CONNECTOR])
    pins[HELPER.removeprefix('vllm/')] = sha(payload[HELPER])
    lines = policy.splitlines(keepends=True)
    lines[assignment.lineno - 1:assignment.end_lineno] = [
        'PINNED_SOURCE_SHA256 = ' + repr(pins) + '\n']
    payload[POLICY] = ''.join(lines).encode()
    manifest['files'].append({'path': HELPER, 'exact_sha256': None,
                               'fp8_parent_sha256': None})
    diffs = []
    for row in manifest['files']:
        name = row['path']
        raw = payload[name]
        compile(raw, name, 'exec')
        destination = HERE / 'candidate' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        row['candidate_sha256'] = sha(raw)
        if raw != original.get(name, b''):
            diffs.extend(difflib.unified_diff(
                original.get(name, b'').decode().splitlines(True),
                raw.decode().splitlines(True), fromfile='parent/' + name,
                tofile='candidate/' + name))
    manifest['runtime_dependency_hashes'] = pins
    manifest['parent_manifest_sha256'] = PARENT_SHA
    manifest['status'] = 'Diagnostic provenance only; not a numerical fix. GPU validation pending.'
    manifest['resume_audit'] = {
        'timing_valid': False, 'max_store_events': 256, 'max_load_events': 256,
        'existing_load_bytecheck_max_events': 64, 'max_event_bytes': 2 * 1024**3,
        'max_watch_steps': 128, 'max_watch_groups_per_step': 16,
        'scope': 'GPU pre-store raw and semantic checkpoint -> CPU completed store -> GPU completed load; request/key/group/boundary provenance; hash-bound resident semantic watches',
        'behavior_change': 'Synchronous readbacks and bounded fail-closed diagnostics only; scheduler, transfer allocation, attention and model kernels unchanged',
        'dependency_correction': 'Parent manifest JSON listed pre-alignment scheduler; reconcile with parent policy actual pinned alignment source',
        'portable_tests': {'path': 'test_resume_audit.py',
                           'sha256': sha((HERE / 'test_resume_audit.py').read_bytes()),
                           'scope': 'Source and mocked transfer/provenance state machine; GPU validation separate'},
    }
    manifest['build_sha256'] = sha(Path(__file__).read_bytes())
    (HERE / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (HERE / 'candidate.diff').write_text(''.join(diffs), encoding='utf-8')
    print(json.dumps({'manifest_sha256': sha((HERE / 'manifest.json').read_bytes()),
                      'connector_sha256': sha(payload[CONNECTOR]),
                      'helper_sha256': sha(payload[HELPER]), 'files': len(payload)}))


if __name__ == '__main__':
    main()

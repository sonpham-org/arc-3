"""Portable CPU-trace launch guards; no Docker, GPU or network calls."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import start_resume_server as parent
import start_trace_server_v2 as server

HERE = Path(__file__).resolve().parent
REAL_BUNDLE = HERE / 'trace-candidate-v2/cpu-audit-composed'


def args():
    return server.parser().parse_args([
        '--arm', 'qsa-cpu-fp8-bytecheck', '--attempt', 'e1',
        '--scheduler-alignment-fix', '--synchronous-eager', '--layer-trace',
        '--resume-diagnostics', str(server.PROBE / server.TRACE_RELATIVE),
        '--resume-manifest-sha256', server.TRACE_MANIFEST_SHA])


class ArgvTests(unittest.TestCase):
    def build(self, value=None):
        return server.build_command(value or args(), {'mounts': [], 'patches': {}, 'evidence': {}}, 'fixture')

    def test_only_trace_env_is_added_to_parent_command(self):
        new, identity, output, cache = self.build()
        old_args = parent.parser().parse_args([
            '--arm', 'qsa-cpu-fp8-bytecheck', '--attempt', 'e1',
            '--scheduler-alignment-fix', '--synchronous-eager',
            '--resume-diagnostics', str(parent.PROBE / 'qsa-resume-correctness-r1/runtime'),
            '--resume-manifest-sha256', server.TRACE_PARENT_SHA])
        old, _, _, old_cache = parent.build_command(old_args, {'mounts': [], 'patches': {}, 'evidence': {}}, 'fixture')
        stripped = list(new)
        for key, value in server.TRACE_ENV.items():
            i = stripped.index(key + '=' + value)
            self.assertEqual(stripped[i - 1], '-e')
            self.assertLess(i, stripped.index(server.IMAGE))
            del stripped[i - 1:i + 1]
        self.assertEqual(stripped, old)
        self.assertEqual(cache, old_cache)
        self.assertTrue(output.name.startswith('trace-v2-'))
        self.assertEqual(identity['command_argv'], new)
        self.assertTrue(identity['layer_trace'])
        self.assertEqual(identity['layer_trace_environment'], server.TRACE_ENV)
        self.assertFalse(identity['trace_timing_valid'])
        self.assertEqual(identity['trace_schema_version'], 2)
        self.assertNotIn('--moe-backend', new)

    def test_resources_and_eager_flags_are_preserved(self):
        cmd, identity, _, _ = self.build()
        for flag, value in [('--gpu-memory-utilization', '0.965'), ('--max-model-len', '131072'),
                            ('--max-num-seqs', '22'), ('--max-num-batched-tokens', '6144'),
                            ('--kv-cache-dtype', 'fp8_e4m3'), ('--tensor-parallel-size', '1')]:
            self.assertEqual(cmd[cmd.index(flag) + 1], value)
        self.assertIn('--enforce-eager', cmd)
        self.assertIn('--no-async-scheduling', cmd)
        self.assertTrue(identity['synchronous_eager_diagnostic'])
        transfer = json.loads(cmd[cmd.index('--kv-transfer-config') + 1])
        self.assertEqual(transfer['kv_connector_extra_config'],
                         {'cpu_bytes_to_use': 16 * 1024**3, 'offload_prompt_only': False})

    def test_trace_and_owned_profile_are_mandatory(self):
        for key, value in [('arm', 'patched-fp8'), ('layer_trace', False), ('synchronous_eager', False),
                           ('scheduler_alignment_fix', False), ('context', 65536), ('sequences', 11),
                           ('attempt', '../old'), ('numeric_report', '../old.json')]:
            with self.subTest(key=key):
                changed = args()
                setattr(changed, key, value)
                with self.assertRaises(ValueError): self.build(changed)

    def test_exact_composition_path_and_manifest_are_mandatory(self):
        for key, value in [('resume_diagnostics', None),
                           ('resume_diagnostics', server.PROBE / 'qsa-resume-correctness-r1/runtime'),
                           ('resume_diagnostics', server.PROBE / 'qsa-resume-correctness-r1/trace-candidate/cpu-audit-composed'),
                           ('resume_manifest_sha256', None),
                           ('resume_manifest_sha256', server.TRACE_PARENT_SHA)]:
            with self.subTest(key=key, value=value):
                changed = args()
                setattr(changed, key, value)
                with self.assertRaises(ValueError): self.build(changed)

    def test_alternative_cpu_cache_and_backends_are_rejected(self):
        for key, value in [('cpu_cache_gib', 32), ('batch_invariant', True), ('moe_backend', 'cutlass')]:
            changed = args()
            setattr(changed, key, value)
            with self.assertRaises(ValueError): self.build(changed)


class SourceTests(unittest.TestCase):
    def fixture(self, root):
        bundle = root / server.TRACE_RELATIVE
        shutil.copytree(REAL_BUNDLE, bundle)
        fp8 = root / 'fp8'
        fp8.mkdir()
        (fp8 / 'patch-manifest.json').write_text('{"files": {}}')
        (fp8 / 'gpu-numeric-r3.json').write_text(json.dumps({
            'status': 'completed', 'all_gates_passed': True,
            'script_sha256': 'abc09adedb35e1cb2976f6f71d4c40566cd4c8d2498424e019b91a51dc6512aa',
            'cases': [{}] * 16, 'patch_manifest_sha256': server.digest(fp8 / 'patch-manifest.json')}))
        scheduler = root / 'scheduler-alignment-r1'
        scheduler.mkdir()
        (scheduler / 'manifest.json').write_text(json.dumps({
            'path': server.SCHEDULER, 'base_sha256': server.SCHEDULER_BASE_SHA,
            'candidate_sha256': server.SCHEDULER_SHA}))
        return args()

    def hashes(self, path):
        path = Path(path)
        if path == Path('/opt/arc3/ple_layer_native_fp8.py'):
            return server.PLE_SHA
        if path.as_posix().endswith('/scheduler-alignment-r1/candidate/' + server.SCHEDULER):
            return server.SCHEDULER_SHA
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def image_hash(self, target):
        return {server.SCHEDULER: server.SCHEDULER_BASE_SHA,
                server.TRACE_MODEL_PATH: server.TRACE_MODEL_BASE_SHA}[target]

    def test_real_frozen_composition_and_all_readonly_mounts(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(server, 'PROBE', Path(temp)):
            value = self.fixture(Path(temp))
            with patch.object(server, 'digest', side_effect=self.hashes):
                verified = server.verified_sources(value, self.image_hash)
            self.assertEqual(set(verified['patches']), server.CPU_PATHS | {
                server.AUDIT_PATH, server.TRACE_MODEL_PATH, server.TRACE_HELPER_PATH,
                server.SCHEDULER, server.PLE})
            self.assertEqual(len(verified['mounts']), 10)
            self.assertEqual(verified['evidence']['resume_manifest_sha256'], server.TRACE_MANIFEST_SHA)
            cmd, _, _, _ = server.build_command(value, verified, 'fixture')
            for source, target in verified['mounts']:
                self.assertIn(source + ':' + target + ':ro', cmd)

    def test_mutated_payload_rejected(self):
        for target in (server.TRACE_MODEL_PATH, server.TRACE_HELPER_PATH, server.AUDIT_PATH):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp, patch.object(server, 'PROBE', Path(temp)):
                value = self.fixture(Path(temp))
                (value.resume_diagnostics / 'candidate' / target).write_text('changed')
                with patch.object(server, 'digest', side_effect=self.hashes), self.assertRaises(RuntimeError):
                    server.verified_sources(value, self.image_hash)

    def test_live_model_and_scheduler_image_identity_required(self):
        for bad_target in (server.TRACE_MODEL_PATH, server.SCHEDULER):
            with self.subTest(target=bad_target), tempfile.TemporaryDirectory() as temp, patch.object(server, 'PROBE', Path(temp)):
                value = self.fixture(Path(temp))
                def image(target):
                    return '0' * 64 if target == bad_target else self.image_hash(target)
                with patch.object(server, 'digest', side_effect=self.hashes), self.assertRaises(RuntimeError):
                    server.verified_sources(value, image)

    def test_manifest_bytes_are_frozen(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(server, 'PROBE', Path(temp)):
            value = self.fixture(Path(temp))
            path = value.resume_diagnostics / 'manifest.json'
            path.write_bytes(path.read_bytes() + b' ')
            with patch.object(server, 'digest', side_effect=self.hashes), self.assertRaises(RuntimeError):
                server.verified_sources(value, self.image_hash)

    def test_inventory_parent_model_base_and_dependencies_independently_checked(self):
        for mode in ('missing', 'extra', 'duplicate', 'parent', 'modelbase', 'modelpayload', 'helperpayload', 'dependency'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp, patch.object(server, 'PROBE', Path(temp)):
                value = self.fixture(Path(temp))
                path = value.resume_diagnostics / 'manifest.json'
                manifest = server.read_json(path)
                if mode == 'missing': manifest['files'].pop()
                elif mode == 'extra': manifest['files'].append(copy.deepcopy(manifest['files'][0]))
                elif mode == 'duplicate': manifest['files'][-1] = copy.deepcopy(manifest['files'][0])
                elif mode == 'parent': manifest['parent_manifest_sha256'] = '0' * 64
                elif mode == 'modelbase':
                    next(row for row in manifest['files'] if row['path'] == server.TRACE_MODEL_PATH)['exact_sha256'] = '0' * 64
                elif mode in ('modelpayload', 'helperpayload'):
                    target = server.TRACE_MODEL_PATH if mode == 'modelpayload' else server.TRACE_HELPER_PATH
                    next(row for row in manifest['files'] if row['path'] == target)['candidate_sha256'] = '0' * 64
                else: manifest['runtime_dependency_hashes'][server.TRACE_MODEL_PATH.removeprefix('vllm/')] = '0' * 64
                path.write_text(json.dumps(manifest))
                value.resume_manifest_sha256 = server.digest(path)
                # Bypass only the outer frozen-manifest pin in this fixture to
                # exercise the independent layout/base/dependency checks.
                with patch.object(server, 'TRACE_MANIFEST_SHA', value.resume_manifest_sha256), \
                     patch.object(server, 'digest', side_effect=self.hashes), self.assertRaises(RuntimeError):
                    server.verified_sources(value, self.image_hash)

    def test_frozen_fp8_numeric_report_still_required(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(server, 'PROBE', Path(temp)):
            value = self.fixture(Path(temp))
            path = Path(temp) / 'fp8/gpu-numeric-r3.json'
            report = server.read_json(path)
            report['all_gates_passed'] = False
            path.write_text(json.dumps(report))
            with patch.object(server, 'digest', side_effect=self.hashes), self.assertRaises(RuntimeError):
                server.verified_sources(value, self.image_hash)


if __name__ == '__main__':
    unittest.main()

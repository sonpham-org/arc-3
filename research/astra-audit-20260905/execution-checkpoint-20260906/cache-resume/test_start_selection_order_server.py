"""Portable isolated selection-order launch guards; no Docker, GPU or network calls."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import start_trace_server_v2 as parent
import start_selection_order_server as server

HERE = Path(__file__).resolve().parent
REAL_BUNDLE = HERE / 'selection-order-candidate-r1'


def args():
    return server.parser().parse_args([
        '--arm', 'qsa-cpu-fp8-bytecheck', '--attempt', 'e1',
        '--scheduler-alignment-fix', '--synchronous-eager', '--layer-trace',
        '--resume-diagnostics', str(server.PROBE / server.TRACE_RELATIVE),
        '--resume-manifest-sha256', server.TRACE_MANIFEST_SHA])


class ArgvTests(unittest.TestCase):
    def build(self, value=None):
        return server.build_command(value or args(), {'mounts': [], 'patches': {}, 'evidence': {}}, 'fixture')

    def test_server_command_matches_frozen_v2_control(self):
        new, identity, output, cache = self.build()
        old_args = parent.parser().parse_args([
            '--arm', 'qsa-cpu-fp8-bytecheck', '--attempt', 'e1',
            '--scheduler-alignment-fix', '--synchronous-eager', '--layer-trace',
            '--resume-diagnostics', str(parent.PROBE / parent.TRACE_RELATIVE),
            '--resume-manifest-sha256', parent.TRACE_MANIFEST_SHA])
        old, _, _, old_cache = parent.build_command(old_args, {'mounts': [], 'patches': {}, 'evidence': {}}, 'fixture')
        self.assertEqual(new, old)
        self.assertEqual(cache, old_cache)
        self.assertTrue(output.name.startswith('selection-order-r1-'))
        self.assertEqual(identity['command_argv'], new)
        self.assertTrue(identity['layer_trace'])
        self.assertEqual(identity['layer_trace_environment'], server.TRACE_ENV)
        self.assertFalse(identity['trace_timing_valid'])
        self.assertEqual(identity['trace_schema_version'], 2)
        self.assertEqual(identity['selection_order_ops_sha256'], server.ORDER_OPS_SHA)
        self.assertEqual(identity['layer_trace_environment']['VLLM_QSA_LAYER_TRACE_MAX_FORWARDS'], '128')
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
                           ('resume_diagnostics', server.PROBE / parent.TRACE_RELATIVE),
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
                server.TRACE_MODEL_PATH: server.TRACE_MODEL_BASE_SHA,
                server.ORDER_OPS_PATH: server.ORDER_OPS_BASE_SHA}[target]

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
        for target in (server.TRACE_MODEL_PATH, server.TRACE_HELPER_PATH, server.AUDIT_PATH, server.ORDER_OPS_PATH):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp, patch.object(server, 'PROBE', Path(temp)):
                value = self.fixture(Path(temp))
                (value.resume_diagnostics / 'candidate' / target).write_text('changed')
                with patch.object(server, 'digest', side_effect=self.hashes), self.assertRaises(RuntimeError):
                    server.verified_sources(value, self.image_hash)

    def test_live_model_and_scheduler_image_identity_required(self):
        for bad_target in (server.TRACE_MODEL_PATH, server.SCHEDULER, server.ORDER_OPS_PATH):
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
        for mode in ('missing', 'extra', 'duplicate', 'parent', 'modelbase', 'modelpayload', 'helperpayload', 'opsbase', 'opsparent', 'opspayload', 'dependency'):
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
                elif mode in ('opsbase', 'opsparent', 'opspayload'):
                    key = {'opsbase': 'exact_sha256', 'opsparent': 'ordering_parent_sha256', 'opspayload': 'candidate_sha256'}[mode]
                    next(row for row in manifest['files'] if row['path'] == server.ORDER_OPS_PATH)[key] = '0' * 64
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


class ExistingServiceTests(unittest.TestCase):
    def test_existing_or_unproven_container_name_never_stopped_or_replaced(self):
        outcomes = [SimpleNamespace(returncode=0, stderr=''),
                    SimpleNamespace(returncode=1, stderr='Docker unavailable')]
        for outcome in outcomes:
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as temp, \
                    patch.object(server, 'PROBE', Path(temp)):
                (Path(temp) / 'READY').touch()
                value = args()
                with patch.object(server, 'parser', return_value=SimpleNamespace(parse_args=lambda: value)), \
                        patch.object(server.subprocess, 'run', return_value=outcome) as run, \
                        patch.object(server.subprocess, 'Popen') as popen, \
                        self.assertRaises(RuntimeError):
                    server.main()
                run.assert_called_once()
                self.assertEqual(run.call_args.args[0], ['docker', 'container', 'inspect', 'astra-serve'])
                popen.assert_not_called()

    def test_missing_owned_ready_marker_prevents_process_calls(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(server, 'PROBE', Path(temp)):
            value = args()
            with patch.object(server, 'parser', return_value=SimpleNamespace(parse_args=lambda: value)), \
                    patch.object(server.subprocess, 'run') as run, self.assertRaises(RuntimeError):
                server.main()
            run.assert_not_called()

    def test_existing_attempt_directory_is_preserved_without_launch(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(server, 'PROBE', Path(temp)):
            root = Path(temp)
            (root / 'READY').touch()
            value = args()
            verified = {'mounts': [], 'patches': {}, 'evidence': {}}
            _, _, out, _ = server.build_command(value, verified, 'fixture')
            out.mkdir(parents=True)
            marker = out / 'identity.json'
            marker.write_text('preserve')
            responses = [SimpleNamespace(returncode=1, stderr='No such container: astra-serve'),
                         SimpleNamespace(returncode=0)]
            with patch.object(server, 'parser', return_value=SimpleNamespace(parse_args=lambda: value)), \
                    patch.object(server, 'verified_sources', return_value=verified), \
                    patch.object(server.subprocess, 'run', side_effect=responses) as run, \
                    patch.object(server.subprocess, 'Popen') as popen, self.assertRaises(RuntimeError):
                server.main()
            self.assertEqual(run.call_count, 2)
            self.assertEqual(marker.read_text(), 'preserve')
            popen.assert_not_called()


if __name__ == '__main__':
    unittest.main()

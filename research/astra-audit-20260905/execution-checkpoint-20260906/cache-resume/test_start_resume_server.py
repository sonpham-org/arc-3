"""Local parser, argv, and immutable-source guards; never invokes Docker."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import start_resume_server as server


class ArgvTests(unittest.TestCase):
    def args(self, *extra):
        return server.parser().parse_args(['--arm', 'patched-fp8', '--attempt', 'test1', *extra])

    def build(self, args):
        return server.build_command(args, {'mounts': [], 'patches': {}, 'evidence': {}}, 'source-fixture')

    def test_default_preserves_resource_and_backend_settings(self):
        cmd, identity, out, cache = self.build(self.args())
        for flag, value in [('--gpus', 'all'), ('--gpu-memory-utilization', '0.965'),
                            ('--max-model-len', '131072'), ('--max-num-seqs', '22'),
                            ('--max-num-batched-tokens', '6144'), ('--kv-cache-dtype', 'fp8_e4m3')]:
            self.assertEqual(cmd[cmd.index(flag) + 1], value)
        self.assertNotIn('--moe-backend', cmd)
        self.assertNotIn('VLLM_BATCH_INVARIANT=1', cmd)
        self.assertNotIn('--enforce-eager', cmd)
        self.assertEqual(identity['moe_backend_requested'], 'auto')
        self.assertEqual(identity['command_argv'], cmd)
        self.assertTrue(out.name.startswith('resume-'))
        self.assertEqual(cache, server.PROBE / 'compile-cache/patched-fp8')

    def test_cutlass_changes_only_backend_flag_and_identity(self):
        before, _, _, _ = self.build(self.args('--synchronous-eager'))
        after, identity, _, _ = self.build(self.args('--synchronous-eager', '--moe-backend', 'cutlass'))
        self.assertEqual(after, before + ['--moe-backend', 'cutlass'])
        self.assertEqual(identity['moe_backend_requested'], 'cutlass')
        self.assertFalse(identity['batch_invariant'])

    def test_batch_invariant_is_docker_environment_not_model_flag(self):
        cmd, identity, _, _ = self.build(self.args('--batch-invariant'))
        where = cmd.index('VLLM_BATCH_INVARIANT=1')
        self.assertEqual(cmd[where - 1], '-e')
        self.assertLess(where, cmd.index(server.IMAGE))
        self.assertTrue(identity['batch_invariant'])

    def test_eager_controls_preserved_together(self):
        cmd, identity, _, _ = self.build(self.args('--synchronous-eager'))
        self.assertEqual(cmd[-2:], ['--enforce-eager', '--no-async-scheduling'])
        self.assertTrue(identity['synchronous_eager_diagnostic'])

    def test_disallowed_profiles_resources_and_backend_rejected(self):
        for key, value in [('arm', 'original-bf16'), ('context', 65536), ('sequences', 11),
                           ('moe_backend', 'unknown'), ('attempt', '../escape'), ('numeric_report', '../escape.json')]:
            args = self.args()
            setattr(args, key, value)
            with self.assertRaises(ValueError): self.build(args)

    def test_cpu_transfer_configuration_and_mounts_preserved(self):
        args = self.args('--arm', 'qsa-cpu-fp8-bytecheck')
        verified = {'mounts': [('/fixture/candidate.py', server.SITE + 'vllm/fixture.py')],
                    'patches': {'vllm/fixture.py': 'digest'}, 'evidence': {'bytecheck_diagnostics': True}}
        cmd, identity, _, _ = server.build_command(args, verified, 'source-fixture')
        transfer = json.loads(cmd[cmd.index('--kv-transfer-config') + 1])
        self.assertEqual(transfer['kv_connector'], 'QSAAlignedCPUOffloadConnector')
        self.assertEqual(transfer['kv_connector_extra_config'], {'cpu_bytes_to_use': 16 * 1024**3, 'offload_prompt_only': False})
        self.assertEqual(cmd[cmd.index('--mamba-cache-mode') + 1], 'align')
        self.assertIn('VLLM_SERVER_DEV_MODE=1', cmd)
        self.assertIn('/fixture/candidate.py:' + server.SITE + 'vllm/fixture.py:ro', cmd)
        self.assertEqual(identity['patches'], verified['patches'])

    def test_resume_requires_exact_owned_path_aligned_cpu_arm_and_sha(self):
        expected = server.PROBE / 'qsa-resume-correctness-r1/runtime'
        valid = self.args('--arm', 'qsa-cpu-fp8-bytecheck', '--scheduler-alignment-fix',
                          '--resume-diagnostics', str(expected), '--resume-manifest-sha256', '1' * 64)
        self.build(valid)
        for key, value in [('arm', 'patched-fp8'), ('scheduler_alignment_fix', False),
                           ('resume_diagnostics', expected.parent / 'other'), ('resume_manifest_sha256', None)]:
            changed = copy.deepcopy(valid)
            setattr(changed, key, value)
            with self.assertRaises(ValueError): self.build(changed)


class SourceTests(unittest.TestCase):
    def fixture(self, root, *, cpu=False, resume=False):
        def write(path, value):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value if isinstance(value, bytes) else json.dumps(value).encode())
        fp8 = {'files': {}}
        for name in server.QSA_PATHS:
            path = root / 'fp8/corrected-patched' / name
            write(path, name.encode())
            fp8['files'][name] = {'corrected_sha256': server.digest(path)}
        manifest_path = root / 'fp8/patch-manifest.json'
        write(manifest_path, fp8)
        write(root / 'fp8/gpu-numeric-r3.json', {'status': 'completed', 'all_gates_passed': True,
            'script_sha256': 'abc09adedb35e1cb2976f6f71d4c40566cd4c8d2498424e019b91a51dc6512aa',
            'cases': [{}] * 16, 'patch_manifest_sha256': server.digest(manifest_path)})
        argv = ['--arm', 'qsa-cpu-fp8-bytecheck' if cpu else 'patched-fp8', '--attempt', 'test1']
        if cpu:
            bundle = root / ('qsa-resume-correctness-r1/runtime' if resume else 'qsa-cpu-bytecheck-r1')
            rows = []
            for name in sorted(server.CPU_PATHS | ({server.AUDIT_PATH} if resume else set())):
                path = bundle / 'candidate' / name
                write(path, name.encode())
                rows.append({'path': name, 'candidate_sha256': server.digest(path)})
            write(bundle / 'manifest.json', {'connector': 'QSAAlignedCPUOffloadConnector', 'files': rows,
                  'runtime_dependency_hashes': {row['path'].removeprefix('vllm/'): row['candidate_sha256'] for row in rows}})
            if resume:
                argv += ['--scheduler-alignment-fix', '--resume-diagnostics', str(bundle),
                         '--resume-manifest-sha256', server.digest(bundle / 'manifest.json')]
                write(root / 'scheduler-alignment-r1/manifest.json', {'path': server.SCHEDULER,
                    'base_sha256': server.SCHEDULER_BASE_SHA, 'candidate_sha256': server.SCHEDULER_SHA})
                write(root / 'scheduler-alignment-r1/candidate' / server.SCHEDULER, b'scheduler-fixture')
        return server.parser().parse_args(argv)

    def hashes(self, path):
        if Path(path) == Path('/opt/arc3/ple_layer_native_fp8.py'): return server.PLE_SHA
        if Path(path).as_posix().endswith('/scheduler-alignment-r1/candidate/' + server.SCHEDULER): return server.SCHEDULER_SHA
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def test_real_file_hashes_and_frozen_numeric_report_accepted(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(server, 'PROBE', Path(temp)):
            args = self.fixture(Path(temp))
            with patch.object(server, 'digest', side_effect=self.hashes):
                result = server.verified_sources(args, lambda target: server.SCHEDULER_BASE_SHA)
            self.assertEqual(set(result['patches']), server.QSA_PATHS | {server.PLE})

    def test_changed_source_or_numeric_report_fails(self):
        for mode in ('source', 'report', 'manifest'):
            with tempfile.TemporaryDirectory() as temp, patch.object(server, 'PROBE', Path(temp)):
                root = Path(temp)
                args = self.fixture(root)
                if mode == 'source': (root / 'fp8/corrected-patched' / sorted(server.QSA_PATHS)[0]).write_text('changed')
                elif mode == 'report':
                    path = root / 'fp8/gpu-numeric-r3.json'
                    value = server.read_json(path); value['all_gates_passed'] = False; path.write_text(json.dumps(value))
                else:
                    path = root / 'fp8/patch-manifest.json'; path.write_bytes(path.read_bytes() + b' ')
                with patch.object(server, 'digest', side_effect=self.hashes), self.assertRaises(RuntimeError):
                    server.verified_sources(args, lambda target: server.SCHEDULER_BASE_SHA)

    def test_cpu_manifest_exact_inventory_and_hashes_required(self):
        for mode in ('valid', 'extra', 'wronghash'):
            with tempfile.TemporaryDirectory() as temp, patch.object(server, 'PROBE', Path(temp)):
                args = self.fixture(Path(temp), cpu=True)
                path = Path(temp) / 'qsa-cpu-bytecheck-r1/manifest.json'
                value = server.read_json(path)
                if mode == 'extra': value['files'].append({'path': 'vllm/extra.py', 'candidate_sha256': '0' * 64})
                elif mode == 'wronghash': value['files'][0]['candidate_sha256'] = '0' * 64
                path.write_text(json.dumps(value))
                with patch.object(server, 'digest', side_effect=self.hashes):
                    if mode == 'valid': self.assertEqual(len(server.verified_sources(args, lambda p: '')['patches']), 6)
                    else:
                        with self.assertRaises(RuntimeError): server.verified_sources(args, lambda p: '')

    def test_resume_manifest_binding_dependencies_and_image_base(self):
        for mode in ('valid', 'wrongsha', 'dependency', 'image'):
            with tempfile.TemporaryDirectory() as temp, patch.object(server, 'PROBE', Path(temp)):
                args = self.fixture(Path(temp), cpu=True, resume=True)
                if mode == 'wrongsha': args.resume_manifest_sha256 = '0' * 64
                elif mode == 'dependency':
                    path = args.resume_diagnostics / 'manifest.json'
                    value = server.read_json(path)
                    value['runtime_dependency_hashes'][server.PLE.removeprefix('vllm/')] = '0' * 64
                    path.write_text(json.dumps(value)); args.resume_manifest_sha256 = server.digest(path)
                image_hash = lambda target: '0' * 64 if mode == 'image' else server.SCHEDULER_BASE_SHA
                with patch.object(server, 'digest', side_effect=self.hashes):
                    if mode == 'valid': self.assertEqual(len(server.verified_sources(args, image_hash)['patches']), 8)
                    else:
                        with self.assertRaises(RuntimeError): server.verified_sources(args, image_hash)


if __name__ == '__main__': unittest.main()

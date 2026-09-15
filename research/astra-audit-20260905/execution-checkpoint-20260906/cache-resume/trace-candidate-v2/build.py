"""V2 MRV2 embedding-aware trace; frozen V1 and CPU audit remain unchanged."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODEL = 'vllm/models/qwen3_8_flash_next/nvidia/model.py'
HELPER = 'vllm/models/qwen3_8_flash_next/common/qsa_layer_trace.py'
POLICY = 'vllm/models/qwen3_8_flash_next/common/qsa_cpu_offload.py'
MODEL_SHA = 'd900cd6fcacba18f460e00b3f018fbf36fbe6ecc310692b6adb1451f7f53cc17'
CPU_MANIFEST_SHA = 'd6d7d3ee7855beff7873b2c3cef64979135d78a88ac9e4a1e28c1d7a0586922f'
V1_MANIFEST_SHA = '726db89acb9da5c68b2004323050d4c9e98c2ba38f018b8146ea76fc3402aa9b'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Trace source anchor mismatch: ' + before)
    return source.replace(before, after)


def write_payload(directory, payload):
    for name, raw in payload.items():
        compile(raw, name, 'exec')
        path = directory / 'candidate' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def main():
    assert sha((HERE.parent / 'trace-candidate/manifest.json').read_bytes()) == V1_MANIFEST_SHA
    original = (ROOT / 'exact-vllm-python' / MODEL).read_bytes()
    assert sha(original) == MODEL_SHA
    source = original.decode().replace('\r\n', '\n')
    source = replace_once(source, 'from .qsa import Qwen3_8FlashNextQSAAttention\n',
        'from .qsa import Qwen3_8FlashNextQSAAttention\nfrom ..common.qsa_layer_trace import install as install_qsa_layer_trace\n')
    anchor = '''        self.start_layer, self.end_layer, self.layers = make_layers(
            config.num_hidden_layers, get_layer, prefix=f"{prefix}.layers"
        )
'''
    source = replace_once(source, anchor, anchor +
        '        self._qsa_layer_trace = install_qsa_layer_trace(self, vllm_config, prefix)\n')
    anchor = '''        deepstack_input_embeds: IntermediateTensors | None = None,
    ) -> torch.Tensor | IntermediateTensors:
        if get_pp_group().is_first_rank:
'''
    source = replace_once(source, anchor, '''        deepstack_input_embeds: IntermediateTensors | None = None,
    ) -> torch.Tensor | IntermediateTensors:
        if self._qsa_layer_trace is not None:
            self._qsa_layer_trace.begin(input_ids, positions, query_start_loc,
                ngram_context, inputs_embeds, deepstack_input_embeds)
        if get_pp_group().is_first_rank:
''')
    source = replace_once(source, '        return sample_hidden_states\n',
        '        if self._qsa_layer_trace is not None:\n            self._qsa_layer_trace.end(sample_hidden_states)\n        return sample_hidden_states\n')
    anchor = '''    def compute_logits(self, hidden_states: torch.Tensor) -> torch.Tensor | None:
        return self.logits_processor(self.lm_head, hidden_states)
'''
    source = replace_once(source, anchor, '''    def compute_logits(self, hidden_states: torch.Tensor) -> torch.Tensor | None:
        trace = self.model._qsa_layer_trace
        if trace is not None:
            trace.logits("input", hidden_states)
        logits = self.logits_processor(self.lm_head, hidden_states)
        if trace is not None:
            trace.logits("output", logits)
        return logits
''')
    payload = {MODEL: source.encode(), HELPER: (HERE / 'qsa_layer_trace.py').read_bytes()}
    write_payload(HERE, payload)
    manifest = {'status': 'V2 accepts and fingerprints MRV2 text embeddings; GPU validation pending; not a numerical fix',
        'trace_schema_version': 2, 'parent_trace_manifest_sha256': V1_MANIFEST_SHA,
        'files': [{'path': name, 'exact_sha256': MODEL_SHA if name == MODEL else None,
                   'candidate_sha256': sha(raw)} for name, raw in payload.items()],
        'flags': {'VLLM_QSA_LAYER_TRACE': '1',
                  'VLLM_QSA_LAYER_TRACE_SUBMODULES': '0 by default; 1 adds QSA/GDN/MLP/PLE',
                  'VLLM_QSA_LAYER_TRACE_MAX_FORWARDS': '128 by default; allowed 1..512'},
        'constraints': ['enforce_eager', 'async_scheduling=false', 'TP/PP/DP/CP=1',
                        'no speculation', 'raw token IDs retained; supplied embeddings also fingerprinted'],
        'timing_valid': False, 'max_tensor_bytes': 256 * 1024**2,
        'build_sha256': sha(Path(__file__).read_bytes()),
        'tests_sha256': sha((HERE / 'test_layer_trace.py').read_bytes())}
    (HERE / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    diff = ''.join(difflib.unified_diff(original.decode().splitlines(True),
        source.splitlines(True), fromfile='exact/' + MODEL, tofile='candidate/' + MODEL))
    (HERE / 'model.diff').write_text(diff)

    # Compose separately. Do not edit the frozen six-file CPU-audit bundle.
    cpu_root = HERE.parent / 'runtime'
    parent_raw = (cpu_root / 'manifest.json').read_bytes()
    assert sha(parent_raw) == CPU_MANIFEST_SHA
    cpu = json.loads(parent_raw)
    composed = {}
    for row in cpu['files']:
        raw = (cpu_root / 'candidate' / row['path']).read_bytes()
        assert sha(raw) == row['candidate_sha256']
        composed[row['path']] = raw
    composed.update(payload)
    policy = composed[POLICY].decode()
    tree = ast.parse(policy)
    node = next(n for n in tree.body if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == 'PINNED_SOURCE_SHA256' for t in n.targets))
    pins = ast.literal_eval(node.value)
    assert pins[MODEL.removeprefix('vllm/')] == MODEL_SHA
    pins[MODEL.removeprefix('vllm/')] = sha(payload[MODEL])
    pins[HELPER.removeprefix('vllm/')] = sha(payload[HELPER])
    lines = policy.splitlines(keepends=True)
    lines[node.lineno - 1:node.end_lineno] = ['PINNED_SOURCE_SHA256 = ' + repr(pins) + '\n']
    composed[POLICY] = ''.join(lines).encode()
    destination = HERE / 'cpu-audit-composed'
    write_payload(destination, composed)
    cpu['files'].extend(manifest['files'])
    for row in cpu['files']:
        row['candidate_sha256'] = sha(composed[row['path']])
    cpu['runtime_dependency_hashes'] = pins
    cpu['parent_manifest_sha256'] = CPU_MANIFEST_SHA
    cpu['status'] = 'Separate CPU provenance + optional layer fingerprints; GPU validation pending'
    cpu['layer_trace'] = {**manifest, 'manifest_sha256': sha((HERE / 'manifest.json').read_bytes())}
    (destination / 'manifest.json').write_text(json.dumps(cpu, indent=2) + '\n')
    print(json.dumps({'trace_manifest_sha256': sha((HERE / 'manifest.json').read_bytes()),
        'cpu_composed_manifest_sha256': sha((destination / 'manifest.json').read_bytes()),
        'trace_files': len(payload), 'composed_files': len(composed)}))


if __name__ == '__main__':
    main()

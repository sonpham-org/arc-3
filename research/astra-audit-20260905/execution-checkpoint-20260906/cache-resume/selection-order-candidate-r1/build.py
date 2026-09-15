"""Isolated post-expansion QSA ordering control; preserve frozen parent bundles."""
import ast
import copy
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'trace-candidate-v2/cpu-audit-composed'
PARENT_SHA = '966b7a9d01f5994d0580468104f3147fa9fd3acdc4af8a20e5a7e42890afd56f'
OPS = 'vllm/models/qwen3_8_flash_next/nvidia/ops/qsa.py'
POLICY = 'vllm/models/qwen3_8_flash_next/common/qsa_cpu_offload.py'
OPS_SHA = '877ff779fd127c750c7d773e07181e90841756119e4e27e3c27358448d08eb18'
ANCHOR = '''            out[row_slice],
        )
    return out


def qsa_sparse_paged_attention('''
REPLACEMENT = '''            out[row_slice],
        )
        # Canonicalize the selected multiset after causal-tail expansion.
        # Negative padding may move: sparse attention masks each index itself.
        # Copy back to preserve the caller-owned topk_indices_buffer alias.
        selected = out[row_slice]
        selected.copy_(selected.sort(dim=-1).values)
    return out


def qsa_sparse_paged_attention('''


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def patch_ops(raw):
    if sha(raw) != OPS_SHA:
        raise ValueError('Parent QSA ops hash mismatch')
    source = raw.decode().replace('\r\n', '\n')
    if source.count(ANCHOR) != 1:
        raise ValueError('Unique QSA selection-return anchor not found')
    return source.replace(ANCHOR, REPLACEMENT).encode()


def main():
    parent_raw = (PARENT / 'manifest.json').read_bytes()
    if sha(parent_raw) != PARENT_SHA:
        raise ValueError('Frozen v2 composition manifest changed')
    manifest = copy.deepcopy(json.loads(parent_raw))
    payload = {}
    for row in manifest['files']:
        raw = (PARENT / 'candidate' / row['path']).read_bytes()
        if sha(raw) != row['candidate_sha256']:
            raise ValueError('Parent payload mismatch: ' + row['path'])
        payload[row['path']] = raw
    original = payload[OPS]
    payload[OPS] = patch_ops(original)
    policy = payload[POLICY].decode()
    tree = ast.parse(policy)
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == 'PINNED_SOURCE_SHA256' for t in n.targets))
    pins = ast.literal_eval(node.value)
    if pins != manifest['runtime_dependency_hashes'] or pins[OPS.removeprefix('vllm/')] != OPS_SHA:
        raise ValueError('Parent dependency binding mismatch')
    pins[OPS.removeprefix('vllm/')] = sha(payload[OPS])
    lines = policy.splitlines(keepends=True)
    lines[node.lineno - 1:node.end_lineno] = ['PINNED_SOURCE_SHA256 = ' + repr(pins) + '\n']
    payload[POLICY] = ''.join(lines).encode()
    for row in manifest['files']:
        raw = payload[row['path']]
        compile(raw, row['path'], 'exec')
        target = HERE / 'candidate' / row['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        row['ordering_parent_sha256'] = row['candidate_sha256']
        row['candidate_sha256'] = sha(raw)
    manifest['runtime_dependency_hashes'] = pins
    manifest['parent_manifest_sha256'] = PARENT_SHA
    manifest['status'] = 'Isolated canonical selected-token ordering; live validation pending'
    manifest['selection_order_control'] = {
        'stage': 'After existing expansion, before returning caller-owned index buffer',
        'operation': 'Ascending integer sort per selected-token row and copy_ to same view',
        'membership': 'No rescoring, tie breaking, deduplication or index filtering',
        'precision': 'Preserves FP8 cache and original sparse-attention kernels',
        'constraints': ['Existing eager/no-async/serial diagnostic profile', 'Same v2 trace and CPU provenance hooks'],
        'timing_valid': False,
        'gpu_validated': False,
        'build_sha256': sha(Path(__file__).read_bytes()),
        'tests_sha256': sha((HERE / 'test_selection_order.py').read_bytes())}
    (HERE / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (HERE / 'ops.diff').write_text(''.join(difflib.unified_diff(
        original.decode().splitlines(True), payload[OPS].decode().splitlines(True),
        fromfile='frozen-v2/' + OPS, tofile='ordering-control/' + OPS)))
    print(json.dumps({'manifest_sha256': sha((HERE / 'manifest.json').read_bytes()),
        'ops_sha256': sha(payload[OPS]), 'files': len(payload)}))


if __name__ == '__main__':
    main()

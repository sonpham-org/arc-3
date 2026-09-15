"""Portable execution of patched selection orchestration; no Torch or GPU."""
import ast
import collections
import copy
import json
from pathlib import Path
import random
from types import SimpleNamespace
import unittest

import build


class Tensor:
    events = []

    def __init__(self, rows, width=None):
        self.rows = rows
        self.shape = (len(rows), len(rows[0]) if rows else width or 0)
        self.device = 'cuda:0'

    def __getitem__(self, key):
        return Tensor(self.rows[key], self.shape[1])

    def sort(self, dim):
        if dim != -1:
            raise AssertionError('Expected last-axis sort')
        self.events.append('sort')
        return SimpleNamespace(values=Tensor([sorted(row) for row in self.rows], self.shape[1]))

    def copy_(self, other):
        if self.shape != other.shape:
            raise AssertionError('copy shape differs')
        self.events.append('copy')
        for row, new in zip(self.rows, other.rows):
            row[:] = new
        return self

    def stride(self, dimension):
        return self.shape[1] if dimension == 0 else 1


def expand_reference(blocks, position, sequence_length, ratio, topk):
    complete = min((position + 1) // ratio, sequence_length // ratio, topk // ratio)
    tokens = [block * ratio + offset for block in blocks[:complete] for offset in range(ratio)]
    tail_start = ((position + 1) // ratio) * ratio
    tokens += list(range(tail_start, position + 1))[:ratio - 1]
    tokens = [token if 0 <= token < sequence_length else -1 for token in tokens]
    return (tokens + [-1] * (topk + ratio - 1))[:topk + ratio - 1]


def execute(rows, positions, sequence_lengths, selected_blocks, *, ratio=4, topk=16,
            chunk_rows=2, supplied=True, cooperative=False, source=None):
    """Execute the actual patched function AST against independent kernel stubs."""
    raw = build.patch_ops((build.PARENT / 'candidate' / build.OPS).read_bytes()) if source is None else source
    tree = ast.parse(raw)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'qsa_select_paged_tokens')
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), function], type_ignores=[])
    ast.fix_missing_locations(module)
    Tensor.events = []
    columns = 32
    current_ids = []

    def empty(shape, **_kwargs):
        if len(shape) == 1:
            return SimpleNamespace(shape=shape)
        return Tensor([[99991] * shape[1] for _ in range(shape[0])], shape[1])

    def score(q, _cache, _table, _requests, _positions, _lengths, _ratio):
        current_ids[:] = [row[0] for row in q.rows]
        return empty((q.shape[0], columns)), None

    def topk_impl(_logits, _visible, output, _workspace, width, _columns):
        Tensor.events.append('topk')
        for dest, source_id in zip(output.rows, current_ids):
            self_selected = selected_blocks[source_id]
            dest[:] = self_selected + [-1] * (width - len(self_selected))

    def expand(blocks, query_positions, lengths, token_to_req, compression, budget, output):
        Tensor.events.append('expand')
        for dest, block, position, request in zip(output.rows, blocks.rows, query_positions, token_to_req):
            dest[:] = expand_reference(block, position, lengths[request], compression, budget)
        return output

    namespace = {'torch': SimpleNamespace(empty=empty, int32='int32', uint8='uint8',
        ops=SimpleNamespace(_C=SimpleNamespace(persistent_topk=topk_impl, cooperative_topk=topk_impl))),
        '_LOGITS_WORKSPACE_BYTES': columns * 4 * chunk_rows, '_TOPK_WORKSPACE_BYTES': 32,
        'current_platform': SimpleNamespace(has_device_capability=lambda _n: cooperative,
            is_device_capability_family=lambda _n: not cooperative),
        'qsa_mqa_paged': score, 'expand_qsa_block_indices_cuda': expand}
    exec(compile(module, str(build.HERE / 'candidate' / build.OPS), 'exec'), namespace)
    q = Tensor([[i] for i in range(rows)])
    out = empty((rows, topk + ratio - 1)) if supplied else None
    original_rows = None if out is None else list(out.rows)
    result = namespace['qsa_select_paged_tokens'](q, SimpleNamespace(shape=(1, 4, 1, 8)),
        SimpleNamespace(shape=(rows, columns // 4)), list(range(rows)), positions,
        sequence_lengths, topk, ratio, out)
    return result, out, original_rows, Tensor.events[:]


class Tests(unittest.TestCase):
    def test_actual_function_preserves_caller_buffer_and_orders_after_expansion(self):
        result, out, original, events = execute(2, [23, 24], [24, 25], [[5, 0, 3, 1], [4, 2, 1, 0]])
        self.assertIs(result, out)
        self.assertTrue(all(a is b for a, b in zip(result.rows, original)))
        self.assertEqual(events, ['topk', 'expand', 'sort', 'copy'])
        self.assertTrue(all(row == sorted(row) for row in result.rows))

    def test_short_prefix_negative_padding_and_open_tail_are_preserved(self):
        positions = [0, 2, 3, 4, 6, 7, 8, 14, 15, 16, 31]
        lengths = [position + 1 for position in positions]
        blocks = [list(reversed(range(min(length // 4, 4)))) for length in lengths]
        result, _, _, _ = execute(len(positions), positions, lengths, blocks)
        for row, selected, position, length in zip(result.rows, blocks, positions, lengths):
            expected = expand_reference(selected, position, length, 4, 16)
            self.assertEqual(collections.Counter(row), collections.Counter(expected))
            self.assertEqual(row, sorted(expected))

    def test_ascending_preexpansion_sort_would_lose_short_prefix_tokens(self):
        blocks = [1, 0, -1, -1]
        original = expand_reference(blocks, 8, 9, 4, 16)
        wrong = expand_reference(sorted(blocks), 8, 9, 4, 16)
        self.assertNotEqual(collections.Counter(original), collections.Counter(wrong))
        actual, _, _, _ = execute(1, [8], [9], [[1, 0]])
        self.assertEqual(collections.Counter(actual.rows[0]), collections.Counter(original))

    def test_permuted_equal_selected_multisets_produce_identical_outputs(self):
        randomizer = random.Random(70192)
        blocks = [1, 3, 5, 7]
        reference = None
        for _ in range(12):
            randomizer.shuffle(blocks)
            result, _, _, _ = execute(1, [40], [41], [blocks[:]])
            reference = result.rows if reference is None else reference
            self.assertEqual(result.rows, reference)

    def test_duplicates_are_preserved_and_membership_changes_remain_visible(self):
        first, _, _, _ = execute(1, [40], [41], [[1, 1, 3, 7]])
        second, _, _, _ = execute(1, [40], [41], [[1, 2, 3, 7]])
        self.assertEqual(first.rows[0].count(4), 2)
        self.assertNotEqual(first.rows, second.rows)

    def test_multiple_chunks_cooperative_and_allocated_output(self):
        args = (5, [24] * 5, [25] * 5, [[4, 1, 3, 2]] * 5)
        chunked, _, _, events = execute(*args, supplied=False, cooperative=True, chunk_rows=2)
        unchunked, _, _, _ = execute(*args, chunk_rows=5)
        self.assertEqual(chunked.rows, unchunked.rows)
        self.assertEqual(events, ['topk', 'expand', 'sort', 'copy'] * 3)

    def test_zero_rows_returns_without_gpu_work(self):
        result, out, _, events = execute(0, [], [], [])
        self.assertIs(result, out)
        self.assertEqual(events, [])

    def test_patch_rejects_wrong_parent_and_changes_only_selection_body(self):
        original = (build.PARENT / 'candidate' / build.OPS).read_bytes()
        with self.assertRaises(ValueError):
            build.patch_ops(original + b'\n')
        a, b = ast.parse(original), ast.parse(build.patch_ops(original))
        def strip(tree):
            return [ast.dump(n, include_attributes=False) for n in tree.body if not (
                isinstance(n, ast.FunctionDef) and n.name == 'qsa_select_paged_tokens')]
        self.assertEqual(strip(a), strip(b))

    def test_composed_payload_and_policy_bind_exactly(self):
        manifest = json.loads((build.HERE / 'manifest.json').read_bytes())
        self.assertEqual(manifest['parent_manifest_sha256'], build.PARENT_SHA)
        changed = []
        for row in manifest['files']:
            raw = (build.HERE / 'candidate' / row['path']).read_bytes()
            self.assertEqual(build.sha(raw), row['candidate_sha256'])
            compile(raw, row['path'], 'exec')
            if row['candidate_sha256'] != row['ordering_parent_sha256']:
                changed.append(row['path'])
        self.assertEqual(set(changed), {build.OPS, build.POLICY})
        tree = ast.parse((build.HERE / 'candidate' / build.POLICY).read_bytes())
        pins = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == 'PINNED_SOURCE_SHA256' for t in n.targets))
        self.assertEqual(pins, manifest['runtime_dependency_hashes'])
        self.assertEqual(pins[build.OPS.removeprefix('vllm/')], build.sha((build.HERE / 'candidate' / build.OPS).read_bytes()))


if __name__ == '__main__':
    unittest.main()

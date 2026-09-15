# Isolated QSA selection-order control

This candidate tests the first measured numerical divergence. Its serial text
CPU-resume parity now passes at three boundaries, while asynchronous,
multimodal, throughput, and gameplay-quality validation remain open. It does
not change the completed matrix or any frozen trace/CPU-audit bundle.

## Evidence and diagnosis

The source-attested v2 trace at boundary 3,200 completed all request bindings and
all three CPU provenance checks. Across all nine within-family pairs (three
resident, three CPU-restored, three cold), the first differing traced observation
was `module_output` for `layer.3.self_attn.indexer`. Selected logical inputs,
embedding fingerprints and CPU/CUDA RNG fingerprints matched. At this layer,
the ordered selection differed while the sorted selected multiset matched.

`observed-evidence.json` records these nine comparisons and SHA-256 hashes of the
original trace, numerical probe, provenance result and comparator report. It does
not duplicate the raw log. The raw evidence remains outside this public
checkpoint and is bound by `../../provenance/raw-artifact-index.json`.

Pinned NVIDIA `ops/qsa.py` dispatches RTX 6000 PRO/SM120 to
`torch.ops._C.persistent_topk`; the cooperative route explicitly excludes device
family 120. The selected compressed blocks are expanded in returned order.
Sparse attention then partitions those token indices into tiles and splits, and
computes normalized reductions in that order. Reordering equal selected tokens
therefore changes floating-point reduction grouping. The observed order change
is proven; its responsibility for the downstream numerical drift is the
hypothesis tested here. Hidden indexer state or omitted metadata are not proved
identical by the trace.

## Narrow change

Only the selection-return path in the existing corrected FP8 `nvidia/ops/qsa.py`
changes. Immediately after each existing expansion call:

```python
selected = out[row_slice]
selected.copy_(selected.sort(dim=-1).values)
```

Integer ascending order is unique for an identical multiset. Equal integers
need no stable sort: exchanging duplicates produces the same values. The copy
preserves the caller-owned `topk_indices_buffer` and its aliases. Operations
stay on the current CUDA stream; no CPU readback or new synchronization is added
by this change. Existing synchronous trace and provenance diagnostics remain.

Sorting occurs **after expansion** because expansion consumes only the first
`complete_blocks` compressed indices. Sorting those indices ascending beforehand
could move `-1` padding into that live prefix and discard selected tokens.
Post-expansion sorting retains every selected token, duplicate, negative padding
entry and open-group tail token. The sparse kernel independently masks negative
indices at every column and consumes the full fixed output width, so their new
positions remain valid. No scoring, selection membership, tie-breaking,
deduplication, masking, attention precision or attention kernel changes.

The change allocates sort values and index workspace for the existing row chunk
and copies the values back. Overhead and GPU memory use require measurement.
Sorting 2,051 expanded token indices is deliberately simpler to validate than
introducing a new compressed-index padding convention or custom sorting kernel.
This control targets the existing eager diagnostic; graph capture and serving
performance are not established by portable tests.

## Bundle and tests

The manifest uses the same eight-file layout as the frozen v2 CPU+trace bundle.
Six payloads are byte-identical. Only the QSA ops payload and its dependency hash
inside `qsa_cpu_offload.py` differ. No new environment flag is required: selecting
this separately attested candidate enables the ordering control.

- Parent manifest: `966b7a9d01f5994d0580468104f3147fa9fd3acdc4af8a20e5a7e42890afd56f`
- Candidate manifest: `9581fb0105abaf3c1850cb6ec0c668199098dbb2004e45cbe8e2e2fc3300de34`
- Candidate ops: `1bb70e3410908e334de9df490f876473ad6b83ca5c3af9c25632b685d69d924d`

Nine portable tests pass. They execute the actual patched selection function AST
against independent kernel stubs and check short prefixes, incomplete causal
tails, preserved duplicates, changed membership visibility, permutation
invariance, chunk boundaries, empty inputs, allocated output and caller-buffer
identity. They also verify all payload hashes and policy dependencies and that
no other ops function changes. These tests do not execute CUDA sorting or prove
numerical parity. See `portable-tests.log` and `ops.diff`.

Independent read-only review reran all nine tests and found no blocker. It also
checked all-invalid leading tiles/splits: probabilities and normalizers remain
zero, partial log-sum-exp is negative infinity, and the merge masks empty splits.
Thus moving negative padding to the front does not introduce an unhandled empty
split in the pinned kernel.

`review-receipt.json` and `LAUNCH.md` are freeze-time records, so their pending
language describes the state before the live result below.

## Bounded live result

The attested 4k trace completed all bindings. All resident, CPU-restored, and
cold same-path comparisons became identical through final logits, and all nine
resident-to-CPU comparisons had exact next-token and top-five log-probability
equality. The transfer audit passed 18 of 18 source→CPU→GPU chains.

The same candidate then passed serial CPU resume at 64,000 and 129,600 cached
tokens. All six restore requests passed 387 of 387 transfer chains; resident
repeats were exact; and all 18 resident-to-CPU prediction pairs were exact.
Together with 4k, this is 405 of 405 transfer chains and 27 of 27 exact
resident-to-CPU pairs.

The full conservative gate remains false because independent cold recomputation
is still unstable at the two long fixtures. Greedy tokens stayed equal, while
top-five probabilities exceeded the unchanged 1e-4 tolerance and the 131k
top-five set varied. This does not implicate CPU copy/restore, but it leaves a
separate QSA cold-prefill issue. See
`../evidence/selection-order-validation.json` for the sanitized outcome and the
provenance index for raw hashes.

Do not enable this candidate in gameplay yet. Sorting changes sparse-attention
reduction order. Multimodal and multi-turn parity, uninstrumented asynchronous
pressure, throughput, and ARC-quality tests remain required.

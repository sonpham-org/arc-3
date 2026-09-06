This is a diagnostic bundle for the isolated correctness probe. It is not a
numerical fix and has no throughput-valid results yet. Existing matrix profiles,
old candidate bundles, core scheduler, attention kernels and transfer backend
are unchanged.

The added helper records three linked observations:

1. After the current forward, immediately before STORE submission, it hashes
   every copied GPU storage page and the tensor owners of its cache group.
2. After STORE completion, before completion is returned to the scheduler, it
   checks CPU bytes against that original snapshot. The ledger retains the exact
   request IDs, cache key, group, token-boundary matches and store event.
3. After LOAD completion, before scheduler admission, it checks GPU bytes against
   the CPU source and semantic GPU state against the recorded original STORE.
   A missing origin is reported as missing coverage, never a successful check.

At new/finished request steps, a bounded watch also compares a sampled
   still-bound GPU checkpoint per group to its original semantic STORE snapshot,
   preferring the highest known token boundary. CPU/GPU
   block hashes must still match; rebound blocks are skipped without pinning them.
   `new_request_ids` marks a check after the first forward of that request;
   `finished_request_ids` is the prior scheduler-reported completion set. This
   is sampled evidence, not continuous monitoring of every checkpoint.

`QSA_RESUME_AUDIT` JSON log records distinguish full raw storage (padding and
shared aliases included) from semantic state (only the checkpoint group owners).
Main attention, compressed indexer, GDN, and PLE are included; noncacheable raw
circular indexer state remains excluded by the original completed-group contract.
Semantic slicing requires exactly one tensor axis equal to physical GPU block
count and fails explicitly if that layout is ambiguous.

Every readback is synchronous. This can alter transfer/compute scheduling and
mask an ordering race; compare an uninstrumented parity control under identical
model/backend/batching settings. These timings must not be used as performance
measurements. Equal bytes still do not prove equal logits, nor do they prove the
model's original checkpoint was computed correctly.

A complete provenance check requires every restored block's `load_origin` to
have `cpu_unchanged_since_store=true`, `semantic_exact=true`, and a non-null
`origin_store_event`, in addition to successful STORE and LOAD raw checks.
Compare the origin's request IDs with the intended producer: a checkpoint first
created by a resident repeat is a different experimental condition. Semantic
differences and missing provenance are logged without aborting so the numerical
probe can finish; its report must inspect these fields rather than treat HTTP
success or `load_raw_copy.exact=true` alone as a pass.

The committed candidate and manifest are sufficient for payload verification and
portable tests with `python -B runtime/test_resume_audit.py`. Re-running
`runtime/build.py` additionally requires the frozen parent directory
`qsa-cpu-aligned-bytecheck-r1/`, which remains outside this public checkpoint.
The manifest preserves the existing
five payload files and adds `common/qsa_resume_audit.py`, six payload files total.
Mount every `candidate/vllm/...` file to the corresponding installed `vllm/...`
path, read-only. Existing aligned scheduler and native PLE overlays remain
required. Runtime dependency hashes are taken from the parent policy, correcting
the parent manifest JSON's stale pre-alignment scheduler hash. No retention
overlay is silently added.

Limits: 2 GiB per transfer event; 256 new STORE / 256 new LOAD captures; existing
bytecheck still limits LOAD validation to 64 events; 128 watch steps with at most
16 groups each. CPU ledger slots are keyed by physical CPU block and cache hash;
eviction legitimately replaces the slot. An external CPU-cache reset clears
provenance only when no diagnostic transfers remain pending. A GPU-only prefix
reset preserves the CPU ledger.

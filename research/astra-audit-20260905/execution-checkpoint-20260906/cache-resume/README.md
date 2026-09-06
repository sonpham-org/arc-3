# CPU KV resume checkpoint

The aim is to park complete FlashNext/QSA sessions in CPU RAM and restore them without rebuilding long prefixes. Transfer correctness and model-output repeatability are separate gates.

## What passed

The frozen runtime instrumentation hashes both complete physical storage and the semantic tensors owned by each cache group. It records the producer request, cache key, token boundary, STORE origin, CPU slot, and restored GPU slot.

- At the 3,200-token boundary, all three v2 CPU restore requests verified 6 of 6 cache-group pairs.
- At 64,000 tokens, three restore requests each verified 44 of 44 pairs.
- At 129,600 tokens, three restore requests each verified 85 of 85 pairs.
- The two long cases therefore verified **387 of 387** source→CPU→GPU chains, with no sampled resident-checkpoint mutation.

This establishes exact transfer provenance for the serial instrumented fixtures. Synchronous readback can hide an ordering race, so it is not an asynchronous-safety or throughput result.

## Original numerical failure

The fixed-next-token gate failed for GPU-resident repeats, cold recomputations, and CPU-restored repeats at the unchanged `1e-4` probability tolerance. Because GPU-only cold and resident paths already fail, CPU transfer cannot be isolated as the cause.

The v2 trace completed with all requests bound. Every same-path repeat first differs at the output of `layer.3.self_attn.indexer`; selected logical inputs and PyTorch RNG fingerprints are equal. Its chosen index order changes while the per-row sorted multiset remains equal. Later QSA layers then change membership, consistent with the earlier ordering difference propagating through sparse-attention reduction. Cold versus resident paths have different full shapes and are interpreted separately.

## Ordering control result

The narrow control sorts the fully expanded QSA token-index rows in ascending integer order before sparse attention. At the 3,200-token boundary, all traced resident, CPU-restored, and cold repeats became internally identical. The comparator found no differing traced module or logits in any same-path pair, and every resident-to-CPU comparison was exact.

The long follow-up also passed the CPU-resume question. At cached boundaries 64,000 and 129,600, all six restored requests passed provenance, all 387 transfer chains matched, resident repeats were exact, and all 18 resident-to-CPU prediction pairs had identical next tokens and top-five log probabilities. Across all three boundaries the control verified 405 of 405 transfer chains and 27 of 27 resident-to-CPU pairs.

Long cold recomputation still failed the unchanged `1e-4` distribution gate. The greedy token remained equal, but top-five probabilities varied; at 131,072 the top-five token set also varied. This is outside the CPU restoration path, yet it means the conservative full probe still fails. The first long attempt timed out while tracing the 65k producer at 180 seconds; the preserved second attempt used the probe's pre-reviewed 600-second request limit without changing the numerical tolerance.

## Decision

The byte-transfer layer and serial text CPU-resume parity are accepted for the tested fixtures. CPU session parking remains **disabled for gameplay** until the ordering control passes multimodal/multi-turn parity, an uninstrumented asynchronous stress test, throughput measurement, and gameplay-quality validation. The ordering change affects floating-point reduction order, so matching resident and restored outputs does not establish unchanged ARC behavior. Cold-rebuild instability should be diagnosed separately; it is no longer evidence against the CPU copy itself.

## Reproducible material

- `runtime/`: source→CPU→GPU provenance instrumentation and six-file composed payload.
- `qsa-cpu-offload/probe/`: restore helper used by the fixed-next-token probe.
- `probe_first_token.py` and `probe_first_token_trace.py`: fail-closed numerical probes.
- `trace-candidate-v2/`: embedding-aware layer trace and the complete eight-file CPU composition.
- `trace-analysis/`: strict request/forward binding and first-difference comparator; 18 portable tests pass.
- `selection-order-candidate-r1/`: frozen ordering candidate, launcher receipts, source diff, and portable tests.
- `scheduler-alignment/` and `runtime-dependencies/`: pinned runtime inputs required by the diagnostic composition.
- `evidence/`: compact public evidence summaries, the ordering-control outcome, and the standalone synthetic CUTLASS result.

The launchers preserve the exact isolated configuration but still require the pinned model, container image, and base-source export. They never replace a running service automatically.

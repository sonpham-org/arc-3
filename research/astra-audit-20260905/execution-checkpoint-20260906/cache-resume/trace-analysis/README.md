# Layer-trace comparison and restart notes

This directory contains the local, read-only comparator for the next isolated
FlashNext trace. It does not launch services, read credentials, or change GPU
state. `analysis_complete=true` means every requested observation was bound and
analyzed; **it does not mean numerical equivalence or resume correctness**.

## Saved startup failure

The first trace profile, `trace-qsa-cpu-fp8-bytecheck-131072-22-trace1`, failed
before health at **2026-09-06 16:52:05 UTC**. No inference probe results or
gameplay were produced. The isolated diagnostic service was subsequently
stopped. Operational service and VM identities are intentionally omitted from
this public checkpoint.

Preserved log:
`../results/trace-qsa-cpu-fp8-bytecheck-131072-22-trace1/vllm.log`.
The traceback at lines 358–443 (use `rg`, because carriage-return progress
lines confuse PowerShell line slicing) follows:

`gpu_worker.compile_or_warm_up_model` → `gpu/warmup.py:330`
`worker_execute_model(prefill_output)` → model forward →
`qsa_layer_trace.begin` →
`RuntimeError('QSA trace currently supports token-ID text input only')`.

This was an instrumentation guard defect. Warmup uses normal attention metadata,
so testing only for missing metadata does not identify every warmup call.
More importantly, **real text requests also carry embedding inputs**:

- Pinned `gpu/model_states/default.py:67–89` always obtains `inputs_embeds`
  through the encoder runner even when there are no multimodal embeddings.
- `gpu/mm/encoder_runner.py:280–291` computes text embeddings and returns its
  preallocated buffer.
- FlashNext declares `requires_raw_input_tokens=True`, retaining raw IDs too.
- Its wrapper obtains deepstack input tensors whenever embeddings are present.

Skipping any call with `inputs_embeds` would silently skip real requests. The
correct narrow change accepts and hashes embedding tensors alongside raw IDs,
including explicit `IntermediateTensors.tensors` contents. Warmup calls remain
ordinary trace records and are excluded through request interval binding and
exact input/position hashes. The separate **trace-candidate-v2** implements this;
the frozen v1 payload remains unchanged.

Independent v2 review: all 16 portable tests passed; all eight composed payload
hashes and Python syntax were verified; policy dependency hashes equal the
manifest and pin the new helper. Reviewed standalone manifest:
`f2755bcd58acf69625e246a82590cb642efdf3b03bfad6bedb0696abd16a52c5`.
Reviewed CPU composition manifest:
`966b7a9d01f5994d0580468104f3147fa9fd3acdc4af8a20e5a7e42890afd56f`.
Check current files and the parent's launch receipt before treating a later run
as this exact configuration; this directory makes no live-state claim.

## Usage

From this checkpoint root, after collecting the complete byte-preserved server
log and the output of `probe_first_token_trace.py` into an external result
directory:

```powershell
python -B cache-resume/trace-analysis/compare_trace.py `
  --logfile <external-results>/<attempt>/vllm.log `
  --probe-report <external-results>/<attempt>/<probe-report>.json `
  --output <external-results>/<attempt>/trace-comparison-r1.json
```

An existing output file is preserved: choose a fresh result filename. Exit 0
means analysis coverage is complete; exit 1 means missing, malformed or ambiguous
evidence. Inspect `first_observed_difference` and logits equality separately.
The command reads at most 256 MiB per input, four MiB per trace line, 300,000 trace
events, three cases, and 16 request rows per case. These are diagnostic bounds.

Portable tests:

```powershell
python -B cache-resume/trace-analysis/test_compare_trace.py
```

The test log and historical SHA-256 receipt are stored beside this README.
That receipt binds the original private-tree README and negative-control bytes;
`provenance/raw-artifact-index.json` maps those source hashes to the sanitized
public copies. Frozen runtime and trace payloads are not modified by these tests.

Current portable coverage: 18 tests pass. The saved
`negative-control-startup-failure.json` deliberately combines the real failed-v1
server log with a previous valid probe report solely to exercise rejection of
missing trace forwards. It returns `no_traced_forward_records`; it is not a
matched live trace result. A completed v2 comparison is summarized in
`../evidence/resume-evidence-summary.json`; its raw report and log remain
outside this public repository and are bound by the provenance index.

## How binding works

The telemetry probe provides on each producer/next-token row:

- `request_id`, `request_started_utc`, `request_finished_utc`;
- `trace_log.start_offset` and `trace_log.end_offset`, measured in bytes;
- `server_log_same_file_and_nonshrinking` and underlying file identity evidence.

Offsets reflect the Docker log follower's buffered observations, not a flushed
trace fence. The comparator accepts only one complete matching forward wholly
inside that exact observed interval. It independently hashes the frozen prompt's
terminal token IDs and their absolute positions, supporting int32/int64 IDs and
one-axis or three-axis text MRoPE positions. Producer target-step, resident and
CPU-restored requests require the same one-token terminal forward; a cold
request may finish with a longer prefill chunk.

The comparator requires one begin/end/logits-input/logits-output record and
complete module input/output coverage matching the installed hook count. QSA
indexer hooks also require their selection fingerprint. It rejects duplicate
JSON keys, nonfinite JSON, duplicated request/forward bindings, rotated logs and
overlapping observed request spans.

V2 begin records must explicitly include their schema version and embedding
representation, typed embedding fingerprints (or explicit null), and typed
deepstack tensor maps (or explicit null). Missing fields cannot compare as equal.
The probe and each case must be completed, with two to five contiguous repeats
for each expected family: resident and cold, plus CPU-restored in CPU mode.
An interrupted or partially supplied experiment cannot satisfy analysis coverage.

If follower buffering places the final trace outside the recorded interval,
the request stays **unbound**, with a specific error. Do not widen intervals
until a repeated request happens to match. Second-resolution server log times
are too coarse to distinguish requests that can finish within 0.15 seconds.
Per-request UTC times are retained for manual evidence reconciliation. A later
improvement could use a bounded log flush fence before recording each end offset;
that would be a new explicitly reviewed telemetry change.

Warmup and every producer decode consume forward IDs. Size
`VLLM_QSA_LAYER_TRACE_MAX_FORWARDS` for the whole diagnostic before launch (the
reviewed helper permits up to 512); the default 128 can be exhausted by several
32-token producers plus repeats. Missing records after exhaustion stay incomplete.

## Comparisons and interpretation

The report compares the producer's target step with the first resident result,
same-category repeats, and the first resident result with CPU-restored and cold
results. Warmup forwards outside request spans are never assigned to requests.

For matching full tensor shapes and selected logical inputs, it identifies the
earliest differing decoder/submodule input or output. Delayed hyperconnection
tuples are included in full. The v2 embedding and deepstack fingerprints are part
of input equality. Physical block maps are reported separately because their
addresses can legitimately differ. Logical metadata coverage is selected, not
exhaustive; equal hashes do not establish equality of every effective cache input.

Cold-prefill and resident one-token activations have different full shapes.
Their layer hashes cannot be interpreted as a fault. The comparator marks that
path ineligible for direct layer comparison and compares only the selected
`logits_input`/`logits_output`. Cold-versus-cold repeats are directly comparable
when their shapes and selected logical inputs match.

For QSA, changed ordered selection with unchanged per-row sorted selection means
the selected multiset is the same. A different multiset narrows the location to
the indexer or its effective inputs; it does not alone prove unstable tie
breaking. A new deterministic ordering/top-k patch should follow measured
evidence, not precede it.

Full-logit hashes distinguish decoder/LM-head changes from downstream logprob
calculation. They report exact differences without magnitude; the existing
next-token probe supplies selected/top-five probability errors at the unchanged
1e-4 tolerance. CPU/CUDA RNG fingerprints are diagnostic; opaque kernels may have
state not represented by PyTorch RNG.

Synchronous CPU readbacks can hide races. No trace timing is a performance
measurement. A CPU provenance pass remains a separate result from numerical
repeatability; use `../analyze_resume_audit.py` for the former.

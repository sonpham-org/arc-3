# Trace v2: MRV2 embedding inputs

The v1 startup failure was in instrumentation, not inference or CPU cache restoration. The preserved log is `../results/trace-qsa-cpu-fp8-bytecheck-131072-22-trace1/vllm.log`: lines 365–400 show `warmup_kernels` calling a regular prefill and the trace rejecting embedding inputs. The saved stop record reports the owned diagnostic VM terminated at 2026-09-06 16:54:55 UTC; this local record was read, not refreshed by a cloud call.

The guard would also reject the intended text probes. In the pinned Python export:

- `vllm/v1/worker/gpu/warmup.py:330` calls the normal worker prefill with real attention metadata.
- `vllm/v1/worker/gpu/model_states/default.py:67–89` prepares embeddings even when no image encoder inputs are scheduled.
- `vllm/v1/worker/gpu/model_runner.py:1600–1647` preserves raw IDs for models declaring `requires_raw_input_tokens`.
- FlashNext declares that attribute at `vllm/models/qwen3_8_flash_next/nvidia/model.py:827`; its wrapper obtains deepstack buffers whenever embeddings are supplied (`:973–987`).

V2 still requires raw token IDs. It accepts supplied tensor embeddings and explicitly fingerprints `IntermediateTensors.tensors` for deepstack inputs. Begin events add `trace_schema_version: 2`, `input_representation`, `inputs_embeds`, and `deepstack_input_embeds`. Missing metadata still skips profiling. Metadata-bearing warmup is traced normally; request mapping must exclude forwards outside actual request intervals. The presence of embeddings is not a warmup or multimodal classifier.

No model computation changes. The model payload is byte-identical to v1. Only the helper and its hash in the separately composed CPU policy differ among the eight payloads. V1, the six-file CPU audit, and all old launchers remain untouched. All existing strict tracing limits and eager/noasync/single-rank constraints remain.

Validation at freeze time: 16 portable tests passed without Torch/GPU/cloud execution. Tests cover embedding content participation, the warmup/text representation, malformed containers, raw-ID rejection, profiling skip, unchanged hooks, forward limits and original guards. Every composed payload was syntax-checked and hash-verified; policy pins equal manifest dependencies. Re-running `build.py` requires the omitted frozen v1 trace manifest and pinned base `model.py` export; the committed payloads support hash and portable-test verification without them. A later live run started successfully and produced the completed comparison summarized in `../evidence/resume-evidence-summary.json`.

Frozen identities:

| Artifact | SHA256 |
|---|---|
| `qsa_layer_trace.py` | `00eb0d70c29d0765bba7aeac8697facb422eb3f3bcf6d9696e435ef9cb9ad54e` |
| `build.py` | `6c98ec8911dd8956501df4298ac688765a48d8e206db5b300de8176c8755b4cc` |
| `test_layer_trace.py` | `8e30f193f16f7a2389c586a92f05d8fb9dcb23ddef699e2605864ab32938863b` |
| `manifest.json` | `f2755bcd58acf69625e246a82590cb642efdf3b03bfad6bedb0696abd16a52c5` |
| `cpu-audit-composed/manifest.json` | `966b7a9d01f5994d0580468104f3147fa9fd3acdc4af8a20e5a7e42890afd56f` |

The separate launcher `../start_trace_server_v2.py` is prepared, SHA `acfd4fe494230d313d46607f8bc27f26ec8f4718f45f27313c1c01f6f44b8ed9`; eleven portable launcher tests pass. It binds `/opt/arc3/astra-probe/qsa-resume-correctness-r1/trace-candidate-v2/cpu-audit-composed`, its exact manifest SHA above and the explicit model/helper payload hashes. It preserves `.965`, context 131072, 22 sequences, batched tokens 6144, CPU cache16GiB, auto MoE, alignment and eager/noasync settings. Eight payloads plus PLE/scheduler remain readonly; the original model-image base is checked. The three explicit trace environment flags remain 1/1/128. A fresh `--attempt e1` creates `serving/trace-v2-qsa-cpu-fp8-bytecheck-131072-22-e1`. V1's manifest binding remains unchanged. Obtain a fresh owned-VM lifecycle/idle check before any separately authorized launch.

```text
python3 /opt/arc3/astra-probe/qsa-resume-correctness-r1/start_trace_server_v2.py
  --arm qsa-cpu-fp8-bytecheck --attempt e1
  --scheduler-alignment-fix --synchronous-eager --layer-trace --dev-cache-reset
  --resume-diagnostics /opt/arc3/astra-probe/qsa-resume-correctness-r1/trace-candidate-v2/cpu-audit-composed
  --resume-manifest-sha256 966b7a9d01f5994d0580468104f3147fa9fd3acdc4af8a20e5a7e42890afd56f
```

The comparator must include both new embedding fields when judging effective input equality. Their absence must not be interpreted as equality for a v2 forward. Fingerprints still cover selected state only; warmup/trace overhead makes timing unsuitable as a throughput result.

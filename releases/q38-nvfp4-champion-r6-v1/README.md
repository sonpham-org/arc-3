# Qwen3.8 NVFP4 champion R6 — hermetic release

This release preserves the exact code and launch contract behind GCP run
`g4run-q38-cap8-ce-think-nvfp4-wmgpu-r6-20260821-014307`, whose 25-game mean
was **7.9424**. The champion used the original flawed/soft per-call checkpoint-8
behavior, the original six-entry persistent world-model curator, gameplay
temperature `1.0`, `top_p=0.95`, `top_k=20`, concurrency `28`, and a 7,920-second
gameplay window. It did **not** use PLU2.

The champion is one stochastic realization, not a deterministic expected score.
Exact GCP replicas R2 and R3 scored 6.4529 and 6.4600. The three-run mean is
6.9518 and the median run is 6.4600.

## What is locked

- GCP instance-template metadata, exact startup/shutdown scripts, and immutable
  GCS object generations.
- The full source/deployment bundle, runner, curator, and exact `arc-agi` 0.9.8 /
  `arcengine` 0.9.3 wheels.
- Model revision and every model-package SHA-256.
- The 195-wheel vLLM serving closure and its lock/manifest/archive hashes.
- Sampling, context, concurrency, curator, and deadline settings.

Run `python tools/verify_release.py` before using the release. Run
`python tools/snapshot_from_gcp.py` only to reconstruct the content-addressed
artifacts from their generation-qualified GCS objects.

## Kaggle strategy

Kaggle should receive a versioned **source dataset** containing the exact source,
pickles, setup code, curator, engine wheels, compiler overlay, and manifests. The
notebook should be a thin loader. Every input is verified by SHA-256 before import
or execution, and the notebook must attach explicit dataset/model versions.

This is materially more stable than copying code into notebook cells or installing
unpinned packages. It does not make Kaggle bit-identical to GCP: Kaggle controls the
host driver, GPU model, filesystem, scheduler, and base notebook container. The
reference Dockerfile documents and tests the userspace closure; Kaggle notebooks do
not execute an arbitrary user Docker image.

Two parity bugs found in Kaggle V23 are fixed in the release builder:

1. V23 forced vLLM `--linear-backend cutlass`; GCP used the default `auto`.
2. V23 initially installed unpinned `arc-agi` from the competition wheel directory;
   the release installs and hashes the exact champion engine wheels.

The first 25 initial gameplay requests from GCP R3 and Kaggle V23 otherwise match
after removing the curator timestamp. Both runs completed 31 levels, so V23's lower
score was not caused by a different public game set or a simple throughput collapse.

## Files

- `CHAMPION_LOCK.json` — machine-readable release contract.
- `artifacts/` — exact small source/runtime artifacts reconstructed from GCP.
- `gcp/` — exact template and scripts.
- `kaggle/` — corrected setup and a dataset builder.
- `Dockerfile.reference` — reproducible userspace audit image, not a Kaggle BYOD mechanism.
- `tools/verify_release.py` — fail-closed artifact and semantic verifier.
- `tools/audit_request_parity.py` — normalized GCP/Kaggle request comparator.


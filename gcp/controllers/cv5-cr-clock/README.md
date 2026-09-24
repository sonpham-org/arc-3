# cv5-cr-clock — compaction-v5-clean-return at 264/396 min, and hard-seven-only

Clock-lifting controller for the 19-Sep `compaction_v5_clean_return_a` arm. Source arm files
(candidate.tgz, selftest.tgz, probes, instance body) are the GCS objects in the arm's
`deployment.json`; blobs are not committed.

- `derive_396.py`  — `ARC3_SUITE_MINUTES=264|396`: lifts the clock in all six pinned places
  (runner, runtime_probe, CONFIG_FLAGS/config_id, selftest bundle constants + manifest env,
  ADAPTER effective-runner hash, startup pins incl. sampler cap 18000).
- `derive_hard7.py` — same, plus `ARC3_GAME_SUBSET` = the hard seven, 7 games, one wave,
  game_seconds = suite*60.
- `verify_396.py`   — local preflight mirroring every `sha256sum -c`, cross-check and bound the VM
  enforces. Run with `ARC3_ARM_NAME=<arm>`; exit 0 before launching. It exists because attempts 1-3
  of the 396 run each died to a pin discovered one VM at a time.
- `launch_396.py`   — Spot `g4-standard-48` from the golden Flash-Next image. On-demand is refused
  (`GPUS_PER_GPU_FAMILY` limit 0).

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

## Five intensive-harness arms on the hard seven (24-Sep)

`derive_arms.py execution|memory|symbolic|solver|selfcheck` builds one arm each: 7 lanes x 7 hard games,
one wave, 7920 s per game (the whole 132-minute clock), from the same 19-Sep base.

| arm | what it is | how |
|---|---|---|
| execution | the ablation paper's verification stack: predeclared `expected_next` checked against the observed frame, mismatch leaves the lease | contract arm `execution` (memory implied), `execution_version=memory_lease_e2` |
| memory | simpler: semantic memory only | contract arm `memory` |
| symbolic | simpler executable world model: declarative scalar-state model, CPU search, validated on observed transitions | contract arm `symbolic` (memory implied), `symbolic_version=v2` |
| solver | act toward the goal; loop/world-model/priors/transition/coordinate prompt surfaces deleted | prompt ablations SEARCH+LOOP+PRIORS+TRANSITION+COORDS; `prompt_probe` count 5 |
| selfcheck | model writes `expect(check)` before every action; host runs it on the real transition and a no-op counterfactual; trivial/failed checks halt the batch | `patch_selfcheck.py` (three constant-only edits), full manifest + `source_sha256` cascade |

Single-switch env semantics matter: `feature_contract.environment(arm)` sets only the arm's own flag,
the agent implies memory for execution/symbolic, and `contract.validate` forbids an env override that
contradicts a flag -- so implied features are OMITTED from `extra_environment`. `verify_396.py` checks
all of it, including that `EXPECTED_PROMPTS.json` equals a fresh local render of the arm's own
candidate under the arm's env (the renderer reproduces the shipped attestation byte-for-byte).

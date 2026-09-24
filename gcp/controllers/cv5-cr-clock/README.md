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

## 24-Sep additions

- **vLLM watchdog** (`watchdog.py`, wired into all three derives): the first hard7-264 run
  (`…-d85c029903`) lost its engine at minute 31 (`RPC call to sample_tokens timed out` → EngineDeadError)
  and the harness spun for hours at a frozen 0.48. Every startup now probes `/v1/models` each 60 s; after
  3 misses it snapshots `vllm.log` to `vllm-crash-N.log`, restarts the container with the startup's own
  `start_server`/`wait_server`, and records `SERVER_RESTARTS` in the run bucket. Teardown kills it.
- **selfcheck gate**: the bundled selftests (`linux_selftest_matrix.py`, `test_action_cap_modes.py`) drive
  `action()` bare, so the `expect()` requirement is read from `ARC3_PREDICTION_CHECK=1`, which the startup
  exports only immediately before `capture_gameplay_metrics start` — after every selftest. Two launches
  died before that placement was right (`…-ff95ec12d4` at the matrix, `…-770663a914` at the action-cap
  test).
- **Generalised clock lift**: `derive_396.py` / `verify_396.py` take `ARC3_SRC_ARM=<path to any 132-min
  arm of this family>` and `ARC3_ARM_TAG=<prefix>`; used for LA-CR at 264
  (`ARC3_SRC_ARM=…\la-clean-return132-20260921\arms\la_clean_return_a ARC3_ARM_TAG=lacr`).
- **v2 arms** (`patch_v2.py`; `derive_arms.py execution_v2|memory_v2|symbolic_v2`): same flags as the arm
  above each, plus a host-persistent **per-game code store** (`store`, `save(**fields)`; `save(code=src)`
  runs now and at the start of every later snippet, keyed by the game's runtime dir in
  `python_tool_sandbox._CODE_STORES`) and one executable, history-replayed primitive:

  | arm | primitive | gate |
  |---|---|---|
  | execution_v2 | `verify(predict)`: replays `predict(before_frame, action) -> grid \| cells \| None` over every recorded transition; with a saved `predict` each action is auto-checked and a mismatch halts the batch | batches > 1 need fidelity ≥ 0.8 on ≥ 3 transitions |
  | memory_v2 | `rule(id, text, holds)`: predicate source over one transition, replayed over the whole history at every snippet start; first `False` revokes the rule and names the counterexample; `rules()`, `drop(id)` | none (rules cannot survive contradiction) |
  | symbolic_v2 | `encode(frame)`/`step(state, action)` as plain Python; `replay()` fidelity; `plan(goal, max_depth, actions)` bounded BFS from the current state; actions auto-checked against the model | same as execution_v2, from `replay()` |

  The batch gate is enabled by `ARC3_V2_BATCH_GATE=1`, exported at the same post-selftest point as the
  selfcheck flag. Smoke-tested locally against a fake host (`smoke_v2.py`: store persistence,
  verify/replay fidelity, plan, mismatch halt, gate cut).

Run ids (24-Sep): hard7-264 v2 `g4run-cv5cr-hard7-264-w7-20260923-7c19c6eb63`; LA-CR 264
`g4run-lacr264-w7-20260923-8367f8ff09`; flag arms execution `…-ce7843057b`, memory `…-d5d8b2be9d`,
symbolic `…-5aac84d4fc`, solver `…-92b391fd79`, selfcheck `…-e58ade7fe2` (3rd launch); v2 arms
execution_v2 `g4run-cv5cr-hard7-execution_v2-132-w7-20260924-2d16389920`, memory_v2
`…-memory_v2-132-w7-20260924-002d497d5a` (both europe-west1-b: us-central1's Spot quota is 8 RTX PRO 6000
GPUs per region and 8 VMs were live), symbolic_v2 `…-symbolic_v2-132-w7-20260924-cd5dccf7c5` (europe-west1-b, second launch after quota/backendError refusals).

## 25-Sep: three bases on the hard seven, and replicates

`derive_hard7.py` now takes `ARC3_SRC_ARM` / `ARC3_ARM_TAG` like `derive_396.py` and accepts
`ARC3_SUITE_MINUTES=132`. Launched 25-Sep 02:50-03:05 UTC, all us-central1-b Spot:
CR hard-7 `g4run-cr-hard7-132-w7-20260924-f891a5f749` (clean_return_repeat132), LA-CR hard-7
`g4run-lacr-hard7-132-w7-20260924-b145353fd8` (la_clean_return_a), and replicate #2 of the cv5-CR arms:
baseline `…-2d74687abe`, solver `…-cfff61d568`, execution `…-51409afc9f`, symbolic `…-7494b2c061`,
selfcheck `…-5e78468d87`. Replicate #1 finals (7-game mean / levels): solver 9.13/17, exec 8.32/19,
symbolic 8.29/14, selfcheck 7.70/16, memory_v2 6.70/14, baseline 6.40/15, symbolic_v2 5.93/15, memory
5.46/12, hard7-264 4.96/15, execution_v2 4.47/11. CR264 replicate `g4run-cr264-w7-20260924-969f751ea3`.

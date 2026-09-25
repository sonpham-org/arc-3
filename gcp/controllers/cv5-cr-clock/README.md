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

## Hard seven, one wave, per game (score / levels / actions) — replicate #1, 24-Sep

Games: bp35, g50t, lf52, ls20, sk48, tn36, wa30. Mean is over the seven. Source: each run's `runs/summary.txt` in the bucket.

| arm | run id | bp35 | g50t | lf52 | ls20 | sk48 | tn36 | wa30 | mean | levels | actions |
|---|---|---|---|---|---|---|---|---|---|---|---|
| solver | `…-92b391fd79` | 10.0 / 3 / 286 | 9.2 / 2 / 470 | 5.2 / 3 / 514 | 2.4 / 2 / 583 | 0.0 / 0 / 917 | 25.6 / 4 / 275 | 11.4 / 3 / 821 | **9.13** | 17 | 3866 |
| execution | `…-ce7843057b` | 2.7 / 2 / 193 | 8.8 / 2 / 373 | 4.1 / 3 / 400 | 2.7 / 2 / 598 | 2.8 / 1 / 172 | 22.1 / 5 / 280 | 15.0 / 4 / 841 | **8.32** | 19 | 2857 |
| symbolic | `…-5aac84d4fc` | 7.4 / 3 / 258 | 10.7 / 2 / 645 | 1.8 / 1 / 385 | 29.0 / 4 / 399 | 0.2 / 1 / 312 | 3.6 / 1 / 657 | 5.3 / 2 / 803 | **8.29** | 14 | 3459 |
| selfcheck | `…-e58ade7fe2` | 2.2 / 2 / 163 | 17.9 / 3 / 493 | 10.4 / 3 / 242 | 3.6 / 1 / 550 | 2.8 / 1 / 88 | 3.6 / 3 / 465 | 13.3 / 3 / 711 | **7.70** | 16 | 2712 |
| memory_v2 | `…-002d497d5a` | 2.9 / 2 / 239 | 1.9 / 1 / 202 | 6.7 / 4 / 442 | 0.1 / 1 / 621 | 0.6 / 1 / 156 | 32.5 / 4 / 297 | 2.2 / 1 / 592 | **6.70** | 14 | 2549 |
| baseline (control) | `…-b4b6f26359` | 0.5 / 1 / 955 | 15.8 / 3 / 479 | 3.1 / 3 / 568 | 6.2 / 3 / 694 | 0.0 / 0 / 127 | 17.3 / 3 / 363 | 1.9 / 2 / 946 | **6.40** | 15 | 4132 |
| symbolic_v2 | `…-2093ec726b` | 1.2 / 2 / 337 | 9.2 / 2 / 488 | 1.8 / 1 / 460 | 8.9 / 3 / 427 | 0.1 / 1 / 275 | 4.5 / 2 / 427 | 15.8 / 4 / 660 | **5.93** | 15 | 3074 |
| memory | `…-d5d8b2be9d` | 8.2 / 3 / 206 | 10.7 / 2 / 609 | 1.8 / 1 / 438 | 2.4 / 1 / 712 | 0.0 / 0 / 182 | 10.7 / 2 / 712 | 4.4 / 3 / 833 | **5.46** | 12 | 3692 |
| base @264 min/game | `…-7c19c6eb63` | 2.0 / 3 / 970 | 0.0 / 0 / 1060 | 7.4 / 3 / 799 | 0.0 / 1 / 1032 | 0.0 / 0 / 1397 | 8.2 / 4 / 1002 | 17.0 / 4 / 975 | **4.96** | 15 | 7235 |
| execution_v2 | `…-2d16389920` | 0.8 / 1 / 281 | 18.5 / 3 / 329 | 9.2 / 4 / 470 | 0.5 / 1 / 285 | 2.2 / 1 / 123 | 0.0 / 0 / 1315 | 0.0 / 1 / 775 | **4.47** | 11 | 3578 |

Replicate #2 of baseline/solver/execution/symbolic/selfcheck and the CR / LA-CR hard-seven arms (x2) launched 25-Sep 02:50-03:12 UTC; ids above.

## 25-Sep: replicate #2 finals, solver on all 25 / at 264, medium thinking

Hard seven, one wave, 132 min (7-game mean; run #1 / run #2): symbolic 8.29 / 6.46, solver 9.13 / 4.73,
LA-CR base 9.04 / 4.55, CR base 4.75 / 8.43, selfcheck 7.70 / 4.94, exec 8.32 / 4.03, cv5-CR base 6.40 / (#2 pending).
The field sits at 6.2–7.4 with ±2 per run; only symbolic has both runs above the field.
`derive_arms.py` gained `--all25` (25 games, 4 waves) and `--effort low|medium|high|xhigh` (Qwen3.8
chat-template `reasoning_effort`, default xhigh). Solver on all 25 at 132: `g4run-cv5cr-all25-solver-132-w7-20260924-46cfc490f5`
= 12.82 / 52 levels (same as the cv5-CR base; LA-CR 18.6). Solver at 264 per hard game:
`g4run-cv5cr-hard7-solver-264-w7-20260924-ffdda82394`. cv5-CR with medium thinking on all 25 x2:
`g4run-cv5cr-all25-baseline-132-effortmedium-w7-20260924-5d764adf5b`, `…-69794c6c30`.

## 25-Sep finals: thinking-effort ladder, baseline #2, solver at 264

| run | mean (25) | hard-7 subset | levels |
|---|---|---|---|
| cv5-CR base 132 (19-Sep, reference) | 14.56 | 4.93 | 58 |
| cv5 medium thinking `…-5d764adf5b` / `…-69794c6c30` | 8.97 / 8.31 | 3.75 / 2.15 | |
| cv5 high thinking (served template, milder sentence) `…-efforthigh-…-5a2a560f32` / `…-4f3ecf36cb` | 13.70 / 13.52 | 1.48 / 2.38 | 52 / 50 |
| LA-CR high (serving-variants `effort_high`) `…-43f09d9403` / `…-222698fd16` | 10.85 / 15.14 | 2.74 / 3.16 | |
| LA-CR xhigh (21-Sep a/b, reference) | 18.01 / 19.24 | 3.53 / 3.85 | |

Every reduction of thinking effort loses: medium costs about 6 points, high 1 to 8. xhigh (the template default)
stays. Hard seven one wave: cv5-CR baseline control #2 `g4run-cv5cr-hard7-baseline-132-w7-20260924-755fe2ab48` = 6.49
(tn36 4 levels) beside #1's 6.40. Solver at 264 per game `…-ffdda82394` = **9.86 / 19 levels** (tn36 36.5 with 6 levels,
g50t 12.95) against 4.96 for the cv5-CR base at 264: the solver prompt benefits from the doubled clock where the base
does not. The minute-score observer under-reported both this run (2.76 at min 253) and act #2 (1.80 at min 124 vs a
final 6.42): treat observer curves as lower bounds late in a run.

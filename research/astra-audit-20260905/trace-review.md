# What Astra's public ARC-3 replays suggest for our harness

Reviewed September 5, 2026. This is a trace and source review; no model inference or production configuration changes were made. The main model's GPU allocation and KV-cache capacity remain fixed constraints.

The strongest finding is that carrying a useful game model forward can save substantial repeated reasoning. This supports testing durable state and plan-aware execution before adding another model. It does not establish that the same change will make Qwen match Astra.

## A matched example with actual token counters

Both runs below use Astra at **max** reasoning on the same public S5I5 environment. Both complete eight levels without a reset.

| Recorded measure | Standard | Provider Adapter |
|---|---:|---:|
| Actions | 242 | 243 |
| Completion tokens, including reasoning | 210,649 | 36,706 |
| Reasoning-token subset | 186,683 | 33,790 |
| Median completion tokens per action | 482.5 | 32 |
| Recorded elapsed time | 90.70 min | 38.66 min |
| Input tokens summed across calls | 37,751,202 | 30,266,170 |
| Cached input tokens | 1,870,954 | 20,923,334 |

The adapter logs **82.6% fewer completion tokens** despite taking one more action. Most of the saving is in reasoning tokens. Its eight first actions of a level consume 18,074 completion tokens, about 49% of its total; the other 235 actions have a median of 31. All 243 visible final responses contain only an action.

Sources: [Standard replay](https://arcprize.org/replay/39d9f100-328a-4121-ad81-ce298e1f9626), [Provider Adapter replay](https://arcprize.org/replay/7609fe46-64be-4d12-b100-81733da7c768). These are individual runs, not an isolated causal ablation. Their elapsed times include service, queue, environment and compaction time.

A second matched max-effort pair, WA30, shows an outcome difference as well:

| Recorded measure | Standard | Provider Adapter |
|---|---:|---:|
| Levels completed | 8/9 | 9/9 |
| Actions | 1,032 | 557 |
| Resets | 6 | 0 |
| Logged completion tokens | 1,400,933 | 73,048 |
| Reasoning-token subset | 1,292,396 | 68,592 |
| Recorded elapsed time | 721.67 min | 91.02 min |

The Standard recording has 1,031 usage-bearing records versus 1,032 reported actions: action 766 is a RESET without usage. These are sums of exposed counters. The adapter has 557 usage-bearing records, 62 returned compaction items and action-only final output throughout. [WA30 Standard replay](https://arcprize.org/replay/be78fcef-1244-4cf8-b680-0a5e4e8f9afe), [WA30 Adapter replay](https://arcprize.org/replay/49ac7afb-b83a-46f4-bb1e-3ecc902ca291).

WA30 also supplies a useful caution. In the Standard run, action 343 chooses a pickup side to preserve cargo offset through a narrow passage; action 701 tracks player orientation, cargo offset and an autonomous helper. After a timing failure, action 837 moves the helper handoff earlier in the plan. However, action 1023 still corrects a mistaken assumption about valid goal regions. Detailed memory is valuable, but can preserve a wrong model. Store confirmed observations separately from hypotheses. UI replay frames corresponding to those actions are 347, 708, 844 and 1030.

## Behaviors worth transferring

**Represent the controllable mechanism.** In S5I5, the early notes identify a three-pixel movement increment after one probe and track remaining clicks. Later notes describe rods through lengths and orientations, map controls to coordinates, and maintain ordered subgoals. A complicated image becomes a small set of variables and constraints. The useful product is the representation, not a prescribed notation.

**Spend reasoning when the problem changes.** The adapter's token distribution is consistent with substantial planning at new levels and inexpensive execution afterward. This supports the proposed investigation/execution modes, with a route back to investigation when observations contradict the plan. It does not support disabling reasoning for every move or blindly executing a long sequence.

**Keep the unfinished plan through compaction.** The S5I5 adapter returns 27 compaction items. Its public logs expose counters and occasional readable reasoning summaries; they do not expose the complete encrypted reasoning or compacted state. Short final actions therefore do not imply that no plan or reasoning was retained.

**Use a smaller spatial model.** In the TU93 adapter replay, the first readable summary maps the 64-pixel board into a 6-by-6 node graph. Later summaries track directions, enemy behavior and remaining route steps. That run completes all nine levels in 191 actions, with 41,193 logged completion tokens. It uses the ordinary provider adapter, not a generated Python maze solver. [TU93 replay](https://arcprize.org/replay/7c54faff-3875-43f3-8a06-ca25720b32c8).

## What the harness comparison does and does not establish

At the same high effort, the published Semi-Private scores are 54.82% Standard and 99.95% Provider Adapter. This is distinct from the public examples above and from Kaggle scoring. [Official results](https://arcprize.org/results/openai-gpt-6-astra).

The current public source implements Standard as visible rolling history and Provider Adapter as native response-item preservation plus provider compaction. The latter does not add a code interpreter or game-specific solver. The blog's examples of generated solver files belong to a separate PRO-LONG evaluation. [Provider source](https://github.com/arcprize/arc-agi-3-benchmarking/blob/1aa78da7e3058e0ead572ede7cd97065d1e5befc/benchmarking/openai_runtime.py), [ARC analysis](https://arcprize.org/blog/astra).

The comparison changes several context-management behaviors together. It does not prove the separate contribution of compaction, reasoning retention, visible-note requirements or caching. The inspected repository has Sol example configurations but no exact Astra configuration at the pinned revision.

## Priorities for our 108k generated-token budget

1. **A durable game-state record:** retain confirmed rules, uncertain rules, current state, goal, pending plan and its position across rotation. Update it during existing planning calls; store it on CPU. Preserve game-wide rules when a level ends, while replacing level-specific state. Attach observations or transition indices to claims so a failed hypothesis can be revised.
2. **Plan-aware execution:** use the existing action-only/no-new-thinking proposal after a plan is established. Require a short expected result and an explicit way to resume investigation. Evaluate reasoning-token savings and actual successes, not only output length.
3. **Audit eviction and observation accounting:** the inspected local candidate estimates serialized payload characters divided by three, including image data, and deletes old history blocks. Calibrate that estimate against server-reported prompt usage and examine what knowledge is lost at rotation. Test image retention separately from changes to reasoning or rules.

These require no second GPU model and no reduction in the main allocation. Our local baseline/candidate already attempts to preserve reasoning text and already supports explicitly saved helper functions. The remaining question is whether the needed facts, data and pending plan survive rotation. Server acceptance of the outgoing reasoning field should be verified, not assumed broken.

The audited candidate has **not** been established as the exact score-13 baseline. Any eventual ablation must be applied to the baseline identified by the runs task, with fixed GPU settings and the same game/token/time budgets.

## Limits and reproducibility

The readable public material consists of decision notes, reasoning summaries, actions and usage counters. It is not the full private reasoning state. Some summaries are generic or absent even when substantial reasoning tokens are recorded; they should not be copied uncritically as training targets.

The adapter S5I5 run has a median input context of 125,793 tokens and a maximum of 195,231. TU93 reaches 264,495 input tokens. Our 32k context cannot retain an equivalent raw history. The practical transfer is compact, verifiable state, not simply keeping everything.

Raw public recordings, session metadata, frame mappings and source snapshots are retained under `work/astra-trace-review/` in the originating local task workspace, outside this repository. The accompanying [replay-metrics.json](replay-metrics.json) records computed counters, source URLs and SHA-256 hashes for five recordings. Usage is summed once per action record when exposed, including RESET usage when present; reasoning tokens are already included in completion tokens. Input totals count repeated/cached inputs. Zero-valued cost fields are not treated as actual prices. See [reproduction notes](README.md#provenance-and-reproduction) and the [context and memory follow-up](context-memory-options.md).

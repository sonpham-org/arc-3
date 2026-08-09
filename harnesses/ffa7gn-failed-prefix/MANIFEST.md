# ffa7gn-failed-prefix

- Derives from `ffa7gn` (`ffa7g-full-stack.patch`, state graph disabled).
- Single mechanism: record the action-plus-settled-state trajectory that ends
  in `GAME_OVER` or deliberate `RESET`. On a retry, checkpoint every six exact
  prefix transitions while the retry remains identical to that failed attempt.
- The mechanism does not reject shared setup and disables itself immediately
  when the retry reaches a different transition.
- Bundle: `bundle-v12ffa7gn-failedprefix-20260809.tgz`.
- Evaluation: official 25 games, two independent Spot runs on the exact
  vrfai/Qwen3.6-27B-FP8 + vLLM 0.19 model-side baseline.

## Validated result

| pass | all-25 mean | ex-`ft09` | `ft09` | positive games | levels | actions |
|---|---:|---:|---:|---:|---:|---:|
| p1 | **2.8489** | 1.3550 | 38.7019 | 13/25 | 18 | 2,596 |
| p2 | 1.7791 | 1.2580 | 14.2857 | 15/25 | 17 | 2,593 |
| pair mean | **2.3140** | **1.3065** | 26.4938 | — | 17.5 | 2,594.5 |

The p1 raw all-25 score is the highest observed local public-set run so far,
but it is not a robust global improvement: `ft09` supplies most of the lift.
The historical ffa7gn control pair scored 1.624 ex-`ft09`, so this variant is
about 19.5% lower on the less outlier-sensitive metric. Preserve and publish
the traces, but do not promote failed-prefix to the submission default without
more evidence or a narrower diagnosis of its `ft09` benefit.

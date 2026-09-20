# Canonical growth-pool glow-up rubric v3

Approved by Son Pham, 14 September 2026. Existing fidelity and pair-distance
scales and gates are retained. Quality Control is added as a separate gate
after 12-dimension differentiation; it is not averaged into either score.
See `glowup-quality-control-v1.md` for the complete approved protocol.
Apply the subsequent user-approved `glowup-recovery-policy-v1.md`; a finite losing
path is no longer mandatory, and forgiving exploration is a separate QC gate.

## Fidelity score (100)

| Dimension | Points |
|---|---:|
| Play feel and immediate causal feedback | 14 |
| Meaningful choices and core-loop quality | 14 |
| Seven-to-twelve-level progression | 14 |
| New mechanics that compose rather than replace | 10 |
| Legibility and accessibility | 12 |
| Visual craft, motif detail, and silhouette variety | 12 |
| Animation and state continuity | 10 |
| Coherent identity and emotional register | 8 |
| Restart, recovery, and replay quality | 6 |

A game passes at 84/100, with no dimension below 60 percent.

Hard quality gates:

- Ship 7-12 real levels. Levels 2-6 introduce components, rules,
  representations, constraints, uncertainty, counters, simulation laws, or
  control changes rather than count or budget inflation.
- At least two late levels compose three or more earlier demands. No more than
  two consecutive levels may be larger instances of the same task.
- Every consequential action has anticipation or selection, an attributable
  event, and a settled deterministic state. Win, loss, reset, blocked input,
  and level transition are distinct.
- Critical state is encoded by at least two of shape, pattern, position,
  count, value, or motion. Required text, digits, cultural knowledge, audio,
  flashing, hidden gestures, twitch timing, and motor precision are forbidden.
- Physics uses exact steps or quanta. Uncertainty is reducible by informative
  action. Strategy uses simultaneous or interleaved fronts rather than a large
  board alone. Counter systems are asymmetric in consequences. Large
  consequences are previewable and causally readable.
- Every accepted mechanic addition appears in progression, composes later, and
  fails an explicit necessity counterfactual when removed.
- Known win and recovery traces, loss traces only where applicable, deterministic resets, double
  replay, source hashes, schema, fuzzing, and exact random-policy resistance
  below 1/10,000 for Levels 2+ pass after every edit.
- Ordinary exploration must be recoverable. Any retained terminal loss needs a
  clear cause, visible remaining lives/resources and an easy current-level retry.
  Test plausible mistakes and preserve completed levels; follow the recovery policy
  for evidence and the evaluation horizon when play permits unlimited retries.
- A verifier must fail under at least one deliberate rule-breaking mutation.

## Pair distance score (100)

Score each axis from 0 (same template) to 4 (strong opposites), then apply the
existing weight.

| Axis | Weight |
|---|---:|
| Core verb | 12 |
| Controlled subject: avatar, object, field, network, or world | 8 |
| Temporal cadence and commitment model | 8 |
| Spatial topology and camera grammar | 8 |
| Information and objective structure | 8 |
| Silhouette family | 10 |
| Composition, density, and scale | 8 |
| Palette architecture | 10 |
| Texture, material, and realism | 8 |
| Motion and effects grammar | 10 |
| Emotional tone | 5 |
| HUD and feedback style | 5 |

The pair passes at 78/100. At least eight axes score 3 or 4, including a
gameplay axis, a visual axis, and a temporal or motion axis at 4. Palette
distance covers at least three of hue, value, saturation, count, temperature,
and texture.

Supplemental difference gates:

- Record control modality, map substrate, action consequence radius,
  simulation regime, uncertainty model, conflict/counter structure, and
  solution structure even when they are folded into the 12 scored axes.
- Each game has at least one exclusive meaningful mechanic and the primary
  mechanic sets are not identical.
- Weighted mechanic overlap is at most 0.65 unless a documented operational
  inversion makes a shared mechanic causally different.
- A hexagonal map differs only when six-neighbor topology is real; decorative
  texture cannot satisfy topology distance.
- A hue swap, more particles, a renamed character, or a different background
  cannot satisfy the gate without gameplay and structural separation.

## Quality Control gate

Apply to both games after pair differentiation and before final qualification
and activation. Preserve the initial and revised mechanics summaries and
Level 1 instructions. Score each from 0 (simple English) to 1 (slop).
Two fresh independent reviewers score both texts; the maximum of the four
final scores must be at most 0.20. Missing or false rules are an automatic
failure regardless of score.

Test Level 1 with a fresh novice using the normal game screen and controls,
without the explanation, source, winning trace, or author coaching. Required
targets: meaningful action within 60 seconds and a win within five minutes,
with exploration and restarts permitted, followed by a simple explanation of
the action's consequence and why it won. Record all observations and failures.

If simple accurate English or cold-start play fails, repair the game and test
again. At most two wording-only revisions precede mandatory design diagnosis.
Level 1 can be easy; retain the Level 2+ random-resistance gate and later depth.
Any game change returns to pair-distance review and QC before qualification.

Record `fail`, `provisional_pass` (simulated screening only), or
`human_confirmed` (actual novice play observed). A simulated pass may proceed
to qualified activation under the approved automatic workflow, but cannot be
reported as evidence that a real human passed. Observed human failure reopens
QC. A failing game prevents activation of the pair.

Neither fidelity nor distance can compensate for failed QC. Preserve exact
versions/hashes, before/after descriptions and scores, tester type, timing,
actions, restarts, help, paraphrase, design repairs, and retest evidence.

## Review and coverage gates

Use at least five independent simulated perspectives before discussion,
including accessibility, first-time or bilingual child, Flash veteran,
systems designer, and animation/VFX or cross-cultural art. Also prefer an
older casual player and exploit hunter. Require median fidelity and pair
distinctness of at least 4/5 and no accessibility score below 3/5. These are
adversarial design aids, not human playtesting.

Selection uses the minimum explicit `glow_up_count`, not version order alone.
Only a fully qualified glow-up activation increments the count. QC maintenance
has a separate count. When every active concept has glow_up_count >= 1, add
ceil(current_pool_size * 0.20) genuinely new seeds before drawing another pair.

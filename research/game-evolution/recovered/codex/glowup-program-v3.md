# ARC3 perpetual glow-up program v3

Approved for execution by Son Pham on 14 September 2026. The initial
44-game Quality Control batch must finish and be committed before ordinary
pair sampling resumes. The same day's fresh-context agent requirement applies
to this batch and every subsequent pass.

Companions: `glowup-rubric-v3.md`, `glowup-quality-control-v1.md`, and
`glowup-agent-isolation-v1.md`. The subsequent user-approved simplification rule in
`glowup-recovery-policy-v1.md` applies to the unfinished batch and all future passes.

## Cadence and atomicity

- Begin a pass every 90 minutes.
- Never overlap passes in one worktree. A heartbeat that finds an unfinished
  pass resumes it and does not draw another pair.
- Each completed pass glow-ups both selected games into immutable new versions.
- Commit each qualified revision and its evidence locally. Local commits are
  authorized by the restart request. Push, publish, deploy, Kaggle submission,
  and GCP execution remain outside this authorization.

## Coverage state

`research/glowup-game-stats-v1.json` is rebuilt from the canonical manifest,
metadata, and completed loop history. For every active concept it records the
current version, origin, `glow_up_count`, `attempt_count`, last sample and glow
times, and mechanics. A glow-up counts only when a new version passes every
gate and becomes active. An abandoned or reverted attempt increments attempts
but not glow-ups.

Selection is lexicographic, not popularity-weighted:

1. refuse to sample while a prior history item is unfinished;
2. find the minimum `glow_up_count` among active concepts;
3. exclude the ten most recently sampled concepts when possible;
4. choose the first game uniformly from the remaining minimum-count tier;
5. rank eligible minimum-count partners by weighted mechanic distance and
   choose uniformly from the farthest 20 percent;
6. widen only the second choice to the next count tier if fewer than two
   minimum-count games are available;
7. record the draw and its pools immediately; never silently redraw it;
8. redraw only the second game if the audited gameplay-distance gate cannot be
   met without corrupting either concept.

Version `v1` remains a useful visible indicator of zero glow-ups, but the
explicit count is authoritative.

## Mechanics and novelty

The two Flash lineage ledgers remain the historical mechanic sources.
`research/glowup-mechanics-registry-v1.json` adds the requested program
families: multi-front strategy, deterministic physics, uncertainty,
asymmetric strength counters, few-actions/large-consequence, genuine
hexagonal topology, and direct mouse navigation.

For each sampled game, draw three underrepresented mechanic candidates using
inverse usage frequency. Adopt at most one. A mechanic may be rejected when it
does not fit, but the reason must be recorded. An adopted mechanic must alter
real decisions, appear in the level curriculum, survive into a late
composition, and have a counterfactual necessity test. It may never be a skin,
animation label, or irrelevant complication.

Weighted mechanic comparison assigns weight 3 to a primary mechanic, 2 to each
major secondary mechanic, and 1 to a minor modifier. Every final pair must have
an exclusive meaningful mechanic on each side, distinct core mechanic sets,
and weighted overlap no greater than 0.65 unless a documented control,
information, or temporal inversion makes the shared atom operationally
different.

Hexagons count only when six-neighbor adjacency changes routing, influence,
coverage, or interaction. Mouse navigation must use snapped targets and
generous deterministic hit regions. Pentagonal maps are excluded.

## One pass

1. Load the canonical pool, rubric, state, game statistics, mechanic registry,
   and both reviewed Flash lineage ledgers.
2. Rebuild statistics and check the pool-growth trigger.
3. If growth is not due, record exactly one fair pair.
4. Baseline-play every level of both games. Measure known solutions, random
   resistance, recovery, state continuity, and presentation failure.
5. Obtain independent pre-discussion reviews from accessibility, bilingual or
   child, older casual, Flash veteran, systems, animation/VFX, cross-cultural,
   and exploit perspectives.
6. Assign each game to a separate fresh-context improvement agent. Each author
   writes its own game-feel and art bible without seeing the other game, its
   author, or its proposed changes. Follow `glowup-agent-isolation-v1.md`.
7. Draw mechanic candidates and record accepted and rejected candidates.
8. Design 7-12 levels per game. Levels 2-6 add genuine demands and at least two
   late levels compose three or more earlier demands.
9. Implement immutable new versions with causal anticipation/event/settle
   animation and redundant critical-state encoding.
10. Freeze both independent candidates, then give a separate fresh-context
    comparison agent both games. Pull them apart across all 12 pair-distance
    dimensions. Return only game-specific repair requests to fresh authors. Score
    the pair and repair weaknesses until the existing distance gates pass.
11. Run **Quality Control** on each game, following
    `glowup-quality-control-v1.md`: honestly summarize mechanics and
    Level 1 play in simple English, record initial 0–1 slop scores, rewrite
    and rescore, and change the game itself when a faithful simple explanation
    or cold-start Level 1 test fails. Required final maximum score: 0.20.
    Record real-human evidence separately from simulated screening.
12. If QC changes either game, repeat step 10 and then step 11 on the exact
    new versions. A stronger distance score never excuses a QC failure.
13. Qualify shortest wins, exploratory/rejected-action recovery, reset, deterministic double
    replay, source and metadata hashes, random resistance, mechanic necessity,
    animation stability, fuzzing, catalog, structure, and final pair distance.
    Level 1 remains an approachable introduction; the strict random-resistance
    requirement continues to apply to Levels 2+.
    Terminal loss is optional. Test a retained loss and its visible life/warning
    buffer; otherwise record why loss is not applicable and qualify real recovery
    and retry paths. Follow `glowup-recovery-policy-v1.md`, including explicit
    verifier/artifact updates and the finite horizon of random-policy tests.
14. Iterate until every existing rubric gate and the new QC screening gate
    passes. Simulated playability remains explicitly provisional; only actual
    novice play can establish `human_confirmed` status.
15. Atomically activate both versions, regenerate thumbnails and honest traces,
    rebuild the catalog and deterministic bundle, rebuild game counts, and
    publish the cycle report locally with each game's QC evidence status.

## Pool growth

Before sampling, rebuild the explicit glow-up counts. When every active
concept has `glow_up_count >= 1`, stop ordinary sampling and add
`ceil(current_pool_size * 0.20)` runnable v1 seed games. Thus growth is
50 to 60, then 60 to 72 after all ten new seeds have been improved. QC
maintenance revisions have a separate count and never count as a seed's
first glow-up. The version suffix alone is not the growth trigger.

Every growth generation is atomic. Each s-series seed must introduce a
genuinely new causal idea, document its closest active prior, pass weighted
mechanic-overlap and structural-clone checks, and ship with source, metadata,
thumbnail, deterministic win and recovery traces (plus loss where applicable), and a runnable baseline. The
seeds may be intentionally less polished than a glow-up result, but they may
not be broken, duplicated, or cosmetic variants.

Growth records live in `research/pool-growth-seeds-v1.json`; the protected
1,000-row q-concept ledgers are never modified. Capability-axis bounds in the
canonical manifest must be updated and tested with each generation.

## Reporting

Each pass reports the draw and selection evidence, counts before and after,
origin coverage including Mark-origin games, mechanic candidates and decisions,
baseline defects, changes, curriculum, raw reviewer scores, machine evidence,
pair axes, caveats, exact files, zero-count remainder, and estimated passes to
complete the current coverage generation. Simulated personas are never called
human validation.


## Quality Control reporting and activation

Both games require either `provisional_pass` or `human_confirmed` QC status
before qualified activation. A `fail` cannot be offset by quality, novelty,
or distance scores. Candidate reports must preserve the distinction between
simulated screening and real human confirmation.

Record both descriptions before and after QC, all reviewer scores and reasons,
the exact tested source hash, cold-start timings and actions, restarts, help,
tester type, rule paraphrase, design repairs, and the final retest results.
Prior cycle records stay unchanged and make no claim to this new QC gate.

The initial QC maintenance batch is tracked in `qc-batch-20260914.json`.
Resume incomplete candidates and their independent reviews before ordinary
pair work. Activation requires verified evidence for the exact source. Keep
all old versions immutable and preserve unrelated changes in the worktree.

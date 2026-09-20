# Rubric: the scores and gates of the evolution loop (v4)

The fidelity and pair-distance scales are Codex's v3 scales, unchanged
([original](recovered/codex/glowup-rubric-v3.md)). v4 adds the step-4 playability gate
and the machine gate.

## Fidelity (100): is this game good? Pass at 84, no dimension under 60% of its points

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

Hard gates that no score offsets:
- 7-12 real levels. Levels 2-6 introduce components, rules, representations, constraints,
  uncertainty, counters, simulation laws or control changes, not count or budget inflation.
  At least two late levels compose three or more earlier demands. No more than two
  consecutive levels are larger instances of the same task.
- Critical state is encoded by at least two of shape, pattern, position, count, value or
  motion. No required text, digits, cultural knowledge, audio, flashing, twitch timing or
  motor precision.
- Physics uses exact steps. Uncertainty is reducible by informative action. Large
  consequences are previewable and causally readable.
- Every adopted mechanic appears in the curriculum, composes later, and fails an explicit
  necessity counterfactual when removed.

## Pair distance (100): are these two games different? Pass at 78

Score each axis 0 (same template) to 4 (strong opposites), times its weight / 4.

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

Also required: at least eight axes at 3 or 4, including a gameplay axis, a visual axis, and
a temporal or motion axis at 4; palette distance on at least three of hue, value,
saturation, count, temperature and texture; an exclusive meaningful mechanic on each side;
weighted mechanic overlap ≤ 0.65 (primary ×3, major secondary ×2, minor ×1). A hue swap,
more particles, or a renamed character never counts. In new-seed mode only the new game
moves, so all distance must come from changes to it.

## Playability (step 4): all must hold

| Check | How it is shown |
|---|---|
| Level 1 wins in ≤ 10 actions | `vet_game.py`: `level1_short` |
| Level 1 cannot be lost by ordinary play | `level1_safe`: 0 GAME_OVERs in random runs |
| No early deaths on any level | `early_death`: ≤ 10% of random runs die within 10 actions |
| Levels 2+ need thought | `random_resistance`: 0 clears by random runs of 250 actions |
| RESET retries the level and keeps earlier ones | `reset` |
| Actions answer visibly | `visible_response`, and the cold-start tester |
| Movement is whole, short, and follows the real path | `frames_per_action`, plus a reviewer signing off the strips |
| A newcomer gets it | cold start: first meaningful action ≤ 60 s, level 1 ≤ 5 min, rule explained |
| It can be said simply | English QC: max of four scores ≤ 0.20 |

## Difficulty curve (step 5): pass at 75, measured by `scripts/curve_score.py`

| Check | Points | Pass |
|---|---:|---|
| `shape` | 25 | the declared roles read `teach, stretch(0-2), [introduce, combine(1-2)](1-2), turn, compose(2), finale(0-1)`; every introduced mechanic is used again; every level after the first says what it asks that the last did not |
| `rising` | 25 | rank correlation between level order and actions in the winning trace is at least 0.5 |
| `teach_first` | 15 | level 1 is at most 10 actions and at most half the median level |
| `growth` | 15 | the last third of levels averages 1.6x the actions of the first third |
| `no_plateau` | 10 | no three levels in a row within 12% of one another |
| `finale` | 10 | the last level is the longest, or within 10% of it |

Plus two gates from playing it, when a felt report is supplied (`--felt`), and step 5 requires
one: `felt_rising`, the per-level demand ratings rise (rank correlation at least 0.5, last
above first), and `felt_verdict`, the player says the game `climbs`. Both outrank the number.

`rising`, `teach_first` and `shape` are hard gates past the seed stage. The measure is a
proxy: a long dull level scores as a hard one. A game that scores well and feels flat has
failed, whatever the number says.

## English QC scale (0 = simple English, 1 = slop)

| Score | Meaning |
|---|---|
| 0.00 | Direct, accurate everyday English. A novice can say what to do and why. |
| 0.25 | Mostly clear; one term, rule or causal link needs explaining. |
| 0.50 | Needs rereading; several rules or exceptions are hard to connect. |
| 0.75 | Jargon and abstraction hide the actions or the goal. |
| 1.00 | No usable account of how the game works. |

A short but false or incomplete explanation fails whatever its score.

## Review perspectives

Before any discussion, collect at least five independent simulated reviews: accessibility,
a first-time or bilingual child, a Flash veteran, a systems designer, and an animation or
cross-cultural art reviewer (an older casual player and an exploit hunter are welcome too).
They need a median of at least 4/5 on fidelity and distinctness and nothing below 3/5 on
accessibility. They are design aids, not playtests.

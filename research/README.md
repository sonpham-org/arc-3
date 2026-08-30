# Alternative Interactive Reasoning Environments

Status: working research program, 29 August 2026

This directory defines the research and production protocol for a new collection of
ARC-AGI-3-compatible environments. It deliberately separates:

1. the 25 ARC Prize public demonstration environments;
2. the 22 bespoke Cellens environments currently in the ARC3 browser;
3. the 252 imported `arc-interactive` environments currently in that browser;
4. the new 1,000-environment production collection, with a provenance-controlled
   400-environment cross-provider evaluation subset.

The fourth collection is not a relabeling of the existing 299-game catalog. A game only
enters it after provenance, novelty, deterministic qualification, solution replay, visual
distance, human calibration, and random-policy resistance have all been checked.

## Research claim

The public ARC-AGI-3 set is a demonstration interface, not a complete sample of the
private benchmark. ARC Prize explicitly says that the public set does not comprehensively
represent private mechanics. Therefore this project studies:

> Which reasoning demands are visible, sparse, or absent in the *publicly observable*
> ARC-AGI-3 environments, and can carefully constructed alternative environments produce
> complementary, human-solvable measurements of those demands?

We must not claim that an unobserved public mechanic is absent from ARC-AGI-3's private
sets.

Primary references:

- [ARC-AGI-3 Technical Report](https://arcprize.org/media/ARC_AGI_3_Technical_Report.pdf)
- [ARC-AGI-3 Preview: 30-Day Learnings](https://arcprize.org/blog/arc-agi-3-preview-30-day-learnings)
- [ARC-AGI-3 launch](https://arcprize.org/blog/arc-agi-3-launch)
- [ARC-AGI game-authoring documentation](https://github.com/arcprize/docs/blob/main/add_game.mdx)

The historical mechanic prior-art pass is documented in
[`flash-game-mechanics-survey.md`](flash-game-mechanics-survey.md). It enumerates 129,019
Flash game records from a content-hashed Flashpoint snapshot and converts 48 reviewed
lineages into mechanic atoms with explicit anti-cloning guardrails. The snapshot itself is
an external input and is not committed.

## Corpus snapshot

| Corpus | Count | Role in this study | Included in new benchmark? |
|---|---:|---|---|
| ARC Prize public demo | 25 | reference coverage and baseline behavior | no |
| Cellens bespoke catalog | 22 | prior art and regression/control pool | no, unless requalified |
| Red Blue Pill catalog | 252 | broad prior-art/dedup corpus | no, unless requalified |
| External idea ledger | 63 | Anthropic-side seed concepts | only after independent review |
| Anthropic implementation queue | 200 | GPT-seeded commissioning briefs | development only; concept-exposed to GPT |
| Consolidated GPT design ledger | 800 | production inventory across 20 capability axes | yes; 200 form the original evaluation partition |
| Strict GPT evaluation subset | 200 | held-out games for Anthropic evaluation | yes |
| Strict Anthropic evaluation subset | 200 | independently authored games for GPT evaluation | yes; still requires a sealed authoring pass |

The external 63-idea source is pinned to:

- repository: `sonpham-org/autoresearch-arena`
- commit: `f245c9583535899e47a120ea8b93419d8a1905ef`
- path: `arc3/game-ideas/ledger.jsonl`
- SHA-256: `ca5e4ccdfd347ac4df091c810c05a03ae5168a260454d775f35404fc96005af9`
- inventory at pin: 63 ideas, of which 10 were marked built and 53 remained ideas

Those ideas retain their original source attribution. Refining their prose or porting an
implementation does not make them GPT-authored.

### Anthropic implementation queue

`anthropic-build-ideas-v1.tsv` contains 200 detailed briefs intended for Anthropic to
implement. It spans 25 primary capability families with eight concepts per family. Every
row records a secondary axis, interaction model, concrete mechanic, differentiator,
anticipated AI failure, and the explicit lineage `gpt-seeded-anthropic-build`.

The queue was retrieved against 562 prior records: the GPT 200, the complete external 63,
and all 299 current browser-manifest entries. The deterministic audit in
`anthropic-build-ideas-v1.audit.json` reports no exact or fuzzy title collisions, no exact
primary-axis reuse, no thresholded within-queue duplicates, and no thresholded lexical
matches to the prior corpus. `scripts/validate_idea_diversity.py` regenerates that audit.
Lexical retrieval is a review aid, not proof of semantic novelty.

### Expanded 1,000-design production ledger

`gpt-ideas-v2.tsv` preserves all 200 rows of `gpt-ideas-v1.tsv` byte-for-byte at the
record level and adds `q201` through `q800`. The additions cross 30 domain families with
30 structural variants per capability axis; each of the 20 axes therefore has 40 GPT
concepts. Combined with the 200 Anthropic implementation briefs, the production inventory
contains exactly 1,000 designs.

`scripts/build_gpt_ideas_v2.py` deterministically regenerates the consolidated ledger and
`gpt-ideas-v2.audit.json`. The audit pins both source and output hashes and checks ID,
title, concept, axis-balance, legacy-preservation, domain-family, and structural-variant
invariants. This expansion changes the production target, not the contamination claim:
only the original sealed 200-by-200 subset is eligible for strict cross-provider held-out
evaluation.

This provenance distinction matters: because GPT produced these briefs, games implemented
directly from them are **concept-exposed to GPT**. They can be used for development and for
an implementation-held-out result, but not honestly labeled a strict GPT-held-out
cross-provider partition. A strict partition still requires Anthropic to author or
substantially re-conceive its games behind a sealed boundary that the GPT evaluator never
sees.

The reproducible static layer of the official-public audit lives in
`official-public-surface-audit.json` and is regenerated by
`scripts/audit_public_game_surface.py`. It records exact source hashes, action references,
input surfaces, level-transition references, randomness references, and rendering metadata
for all 25 official public games. It deliberately does not infer objectives or cognitive
demands from code shape.

## What the public format already measures well

The public environments collectively expose a strong base layer:

- discovering an unstated objective from state changes;
- learning action affordances, including movement, selection, click coordinates, undo,
  and contextual actions;
- object permanence, collision, containment, matching, and local topology;
- short causal experiments followed by plan execution;
- carrying rules across a sequence of increasingly composed levels;
- multi-step navigation and manipulation;
- pattern completion and spatial transformation;
- orchestration of quantities and synchronized state;
- memory of prior frames and recovery from irreversible mistakes;
- action efficiency as a joint measure of exploration and execution.

This is the current semantic synthesis, not yet the completed per-game mechanic matrix.
Every final matrix cell must be backed by source inspection plus controlled play or a
verified replay. The public IDs are intentionally opaque, and the research UI should
preserve those IDs when showing benchmark evidence.

## Candidate gaps in the publicly observable set

The following are hypotheses to test by source audit and controlled play, not declarations
about the private benchmark:

| Candidate demand | Why it is complementary | Environment evidence we should create |
|---|---|---|
| Active causal intervention | Many tasks reveal effects after actions; fewer make choosing the most informative intervention the central scarce resource. | Identical-looking worlds separated only by a minimal intervention policy. |
| Social inference and cooperation | Basic agentness does not imply inferring another agent's belief, preference, or communication protocol. | Agents with stable but initially unknown policies whose cooperation is necessary. |
| Distributed partial observability | A single player usually owns the observation stream. | Multiple bodies each receive complementary evidence that must be integrated. |
| Observer-dependent dynamics | Occlusion usually limits the player; it rarely changes what the world itself does. | Objects that move, freeze, or transform as a causal function of being observed. |
| Conservation-law induction | Resource counts exist, but discovering an invariant across unfamiliar transformations can be the whole problem. | Split/merge/exchange machines with conserved mass, parity, or connectivity. |
| Counterfactual planning | Trial and error tests the actual world; explicit reasoning about actions *not taken* is less directly isolated. | Limited irreversible trials where the winning plan requires ruling out branches cheaply. |
| Non-stationary rule revision | Later levels compose rules, but a learned rule can also change in a detectable, structured way. | A change point with evidence that rewards revising rather than extending the old model. |
| Hierarchical task discovery | Most goals are local or level-terminal. | Latent subgoals whose order and reuse must be inferred across rooms. |
| Multi-scale reference frames | Rotations and maps exist; nested frames can require reasoning in local and global coordinates simultaneously. | Objects controlled in moving local frames embedded in a global board. |
| Tool construction | Selecting or combining tools is weaker than creating a tool whose geometry determines later affordances. | Parts assembled into a bridge, lens, enclosure, or signal transformer. |
| Epistemic resource allocation | Actions are scarce, but observations themselves are rarely priced separately. | A limited sensor budget that forces deliberate choices about what to reveal. |
| Continuous quantity without symbols | The grid supports approximate magnitude, flow, density, and balance without digits. | Analog-looking reservoirs, elastic shapes, or population fields with exact causal rules. |
| Credit assignment across delayed side effects | Delays exist, but side effects can span several apparently successful subgoals. | Early actions alter the feasibility of a much later objective without immediate penalty. |
| Self/other identity under transformation | Role swaps exist, but persistent identity can be separated from appearance, location, and control. | Bodies exchange appearance or controls while hidden identity determines interactions. |
| Policy learning from demonstrations | The agent normally learns by acting. | Nonverbal demonstrations whose latent policy must be inferred before control transfers. |
| Adversarial-but-legible adaptation | Scripted hazards are predictable; an opponent can instead adapt to the player's repeated policy. | Opponents with a small, inferable update rule and exploitable adaptation. |
| Compositional communication | Colors and shapes convey state, but a protocol can be learned and then used to coordinate. | Signals whose meaning is grounded through interaction and composed in later levels. |
| Confidence calibration | Standard success rewards one plan, not knowing when the current hypothesis is unsafe. | Optional commitment actions where delaying is costly but premature commitment is fatal. |
| Structural analogy across levels | Transfer is present implicitly. | Two visually distant systems with the same causal graph, followed by a cross-domain composition. |
| Agency over the action interface | Contextual actions vary by game; the mapping itself can be a learnable, reversible state. | An interface whose control semantics are transformed by objects in the world. |

## Design rules for every new environment

These rules are gates, not aspirations.

1. **Core priors only.** Objectness, geometry/topology, intuitive physics, and agentness are
   allowed. No words, digits, familiar icons, or cultural color conventions are required.
2. **At least six levels.** Level one is a legible tutorial. Every later level introduces
   exactly one new demand or composes previously learned demands.
3. **Multiple mechanics.** Merely increasing board size, count, or path length is not a
   difficulty ladder.
4. **Distinct solver structure.** A solver shared with another environment must not be
   substantially shorter than two independent solvers. We use ARC Prize's practical
   program-compression novelty test as a review heuristic.
5. **Human-solvable.** The intended first-exposure session is under 20 minutes, followed by
   controlled human calibration.
6. **Random-resistant.** No non-tutorial level may exceed a 1-in-10,000 random-policy win
   estimate. Qualification includes long random sweeps and state-graph analysis where
   tractable.
7. **Deterministic replay.** Every level ships with at least one known-good solution trace
   and one known-loss trace. Replaying either must reproduce the same terminal result and
   frame hashes.
8. **Visual distance.** A game must differ from the official set and both author partitions
   in dominant palette, object silhouettes, spatial organization, motion grammar, and HUD.
   Color permutation alone is not novelty.
9. **No evaluator feedback leakage.** Held-out evaluator traces and scores never enter the
   authoring loop for that partition.
10. **Immutable identity.** Source, metadata, solution recordings, and evaluation manifests
    are content-hashed. A code change creates a new version; it never silently rewrites a
    scored game.

## Difficulty ladder contract

Every specification names its progression explicitly:

1. **Orient:** teach the action-to-effect relationship with one forgiving mechanic.
2. **Discriminate:** introduce a contrasting object or inverse rule.
3. **Plan:** require multiple correct actions before feedback or reward.
4. **Remember:** make a prior observation necessary after it leaves view.
5. **Compose:** combine two previously isolated mechanics.
6. **Inhibit:** make the locally attractive action harmful to the global plan.
7. **Transfer:** change appearance/layout while retaining causal structure.
8. **Synthesize:** combine the environment's demands without adding a hidden exception.

Games may use six to twelve levels, but skipping directly from tutorial to scale is a
rejection.

## The 200 / 200 authorship split

Partition A contains 200 GPT-authored games and is evaluated by a frozen Anthropic model.
Partition B contains 200 Anthropic-authored games and is evaluated by a frozen GPT model.
Qwen3.8 and deterministic agents may be used for platform diagnostics on both partitions,
but development-time scores are never reported as held-out generalization results.

The split only addresses model-retention concerns if all of these hold:

- authoring repositories/branches are access-separated until freeze;
- game titles, code, screenshots, solution traces, and mechanics are not published before
  held-out evaluation;
- evaluator models run without browsing, retrieval, or repository access;
- exact model snapshots, system prompts, harness hashes, sampler settings, and tool schemas
  are pinned before any held-out run;
- authors do not receive per-game held-out traces during development;
- failures are analyzed only after the full benchmark version is sealed;
- any post-result repair produces a new benchmark version and requires a fresh evaluation.

The 63 external ideas seed the Anthropic lineage. They do not count toward the GPT 200.
The remaining Anthropic-side concepts must be created and implemented on the isolated
Anthropic side.

## GPT implementation status

The first thirty-five production waves now contain three hundred fifty cross-mechanic prototypes in addition
to `q001 Quiet Field`. `research/gpt-batch01-v1.json` through
`research/gpt-batch35-v1.json` are the content-hashed batch manifests. Each wave samples
ten capability families instead of filling one adjacent family at a time.

Batch 01:

- `q002 Afterimage Mill` — observation-written hidden programs;
- `q011 Courtesy Lines` — stable yielding-preference inference;
- `q021 Switchboard Diagnosis` — intervention-efficient causal diagnosis;
- `q031 Split Vessel` — exact conserved-quantity transformation;
- `q041 Keyhole Budget` — priced spatial observation;
- `q051 Scaffold` — finite-material load-bearing construction;
- `q061 Split Couriers` — distributed partial observation and remote latches;
- `q071 Season Shift` — phase-conditioned terrain and visible rule reversal;
- `q081 Shell Identity` — persistent identity under independent transformations;
- `q091 Workshop Orders` — latent subassembly dependencies and reusable fixtures.

Batch 02:

- `q101 Carousel Coordinates` — moving local and global reference frames;
- `q111 Silent Tutor` — transformed policy learning from demonstration;
- `q121 Habit Hunter` — legible adaptation to recent player behavior;
- `q131 Pulse Language` — grounded compositional communication;
- `q141 Branch Ledger` — persistent counterfactual branch evidence;
- `q151 Pipes to Roads` — structural analogy across visual embodiments;
- `q161 Wager Gate` — evidence-sensitive claim timing;
- `q171 Elastic Balance` — coupled continuous-looking tension;
- `q181 Affordance Debt` — shortcut consequences delayed across rooms;
- `q191 Event Compression` — causal event boundaries within long cycles.

Batch 03:

- `q003 Blind Growth` — observer-directed branching under self-avoidance;
- `q012 Private Appetites` — preference inference and fair allocation;
- `q022 Counterweight Lab` — signed, ratio-coupled platform intervention;
- `q032 Parity Forge` — pairwise transformations under a global invariant;
- `q042 Sonar Pips` — scarce distance-only localization;
- `q052 Lens Bench` — functional optical-tool construction;
- `q062 Relay Shadows` — body/shadow integration across observation panes;
- `q072 Honest Liar` — visible state-conditioned signal inversion;
- `q082 Borrowed Color` — role identity through repeated recoloring;
- `q092 Nesting Rooms` — inner solutions that transform outer subgoals.

Batch 04:

- `q102 Walking Room` — navigation across nested mobile reference frames;
- `q112 Negative Demonstration` — policy inference from success/failure contrasts;
- `q122 Feint` — two-stage displayed intent and adversary manipulation;
- `q132 Shape-Free Code` — relative-position communication;
- `q142 Ghost Alternatives` — scarce counterfactual action previews;
- `q152 Shadows to Forces` — structural transfer from offsets to attraction;
- `q162 Claim or Explore` — confidence-sensitive evidence stopping;
- `q172 Fluid Blend` — two-component conserved mixture reasoning;
- `q182 Borrowed Floor` — cross-room consumable path material;
- `q192 Nested Clocks` — fast/slow temporal synchronization.

Batch 05:

- `q004 Witness Queue` — watched commitment alternating with unseen transit;
- `q013 Signal Camp` — grounded partner-policy inference from spatial demonstrations;
- `q023 Broken Symmetry` — causal intervention on visually symmetric machines;
- `q033 Color Exchange` — global component conservation through pairwise swaps;
- `q043 Sampling Cart` — finite active-perception allocation during safe routing;
- `q053 Bridge Loom` — persistent tool construction over a support graph;
- `q063 Two Rooms One Switch` — remote causal state across alternating views;
- `q073 Phase Change` — threshold-triggered revision of the traversal law;
- `q083 Unmarked Lineage` — persistent identity reconstructed from ancestry;
- `q093 Milestone Garden` — hierarchical subgoals that unlock new operations.

Batch 06:

- `q103 Nested Compass` — composition of independently rotating control frames;
- `q113 Alternating Teacher` — context-selected policy demonstrations;
- `q123 Last-Move Guard` — predictable adaptation against repeated movement;
- `q133 Spatial Grammar` — joint order-and-arrangement communication;
- `q143 Costly Preview` — selective counterfactual information allocation;
- `q153 Braids to Signals` — crossing permutations transferred to temporal channels;
- `q163 Evidence Weight` — reliability-sensitive hypothesis assignment;
- `q173 Density Drift` — conserved distribution shaping through gradients;
- `q183 Delayed Escort` — early assistance with delayed policy effects;
- `q193 Routine Builder` — action macros that preserve exceptional branches.

Batch 07:

- `q005 Lantern Census` — observer-conditioned population growth and merging;
- `q014 Flock Vote` — latent aggregation rules over social gestures;
- `q024 Last Probe` — finite experiment design before irreversible commitment;
- `q034 Area Keeper` — filled-area conservation under silhouette change;
- `q044 Memory Camera` — selective evidence capture for ordered later recall;
- `q054 Gear Teeth` — finite mechanical-resource allocation;
- `q064 Scout Gestures` — grounding reports from remote autonomous observers;
- `q074 Drift Law` — sparse calibration under a rotating action mapping;
- `q084 Control Transfer` — controller identity separated from body objectives;
- `q094 Delivery Tree` — branching upstream dependencies revealed by requests.

Batch 08:

- `q104 Conveyor Frame` — composition of object, belt, and board velocities;
- `q114 Noisy Example` — imitation filtered by visible causal effect;
- `q124 Counter-Predator` — discoverable counters to distance-sensitive tactics;
- `q134 Relay Syntax` — composition of local communication transforms;
- `q144 One Reset` — evidence-preserving reset between experiment and execution;
- `q154 Reservoir Crowd` — population flow under conservation and capacity;
- `q164 Stop Test` — value-of-information stopping under test cost;
- `q174 Resonant Steps` — phase-aligned accumulation of oscillation amplitude;
- `q184 Seeded Weather` — early placements with delayed seasonal hazards;
- `q194 Interrupt Window` — state-timed interruption of autonomous routines.

Batch 09:

- `q006 Shadow Cargo` — visibility-locked transfer among storage pockets;
- `q015 Reciprocal Hands` — short-memory social reciprocity;
- `q025 Latent Gearbox` — causal intervention over hidden clutches;
- `q035 Momentum Bank` — collision-driven conservation and storage;
- `q045 Scout Drones` — disposable sensing under a map-information budget;
- `q055 Funnel Forge` — functional particle-sorter construction;
- `q065 Asymmetric Twins` — complementary color and shape observers;
- `q075 Betrayal Gate` — wear-triggered inversion of a learned rule;
- `q085 Identity Trail` — footprint-grounded identity after convergence;
- `q095 Closure Graph` — nested cycle completion and graph closure.

Batch 10:

- `q105 Orbiting Board` — local exchange under global orbital alignment;
- `q115 Partial Demonstration` — reconstruction of omitted subgoal trajectories;
- `q125 Escalation Ladder` — controlled alternation against adaptive aggression;
- `q135 Parity Signals` — grouped two-channel parity communication;
- `q145 Parallel Sandboxes` — paired counterfactual tests before irreversible action;
- `q155 Mirror Roles` — symmetry transfer from shapes to social roles;
- `q165 Hypothesis Stack` — uncertainty retention under sequential evidence;
- `q175 Pendulum Phase` — transfers timed by position and momentum;
- `q185 Promise Tokens` — identity-bound delayed obligations;
- `q195 Tempo Transfer` — rhythm scaling across mechanisms.

Batch 11:

- `q007 Still Guards` — observer-frozen patrols and visibility-costed gate decay;
- `q016 Blind Guide` — route inference from a guide's demonstrated motion sequence;
- `q026 Controlled Cascade` — joint seed-and-barrier selection for exact propagation;
- `q036 Loop Current` — conserved redistribution across coupled storage loops;
- `q046 One Question` — a single binary intervention before hypothesis commitment;
- `q056 Magnet Chain` — polarity-constrained construction of alternating chains;
- `q066 Beacon Relay` — locally encoded directions propagated through a relay chain;
- `q076 Rule Thermostat` — active temperature control over a state-dependent rule regime;
- `q086 Doppel Memory` — identity recovery through learned, persistent permissions;
- `q096 Subgoal Cache` — reusable completion state across a repeated dependency.

Batch 12:

- `q008 Veiled Orchestra` — occlusion-gated phase alignment across cyclic mechanisms;
- `q017 Mimic or Seeker` — behavioral separation of copied and goal-directed motion;
- `q027 Proxy Lever` — causal roles attached to positions rather than object identities;
- `q037 Hole Count` — topology tracked across large silhouette transformations;
- `q047 Sensor Auction` — minimum-cost evidence selection under a hard budget;
- `q057 Raft Shape` — cargo-supporting footprint construction under channel constraints;
- `q067 Map Fragments` — registration of rotated local maps into a global frame;
- `q077 Aging Tools` — plans composed around use-count-dependent affordance changes;
- `q087 Body Exchange` — identity-bound goals with swappable physical capabilities;
- `q097 Factory Plan` — scheduling over an unlabeled production dependency graph.

Batch 13:

- `q009 Peripheral Current` — focus-radius freezing used to align peripheral flows;
- `q018 Exchange Circle` — preference probing and mutually acceptable trade cycles;
- `q028 Causal Quilt` — sparse intervention to recover local-law boundaries;
- `q038 Balance Web` — conserved load routing through capacity-limited networks;
- `q048 Reveal Paint` — permanent spatial evidence allocated under a paint budget;
- `q058 Antenna` — construction of frequency-tuned conductive spans;
- `q068 Blind Captain` — scarce observer signals guiding an instrument-only controller;
- `q078 Rotating Contract` — arrangement-signaled cycles of social response policies;
- `q088 Mask Debt` — transferable affordances with identity-bound obligations;
- `q098 Rescue Order` — prerequisite discovery among capability-granting rescues.

Batch 14:

- `q010 Shared Blindspot` — Boolean geometry formed by two independent observers;
- `q019 Apprentice Path` — demonstrations adapted to a learner's transformation rule;
- `q029 Fuse Map` — irreversible diagnostic cuts that preserve one live circuit;
- `q039 Charge Pairs` — opposite-charge creation and consumption under net conservation;
- `q049 Confidence Door` — evidence-sensitive stopping before destructive commitment;
- `q059 Sieve` — bidirectional size-selective mesh construction;
- `q069 Echo Windows` — integration of immediate and delayed complementary panes;
- `q079 Exception Signal` — local marked exceptions without abandoning a general rule;
- `q089 Persistent Passenger` — identity tracking across changing visible carriers;
- `q099 Waypoint Memory` — reusable local waypoints assembled into a global route.

Batch 15:

- `q020 Crowd Current` — diagnosed alignment, avoidance, and attraction dynamics;
- `q030 Antidote Network` — interventions with opposing neighbor and distance-two effects;
- `q040 Mass Shadow` — invariant mass recovered across changing projections;
- `q050 Compression Cabinet` — scarce reusable abstractions selected as a pattern basis;
- `q060 Clockwork Tool` — physical cam-and-delay programs that execute autonomously;
- `q070 Triangulation` — hidden-target localization from three relative-distance views;
- `q080 Regime Cart` — a movable radius that transports and composes physical rules;
- `q090 Lineage Garden` — pruning based on persistent inherited traits;
- `q100 Recursive Gate` — nested self-similar dependencies controlled by inner parameters;
- `q106 Local Gravity Wells` — movement across visibly different local gravity frames.

Batch 16:

- `q107 Folding Map` — hinge folds that rewrite global adjacency and orientation;
- `q116 Counterexample Room` — policy learning driven by minority counterexamples;
- `q126 Copycat Trap` — delayed imitation repurposed as a remote actuator;
- `q136 Lossy Channel` — adaptive redundancy for a predictably dropped signal class;
- `q146 Fork Seal` — downstream planning before irreversible sibling closure;
- `q156 Bridge Logic` — transfer from embodied bridges to Boolean activation structure;
- `q166 Checkpoint Choice` — confidence-sensitive placement of one preserved state;
- `q176 Heat Diffusion` — local field prediction through material thresholds;
- `q186 Deferred Mirror` — remote effects scheduled by a visible countdown;
- `q196 Event Order` — causal event abstraction across changing animation durations.

Batch 17:

- `q108 Camera Relative` — camera-relative controls separated from world-relative drift;
- `q117 Teach Back` — learned tutor policies demonstrated to a simpler student;
- `q127 Policy Mirror` — adversaries that adopt the most recently successful strategy;
- `q137 Shared Convention` — feedback-driven convergence on a common signal mapping;
- `q147 Affordance Sketch` — structural fit previewed before irreversible construction;
- `q157 Same Graph New Bodies` — exact causal topology transferred across embodiments;
- `q167 Probe or Act` — safe uncertainty reduction before irreversible object use;
- `q177 Pressure Web` — capacity-safe gradient control across connected chambers;
- `q187 Echo Cost` — early repetition changing an action's later effect;
- `q197 Phase Landmark` — long-cycle synchronization anchored by a distinctive phase.

Batch 18:

- `q109 Body-Centric Maze` — body-centered commands converted under repeated world rotation;
- `q118 Distributed Lesson` — separate tutor components composed into a final policy;
- `q128 Adaptive Patrol` — route diversity under recent-visit patrol adaptation;
- `q138 Command Composition` — typed object, direction, and timing primitives;
- `q148 Delayed Commit` — whole-path queuing and preview before irreversible execution;
- `q158 Causal Rhyme` — cause-effect order transferred across unrelated mechanisms;
- `q168 Calibration Orchard` — resource allocation according to stable noisy likelihoods;
- `q178 Wave Junction` — modular phase alignment across reflected pulse sources;
- `q188 Future Walls` — an early route remembered as a later obstacle pattern;
- `q198 Action Chunking` — a learned action macro reused inside novel plans.

Batch 19:

- `q110 Moving Portal Frame` — portal exits fixed to moving carriers rather than the board;
- `q119 Analog Lesson` — causal policies transferred from flows to moving blocks;
- `q129 Decoy Learner` — teaching an adaptive guard a false preference before commitment;
- `q139 Clock-Skew Messages` — content addressed to asynchronous sender/receiver phases;
- `q149 Model Tokens` — competing possible worlds eliminated through observation intersections;
- `q159 Cross-Scale Transfer` — causal order preserved from small tiles to large regions;
- `q169 Uncertainty Routing` — ambiguous cargo preserved at a reversible hub;
- `q179 Field Alignment` — local vector alignment controlling integrated global drift;
- `q189 Inheritance` — resources and structural damage passed to a successor;
- `q199 Slow Consequence` — pending causes separated from later completed effects.

Batch 20:

- `q201 Aurora Veil` — attention-frozen regions with hysteretic hidden updates;
- `q232 Tide Pact` — probing a hidden group convention before irreversible agreement;
- `q263 Ember Probe` — budgeted causal diagnosis before a single repair;
- `q294 Honeycomb Ledger` — conserved transfers coordinated across nested clocks;
- `q325 Alloy Survey` — budgeted set coverage under a rotating measurement frame;
- `q356 Palimpsest Rig` — one constructed geometry passing two rotated functional tests;
- `q387 Canopy Delegation` — complementary observers communicating through a bounded store;
- `q418 Breakwater Revision` — wear-triggered rule revision with a dormant side effect;
- `q449 Strata Lineage` — persistent ancestry through reversible appearance changes;
- `q480 Spore Dependency` — reusable prerequisites solved at sparse two-actor alignments.

Batch 21:

- `q511 Tapestry Frame` — moving local controls followed by a topology rewrite;
- `q542 Lockwater Lesson` — conditional demonstrations with causally ineffective gestures;
- `q573 Murmuration Counter` — deliberately shaping a recent-history opponent state;
- `q604 Moraine Grammar` — grouped spatial commands transformed by local relays;
- `q635 Waystation Sandbox` — persistent evidence from reset miniature interventions;
- `q666 Backstage Analogy` — sightline structure transferred to quantity-bearing actors;
- `q697 Catalyst Evidence` — reliability-weighted stopping with memory-bound execution;
- `q728 Asterism Gradient` — conserved phased influence with evidence-preserving reset;
- `q759 Reedbed Obligation` — identity-bound debt delayed through tool construction;
- `q790 Vault Rhythm` — dual conservation and event-chunked interrupt timing.

Batch 22:

- `q212 Lockwater Veil` — hidden identities updating beneath exchanged appearances;
- `q243 Murmuration Pact` — parity-checked convention inference with one misleading response;
- `q274 Moraine Probe` — budgeted causal diagnosis coupled to outer progress;
- `q305 Waystation Ledger` — conserved supply routing against a repetition counter;
- `q336 Backstage Survey` — rotating sightline coverage with directed influence;
- `q367 Catalyst Rig` — orientation memory executing a constructed reusable device;
- `q398 Asterism Delegation` — complementary evidence persisting across physical reset;
- `q429 Reedbed Revision` — wear-shifted rules coupled to connectivity construction;
- `q460 Vault Lineage` — causal identity with two conserved shared stores;
- `q491 Pollen Dependency` — a prerequisite DAG spanning a visible rule complement.

Batch 23:

- `q521 Pollen Frame` — moving local controls complemented after visible wear;
- `q552 Semaphore Lesson` — conditional policy inference from noisy miniature relay tests;
- `q583 Impeller Counter` — shaping a stable opponent tactic before stopping samples;
- `q614 Tessera Grammar` — relay-transformed chunks around an interrupt window;
- `q645 Vivarium Sandbox` — fair reset experiments before one irreversible policy;
- `q676 Crossing Analogy` — dock structure transferred through alternating observer marks;
- `q707 Spectrum Evidence` — reliability algebra transferred from geometry to agents;
- `q738 Escapement Gradient` — fault-diagnosed conservation over nested gear phases;
- `q769 Monsoon Obligation` — identity debt repaid after sparse unequal-cycle rewards;
- `q800 Workbench Rhythm` — event-chunked interruption with helper-bound debt.

Batch 24:

- `q222 Semaphore Veil` — occluded updates scheduled after two miniature tests;
- `q253 Impeller Pact` — convention inference with optimal sample stopping;
- `q284 Tessera Probe` — seam diagnosis around an autonomous interrupt;
- `q315 Vivarium Ledger` — conserved population routing with reciprocal fairness;
- `q346 Crossing Survey` — marked observers covering disjoint dock attributes;
- `q377 Spectrum Rig` — prism-tool geometry transferred to agent relations;
- `q408 Escapement Delegation` — fault-probed complementary gear views;
- `q439 Monsoon Revision` — wear-shifted rules ending at an unequal-cycle pair;
- `q470 Workbench Lineage` — helper identity recovered through reversible transforms;
- `q481 Tapestry Dependency` — prerequisite solving across an adjacency rewrite.

Batch 25:

- `q501 Aurora Frame` — local motion composed with translating, rotating, hysteretic frames;
- `q532 Tide Lesson` — conditional policy learning with irrelevant demonstration gestures;
- `q563 Ember Counter` — recent-action opponent shaping under a shared resource budget;
- `q594 Honeycomb Grammar` — grouped relay language under nested local and outer clocks;
- `q625 Alloy Sandbox` — persistent miniature evidence across moving-frame resets;
- `q656 Palimpsest Analogy` — relational transfer with a visible near-miss counterexample;
- `q687 Canopy Evidence` — bounded weighted evidence with provably safe early stopping;
- `q718 Breakwater Gradient` — conserved routing with a dormant early intervention;
- `q749 Strata Obligation` — identity-bound debt surviving physical causal undo;
- `q780 Spore Rhythm` — dual-clock alignment through interruptible macro-time.

Batch 26:

- `q202 Tide Veil` — observation scheduling across coupled reversing currents;
- `q233 Ember Pact` — resource-priced probing of a stable social convention;
- `q264 Honeycomb Probe` — causal diagnosis across nested local and outer clocks;
- `q295 Alloy Ledger` — conserved routing under rotating local controls;
- `q326 Palimpsest Survey` — bounded set-cover observation of overwritten traces;
- `q357 Canopy Rig` — capacity-bounded assembly of reusable multi-effect modules;
- `q388 Breakwater Delegation` — complementary views integrated through persistent marks;
- `q419 Strata Revision` — rule evidence that persists after physical probe undo;
- `q450 Spore Lineage` — ancestry tracking through appearance exchange and unequal clocks;
- `q482 Lockwater Dependency` — identity-conditioned prerequisites across adjacency rewrites.

Batch 27:

- `q203 Ember Veil` — attention-scheduled hidden heat updates under shared fuel;
- `q234 Honeycomb Pact` — phase-sensitive convention inference across two clocks;
- `q265 Alloy Probe` — causal-link diagnosis under a rotating measurement frame;
- `q296 Palimpsest Ledger` — conserved routing constrained by a causal trace;
- `q327 Canopy Survey` — scarce set-cover evidence buffered through a narrow store;
- `q358 Breakwater Rig` — reusable tool assembly with a dormant first effect;
- `q389 Strata Delegation` — reversible distributed probes with persistent marks;
- `q420 Spore Revision` — wear-boundary recalibration at sparse shared events;
- `q451 Tapestry Lineage` — ancestry tracking across a graph rewrite;
- `q483 Murmuration Dependency` — reusable prerequisites with a mislead-correcting parity audit.

Batch 28:

- `q504 Honeycomb Frame` — moving local controls composed with nested scent clocks;
- `q535 Alloy Lesson` — conditional demonstrations under a rotating force frame;
- `q566 Palimpsest Counter` — exact causal-pattern opponent shaping;
- `q597 Canopy Grammar` — grouped relay language through a bounded store;
- `q628 Breakwater Sandbox` — persistent miniature evidence with a dormant first effect;
- `q659 Strata Analogy` — relational transfer after reversible probing;
- `q690 Spore Evidence` — weighted safe stopping at sparse dual-clock events;
- `q721 Tapestry Gradient` — conserved routing across an adjacency rewrite;
- `q752 Lockwater Obligation` — causal-identity debt after appearance exchange;
- `q783 Murmuration Rhythm` — macro-time alignment with a parity audit.

Batch 29:

- `q204 Honeycomb Veil` — observation scheduling that advances nested scent clocks;
- `q235 Alloy Pact` — hidden conventions inferred through rotating force lanes;
- `q266 Palimpsest Probe` — causal diagnosis against a visible near-miss;
- `q297 Canopy Ledger` — conserved seed routing through a narrow store;
- `q328 Breakwater Survey` — set-cover sensing with a dormant first observation;
- `q359 Strata Rig` — multi-effect construction with reversible probing;
- `q390 Spore Delegation` — complementary marks at sparse shared events;
- `q421 Tapestry Revision` — wear-boundary recalibration after adjacency rewrite;
- `q452 Lockwater Lineage` — barge ancestry through carrier exchange;
- `q484 Moraine Dependency` — order-sensitive nested glacier prerequisites.

Batch 30:

- `q505 Alloy Frame` — billet motion composed with translating, rotating force lanes;
- `q536 Palimpsest Lesson` — conditional learning separated from a visible failed twin;
- `q567 Canopy Counter` — capacity-chunked opponent shaping;
- `q598 Breakwater Grammar` — grouped relay language with a dormant first command;
- `q629 Strata Sandbox` — reversible miniature tests with persistent evidence;
- `q660 Spore Analogy` — relational transfer across unequal colony clocks;
- `q691 Tapestry Evidence` — weighted stopping after evidence rewires adjacency;
- `q722 Lockwater Gradient` — conserved barge flow with identity exchange;
- `q753 Murmuration Obligation` — delayed identity debt guarded by parity;
- `q784 Moraine Rhythm` — macro-time glacier alignment coupled to an outer token.

Batch 31:

- `q205 Alloy Veil` — occluded billet updates in a moving force frame;
- `q236 Palimpsest Pact` — hidden conventions inferred against a failed offer;
- `q267 Canopy Probe` — capacity-buffered causal interventions;
- `q298 Breakwater Ledger` — conserved cargo with a dormant first transfer;
- `q329 Strata Survey` — reversible probes with persistent set-cover evidence;
- `q360 Spore Rig` — clock-gated construction at sparse shared events;
- `q391 Tapestry Delegation` — persistent marks followed by rewired choice;
- `q422 Lockwater Revision` — canal-law identification after carrier exchange;
- `q453 Murmuration Lineage` — ancestry tracking with a parity gate;
- `q485 Waystation Dependency` — dependency solving against repetition counters.

Batch 32:

- `q206 Prism Tide` — three-body parallax through a moving observation lens;
- `q237 Lantern Accord` — coalition inference coupled to a shared pledge;
- `q268 Rootline Injection` — chosen valve trials distinguish parent and polarity;
- `q299 Glasshouse Balance` — conserved thermal routing through phase valves;
- `q330 Echo Cartography` — rechargeable probes with persistent map knowledge;
- `q361 Reef Assembly` — ordered tool welding at compatible tide phases;
- `q392 Observatory Relay` — directional transforms over two partial memories;
- `q423 Frostline Amendment` — wear-triggered rule revision across carrier exchange;
- `q454 Masquerade Thread` — persistent lineage beneath independent mask rewrites;
- `q486 Cloudport Dependency` — weather-remapped resources across nested subgoals.

Batch 33:

- `q207 Shadow Orchard` — observer-relative shadows reveal hidden fruit motion;
- `q238 Signal Banquet` — ordered invitations identify a social convention;
- `q269 Mycelium Override` — temporal nutrient pulses discriminate causal networks;
- `q300 Aquifer Tithe` — water remains conserved through pumping and phase change;
- `q331 Lantern Census` — persistent evidence survives sensor remapping at base;
- `q362 Kitewright` — ordered components require coupled wind and tension;
- `q393 Submarine Chorus` — partial tones become ordered acoustic relays;
- `q424 Bloom Calendar` — archived evidence spans a seasonal rule revision;
- `q455 Puppet Provenance` — lineage persists beneath costume and position changes;
- `q487 Archive Staircase` — ordered subgoals use a shifting glyph dictionary.

Batch 34:

- `q208 Mirror Lanterns` — physical lights persist through reflected observer frames;
- `q239 Chorus Market` — bids identify both a norm and a trust regime;
- `q270 Circuit Cautery` — timed reversible clamps distinguish causal circuits;
- `q301 Color Foundry` — weighted pigment mass survives mixing and splitting;
- `q332 Planetarium Keys` — finite batteries constrain remapped telescope filters;
- `q363 Clockwork Menagerie` — assembly couples gear phase with pawl state;
- `q394 Hive Courier` — private dances become ordered comb deposits;
- `q425 Ember Doctrine` — banked samples span a heat-triggered law change;
- `q456 Fossil Carousel` — specimen identity survives pose reconstruction;
- `q488 Temple Scaffold` — dependency nodes require remapped supports.

Batch 35:

- `q209 Tidal Mosaic` — physical tiles persist through a rotating tidal view;
- `q240 Embassy Masks` — protocol and witness reliability are inferred jointly;
- `q271 River Dam Trials` — reversible gates distinguish delayed flood models;
- `q302 Seed Exchange` — crop units remain conserved across growth phases;
- `q333 Archive Microscope` — finite lamps constrain remapped slide filters;
- `q364 Balloon Atelier` — assembly couples pressure and valve state;
- `q395 Firefly Relay` — private flashes become ordered lantern deposits;
- `q426 Monsoon Edict` — banked samples span a rain-triggered revision;
- `q457 Shell Provenance` — creature identity survives shell-pattern changes;
- `q489 Skybridge Charter` — dependency spans require remapped permits.

Each implemented game has six levels, a distinct visual grammar, a known-win recording, a known-loss
recording, source-hash metadata, and seeded action fuzz coverage. These are qualified
engine prototypes, not sealed benchmark releases: random-policy resistance, human
calibration, and the paired default-versus-Tufa diagnostic runs remain open gates.

## Evaluation plan

### Stage 0: deterministic qualification

- import and instantiate under the pinned `arcengine` version;
- RESET and every advertised action are valid;
- frame shape is always 64x64 and every value is in the 16-color palette;
- known-win and known-loss recordings replay exactly;
- serialization/restoration is deterministic;
- random and mutation fuzzing find no crashes or invalid transitions;
- random-policy success is below the acceptance threshold outside the tutorial;
- a static audit catches text, digits, familiar clip art, semantic IDs in prompts, and
  accidental solution metadata.

The shared environment overlay is built from the metadata ledger rather than a hard-coded
game list:

```powershell
python scripts/build_research_games_bundle.py --partition gpt
```

The builder refuses source-hash mismatches, strips semantic titles from evaluator-visible
metadata, fixes both tar and gzip timestamps, and emits byte-identical bundles for identical
inputs. The same overlay is consumed by the default harness and Tufa.

### Stage 1: human calibration

- at least 10 first-exposure participants per environment for an initial baseline;
- record exploration actions, execution actions, resets, wall time, and level completion;
- reject games with poor rule legibility, tedious execution, strong color dependence, or
  failure concentrated in motor precision;
- calculate the upper-median best human action count per level for RHAE-compatible scoring.

### Stage 2: development diagnostics

Run the frozen ARC3 default harness and the frozen Tufa harness on identical game versions.
Use at least three seeds and report:

- levels completed and RHAE-compatible score;
- actions to first state change, first level, and terminal state;
- exploration-to-execution transition;
- repeated-state and no-impact action rates;
- generated tokens, wall time, and tokens per effective action;
- hypothesis revision events from traces;
- crash, retry, and compaction counts.

This stage is for debugging the environment and measuring complementarity. It is not the
cross-provider held-out result.

### Stage 3: sealed cross-provider evaluation

- Anthropic evaluates GPT-authored Partition A only.
- GPT evaluates Anthropic-authored Partition B only.
- Run order is randomized and hidden from the authoring side.
- The harness, prompt, model snapshot, and inference configuration are frozen once.
- Aggregate results are released only after both partitions finish.
- Report macro average across games, capability-family averages, uncertainty across seeds,
  and human-normalized efficiency. Do not rank systems from a single stochastic pass.

### Stage 4: harness-value study

For each permitted model/partition pair, use a paired design:

| Arm | Model | Harness | Purpose |
|---|---|---|---|
| A | same frozen model | ARC3 default | reference agent behavior |
| B | same frozen model | Tufa | estimate harness effect |

Pair runs on the same game version and seed. Primary estimand is the paired difference in
human-normalized environment score. Secondary estimands are action efficiency, token
efficiency, and the fraction of games with at least one level completed. Bootstrap games,
not individual actions, for confidence intervals.

## Distill-style article

The staging article should be one continuous narrative with live figures, not a dashboard
of disconnected cards.

1. **The observable island.** An interactive map places 25 official games, 22 Cellens
   games, 252 imported games, and the 1,000-game production program in separate rings,
   with the 400-game sealed evaluation subset visibly marked. Hovering
   a game reveals a thumbnail, action vocabulary, level count, and audited mechanics.
2. **What does a game measure?** A scroll-linked causal diagram separates perception,
   intervention, belief update, planning, execution, and transfer. Trace excerpts animate
   through the diagram.
3. **Coverage, with uncertainty.** A matrix shows mechanic families by corpus. Filled
   cells mean source-verified evidence; hatched cells mean speculative/manual labels. The
   public-set limitation is always visible.
4. **The missing-mechanics hypotheses.** Small interactive toy diagrams demonstrate active
   observation, social inference, conservation, counterfactual planning, and tool building.
5. **From idea to environment.** A single game progresses from specification through eight
   levels, showing how composition creates difficulty without visual obscurity.
6. **A contamination-aware benchmark.** A split diagram explains the GPT/Anthropic author
   and evaluator separation, frozen hashes, delayed publication, and why Qwen diagnostics
   are not held-out scores.
7. **Evidence.** Human curves, default-vs-Tufa paired results, score distributions, and
   execution traces share a common hover/lock interaction.
8. **Open artifacts.** After evaluation freeze, publish source, recordings, validation
   reports, hashes, and the exact site data snapshot.

## Immediate production order

1. Complete random-policy resistance and static semantic audits for Batch 01.
2. Run first-exposure human calibration before changing any mechanics or budgets.
3. Execute paired ARC3-default and Tufa diagnostic runs on the immutable Batch 01 hashes.
4. Promote only passing games from `prototype` to `qualified`; preserve failed versions.
5. Use the failure report—not contiguous ledger order—to select the ten capability-diverse
   games in Batch 02.

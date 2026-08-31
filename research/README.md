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

The first eighty production waves now contain seven hundred ninety-nine cross-mechanic prototypes in addition
to `q001 Quiet Field`. `research/gpt-batch01-v1.json` through
`research/gpt-batch80-v1.json` are the content-hashed batch manifests. Each wave samples
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

Batch 36:

- `q210 Aurora Parallax` — physical light bands persist across polar views;
- `q241 Festival Oaths` — public replies depend on the interrogation path;
- `q272 Geode Resonance` — ordered strikes expose causal hysteresis;
- `q303 Loom Dye Ledger` — weighted dye survives braiding and unbraiding;
- `q334 Meteor Survey` — orbital remapping constrains telescope passes;
- `q365 Orchestra Workshop` — installed parts alter beat and mute state;
- `q396 Coral Signal` — relay transmission destroys local memory;
- `q427 Eclipse Law` — observing advances the rule boundary;
- `q458 Caravan Seals` — ownership persists independently from seals;
- `q490 Cavern Charter` — chamber dependencies require remapped keystones.

Batch 37:

- `q211 Periscope Current` — spatial controls rotate with the observer frame;
- `q242 Choir Tokens` — each social reply rewrites a shared token;
- `q273 Terrarium Levers` — interventions retain ecological carryover;
- `q304 Glass Bead Exchange` — weighted bead mass survives fusion and splitting;
- `q335 Beacon Triangulation` — rotating bearings constrain finite observations;
- `q366 Marionette Forge` — installed joints rewrite phase and latch state;
- `q397 Mountain Semaphore` — transmitted flags erase local memory;
- `q428 Tundra Revision` — observation itself advances thaw;
- `q459 Stamp Lineage` — authorship persists independently from postmarks;
- `q492 Orchard Scaffold` — dependency terraces require remapped braces.

Batch 38:

- `q213 Kaleidoscope Ferry` — spatial controls couple rotation and reflection;
- `q244 Rumor Potluck` — each reply nonlinearly rewrites a shared rumor;
- `q275 Weather Vane Trials` — interventions retain atmospheric carryover;
- `q306 Ice Crystal Exchange` — weighted crystal mass survives cleavage;
- `q337 Fossil Scanner` — remapped beams constrain finite scans;
- `q368 Clockwork Kitchen` — ingredients rewrite timer and latch state;
- `q399 Cloud Choir` — transmitted tones erase local memory;
- `q430 Orchard Season` — observation itself advances the calendar;
- `q461 Gallery Provenance` — creators persist independently from frames;
- `q493 Aqueduct Scaffold` — channel dependencies require remapped braces.

Batch 39:

- `q214 Gravity Lantern` — rotated controls combine with automatic gravity drift;
- `q245 Trust Auction` — bids rewrite capital while role and trust remain latent;
- `q276 Catalyst Garden` — intervention pulses retain refractory causal memory;
- `q307 Alchemy Ledger` — unequal token weights survive reversible reactions;
- `q338 Survey Drone` — mobile, phased observations consume rechargeable capacity;
- `q369 Circuit Weaver` — installed components rewrite phase and latch state;
- `q400 Ant Relay` — directional relays erase each local scent memory;
- `q431 Tide Statute` — observation itself advances the tide boundary;
- `q462 Mask Custody` — actors persist independently from changing masks;
- `q494 Tower Dependency` — floor dependencies require remapped support permits.

Batch 40:

- `q215 Waystation Veil` — focused regions freeze while hidden dunes and a rival evolve;
- `q246 Backstage Pact` — latent conventions drive a thresholded offer meter;
- `q277 Catalyst Probe` — looking stores orientations that hiding later executes;
- `q308 Asterism Ledger` — evidence survives a reset between experiment and execution;
- `q339 Reedbed Survey` — each bounded sample also rewires later access;
- `q370 Vault Rig` — reusable hardware couples two resource rings;
- `q401 Pollen Delegation` — destructive relays cross a visible rule change;
- `q432 Semaphore Revision` — two test systems recalibrate rule and delay;
- `q463 Impeller Lineage` — ancestors survive split, merge, masks, and costly samples;
- `q495 Vivarium Dependency` — shared subgoals depend on partner reciprocity.

Batch 41:

- `q525 Vivarium Frame` — local motion composes with rotating strata and reciprocity;
- `q556 Crossing Lesson` — conditional demonstrations span alternating partial controllers;
- `q587 Spectrum Counter` — opponent shaping transfers across representations;
- `q618 Escapement Grammar` — grouped gear messages isolate a fault;
- `q649 Monsoon Sandbox` — evidence survives resettable unequal-cycle simulations;
- `q680 Workbench Analogy` — fixture relations transfer with identity-bound debt;
- `q711 Aurora Gradient` — capacity and phase drive a hysteretic threshold;
- `q742 Tide Obligation` — causal identity carries a delayed irreversible return;
- `q773 Ember Rhythm` — interruption shares fuel with observation and repair;
- `q794 Tessera Rhythm` — compressed seam routines require a precise interruption.

Batch 42:

- `q216 Backstage Veil` — focused scenes freeze amid hidden motion and signed accumulation;
- `q247 Catalyst Pact` — social offers store orientations for later execution;
- `q278 Asterism Probe` — causal evidence survives reset between experiment and repair;
- `q309 Reedbed Ledger` — conserved salinity transfers rewire the route;
- `q340 Vault Survey` — bounded echo evidence shares two conserved quantities;
- `q371 Pollen Rig` — assembly crosses a visible complement rule change;
- `q402 Semaphore Delegation` — alternating destructive relays precede one policy;
- `q433 Impeller Revision` — two costly samples recalibrate a worn law;
- `q464 Tessera Lineage` — ancestry folds through a state-window macro;
- `q496 Crossing Dependency` — alternating partial controllers build shared prerequisites.

Batch 43:

- `q217 Catalyst Veil` — attention freezing combines with stored-view execution;
- `q248 Asterism Pact` — social evidence survives reset between test and commitment;
- `q279 Reedbed Probe` — causal repairs rewire marsh connectivity;
- `q310 Vault Ledger` — two quantities remain conserved in shared vessels;
- `q341 Pollen Survey` — finite evidence crosses a visible complement change;
- `q372 Semaphore Rig` — reusable parts require agreement from two test systems;
- `q403 Impeller Delegation` — destructive relay penalizes redundant samples;
- `q434 Tessera Revision` — wear recalibration precedes a macro interruption;
- `q465 Vivarium Lineage` — ancestry carries partner favor through splits;
- `q497 Spectrum Dependency` — one prerequisite graph transfers across frames.

Batch 44:

- `q218 Asterism Veil` — attention freezing combines with evidence-preserving reset;
- `q249 Reedbed Pact` — each social offer rewires a constructed route;
- `q280 Vault Probe` — causal diagnosis tracks two conserved quantities;
- `q311 Pollen Ledger` — visible wear complements a conserved transfer law;
- `q342 Semaphore Survey` — bounded evidence joins two miniature systems;
- `q373 Impeller Rig` — assembly requires exactly two nonredundant samples;
- `q404 Tessera Delegation` — controller evidence meets a macro window;
- `q435 Vivarium Revision` — partner favor follows a revised law;
- `q466 Crossing Lineage` — alternating controllers integrate passenger ancestry;
- `q498 Escapement Dependency` — one fault intervention unlocks nested gears.

Batch 45:

- `q219 Reedbed Veil` — attention scheduling changes salinity and causeway connectivity;
- `q250 Vault Pact` — hidden offer conventions share two conserved resources;
- `q281 Pollen Probe` — causal signatures complement after a visible wear boundary;
- `q312 Semaphore Ledger` — global stock survives two miniature relay tests;
- `q343 Impeller Survey` — only nonredundant wake samples fit the evidence budget;
- `q374 Tessera Rig` — dual-effect components feed a state-window macro interrupt;
- `q405 Vivarium Delegation` — alternating partial views leave marks and reciprocal help;
- `q436 Crossing Revision` — disjoint controllers recalibrate a visibly worn ferry law;
- `q467 Spectrum Lineage` — ancestry persists through splits, merges, and appearance swaps;
- `q499 Monsoon Dependency` — shared weather prerequisites unlock at unequal-cycle phase pairs.

Batch 46:

- `q220 Vault Veil` — one observed chamber freezes while two conserved resources circulate;
- `q251 Pollen Pact` — a social response convention complements after visible wear;
- `q282 Semaphore Probe` — causal identification joins two miniature relay systems;
- `q313 Impeller Ledger` — rotor stock stays conserved while duplicate samples cost extra;
- `q344 Tessera Survey` — seam evidence gates an interruptible topology macro;
- `q375 Vivarium Rig` — dual-effect habitat tools interact with partner reciprocity;
- `q406 Crossing Delegation` — disjoint passenger and dock projections meet through marks;
- `q437 Spectrum Revision` — a worn relational rule transfers across visual domains;
- `q468 Escapement Lineage` — ancestry tracking composes with fault-discriminating probes;
- `q500 Workbench Dependency` — shared fixtures create helper-identity obligations that must be repaid.

Batch 47:

- `q221 Pollen Veil` — attention-frozen bloom dynamics complement after visible wear;
- `q252 Semaphore Pact` — one social convention is inferred across two signal courts;
- `q283 Impeller Probe` — redundant wake interventions consume a strict evidence budget;
- `q314 Tessera Ledger` — conserved stock passes through an interruptible seam macro;
- `q345 Vivarium Survey` — bounded temperature samples interact with partner favor;
- `q376 Crossing Rig` — ferry hardware construction requires alternating controller marks;
- `q407 Spectrum Delegation` — partial prism views integrate across relational domains;
- `q438 Escapement Revision` — a worn gear law is recalibrated by fault intervention;
- `q469 Monsoon Lineage` — rain-seed ancestry must meet a sparse phase pair;
- `q502 Tide Frame` — moving local shell coordinates precede an evidence-gated exchange.

Batch 48:

- `q223 Impeller Veil` — focus-controlled hidden rotor updates make duplicate wake samples costly;
- `q231 Aurora Pact` — a hidden offer convention unfolds under hysteretic curtain control;
- `q261 Aurora Probe` — causal ray models must be separated across hysteretic intervention frames;
- `q291 Aurora Ledger` — conserved crystal stock rotates through a direction-reversing curtain sweep;
- `q321 Aurora Survey` — a finite evidence budget prices samples taken in distinct control states;
- `q351 Aurora Rig` — component-built dual-effect tools alter a hysteretic route state;
- `q381 Aurora Delegation` — alternating partial views leave controller marks for later integration;
- `q411 Aurora Revision` — wear changes the crystal law while delayed effects require recalibration;
- `q441 Aurora Lineage` — ancestry persists through split, merge, appearance rotation, and reversal;
- `q503 Ember Frame` — movement, frame transforms, and observation consume one shared fuel reserve.

Batch 49:

- `q224 Tessera Veil` — an occlusion macro must be interrupted at a seam-defined phase;
- `q254 Tessera Pact` — offer-convention inference is coupled to timed topology interruptions;
- `q262 Tide Probe` — bounded causal probes precede one irreversible repair;
- `q292 Tide Ledger` — conserved shell stock moves through reversing currents before sealing;
- `q322 Tide Survey` — distinct current samples must justify an irreversible route commitment;
- `q352 Tide Rig` — dual-effect components are assembled before a one-way launch;
- `q382 Tide Delegation` — disjoint controller marks are integrated before irreversible handoff;
- `q412 Tide Revision` — a worn current law is recalibrated before delayed effects are committed;
- `q442 Tide Lineage` — split, merge, and appearance histories identify an ancestor at a one-way gate;
- `q506 Palimpsest Frame` — near-miss failed examples reveal composition in a moving archive frame.

Batch 50:

- `q225 Vivarium Veil` — attention-dependent fauna updates are conditioned by remembered partner favor;
- `q255 Vivarium Pact` — colony responses combine a hidden offer convention with reciprocity;
- `q285 Vivarium Probe` — causal diagnosis and irreversible repair must preserve a fair partner state;
- `q293 Ember Ledger` — conserved vessel transfers, heat movement, and repairs share one fuel reserve;
- `q323 Ember Survey` — evidence collection, heat movement, and route commitment consume the same fuel;
- `q353 Ember Rig` — component collection, dual-effect assembly, and activation compete for fuel;
- `q383 Ember Delegation` — partial views, marks, controller handoffs, and integration all consume fuel;
- `q413 Ember Revision` — sparse recalibration of a worn heat law is priced against repair fuel;
- `q443 Ember Lineage` — split, merge, appearance, and ancestry operations deplete one reserve;
- `q507 Canopy Frame` — moving orchard frames compose through a capacity-limited intermediate store.

Batch 51:

- `q226 Crossing Veil` — attention scheduling across capped docks is split between marked controllers;
- `q256 Crossing Pact` — a hidden offer convention is inferred from two controller projections;
- `q286 Crossing Probe` — controller-specific causal evidence precedes one irreversible ferry repair;
- `q316 Crossing Ledger` — conserved passenger stock moves through capped, partially observed docks;
- `q324 Honeycomb Survey` — bounded scent evidence must be interpreted across local and hive clocks;
- `q354 Honeycomb Rig` — assembly effects depend on both the current action cycle and enclosing cycle;
- `q384 Honeycomb Delegation` — alternating controller marks are integrated under nested clocks;
- `q414 Honeycomb Revision` — a worn scent law is recalibrated while two clocks advance;
- `q444 Honeycomb Lineage` — courier ancestry survives transformations across nested cycles;
- `q508 Breakwater Frame` — an early harbor intervention remains dormant through two solved subgoals.

Batch 52:

- `q227 Spectrum Veil` — attention-dependent packet updates preserve one relation across domains;
- `q257 Spectrum Pact` — a hidden convention transfers from geometric panes to unrelated agents;
- `q287 Spectrum Probe` — causal evidence shares an algebra across domains before irreversible repair;
- `q317 Spectrum Ledger` — conserved packet stock survives a change of relational representation;
- `q347 Spectrum Survey` — bounded evidence must cover relations rather than repeated surface samples;
- `q355 Alloy Rig` — dual-effect foundry assembly is expressed in a translating, rotating frame;
- `q385 Alloy Delegation` — controller marks are integrated after the local frame moves;
- `q415 Alloy Revision` — a worn billet law is recalibrated in local rather than screen coordinates;
- `q445 Alloy Lineage` — billet ancestry survives splits, merges, appearance swaps, and frame motion;
- `q509 Strata Frame` — physical probe state can be undone while acquired knowledge persists.

Batch 53:

- `q228 Escapement Veil` — scheduled attention is coupled to one fault-separating clock intervention;
- `q258 Escapement Pact` — a stable offer convention is inferred despite a shared mechanical fault;
- `q288 Escapement Probe` — bounded model evidence precedes an irreversible fault repair;
- `q318 Escapement Ledger` — conserved weight stock moves through a diagnosed clockwork phase;
- `q348 Escapement Survey` — evidence budget and redundancy constrain fault-specific sampling;
- `q378 Escapement Rig` — collected parts become an instrument that reveals the active fault;
- `q386 Palimpsest Delegation` — two readers integrate partial marks by comparing a visible near miss;
- `q416 Palimpsest Revision` — explicit failed examples recalibrate a drifting archive rule;
- `q446 Palimpsest Lineage` — failed exemplars disambiguate ancestry across split, merge, and appearance;
- `q510 Spore Frame` — two greenhouse schedules meet at progressively sparser frame-aligned contacts.

Batch 54:

- `q229 Monsoon Veil` — attention releases hidden rain updates while two weather cycles advance;
- `q259 Monsoon Pact` — a hidden convention must be committed at a shared storm phase;
- `q289 Monsoon Probe` — weather causes are diagnosed before a phase-aligned irreversible repair;
- `q319 Monsoon Ledger` — conserved rain stock moves globally under unequal reservoir cycles;
- `q349 Monsoon Survey` — bounded samples must cover the evidence needed at a sparse policy window;
- `q379 Monsoon Rig` — a reusable rain instrument is assembled and activated at joint phase;
- `q409 Monsoon Delegation` — two forecast readers integrate persistent marks across unequal cycles;
- `q417 Canopy Revision` — a worn orchard law is recalibrated through a capacity-limited store;
- `q447 Canopy Lineage` — seed ancestry survives transformations and constrained store ordering;
- `q529 Monsoon Frame` — local rain controls compose with moving global weather coordinates.

Batch 55:

- `q230 Workbench Veil` — attention-dependent tools borrow help that remains bound to the helper;
- `q260 Workbench Pact` — convention evidence and delayed reciprocity refer to persistent agents;
- `q290 Workbench Probe` — a fixture repair waits until every diagnostic helper is repaid;
- `q320 Workbench Ledger` — temporary loans preserve global stock and helper-specific debt;
- `q350 Workbench Survey` — bounded evidence must account for identity-bound sensor favors;
- `q380 Workbench Rig` — reusable tool assembly creates obligations to the supplying helpers;
- `q410 Workbench Delegation` — controller marks and handoff debts are integrated by identity;
- `q440 Workbench Revision` — wear-driven recalibration preserves the helper attached to each favor;
- `q448 Breakwater Lineage` — a first intervention remains dormant across two solved subgoals;
- `q512 Lockwater Frame` — barge identity survives exchanged appearance, position, and local frames.

Batch 56:

- `q120 Hidden Policy Handoff` — control transfers mid-demonstration without resetting latent state;
- `q130 Rhythm Rival` — an adaptive opponent opens only under deliberate irregular cadence;
- `q140 Grounded Labels` — player-created class markers become reusable worker commands;
- `q150 Minimum Regret` — route selection minimizes worst-case loss and preserves recovery;
- `q160 Tool Metamorphosis` — a mechanical relation transfers into autonomous coordination;
- `q170 Commit Threshold` — decision-specific evidence requirements must be calibrated from feedback;
- `q180 Gradient Climb` — only local field changes guide ascent through deceptive plateaus;
- `q190 Lasting Shortcut` — one route intervention permanently changes every later level;
- `q200 Clock of Clocks` — completed local periods trigger a higher-level temporal machine;
- `q471 Aurora Dependency` — shared prerequisites are reused through a visible hysteresis loop.

Batch 57:

- `q531 Aurora Lesson` — conditional demonstrations transfer through ineffective gestures and context hysteresis;
- `q561 Aurora Counter` — a legible opponent is shaped through hysteretic counterplay;
- `q591 Aurora Grammar` — grouped relay symbols compose under changing channel state;
- `q621 Aurora Sandbox` — simulated and committed copies share persistent evidence but not progress;
- `q651 Aurora Analogy` — a curtain relation transfers into an independent mote system;
- `q681 Aurora Evidence` — unequal evidence reliability determines when stopping is safe;
- `q712 Tide Gradient` — conserved influence, capacity, and phase constrain an irreversible threshold;
- `q741 Aurora Obligation` — delayed obligations remain attached to identity despite immediate rewards;
- `q771 Aurora Rhythm` — chunked rhythms and scaled intervals define interruption windows;
- `q472 Tide Dependency` — shared prerequisites must survive reversing current before irreversible commitment.

Batch 58:

- `q533 Ember Lesson` — a conditional kiln policy must be transferred without copying an effort-wasting gesture;
- `q564 Honeycomb Counter` — a legible rival is shaped while local treatments advance an outer apiary clock;
- `q593 Ember Grammar` — grouping and spatial relay operations compose under one finite effort budget;
- `q623 Ember Sandbox` — evidence persists when disposable simulations reset before one commitment;
- `q653 Ember Analogy` — a heat-band relation transfers to clay vessels despite surface transformation;
- `q683 Ember Evidence` — limited effort calibrates only the unequal observations needed for safe stopping;
- `q713 Ember Gradient` — conserved mass, heat, and phase jointly determine an observed commit threshold;
- `q743 Ember Obligation` — debt remains attached to causal identity after vessel swaps and distracting rewards;
- `q774 Honeycomb Rhythm` — local routine chunks compose into outer-clock interruption windows;
- `q473 Ember Dependency` — stored heat is reused across increasingly nested vessel and tempering prerequisites.

Batch 59:

- `q537 Canopy Lesson` — conditional policy transfer must respect capacity-sensitive seed ordering;
- `q565 Alloy Counter` — local tactics shape a rival through a translating and rotating frame;
- `q595 Alloy Grammar` — grouped relational symbols are decoded only after frame transformation;
- `q627 Canopy Sandbox` — branch evidence survives resets of a hard-capacity simulation store;
- `q655 Alloy Analogy` — a relation transfers exactly despite translation and rotation;
- `q685 Alloy Evidence` — unequal causal evidence must be recovered from rotating visible slots;
- `q715 Alloy Gradient` — conserved billet influence is measured in a phase-sensitive moving frame;
- `q745 Alloy Obligation` — causal debt survives object swaps and reference-frame rotation;
- `q775 Alloy Rhythm` — routine chunks reach interruption windows expressed in moving coordinates;
- `q475 Alloy Dependency` — a single frame-relative catalyst is reused across nested assemblies.

Batch 60:

- `q539 Strata Lesson` — a physical probe is undone while its observation remains available to the policy;
- `q569 Strata Counter` — reversible probes shape a rival through knowledge that survives restoration;
- `q596 Palimpsest Grammar` — one causal relation is isolated from an overwritten near-miss message;
- `q626 Palimpsest Sandbox` — failed-branch evidence survives disposable simulation resets;
- `q657 Canopy Analogy` — seasonal relations transfer through a hard-capacity seed store;
- `q686 Palimpsest Evidence` — unequal evidence remains usable after its visible trace is erased;
- `q716 Palimpsest Gradient` — a visible near miss identifies how to cross a conserved threshold;
- `q746 Palimpsest Obligation` — failed repayment reveals the identity retaining delayed debt;
- `q776 Palimpsest Rhythm` — a failed interruption persists as evidence for a later macro window;
- `q476 Palimpsest Dependency` — one missing-prerequisite trace repairs increasingly many branches.

Batch 61:

- `q538 Breakwater Lesson` — the first harbor intervention wakes only after two solved subgoals;
- `q568 Breakwater Counter` — rival shaping precedes activation of a delayed terminal counter;
- `q599 Strata Grammar` — a composed message survives physical restoration as persistent knowledge;
- `q630 Spore Sandbox` — simulation evidence can be committed only at sparse unequal-clock alignments;
- `q658 Breakwater Analogy` — a latent transform activates after two branches before relational transfer;
- `q688 Breakwater Evidence` — the first unequal sample remains dormant until two subgoals are solved;
- `q717 Canopy Gradient` — conserved seed influence is routed through a capacity-limited seasonal store;
- `q748 Breakwater Obligation` — the first creditor wakes after two tasks and constrains repayment by identity;
- `q778 Breakwater Rhythm` — a timing offset activates only after two completed routines;
- `q478 Breakwater Dependency` — one delayed key governs every later terminal assembly.

Batch 62:

- `q540 Spore Lesson` — conditional policy transfer is coordinated at sparse unequal-clock events;
- `q570 Spore Counter` — repeated shaping rounds align autonomous treatment clocks;
- `q600 Spore Grammar` — grouped messages are relayed only at shared schedule events;
- `q624 Honeycomb Sandbox` — simulation evidence survives resets until nested-clock commitment;
- `q654 Honeycomb Analogy` — relation transfer occurs only at local and outer-clock boundaries;
- `q684 Honeycomb Evidence` — safe stopping is constrained to nested-clock boundaries;
- `q720 Spore Gradient` — conserved distribution reaches a phase threshold at unequal-clock alignment;
- `q750 Spore Obligation` — identity debt is repaid only when clocks align;
- `q779 Strata Rhythm` — timing knowledge persists after a physical probe is undone;
- `q474 Honeycomb Dependency` — shared nectar prerequisites assemble at local-cycle boundaries.

Batch 63:

- `q551 Pollen Lesson` — a conditional policy is transferred across a visible wear-triggered complement;
- `q581 Pollen Counter` — opponent shaping crosses a wear boundary that complements its update law;
- `q611 Pollen Grammar` — grouped messages compose through a wear-complemented relay;
- `q641 Pollen Sandbox` — simulation evidence persists while reset state crosses a rule change;
- `q671 Pollen Analogy` — relational structure transfers after its mapping becomes the complement;
- `q701 Pollen Evidence` — unequal samples support safe stopping across an evidence inversion;
- `q731 Pollen Gradient` — conserved bloom mass moves through channels reversed by wear;
- `q761 Pollen Obligation` — identity debt survives a wear-triggered exchange of visible positions;
- `q791 Pollen Rhythm` — an autonomous period changes before a state-defined interruption window;
- `q513 Murmuration Frame` — local flight composes with a rotating wake and a three-view parity audit.

Batch 64:

- `q519 Reedbed Frame` — rotating local controls interact with links that change route and function;
- `q549 Reedbed Lesson` — conditional policy applications also rewire the route they must use;
- `q579 Reedbed Counter` — opponent-shaping treatments jointly alter rival state and connectivity;
- `q609 Reedbed Grammar` — grouped relay glyphs compose meaning while changing the relay graph;
- `q639 Reedbed Sandbox` — evidence persists while temporary simulated functions and links reset;
- `q669 Reedbed Analogy` — relational structure transfers through function-changing bridges;
- `q699 Reedbed Evidence` — unequal sensor components grow a network until stopping is safe;
- `q729 Reedbed Gradient` — conserved mass crosses links that change channel capacity;
- `q789 Reedbed Rhythm` — a constructed link changes period before a state-defined interruption;
- `q477 Canopy Dependency` — one shared glider serves nested branches through a capacity-limited store.

Batch 65:

- `q517 Catalyst Frame` — stored orientation executes after pipe-frame motion changes its global meaning;
- `q547 Catalyst Lesson` — a conditional demonstration is stored before context changes and execution;
- `q577 Catalyst Counter` — rival state is shaped, observed, and later executed from memory;
- `q607 Catalyst Grammar` — a composed relay code survives subsequent pipe transforms;
- `q637 Catalyst Sandbox` — observed orientations persist when physical simulation copies reset;
- `q667 Catalyst Analogy` — a source relation is stored before surface transforms and target transfer;
- `q727 Catalyst Gradient` — observed pipe directions later execute hidden conserved transfers;
- `q757 Catalyst Obligation` — stored helper identity survives hidden borrowing and appearance swaps;
- `q787 Catalyst Rhythm` — an interruption phase survives intervening macro-routines;
- `q479 Strata Dependency` — restored probes leave knowledge that unlocks one reusable support.

Batch 66:

- `q520 Vault Frame` — two conserved echo types route through containers in a moving local frame;
- `q550 Vault Lesson` — conditional policy transfer maintains two independent shared-container ledgers;
- `q580 Vault Counter` — opponent shaping depends on both conserved echo distributions;
- `q610 Vault Grammar` — grouped operations redistribute two ledgers before decoding;
- `q640 Vault Sandbox` — dual-ledger evidence persists when miniature vaults reset;
- `q670 Vault Analogy` — relational transfer preserves separate source and target ledgers;
- `q700 Vault Evidence` — unequal samples move two conserved types until stopping is safe;
- `q730 Vault Gradient` — two quantities share capacity-limited chambers under phase rotation;
- `q760 Vault Obligation` — two-quantity debts remain attached to identities after swaps;
- `q777 Canopy Rhythm` — a capacity-limited seed store persists through macro timing.

Batch 67:

- `q516 Backstage Frame` — signed pressure accumulates through rotating local sightline frames;
- `q546 Backstage Lesson` — policy transfer depends on threshold distance and signed direction;
- `q576 Backstage Counter` — rival shaping depends on signed pressure and direction;
- `q606 Backstage Grammar` — grouped glyphs compose signed pressure through a direction-changing relay;
- `q636 Backstage Sandbox` — signed evidence persists when physical stage values reset;
- `q696 Backstage Evidence` — safe stopping crosses a visible direction turn;
- `q726 Backstage Gradient` — conserved stage mass crosses direction-reversing controls;
- `q756 Backstage Obligation` — signed pressure debt stays attached to mask identity;
- `q786 Backstage Rhythm` — macro-routines flip direction before an exact interruption window;
- `q677 Spectrum Analogy` — affine magnitude and direction transfer across unlike surfaces.

Batch 67 makes direction as important as distance to threshold. Nine rotating-theater tasks
accumulate signed stage pressure through frame rotations, context switches, rival shaping,
grouped relays, reset simulations, unequal evidence, conserved flow, identity debt, and
macro-time. A prism-gallery analogy transfers an affine pair—magnitude and direction—from
geometry to agents despite unrelated surface features.

Batch 68:

- `q518 Asterism Frame` — local orbit actions compose with a precessing chart while observations survive reset;
- `q548 Asterism Lesson` — conditional star policies must be separated from empty gestures;
- `q578 Asterism Counter` — recent treatments and chart precession jointly shape a three-tactic rival;
- `q608 Asterism Grammar` — grouped glyphs are reversed, recolored, and rotated by precessing relays;
- `q638 Asterism Sandbox` — twin star systems reset physically while their evidence persists;
- `q668 Asterism Analogy` — cyclic gaps and precession transfer from geometry to an unlike surface;
- `q698 Asterism Evidence` — unequal samples stop only when no unseen star can reverse the margin;
- `q737 Spectrum Gradient` — conserved spectral mass crosses capacity-limited phase-rotated channels;
- `q758 Asterism Obligation` — light debts remain attached to identities through swaps and resets;
- `q788 Asterism Rhythm` — changing-period macro-orbits must be interrupted at a state-defined window.

Batch 68 moves from theatrical pressure to orbital relation reasoning. Nine bright observatory
tasks compose local actions with precessing charts across demonstrations, adversaries, language,
simulation, analogy, evidence, identity, and macro-time. A spectrum laboratory adds conserved
flow through rotating, capacity-limited channels. Dominant fields vary across blue, orange, pink,
charcoal, silver, white, and black rather than sharing one dark or red canvas.

Batch 69:

- `q515 Waystation Frame` — local caravan motion composes with shifting dune frames and repetition counters;
- `q545 Waystation Lesson` — conditional policy is separated from context switches and empty guide gestures;
- `q575 Waystation Counter` — the last two treatments and corridor shifts shape a three-tactic rival;
- `q605 Waystation Grammar` — paired glyphs compose through relays affected by recent group outputs;
- `q644 Tessera Sandbox` — folded mosaic copies reset physically while their intervention evidence persists;
- `q665 Waystation Analogy` — repetition-sensitive route transforms transfer from dunes to walkers;
- `q695 Waystation Evidence` — threefold sampling repetition can invert evidence before safe stopping;
- `q725 Waystation Gradient` — repeated routes shrink transfers through capacity-limited conserved bins;
- `q755 Waystation Obligation` — repeated borrowing adds tolls to identity-bound delayed cargo debt;
- `q785 Waystation Rhythm` — repeated macros alter the rival counter before a state-defined interruption.

Batch 69 makes short behavioral history causal. Nine warm caravan tasks expose the previous two
policies and require the solver to predict when repetition changes motion, instruction, opposition,
syntax, analogy, evidence, flow, debt, or timing. A bright folding-mosaic sandbox contributes a
different geometry for reset-persistent counterfactual evidence. Its thumbnails are checked against
all earlier generated thumbnails, preventing a visually identical cross-batch starting state.

Batch 70:

- `q523 Impeller Frame` — local blade motion composes with counter-rotating wake frames and sample cost;
- `q553 Impeller Lesson` — wake-conditioned demonstrations separate empty gestures from costly oversampling;
- `q562 Tide Counter` — recent shell treatments shape a rival before an irreversible sluice opens;
- `q613 Impeller Grammar` — paired blade glyphs compose through sampled counter-rotating relays;
- `q643 Impeller Sandbox` — turbine evidence persists across resets and grows costlier after discrimination;
- `q673 Impeller Analogy` — direction and blade gap transfer from wake diagrams to unlike riders;
- `q703 Impeller Evidence` — stopping must occur at first certainty before another wake probe adds excess cost;
- `q733 Impeller Gradient` — conserved blade mass circulates through four capacity-limited wake reservoirs;
- `q763 Impeller Obligation` — torque debt stays attached to three rider identities across ring rotation;
- `q793 Impeller Rhythm` — counter-rotating macros are interrupted at a sampled state-defined window.

Batch 70 treats information acquisition as an action with consequences. Nine industrial turbine
tasks combine counter-rotating wakes with local frames, instruction, syntax, simulation, analogy,
confidence, conserved flow, causal debt, and macro-time. Repeated sampling after discrimination
raises an explicit cost and can invalidate commitment. The tidal counter adds a separate irreversible
sluice that cannot safely open until the visible rival evidence supports one branch.

Batch 71:

- `q514 Moraine Frame` — local raft motion writes order-sensitive tokens into an outer dependency board;
- `q544 Moraine Lesson` — contextual raft policy separates empty gestures before updating an outer token;
- `q574 Moraine Counter` — a shaped rival state solves the selected outer glacier enclosure;
- `q619 Monsoon Grammar` — rain glyphs relay only at a phase pair of two unequal clocks;
- `q634 Moraine Sandbox` — persistent simulation evidence writes one outer token after physical reset;
- `q664 Moraine Analogy` — a transformed crevasse relation transfers into a selected dependency slot;
- `q694 Moraine Evidence` — decisive local evidence must become an outer token before stopping;
- `q724 Moraine Gradient` — conserved flow writes phase-indexed tokens into the outer board;
- `q754 Moraine Obligation` — identity-bound debt repayment writes values in completion order;
- `q799 Monsoon Rhythm` — rain macros are interrupted at a state-defined unequal-clock phase pair.

Batch 71 connects local success to a larger problem. Eight icy glacier tasks make every local
completion update a visible outer dependency board, so solving the right subproblem in the wrong
order can produce the wrong terminal state. Two saturated weather gardens test a different temporal
abstraction: the useful event is identified by a pair of unequal clock phases, not by a fixed action
count. Initial thumbnails remain globally collision-checked against earlier generated games.

Batch 72:

- `q526 Crossing Frame` — ferry motion crosses local dock frames through mandatory marked handoffs;
- `q555 Vivarium Lesson` — fair and unfair demonstrations reveal a reciprocal partner policy;
- `q586 Crossing Counter` — controller-specific treatments jointly shape a three-tactic ferry rival;
- `q616 Crossing Grammar` — disjoint glyph buffers compose through persistent nonverbal marks;
- `q646 Crossing Sandbox` — ferry copies reset while cross-controller simulation evidence persists;
- `q675 Vivarium Analogy` — temperature relations transfer through a fairness-dependent partner policy;
- `q706 Crossing Evidence` — safe stopping combines unequal samples from two controller projections;
- `q736 Crossing Gradient` — conserved passenger flow crosses controller-specific capacity edges;
- `q766 Crossing Obligation` — identity-bound fare debt is repaid using marked disjoint views;
- `q796 Crossing Rhythm` — two clock projections must be shared before a ferry macro is interrupted.

Batch 72 makes partial observability social rather than merely hidden. Eight vivid ferry tasks split
the relevant state between alternating controllers; switching without first leaving a persistent mark
is illegal, and later solutions must integrate several marks under capacity, evidence, identity, or
timing constraints. Two stacked terrariums test reciprocity and relational transfer under a partner
policy that changes with remembered fairness. Global thumbnail-collision checks remain mandatory.

Batch 73:

- `q527 Spectrum Frame` — packets compose motion through rotating and translating prism frames;
- `q558 Escapement Lesson` — contextual demonstrations separate diagnostic probes from a null gesture;
- `q590 Workbench Counter` — the last two tool treatments shape a visible three-tactic rival;
- `q617 Spectrum Grammar` — grouped color packets compose through meaning-changing prism relays;
- `q648 Escapement Sandbox` — physical clock trials reset while diagnostic evidence persists;
- `q678 Escapement Analogy` — gear-gap relations transfer to weights across fault rotations;
- `q710 Workbench Evidence` — unequal tool tests update a bounded margin and sampling cost;
- `q740 Workbench Gradient` — conserved tool mass flows through phase-dependent fixture capacities;
- `q767 Spectrum Obligation` — photon debt follows causal identity through packet exchanges;
- `q798 Escapement Rhythm` — nested gear cycles require a state-defined interruption phase pair.

Batch 73 changes the material vocabulary again: high-contrast prism galleries, nested clock towers,
and warm mobile workshops replace ferries and terrariums. The ten tasks distinguish screen position
from moving frames, surface imitation from conditional policy, physical resets from persistent
knowledge, and visible objects from causal identities. Their six-level curricula add relays, rival
memory, experiment histories, conservation, obligation, and nested time progressively.

Batch 74:

- `q524 Tessera Frame` — tessera motion composes across rotating and topology-changing seams;
- `q541 Tapestry Lesson` — contextual demonstrations reveal a policy that rewires the loom;
- `q572 Lockwater Counter` — a rival adapts while barges swap appearance but retain identity;
- `q603 Murmuration Grammar` — grouped flock messages use parity to expose a decoy symbol;
- `q632 Lockwater Sandbox` — canal state resets while identity-indexed wake evidence persists;
- `q652 Tide Analogy` — reversing-current relations transfer before an irreversible gate;
- `q692 Lockwater Evidence` — unequal gauge samples follow causal barge identities through swaps;
- `q723 Murmuration Gradient` — conserved flock mass crosses capacity-limited parity-tracked wakes;
- `q747 Canopy Obligation` — seed debt survives seasonal motion through a capacity-one store;
- `q781 Tapestry Rhythm` — a loom macro is interrupted after pattern completion rewires adjacency.

Batch 74 broadens both material appearance and causal structure. Folding mosaics, pale looms, blue
canals, open aviaries, a reset laboratory, a tidal basin, and a terraced orchard all use different
silhouettes and palettes. Across the curricula, topology changes, opponent memory, parity, persistent
knowledge, irreversible commitment, conservation, identity debt, and nested clocks become jointly
necessary rather than decorative state variables.

Batch 75:

- `q522 Semaphore Frame` — flag motion composes across moving relay frames and miniature tests;
- `q534 Honeycomb Lesson` — contextual courier demonstrations reveal a two-clock policy;
- `q582 Semaphore Counter` — recent treatments shape a rival across two visible testbeds;
- `q612 Semaphore Grammar` — grouped flag messages compose before tested policy commitment;
- `q622 Tide Sandbox` — shell state resets while observed current evidence persists;
- `q663 Murmuration Analogy` — geometric relations transfer to flocks under parity constraints;
- `q682 Tide Evidence` — unequal current samples update a costed stopping margin;
- `q714 Honeycomb Gradient` — conserved nectar crosses capacity edges under two clocks;
- `q762 Semaphore Obligation` — signal debt follows flag identity through relay tests;
- `q772 Tide Rhythm` — a reversing-current macro waits for a safe interruption window.

Batch 75 foregrounds visible information systems. Cliff semaphores expose relay frames and miniature
policy tests, apiaries separate courier time from colony time, tidal basins distinguish reversible
physical trials from persistent evidence, and a flock analogy adds a redundant parity constraint.
The final levels require combining these state channels rather than solving independent subpuzzles.

Batch 76:

- `q528 Escapement Frame` — gear-frame motion combines with exclusive diagnostic interventions;
- `q554 Tessera Lesson` — demonstrations reveal a contextual mosaic macro interruption;
- `q589 Monsoon Counter` — a weather rival adapts at unequal clock phase pairs;
- `q620 Workbench Grammar` — grouped tool messages write identity-bound relay debt;
- `q647 Spectrum Sandbox` — prism state resets while wavelength evidence persists;
- `q674 Tessera Analogy` — seam relations transfer across surfaces and macro windows;
- `q689 Strata Evidence` — reversible quarry probes accumulate persistent stopping evidence;
- `q739 Monsoon Gradient` — conserved rain mass crosses cells at useful phase pairs;
- `q768 Escapement Obligation` — weight debt survives diagnostic gear interventions;
- `q795 Vivarium Rhythm` — reciprocal fairness determines a two-clock interruption window.

Batch 76 combines seven visual grammars with stronger causal demands. The clock tasks require active
diagnosis and identity tracking; mosaic tasks distinguish demonstration from relation transfer;
weather tasks bind conserved quantities to unequal time; and the prism, quarry, workshop, and
terrarium tasks make persistent knowledge, symbolic debt, and reciprocal policy operational.

Batch 77:

- `q530 Workbench Frame` — tool motion composes across fixtures that write visible debt;
- `q543 Murmuration Lesson` — parity identifies a decoy in contextual flock demonstrations;
- `q584 Tessera Counter` — a mosaic rival adapts before a fold macro is interrupted;
- `q601 Tapestry Grammar` — completed patterns rewire the graph for later messages;
- `q633 Murmuration Sandbox` — flock state resets while parity evidence persists;
- `q662 Lockwater Analogy` — water relations transfer while barge identity changes surface cues;
- `q705 Vivarium Evidence` — partner fairness changes the policy behind sampled evidence;
- `q719 Strata Gradient` — conserved ore flow composes with persistent probe knowledge;
- `q744 Honeycomb Obligation` — courier debt survives local and colony clock updates;
- `q782 Lockwater Rhythm` — coupled water clocks interact with identity-preserving barge swaps.

Batch 77 spans eight object families and emphasizes causal state that survives visible rearrangement.
The tasks distinguish local frames from debt, demonstrations from parity-valid policy, physical resets
from knowledge, appearance from identity, and local timing from enclosing timing. These mechanisms
are introduced separately before being composed in each sixth level.

Batch 78:

- `q557 Spectrum Lesson` — contextual demonstrations transfer across prism surfaces;
- `q559 Monsoon Lesson` — weather policy depends on unequal phase pairs;
- `q571 Tapestry Counter` — rival adaptation composes with loom graph rewiring;
- `q592 Tide Grammar` — grouped shell messages precede irreversible tidal commitment;
- `q650 Workbench Sandbox` — fixture resets preserve tool-debt evidence;
- `q672 Semaphore Analogy` — relay relations transfer after miniature policy tests;
- `q693 Murmuration Evidence` — wind evidence requires a parity-consistent margin;
- `q734 Tessera Gradient` — conserved tile flow interacts with a macro window;
- `q751 Tapestry Obligation` — thread debt follows identity through graph rewiring;
- `q792 Semaphore Rhythm` — two tests ground a dual-clock signal interruption.

Batch 78 consumes ten of the final twenty-nine GPT-ledger concepts. Its visual systems range from
prism galleries and storm gardens to looms, tidal basins, workshops, aviaries, mosaics, and signal
yards. The batch preserves the distinction between these GPT-authored games and the separate
`a001`–`a200` Anthropic implementation queue.

Batch 79:

- `q560 Workbench Lesson` — contextual tool demonstrations separate null gestures from identity debt;
- `q585 Vivarium Counter` — keeper adaptation depends on recent treatment and reciprocal fairness;
- `q588 Escapement Counter` — diagnostic interventions distinguish clock faults before exploitation;
- `q602 Lockwater Grammar` — grouped barge messages compose while causal identities cross;
- `q615 Vivarium Grammar` — thermal syntax is interpreted through remembered reciprocity;
- `q631 Tapestry Sandbox` — miniature loom resets preserve evidence before graph commitment;
- `q642 Semaphore Sandbox` — two signal copies support one irreversible policy commit;
- `q661 Tapestry Analogy` — crossing-thread relations transfer after adjacency rewires;
- `q679 Monsoon Analogy` — storm relations transfer only at unequal phase pairs;
- `q702 Semaphore Evidence` — reliability-weighted samples determine calibrated stopping.

Batch 79 consumes ten more of the final GPT-ledger concepts, leaving nine for the eightieth wave.
Its pale workshops, stacked terrariums, cobalt clocks, lilac canals, paired miniature systems,
cream looms, peach weather panels, and gold signal towers use ten different canvas backgrounds.
The sixth levels compose retained identity, adaptive state, persistent evidence, graph change,
unequal timing, and stopping criteria rather than merely lengthening earlier action sequences.

Batch 80:

- `q704 Tessera Evidence` — weighted seam evidence composes with a fold-macro interruption;
- `q708 Escapement Evidence` — exclusive interventions localize a fault across nested phases;
- `q709 Monsoon Evidence` — sample reliability depends on unequal weather-clock pairs;
- `q732 Semaphore Gradient` — conserved signal mass crosses capacity-limited relays;
- `q735 Vivarium Gradient` — conserved fauna flow depends on thermal capacity and trust;
- `q764 Tessera Obligation` — mosaic debt follows identity through seams and macro timing;
- `q765 Vivarium Obligation` — fauna debt survives strata swaps and reciprocal updates;
- `q770 Workbench Obligation` — tool debt follows helper identity through reconfiguration;
- `q797 Spectrum Rhythm` — a prism macro is interrupted at a relational phase event.

Batch 80 is intentionally a nine-game ledger boundary rather than mixing authorship lineages.
Together with `q001 Quiet Field`, it completes all 800 implemented q-ledger concepts. The next
200 implementation slots correspond to `a001`–`a200`, whose `gpt-seeded-anthropic-build`
concept lineage must remain explicit even if implementation and evaluation provenance differ.

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

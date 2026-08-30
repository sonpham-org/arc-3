# Flash-game mechanics survey for ARC3 environment design

Status: corpus audit and first synthesis pass, 29 August 2026

## Scope and honesty

“Every Flash game on the internet” is not a finite or recoverable set. Games were lost,
duplicated across portals, removed by authors, or depended on dead servers. The defensible
version of that ambition is:

1. enumerate every Flash game record in the largest public preservation snapshot we can
   query locally;
2. inspect its complete mechanic-tag distribution rather than reading only best-of lists;
3. review unusually generative games and design criticism from several independent scenes;
4. retain portable mechanic atoms, not themes, artwork, level layouts, names, or code;
5. compare every proposed ARC3 environment against our existing corpora before building.

This pass enumerated all `arcade` records whose primary platform alias is `Flash` in the
Flashpoint SQLite snapshot published 20 March 2024. The database is 414,613,504 bytes with
SHA-256 `e101e5cb012b54ac9f2e8a2e20909ed467e27c88a1e5eb1159d1187e34919686`.
The external database is not committed. `scripts/analyze_flashpoint_corpus.py` regenerates
the aggregate artifacts in this repository.

The audit found:

- 169,962 archived game records across all platforms;
- 129,019 distinct Flash game records (75.91% of the archived game table);
- 129,015 Flash records with tags;
- 76,519 with an original description;
- 50,419 with a non-empty release date;
- 268 genre tags used by at least one Flash record.

This is complete **metadata enumeration**, not a claim that we manually played 129,019
games. Tags and descriptions are discovery aids. A game becomes prior art only after a
human source/play review confirms the mechanic.

Primary corpus references:

- [Flashpoint collection search and downloadable master-list documentation](https://flashpointarchive.org/datahub/Searching_the_Collection)
- [Flashpoint tag taxonomy](https://flashpointarchive.org/datahub/Tags)
- [Flashpoint database API](https://github.com/FlashpointProject/flashpoint-database-api)
- [Internet Archive Software Library: Flash](https://archive.org/details/softwarelibrary_flash)
- [Newgrounds game browser](https://www.newgrounds.com/games/browse)
- [Kongregate game browser](https://www.kongregate.com/en/games)
- [Armor Games classic catalog](https://armorgames.com/category/classic-games)
- [Nitrome catalog](https://www.nitrome.com/search.php?id=game&search_type=default)

## Why this corpus is valuable

Flash reduced the cost of publishing a small interactive idea. The resulting ecology was
not merely a set of polished hits; it was a large public laboratory of tiny verbs,
one-screen systems, toy-like interfaces, rule jokes, construction tools, strange sensors,
and genre mutations. The historical synthesis at
[Flash Game History](https://flashgamehistory.com/) describes the medium as an
experimental playground for distilling games to compact engaging elements, while the
[Flash Games Postmortem](https://www.gdcvault.com/play/1023967/The-Flash-Games)
documents the wider development ecosystem.

The corpus is distributed rather than attributable to one portal. In this snapshot the
largest normalized source domains include Newgrounds (9,004 records), Kongregate (6,205),
DeviantArt (5,210), Y8 (2,754), Armor Games (2,024), Addicting Games (954), and many
thousands of smaller sources. Armor's own classic page exposes 1,754 pre-2010 titles;
Nitrome describes a back catalog of more than 130 Flash games. The value is therefore in
the long tail, not only the canonical top fifty.

## What frequency does and does not tell us

The largest labels are broad: Adventure (22,348), Arcade (22,037), Puzzle (21,158),
Escape the Room (16,931), Dress Up (11,758), Score-Attack (9,994), and Simulation (9,529).
This warns against treating popularity as mechanic diversity. The most common tag pair is
Adventure plus Escape the Room (16,871 records), which reflects extensive production and
reskinning around a stable template.

The smaller mechanic labels are often more generative for ARC3: Assemblage (8), Cellular
Automata (14), Grid Toggle (16), Klotski (21), Codebreaker (36), Node-Based Strategy (36),
Sorting (43), Lemmings-like (59), Food Chain (66), Mixing (75), Bomb Maze (68), and
Pipe Connector (119). Their rarity does not prove novelty, but it gives us tractable seams
to inspect.

The complete counts live in `flashpoint-genre-tags.tsv`. Counts should never be used as a
quality score.

## Long-tail retrieval and human review

The aggregate counts are not enough to find unusual interaction rules. A second,
deterministic pass now reads every one of the 129,019 Flash records, cleans description
markup and update notices, retrieves mechanic-bearing phrases and curator tags, separates
interactive games from cross-media artifacts, and applies caps by developer, source,
mechanic signature, and rare core tag. It then interleaves candidates across interaction
families so that the review queue is not simply hundreds of gravity games followed by
hundreds of construction games.

In the current snapshot the pass found 5,342 retrieval candidates and retained 1,281 for
manual review: 1,238 gameplay records and 43 deliberately preserved cross-media records.
The latter are kept because simulations and interactive demonstrations can contain useful
causal ideas, but they are labelled so that calculators, galleries, and utilities do not
swamp the game queue. The query and its exact database hash are recorded in
`flash-long-tail-audit-v1.json`; the ordered records are in
`flash-long-tail-queue-v1.tsv`.

The first source-checked long-tail batch contains 49 lineage decisions in
`flash-long-tail-reviewed-lineages-v1.tsv`: 34 promoted mechanic families, four families
that require a modality or objective adaptation, seven adjacent cases that need a sharper
novelty argument, and four covered cases retained as negative evidence. Promising
additions include:

- one command broadcast over all active branch tips (*Rings and Sticks*);
- behavior selected by the color composition of a temporary worker group (*Tower of
  Babblers*);
- causal-DAG discovery through visible pairwise interventions (*NOBuzzle Tree*);
- topology-controlled quarantine and mixing (*Liquid Colors*);
- a persistent height field edited under an autonomously rolling payload (*Contour*);
- typed particle laws that compose into new dynamics (*Agent Higgs*);
- exact line coverage constrained by both local counts and mutual visibility (*Green
  Leprechauns*);
- ternary neighbor cycling where the target state is itself non-addressable (*Bomb
  Disposal*);
- irreversible bridges whose deployed length is stored in an upright object's visible
  height (*TipOver*);
- a reusable, morphing scaffold manipulated around an autonomous walker (*Enemy 585*);
- an initial cell pattern used as a program for a multi-generation cellular automaton
  (*The irRegularGame of Life*);
- one controlled body serving as the other controlled body's moving floor (*Symbiosis
  Snake*);
- one input decoded into complementary actions by two simultaneous agents (*Poto &
  Cabenga*);
- hidden collision geometry exposed only in a spatially transformed companion view
  (*noitcelfeR*);
- movement that also broadcasts typed motion to responsive obstacles (*Nudge*);
- globally exchanging the behavior of two object classes (*changeType()*);
- causal effects that cross between spatially coexisting rule systems (*Mega Mash*);
- explicit one-gate-per-tick signal propagation in an interactive circuit demonstration.

This is still a review queue, not an automatic novelty oracle. Lexical distance from our
463 concepts is useful for routing attention but cannot establish a structural difference.
Every promoted row therefore names the nearest existing idea or lineage and states the
specific difference that would have to survive implementation.

## The mechanic atoms worth carrying forward

`flash-mechanic-lineages-v1.tsv` records 48 reviewed lineages. Each entry separates:

- the historical source game;
- the portable mechanic atom;
- the ARC3 research question it could support;
- an explicit guardrail against cloning.

The strongest patterns are below.

### 1. The rule or objective is part of the state

*This Is The Only Level* keeps the room recognizable while changing the operative rule;
*Depict1* makes the player privilege repeatable world evidence over guidance; *Karoshi*
and *Don't Escape* reverse a familiar objective; *Achievement Unlocked* makes discovery of
what counts more important than reaching a conventional exit. These are useful because
they attack a common agent shortcut: importing a genre prior and never checking it.

ARC3 translation: demonstrate a small family of rule regimes nonverbally, introduce a
detectable change point, and require the agent to revise one part of its model while
retaining the rest. A random gag or secret keypress is not acceptable evidence.

### 2. The interface can be world geometry

*Continuity* changes adjacency by rearranging panels; *SHIFT* exchanges figure and ground;
*Closure* makes illumination causal to solidity; *Upgrade Complete* lets progression alter
the presentation layer. Flash designers were unusually willing to treat the viewport,
cursor, panels, and menus as manipulable game objects.

ARC3 translation: preserve the six-action API while making the mapping, frame, viewpoint,
or observation mask a visible, reversible state. Never hide a browser-level control or
require clicking outside the game frame.

### 3. A previous action stream can become a tool

`Cursor*10`, *Chronotron*, and *The Company of Myself* turn a recorded past self into a
cooperating actor. The existing external ledger already recognized this lineage in `g003
Echo Crew`; therefore a new environment cannot claim novelty merely by adding ghosts.

ARC3 translation: change what is preserved, who observes the replay, how many histories
can coexist, or whether the replay is editable. The research demand must be distinct from
ordinary synchronized plate holding.

### 4. Construction externalizes a causal model

*Fantastic Contraption*, *Magic Pen*, *Dynamic Systems*, *Personal Universe*, and *Wake Up
the Box* ask the player to build an explanation that can run. *Splitter* and *3 Slices*
make the complementary move: choose a tiny number of structural deletions, then let the
system evolve.

ARC3 translation: snap every placement, joint, field, and cut to a discrete grammar.
Continuous motor precision, floating-point instability, and lucky settling would measure
the interface rather than reasoning.

### 5. Indirect control is often richer than moving the target

*Auditorium* and *Eon* steer streams by modifying fields; *PileOBubbles* manipulates a
payload through inflation and contact; *Meeblings* assigns local fields to different
agents; *Boomshine* permits one intervention before a chain reaction unfolds.

ARC3 translation: make the latent update law exact, show enough demonstrations to infer
it, and force the player to choose interventions rather than micromanage every outcome.

### 6. Transformation order can be the entire puzzle

The *GROW* series makes every early action alter later development. *Factory Balls* uses
noncommutative transformations and masking. *Light-Bot*, *Manufactoria*, and *The Codex of
Alchemical Engineering* progress from action sequences to reusable programs and machines.

ARC3 translation: prefer visual state transformations and spatial procedure tokens over
letters, numbers, or programming syntax. Later levels should demand abstraction, not just
a longer sequence.

### 7. A tool can have a structural side effect

In *Desktop Tower Defense*, a defense is also a wall that reroutes traffic. In *GemCraft*,
combining components changes several functional dimensions. In *The Last Stand*, time
spent preparing one subsystem is unavailable to another before an autonomous phase.

ARC3 translation: require the solver to model at least two effects of an intervention and
to preserve a global constraint while achieving a local one.

### 8. Representation can be the challenge

*I-Sense* reveals geometry by local pings; *Wolfenstein 1D* compresses a world into one
line; *Small Worlds* turns motion into progressive map revelation. These point toward
active sensing and latent-world reconstruction, not generic fog of war.

ARC3 translation: the information channel must be learnable and budgeted. Withholding
arbitrary pixels is not a mechanic.

## What not to import

Large parts of Flash history are poor benchmark material even when they were fun:

- pure reaction time, aiming precision, button mashing, and frame-perfect platforming;
- text, trivia, digits, cultural icons, or knowledge of a franchise;
- progression dominated by grinding, upgrades, waiting, or monetization;
- unconstrained continuous physics whose result changes with tiny placement errors;
- audiovisual tricks that cannot be expressed in the ARC3 observation/action contract;
- hidden hotspots, pixel hunting, unexplained browser gestures, and arbitrary jokes;
- random outcomes that cannot be distinguished by informative intervention;
- visual reskins of a known template;
- copied names, characters, artwork, layouts, source code, or distinctive level sequences.

Flash is a source of design energy, not a content library for us to copy.

## Consequences for the 400-game program

1. Add a structured inspiration record to each game specification: lineage IDs, the
   portable atom, the transformation that makes it a different research instrument, and
   the assets/layouts explicitly excluded from reuse.
2. Treat the 48 lineage cards as retrieval vocabulary during novelty review, not as 48 new
   game concepts. Several are already represented in the external 63 or our 400 queues.
3. Reject a game whose novelty claim is only “classic Flash mechanic in ARC3 graphics.”
4. Require a program-compression comparison: if the historical mechanic plus cosmetic
   substitutions explains the whole game, the game is not new enough.
5. Preserve the Flash virtues that do transfer: immediate legibility, one strong verb,
   cheap restart, surprising composition, and dense visual feedback.

## Immediate build order

`q001 Quiet Field` remains the first GPT-partition implementation. Its core claim—seeing
an object changes whether it advances—is adjacent to Flash's interface experimentation but
is not copied from one of the surveyed games. We should finish its deterministic
qualification before starting `q002`.

For `q002` and later games, mechanic selection should follow this sequence:

1. choose a research demand from the coverage-gap study;
2. retrieve relevant Flash lineage cards and all 463 existing concepts;
3. state the closest prior art and the exact structural difference;
4. define the eight-level causal progression before drawing assets;
5. implement one game completely, including known win/loss traces and random resistance;
6. only then advance the next concept into implementation.

## Generated artifacts

- `flashpoint-corpus-audit.json` — complete aggregate audit, source hash, year counts,
  source domains, developers, tags, and frequent tag pairs;
- `flashpoint-genre-tags.tsv` — all 277 Flashpoint genre tags, including zero-use tags in
  this snapshot, sorted by Flash count;
- `flash-mechanic-lineages-v1.tsv` — 48 manually reviewed mechanic lineages and guardrails;
- `flash-long-tail-queue-v1.tsv` — 1,281 candidates retrieved from the complete Flash
  metadata snapshot and interleaved for human review;
- `flash-long-tail-audit-v1.json` — exact retrieval counts, caps, phrase families, corpus
  hash, and interpretation boundary;
- `flash-long-tail-reviewed-lineages-v1.tsv` — 49 source-checked long-tail decisions with
  nearest-prior comparisons and ARC3 research questions;
- `scripts/analyze_flashpoint_corpus.py` — deterministic regeneration command.
- `scripts/mine_flashpoint_long_tail.py` — deterministic queue construction and nearest-
  concept retrieval command.

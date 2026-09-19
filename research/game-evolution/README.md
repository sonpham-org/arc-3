# The game evolution loop, v4

Author: Claude Opus 5, 19-September-2026, reforming Codex's v3 program at Son Pham's request.
Companions: [AUTHOR_BRIEF.md](AUTHOR_BRIEF.md) (what every author agent follows),
[RUBRIC.md](RUBRIC.md) (the scores and gates), [recovered/](recovered/README.md) (where every
rule below came from, including the v3 originals verbatim).

The loop makes the game set bigger, better, and more different from itself, one published
version at a time. It has four steps, always in this order:

1. **Grow**: when most games have been improved, add new seed games on new topics.
2. **Pair far apart**: sample two games that are as different as possible.
3. **Glow up**: rebuild each sampled game to the quality bar, pulling the pair further apart.
4. **Make it playable**: the game must not die right away, must be clear from its first
   level, and must move objects without silly animation.

Every step ends with a published version on the Games page (arc3.sonpham.net), with its
reason and its primary driver, so each game's tree shows how it evolved.

## What changed from v3

| v3 (Codex, 14-Sep-2026) | v4 |
|---|---|
| Pool = a 50-game JSON list | Pool = every game on the Games page except Official (153 today), read from the trees API |
| Grow only when *every* game has a glow-up | Grow when *most* (80%) have one, or on request. Waiting for all of them stalled growth: six games sat at zero for a week while the QC batch ran |
| Fixes from the September feedback rounds lived in a separate QC batch and a separate motion audit | They are step 4, required for every glow-up and every new seed |
| Versions activated in a local catalog and published by hand | Every step publishes through the upload API, after the vetting gate |
| No machine check before publishing | `scripts/vet_game.py` must pass for the exact bytes; `publish` refuses otherwise |
| New seeds only needed a closest-prior note | New seeds are pushed away from their nearest existing game (new-seed mode, step 2) |

Kept from v3: isolated fresh-context agents per game, the fidelity and pair-distance scales,
mechanic draws from the registry with a necessity test, simple-English QC, honest labelling
of simulated versus human evidence, and "never fabricate a trace or weaken a check to pass".

## The pool and its counts

- **Pool:** every tree on the Games page except the Official 25. A tree's current version is
  its head. (A tree takes its root's family, so the contributed glow-ups, which hang under
  seeds from the retired `ai-generated` set, show as `ai-generated` and are in the pool.)
- **Improved:** a tree with at least one version after its seed that came from step 3 or 4
  (or, for history before v4, any later revision). `scripts/evolution_loop.py status` prints
  pool size, improved share, the least-improved tier, and whether growth is due.
- **Mechanic descriptors** for pool games (primary and secondary mechanics, control,
  topology, timing, objective) live in the loop's private run directory, not in this public
  repo, because most pool games belong to blind families whose designs must not be written
  down in public. New games bring their own `metadata.json`.

## Step 1: Grow

- **When:** at least 80% of the pool is improved, or someone asks for new games.
- **How many:** a generation is 10 seeds (Codex's first generation size), never more than
  20% of the pool.
- **Topics come from real games first.** Draw from the Flash corpus: the 48 classic Flash
  lineages, the 80 reviewed long-tail lineages, then fresh picks from the ranked long-tail
  queue of real Flash games (`research/flash-long-tail-queue-v1.tsv`, mined from Flashpoint's
  129,019 Flash records; see [recovered/](recovered/README.md)). Real players already found
  those mechanics fun. Brainstormed lists (GPT's 800 designs, the 200 briefs in
  `anthropic-build-ideas-v1.tsv`) are a last resort. Generation 1 (19-Sep-2026) is the
  exception: 9 of its 10 topics came from the briefs, and Son asked that later generations
  take theirs from the Flash corpus.
- One topic per mechanic family, each unexplored on the ideas board (`/api/v1/games/ideas`)
  and not close to an existing game (`evolution_loop.py nearest`). Link the idea when
  publishing (`--idea`), so the board shows it as explored.
- **Authors:** one fresh, isolated agent per seed, following [AUTHOR_BRIEF.md](AUTHOR_BRIEF.md).
  A seed has 3-5 levels, a level 1 that teaches the idea, and passes `vet_game.py --profile seed`.
  It may be plain, but not broken, cloned or cosmetic.
- **Publish:** `--kind seed`, reason `Seed: <the idea in one line>`.

## Step 2: Pair far apart

**Normal mode.** Sample the first game uniformly from the least-improved tier, excluding the
ten most recently sampled games when possible. Rank the other games in that tier by mechanic
distance from it (weighted overlap of primary ×3 and secondary ×2 mechanic phrases, as in
v3) and sample the second uniformly from the farthest 20%. Widen to the next tier only if
the tier has one game. Record the draw immediately in the ledger; never silently redraw.
Redraw only the second game, and only if the step-3 distance gate cannot be met without
corrupting either game.

**New-seed mode** (used for a new generation). Pair each new seed with one existing game,
its *anchor*, sampled uniformly from the seed's five nearest existing games. Only the new
game moves in step 3. The anchor is never edited. Pushing a new game away from its closest
neighbour is what makes it genuinely new; pushing it away from a game that is already
distant would change nothing.

## Step 3: Glow up

1. **Baseline:** play every level of the game(s) through `scripts/play_game.py`; note defects.
2. **Distance brief:** a separate fresh agent compares the pair on the 12 pair-distance axes
   ([RUBRIC.md](RUBRIC.md)) and writes, per game, the axes that are too close and directions to
   move. Authors get only their own game's brief, never the other game's code.
3. **Mechanic draw:** draw three underrepresented mechanic families from
   [the registry](recovered/codex/glowup-mechanics-registry-v1.json). Adopt at most one, and only
   if it changes real decisions, appears in the curriculum, survives into a late level, and
   fails a counterfactual necessity test when removed. Record each rejection and its reason
   (`evolution_loop.py draw --game <id> --record`, then `log` a `mechanic-decision`). A hex
   map counts only with click controls: the September rounds moved every keyboard hex game
   to squares because players could not predict six-way keyboard movement.
4. **Rebuild:** a fresh author per game makes 7-12 levels. Levels 2-6 each add a genuine
   demand; at least two late levels combine three or more earlier demands; no more than two
   consecutive levels are larger copies of the same task.
5. **Gates:** fidelity ≥ 84 with no dimension under 60%; pair distance ≥ 78 with at least
   eight axes at 3-4; weighted mechanic overlap ≤ 0.65; each game keeps an exclusive
   meaningful mechanic; `vet_game.py --profile glowup` passes.
6. **Publish:** `--kind revision`, reason `Glow-up: <what changed and which axes moved>`.

## Step 4: Make it playable

These are the two fix rounds of September 2026, made permanent. Step 4 runs on every glow-up
and every new seed before it counts as improved.

**4a. Not dying right away, and clear**
- Level 1 is a tutorial: at most 10 actions, cannot be lost, and its idea reads off the
  screen. Discovery cost belongs to level 2 and later. A level 2 that random play can clear
  is fixed by hardening level 2, never by lengthening level 1.
- No terminal loss during ordinary exploration. A loss that is part of the idea shows its
  cause before it bites, shows lives, and RESET retries the current level with earlier
  levels kept. No hidden move caps; a visible budget needs a recorded gameplay reason.
- Every action visibly answers. A refused action looks refused, at the object that refused.
- Thin noise, don't strip it. Decoration may stay, but never where it hides state.

**4b. Honest movement**
- Decide the rule outcome once, then present it. Presentation frames never tick rules,
  advance enemies, or change counters.
- Moving objects translate whole, along the path the rules took: no splitting, smearing,
  trails, pixel scatter, tile-parity silhouette flips, or shortcuts through walls.
- A one-cell move is 2-4 frames; an action stays under 12 frames (under 30 for a genuine
  cascade). The camera follows the mover. RESET and level changes are instant.
- Native effects that show a real rule (water filling, a beam travelling, a collapse) stay.

**Checks**
- `vet_game.py --profile glowup` passes: `level1_short`, `level1_safe`, `early_death`,
  `random_resistance`, `frames_per_action`, `visible_response`, and the rest.
- A reviewer opens the animation strips (`--strips`) and signs off 4b.
- **Cold start:** a fresh tester who has never seen the source, the trace or any notes plays
  with `play_game.py`: first meaningful action within 60 seconds, level 1 won within five
  minutes, and a plain explanation of what the action changed and why it won.
- **Simple English:** two fresh reviewers score a mechanics summary and a level-1 how-to from
  0 (plain) to 1 (slop). The highest of the four scores must be ≤ 0.20. After two
  wording-only rewrites, change the game, not the words.
- If step 4 changed gameplay, re-run the step-3 distance gate on the new version.
- **Publish:** `--kind revision`, reason `Playability: <what was fixed>`.

QC results are `provisional_pass` when only simulated testers were used and
`human_confirmed` only after a real first-time player passes. A real player's failure
reopens the game. Simulated reviewers are never reported as human evidence.

## Publishing, and the vetting gate

```
python scripts/vet_game.py --source g.py --trace g.trace.json --profile glowup \
    --out g.vet.json --strips strips/
python scripts/publish_game_versions.py publish --game <id> --source g.py \
    --kind revision --parent <previous version id> --driver claude \
    --reason "Glow-up: ..." --idea <idea id> --vet-report g.vet.json
```

- `--driver` is who primarily drove the change: `gpt`, `claude`, or `human` (a person
  actively tuned it). A new game grown out of an old one gets a new id and `--kind branch`.
- `publish` refuses a source unless the vet report passed for exactly those bytes, and
  attaches the report's summary to the version's provenance. The server never runs game
  code, so this gate lives on the uploader's side.
- The gate proves the game loads, is winnable, deterministic, Undo-safe, resettable, hard to
  lose early, and not random-clearable. It cannot prove it is fun, clear or novel. Steps 3
  and 4's reviews do that, and team feedback on the Games page is the last word: read it
  with `publish_game_versions.py feedback --game <id>` before the next pass.

## Isolation and honesty

- A fresh agent for every game at every step. Authors never read other games' code or
  designs, other authors' work, or the pool catalog. Only comparison agents see both games
  of a pair, and their output goes to the coordinator, who forwards each author only its
  own game's deficits.
- Cold-start testers never see source, traces, notes or earlier reviews. A reviewer who has
  seen a solution can't be the cold-start tester for that version.
- Never fabricate a trace, a loss, or a review. Never weaken a check to make a game pass.
  Record failures; a failed pass costs nothing but time.

## Records

- **Run directory (private, not in this repo):** game sources while in progress, traces,
  vet reports, strips, briefs, reviews, and pool descriptors.
- **Ledger (public, ids only):** [ledger.jsonl](ledger.jsonl), one line per event:
  generation, draw, publish, gate result.
- **Games page:** the published versions, their reasons, drivers and feedback.

## Cadence

One pass at a time per game. A recurring job may start a pass every 90 minutes, as Codex's
did, but a job that finds an unfinished pass resumes it instead of drawing a new pair.

<!--
Author: Claude Fable 5.1
Date: 18-September-2026
PURPOSE: Hand-off from arc-explainer to arc-3, answering §1 and §9.1-9.2 of
         2026-09-18-state-of-play-notes.md: the game-mechanics corpus is going to be exported
         as one record per game level, and here is what that record holds, where it will
         live, and the three ways this repo can consume it. Written so the harness and
         distill owners can plan against it before the export exists.
SRP/DRY check: Pass -- the full brief and the page mockup live in arc-explainer at
         docs/plans/2026-09-18-arc3-game-page-glowup-and-dataset-prd.md; this file carries
         only what arc-3 needs to act on.
-->

# The game-mechanics corpus is becoming a dataset. What arc-3 gets from it.

Boss approved this on 18-Sep-2026. Status: **brief and mockup committed in arc-explainer
(commit on `main`, 18-Sep); export not built yet.** Nothing here is available to load today.

## What exists in arc-explainer right now

`shared/arc3Games/<id>.ts`, 25 live games plus the withdrawn as66:

- 553 rule entries, 527 with a `file:lines` citation into the game's own Python
  (`external/ARCEngine/environment_files/<id>/<build>/<id>.py`, public fork at
  github.com/82deutschmark/ARCEngine). Each rule has a category (controls, goal, pieces,
  hazards, budget, feedback) and the level that introduces it.
- The opening frame of every level, engine-rendered at 4x from the live build, plus Boss's
  own mid-play captures where he sent them (dc22 L6, tr87 L4-L5 so far).
- `humanPlay.generated.json`: 50 of Boss's runs since 18-Jun-2026 with per-level actions,
  per-level ARC baseline, resets, score, and the run **guid**. He has won 19 of 25.
- `playerObservations`: Boss's notes in saw / did / expected / happened / in-code form.

## What the export will produce

One JSONL record per (game, level), about 170 records, from a script that reads only the
registry above. Same records back the rebuilt game pages, so page and dataset cannot drift.

Per record: game id, informal name, build hash, action mappings; level number, step budget,
ARC baseline actions for that level; opening frame (PNG path plus the raw 64x64 grid), human
captures with who/when/state; rules in force on this level and rules new on this level, each
with citation and GitHub URL; Boss's runs on this level with actions, cleared or not, and the
guid; observations for this level; dated corrections; export date.

Not in it: the game Python (cited, not bundled), the 50 synthetic games, frame-level replays.

**Release policy, Boss's call 18-Sep:** the export exists behind an admin route only. Nothing
is linked or published until a curation pass has spot-checked every record against its page,
opened every citation, and resolved every guid against the replay corpus here. Then CC BY
4.0, GitHub release, Hugging Face card.

## Three ways arc-3 can consume it, in the order worth trying

1. **Human runs as demonstrations (distill).** Join each run guid to
   `datasets/decision-steps/v0/recordings/<game>/<guid>.ndjson`. Keep levels Boss cleared,
   the same rule `extract_sft.py` applies to model runs (`level <= levels_completed`). This is
   the most direct route from 381 turns toward the 2-5K target: 19 fully won games instead of
   11 games with one level each.
2. **Rules as a reference card (harness, "arm C").** Inject the rules-in-force text and the
   opening frame for the public 25 into the prompt, paired against baseline, to split
   "cannot infer the rules" from "knows the rules, cannot execute". Public games only; this
   does not leak anything about the private set.
3. **Observations as reasoning exemplars (distill).** Boss's saw/did/expected/happened notes
   are the shape of the pre-action reasoning we want. Few today; the export picks up every
   new one he writes.

## Ask of this repo

- Say which loader shape `distill/` wants for (1) so the export emits it directly.
- Confirm the guid in `humanPlay.generated.json` is the same key `replay_scrape.py` uses.
- Do not build a second copy of the mechanics text here; cite the export.

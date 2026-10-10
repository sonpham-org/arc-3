<!--
Author: Claude Sonnet 5.5 (for Boss)
Date: 10-October-2026
PURPOSE: Suggestion to ingest Felix561's open-source ARC3 synthetic games (a community member's work, shared in
  the ARC Discord) into the game-vetting pipeline as seed-tier training environments. Records what was checked,
  what held up, what did not, and the proposed ingest steps. Nothing has been ingested yet.
SRP/DRY check: Pass - the vetting bar is scripts/vet_game.py and AGENTS.md; this doc only applies it to one outside
  source and does not restate it.
-->

# Suggestion: ingest Felix561's synthetic games (seed tier)

Source: https://github.com/Felix561/arc3-synthetic-games (MIT, pushed 10-Oct-2026). Fifty abstract games
(thirty "Studio" plus twenty "Studio V2"), seven levels each, in ARCEngine format with the 0.9.3 engine we already
use. His collection also bundles NVIDIA's DreamTeam synthetic games (twenty-five, Apache-2.0, kept in a separate
folder); this note is about his fifty.

## What was checked (all fifty, locally, with our engine)

- Every game loads in a clean namespace, uses only the imports our vet gate allows, and makes no forbidden calls.
- His recorded AI solution for each game replays from a fresh start to a real WIN. All fifty, all seven levels.
- The boards are readable and abstract: no text on the play surface, no copies of official games. A spot-check of
  eight opening boards looked clean (keys and gates, beams and mirrors, a tray puzzle, a cable puzzle).
- Mechanics are mostly new to our catalog: light relays, balance beams, gear trains with clutches, folding and
  piercing, shadow casting, scent trails, consumable paths, nested containers.

## What did not hold up

- **Too easy for our bar.** Our glow-up profile requires that random play cannot clear level two onward. Nineteen of
  his thirty original games are cleared two levels deep by random clicking within four hundred actions. Several are
  cleared on level one almost every time. Recorded winning lines are short: the median original game is won in under sixty
  actions across all seven levels, and early levels often take one to four actions.
- One game (sg24) has a first level longer than our ten-action limit; one V2 game (v220) has two very long levels.
- **The recordings are not discovery.** His agents could read the game source. They show solutions, not
  exploration, so they are no use as examples of how to find a rule. He says so himself.
- Nobody has played these as a human. Treat `reviewed: false`, as with the copycat games.

## Proposal

1. Ingest the fifty games through the seed profile of the vet gate, not glow-up. Seed allows a rough game.
2. Convert his recorded wins into our trace format so the gate can replay them (his rows are per level, with action
   lists and 64x64 frames; the V2 click fields are column and row).
3. Give them opaque ids, mark them community-sourced with attribution to Felix561 (MIT notice kept), and keep them
   out of anything we report as a yardstick.
4. Run the glow-up loop on the ones that pass the early-death check but fail the random-play check; those are the
   cheapest to harden. Skip his AI trajectories for training: our pipeline learns from solved-level traces we
   made ourselves.
5. Optional, later: the NVIDIA twenty-five, after the same look. Not checked yet.

Evaluation script and per-game results are saved beside the clone in
`/Volumes/Samsung 9100 SSD/kaggle/arc3-synthetic-games-felix/` (`eval_felix.py`, `felix_eval.json`).

# Generation 1, 19-September-2026: ten new seeds

The first run of the v4 loop ([README.md](README.md)), paused after step 3 at Son's request.
Ten new games exist, each with its own topic, anchor and published seed. Game sources, traces,
vet reports, briefs and reviews live in the private run directory
`D:/codex-work/arc3-evolution-run-20260919/` (games are shown blind, so their designs stay out
of this public repo). The ledger here records the ids, draws, gates and versions.

## Where each game stands

Topics: nine from the GPT-seeded brief list (`research/anthropic-build-ideas-v1.tsv`), one
(`db11`) from the Flash lineages. Later generations take their topics from the Flash corpus.

| Game | Idea | Anchor | Pair distance at the seed | Stage when paused |
|---|---|---|---:|---|
| `kx13` | anthropic:a069 | `uy95` | 48.75 → **91.5 (pass)** | step 4 started: glow-up published, playability pass in progress |
| `mc18` | anthropic:a038 | `q052-v1` | 62.5 | glow-up done and vetted (9 levels); final distance check unfinished |
| `hg51` | anthropic:a099 | `g136` | 39.0 | glow-up in progress |
| `sd78` | anthropic:a042 | `ex92` | 48.0 | glow-up in progress |
| `vf22` | anthropic:a050 | `nu72` | 51.75 | glow-up in progress |
| `db11` | flash:f041 | `g171` | 39.0 | glow-up in progress |
| `br10` | anthropic:a057 | `q038-v1` | 44.75 | glow-up in progress |
| `mx78` | anthropic:a083 | `g033` | 45.5 | glow-up in progress |
| `fq27` | anthropic:a021 | `g035` | 35.75 | glow-up in progress |
| `mb64` | anthropic:a149 | `q062-v1` | 71.5 | glow-up in progress |

Eleven versions are published to the **local** stack only: ten seeds and `kx13`'s glow-up.
Nothing is on production, which still has an empty games database.

## What the run showed

- **New topics gave new mechanics, not new games.** Every seed's mechanic overlap with its
  anchor was under 0.31, but the pairs still scored 36-72 out of 100. What held them together
  was presentation and frame: flat top-down grids, charcoal or black backgrounds, square
  pieces, an item taken from a tray and clicked into a slot. Step 3's real work was leaving
  those, and `kx13` shows the size of the move available: 48.75 → 91.5.
- **The machine gate earns its place.** It caught a game that ended itself on RESET (the
  engine runs `step()` for RESET too), traces that no longer won, and level 2s that random
  play cleared. It also missed one: clicks spread uniformly over the screen almost never hit a
  small button, so a click game looked random-proof until a seed author found random heater
  clicks clearing its levels. The clicker now aims at on-screen colours and engine targets.
- **Readability is the recurring defect.** Three separate reviews found decoration in the same
  colour as the state the player must read. "Thin, don't strip" from the clarity loop is the
  rule that keeps getting broken.

## Resuming

1. Start the local stack (Postgres, `catalog_server.py`, the dev proxy) if it is down.
2. For each game with an unfinished glow-up, give a fresh author its seed, its distance brief
   (`briefs/<id>-distance.md`), its drawn mechanics from the ledger, and whatever `v2/` holds.
3. When a glow-up passes `vet_game.py --profile glowup`, have a comparison agent re-score the
   pair against the same anchor and write `briefs/<id>-distance-v2.md`; the pair must reach 78.
4. Publish with `evolution_loop.py publish --step glowup --parent <seed version id>`, then run
   step 4 and its cold-start QC, and publish that as `--step playability`.
5. Production needs its history filled (`sync`, `import-explainer`, `ideas`) before any of
   these games is published there: the Games page falls back to the static catalog only while
   the database is completely empty.

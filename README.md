# arc-3 — games catalog + internal run evaluation

Two things live in this repo, and they share one site (**https://arc3.sonpham.net**):

1. **Games** — a browsable, playable catalog of 927 ARC-AGI-3 games: the 25 official
   ARC Prize Foundation games, our in-house custom games, the reviewed `arena` set, our
   generator's output, and the Red Blue Pill community catalog. Public, no login, runs
   entirely in the browser.
2. **Internal runs** — the evaluation side: every benchmark run we've done of the
   ARC-AGI-3 duck harness, with a scoreboard, a per-turn run inspector, resource usage,
   and score-distribution ("signal") runs. Behind sign-in.

Everything under `docs/` is that site; everything else is the machinery that produces it —
the harness variants, the GCP launch kit, and the raw run logs.

---

## 1. Games

`docs/index.html` — the public half of the site.

**927 games in the catalog**, from five sources that all share the same
`environment_files/<code>/<version>/` layout and the same `ARCBaseGame` / `arcengine`
model:

| Source | Count | Origin |
|---|---:|---|
| `ai-generated` | 571 | straight off our generator, unreviewed |
| `redbluepill` | 252 | [theredbluepill/arc-interactive](https://github.com/theredbluepill/arc-interactive) |
| `arena` | 50 | generated, then played and revised until they hold up — the reviewed set. Also served from local disk by [arc-explainer](https://github.com/82deutschmark/arc-explainer), which is the copy that wins there; see its `Arc3MirrorCatalog.ts`. |
| `custom` | 29 | built in-house |
| `official` | 25 | the public ARC-AGI-3 games (`environment_files/` in this repo) |

**The Games page shows neither `ai-generated` nor `redbluepill`** (19-Sep-2026, not worth
playing). Both stay in `manifest.json`, which arc-explainer mirrors, but neither is published
to the evolution trees (`RETIRED_FAMILIES` in `scripts/publish_game_versions.py`). The page
does show arc.markbarney.net's own sets: its 44 contributed glow-ups, each under the generated
game it came from, and its 25-game research collection (`publish_game_versions.py
import-explainer`). Everything we made is one category, **Additional games** (153), beside
the **Official** 25.

The `arena` rows carry no `description` or `tags`, and their `title` is just the id. That
is deliberate: arc-explainer uses them to collect a blind human baseline, where a player
infers the rules from the frame, so a name spends the data point before the first move.

Game *codes* collide across sources (`cr01`, `ft09`, `ls20`, `pt01`, `vc33` exist in more
than one catalog as entirely different games), so everything keys on the full `game_id`
with its version suffix (`ft09-0d8bbf25` vs `ft09-9ab2447a`) — never the bare code.

### How play works

Click a game and it runs **the real Python game** in your browser: Pyodide (WASM CPython +
numpy) in a Web Worker, with `arcengine`'s wheel pulled straight from PyPI and unzipped into
site-packages. The only thing fetched from us is the game's `.py` source text. Playing sends
nothing to a server and there's no login and no leaderboard; the one thing ever stored is a
review you choose to send from **Feedback games** (below).

- Controls: WASD/arrows to move, `r` reset, Space or `z` = ACTION5, `x`/`c` = ACTION7, click = CLICK.
- Undo, per-level jump strip, FPS control, live status/score.
- **Tile render modes** (`docs/static/games/arc_tiles.py`): `solid` is the engine's stock
  nearest-neighbour upscale; `tiles` gives every palette colour a fixed deterministic motif
  so a cell reads as an object with a texture rather than a flat blob; `random` reshuffles
  both motif and colour assignment per episode from a seed — behaviour untouched, appearance
  not, so an agent can't carry "blue == wall" across episodes. Same board, same rules.

The 16-colour board palette is deliberately duplicated between the thumbnail generator
(`scripts/build_games_manifest.py`) and the play page (`docs/static/js/games-play.js`), so
in-browser play renders pixel-identical to the static thumbnails and to recorded runs.

Those same thumbnails are the site's favicon: `docs/static/js/favicon.js` points each page's
`<link rel="icon">` at one of the 25 `official` games at random per load, and the icon in the
page's head is the static fallback for when JavaScript is off. If the official set changes,
regenerate the id list at the top of `favicon.js` with the one-liner in its comment.

### Evolution trees

The Games page shows **one row per game tree**: on the left, frozen, a big thumbnail of the
tree's current version (the one to play); on the right, the tree itself, scrolling sideways
from its seed to its newest versions. Each node is one exact source, with who made it (GPT,
Claude, a person, or imported), when, and, for the signed-in team, the reason for the change.

Each version is credited to whoever **primarily drove** it: **GPT-driven**, **Claude-driven**,
or **Human-tuned** (a person actively tuned it). History is credited by family: the reviewed
arena set Claude-driven, the glow-ups GPT-driven, in-house, research and official human-tuned.

- **seed**: a game that came from nowhere in this catalog.
- **revision**: the same game, improved. It continues its parent's lane, even when the id
  changes on the way (`q041-v1` → `q041-v2` is one line).
- **branch**: a new game grown from an old one; it drops to a lane of its own (dashed edge).
- A line's latest version is its current, best version; the root line's is the tree's.
- A version can have **several parents** (a crossover). The first places it in its tree; the
  others are drawn as dotted "also made from" links and listed in its drawer.

Versions live in Railway Postgres (`railway/games_schema.sql`) and their files on the volume
under `/srv/data/_games/<game_id>/<sha12>/`, served publicly at `/data/_games/`. A version is
immutable and content-addressed: `version_id = <game_id>@<first 12 hex of sha256(source)>`,
the same 12-hex stamp arc-explainer records as `source_version`, so a review on either site
names the same build. If the API is down, or its database has not been filled, the page falls
back to `docs/static/games/manifest.json`: every game still plays, without history.

**Who sees what.** Anyone can browse trees and play any version. Change notes and written
reviews are team-only (`/api/v1/games/*`, behind Google sign-in), which keeps arena mechanics
out of public view. `railway/games_store.py` documents every route and who may call it.

### The ideas board

Signed in, the top of the Games page is a board of **every game idea we have**: GPT's 800-idea
ledger, the 200 Anthropic briefs, and the Flash mechanic lineages, 1,128 in all. The columns are
*not explored yet · exploring · explored · dropped*. An idea is explored once a game has been
built from it (the card links to that game); the team moves the rest by hand. Ideas name their
mechanic, so the board is team-only, like change notes. `publish_game_versions.py ideas`
(re)loads the ledgers without undoing a card anyone moved; `publish --idea <id>` links a new
version to the idea it explores and marks that idea explored.

### Feedback games

The **Feedback games** button starts a loop: play a game, review it, get the next one. The
server picks the current version that most needs a review: for a signed-in team member,
versions no team member has reviewed yet (and never one they reviewed); for the public, the
least-reviewed. Nothing names or explains the game before or during play. A review stores
ratings (fun, clarity, difficulty, novelty), flags (the first six are arc-explainer's, so the
two sites' data joins), five free-text answers, a verdict, and what actually happened (levels,
actions, resets, undos, time).

Anyone can send one. Signed-in reviews are filed as `team` and always rank ahead of `public`
ones in every list, summary and export; public ones are rate limited and the team can hide
spam from the version drawer.

### Comments, and "good to train"

Each game's page carries the team's running comments, newest first, and a tick on the version
you are looking at:

- **Comments** are free text about a game, stored in the Railway database
  (`arc3_game_comments`). They are team-only to read and write, like change notes, because a
  comment names mechanics and most families are played blind. A comment can be about the whole
  game or about the exact version you were playing when you wrote it.
- **Good to train** marks that exact version as fit for the training pipeline, with who ticked
  it and when. It is per version, not per game, because the pipeline trains on exact bytes and
  the next version of the same game may not be fit at all.

The pipeline pulls the ticked set with the publish token, so it needs no browser session:

```bash
curl -H "Authorization: Bearer $ARC3_PUBLISH_TOKEN"   https://arc3.sonpham.net/api/v1/games/training-set
```

It answers `{"count": N, "versions": [{"versionId", "gameId", "family", "sha256", "sourceUrl",
"author", "markedBy", "markedAt"}, ...]}`, so a training run can fetch each source by its
content-addressed URL and know exactly which bytes a person approved.

### Publishing a game version (no deploy)

Like traces, game versions go through the Railway API with `ARC3_PUBLISH_TOKEN`, never
through Git or a site deploy. The server stores whatever bytes it is given and never runs
game code, so the check happens before upload: `publish` refuses a source unless
`scripts/vet_game.py` passed for exactly those bytes. The vetting gate plays the game in the
site's engine (arcengine 0.9.3). It checks that the game:
- loads, and a recorded winning trace clears every level;
- replays identically, from scratch and from a deep copy (Undo);
- restarts a level on RESET without losing earlier levels;
- has a short level 1 that can't be lost, and no level where random play dies in its first
  10 actions;
- has levels 2 and up that random play can't clear;
- keeps every action under 60 frames.

The report's summary rides along in the version's provenance. The gate can't judge fun,
clarity or novelty; the evolution loop's reviews do that ([research/game-evolution/](research/game-evolution/README.md)).

```bash
# Vet first: a winning trace per level, and the profile (seed = 3+ levels, glowup = 7-12).
python scripts/vet_game.py --source path/to/g009.py --trace g009.trace.json --profile glowup \
    --out g009.vet.json --strips strips/

# Every time GPT, Claude or a person evolves a game: one version, one main reason, and who
# primarily drove it (--driver gpt | claude | human).
python scripts/publish_game_versions.py publish --game g009 --source path/to/g009.py \
    --driver claude --model "Claude Opus 5" --reason "Walls now show which side is sticky" \
    --vet-report g009.vet.json

# A new game grown from an old one: a new id, with the version it came from.
python scripts/publish_game_versions.py publish --game g512 --source g512.py --family contributed-glowup \
    --parent q041-v1@5172e6e8f014 --driver gpt --model "GPT-6 (Codex)" --reason "Square-grid remake" \
    --vet-report g512.vet.json

# A crossover: repeat --parent (the first places it in its tree); --idea links a board idea.
python scripts/publish_game_versions.py publish --game ng02 --source ng02.py --family custom \
    --parent ng01@4b3379dc06bb --parent hv01@e603b9777756 --idea anthropic:a001 \
    --driver human --reason "Negative's inversion inside Hive's swarm" --vet-report ng02.vet.json

# Try a game the way a first-time player would (the loop's cold-start test).
python scripts/play_game.py start --session try1 --source path/to/g009.py
python scripts/play_game.py act --session try1 right

# Everything in docs/static/games/ except the retired ai-generated set, with its history
# rebuilt from this repo's git log. Idempotent: re-run it after any commit that changes
# docs/static/games/src/.
python scripts/publish_game_versions.py sync

# arc.markbarney.net's glow-ups and research collection, from a checkout of arc-explainer;
# and the idea ledgers onto the ideas board.
python scripts/publish_game_versions.py import-explainer --repo ../arc-explainer
python scripts/publish_game_versions.py ideas --explainer ../arc-explainer

# Reviews as JSON lines, team first, for the next evolution pass.
python scripts/publish_game_versions.py feedback --game g009 --since 2026-09-18T00:00:00Z
```

`sync` and `import-explainer` credit history by family (`FAMILY_DRIVERS`); a commit's
`Co-Authored-By` trailer or the file's `Author:` header only supplies the model name when it
agrees with that driver.
Thumbnails are the reset frame, rendered locally (needs `arcengine` + Pillow).

### Rebuilding the catalog

```bash
python scripts/build_games_manifest.py    # manifest.json + per-game src/ + thumbnails
```

Writes `docs/static/games/manifest.json`, `docs/static/games/src/<game_id>/<file>.py`, and
`docs/static/img/games/<game_id>.png`. Needs `arcengine` installed (for thumbnails and
tile-scale detection). Six titles are currently parked in `TEMPORARILY_REMOVED_CODES` —
their source and thumbnails stay on disk; delete the entry to bring one back.

---

## 2. Internal runs

`docs/internal.html` and friends — sign-in gated on the live site.

| Page | What it is |
|---|---|
| `internal.html` | **Scoreboard**: one row per run, one column per game, cell = that run's score |
| `viewer.html` | **Run inspector**: scrub every board state of a game and read the agent's full decision trace per turn |
| `arc-debugger.html` | **Context debugger**: inspect and fork the exact prompt, memory, tools, board, and feature flags for one viewer turn on the two-Spark Qwen cluster |
| `trace.html` | Execution trace for a single run |
| `signals.html` | **Signal runs**: one game played N times, as a box/whisker score distribution |
| `usage.html` | Per-run CPU / GPU / RAM / storage over the life of the run |
| `score-time.html`, `score-over-time.html` | Score over time |
| `research.html` | "Beyond the Public 25" — results off the official set |

Static data from finished runs only — no live streaming. 37 runs are published today.

Viewer URLs are canonical down to the selected action frame: `run`, opaque
`game_id`, duplicate-game `instance` when needed, analyzer `turn`, and `frame`
are all encoded in the hash. Scrubbing updates the URL in place, and **Copy
turn link** produces a stable handoff into either Viewer or Debugger.

The Debugger is a model-context fork, not a mutable replay of the archived game
engine. It reconstructs the exact OpenAI-compatible message/tool payload when
request logs exist, re-renders the selected pre-turn board, applies only flags
with a verified request transformation, and asks the live Qwen cluster for a
continuation. The returned Python tool call is shown for diagnosis; it does not
execute against or alter the archived game. See
`ARC3-Inference/debugger/README.md` for the gateway and deployment contract.

### The metric, and why we don't trust single runs

Score is the ARC-AGI-3 score (level depth is weighted, so depth beats efficiency).
Two rules, both learned the hard way:

- **Score on ex-`ft09`, never raw all-25.** One game (`ft09`) swings the 25-game average by
  ±1.0 on its own. Its own signal run — 25 passes of the same config — ranges 0.0 to 47.6
  (median 10.8, σ 11.2).
- **The 25-game mean is noise-dominated.** Its ~95% range on a fixed config is roughly
  0.45–2.67, so a single-run A/B cannot resolve a harness change. Replicate anything
  promising 2–3×.

### Where things stand

Reference points: Tufa's public-set score with this harness is **1.6002**; their semi-private
milestone score was 1.21. Our pristine reproduction of their stack (`tufa-exact-rung0`) scores
0.679, and that run is the baseline every other run's knobs are diffed against.

Best validated configs, by 2-pass mean ex-`ft09`:

| Config | ex-`ft09` | Note |
|---|---:|---|
| `ffa7gn` — frame-full + ACTION7 + animation + goal-guidance + **no-impact band** | **1.62** | current best; 21 levels |
| `ffa7gnh` — + HUD code-model | 1.60 | flat vs `ffa7gn`; the code model didn't add |
| `frame-full` alone | 1.44 | env-toggle `ARC3_FRAME_MODE=full` |
| `baseline-v12` (frozen reference) | 1.21 | 2 runs: 1.224, 1.188 |
| `ffa7g` — same stack, **no** no-impact band | 1.05 | the ablation control |
| `ffa7gnsg` — + state graph | ~1.11 | **regression**, defaulted OFF |

What the ablations actually said:

- **No-impact detection is the one clear win** (+55% ex-`ft09`, 21 vs 15 levels at equal
  action budget). It stops an explore action whose only board change is the game's
  deterministic HUD/moves band, killing wasted wall-presses. Both runs hit the ~132-min time
  cap, so the savings buy *progress*, not a lower action count.
- **The state graph lost three times running.** The model used its tools heavily but the
  plan-rejection block fired zero times, so we paid the query-turn cost (644 vs 366 tok/action)
  for nothing → fewer actions → fewer levels. A lean rerun that surfaces `untried_here` for
  free still lost on a 7-game A/B (1.533 on vs 2.061 off). Now opt-in via `ARC3_STATE_GRAPH=on`.
- **Model swaps all failed.** 35B-A3B MoE: 0.000 across 25 games. GLM-4.6V (SOTA visual
  grounding): 0.000. Gemma-4-31B (AIME 89.2): 0.156. A brevity-RL fine-tune cut thinking
  tokens 46% but the savings didn't convert to actions (1,710 vs 3,073) and depth collapsed.
  The 27B dense remains the harness's brain.
- **Serving matters, but less than tempo.** The vrfai compressed-tensors quant hits a
  pathological kernel path on vLLM 0.25 (3.4× slower than 0.19; ngram spec decode amplifies it
  to unusable), while spec decode on official weights is statistically tied with the pristine
  stack. Our early agent-side modifications (required ledger, outline renders, 900s yield) cost
  ~2.2× on identical serving — the tempo regime (60s yield, act-look-act) dominates everything
  else at this model scale.

### The custom-games pass

`20260726_054336_v12-ffa7gnsg-customgames17` is the first harness run against the **17 in-house
custom games** instead of the official 25, using the validated-best config. Mean 7.89 over 17
games, 24 levels, all completed without a crash. One outright win: `ps01` (Pouring Water Son, a
*live* real-time physics game) cleared its only level — the first evidence this turn-based
harness can handle continuous game semantics at all. Best partials: `cr01` (Crumbling Route)
9/10 levels, `sn02` (Sneeze) 6/7.

These numbers are **not comparable** to any all-25 or ex-`ft09` figure above: different games,
different level counts, different baselines (several needed `baseline_actions` patched to null
first — see `scripts/build_gcp_customgames_bundle.py`).

### Publishing a run

```bash
scripts/publish_run.sh <gcs-run-id> <log-dir-name>
```

This is the single supported submission path. It pulls logs from GCS, exports the viewer and
execution trace, validates the final score against the timestamped score curve, then uploads one
hash-verified archive to the versioned Railway publication API. The API installs the run files
and commits the run, per-game scores, score events, artifact hashes, and publication receipt to
Railway Postgres in one transaction with filesystem rollback.
Every publication must include `LAUNCH_STATE.json` or `model-info.json` with the exact model
repository and full 40-character revision. The exporter cross-checks both files when both exist,
stores their SHA-256 evidence in the catalog, and refuses an unlabelled or unpinned upload.
The scoreboard and both score-over-time pages read that database-backed catalog, so there is
no separate index upload to remember. Publishing data never changes Git and never triggers a
Railway deployment. The publisher reads `ARC3_PUBLISH_TOKEN` from the environment or, when run
from an authorized machine, from the linked `arc3-viewer` Railway service. Set `$ARC3_SITE_DIR`
only when the current checkout is not Railway-linked.

`scripts/publish_railway_data.py` refuses to overwrite an existing run by default. A deliberate
re-export must pass `--replace`; it first reads the current manifest and uses an optimistic
precondition, so a stale task cannot overwrite a newer publication. The replaced directory is
retained under `/srv/data/.rollback/`.
If the Postgres transaction fails, the newly installed directory is moved to `/srv/data/.failed/`
and the prior volume copy is restored. Raw artifacts remain canonical in GCS.

The Railway image is built from the root `Dockerfile`. It contains the site shell, game assets,
the catalog/publication API, and a userspace Tailscale client for the ARC Debugger relay. The
browser calls the same-origin `/api/v1/debugger/*` route after Google authentication; Railway
then forwards only the debugger API through its local Tailscale HTTP proxy to `a108`. Browser
devices do not need to join the tailnet, and neither the Tailscale enrollment nor the Spark
gateway bearer token is sent to them. Tailscale state is retained on the existing `/srv/data`
volume under `.tailscale/`.

Run metadata lives in Railway Postgres; large immutable viewer
and trace payloads live under `/srv/data`. `docs/data/`, `logs/`, and experiment work directories
remain excluded from the image and from new Git commits.
Deploy code only when the shell or API changes. Ordinary trace publication uses the API and does
not run `railway up`; the volume is mounted independently and is not rebuilt or copied during an
image deployment.

Supporting exporters: `export_viewer_data.py` (per-turn frames), `export_signal_runs.py`,
`export_usage.py`, `export_tool_calls.py`, `export_game_thumbs.py`.

---

## Harness variants

The rule that keeps `main` from drifting away from a known-good baseline:
**the baseline is an immutable artifact; experiments copy from it and never edit it in place.**

- `harnesses/baseline-v12/` is **frozen** — the exact source the `bundle-v12` GCS artifact runs
  (which is not any clean git commit, so this vendored copy is the only faithful record).
- A variant = copy of `baseline-v12` + its own patch → its own new-named bundle. Never mutate
  the baseline, never overwrite a shared GCS bundle.
- Small/additive and sharing the agent loop → an env-toggle stored as `patch/` + `MANIFEST.md`.
  Fundamentally different code (a two-agent world-model harness) → its own folder.
- Every folder carries a `MANIFEST.md`: what it derives from, the diff, env config, and its
  validated ex-`ft09` score(s).

See `harnesses/README.md`.

## Layout

```
docs/            the site — Games (public) + Internal runs (gated), plus a local export cache
  static/games/  game manifest, per-game .py source, the Pyodide engine, tile shim
  data/          generated per-run JSON; published to Railway and ignored by Git
harnesses/       frozen baseline + one folder per variant, each with a MANIFEST
ARC3-Inference/  the duck harness itself (tool-using solver over TAAF); distill/ holds the
                 Phase-1 rejection-sampling SFT extractor
tufa-arc-agi-framework/, vendor-taaf-grafts/   upstream framework + our grafts
gcp/             spot-safe launch kit: restartable runs, GCS log sync, crash-loop guards,
                 one startup script per harness variant
logs/            ignored local artifacts; canonical copies remain in GCS
scripts/         catalog builder, run exporters, publish pipeline
kaggle/          the exact upstream notebook + its launch metadata
environment_files/  the 25 official games
```

Big raw request logs (`*_requests.jsonl`, multi-GB for thinking runs) live in
`gs://cellens-ai-artifacts/arc3-duck/` rather than git; a424-run request logs are included
gzipped.

## Provenance

The harness is a working fork of [Tufa Labs' ARC-AGI-3 Duck Harness](https://www.kaggle.com/code/jeroencottaar/tufa-labs-duck-harness-june-30-milestone-winner)
(June 30 milestone winner) by Harold Bessis, Jeroen Cottaar, Isaiah Pressman, Andries Smit,
Michal Tesnar and Stefano Viel, MIT-licensed. Commit `a2dddac` is pristine upstream; every
divergence since is one reviewed commit. Competition environment files are not redistributed
here.

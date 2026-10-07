<!--
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: Operator README for the Spark runner, the backend of the Mode explorer's Play button. Lives in the repo
  (tools/spark_runner/README.md) and as ~/arc3-runner/README.md on Jethro. How it is wired, how to restart it, where
  things are on disk. Design and caveats: docs/2026-10-06-spark-runner.md.
SRP/DRY check: Pass - operations only; the design write-up is the doc above.
-->

# Spark runner (Jethro, gx10-a424)

Plays ARC-3 games from a chosen level (an exact start, level 1 from RESET, or the stuck-level snapshot) under a Mode explorer scheme, on the two-Spark Flash-Next server. A job either carries context (the default) or starts with **no context**: the board at that level's start, the model on a new game's first turn (added 6-Oct, see below).

```
browser (arc3.sonpham.net/mode-explorer.html, signed in)
  -> site backend /api/v1/spark-runner/*   (railway/spark_runner.py: relay + stores job views in Postgres)
  -> ARC tailnet -> https://gx10-a424.tail1528b6.ts.net   (tailscale serve, tailnet only)
  -> arc3-runner.service on Jethro, 127.0.0.1:8787   (server.py: queue, key, job files)
  -> sample.py, one process per sample   (Son's 31.63 notebook harness, games in the offline engine)
  -> 127.0.0.1:11234 on Jethro = ssh tunnel from Cletus (arc3-runner-tunnel.service on Cletus)
  -> Flash-Next server on Cletus 127.0.0.1:1234 (two-Spark cluster; not the runner's to start or stop)
```

## Layout on Jethro (`~/arc3-runner`)

| Path | What |
|---|---|
| `code/` | `server.py`, `sample.py`, `modes.py`, `prompt_profiles.py`, `dupcheck.py`, `render_requests.py`, `checkpoints.py`, `boards.py`, `replays.py`, `build_harness.py` (copy of `tools/spark_runner/` in sonpham-org/arc-3) |
| `solutions/` | the original games' winning lines, one list per level: copy of `datasets/copycat-games/recolor/solutions/*.json` + `manifest.json` in the repo (trainable public games only) |
| `replays/verified.json` | per trainable game and level: the replay check of the winning line (actions to reach, board hash, same as the opening frame or not), built by `replays.py --verify-all`; a copy is in the repo at `datasets/spark-runner-replays/` |
| `harness/` | Franzen's bundle + the notebook's patch + Son's toolfast edits, `notebook_env.json` with the notebook's flags (built by `build_harness.py`) |
| `environment_files/` | the 25 public games (copy of `~/GitHub/arc-3/environment_files`) |
| `snapshots/` | rebuilt starting points (`<game>.json`, `index.json`) from `datasets/spark-runner-snapshots/`, plus `verified.json` (replay check) |
| `checkpoints/<game>/<level>/<variant>-<id>/` | EXACT level starts: `request.json.gz` (the full request body), `state.pkl.gz` (harness agent + session state), `actions.json` (from RESET), `meta.json`; `checkpoints/index.json` = per game, level and variant, the chosen one. Never pruned by the jobs sweep; at most 8 kept per level (best first) |
| `settings.json` | runner settings changed at run time: `harvest` (on/off), `harvest_lanes` (0-2) |
| `backups/` | tarballs of `code/` taken before each deploy |
| `jobs/<job>/` | `spec.json`, `job.json`, `samples/<k>/` = `transcript.txt`, `turns.jsonl`, `viewer.json`, `progress.json`, `result.json`, `error.txt` if it failed; `samples/<k>.log` |
| `runner.key` | the bearer key (0600). The Boss's copy: `~/bubba-workspace/secrets/arc3-runner.key` on the Mac Mini. The site relay sends it from the arc3-viewer Railway variable `ARC3_SPARK_RUNNER_KEY` (people never type it); change both together |
| `venv/` | Python 3.12: fastapi, uvicorn, requests, arc-agi 0.9.9, arcengine 0.9.3, numpy, pillow, imageio, scipy |

Old trajectories (`transcript.txt`, `viewer.json`) are deleted oldest-first when `jobs/` passes 40 GB
(`ARC3_RUNNER_MAX_GB`); the per-turn logs and results stay.

## Services

```bash
# Jethro
systemctl --user status arc3-runner          # the API + scheduler
systemctl --user restart arc3-runner         # running Play samples are requeued from their start; harvest samples are closed
journalctl --user -u arc3-runner -n 50
tailscale serve status                       # https://gx10-a424.tail1528b6.ts.net -> 127.0.0.1:8787 (tailnet only)
curl -s http://127.0.0.1:8787/api/health     # runner + model server reachability
# Cletus
systemctl --user status arc3-runner-tunnel   # ssh -R 11234 -> Cletus 127.0.0.1:1234 over the 200G cable
```

Settings are `Environment=` lines in `~/.config/systemd/user/arc3-runner.service`: model URL and id, concurrency
(default 4 samples at once), python path. Only one Play job runs at a time: the oldest unfinished one gets all
the lanes, later jobs wait whole, first come first served (`place_in_line` on each job, `play_queue` on
`/api/health`). Harvest only runs when no Play job is running or waiting.

Speed and limits (set 6-Oct after Son said about 40 tokens/s is good enough): measured on the two-Spark server,
one stream gets about 33 tokens/s, three get about 25 each (75 total), six get about 18 each (104 total). Four at
once is the compromise: each sample still gets about 22 tokens/s, so a turn takes about three minutes. Per-sample
caps default to 20 model turns (the main limit, so results do not depend on how busy the cluster is), 250 actions,
and 120 minutes as a safety net (well clear of twenty turns at about three minutes each). A Play request may override max_turns (1-60), max_actions, max_minutes (5-180).
A default 10-sample job takes roughly one to three hours. Outcome "turn_cap" means the sample used its turns.

## Exact level starts and harvest (added 6-Oct-2026, Son)

Every sample (Play and harvest) saves an exact checkpoint the first time it starts a turn after clearing a level:
the full request body the harness posts for that turn (system prompt, every message, board images, tool calls and
results, sampling settings), the harness agent's own attributes (conversation, retained functions, world model,
ledgers, counters) and the session's (runtime-state history, animation record), and every action from RESET. The
Python tool runs a fresh subprocess per call seeded only with the retained functions, so those are the whole REPL
state. If that turn runs a non-Stock mode, or the sample stops right after the clear, the Stock request is built
without being sent and the state put back. A sample that started from a rebuilt snapshot writes checkpoints marked
"not exact lineage"; they are kept but never chosen.

Choosing: per game, level and variant, exact lineage only, then fewest actions from RESET, then fewest tokens.
Play uses the chosen checkpoint for that level when there is one (job `start_kind` "exact"; each sample records
whether its first request equalled the saved one); otherwise the snapshot ("rebuilt").

Harvest: while no Play sample is queued or running, up to two one-sample Stock runs from RESET on the public games
outside the held-out eight (game with the fewest harvest runs first), caps 40 turns / 400 actions / 150 minutes.
A queued Play sample kills every harvest sample at once (job "preempted"; checkpoints already written stay).
Harvest jobs are hidden from `GET /api/jobs` unless `?kind=harvest|all`. When harvest is busy, a Play press waits one scheduler tick (about two seconds) while
harvest is stopped.

```bash
curl -s localhost:8787/api/health | python3 -m json.tool      # "harvest" block and "exact_starts" counts
curl -s localhost:8787/api/exact-starts                          # the index
K=$(cat ~/arc3-runner/runner.key)
curl -s -X POST localhost:8787/api/settings -H "Authorization: Bearer $K" -H 'Content-Type: application/json' \
  -d '{"harvest": false}'                                         # or {"harvest": true, "harvest_lanes": 1}
venv/bin/python code/sample.py --verify-checkpoint checkpoints/<game>/<level>/<id> /tmp/cpcheck   # replay + restore, no model
```

KV cache: not stored. See docs/2026-10-06-spark-runner.md for the measured re-prefill time.

## No context (added 6-Oct-2026, Son)

A Play request with `"context": "none"` starts the chosen level at that level's start board but gives the model a
clean conversation: Son's harness system prompt and the harness's normal first prompt for that board (real step and
level), no earlier turns, no notes, no retained functions, empty `history` in the Python tool apart from the current
frame. The board is reached by replay (`replays.start_for`): the chosen exact checkpoint's actions for that level if
there is one (either wording), else the winning line cut at that level; level 1 is a fresh game. The replay is checked
against the expected level, action count and board hash, and the sample refuses to play if they differ. These jobs
write no checkpoints. Job and sample results carry `context` ("carried" or "none") and `replay_source`; jobs from
before the option have no field and count as carried. `GET /api/replay-starts` lists the playable levels per game.

```bash
cd ~/arc3-runner
venv/bin/python code/replays.py --verify-all                       # bare-engine check of every level start (writes replays/verified.json)
venv/bin/python code/sample.py --render-first lf52 4 son /tmp/r    # one No-context first request, built and stopped before sending
venv/bin/python code/sample.py --render-all /tmp/r                 # every trainable game and level; /tmp/r/render-checks.json
```

The one line that differs from a game's true first turn: past step zero the harness says "No previous action sequence
was captured." where a new game says "No previous sequence has been executed yet." It is the harness's own wording for
a turn with a real step count and nothing executed in this conversation, and it is left as the harness writes it.

## Prompt profiles (added 6-Oct-2026, the Boss approved Astra's notes)

Every job runs under a prompt profile (`prompt_profiles.py`), recorded in its spec, `job.json` and every sample's
`result.json`; checkpoints record theirs in `meta.json`.

- **dedup** (default, every mode including Stock, harvest too): each standing instruction once, in the system prompt;
  the turn message has only this turn's facts (what the last sequence did, events, step, level, valid actions,
  retained functions, board images) and, last, the slot's `instructions` under "Instructions for this turn (<mode>
  mode):". A yielded turn re-opens with the harness's short "state_only" continuation instead of a copy of the turn
  message. A carried conversation built under the original prompts gets the same per-turn treatment.
- **original**: the prompts as the 31.63 notebook sends them, only to compare with older runs.

A Play slot is `{mode, name, base, instructions, settings, version}`; slots from older pages (`prompt` +
`stock_template`) still work: their instructions are the lines they added to Stock. A job queued before the profiles
existed runs under the default and gets `prompt_profile` + `prompt_profile_assigned` in `job.json` when it starts.

```bash
cd ~/arc3-runner
# the exact first request Play would send (no model): also POST /api/preview-request, which the page's button uses
venv/bin/python code/render_requests.py --spec lf52 3 son none dedup /tmp/r preview
# the dedup check: 13 cases, six kinds of turn each, every request through dupcheck.py (writes dedup-checks.json)
venv/bin/python code/render_requests.py --check-all /tmp/dc slots.json dedup original
venv/bin/python code/dupcheck.py /tmp/r/requests/01.json.gz       # one request
# the page's static/data/prompt-profiles.json (system prompts, tool schema, example turn messages)
venv/bin/python code/render_requests.py --page-data /tmp/pd docs-prompt-profiles.json
```

`slots.json` for the check is in the repo at `datasets/spark-runner-prompt-dedup/`. Previews are cached in
`~/arc3-runner/previews/`.

## Public link (Funnel)

Son agreed to a Tailscale Funnel link. It is not on yet: the tailnet policy has to allow this machine first
(Funnel is enabled on the tailnet, but neither Spark is in the allowed list). A tailnet admin opens the link that
`tailscale funnel --bg 8787` prints, or adds the node to the `funnel` node attribute in the policy file. Then:

```bash
tailscale funnel --bg 8787        # same address, https://gx10-a424.tail1528b6.ts.net, becomes public
```

The page does not need it: it goes through the site's relay. Funnel only matters for calling the runner directly
from outside the tailnet (scripts). With Funnel on, `GET /api/health|stuck-points|jobs` are readable by anyone with
the address; Play, Cancel and per-turn logs still need the key.

## API

`GET /api/health`, `GET /api/stuck-points`, `GET /api/exact-starts[?game=]`, `GET /api/jobs[?game=&kind=]`, `GET /api/jobs/<id>`,
`GET /api/start-board?game=&level=&variant=&context=` (the board at the start Play would use there, from `boards.py`; cached in
`~/arc3-runner/boards/`), `GET /api/replay-starts` (levels a No-context job can start from);
with `Authorization: Bearer <key>`: `POST /api/play`, `POST /api/jobs/<id>/cancel`, `POST /api/settings`,
`GET /api/jobs/<id>/samples/<k>/turns`, `GET /api/jobs/<id>/samples/<k>/events?after=` (the Watch view's trace-viewer events, docs/static/js/spark-watch.js), `POST /api/preview-request`. The Play body is built by `docs/static/js/spark-runner.js`.

## Rebuilding pieces

```bash
# harness (on the Mini; the bundle is the Kaggle dataset dfranzen/taaf-kaggle-source-bundle-copy)
python3.13 tools/spark_runner/build_harness.py --bundle <bundle dir> \
  --notebook arc3-kaggle/son-31p6/arc3-daniel-sb-t06-toolfast-rs-hicache11-kq8-ct1.ipynb --out <dir>
rsync -a --delete <dir>/ son@100.106.31.61:arc3-runner/harness/
# snapshots (needs the run files pulled from the arc3-viewer volume, see scripts/build_spark_snapshots.py)
python3 scripts/build_spark_snapshots.py --runs-dir <dir> --plan <plan.json>
rsync -a --delete docs/static/data/snapshots/ son@100.106.31.61:arc3-runner/snapshots/
# then on Jethro, re-run the replay check for every snapshot (writes snapshots/verified.json; no model calls):
cd ~/arc3-runner && venv/bin/python code/sample.py --verify-all snapshots
```

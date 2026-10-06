<!--
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: Operator README for the Spark runner, the backend of the Mode explorer's Play button. Lives in the repo
  (tools/spark_runner/README.md) and as ~/arc3-runner/README.md on Jethro. How it is wired, how to restart it, where
  things are on disk. Design and caveats: docs/2026-10-06-spark-runner.md.
SRP/DRY check: Pass - operations only; the design write-up is the doc above.
-->

# Spark runner (Jethro, gx10-a424)

Plays ARC-3 games from a game's stuck level under a Mode explorer scheme, on the two-Spark Flash-Next server.

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
| `code/` | `server.py`, `sample.py`, `modes.py`, `checkpoints.py`, `build_harness.py` (copy of `tools/spark_runner/` in sonpham-org/arc-3) |
| `harness/` | Franzen's bundle + the notebook's patch + Son's toolfast edits, `notebook_env.json` with the notebook's flags (built by `build_harness.py`) |
| `environment_files/` | the 25 public games (copy of `~/GitHub/arc-3/environment_files`) |
| `snapshots/` | rebuilt starting points (`<game>.json`, `index.json`) from `datasets/spark-runner-snapshots/`, plus `verified.json` (replay check) |
| `checkpoints/<game>/<level>/<variant>-<id>/` | EXACT level starts: `request.json.gz` (the full request body), `state.pkl.gz` (harness agent + session state), `actions.json` (from RESET), `meta.json`; `checkpoints/index.json` = per game, level and variant, the chosen one. Never pruned by the jobs sweep; at most 8 kept per level (best first) |
| `settings.json` | runner settings changed at run time: `harvest` (on/off), `harvest_lanes` (0-2) |
| `backups/` | tarballs of `code/` taken before each deploy |
| `jobs/<job>/` | `spec.json`, `job.json`, `samples/<k>/` = `transcript.txt`, `turns.jsonl`, `viewer.json`, `progress.json`, `result.json`, `error.txt` if it failed; `samples/<k>.log` |
| `runner.key` | the bearer key (0600). The Boss's copy: `~/bubba-workspace/secrets/arc3-runner.key` on the Mac Mini |
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
(default 4 samples at once across all jobs), python path.

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
Harvest jobs are hidden from `GET /api/jobs` unless `?kind=harvest|all`.

```bash
curl -s localhost:8787/api/health | python3 -m json.tool      # "harvest" block and "exact_starts" counts
curl -s localhost:8787/api/exact-starts                          # the index
K=$(cat ~/arc3-runner/runner.key)
curl -s -X POST localhost:8787/api/settings -H "Authorization: Bearer $K" -H 'Content-Type: application/json' \
  -d '{"harvest": false}'                                         # or {"harvest": true, "harvest_lanes": 1}
venv/bin/python code/sample.py --verify-checkpoint checkpoints/<game>/<level>/<id> /tmp/cpcheck   # replay + restore, no model
```

KV cache: not stored. See docs/2026-10-06-spark-runner.md for the measured re-prefill time.

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

`GET /api/health`, `GET /api/stuck-points`, `GET /api/exact-starts[?game=]`, `GET /api/jobs[?game=&kind=]`, `GET /api/jobs/<id>`;
with `Authorization: Bearer <key>`: `POST /api/play`, `POST /api/jobs/<id>/cancel`, `POST /api/settings`,
`GET /api/jobs/<id>/samples/<k>/turns`. The Play body is built by `docs/static/js/spark-runner.js`.

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

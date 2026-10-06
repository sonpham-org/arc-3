<!--
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: How the Mode explorer's Play button works (Son's go, #arc-3, 6-Oct 01:12 ET: "Let's create that Spark Runner
  so that others can start running on it"; his calls at 00:23 ET: a Tailscale public link is fine, and it all lives
  as part of the arc3 page). Covers the path from the page to the DGX Sparks, the starting points (snapshots), what a
  sample does, where trajectories and results live, how to restart it, and what is not exact.
  Updated 6-Oct 09:00 ET (Son, 08:33 ET: restart "with the context as if it played the game and completed the level
  up to that point ... store KV cache and REPL state of each level that has level completed. If there has been
  multiple completions, pick one."): exact level-start checkpoints, how one is chosen, harvest, the KV measurement.
SRP/DRY check: Pass - operations detail is in tools/spark_runner/README.md; stuck levels in
  docs/2026-10-06-stuck-levels-tally.md; mode wording in docs/static/data/modes.json.
-->

# Spark runner: Play on the Mode explorer (6-Oct-2026)

## What a press of Play does

On the Mode explorer's Queue tab, pick a game, drag modes into its queue (or leave it empty for a Stock
baseline) and press Play. The page sends the scheme to the Spark runner on the two DGX Sparks. The runner plays
N samples (default 10) of that game from its stuck level:

1. **Start from the stuck point.** Each sample starts the game in the offline game engine and replays the action
   line a recorded stock run of the Franzen-notebook line took to reach the start of that level, through the
   harness's own action path. Board, level and action count must match the recorded run or the sample refuses to
   play. The model gets that run's earlier conversation and the Python functions it had kept.
2. **Play the scheme.** Son's 31.63 notebook harness (Franzen's patched harness plus Son's port: noborder,
   temperature 0.6, toolfast), same system prompt and per-turn prompt. On each turn the scheduled mode's lines are
   put into the real per-turn prompt (the change between Stock and the mode, applied to the prompt the harness
   built, so placeholders like `{step}` never reach the model) and the slot's temperature, thinking on or off,
   effort, tool-call limit, thinking budget and action budget apply. A turn is one opening prompt; a continuation
   of the same turn keeps its slot.
3. **Stock after the scheme.** When the scheme runs out, Stock plays every later turn until the stuck level is
   cleared, the game ends, or the sample's cap is hit: 20 model turns by default (the main limit, so a sample gets the same
   number of turns however busy the cluster is), 250 actions, or 120 minutes as a safety net.
4. **Results.** Per sample: cleared or not, levels gained, actions used, turns, which modes ran, time. The page
   shows them right under the queue next to the stock tally for that level, for everyone signed in to the site.

Four samples run at once across all jobs; the rest queue. Measured 6-Oct on the two-Spark server: one stream
gets about 33 tokens/s, three about 25 each, six about 18 each. Son said about 40 tokens/s is good enough, so four at
once keeps each sample near 22 tokens/s (a turn takes about three minutes) and a default 10-sample job finishes in
roughly one to three hours. A sample process is light (about 160 MB, one CPU core at
most): the games and harness only. The model work is on the two-Spark Flash-Next server.

## Path

```
mode-explorer.html + static/js/spark-runner.js (signed in)
  -> /api/v1/spark-runner/*  on the site (railway/spark_runner.py)
       relays over the ARC tailnet (the site's Tailscale node, as the debugger relay does)
       stores every job view it sees in Postgres table arc3_spark_runner_jobs
  -> https://gx10-a424.tail1528b6.ts.net  (Jethro, `tailscale serve`, tailnet only)
  -> arc3-runner.service, 127.0.0.1:8787 (tools/spark_runner/server.py)
  -> sample.py per sample -> Flash-Next server on Cletus via ssh tunnel (Jethro 127.0.0.1:11234)
```

- **Access.** Watching results needs only a site sign-in. Play and Cancel need the runner key, asked once and kept
  in that browser; the runner checks it. People get the key from Son or the Boss. The key is not in the repo.
- **Funnel.** Son's choice of a public Tailscale link stands, but it is not switched on: the tailnet policy has to
  allow the machine first (a tailnet admin clicks the approval link once). The page does not need it, because the
  site relays over the tailnet. With Funnel on, the same address becomes public for scripts; reads would be open
  (game, scheme settings, progress, results) and Play, Cancel and turn logs would still need the key.

## Exact level starts (added 6-Oct-2026)

**What a starting point contains now.** Whenever any Spark sample (a Play job or an idle-time harvest run) clears a
level, the runner saves an exact checkpoint for the start of the next level, taken from the live harness process at
the start of the first turn on that level:

| Part | Exact? |
|---|---|
| The full request body the harness sends for that turn: system prompt, every message with its board images (base64), tool calls and raw tool results as sent, sampling settings, chat-template kwargs | **Yes**: captured as it is posted (`request.json.gz`) |
| Harness memory: the agent's own attributes (conversation history, world model, death ledger, pending images, effort rung, token counters, ...) and the session's (runtime-state history the harness reloads every turn, animation record) | **Yes**: pickled from the process (`state.pkl.gz`) |
| REPL state | **Yes**: the Python tool runs a fresh subprocess per call, seeded only with the retained functions (and their imports), which are part of the agent state above. There is no other live interpreter to save |
| Game state | **Yes**: every engine action from RESET with the harness's automatic flag (`actions.json`), replayed and checked against the saved board hash, level and action count |
| Model, variant, notebook flags, Stock settings, source job, actions and tokens to reach | recorded in `meta.json` |

When the turn after the clear runs a non-Stock mode, or the sample stops right after the clear, the Stock request for
that turn is built without being sent (the post is intercepted) and the saved state is put back, so every
checkpoint holds the Stock request. A sample that itself started from a rebuilt snapshot writes checkpoints marked
"not exact lineage"; they are kept but never chosen.

**Picking one.** Per game, level and version (Son's or Franzen's wording): exact lineage only, then the fewest actions
from RESET, then the fewest tokens. Up to eight are kept per level on Jethro; the page shows which one is used (its
action count, and how many there were).

**Starting from one.** Play uses the chosen exact checkpoint for that level when one exists: replay the actions,
check the board, put the harness state back. The job is labelled "exact start" and each sample records whether
the first request it sent equalled the saved one (for a scheme whose first slot is not Stock, only the context
before the last message is expected to match). Without one, Play falls back to the snapshot below and the job says
"conversation rebuilt".

**Tested 6-Oct on the real cluster (Flash-Next, two Sparks).** A harvest run on Functional Tiles (ft09) from RESET cleared
level 1 and wrote the level-2 checkpoint. A Play job (one sample, two turns, Stock) from that checkpoint sent a first
request byte-identical to the saved one and cleared level 2, writing a level-3 checkpoint by the dry build. A second
Play from that one also matched exactly and cleared level 3. Level 3 then had two checkpoints and the one with fewer
actions was chosen. A third Play from the level-4 checkpoint matched exactly too. A queued Play job stopped both running harvest samples within a second, and harvest picked up again when it finished.

**KV cache: not stored, not needed.** Measured on the idle cluster with one-token requests from a saved checkpoint,
cold (prefix cache defeated by a nonce at the start) and then warm:

| Prompt | Cold re-prefill | Warm (prefix cache) |
|---|---|---|
| level-2 checkpoint, 16k tokens | 5.3 s | 2.3 s |
| level-4 checkpoint, 34k tokens | 11.8 s | 3.3 s |
| same, history doubled, 63k tokens (about where the harness drains its history) | 22.0 s | 2.4 s |
| same, history x4, 121k tokens (near the window limit) | 43.7 s | 2.6 s |

So rebuilding the model's memory from a checkpoint costs about twenty seconds on the first sample of a job at a deep
level and a couple of seconds on every later sample, next to minutes per turn of generation. Exporting vLLM's
KV tensors (or adding a disk offload connector such as LMCache) would save seconds and add a fragile dependency on
the server build; not pursued. Flash-Next is a hybrid model whose recurrent state is only cacheable at aligned prefix
blocks (`--mamba-cache-mode align`), which is another reason the request body, not the cache, is the thing to keep.

**Harvest.** While no Play sample is queued or running, the runner plays up to two one-sample Stock runs from RESET
on the public games outside the held-out eight, the least-harvested game first, purely to collect exact checkpoints
for every level they clear (caps 40 turns, 400 actions, 150 minutes). Play always comes first: a queued Play sample
kills every harvest sample at once. On by default; switched with `POST /api/settings` (runner key); state on
`/api/health`. Harvest jobs are not listed with Play jobs.

**Site.** The page reads exact starts from the runner's stuck-points answer; the relay keeps the small index
(game, level, version, count, the chosen one's actions, tokens and source job) in `arc3_spark_runner_exact_starts`.
The checkpoints themselves (request bodies with model thinking and board images) stay on Jethro.

## Starting points (snapshots, "conversation rebuilt")

`datasets/spark-runner-snapshots/<game>.json`, built by `scripts/build_spark_snapshots.py`. One per game that has a stuck
level (21 of 25; the four that clear every level have none). Source: the seven 2-Oct-2026 stock runs of the
Franzen-notebook line that are on the site's volume (the four 3-Oct runs in the tally are not stored there as
full runs). Per game the first of those runs that reached the stuck level is used; the snapshot is the end of the
turn in which it got there (that batch stops at the level change).

| Part | Source | Exact? |
|---|---|---|
| Game state | the run's action line (including automatic RESETs) replayed in the engine | **Yes**: all 21 replayed to the recorded board, level and action count (`verified.json`, checked on Jethro 6-Oct) |
| Conversation | the run's stored per-turn transcripts: prompts, thinking, python calls, rendered tool results | **No**: rebuilt. The site keeps transcripts, not request bodies; board images and the raw tool-result JSON are missing. Oldest turns are dropped past ~200k characters (the harness would have drained them too) |
| Retained functions | top-level functions in those python calls, last definition wins | Close: re-derived with Python's parser, not the harness's own retention checks |
| Harness memory not in the transcript | none | The first turn after the snapshot says "No previous action sequence was captured" where the real run summarised its last batch |

Games stuck at level 1 (Skewer Kebabs, Ghost Twin) start at the beginning of the game with no history, which is
exactly what a real run sees.

The snapshots are small JSON (3.2 MB in all) and live in the repo, not on the site's volume or in its static
files: the site serves its static folder without sign-in, and these files hold verbatim model thinking and code
from Son's runs, whose run data is sign-in only. The runner keeps its own copy; the page never needs them. The model's prompt cache is not stored anywhere: the server's prefix caching warms on
the first sample of a job and the later samples reuse it (measured above). Snapshots are now only the fallback for
levels that have no exact start yet.

## Where things are kept

- **Full trajectories:** on Jethro, `~/arc3-runner/jobs/<job>/samples/<k>/` — the harness's own transcript of every
  prompt, thinking, tool call and result (`transcript.txt`), one line per turn with mode, settings, how the mode
  text was applied, actions, level and tokens (`turns.jsonl`), frames (`viewer.json`). Oldest trajectories are
  pruned past 40 GB; results and turn logs stay.
- **Mode wording per job:** when the runner accepts a Play, the site stores what was sent per slot (full prompt text,
  Stock template, settings) with the shared mode version it came from, who saved that version and when
  (`arc3_spark_runner_job_modes`, see `railway/modes_store.py`). Modes themselves are shared and versioned in
  `arc3_mode_versions`; editing a mode later never changes what a past job points at.
- **Results summaries:** the runner's `job.json` / `result.json`, and a copy of every job view in the site's
  Postgres (`arc3_spark_runner_jobs`), so a game's results still load when the Sparks are off.

## Restart and check

```bash
ssh son@100.106.31.61                       # Jethro
systemctl --user restart arc3-runner        # running samples are requeued and start again from the snapshot
curl -s http://127.0.0.1:8787/api/health
ssh son@100.118.4.20 systemctl --user status arc3-runner-tunnel   # Cletus side of the model link
```

More in `tools/spark_runner/README.md` (also `~/arc3-runner/README.md` on Jethro).

## Not done / limits

- The page plays the stuck level. The runner itself accepts any level that has an exact start (API `stuck_level`).
- Funnel waits for the tailnet admin's approval (above).
- The runner does not start or stop the model server. If the cluster is being rebuilt, samples fail their requests,
  retry, and end with an error after repeated failures; the page shows that per sample.
- The eight held-out games (vc33 ar25 sb26 re86 su15 tr87 tu93 as66) are refused, as in the repo's other run
  scripts; four of them have snapshots (re86, su15, tr87, tu93). Son can lift this with
  `Environment=ARC3_RUNNER_ALLOW_HELD_OUT=1` in the service file.

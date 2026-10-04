# RL rollout server: operator runbook

Author: Claude Opus 5.5, 3-Oct-2026. Son approved starting RL on 3-Oct. Nothing here has been launched yet.

## What it does, in one paragraph

The best-combo notebook (the f40b168002b8 build: border off, ARC hot map, tuned drafter, T0.6, host KV tier) runs as a
**rollout server** on one G4 VM. It takes **sibling jobs**: one node of the game tree plus 5 tries. Try 0 plays the
stock harness (the anchor). The other 4 each play an assigned coach mode at the node, then follow the current policy.
The node is restored **once** (from a state snapshot when one exists, else by replaying the logged play) and forked
into the 5 siblings. The 10 server lanes take 2 nodes x 5 siblings, so the shared ~100k-token context is prefilled
once per node. A learner on the PC compares the siblings at each node, trains the policy toward the faster ones
(reward: the competition's level score, uncapped), writes the next policy and the next round of jobs, and the VM
picks both up while it runs.

## Pieces (all in `gcp/controllers/gtree-rollout/`)

| file | role |
|---|---|
| `pick_nodes.py` | picks nodes from the master files: level starts, then backward from each level's best clear, then uncertain nodes; at most N=4 samples per (node, mode); assigns modes per try |
| `rollout_driver.py` | inside the notebook: `serve()` (lane scheduler), `run_node()` (restore once, fork K siblings; K replays on Windows) |
| `arc3_state.py` | state snapshots: capture at a turn start, restore without replay, per-turn hook (`ARC3_STATE_SNAPSHOTS=1`) |
| `rollout_core.py` | job format, records in the ingest's master format, assignment and policy fields on each step |
| `rl_loop.py` | the learner (init / run / report) |
| `build_rl_notebook.py` | builds the server notebook from the best-combo build |
| `runner/rl-vm-startup.sh`, `runner/launch_rl_vm.sh` | the VM (structure only) |
| `runner/rl_host_sync.py` | on the VM host: stages jobs and policy into the container, uploads finished tries |
| coach (`daniel-base-20261001/variants/coach/arc3_coach.py`) | `ARC3_COACH_POLICY=@file` re-read on change with a version check; `pin_policy`; `assign_next` |

Storage under `gs://cellens-ai-artifacts/arc3-gtree/v1/`: `rollouts/gtr-<campaign>/` (tries), `ctx/`, `blobs/`,
`state/<sha>.pkl.gz` + `state/index/`, and `rl/<campaign>/` (`policy/`, `jobs/round-NNNN/`, `learner/`,
`results/<vm>/`, `runs/<run>/`, `STOP`).

## Pilot, step by step (Git Bash on this PC)

```bash
export CLOUDSDK_PYTHON='C:\python312\python.exe'
cd /d/codex-work/arc3-sglang-parking/gcp/controllers/gtree-rollout

# 1. code the VM host needs, and the server notebook
gcloud.cmd storage cp runner/rl_host_sync.py ../gtree-ingest/gtree_store.py ../gtree-ingest/gtree_ctx.py \
    gs://cellens-ai-artifacts/arc3-gtree/rollout-code/
C:/Python312/python.exe build_rl_notebook.py --out D:/codex-work/gtree-rl/nb --budget-s 7200 --upload
#    prints gs://cellens-ai-artifacts/arc3-duck/daniel-base/notebooks/<sha12>/notebook.ipynb  (= NB below)

# 2. the campaign: policy v0 (stock after the branch) + round 1 jobs from the 4 seed runs
C:/Python312/python.exe rl_loop.py init --campaign rl1 --limit 40 --K 5 --N 4

# 3. one VM (tries the zones in order)
bash runner/launch_rl_vm.sh a rl1 "$NB" us-central1-b us-east4-c us-east1-d

# 4. the learner, every 15 minutes, in its own terminal (survives a bad round; gcloud login expiry shows as an error)
C:/Python312/python.exe rl_loop.py run --campaign rl1 --every 15
```

## Watch

```bash
gcloud.cmd storage cat gs://cellens-ai-artifacts/arc3-gtree/v1/rl/rl1/runs/rl-rl1-a/phases.tsv
gcloud.cmd storage cat gs://cellens-ai-artifacts/arc3-gtree/v1/rl/rl1/results/arc3-rl-a/summary.json   # tries, clears, first_cached
gcloud.cmd storage cat gs://cellens-ai-artifacts/arc3-gtree/v1/rl/rl1/runs/rl-rl1-a/host.log
C:/Python312/python.exe rl_loop.py report --campaign rl1      # one screen, writes nothing
C:/Python312/python.exe rl_loop.py publish-status --campaign rl1 [--dry-run]   # the site's RL2 "Training" view
```
`run` publishes the same status document after every round (`--no-publish` to skip): VMs, rounds, the policy's mode
mix, totals per first mode and every node's sibling tries, to `/api/v1/rl2/publication/rl-campaign-<campaign>` plus the
`rl-campaigns` index (token from `ARC3_PUBLISH_TOKEN` or Railway). `--dry-run` writes both to `<cache>/published/`.

What to look for in `summary.json`: `first_cached` close to `first_prompt` for siblings (prefix sharing works);
`restore_s` small once snapshots exist (seconds, against minutes for a replay); few `diverged` / `aborted`.

The queue (fixed after the 3-Oct pilot, where a new 40-job round every 15 minutes made the server drop each round's
tail, so only ar25, bp35, cd82 and cn04 were ever played): the learner refills only when fewer than `--refill-below`
jobs are unstarted (default 2 x (lanes / K + 1) x VMs reporting = 6 per VM); the server plays the newest two rounds
oldest first (`ARC3_ROLLOUT_KEEP_ROUNDS`, older rounds' unstarted jobs are dropped); every round lists the games
least-sampled first; the host sync does not stage jobs another VM already played, runs or dropped. Use a new VM label
per launch (`launch_rl_vm.sh b ...`): each VM's `results/<vm>/summary.json` is the record of what it played.
Restore failures: a try that ends `diverged` (or aborted on an origin mismatch / failed restore) blocks its restart
point (source play + step) for the campaign; the learner log prints `blocked restart points` with the diff, the same
node is taken from another seed play, and a node that failed from 2+ source plays is blocked outright
(`learner/state.json` `blocked`, the status doc's `blocked`). The diverged try's `result.json` is uploaded to
`results/<vm>/<job>/k<k>/`. (Pilot cause: the ar25 root of seed run b began with the notebook's warmup RESET, which the
tree folds into step 1; the replay did not re-issue it, so the first request said "step 1" against the logged
"step 2". Fixed in `rollout_driver.prepare`; the run-b ar25 root stays blocked in rl1.)

## Publish (operator only, after looking at the tries)

```bash
ARC3_PUBLISH_TOKEN=... C:/Python312/python.exe ../gtree-ingest/ingest.py republish --runs gtr-rl1
```
(set the token from its file in Notepad, never on the command line). Held-out games never reach the store: the
picker, the server, the host sync and the master writer each refuse them.

## Stop

Graceful: the server finishes the nodes in flight, the host uploads, the VM powers off.
```bash
echo stop > /tmp/STOP && gcloud.cmd storage cp /tmp/STOP gs://cellens-ai-artifacts/arc3-gtree/v1/rl/rl1/STOP
```
Otherwise it ends by itself at the notebook budget (2 h). Do not delete a running VM: partial results come up every
2 minutes and at the end.

## Knobs

| where | knob | default |
|---|---|---|
| picker / learner | `--K` siblings, `--N` cap per (node, mode), `--limit` jobs per round, `--per-game`, `--backward-depth`, `--turn-cap`, `--token-cap` (generated tokens per try), `--caps mode,4,none` (cap assignment) | 5, 4, 40, 4, 6, 60, 200000, mode |
| learner | `--every` minutes, `--tau`, `--beta` (KL to the previous policy), `--floor`, `--all-steps` (also the policy's later steps), `--token-alpha` (reward x (sibling median tokens / tokens to clear)^alpha) | 15, 0.5, 0.1, 0.05, branch steps only, 0.5 |
| learner queue | `--refill-below` (unstarted jobs), `--lanes` (sizes the default), `--keep-rounds` (as the server), `--block-after` (failed tries that block a restart point) | 2 x (lanes/K + 1) x VMs, 10, 2, 1 |
| notebook env | `ARC3_ROLLOUT_LANES`, `ARC3_ROLLOUT_BUDGET_S`, `ARC3_ROLLOUT_RESTORERS`, `ARC3_ROLLOUT_FORK=0` (K replays), `ARC3_ROLLOUT_KEEP_ROUNDS` (0 = every round), `ARC3_STATE_SNAPSHOTS`, `ARC3_STATE_EVERY`, `ARC3_STATE_GZIP` | 10, 7200, lanes/5+1, fork, 2, 1, 1, 3 |

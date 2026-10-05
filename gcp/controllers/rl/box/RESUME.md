# Resuming RL v1 plan C after the box disk was deleted (5-Oct-2026)

Son: "pull it to GCS then delete the disk, we might need it back ... copy enough so that you can always resume".
The 3 TB box disk `arc3-rl-box1` (us-central1-b) was archived and deleted on 5-Oct. The run had trained models c001-c006;
c006 is the newest. This page shows where each piece is and how to rebuild the box.

## What lives where

| piece | where | why it is enough |
|---|---|---|
| trainer environment: `/opt/rl/venv`, base weights `/opt/m/bf16`, Daniel's W4A16 checkpoint `/opt/m/daniel`, `/opt/m/daniel-stacked`, round 0's adapter `104k-n0-train` and merge `105k-n0-merge` | snapshot `arc3-rl-train4-snap-20261004a` (US) | the 4-Oct trainer disk, unchanged since; the box was restored from it |
| every plan C training job: adapter, `optim.pt`, logs (`c001-train-1` ... `c006-train-1`) | `gs://cellens-ai-artifacts/arc3-rl/trainer/train4-1002/out/<job>/` | the next training starts from `c006-train-1` (`--init-adapter` + `--init-optim`) |
| merges `c00N-merge` (merged shards for c004-c006, reports and logs for all) | same `out/` prefix | the held-out test card needs merged shards; older merges can be redone from their adapter |
| hot-swap deltas (300 changed layers, 5.8 GB each) | `gs://cellens-ai-artifacts/arc3-rl/box-archive-1005/kaggle-delta/<merge>/` | the game servers load the newest model from these |
| record-picker state: `used_jobs.txt`, cut reports | `.../box-archive-1005/work-c/` | no try is trained twice |
| records of each training | `.../box-archive-1005/records/` | audit |
| held-out test card state (`panel-tested.txt`, image name) | `.../box-archive-1005/var-lib-box/` | models already tested are not tested again |
| box logs | `.../box-archive-1005/var-log-box/` | audit |
| trainer service's done list | `.../box-archive-1005/trainer-done.txt` | the job queue's history |
| driver state (models, campaigns, next job number) | `D:\codex-work\rl-20261001\c_state.json` on Son's PC | `ops/run_c.py` resumes from it |
| game inputs (Daniel's, tuned drafter) | `gs://cellens-ai-artifacts/arc3-duck/daniel-draft/kaggle-input`, `.../daniel-base/kaggle-input` | the box downloads them at boot |
| VM settings of the box | `gs://cellens-ai-artifacts/archive/vm-configs-1005/arc3-rl-box1.json` | metadata keys and notebooks |

Not archived because they can be recreated: docker and the Kaggle image (box_startup.sh installs or pulls them), the
`/kaggle-in` copies of the inputs, per-job n-gram caches (`/opt/m/work/ple`), merged shards of c001-c003 (redo with
merge_lora.py from their adapters).

## Rebuild the box (about 20 min plus the first model load)

1. Disk: `ops/box_create.sh arc3-rl-train4-snap-20261004a arc3-rl-box1 us-central1-b us-central1-c us-central1-f`
   with `CODE=gs://cellens-ai-artifacts/arc3-rl/code/<sha>`. It restores the snapshot to a 3 TB disk and creates the
   g4-standard-384. Set the metadata as in the saved VM config: `slot-gpus "0 1 2"`, `panel-gpu 3`,
   `trainer-gpus 4,5,6,7`, `slot-notebook` (hot-swap notebook), `panel-notebook` (held-out, no queue), `slot-input`.
2. Before the driver starts, put the plan C state back on the disk. SSH in, or use a one-off startup step:
   ```bash
   B=gs://cellens-ai-artifacts/arc3-rl/trainer/train4-1002/out
   A=gs://cellens-ai-artifacts/arc3-rl/box-archive-1005
   for j in c006-train-1 c006-merge; do sudo gcloud storage rsync -r $B/$j /opt/m/work/out/$j; done
   sudo mkdir -p /kaggle-delta /opt/m/work/c /var/lib/box
   sudo gcloud storage rsync -r $A/kaggle-delta/c006-merge /kaggle-delta/c006-merge
   sudo gcloud storage rsync -r $A/work-c /opt/m/work/c
   sudo gcloud storage cp $A/var-lib-box/panel-tested.txt /var/lib/box/panel-tested.txt
   ```
   Only the newest model is needed to continue. The game servers start from the base inputs and swap c006 in.
3. Driver: `C:/Python312/python.exe ops/run_c.py --box arc3-rl-box1 --zone us-central1-b --sha <code> --last-model <N>`,
   run detached (PowerShell Start-Process) with `c_state.json` as it is. Its `last_train` is `c006-train-1` and `k` is 7.
   Delete `D:\codex-work\rl-20261001\STOP_C` first.

## Fix before the next run

On a model switch, a stopped session waits for its running tries, and on 5-Oct one hung try per card blocked every card
from ~08:35 UTC. Kill a stopped session's tries after a grace period (give running Groups a dynamic deadline in
`gtree-rollout/rollout_driver.serve`), then rebuild the hot-swap notebook.

# RL box: the whole RL v1 loop on one 8-card machine

4-Oct-2026. Son: "just take 8 GPU and redo everything". This thread holds us-central1's whole RTX PRO 6000 Spot quota.

**One machine.** A g4-standard-384 (8x RTX PRO 6000, Spot, stops on preemption) in us-central1, the bucket's region. It boots
from a snapshot of the RL trainer's disk, so the weights, venv and earlier adapters are already there.

**Taking turns.** A round's tries must be played by the newest model, so play and training never overlap:

| phase | cards | what runs |
|---|---|---|
| play | all 8 | one rollout server per card (Daniel's notebook in Kaggle's image, `box_slot.sh`), 16 lanes each, until STOP |
| records, train, merge | all 8 | the trainer service's jobs, one model copy per card (`--dp 8`) |

The test panels (train / hard / held, and the extra copies) stay on 1-card VMs in other regions. Nothing waits for them.

**Files**
- `box_startup.sh`: the startup script, run on every boot. It installs docker and the container toolkit once, pulls
  the Kaggle image, then starts `box_agent.sh` and the trainer service (`trainer_service.py --gpus 8`, same job queue
  `train4-1002`).
- `box_agent.sh`: turns the slot requests in `gs://cellens-ai-artifacts/arc3-rl/box/<box>/requests/*.env` into
  `box_slot.sh` units (`rl-slot-<card>`). It hands out no card while `lora_train.py` or `merge_lora.py` runs. It writes
  `slots.json` next to the requests.
- `box_slot.sh`: `gtree-rollout/runner/rl-vm-startup.sh` adapted to one card. It writes the finish line after its last
  upload. Inputs are downloaded once per prefix into `/kaggle-in/<tag>`.
- `../ops/box_create.sh`: probe for an 8-card host, restore the snapshot there, create the box.
- `../ops/run_round_box.sh`: one round, which requests the servers, sends STOP after `PLAY_MIN` minutes from the first
  ready server, runs the loop check on the tries, then records and `run_round_v3b.sh`.
- `../ops/run_round_v3b.sh`: v3x with `KEEP_TRAINER=1` (the box is never stopped) and `DP=8`.
- `../ops/box_loop.sh`: rounds back to back. Round N+1 starts as soon as N has queued its training.

**Code upload.** Copy the box scripts to `gs://cellens-ai-artifacts/arc3-rl/box/code/`. The box reads them at boot,
and the agent fetches `box_slot.sh` again before every slot start, so a fix to it needs no reboot.

```bash
gcloud.cmd storage cp gcp/controllers/rl/box/box_agent.sh gcp/controllers/rl/box/box_slot.sh gs://cellens-ai-artifacts/arc3-rl/box/code/
```

**Logs on the box.**
- `/var/log/box/startup.log`, `/var/log/box/agent.log`
- per card: `/var/log/box/s<card>/{run.log,phases.tsv,host.log}`
- in GCS: `box/<box>/phases.log` and each server's `runs/<run id>/phases.tsv`

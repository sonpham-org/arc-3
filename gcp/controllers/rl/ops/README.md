# RL ops helpers (this Windows box, Git Bash)

- `push_code.sh`: upload this folder's code to `gs://cellens-ai-artifacts/arc3-rl/code/<sha>/`, print the sha.
- `submit_job.py <job_id> "<command>"`: queue a shell job for the trainer service (`trainer_service.py`) on the
  trainer VM; its output folder `/opt/m/work/out/<job_id>/` comes back to `.../trainer/<service>/out/<job_id>/`.
- `wait_job.sh <job_id> [minutes]`: wait for a job's EXIT file, print its log tail.
- `watch_tries.py --campaign <name>`: one line per change of a try campaign (VMs, claims, results).
- `watch_seeds.py`: watch the 4 Combo A RL seed runs (1-Oct) in Firestore.

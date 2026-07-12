"""Print the comma-separated official game ids that still need to be played.

Spot instances get preempted mid-run. Every shard of a run syncs its
runs/<stamp>_<run-id>/benchmark.json to GCS; on (re)start we pull those down and
skip any game that already reached a terminal state in ANY earlier shard:

  - "win"      -- solved, never replay
  - "gave_up"  -- spent its full per-game budget, replaying adds nothing

Games that were "playing"/"cancelled"/"crashed" when the VM died get replayed
from scratch (the arcade state is gone; there is nothing to resume mid-game).
Prints the full official list when no prior state exists.
"""

import glob
import json
import sys

sys.path.insert(0, "/opt/arc3/ARC3-Inference")
from inference.framework.kaggle import DUCK_HARNESS_PUBLIC_GAME_IDS  # noqa: E402

TERMINAL_STATES = {"win", "gave_up"}

done: set[str] = set()
for path in glob.glob(sys.argv[1] + "/*/benchmark.json"):
    try:
        bench = json.load(open(path))
    except (OSError, json.JSONDecodeError):
        continue
    for run in bench.get("game_runs", []):
        if run.get("state") in TERMINAL_STATES:
            done.add(run.get("game_id", ""))

remaining = [g for g in DUCK_HARNESS_PUBLIC_GAME_IDS if g not in done]
print(",".join(remaining) if remaining else "NONE")
print(f"terminal={len(done)} remaining={len(remaining)}", file=sys.stderr)

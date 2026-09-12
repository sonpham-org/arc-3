from __future__ import annotations

import json
import os
import signal
import time
from pathlib import Path


working = Path(os.environ["TAAF_KAGGLE_WORKING_DIR"])
results: dict[str, str] = {}
for label, filename in (
    ("curator", "world-model-curator/curator.pid"),
    ("vllm", "vllm.pid"),
):
    pid_path = working / filename
    if not pid_path.is_file():
        results[label] = "pid-file-missing"
        continue
    try:
        pid = int(pid_path.read_text().strip())
        os.killpg(pid, signal.SIGTERM)
        results[label] = f"terminated-process-group-{pid}"
    except (OSError, ValueError) as exc:
        results[label] = f"already-stopped-or-invalid: {exc}"
time.sleep(3)
(working / "flashnext-teardown.json").write_text(
    json.dumps(results, indent=2) + "\n", encoding="utf-8"
)
print("Flash-Next teardown:", results, flush=True)

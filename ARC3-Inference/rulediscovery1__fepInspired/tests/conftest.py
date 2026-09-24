# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: pytest configuration for the rule discovery prototype's tests: puts the repo root
#   (ARC3-Inference/) on sys.path so `import rulediscovery1__fepInspired` and the harness's
#   `inference.agent.action_names` resolve when pytest is pointed at this folder directly.
#   Written, NOT run (OpenMind asked for code only on 23-Sep-2026).
# SRP/DRY check: Pass -- path setup only; the distill/ path is owned by rulediscovery1__fepInspired/_distill.py.
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Package marker for the ARC-3 rule discovery prototype requested by OpenMind in #arc-3
#   (23-Sep-2026 21:03 ET): an explicit, active-inference-style loop that perceives objects and
#   events, fits a small rule language to what each action did, keeps a Bayesian posterior over
#   rule sets (MDL prior, prequential likelihood with a chain back-off), infers level goals, and
#   picks actions by expected free energy. Written, NOT run: only py_compile was used on it.
#   Module map (see README.md): _distill (the one import shim into ../distill), perception, rules,
#   hypotheses, beliefs, goals, policy, agent, offline_eval; tests/ holds pytest files for later.
#   Import from the repo root (ARC3-Inference/) as `import rulediscovery1__fepInspired`.
# SRP/DRY check: Pass -- marker only; the package reuses distill/ through _distill.py.
"""ARC-3 rule discovery prototype (active inference over a small rule language)."""

__all__ = [
    "perception",
    "rules",
    "hypotheses",
    "beliefs",
    "goals",
    "policy",
    "agent",
    "offline_eval",
]

# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Tensor-logic overhaul of the rule-discovery agent (OpenMind, #arc-3, 24-Sep-2026): engine.py (joins,
#   projection, temperature, forward chaining, gradients), relations.py (perception as a relational database),
#   learner.py (join-shape bank, gradient fit, structure test, T=0 export), rule.py (TLRule for the posterior),
#   plan.py (reachability by forward chaining), bridge.py (agent glue), offline.py (stage-2 evaluation on
#   recorded plays), report.py (the per-game report). Switched on by AgentConfig.use_tl.
# SRP/DRY check: Pass -- package marker only.
"""Tensor logic for the rule-discovery agent."""

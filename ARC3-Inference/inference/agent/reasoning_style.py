"""Harness-level reasoning style: baseline (default) vs compact Astra-shaped blocks.

`baseline` (default) -- no reasoning-format instruction at all, exactly as the
           stock harness always behaved. This is the control arm.
`compact`  -- inject a mandatory compact-reasoning instruction into the system
           prompt and a one-line reminder into every per-turn user prompt. The
           target shape is a terse state readout followed by the chosen action,
           with no self-narration and no re-litigating discarded plans.

Motivation: measured over the 25-game baseline, this model's reasoning blocks
average ~5,300 characters and 88% of them contain "wait"/"hmm"/"actually", while
every run terminates on the runtime clock rather than on losing. Tokens-per-action
is therefore the binding constraint, and it is addressable in the prompt at zero
GPU cost. This flag exists to A/B that claim against the untouched baseline.

Selected by the run config via the ARC3_REASONING_STYLE env var so a single
checkout can run either arm -- no separate patched tree. Default is `baseline`;
set ARC3_REASONING_STYLE=compact for the treatment arm.
"""
from __future__ import annotations

import os


def reasoning_style() -> str:
    style = os.environ.get("ARC3_REASONING_STYLE", "").strip().lower()
    return "compact" if style == "compact" else "baseline"


def compact_reasoning_enabled() -> bool:
    return reasoning_style() == "compact"

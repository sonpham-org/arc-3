# Astra trace audit — front-load the reasoning, then roll forward

Source: Son Pham, posted in `#arc-3` on 2026-09-05. He used Astra to read Astra's public
ARC-3 replay traces and audited our harness against them. The numbers below are transcribed
from his report as posted; they have not been re-derived from the replays here.

See `README.md` in this directory for what the public dump does and does not expose — in
short, the raw chain-of-thought is never available, only intermittent provider summaries
plus token counters. The counters are what this audit rests on.

## The lesson

Astra spends heavily on understanding a mechanic, then avoids repeatedly solving the same
problem. The expensive phase is the initial one. Once it is confident, it rolls forward
cheaply instead of re-deriving what it already knows on every action.

Our harness does the opposite: it pays near-full reasoning freight per action for the whole
run.

## The numbers

**S5I5, same model at max reasoning:**

| Measure | Standard harness | Provider adapter |
|---|---|---|
| Levels solved | 8/8 | 8/8 |
| Actions | 242 | 243 |
| Generated tokens, incl. reasoning | 210,649 | **36,706** |
| Median generated tokens per action | 482.5 | **32** |

82.6% fewer generated tokens for essentially the same action sequence. Most of the saving is
reasoning tokens, not a shorter visible answer.

**WA30:** the standard run reaches 8/9 levels at roughly 1.40M logged generated tokens; the
adapter completes 9/9 at 73,048.

**Caveat, Son's own:** these are individual runs, not an experiment isolating one harness
feature. Do not quote them as a controlled ablation.

## Why it matters here

- Some Astra token traces land **inside our 108k limit**. The behavior is reproducible under
  our budget — the ceiling is not what blocks us, the spend pattern is.
- A median of 482.5 generated tokens per action means we are re-reasoning the mechanic every
  step. The adapter path produces the same actions at 32.
- Worth implementing. It may also let us retreat on model size, since the win comes from
  where the tokens go rather than from raw capability.

## Open questions

- What does the provider-adapter path actually do differently — retained state across
  actions, or just suppressed per-step reasoning?
- Where is the confidence threshold that flips heavy to cheap, and what happens when the
  mechanic shifts mid-game?
- Does cheap rollout survive a level-3+ mechanic change, or does it need an explicit
  re-entry into the expensive phase?

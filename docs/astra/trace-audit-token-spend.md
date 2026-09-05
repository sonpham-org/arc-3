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
- Worth implementing as a cost measure. **Do not yet read it as the cause of the score
  gap** — see the regime caveat below. In particular, "this lets us retreat on model size"
  does not follow from these numbers.

## Open questions

- What does the provider-adapter path actually do differently — retained state across
  actions, or just suppressed per-step reasoning?
- Where is the confidence threshold that flips heavy to cheap, and what happens when the
  mechanic shifts mid-game?
- Does cheap rollout survive a level-3+ mechanic change, or does it need an explicit
  re-entry into the expensive phase?

## Regime caveat: the token result and the score gap are not the same phenomenon

Added 2026-09-05 after re-reading `astra_v3_gaps.json` alongside the numbers above.

Split the 25 games by how much the six default-harness configurations disagree with each
other, and the default harness has three regimes, not one:

| Regime | Games | Default spread across 6 configs | Gap to PA |
|---|---|---|---|
| Deterministic floor | BP35, G50T, TU93, LF52 | 0.018 – 0.087, at scores under 0.11 | 0.89 – 0.98 |
| Chaos band | 17 games | median 0.373, up to CD82 1.000 and SB26 0.972 | 0.00 – 0.79 |
| Deterministic ceiling | S5I5, LP85, FT09, AR25 | 0.000, flat at 1.000 | 0.000 |

This refines the README's "reasoning effort is noise" claim. It is noise **in the middle
band only**. At the floor it is not noise at all — four games fail reproducibly at every
reasoning level, within 0.09 of each other. That reproducibility is what makes them the
debuggable ones.

**The caveat that matters for the token numbers above.** S5I5 — the game the 82.6% figure
comes from — is a deterministic-ceiling game: default spread 0.000, gap to PA 0.000. Both
harnesses win every configuration. So the cheap-rollout evidence was measured on a game
where the harness makes no difference to the score whatsoever. WA30 is no better as a
tiebreaker: its default spread is 0.373, so a single standard-vs-adapter pair there sits
comfortably inside the default harness's own noise.

Conclusion: front-load-then-commit is **demonstrated as a cost win and unproven as the
mechanism of the score gap**. Nobody has yet shown that this is what turns BP35 from 0.02
into 1.000.

## Hypothesis worth testing: the floor games die, they do not run out of budget

The README's TU93 worked case is the only action-level evidence in this directory: the best
default configuration spent 232 actions and **38 resets** to reach 2 of 9 levels and a
GAME_OVER; Provider Adapter took 218 actions and **2 resets** to 9 of 9 and a WIN. Similar
action budget, opposite outcome, twenty times the deaths.

If that generalizes, then front-loading buys score by **not taking fatal actions**, and the
token saving is a second consequence of the same behavior rather than its cause. One
behavior, two effects — not one effect causing the other.

**The check that discriminates.** Pull one BP35 default replay and one BP35 PA replay and
count two things: total resets, and the action index of first death. If the default run
dies early and repeatedly on a game it scores 0.022 on, the mechanism is confirmed and the
fix is a commit-gate on irreversible actions, not a token budget.

Note on getting that data: the replay pages under `three.arcprize.org` render the log
client-side — the served HTML contains only an empty `reasoning-log-empty` shell behind a
suspense boundary. Static `curl` will not get it. Needs a headless browser or the streamed
RSC chunk.

## Correction to the README

`README.md` in this directory calls five games "pure scaffolding failures" and includes
SK48. SK48 does not belong in that group: it is the one game where Provider Adapter also
fails to saturate (worst PA level 0.278), with TN36 at 0.888 the only other non-saturating
case. There are **four** pure scaffolding failures — BP35, G50T, TU93, LF52 — and SK48 is
a separate, more interesting case where neither harness closes it out.

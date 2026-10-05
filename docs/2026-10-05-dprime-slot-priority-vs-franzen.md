# Slot priority: Affectify's D' vs Daniel Franzen's Milestone 2 scheduler

Written 5-Oct-2026 by Bubba (Claude Opus 5.5) after Son asked for a comparison in #arc-3.

Notebook compared: <https://www.kaggle.com/code/shiiin9/affectify-arc-31-54-in-a-single-sub>
("Affectify ARC | 31.54 in a Single Sub", Osaka Metropolitan University team).
Base it modifies: <https://www.kaggle.com/code/dfranzen/arc-agi-3-milestone-2-solution>.
Our best submission (28.94) is also built on Franzen's notebook, so D' can be applied to our base directly.

## What is the same

Both notebooks were pulled and diffed cell by cell. These are identical: the harness patch, the model
(Intel AutoRound W4A16 Qwen3.8 Flash Next with the albucino drafter), sglang serving, prompts, and the
`TRUE_SUBMISSION` settings (1 pass, concurrency 120, 532 minutes per game, analyzer timeout 900 s).
Both run with `ARC3_PRIORITY_REFRESH_QUEUE=1`, so the waiting queue is re-ranked at every context trim.
In both, a running game keeps its slot until its context is trimmed, then competes again for a slot.

The only change in D' is one cell placed just before `await bm.run(...)`. It replaces
`tool_agent.priority_value` and `tool_agent.ProgressPace`, and it changes how unstarted games are ranked.
When the patch is installed it prints `#OURS_FORM ok version=d_prime`. If Franzen's names have changed,
it raises an error.

## Franzen's priority (as he submits it)

Env in his notebook: `PACE=0`, `TAIL_FADE=1`, `TAIL_FADE_FRACTION=0.2`, `TAIL_LOOKUP=remaining`,
`SCORE_NORMALIZATION=1`.

```
value = (A + B·φ) · chance / pace
A      = ℓ · (25 / (25 + a))^2 · norm(N)          norm(N) = 55 / (N(N+1)/2), N clamped 6..10
B      = 8 / 7 / 5 / 0 for ≥3 / 2 / 1 / 0 levels remaining after the current one
φ      = linear fade 1 → 0 over the last 20% of the run
chance = 0.25 · 0.5^((a/115)^2) + 0.75 · 0.5^((t/62000)^2)
pace   = 1 (pace tracking off)
```

Unstarted games sit in a separate band above every started game, so they always go first.

## D' priority

```
value = A·M·C + B·φ
A = (1 + 0.5(ℓ−1)) · norm(N) · (300 / (300 + a))^2.5
M = clip((30000 / p)^0.4, 0.25, 4)       p = mean tokens per cleared level in this game; M = 1 before the first clear
C = 0.1·max(0.1, 1 − a/115) + 0.9·max(0.1, 1 − t/T),   T = 225000 · clip(p/30000, 0.5, 2)^0.5
B = 16 / 14 / 10 / 0 for ≥3 / 2 / 1 / 0 levels remaining
φ = linear fade 1 → 0 over the last 40% of the run (the patch sets TAIL_FADE_FRACTION to 0.4)
```

The authors say the coefficients came from their own simulator (`arceval/sim/simulate.py`). They are not
publishing how they fitted them.

## The real differences

1. **The levels-left bonus is outside the hazard.** Franzen multiplies (A + B) by `chance`, so a game that
   has burned many actions or tokens on one level loses both its current value and its future bonus.
   D' adds B after the hazard. A stuck game with levels left keeps a floor and keeps getting slots until
   the fade. B is also about twice as large as Franzen's.
2. **Pace is on and rewards cheap clears.** Franzen submits with pace off. In D', a game that clears
   levels with few tokens gets up to 4x on its A term, and a game that clears them expensively drops to
   as little as 0.25x. Its token patience T is also stretched for games that need more tokens per level.
3. **Hazard shape.** Franzen uses a half-life curve on tokens with a 62k scale, so it falls off sharply
   past that point. D' uses a linear decay to a 0.1 floor over about 225k tokens, scaled by pace, so it
   is far more patient. Its action penalty is much gentler too (300 vs 25 human-action constant), though
   it uses a steeper power.
4. **Level weighting is flatter.** Franzen's A grows linearly with the level. D' grows at half that rate.
5. **Fade starts earlier.** The fade covers the last 40% of the run instead of the last 20%.
6. **Unstarted games compete.** In Franzen's scheduler they always jump the queue. In D' a fresh game is
   priced by the same formula (ℓ = 1, a = t = 0) and can lose to a game in progress. The cell after the
   run prints `#OURS_FRESH replaced=` with the count.

In short, D' spends more slot time on games that are progressing cheaply and still have levels to give.
It is more patient with long levels, and it gives up the guarantee that every game gets started early.

## How strong the evidence is

D' has one public submission, at 31.54. Franzen's unchanged code has scored 27.89 (his leaderboard),
31.47 (best on his notebook page) and 27.62 (the Affectify team's own resubmission). The authors say
themselves that one run cannot show how much better D' is. **31.54 is inside the run-to-run spread of
the unchanged base.** Treat it as a promising candidate, not a proven gain.

## What we do with it

- It is a cheap test: one self-contained cell on the same base as our 28.94 notebook.
- Gate it on the repeat-pass yardstick (Sprint 1, harness track). Compare our notebook with and without
  the D' cell over several passes before promoting it. Never promote on one pass.
- Check that its install line prints `ok` on our notebook. Our harness patch must keep Franzen's
  `priority_value` / `ProgressPace` / `_snapshot_priority` names, or the cell raises an error.
- Watch for the risk in difference 6: with unstarted games no longer guaranteed a start, a
  short-budget run could leave some games barely played. Check the `#OURS_FRESH` count and per-game
  action totals in the logs.

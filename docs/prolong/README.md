# PRO-LONG — the 97.4% harness, audited

Repo: <https://github.com/alexisfox7/PRO-LONG> · Paper: arXiv:2607.20064 (Fox, Wang, Rosu,
Dhingra, 2026) · MIT licensed · formerly the Read-Grep-Bash (RGB) agent.

Audited 2026-09-05 by cloning the repo and recomputing every number below from the
scorecards it ships (`research/arc-agi-3/scorecards/`). Nothing here is taken from the
abstract. It runs on the **same 25 public games** as the Astra results in `../astra/`, so the
two are directly comparable.

## What it actually is

A minimal harness, not a big scaffold. The whole idea:

> The harness appends every observation, action, and outcome to a single structured
> `logs.txt`, and the agent retrieves and reasons over it programmatically (grep, Python).

No subagents. No retrieval machinery. No vector store. The system prompt is about 30 lines
(`prolong_agent/agent/prompts.py`). The agent is an off-the-shelf coding CLI — Codex or
Claude Code — in a sandboxed container with `Read, Write, Edit, Bash, Grep, Glob` and a
persistent `/workspace/`. Each turn it writes `actions.json` with 1–20 actions; the runner
executes them and calls it again.

Two design choices carry the whole thing:

1. **The board is never read from the prompt.** The prompt tells the agent to parse the log
   programmatically because "reading full 64x64 board states from prompt can introduce
   precision errors." Analysis is written to files in `/workspace/` that persist, so it is
   looked up rather than re-derived.
2. **Front-load, then commit — as an explicit instruction.** Verbatim from the system prompt:

   > Prefer short lists (1–2 actions) when testing a new hypothesis so you see the result
   > before committing further; scale up toward {action_cap} for proven sequences.

That second line is the Astra behavior Son described — spend heavily to understand a
mechanic, then roll forward — written down as a rule instead of left to emerge.

## The numbers, recomputed

`fable_online_scorecards.txt` — Fable 5, 25 games, 1 rep each, official arcprize.org
scorecards: **mean 0.947**. The headline 97.4% in the README is best@2, a different cohort.

### PRO-LONG's scores mapped onto the Astra regimes

Regimes are from `../astra/trace-audit-token-spend.md`.

| Regime | Astra default | Astra PA | PRO-LONG (Fable 5) |
|---|---|---|---|
| Deterministic floor (BP35 G50T TU93 LF52) | 0.02 – 0.11 | 1.000 | mean 0.838, min 0.748 |
| Chaos band (17 games) | 0.21 – 1.00 | 1.000 (SK48 0.278 worst level) | mean 0.960 |
| Deterministic ceiling (S5I5 LP85 FT09 AR25) | 1.000 | 1.000 | 1.000 |

**This partly corrects the "pure scaffolding failure" framing, including my own.** Three of
the four floor games are also PRO-LONG's weakest: BP35 0.748, G50T 0.784, LF52 0.818 — and
those are three of its four lowest scores on the whole set. A completely different harness,
a different model, and the same four games are still the hard ones. They are not purely an
artifact of Astra's default scaffold. Astra's Provider Adapter closing all four at 1.000 is
the outlier result here, not the norm.

**RE86 is the most diagnostic game in the set and nobody has looked at it.** PRO-LONG scores
**0.417** — its single worst game — where Astra's default harness got 0.778 and PA got 1.000.
Every other game PRO-LONG loses is one Astra's default also lost. This one inverts. Whatever
RE86 demands, programmatic-log memory is bad at it and Astra's scaffold is fine with it. One
game, two harnesses, opposite verdicts: that is the cleanest available probe of what the two
approaches actually do differently.

### The ablation is honest, and smaller than the headline

Same model (GPT-5.5, codex backend, reasoning-effort high), memory varied:

| Condition | Max actions | Mean |
|---|---|---|
| prolong (full log) | 1000 | 0.502 |
| prolong, scored at 500-action cutoff | 1000→500 | 0.456 |
| in-prompt, no log (`--log-window -1`) | 500 | 0.247 |

The naive 1k-vs-500 comparison gives +25.5 pp, but it hands prolong twice the action budget.
The repo ships the budget-matched cutoff itself, which gives **+20.9 pp** — close to the
paper's claimed 18 pp average. They did not lean on the confounded number. Credit where due.

### The model matters more than the harness

Same PRO-LONG harness, different model:

- GPT-5.5: **0.502** mean
- Fable 5: **0.947** mean

Swapping the model is worth roughly +45 pp. The memory design is worth roughly +21 pp.
**The 97.4% headline is mostly Fable 5.** This kills the "we might retreat on model size"
line — that idea is already flagged as unsupported in
`../astra/trace-audit-token-spend.md`, and this is the hard evidence against it.

Per-game, the biggest ablation wins are TR87 +0.989, KA59 +0.830, M0R0 +0.763, TU93 +0.738,
LP85 +0.717. Two games get *worse* with the log: CN04 −0.108 and BP35 −0.005.

### Token convergence with Son's measurement

PRO-LONG claims it "matches or exceeds specialized harnesses at 4.2–5.8x fewer billed
tokens." Son's S5I5 figure is 210,649 → 36,706 generated tokens, a ratio of **5.74x**. Two
independent measurements of the same effect landing in the same band. Cost for the 97.4%
best@2 Fable 5 run: **$1,750** for 25 games.

## What we should take from it

1. The mechanism behind the Astra token gap is not mysterious and does not need a private
   provider adapter. Persist analysis to a file, parse the board programmatically, batch
   proven action sequences, and use a short prompt. It is reproducible in MIT-licensed code
   we can read today.
2. Our own harness should stop re-deriving the mechanic per action. That is the concrete
   change, and PRO-LONG is a working reference implementation of it.
3. **Do not report a scalar.** PRO-LONG's own GPT-5.5-vs-Fable-5 spread is 45 points on an
   identical harness. Same lesson as `../astra/README.md` point 3, from a second direction.
4. Next probe: RE86. Read PRO-LONG's RE86 log in `release_logs/` against Astra's RE86
   replays and find out what programmatic memory is bad at.

## Caveats

- The Fable 5 cohort is 1 rep per game and its scorecard file ships no settings block, so
  its action budget is not stated where the GPT-5.5 cohorts state theirs. Do not assume the
  budgets match across cohorts.
- The Astra numbers are best-of-six-configurations per harness; the PRO-LONG Fable numbers
  are single runs. The comparison table above is indicative, not like-for-like.
- Not reproduced locally. Running it needs Docker, an `ARC_API_KEY`, and a model key.

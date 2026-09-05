# GPT-6 Astra on ARC-AGI-3 — harness failure modes

Source: <https://arcprize.org/results/openai-gpt-6-astra>. The page is JS-only; the
numbers below were pulled from the JSON API behind it, not scraped from the HTML.
Raw extract: `astra_v3_gaps.json` (25 games x 12 configurations).

## Read this first: the chain-of-thought is not published

Every action in every replay carries `reasoning: null` alongside a non-zero
`reasoning_tokens` count (e.g. 1256). The model's actual thinking is **sealed** and is
not in the replay dump. What you can read is the terse `output` line per action — the
same ~40 tokens the site's Reasoning Log panel shows.

So the question "is the reasoning performative / nonsensical" is answerable only against
that summary line, plus the ratio of hidden reasoning tokens to output tokens. Anyone who
finds this directory expecting auditable reasoning traces will not find them. Do not plan
an analysis that needs them.

## The gap, per game

`default` = best of six default-harness configurations. `PA` = best of six Provider
Adapter configurations. Same model weights throughout.

- `BP35` — default 0.022 (worst level 0.004) -> PA 1.000 (worst PA level 1.000), gap **0.978**
- `G50T` — default 0.030 (worst level 0.000) -> PA 1.000 (worst PA level 1.000), gap **0.970**
- `TU93` — default 0.067 (worst level 0.022) -> PA 1.000 (worst PA level 1.000), gap **0.933**
- `LF52` — default 0.109 (worst level 0.022) -> PA 1.000 (worst PA level 1.000), gap **0.891**
- `SK48` — default 0.211 (worst level 0.103) -> PA 1.000 (worst PA level 0.278), gap **0.789**
- `SU15` — default 0.416 (worst level 0.077) -> PA 1.000 (worst PA level 1.000), gap **0.584**
- `SC25` — default 0.476 (worst level 0.000) -> PA 1.000 (worst PA level 1.000), gap **0.524**
- `TN36` — default 0.536 (worst level 0.036) -> PA 1.000 (worst PA level 0.888), gap **0.464**
- `M0R0` — default 0.714 (worst level 0.204) -> PA 1.000 (worst PA level 1.000), gap **0.286**
- `VC33` — default 0.733 (worst level 0.357) -> PA 1.000 (worst PA level 1.000), gap **0.267**
- `KA59` — default 0.750 (worst level 0.439) -> PA 1.000 (worst PA level 1.000), gap **0.250**
- `RE86` — default 0.778 (worst level 0.583) -> PA 1.000 (worst PA level 1.000), gap **0.222**
- `WA30` — default 0.800 (worst level 0.427) -> PA 1.000 (worst PA level 1.000), gap **0.200**
- `LS20` — default 0.835 (worst level 0.036) -> PA 1.000 (worst PA level 1.000), gap **0.165**
- `TR87` — default 1.000 (worst level 0.514) -> PA 1.000 (worst PA level 1.000), gap **0.000**
- `SP80` — default 1.000 (worst level 0.454) -> PA 1.000 (worst PA level 1.000), gap **0.000**
- `SB26` — default 1.000 (worst level 0.028) -> PA 1.000 (worst PA level 1.000), gap **0.000**
- `S5I5` — default 1.000 (worst level 1.000) -> PA 1.000 (worst PA level 1.000), gap **0.000**
- `R11L` — default 1.000 (worst level 0.143) -> PA 1.000 (worst PA level 1.000), gap **0.000**
- `LP85` — default 1.000 (worst level 1.000) -> PA 1.000 (worst PA level 1.000), gap **0.000**
- `FT09` — default 1.000 (worst level 1.000) -> PA 1.000 (worst PA level 1.000), gap **0.000**
- `DC22` — default 1.000 (worst level 0.564) -> PA 1.000 (worst PA level 1.000), gap **0.000**
- `CN04` — default 1.000 (worst level 0.588) -> PA 1.000 (worst PA level 1.000), gap **0.000**
- `CD82` — default 1.000 (worst level 0.000) -> PA 1.000 (worst PA level 1.000), gap **0.000**
- `AR25` — default 1.000 (worst level 1.000) -> PA 1.000 (worst PA level 1.000), gap **0.000**
## What that says

**1. Provider Adapter saturates the benchmark.** It reaches 1.000 on **25 of 25** games.
On 23 of 25 it reaches 1.000 at *every* one of its six configurations. The two exceptions
are SK48 (worst PA level 0.278) and TN36 (0.888). There is no game here that the weights
cannot solve; there are games the default scaffold cannot get the weights to solve.

**2. Five games are pure scaffolding failures.** `BP35 G50T TU93 LF52 SK48` — best
default score across all six reasoning levels is 0.02-0.21, PA is 1.000. Reasoning effort
does not move them. These are the cases worth reading action-by-action, because the
difference between 0.02 and 1.000 is entirely harness.

**3. Reasoning effort is not a dial, it is noise, on the default harness.** Within the
default harness alone, the same game swings enormously across levels: `CD82` 0.000-1.000,
`SB26` 0.028-1.000, `LS20` 0.036-0.835, `SC25` 0.000-0.476. Only four games (`S5I5`,
`LP85`, `FT09`, `AR25`) score 1.000 at every default level. **A single-configuration
score on this benchmark carries no information.** Reporting one number per model is
reporting one draw from a wide distribution.

## Consequence for our synthetic set

Point 3 is the one that binds us. If we score a harness against the arena games and
report one number, we have built the same measuring instrument that made a 1.000-capable
model look like it scored 0.02. Score N configurations and report the distribution; a
scalar is not a result.

See also `docs/arc-prize-2025-5th-place-lessons.md` for the same failure in the other
direction — a 120-item binary benchmark whose top ranks are inside its own seed noise.

## Worked case: TU93

Numbers in this section came from a single API pull and have not been re-verified.

Best default configuration: 232 actions, **38 resets**, 2 of 9 levels, GAME_OVER.
Provider Adapter (high): 218 actions, 2 resets, 9 of 9, WIN. Same weights, comparable
action budget. The default run spent its budget dying and restarting.

## Replay URLs

`astra_v3_gaps.json` carries all 12 replay URLs per game. Indices 0-5 are the default
harness and 6-11 are Provider Adapter (confirmed: `max(scores[:6])` reproduces the `base`
field on all 25 games). The order *within* each block of six has not been verified against
a replay — check before you rely on a specific index meaning a specific reasoning level. Transcripts extracted from the
recordings for the five scaffolding-failure games live beside this file when the
extraction has been run.

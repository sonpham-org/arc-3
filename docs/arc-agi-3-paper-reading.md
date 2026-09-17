<!--
Author: Claude Opus 5, for Mark Barney
Date: 17-September-2026
PURPOSE: A full read of the ARC-AGI-3 paper (arXiv:2603.24621v2, all 23 pages), checked against
what this repo's code, prompts and docs actually do. Written because the paper was only ever
cited second-hand: docs/how-this-feeds-kaggle.md sources it "via" the 31-Aug audit in
autoresearch-arena, which read sections 3.6 and 5. Everything else in it had not been read
into the tree, and three places where the repo disagrees with it had not been noticed.
SRP/DRY check: Pass. how-this-feeds-kaggle.md owns "why this project exists";
autoresearch-arena/arc3games/AUDIT_2026-08-31.md owns the private-set design brief. This file
owns only what the paper says and where the repo departs from it. It changes no code.
-->

# The ARC-AGI-3 paper: what it says, and where we don't match it

**ARC Prize Foundation, "ARC-AGI-3: A New Challenge for Frontier Agentic Intelligence".**
arXiv:2603.24621, v2 of 17-Apr-2026.

- arXiv: https://arxiv.org/abs/2603.24621 (PDF: https://arxiv.org/pdf/2603.24621v2)
- ARC's own copy, the one the 31-Aug audit cites: https://arcprize.org/media/ARC_AGI_3_Technical_Report.pdf

The PDF is not committed. arXiv lists it under its non-exclusive distribution license, which
covers arXiv's own distribution and nothing else, and this repo is public. Both links above
serve it.

Read in full on 17-Sep-2026. Where this doc says "the repo does X", the file and line are given.

---

## The short version

1. **Three different score caps are in use.** The paper's text caps each level at 115%. Our
   scoring code matches that. The prompt our agent actually runs with tells the model the cap is
   100%. The paper's own equation, as printed, says a third thing.
2. **ARC's random-play test is much stronger than ours.** ARC runs up to a million random actions
   and wants each level beaten by chance less than 1 time in 10,000. Our probe runs 1,200. Both
   agree the first level is allowed to fall to random play.
3. **`baseline_actions` is the score yardstick, not the budget.** ARC's budget on its own
   leaderboard is five times the human baseline, and it exists to cap API cost.
4. **What we're building is what ARC's official leaderboard leaves out.** The paper names
   training on synthetic lookalike games and ARC-specific harnesses as the things that board will
   not count. That board is not Kaggle, and the paper doesn't apply that rule to the Kaggle prize.
5. **ARC's game rules are written down, with numbers.** At least six levels, more than one
   mechanic, no numbers, letters or cultural symbols, a four-character ID with the real name kept
   private, and a test for whether two games are really different. The checklist is below.

---

## 1. Where the repo disagrees with the paper

### 1a. The per-level score cap

The paper scores each cleared level on how many actions it took compared with the human
baseline, squares that ratio, and caps it. What the cap is depends on where you look:

| where | what it caps | best possible level score |
|---|---|---:|
| paper, text (p.11 and p.13) | the squared score | **115%** |
| paper, Equation 1 as printed (p.12) | the ratio, *then* squares it | 132% |
| `ARC3-Inference/inference/tools/traces.py:42` | the squared score | **115%** |
| `tufa-arc-agi-framework/src/taaf/game.py:408`, `diagnostics.py:179` | the squared score | **115%** |
| ARC toolkit `arc_agi` 0.9.8 and 0.9.9 (`scorecard.py`) | the squared score | **115%** |
| ARC toolkit `arc_agi` 0.9.1 and 0.9.6 | the squared score | 100% |
| **the agent's prompt**, `ARC3-Inference/inference/agent/prompts.py:17` and the frozen `harnesses/baseline-v12` copy | the ratio | **100%** |
| `docs/trace-findings/2026-09-11-priors-vs-the-25.md:54`, `2026-09-11-bp35-astra-grid2-b476.md:105` | the ratio | 100% |

Read this as: **our scoring code, the paper's text and the current ARC toolkit all agree on
115%.** The 100% figure is what older toolkit versions did. The prompt still tells the model
that. Equation 1 as printed goes against the paper's own text, and no code anywhere does it.

What the gap costs, by arithmetic only (not measured): the 15% extra exists only when the agent
clears a level in *fewer* actions than the human baseline. Beating human pace by about 7% earns
all of it. The model is currently told that beating human pace is worth nothing.

**Not fixed here, deliberately.** Changing the prompt changes agent behaviour. That makes it an
experiment arm, not a typo fix, and `harnesses/baseline-v12` is frozen.

Local trap: the Homebrew `python3.13` on the Mac mini has `arc_agi` **0.9.6**, which caps at 100.
Anything scored through that interpreter's copy of the toolkit will come out lower than Kaggle
whenever the agent beats human pace on a level.

### 1b. The random-play gate

ARC checks every game in four ways before it ships (section 3.5):

- **50,000 random steps.** No level may be beaten by accident.
- **1,000,000 random steps.** Every level after the tutorial must stay unbeaten.
- **A second 1,000,000-step sweep across all levels**, used as a crash and bug fuzzer.
- **A state graph.** Every reachable state is mapped, which gives an exact chance that a random
  player wins each level. The bar is **under 1 in 10,000**. The paper's example is `ls20`
  level 1 at 1 in 355. That level is the tutorial, so it's allowed.

Ours (`autoresearch-arena/arc3games/GLOWUP_RECIPE.md`, the `not_free` rule in
`CLARITY_LOOP.md`) is `probe_one.py`: **1,200 random actions**, reset on death, and random play
must not reach level 2.

The two agree on the shape. ARC says outright that random play clearing the tutorial is fine by
design, which backs Son's 07-Sep ruling. The difference is strength: our probe plays about 800
times fewer actions than ARC's second test and gives no per-level chance. A level that random
play clears 1 time in 2,000 can easily pass ours and would fail theirs.

`REFERENCE_SET_LESSONS.md` calls the random-play check "ours alone". That was true of the
community game repo it was reviewing. ARC's own pipeline runs a stronger version.

### 1c. What `baseline_actions` is

`docs/how-this-feeds-kaggle.md` (section "The action budget is derived from humans") says that
`baseline_actions` is the agent's budget, at 5× the human median.

The paper separates these:

- **The human baseline** is the scoring yardstick. Per level, it's the upper-median best human:
  rank everyone who cleared the level by action count and take the upper middle. With 4 or 5
  finishers, that's the 3rd place.
- **The 5× budget** is a limit ARC puts on *its own official-leaderboard runs*, so frontier-model
  API bills stay bounded (section 4.3). ARC says the score lost to it is negligible.

The paper never names the metadata field. It also says nothing about Kaggle's action limit. So
the safe reading is: `baseline_actions` is the yardstick, and the budget is a separate number
per venue.

---

## 2. What bears on our work

### The official leaderboard vs. what we do (section 4.3)

ARC calls two things overfitting that clouds public judgement:

- **Task-specific:** built or trained with knowledge of the public 25. ARC will never report
  public-set scores on the official board, and releases a harness that scores 100% on them from
  human replays to prove the point.
- **Domain-specific:** trained on many synthetic ARC-AGI-3 lookalike games, or run inside a
  harness full of ARC-specific strategy.

The official board therefore runs frontier models behind a plain API, with **no harness, no
tools, and one short fixed system prompt**. In substance, that prompt tells the model it's
playing a game, its goal is to win, and the last action in its reply is the one that runs. Harness results go to a separate, self-reported
**community leaderboard** that ARC doesn't verify.

For us: synthetic games as SFT data plus the duck harness sits squarely in the second bucket. The
paper does not say that affects the Kaggle track. Section 7 only requires prize winners to open
source their solution. Our results belong on the community board, not the official one. The
paper's system prompt is also a ready-made no-harness control, if we ever want one.

### Harnesses built on seen games didn't transfer (section 4.3.1)

ARC paid researchers to build general harnesses on three public games (`ls20`, `ft09`, `vc33`)
and then ran them on the full public set. With Opus 4.6:

| game | no harness | Duke harness |
|---|---:|---:|
| a variant of `tr87` | 0.0% | **97.1%** |
| `bp35` | 0.0% | 0.0% |

ARC's conclusions: seeing the frames and working the API isn't what holds models back, and a
harness tuned on some games says little about unseen ones. Two local connections: our bp35 trace
findings are about the game the Duke harness also couldn't touch, and `tr87` is one of the seven
held-out games fenced out of the SFT corpus in PR #35.

### What earlier approaches did (section 6)

- **StochasticGoose (Tufa Labs), 1st in the 2025 preview, 12.58%.** A small CNN plus
  reinforcement learning that predicts which actions will change the frame. This is the same
  Tufa whose framework is vendored here as `tufa-arc-agi-framework/`.
- **Blind Squirrel, 2nd, 6.71%.** Builds a state graph from observed frames.
- **Duke harness.** Lets the model run Python over its own action history, pulling out only what
  it needs instead of carrying a rolling window of 64×64 frames. It cleared all three preview
  games at about human action counts. Our agent's `python` tool is the same idea.
- **Arcgentica (Symbolica).** An orchestrator that never touches the game and hands work to
  sub-agents that report back short summaries. It also cleared all three.

ARC's summary: both preview winners were informed search, covering as much of the action space as
they could.

### ARC's game rules, as a checklist (section 3.4)

| rule | ours |
|---|---|
| Core-knowledge priors only: objects, basic geometry and topology, basic physics, agents with goals | matches the brief in `how-this-feeds-kaggle.md` |
| No numbers, letters, recognisable real-world clip-art, or cultural conventions (green means go) | not checked here |
| Novel against existing video games *and* against every other game in the set | see the novelty test below |
| Solvable by a person in about 20 minutes, most in a few | no human calibration yet (31-Aug audit, Finding 9) |
| Difficulty from **combining** ideas learned on earlier levels, not from obscurity | not checked here |
| Level 1 is a tutorial. Random play clearing it is acceptable | matches, see 1b |
| **Several mechanics per game.** One mechanic scaled up is named an anti-pattern | not checked here |
| **At least six levels** | the 31-Aug audit measured our set at about a fifth the depth of the public games |
| Four-character ID. The longer name stays private because it leaks the goal | matches our opaque-ID rule, for the same reason |

**The novelty test** is concrete enough to build. If one program can solve two games and is at
least 50% shorter than the two games' separate solvers put together, the games are probably not
different enough. That's a sharper form of what `PAIRWISE_DIFFERENTIATION` is after.

### Other details worth knowing

- **Action space:** five key actions, an **Undo** action, and one click action with grid
  coordinates. Undo is an action like any other, which agrees with
  `docs/trace-findings/2026-09-15-bp35-undo-costs-a-move.md`. Tool calls and reasoning are not
  actions.
- **Level weighting:** level *n* counts *n* times. A game's score is also capped at the weighted
  share of levels cleared, so racing through early levels can't make up for missing late ones.
  `traces.py` does both.
- **Humans vary a lot.** On the public games, human per-level efficiency against the baseline runs
  from about 10% to 300% and beyond (Figure 6). Late levels can take far more actions than early ones. In
  `vc33`, level 6 takes about 10 times the actions of level 1.
- **ARC's engine is Python, built for at least 1,000 frames per second**, after they dropped Unity
  as too slow.

---

## 3. Numbers to have to hand

| | |
|---|---|
| environments | 25 public, 55 semi-private, 55 fully private |
| people per candidate game | 10. Kept only if at least 2 cleared every level on first sight |
| human study | 486 people, 414 candidate games, 2,893 attempts, 427.9 hours |
| typical attempt | 7.4 min median. 20-min soft limit, 30-min hard cut |
| sessions | 90 min, about 9 games each, $115–140 plus $5 per game solved |
| official board at release (semi-private) | Opus 4.6 0.50%, Gemini 3.1 Pro 0.40%, GPT-5.4 0.20%, Grok 4.20 0.10% |
| 2025 preview competition | 18-Jul to 19-Aug-2025, 3 public and 3 hidden games |
| ARC Prize 2026 | $2M across two Kaggle tracks (ARC-AGI-3 and ARC-AGI-2). Winners must open source |

## 4. What the paper does not tell us

- Kaggle's action limit, time limit, or which toolkit version Kaggle scores with.
- Any per-game human baselines. The paper has none, only worked examples for `re86` and `ls20`.
- Anything after April 2026. The GPT-6 Astra figures in `how-this-feeds-kaggle.md` come from
  arcprize.org in September and are not contradicted by the paper, which predates them.

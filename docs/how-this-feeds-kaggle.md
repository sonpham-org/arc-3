# How this whole thing feeds Kaggle

**Author:** Mark Barney / Claude Opus 5
**Date:** 05-September-2026
**Purpose:** The plain-language answer to "what are we actually doing and why does it
matter for the competition." Written because every new agent — and every new human —
rebuilds the same chain of wrong assumptions from scratch. Read this before you touch a
game, a harness, or a score.

---

## The one-paragraph version

ARC-AGI-3 has 135 games. We can see 25 of them. Those 25 are a **tutorial** — already
solved, and deliberately built to be unlike the real test. Kaggle scores us against games
nobody outside ARC has ever seen. So we write our own games as a *guess* at what's behind
that door, let our agent practice on them, and train it on the levels it wins. The whole
project is an attempt to build a practice set for an exam we are not allowed to look at.

---

## 1. The three sets, and which one pays

| set | size | who has seen it | what it's for |
|---|---:|---|---|
| **Public / demonstration** | 25 | everyone | the tutorial |
| **Semi-private** | 55 | frontier labs, via API | the public leaderboard |
| **Fully private** | 55 | ARC only | the competition |

Source: ARC-AGI-3 Technical Report §3.6 and §5.

**The public 25 are not a training resource.** ARC says so directly. They are
intentionally easier for both humans and AI, weighted toward clarity and fun, and they
**deliberately do not represent the mechanics of the private set** — specifically to stop
teams overfitting to them. ARC-AGI-2 was roughly 10:1 public-to-private. ARC-AGI-3 inverts
that on purpose.

### The two numbers that frame everything

| | score |
|---|---|
| frontier models on the **public 25**, with a domain harness | **~99–100%** |
| frontier models on the **semi-private**, at release | **0.10 – 0.50%** |

The tutorial is finished. The real thing was, until very recently, untouched. Every bit of
value in this project lives in that gap.

### September 2026: the gap started closing

OpenAI's GPT-6 ("Astra") posted **62.7%** on the semi-private set with the standard
harness, and **99.9%** with a Provider Adapter harness. Same model, ~37 points apart.

**That gap is the single most important fact on this page for us.** It is direct evidence
that harness engineering is worth more than model choice on this benchmark. That is
precisely the lane this project is in.

---

## 2. The trap

> Imitating the public 25 is not a conservative choice. It is the specific failure the
> report designed the public set to expose.

If our synthetic games look and play like the demo set, we have built a practice exam for
the test that is already passed.

**The line to hold:**

- **Match ARC exactly on conventions** — action space, how a run ends, how scoring works,
  frame format, the 16-colour palette, 64×64 grid.
- **Diverge deliberately on mechanics** — what the player has to work out.

This is also why measuring our games *against* the official 25 is a mistake unless you are
very clear about which of the two you are measuring. "Our games don't look like the
official set" is not automatically a defect. It may be the goal.

---

## 3. What the hidden set is supposed to be

ARC's design brief for the private games — this is our build spec, in their words:

1. Significantly harder for humans *and* AI.
2. Deliberately out-of-distribution relative to the public set.
3. Broader, more diverse mechanics, with **limited overlap** with public-set mechanics.
4. **Deeper compositional reasoning.**
5. Still entirely solvable by humans.

### Human calibration is the inclusion gate

Every private environment was attempted by 10 people. It only qualified if at least **two
independently solved it completely, on first sight** — all levels, no prior exposure. Many
were solved by six or more.

### The action budget is derived from humans

**Agents are evaluated at 5× the human median action count per level.** That is what
`baseline_actions` is in the official game metadata — it is the agent's budget, not
decoration.

**A game with no human median cannot be evaluated the way ARC evaluates.** Our synthetic
games do not currently carry this number. That is a real gap between "a game we made" and
"a game measurable on ARC's terms."

---

## 4. The actual pipeline, end to end

```
   we author synthetic games          (autoresearch-arena/arc3games/gNNN_*.py)
              |
              |  packaged, one standalone file per game
              v
   published + served                 (arc-3/docs/static/games/, arc-explainer)
              |
              |  the duck harness plays them
              v
   run artifacts / trajectories       (ARC3-Inference, logs/)
              |
              |  rejection sampling: KEEP ONLY SOLVED LEVELS
              v
   SFT training corpus                (ARC3-Inference/distill/extract_sft.py)
              |
              |  fine-tune the model on its own wins
              v
   better model  ->  Kaggle notebook  ->  score on games nobody has seen
```

### The step that governs game design

`distill/extract_sft.py` keeps only turns where `level <= levels_completed`. A game
contributes training data **only for the levels our model actually beats.**

That single rule is why difficulty grading matters more than polish:

- **Too hard** → the model never wins → the game produces **nothing**. Wasted build.
- **Too easy** → it wins without reasoning → the data teaches nothing.
- **Too samey** → it learns one trick instead of a general skill.
- **Too much like the demo set** → it gets good at the exam that's already passed.

---

## 5. Where the loop is NOT closed

**Nothing in this pipeline currently measures whether polishing a game moves the Kaggle
score.**

What we do measure:

- Are the games different from each other? (`differentiate.py` — code shape, palette,
  geometry, cell scale, topology, mechanic)
- Do they load, and can they be won? (`verify_all.py`, `legibility_gate.py`, `probe_one.py`)

Both are real and both matter. Neither asks the only question that pays: **did improving
that game make the model better at unseen games?**

Until something connects a game-set change to a harness score, the glow-up and
differentiation campaigns are craft work on a plausible theory. Good craft on a good
theory — but not yet a measured contribution to the score.

**If you only fix one thing in this pipeline, fix this.**

---

## 6. Where the score actually comes from today

Harness variants, scored **ex-`ft09`** (that one game swings the all-25 average by ±1.0,
so it is always excluded):

| config | ex-`ft09` |
|---|---:|
| `ffa7gn` — frame-full + ACTION7 + animation + goal-guidance + no-impact band | **1.62** |
| `frame-full` alone | 1.44 |
| `baseline-v12` (frozen reference) | 1.21 |
| `ffa7g` — same stack, no no-impact band (ablation control) | 1.05 |

Every one of those gains came from **harness work, not from the game set.** Which is
consistent with the GPT-6 Astra result above: on this benchmark, the harness is the lever.

---

## 7. What to tell someone who asks how a two-person team is placing top-five

The honest version, and it holds up:

1. **The benchmark rewards harness engineering more than model scale.** GPT-6 Astra scored
   62.7% and 99.9% on the same weights, with different harnesses. A small team that builds
   a better harness competes directly with far larger ones.
2. **We build our own practice data.** Nobody can train on the hidden set, so everyone is
   guessing at it. Guessing well is a design problem, not a compute problem.
3. **We train the model on its own successes.** Rejection sampling on solved levels — no
   human labelling, no external dataset.
4. **We measure carefully.** Frozen baseline, ex-`ft09` scoring, ablation controls,
   mutation-tested verifiers. Most of the score gains above are separated from each other
   by a control run.

None of that requires a lab. It requires knowing where the leverage is.

---

## 8. A caution from ARC Prize 2025

The 5th-place ARC Prize 2025 writeup is worth reading as a warning about small evaluation
sets. That competitor forked a strong public baseline and changed **the random seed**,
moving from 344th on the public leaderboard to 5th on the private one. Their observed score
range from seed alone was 3.33%–6.67% — a 2× swing on 120 tasks.

The lesson is not "tune seeds." It is: **when the evaluation set is small, rank contains a
lot of noise.** Replicate anything promising 2–3× before believing it. This is exactly why
`harnesses/README.md` requires replication and scores ex-`ft09`.

---

## Sources

- [ARC-AGI-3 overview](https://arcprize.org/arc-agi/3/)
- [ARC Prize 2026 — ARC-AGI-3](https://arcprize.org/competitions/2026/arc-agi-3)
- [GPT-6 Astra results](https://arcprize.org/results/openai-gpt-6-astra)
- [ARC Prize 2025 5th-place writeup](https://www.kaggle.com/competitions/arc-prize-2025/writeups/arc-prize-2025-competition-writeup-5th-place)
- ARC-AGI-3 Technical Report §3.6, §5 — via
  `autoresearch-arena/arc3games/AUDIT_2026-08-31.md`

<!--
Author: Claude Opus 5 (Bubba)
Date: 13-September-2026
PURPOSE: Record and analyse the human WIN replay of bp35 (guid c935ca1b, 9/9 levels,
score 79.34) supplied by the Boss, against our arm-C runs of the same game. Establishes
that ACTION7 (undo) is used 35 times by the human and zero times by us, and that level 9
is a 530-action grind that even a winning human nearly loses on score.
SRP/DRY check: Pass — new artifact (human replay guid c935ca1b). The g50t human replay is
covered separately by 2026-09-13-g50t-human-win-vs-our-zero.md; nothing is restated here.
-->

# bp35 — a human WIN, and the undo we never press

Replay: <https://arcprize.org/replay/c935ca1b-dfee-4be1-9574-bf4cc80c5b89>
Pulled via the two undocumented endpoints (`/api/sessions/<guid>`,
`/api/recordings/bp35-0a0ad940/<guid>`). 138 MB NDJSON, 1,030 rows.
Human-tagged, opened 2026-09-14 00:46 UTC, published 02:40 UTC.

## Result

**WIN, 9 of 9 levels, 1,024 actions, 13 resets, score 79.34.**

| Level | Actions | Baseline | Level score (of 115) |
|---|---|---|---|
| 1 | 17 | 21 | 115 |
| 2 | 42 | 48 | 115 |
| 3 | 48 | 44 | 84.03 |
| 4 | 41 | 38 | 85.90 |
| 5 | 31 | 33 | 113.32 |
| 6 | 85 | 87 | 104.76 |
| 7 | 88 | 86 | 95.51 |
| 8 | 142 | 131 | 85.11 |
| 9 | **530** | **163** | **9.46** |

Levels 1–8 track baseline within about 10%. Level 9 runs **3.25× baseline** and keeps
9.46 of 115 — it costs more actions than the other eight levels combined (530 of 1,024)
and returns almost nothing. Same shape as g50t, where level 5 was the only level played
over baseline and the only level that lost its credit. **A human win is eight levels of
competence plus one level of grinding.**

## The action set

bp35 exposes exactly four actions at every step: `[3, 4, 6, 7]`. No ACTION1/2/5.
ACTION3 and ACTION4 are the movement keys, ACTION6 is the click, and **ACTION7 is the
undo** — bp35 sets `STORES_UNDO = True`, the same flag noted for lf52 in
`2026-09-12-bottom-seven-and-the-moving-frame.md`.

Human per-level usage:

| Level | A3 | A4 | A6 (click) | A7 (undo) | resets |
|---|---|---|---|---|---|
| 1 | 5 | 6 | 5 | 5 | 1 |
| 2 | 10 | 12 | 20 | 0 | 0 |
| 3 | 13 | 18 | 16 | 0 | 1 |
| 4 | 8 | 16 | 12 | 3 | 2 |
| 5 | 9 | 12 | 10 | 0 | 0 |
| 6 | 32 | 31 | 20 | 1 | 1 |
| 7 | 13 | 22 | 38 | 14 | 1 |
| 8 | 9 | 24 | 94 | 12 | 3 |
| 9 | 45 | 53 | 425 | 2 | 5 |

Undo is **35 of 1,024 actions, 3.4%** — sparse, like ACTION5 in g50t, but present from
the first level and concentrated exactly where the levels get hard (7 and 8).

Level 9 is 425 clicks out of 530 actions. Whatever level 9 is, it is a click grind, and
the human stopped reasoning and started brute-forcing.

## Against our runs

Arm C (job 4, mechanics-possibility), all four passes of bp35, action tallies out of
`artifacts/bp35-0a0ad940_p*_events.jsonl`:

| pass | max level | actions | RIGHT | LEFT | MOUSE | UNDO | RESET |
|---|---|---|---|---|---|---|---|
| p0 | 2 | 64 | 24 | 14 | 24 | **0** | 2 |
| p1 | 1 | 11 | 5 | 1 | 4 | **0** | 1 |
| p2 | 1 | 57 | 19 | 16 | 20 | **0** | 2 |
| p3 | 1 | 34 | 17 | 7 | 9 | **0** | 1 |

**ACTION7 is offered on every single step and pressed zero times in 166 actions.**
That is the third game now — sk48, lf52, bp35 — where an undo sits in the legal action
set for the whole run and no pass ever tries it. The human reached for it on level 1.

The other number worth holding: the human cleared level 1 in **17 actions**. Our p1 spent
11 actions on the entire run and stopped; p2 spent 57 and never left level 1. It is not a
budget problem. Level 1 of bp35 is cheap for someone who knows what the verbs are.

## What this does and does not support

- It **supports** arm C's premise: naming what is possible is the intervention, and the
  unnamed verb here is undo. It does not name undo specifically — arm C says "what you
  control may change," not "ACTION7 may be undo."
- It **does not** settle whether naming the undo outright helps. That is the held idea 2
  from the original arm list, still unrun.
- Level 9's 530-action grind is a caution for the arm-F commit-prompt hypothesis: on at
  least one level of one game, the winning human strategy *is* undirected volume.

---

## CORRECTION, 14-September-2026

The claim above that ACTION7 is "pressed zero times" is wrong in its cause. The agent
**does** attempt it — 22 call-shaped attempts across 12 bp35 passes — and every attempt is
refused with `Unknown action at index 1: 'ACTION7'`, because `action_names.py` never maps
ACTION7 to an engine action while still listing it in `valid_actions`. The committed-action
count of zero is the harness refusing the call, not the agent declining to try.

See `2026-09-14-action7-is-unexecutable.md`.

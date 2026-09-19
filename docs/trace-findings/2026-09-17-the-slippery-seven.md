<!--
Author: Claude Opus 5 (Bubba)
Date: 17-September-2026
PURPOSE: Names and characterises the seven games that scored exactly zero in every pass of the
27B mass-data run (dc22, g50t, m0r0, sc25, sk48, tn36, tr87), and answers why three of them
score on the Kaggle arms. Holds the model-swap comparison (Flash-Next vs 27B on the same run
catalog at matched clock), the per-arm Kaggle numbers, the local action-shape evidence, a
correction to an earlier reset count, and the list of which of the seven still have no
mechanic page.
Updated 19-Sep-2026 (Claude Opus 5): §7's documentation hole is marked closed; the three
missing pages were written the same day in 2026-09-17-dc22-m0r0-tr87-what-they-are.md.
SRP/DRY check: Pass — this is the 27B-specific zero set, which is NOT the Flash-Next "bottom
seven" of 2026-09-12-bottom-seven-and-the-moving-frame.md (only three games overlap). Mechanic
descriptions for sk48, g50t and tn36 are cited to 2026-09-12-bottom-seven-what-each-one-is.md
and sc25 to 2026-09-12-sc25-sigil-caster-six-runs.md rather than restated.
-->

# The slippery seven

**`dc22-fdcac232`, `g50t-5849a774`, `m0r0-492f87ba`, `sc25-635fd71a`, `sk48-d8078629`,
`tn36-ef4dde99`, `tr87-cd924810`.**

These are the seven of the official 25 that scored **0.00 in all four passes** of
`20260916_102724_qwen38-27b-massdata-25g-4p` — 28 attempts, zero levels cleared, zero points.
That run was `model=qwen38-27b-nvfp4`, `duck-harness`, 25 games × 4 passes, `concurrent_jobs=25`,
`max_runtime_minutes_per_game=230`, `max_actions=null`, `environments_dir=
/home/son/flash-next-work/environment_files-11p44`. Every one of the 100 runs ended `gave_up`
on the per-game clock; the batch won 0 of 100.

## 1. They are not the same seven as the September-12 "bottom seven"

`2026-09-12-bottom-seven-and-the-moving-frame.md` names **sk48, bp35, ls20, g50t, lf52, wa30,
tn36** — the seven weakest by average score across 166 `RadixArk/Qwen3.8-Flash-Next-NVFP4` runs.
Only **sk48, g50t and tn36** are on both lists. Two things differ: the criterion (weakest mean
vs strictly zero in every pass) and, decisively, the model. Do not treat the two lists as the
same finding, and do not update one from the other.

## 2. Per-pass results, 27B mass-data run

Score is the harness's own `final_score`; actions is the sum of `actions_per_level`.

| game | levels | p0 | p1 | p2 | p3 | actions p0–p3 |
|---|---|---|---|---|---|---|
| `dc22-fdcac232` | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 86 / 31 / 41 / 69 |
| `g50t-5849a774` | 7 | 0.00 | 0.00 | 0.00 | 0.00 | 19 / 31 / 13 / 16 |
| `m0r0-492f87ba` | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 36 / 32 / 41 / 24 |
| `sc25-635fd71a` | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 25 / 91 / 40 / 38 |
| `sk48-d8078629` | 8 | 0.00 | 0.00 | 0.00 | 0.00 | 24 / 11 / 74 / 40 |
| `tn36-ef4dde99` | 7 | 0.00 | 0.00 | 0.00 | 0.00 | 131 / 74 / 52 / 60 |
| `tr87-cd924810` | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 28 / 126 / 87 / 26 |

Two failure shapes, same score. `g50t` spends 13–31 actions and stops; `tn36` and `tr87` spend
126–131 and get nothing. Cheap quit and expensive flail are not the same bug.

## 3. Why they score on Kaggle: the Kaggle arms run a different model

**This is the answer.** The eleven Kaggle prompt-arm notebooks pin
`RadixArk/Qwen3.8-Flash-Next-NVFP4` (`arc3-job1-control.ipynb`, and every sibling). The local
mass-data run is `unsloth/Qwen3.8-27B-NVFP4`. Different checkpoint. The arm labels are not what
moved these games.

The site run catalog (`/data/runs-index.json`, 368 runs) carries both models over the same 25
games, and their **median run duration is identical at 2.21 h** with median 25 games per run —
so this is a model comparison at matched clock, not a throughput comparison.

| game | Flash-Next (166 runs) mean | % zero | 27B (68 runs) mean | % zero | mean actions FN → 27B |
|---|---|---|---|---|---|
| `tr87` | **13.46** | 15% | **0.60** | 85% | 127 → 105 |
| `m0r0` | 9.82 | 8% | 1.22 | 40% | 126 → 150 |
| `sc25` | 9.37 | 24% | 5.87 | 21% | 226 → 159 |
| `dc22` | 9.10 | 12% | 1.41 | 68% | 185 → 189 |
| `tn36` | 4.18 | 13% | 2.02 | 50% | 177 → **307** |
| `g50t` | 2.45 | 53% | 0.37 | 90% | 128 → 74 |
| `sk48` | **0.39** | **84%** | **0.29** | **90%** | 145 → 85 |

Read the last column before the middle ones: on `dc22`, `m0r0` and `tr87` the 27B takes **as
many or more actions** as Flash-Next and still scores near zero, and on `tn36` it takes 73%
*more* actions for less than half the score. Whatever is wrong is not that the 27B ran out of
turns.

**So the seven split three ways:**

1. **`sk48` is hard for everything** — 0.39 / 0.29, 84% / 90% zero. Model-independent. It is
   also the one game the Boss himself has never completed (`2026-09-17-boss-scorecard-inventory.md`:
   GAME_OVER, 6 levels, 889 actions, 11-Sep — his closest miss).
2. **`g50t` is hard for both, worse on the 27B** — 53% → 90% zero. A known-difficult game that
   the smaller model turns into a wall.
3. **`dc22`, `m0r0`, `sc25`, `tn36`, `tr87` are a 27B-specific collapse.** Flash-Next clears
   levels on all five routinely. `tr87` is the extreme: Flash-Next means 13.46 with a best run
   of 71.43 and 5 levels cleared; the 27B means 0.60.

`dc22`, `g50t` and `m0r0` each have a **human WIN** from the Boss in September, so none of the
three is unsolvable in principle.

## 4. Only four of the seven ever ran on Kaggle at all

The 8-job comparable arm set is seven games: `bp35, g50t, lf52, ls20, sk48, tn36, wa30`. The
disjoint job3/job5 set is a different seven and contains `sc25`. **`dc22`, `m0r0` and `tr87`
were never run on Kaggle.** Per-arm means over 4 passes, from each job's own `score.json`:

| arm | g50t | sk48 | tn36 | sc25 |
|---|---|---|---|---|
| job1 A-control | 0.00 | 0.14 | 2.08 | — |
| job2 B-sparse-deletion | 1.05 | 0.00 | 2.68 | — |
| job4 C-mechanics | 0.63 | 1.08 | 2.41 | — |
| job5 A-control (disjoint set) | — | — | — | 1.67 |
| job6 D-glyph-consonants | 0.00 | 0.00 | 0.75 | — |
| job7 E-image-first-turn | 0.00 | 0.00 | 1.53 | — |
| job8 F-commit-prompt | 0.00 | 0.69 | 0.00 | — |
| job9 G-visual-first | **2.16** | 0.69 | 0.00 | — |
| job10 H-action7-roundtrip | 0.00 | 0.16 | 0.00 | — |

`tn36` scores **2.08 on the Kaggle control arm** — no prompt change needed. `sc25` scores 1.67
on its set's control, carried entirely by one pass at 6.66 and zero on the other three. `g50t`
is zero on control and nonzero on three of eight arms. Given a mean per-game pass-level SD of
0.90 (`2026-09-15-arc3-kaggle-arm-matrix.md`), **no single arm's advantage on these games is
separable from noise.** The model is separable; the arms are not.

## 5. What the 27B actually does on them

Action histogram over all four passes, from `artifacts/*_events.jsonl` (`action_name`):

| game | total actions | shape |
|---|---|---|
| `tn36` | 317 | **314 ACTION6**, 3 RESET — nothing but clicks |
| `sc25` | 194 | 143 ACTION6, then 21/10/10/9 spread, 1 RESET |
| `tr87` | 267 | 168 ACTION1, 70 ACTION3 — two keys, repeated |
| `dc22` | 227 | 96 ACTION6, 43/39/32/17 — the most varied of the seven |
| `sk48` | 149 | 53 ACTION4, 49 ACTION3, 26 ACTION1 |
| `m0r0` | 133 | 44 ACTION1, 27/26/18/12/6 |
| `g50t` | 79 | 42 ACTION2, 19 ACTION4, rest single digits |

`tn36` is the clearest single artefact in the run: 99% of its actions are one action. Its
mechanic is that **the controls are an encoded number**
(`2026-09-12-bottom-seven-what-each-one-is.md`), so a model that has not decoded the mapping
has nothing to do but click — which is exactly what the histogram shows.

**`ACTION7` does not appear once in the entire 100-run batch.** That is consistent with
`2026-09-14-action7-is-unexecutable.md` and with the Kaggle job10 finding that ACTION7 *does*
execute on the Kaggle harness path. Not verified here: whether these seven games expose ACTION7
in their action lists at all under the a108 snapshot.

## 6. Correction — the reset count

An earlier verbal report of this run said "2 resets in the whole 100-run batch, both on `sp80`,
zero on the seven." **That count was wrong.** Counting `action_name == "RESET"` across
`artifacts/*_events.jsonl`:

**17 resets total — `sp80` 9, `tu93` 4, `tn36` 3, `sc25` 1.** Four of them are on the seven.

The *mechanism* claim is unchanged and still holds **for this run**, and it is now cited to the
run's own vendored snapshot rather than to the working tree:
`runs/20260916_102724_.../src/ARC3-Inference/inference/framework/solver.py:119`, inside
`_engine_action_names`, does `if name == "RESET": continue` — so RESET is skipped when the action
list offered to the model is built, and it appears in no prompt text. The harness fires reset
itself on game over. RESET in `action_name` is that harness reset being logged. Wrong number,
same mechanism.

**Do not carry the line number forward.** Current `main` has replaced the unconditional skip with
a *guard* (`solver.py:164-278`, `_RESET_MIN_ACTION_GAP = 20`, an `include_reset` flag at `:179`),
landed with the jobs 11/12 reset work — see `2026-09-16-jobs-11-12-reset-guard-result.md`. Any
run after that merge has different reset semantics from the one described here.

## 7. The documentation hole

> **Closed 17-Sep-2026.** The three missing mechanic pages were written the same day:
> `2026-09-17-dc22-m0r0-tr87-what-they-are.md` covers dc22, m0r0 and tr87, cited to file:line in
> each game's source. All seven now have a mechanic write-up. The ARC Explainer game pages
> (`shared/arc3Games/<id>.ts` in arc-explainer) also carry each game's rules level by level.
> The text below is kept as it was written.

Of the seven, these already have a mechanic write-up and should be read before any new work:

- `sk48` — `2026-09-11-sk48-mental-models.md`, `-prompt-vs-ground-truth.md`,
  `-prompt-fights-the-game.md`, `-zero-vs-eight.md`, plus the one-paragraph mechanic in
  `2026-09-12-bottom-seven-what-each-one-is.md`
- `g50t` — `2026-09-13-g50t-human-win-vs-our-zero.md`, `2026-09-13-g50t-action5-correction.md`
- `tn36` — the encoded-controls paragraph in `2026-09-12-bottom-seven-what-each-one-is.md`
- `sc25` — `2026-09-12-sc25-sigil-caster-six-runs.md`

**`dc22`, `m0r0` and `tr87` have no mechanic page.** They appear only in aggregate tables.
`tr87` is the largest unexplained model gap in the whole 25 and is the least documented game on
this list. Sources are in the repo: `docs/static/games/src/dc22-fdcac232/dc22.py` (10,875
lines), `m0r0-492f87ba/m0r0.py` (908), `tr87-cd924810/tr87.py` (1,102). That is the next
write-up, and it needs no GPU.

## 8. The experiment this points at

Not "run the seven again." The single highest-information cheap run is **the seven, 27B,
concurrency dropped from 25, compact-reasoning arm on**, against the Flash-Next numbers in §3 as
the target. Rationale: in 49 attempts across four separate 27B runs the only nonzero any of the
seven ever produced was `m0r0` 0.00 → **3.31** under the compact arm
(`2026-09-17-arc3-style-experiment.md`), the arm that bought +43% actions for the same tokens.
One game, one pass, temperature 1.0 — that is a hypothesis, not a result, and it is the cheapest
one on the board. Seven games instead of 25 is roughly a four-hour night.

## 9. Not verified

1. Whether the 166 Flash-Next runs and the 68 27B runs in `runs-index.json` used the same
   `concurrent_jobs`. Matched median duration (2.21 h) and matched game count are evidence for
   comparable clock; they are not the config field itself, which the index does not carry.
2. Whether every run in those two populations used the same `environment_files` build. The game
   ID hashes match across local, Kaggle and catalog, which is strong but is not a build check.
3. Whether the seven expose `ACTION7` in their action lists at all.
4. The Kaggle numbers in §4 are from the nine job outputs pulled to disk on 14-Sep; job3,
   job11 and job12 were not re-read for this doc.
5. `sc25` shows n=53 runs in the 27B population against n=68 for the other six — not chased.
6. No per-level timing analysis: whether the 27B's actions are being spent on level 1 or
   scattered was not measured here.
7. No claim is made about *why* the 27B collapses on `dc22`/`m0r0`/`tr87` specifically. §3
   establishes that it does; the mechanism is open, and §7 is the prerequisite for guessing.

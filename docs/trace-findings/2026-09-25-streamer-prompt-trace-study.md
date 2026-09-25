<!--
Author: Claude Opus 5.5 (Bubba)
Date: 25-September-2026
PURPOSE: Trace study for Son of why the "streamer" prompt arm (arm E: the Boss's full prompt + the two
answer-key lines + the Gen Z streamer opener, on Son's 7.36 Kaggle harness, Flash-Next NVFP4, RTX PRO 6000)
scored a mean of 15.05 over the 25 public ARC-3 games in one Kaggle pass, against the 7.36 we submit.
Decomposes the score game by game, measures how the model's reasoning differs from Son's unchanged prompt
on the same games, rules confounds in or out (time, game set, single pass, answer-key lines vs streamer
opener, hardware), and gives a verdict. Every number is recomputed from the runs' own files: Kaggle
benchmark.json and transcripts on the Mini, and Son's GCP run-overview.json / run-timeline.json read
(read-only) from the arc3-viewer Railway volume. Held-out games are counted, never quoted.
SRP/DRY check: Pass — the run itself is recorded in docs/2026-09-24-kaggle-streamer-25.md and the arms in
docs/2026-09-23-kaggle-736-prompt-arms.md, 2026-09-24-kaggle-slippery7-round2.md,
2026-09-24-kaggle-bottom7-arms*.md, 2026-09-24-kaggle-attribution-arms.md; this file only analyses them.
Scripts: ~/bubba-workspace/arc3-kaggle/trace-study/ (pool.py, compare.py, gcp_compare.py, tmetrics.py).
-->

# Why did the streamer prompt "nearly double" the score? A trace study — 25-Sep-2026

Practice data only. Nothing here was submitted. Held-out games (Axis Reflectors, Reach Emblems, Sequence
Belt, Sucking Up, Toggle Runes, Trail Unwind, Volume Control) are counted in totals and never quoted.

## Headline and verdict

**It didn't double anything. The 15.05 and the 7.36 are measured on different game sets.** 7.36 is our
Kaggle leaderboard score on the competition's hidden games. 15.05 is the mean over the 25 *public* games,
played offline in a practice notebook. The public games are much easier for this harness, and ARC built
them to be unlike the hidden set.

The fair baseline is Son's prompt on the same 25 public games at the same per-game time. That exists. The
7.36 submission's gameplay comes from Son's GCP arm `g4run-cap-return132-w7-20260916-c8fb225fae` (per
`CONFIG_FLAGS.json` in the Kaggle bundle: "Gameplay source is the verified GCP cap_return arm … mean
15.95 … two byte-identical replicates scored 13.58 / 15.65"). Recomputed from the three runs'
`run-overview.json` on the viewer volume:

| Run (all 25 public games, one pass, Flash-Next) | Mean score | Levels |
|---|---|---|
| Son's prompt, GCP `cap-return132 …c8fb225fae` (16-Sep) | 15.95 | 56 |
| Son's prompt, GCP `clean-return-repeat132 …9677f73fbf` (17-Sep) | 13.58 | 54 |
| Son's prompt, GCP `clean-return-repeat132 …0cfc444a85` (18-Sep) | 15.65 | 60 |
| **Son's prompt, average of the three** | **15.06** | 56.7 |
| **Streamer arm, Kaggle, one pass** (24-Sep) | **15.05** | 54 |

Take out Functional Tiles and the streamer arm is *behind*: 11.59 over the other 24 games, against 14.17
for the average of Son's three runs.

**Verdict.**
- **None of the jump from 7.36 to 15 comes from the prompt.** It comes from switching the scoreboard from
  hidden games to public games. High confidence: this is arithmetic on raw files.
- **Over all 25 public games, the streamer prompt scores the same as Son's prompt.** Moderate
  confidence. It is one Kaggle pass against three GCP runs, and GCP is not the Kaggle card. On the ten
  games where both prompts have Kaggle runs, Kaggle and GCP agree for Son's prompt (8.58 against 8.11),
  so the GCP runs are a fair stand-in.
- **About a quarter of the 15.05 is a single game: Functional Tiles.** The first outright win by any arm
  (6 of 6 levels, score 97.98) gives 3.9 points of the mean. It happened once and has not been repeated,
  and it came from the model writing a solver in Python, which is not what the streamer prompt asks for.
  More on this below.
- **The prompt does change how the model behaves, and the opener is the cause.** It narrates to "chat"
  in about half of its turns, against almost none with Son's prompt. It also takes slightly bigger batches
  of actions per turn and spends fewer tokens per action. None of these changes shows up as levels outside
  one pass's spread.
- **The attribution idea did not come up.** After a level clear, the streamer arm names a cause about as
  often as Son's prompt does.

## (a) Where the 15.05 comes from

Harness score per game (`taaf/game.py::_compute_final_score`): each cleared level scores
`min(115, (baseline/actions)² × 100)`. Level *k* is weighted *k*, and the total is capped by the weights of
the levels cleared. Deep levels dominate. On a 6-level game, clearing only level 1 is worth at most 4.76,
while clearing all six can reach about 100. Efficiency is squared, so a level cleared in twice the
baseline actions keeps a quarter of its value.

Top contributors to the streamer arm's 25-game mean (sum of scores = 376.3):

| Game | Levels | Score | Share of the mean |
|---|---|---|---|
| Functional Tiles | 6/6, won | 97.98 | 3.92 points |
| Loop and Pull | 5/8 | 41.02 | 1.64 |
| Toggle Runes (held out) | 3/6 | 28.57 | 1.14 |
| Axis Reflectors (held out) | 4/8 | 27.78 | 1.11 |
| Reach Emblems (held out) | 4/8 | 27.78 | 1.11 |
| Deck Control | 3/6 | 24.52 | 0.98 |
| Volume Control (held out) | 3/7 | 21.43 | 0.86 |
| the other 18 games | | 107.2 total | 4.29 |

Functional Tiles alone is 26% of the mean. With 4 levels instead of 6 (its level at the time Son's GCP
runs gave that game; see (c)) it would score 37.74, and the 25-game mean would be 12.64.

## Per-game table

The streamer arm is one Kaggle pass. "Son GCP" is the three all-25 runs above: levels and score per run.
"Son Kaggle" is every full-time Kaggle pass of Son's unchanged prompt (arm A: 23-Sep two passes on seven
games; bottom-seven rounds one and two, five passes). A dash means there is no run.

| Game | Held out | Streamer levels | Streamer score | Son GCP levels (3 runs) | Son GCP scores | Son Kaggle levels (per pass) | Son Kaggle mean score |
|---|---|---|---|---|---|---|---|
| Functional Tiles | | 6/6 won | 97.98 | 4, 2, 4 | 47.3, 14.3, 47.6 | 4, 5 | 58.91 |
| Loop and Pull | | 5/8 | 41.02 | 4, 5, 5 | 27.8, 41.7, 41.7 | — | — |
| Toggle Runes | yes | 3/6 | 28.57 | 5, 4, 2 | 71.4, 47.6, 14.3 | — | — |
| Axis Reflectors | yes | 4/8 | 27.78 | 1, 2, 5 | 2.8, 5.9, 41.7 | — | — |
| Reach Emblems | yes | 4/8 | 27.78 | 4, 4, 5 | 27.8, 27.8, 41.7 | — | — |
| Deck Control | | 3/6 | 24.52 | 2, 3, 2 | 11.1, 28.6, 13.3 | — | — |
| Volume Control | yes | 3/7 | 21.43 | 4, 3, 3 | 35.7, 21.0, 14.7 | — | — |
| Sliding Indicator | | 3/8 | 16.67 | 2, 2, 3 | 7.9, 8.3, 16.7 | 1, 2 | 4.65 |
| Reaching Lurch | | 2/6 | 14.29 | 1, 3, 3 | 4.8, 28.6, 28.6 | — | — |
| Compass Dye | | 2/6 | 14.29 | 0, 2, 1 | 0.0, 5.8, 4.8 | — | — |
| Sucking Up | yes | 3/9 | 13.33 | 4, 3, 2 | 22.2, 13.3, 4.6 | — | — |
| Trail Unwind | yes | 3/9 | 11.05 | 2, 3, 2 | 4.4, 12.0, 4.4 | — | — |
| Kick Away | | 2/7 | 10.71 | 3, 2, 2 | 18.6, 10.7, 10.7 | — | — |
| Coded Notches | | 1/6 | 4.76 | 1, 1, 2 | 4.8, 4.8, 14.3 | — | — |
| Streaming Purple | | 1/6 | 4.76 | 1, 1, 1 | 4.8, 4.8, 4.8 | 1, 1 | 1.68 |
| Locksmith | | 1/7 | 3.57 | 1, 1, 2 | 3.6, 3.6, 8.1 | 2, 1, 1, 1, 1, 1, 2 | 5.04 |
| Ghost Twin | | 1/7 | 3.57 | 1, 1, 1 | 3.6, 3.6, 3.6 | 1, 2, 1, 1, 1 | 4.44 |
| Sequence Belt | yes | 1/8 | 2.78 | 6, 3, 5 | 55.6, 7.3, 41.7 | — | — |
| Buoyant Pontoons | | 2/9 | 2.31 | 1, 1, 1 | 1.9, 1.0, 1.9 | 1, 1, 1, 1, 1, 1, 1 | 1.35 |
| Warehouse Associates | | 1/9 | 2.22 | 3, 2, 3 | 13.3, 6.7, 13.3 | 1, 2, 1, 1, 2 | 4.00 |
| Leapfrog | | 1/10 | 1.82 | 2, 1, 1 | 4.7, 1.0, 1.8 | 1, 1, 2, 1, 1 | 2.48 |
| Toggle Navigator | | 1/7 | 0.75 | 2, 1, 1 | 10.7, 3.6, 1.2 | 0, 0, 1, 2, 1, 1, 1 | 3.26 |
| Sigil Caster | | 1/6 | 0.21 | 0, 4, 2 | 0.0, 37.8, 1.8 | — | — |
| Skewer Kebabs | | 0/8 | 0.00 | 0, 0, 0 | 0, 0, 0 | 0 ×7 | 0.00 |
| Mirror Rendezvous | | 0/6 | 0.00 | 2, 0, 2 | 14.3, 0.0, 14.3 | — | — |
| **Mean / levels** | | **54** | **15.05** | 56, 54, 60 | 15.95, 13.58, 15.65 | | |

Where the streamer arm beats every run of Son's prompt: **Functional Tiles** (the win), **Buoyant
Pontoons** (a second level; Son's prompt stopped at one level in all ten runs on record, seven on Kaggle
and three on GCP), Compass Dye on score (2 levels, tied with Son's best run on levels). Sliding Indicator
and Trail Unwind tie Son's best run.

Where the streamer arm falls below all three of Son's GCP runs: **Sequence Belt** (1 against 3 to 6),
Warehouse Associates (1 against 2 to 3; Son's Kaggle passes also had 1–2), Toggle Navigator on score
(0.75 against 1.2–10.7: the same one level but more actions). Mirror Rendezvous: 0, where Son's prompt
got 2 in two of three GCP runs and the streamer arm itself cleared 2 in each of its three slippery-seven
passes.

Level totals: streamer 54, Son's prompt 54 to 60.

## (b) What is different in the reasoning, same games

Here the comparison is Kaggle against Kaggle: same card, model and harness. Son's unchanged prompt (arm
A, 49 full-time runs) is set against the streamer pass on the ten games both played at full time
(Skewer Kebabs, Toggle Navigator, Buoyant Pontoons, Warehouse Associates, Leapfrog, Streaming Purple,
Sliding Indicator, Locksmith, Functional Tiles, Ghost Twin). To isolate the opener: arm D (answer key,
no streamer) against arm E (answer key + streamer) on the slippery seven, three passes each, same
settings. Counts come from `trace-study/tmetrics.py` over every transcript. A "call" is one model response.

| Per run, averages | Son's prompt (A), 10 games | Streamer (E25), same 10 | Answer key, no streamer (D), slippery 7 | Answer key + streamer (E), slippery 7 |
|---|---|---|---|---|
| Model calls per game | 64 | 65 | 68 | 69 |
| Reasoning chars per call, mean / median | 3910 / 1864 | 3890 / 2255 | 3676 / 1963 | 3523 / 2080 |
| Seconds per call | 30.3 | 29.5 | 28.6 | 28.1 |
| Calls with visible text to the viewer | **7%** | **50%** | **5%** | **38%** |
| Calls that press a button (`action(` in the code) | 56% | 58% | 54% | 57% |
| Calls whose code surveys the board (segmentation loops / ascii dumps) | 78% | 73% | 77% | 85% |
| Calls with a Python traceback | 7.4% | 5.3% | 8.6% | 7.9% |
| Game actions per model call | 1.99 | 2.50 | 2.06 | 2.50 |
| Generated tokens per game action | 669 | 551 | 602 | 494 |
| Level clears followed within two calls by a cause-naming phrase | 19 of 55 | 6 of 16 | 6 of 26 | 10 of 30 |
| Calls mentioning a panel, template or matching the example | 18% | 22% | 28% | 32% |

What that says:

1. **The opener does what it says on the surface: the model talks.** Visible narration goes from
   almost never (5–7%) to about half the calls, and it switches on exactly between arm D and arm E, so it
   is the streamer opener and not the answer-key lines. Examples (non-held-out games):
   - Compass Dye: *"Chat, big find: those little icons up top are a **color picker** — clicking the white
     one turned my purple block white, the purple one turned it back. So I can paint the big square with
     either color!"*
   - Leapfrog: *"Peg solitaire! Clicking the green peg at (1,1) highlighted a jump landing spot, and
     clicking it jumped over the neighbor and removed it — 5 pegs down to 4."*
   - Functional Tiles: *"Nice — that top-left cell flipped blue → red, so clicks toggle cells. The target
     glyph wants red at top-left, mid-left, mid-right, bottom-left. Three more clicks."*
   - Buoyant Pontoons, at the time limit: *"Alright chat, that's the timer running out on us 😅"*
2. **Under the voice, the thinking hardly changes.** Reasoning length, calls per game and time per call
   are the same, and so are survey code and tracebacks. "You're here to play, not to code" did not stop
   the coding: about three calls in four still loop over the segmentation or print ASCII crops, as they
   do under Son's prompt. So there is no shorter reasoning, no faster commitment, and no drop in
   over-thinking.
3. **Batches are a bit bigger and each action is cheaper:** about 2.5 actions per call against 2.0, and
   about 550 tokens per action against 670. It is the same kind of shift the Boss's full prompt (arm B,
   no streamer) showed on 23-Sep (2.54 actions per call). It spends actions faster, and because the
   score squares efficiency, that is not free. On the 10 matched games the streamer arm used 163 actions
   per game against 127.
4. **Attribution after a reward: no difference.** A crude phrase detector ("because", "that means", "the
   rule", "worked", …) fires after about a third of clears under both prompts: 19 of 55 for Son's prompt,
   6 of 16 for the streamer pass on the same games (23 of 53 over all 25). The streamer arm writes this
   more visibly (see the Compass Dye line), but it does not do it more often. The earlier finding that
   winners name the cause and the rule is not what separates these two arms.
5. **The answer-key lines are barely visible in the counts.** Panel/template/match talk rises from 18%
   to 22–32%, and the answer-key arm without the streamer (D) already has most of that rise. Where it
   does show, it helps: Compass Dye's *"Target (top-left mini preview) = white on top, p[urple below]"*
   is the model using the "goal is shown in a panel" line. But Compass Dye is one game, one pass.

### The Functional Tiles win, read closely

The streamer arm cleared level 4 at 942 s, level 5 at 1659 s and level 6 at 1801 s, with 137 s to spare.
Son's prompt on Kaggle reached level 5 at 1837 s in its better pass and ran out of time on level 5 in the
other. Both prompts solve this game the same way: they write a decoder. Son's arm A: *"Let me write a
general decoder now: 1. Find block grid positions … 2. Identify map cells … 3. Decode: W subcell → map
center color; g → 'not center color' …"* The streamer arm on level 5 did the same thing. It wrote a
short `snap()` function that reads every glyph, works out the required colour of each cell, and
clicks every cell that differs, stopping on `level_completed`. The final batch of that function cleared
the level. That is not "you're here to play, not to code". The win is the same solver approach as Son's
prompt, and this time it finished inside the clock. Its efficiency was good as well: levels 1, 2, 5 and 6 took fewer actions
than the baseline and levels 3–4 about 1.2–1.3× the baseline, which is why the score is 98 and not 65.

## (c) Confounds

| Confound | Ruled in or out | Evidence |
|---|---|---|
| **Different game set (hidden vs public)** | **In, and it explains the whole "doubling"** | 7.36 is the hidden-set leaderboard; Son's own prompt scores 13.6–16.0 on the public 25 (above). `docs/how-this-feeds-kaggle.md` in the arc-3 repo: the public 25 "deliberately do not represent the mechanics of the private set". |
| **Time per game** (Son's Kaggle practice pass stopped at 15 min) | In for the Kaggle comparison, out for the GCP one | Son's own 7.36 notebook pass played only 7 games for 15 minutes. On those seven, cut at the same 15 minutes, the streamer arm had **5 levels to Son's 7**; with its full ~32 min it reached 10. On the ten matched Kaggle games, levels by the 15-minute mark: streamer 10, Son's prompt 7.6 per pass. The GCP runs gave most games ~1930–2060 s in waves one to three and **~1560–1730 s in the last wave** (read from `run-timeline.json`), against 1938 s on Kaggle. |
| **Functional Tiles got more time on Kaggle** | In, partly | On GCP Functional Tiles sits in the fourth wave and was cut by the suite clock after ~1560–1620 s in all three runs (status `cancelled`). By 1616 s the streamer arm had 4 levels, the same as Son's best GCP run. Its last two levels came after that point. The same cut hit all four fourth-wave games in every GCP run (Locksmith, Reach Emblems, Ghost Twin, Functional Tiles: ~1560–1730 s, status `cancelled`), so Son's prompt matched the streamer's 25-game mean while giving up time on four games. That makes the "no difference" verdict conservative. |
| **Game coverage** | In | No complete 25-game Kaggle pass of Son's prompt exists anywhere on the Mini (searched every `benchmark.json`). The GCP runs are the only 25-game record. |
| **Single-pass noise** | In, large | Son's prompt on the bottom seven, same Kaggle settings, five passes: per-pass mean score 1.59 to 4.37, per-pass levels 6 to 9. On GCP the same arm scored 13.58 to 15.95 over three runs. Sigil Caster alone ranges 0–4 levels, Sequence Belt 3–6. One pass of anything cannot separate a few points of mean. |
| **Answer-key lines vs the streamer opener** | Separated where data exist | Slippery seven, 3 passes each: answer key alone (D) 26 levels, mean 7.49; answer key + streamer (E) 30 levels, mean 8.63. That is within one pass's spread (per-pass totals 6–10 and 7–12). The opener causes the narration (5% → 38%) and the larger batches (2.06 → 2.50 actions per call). It does not cause a measurable level gain. |
| **The Boss's full prompt underneath** | Note | The streamer arm is not "Son's prompt + two lines + opener". It is the Boss's full prompt (picture-first rewrite, the undo line, the "Looking at the screen" block, both edge-strip warnings removed) + the answer-key lines + a new retry wording + the opener. On 23-Sep the Boss's full prompt alone (arm B) scored 3.53 on seven games against 10.44 for Son's prompt. That was mostly Functional Tiles, 5 levels against 9 over two passes. So the same stack that "doubled" here halved there. |
| **Same model / card / kernel** | Out for Kaggle arms; small for GCP | All Kaggle arms: RTX PRO 6000, `RadixArk/Qwen3.8-Flash-Next-NVFP4` (log-verified), same harness and serving datasets, same 1938 s per game. GCP: same model on `g4-standard-48`, but native FP8 PLE where Kaggle uses a preconverted BF16 PLE. The Kaggle bundle also changes four gameplay files (search/scorer wording removed, 50% context swap). On the ten matched games Son's prompt scores 8.58 on Kaggle and 8.11 on GCP, so the difference is small next to the noise. |
| **Timeouts / request errors** | Out | Analyzer read timeouts in the streamer and Son's Kaggle transcripts all come with 9 s or less left on the game clock, i.e. the end-of-game cutoff; no Traceback in the Kaggle log. |

On the ten matched Kaggle games only, excluding Functional Tiles: streamer 3.96 against Son's prompt 2.99,
and 11 levels against 9.4 per pass. Almost all of that gap is Sliding Indicator in one pass (16.67 against
4.65). Without it the order flips: 2.38 against 2.78. Both gaps are inside the 1.6–4.4 per-pass range above.

## (d) Verdict, with confidence

| Part of "15 vs 7.36" | Explained by | Confidence |
|---|---|---|
| ~7.7 points (7.36 → ~15) | Hidden-set leaderboard vs public-game practice mean; Son's prompt already scores ~15 on the public 25 | High |
| Streamer vs Son's prompt, all 25 public games | No difference (15.05 vs 15.06 average; 54 vs 54–60 levels) | Moderate (one pass vs three, Kaggle vs GCP) |
| Functional Tiles win (3.9 points of the 15.05) | The same code-decoder approach as Son's prompt, finished inside the clock; more time on Kaggle than GCP's last wave; not repeated | Low that it is a prompt effect |
| Behaviour change | Real: narration (from the opener), bigger batches, fewer tokens per action | High that it happens; nothing shows it moves levels |

**So:** the streamer prompt changes the model's voice, not its play. Nothing on record says it beats Son's
prompt on the public games, and nothing at all says anything about the hidden games, which are the ones
that score.

## What to test next

1. **The missing control:** one 25-game Kaggle pass of Son's unchanged prompt at these exact settings
   (1938 s per game, no soft end, one pass), beside a second streamer pass. That gives a like-for-like
   public-25 number on the same card, plus a second draw for Functional Tiles. About 2.5 GPU hours each.
2. **Functional Tiles, repeated:** three or more passes of each prompt on Functional Tiles alone. It is
   the only game where the streamer arm is far ahead, and it carries a quarter of the mean.
3. **If a prompt change is ever judged on the public 25, compare it with Son's own public-25 runs
   (13.6–16.0), never with 7.36.** The only way to learn whether the streamer prompt helps where it counts
   is a hidden-set score, and that is a decision about spending a submission.
4. Buoyant Pontoons' second level and Sequence Belt's collapse (held out, count only) are the two per-game
   splits worth a second pass. Both could be single-pass luck.

## Files and method

- Kaggle runs: `~/bubba-workspace/arc3-kaggle/{streamer25,arms,bottom7,bottom7_r2,slippery7,slippery7_r2,attr_arms}/results/*/output/`
  (benchmark.json, transcripts). Son's 15-minute pass: `best-7.36/output/`.
- Son's GCP runs (read-only copies of `run-overview.json`, `run-timeline.json` from the arc3-viewer volume):
  `g4run-cap-return132-w7-20260916-c8fb225fae`, `g4run-clean-return-repeat132-w7-20260917-9677f73fbf`,
  `g4run-clean-return-repeat132-w7-20260918-0cfc444a85`; also consulted: Son's
  `gcp/controllers/cv5-cr-clock/README.md` (branch `docs/deepseek-v41-ceiling-run`), whose all-25 table
  shows other variants of his harness at 8.3–19.2 on the same public games.
- Scripts: `~/bubba-workspace/arc3-kaggle/trace-study/`: `pool.py` (every Kaggle run's levels, score,
  actions, tokens; a lane simulation for each game's start time; levels by 900 s), `compare.py`,
  `gcp_compare.py`, `tmetrics.py` (transcript counts). The score formula was checked by reproducing the
  streamer arm's Functional Tiles 97.98 from its `actions_per_level` and `base_actions_per_level`.
- Levels by 900 s use each game's own start (queue order, seven lanes), because the benchmark's
  `wallclock_seconds` counts from the start of the queue, not of the game.

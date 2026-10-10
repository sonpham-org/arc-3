<!--
Author: Claude Opus 5.5 (Bubba)
Date: 09-October-2026 (10-October-2026: version 3 cause and fix, Ronen's account, start harvest, two-pass baseline)
PURPOSE: Son's level-start sprint (#arc-3, 9-Oct-2026 22:30 ET): the tally of levels we do not clear consistently,
  which of them have a saved level start, and the notebook that plays all of them at once (about ten lanes, one
  variant, a 30-minute clock) on Kaggle (Flash-Next, RTX PRO 6000) or against any local server. How to run a variant,
  what was tested, and what is still missing (carried-context starts for the stuck levels).
SRP/DRY check: Pass - the runner's design is docs/2026-10-06-spark-runner.md and tools/spark_runner/README.md; this
  doc covers only the sprint (tools/level_sprint, kaggle/level-start-sprint).
-->

# Level-start sprint (9-Oct-2026)

Son's plan: tally the levels we still do not clear consistently, start each one from the point where the level before
it was cleared, and tune the prompt and harness against just those levels, with a notebook that plays about ten of
them at once so a change can be judged in about thirty minutes of play. After that, Kaggle hours go to fine-tuning.

## 1. The tally

Read from Son's heatmap (percent of nine-hour runs that clear each level; the steps are sixths, so about six runs per
game). Cross-checked against the site's `docs/static/data/stuck-levels.json`, which is **stale**: it is from 6-Oct,
eleven runs of an older harness, and puts most of these games one to four levels lower (Skewer Kebabs stuck at level
one there, level five in the heatmap). It needs a rebuild from the nine-hour runs; the heatmap is what this sprint uses.

Every level under about 80%, first stuck level in bold (lanes in `tools/level_sprint/lanes.json` are the bold ones):

| Game | Under ~80% (level: %) |
|---|---|
| Buoyant Pontoons | **3: 67**, 4: 17, 5: 17, 6-9: 0 |
| Skewer Kebabs | **5: 33**, 6-8: 17 |
| Leapfrog | **6: 17**, 7-10: 0 (4 and 5 at 83, near the line) |
| Warehouse Associates | **5: 50**, 6: 50, 7: 50, 8-9: 0 |
| Ghost Twin | **6: 67**, 7: 33 (5 at 83) |
| Sliding Indicator | **7: 50**, 8: 33 |
| Streaming Purple | **5: 0**, 6: 0 |
| Coded Notches | **5: 67**, 6: 50 |
| Deck Control | **5: 17**, 6: 0 |
| Locksmith | **5: 67**, 6: 67, 7: 33 |
| Kick Away | **7: 17** |
| Sucking Up (held out) | 5: 67, 6: 67, 7: 50, 8: 33, 9: 33 (4 at 83) |
| Reach Emblems (held out) | 7: 67, 8: 17 |

Everything else in the heatmap is at 100% on every level shown: Toggle Navigator, Mirror Rendezvous, Sigil Caster,
Volume Control, Trail Unwind, Reaching Lurch, Compass Dye, Toggle Runes, Functional Tiles, Sequence Belt, Axis
Reflectors, Loop and Pull.

**Saved level starts.** Exact carried-context checkpoints (`~/arc3-runner/checkpoints` on Jethro; `<game>/<level>/` is
the START of that level, checked: Buoyant Pontoons level 2 is reached after 21 actions, actions into level 0) exist for
only thirteen level starts: Axis Reflectors 2-3, Buoyant Pontoons 2, Compass Dye 2-3, Functional Tiles 2-4, Reach
Emblems 2-3. **None of the stuck levels above has one.** Harvest stopped writing them on 7-Oct when the two-Spark
server went down (runner health: model unreachable). What every stuck level of the eleven trainable games does have
is a verified no-context start: the original game's winning line replayed to the level start and checked against the
expected board (`replays/verified.json`). The two held-out games have no winning line here and are left out.

## 2. The notebook

Kaggle: `sonphamorg/arc3-level-start-sprint` (private), built by `tools/level_sprint/build_notebook.py` from Son's
newest notebook `sonphamorg/arc3-daniel-int8v2-l12-ct1`. Source in the repo: `kaggle/level-start-sprint/`.

- **Serving and harness are Son's, cell for cell**: harness patch, environment cell, port cell (noborder, tuned
  drafter, hot map, temperature, toolfast, host tier, rejection sampling), precache, ARC runtime install, bundle
  import, the SGLang launcher (Flash-Next INT4 + drafter on the RTX PRO 6000, twelve request slots), the monitor.
  Only the benchmark cells are replaced. Same inputs as his notebook plus the dataset `sonphamorg/arc3-level-sprint`.
- **Lanes**: `tools/level_sprint/sprint.py run` starts one `tools/spark_runner/sample.py` process per lane, all at
  once, with the same spec the Spark runner's server writes for a Play job. So the start (exact checkpoint restore with
  the first-request check, or the winning-line replay with its board check), the turn hooks and `result.json` are the
  runner's own code. The harness is the patched bundle the notebook just built, and its flags are frozen from the
  notebook process (`sprint.py freeze-env`), so nothing is retyped.
- **Start per lane**: the notebook's `LANE_START` (default `auto` since version 3) overrides `lanes.json`.
  `auto` = a saved checkpoint at the stuck level's start (exact lineage first, else one a warmup lane saved), else
  `warmup`.
  `warmup` = winning line to the level BEFORE, the model plays that level and carries its own context into the target
  level (cleared = both levels; the clock covers both; checked offline: Skewer Kebabs from level 4 cleared it and
  entered level 5 with the conversation carried); `replay` = the stuck level with no context; `exact` = a saved
  checkpoint; `auto` = exact if one is saved for that level start, else replay.
- **Lane count and length** (added 10-Oct): `COPIES` lanes per level at once (the server has 12 request slots),
  `PASSES` plays the whole lane set again after the first finishes (starts planned once, so a checkpoint saved in
  pass 1 never changes a pass-2 start), `LEVELS_TO_PLAY` lets a lane play on past the stuck level, saving a carried
  checkpoint at every level start it reaches. `LANES_FILE = "lanes-harvest.json"` is the start harvest (section 5).
  "Cleared" in the table always means the stuck level itself was cleared.
- **Clock**: `WALL_MINUTES` (default 30) is play time per lane; the model server's startup (about 12-20 minutes on
  Kaggle) comes on top. A lane still running at the clock plus three minutes is killed and counts as not cleared.
- **Output**: `/kaggle/working/sprint/results.md` + `results.json` (per level: cleared, outcome, actions used, turns,
  minutes, start kind); per lane its transcript and turns under `sprint/lanes/`; any checkpoint a carried-context lane
  writes under `sprint/home/checkpoints/`.
- **Never a submission**: nothing in it reaches the competition gateway.

### Running a variant (Son)

1. Kaggle, `sonphamorg/arc3-level-start-sprint`, Edit. In **Sprint settings** set `VARIANT`: `name`, `instructions`
   (text added to every turn message), `env` (harness flags, any `ARC3_*` / `LOCAL_ANALYZER_*` key), `settings`
   (temperature, thinking, effort, thinking budget). For a harness code change, edit the patch or port cell exactly as
   in your own notebook.
2. Check the accelerator says RTX PRO 6000, then Save & Run All. Results print at the end and in `sprint/results.md`.
3. Compare against the stock control run (section 3). One pass per level is noisy; a level that flips needs a second
   run before it counts.

Locally (any OpenAI-compatible server, e.g. a Spark): build the harness with `tools/spark_runner/build_harness.py
--notebook <Son's .ipynb>`, point `ARC3_RUNNER_HOME` (solutions, replays, checkpoints), `ARC3_RUNNER_HARNESS` and
`ARC3_RUNNER_ENVIRONMENTS` at copies of the runner's folders, then
`sprint.py run --out <dir> --base-url <url>/v1 --model-id <id> --wall-minutes 30`.

### Shipping new checkpoints (and any sprint code change)

1. `build_dataset.py --runner-home <copy of ~/arc3-runner> --owner <owner> --slug arc3-level-sprint --out <dir>
   [--add-checkpoints <run output>/sprint/home/checkpoints ...]`. `--add-checkpoints` merges the checkpoints a run
   saved into the runner-home copy (new folders only). Every build writes a marker `level_sprint/build-<ID>.json` (build
   id, and the level starts that have a checkpoint) and prints the ID.
2. `build_notebook.py ... --expect-build <ID>` writes the notebook with `EXPECT_DATASET_BUILD = '<ID>'`.
3. `push.py --token-file <account's token> --dataset-dir <dir> --kernel-dir <notebook dir>` adds the dataset version,
   **waits until that build's marker file can be downloaded from Kaggle** (the status call is not trusted: it said
   "ready" for the old version on 10-Oct), then pushes the notebook.

If Kaggle still attaches another build, the setup cell stops with "sprint dataset is build X, the notebook expects Y"
before the server starts, so no GPU time is spent on old files. In the Kaggle editor, a hand edit can set
`EXPECT_DATASET_BUILD = ""` to run on whatever is attached. Kaggle unpacks `.gz` files on upload; the notebook's setup
cell gzips `request.json` and `state.pkl` back, and `sprint.py plan` now stops a lane with "saved start(s) ... have no
state.pkl.gz" instead of quietly giving it a warmup start if that step ever fails.

## 3. Tests (9-Oct-2026)

- **Offline, Jethro, no model** (Jethro's GPU was busy with our ARC-2 vote run, so no model was loaded there):
  Son's newest harness built from his notebook (`build_harness.py` needed one fix: the toolfast block now ends at the
  next section header, because his newer notebooks put a drafter section with Kaggle-only paths after it). Plan
  resolves all eleven lanes to verified no-context starts. A No-context first request at Skewer Kebabs level 5 passes
  every check. A scripted-model play (`render_requests.py ... tour`) through `sample.main` with the sprint's spec
  cleared Skewer Kebabs level 5 from the replay start and Buoyant Pontoons level 2 from its exact checkpoint, whose
  first request matched the saved one in all 66 messages (only the model name differed); the checkpoint was saved by
  the older harness and restores into the newer one.
- **Kaggle, stock control, version 1** (`sonphamorg/arc3-level-start-sprint`, Son's account, 9-Oct 22:47-23:29 ET,
  0.6 GPU hours; his reserve untouched). Card checked in the log: NVIDIA RTX PRO 6000 Blackwell Server Edition. Server
  healthy 7 minutes after the notebook started (jit cache restored from his kernel source), then all eleven lanes
  played 30 minutes at once, about 150k generated tokens each, no errors, no request timeouts except the one cut off
  by the clock at the end. **Cleared 0 of 11.** Every lane ended on the clock: Buoyant Pontoons 3 (23 actions, 14
  turns), Skewer Kebabs 5 (398, 33), Leapfrog 6 (107, 54), Warehouse Associates 5 (58, 20), Ghost Twin 6 (103, 23),
  Sliding Indicator 7 (133, 31), Streaming Purple 5 (85, 26), Coded Notches 5 (186, 43), Deck Control 5 (304, 35),
  Locksmith 5 (109, 24), Kick Away 7 (93, 31). Output kept on the Mini under
  `/Volumes/Samsung 9100 SSD/data/arc3-level-sprint/kaggle-v1/`.
- **Kaggle, stock control with warmup, version 2** (9-Oct 23:32 ET - 10-Oct 00:11 ET, 0.6 GPU hours; RTX PRO 6000
  checked; server healthy after about 6 minutes). **Cleared 1 of 11**: Sliding Indicator 7 (it cleared level 6, then
  7, in 29 minutes). Only four lanes cleared their warmup level inside the clock (Sliding Indicator, Deck Control,
  Locksmith, Kick Away); the other seven spent the whole half hour on a level the nine-hour runs always clear. Those
  four lanes saved carried-context checkpoints at Deck Control 5, Locksmith 5, Kick Away 7 and Sliding Indicator 7 and 8.
  All restore into Son's newest harness (checked offline on Jethro: replay, board, 70-91 messages of history, 7-35
  retained functions). They ship in dataset version 3, so `auto` starts those four stuck levels with carried context
  and the full 30 minutes.
- **Kaggle, version 3** (10-Oct 00:13-00:52 ET, 0.6 GPU hours) was meant to be the first `auto` run, but it was
  pushed four seconds before Kaggle finished processing dataset version 3 (`kaggle datasets status` reported the
  previous version as ready), so it ran with version 2's code and checkpoints: every lane started with no context.
  Confirmed 10-Oct: its log shows `--start auto` and every lane labelled "no context (winning_line)", a label the
  version 3 `sprint.py` cannot give for `auto` (its fallback is warmup); its copied `home/checkpoints` has none of
  the four new games. Not the resolver and not the `.gz` handling: dataset version 3 downloaded as Kaggle serves it,
  unpacked, put through the notebook's setup steps and planned with its own `sprint.py --start auto` gives carried
  checkpoints at Sliding Indicator 7 (199 actions from reset), Deck Control 5 (274), Locksmith 5 (223) and Kick Away
  7 (384), warmup for the other seven. Fix: the build marker, `EXPECT_DATASET_BUILD` and `push.py` above.
  It is a second no-context control: **cleared 1 of 11**, Buoyant Pontoons 3 (in 25 minutes; it did not clear in
  version 1). So one-pass no-context results flip from run to run. The notebook source on Kaggle is now version 3
  (`auto`), and dataset version 3 (18 checkpoints) is processed; the `auto` start with carried checkpoints has passed
  the offline restore check but has not yet been played on Kaggle.
- **What that means**: the plumbing works, but as a yardstick a no-context, 30-minute, one-pass control at these levels
  reads zero everywhere, so a variant can only show up by clearing something. The warmup control shows the real cost:
  half an hour is often not enough to clear even the level before. So the sprint is only as good as its saved starts.
  Each run with `auto` saves new carried starts for the levels whose warmup it clears; copy
  `sprint/home/checkpoints/` from the run output into the dataset (section "Shipping new checkpoints") and the next
  run starts more lanes right at the stuck level. A longer clock or two lanes per level helps the levels closest to the
  line (Buoyant Pontoons 3, Ghost Twin 6, Coded Notches 5, Locksmith 5 at 67%).

## 4. What is missing

- Carried-context starts for the stuck levels. They need a model to clear the level before each one and save the
  checkpoint (harvest), and harvest has had no server since 7-Oct. The `warmup` start gives one level of the model's
  own context inside the 30-minute clock; a lane that clears the warmup level writes a (non-exact-lineage) checkpoint
  for the target level start, which can be shipped back in the dataset.
- Ronen's account (scizical) is entered in ARC-3 but cannot read Son's three private datasets (patchsets, the two
  drafters): sharing them with scizical lets sprints run on his thirty spare hours instead of Son's.
- `stuck-levels.json` on the site should be rebuilt from the nine-hour runs.

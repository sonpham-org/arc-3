<!--
Author: Claude Opus 5.5 (Bubba)
Date: 08-October-2026
PURPOSE: Findings for Son's short-prompt arm "draftB" (INT8 v2 build, 7-Oct) against the four normal-prompt
  INT8 v2 controls, and the restored system prompt that replaces the short draft
  (docs/plans/2026-10-06-system-prompt-cleanup/draft-restored.txt). The Boss approved the comparison in #arc-3,
  8-Oct 16:00 ET. Nothing live changed: no runner, notebook, Kaggle or site change, no runs started.
SRP/DRY check: Pass - one findings note; the restored text is built from the deployed dedup builder
  (tools/spark_runner/prompt_profiles.py, dedup_system_prompt) and live-now.txt, not retyped from memory.
-->

# draftB vs the INT8 v2 controls: what the short prompt dropped

## The runs

| Arm | Run | All 25 | Levels | Actions |
|---|---|---|---|---|
| draftB (short prompt) | g4run-daniel-hicache-bint8v2l12db-b-1007 | 46.69 | 123 | 11,767 |
| INT8 v2 c | g4run-daniel-hicache-bint8v2l12-c-1006 | 59.51 | 137 | 9,934 |
| INT8 v2 e | g4run-daniel-hicache-bint8v2l12-e-1006 | 58.64 | 131 | 10,215 |
| INT8 v2 f | g4run-daniel-hicache-bint8v2l12-f-1006 | 55.87 | 127 | 9,192 |
| INT8 v2 g | g4run-daniel-hicache-bint8v2l12-g-1006 | 60.58 | 134 | 9,969 |

Read from the site's score-climb file (`/srv/data/_rl2/score-climb.json`, 8-Oct). The draftB arm id is
`daniel_sb_t06_toolfast_rs0008_hicache32_oa13_stack_w4_fx10b_bestint8v2_draftb_l12_w131k_v1_g7920`: same build,
same twelve lanes, only "draftb" differs. Per-game numbers are Son's (#arc-3, 8-Oct).

Games it broke (normal prompt wins them every time): Reaching Lurch, Mirror Rendezvous, Functional Tiles,
Axis Reflectors, Toggle Runes, and Coded Notches. Games it did better on: Sliding Indicator, Sucking Up,
Streaming Purple (plus small gains on three games the controls nearly clear).

## Blocker: the traces are not reachable

The step files for these runs are not on the site. Checked 8-Oct: not in the Railway volume (all run folders
listed), not in the site catalog, and Son's cloud bucket refuses the Boss's Google login. The stuck-levels doc
already says Son's 4-Oct-on runs have "totals only on the site". So:

- **Not confirmed which text draftB sent.** The arm name and the timing (the draft was committed 6-Oct evening,
  draftB ran 7-Oct) point to `draft-for-boss.txt`, but the run's own logged system prompt was not readable.
- **Not confirmed whether draftB's turn messages were the original harness's** (which repeat many standing lines
  every turn: the `history[-1]` warning, MOUSE needs row and col, the tool-call format, "ground yourself first")
  **or deduplicated.** On the original turn messages those lines still reached the model, so the drops that matter
  most are the ones said only in the system prompt (marked "system prompt only" below).
- Everything below is a **ranked list of candidates from the prompt-vs-prompt diff**, not causes read from traces.

To unblock: Son publishes draftB and one control (g or c) to the site, or shares the step files for Reaching
Lurch, Mirror Rendezvous and Functional Tiles. Then the turn-by-turn comparison takes an hour.

## What the short draft dropped, and the failure each fits

Diff of `draft-for-boss.txt` against the full text (`live-now.txt` = `dedup_system_prompt()`), ranked by how
directly each drop can break an easy game. Every one is back in `draft-restored.txt`.

1. **Game-over flag meaning (system prompt only).** Full: "`game_over` = this attempt FAILED (it never means the
   run is won)". Draft kept "game_over = this attempt failed", dropped the parenthesis. Fits misreading a death
   as progress on short games.
2. **Budget bar vs gameplay (partly system prompt only).** Full: "after every action check whether gameplay
   objects changed or only the bar did", plus the whole `board_changed` / `gameplay_changed` explanation that the
   daniel flag set turns on. Draft: neither. Fits the extra actions: moves that only shrink the bar look like they
   did something.
3. **MOUSE axes (system prompt only).** Full: "zero-based from the top-left, `row` downward and `col` rightward
   (x/y fields are rejected)". Draft: "integers row, col in [0, 63], origin top-left". Click games (Functional
   Tiles, Coded Notches) depend on this; a swapped axis or x/y call wastes actions.
4. **`history[-1]` consequence.** Full: "Comparing `history[-1].frame` to `current_frame` compares the board with
   itself", and the explicit "for the most recent change, compare `previous_frame` to `current_frame` ...". Draft:
   only "history[-1].frame is the CURRENT board". The original turn message repeats this, so it matters only if
   draftB's turn messages were deduplicated.
5. **Segmentation identity (system prompt only).** Full: "equal hashes mean matching shape up to rotation, not the
   same object", the rotation reduction rules, `rotational_symmetry` values, children "fully enclosed". Draft
   shortened all of it. Fits Mirror Rendezvous (two matching shapes) and Axis Reflectors (mirrored pieces).
6. **Coordinates are not the goal (system prompt only).** Full: "Use coordinates to target actions or describe
   local evidence, not as the objective itself." Draft: gone.
7. **Read in code, don't ration calls.** Full: "Do not ration calls while the state is unclear: inspect
   `current_frame`, `history` and `valid_actions` from Python rather than reasoning about the board by eye", and
   `.ascii` "never scan or summarise the whole board with it". Draft: "Inspect the board in code, never by eye",
   ".ascii ... read only small regions".
8. **Act only in code, emit the call.** Full: "never as text in your reply" and "When you decide to call the tool,
   emit the call itself." Draft: both gone (the original turn message repeats the second).
9. **Animation detail (system prompt only).** Full: `transient_pixels`, `transient_bbox`, frame order, the
   timeline's `changes` format, "reading them costs no action". Draft: one sentence. Fits Toggle Runes and
   Reaching Lurch, where a move's effect can show only mid-animation.
10. **`frame_diff` detail.** Full: matching can be wrong with several similar components, `changed_color` and
    `resized` fields, `bbox` format, the worked example. Draft: names only.
11. **Smaller drops:** UNDO "check what it restores"; deaths "treat the death as evidence against the belief that
    it should have worked"; `last_action_call_result` "still describes the call that died"; "verify" backgrounds
    "by area, stability and boundaries"; entity sizes (2x2, 2x3, 3x3); "BFS is usually safest for moving an agent
    to a target"; "write a small scorer"; `automatic=False` for the model's own actions; `{}` before any call;
    "keep snippets purpose-built"; "Tool results report ... why any was rejected"; "cleared when a new game starts".

## The games that improved

Without traces: draftB spent about 1,800 more actions and did better on Sliding Indicator and Sucking Up, two
games where the normal prompt stalls after two or three levels. That is consistent with more probing and less
early commitment, which a looser prompt can produce. One run; the controls already swing a lot on hard games.
If it holds on a repeat, the lever is an explicit instruction to keep probing when stuck (a mode such as Probe or
Recover), not a shorter system prompt.

## The restored prompt

`docs/plans/2026-10-06-system-prompt-cleanup/draft-restored.txt`:

- Persona line from the Boss's draft: "You are a coding agent playing an ARC-AGI-3 game", with the "no
  instructions, learn by acting" sentence.
- Every instruction and fact in `dedup_system_prompt()` kept, each once, in the order goal, each turn, new levels,
  board, tool, globals, history, actions, budget and deaths, playing well. Active voice. Compact notation only
  where lossless (`=` for flag meanings, `0..63`, short field lists).
- The `board_changed` / `gameplay_changed` paragraph is included because the draftB and control arms run the daniel
  flag set. Drop it for the son flag set, where the harness does not explain it.
- Three values are frozen as text, as in `live-now.txt`: the edge-guard distance (4, `ARC3_NOOP_GUARD_BORDER`), the
  tool-output cap (about 3072 tokens) and the colour legend (`grid_utils.ARC_COLOR_LEGEND`). Whoever wires this
  into a builder should fill them from the harness, not paste them.
- The death sentence also carries the original turn message's "record the correction ... instead of retesting it".
- Checked against the dedup profile's `STANDING_LINES`: every fact those lines carry is in the restored text, so it
  is safe under deduplicated turn messages too.

Length is about the same as the full text: nothing was cut, only repeats and ordering changed.

## Next

Son runs the restored prompt as the next arm on the same INT8 v2 build, next to a control. If it lands with the
controls, the short-draft loss came from content, and the per-turn modes are where shorter text can be tried one
line at a time.

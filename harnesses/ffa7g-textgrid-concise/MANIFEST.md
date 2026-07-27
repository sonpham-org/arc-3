# ffa7g-textgrid-concise — anti-redundancy addendum for Laguna

Adds one thing on top of `ffa7g-textgrid`: three extra sentences in
`TEXT_GRID_CONTEXT_ADDENDUM` directly targeting three token-inefficiency
patterns found by reading Laguna's own transcripts (2026-07-26, run
`20260726_221752_laguna-ffa7gnsg-halfconc`).

- **Derives from:** `bundle-v12ffa7gnsg-textgrid.tgz`'s own
  `src/ARC3-Inference/`. `patch/concise.patch` is relative to that bundle
  (mirrors `../ffa7g-textgrid/MANIFEST.md`'s own note about why these patches
  aren't relative to `baseline-v12/`).
- **Patch:** `patch/concise.patch` — 1 file (`prompts.py`), 10 lines added.
- **Bundle:** `gs://cellens-ai-artifacts/arc3-duck/tufa-exact/bundle-v12ffa7gnsg-textgrid-concise.tgz`.

## Why this exists

Direct transcript comparison (Laguna vs. the historical Qwen run, same game
`ar25-0c556536`) found Laguna needs ~6.4-9.7x more tokens per action. Two
compounding causes, both visible in the raw `[THINKING]` blocks:

1. **Manual ASCII counting.** Despite `STRUCTURED_RUNTIME_STATE_ADDENDUM`
   already saying "use `current_frame.segmentation` as your primary view...
   do not scan the whole board" with `current_frame.ascii`, some games'
   transcripts show Laguna counting grid characters column-by-column by hand
   (`"b(0) b(1) b(2) b(3)..."`) instead of reading the segmentation object it
   already has. Inlining the ASCII grid into the prompt text (the
   `ffa7g-textgrid` patch's whole point, since Laguna is text-only) seems to
   make this more tempting than for image-based arms, where there's no raw
   grid text sitting in the message to be tempted by.
2. **Redundant full-board re-derivation.** One game (`re86-8af5384d`) shows
   FIVE separate near-complete node-by-node board summaries across a single
   episode, each re-deriving the whole layout from scratch rather than
   building on the previous one -- one single turn's `[THINKING]` block hit
   ~66,000 characters (~16,500 tokens). Combined with lower action-batching
   (Laguna averages 0.53 actions/turn vs Qwen's 1.47 on the same game, and
   smaller `action(...)` batches when it does act, 1.3 vs 1.8 items/call),
   these two effects compound multiplicatively (~1.7x tokens/turn x ~2.8x
   fewer actions/turn ≈ 4.8x) and account for most of the observed gap.

## What changed (1 file, 10 lines)

`prompts.py`: `TEXT_GRID_CONTEXT_ADDENDUM` gains three more bullet points
(after the existing "you don't need to call python just to read the grid"
line):
1. Explicit "do NOT manually count/transcribe ASCII characters cell-by-cell"
   instruction, naming `current_frame.segmentation` as the fast/correct path.
2. Explicit "do NOT re-derive the whole board every turn" instruction, naming
   `previous_frame`/`last_transition` as the diff-only path for later turns.
3. Explicit "prefer acting over further exploration" + "batch into one call"
   nudge, reinforcing (not duplicating) the batching guidance already in
   `STRUCTURED_RUNTIME_STATE_ADDENDUM`.

## Status

Untested at time of writing — this is one of 4 arms (A: thinking off, **B:
this patch**, C: hard per-turn token cap via `LOCAL_ANALYZER_MAX_OUTPUT`, D:
B+C combined) in a 7-game fast-iteration spot-test sweep
(`gcp/launch_laguna_spottest.sh`), comparing tokens/action and actions/turn
against each other and against the halfconc run's baseline numbers.

# ffa7g-textgrid — inline ASCII grid for text-only models

Adds one thing on top of ffa7gnsg (frame-full + ACTION7-anim + goal-guidance +
no-impact + state-graph, state-graph OFF by default): when no image is being
sent, the current board is inlined into the user turn as ASCII text instead of
relying on the model to spend a `python` tool call just to read it for the
first time each turn.

- **Derives from:** a fresh extraction of `bundle-v12ffa7gnsg.tgz` (**not**
  `../baseline-v12/`, unlike the other variants in this directory). The
  state-graph layer that bundle carries was never captured as a committed
  patch file in this repo (its own MANIFEST section is prose-only, see
  `../ffa7g/MANIFEST.md`), so there's no clean way to reconstruct a
  baseline-v12-relative patch that includes it. `patch/textgrid.patch` is
  therefore relative to the bundle's own `src/ARC3-Inference/`, not baseline.
- **Patch:** `patch/textgrid.patch` — 2 files (`prompts.py`, `tool_agent.py`),
  applies `-p1` to a fresh copy of the bundle's `src/ARC3-Inference/`
  (dry-run clean, verified byte-identical reproduction 2026-07-26).
- **Bundle:** `gs://cellens-ai-artifacts/arc3-duck/tufa-exact/bundle-v12ffa7gnsg-textgrid.tgz`.

## Why this exists

Built to run Poolside's Laguna S 2.1 (text-only, no vision variant exists) on
this harness, which otherwise feeds a rendered board PNG every turn
(`MULTIMODAL_CONTEXT=current_grid`). Reading `vision_context.py` and
`tool_agent.py` directly (2026-07-26) showed the message-shape branch already
works correctly for a text-only arm — `current_grid_image_enabled()` is a
strict equality check against the literal `"current_grid"`, so simply not
setting that env var already yields a plain-string user message today, no
code change needed for that part alone.

The one real gap: **neither mode inlines the board into the prompt text**.
Even in image mode, the model is expected to call the `python` tool and read
`current_frame.ascii`/`.segmentation` to actually reason about the board — the
image is a bonus glance layered on top, not the only way to see it. For a
text-only model that asymmetry is a real cost: every turn needs an extra
tool-call round-trip just to get bearings that image-mode arms don't pay.

## What changed (2 files, ~15 lines)

1. **`prompts.py`**: new `TEXT_GRID_CONTEXT_ADDENDUM` constant, paired with the
   existing `MULTIMODAL_CONTEXT_ADDENDUM` (tells the model the grid is already
   inline, so it doesn't waste a turn re-deriving what it can already read).
2. **`tool_agent.py`**:
   - `_build_system_prompt()`: `else: prompt += TEXT_GRID_CONTEXT_ADDENDUM`
     alongside the existing `if current_grid_image_enabled(): ...` branch.
   - `_build_user_message()`: when there's no image part and a frame exists,
     return `{"role": "user", "content": f"{user_prompt}\n\nCurrent grid
     (ASCII):\n{current_frame.ascii}"}` instead of the bare `user_prompt`.
     `Frame.ascii` (`runtime_state.py:27-29`) already wraps
     `format_grid_ascii()` (`grid_utils.py`) — no new rendering code needed,
     reused exactly what the sandbox already exposed to the agent.

**Deliberately left unchanged:** `GAME_OVERVIEW_ADDENDUM`'s "boards are
presented as 64x64 color grids rendered with ARC color symbols" line —
inspected it directly; it's mode-agnostic and already accurate for the ASCII
letter-coded symbol system, doesn't claim an image is always sent. No image-vs-
text-only investigation found any other place that hardcodes multimodal
content-block shape — `_build_user_message` was the only construction site,
history/token-estimation code was already shape-agnostic.

## Root-cause note (not part of this change, but worth recording)

This project's history notes "Text-only models (gpt-oss-120b, Coder-Next,
Gemma NVFP4) can't do faithful v12 -- the harness feeds board PNGs." Tracing
it: `gcp/v12model_startup.sh` sets `MULTIMODAL_CONTEXT=current_grid
MULTIMODAL_UPSCALE=4` **unconditionally**, regardless of `MODEL_FLAVOR` — so
those earlier text-only attempts were still being sent an `image_url` content
block their chat template couldn't parse, a predictable hard failure. It looks
like a config oversight rather than a discovered architectural limit; a
controlled text-only arm (env var actually unset) was apparently never tried.
Not chasing that further here, but worth knowing before re-reading that old
conclusion as gospel.

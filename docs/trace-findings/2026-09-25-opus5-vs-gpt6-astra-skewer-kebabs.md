# Opus 5 vs GPT-6 Astra on Skewer Kebabs: why the "wrong" Astra reasoning still wins

Author: Claude Opus 5.5 (Bubba). Date: 25-September-2026.
Asked by the Boss (#arc-3, 13:44 ET), comparing https://arcprize.org/replay/c6f88b81-e660-426a-b632-c1b5b0fc966c (Opus 5)
with GPT-6 Astra's Skewer Kebabs replay (the one quoting "ACTION6 allows extending targets ... typical ARC games").
Data: three.arcprize.org/api/sessions/<guid> and /api/recordings/sk48-d8078629/<guid>, read 25-Sep-2026.

## Runs
- Opus 5 (config anthropic-claude-opus-5-high): 2 of 8 levels, 684 actions, not finished. Level 1 by step ~17, level 2 by
  step ~179, then ~500 actions stuck.
- GPT-6 Astra, 12 runs on this game: every "provider-adapter" config WINS all 8 levels (346-545 actions); every plain config
  (none/low/medium/high/xhigh/max) gets only 3-4 levels. The quoted replay is ec8d80f4-... = astra-max-provider-adapter,
  WIN in 346 actions.

## Why Astra's visible reasoning looks wrong
- Astra's per-step record has `output` = just the action ("ACTION4") and usually `reasoning: null`. The occasional
  reasoning text is a provider-generated **summary** of hidden reasoning ("**Evaluating click mechanics** ... Typically,
  ACTION6 allows extending targets ..."), not the reasoning itself. Summaries are paraphrases and can be generic or wrong.
  The step the Boss quoted (step 5) spent ~137 hidden reasoning tokens and then clicked; the next steps went back to ACTION4.
- Visible output: Opus median ~1,900 tokens per turn (its notes ARE its reasoning, ~2.2M output tokens total); Astra median
  ~35 tokens per turn visible, ~59k hidden reasoning tokens for the whole 346-action win. Astra thinks little, acts, and
  learns from the frames.
- Both carry long histories (median input ~127k Astra, ~155k Opus). The adapter's per-step `state` shows history items and
  pruning, i.e. it replays prior turns (likely including the model's own reasoning items) to the provider's native API.
  Same model without the adapter: half the levels. So the harness (keeping the model's own thread between turns) is worth
  more than extra thinking here. [inference from config names + state fields; not documented by ARC Prize]
- "It knows about typical ARC games / kebab puzzle": the summaries mention "a typical ARC3 game" and "the kebab puzzle game
  mechanics". The public ARC-3 games (incl. Skewer Kebabs) have been public for months; a newer model may have seen them in
  training. Unverified; worth keeping in mind when comparing models on public games.

## Opus 5 on the same game
Human-followable notes every turn ("Context / Notes to carry forward", ✅ marks, emojis in over half the steps), correct
mechanics early (up/down, extend, retract, pickup order from the legend), fast level 1. Then it over-writes: long notes each
turn, and on the harder levels it keeps re-deriving and stalls, same pattern as its zero-score games
(2026-09-25-opus5-arcprize-replays-failures.md).

## Takeaway for our harness
Carrying the model's own reasoning/thread across turns, plus short fast actions, beat long visible deliberation on this
game. Worth testing on Flash-Next: does passing prior reasoning back each turn help, versus notes-only memory?

# Simplification: clear consequences and forgiving exploration

Author: Codex (GPT-6)
Date: 2026-09-14
Purpose: Apply Son Pham's accepted KS01 playability feedback to the remaining QC
batch and future game improvements. This is an additional QC requirement, not a
new mechanic for every game.

The user's direction:

> Some action very unclear why it leads to game end. In fact, maybe try to not
> have game end for each of these games bro, or make it very hard to have game
> end, with lives mechanism to clearly indicate to the users what is going on.

The user subsequently accepted the recovery direction as useful for simplification.
This requirement supersedes any blanket demand for a finite losing trace. A game
does not need GAME_OVER to qualify. Preserve interesting decisions, discovery and
later composition; do not substitute a tight move budget for a puzzle.

## Design defaults

- Prefer no terminal loss during ordinary exploration. A rejected action should
  be harmless, reversible, or restore the previous valid position with feedback.
- Empty undo/rewind, a boundary move, an invalid click, or trying an unfamiliar
  control must not silently spend a life or end the run. Show what prevented the
  action, using a cue at the relevant object and plain control labels as needed.
- Keep a loss condition only when the hazard is part of the puzzle's real causal
  idea. Make the hazard, the consequence and any remaining lives visible before
  the next action. A retained life system must allow learning and recover from
  ordinary mistakes; tiny unexplained counters are insufficient.
- Separate lives, move budgets, progress and score. State which actions change a
  resource. Retain a move limit only with a recorded gameplay reason and visible
  accounting. No hidden action cap may end an otherwise playable attempt.
- Retry the current level while keeping completed levels. Offer Undo where it
  fits the mechanic. Explain the scope of recovery; a fresh page/session may
  still start a new campaign if that is how the player works.
- Make the objective, targets, progress and success recognizable. Complete action
  animations before accepting overlapping input, without trapping the player in
  a long animation that cannot be restarted.
- Put help and resource labels in the normal player UI. Avoid unexplained words
  or decorative status markers inside the puzzle. Text may explain a control;
  the puzzle's spatial rules and critical state should remain visually legible.

These are shared design constraints. Do not give authors another game's design,
solution, artwork or reviews as a template. Keep fresh-context isolation.

## Required exploratory checks

In addition to real winning paths and fresh novice play, test:

1. Plausible first moves and every ordinary advertised control, including repeated
   presses, blocked moves, empty recovery actions, and invalid/background clicks.
2. A wrong goal check or a real hazard, where the game has one. Record the visible
   cause, resource change, explanation and recovered state. If terminal loss is
   retained, verify the warning/life buffer and the retry path explicitly.
3. A move beyond the former budget when removing a budget, plus exploration in
   later levels. Removing one initial trap is not evidence that all traps are gone.
4. Undo or retry after a rejected move, and retry after completing an earlier
   level. Confirm that control remains usable and completed levels stay complete.
5. Rapid/repeated input during animation and a restart during playback, when the
   normal player supports animated actions.

Record the exact game source hash, player/recovery mode and any relevant helper
hash, actual actions and visible outcomes. Test the normal player, not just a
verifier's winning sequence. A website recovery wrapper does not prove that a
standalone candidate is forgiving; report that distinction and test the delivered
configuration. Generic "rejected" feedback alone does not establish rule clarity.

## Qualification and existing evidence

Keep deterministic replay, real wins, genuine mechanic necessity, mutation tests,
artifact correctness, independent clarity review and pair-distance gates.

For a game intentionally lacking terminal loss, record `not_applicable` for the
losing path with a reason and substitute real rejected-action, exploration and
retry evidence. Never fabricate a losing recording, disguise a win as a loss or
add an artificial failure solely to satisfy an old verifier. Update affected
verifiers/artifact consumers explicitly for this mode; do not suppress assertions
or claim a machine pass while an old mandatory-loss check still fails.

Random-resistance results must name their evaluation mode and finite action
horizon. Unlimited retries are not the same experiment as a strict attempt with
an action budget. Preserve the existing Level 2+ threshold for its defined test;
do not imply an infinite-horizon probability bound or hide a changed test regime.

Every remaining candidate needs an explicit recovery-policy audit before final
activation. Older QC records stay historical; their existing scores do not grant
this new requirement retroactively. Reopen a candidate when actual user play
exposes an unexplained loss, even if its previous simulated reviews passed.
Changed frozen sources require new versions and new exact-source evidence.

The user's acceptance of KS01 followed explanation and fixes. It is guided human
feedback supporting this direction, not a fresh first-time novice test and not
human confirmation of the other games. See `human-feedback/20260914-recovery.json`.

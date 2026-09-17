<!--
Author: Claude Opus 5
Date: 17-September-2026
PURPOSE: Operator guide for the test-only games folder. Says what is in it (as66), the rule that
it is never trained on, how to point a harness at it, the baselines to compare against, and where
its canonical source lives. Written so a session joining cold cannot mistake this folder for
training material.
SRP/DRY check: Pass -- the game's rules and history live in arc-explainer
(docs/reference/arc3/AS66_Lost_Game.md) and the 15 January runs in
docs/trace-findings/2026-09-15-as66-the-withdrawn-26th-game.md; this file only says how the
build here is used and what must never happen to it.
-->

# Test-only games

**Everything in this folder is for testing agents. None of it is ever trained on.**
Boss's decision, 17-Sep-2026.

## What is here

| game id | levels | what it is |
|---|---|---|
| `as66-v1` | 9 | The 26th game: one of the July 2025 preview games, no longer in the live 25. ARC Prize never published its source. Recreated from Boss's 27-Dec-2025 nine-level winning recording; every frame of that recording replays exactly, and the level layouts match his screenshots. |

As66 is **not** one of the 7 held-out games in
[`datasets/splits/public25-train-test-split.json`](../splits/public25-train-test-split.json).
That split covers only the live 25. As66 is an extra test game on top of it. Report its score
on its own line, never inside an all-25 or ex-`ft09` average.

## The rule: never train on it

- **Never copy it into `docs/static/games/`.** That is the catalog the duck plays for training.
- **Never let an as66 record into a training corpus.** That covers SFT, RL, the decision-step
  corpus and any mix-in, whether the play is human or agent.
- **Whenever you extract from a run directory that played as66, fence it out:** add `as66` to
  `ARC3-Inference/distill/extract_sft.py --exclude-games`, next to the 7 held-out codes:
  `--exclude-games vc33,ar25,sb26,re86,su15,tr87,tu93,as66`. The fence matches the bare code, so
  `as66` catches `as66-v1`.
- The 15 January runs on the original build (`datasets/decision-steps/v0/recordings/as66-821a4dcad9c2/`)
  follow the same rule.

## How to test on it

Point the harness's offline arcade at this folder:

```python
import arc_agi
arcade = arc_agi.Arcade(operation_mode=arc_agi.OperationMode.OFFLINE,
                        environments_dir="datasets/test-only-games")
env = arcade.make("as66-v1")
```

With the in-tree harness, pass `datasets/test-only-games` as `environments_dir` (it builds a
`taaf.game_api.ArcadeSpec` from it) and `as66-v1` as the game id. Checked 17-Sep with
`python3.13`: the folder lists `as66-v1`, and the fewest-move route for each level plays all
nine levels to `WIN` through this API.

Controls: ACTION1-4 move (up, down, left, right). ACTION6 is accepted and does nothing. No
ACTION5, no undo. RESET restarts the current level.

## Baselines

| who | result | source |
|---|---|---|
| Boss (human), 27-Dec-2025 | **9 of 9**, 153 actions, 9 resets | the recording the build was made from |
| Boss (human), 7-Jan-2026 | 6 of 9, 108 actions, 9 resets | trace finding, section 2 |
| 13 agent runs, Jan 2026 (12 are gpt-5-nano gold-agent) | best **2 of 9**; every other run cleared 1 or 0 | trace finding, section 2 |
| fewest possible moves per level | 3, 3, 7, 4, 13, 8, 7, 9, 11 | exhaustive search of the build |
| move budget per level (filling it loses) | 15, 12, 18, 10, 20, 16, 20, 28, 30 | read off the recording |

The January runs were on ARC Prize's original build, not this one. They are a guide, not a
like-for-like comparison.

## Where the source lives

This is a copy. Do not edit it here.

- Canonical: `games/official/as66.py` in `82deutschmark/ARCEngine`, packaged at
  `environment_files/as66/v1/`. Its tests (`tests/games/test_as66.py`) replay the recording
  and check every rule.
- Everything about the game (rules, history, all file locations):
  `docs/reference/arc3/AS66_Lost_Game.md` in `82deutschmark/arc-explainer`.
- To update this copy, overwrite both files from ARCEngine's `environment_files/as66/v1/`.

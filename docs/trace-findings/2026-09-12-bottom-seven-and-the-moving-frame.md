<!--
Author: Claude Opus 5 (Bubba)
Date: 12-September-2026
PURPOSE: The seven weakest games for Qwen3.8-Flash-Next across 163 runs, split by failure
shape; the two of them whose play area scrolls outside the rendered frame (bp35 vertical,
lf52 horizontal) with the camera-offset lines from source; and the risk that the harness's
opening line ("solving a grid-based puzzle game") is a category error for any game in the
semi-private set shaped like a dungeon crawler.
SRP/DRY check: Pass — first corpus-wide per-game doc; siblings are single-game traces. The
64x64 assertion is also flagged in 2026-09-11-priors-vs-the-25.md; here it is the camera, not
the declared grid size, that does the damage.
-->

# The bottom seven, and the two games where the frame moves

Corpus: the 163 runs in `runs-index.json` whose model is
`RadixArk/Qwen3.8-Flash-Next-NVFP4`, restricted to the 25 official games.

## 1. The seven

| rank | game | avg score | levels | avg lvl cleared | % zero | % reach lvl 2 | avg actions |
|---|---|---|---|---|---|---|---|
| 1 | **sk48** | 0.40 | 8 | 0.17 | **84%** | 1% | 146 |
| 2 | **bp35** | 1.03 | 9 | 0.96 | 5% | 1% | 119 |
| 3 | **ls20** | 2.41 | 7 | 0.96 | 13% | 9% | 246 |
| 4 | **g50t** | 2.46 | 7 | 0.61 | **53%** | 13% | 129 |
| 5 | **lf52** | 2.46 | 10 | 1.26 | 2% | 28% | 161 |
| 6 | **wa30** | 2.97 | 9 | 1.17 | 7% | 21% | 284 |
| 7 | **tn36** | 4.15 | 7 | 1.18 | 13% | 28% | 178 |

They are not one failure. They are two:

- **Cannot start.** sk48 scores exactly zero in 84% of runs; g50t in 53%.
- **Always starts, never deepens.** bp35 clears level 1 in 95% of runs and reaches level 2 in
  **1%** — of nine levels. lf52: 98% / 28%, of ten. wa30: 93% / 21%.

**The ranking is confounded by level count.** lf52 clears *more* levels on average (1.26) than
ls20 (0.96) or g50t (0.61) and still ranks below them, because the score divides by ten. Part
of this list is "long game", not "hard game".

### The spend is not the problem

Per-level actions on lf52, from five runs' `actions_per_level`:

| run | L1 | L2 | L3 |
|---|---|---|---|
| `q38-f14-full-qf-r18` | 13 | 108 | **546** |
| `q38-kwbase-long6h-r2` | 11 | 183 | 376 |
| `sym264-w11` | 12 | 260 | 107 |
| `astra-fctx-meta-w7-r1` | 25 | 97 | 161 |
| `astra-grid2-b476-w11` | 13 | **339** | — |

Level 1 costs 11–25 actions. Level 2 then costs 97–339 and usually does not clear. The cheapest
human win on the ARC Prize board is **641 actions for all ten levels** (`Smart Manoj`,
`Peter_Findley`, zero resets; via `POST /api/leaderboards/lf52`). One of our runs spent 546
actions on level 3 alone without clearing it.

So these runs are not quitting early. They are grinding a single level for a large fraction of
what a complete human solve costs, and getting nothing.

Note the budget is counted in a different unit than the run logs: `asqvqzpfdi` increments only
on a committed move (`lf52.py:5255`, `:5313`) and takes a **+20 penalty** at `:5783`, against
caps of 64 / 320 / 640 by level band (`:5749-5758`). Raw action counts and budget counts are
not the same number.

## 2. Two games scroll. The harness never says so.

Of the 25, exactly two move the camera during play. Both are in the seven.

**bp35 — vertical.** `bp35.py:4028`:

```python
self.camera.rczgvgfsfb = (0, self.twdpowducb.grid_y * 6 - 31 - 5)
```

x is pinned at 0; y tracks the player's `grid_y`. The camera follows the player up the shaft.
The game then has to undo its own offset to interpret a click — `:4269`:

```python
kojxiszwpx = self.hdnrlfmyrj.hyntnfvpgl(x, y + self.camera.rczgvgfsfb[1])
```

**lf52 — horizontal.** `lf52.py:5859`, inside `_get_valid_actions`:

```python
xkhfmttedd = [(i[0] - oegtnpbqims.camera.cdpcbbnfdp[0],
               i[1] - oegtnpbqims.camera.cdpcbbnfdp[1]) for i in ahrctkmrda]
```

Screen coordinates are world coordinates minus a live camera offset.

**Control:** ls20 constructs `Camera(width=16, height=16)` over 64×64 levels (`ls20.py:1758`) —
a small window, but nothing in the file ever mutates the camera. It is a fixed viewport, not a
scroller. r11l, sc25, sk48, wa30 and the rest never touch the camera at all.

### Why this breaks the tools specifically

The frame handed to the agent is the camera window. When the camera moves, **every cell in the
frame changes value even though nothing in the world moved.** A frame diff across a scroll step
is a comparison between two different coordinate systems, and it returns "everything changed"
with no error.

The harness has nothing that accounts for this. The prompt asserts a fixed 64×64 board
(`prompts.py`), the per-turn text says "distinguish gameplay change from HUD-only change" with
no third category for *the camera moved*, and the diff helpers (`transitions`, `history`,
`vision.changes()`) are documented purely as frame-to-frame comparisons.

This is the mechanism behind the bp35 turn-2 confusion recorded in
`2026-09-11-bp35-astra-grid2-b476.md`: the agent spent a full turn and five tool calls proving
it had not moved the wrong direction, because it was reading absolute positions out of a frame
whose origin had shifted underneath it.

### And lf52 enumerates its legal clicks, same as sc25

`_get_valid_actions` at `lf52.py:5852-5866` builds coordinate-bearing `ACTION6` inputs for every
clickable cell, already camera-corrected. The solver reads
`game.current_state.available_actions` (ids) instead — see
`2026-09-12-astra-grid2-b476-run-floor.md` §2. That is now **two** of the 25 shipping an exact
answer set that never reaches the model, and in lf52's case the coordinates it drops are the
camera-adjusted ones the agent has no way to compute itself.

## 3. "A grid-based puzzle game" is a claim, and it may be wrong

`tool_agent.py:423`:

> You are a coding agent solving a grid-based puzzle game.

`prompts.py:13`:

> You are solving a multi-level grid puzzle game.

Every game in the public 25 happens to fit. That is not evidence the frame is safe — the public
set is 25 of 135 environments, and the tech report's 55 semi-private and 55 fully private games
are unseen.

The combination is already latent in the public set: **ls20** is room-to-room traversal where
you transform a carried key by walking through tiles, **lf52** is scrolling multi-room traversal
with a cart that ferries you between rooms, and **sk48** is inventory carried on a rod in a
fixed order. Compose those and you have a dungeon crawler — rooms, a moving viewport, an
inventory, a key, and doors that check what you carry. Nothing in the engine prevents it, and
nothing in the public set proves it is absent from the private set.

Why the wording costs something concrete:

- **"Puzzle" implies a static, fully-observable position.** It licenses exactly the behaviour we
  keep measuring: re-derive the whole board every turn, treat the frame as the world, treat a
  solved sub-goal as banked (see `2026-09-12-cn04-weld-vs-pair.md`).
- **It has no word for a world larger than the view.** A player told "puzzle" does not go looking
  for off-screen content. Two public games already have it.
- **It has no word for state you carry.** sk48's rod load, ls20's key shape, r11l's absorbed
  colour are all inventory, and all three are games we do badly at.

Cheapest change that does not overfit to a guess: drop the noun. *"You are solving an unknown
grid-based game. It may be a puzzle, but do not assume it — the board may extend past the view,
you may carry state between rooms, and something you satisfied earlier may no longer hold."*
That is three claims, all true of the public 25, none of which the current framing permits.

## Caveats

- The camera survey is a source read of the 25 public games only. Semi-private and private games
  were not inspected — the dungeon-crawler point in §3 is a stated hypothesis, not a finding.
- lf52's level content is generated procedurally; all ten levels declare `grid_size=(8, 8)` with
  one sprite, so the level geometry in the screenshots was not verified against source.
- `cdpcbbnfdp` and `rczgvgfsfb` are obfuscated attribute names read from usage; they are the
  camera's offset tuple in both files, but the engine-side definition was not inspected.

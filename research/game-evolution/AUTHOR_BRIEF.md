# Author brief: the shared rules every evolution-loop game follows

Author: Claude Opus 5, 19-September-2026. Companion to [README.md](README.md) (the loop) and
[RUBRIC.md](RUBRIC.md) (the scores). Every author agent reads this file. It contains the
technical contract and the quality bar. It contains no other game's design, and an author
must not go looking for one (see "Isolation" below).

## The platform

- **Engine:** `arcengine` 0.9.3 on Python 3.12, the same engine the Games page runs in the
  browser (Pyodide). Read `site-packages/arcengine/README.md` and `OVERVIEW.md` for the API.
  The output is a 64x64 grid of 16 colours; each action returns 1..N frames.
- **One file, one class.** A single `.py` file with exactly one `ARCBaseGame` subclass. It is
  constructed with no arguments and passes `game_id="<id>"` to `super().__init__`. The class
  name is the id with a capital first letter (`fq27` → `Fq27`). Import only from `arcengine`,
  `numpy`, and the standard maths and container modules (`math`, `itertools`, `collections`,
  `dataclasses`, `typing`, `enum`, `functools`, `copy`, `heapq`, `bisect`, `random`). No file,
  network, clock, `eval`, or `exec`.
- **Controls the player has:** arrows/WASD = ACTION1-4 (up, down, left, right), Space =
  ACTION5, click = ACTION6 with screen `x, y` in 0..63, X = ACTION7, R = RESET, and an Undo
  button. Set `available_actions` to exactly the actions your game uses.
- **Deterministic and copyable.** The same inputs always give the same frames. The site's Undo
  deep-copies the game before every action, so the game must survive `copy.deepcopy`. Use
  `random.Random(seed)` if you need randomness at build time, never the module-level functions.
- **Real objects.** Keep game objects as named or tagged sprites in the level, so tools that
  read the engine's object model see them. Don't paint the whole board into one canvas sprite
  from private state. Rule state (positions, counters) lives in your own fields and is rebuilt
  in `on_set_level`, which runs on start, level change, and RESET.
- **RESET runs `step()` too.** After a RESET the engine calls `step()` once with
  `self.action.id == GameAction.RESET`. Complete the action and return without ticking
  anything, or a reset level will not match a fresh one (the skeleton shows the two lines).

## What the player must be able to do

1. **Understand level 1 from the screen.** Level 1 is a tutorial for the one idea: small,
   calm, winnable in at most 10 actions, and impossible to lose by pressing things. A new
   player should make a meaningful move within a minute and win within five, with no text.
2. **Not die right away.** Prefer no terminal loss at all. Mistakes should be harmless,
   reversible, or visibly refused. If a loss is truly part of the idea, show the hazard before
   it matters, show remaining lives, and let RESET retry the current level with earlier levels
   kept. No hidden move limits. Random play must not reach GAME_OVER within its first 10
   actions on any level more than 10% of the time, and never on level 1.
3. **See every consequence.** Every action gets a visible response. A refused action shows a
   small cue at the object that refused (a one-pixel nudge and settle, a brief outline) and
   changes nothing in the rules. A pixel-identical frame after a keypress reads as "the game
   is broken".
4. **Read state without words.** No letters, digits or symbols-as-text on the play surface.
   Encode critical state in at least two of: shape, pattern, position, count, colour, motion.
   No flashing, no timing-based twitch input, no fine motor precision (click targets at least
   4x4 pixels, snapped to cells).

## Animation: intact, short, honest

This is a hard rule; it exists because earlier games shipped embarrassing motion.

- **Rules first, then presentation.** Decide the whole outcome of an action once, then play
  frames that only show it. Presentation frames never tick rules, advance enemies, or change
  counters a second time.
- **Objects move whole.** A moving object is one sprite (or a fixed group) translated by the
  same offset every frame, along the path the rules actually took. It never splits, smears,
  leaves trails, gains or loses pixels, flips its silhouette by tile parity, or cuts through
  a wall on a shortcut. Things that turn or bend follow each real step.
- **Short.** A one-cell move is 2-4 frames. A whole action stays under 12 frames unless it is
  a genuine cascade the player caused (a chain reaction, water filling), and even then under
  30. The site plays about 30 frames a second.
- **Settled.** The last frame of an action is the settled state. Level transitions and RESET
  are instant and distinct from moves.

## Levels

- **Seed (loop step 1):** 3-5 levels. Level 1 teaches the idea; each later level adds one
  real new demand (a new component, rule, constraint, or combination), never just a bigger
  board. A seed may be plain, but not broken, cloned, or cosmetic.
- **Glow-up (steps 3-4):** 7-12 levels. Levels 2-6 each introduce a genuine demand; at least
  two late levels combine three or more earlier demands; no more than two consecutive levels
  are larger instances of the same task. From level 2 on, random play (250 actions, retrying
  after any loss) must not clear a level.

## Files you deliver (in your folder only)

- `<id>.py`: the game.
- `<id>.trace.json`: a winning trace, format `arc3-trace/1`:
  `{"format": "arc3-trace/1", "levels": [{"actions": [4, 4, 2, [6, 31, 20], 5]}, ...]}`,
  one list per level. Use 1-5 and 7 for keys, `[6, x, y]` for a click. Each list must
  end exactly on the action that clears its level.
- `metadata.json`: `primary`, `secondary` (list), `core_verb`, `controlled_subject`
  (avatar | object | cursor | field | network | world | multiple-avatars), `control`
  (keyboard-4dir | keyboard-4dir+action | click | keyboard+click | action-only), `topology`,
  `temporal`, `information`, `objective`, `loss`, `levels`, `visual` (12 words max), and
  `summary` (30 plain words max: what you control, what actions change, what wins).
  Mechanic phrases are short lowercase hyphenated causal ideas, not themes.
- `design.md`: at most one page. The idea in one sentence; what each level adds; how level 1
  teaches it; and what you deliberately left out.
- `vet.json` + `strips/`: the output of the gate below, on your final file.

## The gate you run before you stop

```
python D:/codex-work/arc3-evolution-loop-20260919/scripts/vet_game.py \
  --source <id>.py --trace <id>.trace.json --profile seed|glowup \
  --out vet.json --strips strips
```

The verdict must be PASS. Then open two or three `strips/*.png` and check the motion
against the animation rule above. Also play a few moves the way a stranger would, with
`scripts/play_game.py`, and look at the screen PNG it writes: if you can't tell what
happened, neither can a player. Warnings are allowed at the seed stage. Say which remain
and why.

## Isolation

You author one game. Do not open other games: not `docs/static/games/`, not the local
game store, not other folders under the run directory's `games/`, not the pool catalog.
Don't message other agents. Everything you need about your task is in your prompt and this
brief. If the brief and your prompt disagree, your prompt wins; mention it in `design.md`.

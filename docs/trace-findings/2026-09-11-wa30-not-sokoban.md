# wa30 "Warehouse Allies" — it isn't Sokoban, and the agent's real error isn't thinking it is

**Game:** `wa30-ee6fef47`, 9 levels
**Trace read:** `g4run-sym264-w7-20260906-f8570fe134` — 59 turns, 3 levels, score 13.33
**Source:** `docs/static/games/src/wa30-ee6fef47/wa30.py`

## Distribution

355 runs have played wa30. Best result in the entire corpus is **3 of 9 levels**.

| levels cleared | runs |
|---|---|
| 0 | 154 |
| 1 | 163 |
| 2 | 32 |
| 3 | 6 |

Mean 1.70, median 1.45, max 13.33. The trace read here is one of the six 3-level runs, i.e.
this is the **good** case.

## Ground truth from source

Tags: `wbmdvjhthc` = the player, `geezpjgiyd` = crates, `kdweefinfi` = one faction of
autonomous haulers, `ysysltqlke` = a second faction.

**Crates are carried, not pushed.** `ACTION5` (advertised to the agent as `SPACE`) is
pick-up / put-down:

```python
elif action.id == GameAction.ACTION5:
    if player in self.nsevyuople:          # already holding
        self.kqrtstlzkg(player)            # put down
    else:
        for crate in crates:
            if overlap(player, crate):
                self.xpcvspllwr(player, crate)   # pick up
                break
```

**The same key removes a rival hauler from the board.** Immediately after the pick-up
branch, still inside `ACTION5`:

```python
        for rival in self.current_level.get_sprites_by_tag("ysysltqlke"):
            if vwiozbtqgi(player, rival):
                self.kqrtstlzkg(rival)                       # make it drop its crate
                self.pkbufziase.remove((rival.x, rival.y))
                self.current_level.remove_sprite(rival)      # delete it
                break
```

Stand on a rival, press SPACE, it is gone permanently along with its claim on the crate it
was carrying.

**Two factions with opposing goal sets.** Each faction runs the same loop — if holding a
crate that is on *its* goal, release it; otherwise path toward a goal; if empty-handed,
grab any adjacent unclaimed crate. But they test different predicates:

```python
def shbxbhnhjc(self, v): return v in self.wyzquhjerd    # your goal squares
def ahzqkfjpsc(self, v): return v in self.lqctaojiby    # their goal squares
```

and the rival faction will pick up a crate that is *not already on its own goal* — which
includes a crate sitting finished on yours. **The rivals actively undo your win
condition.**

**Win:** every crate on one of *your* goal squares **and** held by nobody. A crate resting
correctly but still in someone's hands does not count.

**It is simultaneous-move.** Every player action calls `dhrikuybfo()`, which runs both
factions immediately:

```python
def dhrikuybfo(self):
    self.ynmgxjqkgh()   # faction 1 moves
    self.aoeyzovteg()   # faction 2 moves
    self.zzppkjnqgk()   # recolour
```

So the board is never static between the agent's plan and its execution.

## What the agent actually believed

Word-boundary counts over all 347,898 characters of this run's thinking:

| term | count |
|---|---|
| `bot` | **615** |
| `grab` / `grabs` | 284 / 31 |
| `carrying` | 89 |
| `push` | 43 |
| `sokoban` | **2** |
| `ally` / `allies` / `allied` / `rival` | **0 / 0 / 0 / 0** |
| `enemy` / `opponent` | 1 / 1 |

**It is not stuck on Sokoban.** It found carry-and-drop by step 4 and used `SPACE` 77
times. Push appears a third as often as grab. The Sokoban prior is not the failure here.

**The failure is that it models one undifferentiated population of "bots".** Zero
occurrences of ally, allies, allied or rival across 348k characters. It saw the
interference and filed it as weather:

> if a **bot grabs a block I placed in the frame, it would remove it from the frame!**
> Hmm, that could be a problem.

> a **bot removed them** (thinking it was delivering to the frame)

That second line is the agent explaining away adversarial behaviour as a *mistake by a
helper*. The rival was not confused. It was delivering to its own goal squares, correctly,
against the agent.

**It never found the removal move.** 18 sentences put `SPACE` and a bot in the same
thought; every one is about timing, no-ops, or watching the bot move. None consider
standing on one and pressing the key. In a game whose only scaling difficulty is a second
faction competing for the same crates, the agent never used the one action that
permanently deletes a competitor.

## Why the score collapses after level 1

Level 1 is solvable as a puzzle. From level 2 on it is a contested game, and three
assumptions the agent carries forward are all false:

1. **The board is static between plan and execution.** It is not — both factions move on
   every one of your actions. Action counts show the cost: 54 actions on level 1, 62 on
   level 2, **181 on level 3**.
2. **The other movers are helpers or noise.** One faction is, one is not, and the trace
   never separates them.
3. **A delivered crate stays delivered.** It does not, unless the rival that would come for
   it has been removed.

## What would change it

- **Faction separation as an explicit hypothesis.** "Are the autonomous entities one
  population or more than one, and do they have different goals?" is a cheap question and
  the whole game turns on it.
- **Try the interaction key on every entity type, not just on objects.** `SPACE` was known
  from step 4 as pick-up/drop. Nobody tried it on a mover.
- **Re-plan against a moving board.** A plan longer than one action is a bet that neither
  faction interferes, and 181 actions on level 3 is what losing that bet repeatedly costs.

Source references: `yygfcvqoyx()` at line 1188 (action handling, `ACTION5` at 1212),
`dhrikuybfo()` for the NPC turn, `ynmgxjqkgh()` at 1125 and `aoeyzovteg()` at 1155 for the
two factions, `shbxbhnhjc`/`ahzqkfjpsc` at 986/989 for the opposing goal sets,
`ymzfopzgbq()` at 1180 for the win check.

<!--
Author: Claude Opus 5 (Bubba), from Mark's notes
Date: 10-September-2026
PURPOSE: Idea write-up (brainstorm stage, nothing built) for Son to look at: does the LANGUAGE the
agent's instructions are written in change its score, with the instructions themselves unchanged?
Plus Mark's next idea, swapping the letters used for colors in the text version of the board.
SRP/DRY check: Pass -- the only prior language test is two run notes in
scripts/export_runs_index.py (q38-taaf-cap8-zh-*); no write-up of a language experiment exists.
-->

# Idea: does the language of the instructions change the score?

**Status:** idea only, for Son to look at. Nothing built, nothing run.

## The question

Take the setup behind our **latest Kaggle submission**. Keep every instruction exactly the same, but
say it in a different language. Does the score move?

## Mark's calls

- **Start from the latest Kaggle submission,** whichever that is. It's probably *not* the 2.03 one
  (55551321). Son knows which it is.
- **Three languages:** informal German, Gen Z gamer lingo, and Chinese.
- **No new English runs.** We already have plenty of English baselines for our submissions.
- **Kaggle load, on the big cloud cards:** same games, same number at once, same time limit, so the
  scores line up with our normal runs. Not the Mac mini: it's too slow to play a game within the
  time limit, so it would score low from speed alone.
- **Make fresh translations.** Don't go hunting for the old Chinese files.
- **This is our own test.** It doesn't have to copy how the 17-August Chinese test was done.

## What we already know

Son ran a Chinese version once, on 17 August, on the Kaggle 2.03 setup: two runs, 25 games, about
2 h 13 min each.

| Version | Run 1 | Run 2 | Average | Levels solved (both runs) |
|---|---|---|---|---|
| English (14 Aug) | 3.4 | 5.2 | **4.3** | 52 |
| Chinese (17 Aug) | 2.2 | 2.5 | **2.3** | 42 |

Scores are all games except ft09, as usual.

Chinese roughly halved the score, and both Chinese runs landed below both English runs. That test
translated the per-turn note as well as the rulebook.

Also, on 18 August an English test cut the per-turn note to about a sixth of its length. It scored
about the same as normal (4.0). So shorter wording didn't hurt; a different language did.

Source: `scripts/export_runs_index.py`, runs `q38-taaf-cap8-zh-p1/p2`,
`qwen38-taaf-cap8-xhigh-p1/p2`, `q38-taaf-cap8-compact-en-p1/p2`.

## The versions

| Version | What it sounds like | Why it's interesting |
|---|---|---|
| **Informal German** | Casual "du" German, like explaining the game to a friend | A big language the model knows well, just not English |
| **Gen Z gamer lingo** | Still English, but slang: "don't get baited by the timer bar fr", "speedrun it, every extra move is an L" | Tells us whether it's *foreign language* that hurts, or just *not standard English* |
| **Chinese** | Plain Simplified Chinese | Redo the 17-Aug result on the latest setup. Qwen was trained heavily on Chinese, so the drop last time is a surprise worth checking |

## What gets translated

**The rulebook (the system prompt) only.** The note it gets each turn stays in English, so the
rulebook's language is the one and only difference. That was Mark's original ask.

Son may want a second round that also translates the per-turn note, since that's what the
17-August Chinese test did.

**What stays exactly as is,** because the AI has to type these back or match them: code names
(`current_frame`, `action(...)`), action names (`UP`, `MOUSE`), the color letters, and numbers.
Translating those would change what the instructions mean, not just the language.

## How it runs

- The latest Kaggle submission's setup, unchanged except for the rulebook text
- Same 25 official games, same time limit, same number of games at once
- **Two runs per language.** 3 languages × 2 runs = **6 runs**, about 2¼ hours each, which can go in
  one evening.

## What we look at

1. **Score** and **levels solved,** from the usual run records.
2. **What language it thinks in.** Its thinking is saved in the run logs, so skim a few games per
   version. Does the German version think in German? Does Gen Z make it sloppier, or think less?
3. **The old Chinese runs,** skimmed the same way. If it was thinking in Chinese, that may explain
   the drop.

## How to read the results

English runs swing a lot on their own (3.4 vs 5.2 on the same setup). Rule of thumb:

- **Clearly worse:** both runs land below both English runs, like Chinese did.
- **Clearly better:** both runs land above both English runs.
- **Anything mixed:** "no clear difference." Move on.

## Guesses before we run it

- **German:** a small drop, less than Chinese.
- **Gen Z:** close to English. Maybe less thinking per move, since it sounds casual.
- **If Gen Z drops as much as Chinese,** it's "anything unusual throws it off," not the language.

## Maybe later

- Pirate, or Shakespeare, just for fun.

---

# Next idea: the letters we use for colors

Besides the board picture, the AI gets a text version of the board in which each color is one letter
(`W`=white, `R`=red, `b`=blue, `B`=black, and so on). As far as Mark knows, those letters were chosen
more or less arbitrarily.

**Mark's question:** what difference would different letters make?

Not designed yet. Language experiments first. Some directions to talk about:

- **Digits instead of letters** (`0`–`9` plus a few more), the way ARC puzzles are usually written
- **Letters that are harder to mix up.** Right now upper and lower case mean different colors
  (`B` black vs `b` blue, `G` dark gray vs `g` gray, `R` red vs `r` dark red), which may be easy
  to misread
- **Plain symbols** with no color meaning at all (`#`, `.`, `@` …), to see if the letter-to-color
  hint matters

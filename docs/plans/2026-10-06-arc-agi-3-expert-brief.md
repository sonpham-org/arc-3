<!--
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: Write-up of a research line the Boss opened in #arc-3 (6-Oct, 21:38 ET): tell the model it is an
  expert ARC-AGI-3 player and give it a brief (a genre rulebook) on what ARC-AGI-3 games are like, in the
  system prompt and/or injected into user turns. Records why (the model does not know ARC-AGI-3), what we
  already tested in this direction and what came of it, a first draft of the brief, where it could be
  injected, the contamination fence, and the open questions. Nothing here is built or live.
SRP/DRY check: Pass - the system prompt cleanup lives in 2026-10-06-system-prompt-cleanup/; the mechanics
  evidence lives in autoresearch-arena arc3games/LATENT_MECHANICS_IN_THE_PUBLIC_25.md and
  docs/trace-findings/2026-09-13-arm-c-mechanics-possibility.md. This doc points at them, it does not copy them.
-->

# An ARC-AGI-3 expert brief: persona plus a genre rulebook

Status: idea and first draft. Not built, not tested, not live. For the Boss and Son to shape.

## The aim, as the Boss put it (6-Oct, 21:43 ET)

Not overfitting. A generic rulebook of out-of-distribution ideas for the model to try when it is truly
stuck: the tricky mechanics that turn up in the later levels of the public games, and mechanics we suspect
the private games use. It is a list of things to test, not answers about any game. Length is not a worry:
Son notes prefill is very fast on our setup, so a longer rulebook costs little.

Son's concern (21:41 ET): if the rulebook is just the seven hard public games' mechanics, it bets that the
private set looks like them, and unlike the wording ideas it needs a Kaggle submission to judge. Answer in
this design: keep it generic (mechanic families, not game rules), fire it only when the model is stuck, and
judge it first on the Sparks at the stuck levels in the Mode explorer, where it would fire, before spending
a Kaggle submission.

## Why

The Boss asked Qwen 3.8 27B, with our system prompt loaded, what it knows about ARC-AGI-3. It said plainly
that it has no reliable knowledge of ARC-AGI-3 and would not invent any; it only guessed the ARC series might
be moving toward interactive, multi-step tasks. Its training stops before ARC-AGI-3 was public. So the words
"ARC-AGI-3 game" in the persona wake nothing up. If we want to lean into the benchmark (overfit to the genre,
which is fair game), we have to tell the model what the genre is.

The brief is genre knowledge, not answers: what these games tend to look like and how they tend to work,
learned from the public games. It says nothing about any specific game's solution, so it is equally valid on
the hidden evaluation games.

## What we already tried in this direction

1. **Arm C, "mechanics possibility" (Kaggle, 13-15 Sep).** Six lines, each a possibility, not a claim:
   the board may be a window that moves; what you control may change; deciding state may not be drawn;
   order can matter as much as position; a solved thing can come un-solved and parts can act on their own;
   control may be indirect. Best of the eight arms in the September matrix, beat the control on five of the
   seven bottom games, the only arm that looked like a real win. Not decisive (about three standard errors
   on four passes) and never followed up. Write-up: docs/trace-findings/2026-09-13-arm-c-mechanics-possibility.md;
   matrix: bubba-workspace docs/2026-09-15-arc3-kaggle-arm-matrix.md.
2. **The oracle rulebook test (18-19 Sep, old 27B on Cletus).** Full per-game rules for the slippery seven,
   injected at the start. The box was unplugged mid-run; one rulebook pass and two control passes were banked,
   and no comparison was ever written up. Inconclusive by neglect, not by result. Build:
   harnesses/oracle-rules/MANIFEST.md, docs/trace-findings/2026-09-18-oracle-test-*.md.
3. **Skewer Kebabs overfit (21 Sep).** The Boss's full write-up of one game. The model understood all of it
   (win condition, colour order, layout) and still did not act. Later, the board picture alone gave it the
   same understanding. Lesson: a brief fixes comprehension, not the reluctance to act; that needs its own push.

Per-game rulebooks cannot score on the hidden set. The general brief (arm C's direction) can.

## First draft of the brief

Persona line (system prompt, first line):

> You are a coding agent and an expert ARC-AGI-3 player.

Brief (draft; each line comes from what the public games actually do, phrased as what to expect, not as
facts about the game in front of you):

> ARC-AGI-3 games are short interactive grid games made for humans to learn by playing. There are no
> instructions: the controls, the rules and the goal are all found by acting and watching.
> - A game has several levels. Level one teaches a mechanic with a small board; later levels add one new
>   element or twist at a time and combine it with what came before.
> - The goal is almost always shown on the board: a target pattern, a legend, a reference strip, an empty
>   slot or an outline to fill. Look for it before you move.
> - Many games have a step budget drawn as a strip along an edge. Running it out ends the attempt.
> - What to expect, at least once across a game: the visible board can be a window onto a bigger world that
>   scrolls; you can control more than one thing and switch between them; some state is not drawn (what you
>   carry, what you collected); the order of things can matter, not only where they are; a solved part can
>   come undone, and other parts can move on their own; you can control something only through other parts.
> - Clicking games and moving games both exist. One action can mean different things depending on what it
>   is applied to.
> - Humans clear these levels in a modest number of moves once they see the idea. If you are spending many
>   moves without new information, your model of the game is wrong; test a different idea.

Length: about two hundred words. Every claim needs checking against the public games before use (the
"almost always" and "humans clear" lines especially). The Boss decides the wording.

## Where it could go

- **System prompt, once.** Simplest, and the brief is standing knowledge, which is what the system prompt is
  for. Adds a fixed cost to every request but is cached.
- **First turn of the game.** Read once, then carried in the conversation like any other turn.
- **Injected on events, through modes.** The new-level part on the first turn of each level; the "stuck"
  part after a run of moves with no change; the "undone / moving parts" part after a death. This is where
  the Mode explorer fits, and it keeps each line next to the moment it matters. The Boss's idea of injecting
  the rulebook into user turns lands here.
- **Retrieval.** Pick the few brief lines that match what the board shows. Only worth it if the brief grows
  much longer than one screen.

Starting point to propose: persona plus a few lines in the system prompt; the full stuck rulebook injected
whole into the user turn only when the model is stuck (a mode, or a trigger after a run of moves with no
new information), so normal turns stay as they are.

## Fence

- Genre knowledge only. No game names, no per-game solutions, no rule text lifted from one game.
- Held-out games stay out of play and out of the evidence used to write the brief.
- Anything learned from a held-out game does not go in.

## Open questions

- Does the brief help Flash-Next, or only the smaller model? The 27B knew nothing; Flash-Next is untested.
- Does it change the score, or only the reasoning? Skewer Kebabs says understanding alone is not enough.
- Can arm C be re-run cleanly on today's baseline before anything new is added, so we know whether the old
  signal holds?
- Is the oracle run from 18 Sep still on Cletus' disk, and is it worth scoring now?

## How "public wisdom" fits (draft 6-Oct, 21:50 ET; name from Son)

Text: docs/plans/2026-10-06-public-wisdom/public-wisdom.txt. Built from arm C's six possibilities, the nine
latent mechanics read out of the public games (autoresearch-arena arc3games/LATENT_MECHANICS_IN_THE_PUBLIC_25.md),
and general stuck habits. Every line is a mechanic family or a habit, phrased as a possibility with a probe to
run. No game names, nothing from held-out games.

- Stock is untouched. Public wisdom never appears on a normal turn.
- It is injected whole, once, at the bottom of the user turn message when the model is stuck. After that it
  sits in the conversation history, so it does not need repeating; a later stuck stretch adds one line
  pointing back to it.
- "Stuck" for the first test: a human places it with the Mode explorer as a "Public wisdom" mode at the
  stuck levels. If it helps, an automatic trigger comes next (a run of turns with no level progress and no
  new board state, or repeated deaths at the same point).
- First test: on the Sparks, Public wisdom against Stock from the same saved stuck-level starting points.
  Kaggle only if that shows something.

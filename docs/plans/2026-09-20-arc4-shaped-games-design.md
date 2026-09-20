<!--
Author: Mark Barney / Claude Fable 5.1
Date: 20-September-2026
PURPOSE: Design brief for the next batch of synthetic ARC-3 games. These are meant to look
like what we think ARC-4 will be: big worlds behind a small window, long levels, goals you
have to discover. Six games are specified here. This is the document to hand to whoever
authors them in autoresearch-arena/arc3games/.
SRP/DRY check: Pass. LATENT_MECHANICS_IN_THE_PUBLIC_25.md owns the mechanic definitions and
the evidence. This file owns the game designs built on top of them and does not restate
the definitions.
-->

# Six games shaped like ARC-4

## What we are betting on

ARC-4 lands in early 2027. Chollet has not written down what it will be, but from what he
has said in talks we think it will be to ARC-3 what ARC-2 was to ARC-1: the same idea,
stretched. Longer levels. Longer time between doing something and finding out if it worked.
Bigger goals that nobody tells you. Closer to "Claude plays Pokémon" than to a puzzle,
except the game is one nobody has ever seen.

That is a bet, not a fact. Write it down as a bet everywhere it appears.

## The mistake to stop making

Every previous batch turned into Sokoban. The reason is simple: the assistant looked at a
64 by 64 frame and decided that was the world. It is not. It is the window. The engine's
camera can point anywhere in a much larger world, two of the official games scroll, and
one of ours already does. Nothing in the engine is stopping us. The only thing that was
missing was someone deciding that a level is a place, not a screen.

## What we learned from the games nobody could play

The GPT-authored q-series has 84 human plays and not one person ever cleared a level. The
games were inventive and completely opaque. The mechanics were strange enough that a
person could not even guess what to try, and the failure states punished guessing.

The official public 25 went the other way. They were checked to be solvable by ordinary
people, and some of them are honestly a chore to play. They are still solved, because the
verbs are ordinary: walk, push, click, pick up. The strangeness is in what the world does,
not in what your hands do.

That is the recipe. Ordinary verbs. Strange, large, slow-to-reveal worlds. We do not know
whether the semi-private and private sets got the same human check the public 25 did. We
suspect not, and that they are worse. Our games should still be playable by a person,
because a game nobody can finish gives us no human baseline and no training signal.

## The scoring, as far as it matters here

ARC-3 scores an agent against a human baseline on action count, per level, and later
levels count for more: level n counts n times. A game with eight levels rewards an agent
that keeps going far more than a game with three. That is good for us; long games are
what we want anyway.

Do not tune anything to the exact formula. ARC-4 will almost certainly score differently,
possibly in some way we would not guess. Build games that are good regardless of how the
points are counted, and let the harness people worry about the formula.

## Rules every one of these games follows

- The world is at least twice the window on one side. Usually much more.
- Something the win needs is not visible from the starting screen.
- Something carries over from one level to the next: what you hold, what you have unlocked,
  or what you have seen.
- A person solving it makes hundreds of moves per level, not dozens.
- Nothing pushes. If a design's main verb is push, it goes back.
- The verbs stay ordinary. The world is where the difficulty lives.
- No text, no legends, no hints. Same as always.

## The six games

Working names below are for us. Shipped games get opaque ids and nothing else.

### 1. The crawler

**What you see at the start.** A room with a corridor leading off the edge of the screen.
You are a small shape carrying a key. A door nearby has a picture on it that does not match
your key.

**What the world is.** A set of rooms, each about three screens wide, connected by
corridors. The camera follows you. Some floor tiles recolour or reshape the key as you walk
over them. Doors check the key's shape and colour together. Later, you find a second
character standing idle in another room; clicking it moves your controls over to it, and
the first one waits where you left it. Late levels give you a pocket that holds several
keys in a line, and doors that want the keys in a particular order.

**How it reveals itself.** You walk through a tile, your key changes, the door that was
wrong is now right. From there you learn that the floor is the tool. The second character
is found, not announced.

**Why it is long.** Getting a key into the right state can mean walking a loop through
three rooms. Getting two keys in the right order means planning the loop twice.

**Where the agent breaks.** It compares two screens as if they were the same coordinates.
It treats a tile that helped once as always helpful. It never tries clicking the idle body.

**Levels.** Six to eight. Early ones are a single room with one tile type. The second
character arrives around level four. The ordered pocket arrives around level six.

This one is already specified in the mechanics doc as the first thing to build, and no game
in the ledger has been built on the moving-frame axis. Build it first.

### 2. Shrines and seals

**What you see at the start.** Open ground. A coloured wall in the distance. Nothing else.

**What the world is.** An overworld about three screens by three screens. Four small
buildings, each with a switch inside. Each switch dissolves every wall of one colour. The
walls decide which buildings you can reach, so there is an order, and you find it by
getting blocked.

**How it reveals itself.** You wander until you hit a wall, follow it, find a building you
can enter, flip the thing inside, and somewhere far away a wall you never saw is gone.

**Why it is long.** The map is big, the order is hidden, and half your moves are travel.
Between levels the buildings stay where they are but the walls come back in a new
arrangement, so what you learned about the map carries over and what you learned about
the order does not.

**Where the agent breaks.** It has no word for "the thing I did changed something off
screen." It flips a switch, sees nothing change nearby, and decides the switch is broken.

**Levels.** Five or six. Level one has two buildings and one wall colour. By level five all
four buildings and a dependency chain that forces a specific order.

This is the Pokémon-shaped one.

### 3. Seasons

**What you see at the start.** A landscape with water, ice, doors, and a small marker in the
corner that changes every so often.

**What the world is.** A big scrolling map where the rules tick over on a timer measured in
your own moves. Every forty or so actions, the season changes. Ice becomes water. Some
doors become walls, some walls become doors. A bridge exists in one season only. You can
stand still and let time pass, and standing still counts as an action.

**How it reveals itself.** You cross ice, come back later, and fall in. The corner marker is
the only thing that changed. Eventually you notice the marker cycles and the map cycles
with it.

**Why it is long.** A route that works in spring has to be timed against the calendar.
Sometimes the right move is to wait twenty turns.

**Where the agent breaks.** It learns "ice is walkable" and keeps believing it after the
world has stopped agreeing. It never considers waiting as a move.

**Levels.** Six. Two seasons at first, four later, and the last levels shorten the season so
timing gets tight.

### 4. Control room and far bridge (build this one last)

**What you see at the start.** A small room full of switches. One exit, leading off screen.

**What the world is.** The switches together form a number, the way a row of light switches
can spell out a binary value. Each number does one thing somewhere else on a large map:
raises a bridge, opens a gate, turns a platform. The map is several screens away from the
room, and you have to walk there to see whether what you did worked, then walk back to
change it.

**How it reveals itself.** You flip switches, nothing visible happens, you leave, and the
world is different from when you arrived. Eventually you find that particular patterns do
particular things.

**Why it is long.** Every experiment costs a round trip. Learning the switch language takes
many round trips, and the level needs several correct settings in sequence.

**Where the agent breaks.** It cannot connect a cause to an effect a hundred actions later
and several screens away. It gives up on the switches as decorative.

**Why it goes last.** Reading a number off a bank of switches is the kind of symbolic
guess that killed the q-series. Nobody builds this until a person has cleared one of the
other long games. If people cannot clear those, this one gets redesigned, not built.

**Levels.** Six. Level one has two switches and the effect is on the next screen. Later
levels add switches, distance, and settings that have to be applied in order.

### 5. The herd

**What you see at the start.** You, and a handful of small creatures that follow you when
you get near them.

**What the world is.** A big map with gates. Each creature looks the same as the others but
is not: only one of them opens a particular gate far away, and nothing on screen tells you
which. From the second level on, another shepherd is out there gathering creatures for its
own purposes, and it will take yours if they are near it. It is not hunting you. It is
doing its job, and its job wrecks yours.

**How it reveals itself.** A gate opens for one creature and not another. Later, you turn
around and one of yours is walking off with someone else.

**Why it is long.** You have to keep a specific creature with you across a long trip while
another agent keeps interfering, and the route has to be planned around where the other
shepherd goes.

**Where the agent breaks.** It models the rival as a bot that is confused, not as a player
with a goal. It treats the creatures as interchangeable because they look interchangeable.

**Levels.** Six. No rival in the first two. One rival from level three. Two, with different
routes, in the last.

The rival moves by a fixed rule with no randomness. Given the same player inputs it does
the same thing every time. Otherwise a recorded win cannot be replayed to prove the level.

### 6. Cartographer

**What you see at the start.** Darkness, a small lit circle around you, and a tiny grid in a
strip at the top of the screen with one square filled in.

**What the world is.** A large map under fog. As you move, the fog lifts around you and the
tiny grid fills in. The level ends when the grid is complete. Nothing says this. There is
no exit, no key, no door. The only thing that changes as you play is the little grid.

**How it reveals itself.** Slowly. You wander, the strip fills, and at some point you
realise the strip is the point.

**Why it is long.** The map is big, and later levels only count certain kinds of ground, so
you have to work out which cells matter and go find all of them.

**Where the agent breaks.** This is the failure mode our agent is worst at: exploring on
purpose with no reward in sight. It looks for a goal object, finds none, and thrashes.

**Levels.** Five. Small map and every cell counts, then bigger maps and only some cells
count, then a map with dead ends that cost a lot to explore.

## Answers to the first round of questions

**Ids.** The ledger runs g001 to g303 with no gaps, so the six get the next block:

| id | game |
|---|---|
| g304 | the crawler |
| g305 | shrines and seals |
| g306 | seasons |
| g307 | control room and far bridge |
| g308 | the herd |
| g309 | cartographer |

Add all six to the ledger now as `status: "idea"` so the ids are taken, and flip each to
`built` when it lands. Nothing in g500 to g599; that range is reserved.

**Tag.** Every one of the six carries `"series": "arc4"` in its ledger row, and the line
`SERIES: arc4` in the authoring docstring of its `.py` file. Grep for either and you get
exactly these games and nothing else. The contiguous id block is a backup, not the tag.

**Build order.** Crawler first and alone. Then cartographer, then shrines and seals, then
seasons, then the herd. Control room last, and only after a human has cleared one of the
others.

**Branch discipline in the arena repo.** Same rule as here. Branch from `origin/master` in
a worktree, open a PR, never commit on `master`, and leave the uncommitted Kaggle files in
that tree alone.

**The wait problem in seasons** is settled above: every action passes time, and action 5
is an explicit wait.

**The long-session question** is still open and the crawler is the test. If the feedback
site cannot hold a thirty-minute sitting, that is a fix in arc-explainer, not a reason to
shorten the games.

## Two things to sort out before the first one ships

**Checking that a level can be won.** The reference verifier explores every possible state.
On a map this size that will never finish. Instead, each game ships with a written-out
winning move sequence that the verifier replays, plus a check that every region you need
is reachable from the start. Good enough, and honest about what it proves.

That is a change to the verifier rule, not just a new file. The existing games all use
exhaustive search. Land the new rule as its own small change to the arc3games README, and
land it before the crawler's verifier, so the crawler is not the thing that quietly
changed the rule.

**Getting people to play them.** A long game needs a long sitting. Nobody has played a
thirty-minute game on the feedback site, and we do not know whether the session handling
copes. Find out with the crawler before building the other five.

## What to build once, not six times

Camera follow, a room graph, fog, and a minimap strip will show up in most of these. Write
them once as helpers beside `sprite_book.py` so the six games share one implementation and
the packager can inline it the way it already inlines the sprite helpers.

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

Amended: Claude Opus 5, 20-September-2026 -- the four that are next. The crawler is built
and control room is still gated behind a human clear, so shrines, seasons, the herd and
cartographer are the ones being designed now. Each has been revised against what the
crawler's build actually shipped (gear, weight, curses, wardens, send-back) with a rule for
borrowing it, and against two engine facts that were not known when this was written: no
click on a scrolling world, and monotone worlds are the only ones that verify cheaply.
arc3games/G304_HANDOFF.md in the arena repo owns the build lessons; this file does not
restate them beyond what changes a design.
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
- Five actions, and nothing is clicked. You walk onto the things you use.
- What you carry is drawn on the body. No panel, and nothing in a corner of the frame.
- A mechanic borrowed from another game in this series has to change the solve, or it goes.

## What the crawler added, and the rule for borrowing it

The crawler shipped with more than this brief specified. Building it turned up a handful of
mechanics that are worth having in the other games, and they are written here once rather
than in each design:

- **Gear you find and wear.** Boots make rubble walkable, a blade kills the patrol you walk
  into and is spent doing it, an anchor keeps your carried state through a catch. There is
  no pick-up verb: you walk onto a piece and it is yours.
- **The body is the readout.** What you carry is drawn on the avatar -- border, middle,
  corners -- and no panel anywhere says it. Nothing sits in a corner of the frame.
- **Weight, and a carry limit.** The pieces weigh one, one and two, and you carry three, so
  having everything is not an option. Over the limit the world takes two steps for every one
  of yours, which is what slow looks like in a turn-based game.
- **Cursed pieces.** Indistinguishable from real gear on the floor, permanent once taken,
  weight and nothing else. The verifier checks they are twinned with a real piece, never sit
  on a cell a rule reads, and are never required to win.
- **Wardens.** A patrol that never hurts you, kills hostiles it meets, and blocks a body
  that has no blade. Walking into one with a blade spends the blade on the wrong target.
- **Send-back rather than death.** A catch puts you at the last checkpoint you lit, holding
  what you started the level with. What is already open stays open, so it costs a long walk
  and never the run.
- **Inert props.** Things that animate, share colours with live elements, and are read by no
  rule at all. Every game gets them.

**The rule for using any of this in the other four: if deleting the borrow does not change
the solve, delete it.** The worked example is cartographer refusing the overload rule. Being
over the carry limit gives the world a second step, and a second step only costs you because
something is walking toward you. Nothing is walking toward you in cartographer, so the rule
would be decoration there, and it is left out and the limit made hard instead. Four games that all have gear, curses and wardens are four crawler
reskins, `differentiate.py` will say so, and the mechanics doc's own standard convicts us --
if the differentiation loop cannot tell a composition apart from its parents, the composition
was nominal and the design failed. Each design below therefore says what it borrows, what
work the borrow does, and what it refuses to borrow.

Two more rules that came out of the same build and apply to all of them:

- **Five actions, and no click.** The engine's clickable-target list does not subtract the
  camera offset, so on a scrolling world the coordinates offered to an agent are world
  coordinates while the frame is a moved window. Everything in this series is done by
  walking onto it. Where a design wanted a click -- flipping a switch, picking a body --
  it walks onto it instead, or the design changes.
- **A curse must never be the thing that loses the game.** Indistinguishable and permanent
  is fair. Indistinguishable, permanent and fatal is the q-series. The check that g304's
  verifier runs -- twinned, off live cells, never required -- is a series rule now.

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

**Built, 20-September-2026.** Six levels, worlds up to 74x59 cells, routes of roughly 250 to
1000 moves, live as HTML on the arena site and as an ARCEngine build in `dist/`. It shipped
with more mechanics than are described above and without the ordered pocket; both are dealt
with below. Control passes by walking into the idle body or with ACTION5, not by clicking
it -- the paragraph above predates knowing there is no click. It is the only game in the
ledger on the moving-frame axis.

### 2. Shrines and seals (build third)

**Axis.** `delayed-consequence` x `moving-frame-of-reference`. Monotone, so it gets the
cheap exact check rather than replay alone.

**What you see at the start.** Open ground. A coloured wall in the distance. Nothing else.

**What the world is.** An overworld about three screens by three screens. Four small
buildings, each with a plate on the floor inside. Stand on the plate and every wall of one
colour dissolves, everywhere, permanently. The walls decide which buildings you can reach,
so there is an order, and you find it by getting blocked. Nothing on the plate says which
colour it answers for, and the wall it opens is never on the same screen as the plate.

You stand on the plate rather than clicking it. That is not a style choice: a click on a
scrolling world is unresolved in the engine, so this whole series walks onto things.

**What it borrows from the crawler, and why the borrow earns its place.** The send-back. A
shrine you have lit is where a patrol puts you when it catches you, so the shrines are the
puzzle and the checkpoint ladder at the same time, and the reward for reaching one is that
the next attempt starts from there. Delete the borrow and a catch costs the entire walk back
from the far corner of a nine-screen map, which is punishment rather than difficulty.

**What it does not borrow.** Keys, locks, gear, weight. A crawler door tests a value you
carry; a seal here tests nothing at all, it is either standing or gone. Put a key in this
game and it becomes a crawler reskin, and `differentiate.py` would be right to say so.

**How it reveals itself.** You wander until you hit a wall, follow it, find a building you
can enter, stand on the thing inside, and somewhere far away a wall you never saw is gone.
The tell comes on the way back, when a route you walked ten minutes ago is suddenly shorter.

**Why it is long.** The map is big, the order is hidden, half your moves are travel, and the
only way to learn what a shrine did is to go and look.

**What carries between levels.** The buildings stay where they are and the walls come back in
a new arrangement. What you learned about the map carries over; what you learned about the
order does not.

**Where the agent breaks.** It has no word for "the thing I did changed something off
screen." It flips a switch, sees nothing change nearby, decides the switch is broken, and
never goes back to check.

**Levels.** Five or six. Level one has two buildings and one wall colour, close enough
together that the effect is nearly visible from the plate. By level five all four buildings
and a dependency chain that forces a specific order.

This is the Pokémon-shaped one.

### 3. Seasons (build fourth)

**Axis.** `cyclic-time` x `moving-frame-of-reference`, with weight doing the joining. Not
monotone: replay verification only, and budget for that before the levels are drawn.

**What you see at the start.** A landscape with water, ice, doors, and a small marker that
changes every so often. The marker is not in a corner, and it is not the only thing on
screen that changes.

**What the world is.** A big scrolling map where the rules tick over on a timer measured in
your own moves. Every forty or so actions the season changes. Ice becomes water. Some doors
become walls and some walls become doors. A bridge exists in one season only. ACTION5 is
wait, and waiting costs an action like everything else.

**What it borrows from the crawler, and why the borrow earns its place.** Weight, and this
is the one game where the borrow becomes the design. In the crawler, being over the carry
limit gives the world a second step for every one of yours. Here the world's step is the
calendar, so an overloaded body burns the year at double rate. What you carry is therefore
what you can time: the same crossing is a spring walk travelling light and an autumn one
loaded. Delete the weight and the calendar goes back to being an obstacle you wait out.
Keep it and the player is setting their own clock speed without being told they are.

**What else it carries.** Gear that only matters in one season -- something that crosses
water, something that crosses ice -- so choosing what to carry and choosing when to travel
become the same decision. Gear is drawn on the body, as in the crawler. No panel anywhere.
You pick a piece up by walking onto it and leave it by walking onto it again: the game has
no spare verb, because the fifth action is wait.

**How it reveals itself.** You cross ice, come back later, and the ice is water. The marker
is the only other thing that changed. Eventually you notice the marker cycles and the map
cycles with it. The weight rule reveals itself later and harder -- a player who picks up a
third piece finds the seasons turning over twice as fast and blames the map for it.

**Why it is long.** A route that works in one season has to be timed against the calendar.
Sometimes the right move is to wait twenty turns, and sometimes the right move is to put
something down so that twenty turns only costs ten.

**Where the agent breaks.** It learns "ice is walkable" and keeps believing it after the
world has stopped agreeing. It never considers waiting as a move. And it will not connect a
season turning over early to a thing it picked up eighty actions ago.

**Levels.** Six. Two seasons at first, four later, and the last levels shorten the season so
the timing gets tight.

**No curses in this one.** A permanent, undroppable double-rate clock on a timed map is the
q-series failure with extra steps: the player cannot see what went wrong and cannot undo it.

### 4. Control room and far bridge (still last, still gated)

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

**Why it is still last.** Reading a number off a bank of switches is the kind of symbolic
guess that killed the q-series, and the gate on it has not moved: nobody builds this until a
person has cleared one of the other long games. If people cannot clear those, this one gets
redesigned rather than built.

**And one new problem to solve before it can be built at all.** A bank of switches wants a
click, and this series has no click. Walking onto a switch to flip it turns the room into a
route rather than a keyboard, and a route through n switches is not the same puzzle as
setting n switches -- you cannot reach a state without passing through its neighbours. Either
the room is designed as a path problem on purpose, or the engine's click-on-a-moved-window
problem gets fixed first. Do not discover this while building it.

**Levels.** Six. Level one has two switches and the effect is on the next screen. Later
levels add switches, distance, and settings that have to be applied in order.

### 5. The herd (build fifth)

**Axis.** `contested-board` x `moving-frame-of-reference`. `contested-board` is not in
`mechanics.json` yet and has to be adopted before this game's ledger row is written -- see
the arena-repo list at the bottom. `patterned-adversary` is the wrong home for it and the
mechanics doc says why: a patrolling hazard threatens your body and can be dodged by timing,
a rival threatens your objective and cannot be dodged, because it is not aiming at you. The
distinction is what the thing threatens, not how it chooses -- this rival follows a fixed
script, because replay verification needs it to, and that does not make it a patrol.
`real-time-strategy` is the other near miss: that axis wants a world tick independent of the
player, and here the world advances exactly once per player action.

**What you see at the start.** You, and a handful of small creatures that follow you when you
get near them.

**What the world is.** A big map with gates. Each creature looks the same as the others and
is not: only one of them opens a particular gate far away, and nothing on screen says which.
From the second level on, another shepherd is out there gathering creatures for its own
purposes, and it will take yours if they are near it. It is not hunting you. It is doing its
job, and its job wrecks yours.

**What it borrows from the crawler, and why the borrows earn their place.** Two things, both
load-bearing.

The first is the curse's *principle* rather than its objects: identical on the floor,
different in the rules. Crawler curses render as whichever kind of gear they imitate and
there is no way to tell before you take one. The creatures are that idea made into the whole
game. No cursed items here -- the herd does not need them, and shipping them would be the
tourism this series is trying to avoid.

The second is weight, re-read as herd size: every creature following you gives the world an
extra step. Leading the whole herd across the map is slow enough that the rival gets where
it is going first; leading one is fast. Since you cannot tell the right creature by looking,
the cost of bringing them all is exactly what forces you to work out which one it is. Delete
that rule and the answer is always "take everything," and the mechanic the game is about
stops existing.

Note for whoever builds it that this is not the crawler's rule with a different input. The
crawler asks a static question about an inventory you control. This asks a question about a
following herd, which the rival edits: steal a creature and the player's step rate changes
without the player doing anything. `_overloaded(body)` does not port. The rule is the same
sentence and a different mechanic.

**How it reveals itself.** A gate opens for one creature and not another. Later, you turn
around and one of yours is walking off with someone else.

**Why it is long.** You have to keep a specific creature with you across a long trip while
another agent keeps interfering, and the route has to be planned around where that agent
goes.

**Where the agent breaks.** It models the rival as a bot that is confused rather than a
player with a goal. It treats the creatures as interchangeable because they look
interchangeable. And having never been stolen from yet, it plans as though it never will be.

**The rival.** Fixed rule, no randomness: given the same player inputs it does the same thing
every time, or a recorded win cannot be replayed to prove the level. The patrol arithmetic in
the crawler section below is about this game specifically -- a rival parked on a gate, or on
the creature you need, blocks it for as long as it stands there, which is a stall and not a
puzzle. That check goes in before the levels are drawn, not after.

**Levels.** Six. No rival in the first two. One rival from level three. Two, with different
routes, in the last.

### 6. Cartographer (build next)

**Axis.** `occlusion-and-fog` x `moving-frame-of-reference` x `resource-economy`. Monotone --
fog lifts, cells count, nothing un-counts -- so it can be checked exactly and cheaply, which
is half the reason it goes next.

**What you see at the start.** Darkness, a small lit circle around you, and a tiny grid with
one square filled in. The grid runs along one edge of the frame, and which edge is a fact
about the level rather than a constant. It is never in a corner.

**What the world is.** A large map under fog. As you move the fog lifts around you and the
tiny grid fills in. The level ends when the grid is complete. Nothing says this. There is no
exit, no key, no door. The only thing that changes as you play is the little grid.

**What it borrows from the crawler, and why the borrows earn their place.** Gear and the
carry limit, as a straight trade between seeing and reaching.

- Boots and rubble. From level three, part of the map is ground a bare body cannot cross,
  and some of the cells that must be filled are behind it. Delete the boots and those levels
  are unwinnable, which is what load-bearing means.
- A lantern that widens the lit circle. It fills the grid faster per step, and it weighs
  enough that you cannot also carry the boots. That is the whole choice -- see more, or
  reach more -- and it is a choice the crawler never asks, because the crawler's limit is
  about keys and blades.

**What it deliberately does not borrow.** The overload state. In the crawler, being over the
limit gives the world a second step, and a second step only costs you because something is
walking toward you. Nothing is walking toward you here, so that rule would be decoration.
The limit is hard instead: a body carrying two pieces cannot pick up a third. Writing this
down rather than shipping a rule that does nothing is the point of the delete test.

**How it reveals itself.** Slowly. You wander, the grid fills, and at some point you realise
the grid is the point.

**Why it is long.** The map is big, and later levels only count certain kinds of ground, so
you have to work out which cells matter and then go and find all of them.

**Where the agent breaks.** This is the failure mode our agent is worst at: exploring on
purpose with no reward in sight. It looks for a goal object, finds none, and thrashes.

**Levels.** Five. Small map and every cell counts, then bigger maps and only some cells
count, then a map with dead ends that cost a lot to explore. The lantern from level two, so
the trade is learned before it is needed; boots from level three.

**Why it goes next.** It brings the last two shared helpers the series needs -- fog and the
minimap -- and it is monotone, so it can be verified exactly instead of by replay alone.
Write the helpers here, for the four games after it.

**Built, 20-September-2026, and four things about it differ from the paragraphs above.**
Five levels, 35x24 up to 66x44 cells, covering routes of 205 to 737 moves. What changed:

- **There is no third piece of gear and the carry limit is not "cannot pick up a third".**
  Two pieces, both weighing two, and a body that carries three, so it holds one or the
  other and a station swaps them where they lie. A third piece had no work to do and would
  have failed the delete test, so the sentence above is wrong and the game is right.
- **The axis is not `resource-economy`.** That axis is a finite, spendable, non-renewable
  budget, and nothing in this game is spent: stations are never used up and the fog never
  falls back. The gear is `tool-composition` with the sign flipped -- the win needs both
  capabilities and the body can never hold both -- and no axis in `mechanics.json` covers
  abilities that exclude each other. It is written up as a proposal, not assigned.
- **The lantern is required, not a speed-up.** Some counted ground is sealed inside the
  stone, two cells from anywhere a body can stand: pale ground you can map and never walk.
  A bare body's light does not reach it and the lantern's does. So the trade the design
  promised is a hard requirement on both sides -- boots for the ground past the rubble,
  lantern for the ground behind the wall -- and never at the same moment.
- **Level five forces the swap the others only offer.** A lantern and a boots station
  stand inside a boots-only region with ground only visible from in there: walk in booted,
  change where the lantern lies, map it, change back, walk out.

**The verification paid more than this brief expected.** Monotone was the right call and it
bought more than a cheap check: every counted cell is shown lightable by some reachable
body, so each level is winnable *by construction* rather than because a route happened to
win; no dead end exists, computed over the condensation of the movement graph rather than
argued; and it carries a Part B foil -- a policy that walks to every object on the map and
stops -- which loses on all five levels. Two of the three gaps g304 shipped with are closed
for this game. The replay sits on top of that and proves the shipped rules are the rules
that won.

**Two traps for shrines, seasons and the herd.** Both cost time here and both were caught
by checks written before the levels, which is the rule this brief already states.

*An ability gate pair can make a level unwinnable in one line.* Ground behind wall needs
the lantern; ground past rubble needs the boots; ground behind wall *inside* a boots-only
region needs both at once and cannot be done. Two levels shipped that way and were caught,
from measuring against what a booted body can reach instead of a bare one. Any game in
this series with two exclusive abilities has this bug available to it.

*A seal seals nothing if the rooms have already grown into each other.* Rubbling every
corridor into a region did not cut it off, because the generated caves touched across
their shared boundary. Shrines and seals is the same shape of problem with walls instead
of rubble, and it will land there too.

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

Correction, 20-September-2026: the packager cannot do that yet. `make_submission.py` splices
in `sprite_book.py` by name and opens exactly that file, so a second helper module would work
while authoring and be missing from the packaged build. The crawler therefore carries its own
camera follow and room lattice. Cartographer is where the helpers should be written, and the
inliner has to be taught about more than one module first. See the arena-repo list at the
bottom.

## What building the crawler taught, 20-September-2026

g304 is built, verified and live on both surfaces. Five games remain. These are the
things that cost time, written down because they will repeat.

**Patrols that are meant to meet each other almost never do by accident, and the
arithmetic that makes them meet will put the meeting in the wrong place.** A vertical
patrol at `(wx,wy)` meets a horizontal one at `(hx,hy)` exactly when `wx-hx == hy-wy`,
and they meet on `(wx,hy)`. The obvious offsets put that cell on top of whatever the
puzzle uses. This matters most for **the herd**, whose rival shepherd is specified to
move by a fixed rule: a rival parked on a gate or a creature you need blocks it for as
long as it stands there, which is a stall rather than a puzzle. Check it rather than
eyeball it.

**Anything a player can be blocked out of needs a check that it is not blocked
permanently.** Two separate faults in g304 were of this shape and neither was visible in
a diff: a door that covered one cell of a two-cell hall could simply be walked around,
and a room joined by a mis-declared link was connected to nothing at all, stranding a
tile no route could reach. Both now have gates in the verifier. Write those gates for the
next game before the levels, not after.

**Keep every state-changing thing monotone if you possibly can.** The crawler's rune
gates light permanently rather than toggling, and that single decision is what makes its
verification exact and cheap: with control passing from anywhere and everything else
monotone, each body's reach can be settled alone and the coupling is only the set of
things opened. A toggle is the better mechanic and tr87's name points straight at it, and
it also turns a few thousand states into about a hundred million. If a game needs
toggles, budget for a different verifier rather than discovering this late.

**Verification here is replay, not exhaustion, and should be labelled as such.** Each
level ships a recorded winning action sequence that replays through a fresh engine. That
proves the level is winnable and that the shipped rules are the rules that won it. It
does not prove no dead end exists, and none of these games yet carries a Part B foil.

**Two engine facts worth knowing before designing.** `Level.grid_size` must be left unset,
because the engine resizes the camera to it and the camera refuses anything over 64 — a
world larger than the window cannot be declared that way. And the engine's clickable-target
list does not subtract the camera offset, so on a scrolling world the coordinates offered
to an agent are world coordinates while the frame is a moved window. The crawler therefore
has no click at all. Any of the remaining five that wants one needs this resolved first.

**On the long-session question.** The crawler is playable on `arena.sonpham.net` with
anonymous telemetry running, so the gate below is now answerable. Getting the answer needs
people to play it, which has not happened yet.

## What has to happen in the arena repo before the next one lands

Five jobs, none of them big, all of them cheaper now than after four more games exist.

**Adopt `contested-board` into `mechanics.json`.** Only `moving-frame-of-reference` was taken
from the nine when the crawler landed. The herd needs `contested-board`, it is already
written in that file's schema in `LATENT_MECHANICS_IN_THE_PUBLIC_25.md` against wa30, and if
the row gets written before the axis exists the game gets filed under `patterned-adversary`,
which is the boundary that doc explicitly rules out. Adopt it the same way -- with the
reverse boundary onto `patterned-adversary` and `real-time-strategy` -- before g308 is built.

**Teach the packager to inline more than one module.** `make_submission.py` splices in
`sprite_book.py` by name: it matches `node.module == "sprite_book"` and opens exactly that
file. A new helper module beside it would work while authoring and vanish from the packaged
build. So the shared camera-follow, room-lattice, fog and minimap helpers cannot simply be
written to a new file -- either the inliner takes a list of modules, or the helpers go into
the book. Fix the inliner first; it is a smaller change than the four games that depend on it.

**Commit the HTML-to-Python export script.** The playable HTML build is the source of truth
for level data and the engine build's specs are generated from it. That generator currently
exists only inside the history of a commit message, and the two builds have already drifted
apart once and been reconciled by hand. Four more games doubles that risk.

**Write the not-permanently-blocked checks before the levels, not with them.** Both faults
the crawler shipped and then caught were of this shape and neither showed up in a diff. The
herd's rival will produce a third variety of the same bug.

**Say out loud that the crawler shipped three of its four named parts.** The composition in
the mechanics doc is moving-frame, carried-attribute-transform, ordered-carriage and
control-transfer. The built game has the first, second and fourth: the rune gates want a
set of runes lit, in any order, so nothing in it is ordered carriage. That is a fine game and
an honest gap. Either the ordered pocket goes in on a later pass, or the claim gets corrected
to three parts. It should not sit uncorrected while four more games are written on top of it.

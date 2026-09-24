<!--
Author: Claude Fable 5.1, for Son Pham
Date: 24-September-2026
PURPOSE: Son, 24-Sep: "What kinds of harness will allow us to solve really hard games? ... review the
trace and understand what kind of traps the harness tends to fall through, before devising. And ... look
into the official Astra agent moves to see how it was actually solved." This is that review: Astra's
published recordings on the hard seven (arcprize.org/api/recordings), our own transcripts on the same
games from last night's one-wave arms, the traps they show, and the harness design that follows.
SRP/DRY check: Pass. Run numbers live in 2026-09-24-harness-by-game.md and the cv5-cr-clock README
(cited); this doc holds only trace evidence and the design. Astra recordings are under
D:\codex-work\_astra (JSONL + extracted reasoning), our traces under D:\codex-work\_traces (timeline.py
and digest.py produce the compact views quoted here).
-->

# Solving the hard games: what Astra does, where we fall, what to build

## 1. Ground truth: how GPT-6 Astra actually plays the hard seven

Astra's recordings carry every action and a reasoning summary per step. Provider-adapter harness, HIGH
effort (the 99.9 % configuration):

| game | result | actions per level (first → worst) | the mechanic, in its own words |
|---|---|---|---|
| tn36 | 7/7 in **134** actions, all clicks | 10 → 44 | toggle bits program a piece's move sequence; a "run" disk executes it; re-run/edit cycles on levels 5–6 |
| sk48 | 8/8 in 434 | 14 → 103 | a rod that extends/retracts and lifts beads; beads dock on vertical rails only under specific geometry; ACTION7 = undo; clicks select |
| ls20 | 7/7 in 469 | 20 → 99 | push a patterned block to a goal, match its orientation, an energy budget per level, rings refill; dies once, RESETs, re-plans the route to the exact energy |
| g50t | 7/7 in 297 | 24 → 64 | switches advance a blocker along a wire one notch per action; tries one, sees the coupling, RESETs immediately |
| wa30 | 9/9 in 585 | 31 → 111 | five action types incl. SPACE; long sequences |
| bp35 | 9/9 in 489, 6 RESETs | 15 → 114 | platformer; clicks build/destroy blocks; overhead hazards |
| lf52 | 10/10 in 771 | 8 → 145 | 383 clicks + 4 directions; levels 5–10 need 90–145 actions each |

Same model, **standard** harness (a text note carried forward instead of hidden state): sk48 4/8 in 734
actions (454 of them on level 4, four RESETs); ls20 7/7 in 862 (321 on level 6). Its note is a complete
formal state every step, e.g. *"Arm y15/end38; beads 9@26, 14@32, 8@38; loose 12@(38,33). Retract past 8
to test whether it stays on its vertical rail. Targets: x26=[9,14], x38=[8,12]."*

Five behaviours, all of which are harness-shaped rather than model-shaped:

1. **One action per decision, always.** Zero batches. Each action is a probe of one hypothesis or one
   step of a verified plan, and the next frame is read before the next action.
2. **A running formal state**: coordinates of every movable object, the tool's reach, and the targets
   as sequences. Plans are computed on that state, not narrated.
3. **A hypothesis ledger with single-variable tests**: "clicking 8 caused no visible change; test
   whether it selected the bead by moving right" — one variable per action, outcome recorded, the
   untested controls enumerated when stuck (click bead → click hub → click rail → ACTION7 → geometry).
4. **RESET as a tool**: early and deliberate (g50t step 7, ls20 after one death, bp35 six times), then a
   full re-plan from the formal state.
5. **Goal spec extraction first**: every level starts with "what does solved look like" written down
   (target sequences, goal cell, orientation), and progress is checked against it.

The provider-adapter gap (62.7 → 99.9 %) is the same lesson at the model layer: keeping the working
state intact between actions mattered more than reasoning per action.

## 2. Our traces on the same games: the traps

Sources: the one-wave hard-seven arms (exec, solver, symbolic, selfcheck, execution_v2, memory_v2),
hard7-264 and cv5cr264, transcripts digested to one line per tool call (`_traces/*/*.timeline.txt`).

**tn36, three runs of the same base harness.** exec cleared 5 levels (167 calls); memory_v2 cleared 4
with the best tn36 score ever (32.5, 151 calls); execution_v2 cleared **0 in 1,315 actions** (211
calls). All three found the toggles within ~15 calls. The difference is one probe: exec clicked the blue
ball on call 8 ("a white line connecting to the blue ball… click the ball") and saw the animation that
reveals the program runs; memory_v2 clicked it on call 31; execution_v2 **never clicked it**. Instead it
locked onto "the timer bar is a step budget, the toggles are a combination lock", and spent the whole
132 minutes enumerating all 1,024 toggle configurations with a Gray-code walk, timing out the sandbox,
fighting its own store, and reporting coverage percentages to itself. Astra clicked the run disk on
step 2. → **Trap 1: hypothesis lock-in before the control inventory is exhausted.**

**sk48, hard7-264 (0 levels in 1,397 actions, 404 calls, 264 minutes).** The model derived the rod/hook
mechanic correctly by call ~32 (push, hook at max extension, vertical drag while hooked — the same
physics Astra describes). It then assumed the goal was "pack the three blocks into a column on the
left", tested every arrangement, and never read the HUD legend as the target ordering, which is what
Astra's "Targets: rail 11 needs 8→12" is. When arrangements ran out it decided to **drain the timer bar
to force a level reset — for two and a half hours** ("Bar ~19. Continuing.", 60 calls of drain), because
RESET was not in its action list. → **Trap 2: no goal-spec extraction; Trap 3: brute force as the
fallback; Trap 4: RESET unavailable, so a reset costs hours.**

**Recurring, every game:**

- **Trap 5 — API relearning after compaction.** Every run's first 4–8 calls are `pixels` is an int not a
  list, `.ascii` is one flat string, `difflib` is not allowed, `action([...])*2` does not repeat. exec
  relearned all of it again at call 51 after level 1 because the compaction dropped the knowledge. That
  is 5–10 % of every game's calls and it recurs after every context rotation.
- **Trap 6 — throughput management displaces thinking.** 30 s sandbox timeout, 3–4 s per action under
  7 lanes, the 14-action cap, animation pauses. execution_v2 spent ~40 of 211 calls on "timeouts are
  eating 30 s each… use 6 actions per snippet… the save didn't happen". hard7-264's sk48 the same. The
  model is optimising a pipeline it should not be able to see.
- **Trap 7 — memory that fights back.** `remember()` rejections (`memory_update_rejected`, "invalid plan
  action fields", "goal must be ≤180 chars") cost 3–6 calls per game in every memory arm, and a game-over
  restart bumps the epoch and clears it ("Memory got wiped?!"). memory_v2's model gave up on memory at
  call 134 and solved level 4 without it.
- **Trap 8 — state confusion after batches.** "I'm confused again", `previous_frame` is the frame before
  the *last* action of a batch, the image and the ASCII disagree in the model's reading, blocks reported
  in the wrong row three calls running (sk48 h7-264 calls 83–89). Batches hide the transition the model
  needed to see.
- **Trap 9 — the win condition is checked by the score, not by the model.** Nothing in the loop asks
  "what would the frame look like if this level were solved"; runs discover the goal by accident (exec
  tn36 call 50: "all-dark + all-dark gave 5 downs → arch into the cup → level advanced!").

What we are good at, and should keep: once the mechanic *and* goal are known the harness executes
efficiently (compaction v5 keeps the derived model through 60+ minutes; exec's lease and selfcheck's
`expect()` both verified plans cheaply; symbolic search solved ls20's route budget in one call). The
losses are all in the *discovery* phase.

## 3. The harness for hard games: "probe mode"

A distinct mode the router (program item 5) switches on when a game is in the B/W regime (no level
after ~100 actions, or a known-hard id). It changes the loop, not the model.

| component | what it does | trap it closes | cost |
|---|---|---|---|
| **A. Control inventory** (host) | segmentation → one row per distinct object/glyph class; each row has `probed: no/yes → effect`. The prompt shows the table every turn. The host refuses to enter any batch or sweep while an object class is unprobed. | 1 | tiny |
| **B. Goal spec slot** (host-enforced) | before the first non-probe action of a level the model must write `goal: {what changes, where, how checked}` in the state block; the host renders it every turn and asks for a re-check at every score/level event | 2, 9 | tiny |
| **C. Single-step mode** | action cap 1 while `mechanic_confirmed: no`; the host shows the diff (changed cells, moved objects) after every action, so `previous_frame` confusion disappears. Batches ≤ 8 only once the model's predictor (v2 `predict`/`step`) is verified on ≥ 3 transitions — the paper's verification gate, but as the *entry* condition for batching, not a penalty afterwards | 3, 8 | more turns per action; fine on a 132-minute single game |
| **D. RESET as an action** | expose RESET when the engine offers it; the prompt says when it is cheap (known mechanic, bad state) | 4 | none |
| **E. Formal state block** (host-rendered, model-written) | one JSON the host keeps and re-renders each turn: objects with coordinates, controls table, live/dead hypotheses with the test that killed each, goal spec, plan. Replaces free-text `confirmed_rules`; survives compaction and level restarts (no epoch clearing) | 5, 7, 8 | ~600 tokens/turn |
| **F. Sandbox conveniences** | `grid` (list of lists), `rows` (ascii lines), `diff(a,b)`, `objects()`; the API cheat-sheet pinned in the tool description; timeout raised or actions made non-blocking with the host applying them after the snippet | 5, 6 | none |
| **G. Hypothesis ledger** | the v2 `rule()` primitive, kept: every mechanic claim is a predicate over one transition, replayed each turn; the host reports revocations. What Astra does by hand | 3 | tiny |

Two things this deliberately does *not* do: it does not add a bigger world-model machinery (the
ablation paper found executable models the weakest piece, and our symbolic arm only paid off on ls20),
and it does not change the model or the thinking mode. It makes discovery a procedure the host runs.

Expected effect, from the traces: tn36 execution_v2 would have clicked the ball inside its first 15
actions (A), sk48 h7-264 would have written "targets = HUD order" at level 1 (B) and reset in one action
instead of 160 (D), every run gets 5–10 % of its calls back (F). The games where nothing changes are the
ones where the model cannot form the right hypothesis at all (sk48 level 4+ for Astra's standard
harness too); those are model-limited and are where thinking effort, not harness, is the lever.

## 4. Verification plan

Build it as `patch_probe.py` on the cv5-CR base (host-side state block + sandbox conveniences + single-
step cap + RESET exposure; constant-only prompt edits so the selftest identity test holds), run it on
the hard seven one-wave 132 against last night's ladder (base control → solver / exec / symbolic /
selfcheck / v2 arms), then score it on the 25 with the router deciding when it is on. Success criterion:
levels on tn36 / g50t / wa30 / bp35 ≥ the best single-arm result on each, and no game with 0 levels after
1,000 actions.

## Appendix: last night's ladder on the hard seven (7-game mean / levels / actions)

solver 9.13 / 17 / 3,440 · exec 8.32 / 19 / 2,857 · symbolic 8.29 / 14 / 3,247 · selfcheck 7.70 / 16 /
2,712 · memory_v2 6.70 / 14 / 2,549 · memory 5.46 / 12 / 3,692 · hard7-264 (base, 264 min) 4.96 / 15 /
7,235 · execution_v2 4.47 / 11 / 3,578 · baseline control and symbolic_v2 running (24-Sep).

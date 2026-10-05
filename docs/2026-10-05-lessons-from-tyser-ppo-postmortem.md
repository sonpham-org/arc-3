# Lessons for ARC-3 from Keith Tyser's three-competition PPO post-mortem

Written 5-Oct-2026 by Bubba (Claude Opus 5.5) at the Boss's request.
Source: <https://keithtyser.com/blog/three-simulation-competitions-three-ppo-mistakes.html>
Keith Tyser (Kaggle: ktyser) competes against us in ARC-AGI-3. He published the "Duck Qwen3.8 Flash Next
NVFP4 MTP" notebook. He wrote this post about Orbit Wars (bronze), the Pokémon TCG AI Battle (silver) and
Kaggriculture (silver range, still being scored). We were also in Kaggriculture.

## His mistakes, one per competition
- Orbit Wars: he built a very fast simulator, but it simulated a different game. It had shorter games and
  no comets until late in the run, and parity was tested on only 11–23 steps. His evaluation used two games
  per opponent. The optimizer metrics looked fine, and the agent never got strong.
- Pokémon: he picked the largest model that fit the submission limit (300M). It got roughly 200x less
  experience than the Orbit Wars winner. A thread-local `torch.set_grad_enabled` bug made every network
  submission fall back to option zero until 28-Jul. The same file submitted five times scored between
  731 and 1,004.
- Kaggriculture: he had the right model size, but primitive actions (about 18,000 decisions per game).
  The behaviour-cloning model was 86% accurate per decision and won zero games against strong bots.
  PPO reached 98% on his own panel, but the ladder did not follow, because his panel was too close to
  his training pool. His best result was a hybrid: PPO for the early game, then a teammate's planner.

## What applies to ARC-3
1. **Score the exact package in the real harness, at real timing.** His worst failure was a silent
   harness bug. Ours, the pruned 336g line on 2-Oct, passed every public-set test and still scored 8.14
   and 3.93 on Kaggle. Every model or harness change gets a competition-shape run before it is submitted.
2. **One run is noise.** His same-file spread matches what we see on Franzen's notebook (27.62–31.47).
   This is the reason for the repeat-pass yardstick in Sprint 1. Never promote a change on one pass.
3. **The held-out set must really be held out.** His panel was too close to his training pool and gave
   him false confidence. Our test-only games (held-out copycats and recolors) must never enter training,
   and the RL page's held-out panel is the number that counts, not the train/hard panel.
4. **Per-step accuracy does not predict wins.** Judge Son's training rounds by whole games played,
   levels and score, never by loss or imitation accuracy. Train on winning runs, and on the actions that
   actually changed the board, not on wasted or no-op actions. (The 3rd-place Kaggriculture team trained
   on executed actions only.)
5. **Do not make the model learn what a rule can do exactly.** Every top Kaggriculture team put a rule
   or planner under the network. For us that is harness work: anything mechanical (bookkeeping, exact
   coordinates, undoing known dead ends, spotting a rotated or mirrored level) belongs in the harness,
   not in the model's head. Check that the abstraction can express what winning runs actually did
   before relying on it.
6. **Size the model for the training budget, not for the limit.** The question for Son's cut-down
   model is "what can we train to convergence before 2-Nov", not "what is the biggest model that fits".
7. **Throughput last.** Faster serving only helps after points 1–6 are right.

## Second reading: his "next competition" list is his ARC-3 playbook (Boss, 5-Oct)

The first reading above treated the post as general advice. The Boss's correction: the closing section,
"What I will do in the next competition", describes what Keith is doing now, in this contest. Read that
way, it tells us what our competitor will build in the last four weeks.

**Where he stands (our leaderboard poller, 5-Oct).** Team `keithtyser`, rank about 39, 32.74, 98
submissions. That puts him in silver and close to the gold line (about 34). His climb: about 12 on 30-Sep,
26.71 on 1-Oct (the day Franzen's notebook went public), 29.42 on 3-Oct, and 32.74 overnight 4–5-Oct. He is
working on top of the Franzen base and still gaining, while we sit at 28.94.

**His seven rules, translated to ARC-3, and what he will likely do with each:**

1. *Representation and action space first.* In ARC-3, "what the network sees" is how the harness shows
   the frame to the LLM: the grid text, images, frame-to-frame diffs, and what is flagged as changed. "What
   it selects" is the action set: the arrows, the action keys, RESET, and clicks on exact coordinates. His
   Kaggriculture lesson was to keep mechanical execution out of the model and to check that an abstraction
   can express what winners actually did. Expect him to change the harness here: object-level frame
   descriptions, click-on-object instead of raw coordinates, move-to macros run by a path rule, and
   automatic flagging of actions that changed nothing. **This is the biggest harness lever, and we have not
   done this audit.**
2. *Clone winners, the actions the engine executed, and select checkpoints only by full games.* For him,
   "winners" means winning game traces. We already hold the best version of that data: every level of the
   public games and our copycat and recolor copies has a verified winning line, replayed to WIN through the
   offline loader (48 solution files under datasets/copycat-games). That is perfect teacher data with only
   executed actions. It is also exactly what rule 1 says to check an action abstraction against.
3. *Size the model for the training budget.* He has already published both a 27B FP8 notebook and a
   Flash Next NVFP4 + MTP notebook, so he has measured the speed and size trade-off on Kaggle. Expect him
   to fine-tune whatever he can train to convergence by 2-Nov, not the biggest model.
4. *No datacenter needed.* He trains at home on two RTX PRO 6000 cards. **Kaggle's ARC-3 machine is an RTX
   PRO 6000** (Franzen's notebook metadata, `machine_shape: NvidiaRtxPro6000`). So he can rehearse the exact
   package on the exact hardware every day. We rehearse on the DGX Sparks, which are different hardware with
   different speed. Under rule 6, that gap is his Orbit Wars mistake: practice that does not match what is
   scored.
5. *Diverse opponents; keep some out of training.* The ARC-3 analog is a diverse pool of games, with some
   held out. He has only the public games plus whatever he builds. We have a game-authoring pipeline
   (autoresearch-arena arc3games), the authored games, copycats, recolors and test-only games. This is an
   edge for us, if Son's training actually uses it and the held-out set stays clean.
6. *An evaluation you trust.* That means paired seeds, a fixed panel, and the exact package near the real
   harness. Ninety-eight submissions suggest he uses repeat submissions to measure the noise he described
   (731–1,004 on one Pokémon file).
7. *Throughput last.* His public notebooks were throughput work (quantisation, MTP). By his own rule, his
   next moves are rules 1–2, not more speed.

**What this changes for us:**
- Add a harness item now: audit representation and action space against the verified winning lines.
  For each winning line, sort the steps into mechanical steps a rule could do exactly (moving to a
  location, clicking a known object, undoing a dead end) and real decisions. Then measure how often our
  model wastes actions on the mechanical part in its traces. Build harness macros only where the audit
  shows real waste, and confirm each macro can reproduce the winning lines.
- Give Son the winning lines as clean teacher data (executed actions only), keeping test-only games out.
- Close the rehearsal-hardware gap: final candidate packages get a run on Kaggle's own hardware (a
  notebook save-run at competition shape) before they count, not only a Spark run.
- Expect Keith to move into gold contention late. He is the kind of competitor who turns a post-mortem
  into a plan.

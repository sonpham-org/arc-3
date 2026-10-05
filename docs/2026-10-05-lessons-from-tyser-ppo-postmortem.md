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

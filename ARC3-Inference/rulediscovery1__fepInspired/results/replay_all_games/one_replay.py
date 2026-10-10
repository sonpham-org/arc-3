"""
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: Replay ONE saved ARC-3 play through OpenMind's rule-discovery agent (rulediscovery1__fepInspired,
  offline mode, CPU only) and print what it learned: the top rule sets with posterior weights, the
  surprise spikes, and goal guesses. Asked by Son Pham in #experimentalmessing (06-Oct-2026 20:48 ET):
  "Do it for a replay we have, and show me some example rules". Uses offline_eval's machinery unchanged.
  Usage (from ARC3-Inference/): python3 ~/bubba-workspace/scratch/fep_replay/one_replay.py [--game ls20] [--n 77]
SRP/DRY check: Pass - reuses offline_eval / beliefs / hypotheses; new is only the printout.
"""
import sys
from rulediscovery1__fepInspired.agent import AgentConfig
from rulediscovery1__fepInspired._distill import oe, ebul_perception as ep
from rulediscovery1__fepInspired.perception import Perceiver
from rulediscovery1__fepInspired.beliefs import BeliefState
from rulediscovery1__fepInspired.rules import ContextBuilder
from rulediscovery1__fepInspired.goals import GoalBeliefs
from rulediscovery1__fepInspired.hypotheses import HypothesisProposer

want = sys.argv[sys.argv.index("--game") + 1] if "--game" in sys.argv else None
n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 77
NICK = oe.load_nicknames() if hasattr(oe, 'load_nicknames') else None
best = None
for p in ep().trace_paths(n):
    t = oe.load(p, NICK)
    trs = Perceiver.transitions_from_trace(t)
    clears = sum(tr.level_completed for tr in trs)
    if want and want not in (t.nick or "") and want not in p:
        continue
    if best is None or clears > best[2]:
        best = (p, t, clears, len(trs))
p, t, clears, nsteps = best
print(f"replay: {p}\ngame: {t.nick} ({t.gtype}), {nsteps} steps, {clears} level clears\n")
cfg = AgentConfig(propose_every=10, max_hypotheses=4, dl_weight=1.0)
trs = Perceiver.transitions_from_trace(t)
beliefs = BeliefState(cfg.max_hypotheses, cfg.max_records, dl_weight=cfg.dl_weight)
ctx, goals, prop = ContextBuilder(), GoalBeliefs(), HypothesisProposer()
goals.bind_level(trs[0].pre)
spikes = []
for i, tr in enumerate(trs):
    if tr.reset:
        ctx.observe(tr)
        if tr.post is not None:
            goals.bind_level(tr.post)
        continue
    rc = ctx.context(tr.pre, tr.action)
    sur = beliefs.observe(rc, tr)
    if sur.spike:
        spikes.append((i, tr.action.name, tr.label))
    pred = beliefs.map_hypothesis().ruleset.predict(rc)
    goals.observe(tr, tr.pre.apply(pred.effects) if (pred is not None and pred.effects) else None)
    ctx.observe(tr)
    if tr.level_completed and tr.post is not None:
        goals.bind_level(tr.post)
    if sur.spike or tr.level_completed or (i + 1) % cfg.propose_every == 0:
        beliefs.add_rulesets(prop.propose(beliefs))
        beliefs.reduce()
print("top rule sets at the end (posterior weight, rules):")
for h, w in beliefs.top(3):
    print(f"\n  weight {w:.2f}")
    for line in h.ruleset.describe():
        print("   -", line)
print(f"\nsurprise spikes: {len(spikes)}; first few (step, action, outcome):")
for s in spikes[:8]:
    print("  ", s)
print("\ntop goal guesses (goal, weight):")
for g, w in goals.top(3):
    print(f"   {g.describe()}  {w:.2f}")

"""
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE (replays capped at the first 600 steps; per game the play with the most clears, then the shortest): Run OpenMind's rule-discovery agent (rulediscovery1__fepInspired) in offline replay mode, CPU only, on
  ONE saved play per ARC-3 game for every game we have replays of (25), and write a per-game report: the top
  rule sets with posterior weight, surprise spikes, goal guesses. Asked by Son Pham in #experimentalmessing
  (06-Oct-2026 20:50 ET): "Do it for all 25 games, show me individual one". Per game the replay with the most
  level clears is used (ties: more steps), so the agent sees as much of the game as possible.
  Usage (from ARC3-Inference/): PYTHONPATH=. python3 ~/bubba-workspace/scratch/fep_replay/all_games.py
SRP/DRY check: Pass - same replay loop as one_replay.py (offline_eval machinery unchanged); new: the search over
  all replays on disk and the parallel per-game run + report.
"""
import glob, os, re, sys, time, json
from multiprocessing import get_context

HOME = os.path.expanduser("~")
MAX_STEPS = 600   # cap per replay so every game finishes; the report states it
OUT = os.path.join(HOME, "bubba-workspace/scratch/fep_replay/all_games_report.md")


def find_paths():
    pats = set()
    for root in [HOME]:
        for p in glob.glob(root + "/**/*_events.jsonl", recursive=True):
            if "/Library/" in p:
                continue
            m = re.match(r"([a-z0-9]{4})-", os.path.basename(p))
            if m:
                pats.add(p)
    return sorted(pats)


def survey(p):
    try:
        from rulediscovery1__fepInspired._distill import oe
        from rulediscovery1__fepInspired.perception import Perceiver
        t = oe.load(p)
        trs = Perceiver.transitions_from_trace(t)
        return (p, sum(tr.level_completed for tr in trs), len(trs))
    except Exception as e:
        return (p, -1, 0)


def run(p):
    t0 = time.time()
    from rulediscovery1__fepInspired._distill import oe
    from rulediscovery1__fepInspired.agent import AgentConfig
    from rulediscovery1__fepInspired.perception import Perceiver
    from rulediscovery1__fepInspired.beliefs import BeliefState
    from rulediscovery1__fepInspired.rules import ContextBuilder
    from rulediscovery1__fepInspired.goals import GoalBeliefs
    from rulediscovery1__fepInspired.hypotheses import HypothesisProposer
    t = oe.load(p)
    cfg = AgentConfig(propose_every=10, max_hypotheses=4, dl_weight=1.0)
    trs = Perceiver.transitions_from_trace(t)[:MAX_STEPS]
    beliefs = BeliefState(cfg.max_hypotheses, cfg.max_records, dl_weight=cfg.dl_weight)
    ctx, goals, prop = ContextBuilder(), GoalBeliefs(), HypothesisProposer()
    if trs:
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
    return {"path": p, "game": os.path.basename(p)[:4], "nick": getattr(t, "nick", ""), "gtype": getattr(t, "gtype", ""),
            "steps": len(trs), "full_clears": sum(tr.level_completed for tr in Perceiver.transitions_from_trace(t)), "clears": sum(tr.level_completed for tr in trs),
            "rules": [(round(w, 2), h.ruleset.describe()) for h, w in beliefs.top(2)],
            "spikes": len(spikes), "first_spikes": spikes[:4],
            "goals": [(g.describe(), round(w, 2)) for g, w in goals.top(2)], "seconds": round(time.time() - t0, 1)}


if __name__ == "__main__":
    paths = find_paths()
    print(len(paths), "replays found", flush=True)
    cache = OUT.replace("_report.md", "_survey.json")
    if os.path.exists(cache):
        sv = [tuple(x) for x in json.load(open(cache))]
    else:
        with get_context("spawn").Pool(10) as pool:
            sv = pool.map(survey, paths, chunksize=8)
        json.dump(sv, open(cache, "w"))
    best = {}
    for p, c, n in sv:
        g = os.path.basename(p)[:4]
        if c < 0 or n == 0:
            continue
        if g not in best or (c, -n) > (best[g][1], -best[g][2]):   # most clears, then the shortest play
            best[g] = (p, c, n)
    print(len(best), "games with a usable replay", flush=True)
    with get_context("spawn").Pool(10) as pool:
        res = pool.map(run, [v[0] for v in best.values()], chunksize=1)
    res.sort(key=lambda r: r["game"])
    lines = ["# OpenMind rule-discovery agent, offline replay, one play per game (CPU only)\n"]
    for r in res:
        lines.append(f"## {r['game']} {r['nick']} ({r['gtype']}): {r['steps']} steps, {r['clears']} clears, {r['seconds']} s")
        lines.append(f"replay: {r['path']}")
        for w, rs in r["rules"]:
            lines.append(f"- weight {w}: " + ("; ".join(rs) if rs else "(no rules: counts only)"))
        lines.append(f"- surprise spikes: {r['spikes']}; first: {r['first_spikes']}")
        lines.append(f"- goal guesses: {r['goals']}\n")
    open(OUT, "w").write("\n".join(lines))
    json.dump(res, open(OUT.replace(".md", ".json"), "w"), indent=1, default=str)
    print("wrote", OUT)

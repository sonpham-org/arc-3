# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Stage S2 of the tensor-logic overhaul (OpenMind, #arc-3, 24-Sep-2026): the learner OFFLINE on the recorded
#   plays of the evaluation set (results/soft/a0_{ls20,g50t,wa30}.jsonl: 20 plays each, replayed through the exact
#   simulator env.GameEnv; the engine labels in those files are used ONLY to pick the steps to score, never by the
#   agent). The agent watches each play passively (no explorer, no curiosity: the recorded actions are fed in), so
#   every arm sees exactly the same steps and raw nats are comparable across arms:
#     templates  AgentConfig()                        -- the current agent (hand-written templates)
#     touch_tl   use_tl, templates on                 -- tensor-logic rules added
#     tl_only    use_tl, templates off                -- tensor-logic rules alone ("not limited to taught rules")
#   Per game and arm: prequential nats per scored step under the posterior and under the counts-only back-off
#   (rules' gain = counts - posterior on the same steps), the MAP rule set's exact-label hit rate, on all steps and on
#   engine-labelled subsets: first contact (the controlled sprite's move strip holds a colour it never met before in
#   the play -- from the agent's own perception), blocked presses, ghost steps (two copies of the player sprite move),
#   push / carry steps (another sprite moves with the player's displacement), toggle steps (a sprite's visibility
#   flips: doors, switches). Tensor-logic arms also: steps the MAP held a learned rule, learned rules ever MAP, the
#   learned mover vs the engine's arrows, active equations, and the learned clauses in plain words.
#   Output: results/tl/s2_offline.json + .md. Run: .venv/bin/python -m rulediscovery1__fepInspired.tl.offline
# SRP/DRY check: Pass -- replay uses env.GameEnv and the agent unchanged; labels from soft/a0 files; the only new
#   code is the passive loop, the subset flags and the tables.
"""S2: tensor-logic rule learning offline on recorded plays (labels only for scoring)."""
from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from multiprocessing import get_context
from pathlib import Path

from ..agent import AgentConfig, RuleDiscoveryAgent
from ..env import GameEnv
from ..perception import Action

ROOT = Path(__file__).resolve().parents[1]
A0 = ROOT / "results" / "soft"
OUT = ROOT / "results" / "tl"
GAMES = {"ls20": "9607627b", "g50t": "5849a774", "wa30": "ee6fef47"}
NAMES = {"ls20": "Locksmith", "g50t": "Ghost Twin", "wa30": "Warehouse"}
ARMS = {"templates": {}, "touch_tl": {"use_tl": True, "tl_templates": True},
        "tl_only": {"use_tl": True, "tl_templates": False}}
ARROWS = ("ACTION1", "ACTION2", "ACTION3", "ACTION4")


def engine_flags(st: dict, player: str) -> dict:
    """Scoring subsets from the engine labels of one recorded step (never shown to the agent)."""
    mv = st.get("moved", [])
    pl = [m for m in mv if m["name"] == player]
    pd = (pl[0]["dy"], pl[0]["dx"]) if pl else None
    return {"ghost": len(pl) >= 2,
            "push": st["action"] in ARROWS and pd is not None and any(m["name"] != player and (m["dy"], m["dx"]) == pd
                                                                      for m in mv),
            "toggle": bool(st.get("toggled")),
            "blocked": st["action"] in ARROWS and not st.get("player_moved", True)}


def replay(job) -> dict:
    game, pi, arm, max_steps = job
    lines = (A0 / f"a0_{game}.jsonl").read_text().splitlines()
    play = json.loads(lines[pi])
    if not play.get("steps"):
        return {"game": game, "play": pi, "arm": arm, "error": "empty play"}
    env = GameEnv(game, GAMES[game])
    obs = env.reset()
    valid = lambda o: o.valid_actions + ["RESET"]  # noqa: E731
    agent = RuleDiscoveryAgent(AgentConfig(seed=0, dl_weight=0.25, **ARMS[arm]))
    agent.start_play(obs.grid, valid(obs), level=0)
    met: set = set()
    steps = []
    t0 = time.time()
    tl_map_steps, tl_ever = 0, set()
    for i, st in enumerate(play["steps"][:max_steps]):
        a = Action(st["action"])
        scene = agent.perceiver.current
        rc = agent.slow.ctx.context(scene, a)
        first = False
        tracker = agent.slow.ctx.state.agency.tracker
        if a.name in ARROWS and rc.agent is not None:
            d = tracker.direction(a.name)
            if d is not None:
                from .relations import SceneRel
                ys, xs, off = SceneRel.of(scene).strip((rc.agent,), d[0], d[1])
                cols = {int(v) for v in scene.comps.arr[ys, xs]} | ({-9} if off else set())
                first = bool(cols - met)
                met |= cols
        obs = env.step(a)
        if obs.grid != st["board"]:
            return {"game": game, "play": pi, "arm": arm, "error": f"replay diverged at step {i}"}
        rep = agent.observe(a, obs.grid, level_completed=obs.level_completed, game_over=obs.state == "GAME_OVER",
                            level=obs.levels_completed, valid_actions=valid(obs))
        tr = rep.transition
        if not tr.scored:
            continue
        fl = engine_flags(st, play.get("player"))
        fl["first_contact"] = first
        steps.append({"n": round(rep.surprise.surprisal, 4), "c": round(rep.surprise.backoff_surprisal, 4),
                      "hit": rep.surprise.predicted == tr.label, "spoke": rep.surprise.predicted is not None, **fl})
        if agent.tl_source is not None:
            tl_in = [r for r in agent.slow.beliefs.map_hypothesis().ruleset.rules() if r.template == "tl"]
            tl_map_steps += bool(tl_in)
            tl_ever |= {r.key() for r in tl_in}
    out = {"game": game, "play": pi, "arm": arm, "steps": steps, "seconds": round(time.time() - t0, 1),
           "map": agent.slow.beliefs.map_hypothesis().ruleset.describe()[:10]}
    src = agent.tl_source
    if src is not None:
        L = src.learner
        final = [r for r in agent.slow.beliefs.map_hypothesis().ruleset.rules() if r.template == "tl"]
        ctl = agent.slow.ctx.state.agency.tracker.controlled()
        mover = src.mover(ctl) if ctl is not None else None
        eng = defaultdict(lambda: defaultdict(int))    # engine arrows of the player (labels: scoring only)
        for st in play["steps"]:
            pl = [m for m in st.get("moved", []) if m["name"] == play.get("player")]
            if len(pl) == 1 and st["action"] in ARROWS and abs(pl[0]["dy"]) + abs(pl[0]["dx"]) <= 8:
                eng[st["action"]][(pl[0]["dy"], pl[0]["dx"])] += 1
        exported = {f"{r.family}/{r.scope}/{r.structure}": r.clauses()[:12] for r in src.exported}
        out.update({"tl_map_steps": tl_map_steps, "tl_ever_map": len(tl_ever), "tl_final_map": len(final),
                    "tl_final_rules": [r.describe() for r in final], "tl_active": "".join(sorted(L.active)),
                    "tl_activated": L.activated, "tl_fit_seconds": round(L.seconds, 1), "tl_fits": L.fits,
                    "tl_exported": exported, "tl_explanations": L.explanations[:6],
                    "tl_mover": None if mover is None else {"moves": mover[0], "walls": sorted(mover[1]),
                                                            "passable": sorted(mover[2])},
                    "engine_arrows": {k: max(v, key=v.get) for k, v in eng.items()},
                    "tl_lags": {"own_history_tau": int(L.hardened()["LagH"].argmax()) + 1,
                                "tape": list(__import__("rulediscovery1__fepInspired.tl.relations",
                                                        fromlist=["TAPE_LAGS"]).TAPE_LAGS[int(L.hardened()["LagG"].argmax())])}})
    return out


SUBSETS = ("all", "first_contact", "blocked", "ghost", "push", "toggle")


def summarise(rows: list) -> dict:
    res: dict = {}
    for g in GAMES:
        for arm in ARMS:
            rs = [r for r in rows if r["game"] == g and r["arm"] == arm and "error" not in r]
            d = {"plays": len(rs), "seconds": round(sum(r["seconds"] for r in rs), 1)}
            for sub in SUBSETS:
                ss = [s for r in rs for s in r["steps"] if sub == "all" or s.get(sub)]
                if not ss:
                    d[sub] = None
                    continue
                n, c = sum(s["n"] for s in ss), sum(s["c"] for s in ss)
                d[sub] = {"steps": len(ss), "nats": round(n / len(ss), 3), "counts": round(c / len(ss), 3),
                          "gain": round((c - n) / len(ss), 3), "map_hit": round(sum(s["hit"] for s in ss) / len(ss), 3)}
            if arm != "templates":
                d["tl_map_steps_share"] = round(sum(r["tl_map_steps"] for r in rs) / max(sum(len(r["steps"]) for r in rs), 1), 3)
                d["tl_ever_map_mean"] = round(sum(r["tl_ever_map"] for r in rs) / max(len(rs), 1), 2)
                d["plays_tl_in_final_map"] = sum(r["tl_final_map"] > 0 for r in rs)
                right = total = 0
                for r in rs:
                    m = (r.get("tl_mover") or {}).get("moves", {})
                    for k, mode in r["engine_arrows"].items():
                        total += 1
                        right += tuple(m.get(k, ())) == tuple(mode)
                d["mover_arrows_right"] = f"{right}/{total}"
                act = defaultdict(int)
                for r in rs:
                    for q in r["tl_active"]:
                        act[q] += 1
                d["equations_active_plays"] = dict(act)
                d["tl_fit_seconds"] = round(sum(r["tl_fit_seconds"] for r in rs), 1)
            res[f"{g}/{arm}"] = d
    return res


def table(res: dict) -> str:
    lines = ["# S2: tensor-logic rule learning offline on recorded plays", "",
             "Same recorded actions for every arm (passive replay through the exact simulator), so nats are comparable.",
             "gain = counts-only nats minus posterior nats on the same steps (what the rules add). map hit = the MAP rule",
             "set's predicted label equals the observed label. Engine labels choose the step subsets only.", ""]
    for g in GAMES:
        lines += [f"## {NAMES[g]} ({g})", "", "| subset | arm | steps | nats/step | counts | gain | map hit |",
                  "|---|---|---|---|---|---|---|"]
        for sub in SUBSETS:
            for arm in ARMS:
                d = res[f"{g}/{arm}"].get(sub)
                if d:
                    lines.append(f"| {sub} | {arm} | {d['steps']} | {d['nats']} | {d['counts']} | {d['gain']} | {d['map_hit']} |")
        for arm in ("touch_tl", "tl_only"):
            d = res[f"{g}/{arm}"]
            lines.append(f"\n{arm}: learned rule in MAP on {d['tl_map_steps_share']:.0%} of steps; learned rules ever MAP per "
                         f"play {d['tl_ever_map_mean']}; plays with a learned rule in the final MAP {d['plays_tl_in_final_map']}"
                         f"/{d['plays']}; learned mover arrows right {d['mover_arrows_right']} (vs the engine's modal player move); "
                         f"equations active (plays): {d['equations_active_plays']}; learner seconds {d['tl_fit_seconds']}")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", nargs="+", default=list(GAMES))
    ap.add_argument("--plays", type=int, default=20)
    ap.add_argument("--max-steps", type=int, default=400)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--arms", nargs="+", default=list(ARMS))
    ap.add_argument("--tag", default="s2_offline")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = []
    for g in args.games:
        n = len((A0 / f"a0_{g}.jsonl").read_text().splitlines())
        jobs += [(g, pi, arm, args.max_steps) for pi in range(min(n, args.plays)) for arm in args.arms]
    t0 = time.time()
    rows = []
    with get_context("spawn").Pool(args.workers) as pool:
        for r in pool.imap_unordered(replay, jobs):
            rows.append(r)
            print(json.dumps({k: r.get(k) for k in ("game", "play", "arm", "seconds", "error", "tl_active", "tl_final_map")}),
                  flush=True)
            (OUT / f"{args.tag}.partial.json").write_text(json.dumps(rows))
    res = summarise(rows)
    (OUT / f"{args.tag}.json").write_text(json.dumps({"summary": res, "plays": rows}, indent=1, default=str))
    text = table(res) + f"\nwall {time.time() - t0:.0f} s\n"
    (OUT / f"{args.tag}.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()

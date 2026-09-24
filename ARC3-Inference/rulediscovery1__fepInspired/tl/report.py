# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: The per-game report of the tensor-logic overhaul (OpenMind, #arc-3, 24-Sep-2026): reads the S2 offline
#   result (results/tl/s2_offline.json, tl/offline.py) and the S3 live sweep (results/game_sweep/tl_slippery7/rows.json,
#   game_sweep.py arms touch / touch_tl / tl_only), and writes results/tl/report.md + report.json:
#     - live, PER GAME (never aggregated): levels cleared, seeds clearing, median action of the first clear, game overs,
#       rules' gain per scored step (counts-only nats minus posterior nats on the same steps), learned rules adopted by
#       the posterior (distinct learned rules ever MAP per play, plays with one in the final MAP, share of steps with
#       one in the MAP), explorer trips, seconds per play; the morning's references (results/game_sweep/slippery7,
#       hdc_ab) for the touch arm;
#     - example learned rules in plain words per game (the final MAP's learned clauses of a representative play);
#     - the S2 offline tables; the file-by-file list of what changed and where it is called.
#   Run: .venv/bin/python -m rulediscovery1__fepInspired.tl.report
# SRP/DRY check: Pass -- reads the two result files only; offline.table() renders the S2 part.
"""Write results/tl/report.md (+ .json) from the S2 and S3 results."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .offline import table as s2_table

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "tl"
SWEEP = ROOT / "results" / "game_sweep"
NAMES = {"dc22": "Deck Control", "g50t": "Ghost Twin", "m0r0": "Mirror Rendezvous", "sc25": "Sigil Caster", "sk48": "Skewer Kebabs",
         "tn36": "Toggle Navigator", "tr87": "Toggle Runes", "ls20": "Locksmith", "wa30": "Warehouse Associates"}
ARMS = ("touch", "touch_tl", "tl_only")

# Written after reading S2 + S3 (24-Sep-2026 13:30 ET); every number below is in the tables further down.
FINDINGS = [
    "Levels: essentially unchanged; every gain or loss below is ONE seed of ten. Locksmith level one in every seed in "
    "all three arms (median first clear 48 / 49 / 48). Ghost Twin: templates-off cleared level one in seed 8 at action "
    "183 (first Ghost Twin clear of this agent in any sweep; touch and touch_tl did not clear seed 8). Deck Control: "
    "touch and touch_tl clear seed 1 (actions 108 / 107), templates-off does not. Sigil Caster: one clear per arm, "
    "on different seeds (0 / 1 / 7) and later with learned rules (158 -> 308 / 378). Nothing else cleared.",
    "One lever behind both the Ghost Twin clear and the worst regression: the learned program gives the explorer a "
    "mover where the templates had none or a different one, which changes where the agent walks. On Toggle Runes the "
    "templates never found a mover (0 trips per play); the learned one produces ~110-120 trips per play and game overs "
    "go 3 -> 10 in both learned arms. Toggle Navigator templates-off 4 -> 8 game overs. The same lever cuts Skewer "
    "Kebabs game overs 9 -> 2 (templates-off) and plausibly bought the Ghost Twin clear (different mover and "
    "forward-chaining search); not separated from the rules' predictions yet -- that is the next experiment.",
    "Prediction (rules' gain over counts per step): learned rules ADDED to the templates raise it on 8 of 9 games "
    "(Locksmith 0.409 -> 0.559, Ghost Twin 0.313 -> 0.422, Warehouse Associates 0.234 -> 0.292, Mirror Rendezvous "
    "0.165 -> 0.246, Sigil Caster 0.084 -> 0.208, Skewer Kebabs 0.032 -> 0.084, Deck Control 0.182 -> 0.203, Toggle Runes "
    "-0.02 -> 0.008; Toggle Navigator flat 0.02). Learned rules ALONE beat the templates on Locksmith (0.538), Ghost "
    "Twin (0.423), Mirror Rendezvous (0.202), Skewer Kebabs (0.088); worse on Deck Control (0.076), Warehouse "
    "Associates (0.058), Sigil Caster (0.070), Toggle Navigator (0.0).",
    "Offline on the recorded plays (same steps for every arm): added learned rules beat the templates on all three "
    "evaluation games; alone they win on Ghost Twin (best on ghost steps 1.24 -> 1.78 nats gained, door / toggle steps "
    "1.09 -> 1.83) and lose on Locksmith (0.48 -> 0.39) and slightly on Warehouse Associates (0.95 -> 0.90). First-contact "
    "steps: added rules slightly better on all three; alone worse on Locksmith and Warehouse Associates.",
    "Rediscovered without templates (offline): Locksmith arrows right in 75 of 76 cases and both template wall colours "
    "found as walls in every play (as 'only floor colour 3 lets a move through'); step bars as 'a piece that shrank "
    "last step shrinks again'. Ghost Twin: the ghost equation switched on by itself in 5 of 19 plays; in 2 it chose the "
    "true lag (copies the previous run per player move, no shift) with the ghost found as the piece sharing the "
    "player's shape; the timer as 'shrinks every second step'. Warehouse Associates: pushing / carrying as 'a piece "
    "next to (or moved along with) the controlled piece moves with it' -- but the learned mover is right on only about "
    "half the arrows there.",
    "Cost: learned rules make plays 1.5-3.5x slower (Skewer Kebabs 47 -> 170 s per play, added-rules arm).",
    "Posterior adoption: learned rules reach the MAP rule set in most plays of most games (templates-off: 6-10 of 10 "
    "except Toggle Navigator / Toggle Runes); next to the templates, the MAP is often a mix (template d-pad + learned "
    "'bar grows' modifier). Not built: invented predicates as a separate hidden layer (the thresholded Ahead weight is "
    "the only invented 'wall' predicate). Surprise-driven structure is in: 10 of ~150 equation switch-ons were "
    "triggered by a surprise spike.",
]

CHANGES = [
    ("tl/engine.py (new)", "Sparse relations with named indices, join / projection / step with a temperature, forward "
     "chaining to fixpoint, learnable multilinear tensor equations with their own gradient equations, softmax loss, "
     "Adam with an L1 (description-length) step. Called by tl/learner.py, tl/rule.py, tl/plan.py."),
    ("tl/relations.py (new)", "Perception as a relational database: per-step relations over objects (colour, type, "
     "controlled, common-fate group, what lies ahead in each move direction, run into / stood on / next to / clicked / "
     "moved along with the controlled piece, changed last step, own history, the previous run's tape) and per-object "
     "effect targets from the tracker. TLState is made in agent.start_play (via tl/bridge.make_tl) and kept by "
     "rules.ContextBuilder: begin(), annotate() into RuleContext.tl, observe() after every step (training rows)."),
    ("tl/learner.py (new)", "The join-shape bank (own x action, ahead, own relation, linked object, own history with a "
     "learned lag, previous run with a learned lag), gradient fit, structure switched on by the zero-gradient test "
     "(also on surprise spikes, with a backward-chaining explanation), thresholding + model reduction, export as "
     "rules, and the learned mover. Called through tl/bridge.TLSource by hypotheses.HypothesisProposer.propose, "
     "agent.observe (spikes) and explore.ObjectContactExplorer.mover_model."),
    ("tl/rule.py (new)", "TLRule: the thresholded program frozen into a rules.Rule (weights in its identity), priced "
     "in the templates' currency, predicted by forward chaining; scored and selected by beliefs.BeliefState like any "
     "rule; sits before the move templates in the decision list (rules.PRIMARY_ORDER)."),
    ("tl/plan.py (new)", "Reachability as forward chaining over sprite offsets (free-space map by correlating the "
     "sprite with the learned walls); replaces explore.search when ExploreConfig.search == 'tl' (set by "
     "agent.start_play when use_tl and tl_plan)."),
    ("tl/bridge.py (new)", "make_tl() and TLSource (propose / surprise / mover): the glue agent.py uses."),
    ("tl/offline.py, tl/report.py, tl/verify_default.py (new)", "Stage-two offline evaluation, this report, and the "
     "default-off action-for-action check against the backup."),
    ("tests/test_tl.py (new)", "Ten tests: engine, relations, learner, rule price and exact replay, planning, default off."),
    ("rules.py", "RuleContext.tl; ContextBuilder(hdc, tl) begins / annotates / observes the TLState; "
     "PRIMARY_ORDER gains 'tl'."),
    ("agent.py", "AgentConfig.use_tl / tl_templates / tl_plan / tl_cfg; start_play builds the TL state and source, "
     "turns the templates off when asked, and switches the explorer's search; observe() sends surprise spikes to the "
     "learner."),
    ("hypotheses.py", "HypothesisProposer.tl adds the learned rules to the candidates; .templates = False drops the "
     "template fitter."),
    ("explore.py", "ExploreConfig.search; the learned mover when there is no template mover (tl_only); the sprite's "
     "parts from the relational view's group; the forward-chaining search."),
    ("game_sweep.py", "Arms touch_tl and tl_only; per-play learned-rule adoption, active equations, learner time, "
     "learned clauses; trips for every arm."),
]


def live_rows(tag: str) -> list:
    p = SWEEP / tag / "rows.json"
    if not p.exists():
        p = SWEEP / tag / "rows.partial.json"
    return json.loads(p.read_text()) if p.exists() else []


def per_game(rows: list, game: str, arm: str) -> dict:
    rs = [r for r in rows if r["game"] == game and r["arm"] == arm]
    if not rs:
        return {}
    firsts = sorted(r["clear_at"][0] for r in rs if r["clear_at"])
    steps = sum(r.get("steps", 0) for r in rs)
    d = {"plays": len(rs), "levels": sum(r["levels"] for r in rs), "seeds_clearing": sum(bool(r["clear_at"]) for r in rs),
         "first_clear_median": firsts[len(firsts) // 2] if firsts else None, "first_clears": firsts,
         "game_overs": sum(r["state"] == "GAME_OVER" for r in rs),
         "gain_per_step": round(sum(r.get("nats_counts", 0) - r.get("nats", 0) for r in rs) / steps, 3) if steps else None,
         "nats_per_step": round(sum(r.get("nats", 0) for r in rs) / steps, 3) if steps else None,
         "trips_mean": round(sum(r.get("trips") or 0 for r in rs) / len(rs), 1),
         "seconds_per_play": round(sum(r["seconds"] for r in rs) / len(rs), 1)}
    if arm != "touch":
        d.update({"tl_ever_map_mean": round(sum(r.get("tl_ever_map", 0) for r in rs) / len(rs), 2),
                  "plays_tl_in_final_map": sum(r.get("tl_final_map", 0) > 0 for r in rs),
                  "tl_map_step_share": round(sum(r.get("tl_map_steps", 0) for r in rs) / steps, 3) if steps else None,
                  "equations_active": dict(Counter(q for r in rs for q in r.get("tl_active", ""))),
                  "learner_seconds_per_play": round(sum(r.get("tl_fit_seconds", 0) for r in rs) / len(rs), 1)})
    return d


def examples(rows: list, game: str, arm: str, k: int = 6) -> list:
    rs = [r for r in rows if r["game"] == game and r["arm"] == arm and r.get("tl_clauses")]
    rs.sort(key=lambda r: (-r["levels"], -len(r["tl_clauses"])))
    out = []
    for r in rs[:2]:
        for c in r["tl_clauses"]:
            if c not in out:
                out.append(c)
    return out[:k]


def main():
    s2p = OUT / "s2_offline.json"
    s2 = json.loads(s2p.read_text()) if s2p.exists() else None
    rows = live_rows("tl_slippery7")
    base7, hdc = live_rows("slippery7"), live_rows("hdc_ab")
    games = [g for g in NAMES if any(r["game"] == g for r in rows)]
    live = {g: {arm: per_game(rows, g, arm) for arm in ARMS} for g in games}
    ref = {g: per_game(base7 + hdc, g, "touch") for g in games}
    ex = {g: {arm: examples(rows, g, arm) for arm in ("touch_tl", "tl_only")} for g in games}
    L = ["# Tensor-logic overhaul: report (24-Sep-2026)", "",
         "Agent: OpenMind's rule-discovery agent with relational perception and tensor-logic rule learning "
         "(rulediscovery1__fepInspired/tl/). No language model anywhere at run time. Arms: touch = the current agent "
         "(templates, explorer, curiosity); touch_tl = the same plus learned rules; tl_only = templates OFF, learned "
         "rules only (the explorer's mover also comes from the learned program). Exact local simulators, 500 actions, "
         "RESET offered, same seeds per arm. Per game, never aggregated.", "",
         "Rules' gain = counts-only nats minus posterior nats per scored step, on the agent's own steps (arms walk "
         "different paths, so compare gains, not raw nats).", ""]
    L += ["## Findings", ""] + [f"- {f}" for f in FINDINGS] + [""]
    L += ["## Live (S3)", ""]
    for g in games:
        L += [f"### {NAMES[g]} ({g})", "",
              "| arm | levels | seeds clearing | first clear (median action) | game overs | rules' gain / step | "
              "learned rules ever MAP / play | plays with learned rule in final MAP | trips / play | s / play |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for arm in ARMS:
            d = live[g][arm]
            if not d:
                continue
            L.append(f"| {arm} | {d['levels']} | {d['seeds_clearing']}/{d['plays']} | {d['first_clear_median'] or '-'} | "
                     f"{d['game_overs']} | {d['gain_per_step']} | {d.get('tl_ever_map_mean', '-')} | "
                     f"{d.get('plays_tl_in_final_map', '-')} | {d['trips_mean']} | {d['seconds_per_play']} |")
        r = ref[g]
        if r:
            L.append(f"\nMorning reference (touch, earlier sweep): levels {r['levels']}, seeds clearing {r['seeds_clearing']}/"
                     f"{r['plays']}, first clear {r['first_clear_median'] or '-'}, game overs {r['game_overs']}.")
        for arm in ("touch_tl", "tl_only"):
            if ex[g][arm]:
                L.append(f"\nExample learned rules ({arm}):")
                L += [f"- {c}" for c in ex[g][arm]]
        L.append("")
    if s2:
        L += ["## Offline (S2)", "", s2_table(s2["summary"]).split("\n", 2)[2], ""]
    L += ["## What changed, and where it is called", ""] + [f"- **{a}**: {b}" for a, b in CHANGES]
    text = "\n".join(L) + "\n"
    (OUT / "report.md").write_text(text)
    (OUT / "report.json").write_text(json.dumps({"live": live, "reference_touch": ref, "examples": ex,
                                                 "offline": s2["summary"] if s2 else None,
                                                 "changes": CHANGES}, indent=1, default=str))
    print(text)


if __name__ == "__main__":
    main()

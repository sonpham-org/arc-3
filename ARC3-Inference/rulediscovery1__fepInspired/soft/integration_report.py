# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: HDC integration A/B (OpenMind, #arc-3, 24-Sep-2026 10:17 ET): writes results/soft/integration_ab.md + .json
#   from the live sweeps (game_sweep.py --tag hdc_ab: touch vs touch_hdc; --tag hdc_pieces: one piece each) and the
#   offline per-piece table (soft/integration_offline.py). Per game, never aggregated across games: levels cleared,
#   plays clearing a level, the action of each first clear, game overs, mean actions played, and prediction quality
#   from the agent's own prequential surprise (nats per scored step under its posterior; the counts-only back-off on
#   the same steps; their difference = what the rules add), plus a paired per-seed comparison of that gain.
#   Also lists what changed in which file and where it is called.
# SRP/DRY check: Pass -- reads the sweep rows and the offline json; no scoring of its own beyond sums and means.
"""The HDC integration A/B report."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SWEEP = ROOT / "results" / "game_sweep"
OUT = ROOT / "results" / "soft"
GAMES = ("g50t", "ls20", "wa30")
NAMES = {"g50t": "Ghost Twin (g50t:5849a774)", "ls20": "Locksmith (ls20:9607627b)", "wa30": "Warehouse (wa30:ee6fef47)"}

CHANGES = [
    ("agent.py", "AgentConfig.use_hdc (default False) + hdc_pieces; start_play gives the ContextBuilder an "
     "hdc_bridge.HdcState and calls ctx.begin(first board)", "every play; off = the old path, action-for-action equal "
     "to the first sweep on the three seeds spot-checked"),
    ("hdc_bridge.py (new)", "HdcState: GhostTape (phasor run tapes, stage-3/4 finder), WallMap/WallView (fractional-power "
     "place x colour memory, per-step snapshot, per-cell score map), revocable common fate; annotate() freezes the "
     "per-step values into the rule context", "rules.ContextBuilder.context / observe, every step"),
    ("rules.py", "RuleContext gains tape / walls / fate; ContextBuilder builds them and advances HdcState; TapeRule "
     "(modifier: an object repeats an earlier run); RuleSet.predict gates it on the player-move clock; MoveRule asks the "
     "soft wall map where its colour sets are silent (colour first); group FATE takes the sprite's parts from common "
     "fate (sprite_parts / fate_partners / soft_wall)", "beliefs scoring and replay, the policy's predictions, the "
     "planner, the fitter"),
    ("hypotheses.py", "TemplateFitter proposes TapeRule once the tape has explained an object; fit_moves uses the FATE "
     "group instead of co_movers when the fate piece is on (fate_riders drops parts riding on the sprite); "
     "track_record does not count the tape rule on steps where its clock did not tick", "every proposal (every 5 steps, "
     "on surprise spikes and clears) and the explorer's mover lookup"),
    ("explore.py", "sprite() takes common-fate partners for a FATE mover; search() takes the soft wall snapshot and "
     "refuses a step whose new strip the colour sets cannot judge and the soft map calls blocked", "every trip the "
     "touch explorer plans"),
    ("hdc/stage4_real.py", "Tracker.update_objects (parsed objects in, component per track kept)", "hdc_bridge, so the "
     "board is parsed once"),
    ("soft/a1_common_fate.py", "optional decay (revocable fusion), update_objects, last_moves, prequential scoring",
     "hdc_bridge (live), integration_offline (table)"),
    ("soft/a3_walls.py", "SoftWalls.score, ColourRule.verdict, guarded variants in run_game", "integration_offline"),
    ("game_sweep.py", "arms touch_hdc / touch_tape / touch_walls / touch_fate, --arms, --tag, prediction-quality fields",
     "this A/B"),
    ("tests/test_hdc_bridge.py (new)", "off = bare contexts; tape rule and clock gating; wall snapshot and linearity; "
     "exact replay with HDC on", "pytest"),
]


def load(tag: str) -> list:
    p = SWEEP / tag / "rows.json"
    if not p.exists():
        p = SWEEP / tag / "rows.partial.json"
    return json.loads(p.read_text()) if p.exists() else []


def summary(rs: list) -> dict:
    steps = sum(r["steps"] for r in rs)
    firsts = sorted(r["clear_at"][0] for r in rs if r["clear_at"])
    tape_steps = sum(r["tape_steps"] for r in rs)
    return {"plays": len(rs), "levels": sum(r["levels"] for r in rs), "plays_clearing": len(firsts),
            "clear_at": [r["clear_at"] for r in rs if r["clear_at"]],
            "first_clear_median": firsts[len(firsts) // 2] if firsts else None,
            "game_overs": sum(r["state"] == "GAME_OVER" for r in rs),
            "mean_actions": sum(r["actions"] for r in rs) / max(len(rs), 1),
            "nats_per_step": sum(r["nats"] for r in rs) / steps if steps else None,
            "counts_nats_per_step": sum(r["nats_counts"] for r in rs) / steps if steps else None,
            "rule_gain_per_step": (sum(r["nats_counts"] - r["nats"] for r in rs) / steps) if steps else None,
            "tape_steps": tape_steps,
            "tape_gain_per_step": (sum(r["tape_nats_counts"] - r["tape_nats"] for r in rs) / tape_steps
                                   if tape_steps else None),
            "tape_in_final_map": sum(bool(r.get("tape_in_map")) for r in rs),
            "seconds_mean": sum(r["seconds"] for r in rs) / max(len(rs), 1)}


def paired(rows: list, game: str, a: str, b: str) -> dict:
    """Per seed: rule gain per step in arm b minus arm a (same seed); how many seeds b is ahead."""
    ga = {r["seed"]: (r["nats_counts"] - r["nats"]) / max(r["steps"], 1) for r in rows if r["game"] == game and r["arm"] == a}
    gb = {r["seed"]: (r["nats_counts"] - r["nats"]) / max(r["steps"], 1) for r in rows if r["game"] == game and r["arm"] == b}
    seeds = sorted(set(ga) & set(gb))
    d = [gb[s] - ga[s] for s in seeds]
    return {"seeds": len(seeds), "b_ahead": sum(x > 0 for x in d), "mean_diff": sum(d) / len(d) if d else None}


def fmt(x, nd=3):
    return "-" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def table(rows: list, arms: list) -> list:
    lines = ["| game | arm | levels cleared | plays clearing | action of each clear | game overs | mean actions | "
             "nats/step posterior | nats/step counts | rules' gain/step | steps where the tape had an opinion | rules' gain/step on those steps (all rules, not the tape rule's own effect) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    out = {}
    for g in GAMES:
        for arm in arms:
            rs = [r for r in rows if r["game"] == g and r["arm"] == arm]
            if not rs:
                continue
            s = summary(rs)
            out[f"{g}/{arm}"] = s
            lines.append(f"| {NAMES[g]} | {arm} | {s['levels']} | {s['plays_clearing']}/{s['plays']} | "
                         f"{s['clear_at'] or '-'} | {s['game_overs']} | {s['mean_actions']:.0f} | "
                         f"{fmt(s['nats_per_step'])} | {fmt(s['counts_nats_per_step'])} | {fmt(s['rule_gain_per_step'])} | "
                         f"{s['tape_steps']} | {fmt(s['tape_gain_per_step'])} |")
    return lines, out


def main():
    ab = load("hdc_ab")
    pieces = load("hdc_pieces")
    off = json.loads((OUT / "integration_offline.json").read_text())
    res = {"ab": {}, "pieces": {}, "paired": {}, "offline": off}
    lines = ["# HDC integration A/B -- rule agent with vs without the phasor / fractional-power / hyperdimensional pieces",
             "", "24-Sep-2026, Claude Opus 5.5 (Bubba), for OpenMind (#arc-3, 10:17 ET). Nothing committed or pushed.",
             "Backup of the untouched package: ../backupsOldVersions/rulediscovery1__fepInspired_5fe717f335a8", "",
             "## Live A/B (exact local simulator, 10 seeds per game per arm, 500 actions, RESET offered, a game over ends "
             "the play -- the first sweep's settings)", "",
             "Arms: `touch` = rule agent + object-contact explorer + curiosity (the first sweep's best arm); `touch_hdc` = "
             "the same with AgentConfig.use_hdc=True (all three pieces). Same code path, same seeds 0-9. Prediction "
             "quality is the agent's own prequential surprise on its own trajectory; 'rules' gain' = counts-only nats "
             "minus posterior nats on the same steps, so it is comparable across arms even though the arms walk "
             "different paths.", ""]
    t, res["ab"] = table(ab, ["touch", "touch_hdc"])
    lines += t
    lines += ["", "Paired by seed (rules' gain per step, touch_hdc minus touch):", ""]
    for g in GAMES:
        p = paired(ab, g, "touch", "touch_hdc")
        res["paired"][g] = p
        lines.append(f"- {NAMES[g]}: touch_hdc ahead on {p['b_ahead']} of {p['seeds']} seeds, mean difference "
                     f"{fmt(p['mean_diff'])} nats/step")
    if pieces:
        lines += ["", "## Each piece alone (live, same settings)", ""]
        arms = ["touch_tape", "touch_walls", "touch_fate"]
        t, res["pieces"] = table(pieces, arms)
        lines += t
        lines += ["", "Paired by seed against `touch` from the A/B above (rules' gain per step):", ""]
        both = ab + pieces
        for g in GAMES:
            for arm in arms:
                p = paired(both, g, "touch", arm)
                res["paired"][f"{g}/{arm}"] = p
                lines.append(f"- {NAMES[g]}, {arm}: ahead on {p['b_ahead']} of {p['seeds']} seeds, mean difference "
                             f"{fmt(p['mean_diff'])} nats/step")
    lines += ["", "## Prediction quality per piece, offline (recorded plays, engine labels score only)", "",
              (OUT / "integration_offline.md").read_text().strip(), "",
              "## What changed, where, and where it is called", "", "| file | change | called from |", "|---|---|---|"]
    lines += [f"| {f} | {c} | {w} |" for f, c, w in CHANGES]
    lines += ["", "## Tests", "", "Before any change: 36 passed, 1 failed (tests/test_policy.py::"
              "test_salience_ranks_disagreement_first). After: see the run recorded below."]
    res["changes"] = CHANGES
    text = "\n".join(lines) + "\n"
    extra = OUT / "integration_ab_notes.md"
    if extra.exists():
        text += "\n" + extra.read_text()
    (OUT / "integration_ab.md").write_text(text)
    (OUT / "integration_ab.json").write_text(json.dumps(res, indent=1, default=str))
    print(text)


if __name__ == "__main__":
    main()

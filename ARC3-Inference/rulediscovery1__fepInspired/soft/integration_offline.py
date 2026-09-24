# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: HDC integration A/B (OpenMind, #arc-3, 24-Sep-2026 10:17 ET), second table: prediction quality of each
#   piece AS WIRED INTO THE AGENT, offline on the recorded plays with engine labels (A0; labels only score, the
#   pieces never read them), for Ghost Twin (g50t), Locksmith (ls20) and Warehouse (wa30), per game:
#     - wall map (soft/a3_walls.run_game with its guards, vector dimension as live = 2048): the colour rule alone,
#       the soft map alone, and the guard the agent uses (colour rule first, soft map where the colour rule is
#       silent, margin 0.05): accuracy / blocked recall / false walls on arrow presses, predicted before the outcome.
#     - grouping (soft/a1_common_fate.score_game): the type-level co-mover rule the agent had, common fate as in
#       A1 (permanent) and revocable (decay 0.8, what the agent uses), pair recall / precision against engine
#       sprite masks, both end-of-play and prequential (the grouping as it stood before each step).
#     - ghost tape (hdc/stage5_posterior.py result, Ghost Twin only): nats per ghost step, counts alone vs the
#       posterior with the tape rule, on all ghost steps and on the steps where the tape had decided.
#   Output results/soft/integration_offline.json + .md.
# SRP/DRY check: Pass -- every number comes from the existing A1 / A3 / stage-5 code; this file only runs them at
#   the live settings and writes one table.
"""Per-piece prediction quality at the settings the agent uses."""
from __future__ import annotations

import json
from pathlib import Path

from ..hdc.vsa import VSA
from ..hdc_bridge import HdcConfig
from .a1_common_fate import score_game
from .a3_walls import run_game

OUT = Path(__file__).resolve().parent.parent / "results" / "soft"
HDC = Path(__file__).resolve().parent.parent / "results" / "hdc"
GAMES = ("g50t", "ls20", "wa30")


def main():
    cfg = HdcConfig()
    guard = ("colour_first", cfg.tau)
    res = {"settings": {"dim": cfg.dim, "tau": cfg.tau, "fate_decay": cfg.fate_decay}, "walls": {}, "grouping": {}}
    for g in GAMES:
        t = run_game(OUT / f"a0_{g}.jsonl", VSA(cfg.dim, seed=0), [guard])
        res["walls"][g] = {k: {"accuracy": v["ok"] / max(v["n"], 1), "blocked_recall": v["blocked_hit"] / max(v["blocked"], 1),
                               "false_walls": v["false_wall"], "presses": v["n"]} for k, v in t.items()}
        perm, rev = score_game(OUT / f"a0_{g}.jsonl"), score_game(OUT / f"a0_{g}.jsonl", cfg.fate_decay)
        res["grouping"][g] = {"type_level_rule": perm["type_level_rule"],
                              "common_fate_permanent": perm["common_fate"],
                              "common_fate_permanent_prequential": perm["common_fate_prequential"],
                              "common_fate_revocable": rev["common_fate"],
                              "common_fate_revocable_prequential": rev["common_fate_prequential"]}
        print(g, json.dumps(res["walls"][g]), json.dumps(res["grouping"][g]), flush=True)
    s5 = json.loads((HDC / "stage5_posterior.json").read_text())
    res["ghost_tape"] = s5
    gk = f"colour_first@{cfg.tau}"
    f3 = lambda x: f"{x:.3f}"  # noqa: E731
    lines = ["Wall map (blocked moves predicted before the outcome; accuracy / blocked recall / false walls)", "",
             "| game | colour rule (before) | soft map alone | as wired: colour first, soft map fills silence |",
             "|---|---|---|---|"]
    for g in GAMES:
        w = res["walls"][g]
        cell = lambda k: f"{f3(w[k]['accuracy'])} / {f3(w[k]['blocked_recall'])} / {w[k]['false_walls']}"  # noqa: E731
        lines.append(f"| {g} | {cell('colour')} | {cell('soft')} | {cell(gk)} |")
    lines += ["", "Grouping parts into objects (pair recall / precision vs engine sprites; prequential = as the agent "
              "sees it)", "",
              "| game | type-level rule (before) | common fate permanent (prequential) | common fate revocable, as wired (prequential) |",
              "|---|---|---|---|"]
    for g in GAMES:
        r = res["grouping"][g]
        pr = lambda d: f"{f3(d['recall'])} / {f3(d['precision'])}"  # noqa: E731
        lines.append(f"| {g} | {pr(r['type_level_rule'])} | {pr(r['common_fate_permanent_prequential'])} | "
                     f"{pr(r['common_fate_revocable_prequential'])} |")
    lines += ["", f"Ghost tape (Ghost Twin, {s5['ghost_steps']} ghost steps in 20 recorded plays; nats per ghost step, "
              "lower is better): counts alone "
              f"{f3(s5['counts_nats_per_step'])}, posterior with the tape rule {f3(s5['mixture_nats_per_step'])}; on the "
              f"{s5['decided_steps']} steps where the tape had decided: {f3(s5['counts_nats_on_decided'])} -> "
              f"{f3(s5['mixture_nats_on_decided'])}."]
    text = "\n".join(lines)
    print(text)
    (OUT / "integration_offline.json").write_text(json.dumps(res, indent=1, default=str))
    (OUT / "integration_offline.md").write_text(text + "\n")


if __name__ == "__main__":
    main()

# Author: Claude Opus 5.5 (Bubba)
# Date: 25-September-2026
# PURPOSE: Tables for the debate-four picks of OpenMind's rule-discovery agent (#arc-3, 25-Sep-2026 11:24 ET;
#   ~/bubba-workspace/docs/2026-09-25-warehouse-expert-debate-4.md), read straight from the sweep's raw rows
#   (results/game_sweep/debate4/rows.json, any extra rows files, plus the random arm's results/game_sweep/dp_random/rows.json),
#   per game and arm, never pooled across games:
#     - everything debate_report.per_arm / stage1_report.stage1 / debate3_report.debate3 give (levels, clears, game overs,
#       RESETs, Warehouse labels, decision modes, checks and interruptions, budget);
#     - Warehouse grab positions by who chose the step, including the new try-once presses and babbling plans;
#     - pick 1's diagnostic (the check log joined to grab positions by debate4_labels): checks per play, at grab positions,
#       what won there and elsewhere, grab positions with no check, remaining trip steps at checks; try-once presses and
#       new contact classes;
#     - pick 2: babbling episodes / reached / stalled, planning attempts and plans found, plan steps, policy decisions with
#       the preference on; which goals were tried (all plays) and how their weights moved; the goal named after the first
#       clear (contrast log) and whether it is the game's step-bar colour;
#     - per-seed first clears on Locksmith and Ghost Twin, and the seeds where an arm lost / gained a clear vs d3_hb;
#     - a check that the rerun d3_hb rows equal debate three's (results/game_sweep/debate3_hb) per seed.
#   Writes <out>/tables.json and <out>/tables.md. Run from ~/GitHub/arc-3/ARC3-Inference:
#     .venv/bin/python ~/bubba-workspace/scratch/debate4/debate4_report.py --rows <rows.json> ... --prev <d3_hb rows> --out <dir>
# SRP/DRY check: Pass -- base measures from debate_report.per_arm, stage1_report.stage1, debate3_report.debate3 / pct /
#   same_as_prev (imported); new: the debate-four columns.
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "warehouse"))
sys.path.insert(0, str(HERE.parent / "stage1"))
sys.path.insert(0, str(HERE.parent / "debate3"))
from debate3_report import debate3, pct, same_as_prev  # noqa: E402
from debate_report import GAMES, med, per_arm  # noqa: E402
from stage1_report import stage1  # noqa: E402

ORDER = ["random", "d3_hb", "d4_opt", "d4_ov", "d4_try", "d4_goal", "d4_both", "d4_all", "d4_opt3"]
MODES4 = ["touch", "efe", "handoff", "tryonce", "return", "plan", "babble"]
BAR = {"ls20": 11, "g50t": 9, "wa30": 7}          # the step-bar colour each game's budget reader found (debate three rows)


def debate4(rows: list) -> dict:
    ok = [r for r in rows if r.get("state") != "TIMEOUT"]
    out: dict = {}
    if not ok or ok[0]["arm"] == "random":
        return out
    steps = sum(r["actions"] for r in ok)
    for m in MODES4:
        out[f"mode4_{m}"] = round(sum(r.get("modes", {}).get(m, 0) for r in ok) / max(steps, 1), 3)
    gm = [r["labels"].get("grab_by_mode") for r in ok if r.get("labels") and r["labels"].get("grab_by_mode")]
    if gm:
        for m in MODES4:
            out[f"grab4_{m}"] = [sum(g.get(m, [0, 0])[0] for g in gm), sum(g.get(m, [0, 0])[1] for g in gm)]
    cl = [r for r in ok if "check_log" in r]
    if cl:
        won = Counter(c[2] for r in cl for c in r["check_log"])
        out["chk4_per_play"] = round(sum(len(r["check_log"]) for r in cl) / len(cl), 1)
        out["chk4_won"] = {k: round(v / len(cl), 1) for k, v in sorted(won.items())}
        ks = [c[4] for r in cl for c in r["check_log"] if c[2] in ("trip", "button") and c[4] is not None]
        out["chk4_k_median"] = med(ks)
        out["chk4_k_share_1"] = round(sum(k == 1 for k in ks) / len(ks), 3) if ks else None
        out["chk4_interrupts_per_play"] = round(sum(won.get(w, 0) for w in ("button", "try_once")) / len(cl), 2)
        out["chk4_plays_interrupted"] = sum(any(c[2] in ("button", "try_once") for c in r["check_log"]) for r in cl)
        out["try_presses"] = sum(r["try_once"]["presses"] for r in cl if r.get("try_once"))
        out["try_classes_median"] = med([r["try_once"]["new_classes"] for r in cl if r.get("try_once")])
    lab = [r["labels"] for r in ok if r.get("labels") and "checks_total" in r["labels"]]
    if lab and cl:
        agg: Counter = Counter()
        for x in lab:
            agg.update(x["check_won"])
        out["lab_checks"] = sum(x["checks_total"] for x in lab)
        out["lab_unjoined"] = sum(x["checks_unjoined"] for x in lab)
        out["lab_checks_at_grab"] = sum(x["checks_at_grab"] for x in lab)
        out["lab_grab_no_check"] = sum(x["grab_no_check"] for x in lab)
        out["lab_won"] = dict(sorted(agg.items()))
        acts: Counter = Counter()
        for x in lab:
            acts.update(x["check_at_grab_actions"])
        out["lab_grab_actions"] = dict(acts)
    if lab and cl:                                    # G values and triggers at checks the labeller put at grab positions
        gv = {"trip": [], "button": []}
        trig: Counter = Counter()
        capped = 0
        for r in cl:
            x = r.get("labels") or {}
            steps = set(x.get("check_grab_steps", []))
            capped += int(len(x.get("check_grab_steps", [])) < (x.get("checks_at_grab") or 0))
            for c in r["check_log"]:
                if c[0] + 1 in steps:                 # the labeller counts from 1, the agent from 0
                    trig[c[1]] += 1
                    if c[2] in gv:
                        gv[c[2]].append(c[5:8])
        for w, xs in gv.items():
            if xs:
                out[f"grabG_{w}"] = [len(xs)] + [round(med([v[i] for v in xs]), 3) for i in range(3)]
        out["grab_triggers"] = dict(trig.most_common())
        out["grab_steps_capped_plays"] = capped
    bb = [r["babble"] for r in ok if r.get("babble")]
    if bb:
        for k in ("episodes", "reached", "stalled", "attempts", "plans", "plan_steps", "pref_decisions"):
            out[f"bb_{k}"] = round(sum(b[k] for b in bb) / len(bb), 1)
        out["bb_plays_with_plan"] = sum(b["plans"] > 0 for b in bb)
        out["bb_plays_done"] = sum(bool(b["done_at_clear"]) for b in bb)
        tried: Counter = Counter()
        for b in bb:
            tried.update(b["tried"])
        out["bb_tried"] = tried.most_common(10)
        moved: dict = {}
        for b in bb:
            for g, w, share in b["weights"]:
                moved.setdefault(g, []).append(w)
        out["bb_weights"] = sorted([[g, len(ws), med(ws), min(ws), max(ws)] for g, ws in moved.items()],
                                   key=lambda t: -t[1])[:10]
    cz = [r["caused"] for r in ok if r.get("caused")]
    if cz:
        out["cz_idle_share"] = round(sum(c["idle_steps"] for c in cz) / max(sum(c["idle_steps"] + c["active_steps"]
                                                                            for c in cz), 1), 3)
    con = [r for r in ok if r.get("contrast_log")]
    if con:
        g = ok[0]["game"]
        named = Counter(r["contrast_log"][0][1] for r in con)
        bar = f"colour-{BAR.get(g)} "
        out["contrast_plays"] = len(con)
        out["contrast_named"] = named.most_common(6)
        out["contrast_names_bar"] = sum(bar in r["contrast_log"][0][1] or r["contrast_log"][0][1].endswith(
            f"colour {BAR.get(g)}") for r in con)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", nargs="+", required=True)
    ap.add_argument("--prev", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    rows = []
    for p in args.rows:
        rows += json.loads(Path(p).read_text())
    tab = {}
    for g in GAMES:
        for arm in ORDER:
            rs = [r for r in rows if r["game"] == g and r["arm"] == arm]
            if rs:
                tab[f"{g}/{arm}"] = {**per_arm(rs), **stage1(rs), **debate3(rs), **debate4(rs),
                                     "seeds": sorted(r["seed"] for r in rs)}
    if args.prev:
        tab["_rerun_equal"] = same_as_prev([r for r in rows if r["arm"] == "d3_hb"], json.loads(Path(args.prev).read_text()))
    # pick 3's kill rule: plays with the gated contact novelty vs the same arm without it, per game and seed
    F = ("levels", "clear_at", "actions", "state", "presses")
    idx = {(r["game"], r["arm"], r["seed"]): r for r in rows}
    pairs = {}
    for a, b in (("d4_all", "d4_both"), ("d4_opt3", "d4_opt")):
        for g in GAMES:
            rs = [r for r in rows if r["game"] == g and r["arm"] == a]
            if not rs:
                continue
            diff = [r["seed"] for r in rs if (g, b, r["seed"]) in idx
                    and not all(r.get(f) == idx[(g, b, r["seed"])].get(f) for f in F)]
            pairs[f"{g}/{a} vs {b}"] = {"plays": len(rs), "differ": sorted(diff),
                                        "open_presses": sum((r.get("contact") or {}).get("open_presses", 0) for r in rs),
                                        "open_at_median": med([r["contact"]["open_at"] for r in rs
                                                               if (r.get("contact") or {}).get("open_at") is not None])}
    tab["_pick3_pairs"] = pairs
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "tables.json").write_text(json.dumps(tab, indent=1))
    L = []
    for g, name in GAMES.items():
        arms = [a for a in ORDER if f"{g}/{a}" in tab]
        if not arms:
            continue
        T = lambda a: tab[f"{g}/{a}"]  # noqa: E731
        L += [f"## {name} ({g})", "",
              "| arm | plays | levels | plays clearing | first clear (median action) | plays clearing level 2 | game overs "
              "| time-outs | RESETs per play | play seconds (median) |", "|---|---|---|---|---|---|---|---|---|---|"]
        for a in arms:
            t = T(a)
            L.append(f"| {a} | {t['plays']} | {t['levels']} | {t['plays_clearing']} | {t['first_clear_median']} | "
                     f"{t['plays_clearing_2']} | {t['game_overs']} | {t['timeouts']} | {t['resets_per_play']} | "
                     f"{t['seconds_median']} |")
        L.append("")
        if g == "wa30":
            L += ["| arm | grab positions | interact there | plays with a grab | grabs | drops | box configs (median) | "
                  "plays: box on target (seeds) | most boxes on target at once | first box on target (actions) |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
            for a in arms:
                t = T(a)
                if "grab_pos" in t:
                    seeds = t.get("on_target_seeds", [])
                    L.append(f"| {a} | {t['grab_pos']} | {pct(t['interact_at_grab'], t['grab_pos'])} | "
                             f"{t['plays_with_grab']} | {t['grabs']} | {t['drops']} | {t['box_configs_median']} | "
                             f"{t['plays_box_on_target']} ({', '.join(map(str, seeds)) or '-'}) | "
                             f"{t.get('max_on_target', 0)} | {', '.join(map(str, t.get('first_on_target', []))) or '-'} |")
            L.append("")
            L += ["Grab positions by who chose the step, and interact pressed there:", "",
                  "| arm | explorer trip | policy | interruption | try-once | archive replay | planner | babbling plan |",
                  "|---|---|---|---|---|---|---|---|"]
            for a in arms:
                t = T(a)
                if "grab4_efe" in t:
                    cells = []
                    for m in ["touch", "efe", "handoff", "tryonce", "return", "plan", "babble"]:
                        v = t.get(f"grab4_{m}", [0, 0])
                        cells.append(pct(v[1], v[0]) if v[0] else "0")
                    L.append("| " + a + " | " + " | ".join(cells) + " |")
            L.append("")
            lab = [a for a in arms if "lab_checks" in T(a)]
            if lab:
                L += ["Pick 1 diagnostic: checks joined to grab positions (all plays; won = what the check chose):", "",
                      "| arm | checks | checks at a grab position | at grab: button / trip / try-once / other | "
                      "elsewhere: button / trip / try-once / other | grab positions with no check | not joined |",
                      "|---|---|---|---|---|---|---|"]
                for a in lab:
                    t = T(a)
                    w = t["lab_won"]

                    def four(pre):
                        b, tr, to = w.get(f"{pre}:button", 0), w.get(f"{pre}:trip", 0), w.get(f"{pre}:try_once", 0)
                        other = sum(v for k, v in w.items() if k.startswith(pre + ":")) - b - tr - to
                        return f"{b} / {tr} / {to} / {other}"
                    L.append(f"| {a} | {t['lab_checks']} | {t['lab_checks_at_grab']} | {four('grab')} | {four('other')} | "
                             f"{t['lab_grab_no_check']} | {t['lab_unjoined']} |")
                L.append("")
                L += ["At grab-position checks: median G of continuing / of the best non-moving button / of the best move, by "
                      "what won (the labeller keeps each play's first 60 grab-position check steps), and the triggers:", "",
                      "| arm | trip won: n, G_cont / G_button / G_move | button won: n, G_cont / G_button / G_move | triggers | "
                      "plays over the 60 cap |", "|---|---|---|---|---|"]
                for a in lab:
                    t = T(a)
                    cell = lambda w: (f"{t[w][0]}, {t[w][1]} / {t[w][2]} / {t[w][3]}" if w in t else "-")  # noqa: E731
                    trg = ", ".join(f"{k} {v}" for k, v in t.get("grab_triggers", {}).items())
                    L.append(f"| {a} | {cell('grabG_trip')} | {cell('grabG_button')} | {trg} | "
                             f"{t.get('grab_steps_capped_plays')} |")
                L.append("")
        L += ["Steps by who chose them (share of all steps):", "",
              "| arm | explorer trips | policy | interruptions | try-once | archive replays | planner | babbling plans |",
              "|---|---|---|---|---|---|---|---|"]
        for a in arms:
            t = T(a)
            if "mode4_touch" in t:
                L.append("| " + a + " | " + " | ".join(f"{t.get(f'mode4_{m}', 0):.1%}" for m in MODES4) + " |")
        L.append("")
        ck = [a for a in arms if "chk4_per_play" in T(a)]
        if ck:
            L += ["Pick 1, the check log (per play): checks, what won, remaining trip steps k at compared checks:", "",
                  "| arm | checks | won (per play) | interruptions + try-once presses | plays with one | k (median) | "
                  "share of compared checks with k = 1 | try-once presses (all plays) | new contact classes (median) |",
                  "|---|---|---|---|---|---|---|---|---|"]
            for a in ck:
                t = T(a)
                won = ", ".join(f"{k} {v}" for k, v in t["chk4_won"].items())
                L.append(f"| {a} | {t['chk4_per_play']} | {won} | {t['chk4_interrupts_per_play']} | "
                         f"{t['chk4_plays_interrupted']}/{t['plays']} | {t['chk4_k_median']} | {t['chk4_k_share_1']} | "
                         f"{t['try_presses']} | {t['try_classes_median']} |")
            L.append("")
        bb = [a for a in arms if "bb_episodes" in T(a)]
        if bb:
            L += ["Pick 2, goal babbling (per play unless noted):", "",
                  "| arm | episodes | reached (no clear) | stalled | plan attempts | plans found | plays with a plan | "
                  "plan steps | policy decisions with the goal on | plays where a clear ended it | idle share of counted steps |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
            for a in bb:
                t = T(a)
                L.append(f"| {a} | {t['bb_episodes']} | {t['bb_reached']} | {t['bb_stalled']} | {t['bb_attempts']} | "
                         f"{t['bb_plans']} | {t['bb_plays_with_plan']}/{t['plays']} | {t['bb_plan_steps']} | "
                         f"{t['bb_pref_decisions']} | {t['bb_plays_done']} | {t.get('cz_idle_share')} |")
            L.append("")
            for a in bb:
                t = T(a)
                L.append(f"{a}, goals tried (episodes, all plays): " +
                         "; ".join(f"{d} {n}" for d, n in t["bb_tried"]))
                L.append(f"{a}, weights that moved (goal: plays, median / min / max final weight; start 1): " +
                         "; ".join(f"{g}: {n}, {m} / {lo} / {hi}" for g, n, m, lo, hi in t["bb_weights"]))
                L.append("")
        cn = [a for a in arms if "contrast_plays" in T(a)]
        if cn:
            L += ["Goal named after the first clear (contrast log), and plays where it is the step bar's colour:", "",
                  "| arm | plays with a clear | names the bar | most named |", "|---|---|---|---|"]
            for a in cn:
                t = T(a)
                L.append(f"| {a} | {t['contrast_plays']} | {t['contrast_names_bar']} | " +
                         "; ".join(f"{d} ({n})" for d, n in t["contrast_named"]) + " |")
            L.append("")
        if g != "wa30":
            base = T("d3_hb")["clear_by_seed"] if "d3_hb" in arms else {}
            L += ["First clear per seed (action; - = no clear), and seeds where an arm lost / gained a clear vs d3_hb:", "",
                  "| arm | " + " | ".join(str(s) for s in range(20)) + " | lost vs d3_hb | gained vs d3_hb |",
                  "|---|" + "---|" * 22]
            for a in arms:
                t = T(a)
                if "clear_by_seed" not in t:
                    continue
                cb = t["clear_by_seed"]
                lost = [s for s in cb if base.get(s) is not None and cb[s] is None]
                gained = [s for s in cb if base.get(s) is None and cb[s] is not None]
                t["lost_vs_hb"], t["gained_vs_hb"] = lost, gained
                L.append(f"| {a} | " + " | ".join(str(cb.get(s) if cb.get(s) is not None else "-") for s in range(20)) +
                         f" | {', '.join(map(str, lost)) or 'none'} | {', '.join(map(str, gained)) or 'none'} |")
            L.append("")
    if tab.get("_pick3_pairs"):
        L += ["Pick 3's kill rule: plays with the gated contact novelty that differ from the same arm without it (levels, "
              "clears, actions, end state or presses), presses of a button with no learned move while the gate was open, "
              "and the step the gate opened (median):", "",
              "| comparison | plays | seeds that differ | moveless presses while open | gate opened at (median step) |",
              "|---|---|---|---|---|"]
        for k, v in tab["_pick3_pairs"].items():
            L.append(f"| {k} | {v['plays']} | {', '.join(map(str, v['differ'])) or 'none'} | {v['open_presses']} | "
                     f"{v['open_at_median']} |")
        L.append("")
    if "_rerun_equal" in tab:
        L += ["Rerun d3_hb vs debate three's rows (results/game_sweep/debate3_hb), plays equal in levels, clears, actions, "
              "end state and presses:", ""]
        for k, (e, n) in sorted(tab["_rerun_equal"].items()):
            L.append(f"- {k}: {e}/{n}")
        L.append("")
    (out / "tables.json").write_text(json.dumps(tab, indent=1))
    (out / "tables.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()

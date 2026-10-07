# Author: Claude Opus 5.5 (Bubba)
# Date: 25-September-2026
# PURPOSE: Tables for debate five's picks 2 and 3 on OpenMind's rule-discovery agent (#arc-3, 25-Sep-2026 17:14 ET;
#   ~/bubba-workspace/docs/2026-09-25-openmind-agent-expert-debate-5.md, Round 7), read straight from the sweep's raw rows
#   (results/game_sweep/debate5/rows.json), per game and arm, never pooled across games except where a judging rule of the
#   debate asks for it (labelled as such):
#     - levels, plays clearing level 1 / level 2, median first clear, game overs, RESETs per play, time-outs;
#     - Warehouse labeller measures (debate4_labels): interact at grab positions (random arm from dp_random), grabs, drops,
#       plays with a box on a target, most boxes on a target at once;
#     - per-seed clears for Locksmith and Ghost Twin, seeds lost / gained vs the d4_opt rerun;
#     - judging: (a) the old per-seed guard (any Locksmith or Ghost Twin seed that cleared with d4_opt and not with the arm);
#       (b) total clears over paired seeds with an exact two-sided sign test, per game and pooled over the two canaries
#       (Locksmith + Ghost Twin = the debate's forty paired seeds); Locksmith level one 20/20 as the hard gate,
#       and its speed shown plainly (median / mean first clear, seeds slower / faster; no tolerance applied);
#     - pick 3: per restart kind (clear / RESET / lost life) actions until the MAP rule set is right 5 scored steps in a
#       row, censored share, whether the pre-restart MAP rule set is still a hypothesis / still MAP 10 actions later; the
#       library's size and seeding;
#     - try-once under pick 2: d5_flat vs d5_flat_notry, and in d5_flat the try-once checks where the ordinary comparison
#       would have pressed the button anyway (G of the button < G of continuing);
#     - reproduction: the d4_opt rerun vs debate four's d4_opt rows, per seed (clears, actions, presses).
#   Writes <out>/tables.json and <out>/tables.md. Run from ~/GitHub/arc-3/ARC3-Inference with .venv/bin/python.
# SRP/DRY check: Pass -- Warehouse label sums follow debate_report.per_arm's definitions (same label keys); the sign test
#   is a plain binomial tail. New: the debate-five tables.
from __future__ import annotations

import argparse
import json
import math
import statistics as st
from collections import Counter
from pathlib import Path

GAMES = [("wa30", "Warehouse"), ("ls20", "Locksmith"), ("g50t", "Ghost Twin")]
ARMS = ["d4_opt", "d5_flat", "d5_lib", "d5_both", "d5_flat_notry"]
BASE = "d4_opt"
CANARIES = ("ls20", "g50t")


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def sign_test(pos: int, neg: int) -> float:
    """Exact two-sided sign test p (ties dropped)."""
    n = pos + neg
    if n == 0:
        return 1.0
    k = min(pos, neg)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def base_table(rs: list) -> dict:
    ok = [r for r in rs if r.get("state") != "TIMEOUT"]
    firsts = [r["clear_at"][0] for r in ok if r["clear_at"]]
    out = {"plays": len(rs), "timeouts": len(rs) - len(ok), "levels": sum(r["levels"] for r in ok),
           "clear_l1": sum(len(r["clear_at"]) >= 1 for r in ok), "clear_l2": sum(len(r["clear_at"]) >= 2 for r in ok),
           "first_clear_median": med(firsts), "game_overs": sum(r["state"] == "GAME_OVER" for r in ok),
           "resets_per_play": round(sum(r["presses"].get("RESET", 0) for r in ok) / max(len(ok), 1), 2),
           "seconds_median": med([r["seconds"] for r in ok])}
    two = [r for r in ok if len(r["clear_at"]) >= 2]
    out["level2_len_median"] = med([r["clear_at"][1] - r["clear_at"][0] for r in two])
    L = [r["labels"] for r in ok if r.get("labels")]
    if L:
        s = lambda k: sum(x.get(k, 0) or 0 for x in L)  # noqa: E731
        out.update({"grab_pos": s("grab_pos"), "interact_at_grab": s("interact_at_grab"),
                    "interact_rate": round(s("interact_at_grab") / max(s("grab_pos"), 1), 3),
                    "grabs": s("grabs"), "drops": s("drops"),
                    "plays_box_on_target": sum((x.get("max_on_target") or 0) > 0 for x in L),
                    "seeds_box_on_target": sorted(r["seed"] for r in ok if (r.get("labels") or {}).get("max_on_target")),
                    "most_on_target": max((x.get("max_on_target") or 0) for x in L)})
    return out


def per_seed(rs: list) -> dict:
    return {r["seed"]: (r["levels"] if r.get("state") != "TIMEOUT" else None) for r in rs}


def relearn(rs: list) -> dict:
    out = {}
    for why in ("clear", "reset", "life"):
        ev = [e for r in rs for e in r.get("relearn", []) if e[0] == why]
        if not ev:
            continue
        done = [e[2] for e in ev if e[2] is not None]
        kept = [e for e in ev if e[3] is not None and not e[5]]
        out[why] = {"events": len(ev), "per_play": round(len(ev) / len(rs), 2), "relearn_median": med(done),
                    "censored": len(ev) - len(done),
                    "kept_10": f"{sum(e[3] for e in kept)}/{len(kept)}", "map_10": f"{sum(e[4] for e in kept)}/{len(kept)}"}
    lib = [r["library"] for r in rs if r.get("library")]
    if lib:
        out["library"] = {"sets_median": med([x["sets"] for x in lib]), "rules_median": med([x["rules"] for x in lib]),
                          "seeded_per_play": round(sum(x["seeded"] for x in lib) / len(lib), 2)}
    return out


def try_once(rs: list) -> dict:
    cl = [c for r in rs for c in r.get("check_log", []) if c[2] == "try_once"]
    anyway = sum(1 for c in cl if c[5] is not None and c[6] is not None and c[6] < c[5])
    return {"try_presses": len(cl), "would_press_anyway": anyway,
            "try_per_play": round(len(cl) / max(len(rs), 1), 2),
            "interrupt_per_play": round(sum(1 for r in rs for c in r.get("check_log", []) if c[2] == "button")
                                        / max(len(rs), 1), 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", nargs="+", required=True)
    ap.add_argument("--random", default="")
    ap.add_argument("--prev", default="", help="debate four rows (for the d4_opt reproduction check)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    rows = []
    for p in args.rows:
        rows += json.loads(Path(p).read_text())
    rnd = [r for r in json.loads(Path(args.random).read_text()) if r["arm"] == "random"] if args.random else []
    prev = [r for r in json.loads(Path(args.prev).read_text()) if r["arm"] == BASE] if args.prev else []
    T: dict = {"games": {}, "judging": {}, "repro": {}}
    for g, name in GAMES:
        G = T["games"][g] = {"name": name, "arms": {}}
        if rnd and g == "wa30":
            G["arms"]["random"] = base_table([r for r in rnd if r["game"] == g])
        base = per_seed([r for r in rows if r["game"] == g and r["arm"] == BASE])
        for arm in ARMS:
            rs = sorted([r for r in rows if r["game"] == g and r["arm"] == arm], key=lambda r: r["seed"])
            if not rs:
                continue
            A = G["arms"][arm] = base_table(rs)
            ps = per_seed(rs)
            A["seeds_clearing"] = sorted(s for s, v in ps.items() if v)
            A["seeds_level2"] = sorted(r["seed"] for r in rs if len(r["clear_at"]) >= 2)
            if g in ("ls20", "g50t"):
                A["first_clears"] = {r["seed"]: r["clear_at"][:2] for r in rs}
            A["relearn"] = relearn(rs)
            A["try"] = try_once(rs)
            if arm != BASE:
                paired = [s for s in ps if s in base and ps[s] is not None and base[s] is not None]
                pos = sum(ps[s] > base[s] for s in paired)
                neg = sum(ps[s] < base[s] for s in paired)
                A["vs_base"] = {"paired": len(paired), "clears_arm": sum(ps[s] for s in paired),
                                "clears_base": sum(base[s] for s in paired), "seeds_up": pos, "seeds_down": neg,
                                "sign_p": round(sign_test(pos, neg), 4),
                                "lost": sorted(s for s in paired if base[s] and not ps[s]),
                                "gained": sorted(s for s in paired if ps[s] and not base[s]),
                                "fewer_levels": sorted(s for s in paired if ps[s] < base[s]),
                                "more_levels": sorted(s for s in paired if ps[s] > base[s])}
    ls = T["games"]["ls20"]["arms"]
    base_med = ls[BASE]["first_clear_median"] if BASE in ls else None
    for arm in ARMS[1:]:
        if not all(arm in T["games"][g]["arms"] and BASE in T["games"][g]["arms"] for g, _ in GAMES):
            continue
        guard_lost = {g: T["games"][g]["arms"][arm]["vs_base"]["lost"] for g in CANARIES}
        pos = sum(T["games"][g]["arms"][arm]["vs_base"]["seeds_up"] for g in CANARIES)
        neg = sum(T["games"][g]["arms"][arm]["vs_base"]["seeds_down"] for g in CANARIES)
        tot = {g: [T["games"][g]["arms"][arm]["vs_base"]["clears_arm"], T["games"][g]["arms"][arm]["vs_base"]["clears_base"]]
               for g, _ in GAMES}
        gate = ls[arm]["clear_l1"] == 20
        fa = {r_s: v[0] for r_s, v in ls[arm]["first_clears"].items() if v}
        fb = {r_s: v[0] for r_s, v in ls[BASE]["first_clears"].items() if v}
        slower = sum(fa[k] > fb[k] for k in fa if k in fb)
        faster = sum(fa[k] < fb[k] for k in fa if k in fb)
        speed = {"median": ls[arm]["first_clear_median"], "base_median": base_med,
                 "mean": round(st.mean(fa.values()), 1) if fa else None,
                 "base_mean": round(st.mean(fb.values()), 1) if fb else None,
                 "seeds_slower": slower, "seeds_faster": faster, "sign_p": round(sign_test(slower, faster), 4),
                 "slower": ls[arm]["first_clear_median"] is not None and base_med is not None
                 and ls[arm]["first_clear_median"] > base_med}
        T["judging"][arm] = {"guard_lost": guard_lost, "guard_pass": not any(guard_lost.values()),
                             "canary_pairs": 40, "canary_up": pos, "canary_down": neg,
                             "canary_clears": [tot["ls20"][0] + tot["g50t"][0], tot["ls20"][1] + tot["g50t"][1]],
                             "canary_sign_p": round(sign_test(pos, neg), 4), "totals_per_game": tot,
                             "locksmith_gate": gate, "locksmith": [ls[arm]["clear_l1"], ls[arm]["first_clear_median"],
                                                                   base_med], "locksmith_speed": speed}
    if prev:
        cur = {(r["game"], r["seed"]): r for r in rows if r["arm"] == BASE}
        same = diff = 0
        diffs = []
        for r in prev:
            c = cur.get((r["game"], r["seed"]))
            if c is None:
                continue
            eq = c["clear_at"] == r["clear_at"] and c["actions"] == r["actions"] and c["presses"] == r["presses"]
            same += eq
            diff += not eq
            if not eq:
                diffs.append([r["game"], r["seed"]])
        T["repro"] = {"same": same, "differ": diff, "which": diffs}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "tables.json").write_text(json.dumps(T, indent=1))
    (out / "tables.md").write_text(render(T))
    print(render(T))


def render(T: dict) -> str:
    L = []
    for g, G in T["games"].items():
        L += [f"## {G['name']} ({g})", "",
              "| arm | plays | levels | plays clearing level 1 | plays clearing level 2 | first clear (median action) | "
              "level 2 length (median) | game overs | RESETs per play | time-outs | play seconds (median) |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for arm, A in G["arms"].items():
            L.append(f"| {arm} | {A['plays']} | {A['levels']} | {A['clear_l1']} | {A['clear_l2']} | "
                     f"{A['first_clear_median']} | {A['level2_len_median']} | {A['game_overs']} | {A['resets_per_play']} | "
                     f"{A['timeouts']} | {A['seconds_median']} |")
        if g == "wa30":
            L += ["", "| arm | grab positions | interact there | grabs | drops | plays: box on target (seeds) | most on target |",
                  "|---|---|---|---|---|---|---|"]
            for arm, A in G["arms"].items():
                if "grab_pos" in A:
                    L.append(f"| {arm} | {A['grab_pos']} | {A['interact_at_grab']}/{A['grab_pos']} "
                             f"({round(100 * A['interact_rate'])}%) | {A['grabs']} | {A['drops']} | "
                             f"{A['plays_box_on_target']} ({', '.join(map(str, A['seeds_box_on_target'])) or '-'}) | "
                             f"{A['most_on_target']} |")
        L += ["", "| arm | seeds clearing | seeds clearing level 2 | vs d4_opt: clears (arm / base), seeds up / down, sign p "
              "| lost | gained |", "|---|---|---|---|---|---|"]
        for arm, A in G["arms"].items():
            if arm == "random":
                continue
            v = A.get("vs_base")
            vs = "-" if v is None else f"{v['clears_arm']} / {v['clears_base']}, {v['seeds_up']} / {v['seeds_down']}, " \
                                       f"{v['sign_p']}"
            L.append(f"| {arm} | {', '.join(map(str, A['seeds_clearing'])) or '-'} | "
                     f"{', '.join(map(str, A['seeds_level2'])) or '-'} | {vs} | "
                     f"{'-' if v is None else (', '.join(map(str, v['lost'])) or '-')} | "
                     f"{'-' if v is None else (', '.join(map(str, v['gained'])) or '-')} |")
        L += ["", "Re-learning after a restart (actions until the MAP rule set is right on 5 scored steps in a row; censored = "
                  "the next restart or the end came first; kept / MAP = the rule set that was MAP just before is still a "
                  "hypothesis / still MAP 10 actions later, restarts where it was not counts-only):", "",
              "| arm | kind | restarts (per play) | re-learned (median actions) | censored | kept at +10 | MAP at +10 |",
              "|---|---|---|---|---|---|---|"]
        for arm, A in G["arms"].items():
            for why, R in A.get("relearn", {}).items():
                if why == "library":
                    continue
                L.append(f"| {arm} | {why} | {R['events']} ({R['per_play']}) | {R['relearn_median']} | {R['censored']} | "
                         f"{R['kept_10']} | {R['map_10']} |")
        libs = [(arm, A["relearn"]["library"]) for arm, A in G["arms"].items() if A.get("relearn", {}).get("library")]
        if libs:
            L += ["", "| arm | library sets (median) | library rules (median) | sets re-seeded per play |", "|---|---|---|---|"]
            L += [f"| {arm} | {x['sets_median']} | {x['rules_median']} | {x['seeded_per_play']} |" for arm, x in libs]
        L += ["", "| arm | try-once presses | per play | would have pressed anyway (G button < G continuing) | "
                  "comparison interruptions per play |", "|---|---|---|---|---|"]
        for arm, A in G["arms"].items():
            if "try" in A:
                t = A["try"]
                L.append(f"| {arm} | {t['try_presses']} | {t['try_per_play']} | {t['would_press_anyway']} | "
                         f"{t['interrupt_per_play']} |")
        if g in ("ls20", "g50t"):
            L += ["", "First clears per seed (action of level 1, level 2):", ""]
            for arm, A in G["arms"].items():
                if "first_clears" in A:
                    L.append(f"- {arm}: " + "; ".join(f"{s}: {v or '-'}" for s, v in sorted(A["first_clears"].items())))
        L.append("")
    L += ["## Judging", "",
          "| arm | per-seed guard (canary seeds lost vs d4_opt) | canary clears arm / base (40 pairs), seeds up / down, sign p "
          "| clears per game arm / base (wa30, ls20, g50t) | Locksmith level one 20/20 | Locksmith speed: first clear median "
          "(mean) arm vs base, seeds slower / faster, sign p |",
          "|---|---|---|---|---|---|"]
    for arm, J in T["judging"].items():
        lost = "; ".join(f"{g}: {', '.join(map(str, v)) or 'none'}" for g, v in J["guard_lost"].items())
        tp = ", ".join(f"{a}/{b}" for a, b in J["totals_per_game"].values())
        sp = J["locksmith_speed"]
        L.append(f"| {arm} | {'PASS' if J['guard_pass'] else 'FAIL'} ({lost}) | {J['canary_clears'][0]} / "
                 f"{J['canary_clears'][1]}, {J['canary_up']} / {J['canary_down']}, {J['canary_sign_p']} | {tp} | "
                 f"{'PASS' if J['locksmith_gate'] else 'FAIL'} ({J['locksmith'][0]}/20) | "
                 f"{sp['median']} ({sp['mean']}) vs {sp['base_median']} ({sp['base_mean']}), {sp['seeds_slower']} / "
                 f"{sp['seeds_faster']}, {sp['sign_p']}{' -- SLOWER' if sp['slower'] else ''} |")
    if T.get("repro"):
        R = T["repro"]
        L += ["", f"Reproduction: d4_opt rerun vs debate four's d4_opt rows: {R['same']} plays identical (clears, actions, "
                  f"presses), {R['differ']} differ {R['which'][:10]}."]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()

"""Harness x game analysis over dataset.json."""
import json, re, statistics as st, collections
from pathlib import Path

SP = Path(__file__).resolve().parent
D = json.load(open(SP / "dataset.json"))
runs = D["runs"]; gacts = D["game_actions"]
H7 = ["bp35", "g50t", "lf52", "ls20", "sk48", "tn36", "wa30"]
GAMES = sorted({g for r in runs.values() for g in r["games"]})

# family classifier: (regex on run_id, family label, clock)
FAM = [
    (r"cv5cr-hard7-(execution|memory|symbolic|solver|selfcheck)-132", "h7arm:\\1", "h7-132"),
    (r"cv5cr-hard7-264", "cv5-CR", "h7-264"),
    (r"cv5cr264", "cv5-CR", "264"),
    (r"lacr264", "LA-CR", "264"),
    (r"compaction-v5-clean-return-[ab]132", "cv5-CR", "132"),
    (r"la-clean-return-[ab]132", "LA-CR", "132"),
    (r"lacr-(batched16k|effort-medium|nopreserve|xxhigh)", "LA-CR serving-knob", "132"),
    (r"la-v5-clean-return", "LA-v5", "132"),
    (r"lab-v5-clean-return", "LAB-v5", "132"),
    (r"lab-clean-return", "LAB-CR", "132"),
    (r"larf-clean-return", "LA-RF", "132"),
    (r"lb-v5-clean-return", "LB-v5", "132"),
    (r"lb-clean-return", "LB-CR", "132"),
    (r"clean-return264", "clean-return", "264"),
    (r"clean-return-repeat132|cap-return132", "clean-return", "132"),
    (r"compaction-no-cap264", "compaction no-cap", "264"),
    (r"compaction-no-cap132", "compaction no-cap", "132"),
    (r"no-cap264", "no-cap", "264"),
    (r"no-cap(-repeat)?132", "no-cap", "132"),
    (r"legacycap264", "legacy cap", "264"),
    (r"reset-compaction132", "reset-compaction", "132"),
    (r"reset-middle132", "reset-middle", "132"),
    (r"reset-visible132", "reset-visible", "132"),
    (r"symbolic-v2-controls132", "symbolic-v2 controls", "132"),
    (r"symbolic-v2132", "symbolic-v2", "132"),
    (r"sym264", "symbolic (sym264)", "264"),
    (r"cleanrem264", "cleanrem", "264"),
    (r"cleanrem132", "cleanrem", "132"),
    (r"swap30_132", "swap30", "132"), (r"swap70_132", "swap70", "132"),
    (r"swap50-search132|swap50rep132|upper-swap50132|upper4-swap50132", "swap50", "132"),
    (r"prompt-transition264", "prompt-transition", "264"), (r"transition264rep", "transition", "264"),
    (r"loopa132", "loop-A (early)", "132"),
    (r"astra-grid2-b476", "astra grid2 b476", "264"), (r"astra-grid2-b720", "astra grid2 b720", "264"),
]
def fam(run_id):
    for pat, lab, clock in FAM:
        m = re.search(pat, run_id)
        if m:
            return re.sub(r"\\\\1", lambda _: m.group(1), lab) if "\\1" in lab else lab, clock
    return "other:" + re.sub(r"^g4run-|-w\d+.*$|-2026\d{4}.*$", "", run_id), ("264" if "264" in run_id else "132")

for r in runs.values():
    r["family"], r["clock"] = fam(r["run_id"])

def mean(xs): return sum(xs) / len(xs) if xs else float("nan")

# ------------------------------------------------------------------ A. families
print("\n=== A. families (25-game runs), mean of per-run values ===")
groups = collections.defaultdict(list)
for r in runs.values():
    if len(r["games"]) == 25: groups[(r["family"], r["clock"])].append(r)
rows = []
for (f, ck), rs in groups.items():
    h7 = [mean([r["games"][g]["score"] for g in H7 if g in r["games"]]) for r in rs]
    h7l = [sum(r["games"][g]["levels"] for g in H7 if g in r["games"]) for r in rs]
    rows.append((ck, f, len(rs), mean([r["avg"] for r in rs]), mean([r["levels"] for r in rs]), mean([r["actions"] for r in rs]), mean(h7), mean(h7l)))
for ck, f, n, a, l, ac, h7, h7l in sorted(rows, key=lambda x: (x[0], -x[3])):
    print(f"{ck:>4} {f:28s} n={n:2d} mean={a:6.2f} levels={l:5.1f} actions={ac:6.0f} act/level={ac/l:5.0f}  h7={h7:5.2f} h7lv={h7l:4.1f}")

# ------------------------------------------------------------------ B. games
print("\n=== B. games: difficulty and character (all 25-game runs) ===")
g25 = [r for r in runs.values() if len(r["games"]) == 25]
ginfo = {}
for g in GAMES:
    sc = [r["games"][g]["score"] for r in g25 if g in r["games"]]
    lv = [r["games"][g]["levels"] for r in g25 if g in r["games"]]
    ac = [r["games"][g]["actions"] for r in g25 if g in r["games"]]
    lt = max(r["games"][g]["levels_total"] for r in g25 if g in r["games"])
    a = gacts.get(g, {}); tot = sum(a.values()) or 1
    mouse = a.get("MOUSE", 0) / tot; space = a.get("SPACE", 0) / tot
    solved = sum(1 for r in g25 if g in r["games"] and r["games"][g]["levels"] >= lt)
    apl = sum(ac) / max(1, sum(lv))
    ginfo[g] = dict(lt=lt, mean=mean(sc), sd=st.pstdev(sc) if len(sc) > 1 else 0, maxs=max(sc), lv=mean(lv), apl=apl, mouse=mouse, space=space, solved=solved, n=len(sc))
    print(f"{g} lv_total={lt:2d} mean={ginfo[g]['mean']:5.1f} sd={ginfo[g]['sd']:5.1f} max={max(sc):5.1f} lv/run={mean(lv):4.1f} act/level={apl:5.0f} mouse={mouse:4.0%} space={space:4.0%} fullclears={solved:2d}/{len(sc)}")

# ------------------------------------------------------------------ C. family x game (families with n>=2 at 132, and all 264)
print("\n=== C. family x game mean score ===")
sel = [k for k, rs in groups.items() if (len(rs) >= 2 and k[1] == "132") or k[1] == "264"]
sel.sort(key=lambda k: (k[1], -mean([r["avg"] for r in groups[k]])))
print("game  " + " ".join(f"{(k[0][:9]+'/'+k[1][:3]):>13s}" for k in sel))
for g in GAMES:
    line = f"{g}  "
    for k in sel:
        v = mean([r["games"][g]["score"] for r in groups[k] if g in r["games"]])
        line += f"{v:13.1f} "
    print(line)
# best family per game (132 only, n>=2)
print("\n=== C2. best 132 family per game (n>=2) and its margin over the median family ===")
sel132 = [k for k in sel if k[1] == "132"]
for g in GAMES:
    vals = sorted(((mean([r["games"][g]["score"] for r in groups[k] if g in r["games"]]), k[0]) for k in sel132), reverse=True)
    med = st.median(v for v, _ in vals)
    print(f"{g}: best {vals[0][1]:22s} {vals[0][0]:5.1f} | 2nd {vals[1][1]:22s} {vals[1][0]:5.1f} | median {med:5.1f} | worst {vals[-1][1]:22s} {vals[-1][0]:5.1f}")

# ------------------------------------------------------------------ D. clock effect per game
print("\n=== D. 132 -> 264 per game (same family) ===")
pairs = [("clean-return",), ("no-cap",), ("compaction no-cap",), ("cv5-CR",), ("LA-CR",)]
for (f,) in pairs:
    a = groups.get((f, "132"), []); b = groups.get((f, "264"), [])
    if not a or not b: continue
    print(f"-- {f}: 132 n={len(a)} mean={mean([r['avg'] for r in a]):.2f}  264 n={len(b)} mean={mean([r['avg'] for r in b]):.2f}")
    line = []
    for g in GAMES:
        x = mean([r["games"][g]["score"] for r in a if g in r["games"]]); y = mean([r["games"][g]["score"] for r in b if g in r["games"]])
        line.append(f"{g}:{x:.0f}->{y:.0f}")
    print("   " + " ".join(line))

# ------------------------------------------------------------------ E. hard-7 arms (7-game runs)
print("\n=== E. hard-seven one-wave arms (7-game mean; per game score/levels) ===")
for r in sorted(runs.values(), key=lambda r: -r["avg"]):
    if len(r["games"]) == 7:
        print(f"{r['family']:18s} {r['clock']:6s} mean={r['avg']:5.2f} levels={r['levels']:2d} actions={r['actions']:5d}  " + " ".join(f"{g}={r['games'][g]['score']:.1f}/{r['games'][g]['levels']}" for g in H7 if g in r["games"]))
json.dump({"ginfo": ginfo}, open(SP / "ginfo.json", "w"), indent=1)

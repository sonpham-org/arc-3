"""In-play test scores of the RL box's models (4-Oct-2026, Son: "every game play once or twice ... so that we have the
score right away"; plan C, rl/box/README.md). Every model's campaign starts with its test slice (pick_nodes.test_jobs:
the same restart points for every model, 2 tries at each game's frontier level and 1 at the level below); this reads
those tries back and prints, per model, the clear rate at the frontier levels next to the base model's rate at the same
levels (from its full plays), for the 14 training games and the 6 never-trained games apart. The held-out five play
whole games on the box's test card (box_panel.sh); score those with ops/score_panel.py.
  C:/Python312/python.exe ops/test_report.py --state D:/codex-work/rl-20261001/c_state.json [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from pathlib import Path

GCLOUD = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
STORE = "gs://cellens-ai-artifacts/arc3-gtree/v1/rl"
TRAIN = set("bp35,cn04,g50t,ka59,ls20,m0r0,r11l,s5i5,sc25,sk48,sp80,tu93,vc33,wa30".split(","))


def g(*args: str) -> str:
    p = subprocess.run(GCLOUD + list(args), capture_output=True, text=True, timeout=600)
    return p.stdout.replace("\r", "")


def campaign_tests(camp: str, cache: Path) -> list[dict]:
    """[{game, level, frontier, base: [cleared, reached], cleared}] for every finished test try of the campaign."""
    d = cache / camp
    d.mkdir(parents=True, exist_ok=True)
    for sub in ("jobs", "tries"):
        # stdin closed: a gcloud that waits for input hangs the page build (5-Oct: 14 min on 77 job files)
        excl = ["-x", r".*(?<!\.json)$"] if sub == "tries" else []
        try:
            subprocess.run(GCLOUD + ["storage", "rsync", "-r", *excl, f"{STORE}/{camp}/{sub}", str(d / sub)],
                           capture_output=True, stdin=subprocess.DEVNULL, timeout=600)
        except subprocess.TimeoutExpired:
            pass
    specs = {}
    for f in (d / "jobs").rglob("*.json"):
        j = json.loads(f.read_text(encoding="utf-8"))
        if (j.get("pick") or {}).get("class") == "test":
            specs[j["job_id"]] = j
    out = []
    for f in (d / "tries").rglob("result.json"):
        r = json.loads(f.read_text(encoding="utf-8"))
        j = specs.get(r.get("job"))
        if not j or r.get("status") != "done":
            continue
        pk = j["pick"]
        out.append({"game": str(j["game_id"]).split("-")[0], "level": pk["level"], "frontier": pk["frontier"],
                    "base": pk.get("base_rate"), "cleared": bool(r.get("cleared"))})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", required=True, help="run_c.py's c_state.json")
    ap.add_argument("--cache", default=r"D:\codex-work\rl-20261001\test-report-cache")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    st = json.loads(Path(a.state).read_text(encoding="utf-8"))
    rows = []
    for c in st.get("campaigns", []):
        tests = campaign_tests(c["campaign"], Path(a.cache))
        agg = defaultdict(lambda: [0, 0, 0.0])        # group -> [clears, tries, base rate sum]
        for t in tests:
            if t["level"] != t["frontier"]:
                continue
            grp = "trained" if t["game"] in TRAIN else "never trained"
            b = t["base"] or [0, 0]
            agg[grp][0] += t["cleared"]
            agg[grp][1] += 1
            agg[grp][2] += (b[0] / b[1]) if b[1] else 0.0
        row = {"model": c["merge"], "campaign": c["campaign"], "test_tries_done": len(tests)}
        for grp, (k, n, bs) in agg.items():
            row[grp] = {"cleared": k, "tries": n, "rate": round(k / n, 2) if n else None,
                        "base_rate": round(bs / n, 2) if n else None}
        rows.append(row)
    print(f"{'model':16} {'tests':>5}  {'trained games: model / base':>30}  {'never-trained: model / base':>30}")
    for r in rows:
        def cell(grp):
            x = r.get(grp)
            return f"{x['cleared']}/{x['tries']} = {x['rate']:.0%} / {x['base_rate']:.0%}" if x and x["tries"] else "-"
        print(f"{r['model']:16} {r['test_tries_done']:>5}  {cell('trained'):>30}  {cell('never trained'):>30}")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

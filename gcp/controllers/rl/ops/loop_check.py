"""Copy-paste looping in a run's thinking (3-Oct sc25 audit: training made the model paste the same reasoning block
again and again within one reply; base 0.0% of its thinking, first-recipe R1 4.0%, R2 7.2%).

For every transcript of each run: each [THINKING] block is one reply; a line of >= 60 characters already seen earlier
in the same reply counts as repeated. Prints, per run, the repeated share of all thinking, the replies that are more
than 30% repeated (and over 5,000 characters), and the share per game. Over 1% = the round looped (base: 0.0-0.1%).

  python loop_check.py <run id> [<run id> ...]        (downloads transcripts/ to D:/codex-work/rl-20261001/loopcheck)
"""
from __future__ import annotations

import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

GCLOUD = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
RUNS = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"
CACHE = Path("D:/codex-work/rl-20261001/loopcheck")
LIMIT = 1.0      # percent


def replies(path: Path) -> list[list[str]]:
    out, cur, mode = [], None, None
    for s in path.open(encoding="utf-8", errors="replace"):
        s = s.rstrip("\n")
        if s.startswith("--- analysis_step="):
            mode = None
            continue
        m = re.match(r"^\[([A-Z _]+)", s)
        if m:
            mode = m.group(1)
            if mode == "THINKING":
                cur = []
                out.append(cur)
            continue
        if mode == "THINKING":
            cur.append(s)
    return out


def repeated(reply: list[str]) -> tuple[int, int]:
    seen, rep, tot = set(), 0, 0
    for ln in reply:
        k = ln.strip()
        if len(k) < 60:
            continue
        tot += len(k)
        if k in seen:
            rep += len(k)
        seen.add(k)
    return tot, rep


def check(run: str) -> dict:
    d = CACHE / run
    d.mkdir(parents=True, exist_ok=True)
    subprocess.run(GCLOUD + ["storage", "cp", "-r", f"{RUNS}/{run}/working/transcripts/*", str(d)],
                   capture_output=True, text=True)
    per = defaultdict(lambda: [0, 0])
    bad = 0
    for f in sorted(d.glob("*.txt")):
        for r in replies(f):
            tot, rep = repeated(r)
            per[f.name[:4]][0] += tot
            per[f.name[:4]][1] += rep
            if tot > 5000 and rep / tot > 0.3:
                bad += 1
    tot = sum(v[0] for v in per.values())
    rep = sum(v[1] for v in per.values())
    return {"run": run, "files": len(list(d.glob("*.txt"))), "pct": 100 * rep / max(tot, 1), "bad": bad,
            "games": {g: 100 * v[1] / max(v[0], 1) for g, v in sorted(per.items())}}


def main() -> int:
    worst = 0.0
    for run in sys.argv[1:]:
        r = check(run)
        worst = max(worst, r["pct"])
        games = "  ".join(f"{g} {p:.1f}" for g, p in r["games"].items())
        print(f"{r['run']}: repeated {r['pct']:.1f}% of thinking, {r['bad']} looping replies, {r['files']} transcripts"
              f" | {games}", flush=True)
    print(f"{'LOOPING' if worst > LIMIT else 'ok'}: worst {worst:.1f}% (limit {LIMIT}%; base 0.0-0.1%)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

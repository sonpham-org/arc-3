"""Token-matched scores (3-Oct-2026, daniel-draft; Son: "compare the score at the same amount of tokens").

Reads gs://.../daniel-draft/tokmatch/out/<run>.json (written by extract.py on the tokmatch VM). Every game is cut at
the same generated-token budget X (completion tokens, thinking included): the responses whose running total stays
within X are paid for, a level counts if it was completed by the actions those responses decided (response "action"
= next action number), and actions per level come from the viewer. Score at X = our ruler (game_score, all 25).

"cut" = share of the 25 games that the 132-min clock stopped before they had spent X tokens (not won / not over):
past the budget where cut gets large, a group is being scored on its clock, not on its tokens.

  python score_at_tokens.py --group "4-bit 16"=daniel-ctx-kv4s16-a-1003,... [--group ...] [--budgets 50,100,...]
"""
import argparse
import json
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from itertools import accumulate

sys.path.insert(0, r"D:\codex-work\arc3-sglang-parking\gcp")
import arc3_firestore_scores as fs  # noqa: E402

G = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
O = "gs://cellens-ai-artifacts/arc3-duck/daniel-draft/tokmatch/out"
BASE = fs.observer.BASE_ACTIONS
ENDED = {"won", "lost", "game_over", "gameover", "dead", "over"}


def load(run):
    r = subprocess.run(G + ["storage", "cat", f"{O}/{run}.json"], capture_output=True)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout else None


def game_at(g, x):
    """(score, levels, cut) of one game at per-game budget x tokens."""
    v = g.get("viewer") or {}
    levels = int(v.get("levels_completed") or 0)
    apl = [int(a) for a in (v.get("actions_per_level") or [])][:levels]
    done_at = list(accumulate(apl))  # action number that completed each level
    resp = g.get("resp") or []
    total = sum(r[2] for r in resp)
    if x >= total:
        ended = str(v.get("status") or "").lower() in ENDED
        return levels, apl, (not ended and total < x)
    run_tok, acts = 0, None
    for step, action, ctok, _ in resp:
        run_tok += ctok
        if run_tok > x:
            acts = action - 1
            break
    n = sum(1 for a in done_at if a <= acts)
    return n, apl[:n], False


def score(data, x):
    s, lv, cut = [], 0, 0
    for gid, base in BASE.items():
        g = data["games"].get(gid)
        if not g:
            s.append(0.0); cut += 1; continue
        n, apl, c = game_at(g, x)
        s.append(fs.observer.game_score(n, apl, base)); lv += n; cut += c
    return statistics.mean(s), lv, cut / len(BASE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", action="append", required=True, help='NAME=RUN,RUN,...')
    ap.add_argument("--budgets", default="25,50,100,150,200,300,400,600,800,100000")
    a = ap.parse_args()
    groups = [(n, rs.split(",")) for n, rs in (g.split("=", 1) for g in a.group)]
    runs = sorted({r for _, rs in groups for r in rs})
    with ThreadPoolExecutor(8) as ex:
        data = dict(zip(runs, ex.map(load, runs)))
    missing = [r for r in runs if not data[r]]
    if missing:
        print("not extracted yet:", " ".join(missing))
    xs = [int(b) * 1000 for b in a.budgets.split(",")]
    print("per-game token budget (thousand) -> score (levels, % games the clock cut before the budget)")
    print(f"{'group':22s} {'n':>2s} " + " ".join(f"{('full' if x >= 10**8 else x // 1000):>15}" for x in xs))
    for name, rs in groups:
        ok = [data[r] for r in rs if data[r]]
        if not ok:
            continue
        cells = []
        for x in xs:
            res = [score(d, x) for d in ok]
            cells.append(f"{statistics.mean(r[0] for r in res):5.1f} ({statistics.mean(r[1] for r in res):3.0f},{100 * statistics.mean(r[2] for r in res):3.0f}%)")
        print(f"{name:22s} {len(ok):2d} " + " ".join(f"{c:>15}" for c in cells))
    print("\nper run: full score (check vs grid_report), total generated tokens, median tokens per game")
    for r in runs:
        d = data[r]
        if not d:
            continue
        tot = [sum(x[2] for x in g.get("resp") or []) for g in d["games"].values()]
        print(f"  {r:32s} {score(d, 10**12)[0]:6.2f}  {sum(tot) / 1e6:5.2f}M  {statistics.median(tot) / 1e3:5.0f}k")


if __name__ == "__main__":
    main()

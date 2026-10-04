"""Pick a round's training records from g0_data's advantage records (4-Oct restart after R0).

Every played level of every attempt now carries an advantage (its reward minus the game's mean over the attempts,
build_records.level_advantages), so a run yields far more records than a round can train (~5 min per record). This
keeps a fixed budget, split between positive records (better than the game's average) and negative ones (worse), each
side by largest |advantage| first, with at most --per-attempt records from one attempt of one game on each side (a
stuck attempt has many long stretches; without the cap one of them would fill the negative side).

  python select_records.py --in '/opt/m/work/g0r1/*/records/*.jsonl.gz' --out /opt/m/work/records/041 --budget 32
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
from collections import Counter
from pathlib import Path


def record_sign_and_size(rec: dict) -> tuple[int, float]:
    """(+1 / -1 by the mean trained weight, max |trained weight|); (0, 0) when nothing is trained."""
    ws = [w for w, t in zip(rec.get("weights") or [], rec["train"]) if t]
    if not ws:
        return 0, 0.0
    mean = sum(ws) / len(ws)
    return (1 if mean > 0 else -1 if mean < 0 else 0), max(abs(w) for w in ws)


def select(recs: list[dict], budget: int, neg_share: float, per_attempt: int) -> list[dict]:
    sides = {1: [], -1: []}
    for i, r in enumerate(recs):
        s, size = record_sign_and_size(r)
        if s:
            sides[s].append((-size, i, r))
    want = {-1: round(budget * neg_share)}
    want[1] = budget - want[-1]
    picked: list[dict] = []
    for s in (1, -1):
        per: Counter = Counter()
        for _, _, r in sorted(sides[s], key=lambda t: (t[0], t[1])):
            if len([p for p in picked if record_sign_and_size(p)[0] == s]) >= want[s]:
                break
            key = (r["meta"].get("run"), r["meta"].get("game"), r["meta"].get("pass"))
            if per[key] >= per_attempt:
                continue
            per[key] += 1
            picked.append(r)
    # a short side leaves budget the other side can use
    left = budget - len(picked)
    if left > 0:
        chosen = {id(p) for p in picked}
        rest = sorted((t for s in (1, -1) for t in sides[s] if id(t[2]) not in chosen), key=lambda t: (t[0], t[1]))
        picked += [r for _, _, r in rest[:left]]
    return picked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="src", required=True, help="glob of g0_data records files (*.jsonl.gz)")
    ap.add_argument("--out", required=True, help="records dir for the trainer (one .jsonl.gz per record)")
    ap.add_argument("--budget", type=int, default=32)
    ap.add_argument("--neg-share", type=float, default=0.5)
    ap.add_argument("--per-attempt", type=int, default=3)
    args = ap.parse_args()
    recs = []
    for f in sorted(glob.glob(args.src)):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            recs += [json.loads(line) for line in fh if line.strip()]
    picked = select(recs, args.budget, args.neg_share, args.per_attempt)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(picked):
        with gzip.open(out / f"{i:03d}-{r['meta'].get('game', 'x')[:4]}-p{r['meta'].get('pass', 0)}.jsonl.gz", "wt",
                       encoding="utf-8") as fh:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    signs = Counter(record_sign_and_size(r)[0] for r in picked)
    games = Counter(r["meta"].get("game", "?")[:4] for r in picked)
    print(json.dumps({"candidates": len(recs), "picked": len(picked), "positive": signs[1], "negative": signs[-1],
                      "games": dict(games)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

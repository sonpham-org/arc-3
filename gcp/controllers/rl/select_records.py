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


def game_key(rec: dict) -> str:
    """The game for the per-game cap: its 4-letter name. try_records.py's meta "game" is a game id with a suffix
    ("cn04-<hash>") that differs between plays, so the cap counted every play as its own game (4-Oct plan C's first
    cut: cn04 got 15 of 48 records under a cap of 4 per side)."""
    return str(rec["meta"].get("game") or "?")[:4]


def select(recs: list[dict], budget: int, neg_share: float, per_attempt: int, per_game: int = 0) -> list[dict]:
    """per_game (> 0): at most this many records of one game on each side (4-Oct n0: 6 of its 24 records were sc25
    negatives; pushed down six times, a few sc25 tokens fell ~e^10 and the KL term exploded)."""
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
        per_g: Counter = Counter()
        for _, _, r in sorted(sides[s], key=lambda t: (t[0], t[1])):
            if len([p for p in picked if record_sign_and_size(p)[0] == s]) >= want[s]:
                break
            key = (r["meta"].get("run"), r["meta"].get("game"), r["meta"].get("pass"))
            game = game_key(r)
            if per[key] >= per_attempt or (per_game and per_g[game] >= per_game):
                continue
            per[key] += 1
            per_g[game] += 1
            picked.append(r)
    # a short side leaves budget the other side can use
    left = budget - len(picked)
    if left > 0:
        chosen = {id(p) for p in picked}
        side_game = Counter((record_sign_and_size(p)[0], game_key(p)) for p in picked)
        rest = sorted((t for s in (1, -1) for t in sides[s] if id(t[2]) not in chosen), key=lambda t: (t[0], t[1]))
        for _, _, r in rest:                 # the per-game cap holds here too
            if left <= 0:
                break
            k = (record_sign_and_size(r)[0], game_key(r))
            if per_game and side_game[k] >= per_game:
                continue
            side_game[k] += 1
            picked.append(r)
            left -= 1
    return picked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="src", required=True, help="glob of g0_data records files (*.jsonl.gz)")
    ap.add_argument("--out", required=True, help="records dir for the trainer (one .jsonl.gz per record)")
    ap.add_argument("--budget", type=int, default=32)
    ap.add_argument("--neg-share", type=float, default=0.5)
    ap.add_argument("--per-attempt", type=int, default=3)
    ap.add_argument("--per-game", type=int, default=4, help="at most this many records of one game on each side (0 = no cap)")
    args = ap.parse_args()
    recs = []
    for f in sorted(glob.glob(args.src)):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            recs += [json.loads(line) for line in fh if line.strip()]
    picked = select(recs, args.budget, args.neg_share, args.per_attempt, args.per_game)
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

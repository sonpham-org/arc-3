#!/usr/bin/env python3.13
"""One-off: rebuild the leaderboard's past from the public per-team daily history that
https://arc3.huikang.dev/leaderboard/ publishes (it has polled Kaggle since June).

Writes docs/static/data/leaderboard/backfill.json. The page shows it before our own snapshots begin.
Per day it works out every team's rank by carrying each team's last known score forward.
"""
import bisect, json, urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from leaderboard_snapshot import OUR_TEAM_ID, TRAIL_TOP, EVENT_RANK, medal_ranks

URL = "https://tonghuikang--arc3-leaderboard-monitor-get-history.modal.run"
OUT = Path(__file__).resolve().parent.parent / "docs/static/data/leaderboard/backfill.json"


def main():
    d = json.load(urllib.request.urlopen(URL, timeout=120))
    names = {p[0]: p[1] for p in d["positions"]}
    cur = {p[0]: float(p[4]) for p in d["positions"]}
    series = {}                     # team -> sorted [(day, score)]; last entry of a day wins
    for tid, h in d["history"].items():
        byday = {}
        for k in sorted(h):
            byday[k[:10]] = float(h[k][0])
        if byday:
            series[tid] = sorted(byday.items())
    first = min(s[0][0] for s in series.values())
    today = datetime.now(timezone.utc).date()
    days, day = [], date.fromisoformat(first)
    while day < today:               # today onward is covered by our own snapshots
        days.append(day.isoformat()); day += timedelta(days=1)

    def score_on(tid, day):
        s = series.get(tid)
        if not s:
            return None
        i = bisect.bisect_right([x[0] for x in s], day) - 1
        return s[i][1] if i >= 0 else None

    keep = {t for t, _ in sorted(cur.items(), key=lambda kv: -kv[1])[:TRAIL_TOP]} | {OUR_TEAM_ID}
    snaps, trails, events, prev_rank = [], {t: {"name": names.get(t, t), "pts": []} for t in keep}, [], {}
    prev_score = {}
    for day in days:
        board = sorted(((score_on(t, day), t) for t in series), key=lambda x: (x[0] is None, -(x[0] or 0)))
        board = [(s, t) for s, t in board if s is not None]
        n = len(board)
        if not n:
            continue
        cuts = medal_ranks(n)
        at = lambda r: board[min(r, n) - 1][0]
        t_iso = f"{day}T23:59:00Z"
        snaps.append({"t": t_iso, "teams": n, "top": at(1), "gold": at(cuts["gold"]), "silver": at(cuts["silver"]),
                      "bronze": at(cuts["bronze"]), "src": "backfill"})
        for rank, (s, t) in enumerate(board, 1):
            if t in keep:
                pts = trails[t]["pts"]
                if not pts or pts[-1][1:] != [s, rank]:
                    pts.append([t_iso, s, rank])
            if (rank <= EVENT_RANK or t == OUR_TEAM_ID) and prev_score.get(t) not in (None, s):
                events.append({"t": t_iso, "id": t, "name": names.get(t, t), "from": prev_score[t], "to": s,
                               "rankFrom": prev_rank.get(t), "rankTo": rank, "src": "backfill"})
            prev_score[t], prev_rank[t] = s, rank
    trails = {t: v for t, v in trails.items() if v["pts"]}
    OUT.write_text(json.dumps({"built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "snaps": snaps,
                               "trails": trails, "events": events[-2000:]}, separators=(",", ":")))
    print(f"{len(snaps)} days from {first}, {len(trails)} trails, {len(events)} events -> {OUT}")


if __name__ == "__main__":
    main()

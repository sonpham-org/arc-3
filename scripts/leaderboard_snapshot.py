#!/usr/bin/env python3.13
"""Pull the public ARC-AGI-3 Kaggle leaderboard and keep our own history of it.

Writes docs/static/data/leaderboard/latest.json (every team, right now) and
history.json (one line per snapshot, plus a score/rank trail for the top teams and ours).
Run it on a schedule; the Leaderboard tab on the site reads those two files.
"""
import csv, io, json, subprocess, sys, tempfile, zipfile
from datetime import datetime, timezone
from pathlib import Path

COMP = "arc-prize-2026-arc-agi-3"
OUR_TEAM_ID = "15605182"          # Son Pham & Mark Barney
TRAIL_TOP = 100                   # teams with a kept score/rank trail
OUT = Path(__file__).resolve().parent.parent / "docs/static/data/leaderboard"


def medal_ranks(n):
    """Kaggle medal cut-offs (competitions with 250+ teams)."""
    gold = 10 + int(n * 0.002)
    return {"gold": gold, "silver": int(n * 0.05), "bronze": int(n * 0.10)}


def fetch_rows():
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["kaggle", "competitions", "leaderboard", "-c", COMP, "--download", "-p", d],
                       check=True, capture_output=True)
        z = next(Path(d).glob("*.zip"))
        with zipfile.ZipFile(z) as zf:
            raw = zf.read(zf.namelist()[0]).decode("utf-8-sig")
    rows = []
    for r in csv.DictReader(io.StringIO(raw)):
        rows.append([int(r["Rank"]), r["TeamId"], r["TeamName"], r["LastSubmissionDate"],
                     float(r["Score"]), int(r["SubmissionCount"]), r["TeamMemberUserNames"]])
    return rows


def main():
    rows = fetch_rows()
    if len(rows) < 100:
        sys.exit(f"only {len(rows)} rows came back; refusing to overwrite the leaderboard")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = [r for r in rows if r[0] > 0]   # rank 0 = host baseline entries, not competitors
    assert [r[0] for r in rows] == list(range(1, len(rows) + 1)), "ranks are not contiguous"
    n = len(rows)
    cuts = medal_ranks(n)
    by_rank = {r[0]: r[4] for r in rows}
    OUT.mkdir(parents=True, exist_ok=True)

    # "Today" baseline: where everyone stood at the end of the previous UTC day, so the
    # table can show who moved. Rolls forward once per UTC day.
    today = now[:10]
    bp, lp = OUT / "base.json", OUT / "latest.json"
    base = json.loads(bp.read_text()) if bp.exists() else None
    if base is None or base["date"] != today:
        prev = json.loads(lp.read_text()) if lp.exists() else None
        src = prev["rows"] if prev else rows
        base = {"date": today, "ranks": {r[1]: [r[0], r[4]] for r in src}}
        bp.write_text(json.dumps(base, separators=(",", ":")))
    for r in rows:
        b = base["ranks"].get(r[1])
        r.extend([b[0], b[1]] if b else [None, None])

    (OUT / "latest.json").write_text(json.dumps(
        {"fetched": now, "teams": n, "medalRanks": cuts, "ourTeamId": OUR_TEAM_ID, "rows": rows},
        separators=(",", ":")))

    hp = OUT / "history.json"
    hist = json.loads(hp.read_text()) if hp.exists() else {"snaps": [], "trails": {}}
    hist["snaps"].append({"t": now, "teams": n, "top": rows[0][4],
                          "gold": by_rank.get(cuts["gold"]), "silver": by_rank.get(cuts["silver"]),
                          "bronze": by_rank.get(cuts["bronze"])})
    for r in rows:
        if r[0] <= TRAIL_TOP or r[1] == OUR_TEAM_ID:
            trail = hist["trails"].setdefault(r[1], {"name": r[2], "pts": []})
            trail["name"] = r[2]
            if not trail["pts"] or trail["pts"][-1][1:] != [r[4], r[0]]:
                trail["pts"].append([now, r[4], r[0]])
    hp.write_text(json.dumps(hist, separators=(",", ":")))
    print(f"{now}: {n} teams, top {rows[0][4]}, gold line {by_rank.get(cuts['gold'])} (rank {cuts['gold']})")


if __name__ == "__main__":
    main()

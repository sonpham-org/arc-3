"""Copy-paste looping in a rollout campaign's tries (Son 4-Oct: a round must not wait 2.5 h for the previous model's
test games to learn whether it loops). The tries are played by the model the round trains from, and every try logs
each live reply with its reasoning (<try>/replies.jsonl), so the same check as loop_check.py runs on them as soon as
the tries end: a line of >= 60 characters already seen earlier in the same reply counts as repeated. Over 1% of the
reasoning = LOOPING (the base model: 0.0-0.1%; the first recipe's R2: 7.2%).

  python loop_check_tries.py <campaign>        (downloads to D:/codex-work/rl-20261001/loopcheck/tries-<campaign>)
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

GCLOUD = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
STORE = "gs://cellens-ai-artifacts/arc3-gtree/v1/rl"
CACHE = Path("D:/codex-work/rl-20261001/loopcheck")
LIMIT = 1.0


def repeated(text: str) -> tuple[int, int]:
    seen, rep, tot = set(), 0, 0
    for ln in (text or "").split("\n"):
        k = ln.strip()
        if len(k) < 60:
            continue
        tot += len(k)
        if k in seen:
            rep += len(k)
        seen.add(k)
    return tot, rep


def main() -> int:
    campaign = sys.argv[1]
    d = CACHE / f"tries-{campaign}"
    d.mkdir(parents=True, exist_ok=True)
    subprocess.run(GCLOUD + ["storage", "rsync", "-r", "-x", r"^(?!.*replies\.jsonl$).*", f"{STORE}/{campaign}/tries",
                             str(d)], capture_output=True, text=True)
    files = sorted(d.rglob("replies.jsonl"))
    per = defaultdict(lambda: [0, 0])
    bad = n = 0
    for f in files:
        game = next((p.split("-")[0][:4] for p in f.parts if "-" in p and len(p.split("-")[0]) == 4), "?")
        for line in f.open(encoding="utf-8", errors="replace"):
            try:
                m = (json.loads(line).get("message") or {})
            except json.JSONDecodeError:
                continue
            tot, rep = repeated(m.get("reasoning_content") or "")
            per[game][0] += tot
            per[game][1] += rep
            n += 1
            if tot > 5000 and rep / tot > 0.3:
                bad += 1
    tot = sum(v[0] for v in per.values())
    rep = sum(v[1] for v in per.values())
    pct = 100 * rep / max(tot, 1)
    games = "  ".join(f"{g} {100 * v[1] / max(v[0], 1):.1f}" for g, v in sorted(per.items()))
    print(f"{campaign}: {len(files)} tries, {n} replies, repeated {pct:.1f}% of reasoning, {bad} looping replies | {games}")
    if not files:
        print("NO DATA: no replies.jsonl found")
        return 0
    print(f"{'LOOPING' if pct > LIMIT else 'ok'}: {pct:.1f}% (limit {LIMIT}%; base 0.0-0.1%)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

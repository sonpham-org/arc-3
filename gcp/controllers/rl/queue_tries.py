"""Queue try jobs for a campaign (plan §0b step 2: 8 tries per moment up front).

Reads moment documents (seed_moments.py output, one JSONL per source run), picks the n with the most expected
learning signal (rl_tree.select_moments: soft p(1-p) on the level's prior clear rate, at most 15% of the pick from
any one game, the test five and as66 never), and writes one job per moment to the campaign queue the try VMs poll:
  gs://cellens-ai-artifacts/arc3-rl/tries/<campaign>/jobs/<moment_id>.json

  python queue_tries.py --campaign rl-1002a --moments D:/codex-work/rl-20261001/moments/*.jsonl \
      --frontier D:/codex-work/rl-20261001/frontier.json --n-moments 60 --tries 8 [--dry-run]
"""
from __future__ import annotations

import argparse
import glob
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rl_tree as rt  # noqa: E402
import seed_moments as sm  # noqa: E402

ROOT = "gs://cellens-ai-artifacts/arc3-rl/tries"


def load_moments(patterns: list[str]) -> list[dict]:
    out, seen = [], set()
    for pat in patterns:
        for f in sorted(glob.glob(pat)):
            for line in Path(f).read_text(encoding="utf-8").splitlines():
                if line.strip():
                    m = json.loads(line)
                    if m["id"] not in seen:
                        seen.add(m["id"])
                        out.append(m)
    return out


def job_for(m: dict, tries: int, human: list[int]) -> dict:
    root = m["source_uri"].rstrip("/")
    return {"moment_id": m["id"], "game_id": m["game_id"], "fork_step": int(m["turn"]), "level": int(m["level"]),
            "n": int(tries), "transcript_uri": f"{root}/transcripts/{m['game_id']}_p0.txt",
            "policy_id": m.get("policy") or "base", "harness_id": m.get("harness") or "",
            "source_episode_id": None, "human": list(human), "moment": m}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--moments", nargs="+", required=True)
    ap.add_argument("--frontier", required=True)
    ap.add_argument("--n-moments", type=int, default=60)
    ap.add_argument("--tries", type=int, default=8)
    ap.add_argument("--max-game-share", type=float, default=0.15)
    ap.add_argument("--harness", required=True,
                    help="only fork points from runs of this harness (the stack being trained for; 2-Oct: Daniel's "
                         "notebook); the try runner must be able to replay that harness")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    moments = load_moments(a.moments)
    if a.harness:       # forks replay through our harness: other harnesses' transcripts cannot be replayed here
        skipped = sum(1 for m in moments if m.get("harness") != a.harness)
        moments = [m for m in moments if m.get("harness") == a.harness]
        if skipped:
            print(f"skipped {skipped} fork points from other harnesses")
    priors = rt.priors_from_frontier(json.loads(Path(a.frontier).read_text()))
    pick = rt.select_moments(moments, a.n_moments, priors=priors, max_game_share=a.max_game_share)
    obs = sm._observer()
    by_game: dict[str, int] = {}
    jobs = []
    for m in pick:
        if rt.is_fenced(m["game_id"]):
            raise RuntimeError(f"fenced game selected: {m['game_id']}")
        human = list(obs.BASE_ACTIONS.get(m["game_id"]) or [])
        jobs.append(job_for(m, a.tries, human))
        by_game[m["game"]] = by_game.get(m["game"], 0) + 1
    print(f"{len(moments)} moments -> {len(jobs)} jobs x {a.tries} tries; per game {dict(sorted(by_game.items()))}")
    for j in jobs[:5]:
        print(f"  {j['moment_id']}: level {j['level']} turn {j['fork_step']} priority {j['moment'].get('priority'):.3f}")
    if a.dry_run:
        return 0
    stage = Path(sm.__file__).resolve().parent / "_build" / "jobs" / a.campaign
    stage.mkdir(parents=True, exist_ok=True)
    for j in jobs:
        (stage / f"{j['moment_id']}.json").write_text(json.dumps(j), encoding="utf-8")
    dst = f"{ROOT}/{a.campaign}/jobs/"
    p = subprocess.run(sm._gcloud("storage", "cp", str(stage / "*.json"), dst), capture_output=True, text=True)
    if p.returncode:
        print(p.stderr[-2000:])
        return 1
    print(f"queued {len(jobs)} jobs -> {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

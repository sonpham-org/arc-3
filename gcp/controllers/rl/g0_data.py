"""G0 data pass for one run (plan: docs/plans/2026-10-01-rl-on-burst-games.md §9, G0). Runs on a GCP CPU VM
(the local link is too slow for request logs: 20-50 MB per game).

For every non-fenced game of the run:
1. moments: seed_moments on the game's frontier levels (frontier.json), with the reference's remaining tokens;
2. round-0 records: build_records on the cleared levels worth training (efficient wins + every frontier win);
3. exactness: with the model's processor, render each record's prompt and compare the token count with the
   count the server logged for that exact request (plan §11: re-tokenization drift), and check that every
   assistant message maps to exactly one generated span.

Writes <out>/moments.jsonl, <out>/records/<game>.jsonl.gz, <out>/summary.json; optionally Firestore rl_moments.

Usage (on the VM):
  python g0_data.py --run daniel-base-a-1001 --root gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs \
      --frontier frontier.json --hf /opt/rl/hf --campaign rl-1001a --harness daniel-nb-v1 --out /opt/rl/out/<run>
"""
from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_records as br  # noqa: E402
import rl_tree as rt  # noqa: E402
import seed_moments as sm  # noqa: E402


def fetch(src: str, dst: Path) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return True
    r = subprocess.run(["gcloud", "storage", "cp", src, str(dst)], capture_output=True, text=True)
    return r.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--root", required=True, help="gs:// folder holding <run>/working/")
    ap.add_argument("--subdir", default="working", help="run folder holding artifacts/ (our runs: runs)")
    ap.add_argument("--frontier", required=True)
    ap.add_argument("--hf", default="", help="processor dir (tokenizer + chat template + preprocessor); empty = skip check")
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--harness", required=True)
    ap.add_argument("--policy", default="base")
    ap.add_argument("--min-level-score", type=float, default=0.25)
    ap.add_argument("--per-level", type=int, default=6)
    ap.add_argument("--out", required=True)
    ap.add_argument("--write-firestore", action="store_true")
    ap.add_argument("--max-check", type=int, default=6, help="records per game to token-check (the check is slow)")
    args = ap.parse_args()

    out = Path(args.out)
    (out / "records").mkdir(parents=True, exist_ok=True)
    cache = out / "cache"
    obs = sm._observer()
    frontier = json.loads(Path(args.frontier).read_text())["games"]
    processor = None
    if args.hf:
        import render  # noqa: E402  (needs transformers)
        from transformers import AutoProcessor
        processor = AutoProcessor.from_pretrained(args.hf)
    working = f"{args.root.rstrip('/')}/{args.run}/{args.subdir}"
    summary = {"run": args.run, "campaign": args.campaign, "games": {}, "started": time.time()}
    moments_all = []
    for game_id, human in obs.BASE_ACTIONS.items():
        g = rt.game4(game_id)
        if rt.is_fenced(game_id):
            continue
        ev = cache / f"{game_id}_p0_events.jsonl"
        rq = cache / f"{game_id}_p0_requests.jsonl"
        if not fetch(f"{working}/artifacts/{game_id}_p0_events.jsonl", ev):
            summary["games"][g] = {"error": "no events log"}
            continue
        has_rq = fetch(f"{working}/{game_id}_p0_requests.jsonl", rq)
        events = list(sm.iter_jsonl(ev))
        spans = sm.level_spans(events)
        rows = list(sm.iter_jsonl(rq)) if has_rq else []
        tokens = sm.turn_tokens(rows)
        estimated = bool(tokens) and not any(t["tokens"] for t in tokens.values())
        if estimated:          # our harness logs no usage: size the turns from their transcripts (seed_moments)
            est = sm.turn_tokens_from_events(events)
            for st, t in tokens.items():
                t["tokens"] = est.get(st, 0)
        bad = sm.check_turn_starts(spans, tokens)
        info = {"cleared": sorted(spans["clear"]), "frontier": frontier.get(g, {}).get("frontier", []),
                "turns": len(spans["turn_start"]), "requests": sum(r.get("event") == "request" for r in rows),
                "turn_start_mismatch": bad[:10]}
        if bad:
            summary["games"][g] = info
            continue
        ms = sm.moments_for_game(run_id=args.run, game_id=game_id, spans=spans, tokens=tokens,
                                 levels=info["frontier"], human=list(human), harness=args.harness,
                                 policy=args.policy, campaign=args.campaign, per_level=args.per_level,
                                 source_uri=working)
        for m in ms:
            m["ref_tokens_estimated"] = estimated
        moments_all += ms
        info["moments"] = len(ms)
        levels = br.kept_levels(spans, list(human), mode="cleared", min_level_score=args.min_level_score,
                                frontier=info["frontier"])
        recs = br.records_for_game(rows, spans, levels, {"run": args.run, "game": game_id, "levels": sorted(levels),
                                                         "harness": args.harness, "policy": args.policy},
                                   human=list(human))
        info.update(kept_levels=sorted(levels), records=len(recs),
                    trained_replies=sum(r["meta"]["n_trained"] for r in recs))
        with gzip.open(out / "records" / f"{game_id}.jsonl.gz", "wt", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        if processor is not None and recs:
            checks = []
            for r in recs[:args.max_check]:
                try:
                    prompt_rec = (dict(r, messages=r["messages"][:-1], train=r["train"][:-1])
                                  if r["meta"].get("reply_appended") else r)
                    p = render.render(processor, prompt_rec, add_generation_prompt=True)
                    t = render.render(processor, r, add_generation_prompt=False)
                    checks.append({"rendered": len(p["input_ids"]), "logged": r["meta"].get("logged_prompt_tokens"),
                                   "asst_msgs": t["n_assistant_messages"], "asst_spans": t["n_assistant_spans"],
                                   "loss_tokens": t["n_loss_tokens"], "seq_tokens": len(t["input_ids"])})
                except Exception as e:      # recorded, not fatal: the summary is the deliverable
                    checks.append({"error": f"{type(e).__name__}: {e}"[:300]})
            ok = [c for c in checks if "error" not in c]
            info["token_check"] = {
                "checked": len(checks), "errors": [c["error"] for c in checks if "error" in c][:3],
                "exact": sum(c["rendered"] == c["logged"] for c in ok),
                "diffs": [c["rendered"] - (c["logged"] or 0) for c in ok],
                "span_match": sum(c["asst_msgs"] == c["asst_spans"] for c in ok),
                "loss_tokens": sum(c["loss_tokens"] for c in ok), "seq_tokens": [c["seq_tokens"] for c in ok]}
        summary["games"][g] = info
        print(g, json.dumps(info), flush=True)
    with (out / "moments.jsonl").open("w", encoding="utf-8") as fh:
        for m in moments_all:
            fh.write(json.dumps(m) + "\n")
    if args.write_firestore:
        store = rt.FirestoreStore()
        for m in moments_all:
            store.put("rl_moments", m)
    summary["moments"] = len(moments_all)
    summary["finished"] = time.time()
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    print("DONE", args.run, "moments", len(moments_all), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

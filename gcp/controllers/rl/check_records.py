"""Exactness check over every training record (G0): rendered prompt tokens vs the server's logged count, and one
generated span per assistant message. Prints a per-game table and writes JSON.

Run: python check_records.py --records '/opt/rl/out/*/records/*.jsonl.gz' --hf /opt/rl/hf --out check.json
"""
import argparse
import collections
import glob
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True)
    ap.add_argument("--hf", required=True)
    ap.add_argument("--profile", default="sglang-0.5.19")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    from transformers import AutoProcessor
    proc = AutoProcessor.from_pretrained(args.hf)
    per = collections.defaultdict(lambda: collections.Counter())
    diffs = collections.Counter()
    for path in sorted(glob.glob(args.records)):
        game = Path(path).name.split("-")[0]
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                pr = dict(r, messages=r["messages"][:-1], train=r["train"][:-1]) if r["meta"].get("reply_appended") else r
                p = render.render(proc, pr, add_generation_prompt=True, profile=args.profile)
                t = render.render(proc, r, profile=args.profile)
                logged = r["meta"].get("logged_prompt_tokens")
                d = len(p["input_ids"]) - logged if logged else None
                diffs[d] += 1
                c = per[game]
                c["records"] += 1
                c["exact"] += int(d == 0)
                c["span_ok"] += int(t["n_assistant_spans"] == t["n_assistant_messages"])
                c["loss_tokens"] += t["n_loss_tokens"]
                c["seq_tokens"] += len(t["input_ids"])
    out = {"profile": args.profile, "diff_histogram": {str(k): v for k, v in diffs.items()},
           "games": {g: dict(c) for g, c in per.items()},
           "total": dict(sum(per.values(), collections.Counter()))}
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(json.dumps(out["total"]), "diffs:", out["diff_histogram"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

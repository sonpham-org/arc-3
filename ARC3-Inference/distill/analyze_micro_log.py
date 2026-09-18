#!/usr/bin/env python3
# Author: Claude Opus 5 (Bubba)
# Date: 18-September-2026
# PURPOSE: Read a `train_report.json` written by `distill/train_lora.py` and produce the two
#   training-side readouts the raw step curve cannot give. (1) PER-RECORD ACROSS EPOCHS: the
#   trainer's record order is fixed for every epoch, so each record is re-visited once per
#   epoch and its losses form a paired series -- the same record at N points in training,
#   free of the accumulation-window confound that made round 1's step curve unreadable (round
#   1's within-window spread, 0.4866-0.6599, exceeded every step-to-step difference it was
#   asked to show a trend in). (2) EPOCH MEANS over the identical record set, which is
#   comparable across epochs in a way a per-step loss is not.
# SRP/DRY check: Pass -- this module only reads and summarises a report the trainer already
#   wrote. It computes nothing the trainer should have computed and re-runs no model.
"""Summarise a LoRA train_report.json: per-record-across-epochs and per-epoch means."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("report", help="Path to train_report.json")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of a table.")
    args = p.parse_args(argv)

    R = json.load(open(args.report, encoding="utf-8"))
    ml = R.get("micro_log")
    if not ml:
        print("report has no micro_log (trainer predates per-micro-step logging)", file=sys.stderr)
        return 1

    epochs = sorted({m["epoch"] for m in ml})
    by_rec: dict[str, dict[int, float]] = defaultdict(dict)
    for m in ml:
        by_rec[m["id"]][m["epoch"]] = m["loss"]

    # Only records seen in EVERY epoch are comparable. A record missing from one epoch --
    # because an OOM skipped it, or simply because the run is still in flight -- would
    # otherwise contribute to some epoch means and not others, moving the mean by changing
    # the record set rather than by learning.
    complete = {k: v for k, v in by_rec.items() if len(v) == len(epochs)}
    partial = sorted(set(by_rec) - set(complete))

    out = {"epochs": epochs, "records_complete": len(complete),
           "records_incomplete": partial, "in_flight": bool(partial) and len(epochs) > 1}

    ep_mean = {e: sum(v[e] for v in complete.values()) / len(complete) for e in epochs} if complete else {}
    out["epoch_mean_loss_same_records"] = {str(e): round(v, 6) for e, v in ep_mean.items()}

    # Token-weighted epoch mean: supervised-token counts are fixed per record, so this is the
    # same set re-weighted, not a different sample.
    sup = {m["id"]: m["supervised"] for m in ml}
    if complete:
        tot = sum(sup[k] for k in complete)
        out["epoch_token_weighted_loss"] = {
            str(e): round(sum(complete[k][e] * sup[k] for k in complete) / tot, 6) for e in epochs}

    if len(epochs) > 1:
        first, last = epochs[0], epochs[-1]
        d = [complete[k][last] - complete[k][first] for k in complete]
        if d:
            mean_d = sum(d) / len(d)
            var = sum((x - mean_d) ** 2 for x in d) / (len(d) - 1) if len(d) > 1 else 0.0
            sd = var ** 0.5
            out["paired_first_to_last_epoch"] = {
                "n": len(d), "improved": sum(1 for x in d if x < 0),
                "worsened": sum(1 for x in d if x > 0),
                "mean_delta": round(mean_d, 6), "sd_delta": round(sd, 6),
                "t_stat": round(mean_d / (sd / len(d) ** 0.5), 3) if sd > 0 and len(d) > 1 else None,
                "min_delta": round(min(d), 6), "max_delta": round(max(d), 6)}

    if args.json:
        print(json.dumps(out, indent=2))
        return 0

    print(f"epochs {epochs} | {len(complete)} records seen in every epoch"
          + (f" | {len(partial)} record(s) not present in every epoch (OOM-skipped, or the "
             f"run is still in flight) and excluded from the comparison" if partial else ""))
    print("\nepoch mean loss over the identical record set:")
    for e in epochs:
        print(f"  epoch {e}: record-mean {ep_mean[e]:.6f}   "
              f"token-weighted {out['epoch_token_weighted_loss'][str(e)]:.6f}")
    if "paired_first_to_last_epoch" in out:
        q = out["paired_first_to_last_epoch"]
        print(f"\npaired epoch {epochs[0]} -> {epochs[-1]}: {q['improved']}/{q['n']} improved, "
              f"mean {q['mean_delta']:+.6f} (sd {q['sd_delta']:.6f}, t {q['t_stat']})")
    print("\nper-record, by epoch:")
    hdr = "  " + "record".ljust(52) + "".join(f"  e{e}".rjust(10) for e in epochs) + "     delta"
    print(hdr)
    for k in sorted(complete, key=lambda k: complete[k][epochs[-1]] - complete[k][epochs[0]]):
        short = k.split("/", 1)[-1]
        row = "  " + short[-52:].ljust(52)
        row += "".join(f"{complete[k][e]:10.4f}" for e in epochs)
        row += f"{complete[k][epochs[-1]] - complete[k][epochs[0]]:+10.4f}"
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

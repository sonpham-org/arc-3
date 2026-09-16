#!/usr/bin/env python3
# Author: Claude Opus 5 (Bubba)
# Date: 16-September-2026
# PURPOSE: Measure an SFT corpus emitted by distill/extract_sft.py -- record count, assistant
#   (trainable) turns, per-game/per-level contribution, and the token-length distribution that
#   decides what fits in the trainer's context. Exists because "how many records exceed the
#   context limit" is the question that gates a LoRA run, and it cannot be answered from the
#   extractor's summary line.
# SRP/DRY check: Pass -- extract_sft selects and emits, verify_frames checks image fidelity,
#   this module only measures an already-written JSONL. No extraction logic duplicated here.
"""Token and shape statistics for an extract_sft.py corpus.

Usage:
    python distill/corpus_stats.py --corpus ../scratch/sft_baseline.jsonl \
        --tokenizer /path/to/Qwen3.8-27B/tokenizer.json

TEXT TOKENS ARE COUNTED; IMAGE TOKENS ARE ESTIMATED AND REPORTED SEPARATELY.
Running a text tokenizer over an inline `data:image/png;base64,...` string yields a number
with no relationship to what the vision encoder charges, so base64 payloads are excluded from
the text count. The image estimate uses `--image-tokens-per-frame`, which defaults to 64: a
256x256 frame at a 16px patch with 2x2 spatial merge is (256/16)**2 / 4 = 64 tokens. That is
arithmetic from the frame geometry this corpus actually contains, not a measured server
figure -- treat the combined total as an estimate and the text total as measured.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterator


def _iter_records(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def _text_of(message: dict[str, Any]) -> tuple[str, int]:
    """All trainable text in one message, plus the number of image parts it carries."""
    parts: list[str] = []
    images = 0
    content = message.get("content")
    if isinstance(content, list):
        for part in content:
            if part.get("type") == "text":
                parts.append(str(part.get("text") or ""))
            elif part.get("type") in ("image_url", "image"):
                images += 1
    elif isinstance(content, str):
        parts.append(content)
    reasoning = message.get("reasoning")
    if isinstance(reasoning, str):
        parts.append(reasoning)
    for call in message.get("tool_calls") or []:
        fn = call.get("function") or {}
        parts.append(str(fn.get("name") or ""))
        parts.append(str(fn.get("arguments") or ""))
    return "\n".join(p for p in parts if p), images


def _percentiles(values: list[int]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)

    def pct(q: float) -> float:
        idx = min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))
        return float(ordered[idx])

    return {
        "min": float(ordered[0]),
        "p25": pct(0.25),
        "median": float(statistics.median(ordered)),
        "p75": pct(0.75),
        "p90": pct(0.90),
        "max": float(ordered[-1]),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--corpus", action="append", required=True, help="SFT JSONL from extract_sft.py (repeatable).")
    p.add_argument("--tokenizer", required=True, help="Path to the model's tokenizer.json.")
    p.add_argument("--image-tokens-per-frame", type=int, default=64, help="Estimated vision tokens per frame.")
    p.add_argument("--limit-tokens", type=int, default=65536, help="Trainer context limit to report against.")
    args = p.parse_args(argv)

    try:
        from tokenizers import Tokenizer
    except ImportError:
        print("[error] pip install tokenizers", file=sys.stderr)
        return 2
    tok = Tokenizer.from_file(args.tokenizer)

    text_tokens: list[int] = []
    est_totals: list[int] = []
    per_game: Counter[str] = Counter()
    per_level: Counter[int] = Counter()
    per_run: Counter[str] = Counter()
    records = assistant_turns = images = 0

    for corpus in args.corpus:
        for rec in _iter_records(Path(corpus)):
            records += 1
            assistant_turns += int(rec.get("num_assistant_turns") or 0)
            rec_text = 0
            rec_images = 0
            for msg in rec.get("messages") or []:
                text, n_img = _text_of(msg)
                rec_images += n_img
                if text:
                    rec_text += len(tok.encode(text, add_special_tokens=False).ids)
            images += rec_images
            text_tokens.append(rec_text)
            est_totals.append(rec_text + rec_images * args.image_tokens_per_frame)
            per_game[str(rec.get("game_id"))] += int(rec.get("num_assistant_turns") or 0)
            if rec.get("level") is not None:
                per_level[int(rec["level"])] += 1
            per_run[str(rec.get("run"))] += 1

    over = sum(1 for t in est_totals if t > args.limit_tokens)
    print("=" * 72)
    print(f"records                 : {records}")
    print(f"assistant (trainable)   : {assistant_turns} turns")
    print(f"image parts             : {images}")
    print(f"text tokens (measured)  : {sum(text_tokens):,}")
    print(f"image tokens (estimate) : {images * args.image_tokens_per_frame:,}  "
          f"@ {args.image_tokens_per_frame}/frame")
    print(f"total tokens (estimate) : {sum(est_totals):,}")
    print()
    print("per-record text tokens (measured):")
    for k, v in _percentiles(text_tokens).items():
        print(f"  {k:>6}: {v:,.0f}")
    print("per-record total tokens (text measured + image estimate):")
    for k, v in _percentiles(est_totals).items():
        print(f"  {k:>6}: {v:,.0f}")
    print()
    print(f"records over {args.limit_tokens:,} tokens : {over} / {records}"
          f" ({(over / records * 100.0) if records else 0.0:.1f}%)")
    print()
    print("records per level  : " + ", ".join(f"L{k}:{v}" for k, v in sorted(per_level.items())))
    print("runs               : " + ", ".join(f"{k}:{v}" for k, v in sorted(per_run.items())))
    print("assistant turns per game (desc):")
    for game, n in per_game.most_common():
        print(f"  {game:20} {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

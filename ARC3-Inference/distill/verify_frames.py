#!/usr/bin/env python3
# Author: Claude Opus 5 (Bubba)
# Date: 16-September-2026
# PURPOSE: Fidelity oracle for the SFT extractor's regenerated board images. Runs that set
#   `save_request_logs: true` write `<game>_p<N>_requests.jsonl` next to `artifacts/`,
#   containing the exact multimodal payload the model received (inline
#   `data:image/png;base64,...` parts). This decodes those captured PNGs and compares them
#   -- as PIXELS, not as file bytes -- against what `extract_sft._analysis_events` +
#   `vision_context.frame_to_png_bytes` reconstruct, so the claim "the corpus shows the
#   model what it actually saw" is measured rather than assumed. Also used to pin down the
#   run's true `--upscale` / `--style` when run_config.json carries no multimodal block.
# SRP/DRY check: Pass -- reuses extract_sft's observation chain and vision_context's
#   renderer; adds only decode + compare + report. No rendering or selection logic here.
"""Verify regenerated SFT frames against the images captured in request logs.

Usage:
    python distill/verify_frames.py --run-dir ../runs/20260915_230835_qwen38-27b-baseline-25g
    python distill/verify_frames.py --run-dir <run> --upscale 4 --style plain --sweep

`--sweep` tries a grid of upscale values and reports which one reproduces the captured
frames, for runs whose rendering settings are not recorded anywhere.

PNG BYTES ARE NOT COMPARABLE. The serving path and Pillow pick different encoder settings
for the same raster, so identical images have different file bytes and different sizes. All
comparisons here are over decoded RGB pixels.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image  # noqa: E402

from extract_sft import _analysis_events, _load_jsonl, _solved_level_count  # noqa: E402
from inference.agent.vision_context import frame_to_png_bytes  # noqa: E402


def _pixel_hash(png: bytes) -> str:
    with Image.open(io.BytesIO(png)) as im:
        return hashlib.sha1(im.convert("RGB").tobytes()).hexdigest()


def _captured_images(record: dict[str, Any]) -> list[bytes]:
    """Every inline PNG in one request record, in message order."""
    out: list[bytes] = []
    for msg in record.get("messages") or []:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if part.get("type") != "image_url":
                continue
            url = (part.get("image_url") or {}).get("url") or ""
            if url.startswith("data:image/png;base64,"):
                out.append(base64.b64decode(url.split(",", 1)[1]))
    return out


def _observation_chain(events: list[dict[str, Any]]) -> list[list]:
    """The boards the model was shown, in order, as extract_sft reconstructs them."""
    return [rec["grid"] for rec in _analysis_events(events) if isinstance(rec.get("grid"), list)]


def _compare(
    captured: list[bytes],
    boards: list[list],
    upscale: int,
    style: str,
    corpus_indices: set[int] | None = None,
) -> dict[str, Any]:
    """Positional pixel comparison, plus the subset that survives the level filter.

    `corpus_indices` are the chain positions whose turns actually reach the SFT corpus.
    That subset is the number that matters: a frame in a level the rejection sampler
    discards can diverge without affecting a single training record.
    """
    cap = [_pixel_hash(b) for b in captured]
    reg = [_pixel_hash(frame_to_png_bytes(SimpleNamespace(grid=g), upscale=upscale, style=style)) for g in boards]
    prefix = 0
    for a, b in zip(cap, reg):
        if a != b:
            break
        prefix += 1
    positional = sum(1 for i in range(min(len(cap), len(reg))) if cap[i] == reg[i])
    idx = sorted(corpus_indices or set())
    corpus_match = sum(1 for i in idx if i < len(cap) and i < len(reg) and cap[i] == reg[i])
    return {
        "captured": len(cap),
        "regenerated": len(reg),
        "prefix_match": prefix,
        "positional_match": positional,
        "corpus_frames": len(idx),
        "corpus_match": corpus_match,
        "exact": len(cap) == len(reg) == prefix,
        "sizes": sorted({Image.open(io.BytesIO(b)).size for b in captured[:1]}),
    }


def _corpus_indices(events: list[dict[str, Any]], viewer_data: dict[str, Any]) -> set[int]:
    """Chain positions kept by extract_sft's level-granularity rejection sampler."""
    solved = _solved_level_count(viewer_data, events)
    if solved <= 0:
        return set()
    recs = [r for r in _analysis_events(events) if isinstance(r.get("grid"), list)]
    return {i for i, r in enumerate(recs) if (r.get("level") or 0) <= solved}


def _game_pairs(run_dir: Path) -> list[tuple[str, Path, Path]]:
    pairs: list[tuple[str, Path, Path]] = []
    for req in sorted(run_dir.glob("*_requests.jsonl")):
        stem = req.name[: -len("_requests.jsonl")]
        events = run_dir / "artifacts" / f"{stem}_events.jsonl"
        if events.exists():
            pairs.append((stem, req, events))
    return pairs


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--upscale", type=int, default=4)
    p.add_argument("--style", choices=["plain", "outline"], default="plain")
    p.add_argument("--sweep", action="store_true", help="Try several upscale/style combos and report the best.")
    p.add_argument("--max-games", type=int, default=None)
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir)
    pairs = _game_pairs(run_dir)
    if not pairs:
        print(f"[error] no *_requests.jsonl with matching artifacts/ in {run_dir}", file=sys.stderr)
        print("        (the run needs save_request_logs: true)", file=sys.stderr)
        return 2
    if args.max_games is not None:
        pairs = pairs[: args.max_games]

    combos = (
        [(u, s) for u in (1, 2, 3, 4, 6, 8) for s in ("plain", "outline")]
        if args.sweep
        else [(args.upscale, args.style)]
    )

    print(f"run   : {run_dir.name}")
    print(f"games : {len(pairs)} with captured request logs")
    best: tuple[int, tuple[int, str]] | None = None
    for upscale, style in combos:
        total_cap = total_pos = total_corpus = total_corpus_ok = exact_games = 0
        rows: list[str] = []
        for stem, req_path, ev_path in pairs:
            records = _load_jsonl(req_path)
            if not records:
                continue
            events = _load_jsonl(ev_path)
            vd_path = ev_path.with_name(ev_path.name.replace("_events.jsonl", "_viewer_data.json"))
            viewer_data = json.loads(vd_path.read_text(encoding="utf-8")) if vd_path.exists() else {}
            captured = _captured_images(records[-1])
            boards = _observation_chain(events)
            r = _compare(captured, boards, upscale, style, _corpus_indices(events, viewer_data))
            total_cap += r["captured"]
            total_pos += r["positional_match"]
            total_corpus += r["corpus_frames"]
            total_corpus_ok += r["corpus_match"]
            exact_games += 1 if r["exact"] else 0
            rows.append(
                f"  {stem:28} captured={r['captured']:3} chain={r['regenerated']:3} "
                f"match={r['positional_match']:3} corpus={r['corpus_match']:3}/{r['corpus_frames']:<3} "
                f"{'EXACT' if r['exact'] else 'partial'} {r['sizes']}"
            )
        if not args.sweep:
            print("\n".join(rows))
        pct = (total_pos / total_cap * 100.0) if total_cap else 0.0
        cpct = (total_corpus_ok / total_corpus * 100.0) if total_corpus else 0.0
        print(
            f"upscale={upscale} style={style:7} -> all frames {total_pos}/{total_cap} ({pct:.1f}%) "
            f"| corpus frames {total_corpus_ok}/{total_corpus} ({cpct:.1f}%) | exact games {exact_games}/{len(pairs)}"
        )
        if best is None or total_pos > best[0]:
            best = (total_pos, (upscale, style))
    if args.sweep and best is not None:
        print(f"\nbest: --upscale {best[1][0]} --style {best[1][1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

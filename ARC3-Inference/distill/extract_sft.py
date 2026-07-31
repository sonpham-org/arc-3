#!/usr/bin/env python3
"""Phase-1 distillation data pipeline: extract + filter SFT examples from run logs.

This is the *rejection-sampling* (STaR / RFT) data builder for distilling the
incumbent Qwen3.6-27B into itself on its own SOLVED ARC-3 trajectories.

Design (why it looks this thin):
  The harness already reconstructs faithful multi-turn `messages` from the saved
  analysis transcripts via `inference.tools.traces._messages_from_sections`
  (system / user+grid / assistant with reasoning+tool_calls / tool with
  tool_call_id). Re-parsing transcripts by hand would risk train/serve skew, so
  we DRIVE that canonical reconstructor and add only three things on top:

    1. FILTER  -- rejection sampling at the *level* granularity. A game that
       solves level 1 then burns 164 actions failing level 2 (see ar25 in
       ffa7g) must contribute level 1 and NOT level 2. `levels_completed` from
       the viewer_data payload is the authoritative solved-level count; we keep
       analysis turns whose `level <= levels_completed`.
    2. IMAGE   -- the model is multimodal (one current-grid PNG per user turn).
       We regenerate the pixel-identical image from the `board` grid with the
       harness's own renderer (`vision_context.frame_to_png_bytes`).
    3. EMIT    -- one JSONL record per training unit, with metadata (game, level,
       action count for later advantage-weighting) alongside the `messages`.

FIDELITY CAVEAT: these runs did not snapshot the multimodal env
(`save_request_logs: false`), so exact image bytes are not stored. We default to
`--upscale 4 --style plain` (the committed a108.qwen36 config values). For the
real training corpus, do one capture pass with the multimodal env pinned so the
regenerated images are byte-identical to what the model actually saw.

Usage:
    python distill/extract_sft.py \
        --run-dir ../logs/20260718_184500_v12-ffa7g \
        --out ../scratch/sft_ffa7g.jsonl \
        --images-dir ../scratch/sft_ffa7g_images

    # quick validation on a few games:
    python distill/extract_sft.py --run-dir ../logs/... --out /tmp/s.jsonl --max-games 3 --stats-only
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Iterator

# Make the ARC3-Inference package importable regardless of cwd.
_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

# frame_filters.py has no home in the ARC3-Inference package -- it's canonically a
# web-servable static asset (the Games tab's Pyodide worker fetches it as text and
# execs it), so this is the only importable copy. See docs/static/games/src/_shared/.
_FILTERS_DIR = _PKG_ROOT.parent / "docs" / "static" / "games" / "src" / "_shared"
if str(_FILTERS_DIR) not in sys.path:
    sys.path.insert(0, str(_FILTERS_DIR))

from inference.tools.traces import _messages_from_sections, _normalize_int  # noqa: E402
from inference.agent.vision_context import frame_to_png_bytes  # noqa: E402
import frame_filters  # noqa: E402


# --------------------------------------------------------------------------- #
# Loading run artifacts
# --------------------------------------------------------------------------- #
def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def _analysis_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Shape raw analysis events for `_messages_from_sections`, tagging level."""
    out: list[dict[str, Any]] = []
    for e in events:
        if str(e.get("type") or "").strip() != "analysis":
            continue
        transcript = str(e.get("transcript") or "").strip()
        if not transcript:
            continue
        rec: dict[str, Any] = {
            "analysis_step": _normalize_int(e.get("analysis_step")),
            "action_num": _normalize_int(e.get("action_num")),
            "transcript": transcript,
            "level": _normalize_int(e.get("level")),
        }
        board = e.get("board")
        if isinstance(board, list):
            rec["grid"] = board
        out.append(rec)
    return out


def _solved_level_count(viewer_data: dict[str, Any], events: list[dict[str, Any]]) -> int:
    """Authoritative count of solved levels (levels 1..N are solved).

    `score` increments by exactly one per solved level, so the max score across
    action events equals the number of levels cleared. This is robust where the
    per-flag `level` field is NOT: the action that completes level L already
    carries the advanced `level = L+1` (the board steps forward on the same
    action), so counting flags by their level value over-counts by one. We take
    the larger of `levels_completed` (from the summary) and the max score.
    """
    n = _normalize_int(viewer_data.get("levels_completed")) or 0
    max_score = 0
    for e in events:
        if str(e.get("type") or "").strip() != "action":
            continue
        max_score = max(max_score, _normalize_int(e.get("score")) or 0)
    return max(n, max_score)


# --------------------------------------------------------------------------- #
# Image regeneration (pixel-identical to what the model was shown)
# --------------------------------------------------------------------------- #
class _ImageStore:
    def __init__(
        self,
        images_dir: Path | None,
        upscale: int,
        style: str,
        inline: bool,
        filter_id: str = "none",
        filter_params: dict[str, Any] | None = None,
        filter_seed: int = 0,
    ):
        self.images_dir = images_dir
        self.upscale = upscale
        self.style = style
        self.inline = inline
        self.filter_id = filter_id
        self.filter_params = filter_params or {}
        self.filter_seed = filter_seed
        self.count = 0
        self._cache: dict[str, str] = {}
        if images_dir is not None and not inline:
            images_dir.mkdir(parents=True, exist_ok=True)

    def render(self, grid: list) -> str:
        key = hashlib.sha1(
            json.dumps(grid, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if key in self._cache:
            return self._cache[key]
        if self.filter_id != "none":
            # Derived from the grid's own content hash (not a single corpus-wide
            # seed) so distinct grids get distinct noise, while this cache still
            # dedups repeats of the identical raw grid to one PNG, same as before.
            seed = self.filter_seed ^ int(key[:8], 16)
            grid = frame_filters.apply_filter(grid, self.filter_id, self.filter_params, seed=seed)
        png = frame_to_png_bytes(SimpleNamespace(grid=grid), upscale=self.upscale, style=self.style)
        self.count += 1
        if self.inline:
            ref = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        else:
            assert self.images_dir is not None
            out = self.images_dir / f"{key}.png"
            if not out.exists():
                out.write_bytes(png)
            ref = str(out)
        self._cache[key] = ref
        return ref


def _attach_images(messages: list[dict[str, Any]], store: _ImageStore) -> int:
    """Convert each user message's `grid` into an image content part. In place."""
    n = 0
    for msg in messages:
        if msg.get("role") != "user" or "grid" not in msg:
            continue
        grid = msg.pop("grid")
        ref = store.render(grid)
        text = msg.get("content")
        image_part = (
            {"type": "image_url", "image_url": {"url": ref}}
            if store.inline
            else {"type": "image", "image": ref}
        )
        msg["content"] = [{"type": "text", "text": text if isinstance(text, str) else ""}, image_part]
        n += 1
    return n


# --------------------------------------------------------------------------- #
# Example building
# --------------------------------------------------------------------------- #
def _count_assistant_turns(messages: list[dict[str, Any]]) -> int:
    return sum(1 for m in messages if m.get("role") == "assistant")


def build_records(
    run_dir: Path,
    *,
    store: _ImageStore,
    granularity: str,
    only_solved: bool,
    max_games: int | None,
) -> Iterator[dict[str, Any]]:
    artifacts = run_dir / "artifacts"
    vd_paths = sorted(artifacts.glob("*_viewer_data.json"))
    games_done = 0
    for vd_path in vd_paths:
        if max_games is not None and games_done >= max_games:
            break
        events_path = vd_path.with_name(vd_path.name.replace("_viewer_data.json", "_events.jsonl"))
        if not events_path.exists():
            continue
        viewer_data = json.loads(vd_path.read_text(encoding="utf-8"))
        events = _load_jsonl(events_path)
        game_id = str(viewer_data.get("game_id") or vd_path.stem)
        solved_n = _solved_level_count(viewer_data, events)
        if only_solved and solved_n <= 0:
            games_done += 1
            continue

        an_events = _analysis_events(events)
        actions_per_level = viewer_data.get("actions_per_level") or []

        if granularity == "game":
            groups: list[tuple[int | None, list[dict[str, Any]]]] = [(None, an_events)]
        else:  # per-level
            by_level: dict[int, list[dict[str, Any]]] = {}
            for ev in an_events:
                lvl = ev.get("level")
                if lvl is None:
                    continue
                by_level.setdefault(lvl, []).append(ev)
            groups = sorted(by_level.items(), key=lambda kv: kv[0])

        for level, group_events in groups:
            if not group_events:
                continue
            if only_solved and level is not None and level > solved_n:
                continue  # first-unsolved level onward = flailing; drop it
            messages, _links = _messages_from_sections(group_events)
            if not messages or _count_assistant_turns(messages) == 0:
                continue
            n_images = _attach_images(messages, store)
            lvl_actions = (
                actions_per_level[level - 1]
                if isinstance(level, int) and 1 <= level <= len(actions_per_level)
                else None
            )
            yield {
                "id": f"{run_dir.name}/{game_id}" + (f"/L{level}" if level is not None else ""),
                "game_id": game_id,
                "run": run_dir.name,
                "level": level,
                "solved": True if (level is not None and level <= solved_n) else (solved_n > 0),
                "level_actions": lvl_actions,
                "num_messages": len(messages),
                "num_assistant_turns": _count_assistant_turns(messages),
                "num_images": n_images,
                "messages": messages,
            }
        games_done += 1


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-dir", action="append", required=True, help="Run dir with artifacts/ (repeatable).")
    p.add_argument("--out", required=True, help="Output SFT JSONL path.")
    p.add_argument("--images-dir", default=None, help="Dir for regenerated PNGs (default: <out>_images).")
    p.add_argument("--granularity", choices=["level", "game"], default="level")
    p.add_argument("--keep-unsolved", action="store_true", help="Disable the rejection-sampling filter.")
    p.add_argument("--upscale", type=int, default=4, help="Image upscale (match the run's multimodal.upscale).")
    p.add_argument("--style", choices=["plain", "outline"], default="plain")
    p.add_argument("--inline-images", action="store_true", help="Embed base64 data URLs instead of file paths.")
    p.add_argument("--max-games", type=int, default=None, help="Cap games per run (quick validation).")
    p.add_argument("--stats-only", action="store_true", help="Compute + print stats, do not write JSONL.")
    p.add_argument(
        "--filter",
        choices=sorted(frame_filters.FILTERS),
        default="none",
        help="Apply a frame_filters.py transform to every regenerated image (recolor/noise/"
        "merge/occlude), for training on harder-to-memorize synthetic variants.",
    )
    p.add_argument(
        "--filter-params",
        default=None,
        help='JSON object of filter params, e.g. \'{"rate": 0.1}\'. Unset params use the filter\'s default.',
    )
    p.add_argument("--filter-seed", type=int, default=0, help="Base seed mixed with each grid's content hash.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    out_path = Path(args.out)
    images_dir = Path(args.images_dir) if args.images_dir else out_path.with_name(out_path.stem + "_images")
    filter_params = json.loads(args.filter_params) if args.filter_params else {}
    store = _ImageStore(
        images_dir,
        args.upscale,
        args.style,
        args.inline_images,
        filter_id=args.filter,
        filter_params=filter_params,
        filter_seed=args.filter_seed,
    )

    totals = {"records": 0, "assistant_turns": 0, "images": 0, "solved_games": 0, "runs": 0}
    per_level_hist: dict[int, int] = {}
    fh = None if args.stats_only else out_path.open("w", encoding="utf-8")
    try:
        for run in args.run_dir:
            run_dir = Path(run)
            if not (run_dir / "artifacts").exists():
                print(f"[skip] no artifacts/ in {run_dir}", file=sys.stderr)
                continue
            totals["runs"] += 1
            seen_games: set[str] = set()
            for rec in build_records(
                run_dir,
                store=store,
                granularity=args.granularity,
                only_solved=not args.keep_unsolved,
                max_games=args.max_games,
            ):
                totals["records"] += 1
                totals["assistant_turns"] += rec["num_assistant_turns"]
                totals["images"] += rec["num_images"]
                seen_games.add(rec["game_id"])
                if rec.get("level") is not None:
                    per_level_hist[rec["level"]] = per_level_hist.get(rec["level"], 0) + 1
                if fh is not None:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            totals["solved_games"] += len(seen_games)
    finally:
        if fh is not None:
            fh.close()

    print("=" * 60)
    print(f"runs processed        : {totals['runs']}")
    print(f"games with solved data : {totals['solved_games']}")
    print(f"training records       : {totals['records']}  (granularity={args.granularity})")
    print(f"assistant (trainable)  : {totals['assistant_turns']} turns")
    print(f"unique images rendered : {store.count}  (user turns w/ image: {totals['images']})")
    if per_level_hist:
        hist = ", ".join(f"L{k}:{v}" for k, v in sorted(per_level_hist.items()))
        print(f"records per level      : {hist}")
    if not args.stats_only:
        print(f"wrote                  : {out_path}")
        if not args.inline_images:
            print(f"images                 : {images_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

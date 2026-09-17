#!/usr/bin/env python3
# Author: Claude Opus 5 (Bubba); --exclude-games help note by Claude Opus 5, 17-September-2026
# Date: 16-September-2026
# PURPOSE: Phase-1 distillation data pipeline -- extract and filter SFT training records
#   from ARC-3 rollout artifacts (`runs/<run>/artifacts/*_events.jsonl` +
#   `*_viewer_data.json`). Drives the harness's own transcript reconstructor
#   (`inference.tools.traces._messages_from_sections`) to avoid train/serve skew, applies
#   rejection sampling at LEVEL granularity, and re-renders the board observation each
#   decision step was actually taken from via `inference.agent.vision_context`.
#   Downstream consumers: `distill/verify_frames.py` (fidelity oracle against captured
#   request logs) and `distill/corpus_stats.py` (token/length distribution).
# SRP/DRY check: Pass -- image rendering stays in vision_context, message reconstruction
#   stays in traces.py, frame filters stay in frame_filters.py. This module only selects,
#   aligns, and emits.
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
    2. IMAGE   -- the model is multimodal (one board PNG per decision turn). We
       regenerate that image from the *preceding* board snapshot with the harness's
       own renderer (`vision_context.frame_to_png_bytes`). The board stored ON an
       analysis event is the board that event's actions produced, i.e. the OUTCOME,
       not the observation the step was decided from. The observation sequence is
       therefore `[initial.board, analysis[0].board, analysis[1].board, ...]`, and
       decision step k sees element k. See `distill/verify_frames.py` for the check.
    3. EMIT    -- one JSONL record per training unit, with metadata (game, level,
       action count for later advantage-weighting) alongside the `messages`.

FIDELITY: runs that set `save_request_logs: true` write per-game
`<game>_p<N>_requests.jsonl` alongside the artifacts, with the exact multimodal
payload the model received (inline `data:image/png;base64,...` parts). That makes
regeneration checkable rather than assumed. `distill/verify_frames.py` decodes those
captured PNGs and compares them to what this module renders.

Measured on the 20260915_230835_qwen38-27b-baseline-25g run at the defaults below
(`--upscale 4 --style plain`): the regenerated frames are PIXEL-identical to the
captured ones -- not byte-identical, because the serving path and Pillow choose
different PNG encoder settings for the same raster. Compare decoded pixels, never
file bytes.

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
    """Shape raw analysis events for `_messages_from_sections`, tagging level.

    The `grid` we hand each event is the board it was DECIDED FROM, which is the
    board of the *preceding* analysis event -- or the `initial` event's board for
    the first step. The board stored on an analysis event is the state that event's
    actions produced, so attaching an event's own board would show the model the
    outcome of a move as the observation it is about to choose that move from.

    Verified against captured request logs (`distill/verify_frames.py`): on the
    20260915_230835 baseline the step-1 request carries exactly one image and it is
    the `initial` board in all four games checked, and the full predecessor sequence
    reproduces the captured frames pixel-for-pixel (ar25 17/17, r11l 11/11,
    vc33 19/19). Note the chain is built from `initial` + analysis events only;
    `action` events also carry boards but are not what the model was shown.

    This walks the whole ordered event list, not just the analysis subset, so the
    chain stays intact across `action` events and across level boundaries. Callers
    that group by level must call this BEFORE grouping.
    """
    out: list[dict[str, Any]] = []
    prev_board: list | None = None
    for e in events:
        etype = str(e.get("type") or "").strip()
        board = e.get("board")
        if etype == "initial":
            if isinstance(board, list):
                prev_board = board
            continue
        if etype != "analysis":
            continue
        transcript = str(e.get("transcript") or "").strip()
        if not transcript:
            # Still advance the chain: a transcript-less step is dropped from the
            # corpus but its board is what the NEXT step was decided from.
            if isinstance(board, list):
                prev_board = board
            continue
        rec: dict[str, Any] = {
            "analysis_step": _normalize_int(e.get("analysis_step")),
            "action_num": _normalize_int(e.get("action_num")),
            "transcript": transcript,
            "level": _normalize_int(e.get("level")),
        }
        if isinstance(prev_board, list):
            rec["grid"] = prev_board
        if isinstance(board, list):
            prev_board = board
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


def game_code(game_id: str) -> str:
    """Bare 4-char game code from a full game id.

    Artifacts name games `ar25-0c556536`; held-out-set membership is decided by the
    `ar25` prefix alone, so any comparison against a test-set list has to strip the
    content hash first. Comparing full ids to bare codes silently matches nothing.
    """
    return str(game_id).split("-", 1)[0].strip().lower()


def build_records(
    run_dir: Path,
    *,
    store: _ImageStore,
    granularity: str,
    only_solved: bool,
    max_games: int | None,
    exclude_games: frozenset[str] = frozenset(),
    excluded_counter: dict[str, int] | None = None,
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
        # Multi-pass runs emit one viewer_data per (game, pass) and `game_id` carries
        # no pass suffix, so the pass index has to be part of the record identity or
        # every pass of a game collides on `id`.
        pass_index = _normalize_int(viewer_data.get("pass_index"))

        # Held-out test-set fence. Applied at GAME granularity and before any record is
        # built, so excluded games never reach the renderer -- a dropped JSONL row still
        # leaves its regenerated PNG on disk, where a later job can pick it back up.
        if exclude_games and game_code(game_id) in exclude_games:
            if excluded_counter is not None:
                key = game_code(game_id)
                excluded_counter[key] = excluded_counter.get(key, 0) + 1
            games_done += 1
            continue

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
                "id": (
                    f"{run_dir.name}/{game_id}"
                    + (f"/p{pass_index}" if pass_index is not None else "")
                    + (f"/L{level}" if level is not None else "")
                ),
                "game_id": game_id,
                "pass_index": pass_index,
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
    p.add_argument(
        "--exclude-games",
        default=None,
        help="Comma-separated bare game codes (e.g. 'vc33,ar25') to drop entirely -- the "
        "held-out test-set fence. Matched against the code before the content hash, and "
        "applied before image rendering so excluded frames are never written. The test-only "
        "game as66 (datasets/test-only-games/) must always be in this list when the run "
        "played it: vc33,ar25,sb26,re86,su15,tr87,tu93,as66.",
    )
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

    exclude_games = frozenset(
        c.strip().lower() for c in (args.exclude_games or "").split(",") if c.strip()
    )
    excluded_counter: dict[str, int] = {}

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
            seen_games: set[tuple[str, int | None]] = set()
            for rec in build_records(
                run_dir,
                store=store,
                granularity=args.granularity,
                only_solved=not args.keep_unsolved,
                max_games=args.max_games,
                exclude_games=exclude_games,
                excluded_counter=excluded_counter,
            ):
                totals["records"] += 1
                totals["assistant_turns"] += rec["num_assistant_turns"]
                totals["images"] += rec["num_images"]
                seen_games.add((rec["game_id"], rec.get("pass_index")))
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
    print(f"(game,pass) contributing: {totals['solved_games']}")
    print(f"training records       : {totals['records']}  (granularity={args.granularity})")
    print(f"assistant (trainable)  : {totals['assistant_turns']} turns")
    print(f"unique images rendered : {store.count}  (user turns w/ image: {totals['images']})")
    if exclude_games:
        dropped = sum(excluded_counter.values())
        detail = ", ".join(f"{k}:{v}" for k, v in sorted(excluded_counter.items())) or "none"
        print(f"test-set fence         : {sorted(exclude_games)}")
        print(f"  (game,pass) dropped  : {dropped}  [{detail}]")
        missing = sorted(exclude_games - set(excluded_counter))
        if missing:
            print(f"  [warn] fenced codes never seen in these runs: {missing}", file=sys.stderr)
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

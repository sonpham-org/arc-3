"""
Author: Claude Opus 5
Date: 21-September-2026
PURPOSE: Perception probe for sk48 (Skewer Kebabs), one of the seven games the 27B scores a
flat 0.00 on. Tests a specific hypothesis: that sk48's REFERENCE SKEWER STRIP -- the row of
target skewers below the divider line that tells the player which bead colors each skewer needs,
in order -- does not survive into `current_frame.segmentation` in a usable form, and that the
model therefore literally cannot read the win condition no matter how the prompt is worded.

WHY IT MATTERS. The ARC-3 tool agent never sees the board as a picture unless
MULTIMODAL_CONTEXT=current_grid. It writes Python against `current_frame`, which exposes only
.ascii/.segmentation/.step/.level (agent/tool_agent.py:220), and the prompt tells it to use
.segmentation as the PRIMARY view and .ascii "only for a small specific region"
(tool_agent.py:224). So whatever segmentation drops is, in practice, invisible.

METHOD. Grids come from the game's own source via arcengine -- the same
instantiate / set_level(n) / camera.render(get_sprites()) path that
arc-explainer/scripts/arc3/render_public_demo_levels.py is verified against; no PNG inversion,
no re-derived board. Segmentation is the harness's OWN segment_layer() from
inference/utils/segmentation.py with ARC_COLOR_CHARS from inference/utils/grid_utils.py --
deliberately NOT a reimplementation, because the question is what the model actually receives.

Node dicts carry no bbox, only `boundary` corner points, so this script derives bboxes the same
way a model would have to. The strip is located from the full-width gray divider row rather than
a hardcoded row index.

SRP/DRY check: Pass -- segmentation and grid loading are both imported from their existing
sources rather than reimplemented. This file only measures and reports; it renders nothing and
mutates nothing.

Run:  python3.13 scripts/sk48_segmentation_probe.py
      (needs a Python with match-statement support for arcengine, and numpy/PIL absent is fine)
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import sys
from pathlib import Path

ARC_EXPLAINER = Path("/Users/macmini/GitHub/arc-explainer")
ARC3_INFERENCE = Path("/Users/macmini/GitHub/arc-3/ARC3-Inference")
SK48_SRC = ARC_EXPLAINER / "external/ARCEngine/environment_files/sk48/d8078629/sk48.py"

sys.path.insert(0, str(ARC_EXPLAINER / "external/ARCEngine"))
sys.path.insert(0, str(ARC3_INFERENCE))

from inference.utils.grid_utils import ARC_COLOR_CHARS  # noqa: E402
from inference.utils.segmentation import segment_layer  # noqa: E402

# sk48 sprites are classified STRUCTURALLY, not by color, because color alone is ambiguous:
# purple is a handle ring in lvl 6-8 but never a bead, and a bead can be blue whether it sits in
# the play area or the reference strip. The shapes below were read off the raw .ascii (see
# --ascii): a bead is a 4x4 block, a handle is a 6x6 ring, and a 2x2 blob enclosed by a ring is
# that handle's identity marker. Beads may also carry a 2x2 center, which leaves the bead node a
# 12px ring with the center as an enclosed child.
BEAD_SIDE = 4
HANDLE_SIDE = 6
MARKER_SIDE = 2
SHAFT_CHARS = set("wgG")


def shape_of(node, bb):
    """Classify a node by its bounding-box footprint. Returns 'bead' | 'handle' | 'marker' | ''."""
    h, w = bb[2] - bb[0] + 1, bb[3] - bb[1] + 1
    if (h, w) == (BEAD_SIDE, BEAD_SIDE) and node["pixels"] in (12, 16):
        return "bead"
    # A handle occupies a 6x6 footprint, but its fill varies by level: an outline ring in lvl 1-3
    # and 5-8 (18 px), a SOLID block in lvl 4 (~30 px, and colored black -- the same value as the
    # play-area background, only separable here because the strip background is charcoal). Nothing
    # else in sk48 has a 6x6 footprint, so the footprint alone is the reliable signature.
    if (h, w) == (HANDLE_SIDE, HANDLE_SIDE):
        return "handle"
    if (h, w) == (MARKER_SIDE, MARKER_SIDE) and node["pixels"] == 4:
        return "marker"
    return ""


def inside(inner_bb, outer_bb) -> bool:
    return (
        inner_bb[0] >= outer_bb[0] and inner_bb[1] >= outer_bb[1]
        and inner_bb[2] <= outer_bb[2] and inner_bb[3] <= outer_bb[3]
    )


def load_sk48_class():
    from arcengine import ARCBaseGame

    spec = importlib.util.spec_from_file_location("sk48_probe", SK48_SRC)
    mod = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        spec.loader.exec_module(mod)
    return next(
        obj
        for _, obj in vars(mod).items()
        if isinstance(obj, type) and issubclass(obj, ARCBaseGame) and obj is not ARCBaseGame
    )


def render_level(cls, level_index: int) -> list[list[int]]:
    """Opening frame for one level, via the engine's own camera. Matches render_public_demo_levels."""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        game = cls()
        game.set_level(level_index)
        grid = game.camera.render(game.current_level.get_sprites())
    return [[int(v) for v in row] for row in grid]


def bbox(node) -> tuple[int, int, int, int]:
    """(min_row, min_col, max_row, max_col) derived from `boundary` -- the only positional
    information a node carries. A model reading segmentation has to do exactly this."""
    rows = [p[0] for p in node["boundary"]]
    cols = [p[1] for p in node["boundary"]]
    return min(rows), min(cols), max(rows), max(cols)


def find_divider_rows(grid) -> list[int]:
    """Full-width single-color gray rows. sk48 separates the play area from the reference strip
    with one of these; finding it is how the strip gets located without a magic row number."""
    return [
        r
        for r, row in enumerate(grid)
        if len(set(row)) == 1 and ARC_COLOR_CHARS[max(0, min(15, row[0]))] == "g"
    ]


def group_into_skewers(beads, handles):
    """Group strip beads into skewers by column RUN, then attach each run to its adjacent handle.

    Beads on one skewer sit at a regular ~6-column pitch, so a gap wider than that starts a new
    skewer. Attaching by run-then-adjacency rather than by nearest-handle matters: in level 6 the
    second handle sits in the gap between the two runs, and a nearest-handle rule steals the last
    bead of the first run. Within a run, beads are ordered outward from the handle, because a
    skewer can extend either direction and a naive left-to-right read reverses a left-hand one.
    """
    ordered = sorted(beads, key=lambda b: b["bbox"][1])
    runs, cur = [], []
    for bead in ordered:
        if cur and bead["bbox"][1] - cur[-1]["bbox"][3] > BEAD_SIDE + 4:
            runs.append(cur)
            cur = []
        cur.append(bead)
    if cur:
        runs.append(cur)

    out = []
    for run in runs:
        lo, hi = run[0]["bbox"][1], run[-1]["bbox"][3]
        handle, side = None, "left"
        for h in handles:
            if h["bbox"][3] < lo and (handle is None or h["bbox"][3] > handle["bbox"][3]):
                handle, side = h, "right"  # handle left of the run => skewer extends right
        for h in handles:
            if h["bbox"][1] > hi and handle is None:
                handle, side = h, "left"
        if handle is None:
            out.append(("unattached-run", run))
        else:
            seq = run if side == "right" else list(reversed(run))
            out.append((f"handle#{handle['id']}({handle['color']}) extends {side}", seq))
    return out


def probe_level(cls, level_index: int) -> dict:
    grid = render_level(cls, level_index)
    seg = segment_layer(grid, ARC_COLOR_CHARS)
    dividers = find_divider_rows(grid)
    strip_top = max(dividers) if dividers else len(grid)

    by_id = {}
    enriched = []
    for n in seg["nodes"]:
        bb = bbox(n)
        node = {
            **n,
            "bbox": bb,
            "zone": "strip" if bb[0] > strip_top else "interior",
            "shape": shape_of(n, bb),
        }
        enriched.append(node)
        by_id[n["id"]] = node

    def pick(zone, shape):
        return sorted(
            (n for n in enriched if n["zone"] == zone and n["shape"] == shape),
            key=lambda n: n["bbox"][1],
        )

    # A handle's inner 4x4 face has the same footprint as a bead, so it has to be excluded or
    # every skewer grows a phantom bead at the handle end. It cannot be excluded via the
    # containment tree: the 6x6 ring is BROKEN where the shaft attaches (verified in the raw
    # ascii, e.g. lvl 6 rows 215-216 col 10 are shaft dashes, not ring), so the interior is not
    # topologically enclosed and segmentation assigns it no parent. Geometry is the fallback.
    def beads_only(zone):
        rings = pick(zone, "handle")
        return [
            b for b in pick(zone, "bead")
            if not any(inside(b["bbox"], h["bbox"]) for h in rings)
        ]

    return {
        "level": level_index + 1,
        "grid": grid,
        "seg": seg,
        "nodes": enriched,
        "by_id": by_id,
        "dividers": dividers,
        "strip_top": strip_top,
        "strip_beads": beads_only("strip"),
        "strip_handles": pick("strip", "handle"),
        "interior_beads": beads_only("interior"),
        "interior_handles": pick("interior", "handle"),
    }


def describe_children(node, by_id) -> str:
    """Enclosed children, straight from segmentation's own containment tree -- the model is
    handed this nesting, it does not have to infer it."""
    kids = [by_id[c] for c in node["children"] if c in by_id]
    if not kids:
        return ""
    return "  children=" + ", ".join(
        f"{k['color']}/{k['pixels']}px{'/' + k['shape'] if k['shape'] else ''}" for k in kids
    )


def report(result) -> None:
    nodes = result["nodes"]
    by_id = result["by_id"]
    print(f"\n{'=' * 78}\nLEVEL {result['level']}")
    print(f"  total segmentation nodes : {len(nodes)}")
    print(f"  adjacency pairs          : {len(result['seg']['adjacency_list'])}")
    print(f"  full-width gray divider  : rows {result['dividers']} -> strip is rows >{result['strip_top']}")
    tiny = [n for n in nodes if n["pixels"] <= 2]
    shaft = [n for n in tiny if n["color"] in SHAFT_CHARS]
    print(f"  nodes of <=2 px          : {len(tiny)} ({len(shaft)} of them shaft-dash colored)")

    for zone in ("strip", "interior"):
        beads = result[f"{zone}_beads"]
        handles = result[f"{zone}_handles"]
        print(f"\n  --- {zone.upper()} ---")
        print(f"  4x4 bead objects: {len(beads)}   6x6 handle rings: {len(handles)}")
        for h in handles:
            print(f"    handle id={h['id']:<4} {h['color']} px={h['pixels']:<3} bbox={h['bbox']}"
                  f"{describe_children(h, by_id)}")
        for b in beads:
            print(f"    bead   id={b['id']:<4} {b['color']} px={b['pixels']:<3} bbox={b['bbox']}"
                  f"{describe_children(b, by_id)}")
        if zone == "strip":
            print("  COLOR + ORDER recovered per reference skewer:")
            skewers = group_into_skewers(beads, handles)
            for name, seq in skewers:
                print(f"    {name}: {' -> '.join(b['color'] for b in seq)}")
            placed = sum(len(seq) for _, seq in skewers)
            print(f"    (skewers={len(skewers)}, beads accounted for={placed}/{len(beads)})")
        else:
            by_row = {}
            for b in beads:
                by_row.setdefault(b["bbox"][0], []).append(b)
            print("  CONTRAST CONTROL -- interior beads grouped by row:")
            for row in sorted(by_row):
                seq = sorted(by_row[row], key=lambda b: b["bbox"][1])
                print(f"    row {row:<3}: {' -> '.join(b['color'] for b in seq)}")

    ringed = [b for b in result["strip_beads"] if b["pixels"] == 12]
    if ringed:
        print("\n  NOTE: strip beads rendered as a 12px ring around a 2x2 center (a marker inside")
        print("        the bead, NOT occlusion -- the center is an enclosed child node):")
        for b in ringed:
            print(f"    id={b['id']} {b['color']} px={b['pixels']} bbox={b['bbox']}"
                  f"{describe_children(b, by_id)}")

    unclassified = [n for n in nodes if not n["shape"] and n["pixels"] > 2 and n["pixels"] < 100]
    if unclassified:
        print(f"\n  unclassified mid-size nodes ({len(unclassified)}): "
              + ", ".join(f"id{n['id']}/{n['color']}/{n['pixels']}px" for n in unclassified[:12]))


def ascii_of(grid) -> str:
    return "\n".join(
        "".join(ARC_COLOR_CHARS[max(0, min(15, v))] for v in row) for row in grid
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="sk48 reference-strip segmentation probe")
    parser.add_argument("--levels", default="1-8", help="e.g. 1-8 or 1,5,8")
    parser.add_argument("--ascii", action="store_true", help="also dump the raw ascii grid")
    args = parser.parse_args()

    if "-" in args.levels:
        lo, hi = (int(x) for x in args.levels.split("-"))
        targets = list(range(lo, hi + 1))
    else:
        targets = [int(x) for x in args.levels.split(",")]

    cls = load_sk48_class()
    print(f"sk48 class: {cls.__name__}   source: {SK48_SRC}")
    print(f"segmenter : inference.utils.segmentation.segment_layer (the harness's own)")
    print(f"palette   : ARC_COLOR_CHARS = {ARC_COLOR_CHARS!r}")

    for lvl in targets:
        result = probe_level(cls, lvl - 1)
        report(result)
        if args.ascii:
            print(f"\n  raw .ascii for level {lvl}:\n{ascii_of(result['grid'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

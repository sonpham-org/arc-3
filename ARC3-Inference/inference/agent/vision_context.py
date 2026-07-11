"""Optional multimodal context helpers for ARC analyzer prompts."""
from __future__ import annotations

import base64
import io
import os
from typing import Any

from PIL import Image, ImageDraw

from inference.agent.runtime_state import Frame


ARC_COLOR_MAP: dict[int, tuple[int, int, int]] = {
    0: (255, 255, 255),
    1: (204, 204, 204),
    2: (153, 153, 153),
    3: (102, 102, 102),
    4: (51, 51, 51),
    5: (0, 0, 0),
    6: (229, 58, 163),
    7: (255, 123, 204),
    8: (249, 60, 49),
    9: (30, 147, 255),
    10: (136, 216, 241),
    11: (255, 220, 0),
    12: (255, 133, 27),
    13: (146, 18, 49),
    14: (79, 204, 48),
    15: (163, 86, 214),
}


def multimodal_context() -> str:
    return os.environ.get("MULTIMODAL_CONTEXT", "").strip().lower()


def current_grid_image_enabled() -> bool:
    return multimodal_context() == "current_grid"


def current_grid_image_upscale() -> int:
    raw = os.environ.get("MULTIMODAL_UPSCALE", "").strip()
    if not raw:
        return 16
    try:
        return max(1, int(raw))
    except ValueError:
        return 16


def current_grid_image_style() -> str:
    style = os.environ.get("MULTIMODAL_STYLE", "").strip().lower()
    return style if style in {"plain", "outline"} else "plain"


# Gutter tints deliberately sit outside the 16-color game palette (which includes
# pure white and four pure greys), so margin never reads as board. They also differ
# from each other: warm = top/left, cool = bottom/right, giving the model an
# orientation anchor that survives any crop or mental rotation.
_OUTLINE_GUTTER_TOP_LEFT = (240, 233, 216)      # warm parchment
_OUTLINE_GUTTER_BOTTOM_RIGHT = (186, 197, 206)  # cool blue-grey
_OUTLINE_EDGE = (0, 0, 0)
_OUTLINE_HALO = (255, 255, 255)
_OUTLINE_LABEL = (80, 80, 80)
_OUTLINE_MARGIN = 26
_OUTLINE_TICK_EVERY = 8


def _render_plain(grid: list, rows: int, cols: int, scale: int) -> Image.Image:
    image = Image.new("RGB", (cols, rows), ARC_COLOR_MAP[0])
    pixels = image.load()
    for row_idx, row in enumerate(grid):
        for col_idx in range(cols):
            value = row[col_idx] if col_idx < len(row) else 0
            pixels[col_idx, row_idx] = ARC_COLOR_MAP.get(int(value), ARC_COLOR_MAP[0])
    if scale > 1:
        image = image.resize((cols * scale, rows * scale), Image.Resampling.NEAREST)
    return image


def _render_outline(grid: list, rows: int, cols: int, scale: int) -> Image.Image:
    """Cells with borders only along color transitions, plus row/col coordinates.

    Contiguous same-color regions read as single outlined shapes, so the image
    shows the segmentation instead of a flat pixel field, and the margin labels
    tie what the model sees to the row/col coordinates MOUSE actions use.
    """

    def cell(r: int, c: int) -> int:
        row = grid[r]
        return int(row[c]) if c < len(row) else 0

    margin = _OUTLINE_MARGIN
    width = margin + cols * scale + margin
    height = margin + rows * scale + margin
    board = _render_plain(grid, rows, cols, scale)
    # Bottom/right gutter as the ground, top/left gutter as an L on top of it, so the
    # two tints meet at the off corners and every canvas edge is unambiguous.
    image = Image.new("RGB", (width, height), _OUTLINE_GUTTER_BOTTOM_RIGHT)
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, width - 1, margin - 1], fill=_OUTLINE_GUTTER_TOP_LEFT)
    draw.rectangle([0, 0, margin - 1, height - 1], fill=_OUTLINE_GUTTER_TOP_LEFT)
    image.paste(board, (margin, margin))

    def x(c: int) -> int:
        return margin + c * scale

    def y(r: int) -> int:
        return margin + r * scale

    # Edges sit along color transitions only. Halos go down first so a halo never
    # paints over a neighbouring edge's dark line.
    horizontal = [(r, c) for r in range(rows + 1) for c in range(cols)
                  if r == 0 or r == rows or cell(r - 1, c) != cell(r, c)]
    vertical = [(r, c) for c in range(cols + 1) for r in range(rows)
                if c == 0 or c == cols or cell(r, c - 1) != cell(r, c)]
    for width, color in ((4, _OUTLINE_HALO), (2, _OUTLINE_EDGE)):
        for r, c in horizontal:
            draw.line([(x(c), y(r)), (x(c + 1), y(r))], fill=color, width=width)
        for r, c in vertical:
            draw.line([(x(c), y(r)), (x(c), y(r + 1))], fill=color, width=width)

    for c in range(0, cols, _OUTLINE_TICK_EVERY):
        draw.line([(x(c), margin - 5), (x(c), margin - 1)], fill=_OUTLINE_LABEL, width=1)
        draw.text((x(c) + 2, 2), str(c), fill=_OUTLINE_LABEL)
        draw.line([(x(c), y(rows) + 1), (x(c), y(rows) + 5)], fill=_OUTLINE_LABEL, width=1)
        draw.text((x(c) + 2, y(rows) + 8), str(c), fill=_OUTLINE_LABEL)
    for r in range(0, rows, _OUTLINE_TICK_EVERY):
        draw.line([(margin - 5, y(r)), (margin - 1, y(r))], fill=_OUTLINE_LABEL, width=1)
        draw.text((2, y(r) + 2), str(r), fill=_OUTLINE_LABEL)
        draw.line([(x(cols) + 1, y(r)), (x(cols) + 5, y(r))], fill=_OUTLINE_LABEL, width=1)
        draw.text((x(cols) + 8, y(r) + 2), str(r), fill=_OUTLINE_LABEL)
    return image


def frame_to_png_data_url(frame: Frame, *, upscale: int | None = None, style: str | None = None) -> str:
    rows = len(frame.grid)
    cols = max((len(row) for row in frame.grid), default=0)
    if rows <= 0 or cols <= 0:
        raise ValueError("Cannot render an empty grid as an image.")

    scale = current_grid_image_upscale() if upscale is None else max(1, int(upscale))
    resolved_style = current_grid_image_style() if style is None else style
    if resolved_style == "outline":
        image = _render_outline(list(frame.grid), rows, cols, scale)
    else:
        image = _render_plain(list(frame.grid), rows, cols, scale)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def current_grid_image_part(frame: Frame | None) -> dict[str, Any] | None:
    if frame is None or not current_grid_image_enabled():
        return None
    return {
        "type": "image_url",
        "image_url": {
            "url": frame_to_png_data_url(frame),
        },
    }

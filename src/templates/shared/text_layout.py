from __future__ import annotations

from typing import Any

from PIL import ImageDraw

from src.renderer import draw_text_box


def draw_fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    *,
    max_size: int,
    min_size: int,
    fill: str,
    bold: bool = False,
    align: str = "left",
    line_spacing: float = 1.12,
    record_id: str = "text",
    records: list[dict[str, Any]] | None = None,
) -> bool:
    return draw_text_box(
        draw,
        text,
        box,
        max_size,
        min_size,
        fill,
        bold=bold,
        align=align,
        line_spacing=line_spacing,
        record_id=record_id,
        records=records,
    )

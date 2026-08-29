from __future__ import annotations

from typing import Any

from src.templates.base import PagePlan
from src.templates.shared.validation import validate_template_page

from .layout import HEIGHT, WIDTH


def validate_page(records: list[dict[str, Any]], page_plan: PagePlan, height: int = HEIGHT) -> tuple[list[str], list[str]]:
    rects = [
        {"id": slot.metric_id, "x": slot.cell_rect[0], "y": slot.cell_rect[1], "w": slot.cell_rect[2], "h": slot.cell_rect[3]}
        for slot in page_plan.slots
    ]
    return validate_template_page(records, rects, WIDTH, height)

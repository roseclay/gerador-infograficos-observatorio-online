from __future__ import annotations

from typing import Any

from src.validation import validate_no_overlaps, validate_text_bounds


def validate_template_page(records: list[dict[str, Any]], rects: list[dict[str, Any]], width: int, height: int) -> tuple[list[str], list[str]]:
    return validate_text_bounds(records, width, height), validate_no_overlaps(rects, padding=0)

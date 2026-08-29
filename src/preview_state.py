from __future__ import annotations

from dataclasses import dataclass


MIN_PREVIEW_RATIO = 0.28
MAX_PREVIEW_RATIO = 0.62
DEFAULT_PREVIEW_RATIO = 0.42
MIN_PREVIEW_WIDTH = 260


@dataclass(frozen=True)
class PanelWidths:
    editor: float
    preview: float


def clamp_preview_ratio(value: float | int | str | None) -> float:
    try:
        ratio = float(value)
    except (TypeError, ValueError):
        ratio = DEFAULT_PREVIEW_RATIO
    return min(MAX_PREVIEW_RATIO, max(MIN_PREVIEW_RATIO, ratio))


def fallback_preview_ratio(current: float, action: str | None = None) -> float:
    ratio = clamp_preview_ratio(current)
    if action == "smaller":
        return clamp_preview_ratio(ratio - 0.08)
    if action == "balanced":
        return DEFAULT_PREVIEW_RATIO
    if action == "larger":
        return clamp_preview_ratio(ratio + 0.08)
    return ratio


def panel_widths(ratio: float, minimized: bool = False) -> PanelWidths:
    if minimized:
        return PanelWidths(editor=0.94, preview=0.06)
    preview = clamp_preview_ratio(ratio)
    return PanelWidths(editor=1.0 - preview, preview=preview)


def preview_image_width(container_width: int, ratio: float, fit_width: bool, zoom: int) -> int:
    available = max(MIN_PREVIEW_WIDTH, int(container_width * clamp_preview_ratio(ratio)))
    if fit_width:
        return available
    return max(MIN_PREVIEW_WIDTH, int(available * max(25, min(100, int(zoom))) / 100))

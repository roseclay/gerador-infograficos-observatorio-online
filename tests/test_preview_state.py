from __future__ import annotations

from src.preview_state import (
    DEFAULT_PREVIEW_RATIO,
    MAX_PREVIEW_RATIO,
    MIN_PREVIEW_RATIO,
    clamp_preview_ratio,
    fallback_preview_ratio,
    panel_widths,
    preview_image_width,
)


def test_preview_ratio_is_clamped_to_supported_limits():
    assert clamp_preview_ratio(None) == DEFAULT_PREVIEW_RATIO
    assert clamp_preview_ratio(0.01) == MIN_PREVIEW_RATIO
    assert clamp_preview_ratio(0.99) == MAX_PREVIEW_RATIO
    assert clamp_preview_ratio("0.35") == 0.35


def test_fallback_width_buttons_adjust_ratio():
    assert fallback_preview_ratio(0.42, "smaller") < 0.42
    assert fallback_preview_ratio(0.42, "larger") > 0.42
    assert fallback_preview_ratio(0.55, "balanced") == DEFAULT_PREVIEW_RATIO
    assert fallback_preview_ratio(99, "larger") == MAX_PREVIEW_RATIO


def test_panel_widths_preserve_minimized_preview_slot():
    normal = panel_widths(0.4, minimized=False)
    assert normal.editor == 0.6
    assert normal.preview == 0.4

    minimized = panel_widths(0.4, minimized=True)
    assert minimized.editor > minimized.preview
    assert minimized.preview > 0


def test_preview_image_width_respects_fit_and_zoom_limits():
    assert preview_image_width(1200, 0.5, True, 70) == 600
    assert preview_image_width(1200, 0.5, False, 50) == 300
    assert preview_image_width(1200, 0.5, False, 5) == 260

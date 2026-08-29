from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any


@dataclass(frozen=True)
class CardBox:
    metric_id: str
    x: int
    y: int
    w: int
    h: int

    def as_rect(self) -> dict[str, Any]:
        return {"id": self.metric_id, "x": self.x, "y": self.y, "w": self.w, "h": self.h}


@dataclass(frozen=True)
class SectionLayout:
    title: str
    title_box: tuple[int, int, int, int]
    cards: list[CardBox]
    show_title: bool = True


@dataclass(frozen=True)
class InfographicLayout:
    width: int
    height: int
    header_box: tuple[int, int, int, int]
    content_box: tuple[int, int, int, int]
    footer_box: tuple[int, int, int, int]
    sections: list[SectionLayout]

    @property
    def card_rects(self) -> list[dict[str, Any]]:
        return [card.as_rect() for section in self.sections for card in section.cards]


def _metric_field(metric: Any, field: str, default: Any = None) -> Any:
    if isinstance(metric, dict):
        return metric.get(field, default)
    return getattr(metric, field, default)


def _columns_for_count(count: int, single_section: bool = False) -> int:
    if count <= 1:
        return 1
    if count == 2:
        return 2
    if single_section and count <= 4:
        return 2
    if count == 3:
        return 3
    if count == 4:
        return 2
    return 3


def build_layout(metrics: list[Any], width: int = 1600, height: int = 2000) -> InfographicLayout:
    if not 1 <= len(metrics) <= 9:
        raise ValueError("o layout aceita de 1 a 9 indicadores")

    margin_x = 104
    header_box = (margin_x, 66, width - (margin_x * 2), 340)
    content_top = 432
    content_bottom = 1710
    footer_box = (margin_x, 1742, width - (margin_x * 2), 210)

    grouped: dict[str, list[Any]] = {}
    section_order: list[str] = []
    for metric in metrics:
        section = str(_metric_field(metric, "section", "Indicadores") or "Indicadores")
        if section not in grouped:
            grouped[section] = []
            section_order.append(section)
        grouped[section].append(metric)

    for section in grouped.values():
        section.sort(key=lambda item: (int(_metric_field(item, "order", 0) or 0), str(_metric_field(item, "label", ""))))

    sections_meta = []
    total_rows = 0
    single_section = len(section_order) == 1
    for title in section_order:
        count = len(grouped[title])
        columns = _columns_for_count(count, single_section=single_section)
        rows = ceil(count / columns)
        show_title = any(bool(_metric_field(metric, "show_section_title", True)) for metric in grouped[title])
        section_order_value = min(int(_metric_field(metric, "section_order", 999) or 999) for metric in grouped[title])
        sections_meta.append((section_order_value, title, grouped[title], columns, rows, show_title))
        total_rows += rows
    sections_meta.sort(key=lambda item: (item[0], item[1]))

    title_h = 54
    section_gap = 34 if len(sections_meta) > 1 else 0
    card_gap = 18
    total_title_h = sum(title_h if meta[5] else 0 for meta in sections_meta)
    total_section_gap = max(0, len(sections_meta) - 1) * section_gap
    total_row_gaps = sum((rows - 1) * card_gap for _, _, _, _, rows, _ in sections_meta)
    available_for_rows = (content_bottom - content_top) - total_title_h - total_section_gap - total_row_gaps
    row_h = int(max(210, min(390, available_for_rows / max(1, total_rows))))

    sections: list[SectionLayout] = []
    y = content_top
    for _, title, section_metrics, columns, rows, show_title in sections_meta:
        current_title_h = title_h if show_title else 0
        title_box = (margin_x, y, width - (margin_x * 2), current_title_h)
        y += current_title_h
        grid_w = width - (margin_x * 2)
        column_gap = 18
        card_w = int((grid_w - (columns - 1) * column_gap) / columns)
        cards: list[CardBox] = []
        for index, metric in enumerate(section_metrics):
            row = index // columns
            col = index % columns
            x = margin_x + col * (card_w + column_gap)
            card_y = y + row * (row_h + card_gap)
            metric_id = str(_metric_field(metric, "metric_id", _metric_field(metric, "id", f"metric-{index}")))
            cards.append(CardBox(metric_id=metric_id, x=x, y=card_y, w=card_w, h=row_h))
        sections.append(SectionLayout(title=title, title_box=title_box, cards=cards, show_title=show_title))
        y += rows * row_h + (rows - 1) * card_gap + section_gap

    return InfographicLayout(
        width=width,
        height=height,
        header_box=header_box,
        content_box=(margin_x, content_top, width - (margin_x * 2), content_bottom - content_top),
        footer_box=footer_box,
        sections=sections,
    )

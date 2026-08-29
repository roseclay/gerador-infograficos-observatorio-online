from __future__ import annotations

from collections import OrderedDict
from typing import Any

from src.templates.base import PagePlan, SlotPlan, TextPlacement


WIDTH = 1122
HEIGHT = 1402
BLUE = "#0057B8"
DARK_BLUE = "#0B2F78"
TEXT = "#142451"
MUTED = "#65758B"
YELLOW = "#FFD100"

HEADER_BOX = (78, 68, 650, 34)
TITLE_BOX = (78, 122, 624, 84)
TITLE_BOX_NO_SUBTITLE = (78, 132, 624, 104)
SUBTITLE_BOX = (79, 214, 560, 74)
DEMO_BOX = (782, 302, 240, 32)

SECTION_TITLE_BOXES = {
    "principal": (80, 268, 960, 20),
    "intermediate": (80, 699, 960, 20),
    "complementary": (80, 953, 960, 20),
}

PANEL_MASKS = {
    "intermediate": (52, 706, 1018, 254),
    "complementary": (52, 960, 1018, 250),
    "principal_vertical": (554, 318, 8, 356),
    "principal_horizontal": (98, 486, 925, 7),
    "intermediate_vertical": (555, 748, 8, 182),
    "complementary_left": (386, 998, 8, 166),
    "complementary_right": (696, 998, 8, 166),
}

FOOTER = {
    "cta": (392, 1207, 340, 58),
    "meta": (98, 1274, 926, 54),
    "bahia_logo": (438, 1310, 250, 78),
}

FOOTER_COMPACT = {
    "meta": (98, 1208, 926, 48),
    "bahia_logo": (432, 1254, 262, 82),
    "height": 1348,
}

SLOTS: tuple[dict[str, Any], ...] = (
    {
        "slot_id": "principal_1",
        "section_key": "principal",
        "cell_rect": (88, 318, 438, 150),
        "icon_box": (96, 320, 182, 142),
        "value_box": (302, 344, 226, 68),
        "label_box": (303, 431, 224, 62),
    },
    {
        "slot_id": "principal_2",
        "section_key": "principal",
        "cell_rect": (584, 318, 438, 150),
        "icon_box": (600, 326, 136, 136),
        "value_box": (756, 344, 230, 68),
        "label_box": (756, 431, 244, 62),
    },
    {
        "slot_id": "principal_3",
        "section_key": "principal",
        "cell_rect": (88, 504, 438, 170),
        "icon_box": (102, 510, 158, 158),
        "value_box": (302, 524, 226, 68),
        "label_box": (303, 605, 228, 78),
    },
    {
        "slot_id": "principal_4",
        "section_key": "principal",
        "cell_rect": (584, 504, 438, 170),
        "icon_box": (594, 510, 148, 148),
        "value_box": (756, 524, 230, 68),
        "label_box": (756, 605, 240, 78),
    },
    {
        "slot_id": "intermediate_1",
        "section_key": "intermediate",
        "cell_rect": (88, 758, 440, 145),
        "icon_box": (95, 768, 116, 116),
        "value_box": (222, 770, 268, 80),
        "label_box": (254, 862, 266, 70),
    },
    {
        "slot_id": "intermediate_2",
        "section_key": "intermediate",
        "cell_rect": (594, 758, 420, 145),
        "icon_box": (900, 754, 112, 132),
        "value_box": (632, 770, 260, 80),
        "label_box": (642, 862, 266, 70),
    },
    {
        "slot_id": "complementary_1",
        "section_key": "complementary",
        "cell_rect": (92, 1018, 288, 130),
        "icon_box": (96, 1016, 112, 132),
        "value_box": (212, 1037, 152, 58),
        "label_box": (212, 1098, 162, 58),
    },
    {
        "slot_id": "complementary_2",
        "section_key": "complementary",
        "cell_rect": (410, 1018, 285, 130),
        "icon_box": (418, 1024, 104, 122),
        "value_box": (538, 1037, 135, 58),
        "label_box": (538, 1098, 148, 66),
    },
    {
        "slot_id": "complementary_3",
        "section_key": "complementary",
        "cell_rect": (728, 1018, 300, 130),
        "icon_box": (734, 1012, 108, 132),
        "value_box": (846, 1037, 172, 58),
        "label_box": (846, 1098, 176, 70),
    },
)

TOP_SINGLE = (
    {
        "slot_id": "principal_1",
        "section_key": "principal",
        "cell_rect": (96, 348, 930, 265),
        "icon_box": (244, 386, 178, 178),
        "value_box": (472, 378, 330, 90),
        "label_box": (472, 492, 330, 76),
    },
)

TOP_TWO = (
    {
        "slot_id": "principal_1",
        "section_key": "principal",
        "cell_rect": (98, 350, 430, 245),
        "icon_box": (118, 392, 150, 150),
        "value_box": (302, 386, 226, 78),
        "label_box": (303, 488, 224, 70),
    },
    {
        "slot_id": "principal_2",
        "section_key": "principal",
        "cell_rect": (594, 350, 420, 245),
        "icon_box": (610, 392, 138, 138),
        "value_box": (756, 386, 230, 78),
        "label_box": (756, 488, 244, 70),
    },
)

TOP_THREE = (
    {
        "slot_id": "principal_1",
        "section_key": "principal",
        "cell_rect": (102, 354, 285, 235),
        "icon_box": (122, 370, 128, 128),
        "value_box": (104, 504, 280, 70),
        "label_box": (104, 578, 280, 70),
    },
    {
        "slot_id": "principal_2",
        "section_key": "principal",
        "cell_rect": (418, 354, 285, 235),
        "icon_box": (438, 370, 128, 128),
        "value_box": (420, 504, 280, 70),
        "label_box": (420, 578, 280, 70),
    },
    {
        "slot_id": "principal_3",
        "section_key": "principal",
        "cell_rect": (734, 354, 285, 235),
        "icon_box": (754, 370, 128, 128),
        "value_box": (736, 504, 280, 70),
        "label_box": (736, 578, 280, 70),
    },
)

MIDDLE_SINGLE = (
    {
        "slot_id": "intermediate_1",
        "section_key": "intermediate",
        "cell_rect": (96, 758, 930, 145),
        "icon_box": (250, 766, 124, 124),
        "value_box": (410, 768, 300, 82),
        "label_box": (410, 860, 310, 70),
    },
)

BOTTOM_SINGLE = (
    {
        "slot_id": "complementary_1",
        "section_key": "complementary",
        "cell_rect": (112, 1014, 900, 140),
        "icon_box": (276, 1018, 122, 132),
        "value_box": (438, 1033, 210, 62),
        "label_box": (438, 1099, 270, 66),
    },
)

BOTTOM_TWO = (
    {
        "slot_id": "complementary_1",
        "section_key": "complementary",
        "cell_rect": (98, 1014, 430, 140),
        "icon_box": (116, 1018, 118, 132),
        "value_box": (254, 1035, 190, 62),
        "label_box": (254, 1100, 210, 64),
    },
    {
        "slot_id": "complementary_2",
        "section_key": "complementary",
        "cell_rect": (594, 1014, 420, 140),
        "icon_box": (612, 1018, 118, 132),
        "value_box": (750, 1035, 190, 62),
        "label_box": (750, 1100, 220, 64),
    },
)


def slot_defs_for_count(count: int) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
    if count == 1:
        return TOP_SINGLE, ("principal_vertical", "principal_horizontal", "intermediate", "complementary")
    if count == 2:
        return TOP_TWO, ("principal_horizontal", "intermediate", "complementary")
    if count == 3:
        return TOP_THREE, ("principal_vertical", "principal_horizontal", "intermediate", "complementary")
    if count == 5:
        return SLOTS[:4] + MIDDLE_SINGLE, ("intermediate_vertical", "complementary")
    if count == 7:
        return SLOTS[:6] + BOTTOM_SINGLE, ("complementary_left", "complementary_right")
    if count == 8:
        return SLOTS[:6] + BOTTOM_TWO, ("complementary_left", "complementary_right")
    if count <= len(SLOTS):
        hidden = ("intermediate", "complementary") if count <= 4 else ("complementary",) if count <= 6 else ()
        return SLOTS[:count], hidden
    raise ValueError("o template institucional claro aceita de 1 a 9 indicadores por página")


def _metric_field(metric: Any, field: str, default: Any = None) -> Any:
    if isinstance(metric, dict):
        return metric.get(field, default)
    return getattr(metric, field, default)


def _section_groups(metrics: list[Any]) -> OrderedDict[str, list[Any]]:
    groups: dict[str, list[Any]] = {}
    order: dict[str, int] = {}
    for metric in metrics:
        section = str(_metric_field(metric, "section", "Indicadores") or "Indicadores")
        groups.setdefault(section, []).append(metric)
        order[section] = min(order.get(section, 999), int(_metric_field(metric, "section_order", 999) or 999))
    sorted_names = sorted(groups, key=lambda name: (order[name], name))
    result: OrderedDict[str, list[Any]] = OrderedDict()
    for name in sorted_names:
        result[name] = sorted(groups[name], key=lambda metric: (int(_metric_field(metric, "order", 0) or 0), str(_metric_field(metric, "label", ""))))
    return result


def _title_for_section(name: str) -> str:
    normalized = str(name or "").strip()
    return normalized if normalized else "Indicadores"


def build_page_plan(metrics: list[Any], page: int = 1) -> PagePlan:
    if not 1 <= len(metrics) <= len(SLOTS):
        raise ValueError("o template institucional claro aceita de 1 a 9 indicadores por página")

    groups = _section_groups(metrics)
    ordered_metrics: list[Any] = []
    titles: list[TextPlacement] = []
    section_keys = ("principal", "intermediate", "complementary")
    group_items = list(groups.items())
    for index, (section_name, section_metrics) in enumerate(group_items):
        section_key = section_keys[min(index, len(section_keys) - 1)]
        if any(bool(_metric_field(metric, "show_section_title", True)) for metric in section_metrics):
            box = SECTION_TITLE_BOXES[section_key]
            titles.append(TextPlacement(
                id=f"secao-{section_key}",
                text=_title_for_section(section_name).upper(),
                box=box,
                max_size=21 if section_key == "principal" else 20,
                min_size=12,
                fill=BLUE,
                bold=True,
                align="center",
            ))
        ordered_metrics.extend(section_metrics)

    slot_defs, masks = slot_defs_for_count(len(ordered_metrics))
    slots: list[SlotPlan] = []
    for index, metric in enumerate(ordered_metrics):
        slot = slot_defs[index]
        metric_id = str(_metric_field(metric, "metric_id", _metric_field(metric, "id", f"metric-{index + 1}")))
        section = str(_metric_field(metric, "section", "Indicadores") or "Indicadores")
        slots.append(SlotPlan(
            metric_id=metric_id,
            section=section,
            slot_id=str(slot["slot_id"]),
            page=page,
            icon_box=slot["icon_box"],
            value_box=slot["value_box"],
            label_box=slot["label_box"],
            cell_rect=slot["cell_rect"],
        ))

    return PagePlan(page=page, metrics=ordered_metrics, slots=slots, section_titles=titles, hidden_panels=masks)

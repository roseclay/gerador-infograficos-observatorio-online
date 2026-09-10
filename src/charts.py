from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from io import BytesIO
from typing import Any

from PIL import Image, ImageDraw

from .formatting import format_display_value, parse_brazilian_number
from .icon_registry import DEFAULT_COLOR, normalize_hex_color
from .renderer import draw_text_box, get_font


CHART_TYPES = {"bar_horizontal", "bar_vertical"}


def _to_decimal(value: Any) -> Decimal:
    return parse_brazilian_number(value)


def _text_size(draw: ImageDraw.ImageDraw, text: str, size: int, bold: bool = False) -> tuple[int, int]:
    font = get_font(size, bold=bold)
    box = draw.textbbox((0, 0), str(text), font=font)
    return box[2] - box[0], box[3] - box[1]


def normalize_chart_series(series: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized = []
    for index, item in enumerate(series or [], start=1):
        raw = item.get("raw_value", item.get("value", ""))
        try:
            numeric = _to_decimal(raw)
            valid = True
            error = ""
        except Exception as exc:
            numeric = Decimal("0")
            valid = False
            error = str(exc)
        display = str(item.get("display_value") or format_display_value(raw, int(item.get("precision") or 0))).strip()
        normalized.append({
            "key": str(item.get("key") or item.get("indicator_id") or f"serie_{index:03d}").strip(),
            "label": str(item.get("label") or item.get("key") or f"Série {index}").strip(),
            "raw_value": str(raw).strip(),
            "numeric_value": numeric,
            "display_value": display,
            "color": normalize_hex_color(str(item.get("color") or DEFAULT_COLOR)),
            "order": int(item.get("order") or index),
            "valid": valid,
            "error": error,
        })
    normalized.sort(key=lambda row: (row["order"], row["label"]))
    return normalized


def normalize_chart_config(chart: dict[str, Any] | None) -> dict[str, Any]:
    item = deepcopy(chart or {})
    chart_type = str(item.get("type") or "bar_horizontal").strip()
    if chart_type not in CHART_TYPES:
        chart_type = "bar_horizontal"
    fixed_max = item.get("scale_max")
    try:
        fixed_max = _to_decimal(fixed_max) if str(fixed_max or "").strip() else None
    except Exception:
        fixed_max = None
    return {
        "type": chart_type,
        "title": str(item.get("title") or "").strip(),
        "series": normalize_chart_series(item.get("series") or []),
        "show_values": bool(item.get("show_values", True)),
        "show_labels": bool(item.get("show_labels", True)),
        "show_axis": bool(item.get("show_axis", False)),
        "background": str(item.get("background") or "transparent").strip(),
        "bar_color": normalize_hex_color(str(item.get("bar_color") or DEFAULT_COLOR)),
        "label_color": normalize_hex_color(str(item.get("label_color") or "#12356F")),
        "value_color": normalize_hex_color(str(item.get("value_color") or DEFAULT_COLOR)),
        "font_size": max(8, int(item.get("font_size") or 28)),
        "scale_mode": "fixed" if fixed_max is not None else "auto",
        "scale_max": fixed_max,
        "sort": str(item.get("sort") or "manual").strip(),
    }


def chart_errors(chart: dict[str, Any]) -> list[str]:
    errors = []
    series = chart.get("series") or []
    if not series:
        errors.append("grafico sem serie")
    invalid = [row for row in series if not row.get("valid", True)]
    for row in invalid:
        errors.append(f"{row.get('label')}: valor invalido ({row.get('error')})")
    if any(row.get("numeric_value", Decimal("0")) < 0 for row in series):
        errors.append("grafico de contagem nao aceita valores negativos")
    values = [row.get("numeric_value", Decimal("0")) for row in series]
    if chart.get("scale_mode") == "fixed" and chart.get("scale_max") is not None and values:
        if max(values) > chart["scale_max"]:
            errors.append("valor excede a escala fixa configurada")
    return errors


def _ordered_series(chart: dict[str, Any]) -> list[dict[str, Any]]:
    series = list(chart.get("series") or [])
    sort = chart.get("sort")
    if sort == "value_desc":
        series.sort(key=lambda row: row.get("numeric_value", Decimal("0")), reverse=True)
    elif sort == "value_asc":
        series.sort(key=lambda row: row.get("numeric_value", Decimal("0")))
    return series


def _scale_max(chart: dict[str, Any], series: list[dict[str, Any]]) -> Decimal:
    if chart.get("scale_mode") == "fixed" and chart.get("scale_max") is not None:
        return max(Decimal("1"), chart["scale_max"])
    values = [row.get("numeric_value", Decimal("0")) for row in series]
    return max([Decimal("1"), *values])


def _draw_background(draw: ImageDraw.ImageDraw, width: int, height: int, background: str) -> None:
    if background and background != "transparent":
        draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=16, fill=background)


def _draw_horizontal(chart: dict[str, Any], width: int, height: int) -> tuple[Image.Image, list[dict[str, Any]]]:
    image = Image.new("RGBA", (max(1, width), max(1, height)), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    _draw_background(draw, width, height, chart["background"])
    records: list[dict[str, Any]] = []
    series = _ordered_series(chart)
    max_value = _scale_max(chart, series)
    pad_x = max(10, int(width * 0.05))
    top = max(8, int(height * 0.08))
    if chart["title"]:
        draw_text_box(draw, chart["title"], (pad_x, top, width - pad_x * 2, 42), chart["font_size"] + 4, 14, chart["label_color"], bold=True, record_id="chart-title", records=records)
        top += 50
    row_count = max(1, len(series))
    row_h = max(22, int((height - top - 12) / row_count))
    label_w = int(width * 0.30) if chart["show_labels"] else 0
    value_w = int(width * 0.18) if chart["show_values"] else 0
    bar_x = pad_x + label_w + 12
    bar_w = max(20, width - bar_x - value_w - pad_x - 12)
    bar_h = max(8, min(28, int(row_h * 0.34)))
    for index, row in enumerate(series):
        y = top + index * row_h
        label_size = max(10, min(chart["font_size"], int(row_h * 0.36)))
        if chart["show_labels"]:
            draw_text_box(draw, row["label"], (pad_x, y + 2, label_w, row_h - 4), label_size, 8, chart["label_color"], bold=False, record_id=f"chart-label-{row['key']}", records=records)
        track_y = y + (row_h - bar_h) // 2
        draw.rounded_rectangle((bar_x, track_y, bar_x + bar_w, track_y + bar_h), radius=max(4, bar_h // 2), fill=(224, 233, 242, 220))
        ratio = float(row.get("numeric_value", Decimal("0")) / max_value) if max_value else 0.0
        fill_w = int(bar_w * max(0.0, min(1.0, ratio)))
        if fill_w:
            draw.rounded_rectangle((bar_x, track_y, bar_x + fill_w, track_y + bar_h), radius=max(4, bar_h // 2), fill=row["color"])
        records.append({"id": f"barra-{row['key']}", "x": bar_x, "y": track_y, "w": fill_w, "h": bar_h, "kind": "chart_bar", "origin": 0})
        if chart["show_values"]:
            draw_text_box(draw, row["display_value"], (bar_x + bar_w + 12, y, value_w, row_h), label_size + 2, 8, chart["value_color"], bold=True, align="right", record_id=f"chart-value-{row['key']}", records=records)
    return image, records


def _draw_vertical(chart: dict[str, Any], width: int, height: int) -> tuple[Image.Image, list[dict[str, Any]]]:
    image = Image.new("RGBA", (max(1, width), max(1, height)), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    _draw_background(draw, width, height, chart["background"])
    records: list[dict[str, Any]] = []
    series = _ordered_series(chart)
    max_value = _scale_max(chart, series)
    pad_x = max(12, int(width * 0.07))
    top = max(8, int(height * 0.08))
    if chart["title"]:
        draw_text_box(draw, chart["title"], (pad_x, top, width - pad_x * 2, 42), chart["font_size"] + 4, 14, chart["label_color"], bold=True, align="center", record_id="chart-title", records=records)
        top += 50
    bottom_label_h = 44 if chart["show_labels"] else 12
    value_h = 32 if chart["show_values"] else 8
    plot_h = max(20, height - top - bottom_label_h - value_h - 12)
    plot_w = max(20, width - pad_x * 2)
    column_gap = max(8, int(plot_w * 0.035))
    col_w = max(8, int((plot_w - column_gap * max(0, len(series) - 1)) / max(1, len(series))))
    baseline = top + plot_h
    if chart["show_axis"]:
        draw.line((pad_x, baseline, width - pad_x, baseline), fill=(191, 210, 232, 230), width=2)
    for index, row in enumerate(series):
        x = pad_x + index * (col_w + column_gap)
        ratio = float(row.get("numeric_value", Decimal("0")) / max_value) if max_value else 0.0
        col_h = int(plot_h * max(0.0, min(1.0, ratio)))
        y = baseline - col_h
        if col_h:
            draw.rounded_rectangle((x, y, x + col_w, baseline), radius=max(4, col_w // 5), fill=row["color"])
        records.append({"id": f"coluna-{row['key']}", "x": x, "y": y, "w": col_w, "h": col_h, "kind": "chart_column", "origin": 0})
        label_size = max(9, min(chart["font_size"], 20))
        if chart["show_values"]:
            draw_text_box(draw, row["display_value"], (x - 12, max(top, y - value_h - 2), col_w + 24, value_h), label_size + 2, 8, chart["value_color"], bold=True, align="center", record_id=f"chart-value-{row['key']}", records=records)
        if chart["show_labels"]:
            draw_text_box(draw, row["label"], (x - 18, baseline + 8, col_w + 36, bottom_label_h), label_size, 8, chart["label_color"], bold=False, align="center", record_id=f"chart-label-{row['key']}", records=records)
    return image, records


def render_chart_image(chart: dict[str, Any] | None, width: int, height: int) -> tuple[Image.Image, list[dict[str, Any]], list[str]]:
    normalized = normalize_chart_config(chart)
    errors = chart_errors(normalized)
    if normalized["type"] == "bar_vertical":
        image, records = _draw_vertical(normalized, width, height)
    else:
        image, records = _draw_horizontal(normalized, width, height)
    return image, records, errors


def render_chart_png_bytes(chart: dict[str, Any] | None, width: int, height: int) -> bytes:
    image, _records, _errors = render_chart_image(chart, width, height)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()

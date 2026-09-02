from decimal import Decimal

from src.charts import chart_errors, normalize_chart_config, render_chart_image


def test_horizontal_chart_uses_shared_scale_and_accepts_zero():
    chart = normalize_chart_config({
        "type": "bar_horizontal",
        "series": [
            {"key": "a", "label": "A", "raw_value": "100", "display_value": "100"},
            {"key": "b", "label": "B", "raw_value": "50", "display_value": "50"},
            {"key": "c", "label": "C", "raw_value": "0", "display_value": "0"},
        ],
    })

    assert chart["series"][0]["numeric_value"] == Decimal("100")
    assert chart["series"][2]["numeric_value"] == Decimal("0")
    assert chart_errors(chart) == []


def test_vertical_chart_renders_transparent_image():
    image, records, errors = render_chart_image({
        "type": "bar_vertical",
        "title": "Série anual",
        "series": [
            {"key": "2024", "label": "2024", "raw_value": "10", "display_value": "10"},
            {"key": "2025", "label": "2025", "raw_value": "30", "display_value": "30"},
        ],
        "show_axis": True,
    }, 360, 240)

    assert image.size == (360, 240)
    assert records
    assert errors == []


def test_fixed_scale_reports_overflow_instead_of_silently_clipping():
    chart = normalize_chart_config({
        "type": "bar_horizontal",
        "scale_max": "10",
        "series": [{"key": "a", "label": "A", "raw_value": "12", "display_value": "12"}],
    })

    assert "valor excede a escala fixa configurada" in chart_errors(chart)

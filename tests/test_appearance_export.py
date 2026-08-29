from __future__ import annotations

from pathlib import Path

from PIL import Image

from src.metrics import MetricResult
from src.renderer import render_card_thumbnail, render_infographic


def _count_near_color(image: Image.Image, target: tuple[int, int, int], tolerance: int = 16) -> int:
    rgb = image.convert("RGB")
    pixels = rgb.load()
    total = 0
    for y in range(rgb.height):
        for x in range(rgb.width):
            red, green, blue = pixels[x, y]
            if abs(red - target[0]) <= tolerance and abs(green - target[1]) <= tolerance and abs(blue - target[2]) <= tolerance:
                total += 1
    return total


def test_thumbnail_uses_selected_icon_and_color():
    metric = {
        "metric_id": "a",
        "label": "Indicador",
        "display_value": "123",
        "icon": "flask",
        "color": "#B28A8A",
    }

    image = render_card_thumbnail(metric)

    assert image.size == (620, 300)
    assert _count_near_color(image, (178, 138, 138)) > 100


def test_png_and_pdf_exports_use_selected_appearance(tmp_path: Path):
    metric = MetricResult(
        "a",
        "Indicador",
        "Indicadores",
        "valor",
        "direct_value",
        "sem filtro",
        "123",
        "123",
        "direto",
        "",
        "teste.csv",
        icon="flask",
        color="#B28A8A",
    )
    metadata = {
        "header": "OBSERVATÓRIO DE CIÊNCIA, TECNOLOGIA E INOVAÇÃO DA BAHIA",
        "title": "Painel institucional",
        "subtitle": "Resumo dos dados carregados.",
        "source": "teste.csv",
        "updated_at": "25/08/2026",
        "cta": "",
    }
    output_png = tmp_path / "info.png"
    output_pdf = tmp_path / "info.pdf"

    report = render_infographic([metric], metadata, {}, output_png, output_pdf)
    image = Image.open(output_png)

    assert output_pdf.exists()
    assert not report.errors
    assert _count_near_color(image, (178, 138, 138)) > 100

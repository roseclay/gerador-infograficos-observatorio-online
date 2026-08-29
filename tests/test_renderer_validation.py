from pathlib import Path

from PIL import Image

from src.metrics import MetricResult
from src.renderer import render_infographic
from src.validation import validate_no_overlaps, validate_text_bounds


def test_renderer_exports_expected_dimensions(tmp_path: Path):
    metrics = [
        MetricResult("a", "Indicador Alfa", "Indicadores", "valor", "direct_value", "sem filtro", "12345", "12.345", "direto", "", "teste.csv", icon="users"),
        MetricResult("b", "Indicador Beta", "Indicadores", "valor", "direct_value", "sem filtro", "678", "678", "direto", "", "teste.csv", icon="network"),
    ]
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

    report = render_infographic(metrics, metadata, {}, output_png, output_pdf)
    image = Image.open(output_png)

    assert image.size == (1600, 2000)
    assert output_pdf.exists()
    assert not report.overlap_errors
    assert not report.text_errors


def test_validation_detects_text_outside_bounds():
    errors = validate_text_bounds([{"id": "texto", "x": 10, "y": 10, "w": 200, "h": 100, "fits": False}], 160, 120)

    assert errors


def test_validation_detects_overlap():
    errors = validate_no_overlaps([
        {"id": "a", "x": 0, "y": 0, "w": 100, "h": 100},
        {"id": "b", "x": 50, "y": 50, "w": 100, "h": 100},
    ])

    assert errors

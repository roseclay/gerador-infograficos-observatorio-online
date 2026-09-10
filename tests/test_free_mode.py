from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd
from PIL import Image

from src.free_mode import (
    build_free_mode_config,
    build_free_mode_config_with_name,
    changed_dragged_fields,
    fields_from_dataframe,
    fields_to_dataframe,
    free_mode_export_names,
    merge_dragged_fields,
    new_text_field,
    render_free_field_preview_map,
    render_free_infographic,
    render_free_preview_bytes,
    write_fields_csv,
)


def test_imports_long_field_csv_with_coordinates():
    dataframe = pd.DataFrame([
        {"imagem_base": "base.png", "campo": "Total A", "valor": "9.999", "x": "30", "y": "40"},
        {"imagem_base": "base.png", "campo": "Total B", "valor": "+80", "x": "230", "y": "140"},
    ])

    result = fields_from_dataframe(dataframe, image_width=640, image_height=480)

    assert result.base_image_name == "base.png"
    assert result.warnings == []
    assert [field["name"] for field in result.fields] == ["Total A", "Total B"]
    assert [field["value"] for field in result.fields] == ["9.999", "+80"]
    assert result.fields[0]["x"] == 30
    assert result.fields[1]["y"] == 140
    assert result.fields[0]["placed"] is True


def test_imports_wide_field_csv_from_single_record():
    dataframe = pd.DataFrame([{
        "campo1_nome": "Total A",
        "campo1_valor": "alpha",
        "campo1_x": "12",
        "campo1_y": "34",
        "campo2_nome": "Total B",
        "campo2_valor": "beta",
        "campo2_x": "120",
        "campo2_y": "180",
    }])

    result = fields_from_dataframe(dataframe, image_width=500, image_height=300)

    assert [field["name"] for field in result.fields] == ["Total A", "Total B"]
    assert [field["value"] for field in result.fields] == ["alpha", "beta"]
    assert result.fields[0]["x"] == 12
    assert result.fields[1]["y"] == 180


def test_renders_fields_over_base_image(tmp_path: Path):
    base = Image.new("RGB", (700, 420), "#ffffff")
    fields = [
        {
            **new_text_field(order=1, image_width=700, image_height=420),
            "name": "Total A",
            "value": "9.999",
            "x": 60,
            "y": 80,
            "width": 220,
            "height": 70,
            "font_size": 42,
        },
        {
            **new_text_field(order=2, image_width=700, image_height=420),
            "name": "Total B",
            "value": "ok",
            "x": 410,
            "y": 250,
            "width": 180,
            "height": 60,
            "font_size": 34,
        },
    ]

    report = render_free_infographic(base, fields, tmp_path / "livre.png", tmp_path / "livre.pdf")
    image = Image.open(report.output_png)

    assert image.size == (700, 420)
    assert Path(report.output_pdf).exists()
    assert report.errors == []
    assert report.template_id == "imagem_base_livre"


def test_preview_bytes_match_export_renderer_pixels(tmp_path: Path):
    base = Image.new("RGB", (480, 260), "#ffffff")
    fields = [{
        **new_text_field(order=1, image_width=480, image_height=260),
        "name": "Total",
        "value": "11.527",
        "x": 80,
        "y": 90,
        "width": 240,
        "height": 78,
        "font_size": 54,
    }]

    preview_bytes = render_free_preview_bytes(base, fields)
    report = render_free_infographic(base, fields, tmp_path / "export.png")
    preview = Image.open(BytesIO(preview_bytes)).convert("RGB")
    exported = Image.open(report.output_png).convert("RGB")

    assert list(preview.getdata()) == list(exported.getdata())


def test_field_preview_composes_like_export_renderer(tmp_path: Path):
    base = Image.new("RGBA", (480, 260), "#ffffff")
    fields = [{
        **new_text_field(order=1, image_width=480, image_height=260),
        "name": "Total",
        "value": "11.527",
        "x": 80,
        "y": 90,
        "width": 240,
        "height": 78,
        "font_size": 54,
    }]

    previews = render_free_field_preview_map(fields, 480, 260)
    composed = base.copy()
    field_image = Image.open(BytesIO(previews[fields[0]["id"]])).convert("RGBA")
    composed.alpha_composite(field_image, (fields[0]["x"], fields[0]["y"]))
    report = render_free_infographic(base, fields, tmp_path / "export.png")
    exported = Image.open(report.output_png).convert("RGB")

    assert list(composed.convert("RGB").getdata()) == list(exported.getdata())


def test_exports_fields_csv_and_config(tmp_path: Path):
    fields = [{
        **new_text_field(order=1),
        "name": "Total A",
        "value": "texto livre",
        "x": 10,
        "y": 20,
    }]

    csv_path = write_fields_csv(fields, tmp_path / "campos.csv", "base.png")
    exported = pd.read_csv(csv_path)
    config = build_free_mode_config("base.png", fields, (800, 600))
    names = free_mode_export_names("Minha Base.png", date(2026, 8, 25))

    assert exported.iloc[0]["imagem_base"] == "base.png"
    assert fields_to_dataframe(fields, "base.png").iloc[0]["campo"] == "Total A"
    assert config["mode"] == "imagem_base"
    assert config["base_image"]["width"] == 800
    assert names["png"] == "infografico_minha_base_2026-08-25.png"


def test_named_config_and_drag_merge_update_coordinates():
    field = {
        **new_text_field(order=1, image_width=500, image_height=300),
        "name": "Total",
        "value": "123",
        "x": 10,
        "y": 20,
        "width": 120,
        "height": 60,
    }

    config = build_free_mode_config_with_name("base.png", [field], (500, 300), "Indicadores ciência")
    merged = merge_dragged_fields(
        [field],
        [{"id": field["id"], "x": 250, "y": 120, "width": 180, "height": 80, "font_size": 72}],
        500,
        300,
    )

    assert config["name"] == "Indicadores ciência"
    assert merged[0]["x"] == 250
    assert merged[0]["y"] == 120
    assert merged[0]["width"] == 180
    assert merged[0]["height"] == 80
    assert merged[0]["font_size"] == 72


def test_drag_merge_changes_only_the_field_reported_by_the_canvas():
    first = {**new_text_field(order=1, image_width=500, image_height=300), "id": "campo_001", "font_size": 57}
    second = {**new_text_field(["campo_001"], order=2, image_width=500, image_height=300), "id": "campo_002", "font_size": 68}

    browser_result = {
        "selected_id": "campo_002",
        "changed_ids": ["campo_002"],
        "fields": [
            {"id": "campo_001", "font_size": 68},
            {"id": "campo_002", "x": 210, "y": 120, "width": 180, "height": 80, "font_size": 64},
        ],
    }
    merged = merge_dragged_fields(
        [first, second],
        changed_dragged_fields(browser_result),
        500,
        300,
    )

    assert merged[0]["font_size"] == 57
    assert merged[1]["font_size"] == 64


def test_moving_a_field_never_imports_a_stale_font_size_or_dimensions():
    field = {
        **new_text_field(order=1, image_width=500, image_height=300),
        "id": "campo_002",
        "x": 40,
        "y": 50,
        "width": 180,
        "height": 80,
        "font_size": 72,
    }
    browser_result = {
        "selected_id": "campo_002",
        "changed_ids": ["campo_002"],
        "changed_properties": {"campo_002": ["x", "y"]},
        "fields": [
            {"id": "campo_002", "x": 210, "y": 120, "width": 24, "height": 18, "font_size": 8},
        ],
    }

    merged = merge_dragged_fields(
        [field],
        changed_dragged_fields(browser_result),
        500,
        300,
    )

    assert merged[0]["x"] == 210
    assert merged[0]["y"] == 120
    assert merged[0]["width"] == 180
    assert merged[0]["height"] == 80
    assert merged[0]["font_size"] == 72


def test_normalization_assigns_unique_ids_to_imported_rows_without_ids():
    dataframe = pd.DataFrame([
        {"campo": "A", "valor": "1"},
        {"campo": "B", "valor": "2"},
        {"campo": "C", "valor": "3"},
    ])

    result = fields_from_dataframe(dataframe, image_width=500, image_height=300)
    ids = [field["id"] for field in result.fields]

    assert [field["placed"] for field in result.fields] == [False, False, False]
    assert ids == ["campo_001", "campo_002", "campo_003"]


def test_drag_merge_marks_pending_field_as_placed():
    field = {
        **new_text_field(order=1, image_width=500, image_height=300),
        "name": "Pendente",
        "value": "42",
        "placed": False,
    }

    merged = merge_dragged_fields(
        [field],
        [{"id": field["id"], "placed": True, "x": 90, "y": 110, "font_size": 64}],
        500,
        300,
    )

    assert merged[0]["placed"] is True
    assert merged[0]["x"] == 90
    assert merged[0]["y"] == 110
    assert merged[0]["font_size"] == 64

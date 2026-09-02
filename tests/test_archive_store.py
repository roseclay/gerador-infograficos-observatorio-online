from io import BytesIO
from pathlib import Path

from PIL import Image

from src.archive_store import LocalArchiveStore
from src.data_binding import fields_from_dataset_observations
from src.free_mode import render_free_infographic


def png_bytes(width=900, height=600):
    image = Image.new("RGB", (width, height), "#ffffff")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


CSV_V1 = b"""indicador_id,periodo,recorte_id,valor
pesquisadores_ativos,2021-2026,demo_total,1000
grupos_pesquisa,2021-2026,demo_total,120
artigos_cientificos,2021-2026,demo_total,3600
trabalhos_eventos,2021-2026,demo_total,2400
"""

CSV_V2 = b"""indicador_id,periodo,recorte_id,valor
pesquisadores_ativos,2021-2026,demo_total,1100
grupos_pesquisa,2021-2026,demo_total,125
artigos_cientificos,2021-2026,demo_total,3900
trabalhos_eventos,2021-2026,demo_total,2600
"""


def test_archive_persists_dataset_base_and_infographic_across_instances(tmp_path: Path):
    store = LocalArchiveStore(tmp_path / "acervo").bootstrap()
    dataset = store.register_dataset("Demo produção", public_source="Fonte sintética")
    dataset_version = store.add_dataset_version(dataset["id"], CSV_V1, "demo_v1.csv", period="2021-2026")
    base = store.register_base_image("Base limpa demo")
    base_version = store.add_base_image_version(base["id"], png_bytes(), "base.png")
    dataframe, _version = store.load_dataset_dataframe(dataset_version["id"])
    fields = fields_from_dataset_observations(dataframe, dataset["id"], dataset_version["id"], store.list_indicator_definitions(), 900, 600)
    fields[0]["placed"] = True
    fields[0]["x"] = 123
    fields[0]["y"] = 77

    saved = store.save_infographic(
        name="Infográfico demo",
        base_image_id=base["id"],
        base_image_version_id=base_version["id"],
        fields=fields,
        image_size=(900, 600),
    )

    reopened = LocalArchiveStore(tmp_path / "acervo").bootstrap()
    listed = reopened.list_infographics()

    assert saved["status"] == "saved"
    assert len(listed) == 1
    assert listed[0]["field_count"] == 4
    assert reopened.latest_infographic_revision(listed[0]["id"])["config"]["fields"][0]["x"] == 123


def test_new_dataset_version_updates_bound_values_without_moving_layout(tmp_path: Path):
    store = LocalArchiveStore(tmp_path / "acervo").bootstrap()
    dataset = store.register_dataset("Demo produção", public_source="Fonte sintética")
    version_v1 = store.add_dataset_version(dataset["id"], CSV_V1, "demo_v1.csv", period="2021-2026")
    base = store.register_base_image("Base limpa demo")
    base_version = store.add_base_image_version(base["id"], png_bytes(), "base.png")
    dataframe, _version = store.load_dataset_dataframe(version_v1["id"])
    fields = fields_from_dataset_observations(dataframe, dataset["id"], version_v1["id"], store.list_indicator_definitions(), 900, 600)
    fields[0].update({"placed": True, "x": 321, "y": 222, "width": 210, "height": 80})
    saved = store.save_infographic(
        name="Infográfico demo",
        base_image_id=base["id"],
        base_image_version_id=base_version["id"],
        fields=fields,
        image_size=(900, 600),
    )
    infographic_id = saved["infographic"]["id"]

    version_v2 = store.add_dataset_version(dataset["id"], CSV_V2, "demo_v2.csv", period="2021-2026")
    updates = store.check_infographic_updates(infographic_id)
    result = store.apply_dataset_updates(infographic_id)
    latest = store.latest_infographic_revision(infographic_id)
    updated_field = latest["config"]["fields"][0]

    assert version_v2["status"] == "valid"
    assert updates[0]["active_version_id"] == version_v2["id"]
    assert result["status"] == "saved"
    assert updated_field["value"] == "1.100"
    assert updated_field["x"] == 321
    assert updated_field["y"] == 222
    assert updated_field["width"] == 210


def test_duplicate_logical_key_does_not_replace_active_version(tmp_path: Path):
    store = LocalArchiveStore(tmp_path / "acervo").bootstrap()
    dataset = store.register_dataset("Demo produção")
    version_v1 = store.add_dataset_version(dataset["id"], CSV_V1, "demo_v1.csv")
    duplicate = b"""indicador_id,periodo,recorte_id,valor
pesquisadores_ativos,2021-2026,demo_total,1000
pesquisadores_ativos,2021-2026,demo_total,1000
"""

    invalid = store.add_dataset_version(dataset["id"], duplicate, "demo_invalido.csv")
    dataset_after = store.get_dataset(dataset["id"])

    assert version_v1["status"] == "valid"
    assert invalid["status"] == "invalid"
    assert dataset_after["active_version_id"] == version_v1["id"]


def test_identical_dataset_upload_is_idempotent(tmp_path: Path):
    store = LocalArchiveStore(tmp_path / "acervo").bootstrap()
    dataset = store.register_dataset("Demo produção")

    first = store.add_dataset_version(dataset["id"], CSV_V1, "demo_v1.csv", period="2021-2026")
    second = store.add_dataset_version(dataset["id"], CSV_V1, "demo_v1_reenvio.csv", period="2021-2026")

    assert second["id"] == first["id"]
    assert second["idempotent"] is True
    assert len(store.list_datasets()[0]["versions"]) == 1


def test_chart_element_is_exported_inside_free_mode_canvas(tmp_path: Path):
    from src.data_binding import make_chart_element

    store = LocalArchiveStore(tmp_path / "acervo").bootstrap()
    dataset = store.register_dataset("Demo produção")
    version = store.add_dataset_version(dataset["id"], CSV_V1, "demo_v1.csv")
    dataframe, _version = store.load_dataset_dataframe(version["id"])
    chart = make_chart_element(
        dataset["id"],
        version["id"],
        dataframe,
        store.list_indicator_definitions(),
        ["artigos_cientificos", "trabalhos_eventos"],
        title="Produção científica",
        image_width=900,
        image_height=600,
    )
    chart.update({"placed": True, "x": 90, "y": 120, "width": 620, "height": 220})

    report = render_free_infographic(Image.new("RGB", (900, 600), "#ffffff"), [chart], tmp_path / "chart.png")

    assert Path(report.output_png).exists()
    assert report.errors == []


def test_dimension_chart_updates_by_dataset_version(tmp_path: Path):
    from src.data_binding import make_dimension_chart_element

    store = LocalArchiveStore(tmp_path / "acervo").bootstrap()
    dataset = store.register_dataset("Série anual")
    v1 = store.add_dataset_version(dataset["id"], b"ano,valor\n2024,10\n2025,20\n", "anos_v1.csv")
    base = store.register_base_image("Base limpa demo")
    base_version = store.add_base_image_version(base["id"], png_bytes(), "base.png")
    dataframe, _ = store.load_dataset_dataframe(v1["id"])
    chart, errors = make_dimension_chart_element(
        dataset["id"],
        v1["id"],
        dataframe,
        "ano",
        "valor",
        chart_type="bar_vertical",
        title="Série anual",
        image_width=900,
        image_height=600,
    )
    chart.update({"placed": True, "x": 100, "y": 100})
    saved = store.save_infographic(
        name="Infográfico série",
        base_image_id=base["id"],
        base_image_version_id=base_version["id"],
        fields=[chart],
        image_size=(900, 600),
    )

    store.add_dataset_version(dataset["id"], b"ano,valor\n2024,10\n2025,30\n", "anos_v2.csv")
    result = store.apply_dataset_updates(saved["infographic"]["id"])
    latest = store.latest_infographic_revision(saved["infographic"]["id"])
    series = latest["config"]["fields"][0]["chart"]["series"]

    assert errors == []
    assert result["status"] == "saved"
    assert series[1]["display_value"] == "30"
    assert latest["config"]["fields"][0]["x"] == 100

from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import zipfile

from PIL import Image
import pytest

from src.charts import render_chart_image
from src.data_binding import make_chart_element
from src.data_loader import load_csv
from src.free_mode import render_free_preview_bytes
from src.local_workspace import (
    LocalInfographicWorkspace,
    LocalWorkspaceError,
    _atomic_write,
    is_ephemeral_environment,
    safe_id,
    sha256_bytes,
    validate_document,
)


def image_bytes(size=(1122, 1402), color="white") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    return buffer.getvalue()


def csv_bytes(pesquisadores="100", grupos="20") -> bytes:
    return (
        "indicador_id;valor\n"
        f"pesquisadores_ativos;{pesquisadores}\n"
        f"grupos_pesquisa;{grupos}\n"
    ).encode("utf-8")


def prepared_workspace(tmp_path: Path):
    workspace = LocalInfographicWorkspace(tmp_path / "workspace").bootstrap()
    data = csv_bytes()
    fields, warnings = workspace.create_fields(data, "dados.csv", "ciencia", (1122, 1402))
    assert not warnings
    fields[0]["placed"] = True
    document = workspace.save(
        name="Ciência",
        elements=fields,
        canvas=(1122, 1402),
        base_bytes=image_bytes(),
        base_filename="base.png",
        data_bytes=data,
        data_filename="dados.csv",
        metadata={"source": "Fonte institucional"},
    )
    return workspace, document


def test_bootstrap_creates_expected_local_structure(tmp_path):
    workspace = LocalInfographicWorkspace(tmp_path / "workspace").bootstrap()
    assert workspace.infographics_dir.is_dir()
    assert workspace.images_dir.is_dir()
    assert workspace.data_dir.is_dir()
    assert workspace.exports_dir.is_dir()
    assert workspace.catalog_path.is_file()


def test_catalog_has_stable_unique_ids_categories_and_source_keys(tmp_path):
    workspace = LocalInfographicWorkspace(tmp_path).bootstrap()
    catalog = workspace.catalog()
    ids = [item["id"] for item in catalog]
    assert ids and len(ids) == len(set(ids))
    assert all(item["category"] and item["source_key"] for item in catalog)


def test_catalog_search_and_category_are_behavioral(tmp_path):
    workspace = LocalInfographicWorkspace(tmp_path).bootstrap()
    matches = workspace.catalog(query="pesquisadores")
    assert any(item["id"] == "pesquisadores_ativos" for item in matches)
    category = matches[0]["category"]
    assert all(item["category"] == category for item in workspace.catalog(category=category))


def test_bootstrap_adds_new_default_aliases_without_overwriting_local_labels(tmp_path):
    workspace = LocalInfographicWorkspace(tmp_path / "workspace").bootstrap()
    payload = json.loads(workspace.catalog_path.read_text(encoding="utf-8"))
    item = next(field for field in payload["fields"] if field["id"] == "bolsistas_produtividade_total")
    item["label"] = "Rótulo institucional local"
    item["aliases"] = ["bolsa de produtividade"]
    workspace.catalog_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    workspace.bootstrap()

    updated = next(field for field in workspace.catalog() if field["id"] == "bolsistas_produtividade_total")
    assert updated["label"] == "Rótulo institucional local"
    assert "com bolsa produtividade" in updated["aliases"]


def test_demo_csv_maps_all_nine_fields_to_distinct_catalog_concepts(tmp_path):
    workspace = LocalInfographicWorkspace(tmp_path / "workspace").bootstrap()
    csv_bytes = (
        ("Pesqui" + "sadores;11" + "527\n")
        + ("Grupos de" + " pesquisa;21" + "02\n")
        + ("Programas de pós-graduação;18" + "9\n")
        + "Instituições de Ensino e Pesquisa;10\n"
        + ("Produções Científicas Registradas;" + "+" + "90 mil\n")
        + ("Municípios com pesquisadores atuando;" + "+" + "200\n")
        + ("tem doutorado;50" + "%\n")
        + ("com bolsa produtividade;32" + "0\n")
        + ("produções técnicas;2.200" + "+\n")
    ).encode("utf-8")

    fields, warnings = workspace.create_fields(csv_bytes, "dados_info01.csv", "demo", (1600, 2000))

    assert warnings == []
    assert len(fields) == 9
    assert len({field["binding"]["indicator_id"] for field in fields}) == 9
    assert all(field.get("category") not in {None, "", "Outros"} for field in fields)
    municipality = next(field for field in fields if "Municípios" in field["name"])
    assert municipality["binding"]["indicator_id"] == "municipios_pesquisadores_atuando"


def test_safe_id_and_path_traversal_protection(tmp_path):
    workspace = LocalInfographicWorkspace(tmp_path).bootstrap()
    assert safe_id("A ciência baiana") == "a_ciencia_baiana"
    with pytest.raises(LocalWorkspaceError):
        workspace.resolve("../segredo.txt")
    with pytest.raises(LocalWorkspaceError):
        workspace.resolve("C:/segredo.txt")


def test_create_fields_keeps_recurring_field_ids_and_starts_outside_canvas(tmp_path):
    workspace = LocalInfographicWorkspace(tmp_path).bootstrap()
    fields, warnings = workspace.create_fields(csv_bytes(), "dados.csv", "ciencia", (1122, 1402))
    assert not warnings
    assert {(item["binding"]["indicator_id"]) for item in fields} == {"pesquisadores_ativos", "grupos_pesquisa"}
    assert all(item["placed"] is False for item in fields)


def test_save_creates_one_json_and_relative_base_and_data_paths(tmp_path):
    workspace, document = prepared_workspace(tmp_path)
    assert workspace.json_path("ciencia").is_file()
    assert document["base_image"]["path"] == "imagens/infograficos/ciencia/base.png"
    assert document["data_source"]["path"] == "dados/ciencia.csv"
    assert not Path(document["base_image"]["path"]).is_absolute()


def test_saved_json_contains_schema_snapshots_layout_style_and_provenance(tmp_path):
    workspace, document = prepared_workspace(tmp_path)
    payload = json.loads(workspace.json_path("ciencia").read_text(encoding="utf-8"))
    element = payload["elements"][0]
    assert payload["schema_version"] == 1
    assert element["resolved_value"] == "100"
    assert element["layout"]["x"] == element["x"]
    assert element["style"]["font_size"] == element["font_size"]
    assert element["provenance"]["kind"] == "csv"
    assert element["provenance"]["filename"] == "dados.csv"
    assert element["provenance"]["checksum"] == payload["data_source"]["checksum"]
    assert element["provenance"]["raw_value"] == "100"
    assert element["provenance"]["display_value"] == "100"
    assert element["provenance"]["institutional_source"] == "Fonte institucional"


def test_save_preserves_created_at_and_updates_existing_document(tmp_path):
    workspace, document = prepared_workspace(tmp_path)
    updated = workspace.save(
        name=document["name"],
        infographic_id=document["id"],
        elements=document["elements"],
        canvas=(1122, 1402),
        base_bytes=workspace.resolve(document["base_image"]["path"]).read_bytes(),
        base_filename="base.png",
        data_bytes=workspace.resolve(document["data_source"]["path"]).read_bytes(),
        data_filename="dados.csv",
    )
    assert updated["created_at"] == document["created_at"]
    assert updated["updated_at"] >= document["updated_at"]


def test_new_name_collision_is_not_silently_overwritten(tmp_path):
    workspace, document = prepared_workspace(tmp_path)
    with pytest.raises(LocalWorkspaceError, match="Já existe"):
        workspace.save(
            name=document["name"],
            elements=document["elements"],
            canvas=(1122, 1402),
            base_bytes=image_bytes(),
            base_filename="base.png",
        )


def test_atomic_write_preserves_previous_file_when_replace_fails(tmp_path, monkeypatch):
    target = tmp_path / "document.json"
    target.write_bytes(b"anterior")

    def fail_replace(_source, _target):
        raise OSError("falha simulada")

    monkeypatch.setattr("src.local_workspace.os.replace", fail_replace)
    with pytest.raises(OSError):
        _atomic_write(target, b"novo")
    assert target.read_bytes() == b"anterior"
    assert not list(tmp_path.glob("*.tmp"))


def test_round_trip_restores_visual_and_structural_equivalence(tmp_path):
    workspace, document = prepared_workspace(tmp_path)
    loaded = workspace.load(document["id"])
    base = workspace.resolve(loaded["base_image"]["path"])
    before = render_free_preview_bytes(base, document["elements"])
    after = render_free_preview_bytes(base, loaded["elements"])
    assert before == after
    assert loaded["elements"] == document["elements"]


def test_delete_removes_only_the_confirmed_project_files(tmp_path):
    workspace, first = prepared_workspace(tmp_path)
    second = workspace.save(
        name="Tecnologia",
        elements=deepcopy(first["elements"]),
        canvas=(1122, 1402),
        base_bytes=image_bytes(color="blue"),
        base_filename="base.png",
        data_bytes=csv_bytes("200", "40"),
        data_filename="tecnologia.csv",
    )
    png, pdf, _errors = workspace.export(first["id"])
    package = workspace.package(first["id"])
    first_json = workspace.json_path(first["id"])
    first_base = workspace.resolve(first["base_image"]["path"])
    first_data = workspace.resolve(first["data_source"]["path"])
    first_thumbnail = workspace.thumbnails_dir / f"{first['id']}.png"

    removed = workspace.delete(first["id"])

    assert removed
    assert not first_json.exists()
    assert not first_base.exists()
    assert not first_data.exists()
    assert not first_thumbnail.exists()
    assert not png.exists() and not pdf.exists() and not package.exists()
    assert workspace.json_path(second["id"]).exists()
    assert workspace.resolve(second["base_image"]["path"]).exists()
    assert workspace.resolve(second["data_source"]["path"]).exists()
    assert workspace.catalog_path.exists()


def test_discovery_lists_valid_jsons_and_isolates_invalid_json(tmp_path):
    workspace, document = prepared_workspace(tmp_path)
    (workspace.infographics_dir / "quebrado.json").write_text("{", encoding="utf-8")
    projects, issues = workspace.discover()
    assert [item["id"] for item in projects] == [document["id"]]
    assert issues[0]["file"] == "quebrado.json"


def test_update_preview_detects_changed_and_unchanged_values(tmp_path):
    workspace, document = prepared_workspace(tmp_path)
    preview = workspace.update_preview(document["id"], csv_bytes("120", "20"), "dados_novos.csv")
    assert len(preview.changed) == 1
    assert preview.changed[0]["old"] == "100"
    assert preview.changed[0]["new"] == "120"
    assert len(preview.unchanged) == 1
    assert preview.resolved_count == 2
    assert preview.can_apply
    assert preview.file_changed
    assert preview.status_label == "Pronto para atualizar"


def test_update_all_with_new_csv_updates_compatible_projects_and_preserves_design(tmp_path):
    workspace, first = prepared_workspace(tmp_path)
    base_bytes = workspace.resolve(first["base_image"]["path"]).read_bytes()
    original_data = workspace.resolve(first["data_source"]["path"]).read_bytes()
    second = workspace.save(
        name="Tecnologia",
        elements=deepcopy(first["elements"]),
        canvas=(1122, 1402),
        base_bytes=base_bytes,
        base_filename="base.png",
        data_bytes=original_data,
        data_filename="dados.csv",
    )
    before = {
        document["id"]: {
            "base_image": deepcopy(document["base_image"]),
            "layout": [deepcopy(element["layout"]) for element in document["elements"]],
            "style": [deepcopy(element["style"]) for element in document["elements"]],
        }
        for document in (first, second)
    }
    new_csv = (
        "indicador_id;valor;periodo\n"
        "pesquisadores_ativos;150;2026\n"
        "grupos_pesquisa;35;2026\n"
    ).encode("utf-8")

    projects, issues = workspace.discover()
    assert not issues
    previews = [workspace.update_preview(project["id"], new_csv, "dados_2026.csv") for project in projects]
    assert len(previews) == 2
    assert all(preview.can_apply for preview in previews)
    assert all(preview.summary() == {"correspondentes": 2, "alterados": 2, "inalterados": 0, "ausentes": 0, "incompativeis": 0} for preview in previews)

    updated_documents = [workspace.apply_update(preview, new_csv) for preview in previews]
    for document in updated_documents:
        assert [element["value"] for element in document["elements"]] == ["150", "35"]
        assert [element["binding"]["period"] for element in document["elements"]] == ["2026", "2026"]
        assert document["data_source"]["filename"] == "dados_2026.csv"
        assert document["base_image"] == before[document["id"]]["base_image"]
        assert [element["layout"] for element in document["elements"]] == before[document["id"]]["layout"]
        assert [element["style"] for element in document["elements"]] == before[document["id"]]["style"]


def test_new_csv_version_with_same_values_can_update_period_and_provenance(tmp_path):
    workspace, document = prepared_workspace(tmp_path)
    new_csv = (
        "indicador_id;valor;periodo\n"
        "pesquisadores_ativos;100;2026\n"
        "grupos_pesquisa;20;2026\n"
    ).encode("utf-8")

    preview = workspace.update_preview(document["id"], new_csv, "dados_2026.csv")

    assert preview.file_changed
    assert preview.can_apply
    assert not preview.changed
    assert preview.status_label == "Nova versão, mesmos valores"
    updated = workspace.apply_update(preview, new_csv)
    assert updated["data_source"]["filename"] == "dados_2026.csv"
    assert all(element["binding"]["period"] == "2026" for element in updated["elements"])


def test_update_rejects_csv_without_any_corresponding_field(tmp_path):
    workspace, document = prepared_workspace(tmp_path)
    unrelated_csv = "indicador_id;valor\npatentes_total;99\n".encode("utf-8")

    preview = workspace.update_preview(document["id"], unrelated_csv, "outro_assunto.csv")

    assert preview.resolved_count == 0
    assert not preview.is_compatible
    assert not preview.can_apply
    assert preview.status_label == "CSV não corresponde"
    with pytest.raises(LocalWorkspaceError, match="não corresponde"):
        workspace.apply_update(preview, unrelated_csv)


def test_update_is_only_persisted_after_explicit_apply(tmp_path):
    workspace, document = prepared_workspace(tmp_path)
    original = workspace.json_path(document["id"]).read_bytes()
    preview = workspace.update_preview(document["id"], csv_bytes("120", "20"), "dados_novos.csv")
    assert workspace.json_path(document["id"]).read_bytes() == original
    workspace.apply_update(preview, csv_bytes("120", "20"))
    updated = workspace.load(document["id"])
    assert updated["elements"][0]["value"] == "120"
    assert updated["elements"][0]["provenance"]["filename"] == "dados_novos.csv"
    assert updated["elements"][0]["provenance"]["checksum"] == updated["data_source"]["checksum"]
    assert updated["elements"][0]["provenance"]["raw_value"] == "120"


def test_update_preserves_layout_style_base_and_manual_text(tmp_path):
    workspace, document = prepared_workspace(tmp_path)
    original = deepcopy(document)
    manual = deepcopy(document["elements"][0])
    manual.update({"id": "texto_manual", "manual": True, "binding": {}, "value": "Texto fixo", "x": 700, "color": "#112233"})
    document = workspace.save(
        name=document["name"], infographic_id=document["id"], elements=[*document["elements"], manual],
        canvas=(1122, 1402), base_bytes=workspace.resolve(document["base_image"]["path"]).read_bytes(), base_filename="base.png",
        data_bytes=workspace.resolve(document["data_source"]["path"]).read_bytes(), data_filename="dados.csv",
    )
    preview = workspace.update_preview(document["id"], csv_bytes("130", "20"), "v2.csv")
    updated = workspace.apply_update(preview, csv_bytes("130", "20"))
    assert updated["base_image"] == document["base_image"]
    assert updated["elements"][0]["x"] == original["elements"][0]["x"]
    assert updated["elements"][0]["color"] == original["elements"][0]["color"]
    fixed = next(item for item in updated["elements"] if item["id"] == "texto_manual")
    assert fixed["value"] == "Texto fixo" and fixed["x"] == 700


def test_missing_field_preserves_previous_value_and_never_becomes_zero(tmp_path):
    workspace, document = prepared_workspace(tmp_path)
    missing_csv = "indicador_id;valor\npesquisadores_ativos;150\n".encode()
    preview = workspace.update_preview(document["id"], missing_csv, "incompleto.csv")
    assert len(preview.missing) == 1
    missing_element = next(item for item in preview.elements if item["binding"]["indicator_id"] == "grupos_pesquisa")
    assert missing_element["value"] == "20"
    assert missing_element["binding"]["status"] == "missing_value"


def test_missing_field_blocks_export_after_confirmed_update(tmp_path):
    workspace, document = prepared_workspace(tmp_path)
    missing_csv = "indicador_id;valor\npesquisadores_ativos;150\n".encode()
    workspace.apply_update(workspace.update_preview(document["id"], missing_csv, "incompleto.csv"), missing_csv)
    with pytest.raises(LocalWorkspaceError, match="Corrija os campos"):
        workspace.export(document["id"])


@pytest.mark.parametrize("chart_type", ["bar_horizontal", "bar_vertical"])
def test_bar_and_column_charts_serialize_reopen_and_render(tmp_path, chart_type):
    workspace, document = prepared_workspace(tmp_path)
    data = workspace.resolve(document["data_source"]["path"]).read_bytes()
    dataframe, _ = load_csv(BytesIO(data), separator=None, encoding=None, has_header=None)
    chart = make_chart_element(document["id"], sha256_bytes(data), dataframe, workspace.catalog(), ["pesquisadores_ativos", "grupos_pesquisa"], chart_type=chart_type, title="Comparativo", order=27)
    assert chart["order"] == 27
    assert chart["category"] == "Gráficos"
    chart["placed"] = True
    saved = workspace.save(
        name=document["name"], infographic_id=document["id"], elements=[*document["elements"], chart], canvas=(1122, 1402),
        base_bytes=workspace.resolve(document["base_image"]["path"]).read_bytes(), base_filename="base.png", data_bytes=data, data_filename="dados.csv",
    )
    reopened = workspace.load(saved["id"])
    reopened_chart = next(item for item in reopened["elements"] if item["type"] == "chart")
    image, records, errors = render_chart_image(reopened_chart["chart"], reopened_chart["width"], reopened_chart["height"])
    assert image.size == (reopened_chart["width"], reopened_chart["height"])
    assert records and not errors


def test_indicator_chart_reports_unresolved_series_before_save(tmp_path):
    workspace, document = prepared_workspace(tmp_path)
    data = workspace.resolve(document["data_source"]["path"]).read_bytes()
    dataframe, _ = load_csv(BytesIO(data), separator=None, encoding=None, has_header=None)

    chart = make_chart_element(
        document["id"],
        sha256_bytes(data),
        dataframe,
        workspace.catalog(),
        ["pesquisadores_ativos", "conceito_inexistente"],
    )

    assert chart["binding"]["status"] == "invalid_series"
    assert "conceito_inexistente" in chart["binding"]["error"]


def test_chart_items_update_by_binding_and_keep_true_shared_scale(tmp_path):
    workspace, document = prepared_workspace(tmp_path)
    data = workspace.resolve(document["data_source"]["path"]).read_bytes()
    dataframe, _ = load_csv(BytesIO(data), separator=None, encoding=None, has_header=None)
    chart = make_chart_element(document["id"], sha256_bytes(data), dataframe, workspace.catalog(), ["pesquisadores_ativos", "grupos_pesquisa"], chart_type="bar_horizontal")
    chart["placed"] = True
    document = workspace.save(
        name=document["name"], infographic_id=document["id"], elements=[chart], canvas=(1122, 1402),
        base_bytes=workspace.resolve(document["base_image"]["path"]).read_bytes(), base_filename="base.png", data_bytes=data, data_filename="dados.csv",
    )
    preview = workspace.update_preview(document["id"], csv_bytes("200", "50"), "v2.csv")
    updated = workspace.apply_update(preview, csv_bytes("200", "50"))
    series = updated["elements"][0]["chart"]["series"]
    assert [str(item["display_value"]) for item in series] == ["200", "50"]
    _, records, _ = render_chart_image(updated["elements"][0]["chart"], 560, 220)
    bars = [record for record in records if str(record.get("id", "")).startswith("barra-")]
    assert bars[0]["w"] > bars[1]["w"] > 0


def test_long_chart_labels_do_not_produce_out_of_bounds_errors(tmp_path):
    workspace = LocalInfographicWorkspace(tmp_path).bootstrap()
    chart = {
        "type": "bar_horizontal", "title": "Produção", "show_labels": True, "show_values": True,
        "series": [
            {"key": "a", "label": "Rótulo institucional bastante longo para teste", "raw_value": "100", "display_value": "100", "order": 1},
            {"key": "b", "label": "Outro rótulo", "raw_value": "50", "display_value": "50", "order": 2},
        ],
    }
    image, records, errors = render_chart_image(chart, 700, 260)
    assert image.size == (700, 260)
    assert records and not errors


def test_export_png_pdf_and_preview_use_same_canvas_dimensions(tmp_path):
    workspace, document = prepared_workspace(tmp_path)
    png, pdf, errors = workspace.export(document["id"])
    assert png.is_file() and pdf.is_file()
    with Image.open(png) as image:
        assert image.size == (1122, 1402)
    preview = Image.open(BytesIO(render_free_preview_bytes(workspace.resolve(document["base_image"]["path"]), document["elements"])))
    assert preview.size == (1122, 1402)
    assert not errors


def test_project_package_contains_json_base_data_and_catalog(tmp_path):
    workspace, document = prepared_workspace(tmp_path)
    package = workspace.package(document["id"])
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
    assert f"infograficos/{document['id']}.json" in names
    assert document["base_image"]["path"] in names
    assert document["data_source"]["path"] in names
    assert "dados/catalogo_campos.json" in names


def test_ephemeral_detection_has_explicit_safe_override(tmp_path, monkeypatch):
    monkeypatch.setenv("INFOGRAPHICS_STORAGE_MODE", "ephemeral")
    assert is_ephemeral_environment(tmp_path)
    monkeypatch.setenv("INFOGRAPHICS_STORAGE_MODE", "persistent")
    assert not is_ephemeral_environment(tmp_path)


def test_validate_document_rejects_duplicate_ids_and_absolute_paths(tmp_path):
    workspace, document = prepared_workspace(tmp_path)
    broken = deepcopy(document)
    broken["elements"].append(deepcopy(broken["elements"][0]))
    broken["base_image"]["path"] = "C:/fora.png"
    errors = validate_document(broken, workspace.root)
    assert any("duplicado" in error for error in errors)
    assert any("Caminho" in error for error in errors)

from pathlib import Path

import yaml

from src.configuration import (
    aggregate_indicators_from_dataframe,
    config_compatibility,
    duplicate_indicator,
    empty_config,
    export_names,
    new_indicator,
    normalize_config,
    remove_indicator,
    reorder_indicators,
    reset_if_schema_changed,
)
from src.data_loader import load_csv


ROOT = Path(__file__).resolve().parents[1]


def test_initial_config_has_no_csv_or_indicators():
    config = empty_config()

    assert config["metadata"]["source"] == ""
    assert config["indicators"] == []
    assert config["template"]["id"] == "institucional_claro_v1"
    assert config["template"]["version"] == "1.0"


def test_demo_files_are_optional_and_loadable():
    demo_csv = ROOT / "examples" / "dados_exemplo.csv"
    demo_yaml = ROOT / "examples" / "config_exemplo.yaml"

    df, profile = load_csv(demo_csv, separator=";", encoding="utf-8-sig", has_header=False)
    config = normalize_config(yaml.safe_load(demo_yaml.read_text(encoding="utf-8")), profile.columns, demo_csv.name)

    assert demo_csv.exists()
    assert demo_yaml.exists()
    assert profile.data_shape == "agregado"
    assert len(config["indicators"]) == len(df)


def test_aggregate_csv_creates_dynamic_indicators_from_rows():
    df, profile = load_csv(ROOT / "tests" / "fixtures" / "dados_agregado_variado.csv")

    indicators = aggregate_indicators_from_dataframe(df)

    assert profile.data_shape == "agregado"
    assert [item["label"] for item in indicators] == df.iloc[:, 0].tolist()
    assert all(item["operation"] == "direct_value" for item in indicators)
    assert all(item["section"] == "Indicadores" for item in indicators)


def test_dynamic_add_duplicate_remove_and_reorder():
    first = new_indicator(["nome", "valor"], order=2)
    first["label"] = "Segundo"
    second = new_indicator(["nome", "valor"], [first["id"]], order=1)
    second["label"] = "Primeiro"

    indicators = duplicate_indicator([first, second], first["id"])
    assert len(indicators) == 3
    assert indicators[1]["id"] != first["id"]

    indicators = remove_indicator(indicators, first["id"])
    assert all(item["id"] != first["id"] for item in indicators)

    reordered = reorder_indicators(indicators)
    assert [item["order"] for item in reordered] == [1, 2]


def test_csv_switch_resets_indicators_when_schema_changes():
    config = empty_config(["nome", "valor"], "a.csv")
    config["indicators"] = [new_indicator(["nome", "valor"])]

    changed = reset_if_schema_changed(config, ["unidade", "total"], "b.csv")

    assert changed["metadata"]["source"] == ""
    assert changed["indicators"] == []


def test_yaml_compatibility_reports_missing_columns():
    config = empty_config(["nome", "valor"], "a.csv")
    indicator = new_indicator(["nome", "valor"])
    indicator["column"] = "coluna_ausente"
    config["indicators"] = [indicator]

    compatibility = config_compatibility(config, ["nome", "valor"])

    assert not compatibility.compatible
    assert compatibility.missing_columns == ["coluna_ausente"]


def test_yaml_roundtrip_preserves_template_selection():
    config = empty_config(["nome", "valor"], "a.csv")
    config["template"] = {"id": "institucional_claro_v1", "version": "1.0"}

    loaded = normalize_config(yaml.safe_load(yaml.safe_dump(config, allow_unicode=True)), ["nome", "valor"], "a.csv")

    assert loaded["template"] == {"id": "institucional_claro_v1", "version": "1.0"}


def test_export_names_are_derived_from_csv_and_date():
    names = export_names("Planilha Final.csv")

    assert names["png"].startswith("infografico_planilha_final_")
    assert "real" not in " ".join(names.values())

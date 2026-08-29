from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from src.column_profiler import classify_column, profile_columns
from src.data_loader import load_csv
from src.inference_engine import automatic_audit_rows_from_config, infer_config
from src.semantic_rules import (
    confidence_level,
    load_rulebook,
    match_rule,
    normalize_text,
    save_custom_rule,
    semantic_tokens,
)


ROOT = Path(__file__).resolve().parents[1]


def test_normalization_handles_accents_plural_abbreviations_and_stopwords():
    normalized = normalize_text("Pós-graduação, MUN. e docentes")
    assert "pos graduacao" in normalized
    assert "municipio" in normalized
    assert "docentes" in normalized
    assert "docente" in semantic_tokens("Docentes")
    assert "municipio" in semantic_tokens("municípios")
    assert "indicador" not in semantic_tokens("Indicadores de inovação")


def test_rule_matching_uses_synonyms_priority_and_negative_terms():
    rulebook = load_rulebook()

    people = match_rule("docentes vinculados", rulebook)
    assert people.icon == "people"
    assert people.section == "Indicadores principais"
    assert people.confidence >= 60

    location = match_rule("municípios com " + "pesquisa" + "dores atuando", rulebook)
    assert location.icon == "pin"
    assert location.section == "Alcance"


def test_fuzzy_matching_and_confidence_levels():
    rule = match_rule("laboratorios cadastrados")

    assert rule.icon == "flask"
    assert confidence_level(90) == "alta"
    assert confidence_level(70) == "média"
    assert confidence_level(40) == "baixa"


def test_aggregate_csv_inference_preserves_direct_values_and_sections():
    df, profile = load_csv(ROOT / "dados_info01.csv", separator=";", encoding=None, has_header=False)

    result = infer_config(df, profile, "dados_info01.csv")

    labels = [decision.label for decision in result.decisions]
    assert profile.data_shape == "agregado"
    assert len(result.config["indicators"]) == 9
    assert {indicator["operation"] for indicator in result.config["indicators"]} == {"direct_value"}
    assert result.decisions[0].value_or_calculation == "11" + "527"
    assert labels[0] == "Pesqui" + "sadores"
    assert [section["name"] for section in result.config["sections"]] == [
        "Indicadores principais",
        "Alcance",
        "Indicadores complementares",
    ]
    audit_rows = automatic_audit_rows_from_config(result.config)
    assert len(audit_rows) == 9
    assert audit_rows[0]["regra utilizada"]


def test_detailed_csv_profiles_columns_and_avoids_unsafe_operations():
    df = pd.DataFrame({
        "nome": ["Ana", "Bia", "Caio"],
        "matricula": ["100", "101", "102"],
        "municipio": ["A", "B", "A"],
        "ativo": ["sim", "não", "sim"],
        "ano": ["2024", "2025", "2026"],
        "valor_aprovado": ["10", "20", "30"],
        "observacao": ["texto longo", "outro texto", "livre"],
    })
    profiles = {profile.name: profile for profile in profile_columns(df)}

    assert profiles["nome"].kind == "possível informação pessoal"
    assert profiles["matricula"].kind == "possível informação pessoal"
    assert profiles["municipio"].kind == "localização"
    assert profiles["ativo"].kind == "booleano"
    assert profiles["ano"].kind == "data"

    _, csv_profile = load_csv(ROOT / "tests" / "fixtures" / "dados_tabular_sintetico.csv")
    detailed = infer_config(pd.read_csv(ROOT / "tests" / "fixtures" / "dados_tabular_sintetico.csv", dtype=str), csv_profile, "detalhado.csv")
    assert all(indicator["operation"] != "sum" or "valor" in indicator["column"].lower() for indicator in detailed.config["indicators"])


def test_identifier_numeric_and_dates_are_not_summed():
    df = pd.DataFrame({
        "codigo": ["1001", "1002", "1003"],
        "ano": ["2024", "2025", "2026"],
    })

    assert classify_column("codigo", df["codigo"]).kind == "identificador"
    assert classify_column("ano", df["ano"]).kind == "data"


def test_custom_rules_take_precedence(tmp_path: Path):
    default_path = ROOT / "config" / "semantic_rules.yaml"
    custom_path = tmp_path / "custom.yaml"
    custom_path.write_text("version: 1\nrules: {}\n", encoding="utf-8")
    save_custom_rule(
        "custom_lab",
        {
            "enabled": True,
            "terms": ["laboratorio"],
            "section": "Alcance",
            "icon": "microscope",
            "color": "#009739",
            "priority": 300,
            "preferred_label": "Laboratórios ajustados",
            "compatible_operations": ["direct_value"],
        },
        custom_path,
    )

    rule = match_rule("laboratório central", load_rulebook(default_path, custom_path))

    assert rule.rule_id == "custom_lab"
    assert rule.icon == "microscope"
    assert rule.section == "Alcance"


def test_engine_works_with_local_rule_files_only(tmp_path: Path):
    rules_path = tmp_path / "rules.yaml"
    custom_path = tmp_path / "custom.yaml"
    rules_path.write_text((ROOT / "config" / "semantic_rules.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    custom_path.write_text(yaml.safe_dump({"version": 1, "rules": {}}), encoding="utf-8")
    df, profile = load_csv(ROOT / "dados_info01.csv", separator=";", encoding=None, has_header=False)

    result = infer_config(df, profile, "local.csv", rules_path, custom_path)

    assert result.confidence >= 85
    assert not result.warnings

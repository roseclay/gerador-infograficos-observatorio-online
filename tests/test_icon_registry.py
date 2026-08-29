from __future__ import annotations

from copy import deepcopy

import yaml

from src.configuration import empty_config, normalize_config, sections_from_indicators
from src.icon_registry import (
    DEFAULT_COLOR,
    ICON_CATEGORIES,
    ICON_REGISTRY,
    apply_appearance_to_all,
    apply_appearance_to_indicator,
    apply_appearance_to_section,
    apply_color_to_all,
    apply_color_to_section,
    icon_preview_image,
    normalize_hex_color,
    normalize_icon_name,
    validate_hex_color,
)


def test_icon_registry_contains_requested_categories_and_renders_every_icon():
    expected_categories = {
        "pessoas",
        "pesquisa",
        "educação",
        "instituições",
        "localização",
        "documentos",
        "tecnologia",
        "inovação",
        "propriedade intelectual",
        "natureza",
    }

    assert expected_categories.issubset(set(ICON_CATEGORIES))
    for icon in ICON_REGISTRY:
        preview = icon_preview_image(icon.name, "#B28A8A", size=120).convert("RGBA")
        assert preview.getbbox(), icon.name


def test_aliases_and_invalid_icons_normalize_to_supported_icons():
    assert normalize_icon_name("users") == "people"
    assert normalize_icon_name("ribbon") == "medal"
    assert normalize_icon_name("award_user") == "award"
    assert normalize_icon_name("inexistente") == "circle"


def test_hex_color_validation_and_normalization():
    assert validate_hex_color("#B28A8A")
    assert validate_hex_color("abc")
    assert normalize_hex_color("abc") == "#AABBCC"
    assert normalize_hex_color("#b28a8a") == "#B28A8A"
    assert normalize_hex_color("nao-e-cor") == DEFAULT_COLOR


def test_appearance_application_scopes_do_not_mutate_original():
    indicators = [
        {"id": "a", "section": "Um", "icon": "circle", "color": "#0057B8"},
        {"id": "b", "section": "Um", "icon": "circle", "color": "#0057B8"},
        {"id": "c", "section": "Dois", "icon": "circle", "color": "#0057B8"},
    ]
    original = deepcopy(indicators)

    selected = apply_appearance_to_indicator(indicators, "a", icon="flask", color="#B28A8A")
    assert selected[0]["icon"] == "flask"
    assert selected[0]["color"] == "#B28A8A"
    assert selected[1:] == indicators[1:]

    section_colors = apply_color_to_section(indicators, "Um", "#EF3340")
    assert [item["color"] for item in section_colors] == ["#EF3340", "#EF3340", "#0057B8"]

    all_colors = apply_color_to_all(indicators, "#009739")
    assert {item["color"] for item in all_colors} == {"#009739"}

    section_appearance = apply_appearance_to_section(indicators, "Um", icon="network", color="#FFD100")
    assert [item["icon"] for item in section_appearance] == ["network", "network", "circle"]
    assert [item["color"] for item in section_appearance] == ["#FFD100", "#FFD100", "#0057B8"]

    all_appearance = apply_appearance_to_all(indicators, icon="leaf", color="#2F855A")
    assert {item["icon"] for item in all_appearance} == {"leaf"}
    assert {item["color"] for item in all_appearance} == {"#2F855A"}
    assert indicators == original


def test_yaml_roundtrip_preserves_icon_and_color_without_preview_state():
    config = empty_config(["nome", "valor"], "entrada.csv")
    indicator = {
        "enabled": True,
        "id": "indicador_teste",
        "label": "Indicador de teste",
        "section": "Indicadores",
        "column": "valor",
        "operation": "direct_value",
        "filter_column": "nome",
        "filter_operator": "equals",
        "filter_value": "total",
        "decimals": 0,
        "order": 1,
        "icon": "flask",
        "color": "#B28A8A",
    }
    config["indicators"] = [indicator]
    config["sections"] = sections_from_indicators(config["indicators"], [])

    dumped = yaml.safe_dump(config, allow_unicode=True, sort_keys=False)
    loaded = normalize_config(yaml.safe_load(dumped), ["nome", "valor"], "entrada.csv")

    assert loaded["indicators"][0]["icon"] == "flask"
    assert loaded["indicators"][0]["color"] == "#B28A8A"
    assert "preview_ratio" not in dumped
    assert "preview_minimized" not in dumped

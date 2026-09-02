from src.catalog import default_indicator_definitions, validate_indicator_definition


def test_catalog_has_22_reusable_definitions_without_values():
    definitions = default_indicator_definitions()

    assert len(definitions) == 22
    assert {item["id"] for item in definitions} >= {
        "pesquisadores_ativos",
        "producao_tecnica_total",
        "bolsistas_pq",
        "bolsistas_dt",
    }
    assert all("value" not in item and "valor" not in item for item in definitions)
    assert all(validate_indicator_definition(item) == [] for item in definitions)


def test_catalog_preserves_pending_semantic_status():
    definitions = default_indicator_definitions()

    assert all(item["semantic_status"] == "pendente" for item in definitions)

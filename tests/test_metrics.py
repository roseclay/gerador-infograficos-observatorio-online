from pathlib import Path

import pandas as pd

from src.metrics import calculate_metric, calculate_metrics, write_audit


def test_sum_count_distinct_mean_and_percentage():
    df = pd.DataFrame({
        "grupo": ["A", "A", "B", "B", ""],
        "valor": ["1", "2", "3", "", "4"],
        "flag": ["sim", "", "sim", "", "sim"],
    })
    metadata = {"period": "2026", "source": "teste.csv"}

    total = calculate_metric(df, {"label": "Total", "column": "valor", "operation": "sum"}, metadata)
    count = calculate_metric(df, {"label": "Contagem", "column": "valor", "operation": "count"}, metadata)
    distinct = calculate_metric(df, {"label": "Distintos", "column": "grupo", "operation": "distinct_count"}, metadata)
    mean = calculate_metric(df, {"label": "Media", "column": "valor", "operation": "mean", "decimals": 1}, metadata)
    percentage = calculate_metric(df, {"label": "Percentual", "column": "flag", "operation": "percentage", "decimals": 0}, metadata)

    assert total.display_value == "10"
    assert count.display_value == "4"
    assert distinct.display_value == "2"
    assert mean.display_value == "2,5"
    assert percentage.display_value == "60%"


def test_percentage_with_match_value():
    df = pd.DataFrame({"situacao": ["sim", "nao", "sim", "sim"]})

    result = calculate_metric(df, {
        "label": "Participação",
        "column": "situacao",
        "operation": "percentage",
        "match_value": "sim",
        "decimals": 0,
    })

    assert result.display_value == "75%"
    assert result.valid


def test_direct_value_with_filter_and_missing_values():
    df = pd.DataFrame({"indicador": ["A", "B"], "valor": ["", "4.400+"]})

    result = calculate_metric(df, {
        "label": "B",
        "column": "valor",
        "operation": "direct_value",
        "filter_column": "indicador",
        "filter_value": "B",
    })

    assert result.valid
    assert result.display_value == "4.400+"
    assert "indicador igual a B" in result.filter_applied


def test_audit_generation(tmp_path: Path):
    df = pd.DataFrame({"indicador": ["A"], "valor": ["10"]})
    metrics, errors = calculate_metrics(df, [{
        "label": "A",
        "column": "valor",
        "operation": "direct_value",
        "filter_column": "indicador",
        "filter_value": "A",
    }], {"period": "2026", "source": "teste.csv"})
    assert not errors

    audit = write_audit(metrics, tmp_path / "auditoria.csv", csv_name="entrada.csv")

    assert audit.iloc[0]["indicador"] == "A"
    assert audit.iloc[0]["valor exibido"] == "10"
    assert audit.iloc[0]["arquivo CSV"] == "entrada.csv"
    assert (tmp_path / "auditoria.csv").exists()

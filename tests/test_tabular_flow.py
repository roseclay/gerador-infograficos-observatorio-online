from src.data_loader import load_csv
from src.metrics import calculate_metrics


def test_tabular_csv_requires_explicit_configured_operations():
    df, profile = load_csv("tests/fixtures/dados_tabular_sintetico.csv")
    configs = [
        {"label": "Linhas", "operation": "count", "column": "", "order": 1},
        {"label": "Total", "operation": "sum", "column": "valor", "order": 2},
        {"label": "Municípios", "operation": "distinct_count", "column": "municipio", "order": 3},
        {"label": "Ativos", "operation": "percentage", "column": "perfil", "match_value": "ativo", "decimals": 0, "order": 4},
    ]

    metrics, errors = calculate_metrics(df, configs, {"source": "dados_tabular_sintetico.csv"})

    assert profile.data_shape == "detalhado"
    assert not errors
    assert [metric.display_value for metric in metrics] == ["4", "100", "3", "75%"]

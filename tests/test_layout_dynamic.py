from src.layout import build_layout
from src.metrics import MetricResult
from src.validation import validate_no_overlaps


def metric(index: int) -> MetricResult:
    return MetricResult(
        metric_id=f"m{index}",
        label=f"Indicador {index}",
        section="Indicadores",
        column="valor",
        operation="direct_value",
        filter_applied="sem filtro",
        raw_value=str(index),
        display_value=str(index),
        calculation="direto",
        period="",
        source="teste.csv",
        order=index,
    )


def test_layout_supports_variable_indicator_counts_without_overlap():
    for count in [1, 2, 4, 6, 9]:
        layout = build_layout([metric(index) for index in range(1, count + 1)])

        assert len(layout.card_rects) == count
        assert not validate_no_overlaps(layout.card_rects)

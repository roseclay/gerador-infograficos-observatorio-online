from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import pandas as pd

from .formatting import format_display_value, format_brazilian_number, is_missing, normalize_public_text, parse_brazilian_number


OPERATION_LABELS = {
    "direct_value": "valor direto",
    "sum": "soma",
    "count": "contagem",
    "distinct_count": "contagem distinta",
    "mean": "media",
    "percentage": "percentual",
    "latest": "ultimo valor",
}

OPERATION_KEYS = {label: key for key, label in OPERATION_LABELS.items()}


@dataclass
class MetricResult:
    metric_id: str
    label: str
    section: str
    column: str
    operation: str
    filter_applied: str
    raw_value: Any
    display_value: str
    calculation: str
    period: str
    source: str
    prefix: str = ""
    suffix: str = ""
    decimals: int = 0
    icon: str = "circle"
    color: str = "#0057B8"
    order: int = 0
    section_order: int = 1
    show_section_title: bool = True
    valid: bool = True
    error: str = ""

    def audit_row(
        self,
        template: dict[str, Any] | None = None,
        slot_info: dict[str, Any] | None = None,
        mode: str = "manual",
        fallback_used: bool = False,
        csv_name: str = "",
    ) -> dict[str, Any]:
        template = template or {}
        slot_info = slot_info or {}
        return {
            "id": self.metric_id,
            "indicador": self.label,
            "coluna utilizada": self.column,
            "filtro aplicado": self.filter_applied,
            "operacao realizada": OPERATION_LABELS.get(self.operation, self.operation),
            "valor bruto": self.raw_value,
            "valor exibido": self.display_value,
            "periodo": self.period,
            "fonte": self.source,
            "arquivo CSV": csv_name,
            "configuracao": mode,
            "template": template.get("id", ""),
            "versao do template": template.get("version", ""),
            "pagina": slot_info.get("pagina", ""),
            "secao": slot_info.get("secao", self.section),
            "slot": slot_info.get("slot", ""),
            "icone": slot_info.get("icone", self.icon),
            "uso de fallback": bool(fallback_used or slot_info.get("icone_fallback", False)),
        }


def operation_key(value: str) -> str:
    text = normalize_public_text(value).lower()
    return OPERATION_KEYS.get(text, text)


def _non_missing(series: pd.Series) -> pd.Series:
    return series[~series.map(is_missing)]


def _numeric_values(series: pd.Series) -> list[Decimal]:
    values: list[Decimal] = []
    invalid: list[str] = []
    for value in _non_missing(series):
        try:
            values.append(parse_brazilian_number(value))
        except (InvalidOperation, ValueError):
            invalid.append(str(value))
    if invalid:
        raise InvalidOperation(f"valores invalidos para calculo numerico: {', '.join(invalid[:5])}")
    return values


def apply_filter(dataframe: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, str]:
    column = normalize_public_text(config.get("filter_column"))
    value = normalize_public_text(config.get("filter_value"))
    operator = normalize_public_text(config.get("filter_operator") or "equals").lower()
    if not column or not value:
        return dataframe, "sem filtro"
    if column not in dataframe.columns:
        return dataframe.iloc[0:0], f"filtro invalido: coluna '{column}' nao encontrada"

    source = dataframe[column].map(lambda item: "" if item is None else str(item).strip())
    value_folded = value.casefold()
    if operator in {"equals", "igual", "igual a"}:
        mask = source.map(lambda item: item.casefold() == value_folded)
        description = f"{column} igual a {value}"
    elif operator in {"contains", "contem", "contém"}:
        mask = source.map(lambda item: value_folded in item.casefold())
        description = f"{column} contem {value}"
    elif operator in {"not_empty", "nao vazio", "não vazio"}:
        mask = ~source.map(is_missing)
        description = f"{column} nao vazio"
    else:
        mask = source.map(lambda item: item.casefold() == value_folded)
        description = f"{column} igual a {value}"
    return dataframe[mask].copy(), description


def _decimal_sum(values: list[Decimal]) -> Decimal:
    total = Decimal("0")
    for value in values:
        total += value
    return total


def _format_calculated(value: Decimal, decimals: int, prefix: str, suffix: str) -> str:
    return f"{prefix}{format_brazilian_number(value, decimals)}{suffix}"


def calculate_metric(dataframe: pd.DataFrame, config: dict[str, Any], metadata: dict[str, Any] | None = None) -> MetricResult:
    metadata = metadata or {}
    configured_label = normalize_public_text(config.get("label"))
    label = configured_label or normalize_public_text(config.get("id") or "Indicador sem rotulo")
    column = normalize_public_text(config.get("column"))
    configured_operation = normalize_public_text(config.get("operation"))
    operation = operation_key(configured_operation) if configured_operation else ""
    numerator_column = normalize_public_text(config.get("numerator_column"))
    denominator_column = normalize_public_text(config.get("denominator_column"))
    decimals = int(config.get("decimals") or 0)
    prefix = normalize_public_text(config.get("prefix"))
    suffix = normalize_public_text(config.get("suffix"))
    filtered, filter_description = apply_filter(dataframe, config)

    base = MetricResult(
        metric_id=normalize_public_text(config.get("id") or label),
        label=label,
        section=normalize_public_text(config.get("section") or "Indicadores"),
        column=column,
        operation=operation,
        filter_applied=filter_description,
        raw_value="",
        display_value="",
        calculation="",
        period=normalize_public_text(metadata.get("period")),
        source=normalize_public_text(metadata.get("source")),
        prefix=prefix,
        suffix=suffix,
        decimals=decimals,
        icon=normalize_public_text(config.get("icon") or "circle"),
        color=normalize_public_text(config.get("color") or "#0057B8"),
        order=int(config.get("order") or 0),
        section_order=int(config.get("section_order") or 1),
        show_section_title=bool(config.get("show_section_title", True)),
    )

    if not configured_label:
        base.valid = False
        base.error = "rotulo publico ausente"
        return base
    if not configured_operation:
        base.valid = False
        base.error = "operacao ausente"
        return base
    if operation not in OPERATION_LABELS:
        base.valid = False
        base.error = f"operacao '{operation}' nao suportada"
        return base
    requires_column = operation not in {"count"} and not (operation == "percentage" and numerator_column and denominator_column)
    if requires_column and column not in dataframe.columns:
        base.valid = False
        base.error = f"coluna '{column}' nao encontrada"
        return base
    if filtered.empty:
        base.valid = False
        base.error = "nenhuma linha encontrada para o filtro"
        return base

    try:
        if operation == "direct_value":
            values = _non_missing(filtered[column]).tolist()
            if not values:
                raise ValueError("valor ausente")
            raw = values[0]
            base.raw_value = raw
            base.display_value = format_display_value(raw, decimals, prefix, suffix, preserve_qualified_text=True)
            base.calculation = f"primeiro valor nao vazio de '{column}' apos filtro"

        elif operation == "sum":
            values = _numeric_values(filtered[column])
            raw = _decimal_sum(values)
            base.raw_value = raw
            base.display_value = _format_calculated(raw, decimals, prefix, suffix)
            base.calculation = f"soma de {len(values)} valor(es) numericos em '{column}'"

        elif operation == "count":
            if column and column in dataframe.columns:
                count = int(_non_missing(filtered[column]).shape[0])
                base.calculation = f"contagem de valores nao vazios em '{column}'"
            else:
                count = int(filtered.shape[0])
                base.calculation = "contagem de linhas apos filtro"
            base.raw_value = count
            base.display_value = _format_calculated(Decimal(count), decimals, prefix, suffix)

        elif operation == "distinct_count":
            values = _non_missing(filtered[column]).map(lambda value: str(value).strip())
            count = int(values.nunique())
            base.raw_value = count
            base.display_value = _format_calculated(Decimal(count), decimals, prefix, suffix)
            base.calculation = f"contagem distinta de valores nao vazios em '{column}'"

        elif operation == "mean":
            values = _numeric_values(filtered[column])
            if not values:
                raise ZeroDivisionError("sem valores numericos")
            raw = (_decimal_sum(values) / Decimal(len(values))).quantize(Decimal("0.0000000001"), rounding=ROUND_HALF_UP)
            base.raw_value = raw
            base.display_value = _format_calculated(raw, decimals, prefix, suffix)
            base.calculation = f"media de {len(values)} valor(es) numericos em '{column}'"

        elif operation == "percentage":
            match_value = normalize_public_text(config.get("match_value"))
            if match_value:
                denominator = Decimal(int(filtered.shape[0]))
                if denominator == 0:
                    raise ZeroDivisionError("divisao por zero no percentual")
                numerator = Decimal(int(filtered[column].map(lambda value: str(value).strip().casefold() == match_value.casefold()).sum()))
                raw = (numerator / denominator) * Decimal("100")
                base.calculation = f"linhas em que '{column}' e igual a '{match_value}' divididas por linhas filtradas"
            elif numerator_column and denominator_column:
                if numerator_column not in filtered.columns or denominator_column not in filtered.columns:
                    raise ValueError("colunas de numerador/denominador nao encontradas")
                numerator = _decimal_sum(_numeric_values(filtered[numerator_column]))
                denominator = _decimal_sum(_numeric_values(filtered[denominator_column]))
                if denominator == 0:
                    raise ZeroDivisionError("divisao por zero no percentual")
                raw = (numerator / denominator) * Decimal("100")
                base.calculation = f"soma de '{numerator_column}' dividida pela soma de '{denominator_column}'"
            else:
                denominator = Decimal(int(filtered.shape[0]))
                if denominator == 0:
                    raise ZeroDivisionError("divisao por zero no percentual")
                numerator = Decimal(int(_non_missing(filtered[column]).shape[0]))
                raw = (numerator / denominator) * Decimal("100")
                base.calculation = f"valores nao vazios em '{column}' divididos por linhas filtradas"
            base.raw_value = raw
            display_suffix = suffix or "%"
            base.display_value = _format_calculated(raw, decimals, prefix, display_suffix)

        elif operation == "latest":
            values = _non_missing(filtered[column]).tolist()
            if not values:
                raise ValueError("valor ausente")
            raw = values[-1]
            base.raw_value = raw
            base.display_value = format_display_value(raw, decimals, prefix, suffix, preserve_qualified_text=True)
            base.calculation = f"ultimo valor nao vazio de '{column}' apos filtro"

    except Exception as exc:
        base.valid = False
        base.error = str(exc)
        base.display_value = ""
        return base

    if not base.display_value:
        base.valid = False
        base.error = "valor exibido vazio"
    return base


def calculate_metrics(dataframe: pd.DataFrame, configs: list[dict[str, Any]], metadata: dict[str, Any] | None = None) -> tuple[list[MetricResult], list[MetricResult]]:
    results = []
    errors = []
    for config in configs:
        if config.get("enabled", True) is False:
            continue
        result = calculate_metric(dataframe, config, metadata)
        if result.valid:
            results.append(result)
        else:
            errors.append(result)
    results.sort(key=lambda item: (item.section_order, item.order, item.section, item.label))
    return results, errors


def write_audit(
    results: list[MetricResult],
    output_path: str | Path,
    template: dict[str, Any] | None = None,
    slot_map: dict[str, dict[str, Any]] | None = None,
    mode: str = "manual",
    fallback_used: bool = False,
    csv_name: str = "",
) -> pd.DataFrame:
    slot_map = slot_map or {}
    rows = [
        result.audit_row(
            template=template,
            slot_info=slot_map.get(result.metric_id, {}),
            mode=mode,
            fallback_used=fallback_used,
            csv_name=csv_name,
        )
        for result in results
    ]
    audit = pd.DataFrame(rows, columns=[
        "id",
        "indicador",
        "coluna utilizada",
        "filtro aplicado",
        "operacao realizada",
        "valor bruto",
        "valor exibido",
        "periodo",
        "fonte",
        "arquivo CSV",
        "configuracao",
        "template",
        "versao do template",
        "pagina",
        "secao",
        "slot",
        "icone",
        "uso de fallback",
    ])
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output_path, index=False, encoding="utf-8-sig")
    return audit

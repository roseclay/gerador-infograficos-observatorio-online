from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
import unicodedata
from typing import Any

import pandas as pd

from .catalog import catalog_by_id, suggest_indicator_id
from .formatting import format_display_value, is_missing, parse_brazilian_number
from .free_mode import DEFAULT_FIELD_HEIGHT, DEFAULT_FIELD_WIDTH, DEFAULT_FONT_SIZE, make_field_id, normalize_fields
from .icon_registry import DEFAULT_COLOR


@dataclass(frozen=True)
class BindingResolution:
    value: str
    raw_value: Any
    indicator_id: str
    label: str
    unit: str
    source_column: str
    filters_applied: dict[str, str]
    status: str = "ok"
    error: str = ""


def normalize_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return text


def _first_column(dataframe: pd.DataFrame, aliases: set[str]) -> str:
    for column in dataframe.columns:
        if normalize_key(column) in aliases:
            return str(column)
    return ""


def value_column(dataframe: pd.DataFrame) -> str:
    return _first_column(dataframe, {"valor", "value", "texto", "conteudo", "quantidade", "total"})


def indicator_column(dataframe: pd.DataFrame) -> str:
    return _first_column(dataframe, {"indicador_id", "id_indicador", "indicador", "campo", "nome_campo", "nome"})


def period_column(dataframe: pd.DataFrame) -> str:
    return _first_column(dataframe, {"periodo", "ano", "referencia", "periodo_referencia"})


def recorte_column(dataframe: pd.DataFrame) -> str:
    return _first_column(dataframe, {"recorte_id", "recorte", "territorio", "categoria", "grupo"})


def metadata_columns(dataframe: pd.DataFrame) -> dict[str, str]:
    return {
        "indicator": indicator_column(dataframe),
        "value": value_column(dataframe),
        "period": period_column(dataframe),
        "recorte": recorte_column(dataframe),
        "unit": _first_column(dataframe, {"unidade", "unit"}),
    }


def logical_key_columns(dataframe: pd.DataFrame) -> list[str]:
    columns = metadata_columns(dataframe)
    if normalize_key(columns["indicator"]) in {"indicador_id", "id_indicador"}:
        ignored = {columns["value"], columns["unit"], ""}
        return [str(column) for column in dataframe.columns if str(column) not in ignored]
    if columns["indicator"]:
        return [columns["indicator"]]
    return []


def duplicate_logical_keys(dataframe: pd.DataFrame) -> pd.DataFrame:
    keys = logical_key_columns(dataframe)
    if not keys:
        return pd.DataFrame()
    filled = dataframe.fillna("")
    mask = filled.duplicated(subset=keys, keep=False)
    return filled.loc[mask, keys].drop_duplicates()


def _matches_indicator(row_value: Any, indicator_id: str, definition: dict[str, Any] | None = None) -> bool:
    raw = str(row_value or "").strip()
    if not raw:
        return False
    if normalize_key(raw) == normalize_key(indicator_id):
        return True
    if definition:
        candidates = [definition.get("label", ""), *definition.get("aliases", [])]
        return normalize_key(raw) in {normalize_key(candidate) for candidate in candidates}
    return False


def _format_resolved_value(raw_value: Any, definition: dict[str, Any] | None, decimals: int | None = None) -> str:
    definition = definition or {}
    precision = int(decimals if decimals is not None else definition.get("precision") or 0)
    formatted = format_display_value(raw_value, precision, preserve_qualified_text=True)
    if definition.get("format") == "percent_pt_br" and formatted and "%" not in formatted:
        formatted = f"{formatted}%"
    return formatted


def _apply_filters(dataframe: pd.DataFrame, filters: dict[str, Any] | None) -> pd.DataFrame:
    filtered = dataframe
    for column, expected in (filters or {}).items():
        if not str(column).strip() or column not in filtered.columns:
            continue
        if is_missing(expected):
            continue
        expected_text = str(expected).strip().casefold()
        filtered = filtered[filtered[column].map(lambda value: str(value).strip().casefold() == expected_text)]
    return filtered


def resolve_indicator_value(
    dataframe: pd.DataFrame,
    indicator_id: str,
    definitions: list[dict[str, Any]] | None = None,
    *,
    filters: dict[str, Any] | None = None,
    operation: str = "direct_value",
    decimals: int | None = None,
) -> BindingResolution:
    catalog = catalog_by_id(definitions)
    definition = catalog.get(indicator_id)
    columns = metadata_columns(dataframe)
    indicator_col = columns["indicator"]
    val_col = columns["value"]
    if not indicator_col or not val_col:
        return BindingResolution("", "", indicator_id, indicator_id, "", "", filters or {}, "missing_binding", "colunas de indicador/valor ausentes")
    filtered = _apply_filters(dataframe, filters)
    matched = filtered[filtered[indicator_col].map(lambda value: _matches_indicator(value, indicator_id, definition))]
    if matched.empty:
        return BindingResolution("", "", indicator_id, definition.get("label", indicator_id) if definition else indicator_id, definition.get("unit", "") if definition else "", val_col, filters or {}, "missing_value", "indicador sem dados")
    values = [value for value in matched[val_col].tolist() if not is_missing(value)]
    if not values:
        return BindingResolution("", "", indicator_id, definition.get("label", indicator_id) if definition else indicator_id, definition.get("unit", "") if definition else "", val_col, filters or {}, "missing_value", "valor ausente")
    try:
        if operation == "sum":
            raw_value = sum((parse_brazilian_number(value) for value in values), Decimal("0"))
        elif operation == "latest":
            raw_value = values[-1]
        else:
            if len(values) > 1 and not filters and operation == "direct_value":
                return BindingResolution("", "", indicator_id, definition.get("label", indicator_id) if definition else indicator_id, definition.get("unit", "") if definition else "", val_col, filters or {}, "ambiguous", "mais de uma observacao encontrada; informe recorte/filtro")
            raw_value = values[0]
    except (InvalidOperation, ValueError) as exc:
        return BindingResolution("", "", indicator_id, definition.get("label", indicator_id) if definition else indicator_id, definition.get("unit", "") if definition else "", val_col, filters or {}, "invalid_value", str(exc))
    return BindingResolution(
        value=_format_resolved_value(raw_value, definition, decimals),
        raw_value=raw_value,
        indicator_id=indicator_id,
        label=definition.get("label", indicator_id) if definition else indicator_id,
        unit=definition.get("unit", "") if definition else "",
        source_column=val_col,
        filters_applied=filters or {},
    )


def rows_as_indicator_observations(dataframe: pd.DataFrame, definitions: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    catalog = catalog_by_id(definitions)
    columns = metadata_columns(dataframe)
    indicator_col = columns["indicator"]
    val_col = columns["value"]
    if not indicator_col or not val_col:
        return []
    rows = []
    for index, row in dataframe.fillna("").iterrows():
        raw_indicator = str(row[indicator_col]).strip()
        indicator_id = raw_indicator if normalize_key(indicator_col) in {"indicador_id", "id_indicador"} else suggest_indicator_id(raw_indicator, definitions)
        definition = catalog.get(indicator_id, {})
        label = definition.get("label") or raw_indicator or f"Indicador {index + 1}"
        raw_value = row[val_col]
        rows.append({
            "indicator_id": indicator_id or normalize_key(raw_indicator) or f"indicador_{index + 1:03d}",
            "label": label,
            "raw_label": raw_indicator,
            "raw_value": raw_value,
            "display_value": _format_resolved_value(raw_value, definition),
            "period": str(row[columns["period"]]).strip() if columns["period"] else "",
            "recorte": str(row[columns["recorte"]]).strip() if columns["recorte"] else "",
            "source_column": val_col,
        })
    return rows


def fields_from_dataset_observations(
    dataframe: pd.DataFrame,
    dataset_id: str,
    dataset_version_id: str,
    definitions: list[dict[str, Any]] | None,
    image_width: int,
    image_height: int,
    existing_fields: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    existing_ids = [str(field.get("id") or "") for field in existing_fields or []]
    result = []
    for index, observation in enumerate(rows_as_indicator_observations(dataframe, definitions), start=1):
        field_id = make_field_id(existing_ids + [str(item.get("id")) for item in result])
        field = {
            "enabled": True,
            "placed": False,
            "id": field_id,
            "name": observation["label"],
            "value": observation["display_value"],
            "x": 0,
            "y": 0,
            "width": DEFAULT_FIELD_WIDTH,
            "height": DEFAULT_FIELD_HEIGHT,
            "font_size": DEFAULT_FONT_SIZE,
            "color": DEFAULT_COLOR,
            "bold": True,
            "align": "left",
            "render_label": False,
            "order": len(existing_ids) + index,
            "type": "metric",
            "binding": {
                "type": "metric",
                "dataset_id": dataset_id,
                "dataset_version_id": dataset_version_id,
                "applied_version_id": dataset_version_id,
                "indicator_id": observation["indicator_id"],
                "operation": "direct_value",
                "filters": {},
                "source_column": observation["source_column"],
                "version_policy": "notify_then_apply",
                "status": "ok",
            },
        }
        result.append(field)
    return normalize_fields(result, image_width, image_height)


def make_chart_element(
    dataset_id: str,
    dataset_version_id: str,
    dataframe: pd.DataFrame,
    definitions: list[dict[str, Any]] | None,
    indicator_ids: list[str],
    *,
    chart_type: str = "bar_horizontal",
    title: str = "",
    existing_ids: list[str] | None = None,
    order: int = 1,
    image_width: int = 1122,
    image_height: int = 1402,
) -> dict[str, Any]:
    series = []
    for index, indicator_id in enumerate(indicator_ids, start=1):
        resolved = resolve_indicator_value(dataframe, indicator_id, definitions)
        if resolved.status == "ok":
            raw = resolved.raw_value
            display = resolved.value
            label = resolved.label
        else:
            raw = ""
            display = "Sem dados"
            label = catalog_by_id(definitions).get(indicator_id, {}).get("label", indicator_id)
        series.append({
            "key": indicator_id,
            "indicator_id": indicator_id,
            "label": label,
            "raw_value": raw,
            "display_value": display,
            "order": index,
            "color": DEFAULT_COLOR,
        })
    field = {
        "enabled": True,
        "placed": False,
        "id": make_field_id(existing_ids or []),
        "name": title or "Gráfico",
        "value": title or "Gráfico",
        "x": 0,
        "y": 0,
        "width": max(360, int(image_width * 0.50)),
        "height": 220 if chart_type == "bar_horizontal" else 260,
        "font_size": 28,
        "color": DEFAULT_COLOR,
        "bold": True,
        "align": "left",
        "render_label": False,
        "order": order,
        "type": "chart",
        "binding": {
            "type": "chart_series",
            "dataset_id": dataset_id,
            "dataset_version_id": dataset_version_id,
            "applied_version_id": dataset_version_id,
            "indicator_ids": indicator_ids,
            "series_source": "indicators",
            "version_policy": "notify_then_apply",
            "status": "ok",
        },
        "chart": {
            "type": chart_type,
            "title": title,
            "series": series,
            "show_values": True,
            "show_labels": True,
            "show_axis": chart_type == "bar_vertical",
            "background": "transparent",
            "bar_color": DEFAULT_COLOR,
            "font_size": 26,
        },
    }
    return normalize_fields([field], image_width, image_height)[0]


def dimension_chart_series(dataframe: pd.DataFrame, category_column: str, value_column_name: str, operation: str = "direct_value") -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    if category_column not in dataframe.columns:
        return [], [f"coluna de categoria ausente: {category_column}"]
    if value_column_name not in dataframe.columns:
        return [], [f"coluna de valor ausente: {value_column_name}"]
    temp = dataframe[[category_column, value_column_name]].fillna("").copy()
    temp = temp[~temp[category_column].map(is_missing)]
    if operation == "sum":
        grouped: dict[str, Decimal] = {}
        for _, row in temp.iterrows():
            category = str(row[category_column]).strip()
            try:
                grouped[category] = grouped.get(category, Decimal("0")) + parse_brazilian_number(row[value_column_name])
            except Exception as exc:
                errors.append(f"{category}: valor inválido ({exc})")
        items = list(grouped.items())
    else:
        duplicates = temp[temp.duplicated(subset=[category_column], keep=False)]
        if not duplicates.empty:
            return [], ["categorias duplicadas; escolha soma ou ajuste o recorte"]
        items = [(str(row[category_column]).strip(), row[value_column_name]) for _, row in temp.iterrows()]

    def sort_key(item: tuple[str, Any]) -> tuple[int, Any]:
        category = item[0]
        try:
            return (0, int(category))
        except Exception:
            return (1, category.casefold())

    series = []
    for index, (category, raw_value) in enumerate(sorted(items, key=sort_key), start=1):
        series.append({
            "key": category,
            "label": category,
            "raw_value": raw_value,
            "display_value": format_display_value(raw_value, 0, preserve_qualified_text=True),
            "order": index,
            "color": DEFAULT_COLOR,
        })
    return series, errors


def make_dimension_chart_element(
    dataset_id: str,
    dataset_version_id: str,
    dataframe: pd.DataFrame,
    category_column: str,
    value_column_name: str,
    *,
    operation: str = "direct_value",
    chart_type: str = "bar_horizontal",
    title: str = "",
    existing_ids: list[str] | None = None,
    order: int = 1,
    image_width: int = 1122,
    image_height: int = 1402,
) -> tuple[dict[str, Any], list[str]]:
    series, errors = dimension_chart_series(dataframe, category_column, value_column_name, operation)
    field = {
        "enabled": True,
        "placed": False,
        "id": make_field_id(existing_ids or []),
        "name": title or "Gráfico",
        "value": title or "Gráfico",
        "x": 0,
        "y": 0,
        "width": max(360, int(image_width * 0.50)),
        "height": 240 if chart_type == "bar_horizontal" else 280,
        "font_size": 28,
        "color": DEFAULT_COLOR,
        "bold": True,
        "align": "left",
        "render_label": False,
        "order": order,
        "type": "chart",
        "binding": {
            "type": "chart_dimension",
            "dataset_id": dataset_id,
            "dataset_version_id": dataset_version_id,
            "applied_version_id": dataset_version_id,
            "category_column": category_column,
            "value_column": value_column_name,
            "operation": operation,
            "series_source": "dimension",
            "version_policy": "notify_then_apply",
            "status": "ok" if not errors else "invalid_series",
            "error": "; ".join(errors),
        },
        "chart": {
            "type": chart_type,
            "title": title,
            "series": series,
            "show_values": True,
            "show_labels": True,
            "show_axis": chart_type == "bar_vertical",
            "background": "transparent",
            "bar_color": DEFAULT_COLOR,
            "font_size": 26,
        },
    }
    return normalize_fields([field], image_width, image_height)[0], errors


def update_bound_elements(
    elements: list[dict[str, Any]],
    dataset_id: str,
    dataset_version_id: str,
    dataframe: pd.DataFrame,
    definitions: list[dict[str, Any]] | None = None,
    image_width: int = 1122,
    image_height: int = 1402,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    updated = []
    changes = []
    for element in deepcopy(elements):
        binding = element.get("binding") or {}
        if binding.get("dataset_id") != dataset_id:
            updated.append(element)
            continue
        if binding.get("type") == "chart_dimension":
            chart = deepcopy(element.get("chart") or {})
            series, errors = dimension_chart_series(
                dataframe,
                str(binding.get("category_column") or ""),
                str(binding.get("value_column") or ""),
                str(binding.get("operation") or "direct_value"),
            )
            old = {str(item.get("key")): str(item.get("display_value") or "") for item in chart.get("series") or []}
            for item in series:
                previous = old.get(str(item.get("key")))
                if previous is not None and previous != str(item.get("display_value") or ""):
                    changes.append({"element_id": element.get("id"), "indicator_id": item.get("key"), "old": previous, "new": item.get("display_value")})
            chart["series"] = series
            binding["applied_version_id"] = dataset_version_id
            binding["dataset_version_id"] = dataset_version_id
            binding["status"] = "ok" if not errors else "invalid_series"
            binding["error"] = "; ".join(errors)
            element["binding"] = binding
            element["chart"] = chart
            updated.append(element)
            continue
        if binding.get("type") == "chart_series" or element.get("type") == "chart":
            chart = deepcopy(element.get("chart") or {})
            new_series = []
            for item in chart.get("series") or []:
                indicator_id = str(item.get("indicator_id") or item.get("key") or "")
                resolved = resolve_indicator_value(dataframe, indicator_id, definitions)
                new_item = deepcopy(item)
                old_display = str(new_item.get("display_value") or "")
                if resolved.status == "ok":
                    new_item["raw_value"] = resolved.raw_value
                    new_item["display_value"] = resolved.value
                    new_item["label"] = resolved.label
                    binding["status"] = "ok"
                    if old_display != resolved.value:
                        changes.append({"element_id": element.get("id"), "indicator_id": indicator_id, "old": old_display, "new": resolved.value})
                else:
                    new_item["display_value"] = "Sem dados"
                    binding["status"] = resolved.status
                    binding["error"] = resolved.error
                new_series.append(new_item)
            chart["series"] = new_series
            binding["applied_version_id"] = dataset_version_id
            element["binding"] = binding
            element["chart"] = chart
            updated.append(element)
            continue
        indicator_id = str(binding.get("indicator_id") or "")
        resolved = resolve_indicator_value(
            dataframe,
            indicator_id,
            definitions,
            filters=binding.get("filters") or {},
            operation=str(binding.get("operation") or "direct_value"),
        )
        old_value = str(element.get("value") or "")
        if resolved.status == "ok":
            element["value"] = resolved.value
            binding["applied_version_id"] = dataset_version_id
            binding["dataset_version_id"] = dataset_version_id
            binding["status"] = "ok"
            binding.pop("error", None)
            if old_value != resolved.value:
                changes.append({"element_id": element.get("id"), "indicator_id": indicator_id, "old": old_value, "new": resolved.value})
        else:
            binding["status"] = resolved.status
            binding["error"] = resolved.error
        element["binding"] = binding
        updated.append(element)
    if updated:
        updated = normalize_fields(updated, max(1, int(image_width or 1122)), max(1, int(image_height or 1402)))
    return updated, changes

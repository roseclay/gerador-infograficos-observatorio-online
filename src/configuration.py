from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date
import hashlib
import re
import unicodedata
from typing import Any

import pandas as pd


DEFAULT_HEADER = "OBSERVATÓRIO DE CIÊNCIA, TECNOLOGIA E INOVAÇÃO DA BAHIA"
SCHEMA_VERSION = 2
DEFAULT_SECTION = "Indicadores"
DEFAULT_TEMPLATE_ID = "institucional_claro_v1"
DEFAULT_TEMPLATE_VERSION = "1.0"


@dataclass(frozen=True)
class CsvCompatibility:
    compatible: bool
    missing_columns: list[str]
    expected_signature: str
    current_signature: str


def csv_schema_signature(columns: list[str] | tuple[str, ...]) -> str:
    normalized = "\n".join(str(column).strip() for column in columns)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def empty_metadata(source: str = "") -> dict[str, str]:
    return {
        "header": DEFAULT_HEADER,
        "title": "",
        "subtitle": "",
        "period": "",
        "source": "",
        "updated_at": "",
        "cta": "",
        "website": "",
    }


def empty_config(columns: list[str] | None = None, source: str = "") -> dict[str, Any]:
    columns = columns or []
    return {
        "schema_version": SCHEMA_VERSION,
        "csv_schema": {
            "columns": columns,
            "signature": csv_schema_signature(columns),
        },
        "metadata": empty_metadata(source),
        "template": {
            "id": DEFAULT_TEMPLATE_ID,
            "version": DEFAULT_TEMPLATE_VERSION,
        },
        "sections": [],
        "indicators": [],
        "export": {
            "width": 1600,
            "height": 2000,
            "max_indicators_per_page": 9,
        },
    }


def make_indicator_id(existing_ids: list[str] | None = None) -> str:
    existing = set(existing_ids or [])
    index = 1
    while True:
        candidate = f"indicador_{index:03d}"
        if candidate not in existing:
            return candidate
        index += 1


def new_indicator(columns: list[str] | None = None, existing_ids: list[str] | None = None, order: int = 1) -> dict[str, Any]:
    columns = columns or []
    return {
        "enabled": True,
        "id": make_indicator_id(existing_ids),
        "label": "",
        "section": DEFAULT_SECTION,
        "section_order": 1,
        "show_section_title": True,
        "column": "",
        "operation": "",
        "filter_column": "",
        "filter_operator": "equals",
        "filter_value": "",
        "numerator_column": "",
        "denominator_column": "",
        "prefix": "",
        "suffix": "",
        "decimals": 0,
        "order": order,
        "icon": "circle",
        "color": "#0057B8",
    }


def duplicate_indicator(indicators: list[dict[str, Any]], indicator_id: str) -> list[dict[str, Any]]:
    existing_ids = [str(item.get("id", "")) for item in indicators]
    result = deepcopy(indicators)
    for index, indicator in enumerate(indicators):
        if str(indicator.get("id")) == str(indicator_id):
            duplicate = deepcopy(indicator)
            duplicate["id"] = make_indicator_id(existing_ids)
            duplicate["label"] = f"{duplicate.get('label', '')} (cópia)".strip()
            duplicate["order"] = int(duplicate.get("order") or index + 1) + 1
            result.insert(index + 1, duplicate)
            return result
    return result


def remove_indicator(indicators: list[dict[str, Any]], indicator_id: str) -> list[dict[str, Any]]:
    return [deepcopy(item) for item in indicators if str(item.get("id")) != str(indicator_id)]


def reorder_indicators(indicators: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = [deepcopy(item) for item in indicators]
    result.sort(key=lambda item: (int(item.get("section_order") or 999), int(item.get("order") or 999), str(item.get("label", ""))))
    for index, indicator in enumerate(result, start=1):
        indicator["order"] = index
    return result


def clear_indicators(config: dict[str, Any], columns: list[str] | None = None, source: str = "") -> dict[str, Any]:
    cleaned = empty_config(columns or [], source)
    cleaned["metadata"] = deepcopy(config.get("metadata") or empty_metadata(source))
    cleaned["template"] = deepcopy(config.get("template") or cleaned["template"])
    return cleaned


def is_aggregate_dataframe(dataframe: pd.DataFrame) -> bool:
    if dataframe.shape[1] != 2 or dataframe.empty:
        return False
    first = dataframe.iloc[:, 0].map(lambda value: str(value).strip())
    second = dataframe.iloc[:, 1].map(lambda value: str(value).strip())
    return bool(first.ne("").all() and second.ne("").all() and first.nunique() == len(first))


def aggregate_indicators_from_dataframe(dataframe: pd.DataFrame, label_column: str | None = None, value_column: str | None = None) -> list[dict[str, Any]]:
    if not is_aggregate_dataframe(dataframe):
        return []
    label_column = label_column or str(dataframe.columns[0])
    value_column = value_column or str(dataframe.columns[1])
    indicators: list[dict[str, Any]] = []
    existing_ids: list[str] = []
    for index, row in dataframe.iterrows():
        label = str(row[label_column]).strip()
        indicator = new_indicator(list(dataframe.columns), existing_ids, order=len(indicators) + 1)
        indicator["label"] = label
        indicator["column"] = value_column
        indicator["operation"] = "direct_value"
        indicator["filter_column"] = label_column
        indicator["filter_value"] = label
        indicator["section"] = DEFAULT_SECTION
        indicator["section_order"] = 1
        indicator["icon"] = "circle"
        indicators.append(indicator)
        existing_ids.append(indicator["id"])
    return indicators


def sections_from_indicators(indicators: list[dict[str, Any]], existing_sections: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for section in existing_sections or []:
        name = str(section.get("name") or section.get("section") or "").strip()
        if name:
            by_name[name] = {
                "name": name,
                "order": int(section.get("order") or len(by_name) + 1),
                "show_title": bool(section.get("show_title", True)),
            }
    for indicator in indicators:
        name = str(indicator.get("section") or DEFAULT_SECTION).strip() or DEFAULT_SECTION
        if name not in by_name:
            by_name[name] = {
                "name": name,
                "order": int(indicator.get("section_order") or len(by_name) + 1),
                "show_title": bool(indicator.get("show_section_title", True)),
            }
    return sorted(by_name.values(), key=lambda item: (int(item["order"]), str(item["name"])))


def apply_sections_to_indicators(indicators: list[dict[str, Any]], sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    section_map = {
        str(section.get("name", "")).strip(): {
            "order": int(section.get("order") or index + 1),
            "show_title": bool(section.get("show_title", True)),
        }
        for index, section in enumerate(sections)
        if str(section.get("name", "")).strip()
    }
    result = []
    for indicator in indicators:
        item = deepcopy(indicator)
        name = str(item.get("section") or DEFAULT_SECTION).strip() or DEFAULT_SECTION
        item["section"] = name
        item["section_order"] = section_map.get(name, {}).get("order", int(item.get("section_order") or 999))
        item["show_section_title"] = section_map.get(name, {}).get("show_title", bool(item.get("show_section_title", True)))
        result.append(item)
    return result


def normalize_config(config: dict[str, Any], columns: list[str] | None = None, source: str = "") -> dict[str, Any]:
    columns = columns or list((config.get("csv_schema") or {}).get("columns") or [])
    normalized = empty_config(columns, source)
    normalized.update({key: deepcopy(value) for key, value in config.items() if key not in {"metadata", "indicators", "sections", "csv_schema", "export"}})
    normalized["schema_version"] = int(config.get("schema_version") or SCHEMA_VERSION)
    normalized["csv_schema"] = {
        "columns": list((config.get("csv_schema") or {}).get("columns") or columns),
        "signature": (config.get("csv_schema") or {}).get("signature") or csv_schema_signature(columns),
    }
    metadata = empty_metadata(source)
    metadata.update(deepcopy(config.get("metadata") or {}))
    normalized["metadata"] = metadata
    template = deepcopy(config.get("template") or normalized.get("template") or {})
    normalized["template"] = {
        "id": str(template.get("id") or DEFAULT_TEMPLATE_ID),
        "version": str(template.get("version") or DEFAULT_TEMPLATE_VERSION),
    }
    indicators = [deepcopy(item) for item in config.get("indicators") or []]
    existing_ids: list[str] = []
    for index, indicator in enumerate(indicators, start=1):
        if not str(indicator.get("id", "")).strip():
            indicator["id"] = make_indicator_id(existing_ids)
        existing_ids.append(str(indicator["id"]))
        indicator.setdefault("enabled", True)
        indicator.setdefault("section", DEFAULT_SECTION)
        indicator.setdefault("section_order", 1)
        indicator.setdefault("show_section_title", True)
        indicator.setdefault("filter_operator", "equals")
        indicator.setdefault("numerator_column", "")
        indicator.setdefault("denominator_column", "")
        indicator.setdefault("prefix", "")
        indicator.setdefault("suffix", "")
        indicator.setdefault("decimals", 0)
        indicator.setdefault("order", index)
        indicator.setdefault("icon", "circle")
        indicator.setdefault("color", "#0057B8")
    sections = sections_from_indicators(indicators, config.get("sections") or [])
    normalized["sections"] = sections
    normalized["indicators"] = apply_sections_to_indicators(indicators, sections)
    export = normalized["export"]
    export.update(deepcopy(config.get("export") or {}))
    normalized["export"] = export
    return normalized


def referenced_columns(config: dict[str, Any]) -> list[str]:
    columns: list[str] = []
    for indicator in config.get("indicators") or []:
        for key in ["column", "filter_column", "numerator_column", "denominator_column"]:
            value = str(indicator.get(key, "")).strip()
            if value and value not in columns:
                columns.append(value)
    return columns


def config_compatibility(config: dict[str, Any], columns: list[str]) -> CsvCompatibility:
    available = {str(column) for column in columns}
    missing = [column for column in referenced_columns(config) if column not in available]
    expected_signature = str((config.get("csv_schema") or {}).get("signature") or "")
    current_signature = csv_schema_signature(columns)
    signature_ok = not expected_signature or expected_signature == current_signature
    return CsvCompatibility(
        compatible=not missing and signature_ok,
        missing_columns=missing,
        expected_signature=expected_signature,
        current_signature=current_signature,
    )


def update_schema(config: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    updated = deepcopy(config)
    updated["csv_schema"] = {
        "columns": list(columns),
        "signature": csv_schema_signature(columns),
    }
    return updated


def reset_if_schema_changed(config: dict[str, Any], columns: list[str], source: str = "") -> dict[str, Any]:
    previous = str((config.get("csv_schema") or {}).get("signature") or "")
    current = csv_schema_signature(columns)
    if previous and previous != current:
        return empty_config(columns, source)
    return update_schema(config, columns)


def slugify_filename(value: str) -> str:
    base = value.rsplit(".", 1)[0] if value else "dados"
    normalized = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_").lower()
    return normalized or "dados"


def export_names(csv_name: str, today: date | None = None) -> dict[str, str]:
    today = today or date.today()
    slug = slugify_filename(csv_name)
    stamp = today.isoformat()
    return {
        "png": f"infografico_{slug}_{stamp}.png",
        "pdf": f"infografico_{slug}_{stamp}.pdf",
        "audit": f"auditoria_{slug}_{stamp}.csv",
        "data": f"dados_utilizados_{slug}_{stamp}.csv",
        "validation": f"relatorio_validacao_{slug}_{stamp}.txt",
    }

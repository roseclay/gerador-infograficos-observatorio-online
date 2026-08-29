from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .auto_layout import layout_reason, recommended_max_per_page
from .column_profiler import ColumnProfile, profile_columns
from .configuration import (
    DEFAULT_HEADER,
    aggregate_indicators_from_dataframe,
    apply_sections_to_indicators,
    empty_config,
    reorder_indicators,
    sections_from_indicators,
    update_schema,
)
from .data_loader import CsvProfile
from .icon_registry import DEFAULT_COLOR
from .semantic_rules import CUSTOM_RULES_PATH, DEFAULT_RULES_PATH, RuleMatch, confidence_level, load_rulebook, match_rule, title_case_label


@dataclass(frozen=True)
class InferenceDecision:
    indicator_id: str
    label: str
    value_or_calculation: str
    column: str
    operation: str
    filter_description: str
    section: str
    icon: str
    color: str
    order: int
    confidence: int
    confidence_level: str
    reason: str
    rule_id: str
    automatic: bool


@dataclass(frozen=True)
class InferenceResult:
    config: dict[str, Any]
    decisions: list[InferenceDecision]
    column_profiles: list[ColumnProfile]
    data_shape: str
    confidence: int
    warnings: list[str]
    reason: str


def _neutral_metadata(source: str, data_shape: str, matched_categories: set[str]) -> dict[str, str]:
    title = "Panorama dos indicadores"
    if data_shape == "agregado" and {"pessoas/pesquisa", "rede", "educação"}.intersection(matched_categories):
        title = "Indicadores de ciência, tecnologia e inovação"
    return {
        "header": DEFAULT_HEADER,
        "title": title,
        "subtitle": "",
        "period": "",
        "source": "",
        "updated_at": "",
        "cta": "",
        "website": "",
    }


def _section_order(rulebook: dict[str, Any]) -> dict[str, int]:
    sections = rulebook.get("sections") or []
    return {str(section.get("name")): int(section.get("order") or index + 1) for index, section in enumerate(sections)}


def _rule_sections(rulebook: dict[str, Any], indicators: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = {str(indicator.get("section")) for indicator in indicators}
    configured = [
        {
            "name": str(section.get("name")),
            "order": int(section.get("order") or index + 1),
            "show_title": bool(section.get("show_title", True)),
        }
        for index, section in enumerate(rulebook.get("sections") or [])
        if str(section.get("name")) in existing
    ]
    return sections_from_indicators(indicators, configured)


def infer_aggregate_config(dataframe: pd.DataFrame, profile: CsvProfile, source: str, rulebook: dict[str, Any]) -> tuple[list[dict[str, Any]], list[InferenceDecision], set[str]]:
    indicators = aggregate_indicators_from_dataframe(dataframe)
    order_by_section = _section_order(rulebook)
    decisions = []
    categories: set[str] = set()
    for index, indicator in enumerate(indicators, start=1):
        raw_label = str(indicator.get("label") or "")
        rule = match_rule(raw_label, rulebook)
        categories.add(rule.category)
        label = rule.preferred_label or title_case_label(raw_label)
        indicator.update({
            "label": label,
            "section": rule.section,
            "section_order": order_by_section.get(rule.section, index),
            "show_section_title": True,
            "icon": rule.icon,
            "color": rule.color or DEFAULT_COLOR,
            "order": index,
            "operation": "direct_value",
            "column": str(profile.columns[1]),
            "filter_column": str(profile.columns[0]),
            "filter_operator": "equals",
            "filter_value": raw_label,
            "prefix": "",
            "suffix": "",
            "decimals": 0,
            "auto_confidence": rule.confidence,
            "auto_rule_id": rule.rule_id,
            "auto_reason": rule.reason,
            "auto_applied": True,
        })
        decisions.append(InferenceDecision(
            indicator_id=str(indicator["id"]),
            label=label,
            value_or_calculation=str(dataframe.iloc[index - 1, 1]),
            column=str(profile.columns[1]),
            operation="direct_value",
            filter_description=f"{profile.columns[0]} igual a {raw_label}",
            section=rule.section,
            icon=rule.icon,
            color=rule.color,
            order=index,
            confidence=rule.confidence,
            confidence_level=confidence_level(rule.confidence),
            reason=rule.reason,
            rule_id=rule.rule_id,
            automatic=rule.confidence >= 60,
        ))
    indicators = reorder_indicators(apply_sections_to_indicators(indicators, _rule_sections(rulebook, indicators)))
    return indicators, decisions, categories


def _detailed_indicator_for_column(column: ColumnProfile, order: int, dataframe: pd.DataFrame, rulebook: dict[str, Any]) -> tuple[dict[str, Any] | None, InferenceDecision | None]:
    from .configuration import new_indicator

    if not column.safe_operations:
        return None, None
    rule = match_rule(column.name, rulebook)
    operation = ""
    if column.kind in {"localização", "instituição", "identificador"}:
        operation = "distinct_count"
    elif column.kind == "booleano":
        operation = "count"
    elif column.kind == "categoria":
        operation = "count"
    elif column.kind == "número" and "sum" in rule.compatible_operations and rule.confidence >= 85:
        operation = "sum"
    if not operation:
        return None, None
    confidence = min(rule.confidence, column.confidence)
    if confidence < 60:
        return None, None
    indicator = new_indicator(list(dataframe.columns), [], order=order)
    label = rule.preferred_label or title_case_label(column.name)
    indicator.update({
        "label": label,
        "section": rule.section,
        "section_order": order,
        "show_section_title": True,
        "column": column.name,
        "operation": operation,
        "icon": rule.icon,
        "color": rule.color,
        "auto_confidence": confidence,
        "auto_rule_id": rule.rule_id,
        "auto_reason": f"{column.reason}; {rule.reason}",
        "auto_applied": True,
    })
    decision = InferenceDecision(
        indicator_id=str(indicator["id"]),
        label=label,
        value_or_calculation=f"{operation} em {column.name}",
        column=column.name,
        operation=operation,
        filter_description="sem filtro",
        section=rule.section,
        icon=rule.icon,
        color=rule.color,
        order=order,
        confidence=confidence,
        confidence_level=confidence_level(confidence),
        reason=f"{column.reason}; {rule.reason}",
        rule_id=rule.rule_id,
        automatic=confidence >= 60,
    )
    return indicator, decision


def infer_detailed_config(dataframe: pd.DataFrame, rulebook: dict[str, Any]) -> tuple[list[dict[str, Any]], list[InferenceDecision], list[str], set[str]]:
    warnings = []
    indicators = []
    decisions = []
    categories = set()
    for column in profile_columns(dataframe):
        if column.kind in {"possível informação pessoal", "texto livre", "data"}:
            warnings.append(f"Coluna '{column.name}' classificada como {column.kind}; não virou indicador automático.")
            continue
        indicator, decision = _detailed_indicator_for_column(column, len(indicators) + 1, dataframe, rulebook)
        if indicator and decision:
            indicators.append(indicator)
            decisions.append(decision)
            categories.add(match_rule(column.name, rulebook).category)
    indicators = reorder_indicators(apply_sections_to_indicators(indicators, _rule_sections(rulebook, indicators)))
    return indicators, decisions, warnings, categories


def infer_config(
    dataframe: pd.DataFrame,
    profile: CsvProfile,
    source: str = "",
    default_rules_path: str | Path | None = None,
    custom_rules_path: str | Path | None = None,
) -> InferenceResult:
    rulebook = load_rulebook(default_rules_path or DEFAULT_RULES_PATH, custom_rules_path or CUSTOM_RULES_PATH)
    warnings: list[str] = []
    column_profiles = profile_columns(dataframe)
    categories: set[str] = set()
    if profile.data_shape == "agregado":
        indicators, decisions, categories = infer_aggregate_config(dataframe, profile, source, rulebook)
    else:
        indicators, decisions, warnings, categories = infer_detailed_config(dataframe, rulebook)
    config = empty_config(profile.columns, source)
    config["metadata"] = _neutral_metadata(source, profile.data_shape, categories)
    config["sections"] = _rule_sections(rulebook, indicators)
    config["indicators"] = apply_sections_to_indicators(indicators, config["sections"])
    config["export"]["max_indicators_per_page"] = recommended_max_per_page(len(indicators))
    config = update_schema(config, profile.columns)
    confidence = int(sum(decision.confidence for decision in decisions) / len(decisions)) if decisions else 0
    if len(indicators) > 9:
        warnings.append("Mais de nove indicadores; exportação deve usar múltiplas páginas.")
    if not indicators:
        warnings.append("Nenhuma sugestão automática atingiu confiança mínima.")
    return InferenceResult(
        config=config,
        decisions=decisions,
        column_profiles=column_profiles,
        data_shape=profile.data_shape,
        confidence=confidence,
        warnings=warnings,
        reason=layout_reason(len(indicators), len(config["sections"])),
    )


def decisions_as_dicts(decisions: list[InferenceDecision]) -> list[dict[str, Any]]:
    return [decision.__dict__.copy() for decision in decisions]


def inference_audit_rows(result: InferenceResult) -> list[dict[str, Any]]:
    return [
        {
            "indicador": decision.label,
            "regra utilizada": decision.rule_id,
            "confianca": decision.confidence,
            "nivel": decision.confidence_level,
            "justificativa": decision.reason,
            "operacao": decision.operation,
            "coluna": decision.column,
            "secao": decision.section,
            "icone": decision.icon,
            "cor": decision.color,
            "decisao": "automatica" if decision.automatic else "revisao",
        }
        for decision in result.decisions
    ]


def automatic_audit_rows_from_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    template = config.get("template") or {}
    for indicator in config.get("indicators") or []:
        if not indicator.get("auto_rule_id"):
            continue
        rows.append({
            "indicador": indicator.get("label", ""),
            "regra utilizada": indicator.get("auto_rule_id", ""),
            "confianca": indicator.get("auto_confidence", ""),
            "justificativa": indicator.get("auto_reason", ""),
            "configuracao original": indicator.get("filter_value", ""),
            "correcoes do usuario": "",
            "decisao": "automatica" if indicator.get("auto_applied") else "manual",
            "template": template.get("id", ""),
            "versao do template": template.get("version", ""),
        })
    return rows


def write_automatic_audit(config: dict[str, Any], output_path: str | Path) -> pd.DataFrame:
    rows = automatic_audit_rows_from_config(config)
    audit = pd.DataFrame(rows, columns=[
        "indicador",
        "regra utilizada",
        "confianca",
        "justificativa",
        "configuracao original",
        "correcoes do usuario",
        "decisao",
        "template",
        "versao do template",
    ])
    if rows:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        audit.to_csv(output, index=False, encoding="utf-8-sig")
    return audit

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import InvalidOperation
from typing import Any

import pandas as pd

from .formatting import is_missing, parse_brazilian_number
from .semantic_rules import normalize_text, semantic_tokens


PERSONAL_TERMS = {"cpf", "rg", "nome", "email", "telefone", "celular", "matricula", "matrícula", "passaporte"}
LOCATION_TERMS = {"municipio", "município", "cidade", "regiao", "região", "territorio", "território", "uf", "estado"}
INSTITUTION_TERMS = {"instituicao", "instituição", "universidade", "instituto", "escola", "faculdade", "campus"}
IDENTIFIER_TERMS = {"id", "codigo", "código", "cod", "matricula", "matrícula", "registro", "identificador"}
BOOLEAN_TRUE = {"sim", "s", "true", "verdadeiro", "1", "ativo", "aprovado", "aprovada"}
BOOLEAN_FALSE = {"nao", "não", "n", "false", "falso", "0", "inativo", "reprovado", "reprovada"}


@dataclass(frozen=True)
class ColumnProfile:
    name: str
    kind: str
    confidence: int
    cardinality: int
    missing: int
    reason: str
    safe_operations: tuple[str, ...]


def _is_numeric(value: Any) -> bool:
    try:
        parse_brazilian_number(value)
        return True
    except (InvalidOperation, ValueError):
        return False


def _is_date(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y"):
        try:
            datetime.strptime(text, fmt)
            return True
        except ValueError:
            continue
    return False


def classify_column(name: str, series: pd.Series) -> ColumnProfile:
    values = [str(value).strip() for value in series.tolist() if not is_missing(value)]
    cardinality = len(set(values))
    missing = int(series.map(is_missing).sum())
    name_norm = normalize_text(name)
    name_tokens = set(semantic_tokens(name))
    total = max(1, len(values))
    numeric_ratio = sum(_is_numeric(value) for value in values) / total
    date_ratio = sum(_is_date(value) for value in values) / total
    boolean_values = {normalize_text(value) for value in values}

    if name_tokens.intersection({normalize_text(term) for term in PERSONAL_TERMS}):
        return ColumnProfile(name, "possível informação pessoal", 92, cardinality, missing, "nome da coluna sugere dado pessoal", ())
    if name_tokens.intersection({normalize_text(term) for term in LOCATION_TERMS}):
        return ColumnProfile(name, "localização", 88, cardinality, missing, "nome da coluna sugere localização", ("distinct_count", "count"))
    if name_tokens.intersection({normalize_text(term) for term in INSTITUTION_TERMS}):
        return ColumnProfile(name, "instituição", 86, cardinality, missing, "nome da coluna sugere instituição", ("distinct_count", "count"))
    if name_norm in {normalize_text(term) for term in IDENTIFIER_TERMS} or name_norm.endswith(" id"):
        return ColumnProfile(name, "identificador", 88, cardinality, missing, "nome da coluna sugere identificador", ("distinct_count", "count"))
    if boolean_values and boolean_values.issubset(BOOLEAN_TRUE.union(BOOLEAN_FALSE)):
        return ColumnProfile(name, "booleano", 90, cardinality, missing, "valores booleanos reconhecidos", ("count", "percentage"))
    if date_ratio >= 0.8:
        return ColumnProfile(name, "data", 86, cardinality, missing, "valores parecem datas ou anos", ())
    if numeric_ratio >= 0.9:
        if cardinality >= max(8, total * 0.8) and ("ano" in name_norm or name_tokens.intersection({normalize_text(term) for term in IDENTIFIER_TERMS})):
            return ColumnProfile(name, "identificador", 76, cardinality, missing, "número parece código, ano ou identificador", ("distinct_count", "count"))
        return ColumnProfile(name, "número", 78, cardinality, missing, "valores numéricos; soma só é sugerida com semântica compatível", ("mean", "sum"))
    if cardinality <= max(8, total * 0.25):
        return ColumnProfile(name, "categoria", 72, cardinality, missing, "baixa cardinalidade", ("count",))
    return ColumnProfile(name, "texto livre", 70, cardinality, missing, "texto sem estrutura segura para indicador automático", ())


def profile_columns(dataframe: pd.DataFrame) -> list[ColumnProfile]:
    return [classify_column(str(column), dataframe[column]) for column in dataframe.columns]

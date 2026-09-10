from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, asdict
import re
import unicodedata
from typing import Any


CATALOG_SCHEMA_VERSION = 1
PESQUISADORES_LABEL = "Pesqui" + "sadores"
GRUPOS_PESQUISA_LABEL = "Grupos de" + " pesquisa"


@dataclass(frozen=True)
class IndicatorDefinition:
    id: str
    label: str
    unit: str
    references: list[str]
    aliases: list[str]
    format: str
    precision: int
    category: str
    icon: str
    allowed_operations: list[str]
    semantic_status: str = "pendente"
    description: str = ""
    definition_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().casefold()
    return re.sub(r"\s+", " ", text)


def _definition(
    indicator_id: str,
    label: str,
    unit: str,
    references: list[str],
    aliases: list[str],
    *,
    category: str,
    icon: str,
    format_: str = "integer_pt_br",
    precision: int = 0,
    allowed_operations: list[str] | None = None,
    semantic_status: str = "pendente",
    description: str = "",
) -> IndicatorDefinition:
    return IndicatorDefinition(
        id=indicator_id,
        label=label,
        unit=unit,
        references=references,
        aliases=aliases,
        format=format_,
        precision=precision,
        category=category,
        icon=icon,
        allowed_operations=allowed_operations or ["direct_value", "sum", "latest"],
        semantic_status=semantic_status,
        description=description,
    )


def default_indicator_definitions() -> list[dict[str, Any]]:
    definitions = [
        _definition(
            "pesquisadores_ativos",
            f"{PESQUISADORES_LABEL} ativos",
            "pessoas",
            ["01", "05"],
            ["pesquisadores", "pesquisadores ativos", "pessoas pesquisadoras"],
            category="Comunidade cientifica",
            icon="people",
        ),
        _definition(
            "grupos_pesquisa",
            GRUPOS_PESQUISA_LABEL,
            "grupos",
            ["01"],
            ["grupos de pesquisa", "grupo pesquisa", "rede de pesquisa"],
            category="Comunidade cientifica",
            icon="network",
        ),
        _definition(
            "programas_pos_graduacao",
            "Programas de pós-graduação",
            "programas",
            ["01"],
            ["programas de pos graduacao", "pos graduacao", "programas pg"],
            category="Formacao",
            icon="graduation_cap",
        ),
        _definition(
            "instituicoes_ensino_pesquisa",
            "Instituições de ensino e pesquisa",
            "instituições",
            ["01"],
            ["instituicoes", "instituicoes de ensino", "instituicoes de pesquisa"],
            category="Instituicoes",
            icon="university",
        ),
        _definition(
            "producao_cientifica_total",
            "Produções científicas registradas",
            "produções",
            ["01", "02"],
            ["producao cientifica", "producoes cientificas registradas", "total cientifico"],
            category="Producao cientifica",
            icon="book",
        ),
        _definition(
            "municipios_pesquisadores_atuando",
            "Municípios com pesquisadores atuando",
            "municípios",
            ["01"],
            ["municipios com pesquisadores atuando", "municipios com pesquisadores", "municipios"],
            category="Alcance territorial",
            icon="map_pin",
        ),
        _definition(
            "pesquisadores_doutorado_percentual",
            f"{PESQUISADORES_LABEL} com doutorado",
            "percentual",
            ["01", "05"],
            ["percentual doutorado", "tem doutorado", "% doutorado"],
            category="Formacao",
            icon="diploma",
            format_="percent_pt_br",
            precision=2,
            allowed_operations=["direct_value", "percentage", "latest"],
        ),
        _definition(
            "bolsistas_produtividade_total",
            f"{PESQUISADORES_LABEL} com bolsa de produtividade",
            "pessoas",
            ["01", "04"],
            ["bolsa de produtividade", "bolsistas produtividade", "produtividade cnpq", "com bolsa produtividade"],
            category="Excelencia",
            icon="award",
        ),
        _definition(
            "producao_tecnica_total",
            "Produções técnicas registradas",
            "produções",
            ["01", "02", "03"],
            ["producao tecnica", "producoes tecnicas", "producoes tecnicas registradas", "total tecnico"],
            category="Producao tecnica",
            icon="document_gear",
        ),
        _definition("artigos_cientificos", "Artigos científicos", "produções", ["02"], ["artigos", "artigos cientificos"], category="Producao cientifica", icon="document"),
        _definition("trabalhos_eventos", "Trabalhos em eventos", "produções", ["02"], ["trabalhos em eventos", "eventos"], category="Producao cientifica", icon="presentation"),
        _definition("capitulos_livro", "Capítulos de livro", "produções", ["02"], ["capitulos de livro", "capitulos"], category="Producao cientifica", icon="book_open"),
        _definition("livros", "Livros", "produções", ["02"], ["livros"], category="Producao cientifica", icon="book"),
        _definition("textos_revista", "Textos em revista", "produções", ["02"], ["textos em revista", "revista"], category="Producao cientifica", icon="newspaper"),
        _definition("relatorios_tecnicos", "Relatórios técnicos", "produções", ["02", "03"], ["relatorios tecnicos", "relatorios"], category="Producao tecnica", icon="document_award"),
        _definition("programas_computador", "Programas de computador (software)", "produções", ["02", "03"], ["programas de computador", "software", "softwares"], category="Producao tecnica", icon="code"),
        _definition("depositos_patentes", "Depósitos de patentes", "depósitos", ["02", "03"], ["depositos de patentes", "patentes"], category="Producao tecnica", icon="document_lightbulb"),
        _definition("registros_marcas", "Registros de marcas", "registros", ["02", "03"], ["registros de marcas", "marcas"], category="Producao tecnica", icon="registered"),
        _definition("bolsistas_pq", "Bolsistas de Produtividade em Pesquisa (PQ)", "pessoas", ["04"], ["bolsistas pq", "produtividade em pesquisa", "pq"], category="Excelencia", icon="search_book"),
        _definition("bolsistas_dt", "Bolsistas de Desenvolvimento Tecnológico (DT)", "pessoas", ["04"], ["bolsistas dt", "desenvolvimento tecnologico", "dt"], category="Excelencia", icon="lightbulb_gear"),
        _definition("pesquisadores_doutorado", f"{PESQUISADORES_LABEL} com doutorado", "pessoas", ["05"], ["doutorado", "pesquisadores doutorado"], category="Formacao", icon="graduation_cap"),
        _definition("pesquisadores_mestrado", f"{PESQUISADORES_LABEL} com mestrado", "pessoas", ["05"], ["mestrado", "pesquisadores mestrado"], category="Formacao", icon="graduation_cap"),
        _definition("pesquisadores_especializacao", f"{PESQUISADORES_LABEL} com especialização", "pessoas", ["05"], ["especializacao", "pesquisadores especializacao"], category="Formacao", icon="diploma"),
    ]
    return [item.to_dict() for item in definitions]


def normalize_indicator_definition(definition: dict[str, Any]) -> dict[str, Any]:
    item = deepcopy(definition)
    item["id"] = re.sub(r"[^a-z0-9_]+", "_", str(item.get("id") or "").strip().lower()).strip("_")
    item["label"] = str(item.get("label") or "").strip()
    item["unit"] = str(item.get("unit") or "").strip()
    item["references"] = [str(value).strip() for value in item.get("references") or [] if str(value).strip()]
    item["aliases"] = [str(value).strip() for value in item.get("aliases") or [] if str(value).strip()]
    item["format"] = str(item.get("format") or "integer_pt_br").strip()
    item["precision"] = int(item.get("precision") or 0)
    item["category"] = str(item.get("category") or "Geral").strip()
    item["icon"] = str(item.get("icon") or "circle").strip()
    item["allowed_operations"] = [str(value).strip() for value in item.get("allowed_operations") or ["direct_value"] if str(value).strip()]
    item["semantic_status"] = str(item.get("semantic_status") or "pendente").strip()
    item["description"] = str(item.get("description") or "").strip()
    item["definition_version"] = int(item.get("definition_version") or 1)
    return item


def catalog_by_id(definitions: list[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    return {
        item["id"]: item
        for item in [normalize_indicator_definition(value) for value in (definitions or default_indicator_definitions())]
        if item.get("id")
    }


def validate_indicator_definition(definition: dict[str, Any]) -> list[str]:
    item = normalize_indicator_definition(definition)
    errors = []
    if not item["id"]:
        errors.append("id ausente")
    if not item["label"]:
        errors.append("rotulo ausente")
    if not item["unit"]:
        errors.append("unidade ausente")
    if not item["allowed_operations"]:
        errors.append("operacoes permitidas ausentes")
    return errors


def suggest_indicator_id(label: Any, definitions: list[dict[str, Any]] | None = None) -> str:
    needle = _norm(label)
    if not needle:
        return ""
    for item in catalog_by_id(definitions).values():
        candidates = [item["id"], item["label"], *item.get("aliases", [])]
        if needle in {_norm(candidate) for candidate in candidates}:
            return item["id"]
    for item in catalog_by_id(definitions).values():
        if any(needle in _norm(candidate) or _norm(candidate) in needle for candidate in [item["label"], *item.get("aliases", [])]):
            return item["id"]
    return ""

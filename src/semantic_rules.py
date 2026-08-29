from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import re
import unicodedata
from typing import Any

import yaml

from .icon_registry import DEFAULT_COLOR, DEFAULT_ICON, normalize_hex_color, normalize_icon_name


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES_PATH = ROOT / "config" / "semantic_rules.yaml"
CUSTOM_RULES_PATH = ROOT / "config" / "custom_semantic_rules.yaml"

STOPWORDS = {
    "a", "as", "o", "os", "de", "da", "das", "do", "dos", "e", "em", "com",
    "por", "para", "no", "na", "nos", "nas", "um", "uma", "total", "numero",
    "número", "quantidade", "qtd", "indicador", "indicadores",
}
ABBREVIATIONS = {
    "qtd": "quantidade",
    "qtde": "quantidade",
    "mun": "municipio",
    "munic": "municipio",
    "inst": "instituicao",
    "lab": "laboratorio",
    "pos": "pos graduacao",
    "pós": "pos graduacao",
}


@dataclass(frozen=True)
class RuleMatch:
    rule_id: str
    section: str
    icon: str
    color: str
    confidence: int
    reason: str
    priority: int
    preferred_label: str
    category: str
    compatible_operations: tuple[str, ...]


def normalize_text(value: Any) -> str:
    text = str(value or "").strip().casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9%+]+", " ", text)
    words = []
    for word in text.split():
        word = ABBREVIATIONS.get(word, word)
        words.extend(word.split())
    return re.sub(r"\s+", " ", " ".join(words)).strip()


def singularize(word: str) -> str:
    if len(word) > 4 and word.endswith("oes"):
        return word[:-3] + "ao"
    if len(word) > 4 and word.endswith("ais"):
        return word[:-3] + "al"
    if len(word) > 5 and word.endswith("entes"):
        return word[:-1]
    if len(word) > 3 and word.endswith("es"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s"):
        return word[:-1]
    return word


def semantic_tokens(value: Any) -> list[str]:
    tokens = []
    for token in normalize_text(value).split():
        base = singularize(token)
        if base and base not in STOPWORDS:
            tokens.append(base)
    return tokens


def _normalized_phrases(values: list[str] | tuple[str, ...] | None) -> list[str]:
    return [normalize_text(value) for value in values or [] if normalize_text(value)]


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_rulebook(
    default_path: str | Path = DEFAULT_RULES_PATH,
    custom_path: str | Path = CUSTOM_RULES_PATH,
) -> dict[str, Any]:
    default = _load_yaml(Path(default_path))
    custom = _load_yaml(Path(custom_path))
    merged = deepcopy(default)
    merged.setdefault("rules", {})
    custom_rules = custom.get("rules") or {}
    for rule_id, rule in custom_rules.items():
        if rule is None or rule.get("enabled", True) is False:
            continue
        merged["rules"][rule_id] = {**deepcopy(rule), "custom": True}
    return merged


def _term_score(text: str, tokens: set[str], terms: list[str], kind: str) -> tuple[int, str]:
    best_score = 0
    best_reason = ""
    for term in terms:
        normalized = normalize_text(term)
        term_tokens = set(semantic_tokens(term))
        if not normalized:
            continue
        if normalized == text:
            score = 96 if kind == "term" else 90
            reason = f"{kind} exato: {term}"
        elif normalized and normalized in text:
            score = 88 if kind == "term" else 82
            reason = f"{kind} contido: {term}"
        elif term_tokens and term_tokens.issubset(tokens):
            score = 84 if kind == "term" else 78
            reason = f"{kind} por palavras: {term}"
        else:
            similarity = SequenceMatcher(None, normalized, text).ratio()
            overlap = len(tokens.intersection(term_tokens)) / max(1, len(term_tokens))
            score = int(max(similarity * 72, overlap * 76))
            reason = f"{kind} aproximado: {term}"
        if score > best_score:
            best_score = score
            best_reason = reason
    return best_score, best_reason


def match_rule(label: str, rulebook: dict[str, Any] | None = None) -> RuleMatch:
    rulebook = rulebook or load_rulebook()
    defaults = rulebook.get("defaults") or {}
    default_match = RuleMatch(
        rule_id="fallback",
        section=str(defaults.get("section") or "Indicadores"),
        icon=normalize_icon_name(defaults.get("icon") or DEFAULT_ICON),
        color=normalize_hex_color(defaults.get("color") or DEFAULT_COLOR),
        confidence=35,
        reason="nenhuma regra semântica atingiu confiança mínima",
        priority=0,
        preferred_label="",
        category="geral",
        compatible_operations=("direct_value",),
    )
    text = normalize_text(label)
    tokens = set(semantic_tokens(label))
    best = default_match

    for rule_id, rule in (rulebook.get("rules") or {}).items():
        negative_terms = _normalized_phrases(rule.get("negative_terms"))
        if any(term and term in text for term in negative_terms):
            continue
        term_score, term_reason = _term_score(text, tokens, _normalized_phrases(rule.get("terms")), "termo")
        synonym_score, synonym_reason = _term_score(text, tokens, _normalized_phrases(rule.get("synonyms")), "sinônimo")
        base_score, reason = (term_score, term_reason) if term_score >= synonym_score else (synonym_score, synonym_reason)
        if base_score <= 0:
            continue
        priority = int(rule.get("priority") or 0)
        confidence = min(100, int(base_score + min(12, priority // 12)))
        if rule.get("custom"):
            confidence = min(100, confidence + 7)
            priority += 1000
        minimum = int(rule.get("confidence_minimum") or defaults.get("confidence_minimum") or 60)
        if confidence < minimum:
            continue
        candidate = RuleMatch(
            rule_id=str(rule_id),
            section=str(rule.get("section") or defaults.get("section") or "Indicadores"),
            icon=normalize_icon_name(rule.get("icon") or defaults.get("icon") or DEFAULT_ICON),
            color=normalize_hex_color(rule.get("color") or defaults.get("color") or DEFAULT_COLOR),
            confidence=confidence,
            reason=f"{reason}; prioridade {priority}",
            priority=priority,
            preferred_label=str(rule.get("preferred_label") or ""),
            category=str(rule.get("category") or ""),
            compatible_operations=tuple(rule.get("compatible_operations") or ["direct_value"]),
        )
        if (candidate.confidence, candidate.priority) > (best.confidence, best.priority):
            best = candidate
    return best


def title_case_label(value: Any) -> str:
    original = str(value or "").strip()
    if not original:
        return ""
    lower_words = {"de", "da", "das", "do", "dos", "e", "em", "com", "por", "para"}
    words = []
    for index, word in enumerate(original.split()):
        if index > 0 and normalize_text(word) in lower_words:
            words.append(word.casefold())
        elif word.isupper() and len(word) <= 4:
            words.append(word)
        else:
            words.append(word[:1].upper() + word[1:].casefold())
    return " ".join(words)


def confidence_level(confidence: int) -> str:
    if confidence >= 85:
        return "alta"
    if confidence >= 60:
        return "média"
    return "baixa"


def save_custom_rule(rule_id: str, rule: dict[str, Any], path: str | Path = CUSTOM_RULES_PATH) -> None:
    target = Path(path)
    data = _load_yaml(target) or {"version": 1, "rules": {}}
    data.setdefault("version", 1)
    data.setdefault("rules", {})
    normalized = deepcopy(rule)
    normalized.setdefault("enabled", True)
    data["rules"][rule_id] = normalized
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

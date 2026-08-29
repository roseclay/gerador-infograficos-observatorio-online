from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Any


QUALIFIER_RE = re.compile(r"(^\s*\+)|(\+\s*$)|(%\s*$)|\b(mil|milhao|milhoes|milhão|milhões)\b", re.IGNORECASE)


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"nan", "none", "null"}


def has_textual_qualifier(value: Any) -> bool:
    return bool(QUALIFIER_RE.search(str(value)))


def parse_brazilian_number(value: Any) -> Decimal:
    """Parse a Brazilian-formatted number without losing decimal precision."""
    if is_missing(value):
        raise InvalidOperation("valor ausente")

    text = str(value).strip().lower()
    multiplier = Decimal("1")
    if "milhões" in text or "milhoes" in text or "milhão" in text or "milhao" in text:
        multiplier = Decimal("1000000")
        text = re.sub(r"\b(milhões|milhoes|milhão|milhao)\b", "", text)
    elif re.search(r"\bmil\b", text):
        multiplier = Decimal("1000")
        text = re.sub(r"\bmil\b", "", text)

    text = text.replace("r$", "")
    text = text.replace("%", "")
    text = text.replace("+", "")
    text = text.replace("\u00a0", " ")
    text = text.strip()
    text = re.sub(r"[^0-9,.\-]", "", text)
    if text in {"", "-", ",", "."}:
        raise InvalidOperation("valor numerico invalido")

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif "." in text:
        parts = text.split(".")
        if len(parts) > 1 and all(len(part) == 3 for part in parts[1:]) and len(parts[0]) <= 3:
            text = "".join(parts)

    return Decimal(text) * multiplier


def format_brazilian_number(value: Any, decimals: int = 0) -> str:
    number = parse_brazilian_number(value)
    decimals = max(0, int(decimals or 0))
    quantum = Decimal("1") if decimals == 0 else Decimal("1").scaleb(-decimals)
    number = number.quantize(quantum, rounding=ROUND_HALF_UP)
    sign = "-" if number < 0 else ""
    number = abs(number)
    integer_part, _, decimal_part = f"{number:f}".partition(".")
    groups = []
    while integer_part:
        groups.append(integer_part[-3:])
        integer_part = integer_part[:-3]
    formatted = ".".join(reversed(groups or ["0"]))
    if decimals:
        decimal_part = (decimal_part + ("0" * decimals))[:decimals]
        formatted = f"{formatted},{decimal_part}"
    return f"{sign}{formatted}"


def format_display_value(value: Any, decimals: int = 0, prefix: str = "", suffix: str = "", preserve_qualified_text: bool = True) -> str:
    if is_missing(value):
        return ""
    text = str(value).strip()
    if preserve_qualified_text and has_textual_qualifier(text):
        return f"{prefix}{text}{suffix}"
    try:
        return f"{prefix}{format_brazilian_number(text, decimals)}{suffix}"
    except (InvalidOperation, ValueError):
        return f"{prefix}{text}{suffix}"


def normalize_public_text(value: Any) -> str:
    return "" if value is None else str(value).strip()

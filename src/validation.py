from __future__ import annotations

from typing import Any

from .formatting import is_missing


def rect_right(rect: dict[str, float]) -> float:
    return float(rect["x"]) + float(rect["w"])


def rect_bottom(rect: dict[str, float]) -> float:
    return float(rect["y"]) + float(rect["h"])


def rect_within(rect: dict[str, float], width: int, height: int) -> bool:
    return float(rect["x"]) >= 0 and float(rect["y"]) >= 0 and rect_right(rect) <= width and rect_bottom(rect) <= height


def rectangles_overlap(first: dict[str, float], second: dict[str, float], padding: float = 0) -> bool:
    return not (
        rect_right(first) + padding <= float(second["x"])
        or rect_right(second) + padding <= float(first["x"])
        or rect_bottom(first) + padding <= float(second["y"])
        or rect_bottom(second) + padding <= float(first["y"])
    )


def validate_text_bounds(text_boxes: list[dict[str, Any]], width: int, height: int) -> list[str]:
    errors = []
    for box in text_boxes:
        if not box.get("fits", True):
            errors.append(f"texto nao coube na area segura: {box.get('id')}")
        if not rect_within(box, width, height):
            errors.append(f"texto fora dos limites da imagem: {box.get('id')}")
    return errors


def validate_no_overlaps(rectangles: list[dict[str, Any]], padding: float = 0) -> list[str]:
    errors = []
    for index, first in enumerate(rectangles):
        for second in rectangles[index + 1:]:
            if rectangles_overlap(first, second, padding=padding):
                errors.append(f"sobreposicao entre {first.get('id')} e {second.get('id')}")
    return errors


def validate_required_metadata(metadata: dict[str, Any]) -> list[str]:
    required = ["header", "title"]
    return [f"campo obrigatorio ausente: {field}" for field in required if is_missing(metadata.get(field))]


def validate_metric_configs(configs: list[dict[str, Any]], columns: list[str]) -> list[str]:
    errors = []
    for index, config in enumerate(configs, start=1):
        if config.get("enabled", True) is False:
            continue
        configured_label = config.get("label")
        label = configured_label or config.get("id") or f"indicador {index}"
        column = config.get("column")
        operation = config.get("operation")
        if is_missing(configured_label):
            errors.append(f"indicador {index}: rotulo publico ausente")
        if is_missing(operation):
            errors.append(f"{label}: operacao ausente")
        numerator = config.get("numerator_column")
        denominator = config.get("denominator_column")
        requires_column = operation not in {"count"} and not (operation == "percentage" and numerator and denominator)
        if requires_column and column not in columns:
            errors.append(f"{label}: coluna '{column}' nao encontrada")
        if numerator and numerator not in columns:
            errors.append(f"{label}: coluna de numerador '{numerator}' nao encontrada")
        if denominator and denominator not in columns:
            errors.append(f"{label}: coluna de denominador '{denominator}' nao encontrada")
    return errors

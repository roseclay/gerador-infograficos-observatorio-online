from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageColor, ImageDraw, ImageOps

from src.icon_registry import DEFAULT_COLOR, normalize_hex_color, render_icon
from src.semantic_rules import normalize_text


@dataclass(frozen=True)
class IconPlacementResult:
    icon_key: str
    path: str
    fallback_used: bool
    note: str


ICON_ASSET_BY_NAME = {
    "people": "pesquisadores",
    "users": "pesquisadores",
    "network": "grupos_pesquisa",
    "graduation": "pos_graduacao",
    "cap": "pos_graduacao",
    "institution": "instituicoes",
    "building": "instituicoes",
    "globe": "producao_cientifica",
    "pin": "municipios",
    "map": "municipios",
    "medal": "doutorado",
    "ribbon": "doutorado",
    "award": "bolsa_produtividade",
    "award_user": "bolsa_produtividade",
    "document": "producao_tecnica",
    "code": "producao_tecnica",
    "patent": "producao_tecnica",
}

SEMANTIC_ICON_RULES = [
    ("grupos_pesquisa", ("grupo pesquisa", "rede pesquisa", "conexao")),
    ("pos_graduacao", ("pos graduacao", "pós graduação", "programa pos", "formacao")),
    ("instituicoes", ("instituicao", "ensino pesquisa", "universidade")),
    ("producao_cientifica", ("producao cientifica", "publicacao", "artigo")),
    ("municipios", ("municipio", "territorio", "mapa", "localizacao")),
    ("doutorado", ("doutorado", "doutor")),
    ("bolsa_produtividade", ("bolsa produtividade", "produtividade", "pesquisador premiado")),
    ("producao_tecnica", ("producao tecnica", "patente", "software")),
    ("pesquisadores", ("pesquisador", "docente", "pessoa")),
]

ICON_ADJUSTMENTS = {
    "pesquisadores": (1.08, 0, 2),
    "grupos_pesquisa": (1.06, 0, 0),
    "pos_graduacao": (1.10, -4, 2),
    "instituicoes": (1.08, 0, 4),
    "producao_cientifica": (1.15, 0, 0),
    "municipios": (1.12, 2, 0),
    "doutorado": (1.04, -2, 0),
    "bolsa_produtividade": (1.08, 0, 2),
    "producao_tecnica": (1.06, 0, 0),
}


def _metric_field(metric: Any, field: str, default: Any = None) -> Any:
    if isinstance(metric, dict):
        return metric.get(field, default)
    return getattr(metric, field, default)


def resolve_icon_key(metric: Any) -> str | None:
    icon_name = normalize_text(_metric_field(metric, "icon", ""))
    if icon_name in ICON_ASSET_BY_NAME:
        return ICON_ASSET_BY_NAME[icon_name]
    label = normalize_text(_metric_field(metric, "label", ""))
    for icon_key, terms in SEMANTIC_ICON_RULES:
        if any(normalize_text(term) in label for term in terms):
            return icon_key
    return None


def _tint_icon(icon: Image.Image, color: str) -> Image.Image:
    normalized = normalize_hex_color(color, DEFAULT_COLOR)
    if normalized == DEFAULT_COLOR:
        return icon
    alpha = icon.getchannel("A")
    gray = ImageOps.grayscale(icon.convert("RGB"))
    target = Image.new("RGB", icon.size, ImageColor.getrgb(normalized))
    base = Image.new("RGB", icon.size, "#061E55")
    mixed = Image.blend(base, target, 0.85)
    shaded = Image.composite(mixed, target, gray.point(lambda value: min(255, int(value * 1.1))))
    rgba = shaded.convert("RGBA")
    rgba.putalpha(alpha)
    return rgba


def paste_template_icon(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    metric: Any,
    box: tuple[int, int, int, int],
    icons_dir: Path,
) -> IconPlacementResult:
    icon_key = resolve_icon_key(metric)
    color = normalize_hex_color(str(_metric_field(metric, "color", DEFAULT_COLOR) or DEFAULT_COLOR))
    if icon_key:
        icon_path = icons_dir / f"{icon_key}.png"
        if icon_path.exists():
            icon = Image.open(icon_path).convert("RGBA")
            icon = _tint_icon(icon, color)
            scale, dx, dy = ICON_ADJUSTMENTS.get(icon_key, (1.0, 0, 0))
            target = (max(1, int(box[2] * scale)), max(1, int(box[3] * scale)))
            icon.thumbnail(target, Image.Resampling.LANCZOS)
            x = box[0] + (box[2] - icon.width) // 2 + dx
            y = box[1] + (box[3] - icon.height) // 2 + dy
            canvas.alpha_composite(icon, (x, y))
            return IconPlacementResult(icon_key, str(icon_path), False, "ícone do template")

    render_icon(draw, str(_metric_field(metric, "icon", "circle") or "circle"), box, color)
    return IconPlacementResult(str(_metric_field(metric, "icon", "circle") or "circle"), "", True, "Ícone de fallback — revisão recomendada")

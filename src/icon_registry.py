from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
import re
from typing import Any

from PIL import Image, ImageDraw


DEFAULT_ICON = "circle"
DEFAULT_COLOR = "#0057B8"

ICON_CATEGORIES = [
    "todos",
    "pessoas",
    "pesquisa",
    "educação",
    "instituições",
    "localização",
    "documentos",
    "tecnologia",
    "inovação",
    "propriedade intelectual",
    "natureza",
]

INSTITUTIONAL_PALETTE = [
    ("#0057B8", "Azul institucional"),
    ("#FFD100", "Amarelo Bahia"),
    ("#009739", "Verde Bahia"),
    ("#EF3340", "Vermelho Bahia"),
    ("#00A3E0", "Azul claro"),
    ("#7A3E9D", "Violeta"),
    ("#334155", "Grafite"),
    ("#64748B", "Cinza azulado"),
    ("#B28A8A", "Rosado neutro"),
    ("#2F855A", "Verde escuro"),
]


@dataclass(frozen=True)
class IconDefinition:
    name: str
    label: str
    category: str
    aliases: tuple[str, ...] = ()


ICON_REGISTRY: tuple[IconDefinition, ...] = (
    IconDefinition("circle", "Círculo", "todos"),
    IconDefinition("people", "Pessoas", "pessoas", ("users",)),
    IconDefinition("award", "Pessoa premiada", "pessoas", ("award_user", "badge_user")),
    IconDefinition("network", "Rede", "pesquisa", ("nodes",)),
    IconDefinition("microscope", "Microscópio", "pesquisa"),
    IconDefinition("flask", "Laboratório", "pesquisa"),
    IconDefinition("graduation", "Formação", "educação", ("cap", "educacao")),
    IconDefinition("book", "Livro", "educação"),
    IconDefinition("institution", "Instituição", "instituições", ("building", "instituicao")),
    IconDefinition("globe", "Globo", "localização", ("world",)),
    IconDefinition("pin", "Marcador", "localização", ("map-pin",)),
    IconDefinition("map", "Mapa", "localização"),
    IconDefinition("document", "Documento", "documentos", ("file",)),
    IconDefinition("medal", "Medalha", "documentos", ("ribbon", "percent")),
    IconDefinition("computer", "Computador", "tecnologia"),
    IconDefinition("code", "Código", "tecnologia"),
    IconDefinition("database", "Base de dados", "tecnologia"),
    IconDefinition("bulb", "Ideia", "inovação"),
    IconDefinition("gear", "Processo", "inovação"),
    IconDefinition("patent", "Patente", "propriedade intelectual"),
    IconDefinition("tag", "Registro", "propriedade intelectual"),
    IconDefinition("leaf", "Natureza", "natureza"),
)

_ICON_BY_NAME = {icon.name: icon for icon in ICON_REGISTRY}
_ALIASES = {
    alias: icon.name
    for icon in ICON_REGISTRY
    for alias in icon.aliases
}
_HEX_RE = re.compile(r"^#?(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def normalize_icon_name(name: str | None) -> str:
    candidate = str(name or "").strip().lower()
    if candidate in _ICON_BY_NAME:
        return candidate
    if candidate in _ALIASES:
        return _ALIASES[candidate]
    return DEFAULT_ICON


def icon_definition(name: str | None) -> IconDefinition:
    return _ICON_BY_NAME[normalize_icon_name(name)]


def icon_label(name: str | None) -> str:
    return icon_definition(name).label


def icons_for_gallery(category: str = "todos", query: str = "") -> list[IconDefinition]:
    selected_category = str(category or "todos").strip().lower()
    needle = str(query or "").strip().lower()
    result = []
    for icon in ICON_REGISTRY:
        in_category = selected_category in {"", "todos"} or icon.category == selected_category
        searchable = " ".join((icon.name, icon.label, icon.category, *icon.aliases)).lower()
        if in_category and (not needle or needle in searchable):
            result.append(icon)
    return result


def validate_hex_color(value: str | None) -> bool:
    return bool(_HEX_RE.match(str(value or "").strip()))


def normalize_hex_color(value: str | None, fallback: str = DEFAULT_COLOR) -> str:
    candidate = str(value or "").strip()
    if not validate_hex_color(candidate):
        return fallback
    candidate = candidate.upper()
    if not candidate.startswith("#"):
        candidate = f"#{candidate}"
    if len(candidate) == 4:
        candidate = "#" + "".join(channel * 2 for channel in candidate[1:])
    return candidate


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    normalized = normalize_hex_color(color, DEFAULT_COLOR).lstrip("#")
    return tuple(int(normalized[index:index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


def _line_colors(color: str) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    rgb = _hex_to_rgb(color)
    light = tuple(min(255, int(channel + (255 - channel) * 0.78)) for channel in rgb)
    return (*rgb, 255), (*light, 255)


def _star_points(cx: float, cy: float, outer: float, inner: float) -> list[tuple[float, float]]:
    points = []
    for index in range(10):
        radius = outer if index % 2 == 0 else inner
        angle = -90 + index * 36
        radians = angle * math.pi / 180
        points.append((cx + radius * math.cos(radians), cy + radius * math.sin(radians)))
    return points


def render_icon(draw: ImageDraw.ImageDraw, name: str, box: tuple[int, int, int, int], color: str) -> None:
    x, y, w, h = box
    stroke = max(4, int(min(w, h) * 0.055))
    line, fill = _line_colors(color)
    cx = x + w / 2
    cy = y + h / 2
    r = min(w, h) / 2 - stroke
    icon = normalize_icon_name(name)

    def ellipse(center_x: float, center_y: float, radius: float, fill_color=None) -> None:
        draw.ellipse(
            (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
            outline=line,
            width=stroke,
            fill=fill_color,
        )

    if icon == "people":
        ellipse(x + w * 0.36, y + h * 0.34, r * 0.27, fill)
        ellipse(x + w * 0.64, y + h * 0.34, r * 0.27, fill)
        draw.arc((x + w * 0.15, y + h * 0.42, x + w * 0.57, y + h * 0.93), 200, 340, fill=line, width=stroke)
        draw.arc((x + w * 0.43, y + h * 0.42, x + w * 0.85, y + h * 0.93), 200, 340, fill=line, width=stroke)
    elif icon == "award":
        ellipse(cx - r * 0.12, y + h * 0.28, r * 0.25, fill)
        draw.arc((cx - r * 0.58, y + h * 0.42, cx + r * 0.35, y + h * 0.95), 200, 340, fill=line, width=stroke)
        ellipse(cx + r * 0.42, y + h * 0.66, r * 0.24, fill)
        draw.polygon(_star_points(cx + r * 0.42, y + h * 0.66, r * 0.16, r * 0.07), fill=line)
    elif icon == "network":
        points = [(x + w * 0.5, y + h * 0.2), (x + w * 0.25, y + h * 0.7), (x + w * 0.75, y + h * 0.68)]
        draw.line((points[0], points[1]), fill=line, width=stroke)
        draw.line((points[0], points[2]), fill=line, width=stroke)
        draw.line((points[1], points[2]), fill=line, width=stroke)
        for point in points:
            ellipse(point[0], point[1], r * 0.22, fill)
    elif icon == "microscope":
        draw.line((x + w * 0.36, y + h * 0.22, x + w * 0.62, y + h * 0.48), fill=line, width=stroke)
        draw.rounded_rectangle((x + w * 0.25, y + h * 0.14, x + w * 0.46, y + h * 0.34), radius=8, outline=line, width=stroke, fill=fill)
        draw.arc((x + w * 0.36, y + h * 0.36, x + w * 0.82, y + h * 0.82), 110, 300, fill=line, width=stroke)
        draw.line((x + w * 0.52, y + h * 0.78, x + w * 0.52, y + h * 0.88), fill=line, width=stroke)
        draw.line((x + w * 0.25, y + h * 0.88, x + w * 0.78, y + h * 0.88), fill=line, width=stroke)
    elif icon == "flask":
        draw.line((x + w * 0.42, y + h * 0.18, x + w * 0.42, y + h * 0.43), fill=line, width=stroke)
        draw.line((x + w * 0.58, y + h * 0.18, x + w * 0.58, y + h * 0.43), fill=line, width=stroke)
        draw.line((x + w * 0.42, y + h * 0.43, x + w * 0.22, y + h * 0.84), fill=line, width=stroke)
        draw.line((x + w * 0.58, y + h * 0.43, x + w * 0.78, y + h * 0.84), fill=line, width=stroke)
        draw.arc((x + w * 0.22, y + h * 0.70, x + w * 0.78, y + h * 0.98), 180, 360, fill=line, width=stroke)
        draw.line((x + w * 0.34, y + h * 0.70, x + w * 0.66, y + h * 0.70), fill=line, width=stroke)
    elif icon == "graduation":
        draw.polygon([(x + w * 0.12, y + h * 0.38), (cx, y + h * 0.16), (x + w * 0.88, y + h * 0.38), (cx, y + h * 0.58)], outline=line, fill=fill)
        draw.line((x + w * 0.28, y + h * 0.52, x + w * 0.28, y + h * 0.72), fill=line, width=stroke)
        draw.line((x + w * 0.25, y + h * 0.72, x + w * 0.36, y + h * 0.72), fill=line, width=stroke)
        draw.rounded_rectangle((x + w * 0.22, y + h * 0.68, x + w * 0.78, y + h * 0.86), radius=8, outline=line, width=stroke, fill=fill)
    elif icon == "book":
        draw.rounded_rectangle((x + w * 0.18, y + h * 0.18, x + w * 0.50, y + h * 0.82), radius=10, outline=line, width=stroke, fill=fill)
        draw.rounded_rectangle((x + w * 0.50, y + h * 0.18, x + w * 0.82, y + h * 0.82), radius=10, outline=line, width=stroke, fill=fill)
        draw.line((cx, y + h * 0.24, cx, y + h * 0.86), fill=line, width=stroke)
        draw.line((x + w * 0.28, y + h * 0.36, x + w * 0.43, y + h * 0.36), fill=line, width=max(2, stroke // 2))
        draw.line((x + w * 0.57, y + h * 0.36, x + w * 0.72, y + h * 0.36), fill=line, width=max(2, stroke // 2))
    elif icon == "institution":
        draw.polygon([(x + w * 0.12, y + h * 0.36), (cx, y + h * 0.12), (x + w * 0.88, y + h * 0.36)], outline=line, fill=fill)
        draw.line((x + w * 0.16, y + h * 0.4, x + w * 0.84, y + h * 0.4), fill=line, width=stroke)
        for pct in (0.26, 0.42, 0.58, 0.74):
            draw.line((x + w * pct, y + h * 0.45, x + w * pct, y + h * 0.78), fill=line, width=stroke)
        draw.line((x + w * 0.14, y + h * 0.82, x + w * 0.86, y + h * 0.82), fill=line, width=stroke)
    elif icon == "globe":
        ellipse(cx, cy, r * 0.78, None)
        draw.arc((cx - r * 0.38, cy - r * 0.78, cx + r * 0.38, cy + r * 0.78), 90, 270, fill=line, width=stroke)
        draw.arc((cx - r * 0.38, cy - r * 0.78, cx + r * 0.38, cy + r * 0.78), 270, 90, fill=line, width=stroke)
        draw.line((cx - r * 0.76, cy, cx + r * 0.76, cy), fill=line, width=stroke)
        draw.line((cx, cy - r * 0.76, cx, cy + r * 0.76), fill=line, width=stroke)
    elif icon == "pin":
        ellipse(cx, y + h * 0.33, r * 0.28, fill)
        draw.line((cx, y + h * 0.62, cx, y + h * 0.88), fill=line, width=stroke)
        draw.arc((x + w * 0.2, y + h * 0.62, x + w * 0.8, y + h * 0.95), 20, 160, fill=line, width=stroke)
    elif icon == "map":
        draw.line((x + w * 0.16, y + h * 0.24, x + w * 0.36, y + h * 0.16, x + w * 0.62, y + h * 0.28, x + w * 0.84, y + h * 0.20), fill=line, width=stroke)
        draw.line((x + w * 0.16, y + h * 0.24, x + w * 0.16, y + h * 0.78, x + w * 0.36, y + h * 0.70, x + w * 0.62, y + h * 0.82, x + w * 0.84, y + h * 0.74, x + w * 0.84, y + h * 0.20), fill=line, width=stroke)
        draw.line((x + w * 0.36, y + h * 0.16, x + w * 0.36, y + h * 0.70), fill=line, width=max(2, stroke // 2))
        draw.line((x + w * 0.62, y + h * 0.28, x + w * 0.62, y + h * 0.82), fill=line, width=max(2, stroke // 2))
    elif icon == "document":
        draw.rounded_rectangle((x + w * 0.24, y + h * 0.14, x + w * 0.76, y + h * 0.86), radius=8, outline=line, width=stroke, fill=fill)
        draw.line((x + w * 0.36, y + h * 0.38, x + w * 0.64, y + h * 0.38), fill=line, width=stroke)
        draw.line((x + w * 0.36, y + h * 0.52, x + w * 0.64, y + h * 0.52), fill=line, width=stroke)
        draw.line((x + w * 0.36, y + h * 0.66, x + w * 0.55, y + h * 0.66), fill=line, width=stroke)
    elif icon == "medal":
        ellipse(cx, y + h * 0.36, r * 0.48, fill)
        draw.polygon([(cx - r * 0.22, y + h * 0.72), (cx - r * 0.02, y + h * 0.62), (cx + r * 0.08, y + h * 0.9)], outline=line, fill=fill)
        draw.polygon([(cx + r * 0.22, y + h * 0.72), (cx + r * 0.02, y + h * 0.62), (cx - r * 0.08, y + h * 0.9)], outline=line, fill=fill)
        draw.polygon(_star_points(cx, y + h * 0.36, r * 0.23, r * 0.1), fill=line)
    elif icon == "computer":
        draw.rounded_rectangle((x + w * 0.16, y + h * 0.2, x + w * 0.84, y + h * 0.66), radius=10, outline=line, width=stroke, fill=fill)
        draw.line((cx, y + h * 0.66, cx, y + h * 0.82), fill=line, width=stroke)
        draw.line((x + w * 0.34, y + h * 0.84, x + w * 0.66, y + h * 0.84), fill=line, width=stroke)
    elif icon == "code":
        draw.line((x + w * 0.36, y + h * 0.28, x + w * 0.18, cy, x + w * 0.36, y + h * 0.72), fill=line, width=stroke)
        draw.line((x + w * 0.64, y + h * 0.28, x + w * 0.82, cy, x + w * 0.64, y + h * 0.72), fill=line, width=stroke)
        draw.line((x + w * 0.54, y + h * 0.22, x + w * 0.46, y + h * 0.78), fill=line, width=stroke)
    elif icon == "database":
        draw.ellipse((x + w * 0.2, y + h * 0.16, x + w * 0.8, y + h * 0.38), outline=line, width=stroke, fill=fill)
        draw.rectangle((x + w * 0.2, y + h * 0.27, x + w * 0.8, y + h * 0.72), outline=None, fill=fill)
        draw.line((x + w * 0.2, y + h * 0.27, x + w * 0.2, y + h * 0.72), fill=line, width=stroke)
        draw.line((x + w * 0.8, y + h * 0.27, x + w * 0.8, y + h * 0.72), fill=line, width=stroke)
        draw.arc((x + w * 0.2, y + h * 0.61, x + w * 0.8, y + h * 0.83), 0, 180, fill=line, width=stroke)
        draw.arc((x + w * 0.2, y + h * 0.42, x + w * 0.8, y + h * 0.64), 0, 180, fill=line, width=max(2, stroke // 2))
    elif icon == "bulb":
        ellipse(cx, y + h * 0.36, r * 0.46, fill)
        draw.line((cx - r * 0.18, y + h * 0.68, cx + r * 0.18, y + h * 0.68), fill=line, width=stroke)
        draw.line((cx - r * 0.12, y + h * 0.80, cx + r * 0.12, y + h * 0.80), fill=line, width=stroke)
        draw.line((cx, y + h * 0.53, cx, y + h * 0.65), fill=line, width=stroke)
    elif icon == "gear":
        ellipse(cx, cy, r * 0.44, fill)
        ellipse(cx, cy, r * 0.16, None)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0), (-0.7, -0.7), (0.7, -0.7), (-0.7, 0.7), (0.7, 0.7)):
            draw.line((cx + dx * r * 0.48, cy + dy * r * 0.48, cx + dx * r * 0.72, cy + dy * r * 0.72), fill=line, width=stroke)
    elif icon == "patent":
        draw.rounded_rectangle((x + w * 0.24, y + h * 0.14, x + w * 0.76, y + h * 0.86), radius=8, outline=line, width=stroke, fill=fill)
        draw.arc((x + w * 0.38, y + h * 0.29, x + w * 0.65, y + h * 0.50), 270, 90, fill=line, width=stroke)
        draw.line((x + w * 0.38, y + h * 0.30, x + w * 0.38, y + h * 0.72), fill=line, width=stroke)
        draw.line((x + w * 0.38, y + h * 0.50, x + w * 0.62, y + h * 0.50), fill=line, width=stroke)
    elif icon == "tag":
        draw.polygon([(x + w * 0.22, y + h * 0.25), (x + w * 0.62, y + h * 0.18), (x + w * 0.82, y + h * 0.38), (x + w * 0.42, y + h * 0.78), (x + w * 0.20, y + h * 0.56)], outline=line, fill=fill)
        ellipse(x + w * 0.55, y + h * 0.34, r * 0.08, None)
    elif icon == "leaf":
        draw.ellipse((x + w * 0.2, y + h * 0.18, x + w * 0.78, y + h * 0.82), outline=line, width=stroke, fill=fill)
        draw.line((x + w * 0.34, y + h * 0.68, x + w * 0.70, y + h * 0.30), fill=line, width=stroke)
        draw.line((x + w * 0.46, y + h * 0.55, x + w * 0.56, y + h * 0.57), fill=line, width=max(2, stroke // 2))
    else:
        ellipse(cx, cy, r * 0.62, fill)


def icon_preview_image(name: str, color: str = DEFAULT_COLOR, size: int = 96) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(canvas, "RGBA")
    inset = max(8, size // 12)
    render_icon(draw, name, (inset, inset, size - inset * 2, size - inset * 2), color)
    return canvas


def apply_appearance_to_indicator(
    indicators: list[dict[str, Any]],
    indicator_id: str,
    *,
    icon: str | None = None,
    color: str | None = None,
) -> list[dict[str, Any]]:
    result = [deepcopy(item) for item in indicators]
    for item in result:
        if str(item.get("id")) != str(indicator_id):
            continue
        if icon is not None:
            item["icon"] = normalize_icon_name(icon)
        if color is not None:
            item["color"] = normalize_hex_color(color)
    return result


def apply_color_to_section(indicators: list[dict[str, Any]], section: str, color: str) -> list[dict[str, Any]]:
    normalized = normalize_hex_color(color)
    target = str(section or "").strip()
    result = [deepcopy(item) for item in indicators]
    for item in result:
        if str(item.get("section", "")).strip() == target:
            item["color"] = normalized
    return result


def apply_color_to_all(indicators: list[dict[str, Any]], color: str) -> list[dict[str, Any]]:
    normalized = normalize_hex_color(color)
    result = [deepcopy(item) for item in indicators]
    for item in result:
        item["color"] = normalized
    return result


def apply_appearance_to_section(
    indicators: list[dict[str, Any]],
    section: str,
    *,
    icon: str | None = None,
    color: str | None = None,
) -> list[dict[str, Any]]:
    target = str(section or "").strip()
    normalized_icon = normalize_icon_name(icon) if icon is not None else None
    normalized_color = normalize_hex_color(color) if color is not None else None
    result = [deepcopy(item) for item in indicators]
    for item in result:
        if str(item.get("section", "")).strip() != target:
            continue
        if normalized_icon is not None:
            item["icon"] = normalized_icon
        if normalized_color is not None:
            item["color"] = normalized_color
    return result


def apply_appearance_to_all(
    indicators: list[dict[str, Any]],
    *,
    icon: str | None = None,
    color: str | None = None,
) -> list[dict[str, Any]]:
    normalized_icon = normalize_icon_name(icon) if icon is not None else None
    normalized_color = normalize_hex_color(color) if color is not None else None
    result = [deepcopy(item) for item in indicators]
    for item in result:
        if normalized_icon is not None:
            item["icon"] = normalized_icon
        if normalized_color is not None:
            item["color"] = normalized_color
    return result

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import textwrap

from PIL import Image, ImageChops, ImageDraw, ImageFont

from .icon_registry import DEFAULT_COLOR, DEFAULT_ICON, normalize_hex_color, render_icon
from .layout import build_layout, CardBox
from .validation import validate_no_overlaps, validate_text_bounds


WIDTH = 1600
HEIGHT = 2000
BLUE = DEFAULT_COLOR
DARK_BLUE = "#12356F"
LIGHT_BLUE = "#EAF3FF"
TEXT = "#1B2A41"
MUTED = "#65758B"
CARD_BORDER = "#D5E0EE"


@dataclass
class RenderReport:
    output_png: str
    output_pdf: str | None
    width: int
    height: int
    text_errors: list[str]
    overlap_errors: list[str]
    template_id: str = "compatibilidade_padrao"
    template_version: str = ""
    slot_map: dict[str, dict[str, Any]] = field(default_factory=dict)
    fallback_used: bool = False

    @property
    def errors(self) -> list[str]:
        return self.text_errors + self.overlap_errors


@dataclass
class MultiPageRenderReport:
    png_pages: list[str]
    output_pdf: str | None
    width: int
    height: int
    text_errors: list[str]
    overlap_errors: list[str]
    template_id: str = "compatibilidade_padrao"
    template_version: str = ""
    slot_map: dict[str, dict[str, Any]] = field(default_factory=dict)
    fallback_used: bool = False

    @property
    def output_png(self) -> str:
        return self.png_pages[0] if self.png_pages else ""

    @property
    def errors(self) -> list[str]:
        return self.text_errors + self.overlap_errors


def _font_candidates(bold: bool = False) -> list[str]:
    if bold:
        return [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    return [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in _font_candidates(bold):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    words = str(text).split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if _text_size(draw, candidate, font)[0] <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            if _text_size(draw, word, font)[0] <= width:
                current = word
            else:
                pieces = textwrap.wrap(word, width=max(4, int(len(word) * width / max(1, _text_size(draw, word, font)[0]))))
                lines.extend(pieces[:-1])
                current = pieces[-1] if pieces else word
    if current:
        lines.append(current)
    return lines


def draw_text_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    max_size: int,
    min_size: int,
    fill: str,
    bold: bool = False,
    align: str = "left",
    line_spacing: float = 1.12,
    record_id: str = "text",
    records: list[dict[str, Any]] | None = None,
) -> bool:
    x, y, w, h = box
    selected = None
    selected_lines: list[str] = []
    for size in range(max_size, min_size - 1, -2):
        font = get_font(size, bold=bold)
        lines = _wrap(draw, str(text), font, w)
        line_h = max(_text_size(draw, "Ag", font)[1], int(size * 0.72))
        total_h = int(len(lines) * line_h * line_spacing)
        if total_h <= h and all(_text_size(draw, line, font)[0] <= w for line in lines):
            selected = font
            selected_lines = lines
            break
    fits = selected is not None
    if selected is None:
        selected = get_font(min_size, bold=bold)
        selected_lines = _wrap(draw, str(text), selected, w)

    line_h = max(_text_size(draw, "Ag", selected)[1], int(min_size * 0.72))
    cursor_y = y
    used_w = 0
    used_h = 0
    for line in selected_lines:
        line_w, measured_h = _text_size(draw, line, selected)
        if align == "center":
            line_x = x + (w - line_w) / 2
        elif align == "right":
            line_x = x + w - line_w
        else:
            line_x = x
        draw.text((line_x, cursor_y), line, font=selected, fill=fill)
        used_w = max(used_w, line_w)
        used_h += int(line_h * line_spacing)
        cursor_y += int(line_h * line_spacing)

    if records is not None:
        actual_x = x if align != "center" else x + max(0, (w - used_w) / 2)
        records.append({"id": record_id, "x": actual_x, "y": y, "w": min(w, used_w), "h": min(h + 1, used_h), "fits": fits})
    return fits


def draw_shadowed_card(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], radius: int = 22) -> None:
    x, y, w, h = rect
    draw.rounded_rectangle((x + 10, y + 12, x + w + 10, y + h + 12), radius=radius, fill=(28, 72, 125, 18))
    draw.rounded_rectangle((x + 4, y + 5, x + w + 4, y + h + 5), radius=radius, fill=(28, 72, 125, 12))
    draw.rounded_rectangle((x, y, x + w, y + h), radius=radius, fill="#FFFFFF", outline=CARD_BORDER, width=2)


def paste_fit(canvas: Image.Image, image_path: str | Path, box: tuple[int, int, int, int]) -> None:
    path = Path(image_path)
    if not str(image_path).strip() or not path.exists() or not path.is_file():
        return
    image = Image.open(path).convert("RGBA")
    background = Image.new("RGBA", image.size, image.getpixel((0, 0)))
    diff = ImageChops.difference(image, background).convert("L").point(lambda value: 255 if value > 12 else 0)
    crop_box = diff.getbbox()
    if crop_box:
        image = image.crop(crop_box)
    image.thumbnail((box[2], box[3]), Image.Resampling.LANCZOS)
    x = box[0] + (box[2] - image.width) // 2
    y = box[1] + (box[3] - image.height) // 2
    canvas.alpha_composite(image, (x, y))


def draw_icon(draw: ImageDraw.ImageDraw, name: str, box: tuple[int, int, int, int], color: str) -> None:
    render_icon(draw, name, box, normalize_hex_color(color))


def _metric_field(metric: Any, field: str, default: Any = None) -> Any:
    if isinstance(metric, dict):
        return metric.get(field, default)
    return getattr(metric, field, default)


def render_card(draw: ImageDraw.ImageDraw, card: CardBox, metric: Any, records: list[dict[str, Any]]) -> None:
    draw_shadowed_card(draw, (card.x, card.y, card.w, card.h), radius=24)
    color = normalize_hex_color(str(_metric_field(metric, "color", BLUE) or BLUE))
    display_value = str(_metric_field(metric, "display_value", ""))
    label = str(_metric_field(metric, "label", ""))
    icon = str(_metric_field(metric, "icon", DEFAULT_ICON))

    pad = 34
    if card.w >= 620:
        icon_size = int(min(card.h - 82, card.w * 0.24, 168))
        icon_box = (card.x + pad, card.y + (card.h - icon_size) // 2, icon_size, icon_size)
        text_x = icon_box[0] + icon_size + 42
        value_box = (text_x, card.y + 38, card.x + card.w - pad - text_x, int(card.h * 0.34))
        label_box = (text_x, card.y + int(card.h * 0.58), card.x + card.w - pad - text_x, int(card.h * 0.30))
        value_size = 78
        label_size = 32
    else:
        icon_size = int(min(88, card.h * 0.34, card.w * 0.24))
        icon_box = (card.x + pad, card.y + pad, icon_size, icon_size)
        value_box = (card.x + pad + icon_size + 24, card.y + pad + 4, card.w - (pad * 2) - icon_size - 24, int(card.h * 0.30))
        label_box = (card.x + pad, card.y + int(card.h * 0.58), card.w - (pad * 2), int(card.h * 0.30))
        value_size = 60
        label_size = 25

    draw_icon(draw, icon, icon_box, color)
    draw_text_box(draw, display_value, value_box, value_size, 38, color, bold=True, record_id=f"{_metric_field(metric, 'metric_id')}-valor", records=records)
    draw_text_box(draw, label, label_box, label_size, 20, TEXT, bold=False, record_id=f"{_metric_field(metric, 'metric_id')}-rotulo", records=records)


def render_card_thumbnail(metric: Any, width: int = 620, height: int = 300) -> Image.Image:
    canvas = Image.new("RGBA", (width, height), "#F7FBFF")
    draw = ImageDraw.Draw(canvas, "RGBA")
    records: list[dict[str, Any]] = []
    render_card(draw, CardBox("thumbnail", 28, 28, width - 56, height - 56), metric, records)
    return canvas.convert("RGB")


def render_infographic(
    metrics: list[Any],
    metadata: dict[str, Any],
    assets: dict[str, str | Path],
    output_png: str | Path,
    output_pdf: str | Path | None = None,
    width: int = WIDTH,
    height: int = HEIGHT,
) -> RenderReport:
    if not metrics:
        raise ValueError("nao ha indicadores validos para renderizar")
    layout = build_layout(metrics, width=width, height=height)

    canvas = Image.new("RGBA", (width, height), "#F7FBFF")
    draw = ImageDraw.Draw(canvas, "RGBA")
    records: list[dict[str, Any]] = []

    strip_colors = ["#FFD100", "#009739", "#EF3340", "#0057B8"]
    x = 0
    for color in strip_colors:
        next_x = x + width // len(strip_colors)
        draw.rectangle((x, 0, next_x, 28), fill=color)
        x = next_x

    paste_fit(canvas, assets.get("observatorio_logo", ""), (104, 70, 390, 108))
    draw_text_box(draw, str(metadata.get("header", "")), (510, 82, 900, 58), 31, 20, BLUE, bold=True, record_id="cabecalho", records=records)
    draw_text_box(draw, str(metadata.get("title", "")), (104, 180, 1070, 94), 73, 44, DARK_BLUE, bold=True, record_id="titulo", records=records)
    draw_text_box(draw, str(metadata.get("subtitle", "")), (104, 288, 980, 82), 35, 22, TEXT, record_id="subtitulo", records=records)

    period = str(metadata.get("period", "")).strip()
    if period:
        draw_text_box(draw, f"Período dos dados: {period}", (104, 374, 980, 38), 25, 18, MUTED, record_id="periodo", records=records)

    for section in layout.sections:
        sx, sy, sw, sh = section.title_box
        if not section.show_title:
            metric_by_id = {str(_metric_field(metric, "metric_id")): metric for metric in metrics}
            for card in section.cards:
                render_card(draw, card, metric_by_id[card.metric_id], records)
            continue
        title = section.title.upper()
        line_y = sy + sh // 2
        text_w = _text_size(draw, title, get_font(30, bold=True))[0]
        draw.line((sx + 130, line_y, sx + max(132, sw // 2 - text_w // 2 - 34), line_y), fill=(0, 87, 184, 120), width=2)
        draw.line((sx + sw // 2 + text_w // 2 + 34, line_y, sx + sw - 130, line_y), fill=(0, 87, 184, 120), width=2)
        draw_text_box(draw, title, (sx, sy + 6, sw, sh - 8), 31, 24, BLUE, bold=True, align="center", record_id=f"secao-{title}", records=records)
        metric_by_id = {str(_metric_field(metric, "metric_id")): metric for metric in metrics}
        for card in section.cards:
            render_card(draw, card, metric_by_id[card.metric_id], records)

    footer_x, footer_y, footer_w, footer_h = layout.footer_box
    cta = str(metadata.get("cta", "")).strip()
    if cta:
        pill_w = 490
        pill_h = 70
        pill_x = footer_x + (footer_w - pill_w) // 2
        draw.rounded_rectangle((pill_x, footer_y, pill_x + pill_w, footer_y + pill_h), radius=35, fill="#FFD100", outline="#E1B800", width=2)
        draw_text_box(draw, cta, (pill_x + 26, footer_y + 12, pill_w - 52, 46), 37, 22, DARK_BLUE, bold=True, align="center", record_id="cta", records=records)

    meta_parts = []
    if str(metadata.get("source", "")).strip():
        meta_parts.append(f"Fonte: {metadata.get('source')}")
    if str(metadata.get("updated_at", "")).strip():
        meta_parts.append(f"Atualização: {metadata.get('updated_at')}")
    website = str(metadata.get("website", "")).strip()
    if website:
        meta_parts.append(website)
    if meta_parts:
        draw_text_box(draw, "  |  ".join(meta_parts), (footer_x, footer_y + 82, footer_w, 44), 23, 16, MUTED, align="center", record_id="fonte", records=records)

    paste_fit(canvas, assets.get("bahia_logo", ""), (footer_x + (footer_w - 300) // 2, footer_y + 126, 300, 78))

    text_errors = validate_text_bounds(records, width, height)
    overlap_errors = validate_no_overlaps(layout.card_rects, padding=0)

    output_png = Path(output_png)
    output_png.parent.mkdir(parents=True, exist_ok=True)
    rgb = canvas.convert("RGB")
    rgb.save(output_png, format="PNG")

    output_pdf_path = None
    if output_pdf:
        output_pdf_path = Path(output_pdf)
        output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
        rgb.save(output_pdf_path, "PDF", resolution=300.0)

    return RenderReport(
        output_png=str(output_png),
        output_pdf=str(output_pdf_path) if output_pdf_path else None,
        width=width,
        height=height,
        text_errors=text_errors,
        overlap_errors=overlap_errors,
    )


def render_infographic_pages(
    metrics: list[Any],
    metadata: dict[str, Any],
    assets: dict[str, str | Path],
    output_dir: str | Path,
    basename: str,
    output_pdf: str | Path | None = None,
    max_per_page: int = 9,
    width: int = WIDTH,
    height: int = HEIGHT,
) -> MultiPageRenderReport:
    if max_per_page < 1:
        raise ValueError("max_per_page precisa ser maior que zero")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pages = [metrics[index:index + max_per_page] for index in range(0, len(metrics), max_per_page)]
    png_pages: list[str] = []
    text_errors: list[str] = []
    overlap_errors: list[str] = []

    for page_index, page_metrics in enumerate(pages, start=1):
        suffix = f"_p{page_index:02d}" if len(pages) > 1 else ""
        page_png = output_dir / f"{basename}{suffix}.png"
        page_metadata = dict(metadata)
        if len(pages) > 1:
            page_metadata["subtitle"] = " ".join(part for part in [str(metadata.get("subtitle", "")).strip(), f"Página {page_index} de {len(pages)}"] if part)
        report = render_infographic(page_metrics, page_metadata, assets, page_png, None, width=width, height=height)
        png_pages.append(str(page_png))
        text_errors.extend(report.text_errors)
        overlap_errors.extend(report.overlap_errors)

    output_pdf_path = None
    if output_pdf and png_pages:
        output_pdf_path = Path(output_pdf)
        images = [Image.open(path).convert("RGB") for path in png_pages]
        first, rest = images[0], images[1:]
        first.save(output_pdf_path, "PDF", resolution=300.0, save_all=True, append_images=rest)
        for image in images:
            image.close()

    return MultiPageRenderReport(
        png_pages=png_pages,
        output_pdf=str(output_pdf_path) if output_pdf_path else None,
        width=width,
        height=height,
        text_errors=text_errors,
        overlap_errors=overlap_errors,
    )


def write_validation_report(report: RenderReport | MultiPageRenderReport, output_path: str | Path, metric_count: int) -> None:
    lines = [
        "Relatorio de validacao do infografico",
        f"Dimensoes: {report.width} x {report.height}px",
        f"Indicadores renderizados: {metric_count}",
        f"PNG: {report.output_png}",
        f"PDF: {report.output_pdf or 'nao gerado'}",
    ]
    if isinstance(report, MultiPageRenderReport) and len(report.png_pages) > 1:
        lines.append(f"Paginas PNG: {len(report.png_pages)}")
    if report.errors:
        lines.append("Problemas encontrados:")
        lines.extend(f"- {error}" for error in report.errors)
    else:
        lines.append("Validacao visual automatica: sem texto fora dos limites e sem sobreposicao entre cards principais.")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")

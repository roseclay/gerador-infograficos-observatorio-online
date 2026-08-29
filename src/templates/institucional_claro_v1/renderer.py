from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from src.icon_registry import DEFAULT_COLOR, normalize_hex_color
from src.renderer import MultiPageRenderReport, RenderReport, draw_text_box, get_font, paste_fit
from src.templates.base import PagePlan, TemplateContext, TemplateMetadata
from src.templates.shared.icon_compositor import paste_template_icon
from src.templates.shared.pagination import paginate
from src.templates.shared.text_layout import draw_fit_text

from .layout import (
    BLUE,
    DARK_BLUE,
    DEMO_BOX,
    FOOTER,
    FOOTER_COMPACT,
    HEADER_BOX,
    HEIGHT,
    MUTED,
    PANEL_MASKS,
    SUBTITLE_BOX,
    TEXT,
    TITLE_BOX,
    TITLE_BOX_NO_SUBTITLE,
    WIDTH,
    YELLOW,
    build_page_plan,
)
from .validator import validate_page


ROOT = Path(__file__).resolve().parents[3]
ICONS_DIR = ROOT / "assets" / "icons" / "institucional_claro_v1"


def _metric_field(metric: Any, field: str, default: Any = None) -> Any:
    if isinstance(metric, dict):
        return metric.get(field, default)
    return getattr(metric, field, default)


def _metadata_text(metadata: dict[str, Any], key: str) -> str:
    return str(metadata.get(key) or "").strip()


def _write_pdf_from_pngs(png_pages: list[str], output_pdf: str | Path | None) -> str | None:
    if not output_pdf or not png_pages:
        return None
    output_pdf_path = Path(output_pdf)
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    images = [Image.open(path).convert("RGB") for path in png_pages]
    first, rest = images[0], images[1:]
    first.save(output_pdf_path, "PDF", resolution=300.0, save_all=True, append_images=rest)
    for image in images:
        image.close()
    return str(output_pdf_path)


class InstitucionalClaroTemplate:
    def __init__(self, metadata: TemplateMetadata, manifest: dict[str, Any]) -> None:
        self.metadata = metadata
        self.manifest = manifest

    def supports(self, context: TemplateContext) -> bool:
        return bool(context.metrics)

    def plan_layout(self, context: TemplateContext) -> list[PagePlan]:
        return [
            build_page_plan(page_metrics, page=index)
            for index, page_metrics in enumerate(paginate(context.metrics, self.metadata.capacity_per_page), start=1)
        ]

    def _base_canvas(self, page_plan: PagePlan) -> Image.Image:
        if not self.metadata.production_base.exists():
            raise FileNotFoundError(f"matriz de produção ausente: {self.metadata.production_base}")
        base = Image.open(self.metadata.production_base).convert("RGBA")
        if base.size != (WIDTH, HEIGHT):
            base = base.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(base, "RGBA")
        for panel in page_plan.hidden_panels:
            x, y, w, h = PANEL_MASKS[panel]
            if panel.endswith("vertical") or panel.endswith("horizontal") or panel.startswith("complementary_"):
                draw.rectangle((x, y, x + w, y + h), fill=(255, 255, 255, 238))
            else:
                draw.rectangle((x, y, x + w, y + h), fill=(250, 252, 255, 255))
        return base

    def _draw_header(self, canvas: Image.Image, draw: ImageDraw.ImageDraw, context: TemplateContext, records: list[dict[str, Any]]) -> None:
        header = _metadata_text(context.metadata, "header")
        if header:
            draw_fit_text(draw, header.upper(), HEADER_BOX, max_size=22, min_size=13, fill=BLUE, bold=True, record_id="cabecalho", records=records)
        subtitle = _metadata_text(context.metadata, "subtitle")
        title_box = TITLE_BOX if subtitle else TITLE_BOX_NO_SUBTITLE
        draw_fit_text(draw, _metadata_text(context.metadata, "title"), title_box, max_size=62 if subtitle else 68, min_size=32, fill=DARK_BLUE, bold=True, record_id="titulo", records=records)
        if subtitle:
            draw_fit_text(draw, subtitle, SUBTITLE_BOX, max_size=26, min_size=16, fill=TEXT, line_spacing=1.2, record_id="subtitulo", records=records)
        if context.demo_mode:
            draw.rounded_rectangle((DEMO_BOX[0], DEMO_BOX[1], DEMO_BOX[0] + DEMO_BOX[2], DEMO_BOX[1] + DEMO_BOX[3]), radius=16, fill=(255, 209, 0, 235))
            draw_fit_text(draw, "DADOS FICTÍCIOS DE DEMONSTRAÇÃO", DEMO_BOX, max_size=15, min_size=11, fill=DARK_BLUE, bold=True, align="center", record_id="demo", records=records)

    def _draw_section_titles(self, draw: ImageDraw.ImageDraw, page_plan: PagePlan, records: list[dict[str, Any]]) -> None:
        for title in page_plan.section_titles:
            x, y, w, h = title.box
            center_y = y + h // 2
            font = get_font(title.max_size, bold=title.bold)
            text_box = draw.textbbox((0, 0), title.text, font=font)
            text_w = text_box[2] - text_box[0]
            center_x = x + w // 2
            gap = 18 if text_w > 260 else 26
            side_margin = 250 if text_w > 260 else 290
            left_start = x + side_margin
            left_end = center_x - text_w // 2 - gap
            right_start = center_x + text_w // 2 + gap
            right_end = x + w - side_margin
            if left_end - left_start >= 36:
                draw.line((left_start, center_y, left_end, center_y), fill=(0, 87, 184, 105), width=2)
            if right_end - right_start >= 36:
                draw.line((right_start, center_y, right_end, center_y), fill=(0, 87, 184, 105), width=2)
            draw_fit_text(
                draw,
                title.text,
                title.box,
                max_size=title.max_size,
                min_size=title.min_size,
                fill=title.fill,
                bold=title.bold,
                align=title.align,
                line_spacing=title.line_spacing,
                record_id=title.id,
                records=records,
            )

    def _draw_metric(self, canvas: Image.Image, draw: ImageDraw.ImageDraw, metric: Any, slot, records: list[dict[str, Any]]) -> dict[str, Any]:
        color = normalize_hex_color(str(_metric_field(metric, "color", DEFAULT_COLOR) or DEFAULT_COLOR))
        icon_result = paste_template_icon(canvas, draw, metric, slot.icon_box, ICONS_DIR)
        value = str(_metric_field(metric, "display_value", "") or "")
        label = str(_metric_field(metric, "label", "") or "")
        section_key = slot.slot_id.split("_", 1)[0]
        if section_key == "principal":
            value_size, value_min = 66, 34
            label_size, label_min = 24, 15
            align = "left"
        elif section_key == "intermediate":
            value_size, value_min = 78, 42
            label_size, label_min = 22, 15
            align = "center"
        else:
            value_size, value_min = 51, 30
            label_size, label_min = 20, 13
            align = "left"

        draw_text_box(draw, value, slot.value_box, value_size, value_min, color, bold=True, align=align, record_id=f"{slot.metric_id}-valor", records=records)
        draw_text_box(draw, label, slot.label_box, label_size, label_min, TEXT, align=align, line_spacing=1.16, record_id=f"{slot.metric_id}-rotulo", records=records)
        return {
            "pagina": slot.page,
            "secao": slot.section,
            "slot": slot.slot_id,
            "icone": icon_result.icon_key,
            "icone_fallback": icon_result.fallback_used,
            "observacao_icone": icon_result.note,
        }

    def _draw_footer(self, canvas: Image.Image, draw: ImageDraw.ImageDraw, context: TemplateContext, records: list[dict[str, Any]]) -> int:
        cta = _metadata_text(context.metadata, "cta")
        if cta:
            x, y, w, h = FOOTER["cta"]
            draw.rounded_rectangle((x, y, x + w, y + h), radius=30, fill=YELLOW, outline="#D8B100", width=1)
            draw_fit_text(draw, cta, (x + 22, y + 11, w - 44, h - 18), max_size=30, min_size=18, fill=DARK_BLUE, bold=True, align="center", record_id="cta", records=records)

        footer_layout = FOOTER if cta else FOOTER_COMPACT
        parts = []
        if _metadata_text(context.metadata, "source"):
            parts.append(f"Fonte: {_metadata_text(context.metadata, 'source')}")
        if _metadata_text(context.metadata, "period"):
            parts.append(f"Período: {_metadata_text(context.metadata, 'period')}")
        if _metadata_text(context.metadata, "updated_at"):
            parts.append(f"Atualização: {_metadata_text(context.metadata, 'updated_at')}")
        if _metadata_text(context.metadata, "website"):
            parts.append(_metadata_text(context.metadata, "website"))
        if parts:
            draw_fit_text(draw, "  |  ".join(parts), footer_layout["meta"], max_size=17, min_size=11, fill=MUTED, align="center", record_id="rodape", records=records)

        paste_fit(canvas, context.assets.get("bahia_logo", ""), footer_layout["bahia_logo"])
        return int(footer_layout.get("height", HEIGHT))

    def render_page(self, context: TemplateContext, page_plan: PagePlan, output_png: str | Path) -> RenderReport:
        canvas = self._base_canvas(page_plan)
        draw = ImageDraw.Draw(canvas, "RGBA")
        records: list[dict[str, Any]] = []
        slot_map: dict[str, dict[str, Any]] = {}
        metric_by_id = {str(_metric_field(metric, "metric_id", _metric_field(metric, "id", ""))): metric for metric in page_plan.metrics}

        self._draw_header(canvas, draw, context, records)
        self._draw_section_titles(draw, page_plan, records)
        for slot in page_plan.slots:
            metric = metric_by_id[slot.metric_id]
            slot_map[slot.metric_id] = self._draw_metric(canvas, draw, metric, slot, records)
        final_height = self._draw_footer(canvas, draw, context, records)
        if final_height < HEIGHT:
            canvas = canvas.crop((0, 0, WIDTH, final_height))

        text_errors, overlap_errors = validate_page(records, page_plan, height=final_height)
        output_path = Path(output_png)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.convert("RGB").save(output_path, format="PNG")
        return RenderReport(
            output_png=str(output_path),
            output_pdf=None,
            width=WIDTH,
            height=final_height,
            text_errors=text_errors,
            overlap_errors=overlap_errors,
            template_id=self.metadata.id,
            template_version=self.metadata.version,
            slot_map=slot_map,
        )

    def render(self, context: TemplateContext, output_png: str | Path, output_pdf: str | Path | None = None) -> RenderReport:
        plans = self.plan_layout(context)
        if len(plans) != 1:
            raise ValueError("use render_pages para múltiplas páginas")
        report = self.render_page(context, plans[0], output_png)
        output_pdf_path = _write_pdf_from_pngs([report.output_png], output_pdf)
        report.output_pdf = output_pdf_path
        return report

    def render_pages(self, context: TemplateContext, output_dir: str | Path, basename: str, output_pdf: str | Path | None = None) -> MultiPageRenderReport:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        reports: list[RenderReport] = []
        for plan in self.plan_layout(context):
            suffix = f"_p{plan.page:02d}" if len(context.metrics) > self.metadata.capacity_per_page else ""
            page_context = context
            if len(context.metrics) > self.metadata.capacity_per_page:
                page_metadata = dict(context.metadata)
                page_metadata["subtitle"] = " ".join(
                    part for part in [str(context.metadata.get("subtitle", "")).strip(), f"Página {plan.page} de {len(self.plan_layout(context))}"] if part
                )
                page_context = TemplateContext(plan.metrics, page_metadata, context.assets, context.config, context.demo_mode)
            reports.append(self.render_page(page_context, plan, output_dir / f"{basename}{suffix}.png"))

        png_pages = [report.output_png for report in reports]
        output_pdf_path = _write_pdf_from_pngs(png_pages, output_pdf)
        slot_map: dict[str, dict[str, Any]] = {}
        text_errors: list[str] = []
        overlap_errors: list[str] = []
        for report in reports:
            slot_map.update(report.slot_map)
            text_errors.extend(report.text_errors)
            overlap_errors.extend(report.overlap_errors)
        return MultiPageRenderReport(
            png_pages=png_pages,
            output_pdf=output_pdf_path,
            width=WIDTH,
            height=HEIGHT,
            text_errors=text_errors,
            overlap_errors=overlap_errors,
            template_id=self.metadata.id,
            template_version=self.metadata.version,
            slot_map=slot_map,
        )

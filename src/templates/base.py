from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


DEFAULT_TEMPLATE_ID = "institucional_claro_v1"
DEFAULT_TEMPLATE_VERSION = "1.0"
LEGACY_TEMPLATE_ID = "compatibilidade_padrao"


@dataclass(frozen=True)
class TemplateMetadata:
    id: str
    name: str
    description: str
    version: str
    status: str
    thumbnail: Path
    reference: Path
    production_base: Path
    canvas_width: int
    canvas_height: int
    capacity_per_page: int

    @property
    def aspect_ratio(self) -> float:
        return self.canvas_width / self.canvas_height


@dataclass(frozen=True)
class TemplateContext:
    metrics: list[Any]
    metadata: dict[str, Any]
    assets: dict[str, str | Path]
    config: dict[str, Any]
    demo_mode: bool = False


@dataclass(frozen=True)
class TextPlacement:
    id: str
    text: str
    box: tuple[int, int, int, int]
    max_size: int
    min_size: int
    fill: str
    bold: bool = False
    align: str = "left"
    line_spacing: float = 1.12


@dataclass(frozen=True)
class SlotPlan:
    metric_id: str
    section: str
    slot_id: str
    page: int
    icon_box: tuple[int, int, int, int]
    value_box: tuple[int, int, int, int]
    label_box: tuple[int, int, int, int]
    cell_rect: tuple[int, int, int, int]


@dataclass(frozen=True)
class PagePlan:
    page: int
    metrics: list[Any]
    slots: list[SlotPlan]
    section_titles: list[TextPlacement] = field(default_factory=list)
    hidden_panels: tuple[str, ...] = ()


class TemplateError(RuntimeError):
    pass


class TemplateNotFound(TemplateError):
    pass


class TemplateLoadError(TemplateError):
    pass


class InfographicTemplate(Protocol):
    metadata: TemplateMetadata

    def supports(self, context: TemplateContext) -> bool:
        ...

    def plan_layout(self, context: TemplateContext) -> list[PagePlan]:
        ...

    def render_page(self, context: TemplateContext, page_plan: PagePlan, output_png: str | Path):
        ...

    def render(self, context: TemplateContext, output_png: str | Path, output_pdf: str | Path | None = None):
        ...

    def render_pages(self, context: TemplateContext, output_dir: str | Path, basename: str, output_pdf: str | Path | None = None):
        ...


def default_template_config() -> dict[str, str]:
    return {"id": DEFAULT_TEMPLATE_ID, "version": DEFAULT_TEMPLATE_VERSION}


def normalize_template_config(value: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(value, dict):
        return default_template_config()
    template_id = str(value.get("id") or DEFAULT_TEMPLATE_ID).strip() or DEFAULT_TEMPLATE_ID
    version = str(value.get("version") or DEFAULT_TEMPLATE_VERSION).strip() or DEFAULT_TEMPLATE_VERSION
    return {"id": template_id, "version": version}

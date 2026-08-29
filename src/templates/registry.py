from __future__ import annotations

from dataclasses import dataclass
import importlib
import pkgutil
from pathlib import Path
from typing import Any

import yaml

from .base import DEFAULT_TEMPLATE_ID, InfographicTemplate, TemplateLoadError, TemplateMetadata, TemplateNotFound


ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config" / "templates"


@dataclass(frozen=True)
class TemplateRegistryItem:
    metadata: TemplateMetadata
    template: InfographicTemplate | None
    error: str = ""

    @property
    def available(self) -> bool:
        return self.template is not None and not self.error


def load_manifest(template_id: str) -> dict[str, Any]:
    path = CONFIG_DIR / f"{template_id}.yaml"
    if not path.exists():
        raise TemplateLoadError(f"manifesto de template ausente: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def metadata_from_manifest(manifest: dict[str, Any]) -> TemplateMetadata:
    template_id = str(manifest.get("id") or "").strip()
    if not template_id:
        raise TemplateLoadError("manifesto sem id")
    canvas = manifest.get("canvas") or {}
    capacity = manifest.get("capacity") or {}
    return TemplateMetadata(
        id=template_id,
        name=str(manifest.get("name") or template_id),
        description=str(manifest.get("description") or ""),
        version=str(manifest.get("version") or ""),
        status=str(manifest.get("status") or "Disponível"),
        thumbnail=ROOT / str(manifest.get("thumbnail") or ""),
        reference=ROOT / str(manifest.get("reference") or ""),
        production_base=ROOT / str(manifest.get("production_base") or ""),
        canvas_width=int(canvas.get("width") or 0),
        canvas_height=int(canvas.get("height") or 0),
        capacity_per_page=int(capacity.get("per_page") or 9),
    )


class TemplateRegistry:
    def __init__(self) -> None:
        self._items: dict[str, TemplateRegistryItem] | None = None

    def _discover_ids(self) -> list[str]:
        package_dir = Path(__file__).parent
        ignored = {"shared", "__pycache__"}
        ids = [
            module.name
            for module in pkgutil.iter_modules([str(package_dir)])
            if module.ispkg and not module.name.startswith("_") and module.name not in ignored
        ]
        if DEFAULT_TEMPLATE_ID not in ids:
            ids.append(DEFAULT_TEMPLATE_ID)
        return sorted(set(ids))

    def _load_item(self, template_id: str) -> TemplateRegistryItem:
        manifest = load_manifest(template_id)
        metadata = metadata_from_manifest(manifest)
        try:
            module = importlib.import_module(f"src.templates.{template_id}")
            factory = getattr(module, "get_template")
            template = factory(metadata, manifest)
        except Exception as exc:
            return TemplateRegistryItem(metadata=metadata, template=None, error=str(exc))
        return TemplateRegistryItem(metadata=metadata, template=template)

    def items(self, refresh: bool = False) -> list[TemplateRegistryItem]:
        if self._items is None or refresh:
            items: dict[str, TemplateRegistryItem] = {}
            for template_id in self._discover_ids():
                try:
                    items[template_id] = self._load_item(template_id)
                except Exception as exc:
                    placeholder = TemplateMetadata(
                        id=template_id,
                        name=template_id,
                        description="",
                        version="",
                        status="Indisponível",
                        thumbnail=Path(),
                        reference=Path(),
                        production_base=Path(),
                        canvas_width=0,
                        canvas_height=0,
                        capacity_per_page=0,
                    )
                    items[template_id] = TemplateRegistryItem(metadata=placeholder, template=None, error=str(exc))
            self._items = items
        return list(self._items.values())

    def public_templates(self) -> list[TemplateRegistryItem]:
        return [item for item in self.items() if item.available]

    def get(self, template_id: str | None) -> InfographicTemplate:
        selected = str(template_id or DEFAULT_TEMPLATE_ID).strip() or DEFAULT_TEMPLATE_ID
        for item in self.items():
            if item.metadata.id == selected and item.available and item.template is not None:
                return item.template
            if item.metadata.id == selected and item.error:
                raise TemplateLoadError(item.error)
        raise TemplateNotFound(f"template ausente: {selected}")

    def validate_id(self, template_id: str | None) -> bool:
        selected = str(template_id or "").strip()
        return any(item.metadata.id == selected and item.available for item in self.items())

    def fallback(self) -> InfographicTemplate:
        return self.get(DEFAULT_TEMPLATE_ID)


_REGISTRY = TemplateRegistry()


def get_template_registry() -> TemplateRegistry:
    return _REGISTRY

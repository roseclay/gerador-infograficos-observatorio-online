from __future__ import annotations

from typing import Any

from src.templates.base import TemplateMetadata

from .renderer import InstitucionalClaroTemplate


def get_template(metadata: TemplateMetadata, manifest: dict[str, Any]) -> InstitucionalClaroTemplate:
    return InstitucionalClaroTemplate(metadata, manifest)

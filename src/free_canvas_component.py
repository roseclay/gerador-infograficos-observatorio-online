from __future__ import annotations

import base64
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COMPONENT_DIR = ROOT / "components" / "free_canvas"

_drag_canvas = None


def _component():
    global _drag_canvas
    if _drag_canvas is None:
        import streamlit.components.v1 as components

        _drag_canvas = components.declare_component("free_canvas", path=str(COMPONENT_DIR))
    return _drag_canvas


def detect_image_mime(image_bytes: bytes, fallback: str = "image/png") -> str:
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return fallback


def image_data_url(image_bytes: bytes, mime: str | None = None) -> str:
    mime = mime or detect_image_mime(image_bytes)
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def drag_canvas(
    image_bytes: bytes,
    fields: list[dict[str, Any]],
    image_size: tuple[int, int],
    key: str = "free_canvas",
    preview_image_bytes: bytes | None = None,
    field_preview_bytes: dict[str, bytes] | None = None,
) -> dict[str, Any] | None:
    default = {
        "changed": False,
        "selected_id": "",
        "fields": [
            {
                "id": str(field.get("id") or ""),
                "placed": bool(field.get("placed", True)),
                "x": int(field.get("x") or 0),
                "y": int(field.get("y") or 0),
                "width": int(field.get("width") or 0),
                "height": int(field.get("height") or 0),
                "font_size": int(field.get("font_size") or 0),
            }
            for field in fields
        ],
    }
    return _component()(
        image=image_data_url(image_bytes),
        baseImage=image_data_url(image_bytes),
        faithfulPreview=bool(field_preview_bytes) or preview_image_bytes is not None,
        fieldPreviews={
            str(field_id): image_data_url(data)
            for field_id, data in (field_preview_bytes or {}).items()
        },
        fields=fields,
        imageWidth=int(image_size[0]),
        imageHeight=int(image_size[1]),
        default=default,
        key=key,
    )

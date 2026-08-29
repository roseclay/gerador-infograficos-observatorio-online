from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
import unicodedata
from typing import Any

import pandas as pd
from PIL import Image, ImageDraw

from .configuration import slugify_filename
from .icon_registry import DEFAULT_COLOR, normalize_hex_color
from .renderer import RenderReport, draw_text_box
from .validation import validate_no_overlaps, validate_text_bounds


FREE_MODE_SCHEMA_VERSION = 1
DEFAULT_FIELD_WIDTH = 340
DEFAULT_FIELD_HEIGHT = 90
DEFAULT_FONT_SIZE = 58
FIELD_COLUMNS = [
    "enabled",
    "placed",
    "id",
    "name",
    "value",
    "x",
    "y",
    "width",
    "height",
    "font_size",
    "color",
    "bold",
    "align",
    "render_label",
    "order",
]
ALIGN_OPTIONS = ["left", "center", "right"]


@dataclass(frozen=True)
class FreeModeCsvImport:
    fields: list[dict[str, Any]]
    base_image_name: str
    warnings: list[str]


def _ascii_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return text


def _first_column(columns: list[str], aliases: set[str]) -> str:
    for column in columns:
        if _ascii_key(column) in aliases:
            return column
    return ""


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(float(str(value).replace(",", ".")))
    except Exception:
        return default


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    if value is None or str(value).strip() == "":
        return default
    text = _ascii_key(value)
    if text in {"1", "true", "sim", "yes", "y", "s"}:
        return True
    if text in {"0", "false", "nao", "no", "n"}:
        return False
    return default


def make_field_id(existing_ids: list[str] | None = None) -> str:
    existing = set(existing_ids or [])
    index = 1
    while True:
        candidate = f"campo_{index:03d}"
        if candidate not in existing:
            return candidate
        index += 1


def default_position(index: int, count: int, image_width: int, image_height: int) -> tuple[int, int]:
    width = max(1, int(image_width or 1122))
    height = max(1, int(image_height or 1402))
    count = max(1, count)
    columns = 2 if count > 4 else 1
    rows = max(1, (count + columns - 1) // columns)
    margin_x = max(24, int(width * 0.10))
    start_y = max(42, int(height * 0.18))
    usable_w = max(1, width - margin_x * 2)
    usable_h = max(1, int(height * 0.62))
    col = index % columns
    row = index // columns
    x = margin_x + int((usable_w / max(1, columns)) * col)
    y = start_y + int((usable_h / max(1, rows)) * row)
    return x, y


def new_text_field(
    existing_ids: list[str] | None = None,
    order: int = 1,
    image_width: int = 1122,
    image_height: int = 1402,
) -> dict[str, Any]:
    x, y = default_position(order - 1, max(order, 1), image_width, image_height)
    return {
        "enabled": True,
        "placed": True,
        "id": make_field_id(existing_ids),
        "name": "",
        "value": "",
        "x": x,
        "y": y,
        "width": DEFAULT_FIELD_WIDTH,
        "height": DEFAULT_FIELD_HEIGHT,
        "font_size": DEFAULT_FONT_SIZE,
        "color": DEFAULT_COLOR,
        "bold": True,
        "align": "left",
        "render_label": False,
        "order": order,
    }


def normalize_field(
    field: dict[str, Any],
    existing_ids: list[str] | None = None,
    order: int = 1,
    image_width: int = 1122,
    image_height: int = 1402,
) -> dict[str, Any]:
    item = deepcopy(field)
    default_x, default_y = default_position(order - 1, order, image_width, image_height)
    item["enabled"] = _to_bool(item.get("enabled"), True)
    item["placed"] = _to_bool(item.get("placed", item.get("positioned", item.get("posicionado"))), True)
    item["id"] = str(item.get("id") or "").strip() or make_field_id(existing_ids)
    item["name"] = str(item.get("name") or item.get("field") or item.get("campo") or "").strip()
    item["value"] = str(item.get("value") or item.get("valor") or "").strip()
    item["x"] = max(0, _to_int(item.get("x"), default_x))
    item["y"] = max(0, _to_int(item.get("y"), default_y))
    item["width"] = max(24, _to_int(item.get("width"), DEFAULT_FIELD_WIDTH))
    item["height"] = max(18, _to_int(item.get("height"), DEFAULT_FIELD_HEIGHT))
    item["font_size"] = max(8, _to_int(item.get("font_size"), DEFAULT_FONT_SIZE))
    item["color"] = normalize_hex_color(str(item.get("color") or DEFAULT_COLOR))
    item["bold"] = _to_bool(item.get("bold"), True)
    align = str(item.get("align") or "left").strip().lower()
    item["align"] = align if align in ALIGN_OPTIONS else "left"
    item["render_label"] = _to_bool(item.get("render_label"), False)
    item["order"] = max(1, _to_int(item.get("order"), order))
    return {column: item.get(column) for column in FIELD_COLUMNS}


def normalize_fields(fields: list[dict[str, Any]], image_width: int = 1122, image_height: int = 1402) -> list[dict[str, Any]]:
    existing_ids: list[str] = []
    result = []
    for index, field in enumerate(fields, start=1):
        normalized = normalize_field(field, existing_ids, index, image_width, image_height)
        if str(normalized["id"]) in existing_ids:
            normalized["id"] = make_field_id(existing_ids)
        existing_ids.append(str(normalized["id"]))
        result.append(normalized)
    result.sort(key=lambda item: (int(item.get("order") or 999), str(item.get("name") or "")))
    for index, field in enumerate(result, start=1):
        field["order"] = index
    return result


def _read_cell(row: dict[str, Any], column: str) -> str:
    if not column:
        return ""
    value = row.get(column, "")
    return "" if value is None else str(value).strip()


def _field_from_row(row: dict[str, Any], columns: list[str], index: int, count: int, image_width: int, image_height: int) -> dict[str, Any]:
    keys = {_ascii_key(column): column for column in columns}
    name_col = _first_column(columns, {"campo", "nome_campo", "nomecampo", "nome_do_campo", "nome", "field", "label", "indicador"})
    value_col = _first_column(columns, {"valor", "value", "texto", "informacao", "numero", "conteudo"})
    x_col = _first_column(columns, {"x", "coord_x", "coordenada_x", "campo_x"})
    y_col = _first_column(columns, {"y", "coord_y", "coordenada_y", "campo_y"})
    width_col = _first_column(columns, {"width", "largura", "w"})
    height_col = _first_column(columns, {"height", "altura", "h"})
    font_col = _first_column(columns, {"font_size", "fonte", "tamanho", "tamanho_fonte"})
    color_col = _first_column(columns, {"color", "cor"})
    align_col = _first_column(columns, {"align", "alinhamento"})
    label_col = _first_column(columns, {"render_label", "mostrar_rotulo", "mostrar_nome"})
    bold_col = _first_column(columns, {"bold", "negrito"})
    enabled_col = _first_column(columns, {"enabled", "usar", "ativo"})
    placed_col = _first_column(columns, {"placed", "positioned", "posicionado", "na_arte", "no_canvas"})
    order_col = _first_column(columns, {"order", "ordem"})
    x, y = default_position(index, count, image_width, image_height)
    has_coordinates = bool(_read_cell(row, x_col)) and bool(_read_cell(row, y_col))
    return normalize_field(
        {
            "enabled": _read_cell(row, enabled_col) if enabled_col else True,
            "placed": _read_cell(row, placed_col) if placed_col else has_coordinates,
            "name": _read_cell(row, name_col),
            "value": _read_cell(row, value_col),
            "x": _read_cell(row, x_col) if x_col else x,
            "y": _read_cell(row, y_col) if y_col else y,
            "width": _read_cell(row, width_col) if width_col else DEFAULT_FIELD_WIDTH,
            "height": _read_cell(row, height_col) if height_col else DEFAULT_FIELD_HEIGHT,
            "font_size": _read_cell(row, font_col) if font_col else DEFAULT_FONT_SIZE,
            "color": _read_cell(row, color_col) if color_col else DEFAULT_COLOR,
            "bold": _read_cell(row, bold_col) if bold_col else True,
            "align": _read_cell(row, align_col) if align_col else "left",
            "render_label": _read_cell(row, label_col) if label_col else False,
            "order": _read_cell(row, order_col) if order_col else index + 1,
        },
        order=index + 1,
        image_width=image_width,
        image_height=image_height,
    )


def _fields_from_long_dataframe(dataframe: pd.DataFrame, image_width: int, image_height: int) -> list[dict[str, Any]]:
    columns = [str(column) for column in dataframe.columns]
    name_col = _first_column(columns, {"campo", "nome_campo", "nomecampo", "nome_do_campo", "nome", "field", "label", "indicador"})
    value_col = _first_column(columns, {"valor", "value", "texto", "informacao", "numero", "conteudo"})
    if not name_col or not value_col:
        return []
    rows = dataframe.fillna("").to_dict(orient="records")
    return [
        _field_from_row(row, columns, index, len(rows), image_width, image_height)
        for index, row in enumerate(rows)
        if _read_cell(row, name_col) or _read_cell(row, value_col)
    ]


def _fields_from_wide_dataframe(dataframe: pd.DataFrame, image_width: int, image_height: int) -> list[dict[str, Any]]:
    if dataframe.empty:
        return []
    row = dataframe.fillna("").to_dict(orient="records")[0]
    groups: dict[str, dict[str, str]] = {}
    for column in dataframe.columns:
        key = _ascii_key(column)
        match = re.match(r"campo_?(\d+)_(.+)", key) or re.match(r"campo(\d+)(.+)", key)
        if not match:
            continue
        index, suffix = match.groups()
        suffix = suffix.strip("_")
        if suffix in {"nome", "name", "campo", "label"}:
            mapped = "name"
        elif suffix in {"valor", "value", "texto", "informacao"}:
            mapped = "value"
        elif suffix in {"x", "coord_x", "coordenada_x"}:
            mapped = "x"
        elif suffix in {"y", "coord_y", "coordenada_y"}:
            mapped = "y"
        elif suffix in {"w", "width", "largura"}:
            mapped = "width"
        elif suffix in {"h", "height", "altura"}:
            mapped = "height"
        elif suffix in {"placed", "positioned", "posicionado", "na_arte"}:
            mapped = "placed"
        else:
            continue
        groups.setdefault(index, {})[mapped] = str(row.get(column, "")).strip()
    fields = []
    sorted_groups = sorted(groups.items(), key=lambda item: int(item[0]))
    for order, (_, values) in enumerate(sorted_groups, start=1):
        if values.get("name") or values.get("value"):
            values["order"] = order
            if "placed" not in values:
                values["placed"] = bool(values.get("x") and values.get("y"))
            fields.append(normalize_field(values, [str(item["id"]) for item in fields], order, image_width, image_height))
    return fields


def base_image_name_from_dataframe(dataframe: pd.DataFrame) -> str:
    columns = [str(column) for column in dataframe.columns]
    base_col = _first_column(columns, {"imagem_base", "imagem", "image_base", "base", "arquivo_base"})
    if not base_col or dataframe.empty:
        return ""
    value = str(dataframe.iloc[0][base_col] or "").strip()
    return Path(value).name if value else ""


def fields_from_dataframe(dataframe: pd.DataFrame, image_width: int = 1122, image_height: int = 1402) -> FreeModeCsvImport:
    warnings: list[str] = []
    fields = _fields_from_long_dataframe(dataframe, image_width, image_height)
    if not fields:
        fields = _fields_from_wide_dataframe(dataframe, image_width, image_height)
    if not fields and dataframe.shape[1] >= 2:
        temp = dataframe.copy()
        temp.columns = ["campo", "valor", *[f"coluna_{index}" for index in range(3, dataframe.shape[1] + 1)]]
        fields = _fields_from_long_dataframe(temp, image_width, image_height)
        if fields:
            warnings.append("CSV sem cabecalho reconhecido como pares campo/valor; ajuste X e Y antes de exportar.")
    if not fields:
        warnings.append("Nenhum campo de texto foi encontrado no CSV.")
    return FreeModeCsvImport(
        fields=normalize_fields(fields, image_width, image_height),
        base_image_name=base_image_name_from_dataframe(dataframe),
        warnings=warnings,
    )


def fields_to_dataframe(fields: list[dict[str, Any]], base_image_name: str = "") -> pd.DataFrame:
    rows = []
    for field in normalize_fields(fields):
        rows.append({
            "imagem_base": base_image_name,
            "posicionado": field["placed"],
            "campo": field["name"],
            "valor": field["value"],
            "x": field["x"],
            "y": field["y"],
            "largura": field["width"],
            "altura": field["height"],
            "tamanho_fonte": field["font_size"],
            "cor": field["color"],
            "negrito": field["bold"],
            "alinhamento": field["align"],
            "mostrar_nome": field["render_label"],
            "ordem": field["order"],
        })
    return pd.DataFrame(rows)


def write_fields_csv(fields: list[dict[str, Any]], output_path: str | Path, base_image_name: str = "") -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields_to_dataframe(fields, base_image_name).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def build_free_mode_config(base_image_name: str, fields: list[dict[str, Any]], image_size: tuple[int, int]) -> dict[str, Any]:
    return {
        "schema_version": FREE_MODE_SCHEMA_VERSION,
        "mode": "imagem_base",
        "name": "",
        "base_image": {
            "file": base_image_name,
            "width": int(image_size[0]),
            "height": int(image_size[1]),
        },
        "fields": normalize_fields(fields, int(image_size[0]), int(image_size[1])),
    }


def build_free_mode_config_with_name(base_image_name: str, fields: list[dict[str, Any]], image_size: tuple[int, int], name: str = "") -> dict[str, Any]:
    config = build_free_mode_config(base_image_name, fields, image_size)
    config["name"] = str(name or "").strip()
    return config


def merge_dragged_fields(
    fields: list[dict[str, Any]],
    dragged_fields: list[dict[str, Any]],
    image_width: int,
    image_height: int,
) -> list[dict[str, Any]]:
    updates = {str(field.get("id")): field for field in dragged_fields if str(field.get("id") or "").strip()}
    merged = []
    for field in normalize_fields(fields, image_width, image_height):
        update = updates.get(str(field.get("id")))
        if update:
            item = deepcopy(field)
            if "placed" in update:
                item["placed"] = _to_bool(update.get("placed"), bool(field.get("placed", True)))
            item["x"] = max(0, min(image_width, _to_int(update.get("x"), int(field["x"]))))
            item["y"] = max(0, min(image_height, _to_int(update.get("y"), int(field["y"]))))
            item["width"] = max(24, min(image_width, _to_int(update.get("width"), int(field["width"]))))
            item["height"] = max(18, min(image_height, _to_int(update.get("height"), int(field["height"]))))
            item["font_size"] = max(8, min(220, _to_int(update.get("font_size"), int(field["font_size"]))))
            merged.append(item)
        else:
            merged.append(field)
    return normalize_fields(merged, image_width, image_height)


def _open_base_image(base_image: str | Path | bytes | BytesIO | Image.Image) -> Image.Image:
    if isinstance(base_image, Image.Image):
        return base_image.convert("RGBA")
    if isinstance(base_image, bytes):
        return Image.open(BytesIO(base_image)).convert("RGBA")
    if hasattr(base_image, "read"):
        return Image.open(base_image).convert("RGBA")
    return Image.open(base_image).convert("RGBA")


def _render_free_canvas(
    base_image: str | Path | bytes | BytesIO | Image.Image,
    fields: list[dict[str, Any]],
) -> tuple[Image.Image, list[dict[str, Any]], list[dict[str, Any]]]:
    canvas = _open_base_image(base_image)
    width, height = canvas.size
    draw = ImageDraw.Draw(canvas, "RGBA")
    records: list[dict[str, Any]] = []
    overlap_boxes: list[dict[str, Any]] = []

    for field in normalize_fields(fields, width, height):
        if not field.get("enabled", True) or not field.get("placed", True):
            continue
        _draw_free_field(draw, field, int(field["x"]), int(field["y"]), records, overlap_boxes)

    return canvas, records, overlap_boxes


def _draw_free_field(
    draw: ImageDraw.ImageDraw,
    field: dict[str, Any],
    x: int,
    y: int,
    records: list[dict[str, Any]] | None = None,
    overlap_boxes: list[dict[str, Any]] | None = None,
) -> None:
    w = int(field["width"])
    h = int(field["height"])
    color = normalize_hex_color(str(field.get("color") or DEFAULT_COLOR))
    align = str(field.get("align") or "left")
    record_id = str(field.get("id") or field.get("name") or "campo")
    if field.get("render_label") and str(field.get("name") or "").strip():
        value_h = max(12, int(h * 0.62))
        label_h = max(10, h - value_h)
        draw_text_box(
            draw,
            str(field.get("value") or ""),
            (x, y, w, value_h),
            int(field["font_size"]),
            max(8, int(field["font_size"] * 0.55)),
            color,
            bold=bool(field.get("bold", True)),
            align=align,
            record_id=f"{record_id}-valor",
            records=records,
        )
        draw_text_box(
            draw,
            str(field.get("name") or ""),
            (x, y + value_h, w, label_h),
            max(8, int(field["font_size"] * 0.38)),
            8,
            color,
            bold=False,
            align=align,
            record_id=f"{record_id}-nome",
            records=records,
        )
    else:
        draw_text_box(
            draw,
            str(field.get("value") or ""),
            (x, y, w, h),
            int(field["font_size"]),
            max(8, int(field["font_size"] * 0.55)),
            color,
            bold=bool(field.get("bold", True)),
            align=align,
            record_id=record_id,
            records=records,
        )
    if overlap_boxes is not None:
        overlap_boxes.append({"id": record_id, "x": x, "y": y, "w": w, "h": h})


def render_free_preview_bytes(base_image: str | Path | bytes | BytesIO | Image.Image, fields: list[dict[str, Any]]) -> bytes:
    canvas, _records, _overlap_boxes = _render_free_canvas(base_image, fields)
    buffer = BytesIO()
    canvas.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def render_free_field_preview_bytes(field: dict[str, Any], image_width: int = 1122, image_height: int = 1402) -> bytes:
    normalized = normalize_field(field, [], int(field.get("order") or 1), image_width, image_height)
    width = max(24, int(normalized["width"]))
    height = max(18, int(normalized["height"]))
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(canvas, "RGBA")
    local_field = deepcopy(normalized)
    local_field["x"] = 0
    local_field["y"] = 0
    _draw_free_field(draw, local_field, 0, 0)
    buffer = BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


def render_free_field_preview_map(fields: list[dict[str, Any]], image_width: int = 1122, image_height: int = 1402) -> dict[str, bytes]:
    previews: dict[str, bytes] = {}
    for field in normalize_fields(fields, image_width, image_height):
        if not field.get("enabled", True):
            continue
        previews[str(field["id"])] = render_free_field_preview_bytes(field, image_width, image_height)
    return previews


def render_free_infographic(
    base_image: str | Path | bytes | BytesIO | Image.Image,
    fields: list[dict[str, Any]],
    output_png: str | Path,
    output_pdf: str | Path | None = None,
) -> RenderReport:
    canvas, records, overlap_boxes = _render_free_canvas(base_image, fields)
    width, height = canvas.size
    text_errors = validate_text_bounds(records, width, height)
    overlap_errors = validate_no_overlaps(overlap_boxes, padding=0)

    output_path = Path(output_png)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rgb = canvas.convert("RGB")
    rgb.save(output_path, format="PNG")

    output_pdf_path = None
    if output_pdf:
        output_pdf_path = Path(output_pdf)
        output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
        rgb.save(output_pdf_path, "PDF", resolution=300.0)

    return RenderReport(
        output_png=str(output_path),
        output_pdf=str(output_pdf_path) if output_pdf_path else None,
        width=width,
        height=height,
        text_errors=text_errors,
        overlap_errors=overlap_errors,
        template_id="imagem_base_livre",
        template_version=str(FREE_MODE_SCHEMA_VERSION),
    )


def free_mode_export_names(base_image_name: str, today: Any) -> dict[str, str]:
    slug = slugify_filename(base_image_name or "imagem_base")
    stamp = today.isoformat()
    return {
        "png": f"infografico_{slug}_{stamp}.png",
        "pdf": f"infografico_{slug}_{stamp}.pdf",
        "fields": f"campos_{slug}_{stamp}.csv",
        "config": f"config_imagem_base_{slug}_{stamp}.yaml",
        "validation": f"relatorio_validacao_{slug}_{stamp}.txt",
    }

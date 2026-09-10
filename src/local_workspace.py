from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import Any
import zipfile

from PIL import Image

from .catalog import default_indicator_definitions, normalize_indicator_definition
from .data_binding import fields_from_dataset_observations, update_bound_elements
from .data_loader import load_csv
from .free_mode import normalize_fields, render_free_infographic, render_free_preview_bytes


LOCAL_SCHEMA_VERSION = 1
DEFAULT_TEMPLATE = {"id": "institucional_claro_v1", "version": "1.0"}
SUPPORTED_IMAGES = {".png", ".jpg", ".jpeg"}


class LocalWorkspaceError(RuntimeError):
    pass


@dataclass(frozen=True)
class UpdatePreview:
    infographic_id: str
    filename: str
    checksum: str
    previous_checksum: str
    elements: list[dict[str, Any]]
    changed: list[dict[str, Any]]
    unchanged: list[dict[str, Any]]
    missing: list[dict[str, Any]]
    incompatible: list[dict[str, Any]]

    @property
    def resolved_count(self) -> int:
        return sum(
            1
            for element in self.elements
            if not element.get("manual")
            and (element.get("binding") or {})
            and str((element.get("binding") or {}).get("status") or "ok") == "ok"
        )

    @property
    def is_compatible(self) -> bool:
        return self.resolved_count > 0

    @property
    def file_changed(self) -> bool:
        return self.checksum != self.previous_checksum

    @property
    def can_apply(self) -> bool:
        return self.is_compatible and not self.incompatible

    @property
    def status_label(self) -> str:
        if not self.is_compatible:
            return "CSV não corresponde"
        if self.incompatible:
            return "Valores incompatíveis"
        if self.missing:
            return "Campos ausentes"
        if not self.changed and self.file_changed:
            return "Nova versão, mesmos valores"
        if not self.file_changed:
            return "Arquivo já aplicado"
        return "Pronto para atualizar"

    def summary(self) -> dict[str, int]:
        return {
            "correspondentes": self.resolved_count,
            "alterados": len(self.changed),
            "inalterados": len(self.unchanged),
            "ausentes": len(self.missing),
            "incompativeis": len(self.incompatible),
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def safe_id(value: str, fallback: str = "infografico") -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return text or fallback


def _relative_path(value: str) -> PurePosixPath:
    raw = str(value or "").replace("\\", "/")
    path = PurePosixPath(raw)
    if path.is_absolute() or re.match(r"^[a-zA-Z]:/", raw) or ".." in path.parts or not path.parts:
        raise LocalWorkspaceError("Caminho local inválido no projeto.")
    return path


def _atomic_write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return path


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _image_info(data: bytes) -> tuple[int, int, str]:
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
        with Image.open(BytesIO(data)) as image:
            return int(image.width), int(image.height), str(image.format or "PNG").lower()
    except Exception as exc:
        raise LocalWorkspaceError(f"A imagem-base não pôde ser lida: {exc}") from exc


def _enrich_element(
    element: dict[str, Any],
    *,
    data_filename: str = "",
    data_checksum: str = "",
    institutional_source: str = "",
) -> dict[str, Any]:
    item = deepcopy(element)
    binding = deepcopy(item.get("binding") or {})
    is_manual = not bool(binding)
    item["field_id"] = str(binding.get("indicator_id") or item.get("field_id") or "")
    item["manual"] = bool(item.get("manual", is_manual))
    item["resolved_value"] = str(item.get("value") or "")
    item["resolution_status"] = str(binding.get("status") or ("manual" if item["manual"] else "ok"))
    item["page"] = max(1, int(item.get("page") or 1))
    item["layout"] = {
        "x": int(item.get("x") or 0),
        "y": int(item.get("y") or 0),
        "width": int(item.get("width") or 0),
        "height": int(item.get("height") or 0),
        "z_index": int(item.get("order") or 1),
    }
    item["style"] = {
        "font_size": int(item.get("font_size") or 8),
        "color": str(item.get("color") or "#0057B8"),
        "bold": bool(item.get("bold", True)),
        "align": str(item.get("align") or "left"),
        "show_label": bool(item.get("render_label", False)),
    }
    provenance = deepcopy(item.get("provenance") or {})
    provenance.update({
        "kind": "manual" if item["manual"] else "csv",
        "field_id": item["field_id"],
    })
    if not item["manual"]:
        current_filename = str(data_filename or item.get("data_filename") or provenance.get("filename") or "")
        item["data_filename"] = current_filename
        provenance.update({
            "filename": current_filename,
            "checksum": str(data_checksum or binding.get("dataset_version_id") or provenance.get("checksum") or ""),
            "source_column": str(binding.get("source_column") or provenance.get("source_column") or ""),
            "operation": str(binding.get("operation") or provenance.get("operation") or ""),
            "filters": deepcopy(binding.get("filters") or provenance.get("filters") or {}),
            "raw_value": str(binding.get("raw_value") if binding.get("raw_value") is not None else provenance.get("raw_value") or ""),
            "display_value": str(binding.get("display_value") or item.get("value") or ""),
            "period": str(binding.get("period") or provenance.get("period") or ""),
            "recorte": str(binding.get("recorte") or provenance.get("recorte") or ""),
            "institutional_source": str(institutional_source or provenance.get("institutional_source") or ""),
        })
    item["provenance"] = provenance
    return item


def validate_document(document: dict[str, Any], workspace_root: Path | None = None) -> list[str]:
    errors: list[str] = []
    if int(document.get("schema_version") or 0) != LOCAL_SCHEMA_VERSION:
        errors.append("versão de esquema ausente ou incompatível")
    if not safe_id(str(document.get("id") or ""), ""):
        errors.append("ID do infográfico ausente")
    if not str(document.get("name") or "").strip():
        errors.append("nome do infográfico ausente")
    canvas = document.get("canvas") or {}
    if int(canvas.get("width") or 0) <= 0 or int(canvas.get("height") or 0) <= 0:
        errors.append("dimensões do canvas inválidas")
    ids: set[str] = set()
    for element in document.get("elements") or []:
        element_id = str(element.get("id") or "")
        if not element_id:
            errors.append("elemento sem ID")
        elif element_id in ids:
            errors.append(f"ID de elemento duplicado: {element_id}")
        ids.add(element_id)
        if element.get("type") == "chart":
            series = (element.get("chart") or {}).get("series") or []
            if len(series) < 2:
                errors.append(f"{element_id}: gráfico precisa de pelo menos dois itens")
            for series_item in series:
                if series_item.get("raw_value") in (None, ""):
                    errors.append(f"{element_id}: valor numérico ausente no gráfico")
        elif not element.get("manual") and not (element.get("binding") or {}).get("indicator_id"):
            errors.append(f"{element_id}: elemento visível sem proveniência")
    for section in ("base_image", "data_source"):
        value = str((document.get(section) or {}).get("path") or "")
        if value:
            try:
                relative = _relative_path(value)
                if workspace_root and section == "base_image" and not (workspace_root / Path(*relative.parts)).is_file():
                    errors.append("imagem-base não encontrada")
            except LocalWorkspaceError as exc:
                errors.append(str(exc))
    return errors


def is_ephemeral_environment(root: Path | None = None) -> bool:
    mode = os.environ.get("INFOGRAPHICS_STORAGE_MODE", "").strip().lower()
    if mode in {"persistent", "local"}:
        return False
    if mode in {"ephemeral", "temporary"}:
        return True
    candidate = str((root or Path.cwd()).resolve()).replace("\\", "/").lower()
    return "/mount/src/" in candidate or bool(os.environ.get("STREAMLIT_SHARING_MODE"))


class LocalInfographicWorkspace:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.infographics_dir = self.root / "infograficos"
        self.images_dir = self.root / "imagens" / "infograficos"
        self.data_dir = self.root / "dados"
        self.exports_dir = self.root / "exportacoes"
        self.thumbnails_dir = self.infographics_dir / ".miniaturas"
        self.catalog_path = self.data_dir / "catalogo_campos.json"

    def bootstrap(self) -> "LocalInfographicWorkspace":
        for directory in (self.infographics_dir, self.images_dir, self.data_dir, self.exports_dir, self.thumbnails_dir):
            directory.mkdir(parents=True, exist_ok=True)
        defaults = [
            {
                **normalize_indicator_definition(item),
                "source_key": item["id"],
                "data_type": "percentage" if item.get("format") == "percent_pt_br" else "number",
                "active": True,
            }
            for item in default_indicator_definitions()
        ]
        if self.catalog_path.exists():
            try:
                catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise LocalWorkspaceError(f"Catálogo de campos inválido: {exc}") from exc
            fields = list(catalog.get("fields") or [])
            defaults_by_id = {item["id"]: item for item in defaults}
            merged_fields = []
            changed = False
            for field in fields:
                item = deepcopy(field)
                default = defaults_by_id.get(str(item.get("id") or ""))
                if default:
                    for key in ("aliases", "references", "allowed_operations"):
                        current_values = [str(value) for value in item.get(key) or []]
                        merged_values = current_values + [value for value in default[key] if value not in current_values]
                        if merged_values != current_values:
                            item[key] = merged_values
                            changed = True
                merged_fields.append(item)
            existing_ids = {str(item.get("id") or "") for item in merged_fields}
            missing = [item for item in defaults if item["id"] not in existing_ids]
            if missing or changed:
                catalog = {**catalog, "schema_version": 1, "fields": [*merged_fields, *missing]}
                _atomic_write(self.catalog_path, _json_bytes(catalog))
        else:
            catalog = {"schema_version": 1, "fields": defaults}
            _atomic_write(self.catalog_path, _json_bytes(catalog))
        return self

    def resolve(self, relative: str) -> Path:
        path = _relative_path(relative)
        resolved = (self.root / Path(*path.parts)).resolve()
        if self.root != resolved and self.root not in resolved.parents:
            raise LocalWorkspaceError("Caminho fora da área de trabalho.")
        return resolved

    def catalog(self, query: str = "", category: str = "") -> list[dict[str, Any]]:
        try:
            payload = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise LocalWorkspaceError(f"Catálogo de campos inválido: {exc}") from exc
        fields = [normalize_indicator_definition(item) | {
            "source_key": str(item.get("source_key") or item.get("id") or ""),
            "data_type": str(item.get("data_type") or "number"),
            "active": bool(item.get("active", True)),
        } for item in payload.get("fields") or []]
        needle = safe_id(query, "")
        result = []
        for item in fields:
            if not item["active"]:
                continue
            if category and item.get("category") != category:
                continue
            searchable = " ".join([item.get("id", ""), item.get("label", ""), *item.get("aliases", [])])
            if needle and needle not in safe_id(searchable, ""):
                continue
            result.append(item)
        return sorted(result, key=lambda item: (str(item.get("category") or ""), str(item.get("label") or "")))

    def json_path(self, infographic_id: str) -> Path:
        return self.infographics_dir / f"{safe_id(infographic_id)}.json"

    def load(self, infographic_id: str) -> dict[str, Any]:
        path = self.json_path(infographic_id)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise LocalWorkspaceError("Infográfico não encontrado.") from exc
        except Exception as exc:
            raise LocalWorkspaceError(f"JSON inválido em {path.name}: {exc}") from exc
        errors = validate_document(document, self.root)
        if errors:
            raise LocalWorkspaceError(f"{path.name}: " + "; ".join(errors))
        return document

    def discover(self) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        projects: list[dict[str, Any]] = []
        issues: list[dict[str, str]] = []
        for path in sorted(self.infographics_dir.glob("*.json")):
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
                errors = validate_document(document, self.root)
                if errors:
                    raise LocalWorkspaceError("; ".join(errors))
                projects.append(self.summary(document, path))
            except Exception as exc:
                issues.append({"file": path.name, "error": str(exc)})
        projects.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return projects, issues

    def summary(self, document: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
        data_source = document.get("data_source") or {}
        status = "Atualizado"
        data_path = str(data_source.get("path") or "")
        if data_path:
            try:
                current = self.resolve(data_path).read_bytes()
                if sha256_bytes(current) != str(data_source.get("checksum") or ""):
                    status = "Dados alterados"
            except Exception:
                status = "Campo ausente"
        unresolved = [item for item in document.get("elements") or [] if str((item.get("binding") or {}).get("status") or "ok") != "ok" and not item.get("manual")]
        if unresolved:
            status = "Campo ausente"
        return {
            "id": document["id"],
            "name": document["name"],
            "updated_at": document.get("updated_at") or "",
            "data_file": str(data_source.get("filename") or "Sem dados-base"),
            "status": status,
            "element_count": len(document.get("elements") or []),
            "path": path or self.json_path(document["id"]),
        }

    def create_fields(self, csv_bytes: bytes, filename: str, infographic_id: str, canvas: tuple[int, int], existing: list[dict[str, Any]] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
        dataframe, _profile = load_csv(BytesIO(csv_bytes), separator=None, encoding=None, has_header=None)
        checksum = sha256_bytes(csv_bytes)
        fields = fields_from_dataset_observations(
            dataframe,
            infographic_id,
            checksum,
            self.catalog(),
            int(canvas[0]),
            int(canvas[1]),
            existing_fields=existing or [],
        )
        warnings = []
        if not fields:
            warnings.append("Nenhum campo recorrente foi reconhecido. Confira se o CSV possui colunas de indicador e valor.")
        catalog_by_id = {item["id"]: item for item in self.catalog()}
        for field in fields:
            indicator_id = str((field.get("binding") or {}).get("indicator_id") or "")
            field["data_filename"] = filename
            field["resolved_value"] = field.get("value", "")
            field["category"] = str(catalog_by_id.get(indicator_id, {}).get("category") or "Outros")
            field["provenance"] = {"kind": "csv", "filename": filename, "field_id": indicator_id}
        return fields, warnings

    def save(
        self,
        *,
        name: str,
        elements: list[dict[str, Any]],
        canvas: tuple[int, int],
        base_bytes: bytes | None = None,
        base_filename: str = "",
        data_bytes: bytes | None = None,
        data_filename: str = "",
        infographic_id: str = "",
        metadata: dict[str, Any] | None = None,
        template: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        clean_name = str(name or "").strip()
        if not clean_name:
            raise LocalWorkspaceError("Informe um nome para o infográfico.")
        project_id = safe_id(infographic_id or clean_name)
        path = self.json_path(project_id)
        existing = self.load(project_id) if path.exists() else None
        if not infographic_id and path.exists():
            raise LocalWorkspaceError("Já existe um infográfico com esse nome. Abra o existente ou escolha outro nome.")
        created_at = str((existing or {}).get("created_at") or utc_now())

        if base_bytes is not None:
            suffix = Path(base_filename).suffix.lower()
            if suffix not in SUPPORTED_IMAGES:
                raise LocalWorkspaceError("A imagem-base deve ser PNG ou JPG.")
            width, height, _format = _image_info(base_bytes)
            if (width, height) != (int(canvas[0]), int(canvas[1])):
                raise LocalWorkspaceError("As dimensões do canvas não correspondem à imagem-base.")
            base_relative = PurePosixPath("imagens") / "infograficos" / project_id / f"base{suffix}"
            _atomic_write(self.resolve(str(base_relative)), base_bytes)
            base_info = {"path": str(base_relative), "checksum": sha256_bytes(base_bytes)}
        elif existing:
            base_info = deepcopy(existing.get("base_image") or {})
        else:
            raise LocalWorkspaceError("Carregue uma imagem-base antes de salvar.")

        if data_bytes is not None:
            data_relative = PurePosixPath("dados") / f"{project_id}.csv"
            _atomic_write(self.resolve(str(data_relative)), data_bytes)
            data_info = {
                "path": str(data_relative),
                "filename": Path(data_filename or "base_dados.csv").name,
                "checksum": sha256_bytes(data_bytes),
                "loaded_at": utc_now(),
            }
        elif existing:
            data_info = deepcopy(existing.get("data_source") or {})
        else:
            data_info = {"path": "", "filename": "", "checksum": "", "loaded_at": ""}

        normalized = normalize_fields(elements, int(canvas[0]), int(canvas[1]))
        for element in normalized:
            binding = element.get("binding") or {}
            if binding:
                binding["dataset_id"] = project_id
                if data_info.get("checksum"):
                    binding["dataset_version_id"] = data_info["checksum"]
                    binding["applied_version_id"] = data_info["checksum"]
                element["binding"] = binding
        document_metadata = deepcopy(metadata or (existing or {}).get("metadata") or {})
        document = {
            "schema_version": LOCAL_SCHEMA_VERSION,
            "id": project_id,
            "name": clean_name,
            "created_at": created_at,
            "updated_at": utc_now(),
            "template": deepcopy(template or (existing or {}).get("template") or DEFAULT_TEMPLATE),
            "base_image": base_info,
            "data_source": data_info,
            "canvas": {"width": int(canvas[0]), "height": int(canvas[1])},
            "elements": [
                _enrich_element(
                    item,
                    data_filename=str(data_info.get("filename") or ""),
                    data_checksum=str(data_info.get("checksum") or ""),
                    institutional_source=str(document_metadata.get("source") or ""),
                )
                for item in normalized
            ],
            "metadata": document_metadata,
        }
        errors = validate_document(document, self.root)
        if errors:
            raise LocalWorkspaceError("Não foi possível salvar: " + "; ".join(errors))
        _atomic_write(path, _json_bytes(document))
        self.write_thumbnail(document)
        return document

    def write_thumbnail(self, document: dict[str, Any]) -> Path | None:
        try:
            base = self.resolve(str((document.get("base_image") or {}).get("path") or ""))
            preview = Image.open(BytesIO(render_free_preview_bytes(base, document.get("elements") or []))).convert("RGB")
            preview.thumbnail((320, 400), Image.Resampling.LANCZOS)
            output = BytesIO()
            preview.save(output, "PNG")
            path = self.thumbnails_dir / f"{document['id']}.png"
            return _atomic_write(path, output.getvalue())
        except Exception:
            return None

    def update_preview(self, infographic_id: str, csv_bytes: bytes, filename: str) -> UpdatePreview:
        document = self.load(infographic_id)
        dataframe, _profile = load_csv(BytesIO(csv_bytes), separator=None, encoding=None, has_header=None)
        checksum = sha256_bytes(csv_bytes)
        canvas = document.get("canvas") or {}
        updated, changed = update_bound_elements(
            document.get("elements") or [],
            infographic_id,
            checksum,
            dataframe,
            self.catalog(),
            int(canvas.get("width") or 1122),
            int(canvas.get("height") or 1402),
        )
        changed_ids = {(str(item.get("element_id")), str(item.get("indicator_id"))) for item in changed}
        unchanged: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []
        incompatible: list[dict[str, Any]] = []
        for element in updated:
            binding = element.get("binding") or {}
            if not binding or element.get("manual"):
                continue
            status = str(binding.get("status") or "ok")
            if status in {"missing_value", "missing_binding"}:
                missing.append({"element_id": element.get("id"), "field_id": binding.get("indicator_id", ""), "message": binding.get("error", "Campo ausente")})
            elif status != "ok":
                incompatible.append({"element_id": element.get("id"), "field_id": binding.get("indicator_id", ""), "message": binding.get("error", status)})
            elif element.get("type") != "chart" and (str(element.get("id")), str(binding.get("indicator_id"))) not in changed_ids:
                unchanged.append({"element_id": element.get("id"), "field_id": binding.get("indicator_id", ""), "value": element.get("value", "")})
        previous_checksum = str((document.get("data_source") or {}).get("checksum") or "")
        return UpdatePreview(infographic_id, Path(filename).name, checksum, previous_checksum, updated, changed, unchanged, missing, incompatible)

    def apply_update(self, preview: UpdatePreview, csv_bytes: bytes) -> dict[str, Any]:
        if not preview.can_apply:
            if not preview.is_compatible:
                raise LocalWorkspaceError("O CSV selecionado não corresponde aos campos deste infográfico.")
            raise LocalWorkspaceError("A atualização possui valores incompatíveis e não pode ser aplicada.")
        document = self.load(preview.infographic_id)
        data_relative = PurePosixPath("dados") / f"{preview.infographic_id}.csv"
        _atomic_write(self.resolve(str(data_relative)), csv_bytes)
        document["data_source"] = {
            "path": str(data_relative),
            "filename": preview.filename,
            "checksum": preview.checksum,
            "loaded_at": utc_now(),
        }
        document["elements"] = [
            _enrich_element(
                item,
                data_filename=preview.filename,
                data_checksum=preview.checksum,
                institutional_source=str((document.get("metadata") or {}).get("source") or ""),
            )
            for item in preview.elements
        ]
        document["updated_at"] = utc_now()
        errors = validate_document(document, self.root)
        if errors:
            raise LocalWorkspaceError("Atualização inválida: " + "; ".join(errors))
        _atomic_write(self.json_path(preview.infographic_id), _json_bytes(document))
        self.write_thumbnail(document)
        return document

    def export(self, infographic_id: str) -> tuple[Path, Path, list[str]]:
        document = self.load(infographic_id)
        unresolved = [item for item in document.get("elements") or [] if not item.get("manual") and str((item.get("binding") or {}).get("status") or "ok") != "ok"]
        if unresolved:
            raise LocalWorkspaceError("Corrija os campos ausentes ou incompatíveis antes de exportar.")
        base = self.resolve(str((document.get("base_image") or {}).get("path") or ""))
        output_png = self.exports_dir / f"{infographic_id}.png"
        output_pdf = self.exports_dir / f"{infographic_id}.pdf"
        report = render_free_infographic(base, document.get("elements") or [], output_png, output_pdf)
        return output_png, output_pdf, report.errors

    def delete(self, infographic_id: str) -> list[Path]:
        document = self.load(infographic_id)
        project_id = str(document["id"])
        removed: list[Path] = []

        linked_files = [
            self.json_path(project_id),
            self.thumbnails_dir / f"{project_id}.png",
            self.exports_dir / f"{project_id}.png",
            self.exports_dir / f"{project_id}.pdf",
            self.exports_dir / f"{project_id}_projeto.zip",
        ]
        for section in ("base_image", "data_source"):
            relative = str((document.get(section) or {}).get("path") or "")
            if relative:
                linked_files.append(self.resolve(relative))

        for path in dict.fromkeys(linked_files):
            resolved = path.resolve()
            if self.root != resolved and self.root not in resolved.parents:
                raise LocalWorkspaceError("A exclusão tentou acessar um arquivo fora da área de trabalho.")
            if resolved.is_file():
                resolved.unlink()
                removed.append(resolved)

        project_images = (self.images_dir / safe_id(project_id)).resolve()
        if self.images_dir.resolve() not in project_images.parents:
            raise LocalWorkspaceError("Pasta de imagens inválida para exclusão.")
        if project_images.is_dir():
            shutil.rmtree(project_images)
            removed.append(project_images)
        return removed

    def package(self, infographic_id: str) -> Path:
        document = self.load(infographic_id)
        package_path = self.exports_dir / f"{infographic_id}_projeto.zip"
        included = [self.json_path(infographic_id), self.catalog_path]
        for section in ("base_image", "data_source"):
            relative = str((document.get(section) or {}).get("path") or "")
            if relative:
                included.append(self.resolve(relative))
        package_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in included:
                if path.is_file():
                    archive.write(path, path.relative_to(self.root).as_posix())
        return package_path

    def migrate_yaml(self, yaml_path: str | Path, base_bytes: bytes | None = None, base_filename: str = "") -> dict[str, Any]:
        import yaml

        path = Path(yaml_path)
        try:
            config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            raise LocalWorkspaceError(f"YAML antigo inválido: {exc}") from exc
        if config.get("mode") != "imagem_base":
            raise LocalWorkspaceError("O arquivo não pertence ao modo imagem-base.")
        base = config.get("base_image") or {}
        width = int(base.get("width") or 1122)
        height = int(base.get("height") or 1402)
        return self.save(
            name=str(config.get("name") or path.stem),
            elements=config.get("fields") or [],
            canvas=(width, height),
            base_bytes=base_bytes,
            base_filename=base_filename or str(base.get("file") or "base.png"),
            metadata={"migrated_from": path.name},
        )

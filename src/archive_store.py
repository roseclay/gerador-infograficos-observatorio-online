from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4
import zipfile

from PIL import Image

from .catalog import default_indicator_definitions, normalize_indicator_definition, validate_indicator_definition
from .configuration import slugify_filename
from .data_binding import duplicate_logical_keys, update_bound_elements
from .data_loader import load_csv
from .free_mode import build_free_mode_config_with_name, normalize_fields


ARCHIVE_SCHEMA_VERSION = 1
MAX_CSV_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_filename(name: str, fallback: str = "arquivo") -> str:
    raw = Path(str(name or fallback)).name
    stem = slugify_filename(raw) or fallback
    suffix = Path(raw).suffix.lower()
    if suffix and len(suffix) <= 12:
        return f"{stem}{suffix}"
    return stem


def _new_id(prefix: str, name: str = "") -> str:
    slug = slugify_filename(name)[:56] if name else ""
    tail = uuid4().hex[:10]
    return f"{prefix}_{slug}_{tail}" if slug else f"{prefix}_{tail}"


def empty_archive_state() -> dict[str, Any]:
    return {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "datasets": [],
        "dataset_versions": [],
        "base_images": [],
        "base_image_versions": [],
        "infographics": [],
        "infographic_revisions": [],
        "generations": [],
        "indicator_definitions": default_indicator_definitions(),
    }


def _latest_revision(revisions: list[dict[str, Any]], parent_key: str, parent_id: str) -> dict[str, Any] | None:
    candidates = [item for item in revisions if item.get(parent_key) == parent_id]
    if not candidates:
        return None
    return max(candidates, key=lambda item: int(item.get("revision") or item.get("sequence") or 0))


class LocalArchiveStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.files_root = self.root / "files"
        self.state_path = self.root / "archive.json"

    def bootstrap(self) -> "LocalArchiveStore":
        self.root.mkdir(parents=True, exist_ok=True)
        self.files_root.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            self._save_state(empty_archive_state())
        else:
            state = self._load_state()
            if int(state.get("schema_version") or 0) < ARCHIVE_SCHEMA_VERSION:
                state["schema_version"] = ARCHIVE_SCHEMA_VERSION
            existing = {item.get("id") for item in state.get("indicator_definitions") or []}
            for definition in default_indicator_definitions():
                if definition["id"] not in existing:
                    state.setdefault("indicator_definitions", []).append(definition)
            self._save_state(state)
        return self

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return empty_archive_state()
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _save_state(self, state: dict[str, Any]) -> None:
        state["updated_at"] = utc_now()
        self.root.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(self.state_path)

    def diagnostics(self) -> dict[str, Any]:
        state = self._load_state()
        return {
            "provider": "local",
            "root": str(self.root),
            "datasets": len(state.get("datasets") or []),
            "base_images": len(state.get("base_images") or []),
            "infographics": len(state.get("infographics") or []),
            "indicator_definitions": len(state.get("indicator_definitions") or []),
        }

    def list_indicator_definitions(self) -> list[dict[str, Any]]:
        return [normalize_indicator_definition(item) for item in self._load_state().get("indicator_definitions") or []]

    def save_indicator_definition(self, definition: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        item = normalize_indicator_definition(definition)
        errors = validate_indicator_definition(item)
        if errors:
            return None, errors
        state = self._load_state()
        definitions = [normalize_indicator_definition(value) for value in state.get("indicator_definitions") or []]
        for index, current in enumerate(definitions):
            if current["id"] == item["id"]:
                item["definition_version"] = int(current.get("definition_version") or 1) + 1
                definitions[index] = item
                state["indicator_definitions"] = definitions
                self._save_state(state)
                return item, []
        definitions.append(item)
        state["indicator_definitions"] = definitions
        self._save_state(state)
        return item, []

    def register_dataset(self, name: str, description: str = "", owner: str = "", public_source: str = "") -> dict[str, Any]:
        name = str(name or "").strip()
        if not name:
            raise ValueError("nome do conjunto ausente")
        state = self._load_state()
        for dataset in state.get("datasets") or []:
            if dataset.get("name", "").strip().casefold() == name.casefold():
                dataset.update({
                    "description": description or dataset.get("description", ""),
                    "owner": owner or dataset.get("owner", ""),
                    "public_source": public_source or dataset.get("public_source", ""),
                    "updated_at": utc_now(),
                })
                self._save_state(state)
                return dataset
        dataset = {
            "id": _new_id("ds", name),
            "name": name,
            "description": str(description or "").strip(),
            "owner": str(owner or "").strip(),
            "public_source": str(public_source or "").strip(),
            "active_version_id": "",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        state.setdefault("datasets", []).append(dataset)
        self._save_state(state)
        return dataset

    def add_dataset_version(
        self,
        dataset_id: str,
        csv_bytes: bytes,
        file_name: str,
        *,
        period: str = "",
        public_source: str = "",
        source_updated_at: str = "",
        mapping: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if len(csv_bytes) > MAX_CSV_BYTES:
            raise ValueError("CSV maior que o limite local configurado")
        state = self._load_state()
        dataset = self.get_dataset(dataset_id, state)
        if dataset is None:
            raise ValueError("conjunto de dados não encontrado")
        checksum = sha256_bytes(csv_bytes)
        comparable = {
            "dataset_id": dataset_id,
            "checksum": checksum,
            "period": str(period or ""),
            "public_source": str(public_source or dataset.get("public_source") or ""),
            "source_updated_at": str(source_updated_at or ""),
            "mapping": mapping or {},
        }
        for version in state.get("dataset_versions") or []:
            if all(version.get(key) == value for key, value in comparable.items()):
                return {**version, "idempotent": True}
        validation_errors: list[str] = []
        try:
            dataframe, profile = load_csv(BytesIO(csv_bytes), separator=None, encoding=None, has_header=None)
            duplicate_keys = duplicate_logical_keys(dataframe)
            if not duplicate_keys.empty:
                validation_errors.append("chave lógica duplicada no CSV")
            schema = {
                "columns": profile.columns,
                "dtypes": profile.dtypes,
                "row_count": profile.row_count,
                "data_shape": profile.data_shape,
                "separator": profile.separator,
                "encoding": profile.encoding,
                "has_header": profile.has_header,
            }
        except Exception as exc:
            schema = {}
            validation_errors.append(f"CSV inválido: {exc}")
        revisions = [version for version in state.get("dataset_versions") or [] if version.get("dataset_id") == dataset_id]
        sequence = max([int(version.get("sequence") or 0) for version in revisions] or [0]) + 1
        version_id = _new_id("dsv", f"{dataset.get('name')}_{sequence}")
        relative_path = Path("datasets") / dataset_id / f"v{sequence:04d}" / safe_filename(file_name, "dados.csv")
        absolute_path = self.files_root / relative_path
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_bytes(csv_bytes)
        version = {
            "id": version_id,
            "dataset_id": dataset_id,
            "sequence": sequence,
            "checksum": checksum,
            "file_name": Path(file_name).name,
            "storage_path": str(relative_path).replace("\\", "/"),
            "schema": schema,
            "mapping": mapping or {},
            "period": str(period or ""),
            "public_source": str(public_source or dataset.get("public_source") or ""),
            "source_updated_at": str(source_updated_at or ""),
            "status": "valid" if not validation_errors else "invalid",
            "validation_errors": validation_errors,
            "uploaded_at": utc_now(),
            "activated_at": utc_now() if not validation_errors else "",
        }
        state.setdefault("dataset_versions", []).append(version)
        if not validation_errors:
            for item in state["datasets"]:
                if item["id"] == dataset_id:
                    item["active_version_id"] = version_id
                    item["updated_at"] = utc_now()
                    if version["public_source"]:
                        item["public_source"] = version["public_source"]
        self._save_state(state)
        return version

    def get_dataset(self, dataset_id: str, state: dict[str, Any] | None = None) -> dict[str, Any] | None:
        state = state or self._load_state()
        return next((item for item in state.get("datasets") or [] if item.get("id") == dataset_id), None)

    def list_datasets(self) -> list[dict[str, Any]]:
        state = self._load_state()
        versions = state.get("dataset_versions") or []
        result = []
        for dataset in state.get("datasets") or []:
            item = deepcopy(dataset)
            item["versions"] = [version for version in versions if version.get("dataset_id") == dataset["id"]]
            item["dependent_count"] = len(self.list_dependents(dataset["id"], state))
            result.append(item)
        return sorted(result, key=lambda item: item.get("updated_at", ""), reverse=True)

    def get_dataset_version(self, version_id: str, state: dict[str, Any] | None = None) -> dict[str, Any] | None:
        state = state or self._load_state()
        return next((item for item in state.get("dataset_versions") or [] if item.get("id") == version_id), None)

    def active_dataset_version(self, dataset_id: str) -> dict[str, Any] | None:
        dataset = self.get_dataset(dataset_id)
        if not dataset or not dataset.get("active_version_id"):
            return None
        return self.get_dataset_version(dataset["active_version_id"])

    def dataset_version_path(self, version: dict[str, Any]) -> Path:
        return self.files_root / str(version.get("storage_path") or "")

    def load_dataset_dataframe(self, version_id: str) -> tuple[Any, dict[str, Any]]:
        version = self.get_dataset_version(version_id)
        if version is None:
            raise ValueError("versão de dados não encontrada")
        path = self.dataset_version_path(version)
        schema = version.get("schema") or {}
        dataframe, _profile = load_csv(
            path,
            separator=schema.get("separator"),
            encoding=schema.get("encoding"),
            has_header=schema.get("has_header"),
        )
        return dataframe, version

    def register_base_image(self, name: str, description: str = "", kind: str = "production") -> dict[str, Any]:
        name = str(name or "").strip()
        if not name:
            raise ValueError("nome da imagem-base ausente")
        kind = "reference" if kind == "reference" else "production"
        state = self._load_state()
        for base in state.get("base_images") or []:
            if base.get("name", "").strip().casefold() == name.casefold():
                base.update({"description": description or base.get("description", ""), "kind": kind, "updated_at": utc_now()})
                self._save_state(state)
                return base
        base = {
            "id": _new_id("base", name),
            "name": name,
            "description": str(description or "").strip(),
            "kind": kind,
            "active_version_id": "",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        state.setdefault("base_images", []).append(base)
        self._save_state(state)
        return base

    def add_base_image_version(self, base_id: str, image_bytes: bytes, file_name: str, *, review_status: str = "pending") -> dict[str, Any]:
        state = self._load_state()
        base = next((item for item in state.get("base_images") or [] if item.get("id") == base_id), None)
        if base is None:
            raise ValueError("imagem-base não encontrada")
        checksum = sha256_bytes(image_bytes)
        for version in state.get("base_image_versions") or []:
            if version.get("base_image_id") == base_id and version.get("checksum") == checksum and version.get("review_status") == review_status:
                return {**version, "idempotent": True}
        validation_errors: list[str] = []
        try:
            image = Image.open(BytesIO(image_bytes))
            width, height = image.size
            image_format = image.format or Path(file_name).suffix.lstrip(".").upper()
            if width * height > MAX_IMAGE_PIXELS:
                validation_errors.append("imagem maior que o limite de pixels configurado")
        except Exception as exc:
            width, height, image_format = 0, 0, ""
            validation_errors.append(f"imagem inválida: {exc}")
        revisions = [version for version in state.get("base_image_versions") or [] if version.get("base_image_id") == base_id]
        sequence = max([int(version.get("sequence") or 0) for version in revisions] or [0]) + 1
        version_id = _new_id("bsv", f"{base.get('name')}_{sequence}")
        relative_path = Path("base_images") / base_id / f"v{sequence:04d}" / safe_filename(file_name, "base.png")
        absolute_path = self.files_root / relative_path
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_bytes(image_bytes)
        version = {
            "id": version_id,
            "base_image_id": base_id,
            "sequence": sequence,
            "checksum": checksum,
            "file_name": Path(file_name).name,
            "storage_path": str(relative_path).replace("\\", "/"),
            "width": width,
            "height": height,
            "format": image_format,
            "review_status": review_status,
            "status": "valid" if not validation_errors else "invalid",
            "validation_errors": validation_errors,
            "uploaded_at": utc_now(),
        }
        state.setdefault("base_image_versions", []).append(version)
        if not validation_errors:
            for item in state["base_images"]:
                if item["id"] == base_id:
                    item["active_version_id"] = version_id
                    item["updated_at"] = utc_now()
        self._save_state(state)
        return version

    def list_base_images(self, production_only: bool = False) -> list[dict[str, Any]]:
        state = self._load_state()
        versions = state.get("base_image_versions") or []
        bases = []
        for base in state.get("base_images") or []:
            if production_only and base.get("kind") == "reference":
                continue
            item = deepcopy(base)
            item["versions"] = [version for version in versions if version.get("base_image_id") == base["id"]]
            bases.append(item)
        return sorted(bases, key=lambda item: item.get("updated_at", ""), reverse=True)

    def get_base_image_version(self, version_id: str, state: dict[str, Any] | None = None) -> dict[str, Any] | None:
        state = state or self._load_state()
        return next((item for item in state.get("base_image_versions") or [] if item.get("id") == version_id), None)

    def base_image_version_path(self, version: dict[str, Any]) -> Path:
        return self.files_root / str(version.get("storage_path") or "")

    def base_image_version_bytes(self, version: dict[str, Any]) -> bytes:
        return self.base_image_version_path(version).read_bytes()

    def save_infographic(
        self,
        *,
        name: str,
        base_image_id: str,
        base_image_version_id: str,
        fields: list[dict[str, Any]],
        image_size: tuple[int, int],
        mode: str = "imagem_base",
        infographic_id: str = "",
        expected_revision_id: str = "",
        owner: str = "",
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not str(name or "").strip():
            raise ValueError("nome do infográfico ausente")
        state = self._load_state()
        now = utc_now()
        if infographic_id:
            infographic = next((item for item in state.get("infographics") or [] if item.get("id") == infographic_id), None)
            if infographic is None:
                raise ValueError("infográfico não encontrado")
            latest = _latest_revision(state.get("infographic_revisions") or [], "infographic_id", infographic_id)
            if expected_revision_id and latest and latest.get("id") != expected_revision_id:
                return {"status": "conflict", "current_revision_id": latest.get("id"), "infographic": infographic}
            infographic.update({"name": name, "updated_at": now, "base_image_id": base_image_id, "base_image_version_id": base_image_version_id})
        else:
            infographic = {
                "id": _new_id("info", name),
                "name": name,
                "mode": mode,
                "base_image_id": base_image_id,
                "base_image_version_id": base_image_version_id,
                "created_at": now,
                "updated_at": now,
                "owner": owner,
                "latest_revision_id": "",
            }
            state.setdefault("infographics", []).append(infographic)
        latest = _latest_revision(state.get("infographic_revisions") or [], "infographic_id", infographic["id"])
        revision_number = int((latest or {}).get("revision") or 0) + 1
        normalized_fields = normalize_fields(fields, int(image_size[0] or 1122), int(image_size[1] or 1402))
        data_versions = []
        for field in normalized_fields:
            binding = field.get("binding") or {}
            if binding.get("dataset_id"):
                data_versions.append({
                    "dataset_id": binding.get("dataset_id"),
                    "applied_version_id": binding.get("applied_version_id") or binding.get("dataset_version_id") or "",
                    "binding_type": binding.get("type") or field.get("type") or "metric",
                })
        revision_config = deepcopy(config) if config else build_free_mode_config_with_name("", normalized_fields, image_size, name)
        revision_config["mode"] = mode
        revision_config["name"] = name
        revision_config["base_image"] = {
            **(revision_config.get("base_image") or {}),
            "id": base_image_id,
            "version_id": base_image_version_id,
            "width": int(image_size[0] or 0),
            "height": int(image_size[1] or 0),
        }
        revision_config["fields"] = normalized_fields
        revision = {
            "id": _new_id("infrev", f"{name}_{revision_number}"),
            "infographic_id": infographic["id"],
            "revision": revision_number,
            "layout_version": int((revision_config.get("schema_version") or 1)),
            "base_image_version_id": base_image_version_id,
            "data_versions": data_versions,
            "config": revision_config,
            "created_at": now,
            "owner": owner,
        }
        state.setdefault("infographic_revisions", []).append(revision)
        infographic["latest_revision_id"] = revision["id"]
        self._save_state(state)
        return {"status": "saved", "infographic": infographic, "revision": revision}

    def list_infographics(self) -> list[dict[str, Any]]:
        state = self._load_state()
        result = []
        for infographic in state.get("infographics") or []:
            latest = self.get_infographic_revision(infographic.get("latest_revision_id", ""), state)
            config = (latest or {}).get("config") or {}
            updates = self.check_infographic_updates(infographic["id"], state)
            result.append({
                **deepcopy(infographic),
                "revision": int((latest or {}).get("revision") or 0),
                "field_count": len(config.get("fields") or []),
                "updates_available": len(updates),
                "updated": infographic.get("updated_at", ""),
            })
        return sorted(result, key=lambda item: item.get("updated_at", ""), reverse=True)

    def get_infographic_revision(self, revision_id: str, state: dict[str, Any] | None = None) -> dict[str, Any] | None:
        state = state or self._load_state()
        return next((item for item in state.get("infographic_revisions") or [] if item.get("id") == revision_id), None)

    def latest_infographic_revision(self, infographic_id: str, state: dict[str, Any] | None = None) -> dict[str, Any] | None:
        state = state or self._load_state()
        return _latest_revision(state.get("infographic_revisions") or [], "infographic_id", infographic_id)

    def check_infographic_updates(self, infographic_id: str, state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        state = state or self._load_state()
        latest = self.latest_infographic_revision(infographic_id, state)
        if not latest:
            return []
        updates = []
        seen: set[tuple[str, str]] = set()
        for binding in latest.get("data_versions") or []:
            dataset_id = str(binding.get("dataset_id") or "")
            applied = str(binding.get("applied_version_id") or "")
            if (dataset_id, applied) in seen:
                continue
            seen.add((dataset_id, applied))
            dataset = self.get_dataset(dataset_id, state)
            active = self.get_dataset_version(dataset.get("active_version_id", ""), state) if dataset else None
            if active and active.get("id") != applied:
                updates.append({
                    "dataset_id": dataset_id,
                    "dataset_name": dataset.get("name", dataset_id) if dataset else dataset_id,
                    "applied_version_id": applied,
                    "active_version_id": active.get("id"),
                    "active_sequence": active.get("sequence"),
                    "active_checksum": active.get("checksum"),
                })
        return updates

    def apply_dataset_updates(self, infographic_id: str) -> dict[str, Any]:
        state = self._load_state()
        latest = self.latest_infographic_revision(infographic_id, state)
        infographic = next((item for item in state.get("infographics") or [] if item.get("id") == infographic_id), None)
        if latest is None or infographic is None:
            return {"status": "missing", "message": "infográfico não encontrado"}
        updates = self.check_infographic_updates(infographic_id, state)
        if not updates:
            return {"status": "current", "message": "infográfico já está na versão ativa dos dados"}
        config = deepcopy(latest.get("config") or {})
        fields = config.get("fields") or []
        changes: list[dict[str, Any]] = []
        definitions = state.get("indicator_definitions") or []
        image_size = (
            int((config.get("base_image") or {}).get("width") or 1122),
            int((config.get("base_image") or {}).get("height") or 1402),
        )
        for update in updates:
            dataframe, version = self.load_dataset_dataframe(update["active_version_id"])
            fields, field_changes = update_bound_elements(
                fields,
                update["dataset_id"],
                version["id"],
                dataframe,
                definitions,
                image_width=image_size[0],
                image_height=image_size[1],
            )
            changes.extend(field_changes)
        blocked = []
        for field in fields:
            binding = field.get("binding") or {}
            if binding.get("dataset_id") and binding.get("status") not in {"", "ok", None}:
                blocked.append(f"{field.get('name') or field.get('id')}: {binding.get('error') or binding.get('status')}")
        if blocked:
            return {"status": "blocked", "message": "\n".join(blocked), "changes": changes}
        config["fields"] = fields
        saved = self.save_infographic(
            name=infographic.get("name") or config.get("name") or "Infográfico",
            base_image_id=infographic.get("base_image_id") or (config.get("base_image") or {}).get("id", ""),
            base_image_version_id=infographic.get("base_image_version_id") or (config.get("base_image") or {}).get("version_id", ""),
            fields=fields,
            image_size=image_size,
            mode=config.get("mode") or "imagem_base",
            infographic_id=infographic_id,
            expected_revision_id=latest["id"],
            config=config,
        )
        return {"status": saved.get("status"), "message": "dados atualizados", "changes": changes, **saved}

    def list_dependents(self, dataset_id: str, state: dict[str, Any] | None = None) -> list[str]:
        state = state or self._load_state()
        dependents = []
        for infographic in state.get("infographics") or []:
            latest = self.get_infographic_revision(infographic.get("latest_revision_id", ""), state)
            if any(binding.get("dataset_id") == dataset_id for binding in (latest or {}).get("data_versions") or []):
                dependents.append(infographic["id"])
        return dependents

    def record_generation(self, infographic_id: str, revision_id: str, output_paths: list[str], validation: dict[str, Any] | None = None) -> dict[str, Any]:
        state = self._load_state()
        generation = {
            "id": _new_id("gen", infographic_id),
            "infographic_id": infographic_id,
            "revision_id": revision_id,
            "renderer_version": "free_mode_schema_v1",
            "output_paths": output_paths,
            "validation": validation or {},
            "created_at": utc_now(),
        }
        state.setdefault("generations", []).append(generation)
        self._save_state(state)
        return generation

    def create_backup(self, output_zip: str | Path) -> Path:
        output_path = Path(output_zip)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            if self.state_path.exists():
                archive.write(self.state_path, "archive.json")
            for path in self.files_root.rglob("*"):
                if path.is_file():
                    archive.write(path, str(Path("files") / path.relative_to(self.files_root)))
        return output_path

    def restore_backup(self, backup_zip: str | Path) -> None:
        backup_path = Path(backup_zip)
        if not backup_path.exists():
            raise FileNotFoundError(str(backup_path))
        temp_root = self.root.with_name(f"{self.root.name}_restore_{uuid4().hex[:8]}")
        with zipfile.ZipFile(backup_path, "r") as archive:
            archive.extractall(temp_root)
        if not (temp_root / "archive.json").exists():
            shutil.rmtree(temp_root, ignore_errors=True)
            raise ValueError("backup sem archive.json")
        if self.root.exists():
            shutil.rmtree(self.root)
        temp_root.replace(self.root)

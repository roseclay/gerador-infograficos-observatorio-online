from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from io import BytesIO
import json
from pathlib import Path
import zipfile
from typing import Any

from PIL import Image

from .archive_store import (
    MAX_CSV_BYTES,
    MAX_IMAGE_PIXELS,
    _latest_revision,
    _new_id,
    safe_filename,
    sha256_bytes,
    utc_now,
)
from .catalog import default_indicator_definitions, normalize_indicator_definition, validate_indicator_definition
from .data_binding import duplicate_logical_keys, update_bound_elements
from .data_loader import load_csv
from .free_mode import build_free_mode_config_with_name, normalize_fields


DEFAULT_SUPABASE_BUCKET = "observatorio-infograficos"


class SupabaseArchiveError(RuntimeError):
    pass


class SupabaseDependencyError(SupabaseArchiveError):
    pass


class SupabaseConfigurationError(SupabaseArchiveError):
    pass


@dataclass(frozen=True)
class SupabaseArchiveConfig:
    url: str
    anon_key: str = ""
    bucket: str = DEFAULT_SUPABASE_BUCKET
    service_role_key: str = ""
    access_token: str = ""
    refresh_token: str = ""

    @property
    def api_key(self) -> str:
        return self.service_role_key or self.anon_key

    @property
    def uses_user_session(self) -> bool:
        return bool(self.access_token and self.refresh_token and not self.service_role_key)

    def validate(self) -> None:
        if not self.url:
            raise SupabaseConfigurationError("SUPABASE_URL não configurado.")
        if not self.api_key:
            raise SupabaseConfigurationError("SUPABASE_ANON_KEY ou SUPABASE_SERVICE_ROLE_KEY não configurado.")
        if not self.bucket:
            raise SupabaseConfigurationError("Bucket Supabase não configurado.")


def _load_supabase_factory():
    try:
        from supabase import create_client
    except ImportError as exc:  # pragma: no cover - depends on deployment environment
        raise SupabaseDependencyError("Instale a dependência `supabase` para usar o acervo compartilhado.") from exc
    return create_client


def _response_data(response: Any) -> Any:
    if hasattr(response, "data"):
        return response.data
    if isinstance(response, dict):
        return response.get("data")
    return response


def _normalize_json(value: Any, fallback: Any) -> Any:
    if value is None:
        return deepcopy(fallback)
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return deepcopy(fallback)
    return value


def _session_value(obj: Any, key: str, default: str = "") -> str:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return str(obj.get(key) or default)
    return str(getattr(obj, key, default) or default)


def sign_in_supabase_user(url: str, anon_key: str, email: str, password: str) -> dict[str, str]:
    if not url or not anon_key:
        raise SupabaseConfigurationError("URL e anon key do Supabase são obrigatórios para login.")
    create_client = _load_supabase_factory()
    client = create_client(url, anon_key)
    response = client.auth.sign_in_with_password({"email": email, "password": password})
    session = getattr(response, "session", None) or (response.get("session") if isinstance(response, dict) else None)
    user = getattr(response, "user", None) or (response.get("user") if isinstance(response, dict) else None)
    access_token = _session_value(session, "access_token")
    refresh_token = _session_value(session, "refresh_token")
    if not access_token or not refresh_token:
        raise SupabaseArchiveError("Login concluído sem sessão válida retornada pelo Supabase.")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "email": _session_value(user, "email", email),
    }


class SupabaseArchiveStore:
    def __init__(self, config: SupabaseArchiveConfig):
        config.validate()
        create_client = _load_supabase_factory()
        self.config = config
        self.bucket = config.bucket
        self.client = create_client(config.url, config.api_key)
        if config.uses_user_session:
            self.client.auth.set_session(config.access_token, config.refresh_token)

    def bootstrap(self) -> "SupabaseArchiveStore":
        definitions = self.list_indicator_definitions()
        existing = {item.get("id") for item in definitions}
        for definition in default_indicator_definitions():
            if definition["id"] not in existing:
                self.save_indicator_definition(definition)
        return self

    def diagnostics(self) -> dict[str, Any]:
        return {
            "provider": "supabase",
            "url": self.config.url,
            "bucket": self.bucket,
            "auth": "service_role" if self.config.service_role_key else "user_session",
            "datasets": len(self._select_all("datasets")),
            "base_images": len(self._select_all("base_images")),
            "infographics": len(self._select_all("infographics")),
            "indicator_definitions": len(self.list_indicator_definitions()),
        }

    def _table(self, table: str):
        return self.client.table(table)

    def _storage(self):
        return self.client.storage.from_(self.bucket)

    def _select_all(self, table: str) -> list[dict[str, Any]]:
        data = _response_data(self._table(table).select("*").execute()) or []
        return [dict(item) for item in data]

    def _select_eq(self, table: str, column: str, value: Any) -> list[dict[str, Any]]:
        data = _response_data(self._table(table).select("*").eq(column, value).execute()) or []
        return [dict(item) for item in data]

    def _first_eq(self, table: str, column: str, value: Any) -> dict[str, Any] | None:
        rows = self._select_eq(table, column, value)
        return rows[0] if rows else None

    def _insert(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        data = _response_data(self._table(table).insert(row).execute()) or []
        return dict(data[0]) if data else deepcopy(row)

    def _update_by_id(self, table: str, row_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        data = _response_data(self._table(table).update(patch).eq("id", row_id).execute()) or []
        return dict(data[0]) if data else {**patch, "id": row_id}

    def _upload_bytes(self, path: str, data: bytes, content_type: str) -> None:
        storage = self._storage()
        options = {"content-type": content_type, "upsert": "false"}
        try:
            storage.upload(path=path, file=data, file_options=options)
        except TypeError:
            storage.upload(path, data, options)

    def _download_bytes(self, path: str) -> bytes:
        payload = self._storage().download(path)
        if isinstance(payload, bytes):
            return payload
        if hasattr(payload, "content"):
            return bytes(payload.content)
        if isinstance(payload, str):
            return payload.encode("utf-8")
        return bytes(payload)

    def list_indicator_definitions(self) -> list[dict[str, Any]]:
        rows = self._select_all("indicator_definitions")
        for row in rows:
            if "references" not in row and "reference_ids" in row:
                row["references"] = row.get("reference_ids") or []
        return [normalize_indicator_definition(row) for row in rows]

    def save_indicator_definition(self, definition: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        item = normalize_indicator_definition(definition)
        errors = validate_indicator_definition(item)
        if errors:
            return None, errors
        existing = self._first_eq("indicator_definitions", "id", item["id"])
        payload = deepcopy(item)
        payload["aliases"] = payload.get("aliases") or []
        payload["allowed_operations"] = payload.get("allowed_operations") or ["direct_value"]
        payload["reference_ids"] = payload.pop("references", []) or []
        payload["updated_at"] = utc_now()
        if existing:
            payload["definition_version"] = int(existing.get("definition_version") or 1) + 1
            return self._update_by_id("indicator_definitions", item["id"], payload), []
        payload["created_at"] = utc_now()
        return self._insert("indicator_definitions", payload), []

    def register_dataset(self, name: str, description: str = "", owner: str = "", public_source: str = "") -> dict[str, Any]:
        name = str(name or "").strip()
        if not name:
            raise ValueError("nome do conjunto ausente")
        existing = next((item for item in self._select_all("datasets") if str(item.get("name", "")).casefold() == name.casefold()), None)
        if existing:
            patch = {
                "description": description or existing.get("description", ""),
                "owner": owner or existing.get("owner", ""),
                "public_source": public_source or existing.get("public_source", ""),
                "updated_at": utc_now(),
            }
            return self._update_by_id("datasets", str(existing["id"]), patch)
        dataset = {
            "id": _new_id("ds", name),
            "name": name,
            "description": str(description or "").strip(),
            "owner": str(owner or "").strip(),
            "public_source": str(public_source or "").strip(),
            "active_version_id": None,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        return self._insert("datasets", dataset)

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
            raise ValueError("CSV maior que o limite configurado")
        dataset = self.get_dataset(dataset_id)
        if dataset is None:
            raise ValueError("conjunto de dados não encontrado")
        checksum = sha256_bytes(csv_bytes)
        comparable = {
            "checksum": checksum,
            "period": str(period or ""),
            "public_source": str(public_source or dataset.get("public_source") or ""),
            "source_updated_at": str(source_updated_at or ""),
            "mapping": mapping or {},
        }
        versions = self._dataset_versions(dataset_id)
        for version in versions:
            version_mapping = _normalize_json(version.get("mapping"), {})
            if (
                version.get("checksum") == comparable["checksum"]
                and version.get("period") == comparable["period"]
                and version.get("public_source") == comparable["public_source"]
                and version.get("source_updated_at") == comparable["source_updated_at"]
                and version_mapping == comparable["mapping"]
            ):
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

        sequence = max([int(version.get("sequence") or 0) for version in versions] or [0]) + 1
        version_id = _new_id("dsv", f"{dataset.get('name')}_{sequence}")
        storage_path = str(Path("datasets") / dataset_id / f"v{sequence:04d}" / safe_filename(file_name, "dados.csv")).replace("\\", "/")
        version = {
            "id": version_id,
            "dataset_id": dataset_id,
            "sequence": sequence,
            "checksum": checksum,
            "file_name": Path(file_name).name,
            "storage_path": storage_path,
            "schema": schema,
            "mapping": mapping or {},
            "period": str(period or ""),
            "public_source": str(public_source or dataset.get("public_source") or ""),
            "source_updated_at": str(source_updated_at or ""),
            "status": "valid" if not validation_errors else "invalid",
            "validation_errors": validation_errors,
            "uploaded_at": utc_now(),
            "activated_at": utc_now() if not validation_errors else None,
        }
        self._upload_bytes(storage_path, csv_bytes, "text/csv")
        inserted = self._insert("dataset_versions", version)
        if not validation_errors:
            self._update_by_id(
                "datasets",
                dataset_id,
                {
                    "active_version_id": version_id,
                    "public_source": version["public_source"] or dataset.get("public_source", ""),
                    "updated_at": utc_now(),
                },
            )
        return inserted

    def get_dataset(self, dataset_id: str, state: dict[str, Any] | None = None) -> dict[str, Any] | None:
        return self._first_eq("datasets", "id", dataset_id)

    def _dataset_versions(self, dataset_id: str) -> list[dict[str, Any]]:
        versions = self._select_eq("dataset_versions", "dataset_id", dataset_id)
        return sorted(versions, key=lambda item: int(item.get("sequence") or 0))

    def list_datasets(self) -> list[dict[str, Any]]:
        datasets = self._select_all("datasets")
        result = []
        for dataset in datasets:
            item = deepcopy(dataset)
            item["versions"] = self._dataset_versions(str(dataset["id"]))
            item["dependent_count"] = len(self.list_dependents(str(dataset["id"])))
            result.append(item)
        return sorted(result, key=lambda item: item.get("updated_at", ""), reverse=True)

    def get_dataset_version(self, version_id: str, state: dict[str, Any] | None = None) -> dict[str, Any] | None:
        return self._first_eq("dataset_versions", "id", version_id)

    def active_dataset_version(self, dataset_id: str) -> dict[str, Any] | None:
        dataset = self.get_dataset(dataset_id)
        active_id = str((dataset or {}).get("active_version_id") or "")
        return self.get_dataset_version(active_id) if active_id else None

    def dataset_version_path(self, version: dict[str, Any]) -> Path:
        return Path(str(version.get("storage_path") or ""))

    def load_dataset_dataframe(self, version_id: str) -> tuple[Any, dict[str, Any]]:
        version = self.get_dataset_version(version_id)
        if version is None:
            raise ValueError("versão de dados não encontrada")
        schema = _normalize_json(version.get("schema"), {})
        csv_bytes = self._download_bytes(str(version.get("storage_path") or ""))
        dataframe, _profile = load_csv(
            BytesIO(csv_bytes),
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
        existing = next((item for item in self._select_all("base_images") if str(item.get("name", "")).casefold() == name.casefold()), None)
        if existing:
            patch = {
                "description": description or existing.get("description", ""),
                "kind": kind,
                "updated_at": utc_now(),
            }
            return self._update_by_id("base_images", str(existing["id"]), patch)
        base = {
            "id": _new_id("base", name),
            "name": name,
            "description": str(description or "").strip(),
            "kind": kind,
            "active_version_id": None,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        return self._insert("base_images", base)

    def _base_image_versions(self, base_id: str) -> list[dict[str, Any]]:
        versions = self._select_eq("base_image_versions", "base_image_id", base_id)
        return sorted(versions, key=lambda item: int(item.get("sequence") or 0))

    def add_base_image_version(self, base_id: str, image_bytes: bytes, file_name: str, *, review_status: str = "pending") -> dict[str, Any]:
        base = self._first_eq("base_images", "id", base_id)
        if base is None:
            raise ValueError("imagem-base não encontrada")
        checksum = sha256_bytes(image_bytes)
        versions = self._base_image_versions(base_id)
        for version in versions:
            if version.get("checksum") == checksum and version.get("review_status") == review_status:
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

        sequence = max([int(version.get("sequence") or 0) for version in versions] or [0]) + 1
        version_id = _new_id("bsv", f"{base.get('name')}_{sequence}")
        storage_path = str(Path("base_images") / base_id / f"v{sequence:04d}" / safe_filename(file_name, "base.png")).replace("\\", "/")
        version = {
            "id": version_id,
            "base_image_id": base_id,
            "sequence": sequence,
            "checksum": checksum,
            "file_name": Path(file_name).name,
            "storage_path": storage_path,
            "width": width,
            "height": height,
            "format": image_format,
            "review_status": review_status,
            "status": "valid" if not validation_errors else "invalid",
            "validation_errors": validation_errors,
            "uploaded_at": utc_now(),
        }
        content_type = "image/jpeg" if Path(file_name).suffix.lower() in {".jpg", ".jpeg"} else "image/png"
        self._upload_bytes(storage_path, image_bytes, content_type)
        inserted = self._insert("base_image_versions", version)
        if not validation_errors:
            self._update_by_id("base_images", base_id, {"active_version_id": version_id, "updated_at": utc_now()})
        return inserted

    def list_base_images(self, production_only: bool = False) -> list[dict[str, Any]]:
        bases = []
        for base in self._select_all("base_images"):
            if production_only and base.get("kind") == "reference":
                continue
            item = deepcopy(base)
            item["versions"] = self._base_image_versions(str(base["id"]))
            bases.append(item)
        return sorted(bases, key=lambda item: item.get("updated_at", ""), reverse=True)

    def get_base_image_version(self, version_id: str, state: dict[str, Any] | None = None) -> dict[str, Any] | None:
        return self._first_eq("base_image_versions", "id", version_id)

    def base_image_version_path(self, version: dict[str, Any]) -> Path:
        return Path(str(version.get("storage_path") or ""))

    def base_image_version_bytes(self, version: dict[str, Any]) -> bytes:
        return self._download_bytes(str(version.get("storage_path") or ""))

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
        now = utc_now()
        if infographic_id:
            infographic = self._first_eq("infographics", "id", infographic_id)
            if infographic is None:
                raise ValueError("infográfico não encontrado")
            latest = self.latest_infographic_revision(infographic_id)
            if expected_revision_id and latest and latest.get("id") != expected_revision_id:
                return {"status": "conflict", "current_revision_id": latest.get("id"), "infographic": infographic}
            patch = {
                "name": name,
                "base_image_id": base_image_id,
                "base_image_version_id": base_image_version_id,
                "updated_at": now,
            }
            infographic = self._update_by_id("infographics", infographic_id, patch)
        else:
            infographic = self._insert(
                "infographics",
                {
                    "id": _new_id("info", name),
                    "name": name,
                    "mode": mode,
                    "base_image_id": base_image_id,
                    "base_image_version_id": base_image_version_id,
                    "latest_revision_id": None,
                    "created_at": now,
                    "updated_at": now,
                    "owner": owner,
                },
            )

        latest = self.latest_infographic_revision(str(infographic["id"]))
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
        revision = self._insert(
            "infographic_revisions",
            {
                "id": _new_id("infrev", f"{name}_{revision_number}"),
                "infographic_id": infographic["id"],
                "revision": revision_number,
                "layout_version": int((revision_config.get("schema_version") or 1)),
                "base_image_version_id": base_image_version_id,
                "data_versions": data_versions,
                "config": revision_config,
                "created_at": now,
            },
        )
        infographic = self._update_by_id(
            "infographics",
            str(infographic["id"]),
            {"latest_revision_id": revision["id"], "updated_at": now},
        )
        return {"status": "saved", "infographic": infographic, "revision": revision}

    def list_infographics(self) -> list[dict[str, Any]]:
        result = []
        for infographic in self._select_all("infographics"):
            latest = self.get_infographic_revision(str(infographic.get("latest_revision_id") or ""))
            config = _normalize_json((latest or {}).get("config"), {})
            updates = self.check_infographic_updates(str(infographic["id"]))
            result.append({
                **deepcopy(infographic),
                "revision": int((latest or {}).get("revision") or 0),
                "field_count": len(config.get("fields") or []),
                "updates_available": len(updates),
                "updated": infographic.get("updated_at", ""),
            })
        return sorted(result, key=lambda item: item.get("updated_at", ""), reverse=True)

    def get_infographic_revision(self, revision_id: str, state: dict[str, Any] | None = None) -> dict[str, Any] | None:
        revision = self._first_eq("infographic_revisions", "id", revision_id)
        if revision:
            revision["config"] = _normalize_json(revision.get("config"), {})
            revision["data_versions"] = _normalize_json(revision.get("data_versions"), [])
        return revision

    def latest_infographic_revision(self, infographic_id: str, state: dict[str, Any] | None = None) -> dict[str, Any] | None:
        revisions = self._select_eq("infographic_revisions", "infographic_id", infographic_id)
        latest = _latest_revision(revisions, "infographic_id", infographic_id)
        if latest:
            latest["config"] = _normalize_json(latest.get("config"), {})
            latest["data_versions"] = _normalize_json(latest.get("data_versions"), [])
        return latest

    def check_infographic_updates(self, infographic_id: str, state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        latest = self.latest_infographic_revision(infographic_id)
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
            dataset = self.get_dataset(dataset_id)
            active = self.get_dataset_version(str((dataset or {}).get("active_version_id") or "")) if dataset else None
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
        latest = self.latest_infographic_revision(infographic_id)
        infographic = self._first_eq("infographics", "id", infographic_id)
        if latest is None or infographic is None:
            return {"status": "missing", "message": "infográfico não encontrado"}
        updates = self.check_infographic_updates(infographic_id)
        if not updates:
            return {"status": "current", "message": "infográfico já está na versão ativa dos dados"}
        config = deepcopy(latest.get("config") or {})
        fields = config.get("fields") or []
        changes: list[dict[str, Any]] = []
        definitions = self.list_indicator_definitions()
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
        dependents = []
        for infographic in self._select_all("infographics"):
            latest = self.get_infographic_revision(str(infographic.get("latest_revision_id") or ""))
            if any(binding.get("dataset_id") == dataset_id for binding in (latest or {}).get("data_versions") or []):
                dependents.append(str(infographic["id"]))
        return dependents

    def record_generation(self, infographic_id: str, revision_id: str, output_paths: list[str], validation: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._insert(
            "generations",
            {
                "id": _new_id("gen", infographic_id),
                "infographic_id": infographic_id,
                "revision_id": revision_id,
                "renderer_version": "free_mode_schema_v1",
                "output_paths": output_paths,
                "validation": validation or {},
                "created_at": utc_now(),
            },
        )

    def create_backup(self, output_zip: str | Path) -> Path:
        output_path = Path(output_zip)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tables = [
            "indicator_definitions",
            "datasets",
            "dataset_versions",
            "base_images",
            "base_image_versions",
            "infographics",
            "infographic_revisions",
            "generations",
        ]
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            manifest = {table: self._select_all(table) for table in tables}
            archive.writestr("supabase_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
            for version in manifest["dataset_versions"] + manifest["base_image_versions"]:
                storage_path = str(version.get("storage_path") or "")
                if not storage_path:
                    continue
                archive.writestr(str(Path("files") / storage_path), self._download_bytes(storage_path))
        return output_path

    def restore_backup(self, backup_zip: str | Path) -> None:
        raise NotImplementedError("Restauração remota deve ser feita após revisão manual do backup e das políticas do Supabase.")

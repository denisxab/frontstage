"""
Парсер и валидатор YAML-файлов Software Catalog.
Читает директорию с .yaml-файлами, возвращает список CatalogObject.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .models import (
    ApiSpec,
    CatalogObject,
    DatabaseSpec,
    Kind,
    LibrarySpec,
    ServiceSpec,
    TeamSpec,
)

logger = logging.getLogger("frontstage.startup")


def _parse_spec(kind: Kind, data: dict[str, Any]):
    """Создаёт spec-объект нужного типа по kind."""
    spec_map = {
        Kind.Service: ServiceSpec,
        Kind.API: ApiSpec,
        Kind.Database: DatabaseSpec,
        Kind.Library: LibrarySpec,
        Kind.Team: TeamSpec,
    }
    cls = spec_map.get(kind)
    if cls is None:
        raise ValueError(f"Неизвестный kind: {kind}")
    return cls(**data)


def parse_file(path: Path) -> CatalogObject | None:
    """Парсит один YAML-файл. При ошибке логирует и возвращает None."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            logger.error("%s: файл не является YAML-объектом", path)
            return None

        kind = Kind(raw.get("kind", ""))
        spec_data = raw.get("spec", {})
        spec = _parse_spec(kind, spec_data)

        obj = CatalogObject(
            apiVersion=raw["apiVersion"],
            kind=kind,
            metadata=raw["metadata"],
            spec=spec,
            source_file=str(path),
        )
        return obj
    except (KeyError, ValueError, ValidationError, yaml.YAMLError) as exc:
        logger.error("%s: ошибка парсинга — %s", path, exc)
        return None


class CatalogStore:
    """
    Хранилище объектов каталога.
    Загружает все .yaml-файлы из указанной директории.
    """

    def __init__(self, catalog_dir: Path) -> None:
        self.catalog_dir = catalog_dir
        self.objects: list[CatalogObject] = []
        self.errors: list[dict] = []

    def load(self) -> None:
        """Сканирует директорию и загружает все .yaml-файлы."""
        self.objects = []
        self.errors = []

        yaml_files = list(self.catalog_dir.rglob("*.yaml")) + list(self.catalog_dir.rglob("*.yml"))

        for path in yaml_files:
            obj = parse_file(path)
            if obj is not None:
                self.objects.append(obj)
            else:
                self.errors.append({"file": str(path), "error": "parse_error"})

        self._validate_uniqueness()
        logger.info(
            "Каталог загружен: %d объектов, %d ошибок",
            len(self.objects),
            len(self.errors),
        )

    def _validate_uniqueness(self) -> None:
        """Проверяет уникальность name в пределах каждого kind."""
        seen: dict[str, str] = {}  # "kind:name" → source_file
        for obj in self.objects:
            key = f"{obj.kind.value}:{obj.metadata.name}"
            if key in seen:
                logger.error("Дубликат: %s — уже определён в %s", key, seen[key])
                self.errors.append({"file": obj.source_file, "error": f"duplicate: {key}"})
            else:
                seen[key] = obj.source_file or ""

    # ------------------------------------------------------------------
    # Запросы
    # ------------------------------------------------------------------

    def all(self) -> list[CatalogObject]:
        return self.objects

    def by_kind(self, kind: Kind) -> list[CatalogObject]:
        return [o for o in self.objects if o.kind == kind]

    def get(self, kind: Kind, name: str) -> CatalogObject | None:
        for o in self.objects:
            if o.kind == kind and o.metadata.name == name:
                return o
        return None

    def dependents_of(self, kind: Kind, name: str) -> list[CatalogObject]:
        """Возвращает объекты, которые зависят от данного (обратные зависимости)."""
        target_ref = f"{kind.value}:{name}".lower()
        result = []
        for obj in self.objects:
            deps = getattr(obj.spec, "dependsOn", []) or []
            if any(d.lower() == target_ref for d in deps):
                result.append(obj)
        return result

    def resolve_ref(self, ref: str) -> CatalogObject | None:
        """Резолвит ссылку вида 'kind:name'."""
        kind_str, _, name = ref.partition(":")
        # Ищем kind без учёта регистра (API != Api)
        kind_lower = kind_str.lower()
        kind = None
        for k in Kind:
            if k.value.lower() == kind_lower:
                kind = k
                break
        if kind is None:
            return None
        return self.get(kind, name)

    def summary(self) -> dict:
        counts = {k.value: 0 for k in Kind}
        for o in self.objects:
            counts[o.kind.value] += 1
        return {"total": len(self.objects), "by_kind": counts, "errors": len(self.errors)}

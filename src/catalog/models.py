"""
Pydantic-модели для Software Catalog.
Соответствуют спецификации docs/catalog/SPEC.md.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, HttpUrl, field_validator, model_validator


# ---------------------------------------------------------------------------
# Вспомогательные типы
# ---------------------------------------------------------------------------


class Lifecycle(str, Enum):
    production = "production"
    staging = "staging"
    experimental = "experimental"
    deprecated = "deprecated"


class ServiceType(str, Enum):
    backend = "backend"
    frontend = "frontend"
    cli = "cli"
    worker = "worker"
    cronjob = "cronjob"


class ApiType(str, Enum):
    rest = "rest"
    grpc = "grpc"
    graphql = "graphql"
    async_ = "async"


class DbEngine(str, Enum):
    postgresql = "postgresql"
    mysql = "mysql"
    redis = "redis"
    mongodb = "mongodb"
    sqlite = "sqlite"
    elasticsearch = "elasticsearch"
    clickhouse = "clickhouse"
    kafka = "kafka"


class DeploymentStatus(str, Enum):
    healthy = "healthy"
    degraded = "degraded"
    down = "down"
    unknown = "unknown"


class Kind(str, Enum):
    Service = "Service"
    API = "API"
    Database = "Database"
    Library = "Library"
    Team = "Team"


# ---------------------------------------------------------------------------
# Общие блоки
# ---------------------------------------------------------------------------


class Link(BaseModel):
    title: str
    url: HttpUrl
    # Иконка: предустановленное имя (git, github, gitlab, gitea, grafana, sentry, confluence, jira, docs)
    # или произвольное. Если не задано — определяется автоматически по URL.
    icon: Optional[str] = None


class Metadata(BaseModel):
    name: str
    title: str
    description: Optional[str] = None
    tags: list[str] = []
    links: list[Link] = []

    @field_validator("name")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        import re

        if not re.fullmatch(r"[a-z0-9-]{1,63}", v):
            raise ValueError(f"Некорректный slug: '{v}'. Допустимо: [a-z0-9-], длина 1–63")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        import re

        for tag in v:
            if not re.fullmatch(r"[a-z0-9-]+", tag):
                raise ValueError(f"Некорректный тег: '{tag}'")
        return v


def validate_ref(v: str) -> str:
    """Проверяет формат ref: kind:name"""
    parts = v.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Некорректная ref: '{v}'. Ожидается 'kind:name'")
    kind, name = parts
    valid_kinds = {"service", "api", "database", "library", "team"}
    if kind not in valid_kinds:
        raise ValueError(f"Неизвестный kind в ref: '{kind}'")
    return v


# ---------------------------------------------------------------------------
# Spec-блоки по kind
# ---------------------------------------------------------------------------


class Deployment(BaseModel):
    host: str
    url: Optional[HttpUrl] = None
    status: DeploymentStatus = DeploymentStatus.unknown


class ServiceSpec(BaseModel):
    lifecycle: Lifecycle
    owner: str  # ref → Team
    type: ServiceType
    dependsOn: list[str] = []
    providesApis: list[str] = []
    deployments: list[Deployment] = []

    @field_validator("owner")
    @classmethod
    def owner_must_be_team(cls, v: str) -> str:
        if not v.startswith("team:"):
            raise ValueError(f"owner должен быть 'team:<name>', получено: '{v}'")
        return v

    @field_validator("dependsOn", "providesApis")
    @classmethod
    def validate_refs(cls, v: list[str]) -> list[str]:
        for ref in v:
            validate_ref(ref)
        return v


class Definition(BaseModel):
    url: Optional[HttpUrl] = None
    inline: Optional[str] = None

    @model_validator(mode="after")
    def check_one_of(self) -> "Definition":
        if self.url and self.inline:
            raise ValueError("definition: нельзя одновременно указывать url и inline")
        return self


class ApiSpec(BaseModel):
    lifecycle: Lifecycle
    owner: str
    type: ApiType
    definition: Optional[Definition] = None

    @field_validator("owner")
    @classmethod
    def owner_must_be_team(cls, v: str) -> str:
        if not v.startswith("team:"):
            raise ValueError(f"owner должен быть 'team:<name>', получено: '{v}'")
        return v


class DbDeployment(BaseModel):
    host: str
    database: Optional[str] = None


class DatabaseSpec(BaseModel):
    lifecycle: Lifecycle
    owner: str
    engine: DbEngine
    version: Optional[str] = None
    deployments: list[DbDeployment] = []

    @field_validator("owner")
    @classmethod
    def owner_must_be_team(cls, v: str) -> str:
        if not v.startswith("team:"):
            raise ValueError(f"owner должен быть 'team:<name>', получено: '{v}'")
        return v


class LibrarySpec(BaseModel):
    lifecycle: Lifecycle
    owner: str
    language: str
    version: Optional[str] = None

    @field_validator("owner")
    @classmethod
    def owner_must_be_team(cls, v: str) -> str:
        if not v.startswith("team:"):
            raise ValueError(f"owner должен быть 'team:<name>', получено: '{v}'")
        return v


class Member(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    role: Optional[str] = None


class TeamSpec(BaseModel):
    members: list[Member] = []


# ---------------------------------------------------------------------------
# Корневые объекты каталога
# ---------------------------------------------------------------------------


class CatalogObject(BaseModel):
    """Базовый тип — результат парсинга одного YAML-файла."""

    apiVersion: str
    kind: Kind
    metadata: Metadata
    spec: ServiceSpec | ApiSpec | DatabaseSpec | LibrarySpec | TeamSpec
    source_file: Optional[str] = None  # путь к файлу, не из YAML

    @field_validator("apiVersion")
    @classmethod
    def check_api_version(cls, v: str) -> str:
        if v != "frontstage/v1":
            raise ValueError(f"Неизвестный apiVersion: '{v}'")
        return v

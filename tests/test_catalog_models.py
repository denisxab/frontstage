"""
Тесты Pydantic-моделей Software Catalog.

Покрывает:
- Metadata: валидация slug, тегов
- ServiceSpec, ApiSpec, DatabaseSpec, LibrarySpec, TeamSpec
- CatalogObject: сборка объекта, валидация apiVersion
- validate_ref: формат ref
"""

import pytest
from pydantic import ValidationError

from catalog.models import (
    ApiSpec,
    ApiType,
    CatalogObject,
    DatabaseSpec,
    DbEngine,
    Kind,
    LibrarySpec,
    Lifecycle,
    Member,
    Metadata,
    ServiceSpec,
    ServiceType,
    TeamSpec,
    validate_ref,
)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_valid_metadata(self):
        m = Metadata(name="my-service", title="My Service")
        assert m.name == "my-service"
        assert m.tags == []

    def test_slug_must_be_lowercase(self):
        with pytest.raises(ValidationError):
            Metadata(name="MyService", title="x")

    def test_slug_no_spaces(self):
        with pytest.raises(ValidationError):
            Metadata(name="my service", title="x")

    def test_slug_max_63(self):
        with pytest.raises(ValidationError):
            Metadata(name="a" * 64, title="x")

    def test_valid_tags(self):
        m = Metadata(name="svc", title="x", tags=["python", "backend", "v2"])
        assert len(m.tags) == 3

    def test_invalid_tag_uppercase(self):
        with pytest.raises(ValidationError):
            Metadata(name="svc", title="x", tags=["Python"])

    def test_invalid_tag_spaces(self):
        with pytest.raises(ValidationError):
            Metadata(name="svc", title="x", tags=["my tag"])


# ---------------------------------------------------------------------------
# validate_ref
# ---------------------------------------------------------------------------


class TestValidateRef:
    def test_valid_refs(self):
        for ref in ["team:backend", "service:api-gw", "database:pg", "library:sdk", "api:v1"]:
            assert validate_ref(ref) == ref

    def test_missing_colon(self):
        with pytest.raises(ValueError):
            validate_ref("teambackend")

    def test_unknown_kind(self):
        with pytest.raises(ValueError):
            validate_ref("unknown:foo")


# ---------------------------------------------------------------------------
# ServiceSpec
# ---------------------------------------------------------------------------


class TestServiceSpec:
    def test_valid_spec(self):
        s = ServiceSpec(
            lifecycle=Lifecycle.production,
            owner="team:backend",
            type=ServiceType.backend,
        )
        assert s.owner == "team:backend"
        assert s.dependsOn == []

    def test_owner_must_start_with_team(self):
        with pytest.raises(ValidationError):
            ServiceSpec(
                lifecycle=Lifecycle.production,
                owner="api:some",
                type=ServiceType.backend,
            )

    def test_invalid_depends_on_ref(self):
        with pytest.raises(ValidationError):
            ServiceSpec(
                lifecycle=Lifecycle.production,
                owner="team:backend",
                type=ServiceType.backend,
                dependsOn=["bad-ref"],
            )

    def test_valid_depends_on(self):
        s = ServiceSpec(
            lifecycle=Lifecycle.production,
            owner="team:backend",
            type=ServiceType.backend,
            dependsOn=["database:pg", "service:auth"],
        )
        assert len(s.dependsOn) == 2


# ---------------------------------------------------------------------------
# ApiSpec
# ---------------------------------------------------------------------------


class TestApiSpec:
    def test_valid_spec(self):
        s = ApiSpec(
            lifecycle=Lifecycle.staging,
            owner="team:platform",
            type=ApiType.rest,
        )
        assert s.type == ApiType.rest

    def test_owner_not_team(self):
        with pytest.raises(ValidationError):
            ApiSpec(lifecycle=Lifecycle.staging, owner="service:foo", type=ApiType.rest)


# ---------------------------------------------------------------------------
# DatabaseSpec
# ---------------------------------------------------------------------------


class TestDatabaseSpec:
    def test_valid_spec(self):
        s = DatabaseSpec(
            lifecycle=Lifecycle.production,
            owner="team:infra",
            engine=DbEngine.postgresql,
            version="15",
        )
        assert s.engine == DbEngine.postgresql

    def test_invalid_engine(self):
        with pytest.raises(ValidationError):
            DatabaseSpec(lifecycle=Lifecycle.production, owner="team:infra", engine="oracle")


# ---------------------------------------------------------------------------
# LibrarySpec
# ---------------------------------------------------------------------------


class TestLibrarySpec:
    def test_valid_spec(self):
        s = LibrarySpec(
            lifecycle=Lifecycle.production,
            owner="team:backend",
            language="python",
            version="1.2.3",
        )
        assert s.language == "python"


# ---------------------------------------------------------------------------
# TeamSpec
# ---------------------------------------------------------------------------


class TestTeamSpec:
    def test_empty_team(self):
        s = TeamSpec()
        assert s.members == []

    def test_team_with_members(self):
        s = TeamSpec(
            members=[
                Member(name="Alice", email="alice@example.com", role="lead"),
                Member(name="Bob"),
            ]
        )
        assert len(s.members) == 2

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            TeamSpec(members=[Member(name="Bad", email="not-an-email")])


# ---------------------------------------------------------------------------
# CatalogObject
# ---------------------------------------------------------------------------


def _make_team_obj(**kwargs) -> dict:
    """Базовый словарь для CatalogObject с kind=Team."""
    base = {
        "apiVersion": "frontstage/v1",
        "kind": "Team",
        "metadata": {"name": "backend", "title": "Backend Team"},
        "spec": {},
    }
    base.update(kwargs)
    return base


class TestCatalogObject:
    def test_valid_team_object(self):
        obj = CatalogObject(**_make_team_obj())
        assert obj.kind == Kind.Team
        assert obj.metadata.name == "backend"

    def test_wrong_api_version(self):
        with pytest.raises(ValidationError):
            CatalogObject(**_make_team_obj(apiVersion="v2"))

    def test_source_file_optional(self):
        obj = CatalogObject(**_make_team_obj())
        assert obj.source_file is None

    def test_service_object(self):
        obj = CatalogObject(
            apiVersion="frontstage/v1",
            kind="Service",
            metadata={"name": "user-service", "title": "User Service"},
            spec={
                "lifecycle": "production",
                "owner": "team:backend",
                "type": "backend",
            },
        )
        assert obj.kind == Kind.Service
        assert isinstance(obj.spec, ServiceSpec)

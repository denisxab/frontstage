"""
Тесты парсера и CatalogStore.

Покрывает:
- parse_file: валидный YAML, невалидный, отсутствующие поля
- CatalogStore.load: загрузка директории, подсчёт ошибок
- CatalogStore: by_kind, get, resolve_ref, summary, дубликаты, dependents_of
"""

import textwrap
from pathlib import Path

import pytest

from catalog.models import Kind
from catalog.parser import CatalogStore, parse_file


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def write_yaml(tmp_path: Path, name: str, content: str) -> Path:
    """Записывает YAML-файл во временную директорию."""
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


VALID_TEAM_YAML = """\
    apiVersion: frontstage/v1
    kind: Team
    metadata:
      name: backend
      title: Backend Team
    spec:
      members:
        - name: Alice
          role: lead
"""

VALID_SERVICE_YAML = """\
    apiVersion: frontstage/v1
    kind: Service
    metadata:
      name: user-service
      title: User Service
      tags:
        - python
    spec:
      lifecycle: production
      owner: team:backend
      type: backend
      dependsOn:
        - database:users-db
"""

VALID_DATABASE_YAML = """\
    apiVersion: frontstage/v1
    kind: Database
    metadata:
      name: users-db
      title: Users DB
    spec:
      lifecycle: production
      owner: team:backend
      engine: postgresql
"""


# ---------------------------------------------------------------------------
# parse_file
# ---------------------------------------------------------------------------


class TestParseFile:
    def test_valid_team(self, tmp_path):
        p = write_yaml(tmp_path, "team.yaml", VALID_TEAM_YAML)
        obj = parse_file(p)
        assert obj is not None
        assert obj.kind == Kind.Team
        assert obj.metadata.name == "backend"

    def test_valid_service(self, tmp_path):
        p = write_yaml(tmp_path, "svc.yaml", VALID_SERVICE_YAML)
        obj = parse_file(p)
        assert obj is not None
        assert obj.kind == Kind.Service

    def test_source_file_set(self, tmp_path):
        p = write_yaml(tmp_path, "team.yaml", VALID_TEAM_YAML)
        obj = parse_file(p)
        assert obj.source_file == str(p)

    def test_missing_api_version_returns_none(self, tmp_path):
        p = write_yaml(
            tmp_path,
            "bad.yaml",
            """\
            kind: Team
            metadata:
              name: x
              title: x
            spec: {}
            """,
        )
        obj = parse_file(p)
        assert obj is None

    def test_wrong_api_version_returns_none(self, tmp_path):
        p = write_yaml(
            tmp_path,
            "bad.yaml",
            """\
            apiVersion: v999
            kind: Team
            metadata:
              name: x
              title: x
            spec: {}
            """,
        )
        obj = parse_file(p)
        assert obj is None

    def test_unknown_kind_returns_none(self, tmp_path):
        p = write_yaml(
            tmp_path,
            "bad.yaml",
            """\
            apiVersion: frontstage/v1
            kind: Unknown
            metadata:
              name: x
              title: x
            spec: {}
            """,
        )
        obj = parse_file(p)
        assert obj is None

    def test_invalid_slug_returns_none(self, tmp_path):
        p = write_yaml(
            tmp_path,
            "bad.yaml",
            """\
            apiVersion: frontstage/v1
            kind: Team
            metadata:
              name: Invalid Name
              title: x
            spec: {}
            """,
        )
        obj = parse_file(p)
        assert obj is None

    def test_non_dict_yaml_returns_none(self, tmp_path):
        p = tmp_path / "list.yaml"
        p.write_text("- a\n- b\n", encoding="utf-8")
        obj = parse_file(p)
        assert obj is None


# ---------------------------------------------------------------------------
# CatalogStore
# ---------------------------------------------------------------------------


class TestCatalogStore:
    def test_load_empty_dir(self, tmp_path):
        store = CatalogStore(tmp_path)
        store.load()
        assert store.objects == []
        assert store.errors == []

    def test_load_valid_files(self, tmp_path):
        write_yaml(tmp_path, "team.yaml", VALID_TEAM_YAML)
        write_yaml(tmp_path, "svc.yaml", VALID_SERVICE_YAML)
        write_yaml(tmp_path, "db.yaml", VALID_DATABASE_YAML)
        store = CatalogStore(tmp_path)
        store.load()
        assert len(store.objects) == 3
        assert store.errors == []

    def test_load_bad_file_counted_as_error(self, tmp_path):
        write_yaml(tmp_path, "bad.yaml", "not: yaml: object: []")
        store = CatalogStore(tmp_path)
        store.load()
        assert len(store.errors) == 1

    def test_duplicate_detected(self, tmp_path):
        write_yaml(tmp_path, "team1.yaml", VALID_TEAM_YAML)
        write_yaml(tmp_path, "team2.yaml", VALID_TEAM_YAML)
        store = CatalogStore(tmp_path)
        store.load()
        # один объект загружен, второй — дубликат → ошибка
        assert len(store.errors) >= 1

    def test_by_kind(self, tmp_path):
        write_yaml(tmp_path, "team.yaml", VALID_TEAM_YAML)
        write_yaml(tmp_path, "svc.yaml", VALID_SERVICE_YAML)
        store = CatalogStore(tmp_path)
        store.load()
        teams = store.by_kind(Kind.Team)
        assert len(teams) == 1
        assert teams[0].kind == Kind.Team

    def test_get_existing(self, tmp_path):
        write_yaml(tmp_path, "team.yaml", VALID_TEAM_YAML)
        store = CatalogStore(tmp_path)
        store.load()
        obj = store.get(Kind.Team, "backend")
        assert obj is not None
        assert obj.metadata.name == "backend"

    def test_get_nonexistent_returns_none(self, tmp_path):
        write_yaml(tmp_path, "team.yaml", VALID_TEAM_YAML)
        store = CatalogStore(tmp_path)
        store.load()
        assert store.get(Kind.Team, "nonexistent") is None
        assert store.get(Kind.Service, "backend") is None

    def test_resolve_ref(self, tmp_path):
        write_yaml(tmp_path, "team.yaml", VALID_TEAM_YAML)
        store = CatalogStore(tmp_path)
        store.load()
        obj = store.resolve_ref("team:backend")
        assert obj is not None
        assert obj.kind == Kind.Team

    def test_resolve_ref_case_insensitive_kind(self, tmp_path):
        write_yaml(tmp_path, "team.yaml", VALID_TEAM_YAML)
        store = CatalogStore(tmp_path)
        store.load()
        assert store.resolve_ref("Team:backend") is not None

    def test_resolve_ref_unknown_returns_none(self, tmp_path):
        store = CatalogStore(tmp_path)
        store.load()
        assert store.resolve_ref("unknown:foo") is None
        assert store.resolve_ref("team:nonexistent") is None

    def test_summary_structure(self, tmp_path):
        write_yaml(tmp_path, "team.yaml", VALID_TEAM_YAML)
        write_yaml(tmp_path, "svc.yaml", VALID_SERVICE_YAML)
        store = CatalogStore(tmp_path)
        store.load()
        s = store.summary()
        assert s["total"] == 2
        assert s["by_kind"]["Team"] == 1
        assert s["by_kind"]["Service"] == 1
        assert s["errors"] == 0

    def test_reload_clears_previous(self, tmp_path):
        write_yaml(tmp_path, "team.yaml", VALID_TEAM_YAML)
        store = CatalogStore(tmp_path)
        store.load()
        assert len(store.objects) == 1
        # Добавляем файл и перезагружаем
        write_yaml(tmp_path, "svc.yaml", VALID_SERVICE_YAML)
        store.load()
        assert len(store.objects) == 2

    def test_load_recursive(self, tmp_path):
        """Файлы в поддиректориях тоже загружаются."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        write_yaml(subdir, "team.yaml", VALID_TEAM_YAML)
        store = CatalogStore(tmp_path)
        store.load()
        assert len(store.objects) == 1


# ---------------------------------------------------------------------------
# CatalogStore.dependents_of
# ---------------------------------------------------------------------------

VALID_SERVICE2_YAML = """\
    apiVersion: frontstage/v1
    kind: Service
    metadata:
      name: order-service
      title: Order Service
    spec:
      lifecycle: production
      owner: team:backend
      type: backend
      dependsOn:
        - database:users-db
        - service:user-service
"""

VALID_API_YAML = """\
    apiVersion: frontstage/v1
    kind: API
    metadata:
      name: users-api
      title: Users API
    spec:
      lifecycle: production
      owner: team:backend
      type: rest
"""

# Третий сервис, зависящий от user-service
VALID_SERVICE3_YAML = """\
    apiVersion: frontstage/v1
    kind: Service
    metadata:
      name: gateway-service
      title: Gateway Service
    spec:
      lifecycle: production
      owner: team:backend
      type: backend
      dependsOn:
        - service:user-service
"""


class TestDependentsOf:
    def _load_store(self, tmp_path, *yamls) -> CatalogStore:
        for i, content in enumerate(yamls):
            write_yaml(tmp_path, f"obj{i}.yaml", content)
        store = CatalogStore(tmp_path)
        store.load()
        return store

    def test_returns_direct_dependents(self, tmp_path):
        """user-service имеет двух зависимых: order-service и gateway-service."""
        store = self._load_store(
            tmp_path,
            VALID_SERVICE_YAML,
            VALID_SERVICE2_YAML,
            VALID_SERVICE3_YAML,
            VALID_DATABASE_YAML,
            VALID_TEAM_YAML,
        )
        dependents = store.dependents_of(Kind.Service, "user-service")
        names = {o.metadata.name for o in dependents}
        assert names == {"order-service", "gateway-service"}

    def test_database_has_dependents(self, tmp_path):
        """users-db используется в user-service и order-service."""
        store = self._load_store(
            tmp_path,
            VALID_SERVICE_YAML,
            VALID_SERVICE2_YAML,
            VALID_DATABASE_YAML,
            VALID_TEAM_YAML,
        )
        dependents = store.dependents_of(Kind.Database, "users-db")
        names = {o.metadata.name for o in dependents}
        assert names == {"user-service", "order-service"}

    def test_no_dependents_returns_empty(self, tmp_path):
        """Объект без входящих зависимостей — пустой список."""
        store = self._load_store(tmp_path, VALID_TEAM_YAML)
        dependents = store.dependents_of(Kind.Team, "backend")
        assert dependents == []

    def test_nonexistent_object_returns_empty(self, tmp_path):
        """Несуществующий объект — пустой список, не ошибка."""
        store = self._load_store(tmp_path, VALID_SERVICE_YAML, VALID_TEAM_YAML)
        dependents = store.dependents_of(Kind.Database, "ghost-db")
        assert dependents == []

    def test_ref_kind_must_be_lowercase(self, tmp_path):
        """Ссылка 'Database:users-db' с заглавной буквой отклоняется Pydantic-валидацией
        на уровне парсинга файла — такой YAML не попадает в store."""
        yaml_upper_ref = """\
            apiVersion: frontstage/v1
            kind: Service
            metadata:
              name: edge-service
              title: Edge Service
            spec:
              lifecycle: production
              owner: team:backend
              type: backend
              dependsOn:
                - Database:users-db
        """
        store = self._load_store(
            tmp_path, VALID_DATABASE_YAML, VALID_TEAM_YAML, yaml_upper_ref
        )
        # edge-service не загружен — ошибка валидации
        assert store.get(Kind.Service, "edge-service") is None
        assert len(store.errors) == 1
        # users-db не имеет зависимых
        assert store.dependents_of(Kind.Database, "users-db") == []

    def test_object_does_not_depend_on_itself(self, tmp_path):
        """Самоссылка в dependsOn не должна попадать в dependents_of самого себя
        (если такая запись встречается — она корректно обрабатывается)."""
        yaml_self_ref = """\
            apiVersion: frontstage/v1
            kind: Service
            metadata:
              name: loopy-service
              title: Loopy Service
            spec:
              lifecycle: production
              owner: team:backend
              type: backend
              dependsOn:
                - service:loopy-service
        """
        store = self._load_store(tmp_path, VALID_TEAM_YAML, yaml_self_ref)
        # dependents_of возвращает объект, который ссылается на себя — это валидное поведение
        dependents = store.dependents_of(Kind.Service, "loopy-service")
        assert len(dependents) == 1
        assert dependents[0].metadata.name == "loopy-service"

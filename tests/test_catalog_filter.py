"""
Тесты фильтрации /api/catalog.

Покрывает:
- _match_dotpath: scalar, list[scalar], list[dict], вложенные пути, отсутствие ключа
- GET /api/catalog?<filter> — интеграционные тесты через TestClient
"""

import pytest

from main import _match_dotpath

# ---------------------------------------------------------------------------
# Юнит-тесты _match_dotpath
# ---------------------------------------------------------------------------


class TestMatchDotpathScalar:
    """Простые скалярные значения на верхнем уровне и в metadata."""

    def test_top_level_match(self):
        assert _match_dotpath({"kind_lower": "service"}, "kind_lower", "service")

    def test_top_level_no_match(self):
        assert not _match_dotpath({"kind_lower": "service"}, "kind_lower", "team")

    def test_missing_key(self):
        assert not _match_dotpath({"kind_lower": "service"}, "source_file", "/app/x.yaml")

    def test_nested_scalar_match(self):
        obj = {"metadata": {"name": "audit-log"}}
        assert _match_dotpath(obj, "metadata.name", "audit-log")

    def test_nested_scalar_no_match(self):
        obj = {"metadata": {"name": "audit-log"}}
        assert not _match_dotpath(obj, "metadata.name", "other")

    def test_nested_missing_intermediate(self):
        obj = {"metadata": {"name": "audit-log"}}
        assert not _match_dotpath(obj, "spec.lifecycle", "production")


class TestMatchDotpathListScalar:
    """Поля-списки простых значений (tags)."""

    def test_tag_in_list(self):
        obj = {"metadata": {"tags": ["python", "audit", "compliance"]}}
        assert _match_dotpath(obj, "metadata.tags", "python")

    def test_tag_not_in_list(self):
        obj = {"metadata": {"tags": ["python", "audit"]}}
        assert not _match_dotpath(obj, "metadata.tags", "golang")

    def test_empty_list(self):
        obj = {"metadata": {"tags": []}}
        assert not _match_dotpath(obj, "metadata.tags", "python")

    def test_list_with_int_values(self):
        """Значения в списке приводятся к str для сравнения."""
        obj = {"spec": {"ports": [80, 443]}}
        assert _match_dotpath(obj, "spec.ports", "80")


class TestMatchDotpathListDict:
    """Поля-списки объектов (links, members, deployments)."""

    def test_links_title_match(self):
        obj = {
            "metadata": {
                "links": [
                    {"title": "PyPI (internal)", "url": "https://pypi.example.ru/x"},
                    {"title": "Confluence", "url": "https://wiki.example.ru"},
                ]
            }
        }
        assert _match_dotpath(obj, "metadata.links.title", "PyPI (internal)")

    def test_links_title_no_match(self):
        obj = {"metadata": {"links": [{"title": "Confluence", "url": "https://wiki.example.ru"}]}}
        assert not _match_dotpath(obj, "metadata.links.title", "GitHub")

    def test_members_email_match(self):
        obj = {
            "spec": {
                "members": [
                    {"name": "Иван Петров", "email": "i.petrov@example.ru", "role": "lead"},
                    {
                        "name": "Мария Сидорова",
                        "email": "m.sidorova@example.ru",
                        "role": "developer",
                    },
                ]
            }
        }
        assert _match_dotpath(obj, "spec.members.email", "i.petrov@example.ru")

    def test_members_email_no_match(self):
        obj = {
            "spec": {
                "members": [
                    {"name": "Иван Петров", "email": "i.petrov@example.ru", "role": "lead"},
                ]
            }
        }
        assert not _match_dotpath(obj, "spec.members.email", "unknown@example.ru")

    def test_deployments_status_match(self):
        obj = {
            "spec": {
                "deployments": [
                    {"host": "german", "url": "https://app.example.ru/", "status": "healthy"},
                ]
            }
        }
        assert _match_dotpath(obj, "spec.deployments.status", "healthy")

    def test_deployments_status_no_match(self):
        obj = {
            "spec": {
                "deployments": [
                    {"host": "german", "url": "https://app.example.ru/", "status": "healthy"},
                ]
            }
        }
        assert not _match_dotpath(obj, "spec.deployments.status", "degraded")

    def test_empty_list_of_dicts(self):
        obj = {"spec": {"members": []}}
        assert not _match_dotpath(obj, "spec.members.email", "anyone@example.ru")

    def test_list_items_without_target_key(self):
        """Элементы без искомого ключа не вызывают ошибку."""
        obj = {"metadata": {"links": [{"url": "https://example.ru"}]}}
        assert not _match_dotpath(obj, "metadata.links.title", "Something")


# ---------------------------------------------------------------------------
# Интеграционные тесты GET /api/catalog?<filter>
# ---------------------------------------------------------------------------


class TestApiCatalogFilter:
    """Фильтрация через query-параметры эндпоинта /api/catalog."""

    def test_filter_kind_lower(self, client, user_headers):
        """?filter=kind_lower=service возвращает только сервисы."""
        r = client.get("/api/catalog", headers=user_headers, params={"filter": "kind_lower=service"})
        assert r.status_code == 200
        data = r.json()
        assert all(o["kind_lower"] == "service" for o in data)

    def test_filter_kind_lower_no_results(self, client, user_headers):
        """?filter=kind_lower=nonexistent возвращает пустой список."""
        r = client.get("/api/catalog", headers=user_headers, params={"filter": "kind_lower=nonexistent"})
        assert r.status_code == 200
        assert r.json() == []

    def test_filter_metadata_name(self, client, user_headers):
        """?filter=metadata.name=<name> возвращает не более одного объекта с таким именем."""
        # Берём реальное имя из каталога
        all_r = client.get("/api/catalog", headers=user_headers)
        all_objs = all_r.json()
        if not all_objs:
            pytest.skip("Каталог пуст")
        name = all_objs[0]["metadata"]["name"]
        r = client.get("/api/catalog", headers=user_headers, params={"filter": f"metadata.name={name}"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert all(o["metadata"]["name"] == name for o in data)

    def test_filter_metadata_tag(self, client, user_headers):
        """?filter=metadata.tags=<tag> возвращает только объекты с этим тегом."""
        all_r = client.get("/api/catalog", headers=user_headers)
        all_objs = all_r.json()
        # Ищем объект с хотя бы одним тегом
        tagged = [o for o in all_objs if o["metadata"].get("tags")]
        if not tagged:
            pytest.skip("Нет объектов с тегами")
        tag = tagged[0]["metadata"]["tags"][0]
        r = client.get("/api/catalog", headers=user_headers, params={"filter": f"metadata.tags={tag}"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert all(tag in o["metadata"]["tags"] for o in data)

    def test_filter_metadata_links_title(self, client, user_headers):
        """?filter=metadata.links.title=<title> возвращает объекты с такой ссылкой."""
        all_r = client.get("/api/catalog", headers=user_headers)
        all_objs = all_r.json()
        with_links = [o for o in all_objs if o["metadata"].get("links")]
        if not with_links:
            pytest.skip("Нет объектов со ссылками")
        title = with_links[0]["metadata"]["links"][0]["title"]
        r = client.get("/api/catalog", headers=user_headers, params={"filter": f"metadata.links.title={title}"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        for o in data:
            titles = [lnk["title"] for lnk in o["metadata"].get("links", [])]
            assert title in titles

    def test_filter_combined_and(self, client, user_headers):
        """Несколько фильтров работают как AND."""
        all_r = client.get("/api/catalog", headers=user_headers)
        all_objs = all_r.json()
        if not all_objs:
            pytest.skip("Каталог пуст")
        first = all_objs[0]
        kind = first["kind_lower"]
        name = first["metadata"]["name"]
        r = client.get(
            "/api/catalog",
            headers=user_headers,
            params=[("filter", f"kind_lower={kind}"), ("filter", f"metadata.name={name}")],
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        for o in data:
            assert o["kind_lower"] == kind
            assert o["metadata"]["name"] == name

    def test_filter_combined_contradictory_returns_empty(self, client, user_headers):
        """Противоречивые фильтры возвращают пустой список."""
        r = client.get(
            "/api/catalog",
            headers=user_headers,
            params=[("filter", "kind_lower=service"), ("filter", "metadata.name=__no_such_name__")],
        )
        assert r.status_code == 200
        assert r.json() == []

    def test_no_filter_returns_all(self, client, user_headers):
        """Без фильтров возвращаются все объекты."""
        all_r = client.get("/api/catalog", headers=user_headers)
        filtered_r = client.get("/api/catalog", headers=user_headers)
        assert all_r.json() == filtered_r.json()

    def test_filter_requires_auth(self, client):
        """Фильтрация без ключа возвращает 401."""
        r = client.get("/api/catalog", params={"filter": "kind_lower=service"})
        assert r.status_code == 401

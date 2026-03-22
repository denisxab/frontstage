"""
Тесты авторизации JSON API эндпоинтов.

Покрывает:
- GET  /api/catalog         — требует user или admin (X-API-Key)
- GET  /api/catalog/summary — требует user или admin (X-API-Key)
- POST /api/catalog/reload  — требует только admin (X-API-Key)
"""


class TestApiCatalog:
    """GET /api/catalog"""

    def test_no_key_returns_401(self, client):
        r = client.get("/api/catalog")
        assert r.status_code == 401

    def test_wrong_key_returns_401(self, client):
        r = client.get("/api/catalog", headers={"X-API-Key": "wrong"})
        assert r.status_code == 401

    def test_user_key_returns_200(self, client, user_headers):
        r = client.get("/api/catalog", headers=user_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_admin_key_returns_200(self, client, admin_headers):
        r = client.get("/api/catalog", headers=admin_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_response_has_expected_fields(self, client, user_headers):
        r = client.get("/api/catalog", headers=user_headers)
        obj = r.json()[0]
        assert "kind" in obj
        assert "metadata" in obj
        assert "kind_lower" in obj


class TestApiSummary:
    """GET /api/catalog/summary"""

    def test_no_key_returns_401(self, client):
        r = client.get("/api/catalog/summary")
        assert r.status_code == 401

    def test_wrong_key_returns_401(self, client):
        r = client.get("/api/catalog/summary", headers={"X-API-Key": "bad"})
        assert r.status_code == 401

    def test_user_key_returns_200(self, client, user_headers):
        r = client.get("/api/catalog/summary", headers=user_headers)
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "by_kind" in data

    def test_admin_key_returns_200(self, client, admin_headers):
        r = client.get("/api/catalog/summary", headers=admin_headers)
        assert r.status_code == 200


class TestApiReload:
    """POST /api/catalog/reload — только admin"""

    def test_no_key_returns_401_or_403(self, client):
        r = client.post("/api/catalog/reload")
        assert r.status_code in (401, 403)

    def test_wrong_key_returns_403(self, client):
        r = client.post("/api/catalog/reload", headers={"X-API-Key": "wrong"})
        assert r.status_code == 403

    def test_user_key_returns_403(self, client, user_headers):
        """Обычный пользователь не может перезагружать каталог."""
        r = client.post("/api/catalog/reload", headers=user_headers)
        assert r.status_code == 403

    def test_admin_key_returns_200(self, client, admin_headers):
        r = client.post("/api/catalog/reload", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "by_kind" in data

    def test_error_response_is_json(self, client, user_headers):
        r = client.post("/api/catalog/reload", headers=user_headers)
        assert r.headers["content-type"].startswith("application/json")
        assert "detail" in r.json()

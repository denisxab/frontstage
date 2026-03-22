"""
Тесты авторизации HTML-маршрутов.

Покрывает:
- GET  /           — редирект на /login без cookie
- GET  /catalog/*  — редирект на /login без cookie
- GET  /login      — страница входа, редирект если уже авторизован
- POST /login      — установка cookie, редирект на главную
- GET  /logout     — удаление cookie, редирект на /login
- is_admin флаг   — кнопка Reload видна только admin
"""

HTML_HEADERS = {"Accept": "text/html"}


class TestIndexPage:
    """GET /"""

    def test_no_cookie_redirects_to_login(self, client):
        r = client.get("/", headers=HTML_HEADERS)
        assert r.status_code == 302
        assert r.headers["location"] == "/login"

    def test_wrong_cookie_redirects_to_login(self, wrong_cookie_client):
        r = wrong_cookie_client.get("/", headers=HTML_HEADERS)
        assert r.status_code == 302
        assert r.headers["location"] == "/login"

    def test_user_cookie_returns_200(self, user_client):
        r = user_client.get("/")
        assert r.status_code == 200
        assert b"FrontStage" in r.content

    def test_admin_cookie_returns_200(self, admin_client):
        r = admin_client.get("/")
        assert r.status_code == 200

    def test_user_cookie_no_reload_button(self, user_client):
        """Обычный пользователь не видит кнопку Reload catalog."""
        r = user_client.get("/")
        assert b"reload" not in r.content.lower() or b"api/catalog/reload" not in r.content

    def test_admin_cookie_has_reload_button(self, admin_client):
        """Администратор видит кнопку Reload catalog."""
        r = admin_client.get("/")
        assert b"/api/catalog/reload" in r.content


class TestCatalogListPage:
    """GET /catalog/<kind>"""

    def test_no_cookie_redirects_to_login(self, client):
        r = client.get("/catalog/service", headers=HTML_HEADERS)
        assert r.status_code == 302
        assert r.headers["location"] == "/login"

    def test_user_cookie_returns_200(self, user_client):
        r = user_client.get("/catalog/service")
        assert r.status_code == 200

    def test_unknown_kind_returns_404(self, user_client):
        r = user_client.get("/catalog/unknown")
        assert r.status_code == 404


class TestCatalogDetailPage:
    """GET /catalog/<kind>/<name>"""

    def test_no_cookie_redirects_to_login(self, client):
        r = client.get("/catalog/team/backend", headers=HTML_HEADERS)
        assert r.status_code == 302
        assert r.headers["location"] == "/login"

    def test_user_cookie_existing_object_returns_200(self, user_client):
        r = user_client.get("/catalog/team/backend")
        assert r.status_code == 200

    def test_nonexistent_object_returns_404(self, user_client):
        r = user_client.get("/catalog/service/nonexistent-xyz")
        assert r.status_code == 404


class TestLoginPage:
    """GET /login"""

    def test_login_page_renders(self, client):
        r = client.get("/login")
        assert r.status_code == 200
        assert b"api_key" in r.content  # поле формы

    def test_already_authed_redirects_to_index(self, user_client):
        """Уже авторизованный пользователь редиректится с /login на /."""
        r = user_client.get("/login")
        assert r.status_code == 302
        assert r.headers["location"] == "/"

    def test_error_param_shows_error(self, client):
        r = client.get("/login?error=1")
        assert r.status_code == 200
        assert "Неверный ключ".encode() in r.content


class TestLoginSubmit:
    """POST /login"""

    def test_wrong_key_redirects_to_login_with_error(self, client):
        r = client.post("/login", data={"api_key": "wrong"})
        assert r.status_code == 302
        assert "error=1" in r.headers["location"]

    def test_user_key_sets_cookie_and_redirects(self, client):
        r = client.post("/login", data={"api_key": "test-user-key"})
        assert r.status_code == 302
        assert r.headers["location"] == "/"
        assert "fs_key" in r.cookies

    def test_admin_key_sets_cookie_and_redirects(self, client):
        r = client.post("/login", data={"api_key": "test-admin-key"})
        assert r.status_code == 302
        assert r.headers["location"] == "/"
        assert "fs_key" in r.cookies

    def test_cookie_is_httponly(self, client):
        r = client.post("/login", data={"api_key": "test-user-key"})
        set_cookie = r.headers.get("set-cookie", "")
        assert "httponly" in set_cookie.lower()


class TestLogout:
    """GET /logout"""

    def test_logout_redirects_to_login(self, client):
        r = client.get("/logout")
        assert r.status_code == 302
        assert r.headers["location"] == "/login"

    def test_logout_clears_cookie(self, user_client):
        r = user_client.get("/logout")
        set_cookie = r.headers.get("set-cookie", "")
        # cookie сброшена — max-age=0 или expires в прошлом
        assert "fs_key" in set_cookie
        assert "max-age=0" in set_cookie.lower() or 'max-age="0"' in set_cookie.lower() or "expires" in set_cookie.lower()

# Авторизация FrontStage

Реализована в `src/auth.py`. Два уровня доступа, задаются через `.env`:

| Переменная      | Роль    | Доступ                              |
| --------------- | ------- | ----------------------------------- |
| `API_KEY_USER`  | `user`  | Чтение каталога (HTML + JSON API)   |
| `API_KEY_ADMIN` | `admin` | Чтение + `POST /api/catalog/reload` |

Если обе не заданы — **open mode** (авторизация отключена, все = admin).

## Передача ключа

- **Браузер:** `POST /login` (form `api_key`) → httpOnly cookie `fs_key`
- **API / Swagger UI:** заголовок `X-API-Key`
- **Выход:** `GET /logout` → удаляет cookie, редирект на `/login`

## Поведение маршрутов

- **HTML** (`/`, `/catalog/*`): нет/невалидная cookie → 302 на `/login`
- **JSON API** (`/api/*`): нет/невалидный ключ → 401. Недостаточно прав → 403

Admin видит кнопку "Reload catalog" в сайдбаре (флаг `is_admin` передаётся в шаблоны).

## Ключевые функции `auth.py`

- `_resolve_role(key)` — возвращает `'admin'`, `'user'` или `None`
- `require_user` / `require_admin` — `Depends()` для HTML-маршрутов (cookie + заголовок)
- `api_require_user` / `api_require_admin` — `Security()` для API (только заголовок, виден в OpenAPI)
- `resolve_role_from_request(request)` — определяет роль из объекта Request

OpenAPI: security scheme `APIKeyHeader` зарегистрирован, `persistAuthorization: true`.

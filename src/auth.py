"""
Авторизация по API-ключу.

Два уровня доступа:
- user  — API_KEY_USER (чтение каталога)
- admin — API_KEY_ADMIN (чтение + административные операции)

Ключ принимается в порядке приоритета:
1. Заголовок X-API-Key (для API-клиентов / Swagger UI)
2. httpOnly cookie fs_key (для браузера — устанавливается при логине)

Если ни один ключ не задан в окружении — авторизация отключена (open mode).

Архитектура security для FastAPI/OpenAPI:
- api_key_scheme — регистрирует securityScheme в OpenAPI, используется напрямую
  в сигнатуре эндпоинта через Security(api_key_scheme) → замок в Swagger UI
- require_user / require_admin — зависимости с полной логикой (заголовок + cookie)
  используются в HTML-маршрутах через Depends() (не попадают в OpenAPI схему)
"""

import os
from typing import Optional

from fastapi import Cookie, HTTPException, Security, status
from fastapi.security import APIKeyHeader

# Security scheme — регистрируется в OpenAPI securitySchemes
# Используется напрямую в API-эндпоинтах через Security(api_key_scheme)
api_key_scheme = APIKeyHeader(
    name="X-API-Key",
    description=(
        "API-ключ пользователя (`API_KEY_USER`) или администратора (`API_KEY_ADMIN`). "
        "Для admin-операций нужен ключ администратора."
    ),
    auto_error=False,
)


def _get_keys() -> tuple[str | None, str | None]:
    """Возвращает (user_key, admin_key) из окружения."""
    return os.getenv("API_KEY_USER"), os.getenv("API_KEY_ADMIN")


def _resolve_role(key: Optional[str]) -> str | None:
    """Определяет роль по ключу. Возвращает 'admin', 'user' или None."""
    user_key, admin_key = _get_keys()

    # Если ни один ключ не задан — авторизация отключена (open mode)
    if not user_key and not admin_key:
        return "admin"

    if key and admin_key and key == admin_key:
        return "admin"
    if key and user_key and key == user_key:
        return "user"
    return None


def resolve_role_from_request(request) -> str | None:
    """Определяет роль из объекта Request (заголовок или cookie)."""
    key = request.headers.get("X-API-Key") or request.cookies.get("fs_key")
    return _resolve_role(key)


# ---------------------------------------------------------------------------
# Зависимости для HTML-маршрутов (Depends) — cookie + заголовок, не в OpenAPI
# ---------------------------------------------------------------------------

async def require_user(
    header_key: Optional[str] = Security(api_key_scheme),
    fs_key: Optional[str] = Cookie(default=None),
) -> str:
    """Пропускает user и admin. Для HTML-маршрутов — Depends(require_user)."""
    role = _resolve_role(header_key or fs_key)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется API-ключ",
        )
    return role


async def require_admin(
    header_key: Optional[str] = Security(api_key_scheme),
    fs_key: Optional[str] = Cookie(default=None),
) -> str:
    """Пропускает только admin. Для HTML-маршрутов — Depends(require_admin)."""
    role = _resolve_role(header_key or fs_key)
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права администратора",
        )
    return role


# ---------------------------------------------------------------------------
# Зависимости для API-эндпоинтов (Security) — только заголовок, видны в OpenAPI
# ---------------------------------------------------------------------------

async def api_require_user(
    key: Optional[str] = Security(api_key_scheme),
) -> str:
    """Пропускает user и admin. Для API-эндпоинтов — Security(api_require_user)."""
    role = _resolve_role(key)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется API-ключ (X-API-Key)",
        )
    return role


async def api_require_admin(
    key: Optional[str] = Security(api_key_scheme),
) -> str:
    """Пропускает только admin. Для API-эндпоинтов — Security(api_require_admin)."""
    role = _resolve_role(key)
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права администратора",
        )
    return role

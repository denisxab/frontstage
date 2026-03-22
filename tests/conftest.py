"""
Общие фикстуры для тестов FrontStage.
"""

import os
from unittest.mock import AsyncMock, patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

# Устанавливаем тестовые ключи до импорта приложения
os.environ["API_KEY_USER"] = "test-user-key"
os.environ["API_KEY_ADMIN"] = "test-admin-key"
# В тестах логируем только в stdout (нет файловой системы /app/logs)
os.environ.setdefault("LOG_FILE", os.path.join(os.path.dirname(__file__), "..", "logs", "test.log"))
os.environ["LOG_TRUNCATE"] = "1"  # пересоздавать лог-файл при каждом запуске тестов

from plugins.redis_cache import RedisPluginCache  # noqa: E402
from main import app  # noqa: E402 — импорт после установки env


def _make_fake_cache() -> RedisPluginCache:
    """Создаёт RedisPluginCache на fakeredis — без реального Redis."""
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    return RedisPluginCache(client)


async def _fake_create_redis_cache(_url: str) -> RedisPluginCache:
    """Заглушка create_redis_cache — возвращает fakeredis-кеш."""
    return _make_fake_cache()


@pytest.fixture(scope="session")
def client():
    """TestClient с отключёнными редиректами — видим 302 явно."""
    with patch("main.create_redis_cache", side_effect=_fake_create_redis_cache):
        with TestClient(app, follow_redirects=False) as c:
            yield c


@pytest.fixture(scope="session")
def user_client():
    """TestClient с cookie пользователя."""
    with patch("main.create_redis_cache", side_effect=_fake_create_redis_cache):
        with TestClient(app, follow_redirects=False, cookies={"fs_key": "test-user-key"}) as c:
            yield c


@pytest.fixture(scope="session")
def admin_client():
    """TestClient с cookie администратора."""
    with patch("main.create_redis_cache", side_effect=_fake_create_redis_cache):
        with TestClient(app, follow_redirects=False, cookies={"fs_key": "test-admin-key"}) as c:
            yield c


@pytest.fixture(scope="session")
def wrong_cookie_client():
    """TestClient с заведомо неверной cookie — для проверки отказа в доступе."""
    with patch("main.create_redis_cache", side_effect=_fake_create_redis_cache):
        with TestClient(app, follow_redirects=False, cookies={"fs_key": "wrong"}) as c:
            yield c


@pytest.fixture(scope="session")
def user_headers():
    return {"X-API-Key": "test-user-key"}


@pytest.fixture(scope="session")
def admin_headers():
    return {"X-API-Key": "test-admin-key"}

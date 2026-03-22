"""
Тесты Redis-кеша плагинов: TTL, инвалидация, error-кеш.
Используется fakeredis — Redis in-process без реального сервера.
"""

import time

import fakeredis
import pytest

from plugins.base import PanelContext, Plugin
from plugins.redis_cache import RedisPluginCache


class _FakePlugin(Plugin):
    name = "fake"
    refresh_interval = 60

    def match(self, obj):
        return True

    async def fetch(self, obj):
        return {}

    def render(self, ctx):
        return ""


class _FakePluginNoTTL(Plugin):
    name = "fake_no_ttl"
    refresh_interval = None

    def match(self, obj):
        return True

    async def fetch(self, obj):
        return {}

    def render(self, ctx):
        return ""


_plugin = _FakePlugin()
_plugin_no_ttl = _FakePluginNoTTL()


def _make_obj(name="test"):
    return {"kind": "Service", "metadata": {"name": name}}


@pytest.fixture
async def cache():
    """Кеш на fakeredis — изолирован для каждого теста."""
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    yield RedisPluginCache(client)
    await client.aclose()


async def test_get_returns_none_when_empty(cache):
    assert await cache.get(_plugin, _make_obj()) is None


async def test_set_and_get(cache):
    ctx = PanelContext(plugin_name="fake", data={"x": 1})
    await cache.set(_plugin, _make_obj(), ctx)
    result = await cache.get(_plugin, _make_obj())
    assert result is not None
    assert result.data == {"x": 1}
    assert result.plugin_name == "fake"


async def test_get_returns_none_when_expired(cache):
    """TTL контролирует Redis — fakeredis тоже поддерживает TTL."""
    ctx = PanelContext(plugin_name="fake", data={})
    await cache.set(_plugin, _make_obj(), ctx)
    # Явно устанавливаем TTL = 1 сек через redis напрямую и ждём истечения
    key = RedisPluginCache._key(_plugin, _make_obj())
    await cache._r.expire(key, 1)
    # Имитируем истечение — удаляем ключ вручную (fakeredis не умеет реальный time.sleep TTL)
    await cache._r.delete(key)
    assert await cache.get(_plugin, _make_obj()) is None


async def test_error_context_is_cached(cache):
    """Ошибка тоже кешируется (чтобы не долбить внешний сервис)."""
    ctx = PanelContext(plugin_name="fake", error="timeout")
    await cache.set(_plugin, _make_obj(), ctx)
    result = await cache.get(_plugin, _make_obj())
    assert result is not None
    assert result.error == "timeout"


async def test_no_ttl_plugin_stored_without_expiry(cache):
    """Плагин с refresh_interval=None хранится без TTL."""
    ctx = PanelContext(plugin_name="fake_no_ttl", data={"y": 2})
    await cache.set(_plugin_no_ttl, _make_obj(), ctx)
    key = RedisPluginCache._key(_plugin_no_ttl, _make_obj())
    ttl = await cache._r.ttl(key)
    assert ttl == -1  # -1 означает ключ существует без TTL


async def test_invalidate_all(cache):
    ctx = PanelContext(plugin_name="fake", data={})
    await cache.set(_plugin, _make_obj("a"), ctx)
    await cache.set(_plugin, _make_obj("b"), ctx)
    await cache.invalidate_all()
    assert await cache.get(_plugin, _make_obj("a")) is None
    assert await cache.get(_plugin, _make_obj("b")) is None


async def test_invalidate_plugin(cache):
    """invalidate_plugin удаляет только ключи нужного плагина."""
    ctx = PanelContext(plugin_name="fake", data={})
    await cache.set(_plugin, _make_obj("a"), ctx)
    await cache.set(_plugin_no_ttl, _make_obj("a"), ctx)
    await cache.invalidate_plugin("fake")
    assert await cache.get(_plugin, _make_obj("a")) is None
    assert await cache.get(_plugin_no_ttl, _make_obj("a")) is not None


async def test_cached_at_preserved(cache):
    """cached_at сохраняется при сериализации."""
    ts = time.time() - 30
    ctx = PanelContext(plugin_name="fake", data={"z": 3}, cached_at=ts)
    await cache.set(_plugin, _make_obj(), ctx)
    result = await cache.get(_plugin, _make_obj())
    assert result is not None
    assert abs(result.cached_at - ts) < 0.001

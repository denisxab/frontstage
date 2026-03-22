"""
Персистентный кеш результатов плагинов на базе Redis.

Интерфейс совпадает с PluginCache (cache.py), поэтому планировщик
и main.py работают с любой реализацией без изменений.

Схема ключей (изоляция по плагину):
    fs:plugin:{plugin_name}:{kind}:{obj_name}

Пример:
    fs:plugin:git_last_commit:Service:billing-api

TTL задаётся через SETEX равным plugin.refresh_interval.
Если refresh_interval равен None — ключ без TTL (хранится вечно).

Сериализация: JSON. Плагины обязаны возвращать JSON-совместимые
данные из fetch() (dict/list/str/int/float/None).
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

import redis.asyncio as aioredis

if TYPE_CHECKING:
    from .base import PanelContext, Plugin


class RedisPluginCache:
    """Кеш плагинов с Redis-бэкендом и персистентностью между рестартами."""

    _KEY_PREFIX = "fs:plugin"

    def __init__(self, client: aioredis.Redis) -> None:
        self._r = client

    @staticmethod
    def _key(plugin: "Plugin", obj: dict) -> str:
        """Уникальный ключ для пары (плагин, объект каталога)."""
        return f"fs:plugin:{plugin.name}:{obj['kind']}:{obj['metadata']['name']}"

    async def get(self, plugin: "Plugin", obj: dict) -> "PanelContext | None":
        """
        Возвращает закешированный PanelContext или None.
        TTL контролируется Redis — просроченные ключи уже отсутствуют.
        """
        from .base import PanelContext

        raw = await self._r.get(self._key(plugin, obj))
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
            return PanelContext(
                plugin_name=payload["plugin_name"],
                data=payload.get("data"),
                error=payload.get("error"),
                cached_at=payload.get("cached_at", time.time()),
            )
        except Exception:
            # Повреждённая запись — считаем кеш отсутствующим
            return None

    async def set(self, plugin: "Plugin", obj: dict, ctx: "PanelContext") -> None:
        """Сохраняет PanelContext в Redis. TTL = plugin.refresh_interval."""
        payload = json.dumps(
            {
                "plugin_name": ctx.plugin_name,
                "data": ctx.data,
                "error": ctx.error,
                "cached_at": ctx.cached_at,
            },
            ensure_ascii=False,
        )
        key = self._key(plugin, obj)
        if plugin.refresh_interval is not None:
            await self._r.setex(key, plugin.refresh_interval, payload)
        else:
            await self._r.set(key, payload)

    async def invalidate_all(self) -> None:
        """Удаляет все ключи кеша плагинов (вызывается при reload каталога)."""
        # TODO: метод не используется в проекте, нужно починить
        keys = await self._r.keys(f"{self._KEY_PREFIX}:*")
        if keys:
            await self._r.delete(*keys)

    async def invalidate_plugin(self, plugin_name: str) -> None:
        """Удаляет все ключи конкретного плагина."""
        keys = await self._r.keys(f"{self._KEY_PREFIX}:{plugin_name}:*")
        if keys:
            await self._r.delete(*keys)


async def create_redis_cache(redis_url: str) -> RedisPluginCache:
    """
    Создаёт клиент Redis и проверяет соединение (ping).
    Бросает ConnectionError если Redis недоступен — сервер не стартует (fail fast).
    """
    client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        await client.ping()
    except Exception as exc:
        raise ConnectionError(
            f"Redis недоступен по адресу {redis_url!r}: {exc}"
        ) from exc
    return RedisPluginCache(client)

"""
Фоновый планировщик обновления кеша плагинов.
Запускается в lifespan FastAPI как asyncio-задача.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .base import PanelContext
    from .redis_cache import RedisPluginCache
    from .registry import PluginRegistry

logger = logging.getLogger("frontstage.plugins")


class PluginScheduler:
    def __init__(
        self,
        registry: "PluginRegistry",
        cache: RedisPluginCache,
        get_objects: Callable[[], list[dict]],
    ) -> None:
        self._registry = registry
        self._cache = cache
        self._get_objects = get_objects  # функция, возвращающая все объекты каталога
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        """Запустить фоновый цикл обновления."""
        self._task = asyncio.create_task(self._loop(), name="plugin_scheduler")
        logger.info("Планировщик плагинов запущен")

    def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    async def refresh_all(self) -> None:
        """Принудительно обновить кеш для всех плагинов × объектов."""
        objects = self._get_objects()
        for plugin in self._registry.plugins:
            if plugin.refresh_interval is None:
                continue  # этот плагин обновляется только по запросу
            for obj in objects:
                try:
                    if not plugin.match(obj):
                        continue
                except Exception:
                    continue
                await self._update(plugin, obj)

    async def invalidate_all(self) -> None:
        """Сбросить весь кеш (вызывается при reload каталога)."""
        await self._cache.invalidate_all()

    async def _update(self, plugin, obj: dict) -> None:
        """Выполнить fetch и записать результат в кеш."""
        from .base import PanelContext

        obj_id = f"{obj.get('kind')}/{obj.get('metadata', {}).get('name')}"
        try:
            data = await plugin.fetch(obj)
            ctx = PanelContext(plugin_name=plugin.name, data=data, cached_at=time.time())
            logger.debug("Плагин '%s' обновил кеш для %s", plugin.name, obj_id)
        except Exception as exc:
            logger.warning(
                "Плагин '%s' ошибка для %s: %s",
                plugin.name,
                obj_id,
                exc,
            )
            ctx = PanelContext(
                plugin_name=plugin.name,
                error=str(exc),
                cached_at=time.time(),
            )
        await self._cache.set(plugin, obj, ctx)

    async def _loop(self) -> None:
        """Основной цикл планировщика — проверяет устаревшие кеши каждые 60 секунд."""
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Непредвиденная ошибка в планировщике плагинов")
            await asyncio.sleep(60)

    async def _tick(self) -> None:
        """Один проход: обновляем только устаревшие записи."""
        objects = self._get_objects()
        for plugin in self._registry.plugins:
            if plugin.refresh_interval is None:
                continue
            for obj in objects:
                try:
                    if not plugin.match(obj):
                        continue
                except Exception:
                    continue
                # Redis сам вытесняет по TTL — None означает кеш истёк или отсутствует
                ctx = await self._cache.get(plugin, obj)
                if ctx is None:
                    await self._update(plugin, obj)

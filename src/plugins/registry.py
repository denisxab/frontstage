"""
Реестр плагинов FrontStage.
Хранит список зарегистрированных плагинов и предоставляет
метод для получения применимых плагинов к объекту каталога.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import Plugin

logger = logging.getLogger("frontstage.plugins")


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: list["Plugin"] = []

    def register(self, plugin: "Plugin") -> None:
        """Зарегистрировать плагин. Дубли по имени — ошибка."""
        names = {p.name for p in self._plugins}
        if plugin.name in names:
            raise ValueError(f"Плагин с именем '{plugin.name}' уже зарегистрирован")
        self._plugins.append(plugin)
        logger.info("Плагин зарегистрирован: %s", plugin.name)

    @property
    def plugins(self) -> list["Plugin"]:
        return list(self._plugins)

    def matching(self, obj: dict) -> list["Plugin"]:
        """Возвращает плагины, применимые к данному объекту."""
        result = []
        for plugin in self._plugins:
            try:
                if plugin.match(obj):
                    result.append(plugin)
            except Exception:
                logger.exception("Ошибка в plugin.match() плагина '%s'", plugin.name)
        return result

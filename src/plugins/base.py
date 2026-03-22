"""
Базовый класс плагина FrontStage.
Все плагины наследуют Plugin и реализуют match / fetch / render.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PanelContext:
    """Контекст данных для рендера панели плагина."""

    plugin_name: str
    data: Any = None            # результат Plugin.fetch()
    error: str | None = None    # текст ошибки, если fetch упал
    cached_at: float = field(default_factory=time.time)

    @property
    def ok(self) -> bool:
        return self.error is None


class Plugin(ABC):
    """Абстрактный базовый класс плагина."""

    # Уникальный идентификатор — переопределить в подклассе
    name: str = ""

    # Интервал обновления кеша в секундах.
    # None — обновлять только при первом запросе (не через планировщик).
    refresh_interval: int | None = 300

    @abstractmethod
    def match(self, obj: dict) -> bool:
        """
        Возвращает True, если плагин применим к объекту каталога.
        obj — сериализованный dict (apiVersion, kind, metadata, spec, source_file).
        Вызывается синхронно, должен быть быстрым.
        """

    @abstractmethod
    async def fetch(self, obj: dict) -> Any:
        """
        Выполняет основную работу плагина (сетевые запросы, git и т.д.).
        Результат кешируется в PanelContext.data.
        При исключении — ошибка записывается в PanelContext.error.
        """

    @abstractmethod
    def render(self, ctx: PanelContext) -> str:
        """
        Возвращает HTML-строку панели для вставки в detail.html.
        Плагин полностью контролирует внешний вид своей панели.
        """

"""
Система плагинов FrontStage.

Плагин — Python-класс, унаследованный от Plugin (plugins.base).
Каждый плагин:
  - определяет match(obj) — условие применимости к объекту каталога
  - реализует fetch(obj) — асинхронная загрузка данных (кешируется)
  - реализует render(ctx) — возвращает HTML-панель для detail.html

Регистрация:
  Добавить экземпляр плагина в plugin_registry ниже.

Планировщик:
  plugin_scheduler периодически обновляет кеш (интервал задаётся в плагине).
  Запускается в lifespan FastAPI (main.py).
"""

from .base import PanelContext, Plugin
from .redis_cache import RedisPluginCache
from .registry import PluginRegistry
from .scheduler import PluginScheduler

# ---------------------------------------------------------------------------
# Реестр плагинов — добавляй новые плагины сюда
# ---------------------------------------------------------------------------
from .git_last_commit import GitLastCommitPlugin

plugin_registry = PluginRegistry()
plugin_registry.register(GitLastCommitPlugin())

# ---------------------------------------------------------------------------
# Планировщик — создаётся в main.py после инициализации store
# ---------------------------------------------------------------------------

__all__ = [
    "Plugin",
    "PanelContext",
    "RedisPluginCache",
    "PluginRegistry",
    "plugin_registry",
    "PluginScheduler",
]

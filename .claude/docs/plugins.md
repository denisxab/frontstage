# Система плагинов FrontStage

Плагины добавляют панели в левую колонку страницы `detail.html` (`src/templates/catalog/detail.html`).

## Контракт плагина (`src/plugins/base.py`)

Каждый плагин — класс, унаследованный от `Plugin` (ABC):

| Атрибут / метод    | Тип           | Описание                                                                  |
| ------------------ | ------------- | ------------------------------------------------------------------------- |
| `name`             | `str`         | Уникальный идентификатор плагина                                          |
| `refresh_interval` | `int \| None` | Интервал фоновой перезагрузки кеша (сек). `None` — только по HTTP-запросу |
| `match(obj)`       | `bool`        | Применимость к объекту каталога. Синхронно, без I/O                       |
| `fetch(obj)`       | `async → Any` | Загрузка данных. Результат кешируется                                     |
| `render(ctx)`      | `str`         | Рендер HTML-панели. Получает `PanelContext` с `data` или `error`          |

`PanelContext` (dataclass): `plugin_name`, `data: Any`, `error: str | None`, `cached_at: float`.

**`match(obj: dict) -> bool`** вызывается синхронно при каждом HTTP-запросе к `detail.html`.
Плагин получает dict объекта каталога (все поля из YAML + `kind_lower`, `source_file`).

## Кеш плагинов

**Продакшн:** `RedisPluginCache` (`src/plugins/redis_cache.py`)

- Инициализируется в `lifespan` через `create_redis_cache(redis_url)` — fail fast если Redis недоступен
- Хранится в `app.state.plugin_cache`
- Схема ключей: `fs:plugin:{plugin_name}:{kind}:{obj_name}`
- TTL = `plugin.refresh_interval` через Redis `SETEX`
- Все методы async: `get` / `set` / `invalidate_all` / `invalidate_plugin`
- Сериализация: JSON — плагины должны возвращать JSON-совместимые данные из `fetch()`
- Пустой кеш при HTTP-запросе → `render()` получает `PanelContext(error="Загрузка данных...")` (заглушка)

**Тесты:** `PluginCache` (`src/plugins/cache.py`) — in-memory реализация, только для тестов.

## Планировщик (`src/plugins/scheduler.py` — `PluginScheduler`)

Фоновая asyncio-задача, запускается в `lifespan` FastAPI (`src/main.py`).

1. `start()` → `asyncio.create_task(_loop())`
2. `_loop()` — каждые 60 сек вызывает `_tick()`
3. `_tick()` — перебирает пары `(плагин × объект)`: если `match` и кеш устарел → `_update()`
4. `_update()` — `await plugin.fetch(obj)` → `plugin_cache.set(...)`. Ошибки → кеш как `PanelContext(error=str(e))`
5. `stop()` — отменяет задачу при shutdown

`refresh_all()` — принудительный обход всех пар без проверки TTL (используется при reload каталога).

## Рендер панелей в detail.html

`src/main.py` при запросе `/catalog/<kind>/<name>` вызывает `_collect_plugin_panels(obj_dict)`:

- перебирает `plugin_registry.matching(obj_dict)` (только где `match == True`)
- берёт `plugin_cache.get(plugin, obj_dict)` или создаёт заглушку
- вызывает `plugin.render(ctx)` → HTML-строка

В шаблоне:

```jinja2
{% for panel_html in plugin_panels %}
  {{ panel_html | safe }}
{% endfor %}
```

## Добавить новый плагин

1. Создать `src/plugins/<name>/plugin.py` с классом от `Plugin`
2. Реализовать `match`, `fetch`, `render`
3. Зарегистрировать в `src/plugins/__init__.py`: `plugin_registry.register(MyPlugin())`
4. Изменений в `main.py` и `detail.html` не требуется

## Эталонный пример: `git_last_commit`

**Файлы:** `src/plugins/git_last_commit/plugin.py`

**`match`:** объект должен иметь в `metadata.links` ссылку с `gitea.`, `github.com`, `gitlab.com` или `bitbucket.org`.

**`fetch`:** `git ls-remote` (определение ветки, fallback `master`) → `git clone --depth=1` → `git log -1` → парсинг → `shutil.rmtree` в `finally`. Вспомогательная `_run(cmd)` — `asyncio.create_subprocess_exec`, timeout 30 сек.

**Аутентификация:** `GIT_PLUGIN_USER` / `GIT_PLUGIN_PASSWORD` → URL дополняется `user:password@host`.

**Тесты:** `src/plugins/git_last_commit/tests/` — `test_match.py`, `test_fetch.py`, `test_render.py`.

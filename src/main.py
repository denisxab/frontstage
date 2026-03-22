"""
FrontStage — точка входа FastAPI-приложения.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, Security
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from auth import (
    api_require_admin,
    api_require_user,
    require_user,
    resolve_role_from_request,
)
from catalog import CatalogStore, Kind
from logger import get_api_logger, get_ui_logger, setup_logging
from plugins import PluginScheduler, plugin_registry
from plugins.redis_cache import RedisPluginCache, create_redis_cache

setup_logging()

_log_api = get_api_logger()
_log_ui = get_ui_logger()

# ---------------------------------------------------------------------------
# Инициализация хранилища каталога
# ---------------------------------------------------------------------------

CATALOG_DIR = Path(os.getenv("CATALOG_DIR", Path(__file__).parent.parent / "catalog"))

store = CatalogStore(CATALOG_DIR)

_log_startup = logging.getLogger("frontstage.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _log_startup.info("Старт приложения FrontStage")

    # Подключаемся к Redis — fail fast если недоступен
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    _log_startup.info("Подключение к Redis: %s", redis_url)
    plugin_cache: RedisPluginCache = await create_redis_cache(redis_url)
    _log_startup.info("Redis подключён")

    store.load()
    summary = store.summary()
    _log_startup.info(
        "Каталог загружен: %d объектов (%s)",
        summary["total"],
        ", ".join(f"{k}={v}" for k, v in summary["by_kind"].items() if v),
    )

    # Планировщик плагинов стартует после загрузки каталога
    scheduler = PluginScheduler(
        registry=plugin_registry,
        cache=plugin_cache,
        get_objects=lambda: [_serialize_obj(o) for o in store.all()],
    )
    scheduler.start()

    # Передаём кеш в app.state чтобы маршруты могли его использовать
    app.state.plugin_cache = plugin_cache

    yield
    _log_startup.info("Остановка приложения FrontStage")
    scheduler.stop()


app = FastAPI(
    title="FrontStage",
    version="0.1.0",
    lifespan=lifespan,
    swagger_ui_parameters={
        # Скрывать тег admin пока не авторизован — через tagsSorter + filter
        "docExpansion": "none",  # все теги свёрнуты по умолчанию
        "filter": True,  # включает поле поиска/фильтра
        "persistAuthorization": True,  # запоминает введённый ключ между перезагрузками
    },
    description="""
**FrontStage** — open-source developer portal для DevOps-команд.
Хранит описания всех компонентов инфраструктуры в YAML-файлах (Git as source of truth)
и предоставляет единый каталог сервисов, API, баз данных, библиотек и команд.

### Software Catalog

Каталог читается из YAML-файлов в директории `catalog/`.
Каждый файл описывает один объект:

| kind       | Что описывает                                     |
|------------|---------------------------------------------------|
| `Service`  | Микросервис, монолит, воркер, cronjob, фронтенд   |
| `API`      | REST, gRPC, GraphQL или async-интерфейс           |
| `Database` | PostgreSQL, Redis, MongoDB, Kafka и другие        |
| `Library`  | Внутренний пакет, SDK, shared-модуль              |
| `Team`     | Команда разработки или группа поддержки           |

#### Ссылки между объектами

Связи записываются в формате `kind:name`, например:

```yaml
owner: team:backend
dependsOn:
  - database:users-postgres
  - service:payment-service
```

### Управление каталогом

- **Источник данных:** YAML-файлы в `catalog/`
""",
    contact={
        "name": "FrontStage github",
        "url": "https://github.com/your-org/frontstage",
    },
    openapi_tags=[
        {
            "name": "catalog",
            "description": "Чтение объектов Software Catalog — сервисов, API, баз данных, библиотек, команд.",
        },
        {
            "name": "admin",
            "description": "Административные операции: перезагрузка данных каталога из файлов.",
        },
    ],
)

# ---------------------------------------------------------------------------
# Шаблоны и статика
# ---------------------------------------------------------------------------

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
# Глобальный дефолт — перекрывается явной передачей is_admin=True в маршрутах
templates.env.globals["is_admin"] = False

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Обработчик ошибок авторизации — редирект на /login для HTML-запросов
# ---------------------------------------------------------------------------


@app.exception_handler(401)
async def authn_handler(request: Request, exc):
    """HTML-запросы без ключа → /login, API-запросы → JSON 401."""
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(status_code=401, content={"detail": exc.detail})


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def _serialize_obj(obj) -> dict:
    """Конвертирует CatalogObject в dict для шаблона/JSON."""
    data = obj.model_dump(mode="json")
    data["kind_lower"] = obj.kind.value.lower()
    return data


def _match_dotpath(obj: dict, path: str, value: str) -> bool:
    """
    Проверяет соответствие объекта условию path=value.
    path — точечный путь, например 'metadata.tags' или 'spec.members.email'.
    Поддерживает: scalar, list[scalar], list[dict].
    """
    key, _, rest = path.partition(".")
    current = obj.get(key)
    if current is None:
        return False
    if not rest:
        # Конец пути
        if isinstance(current, list):
            return value in [str(v) for v in current]
        return str(current) == value
    # Продолжение пути
    if isinstance(current, list):
        return any(_match_dotpath(item, rest, value) for item in current if isinstance(item, dict))
    if isinstance(current, dict):
        return _match_dotpath(current, rest, value)
    return False


async def _collect_plugin_panels(obj_dict: dict, request: Request) -> list[str]:
    """
    Возвращает список HTML-строк панелей для применимых плагинов.
    Если кеш пуст — возвращает панель-заглушку (данные загружаются фоном).
    """
    import time

    from logger import get_plugins_logger
    from plugins.base import PanelContext

    _log_plugins = get_plugins_logger()
    cache = request.app.state.plugin_cache

    panels = []
    for plugin in plugin_registry.matching(obj_dict):
        ctx = await cache.get(plugin, obj_dict)
        if ctx is None:
            # Кеш ещё не готов — показываем заглушку
            _log_plugins.debug(
                "Плагин '%s': кеш пуст для %s/%s — показываем заглушку",
                plugin.name,
                obj_dict.get("kind"),
                obj_dict.get("metadata", {}).get("name"),
            )
            ctx = PanelContext(
                plugin_name=plugin.name,
                error="Загрузка данных...",
                cached_at=time.time(),
            )
        try:
            panel_html = plugin.render(ctx)
            # Оборачиваем HTML панели в контейнер с меткой плагина
            wrapped = (
                f'<div class="plugin-panel" data-plugin="{plugin.name}">'
                f'<div class="flex justify-end px-1 pb-0.5">'
                f'<span style="font-size:9px; color:#374151; font-family:monospace;">plugin:{plugin.name}</span>'
                f"</div>"
                f"{panel_html}"
                f"</div>"
            )
            panels.append(wrapped)
        except Exception:
            _log_plugins.exception("Ошибка рендера плагина '%s'", plugin.name)
    return panels


# ---------------------------------------------------------------------------
# Маршруты — HTML-страницы
# ---------------------------------------------------------------------------


def _counts() -> dict:
    """Возвращает словарь kind → количество для sidebar."""
    return store.summary()["by_kind"]


@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request):
    """Страница входа. Если cookie уже валидна — редирект на главную."""
    role = resolve_role_from_request(request)
    if role is not None:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "login.html")


@app.post("/login", include_in_schema=False)
async def login_submit(request: Request, api_key: str = Form(...)):
    """Проверяет ключ и устанавливает httpOnly cookie fs_key."""
    from auth import _resolve_role

    role = _resolve_role(api_key)
    client = request.client.host if request.client else "unknown"
    if role is None:
        _log_ui.warning("Неудачная попытка входа с %s", client)
        resp = RedirectResponse(url="/login?error=1", status_code=302)
        return resp
    _log_ui.info("Вход выполнен: роль=%s, ip=%s", role, client)
    resp = RedirectResponse(url="/", status_code=302)
    resp.set_cookie(
        key="fs_key",
        value=api_key,
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,  # 7 дней
    )
    return resp


@app.get("/logout", include_in_schema=False)
async def logout():
    """Удаляет cookie и редиректит на /login."""
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie("fs_key")
    return resp


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request, _role=Depends(require_user)):
    """Главная страница — обзор каталога."""
    _log_ui.debug("GET / role=%s", _role)
    summary = store.summary()
    objects = [_serialize_obj(o) for o in store.all()]
    return templates.TemplateResponse(
        request,
        "catalog/index.html",
        {
            "summary": summary,
            "objects": objects,
            "counts": _counts(),
            "is_admin": _role == "admin",
        },
    )


def _resolve_kind(kind: str) -> Kind:
    """Резолвит kind из URL без учёта регистра."""
    kind_lower = kind.lower()
    for k in Kind:
        if k.value.lower() == kind_lower:
            return k
    raise ValueError(f"Неизвестный kind: {kind}")


@app.get("/catalog/{kind}", response_class=HTMLResponse, include_in_schema=False)
async def catalog_list(request: Request, kind: str, _role=Depends(require_user)):
    """Список объектов по kind."""
    try:
        k = _resolve_kind(kind)
    except ValueError:
        _log_ui.warning("UI: неизвестный kind '%s'", kind)
        raise HTTPException(status_code=404, detail=f"Неизвестный kind: {kind}")

    objects = [_serialize_obj(o) for o in store.by_kind(k)]
    _log_ui.debug("UI: список %s — %d объектов, role=%s", k.value, len(objects), _role)
    return templates.TemplateResponse(
        request,
        "catalog/list.html",
        {
            "kind": k.value,
            "objects": objects,
            "counts": _counts(),
            "is_admin": _role == "admin",
        },
    )


@app.get("/catalog/{kind}/{name}", response_class=HTMLResponse, include_in_schema=False)
async def catalog_detail(request: Request, kind: str, name: str, _role=Depends(require_user)):
    """Детальная страница объекта."""
    try:
        k = _resolve_kind(kind)
    except ValueError:
        _log_ui.warning("UI: неизвестный kind '%s'", kind)
        raise HTTPException(status_code=404, detail=f"Неизвестный kind: {kind}")

    obj = store.get(k, name)
    if not obj:
        _log_ui.warning("UI: объект %s/%s не найден", kind, name)
        raise HTTPException(status_code=404, detail=f"{kind}/{name} не найден")
    _log_ui.debug("UI: detail %s/%s role=%s", kind, name, _role)

    # Резолвим зависимости для отображения
    resolved_deps = []
    spec_data = obj.spec
    for ref in getattr(spec_data, "dependsOn", []):
        dep = store.resolve_ref(ref)
        resolved_deps.append(
            {
                "ref": ref,
                "obj": _serialize_obj(dep) if dep else None,
            }
        )

    provides_apis = []
    for ref in getattr(spec_data, "providesApis", []):
        api = store.resolve_ref(ref)
        provides_apis.append(
            {
                "ref": ref,
                "obj": _serialize_obj(api) if api else None,
            }
        )

    owner_obj = None
    owner_ref = getattr(spec_data, "owner", None)
    if owner_ref:
        owner_obj_raw = store.resolve_ref(owner_ref)
        if owner_obj_raw:
            owner_obj = _serialize_obj(owner_obj_raw)

    # Обратные зависимости — кто зависит от этого объекта
    dependents = [_serialize_obj(d) for d in store.dependents_of(k, name)]

    # Панели плагинов — для каждого применимого плагина получаем/рендерим кеш
    obj_dict = _serialize_obj(obj)
    plugin_panels = await _collect_plugin_panels(obj_dict, request)

    return templates.TemplateResponse(
        request,
        "catalog/detail.html",
        {
            "obj": obj_dict,
            "resolved_deps": resolved_deps,
            "provides_apis": provides_apis,
            "owner_obj": owner_obj,
            "dependents": dependents,
            "counts": _counts(),
            "is_admin": _role == "admin",
            "plugin_panels": plugin_panels,
        },
    )


# ---------------------------------------------------------------------------
# API — JSON endpoints (для Alpine.js fetch)
# ---------------------------------------------------------------------------


@app.get(
    "/api/catalog",
    tags=["catalog"],
    summary="Все объекты каталога",
    description="""
Возвращает плоский список всех объектов каталога вне зависимости от их типа.

Каждый объект содержит:
- `apiVersion` — всегда `frontstage/v1`
- `kind` — тип объекта: `Service`, `API`, `Database`, `Library`, `Team`
- `metadata` — имя, заголовок, описание, теги, ссылки
- `spec` — тип-специфичные поля (зависит от `kind`)
- `kind_lower` — `kind` в нижнем регистре (удобно для построения URL)

Используется фронтендом для глобального поиска и фильтрации.

## Фильтрация через параметр `filter`

Используй повторяемый параметр `filter` в формате `path=value` (AND-логика).

Поддерживаемые типы значений:
- **scalar** — прямое сравнение: `?filter=kind=Service`
- **list[scalar]** — проверка вхождения: `?filter=metadata.tags=python`
- **list[dict]** — рекурсивный поиск: `?filter=spec.members.email=user@example.com`

Примеры:
```
GET /api/catalog?filter=kind=Service&filter=metadata.tags=python
GET /api/catalog?filter=metadata.tags=backend
GET /api/catalog?filter=spec.owner=team-platform
```
""",
    response_description="Список всех объектов каталога",
)
async def api_catalog_all(
    request: Request,
    filter: list[str] | None = Query(
        None,
        description=(
            "Фильтр в формате `path=value`, можно повторять. "
            "Пример: `filter=kind=Service&filter=metadata.tags=python`"
        ),
    ),
    _role: str = Security(api_require_user),
):
    objects = [_serialize_obj(o) for o in store.all()]
    # Разбираем filter-параметры вида "path=value" и применяем dot-path фильтрацию
    filters: dict[str, str] = {}
    for item in filter or []:
        if "=" in item:
            path, _, value = item.partition("=")
            filters[path.strip()] = value.strip()
    for path, value in filters.items():
        objects = [o for o in objects if _match_dotpath(o, path, value)]
    _log_api.info(
        "GET /api/catalog → %d объектов, role=%s, filters=%s",
        len(objects),
        _role,
        filters or "none",
    )
    return objects


@app.get(
    "/api/catalog/summary",
    tags=["catalog"],
    summary="Сводка по каталогу",
    description="""
Возвращает агрегированную статистику по каталогу.

Формат ответа:
```json
{
  "total": 10,
  "by_kind": {
    "Service": 3,
    "API": 2,
    "Database": 2,
    "Library": 1,
    "Team": 2
  }
}
```

Используется для отображения счётчиков в боковой панели навигации.
""",
    response_description="Общее количество объектов и разбивка по типам",
)
async def api_summary(_role: str = Security(api_require_user)):
    _log_api.debug("GET /api/catalog/summary, role=%s", _role)
    return store.summary()


@app.post(
    "/api/catalog/reload",
    tags=["admin"],
    summary="Перезагрузить каталог из файлов",
    description="""
Повторно читает все YAML-файлы из директории каталога и обновляет данные в памяти.

**Когда использовать:** после добавления, изменения или удаления YAML-файлов
без перезапуска сервера.

Директория каталога задаётся переменной окружения `CATALOG_DIR`
(по умолчанию: `catalog/` рядом с проектом).

Возвращает актуальную сводку после перезагрузки — такую же, как `GET /api/catalog/summary`.
""",
    response_description="Сводка по каталогу после перезагрузки",
)
async def api_reload(_role: str = Security(api_require_admin)):
    _log_api.info("POST /api/catalog/reload запрошен, role=%s", _role)
    store.load()
    summary = store.summary()
    _log_api.info(
        "Каталог перезагружен: %d объектов (%s)",
        summary["total"],
        ", ".join(f"{k}={v}" for k, v in summary["by_kind"].items() if v),
    )
    return summary

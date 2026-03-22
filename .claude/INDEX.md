# FrontStage — Карта проекта

## Навигация по задачам

| Задача                                        | Документ                          |
| --------------------------------------------- | --------------------------------- |
| Работа с плагинами (`src/plugins/`)           | `.claude/docs/plugins.md`         |
| Авторизация, API-ключи, маршруты              | `.claude/docs/auth.md`            |
| Software Catalog, YAML-формат, модели         | `.claude/docs/catalog.md`         |
| Логирование, категории логгеров               | `.claude/docs/logging.md`         |
| Алгоритм самопроверки после изменений         | `.claude/SELFCHECK.md`            |
| Ошибки запуска, 404/500, диагностика          | `.claude/docs/troubleshooting.md` |
| Спецификация YAML-формата каталога            | `docs/catalog/SPEC.md`            |
| CLI команды для проекта, основаны из tasks.py | `invoke-commands.md`              |

## Структура директорий

```
apps/frontstage/
├── src/
│   ├── main.py              — FastAPI: все маршруты, lifespan, _collect_plugin_panels
│   ├── auth.py              — авторизация по API-ключу
│   ├── logger.py            — настройка логирования
│   ├── catalog/
│   │   ├── models.py        — Pydantic-модели (Service, API, Database, Library, Team)
│   │   └── parser.py        — парсер YAML, CatalogStore
│   ├── plugins/
│   │   ├── __init__.py      — реестр + регистрация плагинов
│   │   ├── base.py          — абстрактный класс Plugin, PanelContext
│   │   ├── cache.py         — in-memory кеш (только в тестах)
│   │   ├── redis_cache.py   — Redis-кеш (продакшн)
│   │   ├── registry.py      — PluginRegistry
│   │   ├── scheduler.py     — фоновый asyncio-планировщик
│   │   └── git_last_commit/ — эталонный плагин
│   └── templates/
│       ├── base.html        — базовый шаблон с сайдбаром
│       ├── login.html       — страница входа
│       └── catalog/
│           ├── index.html   — главная страница каталога
│           ├── list.html    — список объектов по kind
│           └── detail.html  — детальная страница объекта (рендер панелей плагинов)
├── catalog/                 — тестовые YAML-данные
├── tests/                   — pytest-тесты (auth, catalog, plugins)
├── docs/catalog/SPEC.md     — формальная спецификация YAML (источник истины)
├── nginx/nginx.conf         — reverse proxy: gzip, кеш статики, keep-alive к uvicorn
├── tasks.py                 — все invoke-задачи
├── docker-compose.yml
├── Dockerfile
└── .env.example             — пример переменных окружения с комментариями
```

## Текущее состояние

Прототип реализован. Работает Software Catalog + система плагинов.

- Каталог: 5 kind, YAML-валидация, ссылки между объектами
- Плагины: Redis-кеш, фоновый планировщик, эталонный плагин `git_last_commit`
- Авторизация: два уровня (user/admin), open mode
- Деплой: nginx → uvicorn, Docker Compose
- Тесты: авторизация, модели, парсер, плагины

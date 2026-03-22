# CLI команды проекта (invoke)

Все команды запускаются через `invoke <команда>`.

## Docker

| Команда              | Описание                                          |
| -------------------- | ------------------------------------------------- |
| `invoke up`          | `docker compose up -d --build`                    |
| `invoke down`        | `docker compose down`                             |
| `invoke build`       | `docker compose build`                            |
| `invoke restart`     | Пересобрать и перезапустить (pre: build + up)     |
| `invoke logs`        | Последние 100 строк логов контейнера `frontstage` |
| `invoke logs-follow` | Следить за логами в реальном времени (`-f`)       |

## Каталог

| Команда         | Описание                                                                |
| --------------- | ----------------------------------------------------------------------- |
| `invoke reload` | Перезагрузить каталог без рестарта сервера (`POST /api/catalog/reload`) |

## Проверки

| Команда                | Описание                                                                          |
| ---------------------- | --------------------------------------------------------------------------------- |
| `invoke check`         | Полная проверка (запускает все check-\* задачи последовательно)                   |
| `invoke check-health`  | Проверить доступность сервера (`GET /`)                                           |
| `invoke check-pages`   | Проверить HTTP 200 для всех HTML-страниц каталога                                 |
| `invoke check-api`     | Проверить JSON API: `/api/catalog/summary`, `/api/catalog`, `/api/catalog/reload` |
| `invoke check-catalog` | Валидировать YAML-файлы каталога через `CatalogStore` (без запуска сервера)       |

## Redis и плагины

| Команда               | Описание                                            |
| --------------------- | --------------------------------------------------- |
| `invoke redis-ping`   | Проверить доступность Redis (`redis-cli ping`)      |
| `invoke redis-keys`   | Показать все ключи плагинов в Redis (`fs:plugin:*`) |
| `invoke cache-del`    | Удалить ключи из Redis-кеша                         |
| `invoke plugin-cache` | Показать содержимое кеша плагина с TTL              |

### cache-del — аргументы

```bash
# Удалить конкретный ключ
invoke cache-del --key fs:plugin:git_last_commit:Service:admin-panel

# Удалить все ключи плагина
invoke cache-del --plugin git_last_commit

# Удалить все ключи кеша
invoke cache-del

# Посмотреть что будет удалено без удаления
invoke cache-del --plugin git_last_commit --dry-run
```

### plugin-cache — аргументы

```bash
invoke plugin-cache # все плагины
invoke plugin-cache --plugin git_last_commit # конкретный плагин
```

## Бенчмарк

| Команда        | Описание                                              |
| -------------- | ----------------------------------------------------- |
| `invoke bench` | Apache Benchmark по ключевым URL на порту 8795        |

### bench — аргументы

```bash
invoke bench          # 100 запросов, параллелизм 10
invoke bench -n 500   # 500 запросов
invoke bench -n 200 --c-=20  # 200 запросов, 20 потоков
```

> **ВАЖНО:** перед запуском установите `LOG_LEVEL=INFO`, иначе логи будут скрыты и результаты могут быть искажены:
> ```bash
> LOG_LEVEL=INFO invoke bench
> ```

URL для бенчмарка:
- `http://localhost:8795/catalog/api`
- `http://localhost:8795/catalog/service/crm-service`
- `http://localhost:8795/catalog/api/esp-async`

## Разработка

| Команда       | Описание                                      |
| ------------- | --------------------------------------------- |
| `invoke lint` | Линтинг кода: `ruff check src/`               |
| `invoke test` | Запустить тесты: `pytest tests/`              |
| `invoke lock` | Обновить lock-файл: `poetry lock --no-update` |

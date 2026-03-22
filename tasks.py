"""
FrontStage — задачи управления через Invoke.
Использование: invoke <task> [аргументы]
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from invoke import Collection, task

APP_URL = "http://localhost:8080"
CATALOG_DIR = Path("./catalog")
SRC_DIR = Path("./src")


# ---------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------


def _http_get(url: str) -> tuple[int, bytes]:
    """GET-запрос, возвращает (статус, тело)."""
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except urllib.error.URLError:
        return 0, b""


def _http_post(url: str) -> tuple[int, bytes]:
    """POST-запрос без тела, возвращает (статус, тело)."""
    req = urllib.request.Request(url, data=b"", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except urllib.error.URLError:
        return 0, b""


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _fail(msg: str) -> None:
    print(f"  ✗ {msg}")


# ---------------------------------------------------------------
# Docker
# ---------------------------------------------------------------


@task
def up(c):
    """Запустить (docker compose up -d)."""
    c.run("docker compose up -d --build")


@task
def down(c):
    """Остановить (docker compose down)."""
    c.run("docker compose down")


@task
def build(c):
    """Пересобрать образ (docker compose build)."""
    c.run("docker compose build")


@task(pre=[build])
def restart(c):
    """Пересобрать и перезапустить."""
    c.run("docker compose up -d --build")


@task
def logs(c):
    """Показать последние 100 строк логов."""
    c.run("docker compose logs --tail=100 frontstage")


@task
def logs_follow(c):
    """Следить за логами в реальном времени."""
    c.run("docker compose logs -f frontstage")


# ---------------------------------------------------------------
# Каталог
# ---------------------------------------------------------------


@task
def reload(c):
    """Перезагрузить каталог без рестарта сервера."""
    status, body = _http_post(f"{APP_URL}/api/catalog/reload")
    if status == 200:
        data = json.loads(body)
        _ok(f"Каталог перезагружен: total={data['total']}")
    else:
        _fail(f"Сервер недоступен или вернул ошибку (HTTP {status})")
        sys.exit(1)


# ---------------------------------------------------------------
# Проверки
# ---------------------------------------------------------------


@task
def check_health(c):
    """Проверить доступность сервера."""
    print("--- Проверка доступности сервера ---")
    status, _ = _http_get(f"{APP_URL}/")
    if status == 200:
        _ok(f"{APP_URL}/ — OK")
    else:
        _fail(f"Сервер недоступен: {APP_URL} (HTTP {status})")
        sys.exit(1)


@task
def check_pages(c):
    """Проверить HTTP-коды всех HTML-страниц."""
    print("--- Проверка HTML-страниц ---")
    pages = [
        "/",
        "/catalog/service",
        "/catalog/api",
        "/catalog/database",
        "/catalog/library",
        "/catalog/team",
        "/catalog/service/user-service",
        "/catalog/team/backend",
        "/catalog/database/users-postgres",
    ]
    failed = False
    for page in pages:
        status, _ = _http_get(f"{APP_URL}{page}")
        if status == 200:
            _ok(f"{page} — {status}")
        else:
            _fail(f"{page} — {status} (ожидалось 200)")
            failed = True
    if failed:
        sys.exit(1)


@task
def check_api(c):
    """Проверить JSON API — структуру и содержимое."""
    print("--- Проверка JSON API ---")
    failed = False

    # /api/catalog/summary
    status, body = _http_get(f"{APP_URL}/api/catalog/summary")
    if status != 200:
        _fail("/api/catalog/summary — недоступен")
        sys.exit(1)
    try:
        data = json.loads(body)
        total = data["total"]
        _ok(f"/api/catalog/summary — total={total}")
    except (json.JSONDecodeError, KeyError):
        _fail("/api/catalog/summary — некорректный JSON")
        sys.exit(1)
    if total == 0:
        _fail("Каталог пуст — нет объектов")
        failed = True

    # /api/catalog
    status, body = _http_get(f"{APP_URL}/api/catalog")
    if status == 200:
        try:
            count = len(json.loads(body))
            _ok(f"/api/catalog — {count} объектов")
        except json.JSONDecodeError:
            _fail("/api/catalog — некорректный ответ")
            failed = True
    else:
        _fail(f"/api/catalog — HTTP {status}")
        failed = True

    # /api/catalog/reload
    status, _ = _http_post(f"{APP_URL}/api/catalog/reload")
    if status == 200:
        _ok("/api/catalog/reload — OK")
    else:
        _fail(f"/api/catalog/reload — HTTP {status}")
        failed = True

    if failed:
        sys.exit(1)


@task
def check_catalog(c):
    """Валидировать YAML-файлы каталога через парсер."""
    print("--- Валидация YAML-каталога ---")
    sys.path.insert(0, str(SRC_DIR))
    from catalog.parser import CatalogStore  # noqa: PLC0415

    store = CatalogStore(CATALOG_DIR)
    store.load()
    print(f"  Загружено: {len(store.objects)} объектов")
    for error in store.errors:
        _fail(f"Ошибка: {error}")
    if store.errors:
        _fail("Найдены ошибки в YAML")
        sys.exit(1)
    else:
        _ok("Все YAML-файлы валидны")


@task(pre=[check_health, check_pages, check_api, check_catalog])
def check(c):
    """Полная проверка работоспособности."""
    print()
    print("✓ Все проверки пройдены")


# ---------------------------------------------------------------
# Redis и плагины
# ---------------------------------------------------------------


@task
def redis_ping(c):
    """Проверить доступность Redis."""
    print("--- Redis ping ---")
    result = c.run(
        "docker compose exec redis redis-cli ping",
        warn=True,
        hide=True,
    )
    if result.ok and "PONG" in result.stdout:
        _ok("Redis доступен — PONG")
    else:
        _fail(f"Redis недоступен: {result.stderr or result.stdout}")
        sys.exit(1)


@task
def redis_keys(c):
    """Показать все ключи плагинов в Redis (fs:plugin:*)."""
    print("--- Ключи плагинов в Redis ---")
    result = c.run(
        "docker compose exec redis redis-cli keys fs:plugin:*",
        warn=True,
        hide=True,
    )
    if not result.ok:
        _fail(f"Ошибка: {result.stderr}")
        sys.exit(1)
    lines = [ln.strip() for ln in result.stdout.strip().splitlines() if ln.strip()]
    if not lines:
        print("  (нет ключей)")
    else:
        for line in sorted(lines):
            print(f"  {line}")
        print(f"\n  Итого: {len(lines)} ключей")


@task
def cache_del(c, key="", plugin="", dry_run=False):
    """Удалить ключи из Redis-кеша плагинов.

    # Удалить конкретный ключ
    invoke cache-del --key fs:plugin:git_last_commit:Service:admin-panel

    # Удалить все ключи плагина
    invoke cache-del --plugin git_last_commit

    # Удалить все ключи кеша
    invoke cache-del

    # Посмотреть что будет удалено без удаления
    invoke cache-del --plugin git_last_commit --dry-run
    """

    if key:
        pattern = key
    elif plugin:
        pattern = f"fs:plugin:{plugin}:*"
    else:
        pattern = "fs:plugin:*"

    print(f"--- Удаление ключей ({pattern}) {'[dry-run]' if dry_run else ''} ---")

    result = c.run(
        f'docker compose exec redis redis-cli keys "{pattern}"',
        warn=True,
        hide=True,
    )
    if not result.ok:
        _fail(f"Ошибка: {result.stderr}")
        sys.exit(1)

    keys = [ln.strip() for ln in result.stdout.strip().splitlines() if ln.strip()]
    if not keys:
        print("  (нет подходящих ключей)")
        return

    for k in sorted(keys):
        if dry_run:
            print(f"  [dry-run] удалить: {k}")
        else:
            c.run(f"docker compose exec redis redis-cli del {k}", warn=True, hide=True)
            _ok(f"Удалён: {k}")

    if not dry_run:
        print(f"\n  Итого удалено: {len(keys)} ключей")


@task
def plugin_cache(c, plugin=""):
    """Показать содержимое кеша плагина. -p <name> или все если не указан."""
    pattern = f"fs:plugin:{plugin}:*" if plugin else "fs:plugin:*"
    print(f"--- Кеш плагинов ({pattern}) ---")

    # Получаем список ключей (pattern передаём отдельным аргументом чтобы shell не раскрыл *)
    result = c.run(
        f'docker compose exec redis redis-cli keys "{pattern}"',
        warn=True,
        hide=True,
    )
    if not result.ok:
        _fail(f"Ошибка: {result.stderr}")
        sys.exit(1)

    keys = [ln.strip() for ln in result.stdout.strip().splitlines() if ln.strip()]
    if not keys:
        print("  (нет ключей)")
        return

    for key in sorted(keys):
        # Получаем значение и TTL
        val_result = c.run(
            f"docker compose exec redis redis-cli get {key}",
            warn=True,
            hide=True,
        )
        ttl_result = c.run(
            f"docker compose exec redis redis-cli ttl {key}",
            warn=True,
            hide=True,
        )
        ttl = ttl_result.stdout.strip() if ttl_result.ok else "?"
        print(f"\n  {key}  (TTL: {ttl}s)")
        raw = val_result.stdout.strip()
        try:
            parsed = json.loads(raw)
            # Укорачиваем data если слишком длинная
            pretty = json.dumps(parsed, ensure_ascii=False, indent=4)
            for line in pretty.splitlines():
                print(f"    {line}")
        except (json.JSONDecodeError, TypeError):
            print(f"    {raw[:200]}")


# ---------------------------------------------------------------
# Бенчмарк
# ---------------------------------------------------------------

BENCH_URL = "http://localhost:8795"
BENCH_URLS = [
    f"{BENCH_URL}/catalog/api",
    f"{BENCH_URL}/catalog/service/crm-service",
    f"{BENCH_URL}/catalog/api/esp-async",
]


@task
def bench(c, n=100, c_=25):
    """Бенчмарк через Apache Benchmark (ab).

    Запускать при LOG_LEVEL=INFO:
      LOG_LEVEL=INFO invoke bench

    Аргументы:
      -n  — число запросов (по умолчанию 100)
      -c  — уровень параллелизма (по умолчанию 25)
    """
    print("--- Apache Benchmark ---")
    print("  ВАЖНО: для корректного бенчмарка установите LOG_LEVEL=INFO")
    print(f"  Запросов: {n}, параллельно: {c_}")
    for url in BENCH_URLS:
        print(f"\n  >> {url}")
        result = c.run(f"ab -n {n} -c {c_} {url}", warn=True)
        if not result.ok:
            _fail(f"ab завершился с ошибкой для {url}")


# ---------------------------------------------------------------
# Разработка
# ---------------------------------------------------------------


@task
def lint(c):
    """Проверить код линтером (ruff)."""
    print("--- Линтинг ---")
    c.run(f"poetry run ruff check {SRC_DIR}")
    _ok("ruff — OK")


@task
def test(c):
    """Запустить тесты."""
    print("--- Тесты ---")
    if Path("tests").is_dir():
        c.run("poetry run pytest tests/")
    else:
        print("  (тесты не найдены)")


@task
def lock(c):
    c.run("poetry lock --no-update")


# ---------------------------------------------------------------
# Пространство имён
# ---------------------------------------------------------------

ns = Collection()
ns.add_task(up)
ns.add_task(down)
ns.add_task(build)
ns.add_task(restart)
ns.add_task(logs)
ns.add_task(logs_follow, name="logs-follow")
ns.add_task(reload)
ns.add_task(check)
ns.add_task(check_health, name="check-health")
ns.add_task(check_pages, name="check-pages")
ns.add_task(check_api, name="check-api")
ns.add_task(check_catalog, name="check-catalog")
ns.add_task(redis_ping, name="redis-ping")
ns.add_task(redis_keys, name="redis-keys")
ns.add_task(cache_del, name="cache-del")
ns.add_task(plugin_cache, name="plugin-cache")
ns.add_task(bench)
ns.add_task(lint)
ns.add_task(test)
ns.add_task(lock)

"""
FrontStage — задачи управления через Invoke.
Использование: invoke <task> [аргументы]
"""

import json
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from invoke import Collection, task

APP_URL = "http://localhost:8795"
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

BENCH_URL = APP_URL
BENCH_URLS = [
    f"{BENCH_URL}/catalog/api",
    f"{BENCH_URL}/catalog/service/crm-service",
    f"{BENCH_URL}/catalog/api/esp-async",
]


def _bench_url(url: str, n: int, concurrency: int, fail_fast: bool = False, token: str | None = None) -> dict:
    """Выполняет n запросов к url с заданным параллелизмом, возвращает статистику."""
    latencies = []
    errors = 0
    first_error: str | None = None
    stop_event = threading.Event()
    lock = threading.Lock()

    def worker(count):
        nonlocal errors, first_error
        for _ in range(count):
            if stop_event.is_set():
                break
            t0 = time.perf_counter()
            error_msg = None
            try:
                req = urllib.request.Request(url)
                if token:
                    req.add_header("X-API-Key", f"{token}")
                with urllib.request.urlopen(req, timeout=10) as r:
                    r.read()
                    if not (200 <= r.status < 400):
                        error_msg = f"HTTP {r.status}"
            except urllib.error.HTTPError as e:
                error_msg = f"HTTP {e.code} {e.reason}"
            except urllib.error.URLError as e:
                error_msg = f"URLError: {e.reason}"
            except Exception as e:
                error_msg = str(e)
            elapsed = (time.perf_counter() - t0) * 1000  # мс
            with lock:
                if error_msg is None:
                    latencies.append(elapsed)
                else:
                    errors += 1
                    if first_error is None:
                        first_error = error_msg
                    if fail_fast:
                        stop_event.set()

    # Распределяем запросы по потокам
    base, extra = divmod(n, concurrency)
    threads = []
    for i in range(concurrency):
        cnt = base + (1 if i < extra else 0)
        t = threading.Thread(target=worker, args=(cnt,))
        threads.append(t)

    t_start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total_time = time.perf_counter() - t_start

    if latencies:
        latencies.sort()
        p50 = statistics.median(latencies)
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        mean = statistics.mean(latencies)
        min_ = latencies[0]
        max_ = latencies[-1]
    else:
        p50 = p95 = p99 = mean = min_ = max_ = 0.0

    completed = len(latencies) + errors
    return {
        "total": completed,
        "ok": len(latencies),
        "errors": errors,
        "first_error": first_error,
        "rps": round(completed / total_time, 1) if total_time > 0 else 0.0,
        "mean_ms": round(mean, 1),
        "min_ms": round(min_, 1),
        "max_ms": round(max_, 1),
        "p50_ms": round(p50, 1),
        "p95_ms": round(p95, 1),
        "p99_ms": round(p99, 1),
    }


@task
def bench(c, n=1000, c_=100, fail_fast=False, token=None):
    """Бенчмарк на чистом Python (без ab).

    Запускать при LOG_LEVEL=INFO:
      LOG_LEVEL=INFO invoke bench

    Аргументы:
      -n           — число запросов (по умолчанию 100)
      -c           — уровень параллелизма (по умолчанию 25)
      --fail-fast  — остановить при первой ошибке и показать причину
      --token      — API-токен (передаётся в заголовке X-API-Key)
    """
    print("--- Benchmark ---")
    print("  ВАЖНО: для корректного бенчмарка установите LOG_LEVEL=INFO")
    print(f"  Запросов: {n}, параллельно: {c_}, fail-fast: {bool(fail_fast)}")
    if token:
        print("  Авторизация: Bearer ***")
    for url in BENCH_URLS:
        print(f"\n  >> {url}")
        s = _bench_url(url, int(n), int(c_), fail_fast=bool(fail_fast), token=token)
        print(f"     Всего: {s['total']}  OK: {s['ok']}  Ошибок: {s['errors']}")
        print(f"     RPS:  {s['rps']}")
        print(f"     Latency (мс): mean={s['mean_ms']}  min={s['min_ms']}  max={s['max_ms']}")
        print(f"     Percentiles:  p50={s['p50_ms']}  p95={s['p95_ms']}  p99={s['p99_ms']}")
        if s["errors"] > 0:
            print(f"  ПРЕДУПРЕЖДЕНИЕ: {s['errors']} запросов завершились с ошибкой")
            if s["first_error"]:
                print(f"  Первая ошибка: {s['first_error']}")
            if fail_fast:
                _fail("Остановлено из-за ошибки (--fail-fast)")


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

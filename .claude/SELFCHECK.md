# Самопроверка FrontStage

## Когда запускать

После любого изменения кода (`src/`), YAML (`catalog/`), шаблонов или Docker-файлов.

## Алгоритм проверки локально запущенного проекта

**1. Статика** (не требует Docker):

```bash
invoke check-catalog
```

**2. Пересборка и старт:**

```bash
invoke restart && invoke logs
```

Успешный старт: `Application startup complete`, `Каталог загружен: N объектов, 0 ошибок`.
Проблемы: строки `ERROR`, `ImportError`, `ValidationError`.

**3. Полная проверка:**

```bash
invoke check
```

Проверяет: health → pages (200) → API → catalog. Если прошло — задача выполнена.

**4. При падении check** — см. `.claude/docs/troubleshooting.md`.

> в крайнем случае можно посмотреть логи с локального сервера из logs/frontstage.log

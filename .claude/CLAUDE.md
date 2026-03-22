# FrontStage — Инструкции для Claude

- Отвечай кратко, экономь токены
- Используй CLI-команды с сжатым форматом вывода

## О проекте

**FrontStage** — лёгкий open-source developer portal (альтернатива Backstage).
Стек: Python / FastAPI, Alpine.js + Tailwind, YAML-конфиги, Redis-кеш плагинов, Docker Compose.

Для понимания структуры проекта: `.claude/INDEX.md`

**После каждого изменения кода или YAML** — запускать `invoke check`.
Команды и алгоритм самопроверки: `.claude/SELFCHECK.md`.

Деплой: nginx → uvicorn. Приложение: <http://localhost:8080>

## Актуализация документации

При изменениях (новые модули, роуты, модели, структура директорий) — обновляй `INDEX.md` и соответствующий файл в `.claude/docs/`.

## Язык

Комментарии в коде и документация — на русском.

## CLI команды

Полное описание: `.claude/docs/invoke-commands.md`

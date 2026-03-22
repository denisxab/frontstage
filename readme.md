# FrontStage

Лёгкий open-source developer portal - альтернатива Backstage, которую удобно внедрить и сопровождать самостоятельно.

![logo](docs\catalog\logo.png)

## Зачем FrontStage, если есть Backstage?

Backstage мощный, но тяжёлый: Node.js, TypeScript, плагины на React, сложный деплой и высокий порог вхождения. FrontStage решает ту же задачу - единый портал для команд - без лишней сложности.

| Категория         | FrontStage           | Backstage                  |
| ----------------- | -------------------- | -------------------------- |
| Серверный стек    | Python / FastAPI     | Node.js / TypeScript       |
| Фронтенд          | Alpine.js + Tailwind | React + Material UI        |
| Конфиги           | YAML                 | YAML + TypeScript plugins  |
| БД / Кеш          | Redis                | PostgreSQL                 |
| Кастомизация      | Python / Jinja       | Плагинная система на React |
| Лицензия          | MIT                  | Apache 2.0                 |
| Рекомендуемый RAM | 1gb                  | 16gb                       |
| Рекомендуемый CPU | 0.8cpu               | 4cpu                       |

**Главные преимущества:**

- DevOps понимает стек - Python. Не нужен отдельный фронтенд-разработчик.
- Alpine.js вместо React: шаблоны прозрачны, легко дебажить и дорабатывать.
- Swagger-документация из коробки - просто интегрировать любые бэкенды.
- Простой и читаемый код в одной репе — кастомизации легко вносить самостоятельно или с помощью AI-ассистентов.
- Отлично подходит для корпоративного AI/RAG: структурированные YAML-данные удобно индексировать.
- Разработчик и комьюнити FrontStage уделяет внимание оптимизации потребления ресурсов

_Проблемы Backstage - [debunking.md](./debunking.md)_

## Возможности

### Software Catalog

Централизованный реестр всех сервисов, библиотек, API, баз данных и их владельцев.

Решает проблему "кто отвечает за этот микросервис?" - вся информация об инфраструктуре в одном месте, в Git, в читаемом формате.

Объекты каталога: `Service`, `API`, `Database`, `Library`, `Team`.

## Быстрый старт

Через LLM вы можете быстро сделать конфиги из вашей документации

```bash
mv catalog catalog_example

claude -p 'На основание @docs/catalog/SPEC.md и примера @catalog_example - создай ./catalog для моей команды и сервисов: [Тут вставьте вашу доку]'
```

```bash
docker network create my-proxy-network
docker compose up -d --build
```

Откройте: http://localhost:8795/

## Технический стек

- **Сервер:** Python 3.10+, FastAPI, Jinja2, Nginx
- **Фронтенд:** Alpine.js, Tailwind CSS
- **Кеш:** Redis
- **Конфиги:** YAML
- **Деплой:** Docker, Docker Compose

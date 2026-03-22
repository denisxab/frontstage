# Software Catalog — Структура данных

Описание формата YAML-файлов для Software Catalog в FrontStage.

## Концепция

Каждый объект каталога — отдельный YAML-файл в Git. Это даёт:

- **Git as source of truth** — изменения через PR, история, ревью
- **Поиск владельца** — поле `owner` сразу отвечает "кто отвечает за сервис"
- **Граф зависимостей** — `dependsOn` позволяет визуализировать связи
- **Низкий барьер** — DevOps добавляет новый сервис за 10 строк YAML

## Типы объектов (kind)

| kind       | Описание                        |
| ---------- | ------------------------------- |
| `Service`  | Микросервис, приложение, воркер |
| `API`      | REST, gRPC, GraphQL, Async API  |
| `Database` | Любая БД или хранилище          |
| `Library`  | Переиспользуемая библиотека     |
| `Team`     | Команда и её участники          |

## Структура директорий каталога

```
catalog/
├── teams/
│   ├── backend.yaml
│   └── devops.yaml
├── services/
│   ├── user-service.yaml
│   └── payment-service.yaml
├── apis/
│   ├── public-rest-api.yaml
│   └── internal-grpc.yaml
├── databases/
│   ├── users-postgres.yaml
│   └── cache-redis.yaml
└── libraries/
    └── common-utils.yaml
```

## Формат ссылок между объектами

Ссылки используют формат `kind:name` — без UUID, легко читать и поддерживать:

```yaml
owner: team:backend
dependsOn:
  - database:users-postgres
  - service:payment-service
  - api:internal-grpc
```

## Жизненные циклы (lifecycle)

| lifecycle      | Описание                           |
| -------------- | ---------------------------------- |
| `production`   | Боевой, стабильный                 |
| `staging`      | Тестовое окружение                 |
| `experimental` | Прототип, может исчезнуть          |
| `deprecated`   | Устаревший, планируется к удалению |

## Примеры

- [Service](examples/service.yaml)
- [API](examples/api.yaml)
- [Database](examples/database.yaml)
- [Library](examples/library.yaml)
- [Team](examples/team.yaml)

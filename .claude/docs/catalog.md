# Software Catalog FrontStage

Источник истины по формату YAML: `docs/catalog/SPEC.md`.

## YAML-формат

- Каждый объект — отдельный `.yaml` файл в директории `catalog/`
- Обязательные поля: `apiVersion: frontstage/v1`, `kind`, `metadata.name`
- Типы объектов (`kind`): `Service`, `API`, `Database`, `Library`, `Team`
- Ссылки между объектами: `kind:name` (например `team:backend`, `database:users-postgres`)

## Валидация (`src/catalog/parser.py` — `CatalogStore`)

- Уникальность `name` в пределах `kind`
- Резолюция ссылок (referenced objects должны существовать)
- Форматы: slug, url, email

## Модели (`src/catalog/models.py`)

Pydantic-модели: `Service`, `API`, `Database`, `Library`, `Team`.
Каждая модель сериализуется в dict при передаче в плагины (`kind_lower`, `source_file` добавляются парсером).

## Команды

```bash
invoke check-catalog    # валидация YAML без запуска сервера
invoke reload           # перезагрузить каталог без рестарта (POST /api/catalog/reload)
```

Примеры YAML: `docs/catalog/examples/` (service, api, database, library, team).

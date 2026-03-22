# Software Catalog — Формальная спецификация формата YAML

Этот документ является источником истины для парсера и валидатора.
Все поля, типы и допустимые значения описаны исчерпывающим образом.

---

## 1. Соглашения

| Обозначение  | Смысл                                                      |
| ------------ | ---------------------------------------------------------- |
| **required** | Поле обязательно. Ошибка если отсутствует                  |
| **optional** | Поле необязательно. Если отсутствует — игнорируется        |
| `string`     | Строка UTF-8                                               |
| `string[]`   | Список строк                                               |
| `enum(...)`  | Одно из перечисленных значений                             |
| `ref`        | Ссылка на другой объект в формате `kind:name`              |
| `ref[]`      | Список ссылок                                              |
| `url`        | Строка, валидный HTTP/HTTPS URL                            |
| `email`      | Строка, валидный email                                     |
| `slug`       | Строка: только `[a-z0-9-]`, длина 1–63                     |
| `semver`     | Строка в формате семантической версии: `MAJOR.MINOR.PATCH` |

---

## 2. Общая структура любого объекта

Все объекты каталога имеют единую корневую структуру:

```
apiVersion   (required)  string
kind         (required)  enum(...)
metadata     (required)  object
spec         (required)  object — содержимое зависит от kind
```

### 2.1 Поле `apiVersion`

```
Тип:             string
Допустимые:      "frontstage/v1"
Обязательность:  required
```

### 2.2 Поле `kind`

```
Тип:             enum
Допустимые:      Service | API | Database | Library | Team
Обязательность:  required
```

### 2.3 Блок `metadata`

Общий для всех `kind`.

| Поле          | Тип        | Обязательность | Описание                                                            |
| ------------- | ---------- | -------------- | ------------------------------------------------------------------- |
| `name`        | `slug`     | **required**   | Уникальный идентификатор объекта. Уникален в пределах одного `kind` |
| `title`       | `string`   | **required**   | Человекочитаемое название                                           |
| `description` | `string`   | optional       | Краткое описание назначения объекта                                 |
| `tags`        | `string[]` | optional       | Произвольные теги для поиска и фильтрации. Каждый тег: `[a-z0-9-]`  |
| `links`       | `Link[]`   | optional       | Список внешних ссылок                                               |

#### Объект `Link`

| Поле    | Тип      | Обязательность | Описание                                                                                                                                                                  |
| ------- | -------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `title` | `string` | **required**   | Текст ссылки                                                                                                                                                              |
| `url`   | `url`    | **required**   | HTTP/HTTPS URL                                                                                                                                                            |
| `icon`  | `string` | optional       | Имя иконки. Предустановленные: `github`, `gitlab`, `gitea`, `git`, `grafana`, `sentry`, `confluence`, `jira`, `docs`. Если не задано — определяется автоматически по URL. |

---

## 3. Формат ссылок (`ref`)

Ссылки между объектами записываются как строка вида `kind:name`:

```
kind  — строчный вариант типа объекта: service | api | database | library | team
name  — slug целевого объекта
```

Примеры:

```yaml
owner: team:backend
dependsOn:
  - database:users-postgres
  - service:payment-service
  - api:internal-grpc
```

Валидатор проверяет, что объект с указанным `kind:name` существует в каталоге.

---

## 4. Общие поля `spec`

Поля, присутствующие в `spec` у нескольких `kind`:

| Поле        | Тип                                                   | Обязательность | Применимо к                     |
| ----------- | ----------------------------------------------------- | -------------- | ------------------------------- |
| `lifecycle` | `enum(production, staging, experimental, deprecated)` | **required**   | Service, API, Database, Library |
| `owner`     | `ref` → `Team`                                        | **required**   | Service, API, Database, Library |

---

## 5. Спецификация `kind: Service`

Описывает: микросервис, монолит, воркер, cronjob, фронтенд-приложение.

### `spec`

| Поле           | Тип                                             | Обязательность | Описание                   |
| -------------- | ----------------------------------------------- | -------------- | -------------------------- |
| `lifecycle`    | см. §4                                          | **required**   |                            |
| `owner`        | см. §4                                          | **required**   |                            |
| `type`         | `enum(backend, frontend, cli, worker, cronjob)` | **required**   | Тип сервиса                |
| `dependsOn`    | `ref[]`                                         | optional       | Что использует этот сервис |
| `providesApis` | `ref[]` → `API`                                 | optional       | Какие API предоставляет    |
| `deployments`  | `Deployment[]`                                  | optional       | Список деплойментов        |

#### Объект `Deployment`

| Поле     | Тип                                      | Обязательность | Описание                            |
| -------- | ---------------------------------------- | -------------- | ----------------------------------- |
| `host`   | `string`                                 | **required**   | Имя хоста/сервера                   |
| `url`    | `url`                                    | optional       | Публичный URL сервиса на этом хосте |
| `status` | `enum(healthy, degraded, down, unknown)` | optional       | Текущий статус. Default: `unknown`  |

---

## 6. Спецификация `kind: API`

Описывает: REST API, gRPC, GraphQL, очередь сообщений (async).

### `spec`

| Поле         | Тип                                | Обязательность | Описание                                    |
| ------------ | ---------------------------------- | -------------- | ------------------------------------------- |
| `lifecycle`  | см. §4                             | **required**   |                                             |
| `owner`      | см. §4                             | **required**   |                                             |
| `type`       | `enum(rest, grpc, graphql, async)` | **required**   | Тип интерфейса                              |
| `definition` | `Definition`                       | optional       | Спецификация API (OpenAPI, Protobuf и т.д.) |

#### Объект `Definition`

Должен содержать ровно одно из двух полей:

| Поле     | Тип      | Обязательность | Описание                                                |
| -------- | -------- | -------------- | ------------------------------------------------------- |
| `url`    | `url`    | one-of         | URL до файла спецификации (openapi.json, .proto и т.д.) |
| `inline` | `string` | one-of         | Спецификация вставлена прямо в YAML (multiline string)  |

Валидатор: если присутствуют оба поля — ошибка. Если отсутствуют оба — допустимо (definition опционален).

---

## 7. Спецификация `kind: Database`

Описывает: реляционные БД, кеши, документные хранилища, поисковые движки.

### `spec`

| Поле          | Тип                                                                                 | Обязательность | Описание                        |
| ------------- | ----------------------------------------------------------------------------------- | -------------- | ------------------------------- |
| `lifecycle`   | см. §4                                                                              | **required**   |                                 |
| `owner`       | см. §4                                                                              | **required**   |                                 |
| `engine`      | `enum(postgresql, mysql, redis, mongodb, sqlite, elasticsearch, clickhouse, kafka)` | **required**   | Движок БД                       |
| `version`     | `string`                                                                            | optional       | Версия движка. Свободная строка |
| `deployments` | `DbDeployment[]`                                                                    | optional       | Список деплойментов             |

#### Объект `DbDeployment`

| Поле       | Тип      | Обязательность | Описание                      |
| ---------- | -------- | -------------- | ----------------------------- |
| `host`     | `string` | **required**   | Имя хоста/сервера             |
| `database` | `string` | optional       | Имя базы данных на этом хосте |

---

## 8. Спецификация `kind: Library`

Описывает: внутренние пакеты, SDK, shared-модули.

### `spec`

| Поле        | Тип      | Обязательность | Описание                                           |
| ----------- | -------- | -------------- | -------------------------------------------------- |
| `lifecycle` | см. §4   | **required**   |                                                    |
| `owner`     | см. §4   | **required**   |                                                    |
| `language`  | `string` | **required**   | Язык: `python`, `go`, `typescript`, `java`, и т.д. |
| `version`   | `semver` | optional       | Текущая версия библиотеки                          |

---

## 9. Спецификация `kind: Team`

Описывает: команду разработки, группу поддержки, отдел.

> У `Team` нет полей `lifecycle` и `owner` в `spec`.

### `spec`

| Поле      | Тип        | Обязательность | Описание                  |
| --------- | ---------- | -------------- | ------------------------- |
| `members` | `Member[]` | optional       | Список участников команды |

#### Объект `Member`

| Поле    | Тип      | Обязательность | Описание                                                    |
| ------- | -------- | -------------- | ----------------------------------------------------------- |
| `name`  | `string` | **required**   | Полное имя                                                  |
| `email` | `email`  | optional       | Email                                                       |
| `role`  | `string` | optional       | Роль в команде: `lead`, `developer`, `qa`, `devops`, и т.д. |

---

## 10. Правила валидации

1. **Уникальность `name`** — в пределах одного `kind` значение `metadata.name` должно быть уникальным
2. **Резолюция ссылок** — каждая `ref` в `dependsOn`, `providesApis`, `owner` должна указывать на существующий объект
3. **Формат `slug`** — `metadata.name` и теги: только `[a-z0-9-]`, длина от 1 до 63 символов
4. **Формат `url`** — все URL должны начинаться с `http://` или `https://`
5. **Формат `email`** — стандартный формат `local@domain.tld`
6. **`definition` one-of** — в `API.spec.definition` нельзя одновременно указывать `url` и `inline`
7. **`lifecycle` обязателен** — у `Service`, `API`, `Database`, `Library`; у `Team` — отсутствует
8. **`owner` обязателен** — у `Service`, `API`, `Database`, `Library`; у `Team` — отсутствует
9. **`owner` ссылается на `Team`** — `owner` должен быть ссылкой вида `team:<name>`

---

## 11. Пример полного валидного файла (Service)

```yaml
apiVersion: frontstage/v1
kind: Service
metadata:
  name: user-service
  title: "User Service"
  description: "Управление пользователями и аутентификацией"
  tags: [python, fastapi, auth]
  links:
    - title: "Репозиторий"
      url: https://git.example.com/user-service
spec:
  lifecycle: production
  owner: team:backend
  type: backend
  dependsOn:
    - database:users-postgres
    - service:notification-service
  providesApis:
    - api:public-rest-api
  deployments:
    - host: german
      url: https://users.example.com
      status: healthy
```

# Типичные ошибки и диагностика

## Таблица ошибок

| Ошибка                                | Причина                         | Решение                                              |
| ------------------------------------- | ------------------------------- | ---------------------------------------------------- |
| `ImportError: cannot import name 'X'` | `PYTHONPATH` не содержит `src/` | Проверить `ENV PYTHONPATH=/app/src` в Dockerfile     |
| `ValidationError` при загрузке YAML   | Некорректное поле               | `invoke check-catalog` покажет файл и поле           |
| 404 на странице                       | Объект не найден в каталоге     | Проверить `name` и `kind` через API                  |
| 500 на странице                       | Ошибка в шаблоне Jinja2         | `invoke logs` — ищи обращение к несуществующему полю |

## Диагностика

```bash
# Список всех объектов каталога
curl -s http://localhost:8080/api/catalog | python3 -c "
import sys, json
for o in json.load(sys.stdin): print(o['kind'], o['metadata']['name'])
"

# Проверить конкретную страницу
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/catalog/service/user-service

# API summary
curl -s http://localhost:8080/api/catalog/summary | python3 -m json.tool
```

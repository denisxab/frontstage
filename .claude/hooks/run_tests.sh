#!/bin/bash

# Запускаем pytest и захватываем вывод
OUTPUT=$(pytest --tb=short 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
  # Тесты упали — блокируем остановку Claude и передаём ошибки
  echo "{
    \"decision\": \"block\",
    \"reason\": \"Тесты pytest упали. Исправь ошибки:\n$OUTPUT\"
  }"
  exit 0
fi

# Тесты прошли — даём Claude завершиться

"""
Централизованная настройка логирования FrontStage.

Логгеры делятся на три категории:
  - frontstage.api     — JSON API запросы (/api/*)
  - frontstage.ui      — HTML-страницы (/, /catalog/*, /login, /logout)
  - frontstage.plugins — работа плагинов (планировщик, fetch, render)

Настройка через переменные окружения:
  LOG_FILE  — путь к лог-файлу (по умолчанию /app/logs/frontstage.log)
  LOG_LEVEL — уровень логирования (по умолчанию INFO)
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Формат: дата-время | уровень | категория | сообщение
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """
    Инициализирует систему логирования.
    Вызывается один раз при старте приложения.
    Пишет в файл + stdout.

    Читает LOG_FILE и LOG_LEVEL из окружения в момент вызова,
    чтобы тесты успевали установить переменные до импорта main.
    """
    log_file = os.getenv("LOG_FILE", "/app/logs/frontstage.log")
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # LOG_TRUNCATE=1 — пересоздать файл при старте (используется в тестах)
    # RotatingFileHandler игнорирует mode='w' при maxBytes > 0, поэтому удаляем явно
    if os.getenv("LOG_TRUNCATE") == "1" and log_path.exists():
        log_path.unlink()

    # Ротирующий файловый хендлер: максимум 10 МБ, хранить 5 файлов
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,  # 10 МБ
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    # Консольный хендлер (видно в docker logs)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    level = getattr(logging, log_level, logging.INFO)

    # Корневой логгер получает оба хендлера
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Заглушить шумные логгеры сторонних библиотек
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_api_logger() -> logging.Logger:
    """Логгер для JSON API маршрутов."""
    return logging.getLogger("frontstage.api")


def get_ui_logger() -> logging.Logger:
    """Логгер для HTML UI маршрутов."""
    return logging.getLogger("frontstage.ui")


def get_plugins_logger() -> logging.Logger:
    """Логгер для системы плагинов."""
    return logging.getLogger("frontstage.plugins")

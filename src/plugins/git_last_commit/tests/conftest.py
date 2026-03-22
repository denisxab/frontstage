"""
Фикстуры для тестов плагина git_last_commit.
"""

import asyncio
import sys

import pytest

# На Windows proactor event loop оставляет незакрытые транспорты при завершении,
# что вызывает шум ValueError в stderr. SelectorEventLoop этого не делает.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
def obj_with_git_link():
    """Объект каталога со ссылкой на gitea-репозиторий."""
    return {
        "apiVersion": "frontstage/v1",
        "kind": "API",
        "metadata": {
            "name": "test-api",
            "title": "Test API",
            "description": None,
            "tags": [],
            "links": [
                {"title": "Репозиторий", "url": "https://gitea.example.com/org/repo", "icon": None}
            ],
        },
        "spec": {"lifecycle": "production", "owner": "team:backend", "type": "rest"},
        "source_file": "catalog/test-api.yaml",
        "kind_lower": "api",
    }


@pytest.fixture
def obj_without_git_link():
    """Объект каталога без git-ссылок."""
    return {
        "apiVersion": "frontstage/v1",
        "kind": "Database",
        "metadata": {
            "name": "test-db",
            "title": "Test DB",
            "description": None,
            "tags": [],
            "links": [
                {"title": "Документация", "url": "https://docs.example.com", "icon": None}
            ],
        },
        "spec": {"lifecycle": "production", "owner": "team:backend", "engine": "postgresql"},
        "source_file": "catalog/test-db.yaml",
        "kind_lower": "database",
    }

"""
Плагин git_last_commit — показывает последний коммит, ветку и README.md репозитория.

Применяется к объектам каталога у которых в metadata.links есть ссылка
на Git-репозиторий (gitea, github, gitlab).

Алгоритм:
  1. Находит первую git-ссылку в metadata.links
  2. git clone --depth=1 во временную директорию
  3. git log -1 — берёт hash, сообщение, автора, дату
  4. Читает README.md (или readme.md / README) если есть, конвертирует в HTML
  5. Возвращает dict с этими данными
  6. Временная директория удаляется после клонирования
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import mistune
from jinja2 import Environment, FileSystemLoader

from plugins.base import PanelContext, Plugin

# Шаблоны плагина лежат рядом с самим плагином
_TEMPLATES_DIR = Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=True)

logger = logging.getLogger("frontstage.plugins")

# Git-хосты, по которым определяем что ссылка — репозиторий
_GIT_HOSTS = ("gitea.", "github.com", "gitlab.com", "bitbucket.org")

# Учётные данные из переменных окружения (опционально)
_GIT_USER = os.getenv("GIT_PLUGIN_USER", "")
_GIT_PASSWORD = os.getenv("GIT_PLUGIN_PASSWORD", "")


def _is_git_url(url: str) -> bool:
    return any(host in url for host in _GIT_HOSTS)


def _inject_credentials(url: str) -> str:
    """Вставляет credentials в URL если заданы через env."""
    if not _GIT_USER or not _GIT_PASSWORD:
        return url
    # https://user:pass@host/...
    if url.startswith("https://"):
        return f"https://{_GIT_USER}:{_GIT_PASSWORD}@{url[len('https://') :]}"
    return url


class GitLastCommitPlugin(Plugin):
    name = "git_last_commit"
    refresh_interval = 600  # обновлять каждые 10 минут

    def match(self, obj: dict) -> bool:
        """Применяется если есть хотя бы одна ссылка на git-репозиторий."""
        links = obj.get("metadata", {}).get("links") or []
        return any(_is_git_url(link.get("url", "")) for link in links)

    async def fetch(self, obj: dict) -> dict[str, Any]:
        """Клонирует репозиторий и возвращает данные последнего коммита."""
        links = obj.get("metadata", {}).get("links") or []
        repo_url = next(
            (link["url"] for link in links if _is_git_url(link.get("url", ""))),
            None,
        )
        if not repo_url:
            raise ValueError("Git-ссылка не найдена")

        obj_name = obj.get("metadata", {}).get("name", "?")
        obj_kind = obj.get("kind", "?")
        logger.info("[git_last_commit] fetch: %s/%s → %s", obj_kind, obj_name, repo_url)

        auth_url = _inject_credentials(repo_url)
        tmpdir = tempfile.mkdtemp(prefix="frontstage_git_")
        try:
            result = await _clone_and_get_commit(auth_url, tmpdir)
            logger.info(
                "[git_last_commit] готово: %s/%s — ветка=%s коммит=%s",
                obj_kind,
                obj_name,
                result["branch"],
                result["hash"],
            )
            return result
        except Exception as e:
            logger.warning("[git_last_commit] ошибка: %s/%s — %s", obj_kind, obj_name, e)
            raise
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def render(self, ctx: PanelContext) -> str:
        """Возвращает HTML-панель с данными последнего коммита."""
        if ctx.error or ctx.data is None:
            error = ctx.error or "Данные ещё не загружены"
            tmpl = _jinja_env.get_template("panel_error.html")
            return tmpl.render(error=error)
        tmpl = _jinja_env.get_template("panel.html")
        return tmpl.render(**ctx.data)


async def _clone_and_get_commit(repo_url: str, tmpdir: str) -> dict[str, Any]:
    """Клонирует репозиторий и извлекает данные последнего коммита."""
    # Определяем ветку по умолчанию через ls-remote
    branch = await _detect_default_branch(repo_url)

    # Клонируем только последний коммит нужной ветки
    clone_cmd = [
        "git",
        "clone",
        "--depth=1",
        "--single-branch",
        "--branch",
        branch,
        repo_url,
        tmpdir,
    ]
    await _run(clone_cmd)

    # Получаем данные последнего коммита
    log_cmd = [
        "git",
        "-C",
        tmpdir,
        "log",
        "-1",
        "--format=%H%n%s%n%an%n%ad",
        "--date=format:%Y-%m-%d %H:%M",
    ]
    stdout = await _run(log_cmd)
    lines = stdout.strip().splitlines()
    if len(lines) < 4:
        raise ValueError(f"Неожиданный формат git log: {stdout!r}")

    readme_html = _read_readme(tmpdir)

    return {
        "branch": branch,
        "hash": lines[0][:7],
        "message": lines[1],
        "author": lines[2],
        "date": lines[3],
        "readme_html": readme_html,
    }


async def _detect_default_branch(repo_url: str) -> str:
    """Определяет ветку по умолчанию через git ls-remote --symref."""
    try:
        stdout = await _run(["git", "ls-remote", "--symref", repo_url, "HEAD"])
        # Ищем строку вида: ref: refs/heads/master	HEAD
        for line in stdout.splitlines():
            if line.startswith("ref: refs/heads/"):
                return line.split("refs/heads/")[1].split()[0]
    except Exception:
        pass
    return "master"  # fallback


def _read_readme(repo_dir: str) -> str | None:
    """Читает README.md из клонированного репозитория и конвертирует в HTML."""
    _md = mistune.create_markdown()
    for name in ("README.md", "readme.md", "Readme.md", "README.MD"):
        path = Path(repo_dir) / name
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace")
            result = _md(text)
            return result if isinstance(result, str) else None
    return None


async def _run(cmd: list[str]) -> str:
    """Запускает команду и возвращает stdout. Бросает исключение при ненулевом коде."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},  # не ждать интерактивного ввода
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    if proc.returncode != 0:
        err = stderr.decode(errors="replace").strip()
        raise RuntimeError(f"git завершился с кодом {proc.returncode}: {err}")
    return stdout.decode(errors="replace")

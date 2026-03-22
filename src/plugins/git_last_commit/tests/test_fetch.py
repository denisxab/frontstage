"""
Тесты fetch() плагина git_last_commit — мок subprocess.
"""

import pytest
from unittest.mock import patch

from plugins.git_last_commit import GitLastCommitPlugin
from plugins.git_last_commit.plugin import _clone_and_get_commit

plugin = GitLastCommitPlugin()


def _obj(git_url: str) -> dict:
    return {
        "kind": "API",
        "metadata": {
            "name": "test",
            "links": [{"url": git_url}],
        },
        "spec": {},
    }


GIT_LOG_OUTPUT = "abc1234567890\nfix: тестовый коммит\nIvan Petrov\n2024-01-15 10:30\n"
LS_REMOTE_OUTPUT = "ref: refs/heads/main\tHEAD\nabc123\tHEAD\n"


@pytest.mark.asyncio
async def test_fetch_returns_commit_data():
    """fetch() возвращает корректно распарсенные данные включая readme_html."""
    responses = [LS_REMOTE_OUTPUT, "", GIT_LOG_OUTPUT]
    call_count = 0

    async def fake_run(cmd):
        nonlocal call_count
        result = responses[call_count]
        call_count += 1
        return result

    with (
        patch("plugins.git_last_commit.plugin._run", fake_run),
        patch("plugins.git_last_commit.plugin.tempfile.mkdtemp", return_value="/tmp/test"),
        patch("plugins.git_last_commit.plugin.shutil.rmtree"),
        patch("plugins.git_last_commit.plugin._read_readme", return_value="<p>Привет</p>"),
    ):
        result = await plugin.fetch(_obj("https://gitea.example.com/org/repo"))

    assert result["branch"] == "main"
    assert result["hash"] == "abc1234"
    assert result["message"] == "fix: тестовый коммит"
    assert result["author"] == "Ivan Petrov"
    assert result["date"] == "2024-01-15 10:30"
    assert result["readme_html"] == "<p>Привет</p>"


@pytest.mark.asyncio
async def test_fetch_readme_none_when_missing():
    """fetch() возвращает readme_html=None если README отсутствует."""
    responses = [LS_REMOTE_OUTPUT, "", GIT_LOG_OUTPUT]
    call_count = 0

    async def fake_run(cmd):
        nonlocal call_count
        result = responses[call_count]
        call_count += 1
        return result

    with (
        patch("plugins.git_last_commit.plugin._run", fake_run),
        patch("plugins.git_last_commit.plugin.tempfile.mkdtemp", return_value="/tmp/test"),
        patch("plugins.git_last_commit.plugin.shutil.rmtree"),
        patch("plugins.git_last_commit.plugin._read_readme", return_value=None),
    ):
        result = await plugin.fetch(_obj("https://gitea.example.com/org/repo"))

    assert result["readme_html"] is None


@pytest.mark.asyncio
async def test_fetch_raises_on_git_error():
    """fetch() пробрасывает исключение при ошибке git."""
    async def fake_run(cmd):
        raise RuntimeError("git error")

    with (
        patch("plugins.git_last_commit.plugin._run", fake_run),
        patch("plugins.git_last_commit.plugin.tempfile.mkdtemp", return_value="/tmp/test"),
        patch("plugins.git_last_commit.plugin.shutil.rmtree"),
        patch("plugins.git_last_commit.plugin._read_readme", return_value=None),
    ):
        with pytest.raises(RuntimeError, match="git error"):
            await plugin.fetch(_obj("https://gitea.example.com/org/repo"))


@pytest.mark.asyncio
async def test_fetch_falls_back_to_master_branch():
    """При невозможности определить ветку — используется master."""
    # вызовы: 1) ls-remote (падает → fallback master), 2) git clone, 3) git log
    responses = [RuntimeError("ls-remote failed"), "", GIT_LOG_OUTPUT]
    call_count = 0

    async def fake_run(cmd):
        nonlocal call_count
        val = responses[call_count]
        call_count += 1
        if isinstance(val, Exception):
            raise val
        return val

    with (
        patch("plugins.git_last_commit.plugin._run", fake_run),
        patch("plugins.git_last_commit.plugin.tempfile.mkdtemp", return_value="/tmp/test"),
        patch("plugins.git_last_commit.plugin.shutil.rmtree"),
        patch("plugins.git_last_commit.plugin._read_readme", return_value=None),
    ):
        result = await plugin.fetch(_obj("https://gitea.example.com/org/repo"))

    assert result["branch"] == "master"

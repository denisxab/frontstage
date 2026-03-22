"""
Тесты render() плагина git_last_commit — HTML при data и при error.
"""

from plugins.base import PanelContext
from plugins.git_last_commit import GitLastCommitPlugin

plugin = GitLastCommitPlugin()


def _commit_data(readme_html=None):
    return {
        "branch": "master",
        "hash": "abc1234",
        "message": "fix: исправлен баг",
        "author": "Ivan",
        "date": "2024-01-15 10:30",
        "readme_html": readme_html,
    }


def test_render_with_data():
    ctx = PanelContext(plugin_name="git_last_commit", data=_commit_data())
    html = plugin.render(ctx)
    assert "master" in html
    assert "abc1234" in html
    assert "исправлен баг" in html
    assert "Ivan" in html


def test_render_with_readme():
    """render() отображает readme_html если он есть."""
    ctx = PanelContext(plugin_name="git_last_commit", data=_commit_data(readme_html="<p>Описание проекта</p>"))
    html = plugin.render(ctx)
    assert "Описание проекта" in html


def test_render_without_readme():
    """render() корректно рендерится когда readme_html=None."""
    ctx = PanelContext(plugin_name="git_last_commit", data=_commit_data(readme_html=None))
    html = plugin.render(ctx)
    assert "master" in html
    # Блока README нет — не должно быть артефактов
    assert "None" not in html


def test_render_with_error():
    ctx = PanelContext(plugin_name="git_last_commit", error="repository not found")
    html = plugin.render(ctx)
    assert "repository not found" in html
    # Не должно быть данных о коммите
    assert "master" not in html


def test_render_loading_placeholder():
    """Заглушка при пустом кеше (error = 'Загрузка данных...')."""
    ctx = PanelContext(plugin_name="git_last_commit", error="Загрузка данных...")
    html = plugin.render(ctx)
    assert "Загрузка данных" in html

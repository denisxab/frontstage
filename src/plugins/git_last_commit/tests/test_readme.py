"""
Тесты _read_readme() плагина git_last_commit.
"""

import tempfile
from pathlib import Path

from plugins.git_last_commit.plugin import _read_readme


def _write(tmpdir: str, filename: str, content: str) -> None:
    (Path(tmpdir) / filename).write_text(content, encoding="utf-8")


def test_reads_readme_md():
    """Читает README.md и возвращает HTML."""
    with tempfile.TemporaryDirectory() as d:
        _write(d, "README.md", "# Заголовок\n\nТекст.")
        html = _read_readme(d)
    assert html is not None
    assert "<h1" in html
    assert "Заголовок" in html
    assert "Текст" in html


def test_reads_lowercase_readme():
    """Читает readme.md (нижний регистр)."""
    with tempfile.TemporaryDirectory() as d:
        _write(d, "readme.md", "# Нижний регистр")
        html = _read_readme(d)
    assert html is not None
    assert "Нижний регистр" in html


def test_returns_none_when_no_readme():
    """Возвращает None если README отсутствует."""
    with tempfile.TemporaryDirectory() as d:
        html = _read_readme(d)
    assert html is None


def test_priority_order_is_uppercase_first():
    """README.md проверяется первым в списке кандидатов."""
    # На case-sensitive FS (Linux) README.md и readme.md — разные файлы.
    # На Windows FS нечувствительна к регистру, поэтому тест проверяет только
    # что _read_readme находит файл и возвращает HTML.
    import sys
    if sys.platform == "win32":
        with tempfile.TemporaryDirectory() as d:
            _write(d, "README.md", "# Заголовок")
            html = _read_readme(d)
        assert html is not None
        assert "Заголовок" in html
    else:
        with tempfile.TemporaryDirectory() as d:
            _write(d, "README.md", "# Верхний")
            _write(d, "readme.md", "# Нижний")
            html = _read_readme(d)
        assert html is not None
        assert "Верхний" in html


def test_renders_markdown_elements():
    """Базовые Markdown-элементы конвертируются в HTML."""
    md = "## Заголовок 2\n\n**жирный** и `код`\n\n- элемент 1\n- элемент 2\n"
    with tempfile.TemporaryDirectory() as d:
        _write(d, "README.md", md)
        html = _read_readme(d)
    assert html is not None
    assert "<h2" in html
    assert "<strong>" in html
    assert "<code>" in html
    assert "<li>" in html


def test_handles_empty_readme():
    """Пустой README не вызывает исключение."""
    with tempfile.TemporaryDirectory() as d:
        _write(d, "README.md", "")
        html = _read_readme(d)
    # mistune возвращает пустую строку или None — оба варианта допустимы
    assert html is None or isinstance(html, str)

"""
Тесты реестра плагинов: регистрация, дубли, match-routing.
"""

import pytest

from plugins.base import PanelContext, Plugin
from plugins.registry import PluginRegistry


class _AlwaysPlugin(Plugin):
    name = "always"

    def match(self, obj):
        return True

    async def fetch(self, obj):
        return {}

    def render(self, ctx):
        return "<div>always</div>"


class _NeverPlugin(Plugin):
    name = "never"

    def match(self, obj):
        return False

    async def fetch(self, obj):
        return {}

    def render(self, ctx):
        return "<div>never</div>"


def test_register_and_list():
    reg = PluginRegistry()
    reg.register(_AlwaysPlugin())
    assert len(reg.plugins) == 1


def test_duplicate_raises():
    reg = PluginRegistry()
    reg.register(_AlwaysPlugin())
    with pytest.raises(ValueError, match="уже зарегистрирован"):
        reg.register(_AlwaysPlugin())


def test_matching_returns_applicable(obj_with_git_link):
    reg = PluginRegistry()
    reg.register(_AlwaysPlugin())
    reg.register(_NeverPlugin())
    result = reg.matching(obj_with_git_link)
    assert len(result) == 1
    assert result[0].name == "always"

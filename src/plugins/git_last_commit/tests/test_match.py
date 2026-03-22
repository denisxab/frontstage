"""
Тесты match() плагина git_last_commit.
"""

import pytest

from plugins.git_last_commit import GitLastCommitPlugin

plugin = GitLastCommitPlugin()


def _obj(links):
    return {
        "kind": "Service",
        "metadata": {"name": "svc", "links": links},
        "spec": {},
    }


def test_match_gitea_link():
    assert plugin.match(_obj([{"url": "https://gitea.example.com/org/repo"}])) is True


def test_match_github_link():
    assert plugin.match(_obj([{"url": "https://github.com/org/repo"}])) is True


def test_match_gitlab_link():
    assert plugin.match(_obj([{"url": "https://gitlab.com/org/repo"}])) is True


def test_no_match_without_git_link():
    assert plugin.match(_obj([{"url": "https://docs.example.com"}])) is False


def test_no_match_empty_links():
    assert plugin.match(_obj([])) is False


def test_no_match_none_links():
    obj = {"kind": "Service", "metadata": {"name": "svc", "links": None}, "spec": {}}
    assert plugin.match(obj) is False

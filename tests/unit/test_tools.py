"""Unit tests for the Wikipedia helper and the agent's lookup tool — no network."""

from __future__ import annotations

from typing import Any

import pytest
import wikipedia

from person_finder import tools


def _patch_summary(
    monkeypatch: pytest.MonkeyPatch, outcome: Any
) -> None:
    def _fake(name: str, sentences: int = 3, auto_suggest: bool = True) -> str:
        if isinstance(outcome, type) and issubclass(outcome, BaseException):
            raise outcome(name, [])
        return outcome

    monkeypatch.setattr(tools.wikipedia, "summary", _fake)


def test_fetch_wiki_summary_returns_capped_text(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_summary(monkeypatch, "x" * 5000)

    out = tools.fetch_wiki_summary("Someone", sentences=3, char_cap=600)

    assert out is not None
    assert len(out) == 600


def test_fetch_wiki_summary_returns_none_on_disambiguation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_summary(monkeypatch, wikipedia.exceptions.DisambiguationError)

    assert tools.fetch_wiki_summary("John Smith", sentences=3, char_cap=600) is None


def test_fetch_wiki_summary_returns_none_on_page_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_summary(monkeypatch, wikipedia.exceptions.PageError)

    assert tools.fetch_wiki_summary("No Page", sentences=3, char_cap=600) is None


def test_fetch_wiki_summary_returns_none_on_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_summary(monkeypatch, ConnectionError)

    assert tools.fetch_wiki_summary("Anyone", sentences=3, char_cap=600) is None


def test_fetch_wiki_summary_returns_none_on_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_summary(monkeypatch, "   ")

    assert tools.fetch_wiki_summary("Blank", sentences=3, char_cap=600) is None


def test_wikipedia_lookup_tool_returns_article_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_summary(monkeypatch, "Marie Curie was a physicist and chemist.")

    # `.invoke` is the LangChain tool call surface.
    out = tools.wikipedia_lookup.invoke({"name": "Marie Curie"})

    assert "Marie Curie" in out


def test_wikipedia_lookup_tool_reports_miss_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_summary(monkeypatch, wikipedia.exceptions.PageError)

    out = tools.wikipedia_lookup.invoke({"name": "Nobody At All"})

    # Tool must hand the agent a usable string, not raise — so the agent can
    # decide to answer from its own knowledge or give up.
    assert "No Wikipedia article found" in out
    assert "Nobody At All" in out

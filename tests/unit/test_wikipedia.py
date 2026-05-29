"""Unit tests for raw Wikipedia access — no network.

`wikipedia.py` is the data-access layer: it talks to the `wikipedia` library
and returns plain strings, with no knowledge of LangChain or the agent.
"""

from __future__ import annotations

from typing import Any

import pytest
import wikipedia as wikipedia_lib

from person_finder import wikipedia


def _patch_summary(monkeypatch: pytest.MonkeyPatch, outcome: Any) -> None:
    def _fake(name: str, sentences: int = 3, auto_suggest: bool = True) -> str:
        if isinstance(outcome, type) and issubclass(outcome, BaseException):
            raise outcome(name, [])
        return outcome

    monkeypatch.setattr(wikipedia.wikipedia, "summary", _fake)


def test_fetch_wiki_summary_returns_capped_text(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_summary(monkeypatch, "x" * 5000)

    out = wikipedia.fetch_wiki_summary("Someone", sentences=3, char_cap=600)

    assert out is not None
    assert len(out) == 600


def test_fetch_wiki_summary_returns_none_on_disambiguation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_summary(monkeypatch, wikipedia_lib.exceptions.DisambiguationError)

    assert wikipedia.fetch_wiki_summary("John Smith", sentences=3, char_cap=600) is None


def test_fetch_wiki_summary_returns_none_on_page_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_summary(monkeypatch, wikipedia_lib.exceptions.PageError)

    assert wikipedia.fetch_wiki_summary("No Page", sentences=3, char_cap=600) is None


def test_fetch_wiki_summary_returns_none_on_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_summary(monkeypatch, ConnectionError)

    assert wikipedia.fetch_wiki_summary("Anyone", sentences=3, char_cap=600) is None


def test_fetch_wiki_summary_returns_none_on_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_summary(monkeypatch, "   ")

    assert wikipedia.fetch_wiki_summary("Blank", sentences=3, char_cap=600) is None

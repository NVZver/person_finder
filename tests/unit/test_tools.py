"""Unit tests for the agent's LangChain tools — no network.

`tools.py` is the agent-facing layer: two `@tool`s wrapping the raw Wikipedia
access in :mod:`person_finder.wikipedia`. `lookup_person` pulls a short bio
slice for identification; `lookup_best_work` pulls a longer slice for finding
notable work.
"""

from __future__ import annotations

import pytest

from person_finder import config, tools


def _capture_calls(monkeypatch: pytest.MonkeyPatch, result: str | None) -> list[dict]:
    """Replace the wiki fetch with a recorder; return the list of call kwargs."""
    calls: list[dict] = []

    def _fake(name: str, *, sentences: int, char_cap: int) -> str | None:
        calls.append({"name": name, "sentences": sentences, "char_cap": char_cap})
        return result

    monkeypatch.setattr(tools, "fetch_wiki_summary", _fake)
    return calls


def test_lookup_person_returns_article_text(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _capture_calls(monkeypatch, "Marie Curie was a physicist and chemist.")

    out = tools.lookup_person.invoke({"name": "Marie Curie"})

    assert "Marie Curie" in out
    # Identification uses the short bio slice.
    assert calls[0]["sentences"] == config.IDENTIFY_SENTENCES
    assert calls[0]["char_cap"] == config.IDENTIFY_CHAR_CAP


def test_lookup_person_reports_miss_without_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    _capture_calls(monkeypatch, None)

    out = tools.lookup_person.invoke({"name": "Nobody At All"})

    # Must hand the agent a usable string, not raise — so the agent can fall
    # back to its own knowledge or give up.
    assert "No Wikipedia article found" in out
    assert "Nobody At All" in out


def test_lookup_best_work_returns_article_text(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _capture_calls(monkeypatch, "Einstein developed the theory of relativity.")

    out = tools.lookup_best_work.invoke({"name": "Albert Einstein"})

    assert "relativity" in out
    # Notable-work research uses the longer article slice.
    assert calls[0]["sentences"] == config.TOOL_SENTENCES
    assert calls[0]["char_cap"] == config.TOOL_CHAR_CAP


def test_lookup_best_work_reports_miss_without_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    _capture_calls(monkeypatch, None)

    out = tools.lookup_best_work.invoke({"name": "Nobody At All"})

    assert "No Wikipedia article found" in out
    assert "Nobody At All" in out

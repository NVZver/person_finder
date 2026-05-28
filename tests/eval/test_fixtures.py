"""Smoke tests for the eval-tier fixtures."""

from __future__ import annotations

import pytest

from .conftest import PUBLIC_FIGURES


def test_public_figures_constant() -> None:
    assert PUBLIC_FIGURES == ["Albert Einstein", "Marie Curie"]


def test_judge_configured_skips_when_google_key_missing(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(pytest.skip.Exception) as exc_info:
        request.getfixturevalue("judge_configured")

    assert "GOOGLE_API_KEY" in str(exc_info.value)


def test_agent_under_test_skips_when_google_key_missing(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(pytest.skip.Exception) as exc_info:
        request.getfixturevalue("agent_under_test")

    assert "GOOGLE_API_KEY" in str(exc_info.value)

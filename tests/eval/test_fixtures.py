"""Smoke tests for the eval-tier fixtures."""

from __future__ import annotations

import pytest

from .conftest import PUBLIC_FIGURES


def test_public_figures_roster_is_non_trivial() -> None:
    """The live-agent guard depends on a non-trivial roster — keep at least 5
    iconic figures so a regression has multiple chances to surface."""
    assert len(PUBLIC_FIGURES) >= 5
    assert all(isinstance(name, str) and name.strip() for name in PUBLIC_FIGURES)


def test_agent_under_test_skips_when_groq_key_missing(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(pytest.skip.Exception) as exc_info:
        request.getfixturevalue("agent_under_test")

    assert "GROQ_API_KEY" in str(exc_info.value)

"""Unit tests for `person_finder.config`.

Covers Epic 1 AC: env loader resolves both keys at import time and raises a
clear error when either is missing or blank.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError


def test_settings_load_from_process_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-value")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test-value")

    from person_finder.config import Settings

    settings = Settings()

    assert settings.groq_api_key == "groq-test-value"
    assert settings.google_api_key == "google-test-value"


def test_settings_missing_groq_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test-value")

    from person_finder.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert "GROQ_API_KEY" in str(exc_info.value) or "groq_api_key" in str(exc_info.value)


def test_settings_missing_google_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-value")

    from person_finder.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert "GOOGLE_API_KEY" in str(exc_info.value) or "google_api_key" in str(exc_info.value)


def test_settings_blank_value_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test-value")

    from person_finder.config import Settings

    with pytest.raises(ValidationError):
        Settings()


def test_settings_load_from_dotenv_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GROQ_API_KEY=from-dotenv-groq\nGOOGLE_API_KEY=from-dotenv-google\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    from person_finder.config import Settings

    settings = Settings()

    assert settings.groq_api_key == "from-dotenv-groq"
    assert settings.google_api_key == "from-dotenv-google"


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-value")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test-value")

    from person_finder.config import get_settings

    first = get_settings()
    second = get_settings()

    assert first is second

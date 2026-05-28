"""Settings loads from env / .env and raises clearly when keys are missing."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from person_finder.config import Settings


def test_loads_from_process_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "groq-test")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test")

    settings = Settings()

    assert settings.groq_api_key == "groq-test"
    assert settings.google_api_key == "google-test"


def test_missing_groq_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test")

    with pytest.raises(ValidationError):
        Settings()


def test_missing_google_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "groq-test")

    with pytest.raises(ValidationError):
        Settings()


def test_blank_value_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test")

    with pytest.raises(ValidationError):
        Settings()


def test_loads_from_dotenv_file(tmp_path: Path) -> None:
    """Autouse fixture already chdir'd into tmp_path; just drop a .env there."""
    (tmp_path / ".env").write_text(
        "GROQ_API_KEY=from-dotenv-groq\nGOOGLE_API_KEY=from-dotenv-google\n",
        encoding="utf-8",
    )

    settings = Settings()

    assert settings.groq_api_key == "from-dotenv-groq"
    assert settings.google_api_key == "from-dotenv-google"

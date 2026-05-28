"""`groq_api_key()` reads env or .env and raises clearly when missing."""

from __future__ import annotations

from pathlib import Path

import pytest

from person_finder.config import groq_api_key


def test_loads_from_process_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "groq-test")

    assert groq_api_key() == "groq-test"


def test_missing_groq_raises() -> None:
    """Autouse fixture already deleted `GROQ_API_KEY`."""
    with pytest.raises(RuntimeError, match="GROQ_API_KEY is required"):
        groq_api_key()


def test_blank_value_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "")

    with pytest.raises(RuntimeError, match="GROQ_API_KEY is required"):
        groq_api_key()


def test_loads_from_dotenv_file(tmp_path: Path) -> None:
    """Autouse fixture chdir'd into tmp_path; load_dotenv reads `.env` from CWD."""
    (tmp_path / ".env").write_text("GROQ_API_KEY=from-dotenv-groq\n", encoding="utf-8")

    assert groq_api_key() == "from-dotenv-groq"

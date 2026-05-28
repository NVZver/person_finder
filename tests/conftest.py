"""Shared pytest configuration.

Two layers of isolation so a developer's real keys (in shell env or in
`.env` at the repo root) can't accidentally turn a "missing key" assertion
into a green test:

1. Strip both env vars from the process environment.
2. `chdir` into a per-test `tmp_path` so pydantic-settings resolves its
   `env_file=".env"` lookup against an empty directory instead of the repo
   root. Tests that want to exercise .env loading write their own `.env`
   into `tmp_path` (same directory).
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Remove project env vars, jail cwd, and clear the settings cache."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    try:
        from person_finder.config import get_settings
    except ImportError:
        return
    get_settings.cache_clear()

"""tests.e2e — full-pipeline integration suite.

Modeled on `tests/eval/__init__.py`: this package's `conftest.py` captures
the host's real API keys at conftest import time (before the root
`tests/conftest.py` autouse fixture strips them) and re-emits them via
`monkeypatch.setenv` for every e2e test. Tests skip cleanly when keys are
absent so empty-key dev paths stay green.
"""

from __future__ import annotations

import os
from typing import NamedTuple


class RealKeys(NamedTuple):
    """Snapshot of `GROQ_API_KEY` + `GOOGLE_API_KEY` captured pre-isolation."""

    groq_api_key: str | None
    google_api_key: str | None


def _capture_real_keys() -> RealKeys:
    """Read the host env once. Called at conftest import time.

    Must run BEFORE the root `tests/conftest.py` autouse `_isolate_env`
    fixture deletes the keys. Pytest imports `conftest.py` files during
    collection, before any test fixture executes.
    """
    return RealKeys(
        groq_api_key=os.environ.get("GROQ_API_KEY"),
        google_api_key=os.environ.get("GOOGLE_API_KEY"),
    )

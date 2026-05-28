"""Fixtures + key restoration for the e2e tier (`tests/e2e/`).

Mirrors `tests/eval/conftest.py` in shape but stripped down: this tier
only needs `GROQ_API_KEY` to run the agent end-to-end (no judge model,
no DeepEval). The root `tests/conftest.py` strips both keys for every
test; this autouse fixture re-emits whatever the host shell had at
conftest import time so the e2e subprocess can reach Groq.

Tests skip with a precise reason when `GROQ_API_KEY` is absent so
empty-key dev paths stay green.
"""

from __future__ import annotations

import pytest

from . import RealKeys, _capture_real_keys

# Captured ONCE, at conftest import time, before any autouse fixture
# from the root `tests/conftest.py` has a chance to delete the keys.
_REAL_KEYS: RealKeys = _capture_real_keys()


def _restore_keys(monkeypatch: pytest.MonkeyPatch, keys: RealKeys) -> None:
    """Re-emit captured keys via `monkeypatch.setenv` for one test.

    Empty / `None` values are skipped so a developer with neither key in
    their shell sees the same env the unit tier sees (and the e2e test
    then skips with the documented reason).
    """
    if keys.groq_api_key:
        monkeypatch.setenv("GROQ_API_KEY", keys.groq_api_key)
    if keys.google_api_key:
        monkeypatch.setenv("GOOGLE_API_KEY", keys.google_api_key)


@pytest.fixture(autouse=True)
def _restore_real_keys_for_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer ON TOP of the root `_isolate_env` autouse fixture.

    Same-scope fixtures resolve outer-conftest before inner-conftest, so
    the root `_isolate_env` deletes both keys for every test, then THIS
    function-scoped autouse fixture re-emits whatever the host shell had.
    Unit isolation is preserved — this fixture only loads under
    `tests/e2e/`.
    """
    _restore_keys(monkeypatch, _REAL_KEYS)


@pytest.fixture
def real_keys() -> RealKeys:
    """Expose the captured-at-import host env keys as a typed snapshot."""
    return _REAL_KEYS

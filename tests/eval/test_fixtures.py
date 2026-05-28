"""Smoke tests for the eval-tier fixtures.

These tests prove three things the rest of the eval suite depends on:

1. The captured-key NamedTuple (`real_keys`) exposes whatever was in the host
   env at conftest import time, even after the root `tests/conftest.py`
   autouse fixture strips both keys.
2. The dir-level autouse re-set fixture re-emits the captured values via
   `monkeypatch.setenv` for every eval test, so `os.environ` is correct
   INSIDE the test body.
3. `judge_configured` and `agent_under_test` each emit skip messages whose
   wording names the missing prerequisite.

The tests do NOT call DeepEval, Gemini, Groq, or the agent. Everything
runs side-effect-free.
"""

from __future__ import annotations

import os

import pytest

from . import RealKeys
from . import conftest as eval_conftest
from .conftest import PUBLIC_FIGURES


def test_public_figures_constant_is_stable() -> None:
    """Roster is a fixed two-name list of well-known public figures."""
    assert PUBLIC_FIGURES == ["Albert Einstein", "Marie Curie"]


def test_real_keys_exposes_captured_values(real_keys: RealKeys) -> None:
    """`real_keys` is a NamedTuple-like with `groq_api_key` + `google_api_key` attrs.

    We can't directly observe what was in `os.environ` at conftest IMPORT
    time from inside a test (pytest only invokes us long after that), so we
    test the wiring: the fixture must return the same object as
    `eval_conftest._REAL_KEYS` (which IS what was captured at import).
    """
    assert real_keys is eval_conftest._REAL_KEYS
    assert hasattr(real_keys, "groq_api_key")
    assert hasattr(real_keys, "google_api_key")


def test_autouse_restores_keys_after_root_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dir-level autouse fixture re-sets the keys inside the test body.

    Setup: simulate that the host shell had both keys set by patching the
    module-level capture constant. The dir-level autouse fixture has
    already run by the time this test body executes (it's function-scoped
    and lives in `tests/eval/conftest.py`), so we can't re-trigger it from
    here. Instead, we re-invoke its logic against a fresh simulated
    capture and verify the env ends up with the keys re-emitted.
    """
    fake = RealKeys(groq_api_key="captured-groq", google_api_key="captured-google")
    monkeypatch.setattr(eval_conftest, "_REAL_KEYS", fake)

    # Root autouse `_isolate_env` already deleted both keys before we got
    # here; re-running the eval-tier restore against the patched capture
    # is what _restore_real_keys_for_eval does on every eval test.
    eval_conftest._restore_keys(monkeypatch, fake)

    assert os.environ.get("GROQ_API_KEY") == "captured-groq"
    assert os.environ.get("GOOGLE_API_KEY") == "captured-google"


def test_judge_configured_skips_when_google_key_missing(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Skip reason for the judge-config path must name `GOOGLE_API_KEY`."""
    monkeypatch.setattr(
        eval_conftest,
        "_REAL_KEYS",
        RealKeys(groq_api_key="groq-present", google_api_key=None),
    )

    with pytest.raises(pytest.skip.Exception) as exc_info:
        request.getfixturevalue("judge_configured")

    assert "GOOGLE_API_KEY" in str(exc_info.value)


def test_agent_under_test_skips_on_missing_google_key(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First cascade step — missing Google key → skip naming it."""
    monkeypatch.setattr(
        eval_conftest,
        "_REAL_KEYS",
        RealKeys(groq_api_key="groq-present", google_api_key=None),
    )

    with pytest.raises(pytest.skip.Exception) as exc_info:
        request.getfixturevalue("agent_under_test")

    assert "GOOGLE_API_KEY" in str(exc_info.value)

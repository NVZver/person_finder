"""Fixtures and isolation override for the eval tier (`tests/eval/`).

Four responsibilities, in execution order:

1. **Capture real API keys at conftest import time** — runs BEFORE the
   root `tests/conftest.py` autouse fixture deletes them. The snapshot
   is later re-emitted into `os.environ` for every eval test, so the
   eval tier sees the developer's actual shell env while the unit tier
   stays jailed (NF2).
2. **`real_keys` (function-scoped)** — exposes that snapshot as a typed
   `RealKeys` NamedTuple. Function-scoped so tests can monkeypatch
   `_REAL_KEYS` to exercise skip paths; production semantics are
   unchanged (the constant is captured once at module import).
3. **`judge_configured` (function-scoped)** — instantiates DeepEval's
   `GeminiModel` for Gemini 2.0 Flash when the Google key is present;
   skips at fixture level otherwise (NF6, F3). The DeepEval import is
   inside the fixture to keep conftest import side-effect-free (NF4).
4. **`agent_under_test` (function-scoped)** — skip-then-import-then-skip
   cascade per design.md §"Skip-or-run decision flow". Returns the
   agent callable when prerequisites are met; otherwise skips with a
   message naming the FIRST missing prerequisite (NF6, F4).

A small `PUBLIC_FIGURES` constant (F5) lives at module scope so live
tests in later epics can parametrize over it without duplicating the
roster.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest

from . import RealKeys, _capture_real_keys

# Roster for the eval suite — fixed, well-known public figures so the
# LLM has training data to draw on (F5). NOT sourced from
# `fetch_user_names()` (Epic 2): random-user names defeat the eval
# because the LLM can't know them.
PUBLIC_FIGURES: list[str] = ["Albert Einstein", "Marie Curie"]


# Captured ONCE, at conftest import time, before any autouse fixture
# from the root `tests/conftest.py` has a chance to delete the keys.
_REAL_KEYS: RealKeys = _capture_real_keys()


def _restore_keys(monkeypatch: pytest.MonkeyPatch, keys: RealKeys) -> None:
    """Re-emit captured keys via `monkeypatch.setenv` for one test.

    Extracted as a module-level helper so tests can exercise the
    re-set logic directly without re-entering the autouse machinery.
    Empty / `None` values are skipped so a developer with neither key
    in their shell sees the same env the unit tier sees (and downstream
    fixtures skip cleanly with the documented reason).
    """
    if keys.groq_api_key:
        monkeypatch.setenv("GROQ_API_KEY", keys.groq_api_key)
    if keys.google_api_key:
        monkeypatch.setenv("GOOGLE_API_KEY", keys.google_api_key)


@pytest.fixture(autouse=True)
def _restore_real_keys_for_eval(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer ON TOP of the root `_isolate_env` autouse fixture.

    Pytest runs higher-scoped fixtures first; same-scope fixtures resolve
    outer-conftest before inner-conftest. The root `_isolate_env`
    deletes both keys for every test, then THIS function-scoped autouse
    fixture re-emits whatever the host shell had at conftest import
    time — but only for tests under `tests/eval/`. Unit isolation is
    preserved (NF2 + NF5).
    """
    _restore_keys(monkeypatch, _REAL_KEYS)


@pytest.fixture
def real_keys() -> RealKeys:
    """Expose the captured-at-import host env keys as a typed snapshot.

    Function-scoped so a test can `monkeypatch.setattr` `_REAL_KEYS` and
    have the change propagate downstream (a session-scope cache would
    bake in whichever value was captured first and ignore the patch).
    The production semantics are unchanged — `_REAL_KEYS` is a module
    constant set once at import, so every test reads the same snapshot
    when nothing patches it.
    """
    return _REAL_KEYS


@pytest.fixture
def judge_configured(real_keys: RealKeys) -> Any:
    """Skip-gate for the (future) Gemini 2.0 Flash judge.

    When `GOOGLE_API_KEY` is absent, skips with a message naming the var
    (NF6). When present, returns a sentinel string — the deterministic
    metrics exercised by this epic do not call the judge, so the gate's
    only job here is to surface the prerequisite uniformly.

    The Gemini SDK install (and `GeminiModel` instantiation) is
    deferred to the follow-up live-judge epic per `specs/modules/eval/spec.md`
    NF3. Until then, importing the SDK inside this fixture would either
    fail (SDK not installed) or have no consumer (no metric calls the
    judge), so we don't import it.
    """
    if not real_keys.google_api_key:
        pytest.skip("GOOGLE_API_KEY unset — DeepEval judge cannot be configured")
    return "<judge deferred — Gemini SDK install belongs to the live-judge follow-up epic>"


@pytest.fixture
def agent_under_test(real_keys: RealKeys) -> Callable[..., Any]:
    """Return the agent callable, or skip with a precise reason.

    Cascade per design.md §"Skip-or-run decision flow":

      1. No `GOOGLE_API_KEY` → skip naming it (judge can't be wired).
      2. `person_finder.agent` not importable (Epic 3 not yet merged)
         → skip naming the missing module (NF6, E1-AC5).
      3. No `GROQ_API_KEY` → skip naming it (agent can't reach Groq).
      4. Otherwise → return the agent's public callable.

    The exact public name (`run_agent`, `find_people`, …) is the parallel
    Epic 3 PR's decision (design.md OQ1). The lazy import here keeps
    Epic 1 landable today and adapts with a single-line edit later.
    """
    if not real_keys.google_api_key:
        pytest.skip("GOOGLE_API_KEY unset — DeepEval judge cannot be configured")
    try:
        from person_finder.agent import run_agent
    except ImportError as exc:
        pytest.skip(
            f"person_finder.agent not importable yet — Epic 3 pending ({exc})"
        )
    if not real_keys.groq_api_key:
        pytest.skip("GROQ_API_KEY unset — agent cannot reach Groq")
    return run_agent

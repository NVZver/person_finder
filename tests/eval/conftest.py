"""Fixtures for the eval tier.

Tests skip cleanly when their required API keys are absent so empty-key dev
paths stay green.
"""

from __future__ import annotations

import os
from typing import Any, Callable

import pytest

PUBLIC_FIGURES: list[str] = ["Albert Einstein", "Marie Curie"]


@pytest.fixture
def judge_configured() -> Any:
    """Skip-gate for the (future) Gemini judge.

    The deterministic metrics in this suite don't actually call the judge —
    this fixture exists so live tests fail-skip uniformly when the key is
    missing, and so a Gemini-backed metric can be added later without
    rewiring every test.
    """
    if not os.environ.get("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY unset — DeepEval judge cannot be configured")
    return "<judge deferred — Gemini SDK install pending>"


@pytest.fixture
def agent_under_test() -> Callable[..., Any]:
    """Return `enrich_names`, or skip naming the first missing prerequisite."""
    if not os.environ.get("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY unset")
    if not os.environ.get("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY unset — agent cannot reach Groq")
    from person_finder.agent import enrich_names
    return enrich_names

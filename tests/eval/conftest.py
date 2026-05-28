"""Fixtures for the eval tier.

Tests skip cleanly when `GROQ_API_KEY` is absent so empty-key dev paths stay green.
"""

from __future__ import annotations

import os
from typing import Any, Callable

import pytest

# Roster for the live-agent regression guard. All five are iconic enough that
# any working model + working prompt MUST identify them; if `NoNullInfo`
# fails on this roster, the prompt or the model wiring is broken. Keep the
# list iconic — a flaky entry would mask real regressions.
PUBLIC_FIGURES: list[str] = [
    "Albert Einstein",
    "Marie Curie",
    "Isaac Newton",
    "Charles Darwin",
    "Ada Lovelace",
]


@pytest.fixture
def agent_under_test() -> Callable[..., Any]:
    """Return `enrich_names`, or skip if `GROQ_API_KEY` is missing."""
    if not os.environ.get("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY unset — agent cannot reach Groq")
    from person_finder.agent import enrich_names
    return enrich_names

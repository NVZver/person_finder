"""Fixtures for the eval tier.

Tests skip cleanly when `GROQ_API_KEY` is absent so empty-key dev paths stay green.

The live pipeline is expensive (per person: an identify call plus a tool-calling
agent run) and rate-limited on the free tier, so it runs **once** per session
via `live_payload` and both the structural and correctness evals consume that
single result.
"""

from __future__ import annotations

import os
from typing import Any, Callable

import pytest

# Roster for the live-agent regression guard. All three are iconic enough that
# any working model + working prompt MUST identify them; if `NoNullInfo`
# fails on this roster, the prompt or the model wiring is broken. Kept small
# (and iconic — a flaky entry would mask real regressions) because each name
# now also drives a tool-calling agent run, and the free tier is rate-limited.
PUBLIC_FIGURES: list[str] = [
    "Albert Einstein",
    "Marie Curie",
    "Isaac Newton",
]

# Precision roster: plausible randomuser-style names that are NOT notable
# public figures. The pipeline MUST return the null triple for every one of
# them — a populated `info` here means the identify step hallucinated a
# biography for someone who does not exist. This is the precision counterpart
# to `PUBLIC_FIGURES` (which guards recall). Keep these mundane and clearly
# non-famous; a name that happens to match a real public figure would make the
# guard flaky.
FICTIONAL_NAMES: list[str] = [
    "Gerda Vonderlippe",
    "Mathis Tessnaud",
    "Eline Brinkerhoff",
    "Lasse Ravnsborg",
]


def _require_key() -> str:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        pytest.skip("GROQ_API_KEY unset — agent cannot reach Groq")
    return key


@pytest.fixture
def agent_under_test() -> Callable[..., Any]:
    """Return `enrich_names`, or skip if `GROQ_API_KEY` is missing."""
    _require_key()
    from person_finder.agent import enrich_names
    return enrich_names


@pytest.fixture(scope="session")
def live_payload() -> dict[str, Any]:
    """Run the full live pipeline over `PUBLIC_FIGURES` once per session."""
    if not os.environ.get("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY unset — agent cannot reach Groq")
    from person_finder.agent import enrich_names
    return enrich_names(PUBLIC_FIGURES)


@pytest.fixture(scope="session")
def live_fictional_payload() -> dict[str, Any]:
    """Run the live *identify* step over `FICTIONAL_NAMES` once per session.

    The precision guard is about whether the identify step hallucinates a
    biography, so we run it identify-only (`with_best_work=False`): no 70B
    agent, no judge — just the cheap 8B identify calls. Keeps the guard fast
    and isolates the failure surface to the step it actually tests.
    """
    if not os.environ.get("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY unset — agent cannot reach Groq")
    from person_finder.agent import enrich_names
    return enrich_names(FICTIONAL_NAMES, with_best_work=False)


@pytest.fixture(scope="session")
def judge() -> Any:
    """A Groq-backed DeepEval judge model, or skip if `GROQ_API_KEY` is missing."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        pytest.skip("GROQ_API_KEY unset — judge cannot reach Groq")
    from .judge import GroqJudge
    return GroqJudge(api_key=key)

"""Unit tests for the single person-lookup agent — no live LLM.

The real tool-calling loop runs live in the eval tier. Here we drive
`lookup_person_info` / `lookup_people` with a fake compiled-graph object so the
structured-output extraction, the verify→repair retry, and the safe-coerce
fallback are pinned deterministically.
"""

from __future__ import annotations

from typing import Any

from person_finder import person_lookup_agent as pla
from person_finder.person_lookup_agent import PersonResult


class _FakeAgent:
    """Mimics a compiled `create_agent` graph with `response_format`.

    `.invoke` records each payload and returns the next queued reply. A
    `PersonResult` is wrapped as ``{"structured_response": ...}``; a `None`
    models the real failure mode where the agent ends without a structured
    turn, so the result dict has **no** ``structured_response`` key at all.
    """

    def __init__(self, results: list[PersonResult | None]) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        nxt = self.results.pop(0)
        if nxt is None:
            return {"messages": []}
        return {"structured_response": nxt}


def test_identified_from_wiki_passes_through() -> None:
    agent = _FakeAgent([PersonResult(info="A physicist.", source="wiki", best_work="Relativity.")])

    out = pla.lookup_person_info("Albert Einstein", agent=agent)

    assert out == PersonResult(info="A physicist.", source="wiki", best_work="Relativity.")
    assert len(agent.calls) == 1  # no repair needed
    # The person's name reached the agent prompt.
    assert "Albert Einstein" in str(agent.calls[0]["messages"])


def test_identified_from_memory_keeps_llm_source() -> None:
    agent = _FakeAgent([PersonResult(info="A leader.", source="llm", best_work=None)])

    out = pla.lookup_person_info("Some Statesman", agent=agent)

    assert out.source == "llm"
    assert out.best_work is None


def test_unknown_person_collapses_to_null_triple_without_repair() -> None:
    # Model signalled "don't know" via the UNKNOWN sentinel, cleanly nulled.
    agent = _FakeAgent([PersonResult(info="UNKNOWN", source=None, best_work=None)])

    out = pla.lookup_person_info("Random Generated", agent=agent)

    assert out == PersonResult(info=None, source=None, best_work=None)
    assert len(agent.calls) == 1  # interpreted, not repaired


def test_contradiction_triggers_one_repair_then_succeeds() -> None:
    # First reply: identified but no source (genuine contradiction). Repair fixes it.
    agent = _FakeAgent(
        [
            PersonResult(info="A chemist.", source=None, best_work="X"),
            PersonResult(info="A chemist.", source="wiki", best_work="X"),
        ]
    )

    out = pla.lookup_person_info("Marie Curie", agent=agent)

    assert out == PersonResult(info="A chemist.", source="wiki", best_work="X")
    assert len(agent.calls) == 2  # one repair round-trip
    # The repair turn told the agent what was wrong.
    assert "source" in str(agent.calls[1]["messages"]).lower()


def test_repair_fails_then_coerces_to_contract_safe() -> None:
    # Both replies keep info without a valid source; last-resort coercion must
    # still produce a contract-valid pair (info present => source set).
    agent = _FakeAgent(
        [
            PersonResult(info="A poet.", source=None, best_work=None),
            PersonResult(info="A poet.", source=None, best_work=None),
        ]
    )

    out = pla.lookup_person_info("Edge Case", agent=agent)

    assert out.info == "A poet."
    assert out.source == "llm"  # defaulted: identification kept, provenance lower-trust
    assert len(agent.calls) == 2


def test_orphan_best_work_is_dropped() -> None:
    # best_work on an unidentified person violates "best_work requires identification".
    agent = _FakeAgent(
        [
            PersonResult(info=None, source=None, best_work="orphan"),
            PersonResult(info=None, source=None, best_work=None),
        ]
    )

    out = pla.lookup_person_info("Nobody", agent=agent)

    assert out == PersonResult(info=None, source=None, best_work=None)


def test_missing_structured_response_retries_then_nulls() -> None:
    # Agent never produces a structured turn (e.g. duplicate structured calls).
    # Must not raise KeyError; after one retry, fall back to the null triple.
    agent = _FakeAgent([None, None])

    out = pla.lookup_person_info("Whoever", agent=agent)

    assert out == PersonResult(info=None, source=None, best_work=None)
    assert len(agent.calls) == 2  # one repair round-trip


def test_missing_structured_response_recovers_on_retry() -> None:
    agent = _FakeAgent([None, PersonResult(info="A scientist.", source="wiki", best_work="X")])

    out = pla.lookup_person_info("Whoever", agent=agent)

    assert out == PersonResult(info="A scientist.", source="wiki", best_work="X")
    assert len(agent.calls) == 2


def test_lookup_people_builds_rows_and_reuses_one_agent() -> None:
    agent = _FakeAgent(
        [
            PersonResult(info="A physicist.", source="wiki", best_work="Relativity."),
            PersonResult(info=None, source=None, best_work=None),
        ]
    )

    out = pla.lookup_people(["Albert Einstein", "Random Person"], agent=agent)

    assert out == {
        "data": [
            {"person": "Albert Einstein", "info": "A physicist.", "source": "wiki", "best_work": "Relativity."},
            {"person": "Random Person", "info": None, "source": None, "best_work": None},
        ]
    }


def test_lookup_people_without_key_raises() -> None:
    """No injected agent + no GROQ_API_KEY (autouse fixture deletes it) → build fails."""
    import pytest

    with pytest.raises(RuntimeError, match="GROQ_API_KEY is required"):
        pla.lookup_people(["Ada Lovelace"])

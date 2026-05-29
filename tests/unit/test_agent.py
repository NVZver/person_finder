"""Unit tests for the enrich pipeline — all LLM/Wikipedia/agent calls mocked."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import wikipedia
from langchain_core.messages import AIMessage

from person_finder import agent as agent_module


class _StubLLM:
    """Records each `invoke` payload and returns canned `AIMessage` replies."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls: list[str] = []

    def invoke(self, messages: list[Any]) -> AIMessage:
        # The identify step always sends a single HumanMessage.
        self.calls.append(messages[0].content)
        return AIMessage(content=self.replies.pop(0))


class _StubAgent:
    """Fake best-work agent: records prompts, returns canned final messages."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls: list[str] = []

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload["messages"][-1][1])
        return {"messages": [AIMessage(content=self.replies.pop(0))]}


def _patch_wiki(
    monkeypatch: pytest.MonkeyPatch,
    *,
    by_name: dict[str, str | type[BaseException] | None],
) -> list[str]:
    """Patch the shared `fetch_wiki_summary` to return / raise per name.

    Values: a string is returned as the summary; an exception class is raised
    (surfacing as a miss); `None` is a miss. Records queries for assertion.
    """
    queries: list[str] = []

    def _fake_summary(name: str, *, sentences: int, char_cap: int) -> str | None:
        queries.append(name)
        outcome = by_name[name]
        if isinstance(outcome, type) and issubclass(outcome, BaseException):
            # Mirror the real helper, which swallows wiki exceptions → None.
            return None
        if outcome is None:
            return None
        return outcome

    monkeypatch.setattr(agent_module, "fetch_wiki_summary", _fake_summary)
    return queries


def test_wiki_hit_routes_to_summary_with_wiki_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_wiki(monkeypatch, by_name={"Ada Lovelace": "Ada Lovelace was an English mathematician..."})
    stub = _StubLLM(["English mathematician, daughter of Lord Byron, pioneer of computing."])
    agent = _StubAgent(["Her notes on the Analytical Engine — the first published algorithm."])

    result = agent_module.enrich_names(["Ada Lovelace"], model=stub, best_work_agent=agent)

    assert result == {
        "data": [
            {
                "person": "Ada Lovelace",
                "info": "English mathematician, daughter of Lord Byron, pioneer of computing.",
                "source": "wiki",
                "best_work": "Her notes on the Analytical Engine — the first published algorithm.",
            }
        ]
    }
    # Identify made one call (summarize, not identify-from-memory).
    assert len(stub.calls) == 1
    assert "Ada Lovelace was an English mathematician" in stub.calls[0]
    # The best-work agent was consulted once for the identified person.
    assert len(agent.calls) == 1
    assert "Ada Lovelace" in agent.calls[0]


def test_wiki_miss_then_llm_identifies_routes_to_llm_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_wiki(monkeypatch, by_name={"Adam Smith": None})
    stub = _StubLLM(["Scottish economist (1723-1790), best known for The Wealth of Nations."])
    agent = _StubAgent(["The Wealth of Nations (1776), founding modern economics."])

    result = agent_module.enrich_names(["Adam Smith"], model=stub, best_work_agent=agent)

    assert result == {
        "data": [
            {
                "person": "Adam Smith",
                "info": "Scottish economist (1723-1790), best known for The Wealth of Nations.",
                "source": "llm",
                "best_work": "The Wealth of Nations (1776), founding modern economics.",
            }
        ]
    }
    assert len(stub.calls) == 1
    assert "Adam Smith" in stub.calls[0]


def test_wiki_miss_and_llm_unknown_emits_null_pair_and_skips_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_wiki(monkeypatch, by_name={"Random Fictional": None})
    stub = _StubLLM([agent_module.UNKNOWN_SENTINEL])
    agent = _StubAgent([])  # must never be called

    result = agent_module.enrich_names(["Random Fictional"], model=stub, best_work_agent=agent)

    assert result == {
        "data": [
            {"person": "Random Fictional", "info": None, "source": None, "best_work": None}
        ]
    }
    # Unidentified person → no point researching best work.
    assert agent.calls == []


def test_wiki_hit_but_summary_unknown_emits_null_pair_no_fallthrough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A wiki article that isn't about an identifiable person → summarize emits
    UNKNOWN → null pair. The memory path must NOT be consulted (no second LLM
    call), and the best-work agent must not run."""
    _patch_wiki(monkeypatch, by_name={"Andrea Glavas": "Glavas is a surname. It may refer to..."})
    stub = _StubLLM([agent_module.UNKNOWN_SENTINEL])  # only the summarize call
    agent = _StubAgent([])  # must never be called

    result = agent_module.enrich_names(["Andrea Glavas"], model=stub, best_work_agent=agent)

    assert result == {
        "data": [
            {"person": "Andrea Glavas", "info": None, "source": None, "best_work": None}
        ]
    }
    # Exactly one LLM call (summarize) — no fall-through to identify-from-memory.
    assert len(stub.calls) == 1
    assert agent.calls == []


def test_identified_person_with_unknown_best_work_gets_null_best_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Identified, but the agent can't name a notable work → best_work=None,
    while info/source stay populated."""
    _patch_wiki(monkeypatch, by_name={"Jane Doe": "Jane Doe is a software engineer."})
    stub = _StubLLM(["Software engineer."])
    agent = _StubAgent(["UNKNOWN"])

    result = agent_module.enrich_names(["Jane Doe"], model=stub, best_work_agent=agent)

    row = result["data"][0]
    assert row["info"] == "Software engineer."
    assert row["source"] == "wiki"
    assert row["best_work"] is None
    assert len(agent.calls) == 1


def test_with_best_work_false_skips_agent_entirely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_wiki(monkeypatch, by_name={"Ada Lovelace": "Ada Lovelace article..."})
    stub = _StubLLM(["English mathematician."])
    agent = _StubAgent([])  # must never be called

    result = agent_module.enrich_names(
        ["Ada Lovelace"], model=stub, best_work_agent=agent, with_best_work=False
    )

    assert result["data"][0]["best_work"] is None
    assert agent.calls == []


def test_unknown_sentinel_matching_is_permissive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All of `UNKNOWN`, `unknown.`, ` Unknown `, and "" route to the null pair."""
    names = ["A", "B", "C", "D"]
    _patch_wiki(monkeypatch, by_name={n: None for n in names})
    stub = _StubLLM(["UNKNOWN", "unknown.", " Unknown ", ""])
    agent = _StubAgent([])

    result = agent_module.enrich_names(names, model=stub, best_work_agent=agent)

    for row in result["data"]:
        assert row["info"] is None, f"row {row} should have null info"
        assert row["source"] is None, f"row {row} should have null source"
        assert row["best_work"] is None
    assert agent.calls == []


def test_wikipedia_disambiguation_is_treated_as_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_wiki(
        monkeypatch,
        by_name={"John Smith": wikipedia.exceptions.DisambiguationError},
    )
    stub = _StubLLM([agent_module.UNKNOWN_SENTINEL])
    agent = _StubAgent([])

    result = agent_module.enrich_names(["John Smith"], model=stub, best_work_agent=agent)

    # Disambiguation → wiki miss → LLM fallback (UNKNOWN here) → null pair.
    assert result["data"][0]["source"] is None
    assert len(stub.calls) == 1


def test_wikipedia_page_error_is_treated_as_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_wiki(
        monkeypatch,
        by_name={"Nonexistent Page": wikipedia.exceptions.PageError},
    )
    stub = _StubLLM(["A real person summary."])
    agent = _StubAgent(["A notable achievement."])

    result = agent_module.enrich_names(["Nonexistent Page"], model=stub, best_work_agent=agent)

    assert result["data"][0]["source"] == "llm"
    assert result["data"][0]["info"] == "A real person summary."
    assert result["data"][0]["best_work"] == "A notable achievement."


def test_mixed_batch_attributes_source_and_best_work_per_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Three names, three different identify paths; agent runs only for the two
    identified people, in order."""
    _patch_wiki(
        monkeypatch,
        by_name={
            "Ada Lovelace": "Ada Lovelace article text...",
            "Adam Smith": None,
            "Random Fictional": None,
        },
    )
    stub = _StubLLM([
        "Ada summary from wiki.",   # summarize(Ada)
        "Adam summary from memory.",  # identify(Adam)
        "UNKNOWN",                  # identify(Random)
    ])
    agent = _StubAgent([
        "Ada's best work.",   # research(Ada)
        "Adam's best work.",  # research(Adam)
    ])

    result = agent_module.enrich_names(
        ["Ada Lovelace", "Adam Smith", "Random Fictional"], model=stub, best_work_agent=agent
    )

    assert result == {
        "data": [
            {"person": "Ada Lovelace", "info": "Ada summary from wiki.", "source": "wiki", "best_work": "Ada's best work."},
            {"person": "Adam Smith", "info": "Adam summary from memory.", "source": "llm", "best_work": "Adam's best work."},
            {"person": "Random Fictional", "info": None, "source": None, "best_work": None},
        ]
    }
    # Agent ran twice — once per identified person, in order, skipping the
    # unidentified row. `calls` holds the full prompt string per invocation.
    assert len(agent.calls) == 2
    assert "Ada Lovelace" in agent.calls[0]
    assert "Adam Smith" in agent.calls[1]


def test_enrich_names_without_groq_key_raises() -> None:
    """Autouse fixture already deleted `GROQ_API_KEY`."""
    with pytest.raises(RuntimeError, match="GROQ_API_KEY is required"):
        agent_module.enrich_names(["Ada Lovelace"])


def test_import_has_no_side_effects(tmp_path: Path) -> None:
    """`import person_finder.agent` must not read env, hit disk, or raise."""
    child_env = {"PATH": os.environ["PATH"], "HOME": os.environ["HOME"]}

    result = subprocess.run(
        ["uv", "run", "python", "-c", "import person_finder.agent"],
        cwd=tmp_path,
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"import raised:\n{result.stderr}"
    assert "Traceback" not in result.stderr

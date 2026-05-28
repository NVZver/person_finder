"""Unit tests for the per-name agent loop — all LLM/Wikipedia calls mocked."""

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
        # The agent always sends a single HumanMessage.
        self.calls.append(messages[0].content)
        return AIMessage(content=self.replies.pop(0))


def _patch_wiki(
    monkeypatch: pytest.MonkeyPatch,
    *,
    by_name: dict[str, str | type[BaseException] | None],
) -> list[str]:
    """Patch `wikipedia.summary` to return / raise per name.

    Values: a string is returned as the summary; an exception class is
    raised; `None` returns `""` (treated as a miss). Records the queries
    in the returned list for assertion.
    """
    queries: list[str] = []

    def _fake_summary(name: str, sentences: int = 3, auto_suggest: bool = True) -> str:
        queries.append(name)
        outcome = by_name[name]
        if outcome is None:
            return ""
        if isinstance(outcome, type) and issubclass(outcome, BaseException):
            raise outcome(name, [])  # both PageError and DisambiguationError accept this
        return outcome

    monkeypatch.setattr(agent_module.wikipedia, "summary", _fake_summary)
    return queries


def test_wiki_hit_routes_to_summary_with_wiki_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_wiki(monkeypatch, by_name={"Ada Lovelace": "Ada Lovelace was an English mathematician..."})
    stub = _StubLLM(["English mathematician, daughter of Lord Byron, pioneer of computing."])

    result = agent_module.enrich_names(["Ada Lovelace"], model=stub)

    assert result == {
        "data": [
            {
                "person": "Ada Lovelace",
                "info": "English mathematician, daughter of Lord Byron, pioneer of computing.",
                "source": "wiki",
            }
        ]
    }
    # The LLM was called once (summarize), not twice.
    assert len(stub.calls) == 1
    assert "Ada Lovelace was an English mathematician" in stub.calls[0]


def test_wiki_miss_then_llm_identifies_routes_to_llm_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_wiki(monkeypatch, by_name={"Adam Smith": None})
    stub = _StubLLM(["Scottish economist (1723-1790), best known for The Wealth of Nations."])

    result = agent_module.enrich_names(["Adam Smith"], model=stub)

    assert result == {
        "data": [
            {
                "person": "Adam Smith",
                "info": "Scottish economist (1723-1790), best known for The Wealth of Nations.",
                "source": "llm",
            }
        ]
    }
    assert len(stub.calls) == 1
    assert "Adam Smith" in stub.calls[0]


def test_wiki_miss_and_llm_unknown_emits_null_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_wiki(monkeypatch, by_name={"Random Fictional": None})
    stub = _StubLLM([agent_module.UNKNOWN_SENTINEL])

    result = agent_module.enrich_names(["Random Fictional"], model=stub)

    assert result == {
        "data": [
            {"person": "Random Fictional", "info": None, "source": None}
        ]
    }


def test_unknown_sentinel_matching_is_permissive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The model is at temp=0 but small models still emit punctuation /
    case variation. All of `UNKNOWN`, `unknown.`, ` Unknown `, and the
    empty string must route to the null pair."""
    names = ["A", "B", "C", "D"]
    _patch_wiki(monkeypatch, by_name={n: None for n in names})
    stub = _StubLLM(["UNKNOWN", "unknown.", " Unknown ", ""])

    result = agent_module.enrich_names(names, model=stub)

    for row in result["data"]:
        assert row["info"] is None, f"row {row} should have null info"
        assert row["source"] is None, f"row {row} should have null source"


def test_wikipedia_disambiguation_is_treated_as_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_wiki(
        monkeypatch,
        by_name={"John Smith": wikipedia.exceptions.DisambiguationError},
    )
    stub = _StubLLM([agent_module.UNKNOWN_SENTINEL])

    result = agent_module.enrich_names(["John Smith"], model=stub)

    # Disambiguation → wiki miss → LLM fallback (which says UNKNOWN here) → null pair.
    assert result["data"][0]["source"] is None
    # The LLM was consulted (one call: the identify step).
    assert len(stub.calls) == 1


def test_wikipedia_page_error_is_treated_as_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_wiki(
        monkeypatch,
        by_name={"Nonexistent Page": wikipedia.exceptions.PageError},
    )
    stub = _StubLLM(["A real person summary."])

    result = agent_module.enrich_names(["Nonexistent Page"], model=stub)

    assert result["data"][0]["source"] == "llm"
    assert result["data"][0]["info"] == "A real person summary."


def test_mixed_batch_attributes_source_per_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Three names, three different paths in one call."""
    _patch_wiki(
        monkeypatch,
        by_name={
            "Ada Lovelace": "Ada Lovelace article text...",
            "Adam Smith": None,
            "Random Fictional": None,
        },
    )
    # Call order: summarize(Ada), identify(Adam), identify(Random).
    stub = _StubLLM([
        "Ada summary from wiki.",
        "Adam summary from memory.",
        "UNKNOWN",
    ])

    result = agent_module.enrich_names(
        ["Ada Lovelace", "Adam Smith", "Random Fictional"], model=stub
    )

    assert result == {
        "data": [
            {"person": "Ada Lovelace", "info": "Ada summary from wiki.", "source": "wiki"},
            {"person": "Adam Smith", "info": "Adam summary from memory.", "source": "llm"},
            {"person": "Random Fictional", "info": None, "source": None},
        ]
    }


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

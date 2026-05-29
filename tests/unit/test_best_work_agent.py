"""Unit tests for the best-work agent's extraction logic — no live LLM.

The real tool-calling loop is exercised live in the eval tier. Here we drive
`research_best_work` with a fake compiled-graph object so the answer-extraction
and UNKNOWN handling are pinned deterministically.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from person_finder import best_work_agent


class _FakeGraph:
    """Mimics a compiled `create_agent` graph: `.invoke` → {"messages": [...]}."""

    def __init__(self, final_text: str, *, with_tool: bool = True) -> None:
        self.final_text = final_text
        self.with_tool = with_tool
        self.last_payload: dict[str, Any] | None = None

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.last_payload = payload
        messages: list[Any] = [HumanMessage(content="q")]
        if self.with_tool:
            messages.append(ToolMessage(content="article", tool_call_id="t1"))
        messages.append(AIMessage(content=self.final_text))
        return {"messages": messages}


def test_research_best_work_returns_final_answer() -> None:
    graph = _FakeGraph("Theory of relativity, reshaping modern physics.")

    out = best_work_agent.research_best_work("Albert Einstein", agent=graph)

    assert out == "Theory of relativity, reshaping modern physics."
    # The person's name reached the agent prompt.
    assert "Albert Einstein" in graph.last_payload["messages"][-1][1]


def test_research_best_work_maps_unknown_to_none() -> None:
    graph = _FakeGraph("UNKNOWN", with_tool=True)

    assert best_work_agent.research_best_work("Nobody Real", agent=graph) is None


def test_research_best_work_unknown_is_permissive() -> None:
    graph = _FakeGraph("  unknown.  ")

    assert best_work_agent.research_best_work("Nobody Real", agent=graph) is None


def test_tool_was_called_detects_tool_message() -> None:
    with_tool = [
        HumanMessage(content="q"),
        ToolMessage(content="article", tool_call_id="t1"),
        AIMessage(content="answer"),
    ]
    without_tool = [HumanMessage(content="q"), AIMessage(content="answer")]

    assert best_work_agent.tool_was_called(with_tool) is True
    assert best_work_agent.tool_was_called(without_tool) is False

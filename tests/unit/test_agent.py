"""Unit tests for the agent module — all LLM/agent calls are mocked."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from person_finder import agent as agent_module


class _StubAgent:
    """Records each invoke + returns canned message contents in order."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.invocations: list[list[Any]] = []

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.invocations.append(payload["messages"])
        return {"messages": payload["messages"] + [AIMessage(content=self.responses.pop(0))]}


def _patch_create_agent(monkeypatch: pytest.MonkeyPatch, stub: _StubAgent) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def _factory(**kwargs: Any) -> _StubAgent:
        captured.update(kwargs)
        return stub

    monkeypatch.setattr(agent_module, "create_agent", _factory)
    return captured


def test_enrich_names_returns_parsed_dict_on_first_try(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canned = '{"data":[{"person":"Ada Lovelace","info":"Mathematician"}]}'
    stub = _StubAgent([canned])
    captured = _patch_create_agent(monkeypatch, stub)

    result = agent_module.enrich_names(["Ada Lovelace"], model="sentinel")

    assert result == {"data": [{"person": "Ada Lovelace", "info": "Mathematician"}]}
    assert len(stub.invocations) == 1
    assert captured["model"] == "sentinel"
    assert "Ada Lovelace" in stub.invocations[0][0]["content"]


def test_enrich_names_retries_with_error_message_on_bad_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canned_good = '{"data":[{"person":"Ada","info":"<Not found>"}]}'
    stub = _StubAgent(["not json", canned_good])
    _patch_create_agent(monkeypatch, stub)

    result = agent_module.enrich_names(["Ada"], model="sentinel")

    assert result == {"data": [{"person": "Ada", "info": "<Not found>"}]}
    assert len(stub.invocations) == 2
    repair_msg = stub.invocations[1][-1]
    assert repair_msg["role"] == "user"


def test_enrich_names_raises_after_max_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _StubAgent(["bad"] * agent_module.MAX_ATTEMPTS)
    _patch_create_agent(monkeypatch, stub)

    with pytest.raises(json.JSONDecodeError):
        agent_module.enrich_names(["Ada"], model="sentinel")

    assert len(stub.invocations) == agent_module.MAX_ATTEMPTS


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

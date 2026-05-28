"""Unit tests for the agent module — all LLM/agent calls are mocked."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from person_finder import agent as agent_module


def test_enrich_names_invokes_agent_with_names_and_returns_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canned_json = '{"data":[{"person":"Ada Lovelace","info":"Mathematician"}]}'
    captured: dict[str, Any] = {}

    class _FakeAgent:
        def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
            captured["payload"] = payload
            return {"messages": [AIMessage(content=canned_json)]}

    def _spy_create_agent(**kwargs: Any) -> _FakeAgent:
        captured["create_agent_kwargs"] = kwargs
        return _FakeAgent()

    monkeypatch.setattr(agent_module, "create_agent", _spy_create_agent)

    result = agent_module.enrich_names(["Ada Lovelace"], model="sentinel-model")

    assert result == canned_json
    assert captured["create_agent_kwargs"]["model"] == "sentinel-model"
    assert captured["create_agent_kwargs"]["tools"] == []
    assert "JSON object" in captured["create_agent_kwargs"]["system_prompt"]
    assert "Ada Lovelace" in captured["payload"]["messages"][0]["content"]


def test_enrich_names_without_groq_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test")
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        agent_module.enrich_names(["Ada Lovelace"])


def test_repair_invokes_model_and_returns_content() -> None:
    canned = '{"data":[{"person":"Ada","info":"<Not found>"}]}'

    class _FakeMsg:
        def __init__(self, content: str) -> None:
            self.content = content

    class _FakeModel:
        def __init__(self) -> None:
            self.calls: list[Any] = []

        def invoke(self, messages: Any) -> Any:
            self.calls.append(messages)
            return _FakeMsg(canned)

    fake = _FakeModel()
    out = agent_module.repair("broken raw", "JSON parse error", model=fake)

    assert out == canned
    flat = str(fake.calls[0])
    assert "broken raw" in flat
    assert "JSON parse error" in flat


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

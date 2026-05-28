"""Unit tests for the LangChain agent module.

All external calls (Groq HTTP, the agent runtime) are mocked per
[testing.md](../../specs/standards/testing.md). These tests verify the wiring
contract only — content quality and output validation are out of scope here.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from person_finder import agent as agent_module


def test_find_person_stub_returns_not_found() -> None:
    # The tool is wrapped by @tool, so call it through the runnable interface.
    assert agent_module.findPerson.invoke({"name": "Ada Lovelace"}) == "<Not found>"


def test_enrich_names_returns_final_message_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canned_json = '{"data":[{"person":"Ada Lovelace","info":"<Not found>"}]}'

    class _FakeAgent:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
            self.calls.append(payload)
            return {"messages": [AIMessage(content=canned_json)]}

    fake = _FakeAgent()
    monkeypatch.setattr(agent_module, "create_agent", lambda **_: fake)

    result = agent_module.enrich_names(["Ada Lovelace"], model="sentinel")

    assert result == canned_json
    assert fake.calls, "agent.invoke should have been called exactly once"
    user_msg = fake.calls[0]["messages"][0]["content"]
    assert "Ada Lovelace" in user_msg


def test_build_agent_passes_injected_model_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _spy(**kwargs: Any) -> str:
        captured.update(kwargs)
        return "fake-agent"

    monkeypatch.setattr(agent_module, "create_agent", _spy)

    sentinel = object()
    out = agent_module.build_agent(model=sentinel)

    assert out == "fake-agent"
    assert captured["model"] is sentinel
    # Tool registration is part of the wiring contract — assert by identity.
    assert agent_module.findPerson in captured["tools"]
    assert "JSON object" in captured["system_prompt"]


def test_build_agent_default_model_requires_groq_api_key() -> None:
    # conftest fixture strips GROQ_API_KEY; build_agent must raise at construction.
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        agent_module.build_agent()


def test_import_has_no_side_effects(tmp_path: Path) -> None:
    """AC5 / NF2: `import person_finder.agent` must not read env, hit disk, or raise.

    Run in a fresh subprocess because by the time this test executes, the
    module is already cached in ``sys.modules`` from earlier tests — only a
    fresh interpreter honestly exercises the first-import code path. Strip
    GROQ_API_KEY/GOOGLE_API_KEY from the child env and ``chdir`` to an empty
    ``tmp_path`` so there's no ``.env`` to discover.
    """
    # Minimal env: PATH for binary resolution, HOME for uv's cache dir.
    # GROQ_API_KEY and GOOGLE_API_KEY are intentionally omitted.
    child_env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ["HOME"],
    }

    result = subprocess.run(
        ["uv", "run", "python", "-c", "import person_finder.agent"],
        cwd=tmp_path,
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        f"import raised in fresh interpreter.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    # `uv run` may emit informational lines to stderr (e.g. sync messages);
    # what AC5 forbids is an exception, so assert no traceback bubbled up.
    assert "Traceback" not in result.stderr, (
        f"import produced a traceback in fresh interpreter.\nstderr:\n{result.stderr}"
    )

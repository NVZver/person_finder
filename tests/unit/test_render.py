"""Unit tests for the render orchestrator — all collaborators mocked."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest


def test_success_prints_json_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from person_finder import render

    payload = {"data": [{"person": "Ada Lovelace", "info": None, "source": None}]}
    monkeypatch.setattr(render, "fetch_user_names", lambda: ["Ada Lovelace"])
    monkeypatch.setattr(render, "enrich_names", lambda names: payload)

    with pytest.raises(SystemExit) as exc_info:
        render.main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == payload
    assert captured.err == ""


def test_json_decode_error_prints_stderr_and_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from person_finder import render

    monkeypatch.setattr(render, "fetch_user_names", lambda: ["Ada Lovelace"])

    def _boom(names: list[str]) -> dict[str, Any]:
        raise json.JSONDecodeError("Expecting value", "not json", 0)

    monkeypatch.setattr(render, "enrich_names", _boom)

    with pytest.raises(SystemExit) as exc_info:
        render.main()

    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Could not respond" in captured.err
    assert "Traceback" not in captured.err


def test_api_status_error_prints_api_message_no_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Rate-limit (429), context-length (400), and other 4xx/5xx errors must
    surface Groq's actionable message — not a stack trace, and not the
    generic 'try again later' that erases the wait-time hint."""
    import httpx
    from groq import RateLimitError

    from person_finder import render

    monkeypatch.setattr(render, "fetch_user_names", lambda: ["Ada Lovelace"])

    clean_message = (
        "Rate limit reached for model `llama-3.1-8b-instant`. "
        "Please try again in 2.1s."
    )
    # Real Groq error body shape: the SDK formats `exc.message` as
    # "Error code: 429 - <body>" but the clean string we want for the user
    # lives at `body["error"]["message"]`.
    body = {"error": {"message": clean_message, "type": "tokens"}}
    raw_message = f"Error code: 429 - {body}"

    def _boom(names: list[str]) -> dict[str, Any]:
        request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        response = httpx.Response(429, request=request)
        raise RateLimitError(raw_message, response=response, body=body)

    monkeypatch.setattr(render, "enrich_names", _boom)

    with pytest.raises(SystemExit) as exc_info:
        render.main()

    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert captured.out == ""
    # Clean message surfaced; the ugly "Error code: 429 - {...}" wrapper
    # is stripped.
    assert clean_message in captured.err
    assert "Error code: 429" not in captured.err
    assert "Traceback" not in captured.err


def test_user_fetch_error_prints_same_user_message(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from person_finder import render
    from person_finder.users import UserFetchError

    def _boom() -> list[str]:
        raise UserFetchError("HTTP 503")

    monkeypatch.setattr(render, "fetch_user_names", _boom)

    with pytest.raises(SystemExit) as exc_info:
        render.main()

    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert "Could not respond" in captured.err
    assert "503" not in captured.err
    assert "Traceback" not in captured.err


def test_import_has_no_side_effects(tmp_path: Path) -> None:
    """`import person_finder.render` must not read env, hit disk, or raise."""
    child_env = {"PATH": os.environ["PATH"], "HOME": os.environ["HOME"]}

    result = subprocess.run(
        ["uv", "run", "python", "-c", "import person_finder.render"],
        cwd=tmp_path,
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"import raised:\n{result.stderr}"
    assert "Traceback" not in result.stderr

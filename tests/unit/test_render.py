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

    canned_raw = '{"data":[{"person":"Ada Lovelace","info":"<Not found>"}]}'
    monkeypatch.setattr(render, "fetch_user_names", lambda: ["Ada Lovelace"])
    monkeypatch.setattr(render, "enrich_names", lambda names, *, model=None: canned_raw)
    monkeypatch.setattr(render, "validate_output", lambda raw, repair_fn=None: json.loads(raw))

    with pytest.raises(SystemExit) as exc_info:
        render.main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == json.loads(canned_raw)
    assert captured.err == ""


def test_validation_error_prints_stderr_and_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from person_finder import render
    from person_finder.validation import Error

    monkeypatch.setattr(render, "fetch_user_names", lambda: ["Ada Lovelace"])
    monkeypatch.setattr(render, "enrich_names", lambda names, *, model=None: "not json")

    def _boom(raw: str, repair_fn: Any = None) -> dict[str, Any]:
        raise Error("Could not respond")

    monkeypatch.setattr(render, "validate_output", _boom)

    with pytest.raises(SystemExit) as exc_info:
        render.main()

    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Could not respond" in captured.err
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


def test_passes_callable_repair_fn_to_validate_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from person_finder import render

    captured: dict[str, Any] = {}
    monkeypatch.setattr(render, "fetch_user_names", lambda: [])
    monkeypatch.setattr(render, "enrich_names", lambda names, *, model=None: '{"data":[]}')

    def spy_validate(raw: str, repair_fn: Any = None) -> dict[str, Any]:
        captured["repair_fn"] = repair_fn
        return {"data": []}

    monkeypatch.setattr(render, "validate_output", spy_validate)

    with pytest.raises(SystemExit):
        render.main()

    assert callable(captured["repair_fn"])


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

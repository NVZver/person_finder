"""Unit tests for the render orchestrator (Epic 5).

All collaborators (`users.fetch_user_names`, `agent.enrich_names`,
`agent.repair`, `validation.validate_output`) are mocked per
[testing.md](../../specs/standards/testing.md). No network, no LLM, no
randomuser.me. These tests verify only the wiring contract: the orchestrator
calls the right functions in the right order, surfaces the two named errors
with a user-facing stderr message + non-zero exit, and prints validated JSON
on the success path.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Happy path — full wiring with all collaborators mocked
# ---------------------------------------------------------------------------


def test_main_success_prints_json_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Validated payload is JSON-printed on stdout; process exits 0."""
    from person_finder import render

    canned_raw = '{"data":[{"person":"Ada Lovelace","info":"<Not found>"}]}'
    expected_payload = {"data": [{"person": "Ada Lovelace", "info": "<Not found>"}]}

    monkeypatch.setattr(render, "fetch_user_names", lambda: ["Ada Lovelace"])
    monkeypatch.setattr(
        render, "enrich_names", lambda names, *, model=None: canned_raw
    )
    monkeypatch.setattr(
        render,
        "validate_output",
        lambda raw, repair_fn=None: json.loads(raw),
    )

    with pytest.raises(SystemExit) as exc_info:
        render.main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    # Round-trip stdout to defend against pretty-print whitespace differences.
    assert json.loads(captured.out) == expected_payload
    assert captured.err == ""


# ---------------------------------------------------------------------------
# AC2 — validation.Error path: stderr message, non-zero exit, no traceback
# ---------------------------------------------------------------------------


def test_main_handles_validation_error_with_user_message_and_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`validation.Error("Could not respond")` -> stderr msg + non-zero exit."""
    from person_finder import render
    from person_finder.validation import Error

    monkeypatch.setattr(render, "fetch_user_names", lambda: ["Ada Lovelace"])
    monkeypatch.setattr(
        render, "enrich_names", lambda names, *, model=None: "not json"
    )

    def _boom(raw: str, repair_fn: Any = None) -> dict[str, Any]:
        raise Error("Could not respond")

    monkeypatch.setattr(render, "validate_output", _boom)

    with pytest.raises(SystemExit) as exc_info:
        render.main()

    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert captured.out == "", "no payload should leak on the error path"
    # User-facing message — terse, no exception class name, no traceback.
    assert "Could not respond" in captured.err
    assert "try again" in captured.err.lower()
    assert "Traceback" not in captured.err
    # No Python class name should leak into the user-facing message.
    assert "UserFetchError" not in captured.err
    assert "_ValidationFailure" not in captured.err


# ---------------------------------------------------------------------------
# AC3 — users.UserFetchError path: same user-facing surface
# ---------------------------------------------------------------------------


def test_main_handles_user_fetch_error_with_same_user_message(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`users.UserFetchError` -> same stderr msg + non-zero exit, no traceback.

    The user shouldn't see an httpx-leaking traceback either.
    """
    from person_finder import render
    from person_finder.users import UserFetchError

    def _boom() -> list[str]:
        raise UserFetchError("Random-user endpoint returned HTTP 503")

    monkeypatch.setattr(render, "fetch_user_names", _boom)

    with pytest.raises(SystemExit) as exc_info:
        render.main()

    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Could not respond" in captured.err
    assert "try again" in captured.err.lower()
    assert "Traceback" not in captured.err
    # Don't leak the underlying httpx-flavoured message.
    assert "503" not in captured.err
    assert "httpx" not in captured.err.lower()


# ---------------------------------------------------------------------------
# AC4 — validate_output is invoked with a real callable repair_fn (NOT None)
# ---------------------------------------------------------------------------


def test_main_passes_callable_repair_fn_to_validate_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pins validation/spec.md F4: render wires a real repair callable.

    Captures the `repair_fn` kwarg passed to `validate_output` and asserts
    it is callable — i.e. not `None` (which would short-circuit the entire
    Epic 4 repair retry loop).
    """
    from person_finder import render

    captured: dict[str, Any] = {}
    canned_raw = '{"data":[]}'

    monkeypatch.setattr(render, "fetch_user_names", lambda: [])
    monkeypatch.setattr(
        render, "enrich_names", lambda names, *, model=None: canned_raw
    )

    def spy_validate(raw: str, repair_fn: Any = None) -> dict[str, Any]:
        captured["raw"] = raw
        captured["repair_fn"] = repair_fn
        return {"data": []}

    monkeypatch.setattr(render, "validate_output", spy_validate)

    with pytest.raises(SystemExit) as exc_info:
        render.main()

    assert exc_info.value.code == 0
    assert "repair_fn" in captured, "validate_output must be called"
    assert callable(captured["repair_fn"]), (
        "repair_fn argument must be a real callable, not None — "
        "Epic 4's whole point is the repair retry loop"
    )


# ---------------------------------------------------------------------------
# Edge case — empty names list still produces a valid payload print
# ---------------------------------------------------------------------------


def test_main_with_empty_names_prints_empty_data_payload(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When fetch returns [], the pipeline still completes cleanly."""
    from person_finder import render

    monkeypatch.setattr(render, "fetch_user_names", lambda: [])
    monkeypatch.setattr(
        render, "enrich_names", lambda names, *, model=None: '{"data":[]}'
    )
    monkeypatch.setattr(
        render,
        "validate_output",
        lambda raw, repair_fn=None: json.loads(raw),
    )

    with pytest.raises(SystemExit) as exc_info:
        render.main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"data": []}


# ---------------------------------------------------------------------------
# NF — side-effect-free import (mirror agent/validation pattern)
# ---------------------------------------------------------------------------


def test_import_has_no_side_effects(tmp_path: Path) -> None:
    """`import person_finder.render` MUST NOT read env, hit disk, or raise.

    Fresh subprocess because the module may already be in sys.modules from
    earlier tests. GROQ_API_KEY/GOOGLE_API_KEY intentionally omitted from
    the child env; chdir into empty tmp_path so no `.env` is discoverable.
    Mirrors the pattern in `test_agent.py:test_import_has_no_side_effects`.
    """
    child_env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ["HOME"],
    }

    result = subprocess.run(
        ["uv", "run", "python", "-c", "import person_finder.render"],
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
    assert "Traceback" not in result.stderr, (
        f"import produced a traceback in fresh interpreter.\nstderr:\n{result.stderr}"
    )

"""End-to-end test: `python -m person_finder` against real randomuser.me + Groq.

Skipped cleanly when `GROQ_API_KEY` is unset so empty-key dev paths stay green.
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest


def test_python_module_run_returns_validated_json() -> None:
    if not os.environ.get("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY unset")

    # Settings requires both keys non-blank; render itself never uses the Google
    # key, so a placeholder is fine when only Groq is set.
    child_env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ["HOME"],
        "GROQ_API_KEY": os.environ["GROQ_API_KEY"],
        "GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY", "placeholder"),
    }

    result = subprocess.run(
        ["uv", "run", "python", "-m", "person_finder"],
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )

    assert result.returncode == 0, f"CLI exited non-zero.\nstderr:\n{result.stderr}"

    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    assert isinstance(payload["data"], list)
    for item in payload["data"]:
        assert isinstance(item["person"], str)
        assert isinstance(item["info"], str)

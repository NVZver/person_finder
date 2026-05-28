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

    child_env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ["HOME"],
        "GROQ_API_KEY": os.environ["GROQ_API_KEY"],
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
        assert item["info"] is None or isinstance(item["info"], str)
        assert item["source"] in (None, "wiki", "llm")
        # Paired nullability: both null, or both populated.
        assert (item["info"] is None) == (item["source"] is None)

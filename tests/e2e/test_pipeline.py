"""End-to-end test: full pipeline via `python -m person_finder`.

No mocks. Hits randomuser.me + Groq for real. Subprocess invocation so
the test exercises the actual CLI surface: stdin/stdout/stderr, exit
code, and module-discovery path. Skipped cleanly when `GROQ_API_KEY` is
absent — empty-key dev paths stay green.

Asserts the cross-module CLI contract:
- stdout is valid JSON, top-level dict, contains `data` key
- `data` is a list of `{"person": str, "info": str}` items
- exit code 0
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest

from . import RealKeys


def test_python_module_run_returns_validated_json(real_keys: RealKeys) -> None:
    """`python -m person_finder` against real services prints a validated payload."""
    if not real_keys.groq_api_key:
        pytest.skip("GROQ_API_KEY unset — e2e cannot reach Groq")

    # Pass GROQ_API_KEY explicitly into the child env — the autouse
    # fixture set it in this test's process environment, but
    # `subprocess.run` does not inherit the monkeypatched value unless
    # we hand the child a full env dict.
    child_env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ["HOME"],
        "GROQ_API_KEY": real_keys.groq_api_key,
    }
    if real_keys.google_api_key:
        child_env["GOOGLE_API_KEY"] = real_keys.google_api_key
    else:
        # `person_finder.config.Settings` requires both keys non-blank. Use
        # a placeholder so the agent layer constructs; render does not
        # consult the Google key.
        child_env["GOOGLE_API_KEY"] = "placeholder-for-config-validation"

    result = subprocess.run(
        ["uv", "run", "python", "-m", "person_finder"],
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,  # randomuser.me + Groq round-trips; generous ceiling.
    )

    assert result.returncode == 0, (
        f"CLI exited non-zero.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    # Output must be a parseable JSON document with the cross-module shape.
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"stdout is not valid JSON: {exc}\nstdout:\n{result.stdout}")

    assert isinstance(payload, dict), "top-level payload must be a dict"
    assert "data" in payload, "payload must contain a 'data' key"
    data = payload["data"]
    assert isinstance(data, list), "payload['data'] must be a list"

    for i, item in enumerate(data):
        assert isinstance(item, dict), f"data[{i}] must be a dict, got {type(item).__name__}"
        assert isinstance(item.get("person"), str), f"data[{i}].person must be str"
        assert isinstance(item.get("info"), str), f"data[{i}].info must be str"

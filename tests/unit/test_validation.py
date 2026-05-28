"""Unit tests for the validation module.

All collaborators are mocked or substituted with plain Python callables —
`validate_output` is a pure function over a string and a callable, with no
LLM, network, or disk I/O of its own. The repair-retry budget is the
load-bearing behavior here, so most tests count `repair_fn` invocations.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Happy path — valid input
# ---------------------------------------------------------------------------


def test_valid_json_returns_parsed_dict_without_calling_repair() -> None:
    from person_finder.validation import validate_output

    raw = '{"data": [{"person": "Ada Lovelace", "info": "Mathematician"}]}'
    calls: list[tuple[str, str]] = []

    def repair_fn(broken: str, err: str) -> str:
        calls.append((broken, err))
        return broken

    out = validate_output(raw, repair_fn=repair_fn)

    assert out == {"data": [{"person": "Ada Lovelace", "info": "Mathematician"}]}
    assert calls == [], "repair_fn must not be invoked on first-shot success"


def test_empty_data_list_is_valid() -> None:
    from person_finder.validation import validate_output

    out = validate_output('{"data": []}')
    assert out == {"data": []}


# ---------------------------------------------------------------------------
# Single-repair success — repair_fn called exactly once
# ---------------------------------------------------------------------------


def test_broken_then_repaired_returns_dict_and_calls_repair_once() -> None:
    from person_finder.validation import validate_output

    broken = "not json at all"
    repaired = '{"data": [{"person": "Ada", "info": "<Not found>"}]}'
    calls: list[tuple[str, str]] = []

    def fixer(b: str, err: str) -> str:
        calls.append((b, err))
        return repaired

    out = validate_output(broken, repair_fn=fixer)

    assert out == {"data": [{"person": "Ada", "info": "<Not found>"}]}
    assert len(calls) == 1, "fixer must run exactly once when first repair succeeds"
    assert calls[0][0] == broken, "fixer's first arg must be the original broken raw"
    assert "JSON parse error" in calls[0][1], (
        "fixer's second arg must describe the failure precisely"
    )


# ---------------------------------------------------------------------------
# Repair exhaustion — exactly 3 retries, then Error("Could not respond")
# ---------------------------------------------------------------------------


def test_always_broken_repair_exhausts_after_three_calls() -> None:
    from person_finder.validation import Error, validate_output

    broken = "still not json"
    call_count = 0

    def always_broken(b: str, err: str) -> str:
        nonlocal call_count
        call_count += 1
        return "still not json either"

    with pytest.raises(Error) as excinfo:
        validate_output(broken, repair_fn=always_broken)

    assert excinfo.value.args == ("Could not respond",)
    assert call_count == 3, (
        f"repair_fn must be called exactly 3 times (max retries), got {call_count}"
    )


# ---------------------------------------------------------------------------
# Fail-fast — no repair_fn means immediate Error
# ---------------------------------------------------------------------------


def test_no_repair_fn_raises_immediately() -> None:
    from person_finder.validation import Error, validate_output

    with pytest.raises(Error) as excinfo:
        validate_output("not json")

    assert excinfo.value.args == ("Could not respond",)


# ---------------------------------------------------------------------------
# Error symbol contract
# ---------------------------------------------------------------------------


def test_error_class_is_exception_subclass() -> None:
    from person_finder.validation import Error

    assert issubclass(Error, Exception)
    e = Error("Could not respond")
    assert e.args == ("Could not respond",)


# ---------------------------------------------------------------------------
# AC5 — precise error_msg names the violation for each failure mode
#
# Tests the F5 public contract — "what does repair_fn receive in its
# error_msg arg" — by supplying a repair_fn that captures its second arg.
# Avoids coupling to the private _ValidationFailure type that chains to
# Error.__cause__. The same precise diagnostic flows through both paths
# (repair_fn arg AND __cause__ message); we test the public-callable
# path because that's what F5 actually contracts.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "needle"),
    [
        pytest.param("not json", "JSON parse error", id="malformed-json"),
        pytest.param("null", "top-level", id="top-level-not-dict-null"),
        pytest.param("[]", "top-level", id="top-level-not-dict-list"),
        pytest.param('{"other": 1}', '"data"', id="missing-data-key"),
        pytest.param('{"data": "nope"}', "data", id="data-not-list"),
        pytest.param(
            '{"data": [{"info": "x"}]}',
            "person",
            id="missing-person-key",
        ),
        pytest.param(
            '{"data": [{"person": "Ada", "info": 7}]}',
            "info",
            id="info-not-str",
        ),
        pytest.param(
            '{"data": [{"person": 42, "info": "x"}]}',
            "person",
            id="person-not-str",
        ),
        pytest.param(
            '{"data": ["not a dict"]}',
            "data[0]",
            id="data-item-not-dict",
        ),
    ],
)
def test_repair_fn_receives_precise_error_msg(raw: str, needle: str) -> None:
    from person_finder.validation import Error, validate_output

    captured: list[str] = []

    def capture_repair(broken: str, error_msg: str) -> str:
        captured.append(error_msg)
        # Return something that also fails so the loop runs once and we
        # don't accidentally satisfy validation with a side effect.
        return "still broken"

    with pytest.raises(Error):
        validate_output(raw, repair_fn=capture_repair)

    assert captured, "repair_fn must be invoked at least once"
    assert needle in captured[0], (
        f"expected '{needle}' in repair_fn's error_msg arg, got: {captured[0]!r}"
    )


# ---------------------------------------------------------------------------
# Defensive — repair_fn that returns non-str must not crash; counts as a fail
# ---------------------------------------------------------------------------


def test_repair_fn_returning_non_str_is_a_validation_failure() -> None:
    from person_finder.validation import Error, validate_output

    call_count = 0

    def bad_repair(b: str, err: str) -> Any:
        nonlocal call_count
        call_count += 1
        return None  # not a str — must not crash with TypeError

    with pytest.raises(Error):
        validate_output("not json", repair_fn=bad_repair)

    assert call_count == 3, (
        "non-str repair output must be treated as a normal validation fail "
        "and burn through the retry budget"
    )


# ---------------------------------------------------------------------------
# Import hygiene — mirrors AC5 pattern from test_agent.py
# ---------------------------------------------------------------------------


def test_import_has_no_side_effects(tmp_path: Path) -> None:
    """`import person_finder.validation` MUST NOT read env, hit disk, or raise.

    Run in a fresh subprocess because the module may already be cached in
    ``sys.modules`` from earlier tests. The validation module is stdlib-only
    and trivially side-effect-free; this test pins that property.
    """
    child_env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ["HOME"],
    }

    result = subprocess.run(
        ["uv", "run", "python", "-c", "import person_finder.validation"],
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

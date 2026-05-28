"""Live-agent eval: agent output is a valid JSON structure.

The test makes ONE agent call per `make test-eval` invocation: a single
batched call with the full `PUBLIC_FIGURES` list.

Entry point: `deepeval.assert_test(test_case, [metric])`.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from .conftest import PUBLIC_FIGURES
from .metrics import ValidJsonStructure


@pytest.fixture
def agent_output(agent_under_test: Callable[..., Any]) -> str:
    """Invoke the agent once with the full `PUBLIC_FIGURES` roster.

    Function-scoped to match `agent_under_test` (a higher scope would
    raise `ScopeMismatch`). This file holds a single test function, so
    the fixture still resolves to exactly one Groq call per
    `make test-eval` invocation.
    """
    return agent_under_test(PUBLIC_FIGURES)


def test_agent_output_is_valid_json_structure(
    judge_configured: Any, agent_output: str
) -> None:
    """The agent output parses as the expected JSON shape.

    `judge_configured` is requested to satisfy the judge prerequisite at
    runtime even though `ValidJsonStructure` is deterministic and does
    not invoke the judge. Both fixtures route through the skip cascade
    in `tests/eval/conftest.py`, so missing prerequisites yield a
    `skipped` test, never a failure.
    """
    test_case = LLMTestCase(
        input="evaluate JSON structure",
        actual_output=agent_output,
    )
    assert_test(test_case, [ValidJsonStructure()])

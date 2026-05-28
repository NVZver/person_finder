"""Live-agent eval: every `data[].person` is a member of the input roster.

`PersonNamesMatchInput` receives the input roster via its constructor
because DeepEval 4.0.4 requires `LLMTestCase.input` to be a `str`
(documented in `tests/eval/metrics.py:142-146`).

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
from .metrics import PersonNamesMatchInput


@pytest.fixture
def agent_output(agent_under_test: Callable[..., Any]) -> str:
    """Invoke the agent once with the full `PUBLIC_FIGURES` roster.

    Function-scoped to match `agent_under_test` (a higher scope would
    raise `ScopeMismatch`). One test in this file → one Groq call per
    `make test-eval` invocation.
    """
    return agent_under_test(PUBLIC_FIGURES)


def test_agent_persons_match_input_names(
    judge_configured: Any, agent_output: str
) -> None:
    """Every `data[].person` in the agent output is a member of the input roster.

    `judge_configured` is requested to satisfy the judge prerequisite at
    runtime; `PersonNamesMatchInput` is deterministic and does not
    invoke the judge. Both fixtures route through the skip cascade in
    `tests/eval/conftest.py`.
    """
    test_case = LLMTestCase(
        input="evaluate name membership",
        actual_output=agent_output,
    )
    assert_test(test_case, [PersonNamesMatchInput(input_names=PUBLIC_FIGURES)])

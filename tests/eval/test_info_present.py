"""Live-agent eval: every `data[].info` is non-empty or the `<Not found>` sentinel.

The sentinel string `"<Not found>"` is documented in
`tests/eval/metrics.py:43`.

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
from .metrics import InfoNonEmptyOrSentinel, NoSentinelInfo


@pytest.fixture
def agent_output(agent_under_test: Callable[..., Any]) -> str:
    """Invoke the agent once with the full `PUBLIC_FIGURES` roster.

    Function-scoped to match `agent_under_test` (a higher scope would
    raise `ScopeMismatch`). One test in this file → one Groq call per
    `make test-eval` invocation.
    """
    return agent_under_test(PUBLIC_FIGURES)


def test_agent_info_is_present_and_real(
    judge_configured: Any, agent_output: str
) -> None:
    """Every `data[].info` is non-empty AND no item is the `<Not found>` sentinel.

    Two assertions over the same agent call (kept in one test to preserve
    the "one Groq call per file" budget, since the `agent_output` fixture
    is function-scoped):

    - `InfoNonEmptyOrSentinel`: shape contract — info is a non-empty
      string OR the sentinel. Catches whitespace-only / missing info.
    - `NoSentinelInfo`: regression guard — for the `PUBLIC_FIGURES`
      roster (Einstein, Curie), the LLM MUST resolve every entry from
      training data. A sentinel anywhere means the lookup path is broken
      (e.g. a tool returning empty, or a prompt forbidding the LLM from
      answering from its own knowledge — exactly the stub-tool bug this
      metric was added to prevent).

    `judge_configured` is requested to satisfy the judge prerequisite at
    runtime; both metrics are deterministic and do not invoke the judge.
    """
    test_case = LLMTestCase(
        input="evaluate info presence + identification",
        actual_output=agent_output,
    )
    assert_test(test_case, [InfoNonEmptyOrSentinel(), NoSentinelInfo()])

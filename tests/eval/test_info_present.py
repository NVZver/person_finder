"""Live-agent eval: every `data[].info` is non-empty or the `<Not found>` sentinel.

Covers project AC1 (happy path with both keys + agent module present) and
AC3 (skip when `person_finder.agent` is not importable). AC2 (skip on
missing `GOOGLE_API_KEY`) is satisfied by the `agent_under_test` skip
cascade in `tests/eval/conftest.py:117-143`.

The sentinel string `"<Not found>"` is documented in
`tests/eval/metrics.py:43` and pinned by [ARCHITECTURE.md] §LangChain
agent layer line 33.

The test makes ONE agent call per `make test-eval` invocation (NF1,
E3-AC4): a single batched call with the full `PUBLIC_FIGURES` list.

Entry point: `deepeval.assert_test(test_case, [metric])` per
https://github.com/confident-ai/deepeval/blob/main/docs/content/guides/guides-building-custom-metrics.mdx
(retrieved via context7 `/confident-ai/deepeval`).
"""

from __future__ import annotations

from typing import Any, Callable

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from .conftest import PUBLIC_FIGURES
from .metrics import InfoNonEmptyOrSentinel


@pytest.fixture
def agent_output(agent_under_test: Callable[..., Any]) -> str:
    """Invoke the agent once with the full `PUBLIC_FIGURES` roster.

    Function-scoped to match `agent_under_test` (a higher scope would
    raise `ScopeMismatch`). One test in this file → one Groq call per
    `make test-eval` invocation (NF1, E3-AC4).
    """
    return agent_under_test(PUBLIC_FIGURES)


def test_agent_info_is_non_empty_or_sentinel(
    judge_configured: Any, agent_output: str
) -> None:
    """Every `data[].info` is non-empty after `strip()` or the `<Not found>` sentinel.

    `judge_configured` is requested to satisfy F3 ("judge configured as
    Gemini 2.0 Flash") at runtime; `InfoNonEmptyOrSentinel` is
    deterministic and does not invoke the judge. Both fixtures route
    through the skip cascade in `tests/eval/conftest.py`.
    """
    test_case = LLMTestCase(
        input="evaluate info non-empty",
        actual_output=agent_output,
    )
    assert_test(test_case, [InfoNonEmptyOrSentinel()])

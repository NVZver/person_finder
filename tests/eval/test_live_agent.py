"""Live-agent eval: runs `enrich_names` against the `PUBLIC_FIGURES` roster
and asserts all four deterministic metrics. `enrich_names` handles JSON-decode
retries internally (see `person_finder.agent`); one Groq call per
`make test-eval` on the happy path.
"""

from __future__ import annotations

import json
from typing import Any, Callable

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from .conftest import PUBLIC_FIGURES
from .metrics import (
    InfoHasSourcePrefix,
    InfoNonEmptyOrSentinel,
    NoSentinelInfo,
    PersonNamesMatchInput,
    ValidJsonStructure,
)


@pytest.fixture
def agent_payload(agent_under_test: Callable[..., Any]) -> str:
    payload = agent_under_test(PUBLIC_FIGURES)
    return json.dumps(payload)


def test_live_agent_passes_all_metrics(agent_payload: str) -> None:
    test_case = LLMTestCase(
        input="live agent over PUBLIC_FIGURES",
        actual_output=agent_payload,
    )
    assert_test(
        test_case,
        [
            ValidJsonStructure(),
            PersonNamesMatchInput(input_names=PUBLIC_FIGURES),
            InfoNonEmptyOrSentinel(),
            NoSentinelInfo(),
            InfoHasSourcePrefix(),
        ],
    )

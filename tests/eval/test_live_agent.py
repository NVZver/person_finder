"""Live-agent eval: runs the production fetch→enrich→validate→repair path
against the `PUBLIC_FIGURES` roster and asserts all four deterministic metrics.

One Groq call per `make test-eval`. The `validated_payload` fixture mirrors
production by routing the raw LLM output through `validate_output(..., repair_fn=repair)`,
so transient JSON glitches (Llama occasionally emits trailing chars at temp=0)
get repaired exactly the way the user-facing CLI handles them.
"""

from __future__ import annotations

import json
from typing import Any, Callable

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from person_finder.agent import repair
from person_finder.validation import validate_output

from .conftest import PUBLIC_FIGURES
from .metrics import (
    InfoNonEmptyOrSentinel,
    NoSentinelInfo,
    PersonNamesMatchInput,
    ValidJsonStructure,
)


@pytest.fixture
def validated_payload(agent_under_test: Callable[..., Any]) -> str:
    raw = agent_under_test(PUBLIC_FIGURES)
    payload = validate_output(raw, repair_fn=repair)
    return json.dumps(payload)


def test_live_agent_passes_all_metrics(
    judge_configured: Any, validated_payload: str
) -> None:
    test_case = LLMTestCase(
        input="live agent over PUBLIC_FIGURES",
        actual_output=validated_payload,
    )
    assert_test(
        test_case,
        [
            ValidJsonStructure(),
            PersonNamesMatchInput(input_names=PUBLIC_FIGURES),
            InfoNonEmptyOrSentinel(),
            NoSentinelInfo(),
        ],
    )

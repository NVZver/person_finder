"""Live-agent eval (structural tier): runs the full pipeline over
`PUBLIC_FIGURES` and asserts the four deterministic shape metrics.

These check *structure*, not *truth* — JSON shape, name membership, paired
nullability, no-null-info on a known-famous roster. Semantic correctness of
the `info` and `best_work` text is asserted separately in
`test_correctness.py`. Both tiers share the single session-scoped
`live_payload` run.
"""

from __future__ import annotations

import json

from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from .conftest import PUBLIC_FIGURES
from .metrics import (
    InfoNonEmptyOrNull,
    NoNullInfo,
    PersonNamesMatchInput,
    ValidJsonStructure,
)


def test_live_agent_passes_all_metrics(live_payload: dict) -> None:
    test_case = LLMTestCase(
        input="live agent over PUBLIC_FIGURES",
        actual_output=json.dumps(live_payload),
    )
    assert_test(
        test_case,
        [
            ValidJsonStructure(),
            PersonNamesMatchInput(input_names=PUBLIC_FIGURES),
            InfoNonEmptyOrNull(),
            NoNullInfo(),
        ],
    )

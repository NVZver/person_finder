"""Live correctness eval (semantic tier): validate that the agent's text is
actually *true*, not just well-shaped.

The structural metrics in `test_live_agent.py` prove the output parses and has
the right keys — but a confidently-wrong biography ("Einstein, the French
pastry chef") would sail through every one of them. For a person-identification
tool the factual-accuracy failure is the one that matters most, so this tier
uses an LLM-as-judge (`GEval` over a Groq judge) to score correctness.

Two judged criteria, applied to the same single live run:

  - `info` correctness  — the identify-step output (Ex4), covering BOTH the
    Wikipedia-summarized path (`source="wiki"`) and the training-knowledge
    path (`source="llm"`). The check is the same: is the description an
    accurate, non-fabricated account of who this real person is?
  - `best_work` correctness — the agent's output (Ex5): is the named work a
    genuine, correctly-attributed achievement of that person?

These are non-deterministic (an LLM judges them) with a generous threshold, so
they live apart from the deterministic structural metrics. They skip cleanly
without `GROQ_API_KEY`.
"""

from __future__ import annotations

from typing import Any

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

# A generous bar: we want to catch fabrications and wrong-person answers, not
# nitpick phrasing. The judge scores 0..1; 0.7 clears "accurate but terse".
_THRESHOLD = 0.7


def _info_correctness_metric(judge: Any) -> GEval:
    return GEval(
        name="Info Correctness",
        evaluation_steps=[
            "The 'input' is a real person's name; 'actual_output' is a short "
            "description of who they are.",
            "Decide whether the description is a factually accurate, "
            "non-fabricated account of that specific real person.",
            "Score high when it correctly identifies the right person and "
            "their claim to fame; score low for fabrications, wrong-person "
            "mix-ups, or invented facts. Terseness alone is not a penalty.",
        ],
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        model=judge,
        threshold=_THRESHOLD,
    )


def _best_work_correctness_metric(judge: Any) -> GEval:
    return GEval(
        name="Best Work Correctness",
        evaluation_steps=[
            "The 'input' is a real person's name; 'actual_output' names the "
            "work or achievement they are most celebrated for.",
            "Decide whether that work is genuinely attributable to that "
            "specific real person.",
            "Score high when the achievement is real and correctly attributed; "
            "score low if the work is fabricated or belongs to someone else.",
        ],
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        model=judge,
        threshold=_THRESHOLD,
    )


def _identified_rows(live_payload: dict) -> list[dict]:
    rows = [r for r in live_payload["data"] if r["info"] is not None]
    if not rows:
        pytest.skip("no identified people in live payload — nothing to judge")
    return rows


def test_info_is_factually_correct(live_payload: dict, judge: Any) -> None:
    """Every identified person's `info` must be a true description — covers
    both the wiki and llm source paths."""
    metric = _info_correctness_metric(judge)
    for row in _identified_rows(live_payload):
        test_case = LLMTestCase(
            input=row["person"],
            actual_output=row["info"],
        )
        assert_test(test_case, [metric])


def test_best_work_is_factually_correct(live_payload: dict, judge: Any) -> None:
    """Where the agent named a best work, it must be a real, correctly-
    attributed achievement of that person."""
    metric = _best_work_correctness_metric(judge)
    judged = 0
    for row in _identified_rows(live_payload):
        if row["best_work"] is None:
            continue
        judged += 1
        test_case = LLMTestCase(
            input=row["person"],
            actual_output=row["best_work"],
        )
        assert_test(test_case, [metric])

    if judged == 0:
        pytest.skip("agent named no best work for any person — nothing to judge")

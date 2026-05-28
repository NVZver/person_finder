"""Deterministic metrics REJECT bad payloads with named reasons.

Each metric in `tests/eval/metrics.py` must emit `success=False` and a `reason`
containing a documented substring when fed a violating payload. Those
substrings are the contract metrics promise to downstream readers (skip
messages, CI logs). They are pinned here as module-level constants — if
you change the metric's wording, change the constant in the same commit;
the test will catch any drift.

Happy-path coverage (three additional tests) proves each metric accepts a
well-shaped payload and reports `success=True` with `score=1.0` — together
with the failure-mode tests these establish the bi-directional contract.

No live LLM call. No network. The metrics are pure-Python; the stubs are
canned strings. Tests run in milliseconds.
"""

from __future__ import annotations

from deepeval.test_case import LLMTestCase

from .conftest import PUBLIC_FIGURES
from .metrics import (
    InfoNonEmptyOrSentinel,
    NoSentinelInfo,
    PersonNamesMatchInput,
    ValidJsonStructure,
)
from .stub_agents import (
    empty_info_payload,
    malformed_json_payload,
    sentinel_payload,
    unknown_person_payload,
    valid_payload,
)

# === Reason substrings (the contract) =================================
# These are the EXACT substrings each metric promises to embed in its
# `reason` string when the corresponding violation is detected. If you
# update a metric's wording, update the constant here in the same commit.

REASON_JSON_PARSE_ERROR = "JSON parse error"
REASON_UNKNOWN_PERSON = "unknown person 'Foo Bar'"
REASON_EMPTY_INFO_AT_INDEX = "empty info at index 1"
REASON_SENTINEL_PRESENT = "sentinel '<Not found>'"


# === Failure-mode tests ===============================================


def test_valid_json_structure_rejects_malformed_json() -> None:
    """Malformed JSON → success=False; reason names the parse failure."""
    test_case = LLMTestCase(
        input="evaluate JSON structure",
        actual_output=malformed_json_payload(),
    )

    metric = ValidJsonStructure()
    metric.measure(test_case)

    assert metric.success is False
    assert metric.score == 0.0
    assert REASON_JSON_PARSE_ERROR in metric.reason


def test_person_names_match_input_rejects_unknown_person() -> None:
    """Person not in `input_names` → success=False; reason names the unknown person."""
    test_case = LLMTestCase(
        input="evaluate name membership",
        actual_output=unknown_person_payload(PUBLIC_FIGURES),
    )

    metric = PersonNamesMatchInput(input_names=PUBLIC_FIGURES)
    metric.measure(test_case)

    assert metric.success is False
    assert metric.score == 0.0
    assert REASON_UNKNOWN_PERSON in metric.reason


def test_info_non_empty_or_sentinel_rejects_empty_info() -> None:
    """Empty `info` at index 1 → success=False; reason names the offending index."""
    test_case = LLMTestCase(
        input="evaluate info non-empty",
        actual_output=empty_info_payload(PUBLIC_FIGURES),
    )

    metric = InfoNonEmptyOrSentinel()
    metric.measure(test_case)

    assert metric.success is False
    assert metric.score == 0.0
    assert REASON_EMPTY_INFO_AT_INDEX in metric.reason


def test_no_sentinel_info_rejects_all_sentinel_payload() -> None:
    """All-sentinel payload → success=False; reason names the sentinel.

    This is the regression guard for the stub-tool bug: an agent that
    answers ``<Not found>`` for every famous person must fail eval.
    """
    test_case = LLMTestCase(
        input="evaluate no sentinel",
        actual_output=sentinel_payload(PUBLIC_FIGURES),
    )

    metric = NoSentinelInfo()
    metric.measure(test_case)

    assert metric.success is False
    assert metric.score == 0.0
    assert REASON_SENTINEL_PRESENT in metric.reason


# === Happy-path tests — metric is independently instantiable and
# accepts valid input ==================================================


def test_valid_json_structure_accepts_valid_payload() -> None:
    """Well-shaped JSON → success=True; score=1.0."""
    test_case = LLMTestCase(
        input="evaluate JSON structure",
        actual_output=valid_payload(PUBLIC_FIGURES),
    )

    metric = ValidJsonStructure()
    metric.measure(test_case)

    assert metric.success is True
    assert metric.score == 1.0


def test_person_names_match_input_accepts_payload_with_known_names() -> None:
    """Every person in `input_names` → success=True; score=1.0."""
    test_case = LLMTestCase(
        input="evaluate name membership",
        actual_output=valid_payload(PUBLIC_FIGURES),
    )

    metric = PersonNamesMatchInput(input_names=PUBLIC_FIGURES)
    metric.measure(test_case)

    assert metric.success is True
    assert metric.score == 1.0


def test_info_non_empty_or_sentinel_accepts_sentinel_payload() -> None:
    """`info` is the `<Not found>` sentinel for every item → success=True."""
    test_case = LLMTestCase(
        input="evaluate info non-empty",
        actual_output=sentinel_payload(PUBLIC_FIGURES),
    )

    metric = InfoNonEmptyOrSentinel()
    metric.measure(test_case)

    assert metric.success is True
    assert metric.score == 1.0


def test_no_sentinel_info_accepts_valid_payload() -> None:
    """Every item has real (non-sentinel) info → success=True; score=1.0."""
    test_case = LLMTestCase(
        input="evaluate no sentinel",
        actual_output=valid_payload(PUBLIC_FIGURES),
    )

    metric = NoSentinelInfo()
    metric.measure(test_case)

    assert metric.success is True
    assert metric.score == 1.0

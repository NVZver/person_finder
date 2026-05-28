"""Four deterministic `deepeval.metrics.BaseMetric` subclasses.

Each metric encodes one of the four quality criteria for the agent:

  - `ValidJsonStructure`   — output parses as JSON, has a `data` list of
                              `{person:str, info:str|None, source:enum|None}`
                              items with paired nullability between
                              `info` and `source`. The `source` enum is
                              `"wiki" | "llm" | null`.
  - `PersonNamesMatchInput` — every `data[].person` is in the input list
                              (constructor-injected, since DeepEval
                              4.0.4 rejects non-string `LLMTestCase.input`).
  - `InfoNonEmptyOrNull`   — for each item, `info is None` OR
                              `len(info.strip()) > 0` (no empty / whitespace
                              strings paired with a non-null source).
  - `NoNullInfo`           — for each item, `info is not None` (regression
                              guard for the famous-roster eval).

All four are pure-Python, deterministic, and side-effect-free:

  - No network I/O. No env reads. No file writes.
  - `async_mode = False`, and `a_measure` delegates synchronously to
    `measure` so DeepEval's async runner can call either entry point.
  - On failure, `reason` names BOTH the violated criterion AND the
    offending entry (e.g. `"data[2].info is not a str or null — got int"`),
    so traceability survives without a debugger.

The metrics consume `LLMTestCase.actual_output` (a `str`, matching the
agent output contract). DeepEval requires `LLMTestCase.input` to be a
string; the *real* input list — needed by `PersonNamesMatchInput` — is
therefore passed to the metric's `__init__`, not extracted from the test
case. This mirrors how every first-party DeepEval metric receives
external configuration (e.g. `evaluation_model`).
"""

from __future__ import annotations

import json
from typing import Any

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

# Allowed values for the `source` field. `None` means "no source — the
# person was not identified by either Wikipedia or training knowledge".
ALLOWED_SOURCES: frozenset[str] = frozenset({"wiki", "llm"})


def _parse_payload(actual_output: str) -> tuple[Any, str | None]:
    """Parse the agent's reply and validate its top-level + per-item shape.

    Returns `(parsed_data_list, None)` on success, where `parsed_data_list`
    is the contents of the `data` key. Returns `(None, reason)` on the
    first shape violation, with `reason` naming the specific criterion
    and offending location.

    Shape contract:
      - top-level: dict with a `data` key holding a list.
      - per item: dict with keys `person`, `info`, `source`.
      - `person`: non-empty str.
      - `info`: str or None.
      - `source`: one of `"wiki"`, `"llm"`, or None.
      - paired nullability: `info is None` iff `source is None`.

    Shared across all metrics so the parse error path is one source of
    truth — the reason wording is consistent and the contract substrings
    (e.g. `"JSON parse error"`) cannot drift between metrics.
    """
    try:
        parsed = json.loads(actual_output)
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error: {exc.msg} at pos {exc.pos}"

    if not isinstance(parsed, dict):
        return None, (
            f'top-level value is not an object — got {type(parsed).__name__}'
        )

    if "data" not in parsed:
        return None, 'missing "data" key at top level'

    data = parsed["data"]
    if not isinstance(data, list):
        return None, f'"data" is not a list — got {type(data).__name__}'

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            return None, f"data[{i}] is not an object — got {type(item).__name__}"

        for key in ("person", "info", "source"):
            if key not in item:
                return None, f'data[{i}] missing "{key}" key'

        person = item["person"]
        if not isinstance(person, str):
            return None, (
                f"data[{i}].person is not a str — got {type(person).__name__}"
            )

        info = item["info"]
        if info is not None and not isinstance(info, str):
            return None, (
                f"data[{i}].info is not a str or null — got {type(info).__name__}"
            )

        source = item["source"]
        if source is not None and source not in ALLOWED_SOURCES:
            return None, (
                f"data[{i}].source not in allowed enum — got {source!r}; "
                f"expected null or one of {sorted(ALLOWED_SOURCES)}"
            )

        if (info is None) != (source is None):
            return None, (
                f"data[{i}] mismatched pair: info is "
                f"{'null' if info is None else 'non-null'} but source is "
                f"{'null' if source is None else 'non-null'} — both must "
                f"be null, or both populated"
            )

    return data, None


def _set_failure(metric: BaseMetric, reason: str) -> None:
    """Common failure-state writer: score=0.0, success=False, reason=<arg>."""
    metric.score = 0.0
    metric.success = False
    metric.reason = reason


def _set_success(metric: BaseMetric, reason: str) -> None:
    """Common success-state writer: score=1.0, success=True, reason=<arg>."""
    metric.score = 1.0
    metric.success = True
    metric.reason = reason


class ValidJsonStructure(BaseMetric):
    """Deterministic check: `actual_output` parses as the expected JSON shape.

    Success when:
      - `json.loads(actual_output)` is a dict with a `"data"` list.
      - Every list item is a dict with `person:str`, `info:str|None`,
        `source: "wiki" | "llm" | None`.
      - `info` and `source` are paired-null: both populated, or both null.
    """

    threshold: float = 1.0
    async_mode: bool = False

    def __init__(self, threshold: float = 1.0) -> None:
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase) -> float:
        data, reason = _parse_payload(test_case.actual_output)
        if reason is not None:
            _set_failure(self, reason)
            return self.score
        _set_success(
            self,
            f"valid structure: {len(data)} items with correct types and paired (info,source)",
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return "Valid JSON Structure"


class PersonNamesMatchInput(BaseMetric):
    """Deterministic check: every `data[].person` is in the configured input list.

    The input list comes from the constructor — DeepEval 4.0.4 requires
    `LLMTestCase.input` to be a `str` (verified empirically), so we
    cannot smuggle the list through that field. Constructor injection
    mirrors how DeepEval's first-party metrics receive their external
    config (e.g. `evaluation_model`).
    """

    threshold: float = 1.0
    async_mode: bool = False

    def __init__(self, input_names: list[str], threshold: float = 1.0) -> None:
        self.threshold = threshold
        self.input_names = list(input_names)
        self._allowed = set(input_names)

    def measure(self, test_case: LLMTestCase) -> float:
        data, reason = _parse_payload(test_case.actual_output)
        if reason is not None:
            _set_failure(self, reason)
            return self.score

        unknown = [
            item["person"] for item in data if item["person"] not in self._allowed
        ]
        if unknown:
            first = unknown[0]
            _set_failure(self, f"unknown person '{first}' not in input list")
            return self.score

        _set_success(
            self,
            f"all {len(data)} persons are members of the input list",
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return "Person Names Match Input"


class InfoNonEmptyOrNull(BaseMetric):
    """Deterministic check: every `data[].info` is `None` OR a non-empty string.

    Whitespace-only `info` counts as empty: `len(info.strip()) > 0` is
    the threshold. `info is None` is an explicit pass — that is the
    documented "not found" signal, paired with `source is None`.
    """

    threshold: float = 1.0
    async_mode: bool = False

    def __init__(self, threshold: float = 1.0) -> None:
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase) -> float:
        data, reason = _parse_payload(test_case.actual_output)
        if reason is not None:
            _set_failure(self, reason)
            return self.score

        for i, item in enumerate(data):
            info = item["info"]
            if info is None:
                continue
            if len(info.strip()) == 0:
                _set_failure(self, f"empty info at index {i}")
                return self.score

        _set_success(
            self,
            f"all {len(data)} items have non-empty info or null",
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return "Info Non-Empty Or Null"


class NoNullInfo(BaseMetric):
    """Deterministic check: NO `data[].info` is `None`.

    Stricter sibling of :class:`InfoNonEmptyOrNull`. Use this when the
    input roster is known-famous people (e.g. ``PUBLIC_FIGURES`` for the
    live eval) — the LLM must actually identify them; a null `info` is a
    regression (e.g. the lookup path got disconnected). For random users
    where null `info` is legitimately expected, use
    :class:`InfoNonEmptyOrNull` instead.
    """

    threshold: float = 1.0
    async_mode: bool = False

    def __init__(self, threshold: float = 1.0) -> None:
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase) -> float:
        data, reason = _parse_payload(test_case.actual_output)
        if reason is not None:
            _set_failure(self, reason)
            return self.score

        null_indices = [i for i, item in enumerate(data) if item["info"] is None]
        if null_indices:
            _set_failure(
                self,
                f"null info at indices {null_indices} "
                f"({len(null_indices)}/{len(data)} items) — model failed to "
                f"identify known person(s)",
            )
            return self.score

        _set_success(
            self,
            f"all {len(data)} items have non-null info",
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return "No Null Info"

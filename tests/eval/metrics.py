"""Three deterministic `deepeval.metrics.BaseMetric` subclasses.

Each metric encodes one of the three quality criteria fixed by
[ARCHITECTURE.md] §LLM evaluation lines 92-98:

  - `ValidJsonStructure`     — output parses as JSON, has a `data` list of
                                `{person:str, info:str}` items.
  - `PersonNamesMatchInput`  — every `data[].person` is in the input list
                                (constructor-injected, since DeepEval
                                4.0.4 rejects non-string `LLMTestCase.input`).
  - `InfoNonEmptyOrSentinel` — for each item, `info == "<Not found>"`
                                OR `len(info.strip()) > 0`.

All three are pure-Python, deterministic, and side-effect-free:

  - No network I/O. No env reads. No file writes.
  - `async_mode = False` — `a_measure` is intentionally not implemented;
    DeepEval will not invoke it.
  - On failure, `reason` names BOTH the violated criterion AND the
    offending entry (e.g. `"data[2].info is not a str — got int"`),
    so AC4 traceability survives without a debugger.

The metrics consume `LLMTestCase.actual_output` (a `str`, per the agent
output contract at [main.spec.md:20]). DeepEval requires `LLMTestCase.input`
to be a string; the *real* input list — needed by `PersonNamesMatchInput`
— is therefore passed to the metric's `__init__`, not extracted from the
test case. This mirrors how every first-party DeepEval metric receives
external configuration (e.g. `evaluation_model`).
"""

from __future__ import annotations

import json
from typing import Any

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

# The agent's fallback string when no info is available
# ([ARCHITECTURE.md] §LangChain agent layer line 33). Pinned here as a
# module constant so `InfoNonEmptyOrSentinel` and the stubs in
# `stub_agents.py` cannot drift.
SENTINEL_NOT_FOUND = "<Not found>"


def _parse_payload(actual_output: str) -> tuple[Any, str | None]:
    """Parse the agent's reply and validate its top-level + per-item shape.

    Returns `(parsed_data_list, None)` on success, where `parsed_data_list`
    is the contents of the `data` key (a `list[dict[str, str]]`). Returns
    `(None, reason)` on the first shape violation, with `reason` naming
    the specific criterion and offending location.

    Shared across all three metrics so the parse error path is one source
    of truth — the reason wording is consistent and AC4 substrings (e.g.
    `"JSON parse error"`) cannot drift between metrics.
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
        for key in ("person", "info"):
            if key not in item:
                return None, f'data[{i}] missing "{key}" key'
            if not isinstance(item[key], str):
                return None, (
                    f"data[{i}].{key} is not a str — got "
                    f"{type(item[key]).__name__}"
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
      - `json.loads(actual_output)` is a dict.
      - It has a `"data"` key whose value is a list.
      - Every list item is a dict with `person: str` and `info: str`.
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
            f"valid structure: {len(data)} items, all with person:str and info:str",
        )
        return self.score

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

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return "Person Names Match Input"


class InfoNonEmptyOrSentinel(BaseMetric):
    """Deterministic check: every `data[].info` is non-empty OR the sentinel.

    Whitespace-only info counts as empty: `len(info.strip()) > 0` is the
    threshold. The sentinel `"<Not found>"` is an explicit pass per
    [ARCHITECTURE.md] §LangChain agent layer line 33.
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
            if info == SENTINEL_NOT_FOUND:
                continue
            if len(info.strip()) == 0:
                _set_failure(self, f"empty info at index {i}")
                return self.score

        _set_success(
            self,
            f"all {len(data)} items have non-empty info or the sentinel",
        )
        return self.score

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return "Info Non-Empty Or Sentinel"

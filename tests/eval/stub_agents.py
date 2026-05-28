"""Canned agent-reply payloads for the eval-tier metric tests.

The three deterministic metrics in `tests/eval/metrics.py` must reject
violating payloads with a documented reason substring. Verifying that
against the live LangChain agent is impossible (we cannot coerce the real
LLM to emit a specific malformed payload on demand) and wasteful (one
Groq call per failure mode). The functions below return canned strings
that mirror the production agent's output contract —
`{ "data": [{ "person": str, "info": str }] }` — and let each failure
mode be exercised in microseconds.

Each function returns a `str` (the JSON-shaped agent reply, NOT a parsed
dict, matching the contract surface the metrics consume).

Five generators:

  - `malformed_json_payload()`     — drives `ValidJsonStructure` to fail.
  - `unknown_person_payload(names)` — drives `PersonNamesMatchInput`.
  - `empty_info_payload(names)`     — drives `InfoNonEmptyOrSentinel`.
  - `valid_payload(names)`          — happy path; passes all three.
  - `sentinel_payload(names)`       — happy path with `<Not found>`.
"""

from __future__ import annotations

import json

# The fallback string the agent emits when no info is available.
_SENTINEL = "<Not found>"

# Name that is intentionally NOT in any plausible `PUBLIC_FIGURES` roster
# — used by `unknown_person_payload`. The substring "'Foo Bar'" is part
# of the contract pinned in `test_metric_failure_modes.py`.
_FOREIGN_NAME = "Foo Bar"


def malformed_json_payload() -> str:
    """Return a string that is not valid JSON.

    The leading non-bracket character forces `json.loads` to raise
    `json.JSONDecodeError` on the very first token, which the
    `ValidJsonStructure` metric must catch and report.
    """
    return "this is not json {"


def unknown_person_payload(input_names: list[str]) -> str:
    """Return a valid JSON payload containing one person NOT in `input_names`.

    Shape is fully correct (all keys present, types correct, `info` is a
    non-empty string), so only the set-membership check in
    `PersonNamesMatchInput` will fail. This keeps the failure surface
    one-dimensional: a test failure here means the membership logic is
    wrong, not that some other shape check accidentally caught it.
    """
    items = [{"person": _FOREIGN_NAME, "info": "ghost entry"}]
    items.extend({"person": name, "info": "stub info"} for name in input_names)
    return json.dumps({"data": items})


def empty_info_payload(input_names: list[str]) -> str:
    """Return a valid JSON payload with an empty `info` at index 1.

    Index 0 has a non-empty `info` so the metric's per-item loop must
    reach index 1 before it reports failure — proving the reason names
    the *specific* offending index, not a generic "some info is empty".
    Falls back to a single-item payload if `input_names` is empty,
    keeping the function safe for unusual rosters.
    """
    if len(input_names) < 2:
        # Edge case: a single-name roster still needs index-1 coverage.
        return json.dumps(
            {
                "data": [
                    {"person": input_names[0] if input_names else "Anonymous",
                     "info": "non-empty"},
                    {"person": input_names[0] if input_names else "Anonymous",
                     "info": ""},
                ]
            }
        )
    items = [{"person": input_names[0], "info": "non-empty"}]
    items.append({"person": input_names[1], "info": ""})
    return json.dumps({"data": items})


def valid_payload(input_names: list[str]) -> str:
    """Return a fully-valid JSON payload: all three metrics return `success=True`.

    Each item has `person` in `input_names` and a non-empty `info` string.
    """
    items = [{"person": name, "info": f"stub info for {name}"} for name in input_names]
    return json.dumps({"data": items})


def sentinel_payload(input_names: list[str]) -> str:
    """Return a valid JSON payload where every `info` is the `<Not found>` sentinel.

    Exercises the `InfoNonEmptyOrSentinel` sentinel branch:
    `info == "<Not found>"` must pass even though strictly speaking
    `"<Not found>"` is non-empty (the metric does NOT require the
    sentinel to be the empty string).
    """
    items = [{"person": name, "info": _SENTINEL} for name in input_names]
    return json.dumps({"data": items})

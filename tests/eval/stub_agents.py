"""Canned agent-reply payloads for the eval-tier metric tests.

The four deterministic metrics in `tests/eval/metrics.py` must reject
violating payloads with a documented reason substring. Verifying that
against the live LangChain agent is impossible (we cannot coerce the real
LLM to emit a specific malformed payload on demand) and wasteful (one
Groq call per failure mode). The functions below return canned strings
that mirror the production agent's output contract —
`{ "data": [{ "person": str, "info": str|None, "source": "wiki"|"llm"|None, "best_work": str|None }] }`
— and let each failure mode be exercised in microseconds.

Each function returns a `str` (the JSON-shaped agent reply, NOT a parsed
dict, matching the contract surface the metrics consume).

Six generators:

  - `malformed_json_payload()`         — drives `ValidJsonStructure` to fail.
  - `unknown_person_payload(names)`    — drives `PersonNamesMatchInput`.
  - `empty_info_payload(names)`        — drives `InfoNonEmptyOrNull`.
  - `mismatched_pair_payload(names)`   — drives `ValidJsonStructure` for the
                                          (info,source) paired-nullability rule.
  - `valid_payload(names)`             — happy path; passes every metric.
  - `null_payload(names)`              — happy path with `info=null,source=null`.
"""

from __future__ import annotations

import json

# Mirror of the contract pinned in `tests/eval/metrics.py` — kept here as
# a local literal so the stub file remains self-contained for canned-data
# generation. Drift between this string and `metrics.ALLOWED_SOURCES` is
# caught by the eval metric tests in `test_metric_failure_modes.py`.
_SOURCE_WIKI = "wiki"

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
    non-empty string with a valid `source`), so only the set-membership
    check in `PersonNamesMatchInput` will fail. This keeps the failure
    surface one-dimensional: a test failure here means the membership
    logic is wrong, not that some other shape check accidentally caught it.
    """
    items = [
        {"person": _FOREIGN_NAME, "info": "ghost entry", "source": _SOURCE_WIKI, "best_work": "ghost work"}
    ]
    items.extend(
        {"person": name, "info": "stub info", "source": _SOURCE_WIKI, "best_work": "stub work"}
        for name in input_names
    )
    return json.dumps({"data": items})


def empty_info_payload(input_names: list[str]) -> str:
    """Return a valid JSON payload with an empty `info` at index 1.

    Index 0 has a non-empty `info` so the metric's per-item loop must
    reach index 1 before it reports failure — proving the reason names
    the *specific* offending index, not a generic "some info is empty".
    Falls back to a single-item payload if `input_names` is empty,
    keeping the function safe for unusual rosters.

    Note: empty string still pairs with a non-null `source` (the failure
    we're isolating is "empty `info`", not "mismatched pair"). The
    `ValidJsonStructure` metric accepts this shape; `InfoNonEmptyOrNull`
    is the one that must reject it.
    """
    if len(input_names) < 2:
        # Edge case: a single-name roster still needs index-1 coverage.
        anchor = input_names[0] if input_names else "Anonymous"
        return json.dumps(
            {
                "data": [
                    {"person": anchor, "info": "non-empty", "source": _SOURCE_WIKI, "best_work": "work"},
                    {"person": anchor, "info": "", "source": _SOURCE_WIKI, "best_work": "work"},
                ]
            }
        )
    items = [
        {"person": input_names[0], "info": "non-empty", "source": _SOURCE_WIKI, "best_work": "work"},
        {"person": input_names[1], "info": "", "source": _SOURCE_WIKI, "best_work": "work"},
    ]
    return json.dumps({"data": items})


def valid_payload(input_names: list[str]) -> str:
    """Return a fully-valid JSON payload: every metric returns `success=True`.

    Each item has `person` in `input_names`, a non-empty `info` string,
    and a valid `source` of `"wiki"` — matching the production agent's
    contract.
    """
    items = [
        {
            "person": name,
            "info": f"stub info for {name}",
            "source": _SOURCE_WIKI,
            "best_work": f"notable work of {name}",
        }
        for name in input_names
    ]
    return json.dumps({"data": items})


def mismatched_pair_payload(input_names: list[str]) -> str:
    """Return a payload where index 1 has `info` populated but `source=null`.

    Index 0 carries a valid paired (info, source) so the metric's per-item
    loop must reach index 1 before reporting — proving the reason names
    the *specific* offending index. The contract is paired nullability:
    both populated, or both null; this stub violates that.
    """
    if len(input_names) < 2:
        anchor = input_names[0] if input_names else "Anonymous"
        return json.dumps(
            {
                "data": [
                    {"person": anchor, "info": "paired info", "source": _SOURCE_WIKI, "best_work": "work"},
                    {"person": anchor, "info": "orphan info", "source": None, "best_work": None},
                ]
            }
        )
    items = [
        {"person": input_names[0], "info": "paired info", "source": _SOURCE_WIKI, "best_work": "work"},
        {"person": input_names[1], "info": "orphan info", "source": None, "best_work": None},
    ]
    return json.dumps({"data": items})


def best_work_without_info_payload(input_names: list[str]) -> str:
    """Return a payload where index 1 has `best_work` but null `info`/`source`.

    Index 0 is a valid identified row so the metric's loop must reach index 1.
    Violates the contract rule "best_work requires identification" — you cannot
    research the best work of someone you couldn't identify. Drives
    `ValidJsonStructure` to fail.
    """
    anchor = input_names[0] if input_names else "Anonymous"
    second = input_names[1] if len(input_names) > 1 else anchor
    return json.dumps(
        {
            "data": [
                {"person": anchor, "info": "real info", "source": _SOURCE_WIKI, "best_work": "real work"},
                {"person": second, "info": None, "source": None, "best_work": "orphan work"},
            ]
        }
    )


def null_payload(input_names: list[str]) -> str:
    """Return a valid payload where every `info` and `source` is null.

    Exercises the "no source available" branch: paired null is a valid
    shape (passes `ValidJsonStructure` and `InfoNonEmptyOrNull`) but
    `NoNullInfo` rejects it — that is the regression guard for the
    famous-roster eval.
    """
    items = [
        {"person": name, "info": None, "source": None, "best_work": None}
        for name in input_names
    ]
    return json.dumps({"data": items})

"""Validation + repair-retry loop for the LangChain agent's JSON output.

Runs AFTER the ReAct loop (per ARCHITECTURE.md §Layers/2): parses the LLM's
raw final-message content, asserts the cross-module schema
(``{"data": [{"person": str, "info": str}]}``), and on failure asks the
caller's ``repair_fn`` to fix it. Budget: 3 repair attempts. On exhaustion,
raises ``Error("Could not respond")`` per [main.spec.md §Cross-Module
Contracts](../../specs/main.spec.md).

The module is code-only and intentionally LLM-free: the caller (Epic 5
``render`` layer) wires ``repair_fn`` as a closure over the agent. This keeps
unit tests fast (no network) and reuses ``validate_output`` for any future
repair source.

Naming note — ``Error``: the literal name is dictated by main.spec.md:22's
``Error("Could not respond")`` failure-signal contract. The class is scoped
to this module only (``person_finder.validation.Error``); Python has no
builtin ``Error`` symbol, so no actual builtin is shadowed, but a careless
``from person_finder.validation import *`` would still pollute the importing
namespace. Callers should ``from person_finder.validation import Error``
explicitly.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Final


MAX_REPAIRS: Final[int] = 3


class Error(Exception):
    """Cross-module failure signal per main.spec.md:22.

    Raised by :func:`validate_output` after the repair budget is exhausted.
    Carries the single argument ``"Could not respond"`` per the contract.
    The underlying precise diagnostic is preserved on ``__cause__``.
    """


class _ValidationFailure(Exception):
    """Internal — describes ONE failed validation attempt.

    Carries a human-readable message intended for ``repair_fn``'s ``error_msg``
    argument (e.g. ``'data[2].info is not a str — got int'``). Never leaks
    outside this module; on retry exhaustion it is attached to the public
    :class:`Error` via ``raise ... from`` so callers can still inspect it.
    """


def validate_output(
    raw: str,
    repair_fn: Callable[[str, str], str] | None = None,
) -> dict[str, Any]:
    """Validate the LLM's JSON output, asking ``repair_fn`` to fix failures.

    Parameters
    ----------
    raw:
        The LLM's raw final-message content. Expected to be a JSON object
        of shape ``{"data": [{"person": str, "info": str}, ...]}``.
    repair_fn:
        Optional callable ``(broken_raw, error_msg) -> repaired_raw``. When
        provided, up to :data:`MAX_REPAIRS` failed attempts will be sent to
        ``repair_fn`` for a fresh try. When ``None``, the first failure
        raises immediately.

    Returns
    -------
    dict[str, Any]
        The parsed (and shape-validated) payload.

    Raises
    ------
    Error
        ``Error("Could not respond")`` once the repair budget is exhausted
        (or immediately if ``repair_fn`` is ``None`` and the initial parse
        fails). The chained ``__cause__`` is the last
        :class:`_ValidationFailure` with a precise diagnostic.
    """
    current = raw
    last_failure: _ValidationFailure | None = None

    # One initial attempt + MAX_REPAIRS repair rounds = MAX_REPAIRS+1 total tries.
    for attempt in range(MAX_REPAIRS + 1):
        try:
            return _parse_and_check(current)
        except _ValidationFailure as exc:
            last_failure = exc
            if repair_fn is None or attempt == MAX_REPAIRS:
                break
            # Hand the broken raw + precise error to the caller's repair fn.
            current = repair_fn(current, str(exc))

    # Budget exhausted (or no repair_fn given). Surface the spec-mandated signal
    # while preserving the underlying diagnostic for debugging / tests.
    raise Error("Could not respond") from last_failure


def _parse_and_check(raw: Any) -> dict[str, Any]:
    """Decode + shape-check in one step. Raises :class:`_ValidationFailure` on either.

    ``raw`` is typed ``Any`` (not ``str``) because ``repair_fn`` may return a
    non-string by mistake — we want that case to count against the retry budget
    rather than crash with ``TypeError``.
    """
    if not isinstance(raw, str):
        raise _ValidationFailure(
            f"repair output is not a str — got {type(raw).__name__}"
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _ValidationFailure(f"JSON parse error: {exc.msg}") from exc
    return _check_shape(payload)


def _check_shape(payload: Any) -> dict[str, Any]:
    """Assert ``{"data": [{"person": str, "info": str}, ...]}`` and return it.

    Reports the first violation found with index/key context so ``repair_fn``
    can produce a targeted fix.
    """
    if not isinstance(payload, dict):
        raise _ValidationFailure(
            f"top-level is not a dict — got {type(payload).__name__}"
        )
    if "data" not in payload:
        raise _ValidationFailure('missing "data" key at top level')
    data = payload["data"]
    if not isinstance(data, list):
        raise _ValidationFailure(
            f"data is not a list — got {type(data).__name__}"
        )

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise _ValidationFailure(
                f"data[{i}] is not a dict — got {type(item).__name__}"
            )
        for key in ("person", "info"):
            if key not in item:
                raise _ValidationFailure(f'data[{i}] missing "{key}" key')
            if not isinstance(item[key], str):
                raise _ValidationFailure(
                    f"data[{i}].{key} is not a str — got "
                    f"{type(item[key]).__name__}"
                )

    return payload

"""Random-user fetch + filter + name mapping.

Fetches 20 user records from `randomuser.me`, drops anyone whose year-of-birth
is strictly after 2000, and returns the remaining names as a `list[str]` of
`"First Last"` strings, preserving API response order.

This module is HTTP-shape-aware but agent-layer-agnostic: it raises a typed
`UserFetchError` on any failure so callers (the agent/render layer) can map
that to the user-facing `Error("Could not respond")` flow without coupling
to httpx.

The public function accepts an optional `httpx.Client` so unit tests can inject
an `httpx.MockTransport`; production code passes nothing and the function
builds a short-lived client with a sensible default timeout.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

RANDOMUSER_URL = "https://randomuser.me/api/?results=20"
"""Canonical endpoint. Hard-coded by design: the spec is fixed at 20 results."""

_BIRTH_YEAR_CUTOFF = 2000
"""Records with year-of-birth strictly greater than this are dropped."""

_DEFAULT_TIMEOUT_SECONDS = 10.0
"""Per-request timeout. Keeps a hung upstream from blocking the agent layer."""


class UserFetchError(RuntimeError):
    """Raised when the random-user endpoint is unreachable or returns
    a payload that does not match the expected shape.

    Carries the underlying cause via ``raise ... from exc`` so future logging
    can introspect without this module taking a logging dependency.
    """


def fetch_user_names(client: httpx.Client | None = None) -> list[str]:
    """Fetch 20 random users, drop year-of-birth > 2000, return `"First Last"` list.

    Args:
        client: Optional pre-built httpx client. When omitted, a short-lived
            client is constructed with a 10-second timeout. Tests pass a client
            wired to `httpx.MockTransport` to avoid real network I/O.

    Returns:
        Names of users whose ``dob.date`` ISO-8601 year is ``<= 2000``, in the
        order returned by the API. Empty list is a legal result.

    Raises:
        UserFetchError: HTTP status != 200, body is not valid JSON, payload
            lacks a ``results`` list, or any record lacks ``dob.date``,
            ``name.first``, or ``name.last``.
    """
    if client is None:
        with httpx.Client(timeout=_DEFAULT_TIMEOUT_SECONDS) as owned_client:
            response = _request(owned_client)
    else:
        response = _request(client)

    payload = _parse_json(response)
    records = _extract_results(payload)
    return [_format_name(rec) for rec in records if _keep(rec)]


def _request(client: httpx.Client) -> httpx.Response:
    try:
        response = client.get(RANDOMUSER_URL)
    except httpx.HTTPError as exc:
        raise UserFetchError(f"Request to {RANDOMUSER_URL} failed: {exc}") from exc

    if response.status_code != 200:
        raise UserFetchError(
            f"Random-user endpoint returned HTTP {response.status_code}"
        )
    return response


def _parse_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise UserFetchError("Random-user endpoint returned non-JSON body") from exc


def _extract_results(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or "results" not in payload:
        raise UserFetchError("Random-user payload missing 'results' key")
    results = payload["results"]
    if not isinstance(results, list):
        raise UserFetchError("Random-user 'results' is not a list")
    return results


def _keep(record: dict[str, Any]) -> bool:
    """True if the record's year-of-birth is <= cutoff (2000)."""
    return _year_of_birth(record) <= _BIRTH_YEAR_CUTOFF


def _year_of_birth(record: Any) -> int:
    if not isinstance(record, dict):
        raise UserFetchError("Random-user record is not an object")
    dob = record.get("dob")
    if not isinstance(dob, dict) or not isinstance(dob.get("date"), str):
        raise UserFetchError("Random-user record missing 'dob.date'")
    iso = dob["date"]
    # Normalise trailing 'Z' (UTC) to '+00:00' so fromisoformat accepts it on
    # any 3.x runtime, not just 3.11+.
    normalised = iso.replace("Z", "+00:00") if iso.endswith("Z") else iso
    try:
        return datetime.fromisoformat(normalised).year
    except ValueError as exc:
        raise UserFetchError(f"Random-user record has malformed 'dob.date': {iso!r}") from exc


def _format_name(record: dict[str, Any]) -> str:
    name = record.get("name")
    if not isinstance(name, dict):
        raise UserFetchError("Random-user record missing 'name' object")
    first = name.get("first")
    last = name.get("last")
    if not isinstance(first, str) or not isinstance(last, str):
        raise UserFetchError("Random-user record missing 'name.first' or 'name.last'")
    return f"{first} {last}"

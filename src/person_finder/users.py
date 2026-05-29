"""Fetch random users from randomuser.me; keep those born on or before 2000.

The returned list is truncated to `MAX_PEOPLE` to bound downstream LLM work.
"""

from __future__ import annotations

import json
from datetime import datetime
from urllib.error import URLError
from urllib.request import urlopen

RANDOMUSER_URL = "https://randomuser.me/api/?results=20"
_BIRTH_YEAR_CUTOFF = 2000

MAX_PEOPLE = 5


class UserFetchError(RuntimeError):
    """Raised when randomuser.me is unreachable or returns an unexpected payload."""


def fetch_user_names(*, limit: int = MAX_PEOPLE) -> list[str]:
    """Return up to `limit` `"First Last"` names with DOB year <= 2000, in API order."""
    try:
        with urlopen(RANDOMUSER_URL, timeout=10.0) as response:  # noqa: S310 — fixed URL
            payload = json.load(response)
    except (URLError, OSError) as exc:
        raise UserFetchError(f"Request failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise UserFetchError(f"Bad payload: {exc}") from exc

    try:
        results = payload["results"]
    except (KeyError, TypeError) as exc:
        raise UserFetchError(f"Bad payload: {exc}") from exc

    names: list[str] = []
    for record in results:
        try:
            year = datetime.fromisoformat(record["dob"]["date"]).year
            first, last = record["name"]["first"], record["name"]["last"]
        except (KeyError, TypeError, ValueError) as exc:
            raise UserFetchError(f"Malformed record: {exc}") from exc
        if year <= _BIRTH_YEAR_CUTOFF:
            names.append(f"{first} {last}")
    return names[:limit]

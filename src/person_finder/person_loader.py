"""Fetch random users from randomuser.me; keep those born on or before 2000.

The returned list is truncated to `config.max_people()` to bound downstream LLM work.
"""

from __future__ import annotations

import json
from datetime import datetime
from urllib.error import URLError
from urllib.request import urlopen

from person_finder import config


class UserFetchError(RuntimeError):
    """Raised when randomuser.me is unreachable or returns an unexpected payload."""


def fetch_user_names(*, limit: int | None = None) -> list[str]:
    """Return up to `limit` `"First Last"` names with DOB year <= cutoff, in API order.

    `limit` defaults to `config.max_people()` when not given.
    """
    if limit is None:
        limit = config.max_people()
    try:
        with urlopen(config.RANDOMUSER_URL, timeout=config.REQUEST_TIMEOUT) as response:  # noqa: S310 — fixed URL
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
        if year <= config.BIRTH_YEAR_CUTOFF:
            names.append(f"{first} {last}")
    return names[:limit]

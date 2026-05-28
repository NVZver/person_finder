"""Fetch 20 random users from randomuser.me; keep those born on or before 2000."""

from __future__ import annotations

from datetime import datetime

import httpx

RANDOMUSER_URL = "https://randomuser.me/api/?results=20"
_BIRTH_YEAR_CUTOFF = 2000


class UserFetchError(RuntimeError):
    """Raised when randomuser.me is unreachable or returns an unexpected payload."""


def fetch_user_names(client: httpx.Client | None = None) -> list[str]:
    """Return `"First Last"` names whose DOB year is <= 2000, in API order."""
    owned = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        try:
            response = client.get(RANDOMUSER_URL)
        except httpx.HTTPError as exc:
            raise UserFetchError(f"Request failed: {exc}") from exc
    finally:
        if owned:
            client.close()

    if response.status_code != 200:
        raise UserFetchError(f"HTTP {response.status_code}")

    try:
        results = response.json()["results"]
    except (ValueError, KeyError, TypeError) as exc:
        raise UserFetchError(f"Bad payload: {exc}") from exc

    names: list[str] = []
    for record in results:
        try:
            iso = record["dob"]["date"].replace("Z", "+00:00")
            year = datetime.fromisoformat(iso).year
            first, last = record["name"]["first"], record["name"]["last"]
        except (KeyError, TypeError, ValueError) as exc:
            raise UserFetchError(f"Malformed record: {exc}") from exc
        if year <= _BIRTH_YEAR_CUTOFF:
            names.append(f"{first} {last}")
    return names

"""Unit tests for `person_finder.users`.

Covers: fetch 20 randomuser records, drop year-of-birth > 2000, truncate to
`MAX_PEOPLE` (5), return `list[str]` of `"First Last"` in API response order.

`urllib.request.urlopen` is mocked via `unittest.mock.patch` — no network.
"""

from __future__ import annotations

import io
import json
from typing import Any
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest


def _record(first: str, last: str, year: int, month: int = 6, day: int = 15) -> dict[str, Any]:
    iso = f"{year:04d}-{month:02d}-{day:02d}T08:30:00.000Z"
    return {
        "name": {"title": "Mr", "first": first, "last": last},
        "dob": {"date": iso, "age": 2026 - year},
    }


def _body(records: list[dict[str, Any]]) -> io.BytesIO:
    return io.BytesIO(json.dumps({"results": records}).encode("utf-8"))


def test_happy_path_mixed_years_returns_filtered_subset_in_order() -> None:
    records = [
        _record("Adam", "Smith", 1980),    # kept
        _record("Bea", "Jones", 2005),     # dropped
        _record("Cara", "Lopez", 1999),    # kept
        _record("Dan", "Kim", 2001),       # dropped
        _record("Eve", "Park", 2000),      # kept (boundary)
        _record("Finn", "Ng", 1975),       # kept
        _record("Gwen", "Roy", 2010),      # dropped
        _record("Hal", "Vasquez", 1990),   # kept
        _record("Ivy", "Chen", 2003),      # dropped
        _record("Jon", "Doe", 1968),       # kept
        _record("Kim", "Liu", 1985),       # kept
        _record("Lee", "Sato", 2008),      # dropped
        _record("Mae", "Ito", 1995),       # kept
        _record("Noa", "Tan", 2002),       # dropped
        _record("Ola", "Mak", 1978),       # kept
        _record("Pat", "Cruz", 1999),      # kept
        _record("Quin", "Hall", 2004),     # dropped
        _record("Rae", "Khan", 1972),      # kept
        _record("Sam", "Reed", 2006),      # dropped
        _record("Tia", "West", 1988),      # kept
    ]
    captured: dict[str, Any] = {}

    def _urlopen(url: str, **kwargs: Any) -> io.BytesIO:
        captured["url"] = url
        return _body(records)

    from person_finder.users import fetch_user_names

    with patch("person_finder.users.urlopen", side_effect=_urlopen):
        names = fetch_user_names()

    # 12 records pass the year filter, but the default cap keeps the first 5.
    assert names == [
        "Adam Smith",
        "Cara Lopez",
        "Eve Park",
        "Finn Ng",
        "Hal Vasquez",
    ]
    assert captured["url"] == "https://randomuser.me/api/?results=20"


def test_default_cap_is_five() -> None:
    """Assignment: stick to 5 people for rate limits — `MAX_PEOPLE == 5`."""
    from person_finder.users import MAX_PEOPLE

    assert MAX_PEOPLE == 5


def test_limit_truncates_filtered_results() -> None:
    records = [_record(f"First{i}", f"Last{i}", 1950 + i) for i in range(20)]

    from person_finder.users import fetch_user_names

    with patch("person_finder.users.urlopen", return_value=_body(records)):
        names = fetch_user_names(limit=3)

    assert names == ["First0 Last0", "First1 Last1", "First2 Last2"]


def test_fewer_matches_than_limit_returns_all_matches() -> None:
    records = [_record("Only", "One", 1990)] + [
        _record(f"Young{i}", f"Person{i}", 2005) for i in range(19)
    ]

    from person_finder.users import fetch_user_names

    with patch("person_finder.users.urlopen", return_value=_body(records)):
        assert fetch_user_names() == ["Only One"]


def test_all_born_after_2000_returns_empty_list() -> None:
    records = [_record(f"P{i}", f"L{i}", 2001 + (i % 5)) for i in range(20)]

    from person_finder.users import fetch_user_names

    with patch("person_finder.users.urlopen", return_value=_body(records)):
        assert fetch_user_names() == []


def test_all_born_2000_or_earlier_caps_at_max_people_in_order() -> None:
    records = [_record(f"First{i}", f"Last{i}", 1950 + i) for i in range(20)]

    from person_finder.users import MAX_PEOPLE, fetch_user_names

    with patch("person_finder.users.urlopen", return_value=_body(records)):
        names = fetch_user_names()

    assert names == [f"First{i} Last{i}" for i in range(MAX_PEOPLE)]


def test_boundary_year_2000_is_kept() -> None:
    """Spec: drop *after* 2000 → year == 2000 is retained."""
    records = [_record("Boundary", "Person", 2000)]

    from person_finder.users import fetch_user_names

    with patch("person_finder.users.urlopen", return_value=_body(records)):
        assert fetch_user_names() == ["Boundary Person"]


def test_http_error_status_raises_user_fetch_error() -> None:
    err = HTTPError("https://x", 503, "Service Unavailable", hdrs={}, fp=None)  # type: ignore[arg-type]

    from person_finder.users import UserFetchError, fetch_user_names

    with patch("person_finder.users.urlopen", side_effect=err):
        with pytest.raises(UserFetchError) as exc_info:
            fetch_user_names()

    assert "503" in str(exc_info.value)


def test_url_error_raises_user_fetch_error() -> None:
    from person_finder.users import UserFetchError, fetch_user_names

    with patch("person_finder.users.urlopen", side_effect=URLError("dns failure")):
        with pytest.raises(UserFetchError):
            fetch_user_names()


def test_malformed_json_body_raises_user_fetch_error() -> None:
    from person_finder.users import UserFetchError, fetch_user_names

    with patch("person_finder.users.urlopen", return_value=io.BytesIO(b"{not json")):
        with pytest.raises(UserFetchError):
            fetch_user_names()


def test_missing_results_key_raises_user_fetch_error() -> None:
    from person_finder.users import UserFetchError, fetch_user_names

    with patch("person_finder.users.urlopen", return_value=io.BytesIO(b'{"info":{}}')):
        with pytest.raises(UserFetchError):
            fetch_user_names()


def test_record_missing_dob_date_raises_user_fetch_error() -> None:
    bad_record = {"name": {"first": "No", "last": "Date"}, "dob": {"age": 30}}

    from person_finder.users import UserFetchError, fetch_user_names

    with patch("person_finder.users.urlopen", return_value=_body([bad_record])):
        with pytest.raises(UserFetchError):
            fetch_user_names()


def test_empty_results_returns_empty_list_not_error() -> None:
    from person_finder.users import fetch_user_names

    with patch("person_finder.users.urlopen", return_value=_body([])):
        assert fetch_user_names() == []


def test_record_missing_name_first_raises_user_fetch_error() -> None:
    bad_record = {
        "name": {"last": "OnlyLast"},
        "dob": {"date": "1990-01-01T00:00:00.000Z", "age": 35},
    }

    from person_finder.users import UserFetchError, fetch_user_names

    with patch("person_finder.users.urlopen", return_value=_body([bad_record])):
        with pytest.raises(UserFetchError):
            fetch_user_names()

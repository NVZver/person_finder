"""Unit tests for `person_finder.users`.

Covers Epic 2 AC: fetch 20 randomuser records, drop year-of-birth > 2000,
return `list[str]` of `"First Last"` in API response order.

External HTTP is mocked via `httpx.MockTransport` injected through the
function's optional `client` parameter — no real network calls.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest


def _record(first: str, last: str, year: int, month: int = 6, day: int = 15) -> dict[str, Any]:
    """Build one randomuser-shaped record with a controllable DOB year."""
    iso = f"{year:04d}-{month:02d}-{day:02d}T08:30:00.000Z"
    return {
        "name": {"title": "Mr", "first": first, "last": last},
        "dob": {"date": iso, "age": 2026 - year},
    }


def _payload(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {"results": records, "info": {"seed": "x", "results": len(records), "page": 1, "version": "1.4"}}


def _client_returning(handler) -> httpx.Client:
    """Build an httpx.Client whose transport is the supplied handler."""
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_happy_path_mixed_years_returns_filtered_subset_in_order() -> None:
    """20 records, mixed DOB years; only those born <= 2000 are kept, in order."""
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

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json=_payload(records))

    from person_finder.users import fetch_user_names

    with _client_returning(handler) as client:
        names = fetch_user_names(client=client)

    assert names == [
        "Adam Smith",
        "Cara Lopez",
        "Eve Park",
        "Finn Ng",
        "Hal Vasquez",
        "Jon Doe",
        "Kim Liu",
        "Mae Ito",
        "Ola Mak",
        "Pat Cruz",
        "Rae Khan",
        "Tia West",
    ]
    assert captured["url"] == "https://randomuser.me/api/?results=20"


def test_all_born_after_2000_returns_empty_list() -> None:
    records = [_record(f"P{i}", f"L{i}", 2001 + (i % 5)) for i in range(20)]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_payload(records))

    from person_finder.users import fetch_user_names

    with _client_returning(handler) as client:
        names = fetch_user_names(client=client)

    assert names == []


def test_all_born_2000_or_earlier_returns_all_twenty_in_order() -> None:
    records = [_record(f"First{i}", f"Last{i}", 1950 + i) for i in range(20)]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_payload(records))

    from person_finder.users import fetch_user_names

    with _client_returning(handler) as client:
        names = fetch_user_names(client=client)

    assert names == [f"First{i} Last{i}" for i in range(20)]


def test_boundary_year_2000_is_kept() -> None:
    """Spec: drop *after* 2000 → year == 2000 is retained."""
    records = [_record("Boundary", "Person", 2000)]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_payload(records))

    from person_finder.users import fetch_user_names

    with _client_returning(handler) as client:
        names = fetch_user_names(client=client)

    assert names == ["Boundary Person"]


def test_non_200_response_raises_user_fetch_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    from person_finder.users import UserFetchError, fetch_user_names

    with _client_returning(handler) as client:
        with pytest.raises(UserFetchError) as exc_info:
            fetch_user_names(client=client)

    assert "503" in str(exc_info.value)


def test_malformed_json_body_raises_user_fetch_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"{not json")

    from person_finder.users import UserFetchError, fetch_user_names

    with _client_returning(handler) as client:
        with pytest.raises(UserFetchError):
            fetch_user_names(client=client)


def test_missing_results_key_raises_user_fetch_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"info": {}})

    from person_finder.users import UserFetchError, fetch_user_names

    with _client_returning(handler) as client:
        with pytest.raises(UserFetchError):
            fetch_user_names(client=client)


def test_record_missing_dob_date_raises_user_fetch_error() -> None:
    bad_record = {
        "name": {"first": "No", "last": "Date"},
        "dob": {"age": 30},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_payload([bad_record]))

    from person_finder.users import UserFetchError, fetch_user_names

    with _client_returning(handler) as client:
        with pytest.raises(UserFetchError):
            fetch_user_names(client=client)


def test_empty_results_returns_empty_list_not_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_payload([]))

    from person_finder.users import fetch_user_names

    with _client_returning(handler) as client:
        names = fetch_user_names(client=client)

    assert names == []


def test_record_missing_name_first_raises_user_fetch_error() -> None:
    bad_record = {
        "name": {"last": "OnlyLast"},
        "dob": {"date": "1990-01-01T00:00:00.000Z", "age": 35},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_payload([bad_record]))

    from person_finder.users import UserFetchError, fetch_user_names

    with _client_returning(handler) as client:
        with pytest.raises(UserFetchError):
            fetch_user_names(client=client)


def test_uses_default_url_when_no_client_constructed_internally(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no client is injected, the function builds one and hits the canonical URL."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json=_payload([_record("Solo", "Run", 1990)]))

    # Patch the module-level httpx.Client so the internal `with httpx.Client(...)`
    # path uses our MockTransport without us injecting a client.
    import person_finder.users as users_mod

    real_client = httpx.Client

    def fake_client(*args: Any, **kwargs: Any) -> httpx.Client:
        return real_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(users_mod.httpx, "Client", fake_client)

    names = users_mod.fetch_user_names()
    assert names == ["Solo Run"]
    assert captured["url"] == "https://randomuser.me/api/?results=20"

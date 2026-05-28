# Users Module — Spec

## Purpose

Fetch a fixed batch of random user records, drop anyone born after 2000, and return the remaining names as `list[str]` of `"First Last"` so the agent layer (Epics 3-5) has a clean name list to enrich without re-implementing HTTP, JSON parsing, or DOB filtering per call site.

Pitch source: [ARCHITECTURE.md](../../../ARCHITECTURE.md) §Layers/1 lines 19-22, §Data flow lines 58-66, §Tests/Unit lines 83-90.
Epic: [roadmap.md](../../roadmap.md) row 2 (`Random-user fetch + filter + name mapping`, MVP).

## Scope (artifact paths)

- `src/person_finder/users.py`
- `tests/unit/test_users.py`

## Functional requirements

- **F1 — Public surface.** `src/person_finder/users.py` exposes one public function `fetch_user_names(client: httpx.Client | None = None) -> list[str]` and one public error class `UserFetchError(RuntimeError)`. All other names are private (`_`-prefixed).
- **F2 — Fixed endpoint, fixed batch size.** The function fetches from `https://randomuser.me/api/?results=20` (module-level constant `RANDOMUSER_URL`). The `results=20` query is hard-coded by design — batch size is part of the spec, not a parameter.
- **F3 — DOB filter.** Records whose `dob.date` ISO-8601 year-of-birth is strictly greater than 2000 are dropped. Year == 2000 is retained.
- **F4 — Name mapping.** Surviving records are mapped to `f"{name.first} {name.last}"`. API response order is preserved. An empty list is a legal return value.
- **F5 — Client injection.** The optional `client` parameter accepts a pre-built `httpx.Client` so unit tests can inject `httpx.MockTransport`. When omitted, the function constructs a short-lived `httpx.Client` with a 10-second timeout via `with httpx.Client(timeout=10.0) as ...`.

## Non-functional requirements / invariants

- **NF1 — Typed error contract.** Every failure mode raises `UserFetchError` (subclass of `RuntimeError`) with `raise ... from exc` preserving the underlying cause. Callers MUST NOT need to catch `httpx.*` directly. Failure modes covered: transport error, non-200 status, non-JSON body, payload missing `results` key, `results` is not a list, record missing/malformed `dob.date`, record missing `name.first` / `name.last`.
- **NF2 — No retries this epic.** No retry loop, no rate-limiting, no caching. Deferred to later epics (the agent/render layer in Epic 5 maps `UserFetchError` to the user-facing `Error("Could not respond")` flow).
- **NF3 — HTTP client: `httpx`.** Runtime dependency `httpx>=0.27,<1`. Chosen over `requests` for sync+async unification and first-class transport mocking via `httpx.MockTransport`.
- **NF4 — Agent-layer-agnostic.** The module is HTTP-shape-aware but does not import or reference LangChain, Groq, or the agent layer. The typed `UserFetchError` is the only contract the agent/render layer in Epic 5 consumes — no `httpx` types leak across the module boundary.
- **NF5 — Mocked HTTP in unit tests.** `tests/unit/test_users.py` MUST use `httpx.MockTransport` (or equivalent transport-level mock) injected via the `client` parameter. No real network calls. Aligns with `ARCHITECTURE.md` §Tests/Unit ("all external calls mocked").
- **NF6 — Side-effect-free import.** `import person_finder.users` MUST NOT make HTTP calls, read disk, or raise. Network I/O happens only on `fetch_user_names()` invocation.

## Acceptance criteria

- **AC1** — Given a mocked 200 response with 20 records of mixed DOB years, `fetch_user_names` returns a `list[str]` of `"First Last"` containing exactly the records whose `dob.date` year ≤ 2000, in API order. Verified by `test_happy_path_mixed_years_returns_filtered_subset_in_order`.
- **AC2** — Boundary year 2000 is retained (filter is strict `> 2000`, not `>= 2000`). Verified by `test_boundary_year_2000_is_kept`.
- **AC3** — All NF1 failure modes raise `UserFetchError`. Verified by `test_non_200_response_raises_user_fetch_error`, `test_malformed_json_body_raises_user_fetch_error`, `test_missing_results_key_raises_user_fetch_error`, `test_record_missing_dob_date_raises_user_fetch_error`, `test_record_missing_name_first_raises_user_fetch_error`.
- **AC4** — All-young-cohort and all-old-cohort edge cases. All born > 2000 → `[]`; all born ≤ 2000 → all 20 returned in order. Verified by `test_all_born_after_2000_returns_empty_list`, `test_all_born_2000_or_earlier_returns_all_twenty_in_order`.
- **AC5** — Empty `results` list returns `[]` without error. Verified by `test_empty_results_returns_empty_list_not_error`.
- **AC6** — Default-client path (no injected client) hits the canonical URL. Verified by `test_uses_default_url_when_no_client_constructed_internally`.

## Open questions / follow-ups

| # | Question | Source |
|---|---|---|
| OQ1 | Retry / backoff policy on transient HTTP errors — deferred per NF2; revisit when Epic 5 wires user-facing error surfacing. | Module spec NF2. |
| OQ2 | Configurable batch size (currently hard-coded `results=20`). Architecture lock-in or future-proofing? | Module spec F2; revisit if downstream code needs a variable cohort. |
| OQ3 | `pyproject.toml` and `uv.lock` are listed under `scaffolding` artifact_paths but receive contributions from any module that adds a runtime dep (this module added `httpx`). Cross-module ownership is implicit; not currently formalized. | Reconcile sweep on Epic 2 ship. |

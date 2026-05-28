# Validation Module — Spec

## Purpose

Provide the `validation` module: a stdlib-only, LLM-free validator that parses the LangChain agent's raw final-message content, asserts the cross-module JSON schema (`{"data": [{"person": str, "info": str}, ...]}`), and on failure drives a bounded LLM-repair retry loop via a caller-supplied `repair_fn`. The module returns the validated dict on success or raises the spec-mandated `Error("Could not respond")` on repair-budget exhaustion — surfacing concerns (calling the agent, formatting the repair prompt, rendering output) are out of scope and owned by the upcoming `render` module (Epic 5).

Pitch source: [ARCHITECTURE.md](../../../ARCHITECTURE.md) §Layers/2 (`validate_output` bullet, lines 41-48).
Epic: [roadmap.md](../../roadmap.md) row 4 (`validate_output + repair retry loop`, MVP).
Inherited contracts: [main.spec.md](../../main.spec.md) §Cross-Module Contracts (enrichment-result shape; `Error("Could not respond")` failure signal at line 22).

## Scope (artifact paths)

- `src/person_finder/validation.py`
- `tests/unit/test_validation.py`
- `specs/modules/validation/spec.md` (this file)

## Functional requirements

- **F1 — Public entry point.** The module exposes `validate_output(raw: str, repair_fn: Callable[[str, str], str] | None = None) -> dict[str, Any]`. It parses `raw` as JSON, asserts the cross-module schema, and on failure invokes `repair_fn(broken_raw, error_msg)` up to `MAX_REPAIRS` times before raising `Error("Could not respond")`.
- **F2 — Schema check.** The validator asserts (a) top-level is a `dict`, (b) it contains key `"data"`, (c) `payload["data"]` is a `list`, (d) every `data[i]` is a `dict` with both `"person": str` and `"info": str`. An empty `data` list is valid (per [ARCHITECTURE.md:41-48](../../../ARCHITECTURE.md) — the constitution requires per-item shape, not per-list non-emptiness).
- **F3 — Repair retry budget.** `MAX_REPAIRS = 3` (per [ARCHITECTURE.md:46](../../../ARCHITECTURE.md) "Max retries: 3"). Counted as 3 *repair attempts after the initial parse*, i.e. up to 4 total candidate strings validated.
- **F4 — Repair callable contract.** `repair_fn(broken_raw: str, error_msg: str) -> str`. First arg is the LLM's last bad output verbatim; second arg is the precise failure description (e.g. `'JSON parse error: Expecting value'` or `'data[2].info is not a str — got int'`). The caller (Epic 5 `render`) is responsible for formatting these into an actual repair user-message and calling the LLM.
- **F5 — Failure signal.** On repair exhaustion (or initial failure when `repair_fn is None`), the module raises `Error("Could not respond")` — a module-local `Exception` subclass whose name matches [main.spec.md §Cross-Module Contracts](../../main.spec.md) line 22 literally. The precise underlying diagnostic is preserved via `__cause__`.
- **F6 — Defensive repair output.** A non-`str` return from `repair_fn` (e.g. `None`) is treated as a normal validation failure (counts against the budget), not a `TypeError` crash.

## Non-functional requirements / invariants

- **NF1 — Stdlib only.** Implementation uses only `json`, `collections.abc`, and `typing` from the stdlib. No new third-party dependencies in `pyproject.toml`.
- **NF2 — No LLM coupling.** The module does NOT import `person_finder.agent`, `langchain`, `langchain_groq`, or `groq`. The LLM dependency is injected via `repair_fn`. (Inherits the project's hexagonal-style boundary: pure code in `validation.py`; orchestration glue in Epic 5's `render` module.)
- **NF3 — Side-effect-free import.** `import person_finder.validation` MUST NOT read env, read disk, or raise. Verified by `test_import_has_no_side_effects` in `tests/unit/test_validation.py` (mirrors [agent/spec.md](../agent/spec.md) NF2).
- **NF4 — Fully mocked unit tier.** Unit tests in `tests/unit/test_validation.py` substitute `repair_fn` with plain Python callables. No real LLM call may originate from the unit tier. (Per [testing.md](../../standards/testing.md) §Unit.)
- **NF5 — `Error` name discipline.** The exception class is named `Error` per [main.spec.md:22](../../main.spec.md) literally. Callers MUST import it explicitly (`from person_finder.validation import Error`) rather than via star-import to avoid namespace pollution. Documented in the module docstring.

## Acceptance criteria

- **AC1** — When `validate_output(raw)` is called with a string that parses to `{"data": [{"person": str, "info": str}, ...]}`, the system returns the parsed dict and does NOT invoke `repair_fn`. Currently verified by `test_valid_json_returns_parsed_dict_without_calling_repair` and `test_empty_data_list_is_valid` in `tests/unit/test_validation.py`.
- **AC2** — When `validate_output(broken, repair_fn=fixer)` is called and `fixer` returns valid JSON on first call, the system returns the parsed dict and `fixer` has been called exactly once with `(broken_raw, error_msg)`. Currently verified by `test_broken_then_repaired_returns_dict_and_calls_repair_once`.
- **AC3** — When `validate_output(initial_broken, repair_fn=always_broken)` is called and `always_broken` returns malformed output every time, the system raises `Error("Could not respond")` after exactly 3 calls to `always_broken`. Currently verified by `test_always_broken_repair_exhausts_after_three_calls`.
- **AC4** — When `validate_output(initial_broken)` is called with no `repair_fn`, the system raises `Error("Could not respond")` immediately (zero repair calls). Currently verified by `test_no_repair_fn_raises_immediately`.
- **AC5** — Each failure mode (JSON parse error; top-level not dict; missing `"data"` key; `data` not list; `data[i]` not dict; missing `"person"` / `"info"` key; non-str `"person"` / `"info"`) yields a precise diagnostic on the raised `Error`'s `__cause__`. Currently verified by the parametrized `test_precise_error_message_in_cause` (9 cases) plus `test_repair_fn_returning_non_str_is_a_validation_failure` for the defensive non-str case.
- **AC6** — `make test-unit` exits 0 with no regressions in `test_config.py` or `test_agent.py`. Currently 28 passing tests (6 config + 5 agent + 17 validation).

## Open questions / follow-ups

| # | Question | Source |
|---|---|---|
| OQ1 | Whether the repair-prompt formatting (turning `error_msg` into a user-facing system prompt) should live in `validation.py` as a helper or in Epic 5's `render` module. Currently deferred: validation just exposes `error_msg`. | F4 boundary. |
| OQ2 | Whether `Error("Could not respond")` should optionally carry the last broken raw for user-facing diagnostics, or stay terse per the literal contract. | NF5 / [main.spec.md:22](../../main.spec.md). |
| OQ3 | Whether to expose `_ValidationFailure` publicly so callers can pattern-match on subtypes (parse error vs shape error). Currently private; `__cause__` inspection works for tests. | Design Brief trade-off. |

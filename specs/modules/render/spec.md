# Render Module — Spec

## Purpose

Provide the `render` module: a stdlib-only top-level CLI entrypoint that wires the upstream modules (`users` fetch → `agent` enrich → `validation` validate-with-repair) into the user-facing surface described by [ARCHITECTURE.md](../../../ARCHITECTURE.md) §Layers/1 lines 23-24, §Data flow. On success, the validated `{"data": [...]}` payload is pretty-printed to stdout and the process exits 0. On either of the two named cross-module failure classes — `validation.Error("Could not respond")` (repair budget exhausted) and `users.UserFetchError` (upstream HTTP / parse failure) — the entrypoint prints a single user-facing retry message to stderr (no traceback, no exception class name leak) and exits non-zero. Implementing the LLM repair callable, the HTTP fetch, and the JSON validator is out of scope and owned by the `agent` / `users` / `validation` modules respectively.

Pitch source: [ARCHITECTURE.md](../../../ARCHITECTURE.md) §Layers/1 lines 23-24, §Data flow, §Tests/E2E.
Epic: [roadmap.md](../../roadmap.md) row 5 (`Python render + error surfacing + e2e wiring`, MVP).
Inherited contracts: [main.spec.md](../../main.spec.md) §Cross-Module Contracts (enrichment-result shape at line 24; `Error("Could not respond")` failure signal at line 26).

## Scope (artifact paths)

- `src/person_finder/render.py`
- `src/person_finder/__main__.py`
- `tests/unit/test_render.py`
- `tests/e2e/__init__.py`
- `tests/e2e/conftest.py`
- `tests/e2e/test_pipeline.py`
- `specs/modules/render/spec.md` (this file)

## Functional requirements

- **F1 — Public CLI entry point.** The module exposes `main() -> None` which runs the full pipeline and either prints the validated payload + `sys.exit(0)`, or surfaces the user-facing retry message + `sys.exit(<non-zero>)`. All other names are private (`_`-prefixed) except `USER_FACING_RETRY_MESSAGE` (the literal stderr string, exposed for test assertions).
- **F2 — `python -m person_finder` shim.** `src/person_finder/__main__.py` is a one-liner that imports `main` from `render` and calls it under `if __name__ == "__main__":`. No business logic lives in `__main__.py`.
- **F3 — Pipeline composition.** `_run()` invokes, in order: `users.fetch_user_names()` → `agent.enrich_names(names)` → `validation.validate_output(raw, repair_fn=agent.repair)`. The success return is the parsed dict from `validate_output`.
- **F4 — Real repair callable, never `None`.** `validate_output` is invoked with `repair_fn=agent.repair` (re-exported as the private alias `_repair`). Passing `repair_fn=None` would short-circuit Epic 4's repair retry loop and is a regression. (Pins [validation/spec.md F4](../validation/spec.md) from the caller side.)
- **F5 — Output rendering.** Success branch prints `json.dumps(payload, indent=2)` to stdout with `flush=True`, then `sys.exit(0)`. Pretty-print is chosen for human terminal readability; downstream consumers pipe through `jq -c` if compact is wanted.
- **F6 — Failure-class catch list.** The entrypoint catches exactly `(validation.Error, users.UserFetchError)` — the two cross-module failure classes from [main.spec.md §Cross-Module Contracts](../../main.spec.md). Every other exception propagates uncaught (the suppressed-traceback policy applies only to the named user-facing classes).
- **F7 — User-facing error literal.** `USER_FACING_RETRY_MESSAGE = "Could not respond — please try again later."` is the single string emitted on stderr for both caught failure classes. It carries no Python exception class name, no upstream HTTP status code, and no `__cause__` text. The chained `__cause__` is preserved on the exception (for any future debug-flag epic) but not rendered.

## Non-functional requirements / invariants

- **NF1 — Side-effect-free import.** `import person_finder.render` MUST NOT read env, read disk, make HTTP calls, construct LLM clients, or raise. Collaborators are imported, but pipeline execution and model construction happen only inside `main()` / `_run()`. Mirrors [agent/spec.md NF2](../agent/spec.md) and [validation/spec.md NF3](../validation/spec.md). Verified by a subprocess-based `test_import_has_no_side_effects` in `tests/unit/test_render.py`.
- **NF2 — Stdlib rendering.** Output rendering uses only `json` and `sys` from the stdlib. No new third-party dependencies in `pyproject.toml`.
- **NF3 — Fully mocked unit tier.** Unit tests in `tests/unit/test_render.py` substitute `users.fetch_user_names`, `agent.enrich_names`, and `validation.validate_output` (and where needed `agent.repair`) via `monkeypatch.setattr` against the imported names in the `render` namespace. No real HTTP, no real LLM call may originate from the unit tier. (Per [testing.md](../../standards/testing.md) §Unit.)
- **NF4 — E2E uses subprocess + captured-keys conftest.** `tests/e2e/test_pipeline.py` invokes `uv run python -m person_finder` via `subprocess.run`, capturing stdout/stderr/exit-code. In-process `render.main()` would not exercise the actual CLI surface (`sys.exit`, stdout-vs-stderr, module-discovery). The autouse `_restore_real_keys_for_e2e` fixture in `tests/e2e/conftest.py` re-emits the host shell's `GROQ_API_KEY` / `GOOGLE_API_KEY` AFTER the root `_isolate_env` autouse fixture has stripped them — captured at conftest-import time so unit isolation is preserved while e2e can still reach Groq.
- **NF5 — Suppressed-traceback policy is bounded.** The `except (Error, UserFetchError)` block is the only place Python's default traceback is suppressed. `repair_fn` raising mid-repair (network blip on the repair LLM call) propagates as a normal traceback because Epic 5 only contracts catching the two named classes. Expanding the suppressed surface is an explicit decision, not a default.

## Acceptance criteria

- **AC1** — Running `python -m person_finder` against working APIs prints a parseable JSON document to stdout with the cross-module shape (`{"data": [{"person": str, "info": str}, ...]}`) and exits 0. Currently verified by `test_python_module_run_returns_validated_json` in `tests/e2e/test_pipeline.py` (subprocess against real services; skips cleanly when `GROQ_API_KEY` is unset).
- **AC2** — When `validation.validate_output` raises `validation.Error("Could not respond")`, `main()` prints `USER_FACING_RETRY_MESSAGE` to stderr (containing the literal `"Could not respond"` and a retry hint), prints nothing to stdout, exits with a non-zero code, and does not surface a Python traceback. Currently verified by `test_main_handles_validation_error_with_user_message_and_nonzero_exit` in `tests/unit/test_render.py`.
- **AC3** — When `users.fetch_user_names` raises `users.UserFetchError`, `main()` prints the same `USER_FACING_RETRY_MESSAGE` to stderr (no `httpx` text, no HTTP status code), prints nothing to stdout, exits non-zero, and does not surface a Python traceback. Currently verified by `test_main_handles_user_fetch_error_with_same_user_message` in `tests/unit/test_render.py`.
- **AC4** — `_run()` invokes `validate_output(raw, repair_fn=<callable>)` with a real callable, not `None`. Currently verified by `test_main_passes_callable_repair_fn_to_validate_output` in `tests/unit/test_render.py`, which spies the `repair_fn` kwarg and asserts `callable(...)`.
- **AC5** — When `fetch_user_names()` returns `[]`, the pipeline completes cleanly with a `{"data": []}` payload printed to stdout and exit 0 (no short-circuit, no error). Currently verified by `test_main_with_empty_names_prints_empty_data_payload`.
- **AC6** — `import person_finder.render` in a fresh interpreter (no env vars, empty cwd) returns without raising, with no traceback on stderr. Currently verified by the subprocess-based `test_import_has_no_side_effects` in `tests/unit/test_render.py`.
- **AC7** — Happy-path success branch prints `json.dumps(payload, indent=2)` to stdout and exits 0; stderr stays empty. Currently verified by `test_main_success_prints_json_and_exits_zero`.
- **AC8** — `make test-unit` exits 0 with no regressions in `test_config.py`, `test_users.py`, `test_agent.py`, or `test_validation.py`. `make test-e2e` exits 0 (either runs `test_pipeline.py` successfully against real services OR skips it with a precise reason when `GROQ_API_KEY` is unset).

## Open questions / follow-ups

| # | Question | Source |
|---|---|---|
| OQ1 | Debug-flag environment variable (e.g. `PERSON_FINDER_DEBUG=1`) that re-raises after printing the user-facing message, so the chained `__cause__` becomes visible during development. Currently `__cause__` is preserved on the suppressed exception but never rendered. | Developer agent design-brief follow-up. |
| OQ2 | Whether `repair_fn` raising mid-repair (e.g. network blip on the repair LLM call) should be added to the suppressed-traceback surface, so the user never sees a traceback regardless of which pipeline step failed. NF5 currently bounds the policy to the two named classes. | F6 / NF5 boundary. |
| OQ3 | Per-CLI-invocation `agent.repair` calls `_default_model()` afresh on each invocation (up to 3× per CLI run on the unhappy path). Pre-constructing one model in `render._run` and closure-passing it into `validate_output` would amortize the construction cost, but the validation module's `repair_fn` signature `(broken_raw, error_msg) -> str` would have to be wrapped inline. Acceptable as-is; revisit if construction cost becomes meaningful. | Developer agent trade-off #6. |
| OQ4 | `tests/e2e/test_pipeline.py` hands the child a placeholder `GOOGLE_API_KEY` to satisfy `config.Settings` even though render doesn't consult it. If `config.Settings` ever decouples the judge key from the agent key, the placeholder can go. | NF — config inheritance. |

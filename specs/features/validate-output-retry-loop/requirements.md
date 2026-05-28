# Feature: `validate_output` + repair retry loop (Epic 4)

## Summary

Add a code-only validation module at `src/person_finder/validation.py` that asserts the LangChain agent's JSON output matches the cross-module contract from `main.spec.md:20` (`{"data": [{"person": str, "info": str}, ...]}`), invokes a caller-supplied `repair_fn` up to 3 times on failure, and raises the spec-mandated `Error("Could not respond")` on exhaustion. The module does NOT import the agent — Epic 5 (`render`) supplies `repair_fn` as a closure over the agent so validation stays unit-testable without a live LLM.

Sources: [ARCHITECTURE.md](../../../ARCHITECTURE.md) §Layers/2 lines 41-48 (check list + retry cap + error string); [main.spec.md](../../main.spec.md) §Cross-Module Contracts lines 17-23 (error signal); [code.md](../../standards/code.md) §Validation & retry lines 29-34; [testing.md](../../standards/testing.md) §Unit lines 17-19 (mocked external calls). Roadmap: [roadmap.md](../../roadmap.md) row 4.

## Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| F1 | The module `src/person_finder/validation.py` exposes a public function `validate_output(raw: str, repair_fn: Callable[[str, str], str] \| None = None) -> dict[str, Any]` plus a public exception class `Error(Exception)` whose single argument is the literal `"Could not respond"`. | Must |
| F2 | `validate_output` parses `raw` as JSON via stdlib `json.loads`, then asserts the top-level value is a `dict` containing a `"data"` key whose value is a `list`. Each list item must be a `dict` with `person: str` and `info: str` keys; both values must be `str` instances. | Must |
| F3 | When the parse-or-shape check fails AND `repair_fn` is not None, `validate_output` calls `repair_fn(broken_raw: str, error_msg: str) -> str` and retries validation on the returned string. Maximum 3 repair attempts (1 initial attempt + up to 3 repairs = 4 candidate strings evaluated total). | Must |
| F4 | When `repair_fn` is None and the initial check fails, OR when the 3rd repair attempt also fails, `validate_output` raises `Error("Could not respond")`. The underlying precise diagnostic is preserved on `__cause__` via `raise Error(...) from last_failure`. | Must |
| F5 | `error_msg` (the second arg `repair_fn` receives) names the specific violation with index/key context: e.g. `"JSON parse error: ..."`, `"missing \"data\" key at top level"`, `"data[2].info is not a str — got int"`. Reused by `_check_shape` so the message wording is single-source. | Must |
| F6 | The module is code-only and **does NOT import the agent** (`person_finder.agent`) or any LangChain / Groq / network dependency. Imports are limited to stdlib (`json`, `collections.abc.Callable`, `typing.Any | Final`). | Must |
| F7 | The spec graph is wired: new `specs/modules/validation/spec.md` is created and linked from `specs/main.spec.md` §Module Index; `.lsa.yaml` gains a `validation:` entry under `modules:` with `spec` + `artifact_paths`. | Must |

## Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NF1 | **No new runtime dependencies.** `pyproject.toml` and `uv.lock` MUST NOT be modified by this feature. stdlib `json` only. |
| NF2 | **Side-effect-free imports.** `import person_finder.validation` MUST NOT read env, touch disk, make HTTP calls, or raise. Verified via a fresh-subprocess test (`test_import_has_no_side_effects`). |
| NF3 | **Defensive against non-str `repair_fn` output.** If `repair_fn` returns a non-string by mistake, the result MUST be counted as a normal validation failure (burn one budget unit), NOT crash with `TypeError`. |
| NF4 | **Unit-tested with mocked `repair_fn` only.** No live Groq / LangChain / Gemini calls in any validation test. Tests count invocations via local `list[...]` or `nonlocal int`. |
| NF5 | **Other tiers stay green.** `make test-unit` exits 0 with the existing test count (5 agent + 6 config = 11) plus the new validation tests. `make test-eval` and `make test-e2e` are unaffected. |
| NF6 | **Cross-module symbol shadowing documented.** `Error` is the spec-mandated name (`main.spec.md:22`). Python has no builtin `Error` so nothing is actually shadowed, but the module docstring explicitly warns against `from person_finder.validation import *` and instructs callers to import `Error` explicitly. |

## Inputs & Outputs

- **Input (`raw`):** A `str` — typically the raw final-message content from `person_finder.agent.enrich_names()`, per the agent's `SYSTEM_PROMPT` instructing JSON-only output.
- **Input (`repair_fn`):** Optional callable `(broken_raw: str, error_msg: str) -> str`. Caller-owned; Epic 5 supplies the actual closure-over-agent.
- **Output (success):** The parsed `dict` (e.g. `{"data": [{"person": "Ada", "info": "..."}]}`).
- **Output (failure):** Raises `Error("Could not respond")` with `__cause__` chained to the last `_ValidationFailure`.
- **Side effects:** None within the module. `repair_fn` may have side effects; validation does not.

## Constraints

- [ARCHITECTURE.md §Layers/2](../../../ARCHITECTURE.md) lines 41-48 fixes the check list, retry cap, and error string. This feature does not invent new checks; it operationalizes those four.
- [main.spec.md §Cross-Module Contracts](../../main.spec.md) line 22 fixes the error name + string. The exception class is named `Error` per spec letter.
- [code.md §Validation & retry](../../standards/code.md) lines 29-34 mirror the same contract; this spec implements it.

## Out of Scope

- Implementing the Python render layer that wires agent → validation → user output (Epic 5).
- Implementing the random-user fetch (Epic 2, still on PR #1).
- Live-agent integration tests for the repair loop (deferred to Epic 5's E2E tier).
- A standalone `repair_fn` closure or any agent-specific repair prompt — Epic 5 owns the wiring.
- `info` non-emptiness or sentinel-only enforcement (the eval suite's job; Epic 6 on PR #3).

## Acceptance Criteria

<!-- EARS-form per vision/VISION.md:201; user/system boundary per VISION.md §2 sub-principle 2a. -->

- [ ] **AC1** — When `validate_output(raw)` receives a valid JSON-shaped `raw` matching the contract, the function shall return the parsed `dict` and shall NOT invoke `repair_fn`. *(Ubiquitous)*
- [ ] **AC2** — When `repair_fn` is supplied and the first repair attempt returns valid JSON, `validate_output` shall return the parsed `dict` after calling `repair_fn` exactly once. *(Event)*
- [ ] **AC3** — When `repair_fn` returns malformed output every time, `validate_output` shall raise `Error("Could not respond")` after calling `repair_fn` exactly 3 times (the retry cap). *(Event)*
- [ ] **AC4** — When `repair_fn` is `None` (or omitted) and `raw` fails validation, `validate_output` shall immediately raise `Error("Could not respond")` without any repair calls. *(Event)*
- [ ] **AC5** — For each documented failure mode (malformed JSON, top-level not dict, missing `data` key, `data` not list, `data[i]` not dict, missing `person` / `info` key, `person` / `info` not str), the `error_msg` argument that `repair_fn` receives shall contain a substring naming the specific violation with index/key context. (The chained `__cause__` on the raised `Error` carries the same string by construction, but the public contract is what `repair_fn` sees.) *(Ubiquitous)*
- [ ] **AC6** — `make test-unit` shall exit 0 with all existing tests still green (11 pre-existing — 5 `test_agent.py` + 6 `test_config.py`) plus the new validation tests. `make test-eval` and `make test-e2e` shall remain unaffected. *(Ubiquitous)*
- [ ] **AC7** — `specs/main.spec.md` §Module Index shall list `validation` with a working link, and `.lsa.yaml` shall declare `validation` under `modules:` with `artifact_paths` covering `src/person_finder/validation.py` and `tests/unit/test_validation.py`. *(Ubiquitous)*

## Open Questions

| # | Question | Source |
|---|---|---|
| OQ1 | Should the `agent` module also be added to `main.spec.md` §Module Index here? Epic 3 merged at `659fca7` without doing it. Fix-it-forward acceptable (developer agent already did so) — flagged for explicit confirmation at verify. | Cross-epic hygiene. |
| OQ2 | Should `validate_output` accept the `raw` as `str | bytes` for parity with `json.loads`? Currently `str`-only; widening is a trivial follow-up if Epic 5 surfaces a `bytes` source. | Deferred to Epic 5. |
| OQ3 | Should the retry budget be configurable (e.g. `MAX_REPAIRS` param)? Currently a module-level `Final[int] = 3` per spec letter. Configurable would weaken the spec contract; defer until a real use case appears. | Deferred. |

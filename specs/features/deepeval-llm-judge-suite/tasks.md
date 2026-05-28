# Tasks: DeepEval LLM-Judge Eval Suite (Epic 6)

## Epic Overview

| Epic | Branch | Status | Dependency |
|------|--------|--------|------------|
| E1: Deps + `tests/eval/` scaffolding | `feature/deepeval-llm-judge-suite-e1` | pending | none |
| E2: Deterministic metrics + AC4 stub coverage | `feature/deepeval-llm-judge-suite-e2` | pending | E1 (DeepEval must be importable) |
| E3: Live-agent eval tests (skip-when-absent) | `feature/deepeval-llm-judge-suite-e3` | pending | E1 (fixtures), E2 (metric classes) |
| E4: Spec graph wiring | `feature/deepeval-llm-judge-suite-e4` | pending | none (parallel-safe with E1–E3) |

All four epics merge into `feature/deepeval-llm-judge-suite`. Final PR targets `main`.

---

## Epic 1: Deps + `tests/eval/` scaffolding

### Description
Add the DeepEval + Google SDK dev dependencies to `pyproject.toml`, create the `tests/eval/` directory with `__init__.py`, and author `tests/eval/conftest.py` with the three shared fixtures (`real_keys`, `judge_configured`, `agent_under_test`) and the test-isolation override that re-introduces real API keys for eval tests without weakening unit-test isolation.

### Scope
- Files/modules touched: `pyproject.toml`, `uv.lock` (regenerated), `tests/eval/__init__.py` (new, empty), `tests/eval/conftest.py` (new).
- Creates: `tests/eval/__init__.py`, `tests/eval/conftest.py`.
- Modifies: `pyproject.toml`, `uv.lock`.
- Does NOT touch: `src/person_finder/**`, `tests/unit/**`, `tests/e2e/**`, `tests/conftest.py`, any spec file.

**Covers:** F1 (partial — scaffolding only), F3 (judge configured Gemini 2.0 Flash), F4 (lazy-import fixture), F5 (`PUBLIC_FIGURES` roster constant), NF1 (cost envelope — fixture limits LLM calls), NF2 (isolation override), NF3 (dependency additions), NF4 (side-effect-free imports), NF5 (tier independence — `make test-unit` + `make test-e2e` byte-identical), NF6 (skip-with-reason discipline), AC5 (other tiers byte-identical). Foundation for AC1, AC2, AC3.

### Technical Details
- Add to `pyproject.toml` `[dependency-groups] dev`: `deepeval>=2,<3` (pin minor at install time against actually-installed version), `google-generativeai>=0.8`. Rationale per `design.md` §"Dependency Additions": both deps are dev-only, not application runtime.
- `tests/eval/__init__.py`: empty marker file (mirrors `tests/unit/__init__.py`).
- `tests/eval/conftest.py` provides:
  - `_REAL_KEYS = (os.environ.get("GROQ_API_KEY"), os.environ.get("GOOGLE_API_KEY"))` captured at module import time (BEFORE the root autouse fixture strips them).
  - Session-scoped `real_keys` fixture exposing those two captured values as a typed object.
  - Autouse function-scoped fixture inside `tests/eval/` that re-emits the captured keys via `monkeypatch.setenv` AFTER the root autouse fixture has stripped them — pytest fixture ordering: same-scope autouse fixtures resolve in collection order, and the root fixture is in `tests/conftest.py` (higher up the tree, runs first per pytest docs).
  - `judge_configured` session-scoped fixture: if `GOOGLE_API_KEY` is present, call DeepEval's `set_evaluation_model(...)` (exact API confirmed at impl time via `context7` per `library documentation protocol`). If absent, `pytest.skip("GOOGLE_API_KEY unset — DeepEval judge cannot be configured")` at fixture level so any test depending on it is skipped uniformly.
  - `agent_under_test` function-scoped fixture per `design.md` §"Skip-or-run decision flow": skip-then-import-then-skip cascade, returns the agent callable. Skip reasons name the missing prerequisite (NF6).
  - `PUBLIC_FIGURES: list[str] = ["Albert Einstein", "Marie Curie"]` module-level constant (F5).
- All imports of `deepeval` and `google.generativeai` happen inside fixtures, never at module top (NF4).

### Acceptance Criteria
- [ ] E1-AC1: `uv sync` succeeds after edits; `deepeval` and `google-generativeai` importable from a Python REPL.
- [ ] E1-AC2: `python -c "import tests.eval"` (or pytest collection) makes zero HTTP calls and zero `Settings()` instantiations.
- [ ] E1-AC3: `make test-unit` still exits 0 with the same test count as before (AC5 invariant — eval scaffolding does not leak into the unit tier).
- [ ] E1-AC4: `make test-eval` collects 0 tests (no `test_*.py` under `tests/eval/` yet) and exits 0 via the existing `|| [ $? -eq 5 ]` swallow in the Makefile.
- [ ] E1-AC5: A trivial probe test (in a temporary `tests/eval/test_smoke_e1.py`, deleted before merge OR kept as a smoke test) calling `request.getfixturevalue("agent_under_test")` skips cleanly when `person_finder.agent` is absent, with a skip reason naming the agent module (NF6).

### Testing Plan
| Test Type | What to Cover | Priority |
|-----------|--------------|----------|
| Unit | Fixture skip-reason wording (regex-match against expected substrings); fixture ordering (a small `test_isolation_override.py` under `tests/eval/` proves the captured-key restore works). | Must |
| Integration | None this epic — fixtures only, no end-to-end agent call. | — |
| E2E | None this epic. | — |

### Definition of Done
All E1 ACs pass; `make test-unit` + `make test-eval` + `make test-e2e` all exit 0; no `src/` code touched; `lsa:verify` (scoped to E1) passes.

---

## Epic 2: Deterministic metrics + AC4 stub coverage

### Description
Author `tests/eval/metrics.py` with the three `deepeval.metrics.BaseMetric` subclasses (`ValidJsonStructure`, `PersonNamesMatchInput`, `InfoNonEmptyOrSentinel`) and `tests/eval/stub_agents.py` with the three canned bad-payload generators. Add three pytest tests that feed stub payloads through the metrics and assert `metric.success is False` plus the failure-reason substring — this is the AC4 verification path (no live agent call).

### Scope
- Files/modules touched: `tests/eval/metrics.py` (new), `tests/eval/stub_agents.py` (new), `tests/eval/test_metric_failure_modes.py` (new).
- Creates: those three files.
- Modifies: none.
- Does NOT touch: `pyproject.toml`, `tests/eval/conftest.py`, `src/person_finder/**`, `tests/unit/**`, `tests/e2e/**`, any spec file.

**Covers:** F2 (three metric classes), AC4 (failure modes named).

### Technical Details
- `metrics.py` — each metric is a `BaseMetric` subclass with `measure(test_case) -> float` returning `1.0` on pass / `0.0` on fail, `success` boolean, and `reason` string naming the violated criterion + the offending entry per `design.md` §"Three deterministic metrics".
  - `ValidJsonStructure`: `json.loads(test_case.actual_output)` → assert dict with `"data"` key, list value, per-item `{"person": str, "info": str}`. On failure, `reason` names the specific shape violation (e.g., "data[2].info is not a str — got int").
  - `PersonNamesMatchInput`: parse → for each `item["person"]`, assert membership in `set(test_case.input)`. On failure, `reason` lists the unknown names.
  - `InfoNonEmptyOrSentinel`: parse → for each `item["info"]`, assert `info == "<Not found>"` OR `len(info.strip()) > 0`. On failure, `reason` names the offending index.
- `stub_agents.py` — three bare functions returning canned payloads: `malformed_json_payload()`, `unknown_person_payload(input_names)`, `empty_info_payload(input_names)`.
- `test_metric_failure_modes.py` — one pytest test per failure mode (3 total). Each constructs a `LLMTestCase` (or DeepEval equivalent) with the stub output, instantiates the metric, calls `measure`, asserts `metric.success is False` and `expected_substring in metric.reason`.

### Acceptance Criteria
- [ ] E2-AC1: `tests/eval/metrics.py` defines exactly the three `BaseMetric` subclasses with the names and signal logic above; each is independently instantiable.
- [ ] E2-AC2: Three failure-mode tests pass and demonstrate that each metric reports `success=False` with a `reason` string containing the documented substring (e.g., `"data[2].info"`, `"unknown name 'Foo Bar'"`, `"empty info at index 1"`). Substrings are documented in the test as constants so AC4 traceability is unambiguous.
- [ ] E2-AC3: `make test-eval` exits 0 with at least 3 passing test cases (the failure-mode tests pass — they assert that the metrics correctly REJECT bad payloads).

### Testing Plan
| Test Type | What to Cover | Priority |
|-----------|--------------|----------|
| Unit | All three metrics' pass paths (a happy-payload stub fed through each metric returns `success=True`); the three failure-mode tests (above). | Must |
| Integration | None — no agent call this epic. | — |
| E2E | None — covered by E3. | — |

### Definition of Done
All E2 ACs pass; metrics are pure-Python and side-effect-free (no HTTP); `lsa:verify` (scoped to E2) passes.

---

## Epic 3: Live-agent eval tests (skip-when-absent)

### Description
Author the three live-agent tests (`tests/eval/test_valid_json.py`, `tests/eval/test_person_matches.py`, `tests/eval/test_info_present.py`) that consume the `agent_under_test` fixture from E1 and the metric classes from E2. Tests parametrize over `PUBLIC_FIGURES`, call the agent, and pass the agent output through the corresponding metric via DeepEval's `evaluate()` (or `assert_test()`) entry point. When the agent module is absent (Epic 3 of the project roadmap not yet merged) OR `GOOGLE_API_KEY` is unset, the tests skip via the fixture, never fail.

### Scope
- Files/modules touched: `tests/eval/test_valid_json.py` (new), `tests/eval/test_person_matches.py` (new), `tests/eval/test_info_present.py` (new).
- Creates: those three files.
- Modifies: none.
- Does NOT touch: `pyproject.toml`, `tests/eval/conftest.py`, `tests/eval/metrics.py`, `tests/eval/stub_agents.py`, `src/person_finder/**`.

**Covers:** AC1 (happy path with both keys + agent), AC2 (skip on missing GOOGLE_API_KEY), AC3 (skip on missing agent).

### Technical Details
- Each test file mirrors `design.md` §"Layer placement" — one metric per test file.
- Each test depends on the `agent_under_test` and `judge_configured` fixtures from E1's `conftest.py`. Skip-then-import-then-skip cascade per `design.md` §"Skip-or-run decision flow" runs before any LLM call.
- Test body:
  - `names = PUBLIC_FIGURES`
  - `output = agent_under_test(names)` → string per the contract from `main.spec.md:20`.
  - Construct `LLMTestCase(input=names, actual_output=output)` (or DeepEval equivalent — exact API confirmed via context7 at impl time).
  - `assert_test(test_case, [metric])` where `metric` is one of the three from E2.
- The agent's exact public-function name is unknown until the parallel Epic 3 PR lands (OQ1). The tests use a single named import (`from person_finder.agent import run_agent`), and the import path is the single line to adjust after that PR merges.

### Acceptance Criteria
- [ ] E3-AC1: With both keys set and the agent module present, `make test-eval` runs all three live-agent tests and exits 0 (covers project AC1).
- [ ] E3-AC2: With `GOOGLE_API_KEY` unset, `make test-eval` skips all three live-agent tests with skip-reason naming `GOOGLE_API_KEY`; exit 0 (covers project AC2).
- [ ] E3-AC3: With the agent module absent (current state of `main` and this branch until the parallel agent PR lands), `make test-eval` skips all three live-agent tests with skip-reason naming `person_finder.agent`; exit 0 (covers project AC3).
- [ ] E3-AC4: No live-agent test calls Groq more than once per `PUBLIC_FIGURES` entry per test run — verified by code review (the agent call is hoisted into a fixture if a per-test call would duplicate it).

### Testing Plan
| Test Type | What to Cover | Priority |
|-----------|--------------|----------|
| Unit | None — these ARE the integration-tier tests for this feature. | — |
| Integration | All three live-agent tests (one per criterion). Parametrized over `PUBLIC_FIGURES`. | Must |
| E2E | The journeys "Run the eval suite with both keys + agent present" and "Run the eval suite without GOOGLE_API_KEY" and "Run the eval suite before the LangChain agent is merged" from `test-suites.md`. | Must |

### Definition of Done
All E3 ACs pass; the three live-agent tests run green when prerequisites are met and skip cleanly otherwise; `lsa:verify` (scoped to E3) passes.

---

## Epic 4: Spec graph wiring

### Description
Create `specs/modules/eval/spec.md` (the module's own spec under LSA), add an `eval` row to `specs/main.spec.md` §Module Index, add an `eval:` entry to `.lsa.yaml` `modules:` with `spec` + `artifact_paths` covering `tests/eval/**` and the module spec itself, and flip `roadmap.md` row 6 status to `Done` at ship time (during the final cross-reference sweep, not in this epic — but the row is queued in the integration checklist).

### Scope
- Files/modules touched: `specs/modules/eval/spec.md` (new), `specs/main.spec.md` (modify), `.lsa.yaml` (modify), `specs/roadmap.md` (modify at ship time only).
- Creates: `specs/modules/eval/spec.md`.
- Modifies: `specs/main.spec.md`, `.lsa.yaml`; `specs/roadmap.md` at ship.
- Does NOT touch: `src/person_finder/**`, `tests/**`, `pyproject.toml`.

**Covers:** AC6 (module + main.spec + .lsa.yaml wired), F6.

### Technical Details
- `specs/modules/eval/spec.md` follows the same shape as `specs/modules/users/spec.md`: Purpose, Scope (artifact_paths), Functional requirements, Non-functional requirements/invariants, Acceptance criteria, Open questions. It is the per-module spec — distinct from the per-feature spec under `specs/features/deepeval-llm-judge-suite/`. Content is sourced from this feature's `requirements.md` + `design.md`.
- `specs/main.spec.md` §Module Index gains a row:
  ```
  | eval | [modules/eval/spec.md](modules/eval/spec.md) | active |
  ```
  and the "Future modules" sentence at line 15 has `eval` removed from the future list (or annotated as "now live").
- `.lsa.yaml` gains under `modules:`:
  ```yaml
    eval:
      spec: /specs/modules/eval/spec.md
      artifact_paths:
        - /tests/eval/__init__.py
        - /tests/eval/conftest.py
        - /tests/eval/metrics.py
        - /tests/eval/stub_agents.py
        - /tests/eval/test_metric_failure_modes.py
        - /tests/eval/test_valid_json.py
        - /tests/eval/test_person_matches.py
        - /tests/eval/test_info_present.py
        - /specs/modules/eval/spec.md
  ```
- `specs/roadmap.md` row 6 status flips from `Backlog` to `Done` at ship time, with a final commit-sha citation appended to the Notes column — same pattern as Epic 1/2 already followed.

### Acceptance Criteria
- [ ] E4-AC1: `specs/modules/eval/spec.md` exists and contains the same artifact_paths as `.lsa.yaml`.
- [ ] E4-AC2: `specs/main.spec.md` lists `eval` under Module Index with a working markdown link to the module spec.
- [ ] E4-AC3: `.lsa.yaml` declares `eval` under `modules:` with `spec` and `artifact_paths`; YAML still parses.
- [ ] E4-AC4: All markdown links in the three modified files resolve to live files (manual `ls` check during the cross-reference sweep).

### Testing Plan
| Test Type | What to Cover | Priority |
|-----------|--------------|----------|
| Unit | None — this epic is markdown + YAML. | — |
| Integration | A trivial `python -c "import yaml; yaml.safe_load(open('.lsa.yaml'))"` smoke check OR `make test-unit` (which doesn't read .lsa.yaml but proves nothing broke). | Should |
| E2E | The journey "Spec wiring + roadmap hygiene" from `test-suites.md`. | Must |

### Definition of Done
All E4 ACs pass; markdown links resolve; `.lsa.yaml` parses; `lsa:verify` (scoped to E4) passes.

---

## Integration Checklist
- [ ] All four epics merged into `feature/deepeval-llm-judge-suite`.
- [ ] `make test-unit` exits 0 on the integrated branch (AC5).
- [ ] `make test-eval` exits 0 on the integrated branch — skips cleanly when prerequisites absent (AC2 + AC3) or passes when prerequisites present (AC1).
- [ ] `make test-e2e` exits 0 on the integrated branch (AC5).
- [ ] `make test-all` exits 0 on the integrated branch.
- [ ] `lsa:verify` passed on the integrated branch.
- [ ] `specs/roadmap.md` row 6 status flipped to `Done` with commit-sha citation.
- [ ] `specs/main.spec.md` line 15 updated (eval no longer in "future modules" list).
- [ ] PR to `main` created.

# Tasks: `validate_output` + repair retry loop (Epic 4)

## Epic Overview

| Epic | Branch | Status | Dependency |
|------|--------|--------|------------|
| E1: Validation module + spec graph wiring | `feature/validate-output-retry-loop` | done | none |

Single-epic Standard flow — no decomposition was performed (`lsa:plan` was bypassed). All requirement IDs are satisfied by E1.

---

## Epic 1: Validation module + spec graph wiring

### Description

Add the `validation` module — pure-Python, code-only, no agent import — with the `validate_output(raw, repair_fn=None) -> dict` public surface, the `Error` exception class, and the 3-repair retry loop. Add unit tests covering happy paths, single-repair success, exhaustion semantics, fail-fast behavior, precise diagnostics, defensive non-str handling, and side-effect-free imports. Wire the spec graph: per-module spec, `main.spec.md` Module Index row, and `.lsa.yaml` `modules:` entry. (The `agent` Module Index row is added fix-it-forward to resolve OQ1 from `requirements.md`.)

### Scope

- Files/modules touched:
  - Create: `src/person_finder/validation.py`, `tests/unit/test_validation.py`, `specs/modules/validation/spec.md`.
  - Modify: `specs/main.spec.md` (add `validation` row + fix-it-forward `agent` row + trim Future modules sentence), `.lsa.yaml` (add `validation:` module entry).
  - Not touched: `src/person_finder/agent.py`, `src/person_finder/config.py`, `src/person_finder/__init__.py`, `tests/unit/test_agent.py`, `tests/unit/test_config.py`, `tests/conftest.py`, `pyproject.toml`, `uv.lock`, `specs/roadmap.md`, `specs/standards/**`, `ARCHITECTURE.md`.

**Covers:** F1, F2, F3, F4, F5, F6, F7, NF1, NF2, NF3, NF4, NF5, NF6, AC1, AC2, AC3, AC4, AC5, AC6, AC7. (Every requirement ID in `requirements.md` is implemented by this single epic — Standard flow.)

### Technical Details

- `validation.py` mirrors `design.md` §"Public surface", §"Retry loop shape", §"Error hierarchy", §"Parse + check pipeline" exactly. Stdlib `json` is the only external dependency. The retry loop uses `for attempt in range(MAX_REPAIRS + 1)` with explicit `attempt == MAX_REPAIRS` break-and-raise to avoid an extra `repair_fn` call after the budget is spent. `Error("Could not respond")` chains the last `_ValidationFailure` via `from`.
- `_parse_and_check` accepts `Any` (not `str`) so a `repair_fn` returning `None` becomes a normal validation failure rather than a `TypeError` (NF3).
- `tests/unit/test_validation.py` matches the journey shapes in `test-suites.md`: 8 logical tests, 17 collected pytest items (the AC5 parametrized test contributes 9 cases). All tests use stdlib + `pytest` + module-local mock callables; no LangChain, no Groq, no network.
- Spec graph wiring: `specs/modules/validation/spec.md` follows the LSA module-spec template (mirrors `specs/modules/agent/spec.md`). `main.spec.md` Module Index gains rows for both `agent` and `validation` (agent row is fix-it-forward per OQ1). `.lsa.yaml` `validation:` block lists the two artifact paths.

### Acceptance Criteria

(Same numbering as `requirements.md` — every project AC is an epic AC here, because Standard flow has only one epic.)

- [x] **E1-AC1** = requirements AC1 — first-shot valid returns dict; no repair calls.
- [x] **E1-AC2** = requirements AC2 — single-repair success returns dict; repair called once.
- [x] **E1-AC3** = requirements AC3 — exhaustion raises `Error("Could not respond")` after exactly 3 repair calls.
- [x] **E1-AC4** = requirements AC4 — no `repair_fn` → immediate raise; zero repair calls.
- [x] **E1-AC5** = requirements AC5 — `__cause__` carries precise diagnostic substring per failure mode (9 parametrized cases).
- [x] **E1-AC6** = requirements AC6 — `make test-unit` exits 0; pre-existing 11 tests still green plus new validation tests.
- [x] **E1-AC7** = requirements AC7 — module spec exists, main.spec.md and .lsa.yaml updated.

### Testing Plan

| Test Type | What to Cover | Priority |
|-----------|--------------|----------|
| Unit | All 9 paths from `test-suites.md` journeys: first-shot success, single-repair success, exhaustion (3 repairs), fail-fast (no repair_fn), 9-mode parametrized `__cause__` diagnostic, defensive non-str repair output, side-effect-free import. | Must |
| Integration | None — module is pure code over a string + callable; no real collaborators to integrate against on this branch. The live-agent integration belongs to Epic 5 (render). | — |
| E2E | None — Epic 5 owns the end-to-end agent→validation→user flow. | — |

### Definition of Done

All requirement-level ACs pass; `make test-unit` exits 0 with no regressions in `test_config.py` or `test_agent.py`; no `src/person_finder/agent.py` or `src/person_finder/config.py` touched; no new runtime dependencies; `lsa:verify` passes.

---

## Integration Checklist

- [x] Single epic complete on `feature/validate-output-retry-loop`.
- [x] `make test-unit` exits 0 with 28 tests passing (5 agent + 6 config + 17 validation).
- [x] `make test-eval` exits 0 (empty tier — exit 5 swallowed by Makefile).
- [x] `make test-e2e` exits 0 (empty tier — exit 5 swallowed by Makefile).
- [x] `make test-all` exits 0.
- [ ] `lsa:verify` passed on this branch.
- [ ] `specs/roadmap.md` row 4 status flipped to `Done` with commit-sha citation (ship-time sweep).
- [ ] `specs/main.spec.md` line 15 already updated by this epic (validation + agent removed from Future modules sentence).
- [ ] PR to `main` created.

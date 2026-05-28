# Tasks: LangChain ReAct Agent + `findPerson` Tool

Decomposed from approved [requirements.md](./requirements.md), [test-suites.md](./test-suites.md), [design.md](./design.md). Two epics — well under the ≤5 cap. The scaffold currently on this branch satisfies most of E1 already; E1's implement step is a reconcile pass + one new test (AC5 gap), and E2 is pure LSA metadata.

## Epic Overview

| Epic | Branch | Status | Dependency |
|------|--------|--------|------------|
| E1: Reconcile agent scaffold + close AC5 gap | `feature/langchain-agent` (in place; sub-branch unnecessary given scope) | pending | none |
| E2: Register `agent` module in LSA metadata | `feature/langchain-agent` (in place) | pending | none — independent of E1 |

Both epics share the parent feature branch because each diff is <50 lines; the per-epic sub-branch ceremony in the template would add merge overhead without isolation benefit. They can be sequenced in either order — neither depends on the other at runtime.

## Epics

## Epic 1: Reconcile agent scaffold + close AC5 gap

### Description

Bring the existing agent scaffold (`langchain` + `langchain-groq` deps, `src/person_finder/agent.py`, `tests/unit/test_agent.py`) into formal trace alignment with the approved feature spec, and close the one identified gap: AC5 (import side-effect-free) has no corresponding test.

### Scope

- Files/modules touched: `pyproject.toml`, `uv.lock`, `src/person_finder/agent.py`, `tests/unit/test_agent.py`
- Creates: one new test in `tests/unit/test_agent.py` exercising AC5
- Modifies: `agent.py` only if the reconcile diff against requirements/design surfaces a mismatch (none expected — scaffold was built directly from the same constraints)
- Deletes: nothing
- Does NOT touch: `.lsa.yaml`, `specs/modules/`, `specs/roadmap.md`, `tests/eval/`, `tests/e2e/`, `src/person_finder/users.py` (Epic 2 is in flight elsewhere)

**Covers:** F1, F2, F3, F4, F5, F6, NF1, NF2, NF3, NF4, AC1, AC2, AC3, AC4, AC5

### Technical Details

Reconcile checklist — read each F/NF and confirm the scaffold matches; flag any mismatch as a fix:

- F1: `enrich_names(names, *, model=None) -> str` exists with correct signature. ✓ already.
- F2: `@tool findPerson(name: str) -> str` returns `"<Not found>"`. ✓ already.
- F3: `_default_model()` builds `ChatGroq(model="llama-3.3-70b-versatile", temperature=0)`. ✓ already.
- F4: `SYSTEM_PROMPT` instructs JSON-only output with `"<Not found>"` fallback and no fences. ✓ already.
- F5: `build_agent` uses `langchain.agents.create_agent`. ✓ already.
- F6: `model=` kwarg accepted on `build_agent` and `enrich_names`. ✓ already.
- NF1: `api_key=settings.groq_api_key` passed explicitly to `ChatGroq`. ✓ already.
- NF2: Module imports do not call `get_settings()` or hit network. ✓ structurally already (lazy access inside `_default_model`); **test gap = AC5 below**.
- NF3: All unit tests mock externals. ✓ already (4 tests use monkeypatch or direct stub).
- NF4: `pyproject.toml` pins `langchain>=1,<2`, `langchain-groq>=1,<2`. ✓ already.

**AC5 test (new):** A subprocess test that runs `python -c "import person_finder.agent"` with `GROQ_API_KEY` and `GOOGLE_API_KEY` stripped from the environment, asserts exit code 0, and asserts stderr is empty. Subprocess (not in-process) because the conftest fixture already strips env in-process and the import path may already be cached by other tests — a fresh process is the only honest assertion of "no side effects on first import".

### Acceptance Criteria

- [ ] AC1.E1: `make test-unit` exits 0 with 11/11 tests green (existing 10 + new AC5 test).
- [ ] AC2.E1: Every F/NF/AC ID in **Covers:** above is matched by code OR a test in this epic's scope (no orphan requirement).
- [ ] AC3.E1: `git diff main -- pyproject.toml uv.lock src/person_finder/agent.py tests/unit/test_agent.py` contains no hunk outside this Scope.

### Testing Plan

| Test Type | What to Cover | Priority |
|-----------|--------------|----------|
| Unit | AC1, AC2, AC3, AC4 (existing 4 tests in `test_agent.py`) + AC5 (new subprocess test) | Must |
| Integration | Not applicable — module surface is internal Python; no cross-process boundary in this epic | — |
| E2E | Owned by Epic 5 — out of scope here per `requirements.md` §Out of Scope | — |
| Eval | Owned by Epic 6 (DeepEval) in parallel — out of scope here per `requirements.md` §Out of Scope | — |

### Definition of Done

Standard four-gate: all ACs pass, tests written + passing, no code smells per [code.md](../../standards/code.md), `/lsa:verify` passes (assuming E2 has also landed so the `agent` module is registered).

---

## Epic 2: Register `agent` module in LSA metadata

### Description

Add the new `agent` module to `.lsa.yaml: modules` with `artifact_paths` covering the scaffold files, and write `specs/modules/agent/spec.md` mirroring the F/NF invariants from the feature spec. This is the bookkeeping that lets `/lsa:verify` find the module spec for Read-Protocol Step 3 ("for each module in scope") and lets `/lsa:reconcile` operate on it later.

Note: the LSA discover-skill constraint says module specs are written by `lsa:reconcile`, not directly. In practice, since this is a NEW module with no prior spec to reconcile against, the cleanest path is to author it as part of this epic with the same template scaffolding/spec.md uses, then let `lsa:reconcile` curate future drift. If a stricter interpretation is preferred, this epic can be reduced to "register in `.lsa.yaml` only" and the module spec deferred to a follow-up `/lsa:reconcile` invocation.

### Scope

- Files/modules touched: `.lsa.yaml`, `specs/modules/agent/spec.md` (new)
- Creates: `specs/modules/agent/` directory and its `spec.md`
- Modifies: `.lsa.yaml` adds a `modules.agent` entry
- Deletes: nothing
- Does NOT touch: code or tests under `src/` or `tests/`, the feature spec dir, `specs/roadmap.md`

**Covers:** F1, F2, F3, F4, F5, F6, NF1, NF2, NF3, NF4

These F/NF IDs are not duplicated implementations of E1's work — the module spec *describes* the invariants that E1's code embodies. The orphan-diff predicate is satisfied because every hunk in E2's diff (the YAML lines and the markdown file) is within E2's Scope and cites ≥1 requirement.

### Technical Details

`.lsa.yaml` addition under `modules:`:

```yaml
  agent:
    spec: /specs/modules/agent/spec.md
    artifact_paths:
      - /src/person_finder/agent.py
      - /tests/unit/test_agent.py
```

`specs/modules/agent/spec.md` template (modeled on [scaffolding/spec.md](../../modules/scaffolding/spec.md)):

- **Purpose**: 1-paragraph summary citing the feature pitch.
- **Scope (artifact paths)**: the two file paths.
- **Functional requirements**: paraphrase F1–F6, each with a stable `F<n>` ID and a link back to the feature `requirements.md`.
- **Non-functional requirements / invariants**: paraphrase NF1–NF4, plus the inherited scaffolding NF3 / NF5.
- **Acceptance criteria**: paraphrase AC1–AC5 with their unit-test names where applicable.
- **Open questions / follow-ups**: OQ1 (real findPerson), OQ2 (cost ceiling), OQ3 (temperature param) from feature `design.md`.

### Acceptance Criteria

- [ ] AC1.E2: `.lsa.yaml` parses cleanly and contains a `modules.agent` entry with both artifact_paths present.
- [ ] AC2.E2: `specs/modules/agent/spec.md` exists, is non-empty, and contains sections matching the scaffolding spec template (Purpose, Scope, Functional, Non-functional, Acceptance criteria, Open questions).
- [ ] AC3.E2: Every F-req and NF-req from the feature `requirements.md` is paraphrased in the module spec (no orphan requirement).

### Testing Plan

| Test Type | What to Cover | Priority |
|-----------|--------------|----------|
| Unit | Not applicable — no runtime code | — |
| Integration | Implicit: `/lsa:verify` resolves the new module successfully | Should |
| E2E | Not applicable | — |
| Eval | Not applicable | — |

Manual verification: `python -c "import yaml; yaml.safe_load(open('.lsa.yaml'))"` succeeds; `ls specs/modules/agent/spec.md` succeeds; grep confirms F1–F6 and NF1–NF4 IDs appear.

### Definition of Done

`.lsa.yaml` parses; module spec exists with the required sections; `/lsa:verify` (run after E1 also lands) reads the module spec without error.

---

## Integration Checklist

- [ ] E1 implemented: scaffold reconcile pass complete, AC5 test added, `make test-unit` green (11/11).
- [ ] E2 implemented: `.lsa.yaml` updated, module spec written.
- [ ] All unit tests pass on the feature branch.
- [ ] `/lsa:verify` passes on the feature branch (orphan-diff and orphan-AC predicates clean).
- [ ] (Sync step, not part of these epics) `specs/roadmap.md` row 3 status updated from Backlog → Done.
- [ ] PR to main created.

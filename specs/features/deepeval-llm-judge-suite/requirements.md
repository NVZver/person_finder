# Feature: DeepEval LLM-Judge Eval Suite (Epic 6)

## Summary
Stand up the `tests/eval/` tier so the project's quality bar — "agent output is valid JSON with `data[].person` matching the input list and `data[].info` non-empty or `<Not found>`" — is enforced by a runnable DeepEval suite with Gemini 2.0 Flash configured as the judge model. The suite consumes the agent's public surface (built in parallel by Epics 3–4) and skips cleanly when that surface is absent or when `GOOGLE_API_KEY` is unset, so this epic can land independently of the in-flight LangChain branch.

Sources: [ARCHITECTURE.md](../../../ARCHITECTURE.md) §Stack lines 5-12, §Tests/LLM evaluation lines 92-98, §Scripts lines 106-113, §Environment variables lines 117-122; [roadmap.md](../../roadmap.md) row 6; [main.spec.md](../../main.spec.md) line 15 (`eval` future module) and lines 17-23 (cross-module contracts).

## Functional Requirements
| ID | Requirement | Priority |
|----|-------------|----------|
| F1 | The repo provides a `tests/eval/` test tier whose files Pytest collects under `make test-eval`. Judge configuration (Gemini 2.0 Flash) lives next to the tests (e.g. `tests/eval/conftest.py`); no Python module is added under `src/person_finder/` — eval is test infrastructure, not application code. | Must |
| F2 | At least three DeepEval test cases exist, one per criterion: (a) valid JSON shape (`data[].person:str` + `data[].info:str`), (b) `person` value is in the input list, (c) `info` is `"<Not found>"` or a non-empty string. The three criteria are deterministic checks expressed as DeepEval `BaseMetric` subclasses. | Must |
| F3 | A `judge_configured` fixture gates `GOOGLE_API_KEY` presence and acts as the integration point for the (future) Gemini 2.0 Flash judge. The SDK install + `GeminiModel` instantiation are **deferred to the follow-up live-judge epic** (revised at verify time after dropping unused SDK installs from this branch — see Open Questions OQ5). The deterministic metrics in F2 do not call the judge, so the gate's only job here is to surface the prerequisite uniformly and reserve the wiring point. This satisfies the [ARCHITECTURE.md:9-11](../../../ARCHITECTURE.md) judge-model pin at architectural level without prematurely installing an SDK that no current metric uses. | Must |
| F4 | The suite calls the agent under test via a lazy import (e.g. `pytest.importorskip("person_finder.agent")`). When the agent module is not yet present, the eval tests `skip` with a clear reason; they never `fail` due to a missing dependency. | Must |
| F5 | The suite uses a small fixed roster of well-known public figures (≤3 names, e.g. `["Albert Einstein", "Marie Curie"]`) as its input list. It does NOT call `fetch_user_names()` (Epic 2): random-user names are unknown to the LLM and would yield all-`<Not found>` outputs, defeating the eval. | Must |
| F6 | `specs/modules/eval/spec.md` is created (the module's own spec) and linked from `specs/main.spec.md` §Module Index. `.lsa.yaml` gains an `eval:` entry under `modules:` with `spec` + `artifact_paths`. | Must |

## Non-Functional Requirements
| ID | Requirement |
|----|-------------|
| NF1 | **Cost envelope.** A single `make test-eval` invocation makes at most one real Groq agent call per public-figure name (≤3 calls total) and zero Gemini judge calls under the default configuration. Total budget < $0.05 / run. No retry loop inside the eval suite — Epic 4's repair loop handles repair. |
| NF2 | **Test-isolation override.** The root `tests/conftest.py` autouse fixture strips `GROQ_API_KEY` + `GOOGLE_API_KEY`. `tests/eval/conftest.py` restores both from the real process env (when present) for eval tests only, so unit-test isolation is not weakened. When real keys are absent in the host env, the eval tests skip per F4. |
| NF3 | **Dependency additions.** Add `deepeval` to `pyproject.toml` `[dependency-groups] dev` — not under top-level `dependencies` (eval is test infrastructure, not application runtime). The Gemini judge SDK install (`google-genai`, `google-generativeai`, or whichever DeepEval's then-current `GeminiModel` requires) is **deferred to the follow-up live-judge epic** per OQ5 — installing it now would add deps no current metric exercises and would have to be re-validated when DeepEval's SDK requirement shifts again. |
| NF4 | **Side-effect-free imports.** Importing any file under `tests/eval/` MUST NOT make HTTP calls, read disk beyond `.env`, or raise. Network I/O happens only inside test functions. |
| NF5 | **Eval-test independence from unit/e2e.** Adding `tests/eval/*` MUST NOT change the pass/fail behavior of `make test-unit` or `make test-e2e`. The three tiers stay independently runnable. |
| NF6 | **Skip-with-reason discipline.** When eval tests skip (F4, NF2), the skip message names the missing prerequisite (e.g. `"person_finder.agent not importable yet — Epic 3 pending"` or `"GOOGLE_API_KEY unset"`) so the reader can act without grepping the suite. |

## Inputs & Outputs
- **Input (to the agent under test):** `list[str]` of `"First Last"` strings (a small fixed public-figure roster, F5).
- **Output (from the agent under test, evaluated by this suite):** `{ "data": [{ "person": str, "info": str }] }` per [main.spec.md:20](../../main.spec.md).
- **Side effects:** Optional outbound HTTPS to Groq (agent call) and — only if an LLM-judged metric is added later — Google AI Studio. No file writes outside Pytest's test cache.

## Constraints
- [ARCHITECTURE.md §Tests/LLM evaluation](../../../ARCHITECTURE.md) lines 92-98 fixes the three criteria. This spec does not invent new criteria; it operationalizes those three.
- [ARCHITECTURE.md §Stack](../../../ARCHITECTURE.md) lines 9-11 pins the judge model to Gemini 2.0 Flash. This spec does not pick a different judge.
- [main.spec.md §Cross-Module Contracts](../../main.spec.md) lines 17-23 fixes the agent output contract. This spec consumes it read-only.
- [code.md §Validation & retry](../../standards/code.md) lines 29-34 — the eval suite asserts ON the validated output; it does not re-implement the retry loop.
- [testing.md §LLM evaluation](../../standards/testing.md) lines 19-26 — DeepEval + Gemini 2.0 Flash mandated.

## Out of Scope
- Implementing the LangChain ReAct agent (Epic 3).
- Implementing `validate_output` + the repair retry loop (Epic 4).
- Implementing the top-level Python render + error-surfacing layer (Epic 5).
- Adding ruff / mypy / pre-commit infrastructure.
- Extending the agent output contract (e.g. adding fields beyond `person` + `info`).
- LLM-judged "info relevance" or "info faithfulness" metrics — explicitly deferred to a follow-up epic; the judge is wired only so this metric can be added without re-wiring (F3).
- CI workflow changes — `make test-eval` is the contract; CI provisioning is OQ2 of the scaffolding module.

## Acceptance Criteria
<!-- EARS-form per vision/VISION.md:201; user/system boundary per VISION.md §2 sub-principle 2a. -->
- [ ] **AC1** — When a developer runs `make test-eval` with both `GROQ_API_KEY` and `GOOGLE_API_KEY` set in the host env AND the agent module present, the suite shall execute at least 3 DeepEval test cases (one per criterion) and exit 0 with all cases passing. *(Ubiquitous)*
- [ ] **AC2** — When `GOOGLE_API_KEY` is unset, `make test-eval` shall exit 0 with all eval tests marked `skipped` and the skip reason naming `GOOGLE_API_KEY` per NF6. *(State)*
- [ ] **AC3** — When `person_finder.agent` is not importable (Epic 3 not yet merged), `make test-eval` shall exit 0 with all eval tests marked `skipped` and the skip reason naming the missing agent module per NF6. *(State)*
- [ ] **AC4** — When the agent returns a payload that violates any one of the three criteria (e.g. malformed JSON, a `person` not in the input list, an empty `info` string), the corresponding DeepEval metric shall report `success=False` with a reason string that names the violated criterion, and `make test-eval` shall exit non-zero. *(Event)*
- [ ] **AC5** — `make test-unit` and `make test-e2e` shall exit 0 with the same set of tests as before this epic (no eval-side dependency leaks into the other tiers). *(Ubiquitous)*
- [ ] **AC6** — `specs/main.spec.md` §Module Index shall list `eval` with a link to `specs/modules/eval/spec.md`, and `.lsa.yaml` shall list `eval` under `modules:` with `artifact_paths` covering `tests/eval/**` and `specs/modules/eval/spec.md`. *(Ubiquitous)*

## Contract Trigger Check (User Verification 1)

Inspected requirements for any of:
- API endpoint — **no**.
- Request/response schema (HTTP, RPC) — **no**.
- DB schema / table change — **no**.
- Shared data type used across modules — **no**: the only cross-module data shape consumed (agent input/output) is already declared in `main.spec.md` §Cross-Module Contracts and is **read-only** for this epic. No new type is introduced.

**Trigger = NO.** `contract.yaml` is **skipped** for this feature. The diagonal-coverage check in User Verification 2 will render rows 3 and 4 as `N/A — contract skipped`.

## Open Questions

| # | Question | Source |
|---|---|---|
| OQ1 | When the parallel LangChain branch lands, will the agent's public surface be `agent.run(names: list[str]) -> dict`, `agent.find_people(...)`, or some other shape? Eval F4 calls it via a single named function; we will adapt the import path once the agent contract is finalized. | Cross-branch dependency. |
| OQ2 | If `deepeval` itself pulls in a heavyweight LLM-judge stack as a hard install dep (e.g. it imports `openai` at import time), we may need to wrap it in an `importorskip` too. Verify on first install. | NF3 + NF4 risk. |
| OQ3 | Should the `eval` group be `[dependency-groups] eval` (uv-native) or under `dev`? Current `pyproject.toml` only has `dev`. Keeping it under `dev` is simplest; splitting only if eval deps balloon. | NF3 follow-up. |
| OQ4 | Future LLM-judged "info relevance" metric — deferred to a follow-up epic. F3 leaves the judge gate wired so the addition is one fixture-body change + one metric class. | Out-of-scope deferral. |
| OQ5 | **Gemini SDK install deferred to live-judge follow-up epic.** At verify time the implementation surfaced that DeepEval 4.x's `GeminiModel` requires `google-genai` (not the deprecated `google-generativeai` named in NF3's original draft). Rather than install an SDK with no current consumer (the deterministic metrics never call the judge), the SDK install is deferred to whichever epic introduces the first judge-using metric. The `judge_configured` fixture still skip-gates `GOOGLE_API_KEY` so the wiring point is reserved. | Verify-time finding W3; NF3 + F3 amendment. |

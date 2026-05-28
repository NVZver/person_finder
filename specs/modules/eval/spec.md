# Eval Module — Spec

## Purpose

Stand up the `tests/eval/` test tier so the project's quality bar — "agent output is valid JSON with `data[].person` matching the input list and `data[].info` non-empty or `<Not found>`" — is enforced by a runnable DeepEval suite with Gemini 2.0 Flash configured as the judge model. The module owns the eval infrastructure (fixtures, deterministic metrics, judge wiring, public-figure roster) and consumes the agent's public surface read-only via a lazy import, so it can land independently of the in-flight LangChain agent and degrade to clean skips when prerequisites are absent.

Pitch source: [ARCHITECTURE.md](../../../ARCHITECTURE.md) §Stack lines 5-12, §Tests/LLM evaluation lines 92-98, §Scripts lines 106-113, §Environment variables lines 117-122.
Cross-module contract consumed: [main.spec.md](../../main.spec.md) lines 17-23 (`{ "data": [{ "person": str, "info": str }] }`).
Epic: [roadmap.md](../../roadmap.md) row 6 (`DeepEval LLM-judge eval suite`, MVP).

## Scope (artifact paths)

- `tests/eval/__init__.py`
- `tests/eval/conftest.py`
- `tests/eval/metrics.py`
- `tests/eval/stub_agents.py`
- `tests/eval/test_fixtures.py`
- `tests/eval/test_metric_failure_modes.py`
- `tests/eval/test_valid_json.py`
- `tests/eval/test_person_matches.py`
- `tests/eval/test_info_present.py`
- `specs/modules/eval/spec.md`

## Functional requirements

- **F1 — Eval tier owned under `tests/eval/`.** Pytest collects the suite under `make test-eval`; judge configuration lives next to the tests (in `tests/eval/conftest.py`); no module is added under `src/person_finder/` — eval is test infrastructure, not application code. ([requirements.md F1](../../features/deepeval-llm-judge-suite/requirements.md):11; [ARCHITECTURE.md:92-98](../../../ARCHITECTURE.md))
- **F2 — Three deterministic `BaseMetric` classes.** The module exposes one `deepeval.metrics.BaseMetric` subclass per criterion: `ValidJsonStructure` (shape: `data` key + per-item `person:str` + `info:str`), `PersonNamesMatchInput` (set-membership of every `data[].person` in the input list), `InfoNonEmptyOrSentinel` (each `info` equals `"<Not found>"` OR has non-blank content). Each metric's `measure()` is pure Python, no LLM call. ([requirements.md F2](../../features/deepeval-llm-judge-suite/requirements.md):12; [ARCHITECTURE.md:94-97](../../../ARCHITECTURE.md))
- **F3 — Gemini 2.0 Flash judge gate (SDK install deferred).** A `judge_configured` fixture skip-gates `GOOGLE_API_KEY` and reserves the wiring point for the (future) Gemini 2.0 Flash judge. The SDK install (`google-genai` / `google-generativeai` / whichever DeepEval's `GeminiModel` then-currently requires) is **deferred to the follow-up live-judge epic** — installing it here would add deps no metric in this module exercises (the three F2 metrics are deterministic). ([requirements.md F3](../../features/deepeval-llm-judge-suite/requirements.md):13; [requirements.md OQ5](../../features/deepeval-llm-judge-suite/requirements.md):76; [ARCHITECTURE.md:9-11](../../../ARCHITECTURE.md))
- **F4 — Lazy agent import + clean skip.** Live-agent tests reach the agent via `from person_finder.agent import run_agent` inside a fixture; an `ImportError` triggers `pytest.skip` with a reason naming the missing module. Tests never `fail` due to a missing agent dependency. ([requirements.md F4](../../features/deepeval-llm-judge-suite/requirements.md):14)
- **F5 — Fixed public-figure roster.** The suite uses a small fixed roster (`PUBLIC_FIGURES = ["Albert Einstein", "Marie Curie"]`) — NOT `fetch_user_names()` output — because random-user names are unknown to the LLM and would defeat the eval. ([requirements.md F5](../../features/deepeval-llm-judge-suite/requirements.md):15)
- **F6 — Spec graph wired.** The module is declared in [`main.spec.md`](../../main.spec.md) §Module Index and in `.lsa.yaml` `modules:` with `spec` + `artifact_paths` matching the Scope section above. ([requirements.md F6](../../features/deepeval-llm-judge-suite/requirements.md):16)

## Non-functional requirements / invariants

- **NF1 — Cost envelope.** A single `make test-eval` invocation makes at most one real Groq agent call per public-figure name (≤3 calls per test run) and zero Gemini judge calls under the default configuration. No retry loop inside the eval suite — the validation module (Epic 4) owns repair. ([requirements.md NF1](../../features/deepeval-llm-judge-suite/requirements.md):21)
- **NF2 — Test-isolation override (eval-only).** The root [`tests/conftest.py`](../../../tests/conftest.py) autouse fixture strips `GROQ_API_KEY` + `GOOGLE_API_KEY`; `tests/eval/conftest.py` re-emits them via `monkeypatch.setenv` from a snapshot captured at conftest import time, but ONLY for tests under `tests/eval/`. Unit-test isolation is never weakened. ([requirements.md NF2](../../features/deepeval-llm-judge-suite/requirements.md):22; [tests/eval/conftest.py:43-74](../../../tests/eval/conftest.py))
- **NF3 — Eval deps live in `[dependency-groups] dev` only.** `deepeval` is dev-only and MUST NOT leak into top-level `dependencies`. The Gemini judge SDK install is deferred to the follow-up live-judge epic per F3 above — installing it here would add a dependency no current metric exercises. ([requirements.md NF3](../../features/deepeval-llm-judge-suite/requirements.md):23; [requirements.md OQ5](../../features/deepeval-llm-judge-suite/requirements.md):76)
- **NF4 — Side-effect-free imports.** Importing any file under `tests/eval/` MUST NOT make HTTP calls, read disk beyond `.env`, or raise. All `deepeval` and `google.generativeai` imports happen INSIDE fixtures, never at module top. Network I/O happens only inside test functions. ([requirements.md NF4](../../features/deepeval-llm-judge-suite/requirements.md):24)
- **NF5 — Tier independence.** Adding `tests/eval/*` MUST NOT change the pass/fail behavior of `make test-unit` or `make test-e2e`. The three tiers stay independently runnable. ([requirements.md NF5](../../features/deepeval-llm-judge-suite/requirements.md):25)
- **NF6 — Skip-with-reason discipline.** When eval tests skip, the skip message names the missing prerequisite (e.g. `"GOOGLE_API_KEY unset — DeepEval judge cannot be configured"`, `"person_finder.agent not importable yet — Epic 3 pending"`). The reader acts without grepping the suite. ([requirements.md NF6](../../features/deepeval-llm-judge-suite/requirements.md):26)

## Acceptance criteria

- **AC1 — Green when prerequisites present.** With both keys set in the host env AND `person_finder.agent` importable, `make test-eval` executes ≥3 DeepEval cases (one per criterion) and exits 0 with all cases passing. ([requirements.md AC1](../../features/deepeval-llm-judge-suite/requirements.md):51)
- **AC2 — Clean skip on missing `GOOGLE_API_KEY`.** When `GOOGLE_API_KEY` is unset (or blank), `make test-eval` exits 0 with all eval tests marked `skipped` and the skip reason naming `GOOGLE_API_KEY`. ([requirements.md AC2](../../features/deepeval-llm-judge-suite/requirements.md):52)
- **AC3 — Clean skip on missing agent.** When `person_finder.agent` is not importable, `make test-eval` exits 0 with all live-agent tests marked `skipped` and the skip reason naming the missing module. ([requirements.md AC3](../../features/deepeval-llm-judge-suite/requirements.md):53)
- **AC4 — Criterion-named failure on bad payload.** When agent output violates any one of the three criteria, the corresponding metric reports `success=False` with a `reason` string naming the violated criterion + offending entry; `make test-eval` exits non-zero. Verified via stub bad-payload generators in `tests/eval/stub_agents.py` — no live LLM call. ([requirements.md AC4](../../features/deepeval-llm-judge-suite/requirements.md):54)
- **AC5 — Other tiers byte-identical.** `make test-unit` and `make test-e2e` exit 0 with the same set of tests as before the eval tier landed. ([requirements.md AC5](../../features/deepeval-llm-judge-suite/requirements.md):55)
- **AC6 — Spec graph wired.** `specs/main.spec.md` §Module Index lists `eval` with a link to this file, and `.lsa.yaml` declares `eval` under `modules:` with `artifact_paths` covering `tests/eval/**` and this spec. ([requirements.md AC6](../../features/deepeval-llm-judge-suite/requirements.md):56)

## Open questions / follow-ups

| # | Question | Source |
|---|---|---|
| OQ1 | Agent public-surface shape — `run_agent(names)`, `find_people(names)`, async equivalent? The lazy import in `tests/eval/conftest.py:136` currently targets `run_agent`; adjust the single import line once the parallel agent PR finalizes the name. | [requirements.md OQ1](../../features/deepeval-llm-judge-suite/requirements.md):72; [design.md OQ1](../../features/deepeval-llm-judge-suite/design.md):132. |
| OQ2 | `[dependency-groups]` split — keep eval deps under `dev` or carve a dedicated `eval` group? Currently under `dev` per [requirements.md NF3](../../features/deepeval-llm-judge-suite/requirements.md):23; split only if eval-only deps balloon. | [requirements.md OQ3](../../features/deepeval-llm-judge-suite/requirements.md):74; [design.md cost line](../../features/deepeval-llm-judge-suite/design.md):124. |
| OQ3 | Future LLM-judged "info relevance" metric — deferred follow-up epic. F3 leaves the judge wired so the addition is one new metric class + one test. | [requirements.md OQ4](../../features/deepeval-llm-judge-suite/requirements.md):75; [design.md OQ3](../../features/deepeval-llm-judge-suite/design.md):134. |
| OQ4 | Cross-module dependency on the `agent` module (still future in [main.spec.md:15](../../main.spec.md)). The eval module consumes the agent's public surface read-only and skips cleanly on `ImportError` (NF6, F4) until the parallel branch lands. | [main.spec.md:15](../../main.spec.md); [design.md "Modules Affected"](../../features/deepeval-llm-judge-suite/design.md):3-12. |

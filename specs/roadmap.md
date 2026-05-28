# Roadmap

## Feature Backlog

| Epic | Feature | Priority | Status | Notes |
|------|---------|----------|--------|-------|
| 1 | Project scaffolding & env loading | MVP | Done | Create `pyproject.toml`, `Makefile`, `tests/{unit,eval,e2e}/` layout; load `GROQ_API_KEY` + `GOOGLE_API_KEY` from env. Pitch: [ARCHITECTURE.md](../ARCHITECTURE.md) §Scripts, §Env vars. No dependencies. Shipped in `8afc084`. |
| 2 | Random-user fetch + filter + name mapping | MVP | Done | Fetch 20 users from `randomuser.me/api`, drop born-after-2000, return `list[str]` of `"First Last"`. Pitch: [ARCHITECTURE.md](../ARCHITECTURE.md) §Layers/1. Depends on Epic 1. Spec: [specs/modules/users/spec.md](modules/users/spec.md). |
| 3 | LangChain ReAct agent + `findPerson` tool | MVP | Done | Agent accepts `list[str]`, runs ReAct + CoT loop, calls `findPerson(name)` per person, returns raw JSON-shaped string (no validation). Pitch: [ARCHITECTURE.md](../ARCHITECTURE.md) §Layers/2 lines 26-40. Depends on Epic 1. Shipped in `659fca7`. |
| 4 | `validate_output` + repair retry loop | MVP | Done | Validate JSON / `data` key / `person:str` + `info:str`; on failure re-prompt LLM with error + broken JSON, max 3 retries, then raise `Error("Could not respond")`. Pitch: [ARCHITECTURE.md](../ARCHITECTURE.md) §Layers/2 lines 41-48. Depends on Epic 3. Shipped in `7cae758`. |
| 5 | Python render + error surfacing + e2e wiring | MVP | Done | Top-level entrypoint wires Epics 2→3→4; render validated JSON; catch `Error("Could not respond")` and show user message + retry instruction. Pitch: [ARCHITECTURE.md](../ARCHITECTURE.md) §Layers/1 lines 23-24, §Data flow, §Tests/E2E. Depends on Epics 2, 4. Spec: [specs/modules/render/spec.md](modules/render/spec.md). Shipped in `8f31747`. |
| 6 | DeepEval LLM-judge eval suite | MVP | Done | `tests/eval/` runs DeepEval with Gemini 2.0 Flash judge against three criteria: valid JSON shape, `person` matches input, `info` non-empty or `"<Not found>"`. Pitch: [ARCHITECTURE.md](../ARCHITECTURE.md) §Tests/LLM evaluation. Depends on Epics 3, 4. Spec: [specs/modules/eval/spec.md](modules/eval/spec.md). Shipped in `347f8a4`. The live-judge follow-up (Gemini SDK install + AnswerCorrectness or similar judge-driven metric) is intentionally deferred per `specs/modules/eval/spec.md` NF3. |

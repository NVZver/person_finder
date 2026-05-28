# Test Suites: LangChain ReAct Agent + `findPerson` Tool

Every AC from [requirements.md](./requirements.md) appears in at least one Journey's `**Covers:**` line. The unit tier is exhaustive here per [testing.md](../../standards/testing.md) §Unit (all externals mocked); eval and e2e for this surface are owned by Epics 6 and 5 respectively.

## Journey: Enrich a name list

**Goal:** Get an enrichment string for a list of person names.
**Covers:** AC1, AC3, AC4

**Paths:**
| # | Path | Actions |
|---|------|---------|
| 1 | Happy | caller passes `list[str]` → agent runs with `findPerson` bound → `enrich_names` returns the LLM's final-message content string verbatim |
| 2 | Tool stub | `findPerson.invoke({"name": "<any>"})` called directly → returns `"<Not found>"` |
| 3 | Wiring check | `build_agent(model=<fake>)` called → recorded call to `create_agent` has `findPerson` in `tools` AND `system_prompt` containing the contract phrase ("JSON object") |

**Expected outcome:** Caller receives a string (happy); the stub tool returns `"<Not found>"` verbatim (tool stub); `create_agent` receives the correct `tools` list and `system_prompt` (wiring check).

## Journey: Fail loud when GROQ_API_KEY is missing or blank

**Goal:** Surface misconfiguration before any network call.
**Covers:** AC2

**Paths:**
| # | Path | Actions |
|---|------|---------|
| 1 | Missing key | env has no `GROQ_API_KEY`; no `.env` in cwd → `build_agent()` (default model) → raises `pydantic.ValidationError` |
| 2 | Blank key | env has `GROQ_API_KEY=""` → `build_agent()` → raises `pydantic.ValidationError` |

**Expected outcome:** `pydantic.ValidationError` raised before any HTTP attempt; developer sees a clear misconfig signal.

## Journey: Import the module without side effects

**Goal:** Import `person_finder.agent` in any context (tests, sub-tools, REPL) without triggering Settings validation or network.
**Covers:** AC5

**Paths:**
| # | Path | Actions |
|---|------|---------|
| 1 | Bare import | `python -c "import person_finder.agent"` with no env vars set → import succeeds, exit 0 |

**Expected outcome:** Import completes silently; no env read, no disk read, no exception.

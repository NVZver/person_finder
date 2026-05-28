# Feature: LangChain ReAct Agent + `findPerson` Tool

Epic source: [roadmap.md](../../roadmap.md) row 3 (MVP). Constitution: [ARCHITECTURE.md](../../../ARCHITECTURE.md) §Layers/2, §Stack. Inherited contracts: [main.spec.md](../../main.spec.md) §Cross-Module Contracts.

## Summary

Provide the `agent` module that maps a `list[str]` of `"First Last"` names to the LLM's raw final-message string by running a LangChain ReAct loop over Groq Llama 3.3 70B with a single bound tool `findPerson(name)->str`. Output is returned verbatim — no parsing, validation, repair, or rendering. Validation/repair (Epic 4), rendering (Epic 5), and DeepEval suite (Epic 6) are explicitly out of scope.

## Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| F1 | The `agent` module exposes `enrich_names(names: list[str], *, model=None) -> str` that runs the LangChain agent and returns the LLM's final-message content verbatim. | Must |
| F2 | A `findPerson(name: str) -> str` callable is registered as a LangChain tool on the agent. Stub returns the literal `"<Not found>"`; a real lookup (web search, etc.) is deferred to [research-backlog.md](../../research-backlog.md). | Must |
| F3 | The agent's default LLM is `ChatGroq(model="llama-3.3-70b-versatile", temperature=0)`. Model name is pinned in code; no environment override. | Must |
| F4 | The agent's system prompt instructs the LLM to return ONLY a JSON object shaped `{"data":[{"person": str, "info": str}]}`, use the literal `"<Not found>"` when no info is available, and emit no prose or markdown fences. | Must |
| F5 | The agent is constructed via `langchain.agents.create_agent(model, tools=[findPerson], system_prompt=...)` (LangChain 1.x API) and invoked through `.invoke({"messages":[{"role":"user","content":...}]})`. | Must |
| F6 | `build_agent` and `enrich_names` accept a `model` keyword argument as an injection seam so unit tests can pass a fake without monkey-patching `ChatGroq`. | Must |

## Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NF1 | The Groq API key flows through `person_finder.config.get_settings().groq_api_key`, passed explicitly to `ChatGroq(api_key=...)`. Missing/blank key raises `pydantic.ValidationError` BEFORE any HTTP call. (Inherits [scaffolding/spec.md](../../modules/scaffolding/spec.md) NF3.) |
| NF2 | `import person_finder.agent` must NOT read env, hit disk, or raise. Settings access happens only inside `_default_model()` / `build_agent()` when `model=None`. (Inherits [scaffolding/spec.md](../../modules/scaffolding/spec.md) NF5.) |
| NF3 | Unit tests in `tests/unit/test_agent.py` mock every external call (LLM HTTP, agent runtime). No real Groq network call from the unit tier. (Per [testing.md](../../standards/testing.md) §Unit.) |
| NF4 | `langchain` and `langchain-groq` are pinned to major version `1.x` in `pyproject.toml` (`>=1,<2`). The legacy `create_react_agent` + `AgentExecutor` pattern is not used. |

## Inputs & Outputs

- **Input:** `list[str]` of `"First Last"` names. Produced by Epic 2 (`fetch` module) in production.
- **Output:** raw final-message content string from the LangChain agent run. Expected shape `{"data":[{"person": str, "info": str}]}` per [main.spec.md](../../main.spec.md) §Cross-Module Contracts, but **not enforced here** (Epic 4 owns validation).
- **Side effects:** outbound HTTPS calls to Groq (production only). None in unit tests.

## Constraints

- LangChain 1.x API: `from langchain.agents import create_agent`, `from langchain.tools import tool`, `from langchain_groq import ChatGroq`. ([code.md](../../standards/code.md) §Stack; current stable `langchain-groq` is 1.1.2.)
- ChatGroq constructed with explicit `api_key=...`, never relying on ambient `os.environ`. ([scaffolding/spec.md](../../modules/scaffolding/spec.md) NF3.)
- All external calls mocked in `tests/unit/`. ([testing.md](../../standards/testing.md) §Unit.)

## Out of Scope

- Output JSON parsing, schema validation, repair-retry loop, `Error("Could not respond")` — **Epic 4** (`validation` module).
- Top-level Python entrypoint that wires Epic 2 → Epic 3 → Epic 4 and surfaces errors to the user — **Epic 5** (`render` module).
- DeepEval LLM-judge suite under `tests/eval/` — **Epic 6**.
- A real `findPerson` implementation (web search, knowledge graph) — deferred to [research-backlog.md](../../research-backlog.md).
- End-to-end tests that hit the real Groq API — **Epic 5** and downstream.

## Acceptance Criteria

<!-- Each AC: (a) journey-shaped per VISION §2.2a — user-observable at the user/system boundary (here the boundary is the Python caller of `person_finder.agent`); (b) EARS-form. -->

- [ ] **AC1** (State+Event): While `GROQ_API_KEY` is present and non-blank, when `enrich_names(names)` is called with a non-empty `list[str]`, the system shall return a `str` (the LLM's final-message content) without raising.
- [ ] **AC2** (State+Event): While `GROQ_API_KEY` is missing or blank, when `build_agent()` is called with no model override, the system shall raise `pydantic.ValidationError` before initiating any network request.
- [ ] **AC3** (Event): When `build_agent(model=<injected>)` is called, the system shall pass `findPerson` in the `tools` list and the canonical `SYSTEM_PROMPT` as the `system_prompt` argument to `langchain.agents.create_agent`.
- [ ] **AC4** (Event): When `findPerson` is invoked with any name string, the system shall return the literal `"<Not found>"`.
- [ ] **AC5** (Event): When `import person_finder.agent` runs, the system shall not read environment variables, read disk, or raise.

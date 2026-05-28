# Agent Module — Spec

## Purpose

Provide the `agent` module: a LangChain 1.x ReAct agent over Groq Llama 3.3 70B with a single bound `findPerson(name)->str` tool that maps a `list[str]` of `"First Last"` names to the LLM's raw final-message content (expected JSON-shaped `{"data":[{"person": str, "info": str}]}`). The module returns the string verbatim — parsing, validation, repair-retry, and rendering are out of scope and owned by downstream modules per the cross-module contracts.

Pitch source: [ARCHITECTURE.md](../../../ARCHITECTURE.md) §Layers/2.
Epic: [roadmap.md](../../roadmap.md) row 3 ('LangChain ReAct agent + findPerson tool', MVP).
Inherited contracts: [main.spec.md](../../main.spec.md) §Cross-Module Contracts.

## Scope (artifact paths)

- `src/person_finder/agent.py`
- `tests/unit/test_agent.py`

## Functional requirements

- **F1 — Public enrichment entry point.** The module exposes `enrich_names(names: list[str], *, model=None) -> str` that runs the LangChain agent over the supplied names and returns the LLM's final-message content verbatim, without parsing or validation.
- **F2 — `findPerson` tool registration.** A `findPerson(name: str) -> str` callable is registered as a LangChain tool on the agent. The MVP stub returns the literal `"<Not found>"`; the real lookup (web search, knowledge graph, etc.) is deferred to [research-backlog.md](../../research-backlog.md).
- **F3 — Pinned default LLM.** The agent's default LLM is `ChatGroq(model="llama-3.3-70b-versatile", temperature=0)`. The model name is pinned in code and not overridable via environment variables.
- **F4 — Canonical system prompt.** The system prompt instructs the LLM to return ONLY a JSON object shaped `{"data":[{"person": str, "info": str}]}`, to use the literal `"<Not found>"` when no info is available, and to emit no prose or markdown fences.
- **F5 — LangChain 1.x construction path.** The agent is built via `langchain.agents.create_agent(model, tools=[findPerson], system_prompt=...)` and invoked through `.invoke({"messages":[{"role":"user","content":...}]})`. The legacy `create_react_agent` + `AgentExecutor` pattern is not used.
- **F6 — Model injection seam.** Both `build_agent` and `enrich_names` accept a `model` keyword argument so unit tests can inject a fake LLM without monkey-patching `ChatGroq`.
- **F7 — Repair helper.** The module exposes `repair(broken_raw: str, error_msg: str, *, model: Any | None = None) -> str` — a one-shot LLM call (no ReAct loop, no tool calls) that wraps the validation-module repair-callable contract from [validation/spec.md F4](../validation/spec.md). Uses module-level `REPAIR_SYSTEM_PROMPT`. Default model constructed lazily via `_default_model()` to preserve NF2.

## Non-functional requirements / invariants

- **NF1 — Explicit Groq key flow.** The Groq API key flows through `person_finder.config.get_settings().groq_api_key` and is passed explicitly to `ChatGroq(api_key=...)`. Missing or blank keys raise `pydantic.ValidationError` BEFORE any HTTP call. (Inherits [scaffolding/spec.md](../scaffolding/spec.md) NF3.)
- **NF2 — Side-effect-free import.** `import person_finder.agent` MUST NOT read environment variables, read disk, or raise. Settings access happens only inside `_default_model()` / `build_agent()` when `model=None`. (Inherits [scaffolding/spec.md](../scaffolding/spec.md) NF5.)
- **NF3 — Fully mocked unit tier.** Unit tests in `tests/unit/test_agent.py` mock every external collaborator (LLM HTTP, agent runtime). No real Groq network call may originate from the unit tier. (Per [testing.md](../../standards/testing.md) §Unit.)
- **NF4 — LangChain 1.x version pin.** `langchain` and `langchain-groq` are pinned to major version `1.x` in `pyproject.toml` (`>=1,<2`). Any drift back to LangChain 0.x APIs is a regression.

## Acceptance criteria

- **AC1** — While `GROQ_API_KEY` is present and non-blank, when `enrich_names(names)` is called with a non-empty `list[str]`, the system returns a `str` (the LLM's final-message content) without raising. Currently verified by `test_enrich_names_returns_final_message_content` in `tests/unit/test_agent.py`.
- **AC2** — While `GROQ_API_KEY` is missing or blank, when `build_agent()` is called with no model override, the system raises `pydantic.ValidationError` before initiating any network request. Currently verified by `test_build_agent_default_model_requires_groq_api_key` in `tests/unit/test_agent.py`.
- **AC3** — When `build_agent(model=<injected>)` is called, the system passes `findPerson` in the `tools` list and the canonical `SYSTEM_PROMPT` as the `system_prompt` argument to `langchain.agents.create_agent`. Currently verified by `test_build_agent_passes_injected_model_through` in `tests/unit/test_agent.py`.
- **AC4** — When `findPerson` is invoked with any name string, the system returns the literal `"<Not found>"`. Currently verified by `test_find_person_stub_returns_not_found` in `tests/unit/test_agent.py`.
- **AC5** — When `import person_finder.agent` runs, the system does not read environment variables, read disk, or raise. Currently verified by `test_import_has_no_side_effects` in `tests/unit/test_agent.py`.
- **AC6** — When `repair(broken_raw, error_msg, model=<injected>)` is called, the system invokes the injected model with the canonical `REPAIR_SYSTEM_PROMPT` + a user message containing `error_msg` and `broken_raw`, and returns the model's `.content` verbatim. Currently verified by `test_repair_invokes_model_and_returns_content_string` in `tests/unit/test_agent.py`.

## Open questions / follow-ups

| # | Question | Source |
|---|---|---|
| OQ1 | Real `findPerson` implementation (web search vs. knowledge graph vs. other) — deferred to [research-backlog.md](../../research-backlog.md). | F2 stub policy. |
| OQ2 | Token / cost ceiling on Groq calls — not specified in [ARCHITECTURE.md](../../../ARCHITECTURE.md). | Operational concern. |
| OQ3 | Whether `temperature` should be exposed as a parameter (currently pinned to 0). | F3. |

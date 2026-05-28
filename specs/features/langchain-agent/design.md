# Design: LangChain ReAct Agent + `findPerson` Tool

## Modules Affected

| Module | Change Type |
|--------|-------------|
| `agent` | new — to be registered in `.lsa.yaml` and given `specs/modules/agent/spec.md` via `lsa:reconcile` after this feature lands |
| `scaffolding` | read-only — `agent` inherits `person_finder.config.get_settings()` and the conftest isolation fixture |

## Technical Approach

Per [ARCHITECTURE.md](../../../ARCHITECTURE.md) §Layers/2 and [code.md](../../standards/code.md) §Layer boundaries — a LangChain ReAct agent over Groq Llama 3.3 70B, single bound tool.

**Library API (LangChain 1.x):**

- `from langchain.agents import create_agent` — current 1.x API; returns a Runnable that owns the ReAct loop internally. The legacy `create_react_agent` + `AgentExecutor` pair is NOT used.
- `from langchain.tools import tool` — `@tool`-decorated functions become tools; the docstring becomes the LLM-visible description.
- `from langchain_groq import ChatGroq` — model wrapper, instantiated with explicit `api_key` from `get_settings()`.

**Module shape** (`src/person_finder/agent.py`):

```
SYSTEM_PROMPT: str                                   # canonical agent instructions
@tool findPerson(name: str) -> str                   # stub returns "<Not found>"
_default_model() -> ChatGroq                         # threads api_key from get_settings
build_agent(model=None) -> Runnable                  # injection seam for tests
enrich_names(names: list[str], *, model=None) -> str
```

`build_agent(model=None)` delegates to `_default_model()`, which calls `get_settings()` — that's where the fail-loud contract from [scaffolding/spec.md](../../modules/scaffolding/spec.md) NF3 fires (covers AC2). Tests inject a fake model to bypass.

**Invocation pattern:**

```python
agent = build_agent(model=model)
user_msg = "Look up information for these people:\n" + "\n".join(f"- {n}" for n in names)
result = agent.invoke({"messages": [{"role": "user", "content": user_msg}]})
return result["messages"][-1].content
```

The user message is a deterministic template built from the input list — it does NOT call into the LLM to format names.

**System prompt design:** instructs the LLM to (a) call `findPerson` once per name, (b) return ONLY a JSON object matching the contract schema, (c) use `"<Not found>"` when no info, (d) emit no prose or markdown fences. The "JSON-only output" constraint here is best-effort — actual format-validation belongs to Epic 4. This module returns whatever the LLM produced.

## Data Model Changes

none

## API / Interface Changes

Module-internal Python signatures only — no HTTP, no DB, no inter-process surface:

- `enrich_names(names: list[str], *, model: Any | None = None) -> str` — consumed by Epic 5 (`render` module, top-level entrypoint).
- `findPerson(name: str) -> str` — bound as a LangChain tool. Not called directly by other modules.
- `build_agent(model: Any | None = None) -> Runnable` — internal, exposed for test injection.

## Cross-Module Contracts

Inherits the four contracts from [main.spec.md](../../main.spec.md) §Cross-Module Contracts unchanged:

- **Name list** (Python → Agent): `list[str]` of `"First Last"` strings — consumed as input.
- **Enrichment result** (Agent → Python): `{"data":[{"person": str, "info": str}]}` — emitted as a raw string; format enforcement is Epic 4's job.
- **Tool**: `findPerson(name: str) -> str` — provided.
- **Failure signal** (`Error("Could not respond")`): NOT provided by this module — Epic 4 raises it after exhausting repair retries.

No new contract introduced.

## Open Questions

| # | Question | Source |
|---|---|---|
| OQ1 | Real `findPerson` implementation (web search vs. knowledge graph vs. retrieval over a corpus) — deferred to [research-backlog.md](../../research-backlog.md). | F2 stub policy. |
| OQ2 | Token / cost ceiling on Groq calls — not specified in [ARCHITECTURE.md](../../../ARCHITECTURE.md). Revisit before any deployment that runs against a paid quota. | Operational concern. |
| OQ3 | Whether `temperature` should be exposed as a parameter — currently pinned to 0 in `_default_model()` for determinism. | F3. |

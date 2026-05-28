# person_finder — Main Spec

## Purpose

A minimal, production-style Python application that fetches random user data, runs a LangChain ReAct agent to enrich each person with publicly available information, and returns a validated, structured JSON result.

Source: [README.md](../README.md), [ARCHITECTURE.md](../ARCHITECTURE.md).

## Module Index

| Module | Spec | Status |
|--------|------|--------|
| scaffolding | [modules/scaffolding/spec.md](modules/scaffolding/spec.md) | active |
| users | [modules/users/spec.md](modules/users/spec.md) | active |
| agent | [modules/agent/spec.md](modules/agent/spec.md) | active |
| validation | [modules/validation/spec.md](modules/validation/spec.md) | active |
| eval | [modules/eval/spec.md](modules/eval/spec.md) | active |

Future modules (candidates from [ARCHITECTURE.md](../ARCHITECTURE.md) §Layers, to be confirmed at each feature): `render` (top-level entrypoint + error surfacing, Epic 5).

## Cross-Module Contracts

- **Name list** (Python → Agent): `list[str]` of `"First Last"` strings.
- **Enrichment result** (Agent → Python): `{ "data": [{ "person": str, "info": str }] }`. Missing info → `"<Not found>"`.
- **Agent tool**: `findPerson(name: str) -> str`.
- **Failure signal** (Agent → Python): `Error("Could not respond")` after 3 repair retries exhaust.

Source: [ARCHITECTURE.md:23-49](../ARCHITECTURE.md).

## Non-Functional Requirements

- **Validation**: agent output must be valid JSON with `data[].person:str` and `data[].info:str`; up to 3 LLM repair attempts before failing. ([ARCHITECTURE.md:41-48](../ARCHITECTURE.md))
- **Input filtering**: drop users born after 2000 before enrichment. ([ARCHITECTURE.md:19-22](../ARCHITECTURE.md))
- **Test pyramid**: unit (mocked), LLM eval (DeepEval + Gemini 2.0 Flash judge), e2e (no mocks). ([ARCHITECTURE.md:82-103](../ARCHITECTURE.md))
- **Secrets**: `GROQ_API_KEY`, `GOOGLE_API_KEY` via env. ([ARCHITECTURE.md:117-122](../ARCHITECTURE.md))

# Code Standards

Extracted from [ARCHITECTURE.md](../../ARCHITECTURE.md).

## Stack

| Component | Choice |
|---|---|
| Language | Python |
| Agent framework | LangChain |
| LLM | Groq — Llama 3.3 70B |
| Judge model | Gemini 2.0 Flash (Google AI Studio) |

## Layer boundaries

1. **Python layer** — fetch (`randomuser.me/api`, 20 users), filter (drop born-after-2000), map to `["First Last"]`, hand off to agent, render validated JSON, surface `"Could not respond"` errors to the user with retry instruction.
2. **LangChain agent layer** — ReAct loop with Chain-of-Thought; system prompt defines goal, output schema, and `<Not found>` fallback; single tool `findPerson(name: str) -> str`; `validate_output` runs **after** the loop, not inside it.
3. **Groq — Llama 3.3 70B** — receives prompts, tool calls, repair requests; returns completions.

## Output contract

```
{ "data": [{ "person": str, "info": str }] }
```

- `person` must match an input list entry.
- `info` is a non-empty string or the literal `"<Not found>"`.

## Validation & retry

- `validate_output` checks: valid JSON, `data` key present, each item has `person:str` and `info:str`.
- On failure: send error + broken JSON back to LLM for repair.
- Max retries: **3**.
- On limit: raise `Error("Could not respond")`. Python layer catches, shows user message with retry instruction.

## Environment variables

```
GROQ_API_KEY=       # https://console.groq.com
GOOGLE_API_KEY=     # https://aistudio.google.com
```
